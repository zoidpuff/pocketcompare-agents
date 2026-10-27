#!/usr/bin/env python
"""Full pocket lists WITH descriptors and point clouds for the dimer sample (task 2/3 analysis input).

Runs pocketdetect.burrow.export.pocket_representations (reference pipeline; pockets identical to the CLI)
with af_mode=True, preset=default, ranker=all, min_score=None (full NMS'd list, <= 50 pockets) on every
dimer and monomer of the sample. The v2 default output is the prefix of this list (ranks 1-3 always,
then score >= 0.03), which 05_analyze.py re-derives and checks against the CLI output.

Writes data/processed/dimers/sample/export/{dimers,monomers}_pockets.parquet  (one row per pocket:
       sid, rank, score, residues, n_points, volume_A3, plddt_mean/min, 76 descriptors)
       data/processed/dimers/sample/export/{dimers,monomers}_points.parquet   (sid, rank, x, y, z, vol, point_score)
Usage: python scripts/ppi/04_export_descriptors.py [--workers 16] [--which dimers monomers]
"""
from __future__ import annotations

import argparse
import os
import time
import traceback
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / "data/processed/dimers/sample"


def one(path: str):
    os.environ.setdefault("NUMBA_NUM_THREADS", "1")
    from pocketdetect.burrow.export import pocket_representations
    sid = Path(path).stem
    t0 = time.perf_counter()
    try:
        rep = pocket_representations(path, ranker="all", preset="default", min_score=None, af_mode=True,
                                     structure_id=sid)
    except Exception:  # noqa: BLE001
        return sid, None, None, traceback.format_exc(), time.perf_counter() - t0
    pk = rep["pockets"].copy()
    pk.insert(0, "sid", sid)
    pk["n_candidates"] = rep["n_candidates"]
    pts = rep["points"]
    rows = []
    for r, idx in rep["pocket_points"].items():
        sub = pts.iloc[idx]
        rows.append(pd.DataFrame({"sid": sid, "rank": np.int16(r), "x": sub.x.astype(np.float32),
                                  "y": sub.y.astype(np.float32), "z": sub.z.astype(np.float32),
                                  "vol": sub.vol.astype(np.float32), "point_score": sub.point_score.astype(np.float32)}))
    pp = pd.concat(rows, ignore_index=True) if rows else None
    return sid, pk, pp, None, time.perf_counter() - t0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--which", nargs="+", default=["dimers", "monomers"])
    a = ap.parse_args()
    out = S / "export"
    out.mkdir(parents=True, exist_ok=True)
    for which in a.which:
        paths = (S / f"inputs/{which}.list").read_text().split()
        t0 = time.time()
        with Pool(a.workers, maxtasksperchild=50) as pool:
            res = pool.map(one, paths, chunksize=2)
        pks = [r[1] for r in res if r[1] is not None and len(r[1])]
        pps = [r[2] for r in res if r[2] is not None]
        errs = [(r[0], r[3]) for r in res if r[3]]
        pd.concat(pks, ignore_index=True).to_parquet(out / f"{which}_pockets.parquet")
        pd.concat(pps, ignore_index=True).to_parquet(out / f"{which}_points.parquet")
        pd.DataFrame({"sid": [r[0] for r in res], "sec": [r[4] for r in res],
                      "n_pockets": [0 if r[1] is None else len(r[1]) for r in res]}).to_csv(
            out / f"{which}_timing.tsv", sep="\t", index=False)
        print(f"{which}: {len(paths)} inputs, {len(errs)} errors, wall {time.time() - t0:.0f} s")
        for sid, e in errs[:5]:
            print(sid, e.splitlines()[-1])


if __name__ == "__main__":
    main()
