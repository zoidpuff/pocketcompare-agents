#!/usr/bin/env python
"""Independent re-check of the homology graph and all splits (different code paths from the builders).

  * edges: re-derived from the RAW MMseqs2 all-vs-all output (rule re-implemented here, not imported) and from the
    Foldseek hit table (min(qTM, tTM) >= 0.5), compared with data/splits/homology_edges.parquet;
    sid <-> sequence consistency checked against data/processed/homology/sequences.fasta.
  * graph algorithms: networkx (builders use scipy.sparse).
  * TOUGH-M1: dev/test/excluded groups are whole TOUGH-M1 components; no direct edge dev<->test; no test node
    adjacent to BURROW; no dev node adjacent to ProSPECCTs/Vertex/af_set; excluded groups touch both; dev pair table
    is within-dev; counts in tough_m1_split_counts.json reproduced from the files; sealed files have mode 000.
  * BLiPS: no train/val protein adjacent to TOUGH-M1-test/ProSPECCTs/Vertex/af_set; no train-val edge, no group
    shared; label rules recomputed with RDKit's legacy Morgan API + DataStructs Tanimoto from BioLiP SMILES
    (positives max Tc >= 0.7, negatives < 0.3, n_shared), qualifying-ligand rules, <= 3 sites/protein, cluster
    caps; pairs within partition and across groups; counts reproduced.
  * data/splits/SHA256SUMS.txt matches.
Sealed test files are NOT opened (mode and presence only). Exit code 1 on any failure.
Usage: python scripts/data/verify_splits.py
"""
from __future__ import annotations

import gzip
import json
import os
import stat
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path

