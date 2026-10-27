#!/usr/bin/env python
"""Signal check for fragment-docking fingerprints (feasibility study, qualitative, n is tiny).

Input: results/feasibility/scores_<tag>.tsv (+ pockets.tsv). For each tag:
  1. seed reproducibility: per pocket, Pearson r between the 64-fragment score vectors of two seeds
     (raw and after normalisation N below), median/min over pockets and seed pairs.
  2. normalisation N ("dz"): subtract the per-fragment mean over pockets (fragment size/type effect), then z-score
     each pocket's vector (removes pocket-level mean and scale = size/buriedness effect).
  3. pocket-pair similarity = Pearson r of seed-averaged vectors (raw and N); named pairs + retrieval rank of the
     same-site partner among all other pockets.
  4. confounder: Spearman of per-pocket mean raw score vs BURROW volume_A3 / bur16_mean / n_points; share of
     score-matrix variance explained by pocket means and by fragment means (two-way additive model).
Usage: python analyze_signal.py --tags gpu_v2_fast_pp,... > results/feasibility/signal_<...>.txt
"""
import argparse
import itertools

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ap = argparse.ArgumentParser()
ap.add_argument("--tags", required=True)
ap.add_argument("--pockets", default="results/feasibility/pockets.tsv")
a = ap.parse_args()
pk = pd.read_csv(a.pockets, sep="\t").set_index("pocket_id")

NAMED = [  # (label, pocket A, pocket B)
    ("same site, same protein: CDK2 ATP 1hck/1aq1", "1hck_A_p1", "1aq1_A_p1"),
    ("same site, same protein: trypsin S1 3ptb/2ptn(apo)", "3ptb_A_p2", "2ptn_A_p2"),
    ("same site, same protein: trypsin Ca site 3ptb/2ptn", "3ptb_A_p1", "2ptn_A_p1"),
    ("same site type, other protein: ATP CDK2/PKA", "1hck_A_p1", "1atp_E_p1"),
    ("same ligand, other fold: ATP site PKA/HSP90", "1atp_E_p1", "1byq_A_p1"),
    ("same ligand, other fold: heme myoglobin/P450cam", "1a6m_A_p1", "2cpp_A_p2"),
    ("different: kinase ATP vs heme (CDK2/Mb)", "1hck_A_p1", "1a6m_A_p1"),
    ("different: kinase ATP vs S1 (CDK2/trypsin)", "1hck_A_p1", "3ptb_A_p2"),
    ("different: heme vs S1 (Mb/trypsin)", "1a6m_A_p1", "3ptb_A_p2"),
    ("different: ER ligand site vs S1", "3ert_A_p1", "3ptb_A_p2"),
]
PARTNER = {"1hck_A_p1": "1aq1_A_p1", "1aq1_A_p1": "1hck_A_p1", "3ptb_A_p2": "2ptn_A_p2", "2ptn_A_p2": "3ptb_A_p2",
           "3ptb_A_p1": "2ptn_A_p1", "2ptn_A_p1": "3ptb_A_p1"}


def dz(M):
    M = M - M.mean(0, keepdims=True)
    return (M - M.mean(1, keepdims=True)) / (M.std(1, keepdims=True) + 1e-9)


def corr_mat(M):
    return np.corrcoef(M)


def colz_rowz(M):
    M = (M - M.mean(0, keepdims=True)) / (M.std(0, keepdims=True) + 1e-9)
    return (M - M.mean(1, keepdims=True)) / (M.std(1, keepdims=True) + 1e-9)


