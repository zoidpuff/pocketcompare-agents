"""Pocket adapter (DESIGN §2.1): the single source of BURROW points, point features and pocket definitions
for every method in this project.

    fs = featurize_structure(path)                       # all BURROW solvent-shell points + features + pockets
    lp = lmode_from_ligand(fs, ligand_heavy_xyz)          # L-mode: points <= 4 Å of the ligand
    lp = lmode_from_residues(fs, ["A:43", ...])           # L-mode from a residue list (+ bur10 >= 0.5)
    dm = dmode_match(fs, lp.idx)                          # D-mode: merged region-rule pocket covering lp
    fs.save(path) / Featurized.load(path)                 # per-structure cache (compressed npz)

Points.  ``featurize_structure`` runs the BURROW reference pipeline (``pocketdetect.burrow``) once on the
protein-only view of the structure (ligands, waters, ions, nucleic acids and hydrogens stripped by
``protein_from_structure``) and keeps EVERY featurised point, not only pocket points: the dense LIGSITE
survivors (``vol`` = 1 grid voxel), the coarse sub-lattice points that stand for the exposed shell
(``vol`` = subsample^3 = 27 voxels in the ``default`` preset) and the metal candidates (``vol`` = 0).
Volumes are therefore always ``sum(vol[idx]) * spacing**3`` Å^3, never point counts.

Pockets.  One run yields BURROW's full output list (``min_score=None``, <= 50 pockets after NMS); the
``--output-rule region`` list and the default (v2) list are post-filters of it (flags ``pk_in_region``,
``pk_in_v2``), exactly as ``pocketdetect.burrow.export.pocket_representations`` (tested).

Leakage note (DESIGN §2.6): ``point_score`` is BURROW's learned point score; it is stored separately from
the 84 analytic point features (``feats``) and may only be used in ablation arms.
"""
from __future__ import annotations

import functools
import hashlib
import io
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ADAPTER_VERSION = "pockets-v1"
REGION_RULE = "c16_0.005"          # == pocketdetect.burrow.cli.REGION_RULE (checked at featurisation)
WATER = 2                          # pocketdetect.structure kind codes: 0 protein, 1 ligand, 2 water, 3 other polymer

# defaults of DESIGN §2.1 (all parameterised in the functions below)
L_CUTOFF = 4.0                     # point <= 4 Å of a ligand heavy atom
LINING_CUTOFF = 4.0                # residue heavy atom <= 4 Å of an L-mode point
RES_CUTOFF = 4.0                   # residue-list mode: point <= 4 Å of a listed residue's heavy atom
RES_BUR_MIN = 0.5                  # ... and bur10 >= 0.5
MERGE_TOUCH = 1.5                  # merge detected pockets with any point pair <= 1.5 Å
MERGE_JACCARD = 0.3                # ... or residue Jaccard >= 0.3
COVER_DIST = 1.5                   # L point covered if <= 1.5 Å of a detected pocket point
MIN_COVERAGE = 0.3                 # below -> "missed"


# --------------------------------------------------------------------------- provenance
@functools.lru_cache(maxsize=None)
def _git_state(repo: str) -> dict:
    def run(*a):
        try:
            return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""
    return {"commit": run("rev-parse", "HEAD") or None,
            "src_dirty": bool(run("status", "--porcelain", "--", "src"))}


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


def pocketdetect_root() -> Path:
    import pocketdetect
    return Path(pocketdetect.__file__).resolve().parents[2]


def model_path(ranker: str = "all", preset: str = "default") -> Path:
    from pocketdetect.burrow.cli import DEFAULT_MODELS
    return pocketdetect_root() / DEFAULT_MODELS[(ranker, preset)]


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
    point_score: np.ndarray   # (P,) float32 learned BURROW point score (ablation only, §2.6)
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
    pk_in_v2: np.ndarray      # (K,) bool: in the default (v2 floor) output
    pk_in_region: np.ndarray  # (K,) bool: in the --output-rule region output
    meta: dict = field(default_factory=dict)
    _ptree: object = field(default=None, repr=False, compare=False)
    _atree: object = field(default=None, repr=False, compare=False)

    # ---- convenience
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
        """Write a compressed npz atomically (tmp + rename); byte-deterministic.  Returns bytes written."""
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


