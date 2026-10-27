#!/usr/bin/env python
"""AlphaFold-vs-holo robustness evaluation (claim C5, REPORTED not confirmatory; PREREG §3, DESIGN §2.6).

    python scripts/eval_af_robustness.py --set val              # BLiPS-val v2 sites with an AF model (dev)
    python scripts/eval_af_robustness.py --set train --max-sites 600   # sample of BLiPS-train sites (if val is small)
    FINAL_EVAL=1 python scripts/eval_af_robustness.py --set test --pairs <BLiPS-test pairs parquet>   # PI / final_eval

The script is dataset-agnostic: an *adapter* returns ``(sites, pairs)``.

sites (one row per site that has BOTH a holo-chain pocket and an AF-model pocket of the same site)
    site_id, group_id (homology group = bootstrap unit), role ('val' | 'partner' | 'test' | 'train'),
    holo_cache, holo_structure, holo_chains, holo_lig   (holo Featurized npz [built if missing]; ligand heavy-atom xyz)
    af_cache,   af_structure,   af_lig                   (AF-mode Featurized npz; transferred ligand xyz)
    af_plddt (site mean pLDDT), release_date (holo, first PDB release), site_cluster (label-ligand cluster, optional)
pairs (ligand-sharing labels; optional)
    site_a, site_b, label, pair_cluster, group_a, group_b, site_cluster_a, site_cluster_b

What is computed (fixed before the first run; mode L = ligand shell of the (transferred) ligand, mode D = the
BURROW region-rule pocket that best covers the ligand shell [AF mode on the AF model], matched iff coverage >= 0.3 or
precision >= 0.5; unmatched / <10-point sites are missing and dropped from that mode's COMMON set):
  arms  final (configs/final_method.yaml via pocketcompare.method: raw parts of the located set, shipped scaling,
        cosine), B1 (default, z-scored on the evaluated pool of that mode, holo + AF rows), A1 pair_only (same),
        B0 (size: -|dlog V|; reference, shows how much same-site retrieval a size match alone gives).
  (1) same-site retrieval: query = holo pocket of site i, candidates = AF pockets of all sites of the retrieval pool
      (role in --retrieval-roles); top-1, top-3, MRR (pessimistic ties), AUC(same-site vs other-site similarity),
      bootstrap over homology groups of the QUERY (retrieval) / two-way vertex bootstrap (AUC; evaluate.py).
      Variant 'xgrp': candidates of the query's own homology group (other than the true one) are removed.
  (2) ligand-sharing task, pair AUC with holo/holo vs holo/AF (score of a pair = mean of S(holo_a, AF_b) and
      S(AF_a, holo_b); AF/AF also reported): delta = AUC(holo/holo) - AUC(holo/AF) on the same pairs, paired vertex
      bootstrap, units = homology group and ligand cluster, the WIDER CI is reported (as BLiPS-val).
  (3) strata: holo release before / on-after 2018-05-01 (mirror header; pairs: both-pre / both-post / mixed) and site
      pLDDT band <70, 70-90, >=90 (pairs: min of the two sites).
Every number comes from pocketcompare.evaluate; trials are appended with arm "C5_dev" (dev sets) or "C5" (test).
"""
from __future__ import annotations

import os

if __name__ != "__main__":                       # spawned workers: one core each; the main process keeps threads
    for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[_v] = "1"
else:
    os.environ.setdefault("POCKETCOMPARE_THREADS", "12")
    os.environ.setdefault("NUMBA_NUM_THREADS", "12")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import gzip  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import shlex  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
AFT_IO = Path("/cluster/project/beltrao/gmagnus/pocket_detect/scripts/data")   # READ-ONLY reader of af_train

BENCH = ROOT / "data/processed/benchmarks"
CACHE = ROOT / "data/processed/cache/points"
SPLITS = ROOT / "data/splits"
CUTOFF_DATE = pd.Timestamp("2018-05-01")
PLDDT_BINS = [("<70", -np.inf, 70.0), ("70-90", 70.0, 90.0), (">=90", 90.0, np.inf)]
ARMS = ("final", "B1", "A1pair", "B0")
MODES = ("L", "D")
MIN_POINTS = 10
D_MIN_COV, D_MIN_PREC = 0.3, 0.5
SEED = None   # set from pocketcompare.seeds in main


