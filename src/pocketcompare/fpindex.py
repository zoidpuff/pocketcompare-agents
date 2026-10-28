"""Fingerprint tables (parquet) and FAISS indices (``pip install pocketcompare[search]`` for ``faiss-cpu``).

Fingerprint table: one row per pocket, metadata columns + ``fingerprint`` (fixed-size list of float32, 384 for the
frozen method) and, with ``describe --n1``, ``n1`` (the raw 627-d head input).  The parquet schema metadata key
``pocketcompare`` holds a JSON record of the method (name, config sha256, dims); tables of different methods
(name or dims) are never mixed silently.

Normalisation: a fingerprint is already the complete embedding (z-scored parts -> 3 seed heads -> per-head unit
vectors concatenated / sqrt(3)), so it has unit norm and the score is the plain inner product.  Indices therefore
use METRIC_INNER_PRODUCT on the vectors as stored; no further normalisation is applied (``check_unit`` verifies
the norm).  Zero rows (pocket not describable) are never indexed.

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
N1_COL = "n1"
META_KEY = b"pocketcompare"


def _faiss():
    try:
        import faiss
    except ImportError as e:  # pragma: no cover
        raise ImportError("FAISS is needed for index/search: pip install 'pocketcompare[search]' "
                          "(or faiss-cpu / faiss-gpu)") from e
    return faiss


# ============================================================================================ tables
def method_record(m=None) -> dict:
    from . import __version__
    from . import method as _m
    m = m or _m.default()
    return {"method": m.cfg["name"], "config": m.config_path.name, "config_sha256": _m._sha256(m.config_path),
            "dims": int(m.dim), "metric": "inner_product", "pocketcompare_version": __version__}


def _list_array(M):
    import pyarrow as pa
    M = np.ascontiguousarray(M, np.float32)
    if len(M):
        return pa.FixedSizeListArray.from_arrays(pa.array(M.reshape(-1), pa.float32()), M.shape[1])
    return pa.array([], pa.list_(pa.float32(), M.shape[1] if M.ndim == 2 else 0))


def write_table(path, meta: pd.DataFrame, V: np.ndarray, record: dict | None = None, n1: np.ndarray | None = None
                ) -> None:
    """Write metadata + fingerprints (``fingerprint`` = fixed_size_list<float32>[d]) [+ raw N1] to parquet."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    assert len(meta) == len(V)
    t = pa.Table.from_pandas(meta.reset_index(drop=True), preserve_index=False)
    t = t.append_column(FP_COL, _list_array(V))
    if n1 is not None:
        assert len(n1) == len(V)
        t = t.append_column(N1_COL, _list_array(n1))
    md = dict(t.schema.metadata or {})
    md[META_KEY] = json.dumps(record or {}).encode()
    t = t.replace_schema_metadata(md)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, str(path), compression="zstd")


def _to_matrix(col, n_hint=0) -> np.ndarray:
    col = col.combine_chunks()
    n = len(col)
    if not n:
        return np.zeros((0, n_hint), np.float32)
    flat = col.flatten() if hasattr(col, "flatten") else col.values
    return np.asarray(flat.to_numpy(zero_copy_only=False), np.float32).reshape(n, -1)


def read_table(path, columns=None, with_n1: bool = False):
    """(metadata DataFrame, (n, d) float32 fingerprints, method record) of a fingerprint parquet; with
    ``with_n1`` also the (n, 627) raw N1 matrix (requires a table written by ``describe --n1``)."""
    import pyarrow.parquet as pq
    extra = [FP_COL] + ([N1_COL] if with_n1 else [])
    t = pq.read_table(str(path), columns=None if columns is None else list(columns) + extra)
    rec = json.loads((t.schema.metadata or {}).get(META_KEY, b"{}") or b"{}")
    V = _to_matrix(t.column(FP_COL), int(rec.get("dims", 0)))
    N = None
    if with_n1:
        if N1_COL not in t.column_names:
            raise ValueError(f"{path}: no '{N1_COL}' column (describe with --n1)")
        N = _to_matrix(t.column(N1_COL), 627)
    meta = t.drop([c for c in (FP_COL, N1_COL) if c in t.column_names]).to_pandas()
    return (meta, V, rec, N) if with_n1 else (meta, V, rec)


def read_tables(paths) -> tuple[pd.DataFrame, np.ndarray, dict]:
    metas, Vs, rec = [], [], None
    for p in paths:
        m, V, r = read_table(p)
        if rec is not None and (r.get("method"), r.get("dims")) != (rec.get("method"), rec.get("dims")):
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
                         f"{np.abs(n[bad] - 1).max():.3g}): not pocketcompare fingerprints?")
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
    faiss = _faiss()
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
            "normalisation": "none applied: fingerprints are unit-norm embeddings; score = inner product",
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
        faiss = _faiss()
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


def recall_at_k(I_approx, I_exact, k: int = 10) -> float:
    return float(np.mean([len(set(a[:k]) & set(b[:k])) / k for a, b in zip(I_approx, I_exact)]))


__all__ = ["FP_COL", "N1_COL", "method_record", "write_table", "read_table", "read_tables", "check_unit",
           "ivfpq_factory", "auto_nlist", "build_index", "Index", "recall_at_k"]