SIZE_FREE = ("bur", "depth", "escape", "hit_", "f8_", "psp_mean", "nearest_mean", "aniso")
for tag in a.tags.split(","):
    if tag in ("probe", "desc"):  # feature-table baselines: column z-score, then row z-score ("dz")
        f = "probe_fingerprints.tsv" if tag == "probe" else "pockets_burrow_descriptors.tsv"
        ft = pd.read_csv(f"results/feasibility/{f}", sep="\t").set_index("pocket_id")
        if tag == "desc":
            ft = ft[[c for c in ft.columns if c.startswith(SIZE_FREE)]]
        ft = ft.loc[:, ft.std() > 0]
        ids, seeds = list(ft.index), [0]
        Ms = {0: ft.to_numpy(float)}
        print(f"=== {tag}: {len(ids)} pockets x {ft.shape[1]} features (column-z then row-z)")
        C = np.corrcoef(colz_rowz(Ms[0]))
        iu = np.triu_indices(len(ids), 1)
        print(f"--- pocket-pair Pearson r (dz); all {len(iu[0])} pairs: median {np.median(C[iu]):+.3f}, 90th pct {np.percentile(C[iu], 90):+.3f}")
        for lab, p1, p2 in NAMED:
            i, j = ids.index(p1), ids.index(p2)
            print(f"  {lab:55s} r={C[i, j]:+.3f}  (rank of B among {len(ids) - 1} for A: {1 + int((np.delete(C[i], i) > C[i, j]).sum())})")
        ranks = [1 + int((np.delete(C[ids.index(p)], ids.index(p)) > C[ids.index(p), ids.index(q)]).sum()) for p, q in PARTNER.items()]
        print(f"  same-site partner retrieval ranks (dz): {ranks}")
        vol = np.log(pk.loc[ids, "volume_A3"].to_numpy() + 1)
        dv = -np.abs(vol[:, None] - vol[None, :])
        print(f"  Spearman(pair r, -|dlog volume|) over pairs = {spearmanr(C[iu], dv[iu])[0]:+.3f}")
        continue
    sc = pd.read_csv(f"results/feasibility/scores_{tag}.tsv", sep="\t")
    seeds = sorted(int(x) for x in sc.seed.unique())
    mats = {s: sc[sc.seed == s].pivot(index="pocket_id", columns="frag", values="affinity") for s in seeds}
    ids = list(mats[seeds[0]].index)
    Ms = {s: mats[s].loc[ids].to_numpy() for s in seeds}
    print(f"=== {tag}: {len(ids)} pockets x {Ms[seeds[0]].shape[1]} fragments, seeds {seeds}")
    if len(seeds) > 1:
        for name, f in [("raw", lambda M: M), ("dz", dz)]:
            rs = [pearsonr(f(Ms[s1])[i], f(Ms[s2])[i])[0] for s1, s2 in itertools.combinations(seeds, 2)
                  for i in range(len(ids))]
            print(f"seed reproducibility ({name}): per-pocket Pearson r median {np.median(rs):.3f}, "
                  f"min {np.min(rs):.3f}, 10th pct {np.percentile(rs, 10):.3f}")
        d = np.abs(Ms[seeds[0]] - Ms[seeds[1]])
        print(f"|score(seed0)-score(seed1)| kcal/mol: median {np.median(d):.3f}, 95th pct {np.percentile(d, 95):.3f}, max {d.max():.2f}")
    M = np.mean([Ms[s] for s in seeds], 0)
    # confounder
    pm = M.mean(1)
    for col in ["volume_A3", "bur16_mean", "n_points", "depth_mean"]:
        r = spearmanr(pm, pk.loc[ids, col])[0]
        print(f"Spearman(mean fragment score, {col}) = {r:+.3f}")
    gm = M.mean()
    ss = ((M - gm) ** 2).sum()
    rowv = (len(M[0]) * ((M.mean(1) - gm) ** 2).sum()) / ss
    colv = (len(M) * ((M.mean(0) - gm) ** 2).sum()) / ss
    print(f"variance share: pocket means {rowv:.2f}, fragment means {colv:.2f}, residual (pocket x fragment) {1 - rowv - colv:.2f}")
    nh = sc.groupby("frag").n_heavy.first().to_numpy()
    print(f"Spearman(fragment mean score, heavy atoms) = {spearmanr(M.mean(0), nh)[0]:+.3f}")
    for name, f in [("raw", lambda M: M), ("dz", dz)]:
        C = corr_mat(f(M))
        iu = np.triu_indices(len(ids), 1)
        print(f"--- pocket-pair Pearson r ({name}); all {len(iu[0])} pairs: median {np.median(C[iu]):+.3f}, "
              f"90th pct {np.percentile(C[iu], 90):+.3f}")
        for lab, p1, p2 in NAMED:
            i, j = ids.index(p1), ids.index(p2)
            rank = 1 + int((np.delete(C[i], i) > C[i, j]).sum())
            print(f"  {lab:55s} r={C[i, j]:+.3f}  (rank of B among {len(ids) - 1} for A: {rank})")
        ranks = []
        for p, q in PARTNER.items():
            i, j = ids.index(p), ids.index(q)
            ranks.append(1 + int((np.delete(C[i], i) > C[i, j]).sum()))
        print(f"  same-site partner retrieval ranks ({name}): {ranks}  (random expectation ~{(len(ids)) / 2:.0f})")
        # size-matched control: does the dz similarity just track volume similarity?
        vol = np.log(pk.loc[ids, "volume_A3"].to_numpy() + 1)
        dv = -np.abs(vol[:, None] - vol[None, :])
        print(f"  Spearman(pair r, -|dlog volume|) over pairs = {spearmanr(C[iu], dv[iu])[0]:+.3f}")
