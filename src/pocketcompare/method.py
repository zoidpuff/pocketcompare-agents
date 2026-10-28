"""The final pocket-similarity method (PREREG §1; selected in reports/a4b_selection.md) — public API.

    from pocketcompare import method
    V, info = method.describe("1abc.cif.gz", return_info=True)        # every BURROW region pocket (D mode): (n, d)
    v = method.describe("1abc.cif.gz", site="ligand.sdf")             # a ligand-defined site (L mode): (1, d)
    v = method.describe("1abc.cif.gz", site=["A:43", "A:45", "A:46"])  # a residue-defined site
    v = method.describe(path, site=xyz_array, af_mode=True)           # ligand heavy-atom coordinates; AF model
    S = method.similarity(v, V)                                       # (1, n) scores; higher = more similar

Pipeline (all parameters in configs/final_method.yaml, with sha256 of every data file it needs):
1. BURROW on the protein (``pocketcompare.pockets.featurize_structure``; ``af_mode`` = BURROW AF mode).
2. Site location: ``site=None`` -> each BURROW pocket of the region-rule output (``pockets="region"``; "v2" or
   "full" also accepted) is a site; a ligand (file, or (n, 3) heavy-atom coordinates) -> the 4 Å ligand shell;
   a residue list ("chain:num") -> the residue shell (4 Å, bur10 >= 0.5).  ``locate="burrow"`` replaces a given
   site by the single region-rule BURROW pocket that best covers it (the evaluation's D-mode locator).
3. Description: ``base`` = the located points, ``sph8`` = buried points (bur10 >= 0.5) within 8 Å of the
   bur16^4-weighted centroid of ``base`` (``base`` itself if that set is empty); parts = A1 default (514) and env (113) blocks of these sets
   (N1: A1(sph8) + env(sph8); N2: + A1(base)).
4. Embedding: each part z-scored with the shipped BLiPS-train statistics; non-learned -> equal-weight block cosine
   (unit vector); A4b -> the seed-ensemble projection head (concatenated unit vectors / sqrt(n_seeds)).
5. ``similarity(a, b)`` = inner product (cosine / mean seed cosine), FAISS IndexFlatIP-compatible.  If the method
   uses CSLS, pass ``background`` (the database vectors): s - (r_a + r_b) / 2, r = mean of the top-10 background
   similarities.
Invariant to rigid motions of the input (BURROW features and canonical frame), deterministic, point-order free.
"""
from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import a4b as A4
from . import pockets as pk
from .descriptors import a1 as A1
from .descriptors import a1r as A1R

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/final_method.yaml"


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Method:
    """A configured final method (see the module docstring)."""

    def __init__(self, config_path=CONFIG, verify: bool = True):
        import yaml
        self.config_path = Path(config_path)
        cfg = yaml.safe_load(self.config_path.read_text())
        self.cfg = cfg
        if verify:
            for rel, sha in cfg["files_sha256"].items():
                got = _sha256(ROOT / rel)
                if got != sha:
                    raise RuntimeError(f"{rel}: sha256 {got} != configured {sha}")
        self.inp = cfg["input"]
        self.parts = [(p["src"], p["shaper"]) for p in cfg["parts"]]
        if tuple(self.parts) != tuple(A4.PARTS[self.inp]):
            raise RuntimeError("configured parts differ from pocketcompare.a4b.PARTS")
        self.scaler = A4.PartScaler.from_dict(json.loads((ROOT / cfg["input_stats"]).read_text()))
        self.heads = None
        if cfg["kind"] == "learned":
            self.heads = []
            for f in cfg["model_files"]:
                with np.load(ROOT / f) as z:
                    self.heads.append({k: z[k] for k in z.files})
        self.a1_cfg = A1.make_config(cfg["a1"]["overrides"])
        if A1.config_hash(self.a1_cfg) != cfg["a1"]["config_hash"]:
            raise RuntimeError("A1 config hash mismatch")
        self.csls = cfg["variant"] == "csls"
        self.csls_k = int(cfg.get("csls_k", 10))
        self.dim = int(cfg["dims"])

    # ------------------------------------------------------------------------------------------ sites
    @staticmethod
    def _featurize(structure, af_mode, chains):
        if isinstance(structure, pk.Featurized):
            return structure
        return pk.featurize_structure(structure, chains=chains, af_mode=af_mode)

    def _sites(self, fs, site, pockets, locate):
        """[(base point indices, info dict)] for the requested site(s)."""
        if site is None:
            sel = {"region": fs.pk_in_region, "v2": fs.pk_in_v2, "full": np.ones(fs.n_pockets, bool)}[pockets]
            return [(np.asarray(fs.pocket_idx(i), np.int64), {"burrow_index": int(i), "burrow_rank": int(i) + 1,
                                                             "burrow_score": float(fs.pk_score[i]), "mode": "D"})
                    for i in np.flatnonzero(sel)]
        if isinstance(site, (str, Path)):
            xyz, _ = pk.read_ligand_heavy_atoms(site)
            L = pk.lmode_from_ligand(fs, xyz)
        elif isinstance(site, (list, tuple)) and len(site) and isinstance(site[0], str):
            L = pk.lmode_from_residues(fs, list(site))
        else:
            L = pk.lmode_from_ligand(fs, np.asarray(site, np.float64).reshape(-1, 3))
        info = {"mode": "L", "definition": L.definition, "n_site_points": int(L.n_points)}
        if len(L.idx) == 0:
            raise ValueError("the site contains no BURROW points")
        if locate == "burrow":
            mem = np.flatnonzero(fs.pk_in_region)
            if len(mem) == 0:
                raise ValueError("BURROW found no region-rule pocket")
            m, cov = pk.best_member(fs, L.idx, mem)
            return [(np.asarray(fs.pocket_idx(m), np.int64), {**info, "mode": "D", "burrow_index": int(m),
                                                              "burrow_rank": int(m) + 1, "coverage": cov})]
        if locate != "shell":
            raise ValueError(locate)
        return [(np.asarray(L.idx, np.int64), info)]

    # ------------------------------------------------------------------------------------------ description
    def raw_parts(self, fs, base, atom_types=None) -> list[np.ndarray]:
        """Raw (unscaled) part vectors of one located point set (NaN if a shaped set is empty)."""
        if atom_types is None:
            atom_types = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        sets = {sh: pk.shape_site(fs, base, sh) for sh in dict.fromkeys(sh for _, sh in self.parts)}
        for sh in sets:                       # empty shaped set (fully exposed site) -> the located set
            if len(sets[sh]) == 0:
                sets[sh] = np.asarray(base, np.int64)
        out = []
        feats = A1.needed_features(self.a1_cfg)
        for src, sh in self.parts:
            I = sets[sh]
            if len(I) == 0:
                out.append(np.full(514 if src == "a1" else 113, np.nan))
                continue
            if src == "a1":
                v, _ = A1.a1_descriptor(A1.pocket_input(fs, I, atom_types=atom_types, features=feats), self.a1_cfg)
            else:
                v = A1R.env_descriptor(fs, I)
            out.append(np.asarray(v, np.float64))
        return out

    def embed(self, mats) -> np.ndarray:
        """(n, dim) float32 vectors from raw part matrices (list of (n, d_part))."""
        ok = A4.available(mats)
        if self.heads is None:
            E = A4.embed_nonlearned(mats, self.scaler)
        else:
            E = A4.ensemble_embed(self.heads, A4.head_input(mats, self.scaler), ok)
        E[~ok] = 0.0
        return E

    def describe(self, structure, site=None, af_mode: bool = False, chains=None, pockets: str = "region",
                 locate: str = "shell", return_info: bool = False):
        """Vectors of the site(s) of one structure (path, loaded ``Structure`` or a ``pockets.Featurized``).
        Returns (n, dim) float32 (n = 1 for a given site; one row per BURROW pocket for ``site=None``), and
        with ``return_info`` a pandas DataFrame (site info, n_points, ok, time_ms)."""
        import pandas as pd
        t0 = time.perf_counter()
        fs = self._featurize(structure, af_mode, chains)
        t_burrow = time.perf_counter() - t0
        at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        rows, infos = [], []
        for base, info in self._sites(fs, site, pockets, locate):
            t1 = time.perf_counter()
            rows.append(self.raw_parts(fs, base, at))
            info = {**info, "n_points": int(len(base)), "volume_A3": fs.volume(base),
                    "time_ms": 1e3 * (time.perf_counter() - t1)}
            infos.append(info)
        if not rows:
            E = np.zeros((0, self.dim), np.float32)
        else:
            mats = [np.vstack([r[k] for r in rows]) for k in range(len(self.parts))]
            E = self.embed(mats)
        if not return_info:
            return E
        info = pd.DataFrame(infos)
        if len(info):
            info["ok"] = np.linalg.norm(E, axis=1) > 0
        info.attrs["burrow_s"] = t_burrow
        return E, info

    # ------------------------------------------------------------------------------------------ similarity
    def similarity(self, a, b, background=None) -> np.ndarray | float:
        """Inner-product similarity of vectors ``a`` (d,) or (n, d) and ``b`` (d,) or (m, d).  With CSLS
        (configured) and ``background`` (k, d), the CSLS-corrected score; without ``background`` the raw
        score is returned."""
        A = np.atleast_2d(np.asarray(a, np.float32))
        B = np.atleast_2d(np.asarray(b, np.float32))
        S = A @ B.T
        if self.csls and background is not None:
            from .similarity import csls_r
            bg = np.asarray(background, np.float32)
            S = S - 0.5 * (csls_r(A, bg, self.csls_k)[:, None] + csls_r(B, bg, self.csls_k)[None, :])
        if np.ndim(a) == 1 and np.ndim(b) == 1:
            return float(S[0, 0])
        return S


@lru_cache(maxsize=1)
def default() -> Method:
    return Method()


def describe(structure, site=None, af_mode: bool = False, **kw):
    """``Method().describe`` with configs/final_method.yaml (see the module docstring)."""
    return default().describe(structure, site=site, af_mode=af_mode, **kw)


def similarity(a, b, background=None):
    """``Method().similarity`` with configs/final_method.yaml."""
    return default().similarity(a, b, background=background)


__all__ = ["Method", "CONFIG", "default", "describe", "similarity"]
