#!/usr/bin/env python
"""L4 point sets (label-free): sph8 site points of every pocket used by A4b, capped at 256 by vol-weighted FPS.

    python scripts/l4_extract.py --dataset blips --workers 16        # blips | blips_test_holo | blips_test_af |
                                                                      # tough_m1 | ppips | all

Locators are exactly those of the N1 / N2 inputs (pocketcompare.a4b): L = ligand shell (index ``lmode_idx``),
U = the best-covering BURROW sub-pocket (``u_member`` of the a1r ids table, i.e. the member N1 was computed on),
PPIPS D = union of the merged region pocket's members.  Shaper = ``pockets.shape_site(.., "sph8")``; per point
see ``pocketcompare.l4.site_points``.  Rows follow ``a4b.ids_table(dataset)`` (n_sph8 is checked against the a1r
``n_points`` of the same (locator, sph8) set).  Output: data/processed/l4/<dataset>/{<loc>.npz, ids.parquet(+prov)}.
Never reads a label or pair table.
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

from compute_descriptors import _dmode_idx, load_index, load_light  # noqa: E402
from pocketcompare import a4b as A4  # noqa: E402
from pocketcompare import l4 as L4  # noqa: E402
from pocketcompare import pockets as pk  # noqa: E402
from pocketcompare.descriptors import a1 as A1  # noqa: E402

OUT = ROOT / "data/processed/l4"
DATASETS = ("blips", "blips_test_holo", "blips_test_af", "tough_m1", "ppips")


def locs_of(dataset):
    return ("D",) if dataset == "ppips" else ("L", "U")


def work(task):
    dataset, cache_file, rows = task
    out = []
    t0 = time.perf_counter()
    fs = load_light(ROOT / cache_file)
    at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
    t_struct = 1e3 * (time.perf_counter() - t0)
    cfg = A1.make_config()
    for r in rows:
        rec = {"row": r["row"], "pocket_id": r["pocket_id"], "sets": {}, "error": None, "t_struct_ms": t_struct}
        S = {}
        if dataset == "ppips":
            mem = list(r["d_members"]) if r["d_members"] is not None else []
            if mem:
                S["D"] = _dmode_idx(fs, mem)
        else:
            L = np.asarray(r["lmode_idx"] if r["lmode_idx"] is not None else [], np.int64)
            if len(L):
                S["L"] = L
            if r["u_member"] >= 0:
                m = int(r["u_member"])
                S["U"] = fs.pk_indices[fs.pk_indptr[m]:fs.pk_indptr[m + 1]].astype(np.int64)
        for loc, idx in S.items():
            try:
                t0 = time.perf_counter()
                I = pk.shape_site(fs, idx, "sph8")
                if len(I) == 0:
                    rec["sets"][loc] = {"n_sph8": 0}
                    continue
                d = L4.site_points(fs, I, at, a1_cfg=cfg)
                d["t_ms"] = 1e3 * (time.perf_counter() - t0)
                rec["sets"][loc] = d
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{loc}: {e!r}"
        out.append(rec)
    return out


def run(dataset, workers, limit=None):
    t_start = time.time()
    ids = A4.ids_table(dataset).reset_index(drop=True)
    index = load_index(dataset)
    index = index[index.status == "ok"].set_index("pocket_id")
    ids = ids.iloc[:limit] if limit else ids
    rows = pd.DataFrame({"row": np.arange(len(ids)), "pocket_id": ids.pocket_id.to_numpy()})
    rows["cache_file"] = index.cache_file.loc[rows.pocket_id].to_numpy()
    rows["lmode_idx"] = index.lmode_idx.loc[rows.pocket_id].to_numpy() if dataset != "ppips" else None
    rows["d_members"] = index.d_members.loc[rows.pocket_id].to_numpy()
    rows["u_member"] = ids.u_member.fillna(-1).astype(int).to_numpy() if "u_member" in ids else -1
    tasks = [(dataset, cf, g.to_dict("records")) for cf, g in rows.groupby("cache_file", sort=True)]
    print(f"[l4_extract] {dataset}: {len(rows)} pockets, {len(tasks)} structures, {workers} workers", flush=True)
    res = []
    with get_context("spawn").Pool(workers) as pool:
        for k, rr in enumerate(pool.imap_unordered(work, tasks, chunksize=4)):
            res += rr
            if (k + 1) % max(1, len(tasks) // 5) == 0:
                print(f"  {k + 1}/{len(tasks)}  {time.time() - t_start:.0f}s", flush=True)
    res.sort(key=lambda r: r["row"])
    n = len(res)
    out = OUT / dataset
    out.mkdir(parents=True, exist_ok=True)
    tab = pd.DataFrame({"pocket_id": [r["pocket_id"] for r in res], "row": np.arange(n),
                        "error": [r["error"] for r in res], "t_struct_ms": [r["t_struct_ms"] for r in res]})
    summ = {"n": n, "n_error": int(tab.error.notna().sum())}
    files = {}
    for loc in locs_of(dataset):
        sizes = np.zeros(n, np.int64)
        parts = {k: [] for k in ("xyz", "feats", "types", "vol")}
        nsph, tms = np.zeros(n, np.int64), np.full(n, np.nan)
        for i, r in enumerate(res):
            d = r["sets"].get(loc)
            if d is None:
                nsph[i] = -1
                continue
            nsph[i] = d["n_sph8"]
            if d["n_sph8"] == 0:
                continue
            sizes[i] = len(d["xyz"])
            tms[i] = d["t_ms"]
            for k in parts:
                parts[k].append(d[k])
        indptr = np.concatenate([[0], np.cumsum(sizes)])
        arr = {"indptr": indptr, "xyz": np.concatenate(parts["xyz"]).astype(np.float32),
               "feats": np.concatenate(parts["feats"]).astype(np.float16),
               "types": np.concatenate(parts["types"]).astype(np.float16),
               "vol": np.concatenate(parts["vol"]).astype(np.float32)}
        f = out / f"{loc}.npz"
        tmp = out / f"{loc}.tmp.npz"
        np.savez(tmp, **arr)
        os.replace(tmp, f)
        files[f.name] = str(f)
        tab[f"n_sph8_{loc}"] = nsph
        tab[f"n_pts_{loc}"] = sizes
        tab[f"t_ms_{loc}"] = tms
        tab[f"has_{loc}"] = sizes > 0
        # consistency with the a1r (N1) sph8 set of the same locator
        a1r_loc = A4.locator(dataset, "L" if loc == "L" else "D")
        with np.load(A4.a1r_dir(dataset) / f"{a1r_loc}_sph8.npz") as z:
            ref_n = z["n_points"]
        ref_ids = A4.ids_table(dataset).pocket_id.to_numpy()[:n]
        assert (ref_ids == tab.pocket_id.to_numpy()).all()
        refn = np.where(np.isfinite(ref_n[:n]), ref_n[:n], -1).astype(int)
        ok = nsph >= 0
        mism = int((refn[ok] != nsph[ok]).sum())
        summ[loc] = {"n_sets": int((sizes > 0).sum()), "n_empty_sph8": int((nsph == 0).sum()),
                     "n_no_locator": int((nsph < 0).sum()), "n_capped": int((nsph > L4.CAP).sum()),
                     "pts_median": float(np.median(sizes[sizes > 0])), "sph8_median": float(np.median(nsph[nsph > 0])),
                     "t_ms_median": float(np.nanmedian(tms)), "t_ms_p90": float(np.nanpercentile(tms, 90)),
                     "n_mismatch_vs_a1r_sph8": mism, "bytes": int(f.stat().st_size)}
        if mism:
            print(f"WARNING {dataset} {loc}: {mism} sph8 size mismatches vs a1r", flush=True)
    fn = load_light(ROOT / rows.cache_file.iloc[0]).feature_names
    (out / "layout.json").write_text(json.dumps({"feature_names": fn, "type_channels": list(A1.TYPE_CHANNELS), "cap": L4.CAP,
                                                 "l4_version": L4.L4_VERSION}))
    from pocketcompare.provenance import sha256_file, write_result
    write_result(out / "ids.parquet", tab, script=__file__, args=sys.argv[1:],
                 config={"shaper": "sph8", "cap": L4.CAP, "fps": "vol-weighted (w^(1/3)), start nearest centroid",
                         "locators": list(locs_of(dataset)), "l4_version": L4.L4_VERSION},
                 inputs=[A4.a1r_dir(dataset) / "ids.parquet"], seed=None, device="cpu", start_time=t_start,
                 extra={**summ, "files_sha256": {k: sha256_file(v) for k, v in files.items()}})
    summ["wall_s"] = time.time() - t_start
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    for d in (DATASETS if a.dataset == "all" else a.dataset.split(",")):
        run(d, a.workers, a.limit)


if __name__ == "__main__":
    main()
