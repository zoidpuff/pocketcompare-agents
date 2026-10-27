#!/usr/bin/env python
"""AFDB proteome demo, stage 1: BURROW (AF mode, region rule) + ligand-free tier-1 descriptors for every model.

    python scripts/proteome/run_proteome.py --out data/processed/proteome_human/run_gpu \
        --backend gpu --devices cuda:2,cuda:3 --workers-per-gpu 11 --batch 32
    python scripts/proteome/run_proteome.py --out .../bench_ref --backend refcpu --workers 22 --limit 1000 --sample 0

Inputs: members.parquet from ``index_tar.py`` (models are read from the tarball by byte offset; nothing is
extracted except one temporary uncompressed file per structure in local /tmp, deleted after parsing).

Backends:
* ``gpu``    -- one runner process per GPU, each owning ``--workers-per-gpu`` CPU processes that read + parse +
                AF-prune + prepare structures, while the GPU featurises/scores batches of ``--batch`` structures
                (``pocketdetect.burrow.fast.gpu.featurize_batch``); the CPU workers then run pocket formation,
                ranking, the region rule (``pocketcompare.pockets_fast``), the merge and the descriptors.
* ``fastcpu`` -- fast Numba CPU path end-to-end in ``--workers`` processes.
* ``refcpu`` -- reference adapter ``pockets.featurize_structure`` (BURROW reference implementation).
All three give identical points/features/pockets (scripts/proteome/check_fast_equivalence.py).

Per pocket (merged region-rule pocket with >= 10 points): uniprot, fragment, ranks, score, n points, volume, sph8
site size, centre, lining residues (UniProt numbering), mean/min pLDDT of the lining residues; raw A1(sph8) (514 d)
and env(sph8) (113 d) in float32 shards.  Per structure: atoms, points, pocket counts and stage timings.

Output: OUT/shards/<runner>_<k>.{pockets.parquet,structs.parquet,desc.npz}; OUT/run.json; marker OUT/DONE.
Resumable: structures present in existing shards are skipped.
"""
from __future__ import annotations

import os

_SINGLE = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS",
                            "NUMEXPR_NUM_THREADS")}
os.environ.update(_SINGLE)
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import gzip  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import socket  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from collections import deque  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "scripts/proteome"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

TAR = "/cluster/work/beltrao/shared/alphafold/v6/UP000005640_9606_HUMAN_v6.tar"
MEMBERS = ROOT / "data/processed/proteome_human/members.parquet"
TMP = Path(os.environ.get("PROTEOME_TMP", "/tmp/pocketcompare_proteome_tmp"))

# ------------------------------------------------------------------------------------------------ workers
_W: dict = {}


def _init_worker(tar, af_mode):
    os.environ.update(_SINGLE)
    import numba
    numba.set_num_threads(1)
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/proteome")]
    from pocketcompare import pockets_fast as pf
    _W.update(fh=open(tar, "rb"), af=af_mode, fm=pf.fast_model())
    TMP.mkdir(parents=True, exist_ok=True)


def _materialise(task) -> tuple[Path, int]:
    """Read one member by offset, write the uncompressed PDB to local /tmp; DBREF -> UniProt residue offset."""
    fh = _W["fh"]
    fh.seek(task["offset_data"])
    raw = gzip.decompress(fh.read(task["size"]))
    off = None
    for line in raw[:20000].split(b"\n"):
        if line.startswith(b"DBREF "):
            # 'DBREF  XXXX A    1  1400  UNP    A0A087WUL8 NBPFJ_HUMAN    201   1600' (the id code may
            # overflow its columns, so tokens, not fixed columns): seqBegin before 'UNP', dbBegin = 2nd last
            tok = line.split()
            try:
                i = tok.index(b"UNP")
                off = int(tok[-2]) - int(tok[i - 2])
            except (ValueError, IndexError):
                off = None
            break
    if off is None:            # AFDB convention: 1,400-aa fragments every 200 residues
        off = 200 * (int(task["fragment"]) - 1)
    p = TMP / f"{task['stem']}.{os.getpid()}.pdb"
    p.write_bytes(raw)
    return p, off


