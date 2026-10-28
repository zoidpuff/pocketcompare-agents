#!/usr/bin/env python
"""One AFDB worker per node: claim work units in worklist order, describe every pocket, write per-unit outputs.

    python afdb/worker.py                                  # all tiers, until the work list is exhausted
    python afdb/worker.py --tiers 1 --max-units 2          # testing
    python afdb/worker.py --dry-run --max-units 10         # show what would be claimed
    python afdb/worker.py --unit-ids 17,42 --retry-failed  # re-run failed units

Pipeline on one node (64 cores, 4 GPUs):
  * EXTRACT_THREADS extraction threads claim units (atomic mkdir OUT_ROOT/state/claims/<unit_id>) and stream their
    members (local tar: by byte offset from OUT_ROOT/tar_index; GCS tar: HTTPS, small tars fetched in parallel
    into memory, large ones streamed in tarfile 'r|' mode with restart-and-skip on errors) into $TMPDIR batch
    directories of <= BATCH_STRUCTURES models. Non-.cif.gz members and accessions of earlier tiers are skipped.
  * One slot per GPU runs the frozen method on each batch: ``pocketcompare describe --af-mode --backend fast
    --device cuda:<g> --workers WORKERS_PER_SHARD --batch GPU_BATCH`` (``--runner cli``: a subprocess per batch;
    ``--runner persistent``, the default: describe_server.py, the same code path with a long-lived GPU context and
    worker pool). Extraction of the next batches overlaps describing the current ones (PREFETCH_BATCHES).
  * A finaliser applies the pocket filters, adds metadata and writes (tmp + rename)
      OUT_ROOT/pockets/tier<T>/<unit_id:06d>.parquet     pockets (metadata + fp16 fingerprint)
      OUT_ROOT/structures/tier<T>/<unit_id:06d>.parquet  one row per structure
      OUT_ROOT/state/done/<unit_id>.json                 counts, filter drops, timings, throughput
    and releases the claim. Failed units get OUT_ROOT/state/failed/<unit_id>.json (re-run with --retry-failed).
Stale claims (SLURM job no longer in squeue, a dead local pid, or older than --stale-hours) are reclaimed.
SIGUSR1 (sent by afdb.sbatch shortly before the time limit): stop claiming, finish what is in flight.
SIGTERM/SIGINT: release unfinished claims and exit (a resubmitted job picks them up).
"""
from __future__ import annotations

import os

for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "1")

import argparse  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import queue  # noqa: E402
import select  # noqa: E402
import shutil  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tarfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
import uuid  # noqa: E402
from collections import deque  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from afdb_common import (DIM, atomic_write_json, atomic_write_parquet, cif_stats, env, gcs_base_url,  # noqa: E402
                         fc_extract_chunk, out_root, parse_model_name, slurm_ids, source_label,
                         tar_index_dir)

HERE = Path(__file__).resolve().parent
STOP_CLAIMING = threading.Event()
ABORT = threading.Event()


def log(*a):
    print(f"[worker {os.environ.get('SLURM_ARRAY_TASK_ID', '-')} {time.strftime('%Y-%m-%d %H:%M:%S')}]", *a,
          file=sys.stderr, flush=True)


