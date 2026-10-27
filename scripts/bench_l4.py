#!/usr/bin/env python
"""L4 inference cost: ms/pocket of the 3-seed ensemble on GPU (batch 256) and on 1 CPU thread (batch 32).

    python scripts/bench_l4.py --models results/models/l4 --device cuda:2 [--n 1024]

Pockets = the first ``n`` TOUGH-M1 U-mode point sets (data/processed/l4).  Excludes BURROW and point-set
extraction (sph8 shaper + FPS + soft typing: see data/processed/l4/*/summary.json t_ms_*), includes padding and
host->device copies.  Output: <models>/bench.json (+ printed table).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import train_l4 as T4  # noqa: E402
from pocketcompare import a4b as A4  # noqa: E402


def bench(model_dir, device, ids, reps=3):
    import torch
    out = {}
    for dev, bs, n_use in ((device, 256, len(ids)), ("cpu", 32, min(len(ids), 128))):
        if dev == "cpu":
            torch.set_num_threads(1)
        models, cfg, sc, n1s = T4.load_models(model_dir, dev)
        sub = ids[:n_use]
        T4.ensemble_embed(models, cfg, sc, n1s, "tough_m1", "U", sub[:bs], dev, bs=bs)   # warm-up
        ts = []
        for _ in range(reps):
            if dev.startswith("cuda"):
                torch.cuda.synchronize(dev)
            t0 = time.perf_counter()
            T4.ensemble_embed(models, cfg, sc, n1s, "tough_m1", "U", sub, dev, bs=bs)
            if dev.startswith("cuda"):
                torch.cuda.synchronize(dev)
            ts.append(time.perf_counter() - t0)
        out["gpu" if dev != "cpu" else "cpu1"] = {"ms_per_pocket": 1e3 * min(ts) / n_use, "batch": bs, "n": n_use}
    out["n_params_per_seed"] = int(sum(p.numel() for p in models[0].parameters()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=str(ROOT / "results/models/l4"))
    ap.add_argument("--device", default="cuda:2")
    ap.add_argument("--n", type=int, default=1024)
    a = ap.parse_args()
    ids = A4.ids_table("tough_m1").pocket_id.tolist()[:a.n]
    res = {}
    for d in sorted(Path(a.models).iterdir()):
        if (d / "config.json").exists():
            res[d.name] = bench(d, a.device, ids)
            print(d.name, json.dumps(res[d.name]), flush=True)
    ext = {}
    for ds in ("blips", "tough_m1", "ppips"):
        s = json.loads((ROOT / "data/processed/l4" / ds / "summary.json").read_text())
        ext[ds] = {k: v["t_ms_median"] for k, v in s.items() if isinstance(v, dict)}
    res["_extraction_ms_median"] = ext
    Path(a.models, "bench.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
