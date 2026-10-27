#!/usr/bin/env python
"""AFDB proteome demo, stage 2: collect, de-duplicate fragments, embed, FAISS exact + IVF-PQ search, hubness.

    CUDA_VISIBLE_DEVICES=2,3 python scripts/proteome/index_search.py --run data/processed/proteome_human/run_gpu

1. Collect shards (run_proteome.py).  Fragments of > 2,700-aa proteins (AFDB F1..Fn, 1,400 aa every 200) are
   mapped to UniProt numbering (DBREF offset) and de-duplicated per protein: greedy by BURROW score, a pocket of
   another fragment with lining-residue Jaccard >= 0.5 to a kept pocket is dropped (rule of pocket_detect's
   proteome run, results/proteome/HUMAN.md there).
2. Embed: 1:1 two-part block cosine of z-scored A1(sph8) and env(sph8) (proteome_lib.embed_a1env) with the
   TOUGH-M1-dev + BLiPS-train statistics (ref_stats.py).  Unit float32 vectors, 627 d.
3. Exact inner-product search, faiss GpuIndexFlatIP, all-vs-all top-50 (self excluded).  Timed: total wall,
   batched per-pocket time, single-query latency (GPU and CPU flat).
4. IVF-PQ (vectors zero-padded to 640 d; IVF nlist, PQ64 x 8 bit = 64-byte codes; plain and OPQ-rotated), trained
   on a random subset; recall@10 vs exact over random queries for an nprobe sweep; latency; bytes per pocket.
5. Hubness of the top-10 graph: in-degree distribution, raw vs CSLS (s - (r_i + r_j)/2, k = 10; r from (a) the
   proteome itself and (b) the reference pool = DESIGN §1 background).  CSLS top-10 is exact (augmented-vector
   MIPS: [e_i, 1] . [e_j, -r_j / 2]).

Outputs: data/processed/proteome_human/index/ (pockets.parquet, emb.npy, knn I/D, csls I) and
results/proteome/index_search.json.
"""
from __future__ import annotations

import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "2,3")

import argparse  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/proteome")]
from proteome_lib import embed_a1env  # noqa: E402

import faiss  # noqa: E402

P = ROOT / "data/processed/proteome_human"
RES = ROOT / "results/proteome"
SEED = 0


def collect(run: Path):
    sh = sorted(glob.glob(str(run / "shards/*.structs.parquet")))
    structs, pockets, a1, env = [], [], [], []
    for f in sh:
        b = f[:-len(".structs.parquet")]
        structs.append(pd.read_parquet(f))
        p = pd.read_parquet(b + ".pockets.parquet")
        z = np.load(b + ".desc.npz")
        assert len(p) == len(z["a1"]) == len(z["env"]), b
        pockets.append(p)
        a1.append(z["a1"])
        env.append(z["env"])
    return (pd.concat(structs, ignore_index=True), pd.concat(pockets, ignore_index=True),
            np.concatenate(a1), np.concatenate(env))


def dedupe_fragments(pk: pd.DataFrame, structs: pd.DataFrame, jac: float = 0.5) -> np.ndarray:
    """Index of the pocket each row duplicates (-1 = kept).  Only pockets of fragmented proteins, only across
    different fragments; greedy by score (ties: lower fragment, better rank)."""
    dup = np.full(len(pk), -1, np.int64)
    nfr = structs.set_index("stem").n_fragments
    frag = pk.stem.map(nfr).to_numpy() > 1
    sub = pk[frag]
    for _, g in sub.groupby("uniprot"):
        g = g.sort_values(["score", "fragment", "burrow_rank"], ascending=[False, True, True])
        kept = []
        for i, row in zip(g.index, g.itertuples()):
            rs = set(row.residues.split())
            hit = -1
            for j, fj, rj in kept:
                if fj != row.fragment and rs and len(rs & rj) / len(rs | rj) >= jac:
                    hit = j
                    break
            if hit >= 0:
                dup[i] = hit
            else:
                kept.append((i, row.fragment, rs))
    return dup


def exact_knn(E, k, res_list, batch=16384):
    d = E.shape[1]
    idx = faiss.GpuIndexFlatIP(res_list[0], d)
    idx.add(E)
    t0 = time.perf_counter()
    Dl, Il = [], []
    for s in range(0, len(E), batch):
        D_, I_ = idx.search(E[s:s + batch], k + 1)
        Dl.append(D_)
        Il.append(I_)
    t = time.perf_counter() - t0
    D_, I_ = np.concatenate(Dl), np.concatenate(Il)
    return drop_self(D_, I_, k), t, idx


def drop_self(D_, I_, k, qids=None):
    """Remove each query's own id (``qids``; default 0..n-1) from its result row, keep the first k."""
    n = len(I_)
    q = np.arange(n) if qids is None else np.asarray(qids)
    self_ = I_ == q[:, None]
    # remove the self column (if present) else the last column
    keep = ~self_
    no_self = keep.all(1)
    keep[no_self, -1] = False
    I2 = I_[keep].reshape(n, -1)[:, :k]
    D2 = D_[keep].reshape(n, -1)[:, :k]
    return D2, I2


