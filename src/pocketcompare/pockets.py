"""Pocket adapter: BURROW points, point features and pocket definitions for one structure.

    fs = featurize_structure(path)                       # all BURROW grid points + features + pockets
    lp = lmode_from_ligand(fs, ligand_heavy_xyz)         # site = grid points <= 4 Å of a ligand ("L mode")
    lp = lmode_from_residues(fs, ["A:43", ...])          # site from a residue list (+ bur10 >= 0.5)
    merged = merge_pockets(fs)                           # BURROW region-rule pockets, touching ones merged
    dm = dmode_match(fs, lp.idx, merged=merged)          # merged pocket that best covers a site ("D mode")
    idx = shape_site(fs, base_idx, "sph8")               # the described set: buried points <= 8 Å of the centre

Points.  ``featurize_structure`` runs the BURROW reference pipeline (``pocketdetect.burrow``) once on the
protein-only view of the structure (ligands, waters, ions, nucleic acids and hydrogens are stripped) and keeps
EVERY featurised point, not only pocket points: the dense LIGSITE survivors (``vol`` = 1 grid voxel), the coarse
sub-lattice points that stand for the exposed shell (``vol`` = subsample^3 = 27 voxels in BURROW's ``default``
preset) and the metal candidates (``vol`` = 0).  Volumes are therefore ``sum(vol[idx]) * spacing**3`` Å^3.

Pockets.  One BURROW run yields its full output list (``min_score=None``, <= 50 pockets after NMS); BURROW's
``--output-rule region`` list and its default (v2) list are post-filters of it (flags ``pk_in_region``,
``pk_in_v2``).  pocketcompare describes region-rule pockets.

Only BURROW's analytic point features are used by the fingerprint; ``point_score`` (BURROW's learned point score)
is kept for reference only.  The BURROW model used is the one pinned in ``configs/final_method.yaml``
(``models/burrow/burrow_all_default_s0.json``, BURROW 1.0.0, MIT).
"""
from __future__ import annotations

import functools
import hashlib
import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ADAPTER_VERSION = "pockets-v1"
REGION_RULE = "c16_0.005"          # == pocketdetect.burrow.cli.REGION_RULE (checked at featurisation)
WATER = 2                          # pocketdetect.structure kind codes: 0 protein, 1 ligand, 2 water, 3 other polymer

L_CUTOFF = 4.0                     # ligand site: point <= 4 Å of a ligand heavy atom
LINING_CUTOFF = 4.0                # lining residue: heavy atom <= 4 Å of a site point
RES_CUTOFF = 4.0                   # residue-list site: point <= 4 Å of a listed residue's heavy atom
RES_BUR_MIN = 0.5                  # ... and bur10 >= 0.5
MERGE_TOUCH = 1.5                  # merge detected pockets with any point pair <= 1.5 Å
MERGE_JACCARD = 0.3                # ... or residue Jaccard >= 0.3
COVER_DIST = 1.5                   # a site point is covered if <= 1.5 Å of a detected pocket point
MIN_COVERAGE = 0.3                 # below -> "missed"


# --------------------------------------------------------------------------- BURROW model
@functools.lru_cache(maxsize=None)
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


@functools.lru_cache(maxsize=None)
def _load_model(path: str):
    from pocketdetect.burrow.model import BurrowModel
    return BurrowModel.load(path)


def model_path() -> Path:
    """The pinned BURROW model (``default`` preset, ``all`` ranker, seed 0) shipped with pocketcompare."""
    from .resources import data_root
    return data_root() / "models/burrow/burrow_all_default_s0.json"


def burrow_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("burrow-pockets")
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- featurised structure
_STR = lambda a, w: np.asarray(a).astype(f"U{w}")  # noqa: E731


