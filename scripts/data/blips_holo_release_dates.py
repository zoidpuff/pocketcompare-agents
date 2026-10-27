#!/usr/bin/env python
"""Initial release date of every BLiPS holo structure (label-free; for the C5 stratum "holo release >= 2018-05-01").

    python scripts/data/blips_holo_release_dates.py --workers 8

Reads data/processed/benchmarks/{blips_test_holo,blips}_pockets.parquet (structure paths only) and the mmCIF headers
(_pdbx_audit_revision_history: earliest revision_date = initial release; fallback
_pdbx_database_status.recvd_initial_deposition_date, flagged).  Writes
data/processed/benchmarks/blips_holo_release_dates.parquet (pocket_id, dataset, structure_path, release_date,
date_source) + .prov.json.
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
BENCH = ROOT / "data/processed/benchmarks"


def release(path: str):
    import gemmi
    p = Path(path) if Path(path).is_absolute() else ROOT / path
    try:
        doc = gemmi.cif.read(str(p))
        b = doc.sole_block()
        d = [x for x in b.find_values("_pdbx_audit_revision_history.revision_date") if x not in ("?", ".")]
        if d:
            return path, min(gemmi.cif.as_string(x) for x in d), "audit_revision_history"
        v = b.find_value("_pdbx_database_status.recvd_initial_deposition_date")
        if v not in (None, "?", "."):
            return path, gemmi.cif.as_string(v), "deposition_date(fallback)"
        return path, None, "absent"
    except Exception as e:  # noqa: BLE001
        return path, None, f"error:{e!r}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    t0 = time.time()
    tabs = []
    for ds in ("blips_test_holo", "blips"):
        t = pd.read_parquet(BENCH / f"{ds}_pockets.parquet", columns=["pocket_id", "structure_path"])
        tabs.append(t.assign(dataset=ds))
    T = pd.concat(tabs, ignore_index=True)
    with ProcessPoolExecutor(a.workers) as ex:
        res = {p: (d, s) for p, d, s in ex.map(release, sorted(T.structure_path.unique()), chunksize=32)}
    T["release_date"] = pd.to_datetime([res[p][0] for p in T.structure_path], errors="coerce")
    T["date_source"] = [res[p][1] for p in T.structure_path]
    from pocketcompare.provenance import write_result
    write_result(BENCH / "blips_holo_release_dates.parquet", T, script=__file__, args=sys.argv[1:],
                 config={"cutoff_for_C5_strata": "2018-05-01"}, inputs=[BENCH / "blips_test_holo_pockets.parquet",
                                                                         BENCH / "blips_pockets.parquet"],
                 seed=None, device="cpu", start_time=t0)
    print(T.groupby("dataset").release_date.describe(), T.date_source.value_counts(), sep="\n")


if __name__ == "__main__":
    main()