def single_query_latency(index, E, n=500, rng=None):
    q = E[rng.choice(len(E), n, replace=False)]
    index.search(q[:5], 10)                 # warm
    t = []
    for i in range(n):
        t0 = time.perf_counter()
        index.search(q[i:i + 1], 10)
        t.append(time.perf_counter() - t0)
    return dict(median_ms=1e3 * float(np.median(t)), p90_ms=1e3 * float(np.percentile(t, 90)), n=n)


def indegree_stats(I10, n):
    indeg = np.bincount(I10.reshape(-1), minlength=n)
    s = np.sort(indeg)[::-1]
    from scipy.stats import skew
    return dict(k=I10.shape[1], skewness=float(skew(indeg)), max=int(s[0]), p99=float(np.percentile(indeg, 99)),
                median=float(np.median(indeg)), frac_zero=float((indeg == 0).mean()),
                top1pct_share=float(s[:max(1, n // 100)].sum() / s.sum()),
                top10_hubs=s[:10].tolist()), indeg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=P / "run_gpu")
    ap.add_argument("--k", type=int, default=50)
    ap.add_argument("--nlist", type=int, default=1024)
    ap.add_argument("--n-recall", type=int, default=10000)
    ap.add_argument("--train", type=int, default=100000)
    a = ap.parse_args()
    rng = np.random.default_rng(SEED)
    out = P / "index"
    out.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    rep: dict = dict(faiss_version=faiss.__version__, n_gpus=faiss.get_num_gpus(),
                     cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES"))

    # ---- 1. collect + fragment de-duplication
    t0 = time.perf_counter()
    structs, pk, a1, env = collect(a.run)
    dup = dedupe_fragments(pk, structs)
    pk["dup_of"] = dup
    keep = dup < 0
    rep["collect"] = dict(n_structs=len(structs), n_structs_ok=int((structs.status == "ok").sum()),
                          n_struct_errors=int((structs.status != "ok").sum()), n_pockets_all=len(pk),
                          n_fragment_duplicates=int((~keep).sum()), n_pockets_index=int(keep.sum()),
                          n_uniprot=int(pk.uniprot[keep].nunique()), wall_s=time.perf_counter() - t0)
    pk = pk[keep].reset_index(drop=True)
    a1, env = a1[keep], env[keep]
    pk.to_parquet(out / "pockets.parquet", index=False)
    np.save(out / "a1_raw.npy", a1)
    np.save(out / "env_raw.npy", env)

    # ---- 2. embed
    zs = dict(np.load(P / "zstats.npz"))
    t0 = time.perf_counter()
    E = embed_a1env(a1, env, zs)
    rep["embed"] = dict(dim=int(E.shape[1]), wall_s=time.perf_counter() - t0,
                        zstats=json.loads((P / "zstats.json").read_text()))
    np.save(out / "emb.npy", E)
    N, d = E.shape
    Eref = embed_a1env(zs["ref_a1"], zs["ref_env"], zs)

    # ---- 3. exact search (GPU flat IP)
    res = [faiss.StandardGpuResources() for _ in range(faiss.get_num_gpus())]
    (D50, I50), t_all, gidx = exact_knn(E, a.k, res)
    np.save(out / "knn_exact_I.npy", I50.astype(np.int32))
    np.save(out / "knn_exact_D.npy", D50.astype(np.float16))
    cidx = faiss.IndexFlatIP(d)
    cidx.add(E)
    faiss.omp_set_num_threads(1)
    lat_cpu1 = single_query_latency(cidx, E, 200, rng)
    faiss.omp_set_num_threads(16)
    lat_cpu16 = single_query_latency(cidx, E, 200, rng)
    rep["exact"] = dict(N=N, k=a.k, gpu="1 x RTX 4090 (GpuIndexFlatIP, fp32)", all_vs_all_wall_s=t_all,
                        per_pocket_batched_us=1e6 * t_all / N, pairs_per_s=N * N / t_all,
                        single_query_gpu=single_query_latency(gidx, E, 500, rng),
                        single_query_cpu_1thread=lat_cpu1, single_query_cpu_16threads=lat_cpu16,
                        bytes_per_pocket_float32=4 * d,
                        top1_sim_median=float(np.median(D50[:, 0])), top10_sim_median=float(np.median(D50[:, 9])),
                        top50_sim_median=float(np.median(D50[:, 49])))
    print(json.dumps(rep["exact"], indent=1), flush=True)

    # ---- 4. IVF-PQ (64-byte codes) recall@10 vs exact
    dp = 640
    Ep = np.zeros((N, dp), np.float32)
    Ep[:, :d] = E
    tr = Ep[rng.choice(N, min(a.train, N), replace=False)]
    qi = rng.choice(N, min(a.n_recall, N), replace=False)
    exact10 = I50[qi, :10]
    faiss.omp_set_num_threads(16)
    pq_rep = {}
    for name in (f"IVF{a.nlist},PQ64", f"OPQ64_{dp},IVF{a.nlist},PQ64"):
        ix = faiss.index_factory(dp, name, faiss.METRIC_INNER_PRODUCT)
        t0 = time.perf_counter()
        ix.train(tr)
        t_train = time.perf_counter() - t0
        t0 = time.perf_counter()
        ix.add(Ep)
        t_add = time.perf_counter() - t0
        nbytes = len(faiss.serialize_index(ix))
        ivf = faiss.extract_index_ivf(ix)
        sweep = {}
        for nprobe in (1, 4, 16, 64):
            ivf.nprobe = nprobe
            faiss.omp_set_num_threads(16)
            t0 = time.perf_counter()
            Dq, Iq = ix.search(Ep[qi], 11)
            t_b = time.perf_counter() - t0
            _, Iq = drop_self(Dq, Iq, 10, qi)
            rec = np.mean([len(set(x) & set(y)) / 10 for x, y in zip(Iq, exact10)])
            r1 = float(np.mean(Iq[:, 0] == exact10[:, 0]))
            # shortlist variant: PQ top-100 re-ranked with the exact float vectors (needs them on disk/RAM)
            Ds, Is = ix.search(Ep[qi], 101)
            _, Is = drop_self(Ds, Is, 100, qi)
            sc = np.einsum("qd,qkd->qk", E[qi], E[np.clip(Is, 0, None)])
            sc[Is < 0] = -np.inf
            Ir = np.take_along_axis(Is, np.argsort(-sc, 1)[:, :10], 1)
            rec_rr = np.mean([len(set(x) & set(y)) / 10 for x, y in zip(Ir, exact10)])
            faiss.omp_set_num_threads(1)
            lat = single_query_latency(ix, Ep, 200, rng)
            sweep[nprobe] = dict(recall_at_10=float(rec), top1_agree=r1, batched_us_per_query_16thr=1e6 * t_b / len(qi),
                                 single_query_1thread=lat, recall_at_10_rerank_top100=float(rec_rr))
        pq_rep[name] = dict(train_n=len(tr), train_s=t_train, add_s=t_add, index_bytes=nbytes,
                            bytes_per_pocket=nbytes / N, code_bytes=64, sweep=sweep)
        print(name, json.dumps(pq_rep[name], indent=1), flush=True)
    rep["ivfpq"] = pq_rep

    # ---- 5. hubness: raw vs CSLS (k = 10)
    k = 10
    r_db = D50[:, :k].astype(np.float64).mean(1)
    ridx = faiss.GpuIndexFlatIP(res[0], d)
    ridx.add(Eref)
    Dr, _ = ridx.search(E, k)
    r_ref = Dr.astype(np.float64).mean(1)
    hub = {}
    st, indeg_raw = indegree_stats(I50[:, :k], N)
    hub["raw"] = st
    csls_I = {}
    for name, r in (("csls_db", r_db), ("csls_ref", r_ref)):
        Q = np.concatenate([E, np.ones((N, 1), np.float32)], 1)
        B = np.concatenate([E, (-0.5 * r)[:, None].astype(np.float32)], 1)
        ix = faiss.GpuIndexFlatIP(res[0], d + 1)
        ix.add(B)
        Dc, Ic = ix.search(Q, k + 1)
        _, Ic = drop_self(Dc, Ic, k)
        csls_I[name] = Ic
        st, _ = indegree_stats(Ic, N)
        st["overlap_with_raw_top10"] = float(np.mean([len(set(x) & set(y)) / k for x, y in zip(Ic, I50[:, :k])]))
        hub[name] = st
        np.save(out / f"knn_{name}_I.npy", Ic.astype(np.int32))
    # what are the hubs? (size / burial of the top-100 raw hubs vs all)
    top = np.argsort(-indeg_raw)[:100]
    hub["raw_hub_profile"] = dict(
        site_volume_median_hubs=float(pk.site_volume_A3.iloc[top].median()),
        site_volume_median_all=float(pk.site_volume_A3.median()),
        volume_median_hubs=float(pk.volume_A3.iloc[top].median()), volume_median_all=float(pk.volume_A3.median()),
        score_median_hubs=float(pk.score.iloc[top].median()), score_median_all=float(pk.score.median()),
        r_db_median_hubs=float(np.median(r_db[top])), r_db_median_all=float(np.median(r_db)))
    np.save(out / "r_db.npy", r_db.astype(np.float32))
    np.save(out / "r_ref.npy", r_ref.astype(np.float32))
    rep["hubness"] = hub
    print(json.dumps(hub, indent=1), flush=True)
    (RES / "index_search.json").write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