@dataclass
class Featurized:
    """All BURROW points of one structure, their features, the protein atom table and BURROW's pockets."""
    key: str
    points: np.ndarray        # (P,3) float32, input frame
    X: np.ndarray             # (P,3) float32, BURROW canonical (PCA) frame
    vol: np.ndarray           # (P,) float32 grid-voxel weight (1 dense, 27 coarse sub-lattice, 0 metal cand.)
    is_metal: np.ndarray      # (P,) bool
    point_score: np.ndarray   # (P,) float32 learned BURROW point score (not used by the fingerprint)
    feats: np.ndarray         # (P,F) float32 analytic point features
    feature_names: list
    atom_xyz: np.ndarray      # (N,3) float32 protein heavy atoms (input frame)
    atom_res: np.ndarray      # (N,) int32 -> res_ids
    atom_name: np.ndarray     # (N,) str
    atom_element: np.ndarray  # (N,) str
    res_ids: np.ndarray       # (R,) str "chain:num[icode]" (author numbering of the input file)
    res_names: np.ndarray     # (R,) str
    het_xyz: np.ndarray       # (H,3) float32 non-protein, non-water heavy atoms (stripped before featurising)
    het_element: np.ndarray   # (H,) str
    het_resname: np.ndarray   # (H,) str
    het_res: np.ndarray       # (H,) str "chain:num[icode]"
    pk_score: np.ndarray      # (K,) BURROW full list (rank order = index order, rank = index + 1)
    pk_center: np.ndarray     # (K,3)
    pk_residues: np.ndarray   # (K,) str, space-separated residue ids (BURROW output residues)
    pk_indptr: np.ndarray     # (K+1,) CSR into points
    pk_indices: np.ndarray
    pk_desc: np.ndarray       # (K,76) BURROW pocket descriptors
    desc_names: list
    pk_in_v2: np.ndarray      # (K,) bool: in BURROW's default (v2 floor) output
    pk_in_region: np.ndarray  # (K,) bool: in BURROW's --output-rule region output
    meta: dict = field(default_factory=dict)
    _ptree: object = field(default=None, repr=False, compare=False)
    _atree: object = field(default=None, repr=False, compare=False)

    @property
    def spacing(self) -> float:
        return float(self.meta["feature_cfg"]["spacing"])

    @property
    def n_pockets(self) -> int:
        return len(self.pk_score)

    def feature(self, name: str) -> np.ndarray:
        return self.feats[:, self.feature_names.index(name)]

    def pocket_idx(self, i: int) -> np.ndarray:
        """Point indices of full-list pocket ``i`` (0-based; BURROW rank = i + 1)."""
        return self.pk_indices[self.pk_indptr[i]:self.pk_indptr[i + 1]]

    def pocket_residue_set(self, i: int) -> frozenset:
        s = str(self.pk_residues[i])
        return frozenset(s.split()) if s else frozenset()

    def volume(self, idx) -> float:
        """Å^3 of a point-index set (respects the coarse sub-lattice weights)."""
        return float(self.vol[np.asarray(idx, np.int64)].sum(dtype=np.float64) * self.spacing ** 3)

    def point_tree(self) -> cKDTree:
        if self._ptree is None:
            self._ptree = cKDTree(self.points)
        return self._ptree

    def atom_tree(self) -> cKDTree:
        if self._atree is None:
            self._atree = cKDTree(self.atom_xyz)
        return self._atree

    def residues_near(self, idx, cutoff: float = LINING_CUTOFF) -> list:
        """Residues with a heavy atom <= cutoff of any of the points ``idx`` (sorted by chain, number)."""
        idx = np.asarray(idx, np.int64)
        if len(idx) == 0:
            return []
        hits = self.atom_tree().query_ball_point(self.points[idx], cutoff)
        at = np.unique(np.fromiter((a for l in hits for a in l), np.int64))
        return sort_residues(self.res_ids[np.unique(self.atom_res[at])].tolist()) if len(at) else []

    # ---- cache I/O
    _ARRAYS = ("points", "X", "vol", "is_metal", "point_score", "feats", "atom_xyz", "atom_res", "atom_name",
               "atom_element", "res_ids", "res_names", "het_xyz", "het_element", "het_resname", "het_res",
               "pk_score", "pk_center", "pk_residues", "pk_indptr", "pk_indices", "pk_desc", "pk_in_v2",
               "pk_in_region")

    def save(self, path) -> int:
        """Write a compressed npz atomically (tmp + rename).  Returns bytes written."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        arrs = {k: getattr(self, k) for k in self._ARRAYS}
        arrs["feature_names"] = np.asarray(self.feature_names, dtype="U32")
        arrs["desc_names"] = np.asarray(self.desc_names, dtype="U32")
        arrs["meta"] = np.asarray(json.dumps({"key": self.key, **self.meta}, sort_keys=True))
        buf = io.BytesIO()
        np.savez_compressed(buf, **arrs)
        data = buf.getvalue()
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return len(data)

    @classmethod
    def load(cls, path) -> "Featurized":
        with np.load(path, allow_pickle=False) as z:
            meta = json.loads(str(z["meta"]))
            kw = {k: z[k] for k in cls._ARRAYS}
            kw["feature_names"] = z["feature_names"].tolist()
            kw["desc_names"] = z["desc_names"].tolist()
        key = meta.pop("key")
        return cls(key=key, meta=meta, **kw)


def sort_residues(res) -> list:
    def k(r):
        ch, _, num = r.rpartition(":")
        digits = "".join(c for c in num if c.isdigit() or c == "-")
        try:
            n = int(digits)
        except ValueError:
            n = 0
        return (ch, n, num)
    return sorted(res, key=k)


def featurize_structure(path, chains=None, af_mode: bool = False, key: str | None = None) -> Featurized:
    """Run BURROW (reference implementation, pinned model) once on the protein of ``path`` and keep everything.

    path     : PDB/mmCIF file (``.gz`` allowed) or a loaded ``pocketdetect.structure.Structure``.
    chains   : iterable of author chain ids to keep (None = all protein chains of the first model).
    af_mode  : BURROW AF mode (pLDDT pruning + soft occlusion; needs pLDDT in the B-factor column).
    """
    from pocketdetect.burrow.cli import REGION_RULE as _RR
    from pocketdetect.burrow.export import _feature_cfg
    from pocketdetect.burrow.features import point_features
    from pocketdetect.burrow.model import (FormationConfig, candidates, pocket_features, rank_predict,
                                           score_points)
    from pocketdetect.burrow.output_rules import apply_rule
    from pocketdetect.burrow.pipeline import finalize, output_residues
    from pocketdetect.burrow.pockets import assign_residues
    from pocketdetect.burrow.prep import protein_from_structure
    from pocketdetect.structure import Structure, load_structure

    assert _RR == REGION_RULE, f"BURROW region rule changed: {_RR}"
    t0 = time.perf_counter()
    mp = model_path()
    m = _load_model(str(mp))
    fc_dict = dict(m.formation)
    fc_dict["min_score"] = None                       # full list; v2 / region are post-filters
    fc = FormationConfig(**fc_dict)
    cfg = _feature_cfg(m)

    if isinstance(path, Structure):          # pre-loaded structure (e.g. transformed in memory)
        s = path if chains is None else path.select_chains(chains)
        sid, sha = key or s.id, None
    else:
        path = Path(path)
        sid, sha = key or path.name.split(".")[0], _sha256(str(path))
        s = load_structure(str(path), structure_id=sid, chains=list(chains) if chains is not None else None)
    # stripped non-protein heavy atoms (ligands, ions, cofactors); kept only to resolve ligand-defined sites
    nonprot = (s.kind != 0) & (s.kind != WATER) & ~s.is_hydrogen
    het_xyz = np.asarray(s.coords[nonprot], np.float32).reshape(-1, 3)
    rid = s.atom_residue_ids
    het = dict(het_xyz=het_xyz, het_element=_STR(np.char.upper(s.element[nonprot].astype(str)), 3),
               het_resname=_STR(s.res_name[nonprot], 5), het_res=_STR(rid[nonprot], 16))
    weights = None
    if af_mode:
        from pocketdetect.burrow.af import af_protein
        P, weights, _ = af_protein(s)
    else:
        P = protein_from_structure(s)
    if len(P.coords) == 0:
        raise ValueError("no protein heavy atoms")
    t1 = time.perf_counter()

    ps = point_features(P, cfg, weights)
    t2 = time.perf_counter()
    pb, _ = m.boosters()
    score = score_points(pb, ps.feats, ps.names, m.point_features, m.meta.get("score_floor"))
    pk = candidates(ps.X, ps.points, ps.vol, ps.feats, ps.names, score, fc)
    tree = cKDTree(P.coords)
    assign_residues(pk, ps.points, tree, P.res_index, P.residue_ids)
    Fp, fn = pocket_features(pk, ps.X, ps.vol, ps.feats, ps.names, score, len(P.coords))
    rs = rank_predict(m, Fp[:, [fn.index(n) for n in m.rank_features]]) if len(pk) else np.zeros(0)
    keep = finalize(pk, rs, fc)
    ks = np.asarray(rs, float)[keep] if len(keep) else np.zeros(0)
    kc = np.array([pk[i].center for i in keep], float).reshape(-1, 3)
    in_v2 = np.zeros(len(keep), bool)
    in_v2[apply_rule("v2", ks, kc)] = True
    in_reg = np.zeros(len(keep), bool)
    in_reg[apply_rule(REGION_RULE, ks, kc)] = True
    members = [np.asarray(pk[i].idx, np.int64) for i in keep]
    indptr = np.zeros(len(keep) + 1, np.int64)
    indptr[1:] = np.cumsum([len(x) for x in members])
    t3 = time.perf_counter()

    meta = {
        "adapter_version": ADAPTER_VERSION, "structure_path": None if sha is None else str(path),
        "structure_sha256": sha, "chains": None if chains is None else list(chains), "af_mode": bool(af_mode),
        "model_path": str(mp), "model_sha256": _sha256(str(mp)), "burrow_version": burrow_version(),
        "feature_cfg": json.loads(json.dumps(m.meta["feature_cfg"])), "formation": fc_dict,
        "region_rule": REGION_RULE, "n_candidates": len(pk), "n_atoms": int(len(P.coords)),
        "n_points": int(len(ps.points)),
    }
    timings = {"load_s": t1 - t0, "points_s": t2 - t1, "pockets_s": t3 - t2}
    fs = Featurized(
        key=sid, points=np.ascontiguousarray(ps.points, np.float32), X=np.ascontiguousarray(ps.X, np.float32),
        vol=ps.vol.astype(np.float32), is_metal=ps.is_metal.astype(bool), point_score=score.astype(np.float32),
        feats=np.ascontiguousarray(ps.feats, np.float32), feature_names=list(ps.names),
        atom_xyz=np.ascontiguousarray(P.coords, np.float32), atom_res=P.res_index.astype(np.int32),
        atom_name=_STR(P.atom_name, 4), atom_element=_STR(P.element, 3),
        res_ids=_STR(P.residue_ids, 16), res_names=_res_names(P), **het,
        pk_score=ks.astype(np.float64), pk_center=kc.astype(np.float64),
        pk_residues=np.asarray([" ".join(sort_residues(output_residues(pk[i], tree, P))) for i in keep]
                               or np.zeros(0, "U1"), dtype=str),
        pk_indptr=indptr, pk_indices=np.concatenate(members) if members else np.zeros(0, np.int64),
        pk_desc=(Fp[keep] if len(keep) else np.zeros((0, len(fn)))).astype(np.float64), desc_names=list(fn),
        pk_in_v2=in_v2, pk_in_region=in_reg, meta=meta)
    fs.meta["timings"] = timings
    return fs


def _res_names(P) -> np.ndarray:
    out = np.empty(len(P.residue_ids), dtype="U5")
    out[P.res_index] = P.res_name
    return out


# --------------------------------------------------------------------------- sites given by a ligand / residues
@dataclass
class LPocket:
    idx: np.ndarray           # point indices into Featurized.points (sorted)
    residues: list            # lining residues (<= lining cutoff of the points)
    volume_A3: float
    definition: str           # "ligand" | "residues"
    info: dict = field(default_factory=dict)

    @property
    def n_points(self) -> int:
        return len(self.idx)


def lmode_from_ligand(fs: Featurized, ligand_xyz, cutoff: float = L_CUTOFF,
                      lining_cutoff: float = LINING_CUTOFF) -> LPocket:
    """Points within ``cutoff`` Å of any ligand heavy atom (caller passes heavy atoms only)."""
    L = np.asarray(ligand_xyz, np.float64).reshape(-1, 3)
    if len(L) == 0:
        raise ValueError("no ligand heavy atoms")
    hits = cKDTree(L).query_ball_point(fs.points.astype(np.float64), cutoff, return_length=True)
    idx = np.flatnonzero(hits > 0)
    dmin, _ = fs.atom_tree().query(L, k=1)
    info = {"n_ligand_atoms": int(len(L)), "ligand_protein_min_dist": float(dmin.min()),
            "ligand_protein_median_dist": float(np.median(dmin))}
    return LPocket(idx=idx, residues=fs.residues_near(idx, lining_cutoff), volume_A3=fs.volume(idx),
                   definition="ligand", info=info)


def lmode_from_residues(fs: Featurized, residues, cutoff: float = RES_CUTOFF, bur_min: float = RES_BUR_MIN,
                        bur_feature: str = "bur10", lining_cutoff: float = LINING_CUTOFF,
                        single_chain_fallback: bool = True) -> LPocket:
    """Points within ``cutoff`` Å of a heavy atom of the listed residues AND ``bur_feature >= bur_min``.
    Residue ids must use the numbering of the featurised file ("chain:num[icode]").
    ``single_chain_fallback``: if the structure has exactly one chain and a listed residue's chain is absent,
    the residue is looked up in that chain (recorded as ``info['chain_remapped']``)."""
    want = list(dict.fromkeys(residues))
    chains = sorted({r.rpartition(":")[0] for r in fs.res_ids.tolist()})
    remapped = False
    if single_chain_fallback and len(chains) == 1:
        new = []
        for r in want:
            ch, _, num = r.rpartition(":")
            if ch != chains[0]:
                r, remapped = f"{chains[0]}:{num}", True
            new.append(r)
        want = list(dict.fromkeys(new))
    lookup = {r: i for i, r in enumerate(fs.res_ids.tolist())}
    found = [lookup[r] for r in want if r in lookup]
    missing = [r for r in want if r not in lookup]
    info = {"n_def_residues": len(want), "n_missing_residues": len(missing), "missing_residues": missing[:20],
            "chain_remapped": remapped}
    if not found:
        raise ValueError("none of the pocket residues found in the structure")
    atoms = np.flatnonzero(np.isin(fs.atom_res, np.asarray(found)))
    hits = cKDTree(fs.atom_xyz[atoms].astype(np.float64)).query_ball_point(
        fs.points.astype(np.float64), cutoff, return_length=True)
    idx = np.flatnonzero((hits > 0) & (fs.feature(bur_feature) >= bur_min))
    return LPocket(idx=idx, residues=fs.residues_near(idx, lining_cutoff), volume_A3=fs.volume(idx),
                   definition="residues", info=info)


# --------------------------------------------------------------------------- detected pockets
@dataclass
class MergedPocket:
    members: list             # full-list pocket indices (0-based; BURROW rank = i + 1), ascending
    idx: np.ndarray           # union of member point indices (sorted)
    residues: frozenset
    score: float              # max member score
    volume_A3: float


def merge_pockets(fs: Featurized, which: str = "region", touch: float = MERGE_TOUCH,
                  jaccard: float = MERGE_JACCARD) -> list:
    """Merge touching detected pockets: connected components of the graph whose edges join pockets with any
    point pair <= ``touch`` Å or residue Jaccard >= ``jaccard``.  ``which``: ``region`` | ``v2`` | ``full``.
    Returned in order of their best member's rank."""
    sel = {"region": fs.pk_in_region, "v2": fs.pk_in_v2, "full": np.ones(fs.n_pockets, bool)}[which]
    ids = np.flatnonzero(sel).tolist()
    n = len(ids)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    sets = [fs.pocket_residue_set(i) for i in ids]
    trees = [cKDTree(fs.points[fs.pocket_idx(i)]) for i in ids]
    for a in range(n):
        for b in range(a + 1, n):
            u, v = sets[a] | sets[b], sets[a] & sets[b]
            j = len(v) / len(u) if u else 0.0
            if j >= jaccard or trees[a].count_neighbors(trees[b], touch) > 0:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    groups: dict = {}
    for a in range(n):
        groups.setdefault(find(a), []).append(ids[a])
    out = []
    for root in sorted(groups):
        mem = sorted(groups[root])
        idx = np.unique(np.concatenate([fs.pocket_idx(i) for i in mem]))
        res = frozenset().union(*[fs.pocket_residue_set(i) for i in mem])
        out.append(MergedPocket(members=mem, idx=idx, residues=res, score=float(max(fs.pk_score[mem])),
                                volume_A3=fs.volume(idx)))
    return out


