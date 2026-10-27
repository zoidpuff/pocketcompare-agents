#!/usr/bin/env python
"""Compute tier-1 pocket descriptors for every pocket of a cached dataset (label-free).

    python scripts/compute_descriptors.py --dataset tough_m1 --arm a1 --config all --mode both --workers 12
    python scripts/compute_descriptors.py --dataset tough_m1 --arm b1 --config all --mode both
    python scripts/compute_descriptors.py --dataset tough_m1 --arm b0 --mode both

Inputs : data/processed/cache/points/<dataset>/{index.parquet,<key>.npz} (pocketcompare.pockets point cache).
Outputs: data/processed/descriptors/<dataset>/<arm>_<config>_<mode>.npy        (n, d) float32, NaN rows = failed
         .../<arm>_<config>_<mode>.ids.parquet (+ .prov.json sidecar)          row order of the .npy
         .../<arm>_<config>_<mode>.layout.json                                 block layout / column names
L-mode: every pocket of the index.  D-mode: every pocket with a matched merged BURROW pocket (``d_members``
non-empty); ``d_coverage``, ``d_precision``, ``d_missed`` and ``d_match`` (coverage >= 0.3 or precision >= 0.5,
DESIGN §2.2) are carried in the ids table so callers apply the DESIGN rule themselves.
Per-pocket descriptor time (``time_ms``: pocket assembly + typing + descriptor, one thread, excluding npz I/O)
is recorded per row.

Dataset adapters (index -> rows; the TOUGH-M1 path is unchanged):
  tough_m1, blips, blips_test_holo, blips_test_af, ppi_l   point-cache index.parquet as written by build_point_cache.py
  ppips   data/processed/ppi/ppips/pockets.parquet (merged BURROW region-rule pockets of the AF dimers, >= 10 points;
          scripts/ppi/22_ppips_build.py); there is no ligand, so only mode D exists (pocket = union of the merged
          pocket's members); the ids table carries complex / is_interface / split instead of the d_* columns.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import baselines as BL  # noqa: E402

GRID = ROOT / "configs" / "a1_grid.yaml"
_KEYS = ("points", "X", "vol", "is_metal", "point_score", "feats", "feature_names", "atom_xyz", "atom_res",
         "atom_name", "atom_element", "res_names", "pk_indptr", "pk_indices", "meta")


def load_light(path) -> SimpleNamespace:
    """The arrays of a cached Featurized that descriptors need (no hetero atoms, no pocket descriptors)."""
    with np.load(path, allow_pickle=False) as z:
        d = {k: z[k] for k in _KEYS}
    meta = json.loads(str(d.pop("meta")))
    d["feature_names"] = d["feature_names"].tolist()
    ns = SimpleNamespace(**d, meta=meta, spacing=float(meta["feature_cfg"]["spacing"]))
    return ns


def a1_configs(name: str) -> dict:
    import yaml
    grid = yaml.safe_load(GRID.read_text())["configs"]
    names = list(grid) if name == "all" else name.split(",")
    return {n: A1.make_config(grid[n]) for n in names}


def arm_configs(arm: str, name: str) -> dict:
    if arm == "a1":
        return a1_configs(name)
    if arm == "b1":
        names = list(BL.B1_CONFIGS) if name == "all" else name.split(",")
        return {n: BL.B1_CONFIGS[n] for n in names}
    if arm == "b0":
        return {"default": {}}
    raise ValueError(arm)


def _dmode_idx(fs, members) -> np.ndarray:
    parts = [fs.pk_indices[fs.pk_indptr[m]:fs.pk_indptr[m + 1]] for m in members]
    return np.unique(np.concatenate(parts)) if parts else np.zeros(0, np.int64)


def work(task):
    """task = (arm, configs, modes, rows) -> list of result dicts (one per row x mode)."""
    arm, cfgs, modes, rows = task
    out = []
    for r in rows:
        t_io = time.perf_counter()
        try:
            fs = load_light(ROOT / r["cache_file"])
            err = None
        except Exception as e:  # noqa: BLE001
            fs, err = None, f"load: {e!r}"
        t_io = time.perf_counter() - t_io
        at = None
        if fs is not None and arm == "a1":
            t0 = time.perf_counter()
            at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
            t_type = time.perf_counter() - t0
        for mode in modes:
            if mode == "L":
                idx = np.asarray(r["lmode_idx"], np.int64)
            else:
                mem = list(r["d_members"]) if r["d_members"] is not None else []
                if not mem:
                    continue
                idx = None if fs is None else _dmode_idx(fs, mem)
            rec = {"pocket_id": r["pocket_id"], "mode": mode, "io_ms": 1e3 * t_io, "vec": {}, "time_ms": {},
                   "info": {}, "error": err}
            if fs is not None:
                rec["n_points"] = int(len(idx))
                rec["volume_A3"] = float(fs.vol[idx].sum() * fs.spacing ** 3)
                for cname, cfg in cfgs.items():
                    t0 = time.perf_counter()
                    try:
                        if arm == "a1":
                            feats = A1.needed_features(cfg)
                            pin = A1.pocket_input(fs, idx, atom_types=at, features=feats)
                            v, _, info = A1.a1_descriptor(pin, cfg, return_info=True)
                            rec["info"][cname] = info
                        elif arm == "b1":
                            v, _ = BL.b1_descriptor(fs, idx, learned=cfg["learned"], residues=[])
                        else:
                            v = BL.b0_descriptor(rec["volume_A3"])
                        rec["vec"][cname] = v
                    except Exception as e:  # noqa: BLE001
                        rec["vec"][cname] = None
                        rec["error"] = f"{cname}: {e!r}"
                    rec["time_ms"][cname] = 1e3 * (time.perf_counter() - t0)
                if arm == "a1":
                    rec["type_ms"] = 1e3 * t_type
            out.append(rec)
    return out


def layout_json(arm, cfg) -> list:
    if arm == "a1":
        return A1.layout_to_json(A1.a1_layout(cfg))
    if arm == "b1":
        names = BL.b1_columns(_b1_names(), cfg["learned"])
        return [{"name": "b1", "start": 0, "stop": len(names), "names": names}]
    return [{"name": "size", "start": 0, "stop": 1, "names": ["log_vol_A3"]}]


def _b1_names() -> list:
    idx = load_index(_DATASET)
    fs = load_light(ROOT / idx.cache_file.iloc[0])
    pidx = np.asarray(idx.lmode_idx.iloc[0]) if idx.lmode_idx.iloc[0] is not None \
        else _dmode_idx(fs, list(idx.d_members.iloc[0]))
    _, names = BL.burrow_pocket_descriptors(fs, pidx, residues=[])
    return names


_INDEX_PATH = None
_DATASET = None
PPIPS_POCKETS = ROOT / "data/processed/ppi/ppips/pockets.parquet"
D_ONLY = {"ppips"}


def index_path(dataset: str) -> Path:
    return PPIPS_POCKETS if dataset == "ppips" else ROOT / "data/processed/cache/points" / dataset / "index.parquet"


def load_index(dataset: str) -> pd.DataFrame:
    """Rows with pocket_id, structure_key, cache_file, lmode_idx, d_members, d_coverage, d_precision, d_missed."""
    if dataset != "ppips":
        return pd.read_parquet(index_path(dataset))
    P = pd.read_parquet(PPIPS_POCKETS)
    return pd.DataFrame(dict(pocket_id=P.pocket_id, structure_key=P.complex, status="ok",
                             cache_file=[f"data/processed/cache/points/ppips/{c}.npz" for c in P.complex],
                             lmode_idx=None, d_members=P.members, d_coverage=np.nan, d_precision=np.nan,
                             d_missed=False, complex=P.complex, is_interface=P.is_interface, split=P.split))


def main(argv=None):
    global _INDEX_PATH, _DATASET
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="tough_m1")
    ap.add_argument("--arm", choices=("a1", "b0", "b1"), required=True)
    ap.add_argument("--config", default="all", help="config name, comma list, or 'all'")
    ap.add_argument("--mode", choices=("L", "D", "both"), default="both")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=None, help="first N pockets only (smoke tests)")
    ap.add_argument("--chunk", type=int, default=16)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    t_start = time.time()
    if a.dataset in ("prospeccts", "vertex") and os.environ.get("FINAL_EVAL") != "1":
        raise SystemExit(f"{a.dataset} is sealed (FINAL_EVAL=1 required)")
    _DATASET = a.dataset
    _INDEX_PATH = index_path(a.dataset)
    out_dir = Path(a.out) if a.out else ROOT / "data/processed/descriptors" / a.dataset
    out_dir.mkdir(parents=True, exist_ok=True)
    index = load_index(a.dataset)
    index = index[index.status == "ok"].reset_index(drop=True)
    if a.limit:
        index = index.iloc[:a.limit]
    modes = ["L", "D"] if a.mode == "both" else [a.mode]
    if a.dataset in D_ONLY:
        if "L" in modes:
            print(f"[compute_descriptors] {a.dataset} has no L-mode pockets; computing D only", flush=True)
        modes = ["D"]
    cfgs = arm_configs(a.arm, a.config)
    cols = ["pocket_id", "structure_key", "cache_file", "lmode_idx", "d_members", "d_coverage", "d_precision",
            "d_missed"]
    rows = index[cols].to_dict("records")
    tasks = [(a.arm, cfgs, modes, rows[s:s + a.chunk]) for s in range(0, len(rows), a.chunk)]
    print(f"[compute_descriptors] {a.dataset} arm={a.arm} configs={list(cfgs)} modes={modes} "
          f"pockets={len(rows)} tasks={len(tasks)} workers={a.workers}", flush=True)
    results = []
    if a.workers <= 1:
        for k, t in enumerate(tasks):
            results += work(t)
    else:
        with get_context("spawn").Pool(a.workers) as pool:
            for k, res in enumerate(pool.imap(work, tasks)):
                results += res
                if (k + 1) % max(1, len(tasks) // 10) == 0:
                    print(f"  {k + 1}/{len(tasks)} tasks  {time.time() - t_start:.0f}s", flush=True)
    meta = index.set_index("pocket_id")
    try:
        from pocketcompare import provenance as prov
    except ImportError:
        prov = None
    summary = {}
    for mode in modes:
        recs = [r for r in results if r["mode"] == mode]
        for cname, cfg in cfgs.items():
            lay = layout_json(a.arm, cfg)
            dim = lay[-1]["stop"]
            V = np.full((len(recs), dim), np.nan, np.float32)
            ids = []
            for i, r in enumerate(recs):
                v = r["vec"].get(cname)
                if v is not None:
                    V[i] = v
                m = meta.loc[r["pocket_id"]]
                row = {"row": i, "pocket_id": r["pocket_id"], "structure_key": m.structure_key, "mode": mode,
                       "status": "ok" if v is not None else "failed", "error": r.get("error"),
                       "n_points": r.get("n_points"), "volume_A3": r.get("volume_A3"),
                       "n_cells": r["info"].get(cname, {}).get("n_cells"),
                       "time_ms": r["time_ms"].get(cname), "io_ms": r["io_ms"]}
                if a.dataset == "ppips":
                    row.update(complex=m.complex, is_interface=bool(m.is_interface), split=m.split)
                elif mode == "D":
                    row.update(d_coverage=float(m.d_coverage), d_precision=float(m.d_precision),
                               d_missed=bool(m.d_missed),
                               d_match=bool(m.d_coverage >= 0.3 or m.d_precision >= 0.5))
                ids.append(row)
            ids = pd.DataFrame(ids)
            stem = f"{a.arm}_{cname}_{mode}"
            npy = out_dir / f"{stem}.npy"
            tmp = out_dir / f"{stem}.tmp.npy"
            np.save(tmp, V)
            os.replace(tmp, npy)
            (out_dir / f"{stem}.layout.json").write_text(json.dumps(lay) + "\n")
            npy_sha = hashlib.sha256(npy.read_bytes()).hexdigest()
            ok = ids.status == "ok"
            tm = ids.time_ms[ok]
            stats = {"n": int(len(ids)), "n_failed": int((~ok).sum()), "dim": int(dim),
                     "time_ms_median": float(tm.median()) if len(tm) else None,
                     "time_ms_p90": float(tm.quantile(0.9)) if len(tm) else None,
                     "time_ms_max": float(tm.max()) if len(tm) else None}
            summary[stem] = stats
            extra = {"vectors": str(npy), "vectors_sha256": npy_sha, "shape": list(V.shape),
                     "layout": str(out_dir / f"{stem}.layout.json"), "arm": a.arm, "config_name": cname,
                     "mode": mode, "version": {"a1": A1.A1_VERSION, "b1": BL.B1_VERSION, "b0": BL.B0_VERSION}[a.arm],
                     "stats": stats}
            ids_path = out_dir / f"{stem}.ids.parquet"
            inputs = [_INDEX_PATH] + ([GRID] if a.arm == "a1" else [])
            if prov is not None:
                prov.write_result(ids_path, ids, script=__file__, args=sys.argv, config=cfg, inputs=inputs,
                                  seed=None, device="cpu", start_time=t_start, extra=extra)
            else:  # minimal sidecar
                ids.to_parquet(ids_path, index=False)
                import subprocess
                commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                                        text=True).stdout.strip()
                (ids_path.with_name(ids_path.name + ".prov.json")).write_text(json.dumps(
                    {"git_commit": commit, "args": sys.argv, "config": cfg, **extra}, indent=2, default=str))
            print(f"  wrote {stem}: {V.shape}, failed {stats['n_failed']}, "
                  f"median {stats['time_ms_median']:.2f} ms/pocket (p90 {stats['time_ms_p90']:.2f})", flush=True)
    print(f"[compute_descriptors] done in {time.time() - t_start:.0f}s", flush=True)
    return summary


if __name__ == "__main__":
    main()
