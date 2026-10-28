"""Final-method candidates (PREREG §1): non-learned N1 / N2 and the A4b learned projection head.

Inputs (label-free; ``scripts/compute_descriptors.py --arm a1r``, TOUGH-M1: ``scripts/explore/defrob_compute.py``):

* N1 = [A1(sph8) | env(sph8)]                 (514 + 113 = 627 d; the ligand-free robust descriptor)
* N2 = [A1(base) | A1(sph8) | env(sph8)]      (514 + 514 + 113 = 1,141 d; hybrid)

``base`` = the located point set (L: 4 Å ligand shell; D: the single BURROW sub-pocket ``U`` that best covers the
site, or the merged region pocket for PPIPS); ``sph8`` = buried points within 8 Å of its bur16^4-weighted centroid.
SPH_FALLBACK (fixed 2026-10-28 before any score of it was seen; one fully solvent-exposed BLiPS-val site): if the
sph8 set is empty, the sph8 parts are computed on ``base``.

Scaling (fixed, shipped with the method): each part is z-scored with statistics of the BLiPS-train v2 sites (L rows
and D (= U) rows pooled; label-free).  Non-learned score = equal-weight block cosine (each part z-scored, L2-normalised,
scaled by sqrt(1 / n_parts), concatenated -> inner product = mean of the part cosines).  A4b input = the z-scored
parts concatenated and clipped to [-CLIP, CLIP]; the head maps it to a unit vector; the method's score is the mean
over the seed ensemble of the per-seed cosines = inner product of the concatenated per-seed unit vectors / n_seeds.
Every score is an inner product of unit-norm (or 1/sqrt(n)-scaled) vectors, i.e. FAISS IndexFlatIP-compatible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .similarity import ZScorer, l2_normalise

ROOT = Path(__file__).resolve().parents[2]
DESC = ROOT / "data/processed/descriptors"
PARTS = {"N1": (("a1", "sph8"), ("env", "sph8")),
         "N2": (("a1", "base"), ("a1", "sph8"), ("env", "sph8"))}
CLIP = 5.0


# ============================================================================================ descriptor access
def a1r_dir(dataset: str) -> Path:
    return DESC / "tough_m1/defrob" if dataset == "tough_m1" else DESC / dataset / "a1r"


def locator(dataset: str, mode: str) -> str:
    """Point-set locator of a mode: L -> ligand shell 'L'; D -> best sub-pocket 'U' (PPIPS: merged pocket 'D')."""
    if mode == "L":
        if dataset == "ppips":
            raise ValueError("PPIPS has no L mode")
        return "L"
    return "D" if dataset == "ppips" else "U"


_NPZ: dict = {}


def _npz(dataset, loc, shaper):
    k = (dataset, loc, shaper)
    if k not in _NPZ:
        with np.load(a1r_dir(dataset) / f"{loc}_{shaper}.npz") as z:
            _NPZ[k] = {n: z[n] for n in ("a1", "env", "vol_A3", "n_points", "t_shape", "t_a1", "t_env")}
    return _NPZ[k]


def ids_table(dataset: str) -> pd.DataFrame:
    return pd.read_parquet(a1r_dir(dataset) / "ids.parquet")


def raw_parts(dataset: str, mode: str, pocket_ids, inp: str) -> list[np.ndarray]:
    """Raw part matrices (rows in ``pocket_ids`` order; NaN rows = not available) of input ``inp`` (N1|N2)."""
    ids = ids_table(dataset)
    row = pd.Series(np.arange(len(ids)), index=ids.pocket_id).loc[list(pocket_ids)].to_numpy()
    loc = locator(dataset, mode)
    out = []
    for src, sh in PARTS[inp]:
        M = np.asarray(_npz(dataset, loc, sh)[src][row], np.float64)
        if sh != "base":       # SPH_FALLBACK: empty shaped set -> the located (base) set
            B = np.asarray(_npz(dataset, loc, "base")[src][row], np.float64)
            fb = ~np.isfinite(M).any(1) & np.isfinite(B).any(1)
            M[fb] = B[fb]
        out.append(M)
    return out


def n_fallback(dataset: str, mode: str, pocket_ids) -> int:
    """Number of pockets whose sph8 set is empty (described by the base set instead)."""
    ids = ids_table(dataset)
    row = pd.Series(np.arange(len(ids)), index=ids.pocket_id).loc[list(pocket_ids)].to_numpy()
    loc = locator(dataset, mode)
    M, B = _npz(dataset, loc, "sph8")["a1"][row], _npz(dataset, loc, "base")["a1"][row]
    return int((~np.isfinite(M).any(1) & np.isfinite(B).any(1)).sum())


def part_times(dataset: str, mode: str, pocket_ids, inp: str) -> np.ndarray:
    """Per-pocket descriptor time (ms, one thread; shaper + each distinct (src, shaper) descriptor; excl. I/O and
    per-structure atom typing)."""
    ids = ids_table(dataset)
    row = pd.Series(np.arange(len(ids)), index=ids.pocket_id).loc[list(pocket_ids)].to_numpy()
    loc = locator(dataset, mode)
    tot = np.zeros(len(row))
    for sh in dict.fromkeys(sh for _, sh in PARTS[inp]):
        tot += np.nan_to_num(_npz(dataset, loc, sh)["t_shape"][row])
    for src, sh in PARTS[inp]:
        tot += np.nan_to_num(_npz(dataset, loc, sh)[f"t_{src}"][row])
    return tot


def available(mats) -> np.ndarray:
    ok = np.ones(len(mats[0]), bool)
    for M in mats:
        ok &= np.isfinite(M).any(1)
    return ok


# ============================================================================================ scaling / embeddings
@dataclass
class PartScaler:
    """Per-part z-scoring with fixed reference statistics."""
    inp: str
    scalers: list

    @classmethod
    def fit(cls, inp: str, mats_list) -> "PartScaler":
        """``mats_list`` = list over row-sets (e.g. L rows, D rows) of lists of part matrices; rows are pooled."""
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


SITES_V2 = ROOT / "data/splits/blips_sites_v2.parquet"


def blips_train_ids() -> list[str]:
    s = pd.read_parquet(SITES_V2, columns=["site_id", "partition"])
    return sorted(s.site_id[s.partition == "train"])


def blips_train_scaler(inp: str) -> PartScaler:
    """Input statistics of the method: BLiPS-train v2 sites, L rows and D (= U) rows pooled (label-free)."""
    ids = blips_train_ids()
    return PartScaler.fit(inp, [raw_parts("blips", m, ids, inp) for m in ("L", "D")])


def embed_nonlearned(mats, scaler: PartScaler, dtype=np.float32) -> np.ndarray:
    """Equal-weight block cosine embedding (inner product = mean of the part cosines).  Unavailable rows -> 0."""
    Z = scaler.z(mats)
    w = np.sqrt(1.0 / len(Z))
    E = np.concatenate([l2_normalise(z) * w for z in Z], 1)
    E[~available(mats)] = 0.0
    return E.astype(dtype)


def head_input(mats, scaler: PartScaler, clip: float = CLIP) -> np.ndarray:
    """A4b input: z-scored parts concatenated, clipped to [-clip, clip] (NaN -> 0)."""
    return np.clip(np.concatenate(scaler.z(mats), 1), -clip, clip).astype(np.float32)


# ============================================================================================ A4b head (numpy)
def head_forward_np(params: dict, X: np.ndarray) -> np.ndarray:
    """Inference of one A4b head (eval mode) in numpy: [Linear -> LayerNorm -> GELU] (if hidden) -> Linear -> L2."""
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
    """(per-seed numpy params, config, input scaler) of a saved A4b model directory."""
    model_dir = Path(model_dir)
    cfg = json.loads((model_dir / "config.json").read_text())
    scaler = PartScaler.from_dict(json.loads((model_dir / "input_stats.json").read_text()))
    heads = []
    for s in cfg["seeds"]:
        with np.load(model_dir / f"seed{s}.npz") as z:
            heads.append({k: z[k] for k in z.files})
    return heads, cfg, scaler


__all__ = ["PARTS", "CLIP", "SITES_V2", "blips_train_ids", "blips_train_scaler", "a1r_dir", "locator",
           "ids_table", "raw_parts", "n_fallback", "part_times", "available",
           "PartScaler", "embed_nonlearned", "head_input", "head_forward_np", "ensemble_embed", "load_heads"]
