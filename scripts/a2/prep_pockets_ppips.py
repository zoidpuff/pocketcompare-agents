#!/usr/bin/env python
"""A2 on PPIPS, step 0: docking geometry for every PPIPS pocket (train/val/test, interface and non-interface).

Pocket = the merged region-rule pocket that P-sym / P-ortho refer to (data/processed/ppi/ppips/pockets.parquet,
``members`` = indices into BURROW's full list of the cached structure; scripts/ppi/22_ppips_build.py).
Per pocket: point cloud (input frame), volume-weighted centroid (-> fixed 12 A box centre), volume, volume-
weighted mean bur16, f_min / is_interface / split, receptor = the AFDB dimer PDB the cache was built from.
The geometry is stored in the "L" slots (l_points, center_L, volume_L, bur16_L) so that dock_tough_m1.py and
pocketcompare.descriptors.a2 run on it unchanged with --mode L.

Output: data/processed/docking/ppips/pocket_geom.{npz,parquet}.   Usage: python scripts/a2/prep_pockets_ppips.py
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POCKETS = ROOT / "data/processed/ppi/ppips/pockets.parquet"
CACHE = ROOT / "data/processed/cache/points/ppips"
OUT = ROOT / "data/processed/docking/ppips"


def _complex(args):
    key, rows = args
    with np.load(CACHE / f"{key}.npz", allow_pickle=False) as z:
        pts, vol = z["points"], z["vol"]
        bur = z["feats"][:, z["feature_names"].tolist().index("bur16")]
        indptr, indices = z["pk_indptr"], z["pk_indices"]
        meta = json.loads(str(z["meta"]))
    spacing = float(meta["feature_cfg"]["spacing"]) if isinstance(meta.get("feature_cfg"), dict) else 1.0
    out = []
    for pid, members in rows:
        idx = np.unique(np.concatenate([indices[indptr[m]:indptr[m + 1]] for m in members]))
        w = vol[idx].astype(np.float64)
        ww = w if w.sum() > 0 else np.ones_like(w)
        c = (pts[idx] * ww[:, None]).sum(0) / ww.sum()
        out.append((pid, pts[idx].astype(np.float32), c.astype(np.float32), float(w.sum() * spacing ** 3),
                    float((bur[idx] * ww).sum() / ww.sum()), meta["structure_path"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    pk = pd.read_parquet(POCKETS)
    tasks = [(k, list(zip(g.pocket_id, g.members))) for k, g in pk.groupby("complex", sort=True)]
    import multiprocessing as mp
    t0 = time.perf_counter()
    res = []
    with mp.get_context("spawn").Pool(a.workers) as pool:
        for part in pool.imap(_complex, tasks, chunksize=8):
            res += part
    pid = np.array([r[0] for r in res], dtype="U48")
    lptr = np.concatenate([[0], np.cumsum([len(r[1]) for r in res])]).astype(np.int64)
    cl = np.stack([r[2] for r in res])
    sc = pd.DataFrame(dict(pocket_id=pid, volume_L=[r[3] for r in res], bur16_L=[r[4] for r in res],
                           n_points_L=np.diff(lptr), cx=cl[:, 0], cy=cl[:, 1], cz=cl[:, 2],
                           receptor=[r[5] for r in res]))
    sc = sc.merge(pk[["pocket_id", "complex", "f_min", "is_interface", "split", "volume_A3", "n_res"]],
                  on="pocket_id", how="left", validate="one_to_one")
    sc["d_matched"] = False
    assert np.allclose(sc.volume_L, sc.volume_A3), "volume mismatch vs pockets.parquet"
    np.savez_compressed(OUT / "pocket_geom.npz", pocket_id=pid, l_points=np.concatenate([r[1] for r in res]),
                        l_indptr=lptr, center_L=cl, d_points=np.zeros((0, 3), np.float32),
                        d_indptr=np.zeros(len(pid) + 1, np.int64), center_D=np.full_like(cl, np.nan))
    sc.to_parquet(OUT / "pocket_geom.parquet", index=False)
    print(f"{len(sc)} pockets from {len(tasks)} complexes in {time.perf_counter() - t0:.0f}s; "
          f"interface {int(sc.is_interface.sum())}; splits {sc.split.value_counts().to_dict()}")
    print(sc[["volume_L", "bur16_L", "f_min", "n_points_L"]].describe().to_string())


if __name__ == "__main__":
    main()
