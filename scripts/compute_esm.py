#!/usr/bin/env python
"""B4 ESM-2 pocket descriptors.  Usage: python scripts/compute_esm.py --dataset tough_m1 [--limit N]"""
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
    a = ap.parse_args()
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

main()
