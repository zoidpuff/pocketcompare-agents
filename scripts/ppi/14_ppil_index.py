#!/usr/bin/env python
"""PPI-L step 3: point-cache index.parquet for data/processed/cache/points/ppi_l (adapter, label-free).

11_ppil_pockets.py wrote the pocket table (data/processed/ppi/ppil/pockets.parquet, with lmode_idx / d_members /
d_coverage / d_precision per pocket) and the per-chain point caches, but not the build_point_cache.py-style
index.parquet that compute_descriptors.py, compute_n_inputs.py and scripts/final_eval.py read.  This script writes it
(no re-featurisation, no labels beyond what the table already holds): the table rows with status == 'ok', plus
d_n_points / d_volume_A3 / d_score of the matched merged pocket (union of the d_members; pocket points from the cache).

    python scripts/ppi/14_ppil_index.py --workers 12
"""
from __future__ import annotations

import os

for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
TABLE = ROOT / "data/processed/ppi/ppil/pockets.parquet"
OUT = ROOT / "data/processed/cache/points/ppi_l/index.parquet"


def work(task):
    cache_file, members_by_pocket = task
    from compute_descriptors import load_light
    fs = load_light(ROOT / cache_file)
    res = {}
    for pid, mem in members_by_pocket:
        if len(mem) == 0:
            res[pid] = (0, 0.0, np.nan, np.nan)
            continue
        idx = np.unique(np.concatenate([fs.pk_indices[fs.pk_indptr[m]:fs.pk_indptr[m + 1]] for m in mem]))
        vol = float(fs.vol[idx.astype(np.int64)].sum(dtype=np.float64) * fs.spacing ** 3)
        res[pid] = (int(len(idx)), vol, np.nan, int(len(fs.pk_indptr) - 1))
    return res


def main():
    from pocketcompare.provenance import write_result
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    t0 = time.time()
    T = pd.read_parquet(TABLE)
    T["structure_key"] = T["structure_key"].fillna(T["key"])
    ok = T[T.status == "ok"].reset_index(drop=True)
    tasks = [(cf, [(r.pocket_id, np.asarray(r.d_members, np.int64)) for r in g.itertuples()])
             for cf, g in ok.groupby("cache_file")]
    res = {}
    with get_context("spawn").Pool(min(a.workers, 12)) as pool:
        for r in pool.imap_unordered(work, tasks, chunksize=8):
            res.update(r)
    ok["d_n_points"] = [res[p][0] for p in ok.pocket_id]
    ok["d_volume_A3"] = [res[p][1] for p in ok.pocket_id]
    ok["status"] = "ok"
    ok["failure_reason"] = None
    ok["alt_definition"] = None
    ok = ok.drop(columns=["labels", "cavities"], errors="ignore")
    write_result(OUT, ok, script=__file__, args=sys.argv[1:], config={"source": str(TABLE.relative_to(ROOT))},
                 inputs=[TABLE], seed=None, device="cpu", start_time=t0,
                 extra={"n": int(len(ok)), "n_d_matched": int((ok.d_n_points > 0).sum())})
    print(f"wrote {OUT} ({len(ok)} pockets, {int((ok.d_n_points > 0).sum())} with a D pocket) "
          f"in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
