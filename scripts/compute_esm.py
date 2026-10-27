#!/usr/bin/env python
"""B4 ESM-2 pocket descriptors.  Usage: python scripts/compute_esm.py --dataset tough_m1 [--limit N]

Dataset adapters (the tough_m1 branch is the original code, unchanged):
  blips, blips_test_holo, blips_test_af  point-cache index + data/processed/benchmarks/<ds>_pockets.parquet (structure
        path); L = index lining residues, D = residues of the matched merged pocket (d_members -> pk_residues).
        Only the chains that carry pocket residues are embedded (holo mmCIFs can hold many chains); AF models:
        the AF sequence (chain A of the model file).
  prospeccts, vertex  as blips (generic path); require --label-free-structures (no labels are read).
  ppips merged region-rule pockets (data/processed/ppi/ppips/pockets.parquet), D only = the pocket's BURROW
        output residues on the AF dimer (both chains embedded separately, as for every multi-chain file).
"""
import argparse, json, subprocess, sys, time
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.descriptors import esm_pocket as ep  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", default=None)
    ap.add_argument("--label-free-structures", action="store_true",
                    help="permit prospeccts / vertex (sealed external sets): reads only the point-cache index and "
                         "the pocket table's structure paths, never a label or pair file")
    a = ap.parse_args()
    if a.dataset in ("prospeccts", "vertex") and not a.label_free_structures:
        raise SystemExit(f"{a.dataset} is sealed: pass --label-free-structures (label-free featurisation only)")
    if a.dataset != "tough_m1":
        return main_generic(a)
    t0 = time.time()
    idx = pd.read_parquet(ROOT / f"data/processed/cache/points/{a.dataset}/index.parquet")
    bench = pd.read_parquet(ROOT / f"data/processed/benchmarks/{a.dataset}_pockets.parquet").set_index("pocket_id")
    idx = idx[idx.status == "ok"].reset_index(drop=True)
    if a.limit:
        idx = idx.iloc[:a.limit]
    out = Path(a.out or ROOT / f"data/processed/descriptors/{a.dataset}"); out.mkdir(parents=True, exist_ok=True)
    emb = ep.ESMEmbedder(a.device, ROOT / "data/processed/esm")
    L = np.full((len(idx), ep.DIM), np.nan, np.float32); D = L.copy()
    rows = []
    for k, r in enumerate(idx.itertuples()):
        t = time.time()
        rec = dict(pocket_id=r.pocket_id, structure_key=r.structure_key)
        try:
            chains = ep.chain_residues(ROOT / bench.loc[r.pocket_id, "structure_path"])
            embs = {c: emb.embed_chain(s) for c, (s, _) in chains.items()}
            rec["n_chains"] = len(chains); rec["n_res_total"] = sum(len(v[0]) for v in chains.values())
            v, nf, nm = ep.pool_pocket(chains, embs, str(r.lining_residues).split())
            rec.update(L_found=nf, L_missing=nm)
            if v is not None: L[k] = v
            with np.load(ROOT / r.cache_file) as z:
                pkres = z["pk_residues"]
            mem = list(r.d_members) if r.d_members is not None else []
            dres = sorted({x for m in mem for x in str(pkres[m]).split()})
            rec["D_has"] = bool(mem); rec["D_missed"] = bool(r.d_missed)
            if dres:
                v, nf, nm = ep.pool_pocket(chains, embs, dres)
                rec.update(D_found=nf, D_missing=nm)
                if v is not None: D[k] = v
            rec["error"] = None
        except Exception as e:  # noqa
            rec["error"] = repr(e)
        rec["seconds"] = time.time() - t
        rows.append(rec)
        if k % 200 == 0: print(k, len(idx), f"{time.time()-t0:.0f}s", flush=True)
    ids = pd.DataFrame(rows)
    np.save(out / "b4_esm2_L.npy", L); np.save(out / "b4_esm2_D.npy", D)
    ids.to_parquet(out / "b4_esm2_ids.parquet")
    try: commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception: commit = None
    prov = dict(git_commit=commit, args=vars(a), model=ep.MODEL, pooling="mean over lining residues, last hidden layer",
                window=dict(maxlen=ep.MAXLEN, stride=ep.STRIDE), precision="fp16 forward, fp32 pooling",
                n_pockets=len(idx), n_L=int((~np.isnan(L[:, 0])).sum()), n_D=int((~np.isnan(D[:, 0])).sum()),
                wall_seconds=time.time() - t0, per_pocket_s_median=float(ids.seconds.median()),
                per_pocket_s_mean=float(ids.seconds.mean()), n_errors=int(ids.error.notna().sum()),
                time=time.strftime("%Y-%m-%dT%H:%M:%S"))
    (out / "b4_esm2_provenance.json").write_text(json.dumps(prov, indent=1))
    print(json.dumps(prov, indent=1))
    (ROOT / f"logs/compute_esm_{a.dataset}.done").write_text(prov["time"])


