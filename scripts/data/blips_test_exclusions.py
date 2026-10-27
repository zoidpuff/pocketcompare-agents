#!/usr/bin/env python
"""DESIGN §2.6 exclusion "sites with < 10 BURROW points" for BLiPS-test (label-free; ids and point counts only).

Primary rule: a test site is excluded if its holo-chain L-mode pocket has < 10 BURROW points (or none could be
built).  The AF-model pocket count is recorded alongside (af_lt10) for the C5 common-set analysis.
Reads the point-cache indexes of blips_test_holo / blips_test_af and data/splits/blips_sites.parquet (test rows).
Writes data/splits/blips_test_exclusions_v2.parquet.  The sealed test pairs are NOT opened: filter them by
site id at final evaluation.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "data/processed/cache/points"
S = pd.read_parquet(ROOT / "data/splits/blips_sites.parquet")
S = S[S.partition == "test"][["site_id", "protein", "group_id"]]
for m in ("holo", "af"):
    i = pd.read_parquet(C / f"blips_test_{m}/index.parquet", columns=["pocket_id", "status", "n_points", "d_missed"])
    i = i.set_index("pocket_id").reindex(S.site_id)
    S[f"{m}_status"] = i.status.fillna("missing").to_numpy()
    S[f"{m}_n_points"] = np.where(i.status == "ok", i.n_points, 0).astype(int)
    S[f"{m}_lt10"] = S[f"{m}_n_points"].to_numpy() < 10
S["excluded"] = S.holo_lt10
S.to_parquet(ROOT / "data/splits/blips_test_exclusions_v2.parquet", index=False)
print(f"test sites {len(S)}; excluded (holo < 10 points) {int(S.excluded.sum())}; AF < 10 points "
      f"{int(S.af_lt10.sum())} (of which empty/failed {int((S.af_status != 'ok').sum())}); both {int((S.holo_lt10 & S.af_lt10).sum())}")
