"""L4 — learned point-cloud pocket encoder (PREREG Addendum A1; configs/a4_grid.yaml; reports/l4_pointnet.md).

Input = the sph8 site point set of a located pocket (``pockets.shape_site(fs, S, "sph8")``, the same set N1
describes), capped at ``CAP`` = 256 points by deterministic vol-weighted farthest-point sampling (``fps``), with per
point:

* xyz (input frame, Å) — used only through pairwise distances / E(n)-equivariant updates, so the embedding is
  invariant to rotations, reflections and translations of the input (tested in tests/test_l4.py);
* the 84 BURROW *analytic* point features (``fs.feature_names``: bur*/burbb*, depth, hit_*, escape, psp, nearest,
  metal_cand, n_coord28, coord_spread, n_all*, n4_*, f8_*, f12_*, prot_frac) — never ``point_score`` or any
  learned BURROW output;
* 8 soft VolSite-like type channels (``descriptors.a1.point_type_vectors`` with the A1 default typing: hyd, aro,
  don, acc, da, pos, neg + metal);
* vol weight = the BURROW voxel volume of all sph8 points assigned to the sample (nearest sampled point), so the
  sample's weights sum to the sph8 volume (metal candidates count 1 voxel, as A1/env).

Model (torch, ``L4Net``): per-point input MLP -> L EGNN layers on the kNN graph (k nearest by distance, recomputed
per layer on the updated coordinates; edge input = RBF(d_ij) + h_i + h_j; coordinate update x_i += mean_j (x_i -
x_j) phi(m_ij), bounded) -> vol-weighted attention pooling + vol-weighted mean -> MLP (optionally concatenated with
the N1 head input) -> 128-d, L2-normalised.  Point dropout and random rotations are training augmentations.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

L4_VERSION = "l4-v1"
CAP = 256
N_TYPES = 8

# features transformed by log1p before z-scoring (counts with heavy tails)
LOG1P_PREFIX = ("n_all", "n4_", "n_coord", "psp", "depth")


# ============================================================================================ point sets (numpy)
def fps(xyz: np.ndarray, w: np.ndarray, cap: int = CAP) -> np.ndarray:
    """Deterministic vol-weighted farthest-point sampling.  Start: the point nearest the w-weighted centroid; then
    repeatedly the point maximising min-distance-to-sample * w^(1/3) (ties -> lowest index).  Rigid-motion
    invariant up to float round-off.  Returns sorted indices (all points if n <= cap)."""
    n = len(xyz)
    if n <= cap:
        return np.arange(n)
    X = np.asarray(xyz, np.float64)
    w = np.maximum(np.asarray(w, np.float64), 1.0)
    c = (w[:, None] * X).sum(0) / w.sum()
    first = int(np.argmin(((X - c) ** 2).sum(1)))
    wf = w ** (1.0 / 3.0)
    sel = np.empty(cap, np.int64)
    sel[0] = first
    dmin = np.sqrt(((X - X[first]) ** 2).sum(1))
    for k in range(1, cap):
        j = int(np.argmax(dmin * wf))
        sel[k] = j
        dmin = np.minimum(dmin, np.sqrt(((X - X[j]) ** 2).sum(1)))
    return np.sort(sel)


def site_points(fs, I, atom_types, cap: int = CAP, a1_cfg=None) -> dict:
    """L4 point set of sph8 indices ``I`` of a Featurized-like ``fs``: xyz (m,3) f32, feats (m,84) f32 analytic,
    types (m,8) f32 soft VolSite channels, vol (m,) f32 aggregated voxel weight, n_sph8, vol_sph8 (voxels)."""
    from .descriptors import a1 as A1
    I = np.asarray(I, np.int64)
    if len(I) == 0:
        raise ValueError("empty sph8 set")
    cfg = a1_cfg or A1.make_config()
    v = np.where(np.asarray(fs.is_metal[I], bool), 1.0, np.asarray(fs.vol[I], np.float64))
    P = np.asarray(fs.points[I], np.float64)
    s = fps(P, v, cap)
    if len(s) < len(I):
        _, a = cKDTree(P[s]).query(P, k=1)
        vol = np.bincount(a, weights=v, minlength=len(s))
    else:
        vol = v
    J = I[s]
    pin = A1.pocket_input(fs, J, atom_types=atom_types, features=["bur16"])
    types = A1.point_type_vectors(pin, cfg)
    return {"xyz": np.asarray(fs.points[J], np.float32), "feats": np.asarray(fs.feats[J], np.float32),
            "types": types.astype(np.float32), "vol": vol.astype(np.float32), "n_sph8": int(len(I)),
            "vol_sph8": float(v.sum())}


class PointStore:
    """CSR point sets of one (dataset, locator): data/processed/l4/<dataset>/<loc>.npz + ids.parquet."""

    def __init__(self, path):
        with np.load(path) as z:
            self.indptr = z["indptr"]
            self.xyz = z["xyz"]
            self.feats = z["feats"]
            self.types = z["types"]
            self.vol = z["vol"]
        self.n = len(self.indptr) - 1

    def get(self, i):
        a, b = self.indptr[i], self.indptr[i + 1]
        return self.xyz[a:b], self.feats[a:b], self.types[a:b], self.vol[a:b]

    def size(self, i):
        return int(self.indptr[i + 1] - self.indptr[i])


# ============================================================================================ normalisation
def feature_transform(F: np.ndarray, names) -> np.ndarray:
    F = np.asarray(F, np.float32).copy()
    for k, n in enumerate(names):
        if n.startswith(LOG1P_PREFIX):
            F[:, k] = np.log1p(np.clip(F[:, k], 0, None))
    return F


class PointScaler:
    """z-score of transformed analytic features (statistics: BLiPS-train points, L + U pooled, label-free)."""

    def __init__(self, names, mean, std):
        self.names, self.mean, self.std = list(names), np.asarray(mean, np.float32), np.asarray(std, np.float32)

    @classmethod
    def fit(cls, names, F):
        T = feature_transform(F, names)
        return cls(names, T.mean(0), np.where(T.std(0) > 1e-6, T.std(0), 1.0))

    def __call__(self, F):
        return np.clip((feature_transform(F, self.names) - self.mean) / self.std, -5, 5).astype(np.float32)

    def to_dict(self):
        return {"names": self.names, "mean": self.mean.tolist(), "std": self.std.tolist(),
                "log1p_prefix": list(LOG1P_PREFIX)}

    @classmethod
    def from_dict(cls, d):
        return cls(d["names"], d["mean"], d["std"])


def point_input(feats_z, types, vol) -> np.ndarray:
    """Per-point model input: z-scored analytic features | soft types | log(vol weight)."""
    return np.concatenate([feats_z, types, np.log(np.maximum(vol, 1e-3))[:, None]], 1).astype(np.float32)


def pad_batch(sets, cap: int = CAP):
    """sets: list of (xyz (m,3), x (m,F)) -> xyz (B,cap,3), x (B,cap,F), mask (B,cap) float32 numpy arrays."""
    B, F = len(sets), sets[0][1].shape[1]
    X = np.zeros((B, cap, 3), np.float32)
    H = np.zeros((B, cap, F), np.float32)
    M = np.zeros((B, cap), np.float32)
    for i, (p, h) in enumerate(sets):
        m = len(p)
        X[i, :m], H[i, :m], M[i, :m] = p, h, 1.0
    return X, H, M


# ============================================================================================ model (torch)
def build_model(cfg: dict, d_point: int, d_n1: int = 0):
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class RBF(nn.Module):
        def __init__(self, n=16, r_max=12.0):
            super().__init__()
            self.register_buffer("mu", torch.linspace(0.0, r_max, n))
            self.gamma = (n / r_max) ** 2 / 2.0

        def forward(self, d):
            return torch.exp(-self.gamma * (d[..., None] - self.mu) ** 2)

    class EGNNLayer(nn.Module):
        def __init__(self, h, n_rbf, update_x):
            super().__init__()
            self.edge = nn.Sequential(nn.Linear(2 * h + n_rbf, h), nn.SiLU(), nn.Linear(h, h), nn.SiLU())
            self.att = nn.Linear(h, 1)
            self.node = nn.Sequential(nn.Linear(2 * h, h), nn.SiLU(), nn.Linear(h, h))
            self.norm = nn.LayerNorm(h)
            self.update_x = update_x
            if update_x:
                self.coord = nn.Sequential(nn.Linear(h, h), nn.SiLU(), nn.Linear(h, 1, bias=False))

        def forward(self, x, h, mask, knn, rbf):
            B, N, H = h.shape
            k = knn.shape[-1]
            idx = knn.reshape(B, N * k)
            hj = torch.gather(h, 1, idx[..., None].expand(-1, -1, H)).reshape(B, N, k, H)
            xj = torch.gather(x, 1, idx[..., None].expand(-1, -1, 3)).reshape(B, N, k, 3)
            mj = torch.gather(mask, 1, idx).reshape(B, N, k)
            rel = x[:, :, None, :] - xj
            d = torch.sqrt((rel ** 2).sum(-1) + 1e-8)
            m = self.edge(torch.cat([h[:, :, None, :].expand(-1, -1, k, -1), hj, rbf(d)], -1))
            a = torch.sigmoid(self.att(m)) * mj[..., None]
            agg = (a * m).sum(2) / (mj.sum(2, keepdim=True) + 1e-6)
            h = self.norm(h + self.node(torch.cat([h, agg], -1))) * mask[..., None]
            if self.update_x:
                w = torch.tanh(self.coord(m)) * mj[..., None]
                x = x + (rel * w).sum(2) / (mj.sum(2, keepdim=True) + 1e-6)
            return x, h

    class L4Net(nn.Module):
        def __init__(self):
            super().__init__()
            h = cfg["hidden"]
            self.k = cfg["k"]
            self.rbf = RBF(cfg.get("n_rbf", 16), cfg.get("r_max", 12.0))
            self.inp = nn.Sequential(nn.Linear(d_point, h), nn.SiLU(), nn.Linear(h, h))
            self.layers = nn.ModuleList([EGNNLayer(h, cfg.get("n_rbf", 16), cfg.get("update_x", True))
                                         for _ in range(cfg["layers"])])
            self.pool_att = nn.Sequential(nn.Linear(h, h), nn.SiLU(), nn.Linear(h, 1))
            self.d_n1 = d_n1 if cfg.get("concat_n1") else 0
            if self.d_n1:
                self.n1 = nn.Sequential(nn.Linear(self.d_n1, h), nn.LayerNorm(h), nn.GELU(),
                                        nn.Dropout(cfg.get("dropout", 0.1)))
            d_head = 2 * h + (h if self.d_n1 else 0)
            self.head = nn.Sequential(nn.Linear(d_head, 2 * h), nn.LayerNorm(2 * h), nn.GELU(),
                                      nn.Dropout(cfg.get("dropout", 0.1)), nn.Linear(2 * h, cfg["out_dim"]))

        def knn(self, x, mask):
            D = torch.cdist(x, x)
            D = D + (1.0 - mask[:, None, :]) * 1e6                  # padded points never neighbours
            eye = torch.eye(x.shape[1], device=x.device, dtype=torch.bool)[None]
            D = D.masked_fill(eye, 1e6)                              # no self loops
            k = min(self.k, x.shape[1] - 1)
            return D.topk(k, dim=-1, largest=False).indices

        def forward(self, x, feat, mask, vol_log=None, n1=None):
            """x (B,N,3), feat (B,N,F) (last column = log vol), mask (B,N) -> (B, out_dim) unit vectors."""
            x = x - (x * mask[..., None]).sum(1, keepdim=True) / mask.sum(1, keepdim=True)[..., None]
            h = self.inp(feat) * mask[..., None]
            for layer in self.layers:
                knn = self.knn(x.detach(), mask)
                x, h = layer(x, h, mask, knn, self.rbf)
            lv = feat[..., -1]
            w = torch.exp(lv) * mask
            wm = (w[..., None] * h).sum(1) / (w.sum(1, keepdim=True) + 1e-6)
            lg = self.pool_att(h).squeeze(-1) + lv
            lg = lg.masked_fill(mask <= 0, -1e9)
            att = (torch.softmax(lg, 1)[..., None] * h).sum(1)
            z = [att, wm]
            if self.d_n1:
                z.append(self.n1(n1))
            return F.normalize(self.head(torch.cat(z, -1)), dim=-1)

    return L4Net()


def random_rotations(B, generator=None, device="cpu"):
    """(B,3,3) uniformly random rotation matrices (QR of Gaussian matrices, det +1)."""
    import torch
    A = torch.randn(B, 3, 3, generator=generator, device=device)
    Q, R = torch.linalg.qr(A)
    Q = Q * torch.sign(torch.diagonal(R, dim1=1, dim2=2))[:, None, :]
    det = torch.det(Q)
    Q[:, :, 0] = Q[:, :, 0] * det[:, None]
    return Q


__all__ = ["L4_VERSION", "CAP", "fps", "site_points", "PointStore", "PointScaler", "feature_transform",
           "point_input", "pad_batch", "build_model", "random_rotations"]
