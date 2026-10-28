#!/usr/bin/env python
"""FAISS index over the fingerprints of selected tiers, built without loading all vectors.

    python afdb/build_index.py --tiers 1 --kind flat  -o $OUT_ROOT/index/tier1_flat       # exact, small tiers
    python afdb/build_index.py --tiers 1,2,3 --kind ivfpq -o $OUT_ROOT/index/all_ivfpq   # OPQ + IVF-PQ
    pocketcompare search query.parquet $OUT_ROOT/index/tier1_flat -k 10                  # search it

``ivfpq`` = ``OPQ{m}_{d},IVF{nlist},PQ{m}`` (inner product; m-byte codes): trained on a uniform random sample of
``--train`` fingerprints (drawn file by file), then every pocket file is added in turn. ``flat`` = exact
``IndexFlatIP`` (4 x 384 B per pocket in RAM: 10 M pockets = 15 GB). Fingerprints are stored as float16 and are
unit vectors already: no normalisation is applied.

Output directory (readable by ``pocketcompare search`` / ``pocketcompare.fpindex.Index``): ``index.faiss``,
``meta.parquet`` (row i = FAISS id i: tier, unit_id, row in the unit file, pocket_id, accession, taxid,
burrow_score, plddt_mean, source (derived from the tier for files written before it existed); ``--compact-ids`` keeps only tier/unit_id/row), ``index.json``, and with
``--save-vectors`` ``vectors.f16.npy`` (fp16 copies for exact re-ranking, 768 B/pocket, written as a memmap).

Memory (``ivfpq``, m = 64): ~ (64 + 8) B per pocket for codes + ids, plus nlist x 384 x 4 B of centroids and the
training sample (n_train x 1.5 kB): 10^9 pockets -> ~75 GB index + ~4 GB training, i.e. fits a 192 GB node; the
index file is ~70 GB. meta.parquet with names is ~40 B/pocket on disk (use --compact-ids at 10^9 if needed; the
full metadata stays in the unit files). Training IVF65536 on 2.6 M vectors takes ~20-60 min on 32 CPU threads.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from afdb_common import DIM, fill_source, out_root  # noqa: E402

META_COLS = ["pocket_id", "accession", "taxid", "burrow_score", "plddt_mean"]


def log(*a):
    print(f"[build_index {time.strftime('%H:%M:%S')}]", *a, file=sys.stderr, flush=True)


def fp_matrix(t: pa.Table) -> np.ndarray:
    col = t.column("fingerprint").combine_chunks()
    if len(col) == 0:
        return np.zeros((0, DIM), np.float32)
    return np.asarray(col.flatten().to_numpy(zero_copy_only=False), np.float32).reshape(len(col), -1)


def files_of(root: Path, tiers) -> list[Path]:
    fs = []
    for t in tiers:
        fs += sorted((root / "pockets" / f"tier{t}").glob("[0-9]*.parquet"))
    return fs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--tiers", default="1")
    ap.add_argument("-o", "--out", required=True, help="index directory")
    ap.add_argument("--kind", choices=["flat", "ivfpq"], default="ivfpq")
    ap.add_argument("--nlist", type=int, default=None, help="IVF lists (default ~4 sqrt(n), power of 2, <= 65536)")
    ap.add_argument("--pq-m", type=int, default=64)
    ap.add_argument("--no-opq", action="store_true")
    ap.add_argument("--train", type=int, default=None, help="training sample (default max(64 nlist, 100k), <= 5 M)")
    ap.add_argument("--min-score", type=float, default=None, help="index only pockets with burrow_score >= this")
    ap.add_argument("--save-vectors", action="store_true", help="also write vectors.f16.npy for exact re-ranking")
    ap.add_argument("--compact-ids", action="store_true")
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    import faiss
    if a.threads:
        faiss.omp_set_num_threads(a.threads)
    from pocketcompare.fpindex import auto_nlist, ivfpq_factory
    root = out_root(a.out_root)
    tiers = [int(t) for t in a.tiers.split(",")]
    files = files_of(root, tiers)
    if not files:
        raise SystemExit(f"no pocket files for tiers {tiers} under {root / 'pockets'}")
    counts = np.array([pq.ParquetFile(f).metadata.num_rows for f in files], np.int64)
    rec = json.loads((pq.ParquetFile(files[0]).schema_arrow.metadata or {}).get(b"pocketcompare", b"{}"))
    n_rows = int(counts.sum())
    log(f"{len(files)} pocket files, {n_rows:,} pockets (tiers {tiers})")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    t0 = time.time()
    info = {"kind": a.kind, "dims": DIM, "metric": "inner_product", "tiers": tiers, "source_root": str(root),
            "n_files": len(files), "min_score": a.min_score, "method": rec,
            "normalisation": "none applied: fingerprints are unit-norm embeddings (stored fp16); score = inner product"}
    if a.kind == "flat":
        ix = faiss.IndexFlatIP(DIM)
        info["factory"] = "Flat"
    else:
        nlist = int(a.nlist or min(65536, auto_nlist(n_rows)))
        n_train = int(min(n_rows, a.train or min(5_000_000, max(64 * nlist, 100_000))))
        if n_train < 256:
            raise SystemExit(f"{n_train} training vectors < 256 PQ centroids: use --kind flat")
        fac = ivfpq_factory(DIM, nlist, a.pq_m, 8, not a.no_opq)
        ix = faiss.index_factory(DIM, fac, faiss.METRIC_INNER_PRODUCT)
        # uniform sample without loading everything: choose global row numbers, then read file by file
        pick = np.sort(rng.choice(n_rows, n_train, replace=False))
        starts = np.concatenate([[0], np.cumsum(counts)])
        T = np.empty((n_train, DIM), np.float32)
        k = 0
        for i, f in enumerate(files):
            sel = pick[(pick >= starts[i]) & (pick < starts[i + 1])] - starts[i]
            if len(sel):
                V = fp_matrix(pq.read_table(f, columns=["fingerprint"]))
                T[k:k + len(sel)] = V[sel]
                k += len(sel)
        T = T[:k]
        if a.min_score is not None:
            log("note: the training sample is drawn before the --min-score filter")
        log(f"training {fac} on {len(T):,} vectors")
        ta = time.time()
        ix.train(T)
        info.update(factory=fac, nlist=nlist, pq_m=a.pq_m, pq_bits=8, opq=not a.no_opq, n_train=int(len(T)),
                    train_s=round(time.time() - ta, 1), seed=a.seed, default_nprobe=min(64, nlist), code_bytes=a.pq_m)
        del T
    # ---- add file by file; meta.parquet streamed with a ParquetWriter
    n_added = n_zero = 0
    vec = None
    if a.save_vectors:
        vec = np.lib.format.open_memmap(out / "vectors.f16.tmp.npy", mode="w+", dtype=np.float16,
                                        shape=(n_rows, DIM))
    writer = None
    for i, f in enumerate(files):
        cols = ["tier", "unit_id", "fingerprint"] + ([] if a.compact_ids else META_COLS)
        if a.min_score is not None and "burrow_score" not in cols:
            cols.append("burrow_score")
        have = set(pq.read_schema(f).names)
        t = pq.read_table(f, columns=[c for c in cols + ["source"] if c in have])
        if not a.compact_ids:
            t = fill_source(t)                   # files of the first tier-1/2 run have no `source` column
        V = fp_matrix(t)
        nrm = np.linalg.norm(V, axis=1)
        keep = nrm > 0
        if a.min_score is not None:
            keep &= t.column("burrow_score").to_numpy() >= a.min_score
        n_zero += int((nrm == 0).sum())
        if (np.abs(nrm[keep] - 1) > 2e-3).any():
            raise SystemExit(f"{f}: fingerprints are not unit-norm")
        sel = np.flatnonzero(keep)
        if not len(sel):
            continue
        ix.add(np.ascontiguousarray(V[sel]))
        if vec is not None:
            vec[n_added:n_added + len(sel)] = V[sel].astype(np.float16)
        m = t.drop(["fingerprint"]).take(pa.array(sel))
        m = m.append_column("row", pa.array(sel.astype(np.int32)))
        if a.compact_ids:
            m = m.select(["tier", "unit_id", "row"])
        elif "source" in m.column_names:
            m = m.drop(["source"]).append_column("source", m.column("source"))   # same column order in every file
        if writer is None:
            writer = pq.ParquetWriter(str(out / "meta.parquet.tmp"), m.schema, compression="zstd")
        writer.write_table(m.cast(writer.schema))
        n_added += len(sel)
        if (i + 1) % 200 == 0:
            log(f"added {i + 1}/{len(files)} files, {n_added:,} pockets ({time.time() - t0:.0f} s)")
    if writer is not None:
        writer.close()
        (out / "meta.parquet.tmp").replace(out / "meta.parquet")
    if vec is not None:
        vec.flush()
        del vec
        if n_added < n_rows:                    # trim the memmap to the pockets actually indexed
            v = np.load(out / "vectors.f16.tmp.npy", mmap_mode="r")[:n_added]
            np.save(out / "vectors.f16.npy", v)
            (out / "vectors.f16.tmp.npy").unlink()
        else:
            (out / "vectors.f16.tmp.npy").replace(out / "vectors.f16.npy")
    if a.kind == "ivfpq":
        faiss.extract_index_ivf(ix).nprobe = info["default_nprobe"]
    faiss.write_index(ix, str(out / "index.faiss"))
    info.update(n=int(n_added), n_dropped_zero=n_zero, n_dropped_score=int(n_rows - n_added - n_zero),
                build_s=round(time.time() - t0, 1), faiss_version=faiss.__version__)
    info["bytes"] = {p.name: p.stat().st_size for p in sorted(out.iterdir()) if p.is_file() and p.suffix != ".json"}
    info["index_bytes_per_pocket"] = (out / "index.faiss").stat().st_size / max(n_added, 1)
    (out / "index.json").write_text(json.dumps(info, indent=1))
    log(f"{info['factory']} index of {n_added:,} pockets -> {out} ({info['build_s']} s, "
        f"{info['index_bytes_per_pocket']:.0f} B/pocket)")


if __name__ == "__main__":
    main()
