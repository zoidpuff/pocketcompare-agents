#!/usr/bin/env python
"""D11 exploration, item 1c: set-to-set best-match over BURROW sub-pockets (no oracle choice of one member).

    python scripts/explore/defrob_setmatch.py compute --workers 16     # label-free, all 7,524 pockets
    python scripts/explore/defrob_setmatch.py eval                     # one labelled variant -> trials.tsv

D-mode site of a pocket = the SET of members of its matched merged BURROW pocket, each described by
A1 + env on the sph8 shaper around that member (as the 'sph8U' definition, but for every member).  D-mode pair
score = max over member pairs of the block cosine (A1 and env z-scored separately on the dev member rows, weights
1:1).  L-mode = the single L_sph8 site (identical to variant a1@sph8U+env@sph8U).  Agreement: own D set among all
matched dev pockets' D sets scored by max_k cos(L_i, member_jk) on the union z-scoring.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "scripts/explore")]

DR = ROOT / "data/processed/descriptors/tough_m1/defrob"
VARIANT = "a1@sph8S+env@sph8S (set max)"


def work(rows):
    from compute_descriptors import load_light
    from pocketcompare import pockets as pk
    from pocketcompare.descriptors import a1 as A1
    from pocketcompare.descriptors import a1r
    cfg = A1.make_config()
    out = []
    for r in rows:
        if r["d_members"] is None or len(r["d_members"]) == 0:
            continue
        fs = load_light(ROOT / r["cache_file"])
        at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        for m in sorted(int(x) for x in r["d_members"]):
            t0 = time.perf_counter()
            I = pk.shape_site(fs, fs.pk_indices[fs.pk_indptr[m]:fs.pk_indptr[m + 1]], "sph8")
            if len(I) == 0:
                continue
            v, _ = A1.a1_descriptor(A1.pocket_input(fs, I, atom_types=at, features=A1.needed_features(cfg)), cfg)
            e = a1r.env_descriptor(fs, I)
            out.append((r["pocket_id"], m, v, e, 1e3 * (time.perf_counter() - t0)))
    return out


def cmd_compute(a):
    idx = pd.read_parquet(ROOT / "data/processed/cache/points/tough_m1/index.parquet")
    rows = idx[["pocket_id", "cache_file", "d_members"]].to_dict("records")
    tasks = [rows[s:s + 16] for s in range(0, len(rows), 16)]
    res = []
    with get_context("spawn").Pool(a.workers) as pool:
        for rr in pool.imap(work, tasks):
            res += rr
    np.savez(DR / "D_sph8_members.npz", pocket_id=np.array([r[0] for r in res]), member=np.array([r[1] for r in res]),
             a1=np.stack([r[2] for r in res]), env=np.stack([r[3] for r in res]), t_ms=np.array([r[4] for r in res]))
    print(f"{len(res)} member sites", flush=True)


def cmd_eval(a):
    import defrob_eval as R
    from pocketcompare.provenance import append_trial, write_result
    from pocketcompare.seeds import SEEDS
    from pocketcompare.similarity import ZScorer
    from pocketcompare import evaluate as ev

    ds, rows = R.setup()
    P = ds.pockets
    y = ds.pairs.y.to_numpy().astype(bool)
    dm = P.d_match.to_numpy()
    dset = dm[ds.ia] & dm[ds.ib]
    z = np.load(DR / "D_sph8_members.npz")
    pid2i = {p: i for i, p in enumerate(P.pocket_id)}
    own = np.array([pid2i.get(p, -1) for p in z["pocket_id"]])
    keep = (own >= 0) & dm[np.clip(own, 0, None)]
    own, A, Ev = own[keep], z["a1"][keep].astype(float), z["env"][keep].astype(float)
    parts = R.variant_parts("a1@sph8U+env@sph8U")
    sL, _, dim = R.mode_scores(parts, "L", ds, rows, np.ones(len(P), bool))
    # D: member embeddings, z-scored on the dev member rows
    EM = R.embed_parts([A, Ev], [1.0, 1.0], np.arange(len(own)))
    members = [np.flatnonzero(own == i) for i in range(len(P))]
    sD = np.full(len(y), np.nan)
    for k in np.flatnonzero(dset):
        Ma, Mb = members[ds.ia[k]], members[ds.ib[k]]
        if len(Ma) and len(Mb):
            sD[k] = (EM[Ma] @ EM[Mb].T).max()
    sD = np.where(dset, np.nan_to_num(sD, nan=np.nanmin(sD[dset])), np.nan)
    # agreement (union z-scoring of L rows and member rows)
    mL = [R.part_matrix(p, "L", rows) for p in parts]
    ok = np.array([dm[i] and len(members[i]) > 0 for i in range(len(P))])
    li = np.flatnonzero(ok)
    E = R.embed_parts([np.concatenate([mL[0][li], A]), np.concatenate([mL[1][li], Ev])], [1.0, 1.0],
                      np.arange(len(li) + len(own)))
    EL, EMu = E[:len(li)], E[len(li):]
    S = EL @ EMu.T                                                     # (n_L, n_members)
    Smax = np.full((len(li), len(li)), -np.inf)
    pos = {i: j for j, i in enumerate(li)}
    for m, i in enumerate(own):
        if i in pos:
            Smax[:, pos[i]] = np.maximum(Smax[:, pos[i]], S[:, m])
    d = np.diag(Smax)
    off = ~np.eye(len(li), dtype=bool)
    agree = float((((Smax < d[:, None]) & off).sum(1) / (len(li) - 1)).mean())
    ref = R.S_REF if hasattr(R, "S_REF") else None
    rL, _, _ = R.mode_scores(R.variant_parts(R.REF), "L", ds, rows, np.ones(len(P), bool))
    rD, _, _ = R.mode_scores(R.variant_parts(R.REF), "D", ds, rows, dm)
    rD = np.where(dset, rD, np.nan)
    ci, cj = P.unit.to_numpy()[ds.ia], P.unit.to_numpy()[ds.ib]
    cov = ev.size_covariates(P.logv_L.to_numpy()[ds.ia], P.logv_L.to_numpy()[ds.ib])
    _, b = R._boot_task((VARIANT, y, sL, sD, rL, rD, dset, ds.pos_cluster, cov, ci, cj, a.B, SEEDS[0], None))
    rec = {"variant": VARIANT, "dims": dim, "agree_auc": agree, "n_member_sites": int(len(own)),
           "ms_member_median": float(np.median(z["t_ms"])), "auc_L": ev.roc_auc(y, sL), "auc_D": ev.roc_auc(y[dset], sD[dset])}
    for k, r in b.items():
        rec.update({k: r.estimate, k + "_lo": r.ci_low, k + "_hi": r.ci_high})
    out = R.OUT / "eval_setmatch.parquet"
    write_result(out, pd.DataFrame([rec]), script=__file__, args=sys.argv, config={"variant": VARIANT, "B": a.B},
                 inputs=list(ds.inputs) + [DR / "D_sph8_members.npz"], seed=SEEDS[0], device="cpu")
    for mode in ("L", "D"):
        append_trial("A1R-explore", {"variant": VARIANT, "mode": mode, "B": a.B, "seed": SEEDS[0], "ref": R.REF,
                                     "variant_tag": "setmatch"}, "tough_m1_dev",
                     {"auc": rec[f"auc_{mode}"], "auc_cb": rec[f"cb_{mode}"], "auc_cb_lo": rec[f"cb_{mode}_lo"],
                      "auc_cb_hi": rec[f"cb_{mode}_hi"], "auc_strat": rec[f"strat_{mode}"],
                      "cb_mean_LD": rec["cb_mean"], "d_cb_mean_vs_ref": rec["d_cb_mean_vs_ref"], "agree_auc": agree,
                      "dims": dim}, out)
    print(pd.Series(rec).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("compute", "eval"))
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--B", type=int, default=1000)
    a = ap.parse_args()
    (cmd_compute if a.cmd == "compute" else cmd_eval)(a)


if __name__ == "__main__":
    main()