# ============================================================================================ claims
class Claims:
    def __init__(self, root: Path, stale_hours: float):
        self.root = root
        self.cdir, self.ddir, self.fdir = (root / "state" / x for x in ("claims", "done", "failed"))
        for d in (self.cdir, self.ddir, self.fdir):
            d.mkdir(parents=True, exist_ok=True)
        self.stale_s = stale_hours * 3600
        self.me = slurm_ids()
        self.mine: set[int] = set()
        self.lock = threading.Lock()
        self._sq: dict[str, tuple[float, bool]] = {}

    def is_done(self, uid: int) -> bool:
        return (self.ddir / f"{uid}.json").exists()

    def is_failed(self, uid: int) -> bool:
        return (self.fdir / f"{uid}.json").exists()

    def _job_running(self, jid: str) -> bool | None:
        now = time.time()
        c = self._sq.get(jid)
        if c and now - c[0] < 120:
            return c[1]
        try:
            r = subprocess.run(["squeue", "-h", "-j", jid, "-o", "%T"], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return None                                 # no squeue here: unknown
        if r.returncode != 0 and "Invalid job id" not in r.stderr:
            return None
        run = bool(r.stdout.strip())
        self._sq[jid] = (now, run)
        return run

    def stale(self, uid: int) -> str | None:
        """Reason why an existing claim is stale, or None if it looks alive."""
        try:
            c = json.loads((self.cdir / str(uid) / "claim.json").read_text())
        except (OSError, ValueError):
            try:
                age = time.time() - (self.cdir / str(uid)).stat().st_mtime
            except OSError:
                return "vanished"
            return "no claim.json" if age > 600 else None      # being written right now
        if time.time() - c.get("t", 0) > self.stale_s:
            return f"older than {self.stale_s / 3600:.0f} h"
        jid = c.get("slurm_job_id")
        if jid:
            if jid == self.me["slurm_job_id"] and c.get("pid") != self.me["pid"]:
                return "previous run of this job"
            run = self._job_running(jid)
            if run is False:
                return f"job {jid} not running"
            return None
        if c.get("host") == self.me["host"]:
            try:
                os.kill(int(c["pid"]), 0)
                return None
            except ProcessLookupError:
                return f"pid {c['pid']} dead"
            except (PermissionError, KeyError, ValueError):
                return None
        return None

    def try_claim(self, uid: int, retry_failed: bool) -> bool:
        if self.is_done(uid) or (self.is_failed(uid) and not retry_failed):
            return False
        d = self.cdir / str(uid)
        try:
            d.mkdir()
        except FileExistsError:
            why = self.stale(uid)
            if why is None:
                return False
            trash = self.cdir / f".stale_{uid}_{uuid.uuid4().hex[:8]}"
            try:
                d.rename(trash)                         # only one reclaimer wins the rename
            except OSError:
                return False
            shutil.rmtree(trash, ignore_errors=True)
            log(f"unit {uid}: reclaiming stale claim ({why})")
            try:
                d.mkdir()
            except FileExistsError:
                return False
        if self.is_done(uid):                           # finished between the check and the mkdir
            shutil.rmtree(d, ignore_errors=True)
            return False
        atomic_write_json(d / "claim.json", {**self.me, "unit_id": uid, "t": time.time(),
                                             "time": time.strftime("%Y-%m-%dT%H:%M:%S")})
        with self.lock:
            self.mine.add(uid)
        if retry_failed:
            (self.fdir / f"{uid}.json").unlink(missing_ok=True)
        return True

    def release(self, uid: int):
        d = self.cdir / str(uid)
        trash = self.cdir / f".done_{uid}_{uuid.uuid4().hex[:8]}"
        try:
            d.rename(trash)
            shutil.rmtree(trash, ignore_errors=True)
        except OSError:
            pass
        with self.lock:
            self.mine.discard(uid)

    def release_all(self):
        for uid in list(self.mine):
            self.release(uid)


class UnitSource:
    """Hands out unit rows in worklist order; claims are taken lazily by the extraction threads."""

    def __init__(self, wl: pd.DataFrame, claims: Claims, retry_failed: bool, max_units: int | None):
        self.rows = wl.to_dict("records")
        self.claims, self.retry_failed, self.max_units = claims, retry_failed, max_units
        self.pos, self.n, self.rescanned = 0, 0, False
        self.lock = threading.Lock()
        done = {int(p.stem) for p in claims.ddir.glob("*.json") if p.stem.isdigit()}
        self.done0 = done

    def next(self):
        with self.lock:
            while not STOP_CLAIMING.is_set():
                if self.max_units is not None and self.n >= self.max_units:
                    return None
                if self.pos >= len(self.rows):
                    if self.rescanned:
                        return None
                    self.pos, self.rescanned = 0, True       # second pass: pick up stale claims behind us
                    self.done0 = {int(p.stem) for p in self.claims.ddir.glob("*.json") if p.stem.isdigit()}
                r = self.rows[self.pos]
                self.pos += 1
                uid = int(r["unit_id"])
                if uid in self.done0:
                    continue
                if self.claims.try_claim(uid, self.retry_failed):
                    self.n += 1
                    return r
            return None


# ============================================================================================ units and batches
class Unit:
    def __init__(self, row: dict, work: Path):
        self.row = row
        self.uid = int(row["unit_id"])
        self.tier = int(row["tier"])
        self.work = work / f"u{self.uid:06d}"
        self.work.mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        self.lock = threading.Lock()
        self.submitted = 0                    # batches queued
        self.finished = 0                     # batches processed (or dropped) by the slots
        self.extract_done = False
        self.finalised = False
        self.done_batches: list = []
        self.failed = None
        self.meta: dict[str, dict] = {}       # stem -> per-structure metadata
        self.ext = dict(members_seen=0, non_model=0, skipped_earlier_tier=0, duplicates=0, extracted=0,
                        bytes=0, extract_s=0.0, http_retries=0, sources=len(row["sources"]))
        self.describe_s = 0.0

    def maybe_finish(self, fin: "Finaliser"):
        """Hand the unit to the finaliser once extraction has ended and no batch is in flight (exactly once)."""
        with self.lock:
            if self.finalised or not self.extract_done or self.finished < self.submitted:
                return
            self.finalised = True
        fin.submit(self)


class Batch:
    def __init__(self, unit: Unit, k: int):
        self.unit, self.k = unit, k
        self.dir = unit.work / f"b{k:03d}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.out = unit.work / f"b{k:03d}.parquet"
        self.stems: list[str] = []
        self.attempts = 0


# ============================================================================================ extraction
class RangeReader:
    """Members of a local tar by (offset, size), read in large sequential chunks: the .cif.gz members are
    interleaved with .pdb.gz members, and one seek + small read per member is 4x slower on the shared file
    system (measured 370 vs 1,600 models/s per thread)."""

    def __init__(self, fh, chunk: int = 64 << 20):
        self.fh, self.chunk, self.pos, self.buf = fh, chunk, 0, b""

    def read(self, off: int, size: int) -> bytes:
        end = off + size
        if not (self.pos <= off and end <= self.pos + len(self.buf)):
            keep = self.buf[off - self.pos:] if self.pos <= off < self.pos + len(self.buf) else b""
            self.fh.seek(off + len(keep))
            self.buf = keep + self.fh.read(max(self.chunk, size - len(keep)))
            self.pos = off
            if len(self.buf) < size:
                raise IOError(f"short read at offset {off}")
        return self.buf[off - self.pos:end - self.pos]


class Extractor:
    def __init__(self, a, root: Path, work: Path, skip: dict, bq: queue.Queue, fin: "Finaliser", fc_pool=None):
        self.a, self.root, self.work, self.skip, self.bq, self.fin = a, root, work, skip, bq, fin
        self.fc_pool = fc_pool
        self._fc: dict = {}                              # entries file -> (ParquetFile, rg unit ranges, lock)
        self._fc_taxa: dict = {}
        self._idx: dict[str, pd.DataFrame] = {}
        self._idx_lock = threading.Lock()
        self._token = (None, 0.0)
        self.http = ThreadPoolExecutor(a.gcs_fetch_threads, thread_name_prefix="http")

    # ---- local tars
    def tar_index(self, path: str) -> pd.DataFrame:
        with self._idx_lock:
            if path not in self._idx:
                self._idx[path] = pd.read_parquet(tar_index_dir(self.root) / (Path(path).name + ".parquet"))
                if len(self._idx) > 8:
                    self._idx.pop(next(iter(self._idx)))
            return self._idx[path]

    def local_members(self, u: Unit):
        r = u.row
        idx = self.tar_index(r["source"])
        sl = idx.iloc[int(r["member_start"]):int(r["member_end"])]
        with open(r["source"], "rb", buffering=0) as fh:
            rd = RangeReader(fh)
            for name, off, size in zip(sl.name, sl.offset_data, sl["size"]):
                yield r["source"], name, rd.read(int(off), int(size)), int(r["taxid"])

    # ---- GCS tars
    def _headers(self):
        cmd = env("GCS_AUTH_CMD", "")
        if not cmd:
            return {}
        tok, t = self._token
        if tok is None or time.time() - t > 1800:
            tok = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True).stdout.strip()
            self._token = (tok, time.time())
        return {"Authorization": f"Bearer {tok}"}

    def _url(self, name: str) -> str:
        u = f"{gcs_base_url()}/{urllib.parse.quote(name)}"
        up = env("GCS_USER_PROJECT", "")
        return u + (f"?userProject={up}" if up else "")

    def _open(self, name: str):
        req = urllib.request.Request(self._url(name), headers=self._headers())
        return urllib.request.urlopen(req, timeout=self.a.http_timeout)

    def _fetch(self, name: str, u: Unit) -> bytes:
        for k in range(self.a.http_retries):
            try:
                with self._open(name) as r:
                    return r.read()
            except Exception as e:  # noqa: BLE001
                if ABORT.is_set():
                    raise
                code = getattr(e, "code", None)
                u.ext["http_retries"] += 1
                if code in (401, 403, 404) and k >= 1:
                    raise RuntimeError(f"GCS {name}: HTTP {code} ({e})") from e
                log(f"unit {u.uid}: fetch {name}: {e} (attempt {k + 1}/{self.a.http_retries})")
                time.sleep(min(120, 5 * 2 ** k))
        raise RuntimeError(f"GCS {name}: failed after {self.a.http_retries} attempts")

    def _stream(self, name: str, u: Unit, taxid: int):
        """Stream a large tar in 'r|' mode; on an error restart the download and skip members already seen."""
        seen = 0
        for k in range(self.a.http_retries):
            try:
                with self._open(name) as r, tarfile.open(fileobj=r, mode="r|") as tf:
                    i = 0
                    for m in tf:
                        if i < seen or not m.isfile():
                            i += 1
                            continue
                        data = tf.extractfile(m).read() if m.name.endswith(".cif.gz") else None
                        i += 1
                        seen = i
                        yield name, m.name, data, taxid
                return
            except Exception as e:  # noqa: BLE001
                if ABORT.is_set():
                    raise
                u.ext["http_retries"] += 1
                if getattr(e, "code", None) in (401, 403, 404) and k >= 1:
                    raise RuntimeError(f"GCS {name}: HTTP {e.code}") from e
                log(f"unit {u.uid}: stream {name} at member {seen}: {e} (attempt {k + 1}/{self.a.http_retries})")
                time.sleep(min(120, 5 * 2 ** k))
        raise RuntimeError(f"GCS {name}: stream failed after {self.a.http_retries} attempts")

    def gcs_members(self, u: Unit):
        r = u.row
        names, taxids = list(r["sources"]), [int(t) for t in r["source_taxids"]]
        sizes = r.get("source_sizes")
        sizes = [int(x) for x in sizes] if sizes is not None else [0] * len(names)
        small = [(n, t) for n, t, s in zip(names, taxids, sizes) if 0 < s <= self.a.gcs_small_bytes]
        large = [(n, t) for n, t, s in zip(names, taxids, sizes) if not (0 < s <= self.a.gcs_small_bytes)]
        futs = deque(self.http.submit(self._fetch, n, u) for n, _ in small[:2 * self.a.gcs_fetch_threads])
        pending = deque(small[2 * self.a.gcs_fetch_threads:])
        for n, t in small:
            data = futs.popleft().result()
            if pending:
                futs.append(self.http.submit(self._fetch, pending.popleft()[0], u))
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tf:
                for m in tf:
                    if m.isfile():
                        yield n, m.name, (tf.extractfile(m).read() if m.name.endswith(".cif.gz") else None), t
        for n, t in large:
            yield from self._stream(n, u, t)

    # ---- Foldcomp database
    def fc_entries(self, u: Unit) -> pd.DataFrame:
        import pyarrow.parquet as pq
        f = str(self.root / u.row["sources"][0])
        with self._idx_lock:
            if f not in self._fc:
                pf = pq.ParquetFile(f)
                rg = []
                for i in range(pf.num_row_groups):
                    st = pf.metadata.row_group(i).column(0).statistics      # column 0 = fc_unit (sorted)
                    rg.append((int(st.min), int(st.max)))
                self._fc[f] = (pf, rg, threading.Lock())
            pf, rg, lk = self._fc[f]
        k = int(u.row["member_start"])
        groups = [i for i, (lo, hi) in enumerate(rg) if lo <= k <= hi]
        with lk:
            t = pf.read_row_groups(groups)
        df = t.to_pandas()
        return df[df.fc_unit == k].sort_values("off").reset_index(drop=True)

    def fc_taxa(self, db: str) -> dict:
        with self._idx_lock:
            if db not in self._fc_taxa:
                p = self.root / f"fc_taxa_{db}.parquet"
                t = pd.read_parquet(p, columns=["taxid", "tax_name"]) if p.exists() else pd.DataFrame(
                    columns=["taxid", "tax_name"])
                self._fc_taxa[db] = dict(zip(t.taxid.astype(int), t.tax_name, strict=True))
            return self._fc_taxa[db]

    def run_unit_fc(self, u: Unit):
        """Foldcomp unit: entries -> process pool (pread + decompress + .pdb) -> batches."""
        t0 = time.time()
        db = u.row["source"]
        db_path = str(Path(env("FOLDCOMP_DIR", str(self.root / "foldcomp"))) / db)
        e = self.fc_entries(u)
        taxa = self.fc_taxa(db)
        u.ext["members_seen"] = len(e)
        skip = np.array([self.skip.get(x, 99) < u.tier for x in e.accession], bool)
        u.ext["skipped_earlier_tier"] = int(skip.sum())
        e = e[~skip].reset_index(drop=True)
        e["stem"] = [f"AF-{x}-F{f}-model_v{v}" for x, f, v in zip(e.accession, e.fragment, e.version, strict=True)]
        bs, ck = self.a.batch_structures, 64
        for k, s0 in enumerate(range(0, len(e), bs)):
            b = Batch(u, k)
            sub = e.iloc[s0:s0 + bs]
            rows = list(zip(sub.off.tolist(), sub.len.tolist(), sub.stem.tolist(), strict=True))
            tasks = [(db_path, str(b.dir), rows[i:i + ck]) for i in range(0, len(rows), ck)]
            res = self.fc_pool.map(fc_extract_chunk, tasks, chunksize=1)
            info = {r.stem: r for r in sub.itertuples(index=False)}
            for chunk in res:
                for stem, st, nb, err in chunk:
                    r = info[stem]
                    m = dict(accession=r.accession, fragment=int(r.fragment), model_version=int(r.version),
                             taxid=int(r.taxid), organism=taxa.get(int(r.taxid), ""), source_file=db,
                             **(st or {"n_res": -1, "plddt_mean": np.nan, "plddt_frac_lt70": np.nan,
                                       "plddt_frac_lt50": np.nan}))
                    if err:
                        m["pre_error"] = err
                    else:
                        b.stems.append(stem)
                        u.ext["extracted"] += 1
                        u.ext["bytes"] += nb
                    u.meta[stem] = m
            if ABORT.is_set():
                raise RuntimeError("aborted")
            if u.failed:
                raise RuntimeError(u.failed)
            if b.stems:
                self._put(b)
            else:
                shutil.rmtree(b.dir, ignore_errors=True)
        u.ext["extract_s"] = time.time() - t0

    # ---- the extraction loop of one unit
    def run_unit(self, u: Unit):
        if u.row["source_type"] == "foldcomp":
            return self.run_unit_fc(u)
        t0 = time.time()
        members = self.local_members(u) if u.row["source_type"] == "local_tar" else self.gcs_members(u)
        b = Batch(u, 0)
        nb = 0
        for source, name, data, taxid in members:
            if ABORT.is_set():
                raise RuntimeError("aborted")
            u.ext["members_seen"] += 1
            pm = parse_model_name(name) if data is not None else None
            if pm is None:
                u.ext["non_model"] += 1
                continue
            acc, frag, ver = pm
            if self.skip.get(acc, 99) < u.tier:
                u.ext["skipped_earlier_tier"] += 1
                continue
            base = Path(name).name
            stem = base[:-len(".cif.gz")]
            if stem in u.meta:
                u.ext["duplicates"] += 1
                continue
            (b.dir / base).write_bytes(data)
            st = cif_stats(data)
            u.meta[stem] = dict(accession=acc, fragment=frag, model_version=ver,
                                taxid=st["cif_taxid"] if st["cif_taxid"] > 0 else taxid,
                                organism=st["cif_organism"] or u.row.get("organism") or "", source_file=Path(source).name,
                                n_res=st["n_res"], plddt_mean=st["plddt_mean"],
                                plddt_frac_lt70=st["plddt_frac_lt70"], plddt_frac_lt50=st["plddt_frac_lt50"])
            u.ext["extracted"] += 1
            u.ext["bytes"] += len(data)
            b.stems.append(stem)
            if len(b.stems) >= self.a.batch_structures:
                self._put(b)
                nb += 1
                b = Batch(u, nb)
            if u.failed:                                 # a batch of this unit failed: stop extracting it
                raise RuntimeError(u.failed)
        if b.stems:
            self._put(b)
        else:
            shutil.rmtree(b.dir, ignore_errors=True)
        u.ext["extract_s"] = time.time() - t0

    def _put(self, b: Batch):
        with b.unit.lock:
            b.unit.submitted += 1
        self.bq.put(b)


