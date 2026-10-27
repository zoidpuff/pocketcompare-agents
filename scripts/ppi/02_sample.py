#!/usr/bin/env python
"""Draw the stratified dimer sample and extract monomer chains (task 2 inputs).

Sample: N_PER dimers per organism (human, yeast, ecoli) x type (homo, hetero), uniform within stratum,
seed = pocketcompare.seeds.SEEDS[0]. Default N_PER = 100 -> 300 homo + 300 hetero.
Monomers: each chain is copied verbatim (ATOM records of that chain, same coordinates, same B-factor/pLDDT)
from the dimer file - no new structures are fetched. Because coordinates are unchanged, dimer and monomer
pockets can be compared directly in space.

Writes  data/processed/dimers/sample/sample.tsv
        data/processed/dimers/sample/inputs/dimers/<id>.pdb      (symlinks to the read-only originals)
        data/processed/dimers/sample/inputs/monomers/<id>_<chain>.pdb
        data/processed/dimers/sample/inputs/{dimers,monomers}.list   (@list files for burrow predict)
Usage: python scripts/ppi/02_sample.py [--n-per 100]
Requires 01_inventory.py output (data/processed/dimers/manifest.tsv).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.seeds import SEEDS  # noqa: E402

BASE = ROOT / "data/processed/dimers"


def extract_chain(src: Path, chain: str, dst: Path) -> None:
    with open(src) as fh, open(dst, "w") as out:
        for line in fh:
            if line.startswith(("ATOM", "HETATM")) and line[21] == chain:
                out.write(line)
            elif line.startswith("ENDMDL"):
                break
        out.write("TER\nEND\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-per", type=int, default=100)
    ap.add_argument("--out", default=str(BASE / "sample"))
    a = ap.parse_args()
    out = Path(a.out)
    m = pd.read_csv(BASE / "manifest.tsv", sep="\t")
    parts = []
    for (org, typ), g in m.groupby(["organism", "type"], sort=True):
        parts.append(g.sample(n=min(a.n_per, len(g)), random_state=SEEDS[0]))
    s = pd.concat(parts).sort_values(["type", "organism", "modelEntityId"]).reset_index(drop=True)
    dd, md = out / "inputs/dimers", out / "inputs/monomers"
    dd.mkdir(parents=True, exist_ok=True)
    md.mkdir(parents=True, exist_ok=True)
    dl, ml = [], []
    for r in s.itertuples():
        link = dd / f"{r.modelEntityId}.pdb"
        if not link.exists():
            os.symlink(r.path, link)
        dl.append(str(link))
        for c in (r.chain_A, r.chain_B):
            p = md / f"{r.modelEntityId}_{c}.pdb"
            if not p.exists():
                extract_chain(Path(r.path), c, p)
            ml.append(str(p))
    (out / "inputs/dimers.list").write_text("\n".join(dl) + "\n")
    (out / "inputs/monomers.list").write_text("\n".join(ml) + "\n")
    s.to_csv(out / "sample.tsv", sep="\t", index=False)
    print(s.groupby(["organism", "type"]).size().to_string())
    print(f"{len(dl)} dimers, {len(ml)} monomer chains -> {out}")


if __name__ == "__main__":
    main()