# ====================================================================================== release dates
def mirror_release_date(path) -> pd.Timestamp:
    """First release (first row of _pdbx_audit_revision_history) from the mmCIF header of the PDB mirror file."""
    cols, rows, in_loop = [], [], False
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.startswith("_pdbx_audit_revision_history."):
                cols.append(line.strip().split(".")[1].split()[0])
                in_loop = True
                tok = shlex.split(line)
                if len(tok) > 1:              # single-row category "_x.revision_date 2020-01-01"
                    if cols[-1] == "revision_date":
                        return pd.to_datetime(tok[1], errors="coerce")
                continue
            if in_loop:
                if line.startswith(("#", "loop_", "_")):
                    break
                rows.append(shlex.split(line))
                if len(rows) == 1:
                    break
    if not rows or "revision_date" not in cols:
        return pd.NaT
    return pd.to_datetime(rows[0][cols.index("revision_date")], errors="coerce")


def holo_release_dates(sites: pd.DataFrame, table_names=("blips", "blips_test_holo")) -> pd.Series:
    """release_date per site: the prepared table (audit_revision_history of the mirror header), the mirror header
    itself for sites not in it."""
    R = pd.read_parquet(BENCH / "blips_holo_release_dates.parquet")
    R = R[R.dataset.isin(table_names)].drop_duplicates("pocket_id").set_index("pocket_id").release_date
    out = sites.site_id.map(R)
    for i in np.flatnonzero(out.isna().to_numpy()):
        try:
            out.iloc[i] = mirror_release_date(sites.holo_structure.iloc[i])
        except Exception:  # noqa: BLE001
            pass
    return pd.to_datetime(out)


# ====================================================================================== adapters
def _flat(xyz):
    return np.asarray(xyz, np.float64).reshape(-1, 3)


def _af_site_ligand(entry, sidx, q_ccds):
    """Transferred ligand heavy atoms of source site ``sidx``: instances whose CCD is among the qualifying CCDs of
    the BLiPS site (holo L-mode uses the same union); fallback = all non-ion instances.  Returns (xyz, flag)."""
    a = entry.arrays
    j = np.flatnonzero(np.asarray(a["site_src_index"]) == sidx)
    if len(j) != 1:
        return None, "site_missing"
    j = int(j[0])
    want = set(str(q_ccds).split(";"))
    ptr = np.asarray(a["lig_ptr"])
    inst = [k for k in range(len(a["lig_site"])) if a["lig_site"][k] == j and not a["lig_is_ion"][k]]
    sel = [k for k in inst if str(a["lig_ccd"][k]) in want]
    flag = "ok"
    if not sel:
        sel, flag = inst, "fallback_all_ligands"
    if not sel:
        return None, "no_ligand"
    xyz = np.vstack([a["lig_coords"][ptr[k]:ptr[k + 1]] for k in sel])
    el = np.concatenate([a["lig_elements"][ptr[k]:ptr[k + 1]] for k in sel])
    xyz = xyz[np.asarray([str(e).strip().upper() not in ("H", "D") for e in el])]
    return xyz.astype(np.float64), flag


