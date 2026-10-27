#!/usr/bin/env python
"""Write data/splits/SHA256SUMS.txt: sha256 of every file in data/splits/ (except PPI-agent files and this list)
and data/ref/additives.txt, plus the sealed test files' hashes recorded by the builders at write time (sealed
files are never re-read). Usage: python scripts/data/write_split_sums.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.splitutil import sha256  # noqa: E402

spl = ROOT / "data/splits"
OWN = ("homology_", "tough_m1_", "blips_", "split_sensitivity", "SPLITS.md")
lines = ["# sha256 of split files (data agent) and of sealed test files (hash recorded at write time)"]
for p in sorted(spl.iterdir()):
    if p.is_file() and p.name.startswith(OWN):
        lines.append(f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}")
lines.append(f"{sha256(ROOT / 'data/ref/additives.txt')}  data/ref/additives.txt")
tc = json.loads((spl / "tough_m1_split_counts.json").read_text())
lines.append(f"{tc['sealed_test_pairs_sha256']}  data/sealed/tough_m1_test_pairs.parquet")
bc = json.loads((spl / "blips_split_counts.json").read_text())
for k, v in sorted(bc.items()):
    if k.startswith("sealed_sha256:"):
        lines.append(f"{v}  data/sealed/{k.split(':', 1)[1]}")
(spl / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
