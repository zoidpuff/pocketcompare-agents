"""Shared helpers of the AFDB proteome demo (scripts/proteome/*).

Per structure (``describe_structure``): BURROW region-rule pockets -> merged pockets (``pockets.merge_pockets``,
touch <= 1.5 Å or residue Jaccard >= 0.3) -> keep merged pockets with >= MIN_POINTS points (this also drops the
single-point metal candidates) -> ligand-free site = buried points (bur10 >= 0.5) within 8 Å of the bur16^4-weighted
centroid of the merged pocket (``shape_site(..., 'sph8')``, the "@sph8" definition of
reports/definition_robustness.md) -> A1 default (514 d) + env (113 d) raw descriptors.

The tier-1 embedding (``embed_a1env``) is the 1:1 two-part block cosine used in the D11 exploration: each part is
z-scored with reference statistics, L2-normalised and scaled by sqrt(1/2); the concatenation is a unit vector,
so inner product = mean of the two block cosines.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

from pocketcompare import pockets as pk  # noqa: E402
from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import a1r  # noqa: E402

MIN_POINTS = 10
SHAPER = "sph8"
CFG = A1.make_config()
FEATS = A1.needed_features(CFG)
D_A1 = A1.a1_layout(CFG)[-1].stop
D_ENV = a1r.env_layout()[-1]["stop"]
DESC_NAME = "a1(default)@sph8 + env@sph8 (merged region-rule pocket centre), raw"


def shift_res(r: str, off: int) -> str:
    """'A:123' -> 'A:(123+off)' (AFDB fragments use local numbering 1..1400; offset from DBREF)."""
    if not off:
        return r
    ch, _, num = r.rpartition(":")
    digits = "".join(c for c in num if c.isdigit() or c == "-")
    icode = num[len(digits):]
    return f"{ch}:{int(digits) + off}{icode}"


def describe_structure(fs, plddt: dict | None = None, res_offset: int = 0, min_points: int = MIN_POINTS) -> dict:
    """Merged region pockets with >= ``min_points`` points of a Featurized -> per-pocket records + raw A1/env."""
    t0 = time.perf_counter()
    merged = pk.merge_pockets(fs, "region")
    t1 = time.perf_counter()
    at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
    recs, a1s, envs = [], [], []
    n_small = n_metal_single = n_empty = 0
    for k, mp in enumerate(merged, 1):
        n = len(mp.idx)
        if n < min_points:
            n_small += 1
            n_metal_single += int(n == 1 and bool(fs.is_metal[mp.idx].all()))
            continue
        ts = time.perf_counter()
        c = pk.buried_centroid(fs, mp.idx)
        site = pk.site_sphere(fs, c, 8.0)
        if len(site) == 0:
            n_empty += 1
            continue
        pin = A1.pocket_input(fs, site, atom_types=at, features=FEATS)
        va1, _ = A1.a1_descriptor(pin, CFG)
        venv = a1r.env_descriptor(fs, site)
        td = time.perf_counter() - ts
        res = pk.sort_residues(list(mp.residues))
        pl = [plddt[r] for r in res if plddt is not None and r in plddt]
        recs.append(dict(
            merged_rank=k, burrow_rank=int(mp.members[0]) + 1, members=" ".join(str(m + 1) for m in mp.members),
            score=float(mp.score), n_points=int(n), n_dense=int((fs.vol[mp.idx] == 1).sum()),
            n_metal=int(fs.is_metal[mp.idx].sum()), volume_A3=float(mp.volume_A3),
            site_n_points=int(len(site)), site_volume_A3=float(fs.volume(site)),
            cx=float(c[0]), cy=float(c[1]), cz=float(c[2]),
            n_res=len(res), residues=" ".join(shift_res(r, res_offset) for r in res),
            plddt_mean=float(np.mean(pl)) if pl else float("nan"), plddt_min=float(np.min(pl)) if pl else float("nan"),
            t_desc_ms=1e3 * td))
        a1s.append(va1)
        envs.append(venv)
    t2 = time.perf_counter()
    return dict(records=recs, a1=a1s, env=envs, n_merged=len(merged), n_region=int(fs.pk_in_region.sum()),
                n_full=int(fs.n_pockets), n_small=n_small, n_metal_single=n_metal_single, n_empty_site=n_empty,
                t_merge_s=t1 - t0, t_desc_s=t2 - t1)


# ------------------------------------------------------------------------------------------------ embedding
def zstats(M: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mean/std as pocketcompare.similarity.ZScorer (constant dims -> std 0 -> mapped to 0)."""
    from pocketcompare.similarity import ZScorer
    z = ZScorer.fit(M)
    return z.mean, z.std


def _zpart(M, mean, std):
    M = np.asarray(M, np.float64)
    ok = std > 0
    Z = np.zeros_like(M)
    Z[:, ok] = (M[:, ok] - mean[ok]) / std[ok]
    Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
    n = np.linalg.norm(Z, axis=1, keepdims=True)
    return Z / np.where(n > 0, n, 1.0)


def embed_a1env(a1m, envm, stats: dict) -> np.ndarray:
    """Unit float32 rows [z(a1)/|.| * sqrt(.5), z(env)/|.| * sqrt(.5)] (627 d); stats = {a1_mean, a1_std, env_mean,
    env_std}."""
    A = _zpart(a1m, stats["a1_mean"], stats["a1_std"]) * np.sqrt(0.5)
    E = _zpart(envm, stats["env_mean"], stats["env_std"]) * np.sqrt(0.5)
    return np.ascontiguousarray(np.concatenate([A, E], 1), np.float32)
