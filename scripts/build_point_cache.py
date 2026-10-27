#!/usr/bin/env python
"""Build the BURROW point cache and the per-dataset pocket index (DESIGN §2.1; src/pocketcompare/pockets.py).

    python scripts/build_point_cache.py --dataset tough_m1 --workers 32

Reads ONLY data/processed/benchmarks/<dataset>_pockets.parquet (never a *_pairs.parquet / label file).
Writes (git-ignored):
    data/processed/cache/points/<dataset>/<structure_key>.npz   one per structure (pockets.Featurized.save)
    data/processed/cache/points/<dataset>/index.parquet         one row per benchmark pocket
    data/processed/cache/points/<dataset>/timing.parquet        one row per structure
    data/processed/cache/points/<dataset>/summary.json          headline numbers
and logs/build_point_cache_<dataset>.done on completion.

Existing cache files are re-used (index rebuilt from them) unless --overwrite or their adapter version / preset
differ.  Sealed test sets (prospeccts, vertex) are refused unless FINAL_EVAL=1 (DESIGN §2).
Output is deterministic: tasks and index rows are sorted, npz writes are byte-identical across runs.
"""
from __future__ import annotations

import os

for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"                                   # one core per worker
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "processed" / "benchmarks"
CACHE = ROOT / "data" / "processed" / "cache" / "points"
SEALED = {"prospeccts", "vertex"}
SUPPORTED = {"tough_m1", "tough_c1", "prospeccts", "vertex"}
POCKET_COLS = ["pocket_id", "structure_path", "chain", "pocket_def_type", "pocket_def", "ligand_file",
               "ligand_resname", "het_instances"]


def structure_keys(paths: list[str]) -> dict:
    """Deterministic file-name keys; a short path hash is appended where two paths share a stem."""
    stem = {p: re.sub(r"\.(pdb|ent|cif|mmcif)(\.gz)?$", "", Path(p).name, flags=re.I) for p in paths}
    count = pd.Series(list(stem.values())).value_counts()
    return {p: (s if count[s] == 1 else f"{s}_{hashlib.sha1(p.encode()).hexdigest()[:8]}")
            for p, s in stem.items()}


