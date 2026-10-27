#!/usr/bin/env python
"""Fast GPU / fast CPU vs reference adapter (``pockets.featurize_structure``) on AF models, AF mode.

    python scripts/proteome/check_fast_equivalence.py DIR_WITH_PDB_GZ [--device cuda:2] [--out JSON]

Compares, per structure: points, canonical X, vol, is_metal, the 84 features, point scores, the full pocket
list (scores, centres, memberships, residues) and the v2 / region flags, plus the merged region pockets and the
A1(sph8)+env(sph8) descriptors of every merged pocket with >= 10 points.  Also times both paths (1 thread).
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/proteome"))

from pocketcompare import pockets as pk  # noqa: E402
from pocketcompare import pockets_fast as pf  # noqa: E402
from proteome_lib import describe_structure  # noqa: E402


def cmp(a, b):
    out = {}
    for k in ("points", "X", "vol", "is_metal", "feats", "point_score", "pk_score", "pk_center", "pk_indptr",
              "pk_indices", "pk_in_v2", "pk_in_region", "pk_residues", "res_ids", "atom_xyz"):
        x, y = getattr(a, k), getattr(b, k)
        if x.shape != y.shape:
            out[k] = f"shape {x.shape} vs {y.shape}"
        elif x.dtype.kind in "fc":
            d = float(np.max(np.abs(x.astype(np.float64) - y.astype(np.float64)))) if x.size else 0.0
            if d > 0:
                out[k] = f"maxabs {d:.3g}"
        elif not np.array_equal(x, y):
            out[k] = f"{int((x != y).sum())} differ"
    if list(a.feature_names) != list(b.feature_names):
        out["feature_names"] = "differ"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--device", default="cuda:2")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    files = sorted(Path(a.dir).glob("*.pdb.gz"))
    fm = pf.fast_model()
    from pocketdetect.burrow.fast.gpu import featurize_batch
    # warm-up (numba compile / CUDA context)
    it0, _ = pf.load_and_prep(files[0], "w")
    featurize_batch([it0], fm.cfg, a.device, fm)
    pf.featurize_fast_cpu(files[0], "w", fm=fm)
    pk.featurize_structure(files[0], af_mode=True, key="w")
    rows = []
    for f in files:
        key = f.name.split(".")[0]
        t0 = time.perf_counter()
        ref = pk.featurize_structure(f, af_mode=True, key=key)
        t_ref = time.perf_counter() - t0
        t0 = time.perf_counter()
        cpu = pf.featurize_fast_cpu(f, key, fm=fm)
        t_cpu = time.perf_counter() - t0
        t0 = time.perf_counter()
        it, info = pf.load_and_prep(f, key, fm=fm)
        t1 = time.perf_counter()
        (ps, sc), = featurize_batch([it], fm.cfg, a.device, fm)
        t2 = time.perf_counter()
        gpu = pf.featurized_from_points(it.P, ps, sc, fm, key)
        t3 = time.perf_counter()
        dr = describe_structure(ref)
        dg = describe_structure(gpu)
        same_desc = (len(dr["records"]) == len(dg["records"]) and
                     all(np.array_equal(x, y) for x, y in zip(dr["a1"], dg["a1"])) and
                     all(np.array_equal(x, y) for x, y in zip(dr["env"], dg["env"])))
        r = dict(key=key, n_points=len(ref.points), n_full=ref.n_pockets, n_region=int(ref.pk_in_region.sum()),
                 n_desc=len(dr["records"]), cpu_vs_ref=cmp(ref, cpu), gpu_vs_ref=cmp(ref, gpu),
                 desc_identical=bool(same_desc), t_ref_s=t_ref, t_fastcpu_s=t_cpu,
                 t_gpu_parse_prep_s=t1 - t0, t_gpu_feat_s=t2 - t1, t_gpu_post_s=t3 - t2)
        rows.append(r)
        print(json.dumps(r), flush=True)
    s = dict(n=len(rows), n_cpu_identical=sum(not r["cpu_vs_ref"] for r in rows),
             n_gpu_identical=sum(not r["gpu_vs_ref"] for r in rows),
             n_desc_identical=sum(r["desc_identical"] for r in rows),
             median_t_ref_s=float(np.median([r["t_ref_s"] for r in rows])),
             median_t_fastcpu_s=float(np.median([r["t_fastcpu_s"] for r in rows])),
             note="single structure, 1 thread, GPU batch size 1, shared node")
    print(json.dumps(s, indent=1))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"summary": s, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