def adapter_blips_dev(partition: str, max_sites: int | None, seed: int):
    """BLiPS v2 sites of ``partition`` ('val' | 'train') whose BURROW entry has an AF model in pocket_detect's
    af_train (matched by entry id = UniProt__pdb_chain of the BURROW train/dev pools; the AF model is keyed by the
    UniProt accession).  Partner sites (the other end of a labelled pair) are added with role 'partner' if they have
    AF models too, so that val-vs-train pairs are usable."""
    sys.path.insert(0, str(AFT_IO))
    from build_af_train_io import load_af_entry, read_af_manifest   # noqa: E402  (read-only)
    S = pd.read_parquet(SPLITS / "blips_sites_v2.parquet")
    S["src"] = S.site_id.str.split(":").str[0]
    S["entry"] = S.site_id.str.split(":").str[1]
    S["sidx"] = S.site_id.str.split(":").str[2].astype(int)
    man = {"burrow_dev": read_af_manifest("dev"), "burrow_train": read_af_manifest("train")}
    man = {k: v.set_index("entry_id") for k, v in man.items()}
    P = pd.read_parquet(BENCH / "blips_pockets.parquet").set_index("pocket_id")
    HI = pd.read_parquet(CACHE / "blips/index.parquet").set_index("pocket_id")
    pairs = pd.read_parquet(SPLITS / f"blips_{partition}_pairs_v2.parquet")
    S = S[S.partition.isin({"val", "train"})].copy()
    S = S[S.apply(lambda r: r.entry in man[r.src].index, axis=1)]
    main = S[S.partition == partition]
    if max_sites and len(main) > max_sites:
        main = main.sample(max_sites, random_state=seed)
    ids_main = set(main.site_id)
    pairs = pairs[pairs.site_a.isin(set(S.site_id)) & pairs.site_b.isin(set(S.site_id))]
    pairs = pairs[pairs.site_a.isin(ids_main) | pairs.site_b.isin(ids_main)]
    need = set(pairs.site_a) | set(pairs.site_b) | ids_main
    S = S[S.site_id.isin(need)].copy()
    rows, ent_cache = [], {}
    for r in S.itertuples():
        m = man[r.src].loc[r.entry]
        if r.entry not in ent_cache:
            ent_cache[r.entry] = load_af_entry(m.npz)
        xyz, flag = _af_site_ligand(ent_cache[r.entry], r.sidx, r.q_ccds)
        if xyz is None or r.site_id not in P.index or r.site_id not in HI.index:
            continue
        e = ent_cache[r.entry]
        j = int(np.flatnonzero(np.asarray(e.arrays["site_src_index"]) == r.sidx)[0])
        acc = Path(e.meta["model_path"]).name.replace("-model_v6.cif.gz", "")
        p = P.loc[r.site_id]
        rows.append(dict(
            site_id=r.site_id, group_id=r.group_id, role=("val" if r.partition == "val" and partition == "val" else
                                                           "train" if r.partition == "train" and partition == "train"
                                                           else "partner"),
            uniprot=r.uniprot, site_cluster=r.label_cluster, ccds=r.q_ccds,
            holo_cache=str(ROOT / HI.loc[r.site_id].cache_file), holo_structure=p.structure_path,
            holo_chains=list(p.chains), holo_lig=_flat(p.ligand_xyz),
            af_cache=str(CACHE / "blips_af_dev" / f"{acc}.npz"), af_structure=e.meta["model_path"],
            af_chains=None, af_lig=xyz, af_plddt=float(e.arrays["site_plddt_mean"][j]), af_lig_flag=flag,
            af_rmsd=float(e.arrays["site_rmsd"][j])))
    sites = pd.DataFrame(rows)
    sites["release_date"] = holo_release_dates(sites).to_numpy()
    pairs = pairs[pairs.site_a.isin(set(sites.site_id)) & pairs.site_b.isin(set(sites.site_id))].copy()
    pairs["label"] = pairs["label"].astype(int)
    return sites, pairs


def adapter_blips_test(pairs_path):
    """BLiPS-test (af_set): holo and AF pockets as prepared (cache dirs blips_test_holo / blips_test_af; ligand xyz in
    the unsealed pocket tables).  ``pairs_path`` = the (sealed) blips_test_pairs table, supplied by the PI / the
    final_eval unsealing wrapper -- this function never opens data/sealed itself.  Exclusions = blips_test_exclusions_v2."""
    H = pd.read_parquet(BENCH / "blips_test_holo_pockets.parquet").set_index("pocket_id")
    A = pd.read_parquet(BENCH / "blips_test_af_pockets.parquet").set_index("pocket_id")
    X = pd.read_parquet(SPLITS / "blips_test_exclusions_v2.parquet").set_index("site_id")
    HI = pd.read_parquet(CACHE / "blips_test_holo/index.parquet").set_index("pocket_id")
    AI = pd.read_parquet(CACHE / "blips_test_af/index.parquet").set_index("pocket_id")
    ok = X.index[(~X.excluded) & (X.holo_status == "ok") & (X.af_status == "ok")]
    ok = [s for s in ok if s in H.index and s in A.index and isinstance(H.loc[s].ligand_xyz, (list, np.ndarray))
          and len(H.loc[s].ligand_xyz) and len(A.loc[s].ligand_xyz)]
    sites = pd.DataFrame(dict(
        site_id=ok, group_id=X.loc[ok].group_id.to_numpy(), role="test", site_cluster=np.nan,
        holo_cache=[str(ROOT / HI.loc[s].cache_file) for s in ok],
        holo_structure=[H.loc[s].structure_path for s in ok], holo_chains=[list(H.loc[s].chains) for s in ok],
        holo_lig=[_flat(H.loc[s].ligand_xyz) for s in ok],
        af_cache=[str(ROOT / AI.loc[s].cache_file) for s in ok], af_structure=[A.loc[s].structure_path for s in ok],
        af_chains=[list(A.loc[s].chains) for s in ok], af_lig=[_flat(A.loc[s].ligand_xyz) for s in ok],
        af_plddt=[float(A.loc[s].site_plddt_mean) for s in ok]))
    sites["release_date"] = holo_release_dates(sites, ("blips_test_holo",)).to_numpy()
    pairs = None
    if pairs_path is not None:
        pairs = pd.read_parquet(pairs_path)
        pairs = pairs[pairs.site_a.isin(set(ok)) & pairs.site_b.isin(set(ok))].copy()
        pairs["label"] = pairs["label"].astype(int)
    return sites, pairs


