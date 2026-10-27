#!/usr/bin/env python
"""Write the BLiPS pocket tables read by scripts/build_point_cache.py (definitions: pocketcompare.datasets.blips).

    python scripts/data/prep_blips_pockets.py --part trainval          # -> data/processed/benchmarks/blips_pockets.parquet
    python scripts/data/prep_blips_pockets.py --part test --workers 24 # -> blips_test_{holo,af}_pockets.parquet

trainval: all non-test rows of data/splits/blips_sites.parquet (train + val of v1 = the D9 pool).
test    : reads data/sealed/blips_test_sites.parquet ONLY for site ids, structure ids, representative chains and
          the qualifying ligand set (q_ccds) -- the file is made readable (0400) for the read and set back to 000
          in a ``finally``.  blips_test_pairs.parquet is never opened.  Outputs carry no CCD codes.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_v] = "1"                                   # one core per worker

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.datasets import blips as BP  # noqa: E402

BENCH = ROOT / "data/processed/benchmarks"
SEALED_SITES = ROOT / "data/sealed/blips_test_sites.parquet"
TEST_COLS = ["site_id", "protein", "structure_id", "site_name", "pdb_id", "chain", "q_ccds"]


def read_sealed_sites() -> pd.DataFrame:
    os.chmod(SEALED_SITES, 0o400)
    try:
        return pd.read_parquet(SEALED_SITES, columns=TEST_COLS)
    finally:
        os.chmod(SEALED_SITES, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("trainval", "test"), required=True)
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    t0 = time.time()
    BENCH.mkdir(parents=True, exist_ok=True)
    if a.part == "trainval":
        S = pd.read_parquet(ROOT / "data/splits/blips_sites.parquet")
        S = S[S.partition != "test"]
        T = BP.trainval_table(S)
        T.to_parquet(BENCH / "blips_pockets.parquet", index=False)
        print(f"trainval: {len(T)} sites, {T.structure_key.nunique()} structures, "
              f"no ligand atoms {int((T.n_lig_instances == 0).sum())}, {time.time() - t0:.0f}s")
        return
    S = read_sealed_sites()
    assert S.site_id.str.startswith("af_set:").all()
    T_af = BP.test_af_rows(S)
    T_af.to_parquet(BENCH / "blips_test_af_pockets.parquet", index=False)
    print(f"test AF: {len(T_af)} sites, {T_af.structure_key.nunique()} models, "
          f"no ligand {int((T_af.n_lig_instances == 0).sum())}, fallback {int(T_af.lig_fallback.sum())}", flush=True)
    # holo: qualifying ligand keys per site from the Track C ground truth (status ok instances only)
    # holo chain = LIGYSIS representative chain; sites without one (non-benchmark LIGYSIS sites) use the source
    # chain of their first qualifying transferred instance (Track C transfer order: representative entry first,
    # then resolution) = Track C's own 'pdb_ligand_entry' reference.
    lg = pd.read_csv(BP.PD / "data/processed/af/af_ligands.csv", dtype={"chain": str}, keep_default_na=False)
    lg = lg[lg.status == "ok"]
    lig_chain = {(r.site_name, r.key): f"{r.pdb}_{r.chain}" for r in lg.itertuples()}
    tasks = []
    for acc, g in S.groupby("protein", sort=True):
        sites = []
        for sid_, gg in g.groupby("structure_id"):
            gt = BP._af_gt(sid_)
            by = {s["site_name"]: s for s in gt["sites"]}
            for r in gg.itertuples():
                q = set(r.q_ccds.split(";"))
                site = by[r.site_name]
                keys = [l["key"] for l in site["ligands"] if l["resname"] in q]
                fb = next((lig_chain[(r.site_name, k)] for k in keys if (r.site_name, k) in lig_chain), None)
                if isinstance(r.pdb_id, str) and r.pdb_id:
                    rc, src = f"{r.pdb_id}_{r.chain}", "ligysis_rep_chain"
                else:
                    rc, src = fb, "first_ligand_entry"
                # if no qualifying instance re-transfers onto rc at <= 2 A: the first instance's own source chain
                sites.append(dict(site_id=r.site_id, site_name=r.site_name, rep_chain=rc, holo_chain_source=src,
                                  fallback_chain=fb,
                                  residues=[int(x) for x in site["residues"]], keys=keys))
        tasks.append(dict(acc=acc, sites=sites))
    del S
    rows = []
    with ProcessPoolExecutor(a.workers, mp_context=get_context("spawn")) as ex:
        for k, res in enumerate(ex.map(BP.holo_protein, tasks, chunksize=4)):
            rows += res
            if (k + 1) % 250 == 0:
                print(f"  holo {k + 1}/{len(tasks)} proteins {time.time() - t0:.0f}s", flush=True)
    T_h = pd.DataFrame(rows).sort_values("pocket_id").reset_index(drop=True)
    T_h.to_parquet(BENCH / "blips_test_holo_pockets.parquet", index=False)
    summ = {"n_sites": len(T_h), "n_rep_chains": int(T_h.structure_key.nunique()),
            "holo_errors": T_h.holo_error.fillna("ok").str.slice(0, 160).value_counts().to_dict(),
            "holo_chain_source": T_h.holo_chain_source.value_counts().to_dict(),
            "af_no_ligand": int((T_af.n_lig_instances == 0).sum()), "af_fallback_rmsd_gt2": int(T_af.lig_fallback.sum()),
            "wall_s": time.time() - t0}
    (BENCH / "blips_test_prep_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
