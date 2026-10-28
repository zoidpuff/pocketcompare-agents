"""env — protein-environment block of the N1 descriptor (113 d; research name "A1r", version a1r-v1).

The A1 fingerprint describes the *void* (typed volume, pair distances); its L-mode advantage is largely an imprint
of the ligand shape.  The ``env`` block describes the *protein side* of the site from BURROW's analytic per-point
environment features, which are smoothed over 4–12 Å and therefore change little when the exact point set
changes:

* ``env_mean``  (49): vol-weighted means of first-hit chemistry fractions (hit_apolar/polar/charged/aromatic),
  residue-group counts within 4 Å (n4_rg_*), and atom/residue-group composition fractions within 8 and 12 Å
  (f8_*, f12_*: C N O S aromatic hydrophobic-sc donor acceptor backbone sidechain positive negative + 7 residue
  groups; the size/context-like wcn/coord columns are left out).
* ``env_bur``   (49): the same features weighted by vol * bur16^4 (the buried core dominates).
* ``env_hist``  (15): first-hit chemistry x bur16 tertile volume fractions (12) + tertile volume fractions (3),
  the protein-side analogue of A1's type x buriedness histogram (same fixed tertile edges as A1).

All blocks are intensive (size-free), invariant to rigid motions (features are) and to point order.  Only analytic
point features are used (no ``point_score``).
"""
from __future__ import annotations

import numpy as np

A1R_VERSION = "a1r-v1"

HIT = ["hit_apolar", "hit_polar", "hit_charged", "hit_aromatic"]
RG = ["rg_aliphatic", "rg_aromatic", "rg_polar", "rg_positive", "rg_negative", "rg_his_cys", "rg_gly_pro_other"]
COMP = ["C", "N", "O", "S", "aromatic", "hydrophobic_sc_C", "donor", "acceptor", "backbone", "sidechain",
        "positive", "negative"] + RG
ENV_FEATURES = HIT + [f"n4_{r}" for r in RG] + [f"f8_{c}" for c in COMP] + [f"f12_{c}" for c in COMP]
BUR_EDGES = (0.5833, 0.85)          # A1's fixed bur16 tertile edges
ENV_BLOCKS = ("env_mean", "env_bur", "env_hist")


def env_layout() -> list[dict]:
    names = {"env_mean": [f"env_mean:{f}" for f in ENV_FEATURES],
             "env_bur": [f"env_bur:{f}" for f in ENV_FEATURES],
             "env_hist": [f"env_hist:{h}:b{k}" for h in HIT for k in range(3)] + [f"env_hist:mass:b{k}" for k in range(3)]}
    out, s = [], 0
    for b in ENV_BLOCKS:
        out.append({"name": b, "start": s, "stop": s + len(names[b]), "names": names[b]})
        s += len(names[b])
    return out


def env_descriptor(fs, idx, bur_power: float = 4.0) -> np.ndarray:
    """(113,) float32 env vector of point indices ``idx`` of a Featurized-like object (feats, feature_names, vol,
    is_metal).  Metal candidates (vol 0) get weight 1 voxel (as A1's ``metal_weight``)."""
    idx = np.asarray(idx, np.int64)
    fn = list(fs.feature_names)
    F = np.asarray(fs.feats[idx][:, [fn.index(f) for f in ENV_FEATURES]], np.float64)
    b = np.asarray(fs.feats[idx, fn.index("bur16")], np.float64)
    w = np.where(np.asarray(fs.is_metal[idx], bool), 1.0, np.asarray(fs.vol[idx], np.float64))
    W = w.sum()
    if len(idx) == 0 or W <= 0:
        raise ValueError("empty pocket")
    mean = (w[:, None] * F).sum(0) / W
    wb = w * np.clip(b, 0, None) ** bur_power
    bur = (wb[:, None] * F).sum(0) / wb.sum() if wb.sum() > 0 else mean
    t = np.searchsorted(np.asarray(BUR_EDGES), b, side="right")
    T = np.zeros((len(idx), 3))
    T[np.arange(len(idx)), t] = 1.0
    H = F[:, :len(HIT)]
    hist = np.einsum("n,nh,nt->ht", w, H, T).reshape(-1) / W
    mass = (w[:, None] * T).sum(0) / W
    return np.concatenate([mean, bur, hist, mass]).astype(np.float32)


__all__ = ["A1R_VERSION", "ENV_FEATURES", "ENV_BLOCKS", "env_layout", "env_descriptor"]
