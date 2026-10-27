"""Shared helpers for benchmark fetch scripts and loaders.

Downloads are treated as untrusted data: each dataset gets its own directory
under data/raw/<name>/, archives go to downloads/, extraction goes to
extracted/ using tarfile's 'data' filter / zip path checks (no absolute
paths, no '..', no links outside the target).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
import tarfile
import urllib.parse
import zipfile
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "benchmarks"
PDB_MIRROR = Path("/cluster/scratch/jjaenes/pdb")

PAIR_COLUMNS = ["pair_id", "pocket_a", "pocket_b", "label", "subset", "source_label"]
POCKET_COLUMNS = [
    "pocket_id", "dataset", "subset", "pdb_id", "chain", "structure_path",
    "pocket_def_type", "pocket_def", "pocket_file", "ligand_file",
    "ligand_resname", "in_pdb_mirror",
]


def raw_dir(name: str) -> Path:
    return RAW_DIR / name


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _manifest_path(name: str) -> Path:
    return raw_dir(name) / "MANIFEST.json"


def load_manifest(name: str) -> dict:
    p = _manifest_path(name)
    if p.exists():
        return json.loads(p.read_text())
    return {"dataset": name, "files": {}}


def save_manifest(name: str, manifest: dict) -> None:
    p = _manifest_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def download(name: str, url: str, filename: str, *, method: str = "GET",
             data: dict | None = None, expected_sha256: str | None = None,
             timeout: int = 600, note: str = "") -> Path:
    """Idempotent download into data/raw/<name>/downloads/<filename>.

    If the file exists and its sha256 equals the one recorded in the manifest
    (or expected_sha256), it is not re-downloaded. Records url, date, size,
    sha256 in data/raw/<name>/MANIFEST.json.
    """
    dest_dir = raw_dir(name) / "downloads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    manifest = load_manifest(name)
    rec = manifest["files"].get(filename)
    if dest.exists() and rec:
        sha = sha256_file(dest)
        want = expected_sha256 or rec.get("sha256")
        if sha == want:
            print(f"[skip] {filename} present, sha256 ok")
            return dest
        print(f"[warn] {filename} sha256 mismatch ({sha} != {want}); re-downloading")
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"[get ] {url} -> {dest}")
    with requests.request(method, url, data=data, stream=True, timeout=timeout,
                          headers={"User-Agent": "pocketcompare-fetch/0.1 (academic benchmark download)"}) as r:
        r.raise_for_status()
        with open(tmp, "wb") as fh:
            for block in r.iter_content(1 << 20):
                fh.write(block)
    tmp.replace(dest)
    sha = sha256_file(dest)
    if expected_sha256 and sha != expected_sha256:
        raise RuntimeError(f"sha256 mismatch for {filename}: {sha} != {expected_sha256}")
    manifest["files"][filename] = {
        "url": url, "method": method, "post_data": data, "sha256": sha,
        "size_bytes": dest.stat().st_size,
        "fetched_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "note": note,
    }
    save_manifest(name, manifest)
    return dest


def safe_extract(archive: Path, target: Path) -> None:
    """Extract tar/zip into target, refusing absolute paths, '..' and links out."""
    target.mkdir(parents=True, exist_ok=True)
    troot = target.resolve()
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            tf.extractall(target, filter="data")
    elif zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for m in zf.infolist():
                out = (target / m.filename).resolve()
                if not str(out).startswith(str(troot) + os.sep) and out != troot:
                    raise RuntimeError(f"unsafe path in {archive}: {m.filename}")
            zf.extractall(target)
    else:
        raise ValueError(f"not an archive: {archive}")


def extract_once(name: str, archive: Path, subdir: str | None = None) -> Path:
    """Extract archive into data/raw/<name>/extracted[/subdir] once (stamp file)."""
    target = raw_dir(name) / "extracted"
    if subdir:
        target = target / subdir
    stamp = target / f".extracted_{archive.name}"
    if stamp.exists() and stamp.read_text().strip() == sha256_file(archive):
        print(f"[skip] {archive.name} already extracted")
        return target
    safe_extract(archive, target)
    stamp.write_text(sha256_file(archive))
    return target


def pdb_mirror_path(pdb_id: str) -> Path:
    pdb_id = pdb_id.lower()
    return PDB_MIRROR / pdb_id[1:3] / f"{pdb_id}.cif.gz"


def in_pdb_mirror(pdb_id: str) -> bool:
    return pdb_mirror_path(pdb_id).exists()


# Benchmarks whose pair labels are sealed in data/sealed/ (chmod 000). Their pair tables are never written to
# data/processed/ by a rebuild; set POCKETCOMPARE_WRITE_SEALED_PAIRS=1 (PI only) to override.
SEALED_PAIR_DATASETS = {"prospeccts", "tough_m1", "vertex"}


def write_tables(name: str, pairs, pockets) -> tuple[Path | None, Path]:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pp = PROCESSED_DIR / f"{name}_pairs.parquet"
    kp = PROCESSED_DIR / f"{name}_pockets.parquet"
    if pairs is not None and (name not in SEALED_PAIR_DATASETS
                              or os.environ.get("POCKETCOMPARE_WRITE_SEALED_PAIRS") == "1"):
        pairs.to_parquet(pp, index=False)
    else:
        pp = None
        if pairs is not None:
            print(f"[sealed] {name}: pair table NOT written (labels are sealed in data/sealed/)")
    pockets.to_parquet(kp, index=False)
    return pp, kp


def rel(path: Path | str) -> str:
    """Path relative to project root (portable across mounts)."""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def du(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total