# ============================================================================================ describe runners
class Slot:
    """One GPU: runs batches through describe_server.py (persistent) or `pocketcompare describe` (cli)."""

    def __init__(self, a, device: str, k: int):
        self.a, self.device, self.k = a, device, k
        self.proc = None
        self.env = dict(os.environ, PC_SHARD=f"slot{k}:{device}")

    def _start(self):
        cmd = [sys.executable, str(HERE / "describe_server.py"), "--device", self.device, "--workers",
               str(self.a.workers_per_shard), "--batch", str(self.a.gpu_batch), "--min-points", str(self.a.min_points)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=self.env,
                                     bufsize=1)
        r = self._read(timeout=900)
        if not r.get("ready"):
            raise RuntimeError(f"describe_server on {self.device} did not start: {r}")

    def _read(self, timeout: float) -> dict:
        end = time.time() + timeout
        while True:
            left = end - time.time()
            if left <= 0:
                raise TimeoutError(f"describe_server on {self.device}: no answer in {timeout:.0f} s")
            rl, _, _ = select.select([self.proc.stdout], [], [], min(left, 30))
            if not rl:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"describe_server on {self.device} exited ({self.proc.returncode})")
                continue
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError(f"describe_server on {self.device} exited ({self.proc.poll()})")
            if line.startswith("@@"):
                return json.loads(line[2:])

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=30)
            except Exception:  # noqa: BLE001
                self.proc.kill()
        self.proc = None

    def kill(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()

    def run_persistent(self, b: Batch) -> dict:
        if self.proc is None or self.proc.poll() is not None:
            self._start()
        self.proc.stdin.write(json.dumps({"id": f"{b.unit.uid}:{b.k}", "inputs": str(b.dir), "out": str(b.out)})
                              + "\n")
        self.proc.stdin.flush()
        r = self._read(timeout=600 + 2.0 * len(b.stems))
        if not r.get("ok"):
            self.stop()
            raise RuntimeError(r.get("error", "describe_server error"))
        return r

    def run_cli(self, b: Batch) -> dict:
        exe = Path(sys.executable).with_name("pocketcompare")
        cmd = [str(exe), "describe", str(b.dir), "--af-mode", "--backend", "fast", "--device", self.device,
               "--workers", str(self.a.workers_per_shard), "--batch", str(self.a.gpu_batch),
               "--min-points", str(self.a.min_points), "-o", str(b.out)]
        t0 = time.time()
        p = subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=900 + 2.0 * len(b.stems))
        if p.returncode != 0 or not b.out.exists():
            raise RuntimeError(f"pocketcompare describe rc={p.returncode}: {p.stderr[-800:]}")
        return {"ok": True, "wall_s": time.time() - t0}

    def run(self, b: Batch) -> dict:
        last = None
        tries = 1 + self.a.describe_retries
        for k in range(tries):
            b.attempts += 1
            # persistent runner: the last retry falls back to a plain `pocketcompare describe` subprocess
            use_cli = self.a.runner == "cli" or (k > 0 and k == tries - 1)
            try:
                return self.run_cli(b) if use_cli else self.run_persistent(b)
            except Exception as e:  # noqa: BLE001
                last = e
                log(f"unit {b.unit.uid} batch {b.k} on {self.device}: attempt {k + 1}/{tries} failed: {e}")
                self.kill()
                self.proc = None
        raise RuntimeError(f"describe failed: {last}")


