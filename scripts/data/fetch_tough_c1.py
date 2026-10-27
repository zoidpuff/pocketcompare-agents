#!/usr/bin/env python
"""Fetch TOUGH-C1 (Pu, Govindaraj, ... Brylinski 2019, PLoS Comput Biol 15:e1006718,
DeepDrug3D) from OSF project https://osf.io/enz69/ (no license set on OSF).

TOUGH-C1 is a pocket CLASSIFICATION set (nucleotide / heme / steroid / control),
not a pair benchmark. We fetch the lists, the binding-residue files (LPC =
ligand contacts; fpocket = predicted pocket), protein PDBs and ligands
(~190 MB). Not fetched: fpocket/pocket/pops/profilpro/pdbqt tarballs (~1.1 GB).
sha256 values are those published by the OSF API (checked).

Idempotent. Usage: python -I scripts/data/fetch_tough_c1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.datasets.common import download, extract_once  # noqa: E402

NAME = "tough_c1"
OSF = {
    "nucleotide.list": ("kpa26", "2f093379d39bc27f74fa2d0bae807fb73bfa23113ee07b9f5275f40c4dd22958"),
    "heme.list": ("9e6ha", "5f9dfcd7c025fade7ccc08f7df444d49841105b71f671f37f1c39d81cc470bb9"),
    "steroid.list": ("xzhq3", "3352921577276834b35563b81c6e3ffc31c4a248c5819459e8d8a2fa4ff06690"),
    "control.list": ("md7kb", "702d96f2a24313bb07b5727e78ff52399e731eb8d5bb5e68203bf9db4d25253f"),
    "deepdrug3d_nucleotide.lst": ("82jnk", "55833e3aef74d3bc3e2acfa7f8f468b9b11449c4f1ad102f1223be06bb7e74de"),
    "deepdrug3d_heme.lst": ("wk4u7", "d18c0def9f8e0a865d6e6eea0cd1b5061f85fff4d0bcc187a61ea27a0fae727f"),
    "deepdrug3d_steroid.lst": ("yb8p7", "cc8a0044b901c55b81f87cce878276d24e90382837c3cf256cd193b84e2287ce"),
    "deepdrug3d_control.lst": ("vu59c", "68fb94d866ed2a4ca42cc1fc8d50aa0eb34f92b90f4746d7682381442a3b4e40"),
    "lpc-nucleotide.residues": ("m5z9y", "3fe570aae66b9c4acb8fe3c722cfbac7ef07a4416e57cc9c20a4611d5d078ada"),
    "lpc-heme.residues": ("w839k", "509a9060fe6903c745945a3bff84d6a1d01e0c5a117fc76da669f5948a62bb5e"),
    "lpc-steroid.residues": ("2gt4r", "982662bc8422fe3f058013e3806c6aeb8df8f49b7053c0a452968ed769169728"),
    "lpc-control.residues": ("cehjg", "351dc9ecc77c2581ff0c118db65eae2909c3bd9b25d2d0f16b9ea5e3e217b808"),
    "fpocket-nucleotide.residues": ("tjnyx", "f5f1573c64be8a580e3aafc74d89052687eec4bb375fe365b558bbbf918efbab"),
    "fpocket-heme.residues": ("bcrmq", "f4018e97eaecb852a825a888608ddd0691af2bae2ddce5886a7ca85082ca6a42"),
    "fpocket-steroid.residues": ("qfg49", "d3ea6fc21dfafb928b7519e83e98889fad38709f599fe307099820a09ebde83f"),
    "fpocket-control.residues": ("wxj4f", "5828c835a6a13eec3cef49f498ca0bafab8f600e6896b8b9d4abd19e7cb098a7"),
    "protein-nucleotide.tar.gz": ("rh2we", "ed89d6aa6b3bdd25c589adbf5f95756d54c330b5943664136f3cba64e9c24205"),
    "protein-heme.tar.gz": ("6zwvm", "a77d1e774e875aa57442c17449abdf8d5a20ef9261390f0881984c07e3bb1611"),
    "protein-steroid.tar.gz": ("gxqrv", "46a1bb81a1f4fff857ea3aecec799281e35a3deaaffb04d2a0594e5ecb8e8325"),
    "protein-control.tar.gz": ("w8y7q", "508d5a684d84356cafe82483a0898fcee2ba6f3df02b6ee5d6662342c69c22e9"),
    "ligand-nucleotide.tar.gz": ("5nkw7", "8ec3c3b925e8e402c49dd52c168e6dd808da5a45b12550d55bca8b5d7221ae47"),
    "ligand-heme.tar.gz": ("u2fsq", "1d80ee5e37898f1fd7ed4b211763bb895675f0882f773a1569c9603ccdf17258"),
    "ligand-steroid.tar.gz": ("kugtx", "e9e283f2b4143501a398a383f57ab2eeeba87358608cb3597f5dd50c2ad92fe7"),
    "ligand-control.tar.gz": ("e2s5n", "64df00bb8aaeca5f9e9d69c5fa9b97a6c59bf8e9b272431e00b7b8ef6b86418c"),
}


def main() -> None:
    for fn, (guid, sha) in OSF.items():
        p = download(NAME, f"https://osf.io/download/{guid}/", fn, expected_sha256=sha,
                     note="OSF enz69, sha256 from OSF API")
        if fn.endswith(".tar.gz"):
            extract_once(NAME, p, subdir=fn[:-7])


if __name__ == "__main__":
    main()