def _err(task, stage, e):
    return dict(stem=task["stem"], status="error", error=f"{stage}: {type(e).__name__}: {str(e)[:200]}")


def prep_task(task):
    from pocketcompare import pockets_fast as pf
    t0 = time.perf_counter()
    try:
        p, off = _materialise(task)
        t1 = time.perf_counter()
        try:
            it, info = pf.load_and_prep(p, task["stem"], af_mode=_W["af"], fm=_W["fm"])
        finally:
            p.unlink(missing_ok=True)
        info.update(read_s=t1 - t0, res_offset=off)
        return task, it, info, None
    except Exception as e:  # noqa: BLE001
        return task, None, None, _err(task, "prep", e)


def _finish(task, fs, info, t_burrow_post):
    from proteome_lib import describe_structure
    d = describe_structure(fs, info["plddt"], info["res_offset"])
    pl = np.array(list(info["plddt"].values()), np.float32)
    struct = dict(stem=task["stem"], uniprot=task["uniprot"], fragment=int(task["fragment"]),
                  n_fragments=int(task["n_fragments"]), status="ok", error="", res_offset=int(info["res_offset"]),
                  n_res=int(len(pl)), plddt_mean=float(pl.mean()) if len(pl) else np.nan,
                  n_res_pruned=int(info["n_res_pruned"]), n_atoms=int(len(fs.atom_xyz)), n_points=int(len(fs.points)),
                  n_full=d["n_full"], n_region=d["n_region"], n_merged=d["n_merged"], n_kept=len(d["records"]),
                  n_small=d["n_small"], n_metal_single=d["n_metal_single"], n_empty_site=d["n_empty_site"],
                  t_read_s=info["read_s"], t_parse_s=info["parse_s"], t_prep_s=info.get("prep_s", 0.0),
                  t_feat_s=info.get("feat_s", 0.0), t_burrow_post_s=t_burrow_post,
                  t_merge_s=d["t_merge_s"], t_desc_s=d["t_desc_s"], device=info.get("device", "cpu"))
    for r in d["records"]:
        r.update(stem=task["stem"], uniprot=task["uniprot"], fragment=int(task["fragment"]))
    a1 = np.stack(d["a1"]).astype(np.float32) if d["a1"] else np.zeros((0, 514), np.float32)
    env = np.stack(d["env"]).astype(np.float32) if d["env"] else np.zeros((0, 113), np.float32)
    return dict(struct=struct, pockets=d["records"], a1=a1, env=env)


def post_task(args):
    task, P, ps, score, info = args
    from pocketcompare import pockets_fast as pf
    try:
        t0 = time.perf_counter()
        fs = pf.featurized_from_points(P, ps, score, _W["fm"], task["stem"], _W["af"])
        return _finish(task, fs, info, time.perf_counter() - t0)
    except Exception as e:  # noqa: BLE001
        return dict(struct=_err(task, "post", e), pockets=[], a1=None, env=None)