# ============================================================================================ finalising a unit
class Finaliser:
    def __init__(self, a, root: Path, claims: Claims, stats: "Stats"):
        self.a, self.root, self.claims, self.stats = a, root, claims, stats
        self.q: queue.Queue = queue.Queue()
        self.th = threading.Thread(target=self.loop, name="finaliser", daemon=True)
        self.th.start()

    def submit(self, u: Unit):
        self.q.put(u)

    def loop(self):
        while True:
            u = self.q.get()
            if u is None:
                return
            try:
                if u.failed:
                    self.fail(u, u.failed)
                else:
                    self.finalise(u)
            except Exception as e:  # noqa: BLE001
                log(f"unit {u.uid}: finalise failed: {e}\n{traceback.format_exc()}")
                self.fail(u, f"finalise: {e}")
            finally:
                shutil.rmtree(u.work, ignore_errors=True)
                self.q.task_done()

    def fail(self, u: Unit, why: str):
        atomic_write_json(self.claims.fdir / f"{u.uid}.json", {"unit_id": u.uid, "tier": u.tier, "source_type": u.row["source_type"],
                                                               "source": u.row["source"], "error": str(why)[:2000],
                                                               **slurm_ids(), "extract": u.ext})
        self.claims.release(u.uid)
        self.stats.add_failed(u.uid)
        log(f"unit {u.uid} FAILED: {str(why)[:300]}")

    def finalise(self, u: Unit):
        import pyarrow as pa
        from pocketcompare import fpindex as FX
        a = self.a
        metas, Vs, sts, rec = [], [], [], {}
        for b in sorted(u.done_batches, key=lambda b: b.k):
            m, V, rec = FX.read_table(b.out)
            metas.append(m)
            Vs.append(V)
            sts.append(pd.read_parquet(str(b.out).removesuffix(".parquet") + ".structures.parquet"))
        meta = pd.concat(metas, ignore_index=True) if metas else pd.DataFrame()
        V = np.vstack(Vs) if Vs else np.zeros((0, DIM), np.float32)
        st = pd.concat(sts, ignore_index=True) if sts else pd.DataFrame(columns=["structure", "status", "error"])
        # ---- per-structure table
        st["stem"] = [Path(s).name.removesuffix(".gz").removesuffix(".cif").removesuffix(".pdb") for s in st.structure]
        sm = pd.DataFrame.from_dict(u.meta, orient="index")
        sm.index.name = "stem"
        S = sm.join(st.drop(columns=["structure"]).set_index("stem"), how="left")
        S["status"] = S["status"].fillna("missing")
        S["error"] = S["error"].fillna("")
        if "pre_error" in S:                              # Foldcomp entries that could not be decompressed
            pe = S.pop("pre_error")
            bad = pe.notna()
            S.loc[bad, "status"] = "error"
            S.loc[bad, "error"] = pe[bad]
        src = source_label(u.row)
        if "source_file" not in S:
            S["source_file"] = pd.Series(dtype=str)
        S.insert(S.columns.get_loc("source_file"), "source", src)
        # ---- pocket filters (applied in order; each pocket is counted under the first rule that drops it)
        n_all = len(meta)
        drops = {"min_points": f"applied inside describe_all (merged pockets with < {a.min_points} points are not "
                               "emitted; not counted)"}
        if n_all:
            meta["stem"] = meta["structure_stem"].astype(str)
            r_ok = meta["ok"].to_numpy(bool)
            r_score = meta["burrow_score"].to_numpy(float) >= a.min_score
            pl = meta["plddt_mean"].to_numpy(float)
            r_pl = np.nan_to_num(pl, nan=-1.0) >= a.min_plddt
            keep = r_ok & r_score & r_pl
            drops.update(not_describable=int((~r_ok).sum()), score_lt_min=int((r_ok & ~r_score).sum()),
                         plddt_lt_min=int((r_ok & r_score & ~r_pl).sum()),
                         any_score_lt_min=int((~r_score).sum()), any_plddt_lt_min=int((~r_pl).sum()))
            per_all = meta.groupby("stem").size()
            per_kept = meta[keep].groupby("stem").size()
        else:
            keep = np.zeros(0, bool)
            drops.update(not_describable=0, score_lt_min=0, plddt_lt_min=0, any_score_lt_min=0, any_plddt_lt_min=0)
            per_all = per_kept = pd.Series(dtype=int)
        S["n_pockets_all"] = per_all.reindex(S.index).fillna(0).astype(np.int32)
        S["n_pockets_kept"] = per_kept.reindex(S.index).fillna(0).astype(np.int32)
        S = S.reset_index()
        S.insert(0, "unit_id", np.int32(u.uid))
        S.insert(1, "tier", np.int8(u.tier))
        S = S.rename(columns={"stem": "structure_stem"})
        for c, t_ in (("fragment", np.int16), ("model_version", np.int8), ("taxid", np.int32), ("n_res", np.int32),
                      ("n_pockets", np.int32)):
            if c in S:
                S[c] = S[c].fillna(-1).astype(t_)
        # ---- pocket table: metadata + fp16 fingerprint
        P = meta[keep].reset_index(drop=True) if n_all else pd.DataFrame()
        Vk = V[keep] if n_all else np.zeros((0, DIM), np.float32)
        if len(P):
            sm2 = sm.reindex(P["stem"])
            P = P.drop(columns=[c for c in ("structure", "structure_stem", "mode", "ok", "stem") if c in P])
            lead = pd.DataFrame({"unit_id": np.int32(u.uid), "tier": np.int8(u.tier),
                                 "accession": sm2["accession"].to_numpy(),
                                 "fragment": sm2["fragment"].to_numpy(np.int16),
                                 "model_version": sm2["model_version"].to_numpy(np.int8),
                                 "taxid": sm2["taxid"].to_numpy(np.int32), "organism": sm2["organism"].to_numpy(),
                                 "source": src})
            P = pd.concat([lead, P], axis=1)
        t = pa.Table.from_pandas(P, preserve_index=False) if len(P) else pa.table({"unit_id": pa.array([], pa.int32())})
        H = np.ascontiguousarray(Vk, np.float16)
        fp = pa.FixedSizeListArray.from_arrays(pa.array(H.reshape(-1), pa.float16()), DIM)
        t = t.append_column("fingerprint", fp)
        info = {"unit_id": u.uid, "tier": u.tier, "filters": {"min_points": a.min_points, "min_score": a.min_score,
                                                              "min_plddt": a.min_plddt},
                "fingerprint": "fixed_size_list<halffloat>[384] (float16 of the unit-norm float32 fingerprint)"}
        md = {b"pocketcompare": json.dumps({**rec, "storage": "float16"}).encode(),
              b"pocketcompare_afdb": json.dumps(info).encode()}
        t = t.replace_schema_metadata(md)
        tier_dir = f"tier{u.tier}"
        atomic_write_parquet(self.root / "pockets" / tier_dir / f"{u.uid:06d}.parquet", t)
        atomic_write_parquet(self.root / "structures" / tier_dir / f"{u.uid:06d}.parquet",
                             pa.Table.from_pandas(S, preserve_index=False))
        wall = time.time() - u.t0
        n_s = len(S)
        n_ok = int((S.status == "ok").sum())
        done = {"unit_id": u.uid, "tier": u.tier, "source_type": u.row["source_type"], "source": u.row["source"],
                "structures": n_s, "structures_ok": n_ok, "structures_error": int(n_s - n_ok),
                "pockets_all": int(n_all), "pockets_kept": int(len(P)), "dropped": drops,
                "est_structures": int(u.row["est_structures"]), "extract": u.ext,
                "describe_s": round(u.describe_s, 1), "wall_s": round(wall, 1),
                "structures_per_s_unit_wall": round(n_s / wall, 2) if wall > 0 else None,
                "batches": len(u.done_batches), "runner": a.runner, **slurm_ids(),
                "errors_sample": S.loc[S.status != "ok", ["structure_stem", "error"]].head(5).to_dict("records")}
        atomic_write_json(self.claims.ddir / f"{u.uid}.json", done)
        self.claims.release(u.uid)
        self.stats.add_done(n_s, len(P))
        log(f"unit {u.uid} (tier {u.tier}, {u.row['code']}) done: {n_s} structures ({n_s - n_ok} errors), "
            f"{n_all} -> {len(P)} pockets, {wall:.0f} s")


