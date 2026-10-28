"""The pocketcompare method (frozen: ``configs/final_method.yaml``) — public API.

    from pocketcompare import method
    V, info = method.describe_all("1abc.cif.gz")                      # every pocket of a structure: (n, 384)
    W, _ = method.describe_all("AF-P00918-F1-model_v6.cif.gz", af_mode=True)   # AlphaFold model
    v = method.describe("1abc.cif.gz", site="ligand.sdf")             # a ligand-defined site: (1, 384)
    v = method.describe("1abc.cif.gz", site=["A:43", "A:45", "A:46"])  # a residue-defined site
    v = method.describe(path, site=xyz_array)                         # ligand heavy-atom coordinates (n, 3)
    S = method.similarity(v, V)                                       # (1, n) scores; higher = more similar

Pipeline (all parameters in configs/final_method.yaml, with the sha256 of every file it loads):
1. BURROW on the protein (``pockets.featurize_structure``; ``af_mode`` = BURROW AF mode for AlphaFold models).
2. Site location.
   * No site (``describe_all``): BURROW region-rule pockets merged (touch <= 1.5 Å or residue Jaccard >= 0.3),
     merged pockets with < 10 points dropped; the located set = the merged pocket.
   * A ligand (file, or (n, 3) heavy-atom coordinates) -> the 4 Å ligand shell; a residue list ("chain:num") ->
     the residue shell (4 Å, bur10 >= 0.5) ("L mode", ``locate="shell"``).
   * ``locate="burrow"``: the given site only *locates* a BURROW pocket ("D mode", as in the evaluation):
     (a) the region-rule pockets are merged; (b) the merged pocket with the highest coverage of the site points is
     matched (ties -> higher score, better rank); (c) its single member (sub-pocket) with the highest coverage is
     the located set.  ``locate="burrow_flat"``: step (c) over all region-rule pockets, skipping (a)-(b).
3. Description: sph8 = buried points (bur10 >= 0.5) within 8 Å of the bur16^4-weighted centroid of the located set
   (the located set itself if that is empty); N1 = A1 (514 d) + env (113 d) of the sph8 set.
4. Embedding: each part z-scored with the shipped statistics, clipped to +-5, 3 linear heads (627 -> 128),
   each L2-normalised; concatenated / sqrt(3) -> 384-d unit vector.
5. ``similarity(a, b)`` = inner product (= mean per-seed cosine), FAISS IndexFlatIP-compatible.
Invariant to rigid motions of the input, deterministic, independent of point order.
"""
from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import head as H
from . import pockets as pk
from .descriptors import a1 as A1
from .descriptors import env as ENV
from .resources import default_config

