"""Independent verifier helpers (do NOT import scripts/final_eval.py or pocketcompare.evaluate)."""
import getpass
import hashlib
import os
import socket
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.metrics import roc_auc_score

ROOT = Path("/cluster/project/beltrao/gmagnus/pocket_compare")
LOG = ROOT / "results/verify/unseal_log.tsv"


def read_sealed(name, purpose):
    p = ROOT / "data/sealed" / name
    before = oct(os.stat(p).st_mode & 0o777)
    t = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    os.chmod(p, 0o400)
    try:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        df = pd.read_parquet(p)
    finally:
        os.chmod(p, 0)
    after = oct(os.stat(p).st_mode & 0o777)
    new = not LOG.exists()
    with open(LOG, "a") as fh:
        if new:
            fh.write("time\tfile\tsha256\tmode_before\tmode_after\trows\tpurpose\tuser\thost\tpid\n")
        fh.write(f"{t}\tdata/sealed/{name}\t{h}\t{before}\t{after}\t{len(df)}\t{purpose}\t{getpass.getuser()}\t"
                 f"{socket.gethostname()}\t{os.getpid()}\n")
    return df, h


def components_from_labels(*label_arrays):
    """Connected components of pockets linked when they share any label (labels of different arrays distinct)."""
    n = len(label_arrays[0])
    rows, cols, off = [], [], n
    for k, lab in enumerate(label_arrays):
        codes, uniq = pd.factorize(pd.Series(lab).astype(str).radd(f"{k}:"))
        rows.append(np.arange(n))
        cols.append(codes + off)
        off += len(uniq)
    r = np.concatenate(rows)
    c = np.concatenate(cols)
    A = coo_matrix((np.ones(len(r)), (r, c)), shape=(off, off))
    _, lab = connected_components(A, directed=False)
    return pd.factorize(lab[:n])[0]


def unit_weights(counts, ua, ub):
    ca, cb = counts[ua], counts[ub]
    return np.where(ua == ub, ca, ca * cb).astype(float)


def boot_paired(y, sa, sb, ua, ub, B=2000, seed=12345):
    """Vertex bootstrap over units: unit multiplicities c ~ Multinomial(n_units); pair weight c_u (same unit)
    or c_u * c_v.  Returns dict with point delta, percentile CI, one-sided p (H0 delta <= 0), SE."""
    y = np.asarray(y).astype(int)
    units = np.unique(np.concatenate([ua, ub]))
    remap = {u: i for i, u in enumerate(units)}
    ia = np.array([remap[u] for u in ua])
    ib = np.array([remap[u] for u in ub])
    nu = len(units)
    rng = np.random.default_rng(seed)
    a0, b0 = roc_auc_score(y, sa), roc_auc_score(y, sb)
    ds = []
    ndeg = 0
    for _ in range(B):
        c = rng.multinomial(nu, np.full(nu, 1.0 / nu))
        w = unit_weights(c, ia, ib)
        m = w > 0
        if y[m].min() == y[m].max():
            ndeg += 1
            continue
        ds.append(roc_auc_score(y[m], sa[m], sample_weight=w[m]) - roc_auc_score(y[m], sb[m], sample_weight=w[m]))
    ds = np.asarray(ds)
    return {"auc_a": a0, "auc_b": b0, "delta": a0 - b0, "ci_low": float(np.quantile(ds, 0.025)),
            "ci_high": float(np.quantile(ds, 0.975)), "lower95": float(np.quantile(ds, 0.05)),
            "se": float(ds.std(ddof=1)), "p": float((1 + (ds <= 0).sum()) / (len(ds) + 1)), "n_units": nu,
            "n_degenerate": ndeg, "boot": ds}


def zcos_embed(M, pool):
    """z-score on the pool rows (population std, constant dims -> 0), L2 normalise; rows outside pool -> NaN."""
    M = np.asarray(M, np.float64)
    av = pool & np.isfinite(M).all(1)
    X = M[av]
    mu, sd = X.mean(0), X.std(0)
    ok = sd > 1e-8 * np.maximum(1.0, np.abs(mu))
    Z = np.zeros_like(X)
    Z[:, ok] = (X[:, ok] - mu[ok]) / sd[ok]
    n = np.linalg.norm(Z, axis=1, keepdims=True)
    Z = np.where(n > 0, Z / np.where(n > 0, n, 1), 0)
    E = np.full(M.shape, np.nan)
    E[av] = Z
    return E


