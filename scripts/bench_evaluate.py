"""Timing benchmark of the vertex bootstrap in pocketcompare.evaluate on synthetic pairs (no real data).

Usage: python scripts/bench_evaluate.py [--n 1000000] [--B 2000] [--clusters 1300] [--threads 16]
"""
import argparse
import os
import time

import numpy as np

from pocketcompare import evaluate as ev
from pocketcompare.seeds import SEEDS


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1_000_000)
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--clusters", type=int, default=1300)
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args(argv)
    rng = np.random.default_rng(SEEDS[0])
    y = rng.random(a.n) < 0.5
    ci = rng.integers(0, a.clusters, a.n)
    cj = np.where(y, ci, rng.integers(0, a.clusters, a.n))
    s_a = rng.normal(size=a.n) + 0.8 * y
    s_b = rng.normal(size=a.n) + 0.7 * y
    ev.vertex_bootstrap(y[:1000], s_a[:1000], ci[:1000], cj[:1000], B=8, n_threads=a.threads)  # JIT warm-up
    t0 = time.perf_counter()
    r1 = ev.vertex_bootstrap(y, s_a, ci, cj, B=a.B, n_threads=a.threads)
    t1 = time.perf_counter()
    r2 = ev.paired_bootstrap(y, s_a, s_b, ci, cj, B=a.B, n_threads=a.threads)
    t2 = time.perf_counter()
    print(f"n={a.n} B={a.B} K={a.clusters} threads={a.threads} host={os.uname().nodename}")
    print(f"single method (AUC+AP): {t1 - t0:.1f} s  auc={r1['auc'].estimate:.4f} [{r1['auc'].ci_low:.4f}, "
          f"{r1['auc'].ci_high:.4f}]")
    print(f"paired two methods:     {t2 - t1:.1f} s  dAUC={r2['delta_auc'].estimate:.4f} "
          f"[{r2['delta_auc'].ci_low:.4f}, {r2['delta_auc'].ci_high:.4f}] p={r2['delta_auc'].p_value:.4g}")


if __name__ == "__main__":
    main()
