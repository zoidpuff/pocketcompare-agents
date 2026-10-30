#!/usr/bin/env python
"""Persistent ``pocketcompare describe`` for one GPU (used by worker.py with ``--runner persistent``, the default).

Each request (one JSON line on stdin: {"id", "inputs": <dir of structures>, "out": <parquet>}) is processed exactly
like ``pocketcompare describe <dir> --af-mode --backend fast --device <dev> --workers <n> --batch <b> -o <out>``:
the same functions of ``pocketcompare.cli`` (``_gpu_prep`` / ``featurize_batch`` / ``_gpu_post``, the GPU loop of
``run_gpu``) and the same output files (``<out>`` + ``<out>.structures.parquet``, written with
``pocketcompare.fpindex.write_table``). The only difference is that the GPU context and the pool of CPU workers
live across requests, which removes the ~12 s start-up of every ``pocketcompare describe`` call (measured: 500
structures 13.6 s, 2,000 structures 18.4 s on one GPU + 15 workers). One JSON line per request is answered on
stdout, prefixed with ``@@``.  ``--self-check`` describes a directory once and exits.

A structure whose CPU task does not return within ``--struct-timeout`` seconds aborts the request with an error
(the worker then restarts the server and retries the batch, or falls back to the CLI).
"""
from __future__ import annotations

import os

for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from collections import deque  # noqa: E402
from pathlib import Path  # noqa: E402


def log(*a):
    print(f"[describe_server {os.environ.get('PC_SHARD', '')} {time.strftime('%H:%M:%S')}]", *a, file=sys.stderr,
          flush=True)


def describe_dir(pool, inputs, out, opt, device, batch, fm, timeout):
    import numpy as np
    import pandas as pd
    from pocketdetect.burrow.fast.gpu import featurize_batch
    from pocketcompare import cli as C
    from pocketcompare import fpindex as FX
    paths = C.find_structures([inputs])
    if not paths:
        raise RuntimeError(f"no structure files in {inputs}")
    tasks = [(str(p), opt) for p in paths]
    t0 = time.perf_counter()
    results = []                                    # == cli.run_gpu with a persistent pool
    prep = pool.imap(C._gpu_prep, tasks, chunksize=1)
    post = deque()
    buf = []

    def flush():
        t1 = time.perf_counter()
        res = featurize_batch([b[1] for b in buf], fm.cfg, device, fm)
        dt = time.perf_counter() - t1
        for (path, it, info), (ps, sc) in zip(buf, res):
            info["gpu_s"] = dt / len(buf)
            post.append(pool.apply_async(C._gpu_post, ((path, it.P, ps, sc, info, opt),)))
        buf.clear()

    for _ in range(len(tasks)):
        path, it, info, err = prep.next(timeout=timeout)
        if err:
            results.append(C._gpu_error(path, err, opt))
            continue
        buf.append((path, it, info))
        if len(buf) >= batch:
            flush()
        while post and post[0].ready():
            results.append(post.popleft().get())
    if buf:
        flush()
    while post:
        results.append(post.popleft().get(timeout=timeout))
    wall = time.perf_counter() - t0
    # == cli.cmd_describe output
    keep = [r for r in results if len(r[0])]
    meta = pd.concat([r[0] for r in keep], ignore_index=True) if keep else pd.DataFrame()
    V = np.vstack([r[1] for r in keep]) if keep else np.zeros((0, C._method().dim), np.float32)
    rec = FX.method_record(C._method())
    rec.update(af_mode=opt["af_mode"], backend=opt["backend"], device=device, unit=opt["unit"],
               min_points=opt["min_points"], site=None, locate=opt["locate"])
    FX.write_table(out, meta, V, rec)
    st = pd.DataFrame([r[3] for r in results])
    st.to_parquet(Path(str(out).removesuffix(".parquet") + ".structures.parquet"), index=False)
    n_err = int((st.status != "ok").sum()) if len(st) else 0
    return {"n_structures": len(paths), "n_pockets": int(len(meta)), "n_errors": n_err, "wall_s": wall}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", required=True)
    ap.add_argument("--workers", type=int, default=15)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--min-points", type=int, default=10)
    ap.add_argument("--struct-timeout", type=float, default=1800.0)
    ap.add_argument("--maxtasksperchild", type=int, default=50_000)
    ap.add_argument("--self-check", nargs=2, metavar=("DIR", "OUT"))
    a = ap.parse_args()
    from pocketcompare import cli as C
    from pocketcompare import pockets_fast as pf
    import torch
    torch.set_num_threads(1)
    fm = pf.fast_model()
    C._method()
    # == cli._opt_from_args for `describe --af-mode --backend fast --device cuda:N` (no site, default unit/locate)
    opt = {"af_mode": True, "chains": None, "backend": "fast", "site": None, "locate": "shell", "unit": "merged",
           "min_points": a.min_points, "n1": False}
    ctx = mp.get_context("spawn")
    t0 = time.time()
    with ctx.Pool(a.workers, initializer=C._worker_init, maxtasksperchild=a.maxtasksperchild) as pool:
        if a.self_check:
            r = describe_dir(pool, a.self_check[0], a.self_check[1], opt, a.device, a.batch, fm, a.struct_timeout)
            log(json.dumps(r))
            return
        log(f"ready on {a.device} with {a.workers} workers ({time.time() - t0:.1f} s)")
        print("@@" + json.dumps({"ready": True}), flush=True)
        for line in sys.stdin:
            if not line.strip():
                continue
            req = json.loads(line)
            try:
                r = describe_dir(pool, req["inputs"], req["out"], opt, a.device, a.batch, fm, a.struct_timeout)
                r.update(id=req.get("id"), ok=True)
            except Exception as e:  # noqa: BLE001
                r = {"id": req.get("id"), "ok": False, "error": f"{type(e).__name__}: {e}"[:500]}
                print("@@" + json.dumps(r), flush=True)
                log("request failed, exiting:", r["error"])
                pool.terminate()
                sys.exit(3)
            print("@@" + json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