def cpu_task(args):
    """Whole structure on the CPU: backend 'fastcpu' (Numba fast path) or 'refcpu' (reference adapter)."""
    task, backend = args
    from pocketcompare import pockets as pk
    from pocketcompare import pockets_fast as pf
    try:
        t0 = time.perf_counter()
        p, off = _materialise(task)
        t1 = time.perf_counter()
        try:
            if backend == "refcpu":
                _, _, pld, npr = pf.load_protein_af(p, task["stem"], _W["af"])     # pLDDT table only
                t2 = time.perf_counter()
                fs = pk.featurize_structure(p, af_mode=_W["af"], key=task["stem"])
                tm = fs.meta["timings"]
                parse_s = (t2 - t1) + tm["load_s"]
                feat_s, post_s = tm["points_s"], tm["pockets_s"]
            else:
                from pocketdetect.burrow.fast.pipeline import featurize
                P, w, pld, npr = pf.load_protein_af(p, task["stem"], _W["af"])
                t2 = time.perf_counter()
                ps = featurize(P, _W["fm"].cfg, w)
                t3 = time.perf_counter()
                fs = pf.featurized_from_points(P, ps, None, _W["fm"], task["stem"], _W["af"])
                parse_s, feat_s, post_s = t2 - t1, t3 - t2, time.perf_counter() - t3
        finally:
            p.unlink(missing_ok=True)
        info = dict(plddt=pld, res_offset=off, n_res_pruned=npr, read_s=t1 - t0, parse_s=parse_s, feat_s=feat_s,
                    device=backend)
        return _finish(task, fs, info, post_s)
    except Exception as e:  # noqa: BLE001
        return dict(struct=_err(task, backend, e), pockets=[], a1=None, env=None)


# ------------------------------------------------------------------------------------------------ shards
class ShardWriter:
    def __init__(self, out: Path, name: str, size: int):
        self.dir = out / "shards"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.name, self.size = name, size
        self.k = len(list(self.dir.glob(f"{name}_*.structs.parquet")))
        self.buf: list = []

    def add(self, res):
        self.buf.append(res)
        if len(self.buf) >= self.size:
            self.flush()

    def flush(self):
        if not self.buf:
            return
        stem = self.dir / f"{self.name}_{self.k:05d}"
        ok = [r for r in self.buf if r["a1"] is not None]
        a1 = np.concatenate([r["a1"] for r in ok]) if ok else np.zeros((0, 514), np.float32)
        env = np.concatenate([r["env"] for r in ok]) if ok else np.zeros((0, 113), np.float32)
        pockets = pd.DataFrame([p for r in ok for p in r["pockets"]])
        np.savez(str(stem) + ".desc.npz", a1=a1, env=env)
        pockets.to_parquet(str(stem) + ".pockets.parquet", index=False)
        pd.DataFrame([r["struct"] for r in self.buf]).to_parquet(str(stem) + ".structs.parquet", index=False)  # last
        self.k += 1
        self.buf = []


# ------------------------------------------------------------------------------------------------ runners
def gpu_runner(device, tasks, out, workers, batch, af_mode, shard, prof_file):
    os.environ.update(_SINGLE)
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/proteome")]
    import torch
    torch.set_num_threads(1)
    from pocketcompare import pockets_fast as pf
    from pocketdetect.burrow.fast.gpu import featurize_batch
    fm = pf.fast_model()
    T = dict(device=device, n=len(tasks), start=time.time())
    writer = ShardWriter(Path(out), device.replace(":", ""), shard)
    ctx = mp.get_context("spawn")
    gpu_s = wait_prep_s = 0.0
    n_batches = 0
    with ctx.Pool(workers, initializer=_init_worker, initargs=(TAR, af_mode)) as pool:
        todo = deque(tasks)
        window = max(2 * batch, 2 * workers)
        prep_q, post_q = deque(), deque()

        def fill():
            while len(prep_q) < window and todo:
                prep_q.append(pool.apply_async(prep_task, (todo.popleft(),)))

        def drain(block_until: int):
            while post_q and (post_q[0].ready() or len(post_q) > block_until):
                writer.add(post_q.popleft().get())

        fill()
        buf = []

        def flush():
            nonlocal gpu_s, n_batches
            t0 = time.perf_counter()
            res = featurize_batch([b[1] for b in buf], fm.cfg, device, fm)
            dt = time.perf_counter() - t0
            gpu_s += dt
            n_batches += 1
            for (task, it, info), (ps, sc) in zip(buf, res):
                info.update(feat_s=dt / len(buf), device=device)
                post_q.append(pool.apply_async(post_task, ((task, it.P, ps, sc, info),)))
            buf.clear()

        while prep_q:
            t0 = time.perf_counter()
            task, it, info, err = prep_q.popleft().get()
            wait_prep_s += time.perf_counter() - t0
            fill()
            if err:
                writer.add(dict(struct=err, pockets=[], a1=None, env=None))
                continue
            buf.append((task, it, info))
            if len(buf) >= batch:
                flush()
                drain(window)
        if buf:
            flush()
        drain(0)
        writer.flush()
    T.update(end=time.time(), gpu_featurize_s=gpu_s, wait_prep_s=wait_prep_s, n_batches=n_batches)
    with open(prof_file, "a") as f:
        f.write(json.dumps(T) + "\n")


