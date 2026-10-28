"""Input scaling and the learned projection head (research name "A4b").

Input N1 = [A1(sph8) | env(sph8)] (514 + 113 = 627 d), computed on the sph8 site: the buried grid points
(bur10 >= 0.5) within 8 Å of the bur16^4-weighted centroid of the located point set.  If that set is empty
(a fully solvent-exposed site), the located set itself is described instead (SPH_FALLBACK).

Scaling (fixed, shipped with the method): each part is z-scored with statistics of the BLiPS-train sites (ligand-
shell and detected-pocket rows pooled; label-free); dimensions that are constant in the reference set map to 0.
Head input = the z-scored parts concatenated and clipped to [-CLIP, CLIP].  Each head (one per training seed) maps
it to a vector that is L2-normalised; the fingerprint is the concatenation of the per-seed unit vectors divided by
sqrt(n_seeds), so the inner product of two fingerprints = the mean per-seed cosine (FAISS IndexFlatIP-compatible).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .similarity import ZScorer, l2_normalise

PARTS = {"N1": (("a1", "sph8"), ("env", "sph8"))}
PART_DIMS = {"a1": 514, "env": 113}
CLIP = 5.0


def available(mats) -> np.ndarray:
    """Rows for which every part is (at least partly) finite."""
    ok = np.ones(len(mats[0]), bool)
    for M in mats:
        ok &= np.isfinite(M).any(1)
    return ok


@dataclass
class PartScaler:
    """Per-part z-scoring with fixed reference statistics."""
    inp: str
    scalers: list

    @classmethod
    def fit(cls, inp: str, mats_list) -> "PartScaler":
        """``mats_list`` = list over row-sets (e.g. ligand-shell rows, detected-pocket rows) of lists of part
        matrices; rows are pooled.  Rows with no finite value are ignored."""
        n = len(PARTS[inp])
        sc = []
        for k in range(n):
            M = np.concatenate([m[k] for m in mats_list])
            M = M[np.isfinite(M).any(1)]
            sc.append(ZScorer.fit(M))
        return cls(inp, sc)

    def z(self, mats) -> list[np.ndarray]:
        return [s.transform(M) for s, M in zip(self.scalers, mats)]

    def to_dict(self) -> dict:
        return {"inp": self.inp, "parts": [{"src": s_, "shaper": sh} for s_, sh in PARTS[self.inp]],
                "mean": [s.mean.tolist() for s in self.scalers], "std": [s.std.tolist() for s in self.scalers],
                "n_ref": [s.n_ref for s in self.scalers]}

    @classmethod
    def from_dict(cls, d) -> "PartScaler":
        return cls(d["inp"], [ZScorer(mean=np.asarray(m, np.float64), std=np.asarray(s, np.float64), n_ref=int(n))
                              for m, s, n in zip(d["mean"], d["std"], d["n_ref"])])


def split_parts(N, inp: str = "N1") -> list[np.ndarray]:
    """(n, 627) concatenated raw N1 matrix -> [A1 (n, 514), env (n, 113)]."""
    N = np.atleast_2d(np.asarray(N, np.float64))
    out, s = [], 0
    for src, _ in PARTS[inp]:
        out.append(N[:, s:s + PART_DIMS[src]])
        s += PART_DIMS[src]
    if s != N.shape[1]:
        raise ValueError(f"expected {s} columns, got {N.shape[1]}")
    return out


def head_input(mats, scaler: PartScaler, clip: float = CLIP) -> np.ndarray:
    """Head input: z-scored parts concatenated, clipped to [-clip, clip] (NaN -> 0)."""
    return np.clip(np.concatenate(scaler.z(mats), 1), -clip, clip).astype(np.float32)


def embed_nonlearned(mats, scaler: PartScaler, dtype=np.float32) -> np.ndarray:
    """Non-learned N1 score (the head's parent): equal-weight block cosine (each part z-scored, L2-normalised,
    scaled by sqrt(1 / n_parts)).  Unavailable rows -> 0."""
    Z = scaler.z(mats)
    w = np.sqrt(1.0 / len(Z))
    E = np.concatenate([l2_normalise(z) * w for z in Z], 1)
    E[~available(mats)] = 0.0
    return E.astype(dtype)


def head_forward_np(params: dict, X: np.ndarray) -> np.ndarray:
    """Inference of one head (eval mode) in numpy: [Linear -> LayerNorm -> GELU] (if hidden) -> Linear -> L2.
    The published head is linear (``w2``, ``b2`` only)."""
    from scipy.special import erf
    H = np.asarray(X, np.float32)
    if "w1" in params:
        H = H @ params["w1"].T + params["b1"]
        mu = H.mean(1, keepdims=True)
        var = H.var(1, keepdims=True)
        H = (H - mu) / np.sqrt(var + 1e-5) * params["ln_w"] + params["ln_b"]
        H = 0.5 * H * (1.0 + erf(H / np.sqrt(2.0)))
    H = H @ params["w2"].T + params["b2"]
    n = np.linalg.norm(H, axis=1, keepdims=True)
    return (H / np.where(n > 0, n, 1.0)).astype(np.float32)


def ensemble_embed(heads: list[dict], X: np.ndarray, avail=None) -> np.ndarray:
    """Concatenated per-seed unit vectors scaled by 1/sqrt(n): inner product = mean per-seed cosine."""
    E = np.concatenate([head_forward_np(p, X) for p in heads], 1) / np.sqrt(len(heads))
    if avail is not None:
        E[~np.asarray(avail, bool)] = 0.0
    return E.astype(np.float32)


def load_heads(model_dir) -> tuple[list[dict], dict, PartScaler]:
    """(per-seed numpy params, config, input scaler) of a saved head directory (``seed<k>.npz``,
    ``config.json``, ``input_stats.json``)."""
    model_dir = Path(model_dir)
    cfg = json.loads((model_dir / "config.json").read_text())
    scaler = PartScaler.from_dict(json.loads((model_dir / "input_stats.json").read_text()))
    heads = []
    for s in cfg["seeds"]:
        with np.load(model_dir / f"seed{s}.npz") as z:
            heads.append({k: z[k] for k in z.files})
    return heads, cfg, scaler


__all__ = ["PARTS", "PART_DIMS", "CLIP", "available", "PartScaler", "split_parts", "head_input",
           "embed_nonlearned", "head_forward_np", "ensemble_embed", "load_heads"]
