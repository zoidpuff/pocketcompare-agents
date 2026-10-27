#!/usr/bin/env python
"""Cheap alternative to fragment docking: Vina-potential probe maps on BURROW pocket points (no pose search).

For each pocket: receptor atoms typed as in ADock (adock.typing.type_receptor), then for each of 10 XS probe types
(C_H C_P N_D N_A N_DA O_A O_DA S_P F_H Cl_H) the Vina inter energy (ADock 'vina' weights, 8 A cutoff) of a single
probe atom at every BURROW pocket point, relaxed by taking the minimum over a 3x3x3 lattice of +/-0.75 A offsets.
Fingerprint per pocket = for each probe: 5th/25th/50th percentile of point energies + fraction of points < -0.5
kcal/mol (40 numbers; all intensive, i.e. not sums over the pocket). CPU only (torch).
Output: results/feasibility/probe_fingerprints.tsv; timing printed (ms per pocket).
"""
import json
import time

import numpy as np
import pandas as pd
import torch
from scipy.spatial import cKDTree

from adock.config import load_config, sf_params
from adock.scoring import PairPotential
from adock.typing import type_receptor

PROBES = ["C_H", "C_P", "N_D", "N_A", "N_DA", "O_A", "O_DA", "S_P", "F_H", "Cl_H"]
torch.set_num_threads(1)
cfg = load_config()
sfp = sf_params(cfg, "vina")
pot = PairPotential(sfp, "cpu")
w = pot.weights()
cut = float(sfp["cutoff"])
pk = pd.read_csv("results/feasibility/pockets.tsv", sep="\t")
pts = np.load("results/feasibility/pocket_points.npz")
off = np.stack(np.meshgrid(*[np.array([-0.75, 0, 0.75])] * 3, indexing="ij"), -1).reshape(-1, 3)
pt_idx = [cfg["_xs_index"][p] for p in PROBES]
rows, times = [], []
for _, r in pk.iterrows():
    t0 = time.perf_counter()
    box = json.loads(r["box"])
    xyz, typ = type_receptor(r["receptor"], cfg, center=np.array(box["center"]), half_extent=np.array(box["size"]) / 2)
    t1 = time.perf_counter()
    P = pts[r["pocket_id"]].astype(np.float64)
    Q = (P[:, None, :] + off[None]).reshape(-1, 3)              # [n*27, 3]
    tree = cKDTree(xyz)
    pairs = tree.query_ball_point(Q, cut)
    qi = np.repeat(np.arange(len(Q)), [len(x) for x in pairs])
    aj = np.concatenate([np.asarray(x, dtype=np.int64) for x in pairs]) if len(qi) else np.zeros(0, np.int64)
    d = torch.tensor(np.linalg.norm(Q[qi] - xyz[aj], axis=1), dtype=torch.float32)
    tj = torch.tensor(typ[aj], dtype=torch.long)
    feats = {"pocket_id": r["pocket_id"]}
    for name, ti in zip(PROBES, pt_idx):
        e = (pot.terms(d, torch.full_like(tj, ti), tj) * w).sum(-1).numpy()
        E = np.bincount(qi, weights=e, minlength=len(Q)).reshape(len(P), len(off)).min(1)
        q = np.percentile(E, [5, 25, 50])
        feats.update({f"{name}_q05": q[0], f"{name}_q25": q[1], f"{name}_q50": q[2], f"{name}_fneg": float((E < -0.5).mean())})
    t2 = time.perf_counter()
    rows.append(feats)
    times.append((t1 - t0, t2 - t1, len(P)))
pd.DataFrame(rows).to_csv("results/feasibility/probe_fingerprints.tsv", sep="\t", index=False)
tt = np.array(times)
print(f"{len(rows)} pockets; receptor typing median {1000 * np.median(tt[:, 0]):.1f} ms, probe maps median "
      f"{1000 * np.median(tt[:, 1]):.1f} ms (max {1000 * tt[:, 1].max():.1f} ms, {int(tt[:, 2].max())} points), 1 CPU thread")