MIN_POINTS = 10      # describe_all: merged pockets with fewer points are dropped


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Method:
    """A configured method (see the module docstring).  ``config_path`` defaults to the frozen method; relative
    file paths in the config are resolved against ``<config dir>/<root>`` (``root`` key, default ``..``)."""

    def __init__(self, config_path=None, verify: bool = True):
        import yaml
        self.config_path = Path(config_path) if config_path is not None else default_config()
        cfg = yaml.safe_load(self.config_path.read_text())
        self.cfg = cfg
        self.root = (self.config_path.parent / cfg.get("root", "..")).resolve()
        if verify:
            for rel, sha in cfg["files_sha256"].items():
                got = _sha256(self.root / rel)
                if got != sha:
                    raise RuntimeError(f"{rel}: sha256 {got} != configured {sha}")
        want = cfg.get("burrow", {}).get("model_sha256")
        if verify and want and _sha256(pk.model_path()) != want:
            raise RuntimeError(f"BURROW model {pk.model_path()}: sha256 differs from the configured {want}")
        self.inp = cfg["input"]
        self.parts = [(p["src"], p["shaper"]) for p in cfg["parts"]]
        if tuple(self.parts) != tuple(H.PARTS[self.inp]):
            raise RuntimeError("configured parts differ from pocketcompare.head.PARTS")
        self.scaler = H.PartScaler.from_dict(json.loads((self.root / cfg["input_stats"]).read_text()))
        self.heads = None
        if cfg["kind"] == "learned":
            self.heads = []
            for f in cfg["model_files"]:
                with np.load(self.root / f) as z:
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
        if locate == "burrow":           # == the evaluation's D-mode locator (matched merged pocket -> best member)
            merged = pk.merge_pockets(fs, "region")
            dm = pk.dmode_match(fs, L.idx, merged=merged)
            if dm.pocket is None:
                raise ValueError("BURROW found no region-rule pocket")
            m, cov = pk.best_member(fs, L.idx, dm.pocket.members)
            prec = pk.coverage(fs, dm.pocket.idx, L.idx)
            return [(np.asarray(fs.pocket_idx(m), np.int64), {
                **info, "mode": "D", "locate": "burrow", "burrow_index": int(m), "burrow_rank": int(m) + 1,
                "burrow_score": float(fs.pk_score[m]), "coverage": cov,
                "merged_members": " ".join(str(int(x) + 1) for x in dm.pocket.members),
                "merged_coverage": dm.coverage, "merged_precision": prec,
                "d_match": bool(dm.coverage >= pk.MIN_COVERAGE or prec >= 0.5)})]
        if locate == "burrow_flat":      # best single region pocket, no merge step
            mem = np.flatnonzero(fs.pk_in_region)
            if len(mem) == 0:
                raise ValueError("BURROW found no region-rule pocket")
            m, cov = pk.best_member(fs, L.idx, mem)
            return [(np.asarray(fs.pocket_idx(m), np.int64), {**info, "mode": "D", "locate": "burrow_flat",
                                                              "burrow_index": int(m), "burrow_rank": int(m) + 1,
                                                              "burrow_score": float(fs.pk_score[m]),
                                                              "coverage": cov})]
        if locate != "shell":
            raise ValueError(f"locate must be 'shell', 'burrow' or 'burrow_flat', not {locate!r}")
        return [(np.asarray(L.idx, np.int64), info)]

    # ------------------------------------------------------------------------------------------ description
    def raw_parts(self, fs, base, atom_types=None) -> list[np.ndarray]:
        """Raw (unscaled) N1 part vectors [A1 (514), env (113)] of one located point set."""
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
                out.append(np.full(H.PART_DIMS[src], np.nan))
                continue
            if src == "a1":
                v, _ = A1.a1_descriptor(A1.pocket_input(fs, I, atom_types=atom_types, features=feats), self.a1_cfg)
            else:
                v = ENV.env_descriptor(fs, I)
            out.append(np.asarray(v, np.float64))
        return out

    def embed(self, mats) -> np.ndarray:
        """(n, dim) float32 fingerprints from raw part matrices (list of (n, d_part))."""
        ok = H.available(mats)
        if self.heads is None:
            E = H.embed_nonlearned(mats, self.scaler)
        else:
            E = H.ensemble_embed(self.heads, H.head_input(mats, self.scaler), ok)
        E[~ok] = 0.0
        return E

    def embed_n1(self, N) -> np.ndarray:
        """Fingerprints from a concatenated raw N1 matrix (n, 627) (e.g. the ``n1`` column of ``describe --n1``)."""
        return self.embed(H.split_parts(N, self.inp))

    def _finish(self, rows, infos, t_burrow, return_info, return_n1, attrs=None):
        import pandas as pd
        if rows:
            mats = [np.vstack([r[k] for r in rows]) for k in range(len(self.parts))]
            E = self.embed(mats)
            N = np.concatenate(mats, 1).astype(np.float32)
        else:
            E = np.zeros((0, self.dim), np.float32)
            N = np.zeros((0, sum(H.PART_DIMS[s] for s, _ in self.parts)), np.float32)
        out = [E]
        if return_info:
            info = pd.DataFrame(infos)
            if len(info):
                info["ok"] = np.linalg.norm(E, axis=1) > 0
            info.attrs["burrow_s"] = t_burrow
            info.attrs.update(attrs or {})
            out.append(info)
        if return_n1:
            out.append(N)
        return out[0] if len(out) == 1 else tuple(out)

    def describe(self, structure, site=None, af_mode: bool = False, chains=None, pockets: str = "region",
                 locate: str = "shell", return_info: bool = False, return_n1: bool = False):
        """Fingerprints of the site(s) of one structure (path, loaded ``Structure`` or a ``pockets.Featurized``).
        Returns (n, dim) float32 (n = 1 for a given site; one row per region-rule sub-pocket for ``site=None``),
        with ``return_info`` a pandas DataFrame (site info, n_points, volume_A3, ok, time_ms), and with
        ``return_n1`` the raw (n, 627) N1 descriptors (input of the head; used to retrain it).
        ``locate``: ``"shell"`` (the site itself), ``"burrow"`` (the BURROW pocket at the site, as evaluated) or
        ``"burrow_flat"``.  For all pockets of a structure prefer ``describe_all``."""
        t0 = time.perf_counter()
        fs = self._featurize(structure, af_mode, chains)
        t_burrow = time.perf_counter() - t0
        at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        rows, infos = [], []
        for base, info in self._sites(fs, site, pockets, locate):
            t1 = time.perf_counter()
            rows.append(self.raw_parts(fs, base, at))
            infos.append({**info, "n_points": int(len(base)), "volume_A3": fs.volume(base),
                          "time_ms": 1e3 * (time.perf_counter() - t1)})
        return self._finish(rows, infos, t_burrow, return_info, return_n1)

    def describe_all(self, structure, af_mode: bool = False, chains=None, unit: str = "merged",
                     min_points: int = MIN_POINTS, return_info: bool = True, return_n1: bool = False):
        """Every pocket of a structure, without a site (deployment).

        ``unit="merged"`` (default; the unit of the human AFDB release): BURROW region-rule pockets merged by
        ``pockets.merge_pockets`` (touch <= 1.5 Å or residue Jaccard >= 0.3), merged pockets with fewer than
        ``min_points`` (10) points dropped (this removes the single-point metal candidates); located set = the
        merged pocket, described by sph8 around its bur16^4 centroid.  Rows in merged order (= best member's
        BURROW rank).  ``unit="member"``: every region-rule sub-pocket separately (= ``describe(site=None)``).

        Returns (n, dim) float32 and, with ``return_info`` (default), a DataFrame with one row per pocket:
        merged_index, burrow_index / burrow_rank (best member), members (1-based ranks), burrow_score (max member
        score), n_points, volume_A3 (located set), center_{x,y,z} (sph8 centre), site_n_points, site_volume_A3
        (sph8 set), sph8_fallback, residues (BURROW output residues, author numbering), ok, time_ms; with
        ``return_n1`` also the raw (n, 627) N1 descriptors."""
        t0 = time.perf_counter()
        fs = self._featurize(structure, af_mode, chains)
        t_burrow = time.perf_counter() - t0
        at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        if unit == "merged":
            units = [(k, mp.members, mp.idx, mp.score, mp.residues)
                     for k, mp in enumerate(pk.merge_pockets(fs, "region")) if len(mp.idx) >= min_points]
        elif unit == "member":
            units = [(k, [int(i)], np.asarray(fs.pocket_idx(i), np.int64), float(fs.pk_score[i]),
                      fs.pocket_residue_set(i)) for k, i in enumerate(np.flatnonzero(fs.pk_in_region))]
        else:
            raise ValueError(f"unit must be 'merged' or 'member', not {unit!r}")
        rows, infos = [], []
        for k, members, base, score, res in units:
            t1 = time.perf_counter()
            base = np.asarray(base, np.int64)
            c = pk.buried_centroid(fs, base)
            site = pk.shape_site(fs, base, "sph8")
            rows.append(self.raw_parts(fs, base, at))
            infos.append({"merged_index" if unit == "merged" else "member_index": int(k),
                          "burrow_index": int(members[0]), "burrow_rank": int(members[0]) + 1,
                          "members": " ".join(str(int(m) + 1) for m in members), "burrow_score": float(score),
                          "n_points": int(len(base)), "volume_A3": fs.volume(base),
                          "center_x": float(c[0]), "center_y": float(c[1]), "center_z": float(c[2]),
                          "site_n_points": int(len(site)), "site_volume_A3": fs.volume(site),
                          "sph8_fallback": bool(len(site) == 0),
                          "residues": " ".join(pk.sort_residues(list(res))),
                          "time_ms": 1e3 * (time.perf_counter() - t1)})
        return self._finish(rows, infos, t_burrow, return_info, return_n1, {"unit": unit})

    # ------------------------------------------------------------------------------------------ similarity
    def similarity(self, a, b, background=None) -> np.ndarray | float:
        """Inner-product similarity of fingerprints ``a`` (d,) or (n, d) and ``b`` (d,) or (m, d).  If the
        configured variant is CSLS and ``background`` (k, d) is given, the CSLS-corrected score."""
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
    """The frozen method (cached)."""
    return Method()


def describe(structure, site=None, af_mode: bool = False, **kw):
    """``Method().describe`` with the frozen method (see the module docstring)."""
    return default().describe(structure, site=site, af_mode=af_mode, **kw)


def describe_all(structure, af_mode: bool = False, **kw):
    """``Method().describe_all`` with the frozen method (see ``Method.describe_all``)."""
    return default().describe_all(structure, af_mode=af_mode, **kw)


def similarity(a, b, background=None):
    """``Method().similarity`` with the frozen method."""
    return default().similarity(a, b, background=background)


__all__ = ["Method", "MIN_POINTS", "default", "describe", "describe_all", "similarity"]
