"""Provenance sidecars and the append-only trials log (DESIGN §4, §5; reviews/round1_agent_failure_modes.md M2, M4).

``write_result(path, obj, ...)`` writes a result file (format from the extension: .parquet, .json, .tsv, .csv)
and next to it ``<path>.prov.json`` with:

* git commit of the project + ``git_dirty`` (tracked files modified; untracked files are not counted, their number
  is recorded as ``git_untracked``).  Writing under ``results/final/`` from a dirty tree is refused.
* script path + sha256, args, config (inline if JSON-serialisable) + config sha256 (canonical JSON with sorted
  keys for a dict; raw bytes for a file path), seed, device, hostname, start/end time (UTC ISO), wall seconds.
* inputs: for each input file sha256 + size; **files larger than 1 GiB are fingerprinted by size + mtime_ns
  only** (``"method": "size_mtime"``) because hashing them would cost minutes per result.
* sha256 of ``pocketcompare/evaluate.py`` (the frozen metric module) and of the result file itself.

``start_time`` defaults to the start time of the current process (Linux /proc), so wall seconds cover the whole
script run; pass ``start_time=time.time()`` captured earlier to time a section instead.

``append_trial(arm, config, dataset_split, metrics, result_path)`` appends one row to ``results/trials.tsv``
(created with a header if missing; never rewritten; an exclusive ``flock`` serialises concurrent writers).
"""
from __future__ import annotations

import datetime as _dt
import fcntl
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

PKG_DIR = Path(__file__).resolve().parent
ROOT = PKG_DIR.parents[1]
EVALUATE_PY = PKG_DIR / "evaluate.py"
TRIALS_TSV = ROOT / "results" / "trials.tsv"
LARGE_FILE = 1 << 30  # 1 GiB: above this, inputs are fingerprinted by size + mtime
TRIAL_COLUMNS = ["timestamp_utc", "arm", "config_sha256", "dataset_split", "metrics", "result_path", "config",
                 "git_commit", "git_dirty", "evaluate_sha256", "hostname", "user"]


def sha256_file(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while b := fh.read(chunk):
            h.update(b)
    return h.hexdigest()


def _jsonable(o):
    import numpy as np

    if isinstance(o, Path):
        return str(o)
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if hasattr(o, "to_dict"):
        return o.to_dict()
    raise TypeError(f"not JSON serialisable: {type(o)}")


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_jsonable, allow_nan=True)


def config_sha256(config) -> str | None:
    """sha256 of a config: file bytes if a path to an existing file, else canonical JSON."""
    if config is None:
        return None
    if isinstance(config, (str, Path)) and Path(config).is_file():
        return sha256_file(config)
    return hashlib.sha256(canonical_json(config).encode()).hexdigest()


def file_fingerprint(path) -> dict:
    p = Path(path)
    st = p.stat()
    if st.st_size > LARGE_FILE:
        return {"path": str(p), "size": st.st_size, "mtime_ns": st.st_mtime_ns, "method": "size_mtime"}
    return {"path": str(p), "size": st.st_size, "sha256": sha256_file(p), "method": "sha256"}


def _git(*args, cwd=ROOT) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                              timeout=30).stdout.rstrip("\n")
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def git_state(cwd=ROOT) -> dict:
    commit = _git("rev-parse", "HEAD", cwd=cwd)
    tracked = _git("status", "--porcelain", "--untracked-files=no", cwd=cwd)
    untracked = _git("ls-files", "--others", "--exclude-standard", cwd=cwd)
    return {"git_commit": commit, "git_dirty": None if tracked is None else bool(tracked),
            "git_dirty_files": [] if not tracked else [ln[3:] for ln in tracked.splitlines()][:50],
            "git_untracked": None if untracked is None else len([x for x in untracked.splitlines() if x])}


def process_start_time() -> float:
    """Unix start time of the current process (Linux /proc); falls back to module import time."""
    try:
        with open("/proc/self/stat") as fh:
            ticks = int(fh.read().rsplit(")", 1)[1].split()[19])
        with open("/proc/stat") as fh:
            btime = next(int(ln.split()[1]) for ln in fh if ln.startswith("btime"))
        return btime + ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, StopIteration):
        return _IMPORT_TIME


_IMPORT_TIME = time.time()


def _iso(t: float) -> str:
    return _dt.datetime.fromtimestamp(t, tz=_dt.timezone.utc).isoformat(timespec="seconds")


