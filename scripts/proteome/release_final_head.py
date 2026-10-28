#!/usr/bin/env python
"""Human-proteome fingerprint release with the FINAL method head (A4b:n1_linear) + FAISS indices + evaluation.

    CUDA_VISIBLE_DEVICES=1 python scripts/proteome/release_final_head.py [--n-crosscheck 40]

Inputs (no BURROW re-run): the stored raw N1 descriptors of the proteome demo, data/processed/proteome_human/index/
{a1_raw,env_raw}.npy + pockets.parquet (116,246 fragment-deduplicated merged region-rule pockets >= 10 points of
AFDB v6 human, AF mode; scripts/proteome/run_proteome.py + index_search.py).  The frozen head
(configs/final_method.yaml via ``pocketcompare.method.Method.embed``: BLiPS-train z-scoring, clip +-5, 3 seed heads)
maps them to 384-d unit fingerprints.

Check: cross-check against the public API -- ``method.describe_all`` re-run from the AF model files (fast CPU BURROW,
float64 descriptors) for ``--n-crosscheck`` random released models must reproduce the released vectors (which were
embedded from float32-stored raw parts).

Outputs data/processed/release/human_afdb_v6/: fingerprints.parquet (metadata + fingerprint), index_flat/
(IndexFlatIP), index_opq_ivfpq/ (OPQ64_384,IVF1024,PQ64 + fp16 vectors for re-rank), SHA256SUMS; results/release/
human_afdb_v6.json (+ .prov.json): recall@10 of PQ vs exact (10k queries, self excluded, nprobe sweep, with/without
exact re-rank of the top-100), latency, storage, hubness (raw / CSLS with database radii) and the overlap of the
final-head neighbours with the demo's N1 neighbours.
"""
from __future__ import annotations

import os

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")

import argparse  # noqa: E402
import glob  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare import fpindex as FX  # noqa: E402
from pocketcompare import method as MM  # noqa: E402

P = ROOT / "data/processed/proteome_human"
IX = P / "index"
REL = ROOT / "data/processed/release/human_afdb_v6"
RES = ROOT / "results/release/human_afdb_v6.json"
TAR = "/cluster/work/beltrao/shared/alphafold/v6/UP000005640_9606_HUMAN_v6.tar"
SEED = 0


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def crosscheck(m, meta, E, n, seed=SEED) -> dict:
    """``method.describe_all`` from the model file (fast CPU BURROW) vs the released vectors."""
    from pocketcompare import pockets_fast as pf
    mem = pd.read_parquet(P / "members.parquet").set_index("stem")
    rng = np.random.default_rng(seed)
    stems = rng.choice(sorted(set(meta.structure_stem)), n, replace=False)
    pos = pd.Series(np.arange(len(meta)), index=meta.pocket_id)
    diffs, n_rel, n_api, n_matched, extra_fb, extra_dup = [], 0, 0, 0, 0, 0
    with open(TAR, "rb") as fh, tempfile.TemporaryDirectory() as td:
        for s in stems:
            r = mem.loc[s]
            fh.seek(int(r.offset_data))
            f = Path(td) / f"{s}.pdb"
            f.write_bytes(gzip.decompress(fh.read(int(r["size"]))))
            fs = pf.featurize_fast_cpu(f, s, af_mode=True)
            V, info = m.describe_all(fs)
            mine = meta.structure_stem == s
            n_rel += int(mine.sum())
            n_api += len(info)
            for k, v, fb in zip(info.merged_index, V, info.sph8_fallback):
                pid = f"{s}:m{k}"
                if pid in pos.index:
                    diffs.append(float(np.abs(E[pos[pid]] - v).max()))
                    n_matched += 1
                elif fb:
                    extra_fb += 1           # empty sph8: the demo dropped it, the API describes it (SPH_FALLBACK)
                else:
                    extra_dup += 1          # fragment duplicate removed from the release
    return {"n_models": int(n), "n_release_pockets": n_rel, "n_api_pockets": n_api, "n_matched": n_matched,
            "all_release_pockets_reproduced": n_matched == n_rel, "api_extra_empty_sph8": extra_fb,
            "api_extra_other(fragment_dedup)": extra_dup, "max_abs_diff": float(max(diffs)) if diffs else None,
            "median_max_abs_diff": float(np.median(diffs)) if diffs else None}


