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


def pdb_plddt_stats(pdb: str) -> dict:
    """Residue count and pLDDT summary from the CA B-factors of a PDB text (Foldcomp keeps pLDDT to +-0.03)."""
    v = np.array([float(ln[60:66]) for ln in pdb.splitlines() if ln.startswith("ATOM") and ln[12:16] == " CA "],
                 np.float32)
    if not len(v):
        return {"n_res": 0, "plddt_mean": np.nan, "plddt_frac_lt70": np.nan, "plddt_frac_lt50": np.nan}
    return {"n_res": int(len(v)), "plddt_mean": float(v.mean()), "plddt_frac_lt70": float((v < 70).mean()),
            "plddt_frac_lt50": float((v < 50).mean())}


_FC_FD: dict = {}


def fc_extract_chunk(args):
    """Process-pool task: read Foldcomp entries by (offset, length) with os.pread, decompress, write
    ``<out_dir>/<stem>.pdb``. Returns [(stem, stats | None, n_bytes, error)]."""
    db_path, out_dir, rows = args
    import foldcomp
    fd = _FC_FD.get(db_path)
    if fd is None:
        fd = _FC_FD[db_path] = os.open(db_path, os.O_RDONLY)
    out = []
    for off, ln, stem in rows:
        try:
            data = os.pread(fd, int(ln), int(off))
            if len(data) != int(ln):
                raise IOError(f"short read at {off}")
            name, pdb = foldcomp.decompress(data)
            if not str(name).startswith(stem):
                raise ValueError(f"entry name {name} != {stem}")
            Path(out_dir, f"{stem}.pdb").write_text(pdb)
            out.append((stem, pdb_plddt_stats(pdb), len(data), None))
        except Exception as e:  # noqa: BLE001
            out.append((stem, None, 0, f"foldcomp: {type(e).__name__}: {e}"[:300]))
    return out


SOURCE_LABELS = {"afdb_uniprot_v4": "foldcomp:afdb_uniprot_v4", "afdb_rep_v4": "foldcomp:afdb_rep_v4",
                 "afdb_swissprot_v4": "foldcomp:afdb_swissprot_v4"}


def source_label(row: dict) -> str:
    """The ``source`` column: afdb_v6_tar | afdb_swissprot_v6_tar | foldcomp:<db> | gcs_v4_tar."""
    st = row["source_type"]
    if st == "local_tar":
        return "afdb_swissprot_v6_tar" if "swissprot" in str(row["source"]) else "afdb_v6_tar"
    if st == "foldcomp":
        return SOURCE_LABELS.get(row["source"], f"foldcomp:{row['source']}")
    return "gcs_v4_tar"


TIER_SOURCE_DEFAULT = {1: "afdb_v6_tar", 2: "afdb_swissprot_v6_tar"}


def fill_source(table):
    """Add / complete the ``source`` column of a pocket or structure table (pyarrow Table or pandas DataFrame).
    Files written before the column existed (the first tier-1/2 run, commit 24d1c8f) lack it: tier 1 ->
    afdb_v6_tar, tier 2 -> afdb_swissprot_v6_tar (the only sources those tiers have). Tier-3 rows always have it."""
    import pandas as pd
    if isinstance(table, pd.DataFrame):
        derived = table["tier"].map(TIER_SOURCE_DEFAULT)
        if "source" not in table:
            return table.assign(source=derived)
        return table.assign(source=table["source"].fillna(derived))
    import pyarrow as pa
    import pyarrow.compute as pc
    tier = table.column("tier").to_pandas().map(TIER_SOURCE_DEFAULT)
    derived = pa.array(tier.where(tier.notna(), None), pa.string())
    if "source" not in table.column_names:
        return table.append_column("source", derived)
    i = table.column_names.index("source")
    return table.set_column(i, "source", pc.coalesce(table.column("source").cast(pa.string()), derived))


def open_pockets(root, kind: str = "pockets"):
    """pyarrow dataset over OUT_ROOT/<kind>/tier*/*.parquet with a schema unified across files, so files without
    the ``source`` column (first tier-1/2 run) read as nulls instead of being dropped; apply fill_source() to the
    tables you read from it."""
    import pyarrow as pa
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
    files = sorted(str(f) for f in Path(root, kind).glob("tier*/[0-9]*.parquet"))
    firsts = {}
    for f in files:                              # one schema per tier directory is enough
        firsts.setdefault(Path(f).parent.name, f)
    schema = pa.unify_schemas([pq.read_schema(f) for f in firsts.values()], promote_options="permissive")
    return ds.dataset(files, schema=schema, format="parquet")


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
