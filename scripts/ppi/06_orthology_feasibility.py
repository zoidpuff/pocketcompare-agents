#!/usr/bin/env python
"""Feasibility of cross-species "same interface" pairs (task 4b): homologous complexes (interologs) in the
AFDB dimer set, found with MMseqs2 on the chain sequences of ALL 15,161 dimers (not just the sample).

Steps: unique protein sequences per accession (from 01_inventory.py sequences.fasta) -> MMseqs2 easy-search
all-vs-all (-s 7.5, E <= 1e-3, coverage >= 0.5 of both sequences, cov-mode 0) -> protein homology pairs ->
complex pairs. Two complexes (P1,P2) and (Q1,Q2) are interologs if P1~Q1 and P2~Q2 (or crossed);
homodimers need P~Q. Reported per organism pair, with the identity of the weaker of the two chain matches
("pair identity" = min over the two chains), which is what a sequence-identity baseline would exploit.

Writes data/processed/dimers/orthology/{hits.m8, interologs.tsv, summary.txt}.
Usage: python scripts/ppi/06_orthology_feasibility.py [--threads 16]
MMseqs2 binary: pocket_detect/tools/bin/mmseqs (release 18-8cc5c).
"""
from __future__ import annotations

import argparse
import subprocess
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/processed/dimers"
MMSEQS = "/cluster/project/beltrao/gmagnus/pocket_detect/tools/bin/mmseqs"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()
    out = BASE / "orthology"
    out.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(BASE / "manifest.tsv", sep="\t")
    # unique sequences per accession
    seqs, org_of = {}, {}
    name = None
    for line in (BASE / "sequences.fasta").read_text().splitlines():
        if line.startswith(">"):
            f = line[1:].split()
            name, acc, org = f[0], f[1], f[2]
        else:
            seqs.setdefault(acc, line)
            org_of[acc] = org
    fa = out / "proteins.fasta"
    fa.write_text("".join(f">{k}\n{v}\n" for k, v in seqs.items()))
    hits = out / "hits.m8"
    if not hits.exists():
        subprocess.run([MMSEQS, "easy-search", str(fa), str(fa), str(hits), "/tmp/ppi_mmseqs_tmp", "-s", "7.5",
                        "-e", "1e-3", "-c", "0.5", "--cov-mode", "0", "--threads", str(a.threads),
                        "--max-seqs", "2000", "--format-output", "query,target,fident,evalue,bits,qcov,tcov"],
                       check=True, stdout=subprocess.DEVNULL)
    h = pd.read_csv(hits, sep="\t", names=["q", "t", "fident", "evalue", "bits", "qcov", "tcov"])
    h = h[h.q != h.t]
    h["oq"], h["ot"] = h.q.map(org_of), h.t.map(org_of)
    ident = defaultdict(float)
    for r in h.itertuples():
        k = (r.q, r.t) if r.q < r.t else (r.t, r.q)
        ident[k] = max(ident[k], r.fident)

    def sim(x, y):
        if x == y:
            return 1.0
        return ident.get((x, y) if x < y else (y, x), 0.0)

    by_acc = defaultdict(list)          # accession -> complexes containing it
    cx = m[["modelEntityId", "organism", "type", "uniprotAccession_1", "uniprotAccession_2"]].to_records(index=False)
    for c in cx:
        by_acc[c[3]].append(c)
        by_acc[c[4]].append(c)
    homologs = defaultdict(set)
    for (x, y) in ident:
        homologs[x].add(y)
        homologs[y].add(x)
    rows = []
    for c in cx:
        cid, org, typ, p1, p2 = c
        cands = set()
        for y in homologs[p1] | {p1}:
            for d in by_acc[y]:
                cands.add(tuple(d))
        for d in cands:
            did, dorg, dtyp, q1, q2 = d
            if did <= cid or dtyp != typ:
                continue
            s1 = min(sim(p1, q1), sim(p2, q2))
            s2 = min(sim(p1, q2), sim(p2, q1))
            s = max(s1, s2)
            if s > 0:
                rows.append((cid, org, did, dorg, typ, s, p1 == q1 or p1 == q2 or p2 == q1 or p2 == q2))
    df = pd.DataFrame(rows, columns=["cx1", "org1", "cx2", "org2", "type", "pair_ident", "share_protein"])
    df.to_csv(out / "interologs.tsv", sep="\t", index=False)
    lines = [f"proteins: {len(seqs)}; homologous protein pairs (E<=1e-3, cov>=0.5): {len(ident)}",
             f"cross-organism protein pairs: {sum(org_of[x] != org_of[y] for x, y in ident)}"]
    for (o1, o2) in [("human", "yeast"), ("human", "ecoli"), ("yeast", "ecoli")]:
        for typ in ["homo", "hetero"]:
            g = df[(df.type == typ) & (((df.org1 == o1) & (df.org2 == o2)) | ((df.org1 == o2) & (df.org2 == o1)))]
            n1 = len(set(g.cx1[g.org1 == o1]) | set(g.cx2[g.org2 == o1]))
            n2 = len(set(g.cx1[g.org1 == o2]) | set(g.cx2[g.org2 == o2]))
            q = g.pair_ident.quantile([0.25, 0.5, 0.75]).round(2).tolist() if len(g) else []
            lines.append(f"{o1}-{o2} {typ:6s}: complex pairs {len(g):6d} | {o1} complexes {n1:5d} | {o2} complexes {n2:5d} "
                         f"| pair identity q25/50/75 {q} | pairs with identity<0.3: {(g.pair_ident < 0.3).sum()}")
    for o in ["human", "yeast", "ecoli"]:
        for typ in ["homo", "hetero"]:
            g = df[(df.type == typ) & (df.org1 == o) & (df.org2 == o)]
            lines.append(f"within {o} {typ}: homologous complex pairs {len(g)} (sharing a protein: {g.share_protein.sum()}), "
                         f"identity<0.5: {(g.pair_ident < 0.5).sum()}")
    txt = "\n".join(lines)
    print(txt)
    (out / "summary.txt").write_text(txt + "\n")


if __name__ == "__main__":
    main()
