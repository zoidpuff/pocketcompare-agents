#!/usr/bin/env python
"""A2: seed reproducibility of the docking profile (DESIGN §3 A2 / reviews/round1_domain.md §2).

Per pocket x panel: Pearson r of the 128 scores between seed pairs (and of the ligand-efficiency vector and
the rank vector).  Per molecule: top-pose heavy-atom RMSD between seeds (no symmetry correction, so an upper
bound).  Writes results/a2/repro.json and prints a summary.
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/processed/docking/tough_m1/raw_repro_L"
OUT = ROOT / "results/a2"


def main():
    df = pd.concat([pd.read_parquet(p) for p in sorted(RAW.glob("shard*.parquet"))], ignore_index=True)
    seeds = sorted(df.seed.unique())
    poses = {}
    for p in sorted(RAW.glob("shard*_poses.npz")):
        with np.load(p, allow_pickle=False) as z:
            poses.update({k: z[k] for k in z.files})
    rep = {"n_pockets": int(df.pocket_id.nunique()), "seeds": [int(s) for s in seeds], "panels": {}}

    for panel, dp in df.groupby("panel"):
        piv = dp.pivot_table(index=["pocket_id", "seed"], columns="mol_id",
                             values=["score", "le"], aggfunc="first")
        rs, rl, rrank = [], [], []
        for pid, g in piv.groupby(level=0):
            S = g["score"].to_numpy()
            L = g["le"].to_numpy()
            R = np.apply_along_axis(lambda v: pd.Series(v).rank().to_numpy(), 1, S)
            for i, j in combinations(range(len(S)), 2):
                rs.append(np.corrcoef(S[i], S[j])[0, 1])
                rl.append(np.corrcoef(L[i], L[j])[0, 1])
                rrank.append(np.corrcoef(R[i], R[j])[0, 1])
        q = lambda v: dict(mean=float(np.mean(v)), median=float(np.median(v)), p05=float(np.percentile(v, 5)),
                           min=float(np.min(v)), frac_ge_095=float(np.mean(np.asarray(v) >= 0.95)))
        rep["panels"][panel] = {"score_r": q(rs), "le_r": q(rl), "rank_r": q(rrank)}

    # top-pose RMSD across seeds (per molecule), split by panel via the row order of the raw frame
    order = (df[df.seed == seeds[0]].sort_values(["pocket_id"])
             .groupby("pocket_id", sort=True).agg(panel=("panel", list), nh=("n_heavy", list)))
    rmsd = {p: [] for p in df.panel.unique()}
    for pid, row in order.iterrows():
        mats = []
        for s in seeds:
            k = f"{pid}|{s}"
            if k not in poses:
                break
            mats.append(poses[k])
        if len(mats) != len(seeds):
            continue
        nh = np.asarray(row["nh"])
        ends = np.cumsum(nh)
        starts = ends - nh
        for a, b in combinations(range(len(seeds)), 2):
            for m, (s0, e0) in enumerate(zip(starts, ends)):
                d = mats[a][s0:e0] - mats[b][s0:e0]
                rmsd[row["panel"][m]].append(float(np.sqrt((d ** 2).sum(1).mean())))
    for p, v in rmsd.items():
        v = np.asarray(v)
        rep["panels"][p]["top_pose_rmsd_A"] = dict(
            n=int(v.size), median=float(np.median(v)), mean=float(v.mean()),
            p90=float(np.percentile(v, 90)), frac_le_2A=float((v <= 2.0).mean()),
            frac_le_1A=float((v <= 1.0).mean()))

    # stability of the pose-interaction block itself (the descriptor the poses feed, not the poses)
    from pocketcompare.descriptors.a2 import CONTACT_FEATURES
    for panel, dp in df.groupby("panel"):
        piv = dp.pivot_table(index=["pocket_id", "seed"], columns="mol_id", values=list(CONTACT_FEATURES),
                             aggfunc="first")
        rr = []
        for pid, g in piv.groupby(level=0):
            V = g.to_numpy()
            for i, j in combinations(range(len(V)), 2):
                if V[i].std() > 0 and V[j].std() > 0:
                    rr.append(np.corrcoef(V[i], V[j])[0, 1])
        rep["panels"][panel]["ifp_r"] = dict(mean=float(np.mean(rr)), median=float(np.median(rr)),
                                             p05=float(np.percentile(rr, 5)), min=float(np.min(rr)),
                                             frac_ge_095=float(np.mean(np.asarray(rr) >= 0.95)))

    # non-binder / in-pocket diagnostics
    rep["in_pocket_rate"] = {k: float(v) for k, v in df.groupby("panel").in_pocket.mean().items()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "repro.json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    print(json.dumps(rep, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
