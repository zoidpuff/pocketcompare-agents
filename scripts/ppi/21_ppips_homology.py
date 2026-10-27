#!/usr/bin/env python
"""PPIPS step 2: chain sequences, chain alignments and the dataset's own homology graph.

Proteins = UniProt accessions of the complexes featurised by 20_ppips_featurize.py.
 * data/splits/inputs/ppips_chains.fasta (header = "afdimer:<accession>"; input for the global graph agent)
 * MMseqs2 (tools/mmseqs, -s 7.5, E <= 1e-3, --max-seqs 2000, with alignment strings) all-vs-all ->
   data/processed/ppi/ppips/mmseqs_aln.tsv  (used for (i) the homology rule and (ii) residue mapping)
 * Foldseek (tools/foldseek, exhaustive, TM-scores) all-vs-all on one chain per accession, cut from its first
   dimer file -> data/processed/ppi/ppips/foldseek.tsv
 * protein edges = pocketdetect.datasets.leakage.apply_rule (E < 1e-3, id >= 0.30, cov >= 0.5 either or
   alnlen >= 80)  OR  Foldseek min(qTM, tTM) >= 0.5 (both normalisations)
 * data/processed/ppi/ppips/protein_groups.parquet (accession -> protein component)
Residue numbering of the dimer files is the UniProt numbering, contiguous from 1, so sequence position i
== residue number i (checked here against the PDB files).
Usage: python scripts/ppi/21_ppips_homology.py --threads 16
"""
from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from pocketdetect.datasets.leakage import apply_rule

ROOT = Path(__file__).resolve().parents[2]
DIM = ROOT / "data/processed/dimers"
OUT = ROOT / "data/processed/ppi/ppips"
MMSEQS = ROOT / "tools/mmseqs/bin/mmseqs"
FOLDSEEK = ROOT / "tools/foldseek/bin/foldseek"
AA3 = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
       "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
       "TYR": "Y", "VAL": "V"}
COLS = ["query", "target", "fident", "alnlen", "qlen", "tlen", "qcov", "tcov", "evalue", "bits",
        "qstart", "qend", "tstart", "tend", "qaln", "taln"]


class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def chain_text(path: str, chain: str) -> tuple[str, str]:
    """PDB lines of one chain and its sequence (one letter per residue, file order)."""
    op = gzip.open if path.endswith(".gz") else open
    lines, seq, last = [], [], None
    with op(path, "rt") as fh:
        for ln in fh:
            if ln.startswith("ATOM") and ln[21] == chain:
                lines.append(ln)
                rid = ln[22:27]
                if rid != last:
                    last = rid
                    seq.append(AA3.get(ln[17:20], "X"))
    return "".join(lines) + "END\n", "".join(seq)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cx = pd.read_parquet(ROOT / "data/processed/cache/points/ppips/complexes.parquet")
    # one source (complex, chain) per accession
    src = {}
    for r in cx.itertuples():
        for acc, ch in ((r.uniprotAccession_1, "A"), (r.uniprotAccession_2, "B")):
            src.setdefault(acc, (r.path, ch))
    seqs = {}
    for line in (DIM / "orthology/proteins.fasta").read_text().splitlines():
        if line.startswith(">"):
            name = line[1:].split()[0]
        else:
            seqs[name] = line
    cdir = OUT / "chains"
    cdir.mkdir(exist_ok=True)
    bad = 0
    for acc, (p, ch) in sorted(src.items()):
        txt, s = chain_text(p, ch)
        if s != seqs[acc]:
            bad += 1
        (cdir / f"{acc}.pdb").write_text(txt)
    print(f"[hom] {len(src)} proteins; sequence(file) != proteins.fasta for {bad}", flush=True)
    fa = ROOT / "data/splits/inputs/ppips_chains.fasta"
    fa.parent.mkdir(parents=True, exist_ok=True)
    fa.write_text("".join(f">afdimer:{acc}\n{seqs[acc]}\n" for acc in sorted(src)))
    fa_local = OUT / "proteins.fasta"
    fa_local.write_text("".join(f">{acc}\n{seqs[acc]}\n" for acc in sorted(src)))

    env = {**os.environ, "OMP_NUM_THREADS": str(a.threads)}
    m8 = OUT / "mmseqs_aln.tsv"
    if not m8.exists():
        tmp = OUT / "tmp_mmseqs"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        run = lambda *x: subprocess.run([str(MMSEQS), *map(str, x)], check=True, env=env)  # noqa: E731
        run("createdb", fa_local, tmp / "q", "--dbtype", "1", "-v", "1")
        run("search", tmp / "q", tmp / "q", tmp / "r", tmp / "w", "-a", "-s", "7.5", "-e", "1e-3",
            "--max-seqs", "2000", "--threads", a.threads, "-v", "1")
        run("convertalis", tmp / "q", tmp / "q", tmp / "r", m8, "--format-output", ",".join(COLS), "-v", "1")
        shutil.rmtree(tmp, ignore_errors=True)
    fsk = OUT / "foldseek.tsv"
    if not fsk.exists():
        tmp = OUT / "tmp_foldseek"
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run([str(FOLDSEEK), "easy-search", str(cdir), str(cdir), str(fsk), str(tmp), "--exhaustive-search",
                        "1", "-e", "10", "--threads", str(a.threads), "-v", "1", "--format-output",
                        "query,target,evalue,alntmscore,qtmscore,ttmscore,fident"], check=True, env=env)
        shutil.rmtree(tmp, ignore_errors=True)
    h = pd.read_csv(m8, sep="\t", names=COLS)
    h = h[h["query"] != h["target"]]
    f = pd.read_csv(fsk, sep="\t", names=["query", "target", "evalue", "alntm", "qtm", "ttm", "fident"])
    f["query"] = f["query"].str.replace(r"\.pdb$", "", regex=True)
    f["target"] = f["target"].str.replace(r"\.pdb$", "", regex=True)
    f = f[f["query"] != f["target"]]
    seq_e = h[apply_rule(h)][["query", "target"]]
    str_e = f[(f[["qtm", "ttm"]].min(axis=1) >= 0.5)][["query", "target"]]
    uf = UF()
    for acc in src:
        uf.find(acc)
    for e in (seq_e, str_e):
        for q, t in e.itertuples(index=False):
            if q in src and t in src:
                uf.union(q, t)
    g = pd.DataFrame({"accession": sorted(src)})
    g["protein_group"] = g.accession.map(uf.find)
    g.to_parquet(OUT / "protein_groups.parquet", index=False)
    sz = g.protein_group.value_counts()
    print(f"[hom] seq edges {len(seq_e)}, struct edges {len(str_e)}; protein groups {len(sz)}, largest {sz.iloc[0]}")


if __name__ == "__main__":
    main()
