"""A1 — typed volumetric pocket fingerprint (514 d in the default configuration used by the method).

    pin = pocket_input(fs, idx)                       # from a pocketcompare.pockets.Featurized + point indices
    vec, layout = a1_descriptor(pin, cfg)             # float32 vector + block layout (list of Block)

Pipeline (every step is a parameter of the config dict, see ``DEFAULT_CONFIG``; the method uses it unchanged):

1. **Typing** (input frame).  Every protein heavy atom gets one VolSite-like pharmacophore type from a
   residue/atom-name table (``atom_type_codes``): hydrophobic, aromatic, donor, acceptor, donor/acceptor,
   positive, negative, or null (carbons bonded to N/O, Gly CA, Pro N ...).  A pocket point is typed by the atoms
   within ``radius`` (4.5 Å): *soft* = weights exp(-(d - d_min)/tau) over the atoms in range, times a cosine
   taper that brings the weight of an atom (and of the whole point, via d_min) to 0 at ``radius`` so the
   descriptor is continuous in the coordinates; *hard* = one-hot type of the nearest atom (VolSite).  BURROW
   metal-candidate points (vol = 0, protein-only view, so no ions) form the "metal" channel with weight
   ``metal_weight`` voxels.
2. **Resampling** (BURROW canonical frame ``X``, in which BURROW's 1 Å grid is defined, so the lattice is
   invariant to rigid motions of the input).  Each coarse sub-lattice point (vol = s^3, s = 3 in the default
   preset) is splatted into its s^3 grid voxels (they inherit its type/buriedness), duplicates with real dense
   voxels are dropped (dense wins), and voxels are pooled into cubic cells of ``resample.spacing`` (2 Å)
   anchored at the pocket's own bounding-box corner (integer grid indices -> no round-off at cell borders).
   Cell weight = number of voxels, cell coordinate = voxel centroid, cell attributes = voxel means.
   ``resample: null`` keeps the raw points weighted by ``vol``.
3. **Blocks** (all optional, order fixed):
   * ``hist`` — type x buriedness histogram: for channels shape + 8 types, the volume fraction of the pocket in
     each buriedness bin (``buriedness.feature``, fixed ``edges``; [] = no split).  Size-free.
   * ``pair`` — typed pair-distance distributions H_ab(r) = sum_{i != j} m_ia m_jb g_ij(r) / (W^2 - sum w_i^2),
     m_ia = w_i t_ia, over unordered channel pairs (a <= b) of ``pairs.channels``; g = Gaussian (sigma)
     soft-assignment of d_ij to ``n_bins`` centres on [r_min, r_max], normalised over bins (so the first and
     the last bin are open-ended).
   * ``usr`` — typed USRCAT-like moments: for each channel, the weighted mean / std / signed cube-root third
     moment of the distances of its mass to 4 reference points: centroid, buriedness-weighted centroid
     (weights w * b^bur_power), soft-farthest point from the centroid, soft-farthest from that point
     (soft-argmax with temperature ``soft_T`` Å; continuous, order-free).  In Å (shape scale is information).
   * ``glob`` — size-free scalars: volume-weighted means of buriedness/depth/escape/nearest point features,
     sqrt PCA eigenvalue ratios, compactness R_g / V^(1/3).
   * ``size`` — log pocket volume (Å^3), its own block so it can be down-weighted at scoring time.
4. ``hellinger``: square root of the (non-negative) ``hist`` and ``pair`` blocks.

Z-scoring and the learned projection live in ``pocketcompare.head``.
Only analytic BURROW point features are used (no ``point_score``).
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

A1_VERSION = "a1-v1"

# ----------------------------------------------------------------------------------------------- atom typing
ATOM_TYPES = ("null", "hyd", "aro", "don", "acc", "da", "pos", "neg")   # atom type codes 0..7
TYPE_CHANNELS = ("hyd", "aro", "don", "acc", "da", "pos", "neg", "met")  # point type vector (8)
_T = {n: i for i, n in enumerate(ATOM_TYPES)}

_BACKBONE = {"N": "don", "CA": "null", "C": "null", "O": "acc", "OXT": "neg"}
_SIDE = {
    "GLY": {},
    "ALA": {"CB": "hyd"},
    "VAL": {"CB": "hyd", "CG1": "hyd", "CG2": "hyd"},
    "LEU": {"CB": "hyd", "CG": "hyd", "CD1": "hyd", "CD2": "hyd"},
    "ILE": {"CB": "hyd", "CG1": "hyd", "CG2": "hyd", "CD1": "hyd"},
    "MET": {"CB": "hyd", "CG": "hyd", "SD": "hyd", "CE": "hyd"},
    "PRO": {"N": "null", "CB": "hyd", "CG": "hyd", "CD": "null"},
    "CYS": {"CB": "hyd", "SG": "hyd"},
    "PHE": {"CB": "hyd", **{a: "aro" for a in ("CG", "CD1", "CD2", "CE1", "CE2", "CZ")}},
    "TYR": {"CB": "hyd", **{a: "aro" for a in ("CG", "CD1", "CD2", "CE1", "CE2", "CZ")}, "OH": "da"},
    "TRP": {"CB": "hyd", **{a: "aro" for a in ("CG", "CD1", "CD2", "CE2", "CE3", "CZ2", "CZ3", "CH2")},
            "NE1": "don"},
    "HIS": {"CB": "hyd", "CG": "aro", "CD2": "aro", "CE1": "aro", "ND1": "da", "NE2": "da"},
    "SER": {"CB": "null", "OG": "da"},
    "THR": {"CB": "null", "CG2": "hyd", "OG1": "da"},
    "ASN": {"CB": "hyd", "CG": "null", "OD1": "acc", "ND2": "don"},
    "GLN": {"CB": "hyd", "CG": "hyd", "CD": "null", "OE1": "acc", "NE2": "don"},
    "ASP": {"CB": "hyd", "CG": "null", "OD1": "neg", "OD2": "neg"},
    "GLU": {"CB": "hyd", "CG": "hyd", "CD": "null", "OE1": "neg", "OE2": "neg"},
    "LYS": {"CB": "hyd", "CG": "hyd", "CD": "hyd", "CE": "null", "NZ": "pos"},
    "ARG": {"CB": "hyd", "CG": "hyd", "CD": "null", "NE": "pos", "CZ": "null", "NH1": "pos", "NH2": "pos"},
}
_ALIAS = {"MSE": ("MET", {"SE": "SD"}), "HSD": ("HIS", {}), "HSE": ("HIS", {}), "HID": ("HIS", {}),
          "HIE": ("HIS", {}), "HIP": ("HIS", {}), "CYX": ("CYS", {}), "ASH": ("ASP", {}), "GLH": ("GLU", {}),
          "LYN": ("LYS", {})}
_ELEMENT_FALLBACK = {"C": "hyd", "N": "don", "O": "acc", "S": "hyd", "SE": "hyd"}


def atom_type(res_name: str, atom_name: str, element: str = "") -> int:
    """Type code (index into ATOM_TYPES) of one protein heavy atom.  Unknown residues/atoms fall back to the
    element (C/S/Se hydrophobic, N donor, O acceptor, else null)."""
    rn, an = str(res_name).upper(), str(atom_name).upper()
    if rn in _ALIAS:
        rn, ren = _ALIAS[rn]
        an = ren.get(an, an)
    side = _SIDE.get(rn)
    if side is not None:
        if an in side:
            return _T[side[an]]
        if an in _BACKBONE:
            return _T[_BACKBONE[an]]
    return _T[_ELEMENT_FALLBACK.get(str(element).upper(), "null")]


def atom_type_codes(res_names, atom_names, elements) -> np.ndarray:
    """Vectorised ``atom_type`` over atoms (unique (res, atom, element) triples are looked up once)."""
    keys = np.char.add(np.char.add(np.asarray(res_names, str), "|"),
                       np.char.add(np.char.add(np.asarray(atom_names, str), "|"), np.asarray(elements, str)))
    u, inv = np.unique(keys, return_inverse=True)
    lut = np.array([atom_type(*k.split("|")) for k in u.tolist()], np.int8)
    return lut[inv.reshape(-1)] if len(u) else np.zeros(0, np.int8)


# ----------------------------------------------------------------------------------------------- config
DEFAULT_PAIR_CHANNELS = ["shape", "hyd", "aro", "don", "acc", "pos", "neg"]
DEFAULT_CONFIG = {
    "typing": {"mode": "soft", "radius": 4.5, "tau": 0.5, "taper": 0.5, "k_max": 32},
    "metal_weight": 1.0,
    # bur16 takes values on a 1/30 grid (30 rays); edges sit half-way between grid values -> TOUGH-M1 L-mode
    # volume tertiles (0.600 / 0.867 measured on 400 pockets, label-free)
    "buriedness": {"feature": "bur16", "edges": [0.5833, 0.85]},
    "resample": {"spacing": 2.0},
    "pairs": {"r_min": 2.0, "r_max": 20.0, "n_bins": 14, "sigma": 1.0, "channels": DEFAULT_PAIR_CHANNELS},
    "usr": {"channels": DEFAULT_PAIR_CHANNELS, "soft_T": 0.5, "bur_power": 4.0},
    "glob": {"features": ["bur6", "bur10", "bur16", "burbb16", "depth", "escape", "nearest"]},
    "blocks": ["hist", "pair", "usr", "glob", "size"],
    "hellinger": True,
    # scoring-time block weights of the research code; not used by the descriptor or the method
    "score_weights": {"hist": 1.0, "pair": 1.0, "usr": 1.0, "glob": 1.0, "size": 0.25},
}
BLOCK_ORDER = ("hist", "pair", "usr", "glob", "size")


def _deep_update(base: dict, upd: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (upd or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_update(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def make_config(overrides: dict | None = None) -> dict:
    """DEFAULT_CONFIG updated recursively with ``overrides`` (``resample: null`` disables resampling)."""
    cfg = _deep_update(DEFAULT_CONFIG, overrides or {})
    bad = set(cfg["blocks"]) - set(BLOCK_ORDER)
    if bad:
        raise ValueError(f"unknown blocks {bad}")
    if cfg["typing"]["mode"] not in ("soft", "hard"):
        raise ValueError("typing.mode must be soft|hard")
    return cfg


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


# ----------------------------------------------------------------------------------------------- inputs
@dataclass
class PocketInput:
    """Everything A1 needs for one pocket.

    xyz       (n,3) point coordinates in the input frame (typing against ``atom_xyz``)
    X         (n,3) the same points in BURROW's canonical frame (resampling lattice); toy inputs may pass xyz
    vol       (n,)  grid-voxel weights (1 dense, s^3 coarse, 0 metal candidate)
    is_metal  (n,)  bool
    feats     {name: (n,)} analytic point features used (buriedness feature + glob features)
    atom_xyz  (m,3) protein heavy atoms near the pocket (input frame), atom_type (m,) codes into ATOM_TYPES
    point_types optional (n,8) precomputed point type vectors (skips atom typing; used by tests)
    spacing   BURROW grid spacing (Å)
    """
    xyz: np.ndarray
    X: np.ndarray
    vol: np.ndarray
    is_metal: np.ndarray
    feats: dict
    atom_xyz: np.ndarray | None = None
    atom_type: np.ndarray | None = None
    point_types: np.ndarray | None = None
    spacing: float = 1.0
    meta: dict = field(default_factory=dict)


def needed_features(cfg: dict) -> list:
    return sorted({cfg["buriedness"]["feature"], *cfg["glob"]["features"]})


def pocket_input(fs, idx, atom_types: np.ndarray | None = None, features=None, radius: float = 6.0) -> PocketInput:
    """PocketInput for point indices ``idx`` of a ``pocketcompare.pockets.Featurized`` (or any object with the
    same attributes: points, X, vol, is_metal, feats, feature_names, atom_xyz, atom_name, atom_element,
    atom_res, res_names, spacing).  Atoms within ``radius`` + bounding box of the points are kept.
    ``atom_types``: precomputed ``atom_type_codes`` for all atoms of the structure (cache it per structure)."""
    idx = np.asarray(idx, np.int64)
    pts = np.asarray(fs.points[idx], np.float64)
    names = list(fs.feature_names)
    features = features or sorted(set(DEFAULT_CONFIG["glob"]["features"]) | {"bur16"})
    feats = {f: np.asarray(fs.feats[idx, names.index(f)], np.float64) for f in features}
    if atom_types is None:
        atom_types = atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
    A = np.asarray(fs.atom_xyz, np.float64)
    if len(pts):
        lo, hi = pts.min(0) - radius, pts.max(0) + radius
        near = np.all((A >= lo) & (A <= hi), axis=1)
    else:
        near = np.zeros(len(A), bool)
    return PocketInput(xyz=pts, X=np.asarray(fs.X[idx], np.float64), vol=np.asarray(fs.vol[idx], np.float64),
                       is_metal=np.asarray(fs.is_metal[idx], bool), feats=feats, atom_xyz=A[near],
                       atom_type=np.asarray(atom_types)[near], spacing=float(fs.spacing))


# ----------------------------------------------------------------------------------------------- steps
def _taper(d, radius, width):
    """1 for d <= radius - width, cosine down to 0 at radius, 0 beyond (inf -> 0)."""
    if width <= 0:
        return (d <= radius).astype(np.float64)
    x = np.clip((d - (radius - width)) / width, 0.0, 1.0)
    out = 0.5 * (1.0 + np.cos(np.pi * x))
    out[~np.isfinite(d)] = 0.0
    return out


def type_points(xyz, atom_xyz, atom_type, cfg_typing: dict) -> np.ndarray:
    """(n, 7) atom-derived type vectors (channels hyd..neg; the metal channel is added by the caller)."""
    n = len(xyz)
    out = np.zeros((n, 7), np.float64)
    if n == 0 or atom_xyz is None or len(atom_xyz) == 0:
        return out
    R = float(cfg_typing["radius"])
    k = int(min(cfg_typing.get("k_max", 32), len(atom_xyz)))
    d, j = cKDTree(atom_xyz).query(xyz, k=k, distance_upper_bound=R)
    d = d.reshape(n, k)
    j = j.reshape(n, k)
    valid = np.isfinite(d)
    jj = np.where(valid, j, 0)
    codes = np.asarray(atom_type, np.int64)[jj]                       # (n, k)
    onehot = np.zeros((n, k, len(ATOM_TYPES)), np.float64)
    np.put_along_axis(onehot, codes[..., None], 1.0, axis=2)
    onehot[~valid] = 0.0
    if cfg_typing["mode"] == "hard":
        t = onehot[:, 0, 1:]                                          # nearest atom (k sorted by distance)
        return np.where(valid[:, :1], t, 0.0)
    dmin = np.where(valid[:, 0], d[:, 0], np.inf)
    tau = float(cfg_typing["tau"])
    width = float(cfg_typing.get("taper", 0.0))
    with np.errstate(invalid="ignore"):
        a = np.exp(-(np.where(valid, d, R) - np.where(np.isfinite(dmin), dmin, R)[:, None]) / tau)
    a = a * _taper(d, R, width) * valid
    s = a.sum(1)
    t = np.einsum("nk,nkc->nc", a, onehot[:, :, 1:]) / np.maximum(s, 1e-300)[:, None]
    t *= _taper(dmin, R, width)[:, None]
    t[s <= 0] = 0.0
    return t


def point_type_vectors(pin: PocketInput, cfg: dict) -> np.ndarray:
    """(n, 8) per-point type vectors (TYPE_CHANNELS)."""
    if pin.point_types is not None:
        return np.asarray(pin.point_types, np.float64)
    t7 = type_points(pin.xyz, pin.atom_xyz, pin.atom_type, cfg["typing"])
    met = pin.is_metal.astype(np.float64)
    t7[pin.is_metal] = 0.0
    return np.concatenate([t7, met[:, None]], 1)


def _bur_bins(b, edges) -> np.ndarray:
    edges = list(edges or [])
    if not edges:
        return np.ones((len(b), 1))
    k = np.searchsorted(np.asarray(edges, np.float64), b, side="right")
    out = np.zeros((len(b), len(edges) + 1))
    out[np.arange(len(b)), k] = 1.0
    return out


def point_weights(pin: PocketInput, cfg: dict) -> np.ndarray:
    return np.where(pin.is_metal, float(cfg["metal_weight"]), pin.vol).astype(np.float64)


def resample(pin: PocketInput, attrs: np.ndarray, cfg: dict):
    """Cells of the uniform lattice.  Returns (w (c,), C (c,3), A (c,p)) with A the weighted mean of ``attrs``.
    Without resampling: raw points (weights = vol, metal candidates = metal_weight)."""
    w0 = point_weights(pin, cfg)
    keep = w0 > 0
    rs = cfg.get("resample")
    if not rs:
        return w0[keep], pin.X[keep], attrs[keep]
    h = float(rs["spacing"])
    sp = float(pin.spacing)
    X = np.asarray(pin.X, np.float64)
    grid = ~pin.is_metal & (pin.vol > 0)
    if not grid.any():                                                # metal-only pocket: one point per cell
        return w0[keep], X[keep], attrs[keep]
    ref = X[grid].min(0)                                              # an on-grid point per axis
    u = (X - ref) / sp                                                # ~integers for grid points
    ui = np.rint(u).astype(np.int64)
    # splat coarse points into their s^3 voxels (s = round(vol^(1/3)))
    s = np.where(grid, np.rint(np.cbrt(np.maximum(pin.vol, 1.0))), 1).astype(np.int64)
    vox, par = [], []
    for sv in np.unique(s[grid]):
        sel = np.flatnonzero(grid & (s == sv))
        if sv == 1:
            vox.append(ui[sel])
            par.append(sel)
            continue
        o = np.arange(sv) - (sv - 1) // 2
        off = np.stack(np.meshgrid(o, o, o, indexing="ij"), -1).reshape(-1, 3)
        vox.append((ui[sel][:, None, :] + off[None]).reshape(-1, 3))
        par.append(np.repeat(sel, len(off)))
    # real dense voxels first so that np.unique(return_index) keeps them over splatted copies
    order = np.argsort([0 if (len(p) and s[p[0]] == 1) else 1 for p in par], kind="stable")
    vox = np.concatenate([vox[i] for i in order])
    par = np.concatenate([par[i] for i in order])
    _, first = np.unique(vox, axis=0, return_index=True)
    first = np.sort(first)
    vox, par = vox[first], par[first]
    vw = np.ones(len(vox))
    # metal candidates: not on the grid; own weight
    mi = np.flatnonzero(pin.is_metal & (w0 > 0))
    vu = np.concatenate([vox.astype(np.float64), u[mi]])
    vw = np.concatenate([vw, w0[mi]])
    par = np.concatenate([par, mi])
    anchor = vox.min(0).astype(np.float64)
    m = h / sp
    cell = np.floor((vu - anchor + 0.5) / m).astype(np.int64)
    _, inv = np.unique(cell, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    nc = inv.max() + 1
    W = np.bincount(inv, weights=vw, minlength=nc)
    xyz_v = ref + vu * sp
    C = np.stack([np.bincount(inv, weights=vw * xyz_v[:, k], minlength=nc) for k in range(3)], 1) / W[:, None]
    A = np.stack([np.bincount(inv, weights=vw * attrs[par, k], minlength=nc) for k in range(attrs.shape[1])], 1)
    A /= W[:, None]
    return W, C, A


def pair_histogram(C, M, r_min, r_max, n_bins, sigma, block_rows: int = 256) -> np.ndarray:
    """H[a, b, k] = sum_{i != j} M[i,a] M[j,b] g(d_ij, r_k); g = softmax over bins of -(d - r_k)^2 / 2 sigma^2.
    Not normalised."""
    C = np.asarray(C, np.float64)
    M = np.asarray(M, np.float64)
    n, nc = M.shape
    r = np.linspace(r_min, r_max, n_bins)
    H = np.zeros((nc, nc, n_bins))
    inv2s2 = 1.0 / (2.0 * sigma * sigma)
    for s0 in range(0, n, block_rows):
        s1 = min(n, s0 + block_rows)
        d = np.sqrt(((C[s0:s1, None, :] - C[None, :, :]) ** 2).sum(-1))       # (b, n)
        lg = -((d[..., None] - r) ** 2) * inv2s2                               # (b, n, K)
        lg -= lg.max(-1, keepdims=True)
        E = np.exp(lg)
        E /= E.sum(-1, keepdims=True)
        ii = np.arange(s0, s1)
        E[ii - s0, ii, :] = 0.0                                                # no self pairs
        tmp = np.einsum("bnk,nc->bkc", E, M, optimize=True)
        H += np.einsum("ba,bkc->ack", M[s0:s1], tmp, optimize=True)
    return H


def _pair_channel_matrix(T8, channels) -> np.ndarray:
    """(c, len(channels)) channel masses per cell for the pair/USR blocks.  'don'/'acc' absorb half of the
    donor/acceptor ('da') type; 'shape' = 1; 'met' and 'da' are also available by name."""
    idx = {n: i for i, n in enumerate(TYPE_CHANNELS)}
    cols = []
    for ch in channels:
        if ch == "shape":
            cols.append(np.ones(len(T8)))
        elif ch in ("don", "acc"):
            cols.append(T8[:, idx[ch]] + 0.5 * T8[:, idx["da"]])
        else:
            cols.append(T8[:, idx[ch]])
    return np.stack(cols, 1) if cols else np.zeros((len(T8), 0))


def _soft_argmax_point(C, w, d, T):
    z = d / T
    z = z - z.max()
    p = w * np.exp(z)
    return (p[:, None] * C).sum(0) / p.sum()


def _usr(C, w, b, Mc, cfg_usr) -> np.ndarray:
    W = w.sum()
    ctd = (w[:, None] * C).sum(0) / W
    bw = w * np.clip(b, 0, None) ** float(cfg_usr["bur_power"])
    cbur = (bw[:, None] * C).sum(0) / bw.sum() if bw.sum() > 0 else ctd
    T = float(cfg_usr["soft_T"])
    fct = _soft_argmax_point(C, w, np.linalg.norm(C - ctd, axis=1), T)
    ftf = _soft_argmax_point(C, w, np.linalg.norm(C - fct, axis=1), T)
    out = []
    for c in range(Mc.shape[1]):
        om = Mc[:, c] * w
        S = om.sum()
        for ref in (ctd, cbur, fct, ftf):
            if S <= 1e-9 * W:
                out += [0.0, 0.0, 0.0]
                continue
            dd = np.linalg.norm(C - ref, axis=1)
            mu = (om * dd).sum() / S
            var = (om * (dd - mu) ** 2).sum() / S
            m3 = (om * (dd - mu) ** 3).sum() / S
            out += [mu, np.sqrt(max(var, 0.0)), float(np.cbrt(m3))]
    return np.asarray(out)


# ----------------------------------------------------------------------------------------------- layout
@dataclass
class Block:
    name: str
    start: int
    stop: int
    names: list

    @property
    def size(self) -> int:
        return self.stop - self.start


def _block_names(cfg: dict) -> dict:
    nb = len(cfg["buriedness"]["edges"] or []) + 1
    hist_ch = (["shape"] if nb > 1 else []) + list(TYPE_CHANNELS)
    pc = list(cfg["pairs"]["channels"])
    pairs = [(pc[a], pc[b]) for a in range(len(pc)) for b in range(a, len(pc))]
    K = int(cfg["pairs"]["n_bins"])
    r = np.linspace(cfg["pairs"]["r_min"], cfg["pairs"]["r_max"], K)
    return {
        "hist": [f"hist:{c}:b{k}" for c in hist_ch for k in range(nb)],
        "pair": [f"pair:{a}-{b}:{rk:.2f}" for a, b in pairs for rk in r],
        "usr": [f"usr:{c}:{ref}:{m}" for c in cfg["usr"]["channels"] for ref in ("ctd", "cbur", "fct", "ftf")
                for m in ("mean", "std", "skew")],
        "glob": [f"glob:{f}" for f in cfg["glob"]["features"]] + ["glob:pca21", "glob:pca31", "glob:rg_v13"],
        "size": ["size:log_vol_A3"],
    }


def a1_layout(cfg: dict) -> list:
    names = _block_names(cfg)
    out, s = [], 0
    for b in BLOCK_ORDER:
        if b in cfg["blocks"]:
            out.append(Block(b, s, s + len(names[b]), names[b]))
            s += len(names[b])
    return out


def layout_to_json(layout) -> list:
    return [{"name": b.name, "start": b.start, "stop": b.stop, "names": b.names} for b in layout]


# ----------------------------------------------------------------------------------------------- main
def a1_descriptor(pin: PocketInput, cfg: dict | None = None, return_info: bool = False):
    """A1 vector (float32) and its block layout.  ``cfg`` = full config (``make_config``) or None (default)."""
    cfg = make_config() if cfg is None else cfg
    layout = a1_layout(cfg)
    blocks = set(cfg["blocks"])
    n = len(pin.vol)
    w_pts = point_weights(pin, cfg)
    if n == 0 or w_pts.sum() <= 0:
        raise ValueError("empty pocket")
    T8 = point_type_vectors(pin, cfg)                                         # (n, 8)
    bfeat = np.asarray(pin.feats[cfg["buriedness"]["feature"]], np.float64)
    Bm = _bur_bins(bfeat, cfg["buriedness"]["edges"])                          # (n, nb)
    attrs = np.concatenate([T8, Bm, bfeat[:, None]], 1)
    w, C, A = resample(pin, attrs, cfg)
    Tc, Bc, bc = A[:, :8], A[:, 8:8 + Bm.shape[1]], A[:, -1]
    W = w.sum()
    parts = {}
    if "hist" in blocks:
        ch = ([np.ones(len(w))] if Bm.shape[1] > 1 else []) + [Tc[:, k] for k in range(8)]
        parts["hist"] = np.concatenate([((w * c)[:, None] * Bc).sum(0) / W for c in ch])
    if "pair" in blocks:
        pc = cfg["pairs"]
        Mp = _pair_channel_matrix(Tc, pc["channels"]) * w[:, None]
        H = pair_histogram(C, Mp, pc["r_min"], pc["r_max"], int(pc["n_bins"]), pc["sigma"])
        norm = max(W * W - (w * w).sum(), 1e-12)
        iu = np.triu_indices(Mp.shape[1])
        parts["pair"] = (H[iu[0], iu[1], :] / norm).reshape(-1)
    if "usr" in blocks:
        parts["usr"] = _usr(C, w, bc, _pair_channel_matrix(Tc, cfg["usr"]["channels"]), cfg["usr"])
    if "glob" in blocks:
        wp = w_pts / w_pts.sum()
        g = [float((wp * pin.feats[f]).sum()) for f in cfg["glob"]["features"]]
        mu = (w[:, None] * C).sum(0) / W
        D = C - mu
        cov = (w[:, None, None] * D[:, :, None] * D[:, None, :]).sum(0) / W
        ev = np.sort(np.clip(np.linalg.eigvalsh(cov), 0, None))[::-1]
        r21 = np.sqrt(ev[1] / ev[0]) if ev[0] > 0 else 0.0
        r31 = np.sqrt(ev[2] / ev[0]) if ev[0] > 0 else 0.0
        vol_A3 = float(pin.vol.sum() * pin.spacing ** 3)
        rg = float(np.sqrt(ev.sum()))
        parts["glob"] = np.asarray(g + [r21, r31, rg / max(vol_A3, 1.0) ** (1 / 3)])
    if "size" in blocks:
        parts["size"] = np.asarray([np.log(max(float(pin.vol.sum() * pin.spacing ** 3), 1.0))])
    if cfg["hellinger"]:
        for b in ("hist", "pair"):
            if b in parts:
                parts[b] = np.sqrt(np.clip(parts[b], 0, None))
    vec = np.concatenate([parts[b.name] for b in layout]).astype(np.float32)
    assert len(vec) == layout[-1].stop
    if return_info:
        return vec, layout, {"n_cells": int(len(w)), "n_points": int(n)}
    return vec, layout


__all__ = ["A1_VERSION", "ATOM_TYPES", "TYPE_CHANNELS", "DEFAULT_CONFIG", "make_config", "config_hash",
           "atom_type", "atom_type_codes", "PocketInput", "pocket_input", "needed_features", "type_points",
           "resample", "pair_histogram", "a1_layout", "layout_to_json", "a1_descriptor", "Block"]
