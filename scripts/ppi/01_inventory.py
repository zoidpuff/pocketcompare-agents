#!/usr/bin/env python
"""Inventory of the AFDB predicted-dimer set (task 1 of the PPI characterisation).

Reads every manifest and every PDB file under DIMERS (read-only) and writes
  OUT/manifest.tsv     one row per dimer file: organism, type, ids, accessions, genes, ipTM/ipSAE/pDockQ2,
                       chains, per-chain length / mean pLDDT / fraction pLDDT<50 and <70, numbering ranges,
                       interface size (residues with a heavy atom <= 5 A of the other chain) and interface pLDDT,
                       per-residue B-factor constancy check (B-factor = pLDDT?), chain sequence identity flag.
  OUT/sequences.fasta  per-chain sequences from ATOM records (>{entity}_{chain} accession), for MMseqs2.
  OUT/inventory_summary.txt  counts and quantiles (printed too).

Usage: python scripts/ppi/01_inventory.py [--workers 16]
Deterministic; no randomness. Runtime ~2-4 min with 16 workers (reads ~7 GB of PDB text).
"""
from __future__ import annotations

import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

DIMERS = Path("/cluster/project/beltrao/gmagnus/dimers")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/dimers"
ORGS = {"human": "afdb_human_dimers", "yeast": "afdb_yeast_dimers", "ecoli": "afdb_ecoli_dimers"}
TYPES = {"homo": "homodimers", "hetero": "heterodimers"}
AA3 = dict(ALA="A", ARG="R", ASN="N", ASP="D", CYS="C", GLN="Q", GLU="E", GLY="G", HIS="H", ILE="I", LEU="L",
           LYS="K", MET="M", PHE="F", PRO="P", SER="S", THR="T", TRP="W", TYR="Y", VAL="V")
IFACE_CUT = 5.0  # A, heavy-atom contact defining interface residues


def parse_pdb(path: str) -> dict:
    chains, resid, resn, bf, xyz, dbref = [], [], [], [], [], {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("ATOM"):
                if line[76:78].strip() == "H":
                    continue
                chains.append(line[21])
                resid.append(int(line[22:26]))
                resn.append(line[17:20])
                bf.append(float(line[60:66]))
                xyz.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
            elif line.startswith("DBREF"):
                dbref[line[12]] = line[33:41].strip()
            elif line.startswith("ENDMDL"):
                break
    ch = np.array(chains)
    rid = np.array(resid)
    bf = np.array(bf)
    xyz = np.array(xyz, dtype=np.float32)
    rec = {"file": path, "n_models_or_chains": len(set(chains)), "chains": "".join(dict.fromkeys(chains)),
           "n_atoms": len(chains)}
    # residue table
    key = np.char.add(ch.astype("U1"), rid.astype("U6"))
    _, first, inv = np.unique(key, return_index=True, return_inverse=True)
    # B-factor constant within residue?
    bmax = np.zeros(len(first))
    bmin = np.full(len(first), 1e9)
    np.maximum.at(bmax, inv, bf)
    np.minimum.at(bmin, inv, bf)
    rec["bfac_const_per_res"] = bool(np.all(bmax - bmin < 1e-6))
    rec["bfac_min"], rec["bfac_max"] = float(bf.min()), float(bf.max())
    res_ch = ch[first]
    res_pl = bf[first]
    # interface residues: heavy atom of chain X within IFACE_CUT of other chain
    cl = list(dict.fromkeys(chains))
    iface_res = np.zeros(len(first), bool)
    if len(cl) == 2:
        a, b = ch == cl[0], ch == cl[1]
        ta, tb = cKDTree(xyz[a]), cKDTree(xyz[b])
        da, _ = tb.query(xyz[a], distance_upper_bound=IFACE_CUT)
        db, _ = ta.query(xyz[b], distance_upper_bound=IFACE_CUT)
        hit = np.zeros(len(ch), bool)
        hit[np.flatnonzero(a)[np.isfinite(da)]] = True
        hit[np.flatnonzero(b)[np.isfinite(db)]] = True
        np.logical_or.at(iface_res, inv, hit)
    seqs = {}
    for i, c in enumerate(cl[:2]):
        m = res_ch == c
        order = np.argsort(rid[first][m])
        seq = "".join(AA3.get(resn[j], "X") for j in first[m][order])
        seqs[c] = seq
        nums = rid[first][m]
        p = res_pl[m]
        s = "AB"[i]
        rec[f"chain_{s}"] = c
        rec[f"acc_{s}_dbref"] = dbref.get(c, "")
        rec[f"len_{s}"] = int(m.sum())
        rec[f"num_{s}"] = f"{nums.min()}-{nums.max()}"
        rec[f"num_contig_{s}"] = bool(nums.max() - nums.min() + 1 == m.sum())
        rec[f"plddt_{s}"] = float(p.mean())
        rec[f"f_pl50_{s}"] = float((p < 50).mean())
        rec[f"f_pl70_{s}"] = float((p < 70).mean())
        rec[f"n_iface_{s}"] = int(iface_res[m].sum())
    rec["iface_plddt"] = float(res_pl[iface_res].mean()) if iface_res.any() else np.nan
    rec["n_iface"] = int(iface_res.sum())
    rec["same_seq"] = len(seqs) == 2 and len(set(seqs.values())) == 1
    rec["_seqs"] = seqs
    return rec


def load_manifests() -> pd.DataFrame:
    rows = []
    for org, od in ORGS.items():
        for typ, td in TYPES.items():
            d = DIMERS / od / td
            cand = pd.read_csv(d / "candidates.csv")
            man = pd.read_csv(d / "download_manifest.csv")
            files = sorted(p.name for p in d.glob("*.pdb"))
            n_man_rows = len(man)
            man_ok = man[man.status.isin(["downloaded", "copied", "present"])].drop_duplicates("modelEntityId")
            n_err = man[man.status == "download_error"].modelEntityId.nunique()
            ids = {f[:-4] for f in files}
            print(f"{org:6s} {typ:6s} files={len(files):5d} candidates={len(cand):5d} manifest_rows={n_man_rows:5d} "
                  f"manifest_unique_ok={len(man_ok):5d} download_errors={n_err:3d} "
                  f"cand_without_file={len(set(cand.modelEntityId) - ids):3d} file_not_in_cand={len(ids - set(cand.modelEntityId))}")
            c = cand[cand.modelEntityId.isin(ids)].drop_duplicates("modelEntityId").copy()
            c["organism"], c["type"] = org, typ
            c["path"] = [str(d / f"{m}.pdb") for m in c.modelEntityId]
            rows.append(c)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0, help="debug: only parse the first N files")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_manifests()
    if args.limit:
        df = df.head(args.limit)
    with Pool(args.workers) as pool:
        recs = pool.map(parse_pdb, df.path.tolist(), chunksize=16)
    with open(OUT / "sequences.fasta", "w") as fh:
        for (_, r), rec in zip(df.iterrows(), recs):
            for i, (c, s) in enumerate(rec["_seqs"].items()):
                acc = r[f"uniprotAccession_{i + 1}"]
                fh.write(f">{r.modelEntityId}_{c} {acc} {r.organism} {r.type}\n{s}\n")
    info = pd.DataFrame([{k: v for k, v in rec.items() if k != "_seqs"} for rec in recs]).drop(columns="file")
    m = pd.concat([df.reset_index(drop=True), info], axis=1)
    m["acc_match"] = (m.acc_A_dbref == m.uniprotAccession_1) & (m.acc_B_dbref == m.uniprotAccession_2)
    m.to_csv(OUT / "manifest.tsv", sep="\t", index=False)
    summarize(m)


