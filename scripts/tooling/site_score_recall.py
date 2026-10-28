"""Dev-only: how many true ligand sites survive a BURROW pocket-score cutoff in the blind (ligand-free) setting?

For BLiPS v2 val (+ train) sites with an AlphaFold model, every AF model is run through BURROW + describe_all exactly
as in scripts/eval_blind.py (merged region-rule pockets with >= 10 points), each true site is matched to a pocket by
the D-mode rule, and the matched pocket's BURROW score / rank are recorded. Output: the fraction of sites (and of
pockets in the pool) kept at each score cutoff. Never touches test data.

    python scripts/tooling/site_score_recall.py --workers 24 --out results/tooling/site_score_recall.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from eval_af_robustness import adapter_blips_dev  # noqa: E402
from eval_blind import build_pool, describe_models  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402

CUTS = [0.0, 0.01, 0.02, 0.03, 0.05, 0.1, 0.2, 0.3, 0.5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--partitions", default="val,train")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = time.time()
    frames = []
    for part in a.partitions.split(","):
        s, _ = adapter_blips_dev(part, None, SEEDS[0])
        frames.append(s[s.role == part])
    sites = pd.concat(frames).drop_duplicates("site_id").reset_index(drop=True)
    models, desc = describe_models(sites, a.workers, print)
    pool, _, site_pocket = build_pool(sites, models, desc)
    pool["rank_in_model"] = pool.groupby("model").score.rank(ascending=False, method="first")
    idx = np.array([site_pocket.get(s, -1) for s in sites.site_id])
    det = idx >= 0
    sc = np.where(det, pool.score.to_numpy()[np.clip(idx, 0, None)], np.nan)
    rk = np.where(det, pool.rank_in_model.to_numpy()[np.clip(idx, 0, None)], np.nan)
    rows = []
    for c in CUTS:
        rows.append({"cut": c, "site_recall": float(np.mean(det & (np.nan_to_num(sc, nan=-1) >= c))),
                     "site_recall_given_detected": float(np.mean(sc[det] >= c)),
                     "pool_fraction_kept": float(np.mean(pool.score >= c)),
                     "pockets_per_model": float((pool.score >= c).sum() / pool.model.nunique())})
    topk = {k: float(np.mean(det & (np.nan_to_num(rk, nan=1e9) <= k))) for k in (1, 3, 5, 10)}
    res = {"n_sites": int(len(sites)), "n_models": int(pool.model.nunique()), "n_pool": int(len(pool)),
           "detected": float(det.mean()), "matched_score_median": float(np.nanmedian(sc)),
           "cutoffs": rows, "site_recall_by_rank": topk, "seconds": time.time() - t0,
           "note": "dev data only (BLiPS v2 val + train sites with AF models); merged region pockets >= 10 points"}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
