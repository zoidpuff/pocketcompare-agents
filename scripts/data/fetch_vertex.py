#!/usr/bin/env python
"""Fetch the Vertex binding-site similarity set (Chen et al. 2016, J Chem Inf Model
56:1734-1745, doi:10.1021/acs.jcim.6b00118).

Source: ACS supporting information ci6b00118_si_002.zip, mirrored by ACS on
figshare: doi:10.1021/acs.jcim.6b00118.s002 (article 3803883, file 5922126,
license CC BY-NC 4.0). md5 from the figshare API is checked.
(pubs.acs.org itself returns HTTP 403 to scripted clients; not used.)

Structures are NOT shipped; they come from the local PDB mirror.

Optional (--with-deeplytough): dt_vertex.zip, DeeplyTough's pre-processed copy
(Zenodo 3687317, CC-BY-4.0, 2.25 GB zip / 9.9 GB extracted; contains
DeeplyTough's own ligand/site extraction and HTMD features, NO pair list).
Not needed by our loader; off by default.

Idempotent. Usage: python -I scripts/data/fetch_vertex.py [--with-deeplytough]
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.datasets.common import download, extract_once  # noqa: E402

NAME = "vertex"
FIGSHARE = ("ci6b00118_si_002.zip", "https://ndownloader.figshare.com/files/5922126",
            "ff40a1561bdbe2fe16a4ac5b066c210c")
ZENODO = ("dt_vertex.zip", "https://zenodo.org/records/3687317/files/dt_vertex.zip?download=1",
          "989b778f7d1e969e550088fed77bab4e")


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def get(spec, subdir, note):
    fn, url, want = spec
    p = download(NAME, url, fn, timeout=3600, note=f"{note}; md5 {want}")
    if md5(p) != want:
        raise RuntimeError(f"md5 mismatch for {fn}")
    print(f"[ok  ] {fn} md5 matches")
    extract_once(NAME, p, subdir=subdir)


def main() -> None:
    get(FIGSHARE, "acs_si", "ACS SI via figshare 3803883")
    if "--with-deeplytough" in sys.argv:
        get(ZENODO, "dt_vertex", "DeeplyTough Zenodo 3687317")


if __name__ == "__main__":
    main()
