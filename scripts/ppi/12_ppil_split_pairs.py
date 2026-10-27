#!/usr/bin/env python
"""PPI-L step 3: homology groups, 60/20/20 group split, ligand-grounded pairs, and the C3 gate (counts only).

Pockets (PI round 2): ONLY cavities with a PDB HET modulator, L-mode on that ligand (11_).  Eligible pocket:
  status ok; ligand parsed; >= 12 heavy atoms; SDF complete (SDF heavy atoms >= 0.8 x atoms of the HET residue
  in the structure); CCD id not in the cofactor/additive list below (not PPI modulators: nucleotides, SAM/SAH,
  CoA esters, flavins, haem, detergents, cryo-additives).
  primary set = PLOC + PLONC ("orthosteric" = at the PPI interface); PLA (allosteric) reported as a variant.
Homology (dataset-own graph; DESIGN §2.1 rule as updated by the PI): chain edges =
  pocketdetect.datasets.leakage.apply_rule on an MMseqs2 all-vs-all (tools/mmseqs, -s 7.5, E <= 1e-3)
  OR Foldseek (exhaustive) min(qTM, tTM) >= 0.5; groups = connected components over chains (pdb_chain).
Split: groups shuffled with SEEDS[0], greedy 60/20/20 by eligible-pocket count (no group is forced).
Pairs (within one split, pockets of DIFFERENT groups): ECFP4 (r=2, 2048) Tc >= 0.5 -> positive (1),
  Tc < 0.3 -> negative (0); 0.3-0.5 not used.  Volume and lining-residue count are stored for size control.
Gate (PI round 2, recorded here BEFORE any similarity score exists): test positives >= 50 pairs spanning
  >= 10 homology groups and >= 5 ligand clusters (Butina 0.6, from 10_); also DESIGN v1's >= 100.
Outputs: data/splits/ppi_l_pockets.parquet (pocket table + group + split; small), data/splits/ppi_l_pairs_{train,val}.parquet,
  data/sealed/ppi_l_test_pairs.parquet (chmod 000), data/processed/ppi/ppil/{mmseqs.m8,foldseek.tsv,chain_groups.parquet},
  results/ppi/ppil_gate.json (counts only).
Usage: python scripts/ppi/12_ppil_split_pairs.py --threads 16
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from pocketdetect.datasets.leakage import M8_COLUMNS, apply_rule

ROOT = Path(__file__).resolve().parents[2]
PPIL = ROOT / "data/processed/ppi/ppil"
SPL = ROOT / "data/splits"
SEALED = ROOT / "data/sealed"
MMSEQS = ROOT / "tools/mmseqs/bin/mmseqs"
FOLDSEEK = ROOT / "tools/foldseek/bin/foldseek"
MIN_HA = 12
POS_TC, NEG_TC = 0.5, 0.3
COFACTOR_ADDITIVE = set("""
SAM SAH SFG 5GP GCP GNP GSP GTP GDP ATP ADP AMP ANP ACP AGS APR APC UDP UTP UMP CTP CDP TTP 3AT C2E CMP PCG
NAD NAI NAP NDP NAJ NHD FAD FDA FMN COA ACO MYA SCA CAA HXC PLM MYR OLA STE PAM HEM HEC HEA PLP TPP BTN H4B
BNG MA4 LMT BOG C8E LDA OLC CLA DMU UMQ HTG SOG PEG PG4 1PE P6G PGE GOL EDO MPD DMS CIT MES EPE TRS FLC
SO4 PO4 ACT CL NA MG ZN CA K
""".split())


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


def homology(threads: int) -> pd.DataFrame:
    fa = PPIL / "chains.fasta"
    env = {**os.environ, "OMP_NUM_THREADS": str(threads)}
    m8 = PPIL / "mmseqs.m8"
    if not m8.exists():
        tmp = PPIL / "tmp_mmseqs"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        run = lambda *x: subprocess.run([str(MMSEQS), *map(str, x)], check=True, env=env)  # noqa: E731
        run("createdb", fa, tmp / "q", "--dbtype", "1", "-v", "1")
        run("search", tmp / "q", tmp / "q", tmp / "r", tmp / "w", "-s", "7.5", "-e", "1e-3", "--max-seqs", "5000",
            "--threads", threads, "-v", "1")
        run("convertalis", tmp / "q", tmp / "q", tmp / "r", m8, "--format-output", ",".join(M8_COLUMNS), "-v", "1")
        shutil.rmtree(tmp, ignore_errors=True)
    fsk = PPIL / "foldseek.tsv"
    if not fsk.exists():
        tmp = PPIL / "tmp_foldseek"
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run([str(FOLDSEEK), "easy-search", str(PPIL / "chains"), str(PPIL / "chains"), str(fsk), str(tmp),
                        "--exhaustive-search", "1", "-e", "10", "--threads", str(threads), "-v", "1",
                        "--format-output", "query,target,evalue,alntmscore,qtmscore,ttmscore,fident"],
                       check=True, env=env)
        shutil.rmtree(tmp, ignore_errors=True)
    h = pd.read_csv(m8, sep="\t", names=M8_COLUMNS, dtype={"query": str, "target": str})
    f = pd.read_csv(fsk, sep="\t", names=["query", "target", "evalue", "alntm", "qtm", "ttm", "fident"],
                    dtype={"query": str, "target": str})
    for c in ("query", "target"):
        f[c] = f[c].str.replace(r"\.pdb$", "", regex=True)
    keys = [ln[1:].strip() for ln in fa.read_text().splitlines() if ln.startswith(">")]
    uf = UF()
    for k in keys:
        uf.find(k)
    se = h[apply_rule(h) & (h["query"] != h["target"])]
    fe = f[(f[["qtm", "ttm"]].min(axis=1) >= 0.5) & (f["query"] != f["target"])]
    for e in (se, fe):
        for q, t in e[["query", "target"]].itertuples(index=False):
            uf.union(q, t)
    g = pd.DataFrame({"chain_key": keys})
    g["group"] = g.chain_key.map(uf.find)
    g.attrs["n_seq_edges"], g.attrs["n_struct_edges"] = len(se), len(fe)
    print(f"[ppil] homology: {len(keys)} chains, seq edges {len(se)}, struct edges {len(fe)}, "
          f"groups {g.group.nunique()}, largest {g.group.value_counts().iloc[0]}", flush=True)
    return g


def onbits_matrix(L: pd.DataFrame) -> np.ndarray:
    X = np.zeros((len(L), 2048), np.float32)
    for i, b in enumerate(L.ecfp4_onbits):
        X[i, np.asarray(b, int)] = 1
    return X


def make_pairs(P: pd.DataFrame, X: np.ndarray) -> pd.DataFrame:
    inter = X @ X.T
    cnt = X.sum(1)
    tc = inter / np.maximum(cnt[:, None] + cnt[None, :] - inter, 1)
    grp = P.group.values
    i, j = np.triu_indices(len(P), 1)
    keep = grp[i] != grp[j]
    i, j = i[keep], j[keep]
    t = tc[i, j]
    lab = np.where(t >= POS_TC, 1, np.where(t < NEG_TC, 0, -1))
    m = lab >= 0
    i, j, t, lab = i[m], j[m], t[m], lab[m]
    pid = P.pocket_id.values
    return pd.DataFrame({"pocket_a": pid[i], "pocket_b": pid[j], "label": lab.astype(np.int8), "ecfp4_tc": t.astype(np.float32),
                         "group_a": grp[i], "group_b": grp[j],
                         "ligand_cluster_a": P.ligand_cluster.values[i], "ligand_cluster_b": P.ligand_cluster.values[j],
                         "volume_a": P.volume_A3.values[i], "volume_b": P.volume_A3.values[j],
                         "label_a": P.label.values[i], "label_b": P.label.values[j]})


def gate_counts(pairs: pd.DataFrame) -> dict:
    pos = pairs[pairs.label == 1]
    return {"positives": int(len(pos)), "negatives": int((pairs.label == 0).sum()),
            "pos_groups": int(len(set(pos.group_a) | set(pos.group_b))),
            "pos_ligand_clusters": int(len(set(pos.ligand_cluster_a) | set(pos.ligand_cluster_b))),
            "pos_pockets": int(len(set(pos.pocket_a) | set(pos.pocket_b))),
            "pos_identical_molecule": int((pos.ecfp4_tc >= 0.999).sum())}


def write_sealed(frames: dict) -> dict:
    SEALED.mkdir(exist_ok=True)
    mode = SEALED.stat().st_mode & 0o7777
    os.chmod(SEALED, mode | 0o700)
    out = {}
    try:
        for name, df in frames.items():
            f = SEALED / name
            if f.exists():
                os.chmod(f, 0o600)
            df.to_parquet(f, index=False)
            out[name] = hashlib.sha256(f.read_bytes()).hexdigest()
            print(f"[sealed] {name} sha256 {out[name]} rows {len(df)}", flush=True)
            os.chmod(f, 0o000)
    finally:
        os.chmod(SEALED, mode)
    return out


def split_groups(P: pd.DataFrame, seed: int) -> dict:
    gs = P.group.value_counts()
    rng = np.random.default_rng(seed)
    order = [gs.index[k] for k in rng.permutation(len(gs))]
    n = gs.sum()
    tgt = {"train": 0.6 * n, "val": 0.2 * n, "test": 0.2 * n}
    cnt = dict.fromkeys(tgt, 0)
    out = {}
    for g in order:
        s = max(tgt, key=lambda k: (tgt[k] - cnt[k]) / tgt[k])
        out[g] = s
        cnt[s] += gs[g]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()
    from pocketcompare.seeds import SEEDS
    G = homology(a.threads)
    G.to_parquet(PPIL / "chain_groups.parquet", index=False)
    P = pd.read_parquet(PPIL / "pockets.parquet")
    Lfp = pd.read_parquet(PPIL / "ligand_instances.parquet", columns=["pocket_id", "ecfp4_onbits"])
    P = P.merge(Lfp, on="pocket_id", how="left")
    P = P.merge(G.rename(columns={"chain_key": "key"}), on="key", how="left")
    P["sdf_complete"] = P.heavy_atoms >= 0.8 * P.n_ligand_atoms_struct.fillna(0)
    P["cofactor_additive"] = P.lig.isin(COFACTOR_ADDITIVE)
    P["eligible_any"] = ((P.status == "ok") & P.smiles.notna() & (P.heavy_atoms >= MIN_HA) & P.sdf_complete
                         & ~P.cofactor_additive & P.group.notna())
    P["in_primary"] = P.eligible_any & P.label.isin(["PLOC", "PLONC"])
    excl = {"not_ok": int((P.status != "ok").sum()), "no_smiles": int(P.smiles.isna().sum()),
            "lt12HA": int((P.heavy_atoms < MIN_HA).sum()), "sdf_incomplete": int((~P.sdf_complete).sum()),
            "cofactor_additive": int(P.cofactor_additive.sum()), "eligible_any": int(P.eligible_any.sum()),
            "primary_PLOC_PLONC": int(P.in_primary.sum()), "PLA_eligible": int((P.eligible_any & (P.label == "PLA")).sum())}
    print("[ppil] eligibility", excl, flush=True)

    res = {"exclusions": excl, "homology": {"chains": int(len(G)), "groups": int(G.group.nunique()),
                                            "largest_group_chains": int(G.group.value_counts().iloc[0]),
                                            "seq_edges": G.attrs["n_seq_edges"], "struct_edges": G.attrs["n_struct_edges"]}}
    variants = {"primary": P[P.in_primary], "with_PLA": P[P.eligible_any]}
    for vname, V in variants.items():
        V = V.reset_index(drop=True)
        sp = split_groups(V, SEEDS[0])
        V["split"] = V.group.map(sp)
        X = onbits_matrix(V)
        per = {}
        allpairs = {}
        for s in ("train", "val", "test"):
            m = (V.split == s).values
            pr = make_pairs(V[m].reset_index(drop=True), X[m])
            allpairs[s] = pr
            per[s] = {"pockets": int(m.sum()), "groups": int(V[m].group.nunique()),
                      "ligand_clusters": int(V[m].ligand_cluster.nunique()), **gate_counts(pr)}
        # what a random split could give at best: all cross-group positives in the whole set
        whole = make_pairs(V, X)
        per["all_cross_group"] = gate_counts(whole)
        per["top_group_share_of_cross_group_positives"] = float(
            pd.concat([whole[whole.label == 1].group_a, whole[whole.label == 1].group_b]).value_counts(normalize=True)
            .iloc[0] / 2 * 2) if (whole.label == 1).any() else 0.0
        t = per["test"]
        per["gate_PI_round2"] = {"rule": "test positives >= 50, spanning >= 10 groups and >= 5 ligand clusters",
                                 "pass": bool(t["positives"] >= 50 and t["pos_groups"] >= 10 and t["pos_ligand_clusters"] >= 5)}
        per["gate_DESIGN_v1"] = {"rule": "test cross-group positives >= 100", "pass": bool(t["positives"] >= 100)}
        res[vname] = per
        if vname == "primary":
            V.drop(columns=["ecfp4_onbits", "lmode_idx", "d_members"], errors="ignore").to_parquet(
                SPL / "ppi_l_pockets.parquet", index=False)
            for s in ("train", "val"):
                allpairs[s].to_parquet(SPL / f"ppi_l_pairs_{s}.parquet", index=False)
            res["sealed_sha256"] = write_sealed({"ppi_l_test_pairs.parquet": allpairs["test"]})
            # positives in the whole primary set, by protein family pair (diagnostic: what do they look like?)
            pos = whole[whole.label == 1]
            fam = dict(zip(V.pocket_id, V.pfam_name.fillna(V.uniprot)))
            fp = pd.Series([" | ".join(sorted((str(fam[x]), str(fam[y])))) for x, y in zip(pos.pocket_a, pos.pocket_b)])
            res["primary_all_cross_group_positive_family_pairs_top"] = fp.value_counts().head(15).to_dict()
    (ROOT / "results/ppi").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/ppi/ppil_gate.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
