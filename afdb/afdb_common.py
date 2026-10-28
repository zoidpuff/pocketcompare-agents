"""Shared helpers of the AFDB pipeline (worklist, worker, status, index). Knobs come from the environment
(``config.sh`` exports them); the defaults here equal the ones in config.sh."""
from __future__ import annotations

import json
import os
import re
import socket
import tempfile
import time
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DIM = 384
NAME_RE = re.compile(r"AF-(?P<acc>[A-Za-z0-9_.-]+?)-F(?P<frag>\d+)-model_v(?P<ver>\d+)\.cif\.gz$")
GCS_RE = re.compile(r"proteome-tax_id-(?P<taxid>\d+)-(?P<shard>\d+)_v(?P<ver>\d+)\.tar$")


def env(name: str, default):
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return type(default)(v) if not isinstance(default, bool) else v.lower() in ("1", "true", "yes")


def out_root(arg=None) -> Path:
    return Path(arg or env("OUT_ROOT", "/cluster/scratch/gmagnusson/pocketcompare_afdb"))


def tar_index_dir(root: Path) -> Path:
    """Cached member indices of the local tars (TAR_INDEX_DIR, default OUT_ROOT/tar_index)."""
    return Path(env("TAR_INDEX_DIR", str(Path(root) / "tar_index")))


def gcs_base_url() -> str:
    return env("GCS_BASE_URL", f"https://storage.googleapis.com/{env('GCS_BUCKET', 'public-datasets-deepmind-alphafold-v4')}")


def parse_model_name(name: str):
    """'.../AF-P00918-F1-model_v6.cif.gz' -> (accession, fragment, model version) or None."""
    m = NAME_RE.search(name)
    if m is None:
        return None
    return m["acc"], int(m["frag"]), int(m["ver"])


_UMASK = os.umask(0)
os.umask(_UMASK)


def _publish(tmp: str, path: Path):
    os.chmod(tmp, 0o666 & ~_UMASK)          # mkstemp creates 0600 files
    os.replace(tmp, path)


def atomic_write_bytes(path: Path, data: bytes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    _publish(tmp, path)


def atomic_write_json(path: Path, obj):
    atomic_write_bytes(path, (json.dumps(obj, indent=1, default=_jsonable) + "\n").encode())


def _jsonable(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    return str(x)


def atomic_write_parquet(path: Path, table):
    import pyarrow.parquet as pq
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    pq.write_table(table, tmp, compression="zstd")
    _publish(tmp, path)


def _cif_value(raw: bytes, key: bytes):
    i = raw.find(b"\n" + key)
    if i < 0:
        return None
    j = raw.find(b"\n", i + 1)
    v = raw[i + 1 + len(key):j].strip()
    if v.startswith((b'"', b"'")):
        v = v[1:-1]
    return v.decode(errors="replace") if v not in (b"?", b".", b"") else None


def cif_stats(gz: bytes) -> dict:
    """Light per-structure statistics from an AFDB mmCIF.gz (~0.7 ms): residue count and pLDDT summary from the
    ``_ma_qa_metric_local`` loop, NCBI taxid and organism from ``_ma_target_ref_db_details``."""
    out = {"n_res": -1, "plddt_mean": np.nan, "plddt_frac_lt70": np.nan, "plddt_frac_lt50": np.nan,
           "cif_taxid": -1, "cif_organism": None}
    try:
        raw = zlib.decompress(gz, 31)
    except zlib.error:
        return out
    i = raw.find(b"\n_ma_qa_metric_local.")
    if i >= 0:
        j = raw.find(b"\n#", i)
        block = raw[i + 1:j].split(b"\n")
        hdr = [h.strip() for h in block if h.startswith(b"_ma_qa_metric_local.")]
        try:
            col = hdr.index(b"_ma_qa_metric_local.metric_value")
            v = np.array([r.split()[col] for r in block[len(hdr):] if r.strip()], dtype=np.float32)
            if len(v):
                out.update(n_res=int(len(v)), plddt_mean=float(v.mean()), plddt_frac_lt70=float((v < 70).mean()),
                           plddt_frac_lt50=float((v < 50).mean()))
        except (ValueError, IndexError):
            pass
    t = _cif_value(raw, b"_ma_target_ref_db_details.ncbi_taxonomy_id")
    if t and t.isdigit():
        out["cif_taxid"] = int(t)
    out["cif_organism"] = _cif_value(raw, b"_ma_target_ref_db_details.organism_scientific")
    return out


def slurm_ids() -> dict:
    e = os.environ
    return {"host": socket.gethostname(), "pid": os.getpid(), "slurm_job_id": e.get("SLURM_JOB_ID"),
            "slurm_array_job_id": e.get("SLURM_ARRAY_JOB_ID"), "slurm_array_task_id": e.get("SLURM_ARRAY_TASK_ID"),
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "t": time.time()}


def read_worklist(root: Path):
    import pandas as pd
    return pd.read_parquet(Path(root) / "worklist.parquet")


def fp16_loader_doc() -> str:
    return ("import pyarrow.parquet as pq, numpy as np\n"
            "t = pq.read_table('pockets/tier1/000000.parquet')\n"
            "V = np.asarray(t['fingerprint'].combine_chunks().flatten()).reshape(-1, 384)   # float16")