# ====================================================================================== featurize + describe
def _featurize_one(task):
    """Build a missing Featurized cache file (AF mode for AF models)."""
    path, structure, chains, af_mode = task
    from pocketcompare import pockets as pk
    if Path(path).exists():
        return path, None
    try:
        fs = pk.featurize_structure(structure, chains=chains, af_mode=af_mode, key=Path(path).stem)
        fs.meta.update(af_mode=af_mode, chains=chains)
        fs.save(path)
        return path, None
    except Exception as e:  # noqa: BLE001
        return path, repr(e)


_W = {}


def _init_worker():
    from pocketcompare import method as M
    _W["m"] = M.Method()
    from pocketcompare.descriptors import a1 as A1
    import yaml
    grid = yaml.safe_load((ROOT / "configs/a1_grid.yaml").read_text())["configs"]
    _W["a1cfg"] = A1.make_config(grid["pair_only"])


def _locate(fs, lig):
    """L-mode set, D-mode set U (best-covering region pocket), coverage, precision, flags."""
    from pocketcompare import pockets as pk
    from scipy.spatial import cKDTree
    L = pk.lmode_from_ligand(fs, lig)
    rec = {"n_L": int(L.n_points), "clash": float(L.info["ligand_protein_min_dist"]), "U": None, "cov": 0.0,
           "prec": 0.0, "D_ok": False}
    mem = np.flatnonzero(fs.pk_in_region)
    if len(L.idx) and len(mem):
        m, cov = pk.best_member(fs, L.idx, mem)
        U = np.asarray(fs.pocket_idx(m), np.int64)
        prec = 0.0
        if len(U):
            d, _ = cKDTree(fs.points[L.idx]).query(fs.points[U], k=1, distance_upper_bound=pk.COVER_DIST + 1e-9)
            prec = float(np.isfinite(d).mean())
        rec.update(U=U, cov=float(cov), prec=prec, D_ok=bool(cov >= D_MIN_COV or prec >= D_MIN_PREC),
                   burrow_rank=int(m) + 1)
    return L.idx, rec


def _describe_side(fs, lig):
    from pocketcompare.descriptors import a1 as A1
    from pocketcompare.descriptors import baselines as BL
    m, a1cfg = _W["m"], _W["a1cfg"]
    at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
    Lidx, rec = _locate(fs, lig)
    out = {"loc": {k: v for k, v in rec.items() if k != "U"}}
    for mode, idx in (("L", Lidx), ("D", rec["U"] if rec["D_ok"] else None)):
        if idx is None or len(idx) < MIN_POINTS:
            out[mode] = None
            continue
        d = {"n": int(len(idx)), "vol": float(fs.volume(idx))}
        d["parts"] = m.raw_parts(fs, idx, at)                       # final-method raw parts (a1@sph8, env@sph8)
        pin = A1.pocket_input(fs, idx, atom_types=at, features=A1.needed_features(a1cfg))
        d["a1pair"], _ = A1.a1_descriptor(pin, a1cfg)
        d["b1"], _ = BL.b1_descriptor(fs, idx, learned=False, residues=[])
        out[mode] = d
    return out


def _describe_site(row):
    from pocketcompare import pockets as pk
    res = {"site_id": row["site_id"], "error": None}
    try:
        for side in ("holo", "af"):
            fs = pk.Featurized.load(row[f"{side}_cache"])
            res[side] = _describe_side(fs, row[f"{side}_lig"])
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{e!r}\n{traceback.format_exc()[-400:]}"
    return res


