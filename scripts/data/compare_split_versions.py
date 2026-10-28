#!/usr/bin/env python
"""Units that moved between the committed split tables (git REF, default HEAD) and the working tree (D15 rebuild).

Units: TOUGH-M1 pockets (dev/test/excluded); BLiPS v1 sites + proteins (train/val/test/removed); BLiPS v2 sites
(train/val/excluded_*; missing = not in the pool); PPIPS complexes (train/val/test). Labels are not read.
Writes data/splits/split_changes.json. Usage: python scripts/data/compare_split_versions.py [REF]
"""
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REF = sys.argv[1] if len(sys.argv) > 1 else "HEAD"


def old(path):
    b = subprocess.run(["git", "show", f"{REF}:{path}"], cwd=ROOT, check=True, capture_output=True).stdout
    return pd.read_parquet(io.BytesIO(b))


def new(path):
    return pd.read_parquet(ROOT / path)


def moved(o, n, key, col, absent="absent"):
    m = o[[key, col]].merge(n[[key, col]], on=key, how="outer", suffixes=("_old", "_new")).fillna(absent)
    ch = m[m[f"{col}_old"] != m[f"{col}_new"]]
    return {"n_units_old": int(len(o)), "n_units_new": int(len(n)), "n_moved": int(len(ch)),
            "transitions": {f"{a}->{b}": int(v) for (a, b), v in
                            ch.groupby([f"{col}_old", f"{col}_new"]).size().items()}}


out = {"ref": subprocess.run(["git", "rev-parse", REF], cwd=ROOT, capture_output=True, text=True).stdout.strip()}
out["tough_m1_pockets"] = moved(old("data/splits/tough_m1_pockets_split.parquet"),
                                new("data/splits/tough_m1_pockets_split.parquet"), "pocket_id", "partition")
f = "data/splits/blips_sites.parquet"
out["blips_v1_sites"] = moved(old(f), new(f), "site_id", "partition", absent="removed")
po, pn = old(f).drop_duplicates("protein"), new(f).drop_duplicates("protein")
out["blips_v1_proteins"] = moved(po, pn, "protein", "partition", absent="removed")
f = "data/splits/blips_sites_v2.parquet"
out["blips_v2_sites"] = moved(old(f), new(f), "site_id", "partition", absent="not_in_pool")
f = "data/splits/ppips_complex_splits.parquet"
out["ppips_complexes"] = moved(old(f), new(f), "complex", "split")
(ROOT / "data/splits/split_changes.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