import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SPL = ROOT / "data/splits"
SEALED = ROOT / "data/sealed"
PROC = ROOT / "data/processed/homology"
PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
FAIL = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def main():
    nodes = pd.read_parquet(SPL / "homology_nodes.parquet")
    edges = pd.read_parquet(SPL / "homology_edges.parquet")

    # ---------------- sequences / sids
    seqs, name = {}, None
    for line in open(PROC / "sequences.fasta"):
        if line.startswith(">"):
            name = line[1:].strip()
        else:
            seqs[name] = line.strip()
    check(len(set(seqs.values())) == len(seqs), "sid <-> sequence is one-to-one")
    check(set(nodes.sid) <= set(seqs), "every node sid has a sequence")

    # ---------------- edges re-derived from raw search outputs
    cols = ["query", "target", "fident", "alnlen", "qlen", "tlen", "qcov", "tcov", "evalue", "bits"]
    raw = pd.read_csv(PROC / "mmseqs_allvsall.m8", sep="\t", header=None, names=cols)
    ok = ((raw.evalue < 1e-3) & (raw.fident >= 0.3) & ((raw.qcov >= 0.5) | (raw.tcov >= 0.5) | (raw.alnlen >= 80))
          & (raw["query"] != raw["target"]))
    seq_e = {tuple(sorted(p)) for p in zip(raw["query"][ok], raw["target"][ok])}
    fs = pd.read_parquet(PROC / "foldseek_allvsall_tm04.parquet")
    fok = (fs.qtmscore >= 0.5) & (fs.ttmscore >= 0.5)
    fs_e = {tuple(sorted(p)) for p in zip(fs["query"][fok], fs["target"][fok])}
    built = {(a, b): (s, f) for a, b, s, f in zip(edges.sid_a, edges.sid_b, edges.seq_edge, edges.fs_edge)}
    check({k for k, v in built.items() if v[0]} == seq_e, f"seq edges reproduced from raw MMseqs2 m8 ({len(seq_e)})")
    check({k for k, v in built.items() if v[1]} == fs_e, f"fs edges reproduced from Foldseek hits ({len(fs_e)})")

    G = nx.Graph()
    G.add_nodes_from(seqs)
    G.add_edges_from(seq_e | fs_e)
    sid_of = dict(zip(nodes.node_id, nodes.sid))
    ds_sids = nodes.groupby("dataset").sid.agg(set).to_dict()

    def nbr(sids):  # closed neighbourhood
        out = set(sids)
        for s in sids:
            out.update(G.neighbors(s))
        return out

    # within-dataset components reproduce group ids (partition of nodes)
    for gname, sub in nodes[nodes.group_dataset.notna()].groupby("group_dataset"):
        H = G.subgraph(set(sub.sid))
        comp = {s: i for i, c in enumerate(nx.connected_components(H)) for s in c}
        a = sub.sid.map(comp)
        same = pd.crosstab(a, sub.group_id).astype(bool).sum(axis=1).max() == 1 and \
            pd.crosstab(sub.group_id, a).astype(bool).sum(axis=1).max() == 1
        check(same, f"{gname}: group_id == networkx components ({sub.group_id.nunique()} groups)")

    # ---------------- TOUGH-M1
    tm = pd.read_parquet(SPL / "tough_m1_pockets_split.parquet")
    tc = json.loads((SPL / "tough_m1_split_counts.json").read_text())
    check(tm.groupby("group_id").partition.nunique().max() == 1, "TOUGH-M1: every group in exactly one partition")
    part_s = {p: set(tm[tm.partition == p].sid) for p in ("dev", "test", "excluded")}
    check(not (nbr(part_s["dev"]) & part_s["test"]), "TOUGH-M1: no direct edge / shared sequence dev <-> test")
    burrow = ds_sids["burrow_train"] | ds_sids["burrow_dev"] | ds_sids["burrow_partner"]
    ppi_test = set(nodes[(nodes.dataset == "ppi_l") & nodes.ppi_split.fillna("").str.contains("test")].sid)
    sealed = ds_sids["prospeccts"] | ds_sids["vertex"] | ds_sids["af_set"] | ppi_test
    check(not (nbr(part_s["test"]) & burrow), "TOUGH-M1-test: no node adjacent to BURROW train/dev/partner")
    check(not (nbr(part_s["dev"]) & sealed), "TOUGH-M1-dev: no node adjacent to ProSPECCTs/Vertex/af_set/PPI-L-test")
    for gid, gdf in tm[tm.partition == "excluded"].groupby("group_id"):
        s = set(gdf.sid)
        if not (nbr(s) & burrow and nbr(s) & sealed):
            check(False, f"excluded group {gid} touches both")
            break
    else:
        check(True, "TOUGH-M1: every excluded group touches BURROW and a sealed set")
    for gid, gdf in tm[tm.partition == "dev"].groupby("group_id"):
        if not nbr(set(gdf.sid)) & burrow:
            check(False, f"dev group {gid} has no BURROW neighbour")
            break
    else:
        check(True, "TOUGH-M1: every dev group touches BURROW")
    dev = pd.read_parquet(SPL / "tough_m1_dev_pairs.parquet")
    dset = set(tm[tm.partition == "dev"].pocket_id)
    check(dev.pocket_a.isin(dset).all() and dev.pocket_b.isin(dset).all(), "TOUGH-M1 dev pairs: both pockets dev")
    check(int((dev.label == 1).sum()) == tc["dev"]["n_pos"] and int((dev.label == 0).sum()) == tc["dev"]["n_neg"],
          "TOUGH-M1 dev pos/neg counts reproduced")
    for p in ("dev", "test", "excluded"):
        sub = tm[tm.partition == p]
        check(len(sub) == tc[p]["n_pockets"] and sub.group_id.nunique() == tc[p]["n_groups"]
              and sub.ligand_cluster.nunique() == tc[p]["n_ligand_clusters"], f"TOUGH-M1 {p}: pocket/group/cluster counts")
    for f in ("tough_m1_test_pairs.parquet", "tough_m1_pairs.parquet", "blips_test_pairs.parquet",
              "blips_test_sites.parquet", "prospeccts_pairs.parquet", "vertex_pairs.parquet"):
        p = SEALED / f
        check(p.exists() and stat.S_IMODE(os.stat(p).st_mode) == 0, f"sealed {f} present with mode 000")
    for f in ("TOUGH-M1_positive.list", "TOUGH-M1_negative.list") + tuple(
            f"{t}-TOUGH-M1_{l}.score" for t in ("APoc", "G-LoSA", "SiteEngine") for l in ("positive", "negative")):
        p = ROOT / "data/raw/tough_m1/downloads" / f
        check(stat.S_IMODE(os.stat(p).st_mode) == 0, f"raw {f} mode 000")

    # ---------------- BLiPS
    S = pd.read_parquet(SPL / "blips_sites.parquet")
    bc = json.loads((SPL / "blips_split_counts.json").read_text())
    tv = S[S.partition.isin(["train", "val"])]
    tough_test = set(tm[tm.partition == "test"].sid)
    for name_, tg in (("TOUGH-M1-test", tough_test), ("ProSPECCTs", ds_sids["prospeccts"]),
                      ("Vertex", ds_sids["vertex"]), ("af_set/BLiPS-test", ds_sids["af_set"]), ("PPI-L-test", ppi_test)):
        check(not (nbr(set(tv.sid)) & tg), f"BLiPS train/val: no protein adjacent to {name_}")
    tr_s, va_s = set(S[S.partition == "train"].sid), set(S[S.partition == "val"].sid)
    check(not (nbr(tr_s) & va_s), "BLiPS: no direct edge train <-> val")
    H = G.subgraph(tr_s | va_s)
    mixed = [c for c in nx.connected_components(H) if c & tr_s and c & va_s]
    check(not mixed, "BLiPS: no train+val connected component")
    check(S.groupby("group_id").partition.nunique().max() == 1, "BLiPS: groups do not span partitions")
    check(S.groupby("protein").size().max() <= 3, "BLiPS: <= 3 sites per protein")
    check(S.site_id.is_unique, "BLiPS: site ids unique")

    # ligand rules with a different fingerprint code path
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import AllChem
    RDLogger.DisableLog("rdApp.*")
    smi = {}
    with gzip.open(PD / "data/raw/biolip2/current/ligand.tsv.gz", "rt") as fh:
        for line in fh:
            if not line.startswith("#"):
                f = line.rstrip("\n").split("\t")
                smi[f[0]] = f[4] if len(f) > 4 else ""
    add = set()
    for line in open(ROOT / "data/ref/additives.txt"):
        add |= set(line.split("#")[0].split())
    fp_cache, ha_cache = {}, {}

    def mol(c):
        for s in smi.get(c, "").split(";"):
            m = Chem.MolFromSmiles(s.strip()) if s.strip() else None
            if m is not None:
                return m
        for s in smi.get(c, "").split(";"):
            m = Chem.MolFromSmiles(s.strip(), sanitize=False) if s.strip() else None
            if m is not None:
                m.UpdatePropertyCache(strict=False)
                Chem.GetSymmSSSR(m)
                return m
        return None

    def fp(c):
        if c not in fp_cache:
            m = mol(c)
            ha_cache[c] = m.GetNumHeavyAtoms() if m is not None else 0
            fp_cache[c] = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048) if m is not None else None
        return fp_cache[c]

    bad_q = 0
    for r in tv.itertuples():
        q = r.q_ccds.split(";")
        for c in q:
            fp(c)
        exp = sorted(c for c in r.all_ccds.split(";") if c and fp(c) is not None and ha_cache[c] >= 10 and c not in add)
        if exp != sorted(q) or r.label_ccd != max(q, key=lambda c: (ha_cache[c], c)):
            bad_q += 1
    check(bad_q == 0, f"BLiPS train/val: qualifying sets and label ligands recomputed ({bad_q} mismatches)")
    site = tv.set_index("site_id")
    tc_cache = {}

    def tc(a, b):
        k = (a, b) if a <= b else (b, a)
        if k not in tc_cache:
            tc_cache[k] = DataStructs.TanimotoSimilarity(fp(a), fp(b))
        return tc_cache[k]

    for p in ("train", "val"):
        df = pd.read_parquet(SPL / f"blips_{p}_pairs.parquet")
        sa, sb = site.loc[df.site_a], site.loc[df.site_b]
        check((sa.partition.values == p).all() and (sb.partition.values == p).all(), f"BLiPS {p}: pairs within partition")
        check((sa.group_id.values != sb.group_id.values).all(), f"BLiPS {p}: pairs across homology groups")
        check(not df[["site_a", "site_b"]].apply(lambda x: tuple(sorted(x)), axis=1).duplicated().any(),
              f"BLiPS {p}: no duplicate pairs")
        bad_pos = bad_neg = bad_ns = 0
        for r, qa, qb in zip(df.itertuples(), sa.q_ccds, sb.q_ccds):
            A, B = qa.split(";"), qb.split(";")
            mx = max(tc(x, y) for x in A for y in B)
            if r.label == 1:
                bad_pos += mx < 0.7 - 1e-6
                ns = min(sum(any(tc(x, y) >= 0.7 for y in B) for x in A), sum(any(tc(x, y) >= 0.7 for x in A) for y in B))
                bad_ns += ns != r.n_shared
            else:
                bad_neg += mx >= 0.3 - 1e-6
        check(bad_pos == 0, f"BLiPS {p}: positives have max Tc >= 0.7 ({bad_pos} bad)")
        check(bad_neg == 0, f"BLiPS {p}: negatives have max Tc < 0.3 ({bad_neg} bad)")
        check(bad_ns == 0, f"BLiPS {p}: n_shared recomputed ({bad_ns} bad)")
        pos = df[df.label == 1]
        vc = pos.pair_cluster.value_counts()
        check(vc.max() <= 300, f"BLiPS {p}: <= 300 positives per ligand cluster (max {vc.max()})")
        c = bc[p]
        check(c["n_pos"] == len(pos) and c["n_neg"] == int((df.label == 0).sum())
              and c["n_sites"] == int((S.partition == p).sum()) and c["n_proteins"] == S[S.partition == p].protein.nunique()
              and c["n_groups"] == S[S.partition == p].group_id.nunique(), f"BLiPS {p}: counts reproduced")
        check(abs(c["max_pos_cluster_share"] - round(vc.iloc[0] / len(pos), 4)) < 1e-9, f"BLiPS {p}: cluster share reproduced")
    te = S[S.partition == "test"]
    check(te.label_ccd.isna().all() if "label_ccd" in te else True, "BLiPS test sites in data/splits carry no ligand labels")
    check(bc["test"]["n_sites"] == len(te) and bc["test"]["n_proteins"] == te.protein.nunique(), "BLiPS test: site/protein counts reproduced")

    # ---------------- checksums
    sums = SPL / "SHA256SUMS.txt"
    if sums.exists():
        bad = []
        for line in sums.read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            h, f = line.split(maxsplit=1)
            p = ROOT / f.strip()
            if not os.access(p, os.R_OK):
                continue  # sealed entries: hash recorded at write time, not re-read
            if sha256(p.read_bytes()).hexdigest() != h:
                bad.append(f)
        check(not bad, f"SHA256SUMS.txt matches readable files ({bad})")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
