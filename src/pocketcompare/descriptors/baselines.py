"""Baselines B0 (size only) and B1 (BURROW size-free pocket descriptor) — DESIGN §3 "Baselines".

B0: ``b0_descriptor`` = [log pocket volume (Å^3)]; similarity = -|log V_a - log V_b| (``b0_pair_scores``).

B1: the 76 BURROW pocket descriptors computed with ``pocketdetect.burrow.model.pocket_features`` on the pocket
point set (L- or D-mode), restricted to the size-free, context-free columns below; scored by cosine on
z-scored vectors (``pocketcompare.similarity``).  Exclusion rule (fixed before any label is seen):

* size by construction (extensive: counts, sums, absolute extents): n_pts, vol, sqrt_vol, sat_vol,
  geo_strength (volume-weighted sum of bur10/16/24), metal_n, pca1, pca2, pca3, extent, n_res
* protein context (whole-protein properties, not the pocket): n_atoms_prot, log_atoms, prot_frac
  (Spearman rho with log protein atoms = -0.92 on 500 TOUGH-M1 L-mode pockets), f8_wcn (rho = +0.85),
  n_chains
* candidate-generation context (constant / meaningless for an externally defined pocket): level, is_sub,
  is_score_src, score_rank, score_rel
* exact duplicates in the default preset (bur24 = longest ray = bur16): bur24_mean, bur24_q90, bur24_q10
* learned (DESIGN §2.8; ablation variant ``learned`` only): score_sum, score_sqrt, score_mean, score_max,
  score_top10, score_top30, score_q50 (score_sum and score_sqrt are also size-mixed and never used)

Intensive descriptors that merely correlate with size (e.g. bur*_mean, rho ~ -0.6 with log volume: bigger
pockets are more open) are kept: they describe the pocket.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

B0_VERSION = "b0-v1"
B1_VERSION = "b1-v1"

B1_EXCLUDE_SIZE = ["n_pts", "vol", "sqrt_vol", "sat_vol", "geo_strength", "metal_n", "pca1", "pca2", "pca3",
                   "extent", "n_res"]
B1_EXCLUDE_CONTEXT = ["n_atoms_prot", "log_atoms", "prot_frac", "f8_wcn", "n_chains"]
B1_EXCLUDE_CANDIDATE = ["level", "is_sub", "is_score_src", "score_rank", "score_rel"]
B1_EXCLUDE_DUPLICATE = ["bur24_mean", "bur24_q90", "bur24_q10"]
B1_LEARNED_ALL = ["score_sum", "score_sqrt", "score_mean", "score_max", "score_top10", "score_top30", "score_q50"]
B1_LEARNED_SIZE_FREE = ["score_mean", "score_max", "score_top10", "score_top30", "score_q50"]

B1_CONFIGS = {
    "default": {"learned": False},     # analytic only (DESIGN §2.8)
    "learned": {"learned": True},      # ablation: + size-free learned point-score summaries
}


def b1_columns(desc_names, learned: bool = False) -> list:
    """Kept B1 columns, in BURROW's descriptor order."""
    excl = set(B1_EXCLUDE_SIZE + B1_EXCLUDE_CONTEXT + B1_EXCLUDE_CANDIDATE + B1_EXCLUDE_DUPLICATE + B1_LEARNED_ALL)
    keep_learned = set(B1_LEARNED_SIZE_FREE) if learned else set()
    return [n for n in desc_names if n not in excl or n in keep_learned]


def burrow_pocket_descriptors(fs, idx, residues=None) -> tuple[np.ndarray, list]:
    """All 76 BURROW descriptors of one point-index set on a Featurized structure (pocket_features verbatim;
    point scores = the cached learned ``point_score``, only consumed by the score_* columns)."""
    from pocketdetect.burrow.model import pocket_features
    idx = np.asarray(idx, np.int64)
    if residues is None:
        residues = fs.residues_near(idx)
    p = SimpleNamespace(idx=idx, residues=list(residues), level=0)
    F, names = pocket_features([p], fs.X, fs.vol, fs.feats, list(fs.feature_names), fs.point_score,
                               len(fs.atom_xyz))
    return F[0].astype(np.float64), names


def b1_descriptor(fs, idx, learned: bool = False, residues=None) -> tuple[np.ndarray, list]:
    F, names = burrow_pocket_descriptors(fs, idx, residues)
    cols = b1_columns(names, learned)
    pos = [names.index(c) for c in cols]
    return F[pos].astype(np.float32), cols


def b0_descriptor(volume_A3: float) -> np.ndarray:
    return np.asarray([np.log(max(float(volume_A3), 1.0))], np.float32)


def b0_pair_scores(logv, i, j) -> np.ndarray:
    """-|log V_i - log V_j| for index arrays i, j into ``logv`` (n,) or (n,1)."""
    v = np.asarray(logv, np.float64).reshape(-1)
    return (-np.abs(v[np.asarray(i)] - v[np.asarray(j)])).astype(np.float32)


__all__ = ["b0_descriptor", "b0_pair_scores", "b1_columns", "b1_descriptor", "burrow_pocket_descriptors",
           "B1_CONFIGS", "B1_EXCLUDE_SIZE", "B1_EXCLUDE_CONTEXT", "B1_EXCLUDE_CANDIDATE", "B1_EXCLUDE_DUPLICATE",
           "B1_LEARNED_ALL", "B1_LEARNED_SIZE_FREE"]
