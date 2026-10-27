#!/usr/bin/env python
"""AFDB proteome demo: throughput tables, backend comparison and the AFDB-scale EXTRAPOLATION.

    python scripts/proteome/summarize.py

Reads data/processed/proteome_human/{members.json, run_*/, bench_*/, index/} and results/proteome/index_search.json;
writes results/proteome/summary.json.  Every AFDB-scale number is a linear extrapolation of the human measurement
(marked ``extrapolated``), not a run.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data/processed/proteome_human"
RES = ROOT / "results/proteome"
N_AFDB = 200e6
CPU_COLS = ["t_read_s", "t_parse_s", "t_prep_s", "t_burrow_post_s", "t_merge_s", "t_desc_s"]


def run_stats(run: Path) -> dict | None:
    f = sorted(glob.glob(str(run / "shards/*.structs.parquet")))
    if not f or not (run / "run.json").exists():
        return None
    s = pd.concat([pd.read_parquet(x) for x in f], ignore_index=True)
    r = json.loads((run / "run.json").read_text())[-1]
    ok = s[s.status == "ok"]
    n, wall = len(s), r["wall_s"]
    npk = int(ok.n_kept.sum())
    cpu = {c: float(ok[c].sum()) for c in CPU_COLS}
    burrow_cpu = cpu["t_parse_s"] + cpu["t_prep_s"] + cpu["t_burrow_post_s"]
    feat = float(ok.t_feat_s.sum())
    on_gpu = r["backend"] == "gpu"
    if not on_gpu:
        burrow_cpu += feat
    desc_cpu = cpu["t_merge_s"] + cpu["t_desc_s"]
    return dict(
        backend=r["backend"], devices=r["devices"], cpu_workers=r["cpu_workers"], n_structures=n,
        n_errors=int((s.status != "ok").sum()), errors=s[s.status != "ok"].error.value_counts().to_dict(),
        n_pockets=npk, wall_s=wall, structures_per_s=n / wall, pockets_per_s=npk / wall,
        loadavg_start=r["loadavg_start"], loadavg_end=r["loadavg_end"],
        cpu_s_per_structure=dict(read_decompress=cpu["t_read_s"] / n, burrow=burrow_cpu / n, descriptors=desc_cpu / n,
                                 total=(cpu["t_read_s"] + burrow_cpu + desc_cpu) / n),
        gpu_s_per_structure=feat / n if on_gpu else 0.0,
        descriptor_ms_per_pocket=1e3 * desc_cpu / max(npk, 1),
        share_of_cpu=dict(read=cpu["t_read_s"] / (cpu["t_read_s"] + burrow_cpu + desc_cpu),
                          burrow=burrow_cpu / (cpu["t_read_s"] + burrow_cpu + desc_cpu),
                          descriptors=desc_cpu / (cpu["t_read_s"] + burrow_cpu + desc_cpu)),
        stage_cpu_s_total=cpu, gpu_feat_s_total=feat if on_gpu else 0.0,
        median_atoms=float(ok.n_atoms.median()), median_points=float(ok.n_points.median()),
        pockets_per_structure=npk / max(len(ok), 1),
        merged_per_structure=float(ok.n_merged.mean()), region_per_structure=float(ok.n_region.mean()),
        dropped_lt10_per_structure=float(ok.n_small.mean()),
        dropped_single_metal_per_structure=float(ok.n_metal_single.mean()))


def main():
    out: dict = {"tar": json.loads((P / "members.json").read_text())}
    out["runs"] = {p.name: run_stats(p) for p in sorted(P.glob("run_*")) + sorted(P.glob("bench_*"))}
    out["runs"] = {k: v for k, v in out["runs"].items() if v}
    ix = json.loads((RES / "index_search.json").read_text())
    pk = pd.read_parquet(P / "index/pockets.parquet")
    st = pd.concat([pd.read_parquet(x) for x in glob.glob(str(P / "run_gpu/shards/*.structs.parquet"))])
    N = len(pk)
    nonfrag = st[(st.n_fragments == 1) & (st.status == "ok")]
    pps_nonfrag = float(nonfrag.n_kept.mean())
    meta_bytes = (P / "index/pockets.parquet").stat().st_size / N
    out["pockets"] = dict(
        N_index=N, per_protein=N / pk.uniprot.nunique(), per_model_nonfragment=pps_nonfrag,
        frac_structures_without_pocket=float((st.n_kept == 0).mean()),
        n_points=dict(median=float(pk.n_points.median()), p90=float(pk.n_points.quantile(.9))),
        volume_A3=dict(median=float(pk.volume_A3.median()), p90=float(pk.volume_A3.quantile(.9))),
        site_volume_A3=dict(median=float(pk.site_volume_A3.median()), p90=float(pk.site_volume_A3.quantile(.9))),
        score=dict(median=float(pk.score.median()), frac_ge_0_1=float((pk.score >= 0.1).mean())),
        plddt_mean=dict(median=float(pk.plddt_mean.median()), frac_lt_70=float((pk.plddt_mean < 70).mean())),
        n_res=dict(median=float(pk.n_res.median())), metadata_bytes_per_pocket_parquet=meta_bytes)
    g = out["runs"]["run_gpu"]
    pq = ix["ivfpq"]
    best_pq = max(pq.values(), key=lambda v: v["sweep"]["16"]["recall_at_10"])
    n_pk = N_AFDB * pps_nonfrag
    ex = ix["exact"]
    # per-structure costs of NON-fragment models (fragments are 1,400-aa windows and cost more)
    okn = nonfrag
    cpu_cols_burrow = ["t_parse_s", "t_prep_s", "t_burrow_post_s"]
    c_read = float(okn.t_read_s.mean())
    c_burrow = float(okn[cpu_cols_burrow].sum(axis=1).mean())
    c_desc = float((okn.t_merge_s + okn.t_desc_s).mean())
    c_gpu = float(okn.t_feat_s.mean())
    tot_all = g["cpu_s_per_structure"]["total"] * g["n_structures"]
    util = tot_all / (g["cpu_workers"] * g["wall_s"])
    out["nonfragment_cost_per_structure"] = dict(cpu_read_s=c_read, cpu_burrow_s=c_burrow, cpu_desc_s=c_desc,
                                                 gpu_s=c_gpu, cpu_worker_utilisation_full_run=util)
    out["extrapolation_200M"] = dict(
        note=("EXTRAPOLATED linearly from the human AFDB run (23,586 models, 2 x RTX 4090 + 22 CPU workers, shared "
              "node). Assumes AFDB structures cost what human non-fragment models cost on average (human models are "
              "longer than the AFDB average, so this is likely conservative) and the same pockets per model."),
        structures=N_AFDB, pockets_per_structure=pps_nonfrag, pockets=n_pk,
        cpu_core_hours=N_AFDB * (c_read + c_burrow + c_desc) / 3600,
        cpu_core_hours_read=N_AFDB * c_read / 3600,
        cpu_core_hours_burrow=N_AFDB * c_burrow / 3600,
        cpu_core_hours_descriptors=N_AFDB * c_desc / 3600,
        gpu_hours=N_AFDB * c_gpu / 3600,
        days_on_this_node_config=N_AFDB * (c_read + c_burrow + c_desc) / (g["cpu_workers"] * util) / 86400,
        storage_TB=dict(raw_float32_627d=n_pk * 2508 / 1e12, float16=n_pk * 1254 / 1e12,
                        ivfpq64_index=n_pk * best_pq["bytes_per_pocket"] / 1e12,
                        metadata_parquet=n_pk * meta_bytes / 1e12),
        exact_all_vs_all_gpu_hours=(n_pk ** 2) / ex["pairs_per_s"] / 3600,
        exact_single_query_s_cpu_1thread=ex["single_query_cpu_1thread"]["median_ms"] / 1e3 * n_pk / N,
        ivfpq_note="ANN latency at 1e9 vectors is NOT measured; IVF-PQ cost per query scales with nprobe/nlist x N "
                   "codes scanned + the coarse search, so nlist must grow with N (e.g. 2^16-2^20 with an HNSW coarse "
                   "quantizer).")
    (RES / "summary.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
