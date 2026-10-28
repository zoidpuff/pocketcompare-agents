"""Fingerprint tables and FAISS indices for the final method (used by ``pocketcompare.cli`` and the release scripts).

Fingerprint table (parquet): one row per pocket, metadata columns + ``fingerprint`` (fixed-size list of float32,
``dims`` = 384 for the final method).  The parquet schema metadata key ``pocketcompare`` holds a JSON record of the
method (name, config sha256, dims) so that tables from different methods are never mixed silently.

Normalisation: a final-method fingerprint is already the complete embedding -- each part z-scored with the
shipped BLiPS-train statistics, clipped, passed through the 3 seed heads, each head output L2-normalised, the three
unit vectors concatenated and divided by sqrt(3) -- so it has unit norm and the method's score is the plain inner
product (mean per-seed cosine).  Indices therefore use METRIC_INNER_PRODUCT on the vectors as stored; no further
z-scoring or normalisation is applied (``check_unit`` verifies the norm).  Zero rows (pocket not describable) are
never indexed.

Index directory (``build_index``): ``index.faiss``, ``meta.parquet`` (row i = FAISS id i), ``vectors.f16.npy``
(fp16 copies for exact re-ranking of a compressed index; 768 B/pocket), ``index.json``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

FP_COL = "fingerprint"
META_KEY = b"pocketcompare"


# ============================================================================================ tables
def method_record(m=None) -> dict:
    from . import method as _m
    from .provenance import sha256_file
    m = m or _m.default()
    return {"method": m.cfg["name"], "config": str(m.config_path.relative_to(_m.ROOT))
            if m.config_path.is_relative_to(_m.ROOT) else str(m.config_path),
            "config_sha256": sha256_file(m.config_path), "dims": int(m.dim), "metric": "inner_product"}


def write_table(path, meta: pd.DataFrame, V: np.ndarray, record: dict | None = None) -> None:
    """Write metadata + fingerprints (``fingerprint`` = fixed_size_list<float32>[d]) to parquet."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    V = np.ascontiguousarray(V, np.float32)
    assert len(meta) == len(V)
    t = pa.Table.from_pandas(meta.reset_index(drop=True), preserve_index=False)
    arr = pa.FixedSizeListArray.from_arrays(pa.array(V.reshape(-1), pa.float32()), V.shape[1]) if len(V) else \
        pa.array([], pa.list_(pa.float32(), V.shape[1] if V.ndim == 2 else 0))
    t = t.append_column(FP_COL, arr)
    md = dict(t.schema.metadata or {})
    md[META_KEY] = json.dumps(record or {}).encode()
    t = t.replace_schema_metadata(md)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, str(path), compression="zstd")


def read_table(path, columns=None) -> tuple[pd.DataFrame, np.ndarray, dict]:
    """(metadata DataFrame, (n, d) float32 fingerprints, method record) of a fingerprint parquet."""
    import pyarrow.parquet as pq
    t = pq.read_table(str(path), columns=None if columns is None else list(columns) + [FP_COL])
    rec = json.loads((t.schema.metadata or {}).get(META_KEY, b"{}") or b"{}")
    col = t.column(FP_COL).combine_chunks()
    n = len(col)
    if n:
        flat = col.flatten() if hasattr(col, "flatten") else col.values
        V = np.asarray(flat.to_numpy(zero_copy_only=False), np.float32).reshape(n, -1)
    else:
        V = np.zeros((0, int(rec.get("dims", 0))), np.float32)
    meta = t.drop([FP_COL]).to_pandas()
    return meta, V, rec


def read_tables(paths) -> tuple[pd.DataFrame, np.ndarray, dict]:
    metas, Vs, rec = [], [], None
    for p in paths:
        m, V, r = read_table(p)
        if rec is not None and r.get("config_sha256") != rec.get("config_sha256"):
            raise ValueError(f"{p}: fingerprints of a different method ({r.get('method')}) than the first file")
        rec = rec or r
        metas.append(m)
        Vs.append(V)
    return pd.concat(metas, ignore_index=True), np.vstack(Vs), rec or {}


