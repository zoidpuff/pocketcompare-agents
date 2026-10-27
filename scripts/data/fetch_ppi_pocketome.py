#!/usr/bin/env python
"""Fetch the Pasteur PPI pocketome (Moine-Franel et al., Sci Data 2024) from Zenodo 10.5281/zenodo.10805580
(CC-BY-4.0) into data/raw/ppi_pocketome/ (untrusted data; nothing in it is ever executed or imported).

Steps (idempotent, resumable):
  1. small files (README.txt, two TMAP html files) via common.download (sha256 in MANIFEST.json);
  2. CDPPILBP.tar.gz (11.1 GB) with curl resume (-C -), md5 checked against the Zenodo API, sha256 recorded;
  3. member listing -> extracted/members.tsv (name, size, type);
  4. selective, path-checked extraction (tarfile 'data' filter) of the files we use: annotation CSVs, ligand
     SDF/mol2, VolSite cavity mol2 (labelled variants only, not the '_ALL__' duplicates), ligand-contact
     residue lists and logs-free text; structures (.pdb/.ent) are NOT extracted (local PDB mirror is used).
Usage: python -I scripts/data/fetch_ppi_pocketome.py [--no-extract] [--keep-archive]
"""
import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.datasets.common import download, load_manifest, raw_dir, save_manifest, sha256_file  # noqa: E402

NAME = "ppi_pocketome"
REC = "https://zenodo.org/api/records/10805580"
SMALL = ["README.txt", "PPI-Pocketome_MST_Euclidean_complete_PSI.html", "PPI-Chemical-Space.html"]
BIG = "CDPPILBP.tar.gz"


def zenodo_files() -> dict:
    out = subprocess.run(["curl", "-sS", "-m", "60", REC], capture_output=True, text=True, check=True).stdout
    return {f["key"]: f for f in json.loads(out)["files"]}


def md5_file(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def want_member(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    if base.endswith(".csv"):
        return True
    if base.endswith(".sdf"):
        return True
    if base.endswith(".mol2"):
        # cavities: keep labelled variants (…_ALL_orthosteric.mol2, …_ALL_liganded_…, …_ALL_unliganded.mol2,
        # …_ALL_nonorthosteric.mol2); skip the unlabelled duplicates ending in '_ALL__.mol2'
        return not base.endswith("_ALL__.mol2")
    if base.endswith(".txt") and "interface-residues" in base:
        return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-extract", action="store_true")
    a = ap.parse_args()
    zf = zenodo_files()
    for fn in SMALL:
        download(NAME, f"{REC}/files/{fn}/content", fn, note=f"Zenodo md5 {zf[fn]['checksum']}")

    dl = raw_dir(NAME) / "downloads"
    big = dl / BIG
    man = load_manifest(NAME)
    if not (big.exists() and man["files"].get(BIG, {}).get("sha256")):
        part = dl / (BIG + ".part")
        url = f"{REC}/files/{BIG}/content"
        print(f"[get ] {url} (resumable)", flush=True)
        for attempt in range(20):
            r = subprocess.run(["curl", "-sS", "-L", "--retry", "5", "-C", "-", "-o", str(part), url])
            if r.returncode == 0 and part.stat().st_size == zf[BIG]["size"]:
                break
            print(f"[retry] curl rc={r.returncode} size={part.stat().st_size if part.exists() else 0}", flush=True)
        if part.stat().st_size != zf[BIG]["size"]:
            raise RuntimeError("incomplete download")
        md5 = md5_file(part)
        if "md5:" + md5 != zf[BIG]["checksum"]:
            raise RuntimeError(f"md5 mismatch {md5} vs {zf[BIG]['checksum']}")
        part.replace(big)
        man = load_manifest(NAME)
        man["files"][BIG] = {"url": url, "sha256": sha256_file(big), "md5": md5, "size_bytes": big.stat().st_size,
                             "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                             "note": "md5 matches Zenodo API"}
        save_manifest(NAME, man)
        print("[ok  ] archive verified", flush=True)
    if a.no_extract:
        return
    ext = raw_dir(NAME) / "extracted"
    stamp = ext / ".selective_done"
    if stamp.exists():
        print("[skip] already extracted")
        return
    ext.mkdir(parents=True, exist_ok=True)
    n_all = n_keep = b_keep = 0
    with tarfile.open(big, "r|gz") as tf, open(ext / "members.tsv", "w") as lst:
        lst.write("name\tsize\ttype\textracted\n")
        for m in tf:
            n_all += 1
            keep = m.isfile() and want_member(m.name)
            lst.write(f"{m.name}\t{m.size}\t{m.type.decode() if isinstance(m.type, bytes) else m.type}\t{int(keep)}\n")
            if keep:
                tf.extract(m, ext, filter="data")
                n_keep += 1
                b_keep += m.size
            if n_all % 100000 == 0:
                print(f"  {n_all} members, {n_keep} kept ({b_keep / 1e9:.2f} GB)", flush=True)
    stamp.write_text(json.dumps({"members": n_all, "extracted": n_keep, "bytes": b_keep}))
    print(f"[ok  ] {n_all} members, extracted {n_keep} ({b_keep / 1e9:.2f} GB)")


if __name__ == "__main__":
    main()
