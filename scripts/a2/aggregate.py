#!/usr/bin/env python
"""A2: merge the docking shards into one parquet per panel (+ provenance sidecar) and report run statistics.

  python scripts/a2/aggregate.py --raw raw_L --suffix ""        # -> data/processed/docking/tough_m1/fragments.parquet
  python scripts/a2/aggregate.py --raw raw_D --suffix _dmode
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare import provenance as prov  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402

BASE = ROOT / "data/processed/docking/tough_m1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="raw_L")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--mode", default="L")
    a = ap.parse_args()
    t0 = time.time()
    raw = BASE / a.raw
    shards = sorted(raw.glob("shard*.parquet"))
    stats = [json.loads(p.read_text()) for p in sorted(raw.glob("shard*.json"))]
    df = pd.concat([pd.read_parquet(p) for p in shards], ignore_index=True)
    geom = pd.read_parquet(BASE / "pocket_geom.parquet")
    expected = int(geom.d_matched.sum()) if a.mode == "D" else len(geom)

    summary = dict(mode=a.mode, raw=a.raw, n_shards=len(shards),
                   n_pockets_done=int(df.pocket_id.nunique()), n_pockets_expected=expected,
                   n_fail=int(sum(s["n_fail"] for s in stats)),
                   wall_s_max_shard=max(s["wall_s"] for s in stats),
                   s_per_pocket_per_shard=round(float(np.mean([s["s_per_pocket"] for s in stats])), 4),
                   n_mols=int(stats[0]["n_mols"]), preset=stats[0]["preset"], box_side=stats[0]["box_side"],
                   seeds=sorted({s for st in stats for s in st["seeds"]}),
                   rec_annot_match=round(float(np.mean([s["rec_annot_match"] for s in stats])), 5))
    for panel, dp in df.groupby("panel"):
        out = BASE / f"{panel}{a.suffix}.parquet"
        dp = dp.sort_values(["pocket_id", "seed", "mol_id"]).reset_index(drop=True)
        prov.write_result(out, dp, script=__file__, args=sys.argv[1:],
                          config=dict(preset=stats[0]["preset"], box_side=stats[0]["box_side"], mode=a.mode,
                                      panel=panel, in_pocket_cut=2.0),
                          inputs=[ROOT / f"data/ref/panels/{panel}_v1.sdf",
                                  BASE / "pocket_geom.npz", BASE / "pocket_geom.parquet"],
                          seed=SEEDS[0], device="cuda:0+cuda:2", start_time=t0,
                          extra=dict(shard_stats=stats))
        nb = dp.groupby("pocket_id").score.quantile(0.9)
        summary[panel] = dict(
            n_rows=len(dp), n_molecules=int(dp.mol_id.nunique()),
            bytes=out.stat().st_size,
            score_mean=round(float(dp.score.mean()), 4), score_sd=round(float(dp.score.std()), 4),
            le_mean=round(float(dp["le"].mean()), 4),
            in_pocket_rate=round(float(dp.in_pocket.mean()), 5),
            frac_positive_score=round(float((dp.score > 0).mean()), 6),
            nonbinder_rate_90pct=round(float((dp.score > dp.score.quantile(0.90)).mean()), 5),
            median_pocket_p90=round(float(nb.median()), 4),
            buried_frac_mean=round(float(dp.buried_frac.mean()), 4))
    (ROOT / "results/a2").mkdir(parents=True, exist_ok=True)
    (ROOT / f"results/a2/run_summary{a.suffix}_{a.mode}.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