def generic_rows(dataset: str) -> pd.DataFrame:
    """pocket_id, structure_key, structure_path, L_res (list|None), D_res (list|None), d_missed."""
    if dataset == "ppips":
        P = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
        cx = pd.read_parquet(ROOT / "data/processed/cache/points/ppips/complexes.parquet").set_index("modelEntityId")
        return pd.DataFrame(dict(pocket_id=P.pocket_id, structure_key=P.complex,
                                 structure_path=P.complex.map(cx.path), L_res=None,
                                 D_res=[r.split() for r in P.residues], d_missed=False))
    idx = pd.read_parquet(ROOT / f"data/processed/cache/points/{dataset}/index.parquet")
    idx = idx[idx.status == "ok"].reset_index(drop=True)
    bench = pd.read_parquet(ROOT / f"data/processed/benchmarks/{dataset}_pockets.parquet").set_index("pocket_id")
    D = []
    for key, g in idx.groupby("structure_key", sort=False):
        with np.load(ROOT / g.cache_file.iloc[0]) as z:
            pkres = z["pk_residues"]
        for r in g.itertuples():
            mem = list(r.d_members) if r.d_members is not None else []
            D.append((r.pocket_id, sorted({x for m in mem for x in str(pkres[m]).split()}) or None))
    D = dict(D)
    return pd.DataFrame(dict(pocket_id=idx.pocket_id, structure_key=idx.structure_key,
                             structure_path=idx.pocket_id.map(bench.structure_path),
                             L_res=[str(x).split() for x in idx.lining_residues], D_res=idx.pocket_id.map(D),
                             d_missed=idx.d_missed.astype(bool)))


def main_generic(a):
    t0 = time.time()
    R = generic_rows(a.dataset)
    if a.limit:
        R = R.iloc[:a.limit]
    R = R.reset_index(drop=True)
    out = Path(a.out or ROOT / f"data/processed/descriptors/{a.dataset}"); out.mkdir(parents=True, exist_ok=True)
    emb = ep.ESMEmbedder(a.device, ROOT / "data/processed/esm")
    L = np.full((len(R), ep.DIM), np.nan, np.float32); D = L.copy()
    rows = [None] * len(R)
    n_new = 0
    for k_s, (path, g) in enumerate(R.groupby("structure_path", sort=True)):
        t = time.time()
        try:
            chains = ep.chain_residues(path if Path(path).is_absolute() else ROOT / path)
            need = {x.partition(":")[0] for res in list(g.L_res) + list(g.D_res) if res for x in res}
            chains = {c: v for c, v in chains.items() if c in need} or chains
            embs = {}
            for c, (sq, _) in chains.items():
                n_new += not (emb.cache / f"{ep.seq_key(sq)}.npy").exists()
                embs[c] = emb.embed_chain(sq)
            err = None
        except Exception as e:  # noqa
            chains, embs, err = None, None, repr(e)
        dt = (time.time() - t) / len(g)
        for k, r in zip(g.index, g.itertuples()):
            rec = dict(pocket_id=r.pocket_id, structure_key=r.structure_key, error=err, seconds=dt)
            if chains is not None:
                rec["n_chains_embedded"] = len(chains)
                rec["n_res_total"] = sum(len(v[0]) for v in chains.values())
                if r.L_res:
                    v, nf, nm = ep.pool_pocket(chains, embs, r.L_res)
                    rec.update(L_found=nf, L_missing=nm)
                    if v is not None: L[k] = v
                rec["D_has"] = bool(r.D_res); rec["D_missed"] = bool(r.d_missed)
                if r.D_res:
                    v, nf, nm = ep.pool_pocket(chains, embs, r.D_res)
                    rec.update(D_found=nf, D_missing=nm)
                    if v is not None: D[k] = v
            rows[k] = rec
        if k_s % 200 == 0: print(k_s, f"{time.time() - t0:.0f}s", flush=True)
    ids = pd.DataFrame(rows)
    if a.dataset != "ppips":
        np.save(out / "b4_esm2_L.npy", L)
    np.save(out / "b4_esm2_D.npy", D)
    ids.to_parquet(out / "b4_esm2_ids.parquet")
    try: commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception: commit = None
    prov = dict(git_commit=commit, args=vars(a), model=ep.MODEL, pooling="mean over lining residues, last hidden layer",
                window=dict(maxlen=ep.MAXLEN, stride=ep.STRIDE), precision="fp16 forward, fp32 pooling",
                n_pockets=len(R), n_L=int((~np.isnan(L[:, 0])).sum()), n_D=int((~np.isnan(D[:, 0])).sum()),
                n_structures=int(R.structure_path.nunique()), n_new_sequences_embedded=int(n_new),
                wall_seconds=time.time() - t0, per_pocket_s_median=float(ids.seconds.median()),
                per_pocket_s_mean=float(ids.seconds.mean()), n_errors=int(ids.error.notna().sum()),
                time=time.strftime("%Y-%m-%dT%H:%M:%S"))
    (out / "b4_esm2_provenance.json").write_text(json.dumps(prov, indent=1))
    print(json.dumps(prov, indent=1))
    if not a.limit:
        (ROOT / f"logs/compute_esm_{a.dataset}.done").write_text(prov["time"])


main()
