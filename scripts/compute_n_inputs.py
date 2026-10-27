#!/usr/bin/env python
"""N1 / N2 input blocks (PREREG §1; reports/definition_robustness.md) for every pocket of a cached dataset (label-free).

    python scripts/compute_n_inputs.py --dataset prospeccts --label-free-structures --workers 22

Locators (as scripts/explore/defrob_compute.py): L-mode = the ligand shell (``lmode_idx``); D-mode = "U", the single
member of the matched merged BURROW pocket with maximal coverage of the L-mode points (pockets.best_member; the
same oracle use of the ligand as the D-mode definition).  Per locator S the blocks are
  a1_base  = A1 default (514) of S itself                (N2's "A1(best sub-pocket)" in D; the 4 Å shell in L)
  a1_sph8  = A1 default (514) of pockets.shape_site(S, "sph8")   (ligand-free 8 Å buried sphere)
  env_sph8 = a1r.env_descriptor (113) of the same sph8 set
so N1 = [a1_sph8 | env_sph8] (627 d) and N2 = [a1_base | a1_sph8 | env_sph8] (1,141 d); blocks are combined with a
1:1 block cosine by the consumer.  Output: data/processed/descriptors/<dataset>/n_inputs_{L,D}.npz (arrays + n_points,
vol_A3, t_* ms per pocket) and n_inputs_ids.parquet (pocket_id, row, has_D, u_member, u_coverage, d_match) with a
.prov.json sidecar.  Rows of both npz files follow n_inputs_ids.parquet; a pocket without D gets NaN rows in D.

--label-free-structures: needed for the sealed external sets (prospeccts, vertex); reads only the point cache built
from their pocket tables / structure files, never a label or pair file.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from compute_descriptors import _dmode_idx, load_light  # noqa: E402
from pocketcompare import pockets as pk  # noqa: E402
from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import a1r  # noqa: E402

CFG = A1.make_config()
D_A1 = A1.a1_layout(CFG)[-1].stop
D_ENV = a1r.env_layout()[-1]["stop"]
SEALED = {"prospeccts", "vertex"}
BLOCKS = ("a1_base", "a1_sph8", "env_sph8")
SCAL = ("n_points_base", "n_points_sph8", "vol_base_A3", "vol_sph8_A3", "t_shape_ms", "t_a1_base_ms",
        "t_a1_sph8_ms", "t_env_ms")


def describe(fs, at, S):
    d = {}
    t0 = time.perf_counter()
    I = pk.shape_site(fs, S, "sph8")
    d["t_shape_ms"] = 1e3 * (time.perf_counter() - t0)
    d["n_points_base"], d["n_points_sph8"] = len(S), len(I)
    d["vol_base_A3"] = float(fs.vol[S].sum() * fs.spacing ** 3)
    d["vol_sph8_A3"] = float(fs.vol[I].sum() * fs.spacing ** 3) if len(I) else 0.0
    feats = A1.needed_features(CFG)
    t0 = time.perf_counter()
    d["a1_base"], _ = A1.a1_descriptor(A1.pocket_input(fs, S, atom_types=at, features=feats), CFG)
    d["t_a1_base_ms"] = 1e3 * (time.perf_counter() - t0)
    if len(I):
        t0 = time.perf_counter()
        d["a1_sph8"], _ = A1.a1_descriptor(A1.pocket_input(fs, I, atom_types=at, features=feats), CFG)
        d["t_a1_sph8_ms"] = 1e3 * (time.perf_counter() - t0)
        t0 = time.perf_counter()
        d["env_sph8"] = a1r.env_descriptor(fs, I)
        d["t_env_ms"] = 1e3 * (time.perf_counter() - t0)
    return d


def work(rows):
    out = []
    for r in rows:
        rec = {"pocket_id": r["pocket_id"], "has_D": False, "u_member": -1, "u_coverage": np.nan, "L": None, "D": None,
               "error": None}
        try:
            fs = load_light(ROOT / r["cache_file"])
            at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
            L = np.asarray(r["lmode_idx"], np.int64)
            rec["L"] = describe(fs, at, L)
            mem = list(r["d_members"]) if r["d_members"] is not None else []
            if mem:
                m, c = pk.best_member(fs, L, mem)
                U = fs.pk_indices[fs.pk_indptr[m]:fs.pk_indptr[m + 1]].astype(np.int64)
                rec.update(has_D=True, u_member=int(m), u_coverage=float(c))
                rec["D"] = describe(fs, at, U)
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--chunk", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--label-free-structures", action="store_true")
    a = ap.parse_args()
    if a.dataset in SEALED and os.environ.get("FINAL_EVAL") != "1" and not a.label_free_structures:
        raise SystemExit(f"{a.dataset} is sealed: pass --label-free-structures (label-free) or FINAL_EVAL=1")
    t_start = time.time()
    f_index = ROOT / "data/processed/cache/points" / a.dataset / "index.parquet"
    index = pd.read_parquet(f_index)
    index = index[index.status == "ok"].reset_index(drop=True)
    if a.limit:
        index = index.iloc[:a.limit]
    rows = index[["pocket_id", "cache_file", "lmode_idx", "d_members"]].to_dict("records")
    tasks = [rows[s:s + a.chunk] for s in range(0, len(rows), a.chunk)]
    res = []
    with get_context("spawn").Pool(a.workers) as pool:
        for k, rr in enumerate(pool.imap(work, tasks)):
            res += rr
            if (k + 1) % max(1, len(tasks) // 10) == 0:
                print(f"  {k + 1}/{len(tasks)}  {time.time() - t_start:.0f}s", flush=True)
    out = Path(a.out) if a.out else ROOT / "data/processed/descriptors" / a.dataset
    out.mkdir(parents=True, exist_ok=True)
    n = len(res)
    dm = ((index.d_coverage >= 0.3) | (index.d_precision >= 0.5)).to_numpy()
    ids = pd.DataFrame({"pocket_id": [r["pocket_id"] for r in res], "row": np.arange(n),
                        "has_D": [r["has_D"] for r in res], "u_member": [r["u_member"] for r in res],
                        "u_coverage": [r["u_coverage"] for r in res], "d_match": dm[:n],
                        "error": [r["error"] for r in res]})
    dims = {"a1_base": D_A1, "a1_sph8": D_A1, "env_sph8": D_ENV}
    summ = {"n": n, "n_error": int(ids.error.notna().sum()), "n_has_D": int(ids.has_D.sum())}
    for mode in ("L", "D"):
        arr = {b: np.full((n, d), np.nan, np.float32) for b, d in dims.items()}
        sc = {k: np.full(n, np.nan) for k in SCAL}
        for i, r in enumerate(res):
            d = r[mode]
            if d is None:
                continue
            for b in arr:
                if b in d:
                    arr[b][i] = d[b]
            for k in sc:
                if k in d:
                    sc[k][i] = d[k]
        tmp = out / f"n_inputs_{mode}.tmp.npz"
        np.savez(tmp, **arr, **sc)
        os.replace(tmp, out / f"n_inputs_{mode}.npz")
        summ[mode] = {"n_ok_sph8": int(np.isfinite(arr["a1_sph8"][:, 0]).sum()),
                      "t_ms_median": {k: float(np.nanmedian(sc[k])) if np.isfinite(sc[k]).any() else None
                                      for k in SCAL if k.startswith("t_")}}
    (out / "n_inputs_layout.json").write_text(json.dumps({"a1": A1.layout_to_json(A1.a1_layout(CFG)),
                                                          "env": a1r.env_layout(), "dims": dims}))
    from pocketcompare.provenance import write_result
    write_result(out / "n_inputs_ids.parquet", ids, script=__file__, args=sys.argv[1:],
                 config={"a1": "default", "shaper": "sph8", "locator_D": "U (best member)",
                         "a1r_version": a1r.A1R_VERSION, "a1_version": A1.A1_VERSION},
                 inputs=[f_index], seed=None, device="cpu", start_time=t_start, extra=summ)
    print(json.dumps(summ, indent=1), f"\ndone {n} pockets in {time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
