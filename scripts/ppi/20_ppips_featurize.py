#!/usr/bin/env python
"""PPIPS step 1: BURROW (AF mode, default preset, `all` ranker) on the AFDB dimers needed for P-ortho / P-sym,
cached through the pocket adapter (src/pocketcompare/pockets.py; DESIGN §2.2/§2.5).

Dimers = every complex in a cross-species interolog pair with pair identity < 0.30
(data/processed/dimers/orthology/interologs.tsv, from 06_orthology_feasibility.py) -> 1,991 complexes
(their 1,216 homodimers also serve P-sym).
Writes data/processed/cache/points/ppips/<modelEntityId>.npz (+ timing.parquet, summary.json) and
logs/ppips_featurize.done.  Resumable (existing npz with the same adapter version are kept).
Usage: python scripts/ppi/20_ppips_featurize.py --workers 16
"""
from __future__ import annotations

import os

for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DIM = ROOT / "data/processed/dimers"
OUT = ROOT / "data/processed/cache/points/ppips"
MAX_IDENT = 0.30


def needed_complexes() -> pd.DataFrame:
    il = pd.read_csv(DIM / "orthology/interologs.tsv", sep="\t")
    x = il[(il.org1 != il.org2) & (il.pair_ident < MAX_IDENT)]
    cx = set(x.cx1) | set(x.cx2)
    m = pd.read_csv(DIM / "manifest.tsv", sep="\t").drop_duplicates("modelEntityId")
    return m[m.modelEntityId.isin(cx)].sort_values("modelEntityId").reset_index(drop=True)


def work(task: dict) -> dict:
    from pocketcompare import pockets as pk
    t0 = time.perf_counter()
    out = Path(task["out"])
    rec = {"key": task["key"], "status": "ok", "cached": False}
    if out.exists():
        try:
            fs = pk.Featurized.load(out)
            if fs.meta.get("adapter_version") == pk.ADAPTER_VERSION and fs.meta.get("af_mode"):
                rec.update(cached=True, n_points=len(fs.points), n_full=fs.n_pockets,
                           n_region=int(fs.pk_in_region.sum()), total_s=time.perf_counter() - t0)
                return rec
        except Exception:  # noqa: BLE001
            pass
    try:
        fs = pk.featurize_structure(task["path"], af_mode=True, key=task["key"])
        rec["bytes"] = fs.save(out)
        rec.update(fs.meta["timings"], n_atoms=len(fs.atom_xyz), n_points=len(fs.points), n_full=fs.n_pockets,
                   n_region=int(fs.pk_in_region.sum()))
    except Exception as e:  # noqa: BLE001
        rec.update(status="failed", error=f"{type(e).__name__}: {e}")
    rec["total_s"] = time.perf_counter() - t0
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    m = needed_complexes()
    if a.limit:
        m = m.head(a.limit)
    OUT.mkdir(parents=True, exist_ok=True)
    m[["modelEntityId", "organism", "type", "uniprotAccession_1", "uniprotAccession_2", "path"]].to_parquet(
        OUT / "complexes.parquet", index=False)
    tasks = [{"key": r.modelEntityId, "path": r.path, "out": str(OUT / f"{r.modelEntityId}.npz")}
             for r in m.itertuples()]
    print(f"[ppips] {len(tasks)} dimers -> {OUT}", flush=True)
    t0 = time.perf_counter()
    recs = []
    with ProcessPoolExecutor(a.workers, mp_context=get_context("spawn")) as ex:
        for i, f in enumerate(as_completed([ex.submit(work, t) for t in tasks]), 1):
            recs.append(f.result())
            if i % 200 == 0 or i == len(tasks):
                el = time.perf_counter() - t0
                print(f"[ppips] {i}/{len(tasks)} {el:.0f} s {i / el:.1f}/s", flush=True)
    tm = pd.DataFrame(recs).sort_values("key").reset_index(drop=True)
    tm.to_parquet(OUT / "timing.parquet", index=False)
    summ = {"n": len(tm), "ok": int((tm.status == "ok").sum()), "wall_s": time.perf_counter() - t0,
            "workers": a.workers, "disk_bytes": int(sum(p.stat().st_size for p in OUT.glob("*.npz"))),
            "failures": (tm.loc[tm.status != "ok", "error"].astype(str).str.slice(0, 100).value_counts().to_dict()
                         if "error" in tm else {})}
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))
    if not a.limit:
        (ROOT / "logs/ppips_featurize.done").write_text(time.strftime("%F %T") + "\n")


if __name__ == "__main__":
    main()