def describe_all(sites: pd.DataFrame, workers: int, log):
    # 1. missing Featurized caches
    tasks = {}
    for r in sites.itertuples():
        for side, af in (("holo", False), ("af", True)):
            path = getattr(r, f"{side}_cache")
            if not Path(path).exists():
                chains = getattr(r, f"{side}_chains")
                tasks[path] = (path, getattr(r, f"{side}_structure"), None if chains is None else list(chains), af)
    ctx = get_context("spawn")
    if tasks:
        log(f"featurizing {len(tasks)} missing structures ({workers} workers)")
        t0 = time.time()
        with ProcessPoolExecutor(workers, mp_context=ctx) as ex:
            errs = [e for e in ex.map(_featurize_one, list(tasks.values()), chunksize=2) if e[1]]
        log(f"  done in {time.time() - t0:.0f}s, {len(errs)} failures")
        for p, e in errs[:5]:
            log(f"  FAIL {p}: {e}")
    # 2. descriptors
    rows = sites[["site_id", "holo_cache", "af_cache", "holo_lig", "af_lig"]].to_dict("records")
    rows = [r for r in rows if Path(r["holo_cache"]).exists() and Path(r["af_cache"]).exists()]
    t0 = time.time()
    with ProcessPoolExecutor(workers, mp_context=ctx, initializer=_init_worker) as ex:
        res = list(ex.map(_describe_site, rows, chunksize=4))
    log(f"described {len(res)} sites in {time.time() - t0:.0f}s, {sum(r['error'] is not None for r in res)} errors")
    return {r["site_id"]: r for r in res}


# ====================================================================================== embeddings
def build_vectors(sites, desc, method):
    """{arm: {mode: {side: (N, d) array with NaN rows = missing}}}, {mode: {side: ok (N,)}}, {mode: logV}."""
    from pocketcompare.similarity import ZScorer, embed
    N = len(sites)
    V, OK, LOGV = {a: {m: {} for m in MODES} for a in ARMS}, {m: {} for m in MODES}, {m: {} for m in MODES}
    for mode in MODES:
        for side in ("holo", "af"):
            ids = sites.site_id.tolist()
            have = np.array([(desc.get(s) or {}).get("error", "x") is None and desc[s][side][mode] is not None
                             for s in ids])
            OK[mode][side] = have
            g = lambda k: [desc[s][side][mode][k] if h else None for s, h in zip(ids, have)]   # noqa: E731
            LOGV[mode][side] = np.array([np.log(desc[s][side][mode]["vol"] + 1.0) if h else np.nan
                                         for s, h in zip(ids, have)])
            raw = {"b1": g("b1"), "a1pair": g("a1pair")}
            parts = g("parts")
            mats = [np.vstack([p[k] if p is not None else np.full(len(parts[have.argmax()][k]), np.nan)
                               for p in parts]) for k in range(len(method.parts))]
            E = np.full((N, method.dim), np.nan, np.float32)
            if have.any():
                E[have] = method.embed([M[have] for M in mats])
                E[have & ~(np.linalg.norm(np.nan_to_num(E), axis=1) > 0)] = np.nan
            V["final"][mode][side] = E
            for arm, key in (("B1", "b1"), ("A1pair", "a1pair")):
                dd = len(next(x for x in raw[key] if x is not None))
                M = np.full((N, dd), np.nan)
                M[have] = np.vstack([x for x in raw[key] if x is not None])
                V[arm][mode][side] = M
        # label-free z-score on this mode's pool (holo + AF rows of the evaluated sites)
        for arm in ("B1", "A1pair"):
            both = np.vstack([V[arm][mode][s][OK[mode][s]] for s in ("holo", "af")])
            z = ZScorer.fit(both)
            for side in ("holo", "af"):
                E = np.full((N, both.shape[1]), np.nan, np.float32)
                E[OK[mode][side]] = embed(V[arm][mode][side][OK[mode][side]], z)
                V[arm][mode][side] = E
        for side in ("holo", "af"):
            V["B0"][mode][side] = LOGV[mode][side][:, None]
    return V, OK, LOGV


def sim_matrix(arm, A, B):
    """(Na, Nb) similarity, NaN where a row is missing."""
    if arm == "B0":
        return -np.abs(A[:, :1] - B[:, :1].T)
    return A @ B.T


# ====================================================================================== metrics
def _ev():
    from pocketcompare import evaluate as ev
    return ev


def group_boot(vals, groups, B, seed, alpha=0.05):
    """Bootstrap of mean(vals) over resampled homology groups (multinomial group counts; evaluate.bootstrap_counts)."""
    ev = _ev()
    codes, uniq = pd.factorize(pd.Series(groups))
    K = len(uniq)
    if K < 2:
        return (np.nan, np.nan)
    s = np.bincount(codes, weights=vals, minlength=K)
    n = np.bincount(codes, minlength=K).astype(float)
    reps = []
    for _, cnt in ev.bootstrap_counts(K, B, seed):
        reps.append((cnt @ s) / (cnt @ n))
    reps = np.concatenate([np.atleast_1d(r) for r in reps])
    return tuple(np.quantile(reps, [alpha / 2, 1 - alpha / 2]))


