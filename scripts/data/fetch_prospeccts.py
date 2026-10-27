#!/usr/bin/env python
"""Fetch ProSPECCTs (Ehrt, Brinkjost & Koch 2018, PLoS Comput Biol 14:e1006483).

The original URL http://www.ccb.tu-dortmund.de/ag-koch/prospeccts/ is dead (404
since ~2024); the same download form is still served at
http://www.ewit.ccb.tu-dortmund.de/ag-koch/prospeccts/ (the host used by the
DeeplyTough downloader). Files are obtained by POSTing the license acceptance.

LICENSE: TU Dortmund "Terms of Use" (license_en.pdf, fetched alongside):
free, non-exclusive, internal use only; NO redistribution / sub-licensing;
cite the paper. => never commit these files or derived per-structure data.

Idempotent: re-running skips files whose sha256 matches MANIFEST.json.
Usage: python -I scripts/data/fetch_prospeccts.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.datasets.common import download, extract_once  # noqa: E402

NAME = "prospeccts"
BASE = "http://www.ewit.ccb.tu-dortmund.de/ag-koch/prospeccts/"
FILES = [
    "README.txt",
    "identical_structures.tar.gz",                 # P1
    "identical_structures_similar_ligands.tar.gz", # P1.2
    "NMR_structures.tar.gz",                       # P2
    "decoy.tar.gz",                                # P3, P4
    "kahraman_structures.tar.gz",                  # P5, P5.2
    "barelier_structures.tar.gz",                  # P6, P6.2
    "review_structures.tar.gz",                    # P7
]


def main() -> None:
    for lic in ("license_en.pdf", "license_de.pdf"):
        download(NAME, BASE + lic, lic, note="license terms")
    for fn in FILES:
        p = download(NAME, BASE, fn, method="POST",
                     data={"file": fn, "licenseagreement": "accept", "action": "Download"},
                     note="POST form, license accepted")
        if fn.endswith(".tar.gz"):
            extract_once(NAME, p)


if __name__ == "__main__":
    main()
