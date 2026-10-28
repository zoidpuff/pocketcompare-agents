"""``pocketcompare`` command line: describe pockets, compare them, build and search FAISS indices.

    pocketcompare describe STRUCTURE|DIR ... -o pockets.parquet [--af-mode] [--workers 8] [--device cuda:0]
    pocketcompare describe 1abc.cif.gz --ligand lig.sdf -o site.parquet          # one ligand-defined site
    pocketcompare describe 1abc.cif.gz --residues A:43,A:45 --locate burrow -o d.parquet   # BURROW pocket at a site
    pocketcompare compare a.parquet b.parquet [--top 5] [-o pairs.tsv] [--matrix S.npy]
    pocketcompare index pockets.parquet -o idx/ [--kind flat|ivfpq] [--nlist N]        # needs [search] extra
    pocketcompare search query.parquet idx/ [-k 10] [--rerank 100] [-o hits.parquet]  # needs [search] extra
    python -m pocketcompare ...                                                   # same

``describe`` without a site describes every pocket of each structure (``method.describe_all``: merged BURROW
region-rule pockets with >= 10 points); with ``--ligand``/``--residues`` one site per structure.  Output: one row
per pocket with id, BURROW score, residues, centre, volume, pLDDT stats (``--af-mode``) and the 384-d fingerprint
(see ``pocketcompare.fpindex`` for the table format); ``--n1`` also stores the raw 627-d N1 descriptor (needed to
retrain the head, ``scripts/train_head.py``).  BURROW backends: ``ref`` (reference implementation, the one the
method was evaluated with), ``fast`` (BURROW's Numba CPU path) and ``--device cuda:N`` (BURROW's batched GPU
featurisation, needs ``torch``/``triton``); they give identical pockets and fingerprints.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

STRUCT_SUFFIXES = (".pdb", ".ent", ".cif", ".mmcif", ".pdb.gz", ".ent.gz", ".cif.gz", ".mmcif.gz", ".bcif")
_SINGLE = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS")}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def is_structure(p: Path) -> bool:
    n = p.name.lower()
    return any(n.endswith(s) for s in STRUCT_SUFFIXES)


def stem_of(p: Path) -> str:
    n = p.name
    for s in sorted(STRUCT_SUFFIXES, key=len, reverse=True):
        if n.lower().endswith(s):
            return n[:-len(s)]
    return p.stem


def find_structures(inputs) -> list[Path]:
    out = []
    for x in inputs:
        p = Path(x)
        if p.is_dir():
            out += sorted(f for f in p.rglob("*") if f.is_file() and is_structure(f))
        elif p.is_file():
            out.append(p)
        else:
            raise FileNotFoundError(x)
    return out


# ============================================================================================ describe (one structure)
_W: dict = {}


def _worker_init(single_thread: bool = True):
    if single_thread:
        os.environ.update(_SINGLE)
        try:
            import numba
            numba.set_num_threads(1)
        except Exception:  # noqa: BLE001
            pass
    from . import method
    _W["m"] = method.default()


def _method():
    if "m" not in _W:
        from . import method
        _W["m"] = method.default()
    return _W["m"]


def _empty(n1: bool):
    d = _method().dim
    return pd.DataFrame(), np.zeros((0, d), np.float32), (np.zeros((0, 627), np.float32) if n1 else None)


def _plddt_of_structure(s) -> dict:
    from pocketdetect.burrow.af import residue_plddt
    sp = s.select(s.protein_heavy_mask())
    return dict(zip(sp.residue_ids.tolist(), residue_plddt(sp).astype(float).tolist()))


def _plddt_stats(residues: str, pld: dict | None) -> dict:
    if not pld:
        return {"plddt_mean": np.nan, "plddt_min": np.nan, "plddt_frac_lt70": np.nan}
    v = np.array([pld[r] for r in residues.split() if r in pld], float)
    if not len(v):
        return {"plddt_mean": np.nan, "plddt_min": np.nan, "plddt_frac_lt70": np.nan}
    return {"plddt_mean": float(v.mean()), "plddt_min": float(v.min()), "plddt_frac_lt70": float((v < 70).mean())}


def featurize(path: Path, opt: dict):
    """(Featurized, pLDDT dict | None, timings) with the CPU backends (ref | fast)."""
    from . import pockets as pk
    from . import pockets_fast as pf
    t0 = time.perf_counter()
    chains = opt.get("chains")
    if opt["backend"] == "fast":
        from pocketdetect.burrow.fast.pipeline import featurize as ffeat
        P, w, pld, _ = pf.load_protein_af(path, stem_of(path), opt["af_mode"], chains)
        t1 = time.perf_counter()
        ps = ffeat(P, pf.fast_model().cfg, w)
        fs = pf.featurized_from_points(P, ps, None, pf.fast_model(), stem_of(path), opt["af_mode"])
    else:
        from pocketdetect.structure import load_structure
        s = load_structure(str(path), structure_id=stem_of(path), chains=list(chains) if chains else None)
        pld = _plddt_of_structure(s)
        t1 = time.perf_counter()
        try:
            fs = pk.featurize_structure(s, af_mode=opt["af_mode"], key=stem_of(path))
        except ValueError as e:
            # AF-mode pLDDT pruning removed every residue: no pocket (the fast backend returns 0 pockets too)
            if not (opt["af_mode"] and "no protein heavy atoms" in str(e) and s.protein_heavy_mask().any()):
                raise
            fs = None
    return fs, pld, {"parse_s": t1 - t0, "burrow_s": time.perf_counter() - t1}


def describe_featurized(fs, path: Path, pld: dict | None, opt: dict, tim: dict):
    """(rows, fingerprints, raw N1 | None) of one featurised structure."""
    m = _method()
    t0 = time.perf_counter()
    stem = stem_of(path)
    pld = pld if opt["af_mode"] else None
    site = opt.get("site")
    want_n1 = bool(opt.get("n1"))
    if site is None:
        V, info, N = m.describe_all(fs, unit=opt.get("unit", "merged"), min_points=opt.get("min_points", 10),
                                    return_n1=True)
        info = info.drop(columns=["time_ms"], errors="ignore")
        if not len(info):
            tim["describe_s"] = time.perf_counter() - t0
            return info, V, (N if want_n1 else None)
        key = "merged_index" if "merged_index" in info else "member_index"
        info.insert(0, "pocket_id", [f"{stem}:{'m' if key == 'merged_index' else 'p'}{k}" for k in info[key]])
        info.insert(1, "mode", "D")
    else:
        from . import pockets as pk
        V, info, N = m.describe(fs, site=site, locate=opt.get("locate", "shell"), return_info=True, return_n1=True)
        info = info.drop(columns=["time_ms"], errors="ignore")
        base = _site_base(fs, site, opt.get("locate", "shell"), info)
        c = pk.buried_centroid(fs, base)
        sph = pk.shape_site(fs, base, "sph8")
        info["center_x"], info["center_y"], info["center_z"] = (float(x) for x in c)
        info["site_n_points"], info["site_volume_A3"] = int(len(sph)), fs.volume(sph)
        info["sph8_fallback"] = bool(len(sph) == 0)
        info["residues"] = " ".join(fs.residues_near(base))
        info.insert(0, "pocket_id", f"{stem}:site")
    if len(info):
        st = pd.DataFrame([_plddt_stats(r, pld) for r in info.residues])
        info = pd.concat([info.reset_index(drop=True), st], axis=1)
        info.insert(1, "structure", str(path))
        info.insert(2, "structure_stem", stem)
    tim["describe_s"] = time.perf_counter() - t0
    return info, V, (N if want_n1 else None)


def _site_base(fs, site, locate, info):
    """The located point set of a single-site describe (for centre / residues in the output table)."""
    from . import pockets as pk
    if locate in ("burrow", "burrow_flat"):
        return np.asarray(fs.pocket_idx(int(info.burrow_index.iloc[0])), np.int64)
    if isinstance(site, (str, Path)):
        return pk.lmode_from_ligand(fs, pk.read_ligand_heavy_atoms(site)[0]).idx
    if isinstance(site, (list, tuple)) and len(site) and isinstance(site[0], str):
        return pk.lmode_from_residues(fs, list(site)).idx
    return pk.lmode_from_ligand(fs, np.asarray(site, np.float64).reshape(-1, 3)).idx


def describe_one(args):
    """CPU task: one structure end to end -> (rows, V, N1 | None, structure record)."""
    path, opt = args
    t0 = time.perf_counter()
    rec = {"structure": str(path), "status": "ok", "error": ""}
    try:
        fs, pld, tim = featurize(Path(path), opt)
        if fs is None:
            info, V, N = _empty(opt.get("n1"))
            rec["note"] = "AF pruning removed all residues: no pocket"
        else:
            info, V, N = describe_featurized(fs, Path(path), pld, opt, tim)
        rec.update(tim, n_pockets=int(len(info)))
    except Exception as e:  # noqa: BLE001
        info, V, N = _empty(opt.get("n1"))
        rec.update(status="error", error=f"{type(e).__name__}: {e}"[:300], n_pockets=0)
    rec["total_s"] = time.perf_counter() - t0
    return info, V, N, rec


# ---- GPU backend: CPU workers parse/prep and post-process, the main process featurises batches on the GPU
def _gpu_prep(args):
    path, opt = args
    from . import pockets_fast as pf
    t0 = time.perf_counter()
    try:
        it, info = pf.load_and_prep(path, stem_of(Path(path)), af_mode=opt["af_mode"], chains=opt.get("chains"))
        info["t0"] = t0
        return path, it, info, None
    except Exception as e:  # noqa: BLE001
        return path, None, {"parse_s": time.perf_counter() - t0}, f"{type(e).__name__}: {e}"[:300]


def _gpu_post(args):
    path, P, ps, score, info, opt = args
    from . import pockets_fast as pf
    t0 = time.perf_counter()
    rec = {"structure": str(path), "status": "ok", "error": "", "parse_s": info["parse_s"] + info["prep_s"],
           "gpu_s": info["gpu_s"]}
    try:
        fs = pf.featurized_from_points(P, ps, score, pf.fast_model(), stem_of(Path(path)), opt["af_mode"])
        rec["burrow_s"] = time.perf_counter() - t0
        tim = {}
        out, V, N = describe_featurized(fs, Path(path), info["plddt"], opt, tim)
        rec.update(tim, n_pockets=int(len(out)))
    except Exception as e:  # noqa: BLE001
        out, V, N = _empty(opt.get("n1"))
        rec.update(status="error", error=f"{type(e).__name__}: {e}"[:300], n_pockets=0)
    rec["total_s"] = rec["parse_s"] + rec["gpu_s"] + time.perf_counter() - t0
    return out, V, N, rec


def _gpu_error(path, err, opt):
    return (*_empty(opt.get("n1")), {"structure": path, "status": "error", "error": err, "n_pockets": 0})


def run_gpu(paths, opt, device, workers, batch):
    import multiprocessing as mp
    from collections import deque
    from pocketdetect.burrow.fast.gpu import featurize_batch
    from . import pockets_fast as pf
    fm = pf.fast_model()
    results = []
    tasks = [(str(p), opt) for p in paths]
    if workers <= 0:                                   # in-process (tests, latency)
        _worker_init(single_thread=False)
        for t in tasks:
            path, it, info, err = _gpu_prep(t)
            if err:
                results.append(_gpu_error(path, err, opt))
                continue
            t0 = time.perf_counter()
            (ps, sc), = featurize_batch([it], fm.cfg, device, fm)
            info["gpu_s"] = time.perf_counter() - t0
            results.append(_gpu_post((path, it.P, ps, sc, info, opt)))
        return results
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, initializer=_worker_init) as pool:
        prep = pool.imap(_gpu_prep, tasks, chunksize=1)
        post = deque()
        buf = []

        def flush():
            t0 = time.perf_counter()
            res = featurize_batch([b[1] for b in buf], fm.cfg, device, fm)
            dt = time.perf_counter() - t0
            for (path, it, info), (ps, sc) in zip(buf, res):
                info["gpu_s"] = dt / len(buf)
                post.append(pool.apply_async(_gpu_post, ((path, it.P, ps, sc, info, opt),)))
            buf.clear()

        for path, it, info, err in prep:
            if err:
                results.append(_gpu_error(path, err, opt))
                continue
            buf.append((path, it, info))
            if len(buf) >= batch:
                flush()
            while post and post[0].ready():
                results.append(post.popleft().get())
        if buf:
            flush()
        while post:
            results.append(post.popleft().get())
    return results


def describe_paths(paths, opt, workers=1, device="cpu", batch=16):
    """[(rows DataFrame, V, N1 | None, structure record)] for a list of structure files."""
    if device.startswith("cuda"):
        return run_gpu(paths, opt, device, workers, batch)
    tasks = [(str(p), opt) for p in paths]
    if workers <= 1:
        _worker_init(single_thread=False)
        return [describe_one(t) for t in tasks]
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(workers, initializer=_worker_init) as pool:
        return list(pool.imap(describe_one, tasks, chunksize=1))


def _site_from_args(a):
    if getattr(a, "ligand", None):
        return str(a.ligand)
    if getattr(a, "residues", None):
        from .pockets import parse_residue_list
        toks = [t for t in a.residues.replace(" ", "").split(",") if t]
        if all(":" in t for t in toks):
            return toks
        return parse_residue_list(a.residues)
    return None


def _opt_from_args(a) -> dict:
    site = _site_from_args(a)
    backend = "fast" if a.device.startswith("cuda") else a.backend
    return {"af_mode": bool(a.af_mode), "chains": a.chains.split(",") if a.chains else None, "backend": backend,
            "site": site, "locate": getattr(a, "locate", "shell"), "unit": a.unit, "min_points": a.min_points,
            "n1": bool(getattr(a, "n1", False))}


def cmd_describe(a):
    from . import fpindex as FX
    paths = find_structures(a.inputs)
    if not paths:
        raise SystemExit("no structure files found")
    opt = _opt_from_args(a)
    if opt["site"] is not None and len(paths) > 1:
        log(f"note: the same site ({a.ligand or a.residues}) is applied to all {len(paths)} structures")
    t0 = time.perf_counter()
    res = describe_paths(paths, opt, a.workers, a.device, a.batch)
    wall = time.perf_counter() - t0
    keep = [r for r in res if len(r[0])]
    meta = pd.concat([r[0] for r in keep], ignore_index=True) if keep else pd.DataFrame()
    V = np.vstack([r[1] for r in keep]) if keep else np.zeros((0, _method().dim), np.float32)
    N = (np.vstack([r[2] for r in keep]) if keep else np.zeros((0, 627), np.float32)) if opt["n1"] else None
    rec = FX.method_record(_method())
    rec.update(af_mode=opt["af_mode"], backend=opt["backend"], device=a.device, unit=opt["unit"],
               min_points=opt["min_points"], site=None if opt["site"] is None else str(a.ligand or a.residues),
               locate=opt["locate"])
    FX.write_table(a.out, meta, V, rec, n1=N)
    st = pd.DataFrame([r[3] for r in res])
    st_path = Path(str(a.out).removesuffix(".parquet") + ".structures.parquet")
    st.to_parquet(st_path, index=False)
    n_err = int((st.status != "ok").sum())
    log(f"{len(paths)} structures ({n_err} errors), {len(meta)} pockets -> {a.out}  "
        f"[{wall:.1f} s wall, {wall / len(paths):.3f} s/structure; {a.device}, backend {opt['backend']}, "
        f"{a.workers} workers]")
    for _, r in st[st.status != "ok"].head(10).iterrows():
        log(f"  error {r.structure}: {r.error}")
    return 1 if n_err == len(paths) else 0


# ============================================================================================ compare / index / search
def load_fingerprints(x, a=None) -> tuple[pd.DataFrame, np.ndarray]:
    """A fingerprint parquet, or a structure file (described on the fly with ``a``'s describe options)."""
    from . import fpindex as FX
    p = Path(x)
    if p.suffix == ".parquet":
        meta, V, _ = FX.read_table(p)
        return meta, V
    opt = _opt_from_args(a)
    (info, V, _, rec), = describe_paths([p], opt, workers=1, device=a.device)
    if rec["status"] != "ok":
        raise SystemExit(f"{p}: {rec['error']}")
    return info, V


def _ids(meta):
    return meta["pocket_id"].astype(str).to_numpy() if "pocket_id" in meta else np.arange(len(meta)).astype(str)


def cmd_compare(a):
    ma, A = load_fingerprints(a.a, a)
    mb, B = load_fingerprints(a.b, a)
    S = A @ B.T
    ia, ib = _ids(ma), _ids(mb)
    if a.matrix:
        if a.matrix.endswith(".npy"):
            np.save(a.matrix, S)
        else:
            pd.DataFrame(S, index=ia, columns=ib).to_csv(a.matrix, sep="\t" if a.matrix.endswith(".tsv") else ",",
                                                         float_format="%.5f")
    k = min(a.top, S.shape[1])
    rows = []
    for i in range(S.shape[0]):
        o = np.argsort(-S[i], kind="stable")[:k]
        rows += [{"query_id": ia[i], "rank": r + 1, "target_id": ib[j], "score": float(S[i, j])}
                 for r, j in enumerate(o)]
    out = pd.DataFrame(rows)
    if a.out:
        out.to_parquet(a.out, index=False) if a.out.endswith(".parquet") else out.to_csv(a.out, sep="\t", index=False)
    if len(out):
        best = out.sort_values("score", ascending=False).drop_duplicates(["query_id", "target_id"]).head(a.print)
        print(best.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    log(f"similarity matrix {S.shape[0]} x {S.shape[1]}")
    return 0


def cmd_index(a):
    from . import fpindex as FX
    meta, V, rec = FX.read_tables(a.fingerprints)
    info = FX.build_index(V, meta, a.out, kind=a.kind, nlist=a.nlist, m=a.pq_m, bits=a.pq_bits, opq=not a.no_opq,
                          n_train=a.train, seed=a.seed, record=rec, save_vectors=not a.no_vectors,
                          threads=a.threads)
    log(f"{info['factory']} index of {info['n']} pockets -> {a.out} ({info['build_s']:.1f} s; "
        f"{info['index_bytes_per_pocket']:.0f} B/pocket in index.faiss)")
    return 0


def cmd_search(a):
    from . import fpindex as FX
    if a.threads:
        FX._faiss().omp_set_num_threads(a.threads)
    ix = FX.Index(a.index, nprobe=a.nprobe)
    mq, Q = load_fingerprints(a.query, a)
    ok = np.linalg.norm(Q, axis=1) > 0
    qid = _ids(mq)
    t0 = time.perf_counter()
    kk = a.k + 1 if a.exclude_self else a.k
    D, I = ix.search(Q[ok], kk, rerank=a.rerank)
    dt = time.perf_counter() - t0
    hid = _ids(ix.meta)
    rows = []
    for qi, d_, i_ in zip(np.flatnonzero(ok), D, I):
        r = 0
        for s, j in zip(d_, i_):
            if j < 0 or (a.exclude_self and hid[j] == qid[qi]) or r >= a.k:
                continue
            r += 1
            rows.append({"query_id": qid[qi], "rank": r, "score": float(s), "hit_row": int(j)})
    out = pd.DataFrame(rows)
    if len(out):
        hm = ix.meta.add_prefix("hit_").rename(columns={"hit_pocket_id": "hit_id"})
        out = pd.concat([out.reset_index(drop=True), hm.iloc[out.hit_row.to_numpy()].reset_index(drop=True)], axis=1)
    if a.out:
        out.to_parquet(a.out, index=False) if a.out.endswith(".parquet") else out.to_csv(a.out, sep="\t", index=False)
    cols = [c for c in ("query_id", "rank", "score", "hit_id", "hit_structure_stem", "hit_uniprot", "hit_residues")
            if c in out]
    if len(out):
        print(out[cols].head(a.print).to_string(index=False, float_format=lambda v: f"{v:.4f}", max_colwidth=60))
    log(f"{int(ok.sum())} queries ({int((~ok).sum())} zero fingerprints skipped) vs {len(ix.meta)} pockets "
        f"({ix.info['factory']}{', re-ranked top-%d' % a.rerank if ix.compressed and a.rerank else ''}): "
        f"{1e3 * dt / max(ok.sum(), 1):.3f} ms/query")
    return 0


# ============================================================================================ argparse
def _add_describe_opts(p, site=True):
    p.add_argument("--af-mode", action="store_true", help="BURROW AF mode (pLDDT pruning; pLDDT in B-factors)")
    p.add_argument("--chains", default=None, help="comma-separated author chain ids to keep (default: all)")
    p.add_argument("--backend", choices=["ref", "fast"], default="ref",
                   help="CPU BURROW backend: ref (reference implementation) or fast (Numba); identical output")
    p.add_argument("--device", default="cpu", help="cpu | cuda:N (BURROW fast GPU featurisation)")
    p.add_argument("--unit", choices=["merged", "member"], default="merged",
                   help="no-site pocket unit: merged region pockets (default) or every region sub-pocket")
    p.add_argument("--min-points", type=int, default=10, help="drop merged pockets with fewer points (default 10)")
    if site:
        g = p.add_mutually_exclusive_group()
        g.add_argument("--ligand", help="ligand file (.sdf/.mol V2000 or .pdb): describe its site")
        g.add_argument("--residues", help="residue list 'A:43,A:45' or 'A:43,45,46': describe that site")
        p.add_argument("--locate", choices=["shell", "burrow", "burrow_flat"], default="shell",
                       help="site -> described set: shell = the site itself (L mode); burrow = the BURROW pocket "
                            "that covers it, as evaluated (D mode); burrow_flat = without the merge step")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pocketcompare", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    from . import __version__
    ap.add_argument("--version", action="version", version=f"pocketcompare {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("describe", help="structures -> pocket fingerprints (parquet)")
    p.add_argument("inputs", nargs="+", help="structure files (.pdb/.cif[.gz]) or directories (searched recursively)")
    p.add_argument("-o", "--out", required=True, help="output parquet (+ <out>.structures.parquet with timings)")
    _add_describe_opts(p)
    p.add_argument("--n1", action="store_true", help="also store the raw 627-d N1 descriptor (column 'n1')")
    p.add_argument("--workers", type=int, default=1, help="CPU worker processes (GPU: prep/post workers)")
    p.add_argument("--batch", type=int, default=16, help="GPU batch size (structures)")
    p.set_defaults(func=cmd_describe)

    p = sub.add_parser("compare", help="two fingerprint files or structures -> similarity matrix / top pairs")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--top", type=int, default=5, help="top targets per query row in --out (default 5)")
    p.add_argument("--print", type=int, default=20, help="pairs printed (best first)")
    p.add_argument("-o", "--out", help="top pairs (.parquet or .tsv)")
    p.add_argument("--matrix", help="full similarity matrix (.npy, .tsv or .csv)")
    _add_describe_opts(p, site=True)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("index", help="fingerprints -> FAISS index directory (needs faiss)")
    p.add_argument("fingerprints", nargs="+", help="fingerprint parquet file(s) from `describe`")
    p.add_argument("-o", "--out", required=True, help="index directory")
    p.add_argument("--kind", choices=["flat", "ivfpq"], default="flat",
                   help="flat = exact IndexFlatIP; ivfpq = OPQ + IVF-PQ (m-byte codes) + fp16 vectors for re-rank")
    p.add_argument("--nlist", type=int, default=None, help="IVF lists (default ~4 sqrt(n), power of two)")
    p.add_argument("--pq-m", type=int, default=64, help="PQ sub-quantisers (bytes/code at 8 bits; default 64)")
    p.add_argument("--pq-bits", type=int, default=8)
    p.add_argument("--no-opq", action="store_true")
    p.add_argument("--train", type=int, default=100_000, help="training sample size")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--no-vectors", action="store_true", help="do not store fp16 vectors (no exact re-rank)")
    p.add_argument("--threads", type=int, default=None)
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("search", help="query fingerprints (or a structure) vs an index -> top-k (needs faiss)")
    p.add_argument("query", help="fingerprint parquet or a structure file")
    p.add_argument("index", help="index directory from `index`")
    p.add_argument("-k", type=int, default=10)
    p.add_argument("--nprobe", type=int, default=None, help="IVF lists probed (default: index.json, 64)")
    p.add_argument("--rerank", type=int, default=100, help="compressed index: exact re-rank of the top-N (0 = off)")
    p.add_argument("--exclude-self", action="store_true", help="drop hits with the query's pocket_id")
    p.add_argument("--print", type=int, default=20)
    p.add_argument("-o", "--out", help="hits (.parquet or .tsv)")
    p.add_argument("--threads", type=int, default=None)
    _add_describe_opts(p, site=True)
    p.set_defaults(func=cmd_search)
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return int(a.func(a) or 0)


if __name__ == "__main__":
    sys.exit(main())