# ============================================================================================ progress
class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.t0 = time.time()
        self.units = self.failed = self.structures = self.pockets = 0
        self.hist = deque()                               # (t, structures done so far)

    def add_done(self, n, p):
        with self.lock:
            self.units += 1
            self.structures += n
            self.pockets += p
            self.hist.append((time.time(), self.structures))

    def add_failed(self, uid):
        with self.lock:
            self.failed += 1

    def line(self, bq: queue.Queue, busy: int) -> str:
        with self.lock:
            now = time.time()
            while self.hist and now - self.hist[0][0] > 900:
                self.hist.popleft()
            rec = (self.structures - self.hist[0][1]) / max(1.0, now - self.hist[0][0]) if len(self.hist) > 1 else 0.0
            tot = self.structures / max(1.0, now - self.t0)
            return (f"progress: {self.units} units done ({self.failed} failed), {self.structures:,} structures, "
                    f"{self.pockets:,} pockets kept | rate {rec:.0f}/s (15 min), {tot:.0f}/s (job) | "
                    f"batches queued {bq.qsize()}, slots busy {busy}")


# ============================================================================================ main
def load_skip(root: Path) -> dict:
    p = root / "skip_accessions.txt"
    if not p.exists():
        return {}
    s = pd.read_csv(p, sep="\t", header=None, names=["acc", "tier"], dtype={"acc": str, "tier": np.int8},
                    na_filter=False)
    return dict(zip(s.acc, s.tier.astype(int)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--worklist", default=None, help="default OUT_ROOT/worklist.parquet")
    ap.add_argument("--tiers", default=None, help="e.g. 1 or 1,2 (default: all tiers of the work list)")
    ap.add_argument("--unit-ids", default=None, help="only these unit ids (comma-separated)")
    ap.add_argument("--max-units", type=int, default=None, help="claim at most N units (testing)")
    ap.add_argument("--dry-run", action="store_true", help="list the next units that would be claimed and exit")
    ap.add_argument("--retry-failed", action="store_true", help="also claim units with a failed marker")
    ap.add_argument("--devices", default=None, help="default cuda:0..SHARDS_PER_NODE-1")
    ap.add_argument("--runner", choices=["persistent", "cli"], default=env("RUNNER", "persistent"))
    ap.add_argument("--workers-per-shard", type=int, default=env("WORKERS_PER_SHARD", 15))
    ap.add_argument("--gpu-batch", type=int, default=env("GPU_BATCH", 16))
    ap.add_argument("--batch-structures", type=int, default=env("BATCH_STRUCTURES", 4000))
    ap.add_argument("--prefetch", type=int, default=env("PREFETCH_BATCHES", 4))
    ap.add_argument("--extract-threads", type=int, default=env("EXTRACT_THREADS", 4))
    ap.add_argument("--fc-procs", type=int, default=env("FC_PROCS", 4),
                    help="processes reading + decompressing Foldcomp entries (~2.4 ms each)")
    ap.add_argument("--gcs-fetch-threads", type=int, default=env("GCS_FETCH_THREADS", 32))
    ap.add_argument("--gcs-small-bytes", type=int, default=env("GCS_SMALL_BYTES", 16 * 1024 * 1024))
    ap.add_argument("--http-retries", type=int, default=env("HTTP_RETRIES", 8))
    ap.add_argument("--http-timeout", type=float, default=env("HTTP_TIMEOUT", 300.0))
    ap.add_argument("--describe-retries", type=int, default=env("DESCRIBE_RETRIES", 1))
    ap.add_argument("--min-points", type=int, default=env("MIN_POINTS", 10))
    ap.add_argument("--min-score", type=float, default=env("MIN_SCORE", 0.03))
    ap.add_argument("--min-plddt", type=float, default=env("MIN_PLDDT", 70.0))
    ap.add_argument("--stale-hours", type=float, default=env("STALE_HOURS", 24.0))
    ap.add_argument("--log-every", type=float, default=60.0)
    ap.add_argument("--tmp", default=None, help="node-local work dir (default $TMPDIR)")
    a = ap.parse_args()
    root = out_root(a.out_root)
    wl = pd.read_parquet(a.worklist or root / "worklist.parquet")
    if a.tiers:
        wl = wl[wl.tier.isin([int(t) for t in a.tiers.split(",")])]
    if a.unit_ids:
        wl = wl[wl.unit_id.isin([int(t) for t in a.unit_ids.split(",")])]
    claims = Claims(root, a.stale_hours)
    if a.dry_run:
        n = 0
        for r in wl.itertuples():
            if claims.is_done(r.unit_id) or (claims.is_failed(r.unit_id) and not a.retry_failed):
                continue
            c = claims.cdir / str(r.unit_id)
            state = "claimed" if c.exists() else "pending"
            print(f"{r.unit_id}\ttier {r.tier}\t{state}\t{r.code}\t{r.est_structures}\t{r.source}")
            n += 1
            if a.max_units and n >= a.max_units:
                break
        return 0
    devices = a.devices.split(",") if a.devices else [f"cuda:{g}" for g in range(env("SHARDS_PER_NODE", 4))]
    tmp = Path(a.tmp or os.environ.get("TMPDIR", "/tmp"))
    work = tmp / f"pocketcompare_afdb_{os.environ.get('SLURM_JOB_ID', os.getpid())}"
    work.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    skip = load_skip(root)
    log(f"{len(wl)} units in scope; devices {devices}; runner {a.runner}; {a.workers_per_shard} workers/shard; "
        f"batch {a.batch_structures}; filters score >= {a.min_score}, pLDDT >= {a.min_plddt}; skip list {len(skip):,}; "
        f"work dir {work}")

    def on_usr1(*_):
        log("SIGUSR1: no new units; finishing the units in flight")
        STOP_CLAIMING.set()

    def on_term(signum, *_):
        log(f"signal {signum}: releasing unfinished claims and exiting")
        STOP_CLAIMING.set()
        ABORT.set()
        for s in slots:
            s.kill()
        claims.release_all()
        shutil.rmtree(work, ignore_errors=True)
        os._exit(143)
    slots = [Slot(a, d, k) for k, d in enumerate(devices)]
    signal.signal(signal.SIGUSR1, on_usr1)
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    stats = Stats()
    fin = Finaliser(a, root, claims, stats)
    bq: queue.Queue = queue.Queue(maxsize=max(1, a.prefetch))
    src = UnitSource(wl, claims, a.retry_failed, a.max_units)
    fc_pool = None
    if (wl.source_type == "foldcomp").any():         # pread + decompress need processes (decompress holds the GIL)
        import multiprocessing as mp
        fc_pool = mp.get_context("spawn").Pool(a.fc_procs)
    ex = Extractor(a, root, work, skip, bq, fin, fc_pool)
    busy = [0]

    def extract_loop():
        while True:
            r = src.next()
            if r is None:
                return
            u = Unit(r, work)
            log(f"unit {u.uid} claimed (tier {u.tier}, {r['code']}, ~{r['est_structures']} models, "
                f"{len(r['sources'])} source(s))")
            try:
                ex.run_unit(u)
            except Exception as e:  # noqa: BLE001
                log(f"unit {u.uid}: extraction failed: {e}")
                with u.lock:
                    u.failed = u.failed or f"extract: {e}"
            with u.lock:
                u.extract_done = True
            u.maybe_finish(fin)       # batches still queued are dropped (failed unit) or finish it later

    def slot_loop(s: Slot):
        while True:
            b = bq.get()
            if b is None:
                return
            u = b.unit
            if not u.failed:
                busy[0] += 1
                try:
                    t0 = time.time()
                    s.run(b)
                    u.describe_s += time.time() - t0
                    with u.lock:
                        u.done_batches.append(b)
                except Exception as e:  # noqa: BLE001
                    with u.lock:
                        u.failed = u.failed or f"describe batch {b.k}: {e}"
                finally:
                    busy[0] -= 1
            shutil.rmtree(b.dir, ignore_errors=True)
            with u.lock:
                u.finished += 1
            u.maybe_finish(fin)

    def monitor():
        while not ABORT.is_set():
            time.sleep(a.log_every)
            log(stats.line(bq, busy[0]))

    threading.Thread(target=monitor, daemon=True, name="monitor").start()
    xs = [threading.Thread(target=extract_loop, name=f"extract{i}") for i in range(max(1, a.extract_threads))]
    ss = [threading.Thread(target=slot_loop, args=(s,), name=f"slot{s.k}") for s in slots]
    for t in xs + ss:
        t.start()
    for t in xs:
        t.join()
    for _ in ss:
        bq.put(None)
    for t in ss:
        t.join()
    fin.q.join()
    fin.q.put(None)
    for s in slots:
        s.stop()
    ex.http.shutdown(wait=False)
    if fc_pool is not None:
        fc_pool.terminate()
    shutil.rmtree(work, ignore_errors=True)
    log("finished: " + stats.line(bq, 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
