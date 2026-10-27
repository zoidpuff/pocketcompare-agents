#!/usr/bin/env python
"""Runtime of the configured final method (configs/final_method.yaml), one thread.

    python scripts/bench_method.py --n-structures 200

* descriptor ms/pocket: ``Method.describe`` on cached BLiPS-val structures (``pockets.Featurized.load``; BURROW
  itself excluded, reported separately in its own runtime table), D mode = every region-rule pocket, timed end to
  end per structure (atom typing + shapers + A1 + env + embedding incl. the A4b forward) / number of pockets.
  L mode = the site's ligand shell from the point-cache index.
* embedding-only µs/pocket (z-scoring + A4b forward, batch of 10,000).
* µs/pair: one query against 1,000,000 random unit database vectors (float32 matmul), and per pair for a
  single (a, b) call of ``Method.similarity``.
Output: results/dev/final_method_runtime.json (+ .prov.json).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pocketcompare import method as MT  # noqa: E402
from pocketcompare import pockets as pk  # noqa: E402
from pocketcompare.provenance import write_result  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-structures", type=int, default=200)
    ap.add_argument("--out", default=str(ROOT / "results/dev/final_method_runtime.json"))
    a = ap.parse_args()
    t_start = time.time()
    M = MT.Method()
    ix = pd.read_parquet(ROOT / "data/processed/cache/points/blips/index.parquet")
    sites = pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet")
    val = set(sites.site_id[sites.partition == "val"])
    ix = ix[ix.pocket_id.isin(val)].drop_duplicates("cache_file").sort_values("pocket_id")
    ix = ix.sample(n=min(a.n_structures, len(ix)), random_state=SEEDS[0])
    d_ms, d_n, l_ms = [], [], []
    for r in ix.itertuples():
        fs = pk.Featurized.load(ROOT / r.cache_file)
        t0 = time.perf_counter()
        V = M.describe(fs)
        dt = time.perf_counter() - t0
        if len(V):
            d_ms.append(1e3 * dt / len(V))
            d_n.append(len(V))
        L = np.asarray(r.lmode_idx, np.int64)
        t0 = time.perf_counter()
        at = __import__("pocketcompare.descriptors.a1", fromlist=["x"]).atom_type_codes(
            fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        mats = [x[None] for x in M.raw_parts(fs, L, at)]
        M.embed(mats)
        l_ms.append(1e3 * (time.perf_counter() - t0))
    rng = np.random.default_rng(SEEDS[0])
    parts = [rng.normal(size=(10000, len(s.mean))) for s in M.scaler.scalers]
    t0 = time.perf_counter()
    M.embed(parts)
    emb_us = 1e6 * (time.perf_counter() - t0) / 10000
    DB = rng.normal(size=(1_000_000, M.dim)).astype(np.float32)
    DB /= np.linalg.norm(DB, axis=1, keepdims=True)
    q = DB[:1]
    reps = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = DB @ q[0]
        reps.append(time.perf_counter() - t0)
    pair_us_batch = 1e6 * min(reps) / len(DB)
    t0 = time.perf_counter()
    for k in range(10000):
        M.similarity(DB[k], DB[k + 1])
    pair_us_single = 1e6 * (time.perf_counter() - t0) / 10000
    res = {"method": M.cfg["name"], "dims": M.dim, "threads": 1, "n_structures": int(len(ix)),
           "D_pockets_per_structure_median": float(np.median(d_n)),
           "D_ms_per_pocket_median": float(np.median(d_ms)), "D_ms_per_pocket_p90": float(np.percentile(d_ms, 90)),
           "D_ms_per_pocket_mean_weighted": float(np.sum(np.asarray(d_ms) * d_n) / np.sum(d_n)),
           "L_ms_per_site_median": float(np.median(l_ms)), "L_ms_per_site_p90": float(np.percentile(l_ms, 90)),
           "embed_us_per_pocket": emb_us, "pair_us_batched_1M": pair_us_batch,
           "pair_us_single_call": pair_us_single, "bytes_per_pocket_float32": int(4 * M.dim),
           "note": "BURROW featurisation excluded (descriptor + embedding only); cached BLiPS-val structures"}
    print(res)
    write_result(a.out, res, script=__file__, args=sys.argv[1:], config={"n_structures": a.n_structures},
                 inputs=[MT.CONFIG], seed=SEEDS[0], device="cpu", start_time=t_start)


if __name__ == "__main__":
    main()
