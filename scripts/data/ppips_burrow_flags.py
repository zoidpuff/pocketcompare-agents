#!/usr/bin/env python
"""PPIPS complexes with a DIRECT homology edge to BURROW train/dev chains (stratification flag; membership unchanged).

Audit D15: BURROW prepares the PPIPS pockets, so PPIPS val/test results are reported stratified by whether a complex
contains a chain homologous to a BURROW train/dev chain. Same edge rule as the homology graph:
  seq : MMseqs2 rule edges of data/splits/homology_edges.parquet between the complex's chain sequences (dimer nodes)
        and BURROW train/dev representative chains (and, separately, their assembly partners);
  fs  : Foldseek EXHAUSTIVE search (-e 10, -a) of EVERY PPIPS chain model (data/processed/ppi/ppips/chains_all, one
        file per complex chain, written by scripts/ppi/21_ppips_homology.py) against the BURROW representative and
        partner structures (subset of the graph's Foldseek DB); exact TM (--exact-tmscore 1) for all hits with
        approximate min(qTM, tTM) >= 0.45; edge iff exact qTM >= 0.5 and tTM >= 0.5.
Output: data/splits/ppips_burrow_homology.parquet (complex, split, burrow_rep_edge, burrow_rep_seq_edge,
        burrow_rep_fs_edge, burrow_partner_edge, burrow_any_edge) and counts in data/splits/ppips_burrow_homology.json.
Usage: python scripts/data/ppips_burrow_flags.py --threads 24 [--work /tmp/gm_splits/homology]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.splitutil import SPLITS, SidGraph, load_homology  # noqa: E402

FOLDSEEK = ROOT / "tools/foldseek/bin/foldseek"
CHAINS = ROOT / "data/processed/ppi/ppips/chains_all"
COLS = ["query", "target", "qtmscore", "ttmscore", "evalue"]


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=24)
    ap.add_argument("--work", default="/tmp/gm_splits/homology")
    args = ap.parse_args()
    work = Path(args.work)
    w = work / "ppips_burrow"
    shutil.rmtree(w, ignore_errors=True)
    w.mkdir(parents=True)

    nodes, edges = load_homology()
    cx = pd.read_parquet(SPLITS / "ppips_complex_splits.parquet")[["complex", "split"]]
    rep = nodes[nodes.dataset.isin(["burrow_train", "burrow_dev"])]
    par = nodes[nodes.dataset == "burrow_partner"]
    # ---- sequence edges via the graph (dimer node = dimers:<complex>_<chain>)
    g = SidGraph(nodes, edges[edges.seq_edge])
    dn = nodes[nodes.dataset == "dimers"].copy()
    dn["complex"] = dn.node_id.str.split(":").str[1].str.rsplit("_", n=1).str[0]
    dn = dn[dn.complex.isin(cx.complex)]
    dn["seq_rep"] = g.touches(dn.sid, rep.sid).values
    dn["seq_par"] = g.touches(dn.sid, par.sid).values

    # ---- structure: all PPIPS chain models vs BURROW structures (exhaustive, exact TM for candidates)
    nf = pd.read_parquet(ROOT / "data/processed/homology/node_files.parquet")
    tgt = nf[nf.node_id.isin(set(rep.node_id) | set(par.node_id)) & nf.fs_key.notna()]
    (w / "t.ids").write_text("\n".join(str(int(k)) for k in sorted(set(tgt.fs_key))) + "\n")
    src = work / "fsdb" / "all"
    for suf in ("", "_ss", "_ca", "_h"):
        run([FOLDSEEK, "createsubdb", w / "t.ids", str(src) + suf, str(w / "t") + suf, "-v", "1"])
    files = sorted(str(p) for p in CHAINS.glob("*.pdb"))
    (w / "q.tsv").write_text("\n".join(files) + "\n")
    run([FOLDSEEK, "createdb", w / "q.tsv", w / "q", "--threads", args.threads, "-v", "1"])
    run([FOLDSEEK, "search", w / "q", w / "t", w / "aln", w / "tmp", "--exhaustive-search", "1", "-e", "10", "-a",
         "--threads", args.threads, "-v", "1"])
    run([FOLDSEEK, "convertalis", w / "q", w / "t", w / "aln", w / "aln.m8", "--format-output", ",".join(COLS),
         "--threads", args.threads, "-v", "1"])
    h = pd.read_csv(w / "aln.m8", sep="\t", header=None, names=COLS)
    cand = h[np.minimum(h.qtmscore, h.ttmscore) >= 0.45]
    qlk = pd.read_csv(str(w / "q") + ".lookup", sep="\t", header=None, names=["key", "name", "f"])
    tlk = pd.read_csv(str(src) + ".lookup", sep="\t", header=None, names=["key", "name", "f"])
    qk, tk = dict(zip(qlk.name, qlk.key)), dict(zip(tlk.name, tlk.key))
    with open(w / "cand.tsv", "w") as fh:
        for q, t in sorted({(qk[a], tk[b]) for a, b in zip(cand["query"], cand["target"])}):
            fh.write(f"{q}\t{t}\t0\t0\n")
    run([FOLDSEEK, "tsv2db", w / "cand.tsv", w / "cand_pref", "--output-dbtype", "7", "-v", "1"])
    run([FOLDSEEK, "structurealign", w / "q", w / "t", w / "cand_pref", w / "cand_aln", "-a", "-e", "10",
         "--threads", args.threads, "-v", "1"])
    run([FOLDSEEK, "convertalis", w / "q", w / "t", w / "cand_aln", w / "exact.m8", "--format-output", ",".join(COLS),
         "--exact-tmscore", "1", "--threads", args.threads, "-v", "1"])
    ex = pd.read_csv(w / "exact.m8", sep="\t", header=None, names=COLS)
    ex = ex[np.minimum(ex.qtmscore, ex.ttmscore) >= 0.5]
    key2node = dict(zip(tgt.fs_key.astype(int), tgt.node_id))
    tname2key = dict(zip(tlk.name, tlk.key))
    ex["tnode"] = ex["target"].map(lambda n: key2node.get(int(tname2key[n])))
    ex["complex"] = ex["query"].str.replace(r"\.pdb$", "", regex=True).str.rsplit("_", n=1).str[0]
    fs_rep = set(ex[ex.tnode.isin(set(rep.node_id))].complex)
    fs_par = set(ex[ex.tnode.isin(set(par.node_id))].complex)

    out = cx.copy()
    seq_rep = set(dn[dn.seq_rep].complex)
    seq_par = set(dn[dn.seq_par].complex)
    out["burrow_rep_seq_edge"] = out.complex.isin(seq_rep)
    out["burrow_rep_fs_edge"] = out.complex.isin(fs_rep)
    out["burrow_rep_edge"] = out.burrow_rep_seq_edge | out.burrow_rep_fs_edge
    out["burrow_partner_edge"] = out.complex.isin(seq_par | fs_par)
    out["burrow_any_edge"] = out.burrow_rep_edge | out.burrow_partner_edge
    out.to_parquet(SPLITS / "ppips_burrow_homology.parquet", index=False)
    counts = {s: {"n_complexes": int((out.split == s).sum()),
                  **{c: int(out[out.split == s][c].sum()) for c in
                     ("burrow_rep_edge", "burrow_rep_seq_edge", "burrow_rep_fs_edge", "burrow_partner_edge",
                      "burrow_any_edge")}} for s in ("train", "val", "test")}
    counts["n_query_models"] = len(files)
    counts["n_burrow_target_structures"] = int(len(set(tgt.fs_key)))
    (SPLITS / "ppips_burrow_homology.json").write_text(json.dumps(counts, indent=1))
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main()
