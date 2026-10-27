#!/usr/bin/env python
"""Feasibility of a PPI-inhibitor pocket set (task 4c): fetch the iPPI-DB cavity summary via its REST API and
check overlap with the AFDB dimer set.

iPPI-DB (https://ippidb.pasteur.fr, Institut Pasteur) exposes /api/summary/ (one row per detected cavity in a PDB
PPI complex, with partner type protein or ligand and orthosteric/allosteric label), /api/ligand/ (PDB ligands of
PPI-inhibitor complexes) and /api/linkedpdb/ (ligands superposed onto PPI complexes). Only /api/summary/ is
downloaded here (raw JSON -> data/raw/ippidb/summary.json, git-ignored; re-fetched only if missing).
Licence: see the iPPI-DB website (record in DATA.md before any use beyond this feasibility check).

Prints: cavity counts by partner type and orthosteric/allosteric label, PDB / UniProt counts, and how many
iPPI-DB protein pairs (and ligand-bound proteins) are also in the AFDB dimer set (any organism).
Writes data/processed/dimers/ippidb/summary.txt
Usage: python scripts/ppi/07_ippidb_feasibility.py
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/ippidb"
OUT = ROOT / "data/processed/dimers/ippidb"
URL = "https://ippidb.pasteur.fr/api/summary/?format=json&limit=200&offset={}"


def fetch() -> list[dict]:
    RAW.mkdir(parents=True, exist_ok=True)
    f = RAW / "summary.json"
    if not f.exists():
        rows, off = [], 0
        while True:
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(URL.format(off), timeout=120) as r:
                        d = json.load(r)
                    break
                except Exception:  # noqa: BLE001  (server returns sporadic 502s)
                    if attempt == 4:
                        raise
                    time.sleep(30 * (attempt + 1))
            rows += d["results"]
            off += 200
            time.sleep(1.0)   # be polite: the server rate-limits (503) under rapid paging
            if not d.get("next"):
                break
        f.write_text(json.dumps(rows))
    print(f"{f}: sha256 {hashlib.sha256(f.read_bytes()).hexdigest()}")
    return json.loads(f.read_text())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = fetch()
    df = pd.json_normalize(rows)
    lines = [f"cavities: {len(df)}; PDB entries: {df['chain.pdb'].nunique()}; UniProt (cavity chain): {df['chain.uniprot'].nunique()}",
             f"partner type counts: {df['partner.type'].value_counts().to_dict()}",
             f"site label counts: {df['type'].value_counts().to_dict()}",
             f"organisms (top): {df['chain.organism'].value_counts().head(5).to_dict()}"]
    lig = df[df["partner.type"] != "protein"]
    lines.append(f"ligand-partner cavities: {len(lig)}; PDB {lig['chain.pdb'].nunique()}; UniProt {lig['chain.uniprot'].nunique()}; "
                 f"distinct ligand ids {lig['partner.pdb_ligand_id'].nunique()}")
    m = pd.read_csv(ROOT / "data/processed/dimers/manifest.tsv", sep="\t")
    accs = set(m.uniprotAccession_1) | set(m.uniprotAccession_2)
    pairs = {frozenset((a, b)) for a, b in zip(m.uniprotAccession_1, m.uniprotAccession_2)}
    prot = df[df["partner.type"] == "protein"]
    ipairs = {frozenset((a, b)) for a, b in zip(prot["chain.uniprot"], prot["partner.uniprot"])}
    lines.append(f"iPPI-DB protein-protein pairs: {len(ipairs)}; also an AFDB dimer (same UniProt pair): {len(ipairs & pairs)}")
    hit = sorted(" / ".join(sorted(p)) for p in ipairs & pairs)
    lines.append(f"  examples: {hit[:15]}")
    lp = set(lig["chain.uniprot"])
    lines.append(f"ligand-bound UniProts: {len(lp)}; present in any AFDB dimer: {len(lp & accs)}")
    txt = "\n".join(lines)
    print(txt)
    (OUT / "summary.txt").write_text(txt + "\n")


if __name__ == "__main__":
    main()
