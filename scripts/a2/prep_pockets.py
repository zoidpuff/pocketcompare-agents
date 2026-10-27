#!/usr/bin/env python
"""A2 step 0: per-pocket docking geometry for TOUGH-M1 (DESIGN §3 A2).

For every pocket in data/processed/cache/points/tough_m1/index.parquet:
  * L-mode point cloud (input frame) and its volume-weighted centroid  -> the fixed 12 A box centre;
  * D-mode (merged region-rule) point cloud and centroid, when the site is matched (``d_missed`` False);
  * volume (sum vol * spacing^3) and volume-weighted mean buriedness (BURROW point feature ``bur16``);
  * the receptor PDB path (TOUGH-M1 files are already protein-only: 0 HETATM, no waters, no H).

Output: data/processed/docking/tough_m1/pocket_geom.npz (CSR point clouds + scalars) and .parquet (scalars).

Usage: python scripts/a2/prep_pockets.py --workers 8
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IDX = ROOT / "data/processed/cache/points/tough_m1/index.parquet"
BENCH = ROOT / "data/processed/benchmarks/tough_m1_pockets.parquet"
OUT = ROOT / "data/processed/docking/tough_m1"


def _one(args):
    pocket_id, cache_file, l_idx, d_members = args
    with np.load(ROOT / cache_file, allow_pickle=False) as z:
        pts, vol = z["points"], z["vol"]
        fn = z["feature_names"].tolist()
        bur = z["feats"][:, fn.index("bur16")]
        meta = str(z["meta"])
        indptr, indices = z["pk_indptr"], z["pk_indices"]
    spacing = 1.0
    i = meta.find('"spacing":')
    if i >= 0:
        spacing = float(meta[i + 10:].split(",")[0].split("}")[0])

    l_idx = np.asarray(l_idx, np.int64)
    w = vol[l_idx].astype(np.float64)
    wl = w if w.sum() > 0 else np.ones_like(w)
    cl = (pts[l_idx] * wl[:, None]).sum(0) / wl.sum()
    vol_l = float(w.sum() * spacing ** 3)
    bur_l = float((bur[l_idx] * wl).sum() / wl.sum())

    dm = np.asarray(d_members, np.int64) if d_members is not None else np.array([], np.int64)
    if len(dm):
        d_idx = np.unique(np.concatenate([indices[indptr[k]:indptr[k + 1]] for k in dm]))
        wd = vol[d_idx].astype(np.float64)
        wd2 = wd if wd.sum() > 0 else np.ones_like(wd)
        cd = (pts[d_idx] * wd2[:, None]).sum(0) / wd2.sum()
        vol_d = float(wd.sum() * spacing ** 3)
        bur_d = float((bur[d_idx] * wd2).sum() / wd2.sum())
    else:
        d_idx, cd, vol_d, bur_d = np.array([], np.int64), np.full(3, np.nan), np.nan, np.nan
    return (pocket_id, pts[l_idx].astype(np.float32), pts[d_idx].astype(np.float32),
            cl.astype(np.float32), cd.astype(np.float32), vol_l, vol_d, bur_l, bur_d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ix = pd.read_parquet(IDX)
    bench = pd.read_parquet(BENCH).set_index("pocket_id")
    ix = ix[ix.status == "ok"].reset_index(drop=True)
    print(f"{len(ix)} pockets", flush=True)
    args = [(r.pocket_id, r.cache_file, r.lmode_idx, None if r.d_missed else r.d_members)
            for r in ix.itertuples(index=False)]

    import multiprocessing as mp
    t0 = time.perf_counter()
    with mp.get_context("spawn").Pool(a.workers) as pool:
        res = []
        for k, out in enumerate(pool.imap(_one, args, chunksize=16)):
            res.append(out)
            if (k + 1) % 1000 == 0:
                print(f"  {k + 1} / {len(args)}  {time.perf_counter() - t0:.0f}s", flush=True)

    pid = np.array([r[0] for r in res], dtype="U32")
    lpts = np.concatenate([r[1] for r in res])
    lptr = np.concatenate([[0], np.cumsum([len(r[1]) for r in res])]).astype(np.int64)
    dpts = np.concatenate([r[2] for r in res]) if sum(len(r[2]) for r in res) else np.zeros((0, 3), np.float32)
    dptr = np.concatenate([[0], np.cumsum([len(r[2]) for r in res])]).astype(np.int64)
    cl = np.stack([r[3] for r in res])
    cd = np.stack([r[4] for r in res])
    sc = pd.DataFrame(dict(pocket_id=pid, volume_L=[r[5] for r in res], volume_D=[r[6] for r in res],
                           bur16_L=[r[7] for r in res], bur16_D=[r[8] for r in res],
                           n_points_L=np.diff(lptr), n_points_D=np.diff(dptr),
                           cx=cl[:, 0], cy=cl[:, 1], cz=cl[:, 2],
                           dx=cd[:, 0], dy=cd[:, 1], dz=cd[:, 2]))
    sc["receptor"] = [str(ROOT / bench.loc[p, "structure_path"]) for p in pid]
    sc["d_matched"] = sc.n_points_D > 0
    np.savez_compressed(OUT / "pocket_geom.npz", pocket_id=pid, l_points=lpts, l_indptr=lptr,
                        d_points=dpts, d_indptr=dptr, center_L=cl, center_D=cd)
    sc.to_parquet(OUT / "pocket_geom.parquet", index=False)
    print(f"wrote {OUT/'pocket_geom.npz'} ({(OUT/'pocket_geom.npz').stat().st_size/1e6:.1f} MB) in "
          f"{time.perf_counter() - t0:.0f}s; D-mode matched {int(sc.d_matched.sum())}/{len(sc)}")
    print(sc[["volume_L", "bur16_L", "n_points_L", "n_points_D"]].describe().to_string())


if __name__ == "__main__":
    main()