@dataclass
class DMatch:
    pocket: MergedPocket | None   # best-covering merged pocket (None if there are no detected pockets)
    coverage: float               # fraction of site points <= cover_dist of a point of ``pocket``
    missed: bool                  # coverage < min_coverage
    n_merged: int                 # merged pockets available
    rank_in_merged: int           # 1-based position of ``pocket`` in score order of the merged list (-1 if none)


def coverage(fs: Featurized, l_idx, d_idx, cover_dist: float = COVER_DIST) -> float:
    l_idx = np.asarray(l_idx, np.int64)
    if len(l_idx) == 0 or len(d_idx) == 0:
        return 0.0
    d, _ = cKDTree(fs.points[np.asarray(d_idx, np.int64)]).query(fs.points[l_idx], k=1,
                                                                  distance_upper_bound=cover_dist + 1e-9)
    return float(np.isfinite(d).mean())


def dmode_match(fs: Featurized, l_idx, which: str = "region", cover_dist: float = COVER_DIST,
                min_coverage: float = MIN_COVERAGE, merged: list | None = None, **merge_kw) -> DMatch:
    """Detected pocket (merged, see ``merge_pockets``) with the highest coverage of the site points.
    Ties -> higher score, then better rank.  ``missed`` if coverage < ``min_coverage``."""
    if merged is None:
        merged = merge_pockets(fs, which, **merge_kw)
    if not merged:
        return DMatch(None, 0.0, True, 0, -1)
    cov = [coverage(fs, l_idx, mp.idx, cover_dist) for mp in merged]
    best = min(range(len(merged)), key=lambda k: (-cov[k], -merged[k].score, merged[k].members[0]))
    order = sorted(range(len(merged)), key=lambda k: (-merged[k].score, merged[k].members[0]))
    return DMatch(merged[best], cov[best], cov[best] < min_coverage, len(merged), order.index(best) + 1)


