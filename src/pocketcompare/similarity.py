"""Tier-1 scoring helpers: z-scoring on a reference set, (block-weighted) cosine, CSLS hub correction, batched
pair scoring (DESIGN §1, §3).

    zs = ZScorer.fit(D, ids, ref_ids)                  # statistics from the caller's train/dev pocket ids only
    E = embed(D, zs)                                   # unit rows: E[i] @ E[j] = cosine of z-scored vectors
    E = embed(D, zs, layout=lay, block_weights={...})  # unit rows: E[i] @ E[j] = sum_b w_b cos_b / sum_b w_b
    s = pair_scores(E, i, j)                           # millions of pairs, chunked, float32
    r = csls_r(E, E[bg], k=10, query_ids=ids, bg_ids=ids[bg])     # mean top-k background similarity
    s_c = csls_pair_scores(E, i, j, r)                 # s - (r_i + r_j) / 2   (DESIGN §1)

Every embedding is a plain unit vector, so all scores are inner products (FAISS IndexFlatIP-compatible).
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
    def fit(cls, D, ids=None, ref_ids=None, clip: float | None = None) -> "ZScorer":
        """Statistics over the rows of ``D`` whose id is in ``ref_ids`` (all rows if ``ref_ids`` is None).
        Non-finite values are ignored in the statistics."""
        D = np.asarray(D, np.float64)
        if ref_ids is not None:
            if ids is None:
                raise ValueError("ids are needed to select ref_ids")
            m = np.isin(np.asarray(ids), np.asarray(ref_ids))
            if not m.any():
                raise ValueError("no reference rows")
            D = D[m]
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


def _blocks(layout):
    """Accept a1.Block objects or dicts {name, start, stop}."""
    out = []
    for b in layout:
        if isinstance(b, dict):
            out.append((b["name"], int(b["start"]), int(b["stop"])))
        else:
            out.append((b.name, int(b.start), int(b.stop)))
    return out


def embed(D, zscorer: ZScorer | None = None, layout=None, block_weights: dict | None = None,
          dtype=np.float32) -> np.ndarray:
    """Unit-norm embedding.  Without ``block_weights``: cosine of the (z-scored) vector.  With them: each block
    is z-scored, L2-normalised separately and scaled by sqrt(w_b / sum w), so that the inner product equals the
    weighted mean of per-block cosines (blocks absent from ``block_weights`` or with weight 0 are dropped)."""
    Z = zscorer.transform(D) if zscorer is not None else np.asarray(D, np.float64)
    if block_weights is None:
        return l2_normalise(Z).astype(dtype)
    if layout is None:
        raise ValueError("block_weights need a layout")
    bl = [(n, s, e) for n, s, e in _blocks(layout) if block_weights.get(n, 0.0) > 0]
    tot = sum(block_weights[n] for n, _, _ in bl)
    parts = [l2_normalise(Z[:, s:e]) * np.sqrt(block_weights[n] / tot) for n, s, e in bl]
    return np.concatenate(parts, 1).astype(dtype)


def pair_scores(E, i, j, batch: int = 1 << 18) -> np.ndarray:
    """Inner products E[i_k] . E[j_k] for index arrays i, j (vectorised in chunks; float32 out)."""
    E = np.ascontiguousarray(E)
    i = np.asarray(i, np.int64)
    j = np.asarray(j, np.int64)
    out = np.empty(len(i), np.float32)
    for s in range(0, len(i), batch):
        a = E[i[s:s + batch]]
        b = E[j[s:s + batch]]
        out[s:s + batch] = np.einsum("nd,nd->n", a, b)
    return out


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


def csls_pair_scores(E, i, j, r, batch: int = 1 << 18) -> np.ndarray:
    """CSLS-style local scaling (DESIGN §1): s(i, j) - (r_i + r_j) / 2."""
    r = np.asarray(r, np.float64)
    s = pair_scores(E, i, j, batch).astype(np.float64)
    return (s - 0.5 * (r[np.asarray(i)] + r[np.asarray(j)])).astype(np.float32)


def scorer_from_reference(D, ids, ref_ids, layout=None, block_weights=None, clip=None, csls_k: int | None = None):
    """Convenience: fit z-scoring on ``ref_ids``, embed all rows, and (optionally) CSLS radii against the
    reference rows as background.  Returns (E, r or None, zscorer)."""
    zs = ZScorer.fit(D, ids, ref_ids, clip=clip)
    E = embed(D, zs, layout, block_weights)
    r = None
    if csls_k:
        bg = np.isin(np.asarray(ids), np.asarray(ref_ids))
        r = csls_r(E, E[bg], csls_k, query_ids=ids, bg_ids=np.asarray(ids)[bg])
    return E, r, zs


__all__ = ["ZScorer", "l2_normalise", "embed", "pair_scores", "csls_r", "csls_pair_scores",
           "scorer_from_reference"]
