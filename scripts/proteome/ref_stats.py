#!/usr/bin/env python
"""Z-score reference statistics for the proteome index: TOUGH-M1-dev + BLiPS-train (v2) pocket pool, D-mode.

    python scripts/proteome/ref_stats.py --workers 16

Definition = the deployment definition: matched merged region-rule BURROW pocket (``d_members`` of the point
cache) -> bur16^4 centroid -> sph8 site -> A1 default + env.  TOUGH-M1-dev rows are read from the D11 exploration
(``data/processed/descriptors/tough_m1/defrob/D_sph8.npz``, same definition; 20 rows are re-computed here as a
check); BLiPS-train rows (``blips_sites_v2.parquet`` partition == train) are computed from the point cache
``blips``.  No test-set pocket (TOUGH-M1-test, BLiPS-test, ProSPECCTs, Vertex) is touched; no label is read
(only the split membership columns).

Output: data/processed/proteome_human/zstats.npz (a1_mean, a1_std, env_mean, env_std) + zstats.json.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "scripts/proteome")]

from compute_descriptors import _dmode_idx, load_light  # noqa: E402
from pocketcompare import pockets as pk  # noqa: E402
from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import a1r  # noqa: E402
from proteome_lib import CFG, FEATS, zstats  # noqa: E402

OUT = ROOT / "data/processed/proteome_human"
DR = ROOT / "data/processed/descriptors/tough_m1/defrob"


def work(rows):
    out = []
    for r in rows:
        fs = load_light(ROOT / r["cache_file"])
        at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        mem = list(r["d_members"]) if r["d_members"] is not None else []
        if not mem:
            out.append((r["pocket_id"], None, None))
            continue
        S = _dmode_idx(fs, mem)
        site = pk.shape_site(fs, S, "sph8")
        if len(site) == 0:
            out.append((r["pocket_id"], None, None))
            continue
        v, _ = A1.a1_descriptor(A1.pocket_input(fs, site, atom_types=at, features=FEATS), CFG)
        out.append((r["pocket_id"], v, a1r.env_descriptor(fs, site)))
    return out


def compute(index: pd.DataFrame, workers: int):
    rows = index[["pocket_id", "cache_file", "d_members"]].to_dict("records")
    tasks = [rows[s:s + 8] for s in range(0, len(rows), 8)]
    with get_context("spawn").Pool(workers) as pool:
        res = [x for rr in pool.imap(work, tasks) for x in rr]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    # TOUGH-M1-dev from the D11 exploration (same definition) + a recomputation check
    split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet", columns=["pocket_id", "partition"])
    dev_ids = set(split.pocket_id[split.partition == "dev"])
    ids = pd.read_parquet(DR / "ids.parquet")
    z = np.load(DR / "D_sph8.npz")
    m = ids.pocket_id.isin(dev_ids).to_numpy() & np.isfinite(z["a1"][:, 0]) & np.isfinite(z["env"][:, 0])
    t_a1, t_env = z["a1"][m], z["env"][m]
    tidx = pd.read_parquet(ROOT / "data/processed/cache/points/tough_m1/index.parquet")
    chk = tidx[tidx.pocket_id.isin(ids.pocket_id[m].iloc[:20])]
    chk_res = compute(chk, min(a.workers, 4))
    pos = {p: i for i, p in enumerate(ids.pocket_id[m])}
    dmax = max(float(np.max(np.abs(np.concatenate([v, e]) - np.concatenate([t_a1[pos[p]], t_env[pos[p]]]))))
               for p, v, e in chk_res if v is not None)
    # BLiPS-train (v2)
    sites = pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet", columns=["site_id", "partition"])
    tr = set(sites.site_id[sites.partition == "train"])
    bidx = pd.read_parquet(ROOT / "data/processed/cache/points/blips/index.parquet")
    bidx = bidx[bidx.pocket_id.isin(tr) & (bidx.status == "ok")]
    bres = [x for x in compute(bidx, a.workers) if x[1] is not None]
    b_a1 = np.stack([x[1] for x in bres])
    b_env = np.stack([x[2] for x in bres])
    A = np.concatenate([t_a1, b_a1]).astype(np.float64)
    E = np.concatenate([t_env, b_env]).astype(np.float64)
    a1_mean, a1_std = zstats(A)
    env_mean, env_std = zstats(E)
    np.savez(OUT / "zstats.npz", a1_mean=a1_mean, a1_std=a1_std, env_mean=env_mean, env_std=env_std,
             ref_a1=A.astype(np.float32), ref_env=E.astype(np.float32))
    h = hashlib.sha256(open(OUT / "zstats.npz", "rb").read()).hexdigest()
    info = dict(definition="D-mode: matched merged region pocket -> sph8 (bur16^4 centroid, 8 Å, bur10>=0.5); "
                           "A1 default (514) + env (113)",
                n_tough_m1_dev=int(m.sum()), n_blips_train=len(b_a1), n_blips_train_sites=len(tr),
                n_total=int(len(A)), a1_const_dims=int((a1_std == 0).sum()), env_const_dims=int((env_std == 0).sum()),
                recompute_check_n=len(chk_res), recompute_check_maxabs=dmax, sha256=h,
                sources=["data/processed/descriptors/tough_m1/defrob/D_sph8.npz",
                         "data/splits/tough_m1_pockets_split.parquet (partition==dev)",
                         "data/splits/blips_sites_v2.parquet (partition==train)",
                         "data/processed/cache/points/blips/"])
    (OUT / "zstats.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
