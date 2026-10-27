#!/usr/bin/env python
"""Fetch KLIFS kinase-pocket METADATA via the public REST API (https://klifs.net/api,
Kanev et al. 2021 NAR 49:D562). Metadata only: kinase information and the
structure list (per PDB chain/altloc: kinase, ligand, DFG/aC conformations and
the 85-residue KLIFS pocket alignment string). Per-structure residue numbers
(/structure_get_pocket) and coordinate files are NOT fetched (one call per
structure, ~15k+ calls); do that later if needed.

The API is live data: re-running gives a newer snapshot; sha256 of each saved
JSON is recorded in MANIFEST.json together with the fetch date.
Usage: python -I scripts/data/fetch_klifs.py [--refresh]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.datasets.common import download, raw_dir  # noqa: E402

NAME = "klifs"
API = "https://klifs.net/api"


def main() -> None:
    dl = raw_dir(NAME) / "downloads"
    if "--refresh" in sys.argv:
        for f in ("kinase_information.json", "structures_list.json"):
            (dl / f).unlink(missing_ok=True)
    kin = download(NAME, f"{API}/kinase_information", "kinase_information.json", note="KLIFS API snapshot")
    ids = sorted({k["kinase_ID"] for k in json.loads(kin.read_text())})
    download(NAME, f"{API}/structures_list?kinase_ID=" + ",".join(map(str, ids)),
             "structures_list.json", timeout=1800, note=f"KLIFS API snapshot, {len(ids)} kinase IDs")


if __name__ == "__main__":
    main()