def exact_knn_gpu(E, k):
    import faiss
    res = faiss.StandardGpuResources()
    ix = faiss.GpuIndexFlatIP(res, E.shape[1])
    ix.add(E)
    t0 = time.perf_counter()
    Ds, Is = [], []
    for s in range(0, len(E), 16384):
        D_, I_ = ix.search(E[s:s + 16384], k + 1)
        Ds.append(D_)
        Is.append(I_)
    t = time.perf_counter() - t0
    D_, I_ = FX.drop_self(np.concatenate(Ds), np.concatenate(Is), k, np.arange(len(E)))
    return D_, I_, t


def latency(search, Q, n=300):
    search(Q[:5])
    t = []
    for i in range(n):
        t0 = time.perf_counter()
        search(Q[i:i + 1])
        t.append(time.perf_counter() - t0)
    return {"median_ms": 1e3 * float(np.median(t)), "p90_ms": 1e3 * float(np.percentile(t, 90)), "n": n}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    import faiss
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-crosscheck", type=int, default=40)
    ap.add_argument("--n-recall", type=int, default=10000)
    ap.add_argument("--nlist", type=int, default=1024)
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()
    t_start = time.time()
    rng = np.random.default_rng(SEED)
    m = MM.Method()
    rep: dict = {"method": FX.method_record(m), "faiss_version": faiss.__version__}

    # ---- 1. embed the stored N1 parts with the final head
    pk = pd.read_parquet(IX / "pockets.parquet")
    a1 = np.load(IX / "a1_raw.npy")
    env = np.load(IX / "env_raw.npy")
    assert len(pk) == len(a1) == len(env) and (pk.dup_of < 0).all()
    t0 = time.perf_counter()
    E = m.embed([a1.astype(np.float64), env.astype(np.float64)])
    rep["embed"] = {"n": len(E), "wall_s": time.perf_counter() - t0, "n_zero": int((np.linalg.norm(E, axis=1) == 0).sum()),
                    "input": "stored raw A1(sph8) + env(sph8) (float32) of the proteome demo; no BURROW re-run"}
    log("embedded", E.shape)

    # ---- 2. release table
    structs = pd.concat([pd.read_parquet(f) for f in glob.glob(str(P / "run_gpu/shards/*.structs.parquet"))])
    meta = pd.DataFrame({
        "pocket_id": pk.stem + ":m" + (pk.merged_rank - 1).astype(str),
        "uniprot": pk.uniprot, "fragment": pk.fragment, "structure_stem": pk.stem,
        "merged_index": pk.merged_rank - 1, "burrow_rank": pk.burrow_rank, "members": pk.members,
        "burrow_score": pk.score, "n_points": pk.n_points, "volume_A3": pk.volume_A3,
        "center_x": pk.cx, "center_y": pk.cy, "center_z": pk.cz,
        "site_n_points": pk.site_n_points, "site_volume_A3": pk.site_volume_A3,
        "residues": pk.residues, "n_residues": pk.n_res, "plddt_mean": pk.plddt_mean, "plddt_min": pk.plddt_min,
        "ok": np.linalg.norm(E, axis=1) > 0})
    assert meta.pocket_id.is_unique
    rec = dict(rep["method"], source="AFDB v6 human proteome (UP000005640_9606_HUMAN_v6.tar), AF mode",
               unit="merged region-rule pockets >= 10 points (method.describe_all)", residues="UniProt numbering",
               af_mode=True, backend="fast GPU (identical to ref)")
    REL.mkdir(parents=True, exist_ok=True)
    FX.write_table(REL / "fingerprints.parquet", meta, E, rec)
    rep["release_counts"] = {"n_pockets": len(meta), "n_uniprot": int(meta.uniprot.nunique()),
                             "n_models": int(meta.structure_stem.nunique()),
                             "n_models_processed": int((structs.status == "ok").sum()),
                             "n_models_error": int((structs.status != "ok").sum()),
                             "n_empty_sph8_dropped": int(structs.n_empty_site.sum()),
                             "fingerprints_parquet_bytes": (REL / "fingerprints.parquet").stat().st_size}
    log("release table", rep["release_counts"])

    # ---- 3. cross-check against the public API
    rep["crosscheck_describe_all"] = crosscheck(m, meta, E, a.n_crosscheck)
    log("crosscheck", rep["crosscheck_describe_all"])

    # ---- 4. indices
    faiss.omp_set_num_threads(a.threads)
    rep["index_flat"] = FX.build_index(E, meta, REL / "index_flat", kind="flat", record=rec, save_vectors=False)
    rep["index_opq_ivfpq"] = FX.build_index(E, meta, REL / "index_opq_ivfpq", kind="ivfpq", nlist=a.nlist, m=64,
                                            record=rec, seed=SEED)
    log("indices built")

    # ---- 5. exact ground truth, recall of PQ, latency
    N = len(E)
    D50, I50, t_all = exact_knn_gpu(E, 50)
    rep["exact"] = {"all_vs_all_top50_gpu_s": t_all, "top1_sim_median": float(np.median(D50[:, 0])),
                    "top10_sim_median": float(np.median(D50[:, 9])), "top50_sim_median": float(np.median(D50[:, 49]))}
    qi = rng.choice(N, min(a.n_recall, N), replace=False)
    ex10 = I50[qi, :10]
    flat = FX.Index(REL / "index_flat")
    faiss.omp_set_num_threads(1)
    rep["exact"]["single_query_cpu_1thread"] = latency(lambda q: flat.search(q, 10), E[qi])
    pq = FX.Index(REL / "index_opq_ivfpq")
    ivf = faiss.extract_index_ivf(pq.index)
    sweep = {}
    for nprobe in (1, 4, 16, 32, 64):
        ivf.nprobe = nprobe
        faiss.omp_set_num_threads(a.threads)
        Dq, Iq = pq.index.search(E[qi], 11)
        _, Iq = FX.drop_self(Dq, Iq, 10, qi)
        Dr, Ir = pq.search(E[qi], 101, rerank=101)
        _, Ir = FX.drop_self(Dr, Ir, 10, qi)
        faiss.omp_set_num_threads(1)
        sweep[nprobe] = {"recall_at_10": FX.recall_at_k(Iq, ex10), "top1_agree": float(np.mean(Iq[:, 0] == ex10[:, 0])),
                         "recall_at_10_rerank_top100": FX.recall_at_k(Ir, ex10),
                         "top1_agree_rerank": float(np.mean(Ir[:, 0] == ex10[:, 0])),
                         "single_query_1thread_pq": latency(lambda q: pq.index.search(q, 10), E[qi], 200),
                         "single_query_1thread_rerank100": latency(lambda q: pq.search(q, 10, rerank=100), E[qi], 200)}
        log("nprobe", nprobe, {k: v for k, v in sweep[nprobe].items() if not isinstance(v, dict)})
    rep["opq_ivfpq_recall"] = {"n_queries": len(qi), "self_excluded": True, "truth": "exact inner product top-10",
                               "sweep": sweep}
    rep["storage_bytes_per_pocket"] = {
        "fingerprint_float32": 4 * E.shape[1], "fingerprint_fp16": 2 * E.shape[1],
        "flat_index": rep["index_flat"]["index_bytes_per_pocket"],
        "opq_ivfpq_index": rep["index_opq_ivfpq"]["index_bytes_per_pocket"],
        "fingerprints_parquet_incl_metadata": (REL / "fingerprints.parquet").stat().st_size / N}

    # ---- 6. hubness (raw vs CSLS with database radii) and agreement with the demo's N1 neighbours
    k = 10
    hub = {"raw": FX.hubness(I50[:, :k], N)}
    r_db = D50[:, :k].astype(np.float64).mean(1)
    Q = np.concatenate([E, np.ones((N, 1), np.float32)], 1)
    B = np.concatenate([E, (-0.5 * r_db)[:, None].astype(np.float32)], 1)
    res = faiss.StandardGpuResources()
    gx = faiss.GpuIndexFlatIP(res, B.shape[1])
    gx.add(B)
    Dc, Ic = gx.search(Q, k + 1)
    _, Ic = FX.drop_self(Dc, Ic, k, np.arange(N))
    hub["csls_db"] = FX.hubness(Ic, N)
    hub["csls_db"]["overlap_with_raw_top10"] = FX.recall_at_k(Ic, I50[:, :k])
    indeg = np.bincount(I50[:, :k].reshape(-1), minlength=N)
    top = np.argsort(-indeg)[:100]
    hub["raw_hub_profile"] = {"site_volume_median_hubs": float(meta.site_volume_A3.iloc[top].median()),
                              "site_volume_median_all": float(meta.site_volume_A3.median()),
                              "r_db_median_hubs": float(np.median(r_db[top])), "r_db_median_all": float(np.median(r_db))}
    old = json.loads((ROOT / "results/proteome/index_search.json").read_text())["hubness"]
    hub["n1_demo_for_reference"] = {kk: {x: old[kk][x] for x in ("skewness", "max", "p99", "frac_zero",
                                                                    "top1pct_share")} for kk in ("raw", "csls_db")}
    rep["hubness"] = hub
    # background: similarity of random pairs of pockets from different proteins (for score thresholds)
    i, j = rng.integers(0, N, 2_000_000), rng.integers(0, N, 2_000_000)
    up = meta.uniprot.to_numpy()
    keep = up[i] != up[j]
    s_bg = np.einsum("nd,nd->n", E[i[keep]], E[j[keep]])
    rep["random_pair_similarity"] = {"n_pairs": int(keep.sum()), "different_proteins": True,
                                     **{f"p{q}": float(np.percentile(s_bg, q)) for q in (1, 10, 50, 90, 99, 99.9)}}
    rep["exact"]["top1_sim_percentiles"] = {f"p{q}": float(np.percentile(D50[:, 0], q)) for q in (10, 50, 90)}
    I_n1 = np.load(IX / "knn_exact_I.npy", mmap_mode="r")
    rep["neighbour_overlap_with_n1_demo_top10"] = FX.recall_at_k(I50[qi, :10], np.asarray(I_n1[qi, :10]))
    rep["same_protein_top1_frac"] = float(np.mean(meta.uniprot.to_numpy()[I50[:, 0]] == meta.uniprot.to_numpy()))
    np.save(REL / "index_flat" / "knn_top10_I.npy", I50[:, :10].astype(np.int32))
    np.save(REL / "index_flat" / "knn_top10_D.npy", D50[:, :10].astype(np.float16))
    np.save(REL / "index_flat" / "csls_r_db.npy", r_db.astype(np.float32))
    log("hubness", json.dumps(hub["raw"]), json.dumps(hub["csls_db"]))

    # ---- 7. checksums + result
    files = sorted(f for f in REL.rglob("*") if f.is_file() and f.name not in ("SHA256SUMS", "README.md"))
    (REL / "SHA256SUMS").write_text("".join(f"{sha256(f)}  {f.relative_to(REL)}\n" for f in files))
    rep["files"] = {str(f.relative_to(REL)): f.stat().st_size for f in files}
    from pocketcompare.provenance import write_result
    write_result(RES, rep, script=__file__, args=vars(a), config=str(MM.CONFIG.relative_to(ROOT)),
                 inputs=[IX / "pockets.parquet", IX / "a1_raw.npy", IX / "env_raw.npy", MM.CONFIG,
                         *[ROOT / f for f in m.cfg["model_files"]], ROOT / m.cfg["input_stats"]],
                 seed=SEED, device=os.environ.get("CUDA_VISIBLE_DEVICES", "cpu"), start_time=t_start)
    log("done", RES)


if __name__ == "__main__":
    main()