def retrieval(arm, V, ok, sites, pool_mask, query_mask, B, seed, max_neg=None, rng=None, same_group_excl=False):
    """Same-site retrieval holo query -> AF candidates.  pool_mask: sites usable (both sides ok & in the retrieval
    pool); query_mask: subset of the pool used as queries (strata).  Returns dict with point metrics + CIs."""
    ev = _ev()
    pidx = np.flatnonzero(pool_mask)
    n = len(pidx)
    if n < 3:
        return {"n_queries": int(query_mask[pidx].sum()), "n_pool": n}
    S = sim_matrix(arm, V["holo"][pidx], V["af"][pidx])           # (n, n); row = holo query, column = AF candidate
    grp = sites.group_id.to_numpy()[pidx]
    same = grp[:, None] == grp[None, :]
    np.fill_diagonal(same, False)
    cand = np.ones_like(S, bool)
    if same_group_excl:
        cand &= ~same
    diag = np.diag(S)
    gt = ((S > diag[:, None]) & cand).sum(1)
    tie = ((S == diag[:, None]) & cand).sum(1) - 1               # excl. the true candidate itself
    rank = 1 + gt + tie
    q = query_mask[pidx]
    if q.sum() < 2:
        return {"n_queries": int(q.sum()), "n_pool": n}
    out = {"n_queries": int(q.sum()), "n_pool": n, "n_groups": int(pd.Series(grp[q]).nunique()),
           "top1": float((rank[q] <= 1).mean()), "top3": float((rank[q] <= 3).mean()),
           "mrr": float((1.0 / rank[q]).mean()), "median_rank": float(np.median(rank[q]))}
    if q.sum() >= 5:
        for k, v in (("top1", (rank <= 1)), ("top3", (rank <= 3)), ("mrr", 1.0 / rank)):
            lo, hi = group_boot(v[q].astype(float), grp[q], B, seed)
            out[f"{k}_lo"], out[f"{k}_hi"] = lo, hi
    # AUC same-site (positives, one per query) vs other-site (negatives) similarity over the query rows
    qi = np.flatnonzero(q)
    I, J = np.meshgrid(qi, np.arange(n), indexing="ij")
    I, J = I.ravel(), J.ravel()
    keep = cand[I, J]
    if max_neg is not None and len(qi) * n > max_neg:
        r = rng.random(len(I))
        keep &= (I == J) | (r < max_neg / (len(qi) * n))
    I, J = I[keep], J[keep]
    y = (I == J).astype(int)
    s = S[I, J]
    out["auc"] = ev.roc_auc(y, s)
    if q.sum() >= 5:
        try:
            r = ev.vertex_bootstrap(y, s, grp[I], grp[J], B=B, seed=seed)["auc"]
            out["auc_lo"], out["auc_hi"] = r.ci_low, r.ci_high
        except ValueError:
            pass
    return out


def pair_task(arm, V, ok_both, sites, pairs, mask_fn, B, seed):
    """holo/holo vs holo/AF vs AF/AF AUC on labelled pairs (both endpoints usable); paired delta with the wider CI of
    the homology-group and ligand-cluster unit definitions."""
    ev = _ev()
    idx = pd.Series(np.arange(len(sites)), index=sites.site_id)
    ia, ib = idx.loc[pairs.site_a].to_numpy(), idx.loc[pairs.site_b].to_numpy()
    m = ok_both[ia] & ok_both[ib] & mask_fn(ia, ib)
    if m.sum() == 0:
        return {"n_pairs": 0}
    ia, ib, y = ia[m], ib[m], pairs.label.to_numpy()[m]
    Vh, Va = V["holo"], V["af"]

    def sc(X, Y, i, j):
        if arm == "B0":
            return -np.abs(X[i, 0] - Y[j, 0])
        return np.einsum("nd,nd->n", X[i], Y[j])
    s_hh = sc(Vh, Vh, ia, ib)
    s_ha = 0.5 * (sc(Vh, Va, ia, ib) + sc(Va, Vh, ia, ib))
    s_aa = sc(Va, Va, ia, ib)
    out = {"n_pairs": int(len(y)), "n_pos": int(y.sum()), "n_neg": int((1 - y).sum())}
    if y.sum() < 5 or (1 - y).sum() < 5:
        return out
    ga, gb = sites.group_id.to_numpy()[ia], sites.group_id.to_numpy()[ib]
    cl = sites.site_cluster.to_numpy().astype(float)
    sid = sites.site_id.to_numpy()
    ca = np.where(np.isnan(cl[ia]), sid[ia], cl[ia].astype(str))
    cb = np.where(np.isnan(cl[ib]), sid[ib], cl[ib].astype(str))
    out.update(auc_hh=ev.roc_auc(y, s_hh), auc_ha=ev.roc_auc(y, s_ha), auc_aa=ev.roc_auc(y, s_aa),
               delta_ha=ev.roc_auc(y, s_hh) - ev.roc_auc(y, s_ha), delta_aa=ev.roc_auc(y, s_hh) - ev.roc_auc(y, s_aa))
    if "pair_cluster" in pairs:
        pc = pairs.pair_cluster.to_numpy()[m]
        out["cb_hh"] = ev.cluster_balanced_auc(y, s_hh, pc)["auc_cb"] if y.sum() else np.nan
        out["cb_ha"] = ev.cluster_balanced_auc(y, s_ha, pc)["auc_cb"] if y.sum() else np.nan
    for tag, sb_ in (("ha", s_ha), ("aa", s_aa)):
        res = []
        for ci, cj in ((ga, gb), (ca, cb)):
            try:
                res.append(ev.paired_bootstrap(y, s_hh, sb_, ci, cj, B=B, seed=seed)["delta_auc"])
            except ValueError:
                pass
        if res:
            w = ev.wider_ci(*res)
            out[f"delta_{tag}_lo"], out[f"delta_{tag}_hi"], out[f"delta_{tag}_p"] = w.ci_low, w.ci_high, w.p_value
        # single-AUC CIs (hom-group units)
    for tag, s_ in (("hh", s_hh), ("ha", s_ha)):
        try:
            r = ev.vertex_bootstrap(y, s_, ga, gb, B=B, seed=seed)["auc"]
            out[f"auc_{tag}_lo"], out[f"auc_{tag}_hi"] = r.ci_low, r.ci_high
        except ValueError:
            pass
    return out