def best_member(fs, l_idx, members, cover_dist: float = COVER_DIST) -> tuple[int, float]:
    """The single detected (full-list) pocket among ``members`` with maximal coverage of the site points
    (ties -> lower index = better BURROW rank).  Returns (member, coverage)."""
    l_idx = np.asarray(l_idx, np.int64)
    best, bc = int(members[0]), -1.0
    for m in sorted(int(x) for x in members):
        d_idx = fs.pk_indices[fs.pk_indptr[m]:fs.pk_indptr[m + 1]]
        if len(l_idx) == 0 or len(d_idx) == 0:
            c = 0.0
        else:
            d, _ = cKDTree(np.asarray(fs.points[d_idx], np.float64)).query(
                np.asarray(fs.points[l_idx], np.float64), k=1, distance_upper_bound=cover_dist + 1e-9)
            c = float(np.isfinite(d).mean())
        if c > bc:
            best, bc = m, c
    return best, bc


# --------------------------------------------------------------------------- ligand files / residue lists
_TWO_LETTER = {"CL", "BR", "FE", "ZN", "MG", "MN", "CU", "CO", "NI", "CA", "NA", "SE", "HG", "CD", "PT", "AU",
               "AS", "SI", "LI", "AL", "GA", "RU", "RH", "IR", "OS", "PD", "AG", "SB", "TE", "XE", "KR", "BE"}