def cpu_runner(backend, tasks, out, workers, af_mode, shard):
    writer = ShardWriter(Path(out), backend, shard)
    with mp.get_context("spawn").Pool(workers, initializer=_init_worker, initargs=(TAR, af_mode)) as pool:
        for r in pool.imap_unordered(cpu_task, [(t, backend) for t in tasks], chunksize=1):
            writer.add(r)
    writer.flush()


# ------------------------------------------------------------------------------------------------ main
def done_stems(out: Path) -> set:
    s = set()
    for f in (out / "shards").glob("*.structs.parquet"):
        s |= set(pd.read_parquet(f, columns=["stem"]).stem)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--backend", choices=["gpu", "fastcpu", "refcpu"], default="gpu")
    ap.add_argument("--devices", default="cuda:2,cuda:3")
    ap.add_argument("--workers-per-gpu", type=int, default=11)
    ap.add_argument("--workers", type=int, default=22, help="CPU backends")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--shard", type=int, default=500)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None, help="seed: random --limit models instead of the first")
    ap.add_argument("--no-af-mode", action="store_true")
    a = ap.parse_args()
    out = a.out if a.out.is_absolute() else ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "DONE").unlink(missing_ok=True)
    m = pd.read_parquet(MEMBERS)
    if a.limit:
        m = m.sample(a.limit, random_state=a.sample) if a.sample is not None else m.iloc[:a.limit]
    done = done_stems(out)
    todo = m[~m.stem.isin(done)]
    # largest first inside each runner -> fewer stragglers at the end
    todo = todo.sort_values("size", ascending=False)
    tasks = todo[["stem", "uniprot", "fragment", "n_fragments", "offset_data", "size"]].to_dict("records")
    af = not a.no_af_mode
    print(f"{len(m)} models, {len(done)} already done, {len(tasks)} to run; backend {a.backend}", flush=True)
    t0 = time.time()
    load0 = os.getloadavg()
    prof = out / "runners.jsonl"
    if a.backend == "gpu":
        devs = a.devices.split(",")
        ctx = mp.get_context("spawn")
        procs = [ctx.Process(target=gpu_runner, args=(d, tasks[i::len(devs)], str(out), a.workers_per_gpu, a.batch,
                                                      af, a.shard, str(prof))) for i, d in enumerate(devs)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        n_workers = a.workers_per_gpu * len(devs)
        ok = all(p.exitcode == 0 for p in procs)
    else:
        cpu_runner(a.backend, tasks, str(out), a.workers, af, a.shard)
        devs, n_workers, ok = [], a.workers, True
    wall = time.time() - t0
    info = dict(backend=a.backend, devices=devs, cpu_workers=n_workers, batch=a.batch, af_mode=af,
                n_models_selected=len(m), n_run_now=len(tasks), wall_s=wall, host=socket.gethostname(),
                loadavg_start=load0, loadavg_end=os.getloadavg(), started=time.strftime("%F %T", time.localtime(t0)),
                runners_ok=ok, argv=sys.argv)
    runs = json.loads((out / "run.json").read_text()) if (out / "run.json").exists() else []
    runs.append(info)
    (out / "run.json").write_text(json.dumps(runs, indent=1))
    if ok:
        (out / "DONE").write_text(time.strftime("%F %T\n"))
    print(json.dumps(info, indent=1), flush=True)


if __name__ == "__main__":
    main()