def featurize_structure(path, chains=None, af_mode: bool = False, preset: str = "default", ranker: str = "all",
                        key: str | None = None) -> Featurized:
    """Run BURROW (reference implementation) once on the protein of ``path`` and keep everything.

    path     : PDB/mmCIF file (``.gz`` allowed) or a loaded ``pocketdetect.structure.Structure``.
    chains   : iterable of author chain ids to keep (None = all protein chains of the first model).
    af_mode  : BURROW AF mode (pLDDT pruning + soft occlusion; needs pLDDT in the B-factor column).
    preset   : BURROW preset (``default`` | ``accurate`` | ``fast``); ranker ``all`` | ``small``.
    """
    from pocketdetect.burrow.model import (FormationConfig, candidates, pocket_features, rank_predict,
                                           score_points)
    from pocketdetect.burrow.cli import REGION_RULE as _RR
    from pocketdetect.burrow.export import _feature_cfg
    from pocketdetect.burrow.features import point_features
    from pocketdetect.burrow.output_rules import apply_rule
    from pocketdetect.burrow.pipeline import finalize, output_residues
    from pocketdetect.burrow.pockets import assign_residues
    from pocketdetect.burrow.prep import protein_from_structure
    from pocketdetect.structure import Structure, load_structure

    assert _RR == REGION_RULE, f"BURROW region rule changed: {_RR}"
    t0 = time.perf_counter()
    mp = model_path(ranker, preset)
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
    # stripped non-protein heavy atoms (ligands, ions, cofactors); kept only to resolve ligand-defined pockets
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

    gs = _git_state(str(pocketdetect_root()))
    meta = {
        "adapter_version": ADAPTER_VERSION, "structure_path": None if sha is None else str(path), "structure_sha256": sha,
        "chains": None if chains is None else list(chains), "af_mode": bool(af_mode), "preset": preset,
        "ranker": ranker, "model_path": str(mp), "model_sha256": _sha256(str(mp)),
        "pocketdetect_commit": gs["commit"], "pocketdetect_src_dirty": gs["src_dirty"],
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


# --------------------------------------------------------------------------- L-mode
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
    the residue is looked up in that chain (TOUGH-M1's table writes "A:" although its files keep the original
    chain letter); recorded as ``info['chain_remapped']``."""
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


# --------------------------------------------------------------------------- D-mode
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
    coverage: float               # fraction of L-mode points <= cover_dist of a point of ``pocket``
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
    """Detected pocket (merged, see ``merge_pockets``) with the highest coverage of the L-mode points.
    Ties -> higher score, then better rank.  ``missed`` if coverage < ``min_coverage``."""
    if merged is None:
        merged = merge_pockets(fs, which, **merge_kw)
    if not merged:
        return DMatch(None, 0.0, True, 0, -1)
    cov = [coverage(fs, l_idx, mp.idx, cover_dist) for mp in merged]
    best = min(range(len(merged)), key=lambda k: (-cov[k], -merged[k].score, merged[k].members[0]))
    order = sorted(range(len(merged)), key=lambda k: (-merged[k].score, merged[k].members[0]))
    return DMatch(merged[best], cov[best], cov[best] < min_coverage, len(merged), order.index(best) + 1)


# --------------------------------------------------------------------------- ligand files / definitions
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


def resolve_pocket(fs: Featurized, row: dict, root: Path | None = None, cutoff: float = L_CUTOFF,
                   bur_min: float = RES_BUR_MIN, prefer: str = "ligand") -> tuple[LPocket, dict]:
    """L-mode pocket for one benchmark pocket-table row.  Precedence: a shipped ligand file (if
    ``prefer == 'ligand'``), then ligand residues inside the structure (``ligand_residue``: ``LIG:chain:resnum``
    ;-joined, ProSPECCTs; ``ligand_het_site``: Vertex), then a residue list (``residue_list``).  Returns the
    pocket and a record ``{definition, alt_*}`` (for TOUGH-style sets with both ligand file and residue list the
    residue-list pocket is computed as an alternative and its Jaccard with the chosen one recorded)."""
    root = Path(root) if root is not None else Path(".")
    dtype = row.get("pocket_def_type")
    lig_file = row.get("ligand_file")
    rec: dict = {}
    res_pocket = None
    if dtype == "residue_list" and row.get("pocket_def"):
        try:
            res_pocket = lmode_from_residues(fs, parse_residue_list(row["pocket_def"]), bur_min=bur_min)
        except ValueError as e:
            rec["alt_error"] = str(e)
    lp = None
    if prefer == "ligand" and isinstance(lig_file, str) and lig_file:
        lf = root / lig_file
        sdf = lf.with_suffix(".sdf")
        src = sdf if sdf.exists() else lf
        xyz, _ = read_ligand_heavy_atoms(src)
        lp = lmode_from_ligand(fs, xyz, cutoff)
        rec["definition"] = f"ligand_file:{src.suffix.lstrip('.')}"
    elif dtype == "ligand_xyz":
        # BLiPS: ligand heavy-atom coordinates given directly (pooled/transferred instances, flattened x,y,z)
        xyz = np.asarray(row["ligand_xyz"], np.float64).reshape(-1, 3)
        lp = lmode_from_ligand(fs, xyz, cutoff)
        rec["definition"] = "ligand_xyz"
        alt = row.get("alt_ligand_xyz")
        if alt is not None and len(alt):
            ap_ = lmode_from_ligand(fs, np.asarray(alt, np.float64).reshape(-1, 3), cutoff)
            a, b = set(lp.idx.tolist()), set(ap_.idx.tolist())
            rec.update(alt_definition="label_ligand_only", alt_n_points=ap_.n_points, alt_volume_A3=ap_.volume_A3,
                       alt_idx=ap_.idx, alt_jaccard=len(a & b) / len(a | b) if a | b else 0.0,
                       alt_n_missing_residues=0, alt_chain_remapped=False)
    elif dtype == "ligand_residue":
        sel = []
        for tok in str(row["pocket_def"]).split(";"):
            _, ch, num = tok.split(":")
            sel.append(f"{ch}:{num}")
        m = np.isin(fs.het_res, sel) & (fs.het_resname == str(row.get("ligand_resname") or "LIG"))
        lp = lmode_from_ligand(fs, fs.het_xyz[m], cutoff)
        rec["definition"] = "ligand_residue"
    elif dtype == "ligand_het_site":
        # Vertex: "HET:<code>;site_index:<k>"; instance k (1-based) of the residues named <code> in
        # ``het_instances`` order (chain, seqid sorted).  UNVERIFIED semantics -- check before the final eval.
        het = str(row["pocket_def"]).split(";")[0].split(":")[1]
        k = int(str(row["pocket_def"]).split("site_index:")[1])
        inst = [x for x in str(row.get("het_instances") or "").split(";") if x]
        if not (1 <= k <= len(inst)):
            raise ValueError(f"site_index {k} not among {len(inst)} {het} instances")
        ch, _, seqid = inst[k - 1].partition(":")
        m = (fs.het_resname == het) & (fs.het_res == f"{ch}:{seqid.strip()}")
        lp = lmode_from_ligand(fs, fs.het_xyz[m], cutoff)
        rec["definition"] = "ligand_het_site(unverified)"
    elif res_pocket is not None:
        lp, res_pocket = res_pocket, None
        rec["definition"] = "residue_list" + ("(chain_remapped)" if lp.info["chain_remapped"] else "")
    else:
        raise ValueError(rec.get("alt_error") or f"unsupported pocket definition {dtype!r}")
    if res_pocket is not None:
        a, b = set(lp.idx.tolist()), set(res_pocket.idx.tolist())
        rec.update(alt_definition="residue_list", alt_n_points=res_pocket.n_points,
                   alt_volume_A3=res_pocket.volume_A3, alt_idx=res_pocket.idx,
                   alt_jaccard=len(a & b) / len(a | b) if a | b else 0.0,
                   alt_n_missing_residues=res_pocket.info["n_missing_residues"],
                   alt_chain_remapped=res_pocket.info["chain_remapped"])
    return lp, rec


__all__ = ["Featurized", "featurize_structure", "LPocket", "lmode_from_ligand", "lmode_from_residues",
           "MergedPocket", "merge_pockets", "DMatch", "dmode_match", "coverage", "read_ligand_heavy_atoms",
           "parse_residue_list", "resolve_pocket", "sort_residues", "model_path", "ADAPTER_VERSION"]