def _abs(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def _rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def run_structure(task: dict) -> tuple[list, dict]:
    """Featurise (or load) one structure and resolve all of its benchmark pockets."""
    from pocketcompare import pockets as pk
    t0 = time.perf_counter()
    key, out = task["key"], Path(task["cache_file"])
    tim = {"structure_key": key, "cached": False, "status": "ok", "error": None}
    fs = None
    if out.exists() and not task["overwrite"]:
        try:
            fs = pk.Featurized.load(out)
            if (fs.meta.get("adapter_version") != pk.ADAPTER_VERSION or fs.meta.get("preset") != task["preset"]
                    or fs.meta.get("ranker") != task["ranker"] or fs.meta.get("af_mode") != task["af_mode"]):
                fs = None
            else:
                tim["cached"] = True
        except Exception:  # noqa: BLE001  (corrupt/partial file -> recompute)
            fs = None
    if fs is None:
        try:
            fs = pk.featurize_structure(_abs(task["structure_path"]), chains=task["chains"], af_mode=task["af_mode"],
                                        preset=task["preset"], ranker=task["ranker"], key=key)
            ts = time.perf_counter()
            tim["bytes"] = fs.save(out)
            tim["save_s"] = time.perf_counter() - ts
            tim.update(fs.meta["timings"])
        except Exception as e:  # noqa: BLE001
            tim.update(status="failed", error=f"featurize: {type(e).__name__}: {e}")
            tim["total_s"] = time.perf_counter() - t0
            rows = [{"pocket_id": r["pocket_id"], "structure_key": key, "status": "failed",
                     "failure_reason": tim["error"]} for r in task["rows"]]
            return rows, tim
    tim.update(n_atoms=int(len(fs.atom_xyz)), n_points=int(len(fs.points)), n_full=int(fs.n_pockets),
               n_region=int(fs.pk_in_region.sum()))
    ti = time.perf_counter()
    merged = {w: pk.merge_pockets(fs, w) for w in ("region", "full")}
    rows = []
    for r in task["rows"]:
        row = {"pocket_id": r["pocket_id"], "structure_key": key, "cache_file": _rel(out),
               "status": "ok", "failure_reason": None, "n_points_structure": int(len(fs.points)),
               "n_full": int(fs.n_pockets), "n_region": int(fs.pk_in_region.sum()),
               "n_merged_region": len(merged["region"])}
        try:
            lp, rec = pk.resolve_pocket(fs, r, root=ROOT)
            row.update(definition=rec["definition"], lmode_idx=lp.idx.astype(np.int32), n_points=lp.n_points,
                       n_points_dense=int((fs.vol[lp.idx] == 1).sum()), volume_A3=lp.volume_A3,
                       n_lining_res=len(lp.residues), lining_residues=" ".join(lp.residues),
                       n_ligand_atoms=lp.info.get("n_ligand_atoms"),
                       ligand_protein_min_dist=lp.info.get("ligand_protein_min_dist"),
                       n_missing_residues=lp.info.get("n_missing_residues"))
            if "alt_definition" in rec:
                row.update(alt_definition=rec["alt_definition"], alt_idx=rec["alt_idx"].astype(np.int32),
                           alt_n_points=rec["alt_n_points"], alt_volume_A3=rec["alt_volume_A3"],
                           alt_jaccard=rec["alt_jaccard"], alt_n_missing_residues=rec["alt_n_missing_residues"],
                           alt_chain_remapped=rec["alt_chain_remapped"])
            elif "alt_error" in rec:
                row["alt_error"] = rec["alt_error"]
            if lp.n_points == 0:
                raise ValueError("empty L-mode pocket (no BURROW point within cutoff)")
            for w, pre in (("region", "d_"), ("full", "dfull_")):
                dm = pk.dmode_match(fs, lp.idx, merged=merged[w])
                row[pre + "coverage"] = dm.coverage
                row[pre + "missed"] = dm.missed
                if w == "region":
                    p = dm.pocket
                    row.update(d_members=np.asarray(p.members if p else [], np.int32),
                               d_n_points=len(p.idx) if p else 0, d_volume_A3=p.volume_A3 if p else 0.0,
                               d_score=p.score if p else np.nan, d_rank_in_merged=dm.rank_in_merged,
                               # diagnostic: fraction of the matched pocket's points <= 1.5 Å of L-mode points
                               d_precision=pk.coverage(fs, p.idx, lp.idx) if p else 0.0)
        except Exception as e:  # noqa: BLE001
            row.update(status="failed", failure_reason=f"{type(e).__name__}: {e}")
        rows.append(row)
    tim["index_s"] = time.perf_counter() - ti
    tim["total_s"] = time.perf_counter() - t0
    return rows, tim


def summarize(index: pd.DataFrame, timing: pd.DataFrame, out_dir: Path, wall_s: float, workers: int) -> dict:
    ok = index[index.status == "ok"]
    fresh = timing[(~timing.cached) & (timing.status == "ok")]
    du = sum(f.stat().st_size for f in out_dir.glob("*.npz"))
    q = lambda s: {k: float(s.quantile(v)) for k, v in (("p50", .5), ("p90", .9), ("p99", .99), ("max", 1.))} if len(s) else {}  # noqa: E731
    return {
        "n_pockets": int(len(index)), "n_ok": int(len(ok)), "success_rate": float(len(ok) / max(len(index), 1)),
        "failure_reasons": index.loc[index.status != "ok", "failure_reason"].str.slice(0, 120).value_counts().to_dict(),
        "n_structures": int(len(timing)), "n_structures_cached": int(timing.cached.sum()),
        "definition_counts": ok.definition.value_counts().to_dict() if len(ok) else {},
        "lmode_points": q(ok.n_points.astype(float)) if len(ok) else {},
        "lmode_volume_A3": q(ok.volume_A3) if len(ok) else {},
        "lmode_n_lining_res_p50": float(ok.n_lining_res.median()) if len(ok) else None,
        "alt_residue_def_points_p50": float(ok.alt_n_points.median()) if "alt_n_points" in ok else None,
        "alt_jaccard_p50": float(ok.alt_jaccard.median()) if "alt_jaccard" in ok else None,
        "dmode_region_miss_rate": float(ok.d_missed.mean()) if len(ok) else None,
        "dmode_region_coverage_p50": float(ok.d_coverage.median()) if len(ok) else None,
        "dmode_full_miss_rate": float(ok.dfull_missed.mean()) if len(ok) else None,
        "dmode_region_missed_but_precision_ge_0.5": float((ok.d_missed & (ok.d_precision >= 0.5)).mean())
        if len(ok) else None,
        "dmode_region_precision_p50": float(ok.d_precision.median()) if len(ok) else None,
        "alt_n_failed": int(ok.alt_error.notna().sum()) if "alt_error" in ok else 0,
        "alt_chain_remapped": int(ok.alt_chain_remapped.fillna(False).astype(bool).sum())
        if "alt_chain_remapped" in ok else 0,
        "alt_missing_residues_any": int((ok.alt_n_missing_residues.fillna(0) > 0).sum())
        if "alt_n_missing_residues" in ok else 0,
        "n_region_pockets_p50": float(ok.n_region.median()) if len(ok) else None,
        "n_merged_region_p50": float(ok.n_merged_region.median()) if len(ok) else None,
        "structure_points": q(timing.n_points.dropna().astype(float)) if "n_points" in timing else {},
        "time_per_structure_s": q(fresh.total_s) if len(fresh) else {},
        "time_featurize_s_p50": float((fresh.points_s + fresh.pockets_s).median()) if len(fresh) else None,
        "wall_s": wall_s, "workers": workers, "throughput_structures_per_s": len(timing) / max(wall_s, 1e-9),
        "disk_bytes_npz": int(du), "npz_bytes_p50": float(fresh.bytes.median()) if len(fresh) else None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True, choices=sorted(SUPPORTED))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--preset", default="default")
    ap.add_argument("--ranker", default="all")
    ap.add_argument("--af-mode", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="first N structures (smoke test)")
    ap.add_argument("--cache-root", default=str(CACHE))
    a = ap.parse_args(argv)
    if a.dataset in SEALED and os.environ.get("FINAL_EVAL") != "1":
        print(f"[cache] {a.dataset} is a sealed test set; refusing (set FINAL_EVAL=1 at final evaluation)")
        return 2
    t_start = time.perf_counter()
    tab = pd.read_parquet(BENCH / f"{a.dataset}_pockets.parquet")
    tab = tab[[c for c in POCKET_COLS if c in tab.columns]].sort_values("pocket_id", kind="stable")
    missing = tab.structure_path.isna()
    paths = sorted(tab.loc[~missing, "structure_path"].unique().tolist())
    keys = structure_keys(paths)
    out_dir = Path(a.cache_root) / a.dataset
    out_dir.mkdir(parents=True, exist_ok=True)
    by = {p: g.to_dict("records") for p, g in tab[~missing].groupby("structure_path", sort=True)}
    tasks = [{"key": keys[p], "structure_path": p, "chains": None, "rows": by[p],
              "cache_file": str(out_dir / f"{keys[p]}.npz"), "overwrite": a.overwrite,
              "preset": a.preset, "ranker": a.ranker, "af_mode": a.af_mode} for p in paths]
    tasks.sort(key=lambda t: t["key"])
    if a.limit:
        tasks = tasks[:a.limit]
    print(f"[cache] {a.dataset}: {len(tab)} pockets, {len(tasks)} structures, {int(missing.sum())} without file, "
          f"workers={a.workers} -> {out_dir}", flush=True)
    rows = [{"pocket_id": r.pocket_id, "structure_key": None, "status": "failed",
             "failure_reason": "no structure file in pocket table"} for r in tab[missing].itertuples()]
    timings = []
    done = 0
    with ProcessPoolExecutor(a.workers, mp_context=get_context("spawn")) as ex:
        futs = {ex.submit(run_structure, t): t["key"] for t in tasks}
        for f in as_completed(futs):
            try:
                r, tm = f.result()
            except Exception as e:  # noqa: BLE001  (worker crash, e.g. OOM)
                k = futs[f]
                t = next(t for t in tasks if t["key"] == k)
                r = [{"pocket_id": x["pocket_id"], "structure_key": k, "status": "failed",
                      "failure_reason": f"worker: {type(e).__name__}: {e}"} for x in t["rows"]]
                tm = {"structure_key": k, "status": "failed", "error": traceback.format_exc(limit=1), "cached": False}
            rows += r
            timings.append(tm)
            done += 1
            if done % 250 == 0 or done == len(tasks):
                el = time.perf_counter() - t_start
                print(f"[cache] {done}/{len(tasks)} structures, {el:.0f} s, {done / el:.1f}/s", flush=True)
    index = pd.DataFrame(rows).sort_values("pocket_id", kind="stable").reset_index(drop=True)
    timing = pd.DataFrame(timings).sort_values("structure_key", kind="stable").reset_index(drop=True)
    sfx = f".limit{a.limit}" if a.limit else ""
    index.to_parquet(out_dir / f"index{sfx}.parquet", index=False)
    timing.to_parquet(out_dir / f"timing{sfx}.parquet", index=False)
    summ = summarize(index, timing, out_dir, time.perf_counter() - t_start, a.workers)
    summ.update(dataset=a.dataset, preset=a.preset, ranker=a.ranker, af_mode=a.af_mode, limit=a.limit)
    (out_dir / f"summary{sfx}.json").write_text(json.dumps(summ, indent=1, sort_keys=True))
    print(json.dumps(summ, indent=1, sort_keys=True), flush=True)
    if not a.limit:
        (ROOT / "logs").mkdir(exist_ok=True)
        (ROOT / "logs" / f"build_point_cache_{a.dataset}.done").write_text(time.strftime("%F %T") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