def check_unit(V, tol: float = 1e-3) -> np.ndarray:
    """Boolean mask of usable rows (norm > 0); raises if a non-zero row is not unit-norm."""
    n = np.linalg.norm(V, axis=1)
    ok = n > 0
    bad = ok & (np.abs(n - 1) > tol)
    if bad.any():
        raise ValueError(f"{int(bad.sum())} fingerprints are not unit-norm (max |norm-1| "
                         f"{np.abs(n[bad] - 1).max():.3g}): not final-method vectors?")
    return ok


# ============================================================================================ index
def ivfpq_factory(d: int, nlist: int, m: int = 64, bits: int = 8, opq: bool = True) -> str:
    pq = f"PQ{m}" + (f"x{bits}" if bits != 8 else "")
    return (f"OPQ{m}_{d}," if opq else "") + f"IVF{nlist},{pq}"


def auto_nlist(n: int) -> int:
    """~4 sqrt(n), power of two, in [1, 65536], and at least 39 training points per list."""
    k = int(2 ** np.round(np.log2(max(1.0, 4 * np.sqrt(n)))))
    while k > 1 and n < 39 * k:
        k //= 2
    return int(min(max(k, 1), 65536))


def build_index(V, meta: pd.DataFrame, out_dir, kind: str = "flat", nlist: int | None = None, m: int = 64,
                bits: int = 8, opq: bool = True, n_train: int = 100_000, seed: int = 0, record: dict | None = None,
                save_vectors: bool = True, threads: int | None = None) -> dict:
    """Build and save an index over unit fingerprints ``V`` (zero rows dropped).  ``kind``: ``flat`` (exact
    IndexFlatIP) or ``ivfpq`` (``OPQ{m}_{d},IVF{nlist},PQ{m}``: m-byte codes; trained on ``n_train`` random rows).
    Returns the index.json record."""
    import faiss
    if threads:
        faiss.omp_set_num_threads(int(threads))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    V = np.ascontiguousarray(V, np.float32)
    ok = check_unit(V)
    V, meta = V[ok], meta[ok].reset_index(drop=True)
    n, d = V.shape
    t0 = time.perf_counter()
    info = {"kind": kind, "n": int(n), "dims": int(d), "n_dropped_zero": int((~ok).sum()), "metric": "inner_product",
            "normalisation": "none applied: final-method fingerprints are unit-norm embeddings; score = inner product",
            "method": record or {}}
    if kind == "flat":
        ix = faiss.IndexFlatIP(d)
        ix.add(V)
        info["factory"] = "Flat"
    elif kind == "ivfpq":
        nlist = int(nlist or auto_nlist(n))
        if n < 2 ** bits:
            raise ValueError(f"{n} vectors < 2^{bits} PQ centroids: use --kind flat (or fewer --pq-bits)")
        if d % m:
            raise ValueError(f"dims {d} not divisible by PQ m={m}")
        fac = ivfpq_factory(d, nlist, m, bits, opq)
        ix = faiss.index_factory(d, fac, faiss.METRIC_INNER_PRODUCT)
        rng = np.random.default_rng(seed)
        tr = V[rng.choice(n, min(n_train, n), replace=False)] if n > n_train else V
        ta = time.perf_counter()
        ix.train(tr)
        info["train_s"] = time.perf_counter() - ta
        ix.add(V)
        faiss.extract_index_ivf(ix).nprobe = min(64, nlist)
        info.update(factory=fac, nlist=nlist, pq_m=m, pq_bits=bits, opq=opq, n_train=int(len(tr)), seed=seed,
                    default_nprobe=min(64, nlist), code_bytes=m * bits // 8)
    else:
        raise ValueError(f"kind must be 'flat' or 'ivfpq', not {kind!r}")
    info["build_s"] = time.perf_counter() - t0
    faiss.write_index(ix, str(out / "index.faiss"))
    meta.to_parquet(out / "meta.parquet", index=False)
    if save_vectors:
        np.save(out / "vectors.f16.npy", V.astype(np.float16))
    info["bytes"] = {f.name: f.stat().st_size for f in sorted(out.iterdir()) if f.is_file() and f.name != "index.json"}
    info["index_bytes_per_pocket"] = (out / "index.faiss").stat().st_size / max(n, 1)
    info["faiss_version"] = faiss.__version__
    (out / "index.json").write_text(json.dumps(info, indent=1))
    return info


class Index:
    """A saved index directory.  ``search(Q, k)`` -> (scores, ids) with exact re-ranking of a compressed index."""

    def __init__(self, path, nprobe: int | None = None, load_vectors: bool = True):
        import faiss
        self.path = Path(path)
        self.info = json.loads((self.path / "index.json").read_text())
        self.index = faiss.read_index(str(self.path / "index.faiss"))
        self.meta = pd.read_parquet(self.path / "meta.parquet")
        self.compressed = self.info["kind"] != "flat"
        if self.compressed:
            faiss.extract_index_ivf(self.index).nprobe = int(nprobe or self.info.get("default_nprobe", 64))
        vf = self.path / "vectors.f16.npy"
        self.vectors = np.load(vf, mmap_mode="r") if (load_vectors and vf.exists()) else None

    @property
    def dims(self) -> int:
        return int(self.info["dims"])

    def search(self, Q, k: int = 10, rerank: int = 100) -> tuple[np.ndarray, np.ndarray]:
        """Top-``k`` (scores, ids) per query row.  Flat: exact.  Compressed: PQ shortlist of ``max(k, rerank)``
        re-scored exactly against the fp16 vectors (``rerank=0`` or no vectors: PQ scores as is).  ids -1 =
        fewer than k hits."""
        Q = np.ascontiguousarray(np.atleast_2d(Q), np.float32)
        if Q.shape[1] != self.dims:
            raise ValueError(f"query dims {Q.shape[1]} != index dims {self.dims}")
        if not self.compressed or not rerank or self.vectors is None:
            return self.index.search(Q, k)
        kk = max(k, rerank)
        _, I = self.index.search(Q, kk)
        S = np.empty(I.shape, np.float32)
        for s in range(0, len(Q), 1024):              # exact re-score of the shortlist, chunked
            Ic = I[s:s + 1024]
            Vc = np.asarray(self.vectors[np.clip(Ic, 0, None).reshape(-1)], np.float32).reshape(*Ic.shape, -1)
            S[s:s + 1024] = np.einsum("qkd,qd->qk", Vc, Q[s:s + 1024])
        S[I < 0] = -np.inf
        o = np.argsort(-S, 1, kind="stable")[:, :k]
        D, I = np.take_along_axis(S, o, 1), np.take_along_axis(I, o, 1)
        I[~np.isfinite(D)] = -1
        return D, I


# ============================================================================================ evaluation helpers
def recall_at_k(I_approx, I_exact, k: int = 10) -> float:
    return float(np.mean([len(set(a[:k]) & set(b[:k])) / k for a, b in zip(I_approx, I_exact)]))


def drop_self(D, I, k, qids):
    """Remove each query's own id from its result row (else the last column); keep the first k."""
    n = len(I)
    keep = I != np.asarray(qids)[:, None]
    keep[keep.all(1), -1] = False
    return D[keep].reshape(n, -1)[:, :k], I[keep].reshape(n, -1)[:, :k]


def hubness(I_k, n) -> dict:
    """In-degree statistics of a top-k graph (self excluded)."""
    from scipy.stats import skew
    indeg = np.bincount(np.asarray(I_k).reshape(-1)[np.asarray(I_k).reshape(-1) >= 0], minlength=n)
    s = np.sort(indeg)[::-1]
    return {"k": int(I_k.shape[1]), "skewness": float(skew(indeg)), "max": int(s[0]),
            "p99": float(np.percentile(indeg, 99)), "median": float(np.median(indeg)),
            "frac_zero": float((indeg == 0).mean()), "top1pct_share": float(s[:max(1, n // 100)].sum() / s.sum())}


__all__ = ["FP_COL", "method_record", "write_table", "read_table", "read_tables", "check_unit", "ivfpq_factory",
           "auto_nlist", "build_index", "Index", "recall_at_k", "drop_self", "hubness"]