def strata_defs(sites):
    rel = sites.release_date
    pre = (rel < CUTOFF_DATE).to_numpy()
    known = rel.notna().to_numpy()
    pl = sites.af_plddt.to_numpy()
    site_strata = {"all": np.ones(len(sites), bool)}
    site_strata["holo_pre2018-05"] = pre & known
    site_strata["holo_post2018-05"] = ~pre & known
    for name, lo, hi in PLDDT_BINS:
        site_strata[f"plddt{name}"] = (pl >= lo) & (pl < hi)
    return site_strata, pre, known


def run(sites, pairs, desc, args, log, split_label):
    from pocketcompare import method as M
    ev = _ev()
    method = M.Method()
    V, OK, LOGV = build_vectors(sites, desc, method)
    site_strata, pre, known = strata_defs(sites)
    pl = sites.af_plddt.to_numpy()
    roles = set(args.retrieval_roles.split(","))
    in_pool = sites.role.isin(roles).to_numpy()
    rng = np.random.default_rng(args.seed)
    rows = []
    for mode in MODES:
        ok_both = OK[mode]["holo"] & OK[mode]["af"]
        log(f"[{mode}] usable sites (both holo and AF): {ok_both.sum()} / {len(sites)} "
            f"(pool {int((ok_both & in_pool).sum())})")
        for arm in ARMS:
            Vm = {s: V[arm][mode][s] for s in ("holo", "af")}
            ok = ok_both & np.isfinite(Vm["holo"]).all(1) & np.isfinite(Vm["af"]).all(1)
            for sname, smask in site_strata.items():
                for variant in ("all", "xgrp"):
                    r = retrieval(arm, Vm, ok, sites, ok & in_pool, smask & ok & in_pool, args.B, args.seed,
                                  max_neg=args.max_neg, rng=rng, same_group_excl=(variant == "xgrp"))
                    rows.append(dict(task="retrieval", variant=variant, mode=mode, arm=arm, stratum=sname, **r))
            if pairs is not None and len(pairs):
                def pmask(kind):
                    def f(ia, ib):
                        if kind == "all":
                            return np.ones(len(ia), bool)
                        if kind in ("both_pre", "both_post", "mixed"):
                            if not (known[ia].all() and known[ib].all()):
                                k = known[ia] & known[ib]
                            else:
                                k = np.ones(len(ia), bool)
                            a, b = pre[ia], pre[ib]
                            return k & {"both_pre": a & b, "both_post": ~a & ~b, "mixed": a != b}[kind]
                        name = kind
                        lo, hi = {n: (l, h) for n, l, h in PLDDT_BINS}[name.replace("plddt", "")]
                        mn = np.minimum(pl[ia], pl[ib])
                        return (mn >= lo) & (mn < hi)
                    return f
                kinds = ["all", "both_pre", "both_post", "mixed"] + [f"plddt{n}" for n, _, _ in PLDDT_BINS]
                for kind in kinds:
                    r = pair_task(arm, Vm, ok, sites, pairs, pmask(kind), args.B, args.seed)
                    rows.append(dict(task="pairs", variant="min_plddt" if kind.startswith("plddt") else "release"
                                     if kind != "all" else "all", mode=mode, arm=arm, stratum=kind, **r))
    R = pd.DataFrame(rows)
    # per-site diagnostics: same-site self-similarity, size agreement, coverage
    diag = []
    for s in sites.site_id:
        d = desc.get(s)
        if not d or d["error"]:
            diag.append({"site_id": s, "error": (d or {}).get("error", "missing")})
            continue
        diag.append({"site_id": s, "error": None, **{f"{sd}_{k}": v for sd in ("holo", "af")
                                                    for k, v in d[sd]["loc"].items()},
                     **{f"{sd}_{m}_ok": d[sd][m] is not None for sd in ("holo", "af") for m in MODES}})
    return R, pd.DataFrame(diag), OK