def read_ligand_heavy_atoms(path) -> tuple[np.ndarray, list]:
    """Heavy-atom coordinates and elements of a ligand file (.sdf/.mol: V2000 atom block of the first record;
    .pdb: ATOM/HETATM records, element from columns 77-78 or the atom name)."""
    path = Path(path)
    text = path.read_text(errors="replace").splitlines()
    xyz, el = [], []
    if path.suffix.lower() in (".sdf", ".mol"):
        counts = text[3]
        if "V3000" in counts:
            raise ValueError("V3000 molfile not supported")
        na = int(counts[0:3])
        for line in text[4:4 + na]:
            xyz.append([float(line[0:10]), float(line[10:20]), float(line[20:30])])
            el.append(line[31:34].strip().upper())
    else:
        for line in text:
            if line.startswith(("ATOM  ", "HETATM")):
                e = line[76:78].strip()
                if not e:  # no element column: two-letter element only if left-aligned in the name field
                    nm = line[12:16]
                    two = nm[:2].upper()
                    e = two if (nm[0].isalpha() and two in _TWO_LETTER) else nm.strip().lstrip("0123456789")[:1]
                xyz.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                el.append(e.upper())
    xyz = np.asarray(xyz, np.float64).reshape(-1, 3)
    el = np.asarray(el)
    heavy = ~np.isin(el, ["H", "D"])
    return xyz[heavy], el[heavy].tolist()


