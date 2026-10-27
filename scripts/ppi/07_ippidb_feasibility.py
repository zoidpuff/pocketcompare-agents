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
Usage: python scripts/ppi/07_ippidb_feasibility.py [--partial]
(2026-10-27: the server returned 503s under paging; only 10/117 pages were fetched -> --partial was used.)
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
    """Resumable: each 200-row page is cached in data/raw/ippidb/pages/; rerun to continue after a 503."""
    RAW.mkdir(parents=True, exist_ok=True)
    f = RAW / "summary.json"
    if not f.exists():
        pdir = RAW / "pages"
        pdir.mkdir(exist_ok=True)
        off = 0
        while True:
            pf = pdir / f"{off:06d}.json"
            if not pf.exists():
                for attempt in range(5):
                    try:
                        with urllib.request.urlopen(URL.format(off), timeout=120) as r:
                            pf.write_bytes(r.read())
                        break
                    except Exception:  # noqa: BLE001  (server returns 502/503 under load)
                        if attempt == 4:
                            raise
                        time.sleep(60 * (attempt + 1))
                time.sleep(3.0)   # be polite: the server rate-limits rapid paging
            d = json.loads(pf.read_text())
            off += 200
            if not d.get("next"):
                break
        rows = [r for pf in sorted(pdir.glob("*.json")) for r in json.loads(pf.read_text())["results"]]
        f.write_text(json.dumps(rows))
    print(f"{f}: sha256 {hashlib.sha256(f.read_bytes()).hexdigest()}")
    return json.loads(f.read_text())


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--partial", action="store_true", help="summarise only the pages cached so far (no network)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.partial:
        rows = [r for pf in sorted((RAW / "pages").glob("*.json")) for r in json.loads(pf.read_text())["results"]]
    else:
        rows = fetch()
    df = pd.json_normalize(rows)
    lines = [f"{'PARTIAL (cached pages only, first rows of the API order)' if a.partial else 'FULL'} summary",
             f"cavities: {len(df)}; PDB entries: {df['chain.pdb'].nunique()}; UniProt (cavity chain): {df['chain.uniprot'].nunique()}",
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