def summarize(m: pd.DataFrame) -> None:
    lines = []
    q = lambda s: " ".join(f"{x:.2f}" for x in s.quantile([0.05, 0.25, 0.5, 0.75, 0.95]))  # noqa: E731
    lines.append(f"total dimers with file: {len(m)}")
    lines.append(f"chains per file: {m.n_models_or_chains.value_counts().to_dict()}; chain ids: {m.chains.value_counts().to_dict()}")
    lines.append(f"B-factor constant within every residue (=per-residue pLDDT): {m.bfac_const_per_res.mean():.4f}; "
                 f"B range {m.bfac_min.min():.1f}-{m.bfac_max.max():.1f}")
    lines.append(f"DBREF accessions match manifest: {m.acc_match.mean():.4f}; numbering contiguous from 1: "
                 f"{(m.num_contig_A & m.num_contig_B & m.num_A.str.startswith('1-') & m.num_B.str.startswith('1-')).mean():.4f}")
    lines.append(f"homodimers with identical chain sequences: {m[m.type == 'homo'].same_seq.mean():.4f}; "
                 f"heterodimers with identical sequences: {m[m.type == 'hetero'].same_seq.sum()}")
    lines.append(f"heterodimers whose accessions are equal: {(m[m.type == 'hetero'].uniprotAccession_1 == m[m.type == 'hetero'].uniprotAccession_2).sum()}")
    lines.append("quantiles 5/25/50/75/95 per organism x type:")
    for (o, t), g in m.groupby(["organism", "type"], sort=False):
        lines.append(f"  {o:6s} {t:6s} n={len(g):5d} | n_res {q(g.n_residues)} | ipTM {q(g.ipTM)} | ipSAE {q(g.max_ipSAE)} "
                     f"| pDockQ2 {q(g.max_pDockQ2)} | mean pLDDT {q((g.plddt_A * g.len_A + g.plddt_B * g.len_B) / (g.len_A + g.len_B))} "
                     f"| iface pLDDT {q(g.iface_plddt)} | n_iface_res {q(g.n_iface)} | frac pLDDT<50 {q((g.f_pl50_A * g.len_A + g.f_pl50_B * g.len_B) / (g.len_A + g.len_B))}")
    lines.append(f"min ipTM {m.ipTM.min():.3f}; min ipSAE {m.max_ipSAE.min():.3f}; min pDockQ2 {m.max_pDockQ2.min():.3f}; "
                 f"n_residues max {m.n_residues.max()}; dimers with n_iface==0: {(m.n_iface == 0).sum()}")
    txt = "\n".join(lines)
    print(txt)
    (OUT / "inventory_summary.txt").write_text(txt + "\n")


if __name__ == "__main__":
    sys.exit(main())