def parse_residue_list(pocket_def: str) -> list:
    """``"A:43,45,46"`` (optionally ``;``-separated per chain) -> ["A:43", "A:45", "A:46"]."""
    out = []
    for part in str(pocket_def).split(";"):
        if not part.strip():
            continue
        ch, _, nums = part.partition(":")
        out += [f"{ch.strip()}:{n.strip()}" for n in nums.split(",") if n.strip()]
    return out


# --------------------------------------------------------------------------- site shaper (sph<R>)
# A located point set S (ligand shell, residue shell or a BURROW pocket) only *locates* the site; the shaper
# cuts the described set: all buried points within R Å of S's buriedness-weighted centroid.  L- and D-located
# sites therefore differ only in where the centre is, not in how the extent is cut.
SITE_BUR_FEATURE = "bur10"
SITE_BUR_MIN = 0.5


def _feat(fs, name):
    return np.asarray(fs.feats[:, list(fs.feature_names).index(name)], np.float64)


def buried_centroid(fs, idx, feature: str = "bur16", power: float = 4.0) -> np.ndarray:
    """Centroid of ``idx`` weighted by vol * feature^power (input frame).  Falls back to the vol-weighted centroid
    (then the plain centroid) if the weights vanish."""
    idx = np.asarray(idx, np.int64)
    if len(idx) == 0:
        raise ValueError("empty point set")
    P = np.asarray(fs.points[idx], np.float64)
    v = np.asarray(fs.vol[idx], np.float64)
    for w in (v * np.clip(_feat(fs, feature)[idx], 0, None) ** power, v, np.ones(len(idx))):
        if w.sum() > 0:
            return (w[:, None] * P).sum(0) / w.sum()
    return P.mean(0)