def l2n(Z):
    n = np.linalg.norm(Z, axis=1, keepdims=True)
    return np.where(n > 0, Z / np.where(n > 0, n, 1), 0)


def pair_cos(E, ia, ib):
    return np.einsum("nd,nd->n", E[ia], E[ib])


# ------------------------------------------------------------------ final method, own numpy re-implementation
import json as _json


def _desc_dir(ds):
    d = ROOT / "data/processed/descriptors"
    return d / "tough_m1/defrob" if ds == "tough_m1" else d / ds / "a1r"


def final_seed_embeddings(ds, loc, pocket_ids):
    """Per-seed 128-d unit embeddings (list of 3 arrays) + availability, from stored part descriptors."""
    stats = _json.load(open(ROOT / "results/models/a4b/n1_linear/input_stats.json"))
    heads = [dict(np.load(ROOT / f"results/models/a4b/n1_linear/seed{s}.npz")) for s in (0, 1, 2)]
    ids = pd.read_parquet(_desc_dir(ds) / "ids.parquet")
    r = pd.Series(np.arange(len(ids)), index=ids.pocket_id).reindex(list(pocket_ids)).to_numpy()
    have = ~pd.isna(r)
    ri = np.where(have, r, 0).astype(int)
    sph = np.load(_desc_dir(ds) / f"{loc}_sph8.npz")
    base = np.load(_desc_dir(ds) / f"{loc}_base.npz")
    mats = []
    for src in ("a1", "env"):
        M = sph[src][ri].astype(np.float64)
        Bm = base[src][ri].astype(np.float64)
        fb = ~np.isfinite(M).any(1) & np.isfinite(Bm).any(1)
        M[fb] = Bm[fb]
        M[~have] = np.nan
        mats.append(M)
    Z = []
    for k, M in enumerate(mats):
        mu, sd = np.asarray(stats["mean"][k]), np.asarray(stats["std"][k])
        z = np.zeros_like(M)
        g = sd > 0
        z[:, g] = (M[:, g] - mu[g]) / sd[g]
        Z.append(np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0))
    X = np.clip(np.concatenate(Z, 1), -5, 5)
    per_seed = [l2n(X @ hd["w2"].astype(np.float64).T + hd["b2"].astype(np.float64)) for hd in heads]
    avail = np.ones(len(X), bool)
    for M in mats:
        avail &= np.isfinite(M).any(1)
    return per_seed, avail


def final_scores(ds, loc, pocket_ids, pool, ia, ib):
    per_seed, avail = final_seed_embeddings(ds, loc, pocket_ids)
    av = avail & pool
    s = np.mean([pair_cos(E, ia, ib) for E in per_seed], 0)
    s[~(av[ia] & av[ib])] = np.nan
    return s


def desc_matrix(ds, stem, pocket_ids, ids_file=None):
    d = ROOT / "data/processed/descriptors" / ds
    A = np.load(d / f"{stem}.npy", mmap_mode="r")
    ii = pd.read_parquet(d / (ids_file or f"{stem}.ids.parquet"), columns=["pocket_id"]).pocket_id
    r = pd.Series(np.arange(len(ii)), index=ii.to_numpy()).reindex(list(pocket_ids)).to_numpy()
    M = np.full((len(r), A.shape[1]), np.nan)
    g = ~pd.isna(r)
    M[g] = np.asarray(A[r[g].astype(int)], np.float64)
    return M


def boot_single(y, s, ua, ub, B=2000, seed=1):
    """Vertex bootstrap of one AUC (for spot checks): returns point, 2.5/97.5 percentiles."""
    y = np.asarray(y).astype(int)
    units, inv = np.unique(np.concatenate([ua, ub]), return_inverse=True)
    ia, ib = inv[:len(ua)], inv[len(ua):]
    nu = len(units)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(B):
        c = rng.multinomial(nu, np.full(nu, 1.0 / nu))
        w = unit_weights(c, ia, ib)
        m = w > 0
        if y[m].min() == y[m].max():
            continue
        out.append(roc_auc_score(y[m], s[m], sample_weight=w[m]))
    return roc_auc_score(y, s), float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))
