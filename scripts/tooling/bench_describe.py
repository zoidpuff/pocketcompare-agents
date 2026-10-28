#!/usr/bin/env python
"""End-to-end runtime of ``pocketcompare describe`` (CLI) per structure: CPU (ref / fast backends) and fast GPU.

    python scripts/tooling/bench_describe.py --n 200 --workers 22 --device cuda:0

Structures: ``--n`` random AFDB v6 human models (seed 0; read from the proteome tarball by byte offset into
``--workdir``), AF mode, all pockets (``describe_all``: merged region pockets >= 10 points).
Runs (each a fresh ``pocketcompare describe`` subprocess; wall time includes nothing but the run itself, the
subprocess start-up / imports / Numba-cache load is reported separately as ``startup_s``):
* latency: the first ``--n-latency`` structures, 1 worker, single-threaded (NUMBA/OMP threads = 1) for the CPU
  backends; GPU: in-process (``--workers 0``), batch 1.  Per-structure time = the CLI's ``total_s``
  (parse + BURROW + description + embedding; file read included).
* throughput: all ``--n`` structures with ``--workers`` CPU processes (GPU: batch 16).
Also checks that the three backends give identical fingerprints.
Output: results/tooling/describe_runtime.json (+ .prov.json).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
TAR = "/cluster/work/beltrao/shared/alphafold/v6/UP000005640_9606_HUMAN_v6.tar"
MEMBERS = ROOT / "data/processed/proteome_human/members.parquet"
OUT = ROOT / "results/tooling/describe_runtime.json"


def extract(n, workdir: Path, seed=0) -> list[Path]:
    m = pd.read_parquet(MEMBERS).sample(n, random_state=seed)
    workdir.mkdir(parents=True, exist_ok=True)
    out = []
    with open(TAR, "rb") as fh:
        for r in m.itertuples():
            p = workdir / f"{r.stem}.pdb.gz"
            if not p.exists():
                fh.seek(r.offset_data)
                raw = fh.read(r.size)
                gzip.decompress(raw)                  # integrity check
                p.write_bytes(raw)
            out.append(p)
    return out


def run(files, out, extra, single_thread=False, env_extra=None):
    env = dict(os.environ)
    if single_thread:
        env.update({k: "1" for k in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                     "MKL_NUM_THREADS")})
    env.update(env_extra or {})
    lst = out.with_suffix(".txt")
    t0 = time.perf_counter()
    cmd = [sys.executable, "-m", "pocketcompare", "describe", *map(str, files), "--af-mode", "-o", str(out), *extra]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    wall = time.perf_counter() - t0
    if r.returncode:
        raise RuntimeError(r.stderr[-3000:])
    lst.write_text(r.stderr)
    st = pd.read_parquet(str(out).removesuffix(".parquet") + ".structures.parquet")
    # the CLI's own wall time (after imports) is printed in its last log line: "[12.3 s wall, ...]"
    last = [ln for ln in r.stderr.splitlines() if " s wall" in ln][-1]
    cli_wall = float(last.rsplit("[", 1)[1].split(" s wall")[0])
    ok = st[st.status == "ok"]
    rec = {"n_structures": len(st), "n_errors": int((st.status != "ok").sum()), "n_pockets": int(st.n_pockets.sum()),
           "process_wall_s": wall, "cli_wall_s": cli_wall, "startup_s": wall - cli_wall,
           "s_per_structure_wall": cli_wall / len(st), "structures_per_s": len(st) / cli_wall,
           "pockets_per_s": float(st.n_pockets.sum()) / cli_wall,
           "per_structure_total_s": {"median": float(ok.total_s.median()), "mean": float(ok.total_s.mean()),
                                     "p90": float(ok.total_s.quantile(0.9))},
           "stage_mean_s": {c: float(ok[c].mean()) for c in ("parse_s", "burrow_s", "gpu_s", "describe_s")
                            if c in ok}}
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--n-latency", type=int, default=50)
    ap.add_argument("--workers", type=int, default=22)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--workdir", type=Path, default=Path(os.environ.get("TMPDIR", "/tmp")) / "pocketcompare_bench")
    a = ap.parse_args()
    t_start = time.time()
    files = extract(a.n, a.workdir / "structures")
    lat = files[:a.n_latency]
    od = a.workdir / "out"
    od.mkdir(parents=True, exist_ok=True)
    rep = {"n": a.n, "n_latency": a.n_latency, "workers": a.workers, "device": a.device, "host": os.uname().nodename,
           "loadavg_start": os.getloadavg(), "cpu_count": os.cpu_count(),
           "structures": "random AFDB v6 human models (members.parquet sample, seed 0), AF mode, describe_all"}
    runs = {}
    runs["latency_ref_cpu1"] = run(lat, od / "lat_ref.parquet", ["--backend", "ref", "--workers", "1"], True)
    runs["latency_fast_cpu1"] = run(lat, od / "lat_fast.parquet", ["--backend", "fast", "--workers", "1"], True)
    runs["latency_gpu_inprocess"] = run(lat, od / "lat_gpu.parquet", ["--device", a.device, "--workers", "0",
                                                                      "--batch", "1"])
    runs[f"throughput_ref_cpu{a.workers}"] = run(files, od / "tp_ref.parquet",
                                                 ["--backend", "ref", "--workers", str(a.workers)])
    runs[f"throughput_fast_cpu{a.workers}"] = run(files, od / "tp_fast.parquet",
                                                  ["--backend", "fast", "--workers", str(a.workers)])
    runs[f"throughput_gpu_{a.workers}workers"] = run(files, od / "tp_gpu.parquet",
                                                     ["--device", a.device, "--workers", str(a.workers),
                                                      "--batch", "16"])
    rep["runs"] = runs
    # backend equivalence
    from pocketcompare import fpindex as FX
    tabs = {k: FX.read_table(od / f"tp_{k}.parquet") for k in ("ref", "fast", "gpu")}
    key = lambda m: m.pocket_id.to_numpy()  # noqa: E731
    eq = {}
    for k in ("fast", "gpu"):
        m0, V0, _ = tabs["ref"]
        m1, V1, _ = tabs[k]
        o0, o1 = np.argsort(key(m0)), np.argsort(key(m1))
        same_ids = bool(np.array_equal(key(m0)[o0], key(m1)[o1]))
        eq[k] = {"same_pocket_ids": same_ids,
                 "max_abs_diff": float(np.abs(V0[o0] - V1[o1]).max()) if same_ids and len(V0) else None}
    rep["equivalence_vs_ref"] = eq
    rep["loadavg_end"] = os.getloadavg()
    from pocketcompare.provenance import write_result
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_result(OUT, rep, script=__file__, args=vars(a) | {"workdir": str(a.workdir)}, config=None,
                 inputs=[MEMBERS], seed=0, device=a.device, start_time=t_start)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
