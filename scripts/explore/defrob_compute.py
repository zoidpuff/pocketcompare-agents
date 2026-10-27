#!/usr/bin/env python
"""Definition-robustness exploration (D11): descriptors of every TOUGH-M1 pocket under ligand-free site shapers.

    python scripts/explore/defrob_compute.py --workers 16          # all 7,524 pockets, label-free

Locators (where the site is):  L = L-mode ligand shell (index ``lmode_idx``);  D = matched merged BURROW pocket
(``d_members`` union, as in the dev evaluation);  U = the single member of the matched merged pocket with maximal
coverage of the L-mode points (unmerged D-mode; same oracle use of the ligand as D).
Shapers (what is described; ``pocketcompare.pockets.shape_site``): base, res, sph6, sph8, sph10, core8.
Descriptors per (locator, shaper): A1 default (514 dims; blocks sliced at evaluation), B1 (45), env (113,
``pocketcompare.descriptors.a1r``).  Per-pocket times (ms, one thread, excl. npz I/O) are stored per descriptor
and for the shaper.

Output: data/processed/descriptors/tough_m1/defrob/<loc>_<shaper>.npz (a1, b1, env, vol_A3, n_points,
t_shape, t_a1, t_b1, t_env; rows = index order) + ids.parquet (pocket_id, has_D, U member, U coverage).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from compute_descriptors import _dmode_idx, load_light  # noqa: E402
from pocketcompare import pockets as pk  # noqa: E402
from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import a1r  # noqa: E402
from pocketcompare.descriptors import baselines as BL  # noqa: E402

LOCATORS = ("L", "D", "U")
SHAPERS = pk.SHAPERS
CFG = A1.make_config()
D_A1 = A1.a1_layout(CFG)[-1].stop
D_ENV = a1r.env_layout()[-1]["stop"]
D_B1 = 45
OUT = ROOT / "data/processed/descriptors/tough_m1/defrob"


def work(rows):
    out = []
    for r in rows:
        fs = load_light(ROOT / r["cache_file"])
        at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        L = np.asarray(r["lmode_idx"], np.int64)
        mem = list(r["d_members"]) if r["d_members"] is not None else []
        loc = {"L": L}
        rec = {"pocket_id": r["pocket_id"], "has_D": bool(mem), "u_member": -1, "u_coverage": np.nan, "sets": {}}
        if mem:
            loc["D"] = _dmode_idx(fs, mem)
            m, c = pk.best_member(fs, L, mem)
            loc["U"] = fs.pk_indices[fs.pk_indptr[m]:fs.pk_indptr[m + 1]].astype(np.int64)
            rec.update(u_member=int(m), u_coverage=float(c))
        for ln, S in loc.items():
            for sh in SHAPERS:
                t0 = time.perf_counter()
                I = pk.shape_site(fs, S, sh)
                t_shape = time.perf_counter() - t0
                d = {"n_points": len(I), "vol_A3": float(fs.vol[I].sum() * fs.spacing ** 3), "t_shape": 1e3 * t_shape}
                if len(I) == 0:
                    rec["sets"][(ln, sh)] = d
                    continue
                t0 = time.perf_counter()
                pin = A1.pocket_input(fs, I, atom_types=at, features=A1.needed_features(CFG))
                d["a1"], _ = A1.a1_descriptor(pin, CFG)
                d["t_a1"] = 1e3 * (time.perf_counter() - t0)
                t0 = time.perf_counter()
                d["b1"], _ = BL.b1_descriptor(fs, I, residues=[])
                d["t_b1"] = 1e3 * (time.perf_counter() - t0)
                t0 = time.perf_counter()
                d["env"] = a1r.env_descriptor(fs, I)
                d["t_env"] = 1e3 * (time.perf_counter() - t0)
                rec["sets"][(ln, sh)] = d
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--chunk", type=int, default=8)
    a = ap.parse_args()
    t_start = time.time()
    index = pd.read_parquet(ROOT / "data/processed/cache/points/tough_m1/index.parquet")
    index = index[index.status == "ok"].reset_index(drop=True)
    if a.limit:
        index = index.iloc[:a.limit]
    rows = index[["pocket_id", "cache_file", "lmode_idx", "d_members"]].to_dict("records")
    tasks = [rows[s:s + a.chunk] for s in range(0, len(rows), a.chunk)]
    res = []
    with get_context("spawn").Pool(a.workers) as pool:
        for k, rr in enumerate(pool.imap(work, tasks)):
            res += rr
            if (k + 1) % max(1, len(tasks) // 20) == 0:
                print(f"  {k + 1}/{len(tasks)}  {time.time() - t_start:.0f}s", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    n = len(res)
    ids = pd.DataFrame({k: [r[k] for r in res] for k in ("pocket_id", "has_D", "u_member", "u_coverage")})
    ids.to_parquet(OUT / "ids.parquet", index=False)
    summ = {}
    for ln in LOCATORS:
        for sh in SHAPERS:
            arr = {"a1": np.full((n, D_A1), np.nan, np.float32), "b1": np.full((n, D_B1), np.nan, np.float32),
                   "env": np.full((n, D_ENV), np.nan, np.float32)}
            sc = {k: np.full(n, np.nan) for k in ("n_points", "vol_A3", "t_shape", "t_a1", "t_b1", "t_env")}
            for i, r in enumerate(res):
                d = r["sets"].get((ln, sh))
                if d is None:
                    continue
                for k in arr:
                    if k in d:
                        arr[k][i] = d[k]
                for k in sc:
                    if k in d:
                        sc[k][i] = d[k]
            np.savez(OUT / f"{ln}_{sh}.npz", **arr, **sc)
            summ[f"{ln}_{sh}"] = {"n_ok": int(np.isfinite(arr["a1"][:, 0]).sum()),
                                  "vol_median": float(np.nanmedian(sc["vol_A3"])),
                                  **{f"{k}_median_ms": float(np.nanmedian(sc[k])) for k in ("t_shape", "t_a1", "t_b1", "t_env")},
                                  **{f"{k}_p90_ms": float(np.nanpercentile(sc[k], 90)) for k in ("t_shape", "t_a1")}}
    (OUT / "summary.json").write_text(json.dumps({"n": n, "wall_s": time.time() - t_start,
                                                   "a1r_version": a1r.A1R_VERSION, "sets": summ}, indent=1))
    (OUT / "env_layout.json").write_text(json.dumps(a1r.env_layout()))
    (OUT / "a1_layout.json").write_text(json.dumps(A1.layout_to_json(A1.a1_layout(CFG))))
    print(f"done {n} pockets in {time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