def site_sphere(fs, center, radius: float, bur_feature: str = SITE_BUR_FEATURE,
                bur_min: float = SITE_BUR_MIN) -> np.ndarray:
    """All points of the structure within ``radius`` Å of ``center`` with ``bur_feature >= bur_min`` (sorted)."""
    P = np.asarray(fs.points, np.float64)
    d2 = ((P - np.asarray(center, np.float64)) ** 2).sum(1)
    return np.flatnonzero((d2 <= radius * radius) & (_feat(fs, bur_feature) >= bur_min))


def shape_site(fs, idx, shaper: str) -> np.ndarray:
    """Apply a named shaper to a located point set: ``base`` (the set itself) or ``sph<R>`` (buried points
    within R Å of the buriedness-weighted centroid of the set; the method uses sph8)."""
    idx = np.asarray(idx, np.int64)
    if shaper == "base":
        return idx
    if shaper.startswith("sph"):
        return site_sphere(fs, buried_centroid(fs, idx), float(shaper[3:]))
    raise ValueError(shaper)


__all__ = ["Featurized", "featurize_structure", "model_path", "LPocket", "lmode_from_ligand",
           "lmode_from_residues", "MergedPocket", "merge_pockets", "DMatch", "dmode_match", "coverage",
           "best_member", "read_ligand_heavy_atoms", "parse_residue_list", "sort_residues", "buried_centroid",
           "site_sphere", "shape_site", "ADAPTER_VERSION", "REGION_RULE"]