def _write_data(path: Path, obj) -> int | None:
    import pandas as pd

    suf = path.suffix.lower()
    n_rows = None
    if suf == ".json":
        if isinstance(obj, pd.DataFrame):
            obj, n_rows = obj.to_dict(orient="records"), len(obj)
        path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=_jsonable, allow_nan=True) + "\n")
        return n_rows
    if isinstance(obj, Mapping):
        vals = list(obj.values())
        obj = pd.DataFrame(obj) if vals and all(hasattr(v, "__len__") and not isinstance(v, str)
                                                for v in vals) else pd.DataFrame([obj])
    if not isinstance(obj, pd.DataFrame):
        raise TypeError("tabular formats need a DataFrame or a dict")
    if suf == ".parquet":
        obj.to_parquet(path, index=False)
    elif suf in (".tsv", ".csv"):
        obj.to_csv(path, sep="\t" if suf == ".tsv" else ",", index=False)
    else:
        raise ValueError(f"unsupported result format {suf!r} (use .parquet, .json, .tsv, .csv)")
    return len(obj)


def sidecar_path(path) -> Path:
    p = Path(path)
    return p.with_name(p.name + ".prov.json")


def write_result(path, df_or_dict, *, script, args, config, inputs: Sequence = (), seed, device: str,
                 start_time: float | None = None, extra: Mapping[str, Any] | None = None) -> dict:
    """Write a result file and its ``<path>.prov.json`` sidecar.  Returns the sidecar dict."""
    path = Path(path).resolve()
    git = git_state()
    try:
        under_final = path.is_relative_to((ROOT / "results" / "final").resolve())
    except ValueError:
        under_final = False
    if under_final and git["git_dirty"] is not False:
        raise RuntimeError(f"refusing to write {path}: results/final/ needs a clean, committed tree")
    t0 = process_start_time() if start_time is None else float(start_time)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp" + path.suffix)
    n_rows = _write_data(tmp, df_or_dict)
    os.replace(tmp, path)
    t1 = time.time()
    script = Path(script).resolve() if script else None
    prov = {
        "result": str(path), "result_sha256": sha256_file(path), "n_rows": n_rows,
        **{k: git[k] for k in ("git_commit", "git_dirty", "git_dirty_files", "git_untracked")},
        "script": str(script) if script else None,
        "script_sha256": sha256_file(script) if script and script.is_file() else None,
        "args": list(args) if isinstance(args, (list, tuple)) else args,
        "config": config if not isinstance(config, Path) else str(config),
        "config_sha256": config_sha256(config),
        "inputs": [file_fingerprint(p) for p in inputs],
        "evaluate_sha256": sha256_file(EVALUATE_PY),
        "seed": seed, "device": device, "hostname": socket.gethostname(),
        "python": sys.version.split()[0],
        "start_time": _iso(t0), "end_time": _iso(t1), "wall_seconds": round(t1 - t0, 3),
        "extra": dict(extra) if extra else None,
    }
    sc = sidecar_path(path)
    tmp = sc.with_name(sc.name + ".tmp")
    tmp.write_text(json.dumps(prov, indent=2, default=_jsonable, allow_nan=True) + "\n")
    os.replace(tmp, sc)
    return prov


def _cell(v) -> str:
    s = v if isinstance(v, str) else canonical_json(v)
    return s.replace("\t", " ").replace("\n", " ").replace("\r", " ")


def append_trial(arm: str, config, dataset_split: str, metrics: Mapping, result_path, *,
                 trials_path=None) -> dict:
    """Append one trial row to results/trials.tsv (append-only; header written when the file is new/empty)."""
    tp = Path(trials_path) if trials_path is not None else TRIALS_TSV
    tp.parent.mkdir(parents=True, exist_ok=True)
    git = git_state()
    row = {"timestamp_utc": _iso(time.time()), "arm": arm, "config_sha256": config_sha256(config),
           "dataset_split": dataset_split, "metrics": metrics, "result_path": str(result_path),
           "config": config if not isinstance(config, Path) else str(config),
           "git_commit": git["git_commit"], "git_dirty": git["git_dirty"],
           "evaluate_sha256": sha256_file(EVALUATE_PY), "hostname": socket.gethostname(),
           "user": os.environ.get("USER", "")}
    line = "\t".join(_cell(row[c]) for c in TRIAL_COLUMNS) + "\n"
    with open(tp, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.seek(0)
            head = fh.readline()
            if not head:
                fh.write("\t".join(TRIAL_COLUMNS) + "\n")
            elif head.rstrip("\n").split("\t") != TRIAL_COLUMNS:
                raise RuntimeError(f"{tp} has an unexpected header; refusing to append")
            fh.seek(0, os.SEEK_END)
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
    return row
