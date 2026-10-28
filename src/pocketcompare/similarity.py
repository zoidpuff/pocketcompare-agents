"""Scoring helpers: z-scoring on a reference set, L2 normalisation and the CSLS hub correction.

    zs = ZScorer.fit(D)                                # statistics of a reference matrix
    Z = zs.transform(D)                                # constant reference dims -> 0, NaN -> 0
    r = csls_r(E_query, E_db, k=10)                    # mean top-k similarity to a background set
    s_csls = s - (r_a + r_b) / 2                       # CSLS-corrected score (optional; not the default)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EPS_STD = 1e-8


@dataclass
class ZScorer:
    mean: np.ndarray
    std: np.ndarray            # 0 marks a constant dimension in the reference set (mapped to 0)
    n_ref: int
    clip: float | None = None

    @classmethod
    def fit(cls, D, clip: float | None = None) -> "ZScorer":
        """Statistics over the rows of ``D``; non-finite values are ignored."""
        D = np.asarray(D, np.float64)
        mean = np.nanmean(D, 0)
        std = np.nanstd(D, 0)
        std = np.where(std > EPS_STD * np.maximum(1.0, np.abs(mean)), std, 0.0)
        return cls(mean=mean, std=std, n_ref=int(len(D)), clip=clip)

    def transform(self, D) -> np.ndarray:
        D = np.asarray(D, np.float64)
        ok = self.std > 0
        Z = np.zeros_like(D)
        Z[:, ok] = (D[:, ok] - self.mean[ok]) / self.std[ok]
        Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
        if self.clip is not None:
            np.clip(Z, -self.clip, self.clip, out=Z)
        return Z


def l2_normalise(Z) -> np.ndarray:
    Z = np.asarray(Z, np.float64)
    n = np.linalg.norm(Z, axis=1, keepdims=True)
    return np.where(n > 0, Z / np.where(n > 0, n, 1.0), 0.0)


def csls_r(E_query, E_bg, k: int = 10, query_ids=None, bg_ids=None, batch: int = 2048) -> np.ndarray:
    """Mean of the top-``k`` inner products of each query row with the background rows.  If ids are given, a
    query is never its own neighbour (equal ids are masked)."""
    Eq = np.asarray(E_query, np.float32)
    Eb = np.asarray(E_bg, np.float32)
    if k > len(Eb) - (1 if query_ids is not None else 0):
        raise ValueError("k larger than the background")
    qid = None if query_ids is None else np.asarray(query_ids)
    bid = None if bg_ids is None else np.asarray(bg_ids)
    r = np.empty(len(Eq), np.float64)
    for s in range(0, len(Eq), batch):
        S = Eq[s:s + batch] @ Eb.T
        if qid is not None and bid is not None:
            S[qid[s:s + batch, None] == bid[None, :]] = -np.inf
        top = np.partition(S, -k, axis=1)[:, -k:]
        r[s:s + batch] = top.mean(1)
    return r


__all__ = ["ZScorer", "l2_normalise", "csls_r"]