# ====================================================================================== main
def main(argv=None):
    from pocketcompare.provenance import append_trial, write_result
    from pocketcompare.seeds import SEEDS
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--set", choices=["val", "train", "test"], required=True)
    ap.add_argument("--pairs", default=None, help="test only: BLiPS-test pairs parquet (sealed; supplied by the PI)")
    ap.add_argument("--max-sites", type=int, default=None, help="train: random sample of this many sites")
    ap.add_argument("--retrieval-roles", default=None, help="comma list of site roles forming the retrieval pool "
                    "(default: val->val, train->train, test->test)")
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--max-neg", type=int, default=None, help="cap on query-candidate pairs for the retrieval AUC")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-trials", action="store_true")
    ap.add_argument("--seed", type=int, default=SEEDS[0])
    args = ap.parse_args(argv)
    args.workers = min(args.workers, 12)
    if args.set == "test" and os.environ.get("FINAL_EVAL") != "1":
        sys.exit("refusing: --set test needs FINAL_EVAL=1 (PI / final_eval wrapper only)")
    args.retrieval_roles = args.retrieval_roles or {"val": "val", "train": "train", "test": "test"}[args.set]
    out = Path(args.out or ROOT / f"results/{'final' if args.set == 'test' else 'dev'}/af_robustness_{args.set}")
    out.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    def log(m):
        print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

    if args.set == "test":
        sites, pairs = adapter_blips_test(args.pairs)
        split_label = "blips_test_af"
    else:
        sites, pairs = adapter_blips_dev(args.set, args.max_sites, args.seed)
        split_label = f"blips_{args.set}_v2_af"
    log(f"{split_label}: {len(sites)} sites with holo + AF ({sites.role.value_counts().to_dict()}), "
        f"{0 if pairs is None else len(pairs)} labelled pairs")
    desc = describe_all(sites, args.workers, log)
    R, diag, OK = run(sites, pairs, desc, args, log, split_label)
    R.to_csv(out / "metrics.csv", index=False)
    cfg = {"method": "configs/final_method.yaml", "arms": list(ARMS), "set": args.set, "B": args.B,
           "retrieval_roles": args.retrieval_roles, "cutoff_date": str(CUTOFF_DATE.date()), "n_sites": len(sites)}
    common = dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=[ROOT / "configs/final_method.yaml"],
                  seed=args.seed, device="cpu", start_time=t_start)
    write_result(out / "metrics.parquet", R, **common)
    write_result(out / "site_diagnostics.parquet", diag.assign(**{c: sites[c].to_numpy() for c in
                                                                  ("role", "group_id", "af_plddt", "release_date")}),
                 **common)
    if not args.no_trials:
        arm_name = "C5" if args.set == "test" else "C5_dev"
        for (task, variant, mode, arm, st), g in R.groupby(["task", "variant", "mode", "arm", "stratum"]):
            if variant not in ("all", "release", "min_plddt", "xgrp") or (task == "retrieval" and variant == "xgrp"):
                continue
            r = g.iloc[0].dropna().to_dict()
            keep = {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in r.items()
                    if k not in ("task", "variant", "mode", "arm", "stratum")}
            append_trial(arm_name, {"config": cfg, "task": task, "mode": mode, "arm_method": arm, "stratum": st},
                         split_label, keep, out / "metrics.parquet")
    log(f"done in {time.time() - t_start:.0f}s; results in {out}")


if __name__ == "__main__":
    main()
