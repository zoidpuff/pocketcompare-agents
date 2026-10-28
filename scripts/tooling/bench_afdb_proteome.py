"""End-to-end throughput of ``pocketcompare describe`` on a random sample of one AFDB v6 proteome tarball.

Used for the AFDB-scale cost estimate (docs/AFDB_COST.md): it measures structures/s, pockets/s, residues per model
and peak resident memory summed over the whole process tree (sampled every 0.5 s), so per-structure cost can be
related to protein length and extrapolated to the AFDB length distribution.

    python scripts/tooling/bench_afdb_proteome.py --tar /cluster/work/beltrao/shared/alphafold/v6/UP000000625_83333_ECOLI_v6.tar \
        --n 2000 --workers 32 --device cuda:0 --out results/tooling/bench_ecoli.json
"""
import argparse
import gzip
import json
import os
import random
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.seeds import SEEDS  # noqa: E402


def n_residues(cif_gz: bytes) -> int:
    """Count CA atoms in an AF model mmCIF (one chain, one model)."""
    n = 0
    for line in gzip.decompress(cif_gz).decode().splitlines():
        if line.startswith("ATOM") and " CA " in line:
            n += 1
    return n


def tree_rss(proc: psutil.Process) -> int:
    total = 0
    for p in [proc] + proc.children(recursive=True):
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tar", required=True)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--device", default="cuda:0", help="cuda:N (fast GPU backend) or cpu (fast CPU backend)")
    ap.add_argument("--workdir", type=Path, default=Path("/tmp/pc_bench_afdb"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    rng = random.Random(SEEDS[0])
    with tarfile.open(a.tar) as tf:
        members = [m for m in tf.getmembers() if m.name.endswith(".cif.gz") and "-F1-" in m.name]
        sample = rng.sample(members, min(a.n, len(members)))
        inp = a.workdir / "in"
        inp.mkdir(parents=True, exist_ok=True)
        lengths = []
        for m in sample:
            data = tf.extractfile(m).read()
            (inp / Path(m.name).name).write_bytes(data)
            lengths.append(n_residues(data))
    out_dir = a.workdir / "out"
    cmd = [sys.executable, "-m", "pocketcompare", "describe", str(inp), "--af-mode", "--workers", str(a.workers),
           "--out", str(out_dir / "fp.parquet")]
    cmd += ["--backend", "fast", "--device", a.device]
    env = dict(os.environ, NUMBA_CACHE_DIR=os.environ.get("NUMBA_CACHE_DIR", "/tmp/numba_cache"))
    peak = [0]
    t0 = time.time()
    proc = subprocess.Popen(cmd, env=env)
    ps = psutil.Process(proc.pid)

    def sample_rss():
        while proc.poll() is None:
            peak[0] = max(peak[0], tree_rss(ps))
            time.sleep(0.5)
    th = threading.Thread(target=sample_rss, daemon=True)
    th.start()
    rc = proc.wait()
    wall = time.time() - t0
    th.join(timeout=2)
    import pandas as pd
    fp = pd.read_parquet(out_dir / "fp.parquet")
    lengths.sort()
    res = {"tar": a.tar, "n_structures": len(sample), "workers": a.workers, "device": a.device, "rc": rc,
           "wall_s_incl_startup": wall, "structures_per_s": len(sample) / wall, "pockets": int(len(fp)),
           "pockets_per_structure": len(fp) / len(sample), "pockets_per_s": len(fp) / wall,
           "residues_mean": sum(lengths) / len(lengths), "residues_median": lengths[len(lengths) // 2],
           "peak_rss_tree_GB": peak[0] / 1e9, "cpu_count": os.cpu_count(), "loadavg_start": os.getloadavg(),
           "seed": SEEDS[0]}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
