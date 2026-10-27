#!/usr/bin/env python
"""Fetch TOUGH-M1 (Govindaraj & Brylinski 2018, BMC Bioinformatics 19:91).

Sources (same as DeeplyTough's datasets_downloader.sh):
  * structures + ligands + fpocket output: Harvard Dataverse doi:10.7910/DVN/L7H7JJ
    file TOUGH-M1_dataset.tar.gz (persistentId doi:10.7910/DVN/L7H7JJ/UFO5CB),
    dataset version 3, CC0 1.0. Dataverse MD5 is checked.
  * pair / pocket / target lists + baseline score files: OSF project
    https://osf.io/6ngbs/ (no license set on OSF); sha256 checked against OSF API.
The per-tool score archives (APoc, G-LoSA, SiteEngine, Vina, rDock; ~19 GB) in
the same Dataverse record are NOT fetched.

Idempotent. Usage: python -I scripts/data/fetch_tough_m1.py
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.datasets.common import download, extract_once  # noqa: E402

NAME = "tough_m1"
DV = "https://dataverse.harvard.edu/api/access/datafile/:persistentId?persistentId="
ARCHIVE = ("TOUGH-M1_dataset.tar.gz", DV + "doi:10.7910/DVN/L7H7JJ/UFO5CB",
           "42c35ac0c17d819e35446954ffb519c5")
# OSF file -> (download URL, sha256 published by OSF API). The *.score files are
# the published baseline scores (APoc, G-LoSA, SiteEngine) - useful as positive
# controls for our evaluation code.
OSF = {
    "TOUGH-M1_positive.list": ("https://osf.io/download/tmgne/", "04d4be33619ad03becf7d1fa509669db455d2754b3d3c3d1ba6f6dd41331dbb7"),
    "TOUGH-M1_negative.list": ("https://osf.io/download/3aypv/", "41a8b6501935690176507b0e4ccec83b19cfb23d9b992fc77aaacdf9c815405e"),
    "TOUGH-M1_pocket.list": ("https://osf.io/download/6dn5s/", "57aad20c9a3ab3bcfa72970834282c31616e2bbad45131286e2d0b15c723311b"),
    "TOUGH-M1_target.list": ("https://osf.io/download/e7qu4/", "54cfcdccd67f29ca2e2d98cdc4b7a992547e14dc5b4b7221fdc8d2e19a296d64"),
    "TOUGH-M1_dataset.info": ("https://osf.io/download/2s5j6/", "1e17e45b8e24f52665a3d036498d68b960615263b3bf27711f4830aacf802b9c"),
    "APoc-TOUGH-M1_positive.score": ("https://osf.io/download/t2me4/", "282f1ab6324459f26b008658dd970593d019426da314c18533b9b62356b13d61"),
    "APoc-TOUGH-M1_negative.score": ("https://osf.io/download/sf9am/", "0196691f3dde40dbe6b3f807fcf36852a70140dec62660dd411e486bead72420"),
    "G-LoSA-TOUGH-M1_positive.score": ("https://osf.io/download/w98h2/", "1574993c798365eadd4133147230cf652451d72dd7e8ff870d498bdbfecf868a"),
    "G-LoSA-TOUGH-M1_negative.score": ("https://osf.io/download/2vmzf/", "74f5cdf7a52a585683f2b039aed357376f0d85b160a5227d99fc28937945bb10"),
    "SiteEngine-TOUGH-M1_positive.score": ("https://osf.io/download/tnqgu/", "4728961fdc7746a2571d700508667765b5409ad5d9a7dea72eb2b3fa7985362a"),
    "SiteEngine-TOUGH-M1_negative.score": ("https://osf.io/download/3mbpk/", "ff373ef229a46e2dd357f1727e9cd061a060f64099007e7c940be2fc6f0ce099"),
}


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    for fn, (url, sha) in OSF.items():
        download(NAME, url, fn, expected_sha256=sha, note="OSF 6ngbs, sha256 from OSF API")
    fn, url, want_md5 = ARCHIVE
    p = download(NAME, url, fn, timeout=3600, note=f"Dataverse md5 {want_md5}")
    got = md5(p)
    if got != want_md5:
        raise RuntimeError(f"MD5 mismatch for {fn}: {got} != {want_md5}")
    print(f"[ok  ] {fn} md5 matches Dataverse")
    extract_once(NAME, p)


if __name__ == "__main__":
    main()
