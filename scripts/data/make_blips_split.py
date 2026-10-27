#!/usr/bin/env python
"""BLiPS: BioLiP ligand-sharing site pairs (DESIGN §2.6, as amended in design round 2).

Sites
  train  BURROW train entries (pocket_detect data/processed/train/manifest.csv + entries/*.npz site tables)
  val    BURROW dev entries
  test   BURROW Track C af_set: LIGYSIS human sites with include == True; ligands = af_ligands.csv rows with
         status == 'ok' (<= 5 transferred instances per site, as recorded by Track C)
Ligand qualification: CCD has a BioLiP2 SMILES (ligand.tsv.gz, first parseable), >= 10 heavy atoms (RDKit, from
  that SMILES; excludes all ions/metals), not in data/ref/additives.txt. A site needs >= 1 qualifying ligand;
  its label ligand = the largest qualifying one (heavy atoms, then CCD code). The sites' full qualifying sets are kept.
Homology (graph of build_homology_graph.py; edges = BURROW's MMseqs2 rule OR Foldseek TM >= 0.5 both ways)
  1. train/val proteins with a DIRECT edge (or identical sequence) to TOUGH-M1-test, ProSPECCTs, Vertex,
     BLiPS-test (all af_set proteins) or PPI-L-test are removed;
  2. groups = connected components of the remaining train+val graph; a component containing both train and val
     proteins loses its val proteins (BURROW's convention: dev yields to train);
  3. groups within each partition = components of that partition's own subgraph (test: af proteins with sites).
Caps: <= 3 sites per protein (sites with distinct label-ligand clusters first, then seeded order).
Ligand clusters: Butina on ECFP4 (Morgan r=2, 2048 bits, no chirality) of all qualifying CCDs of all partitions,
  neighbours at Tanimoto >= 0.6.
Pairs (within a partition, sites of different groups):
  positive  max Tanimoto over the two qualifying sets >= 0.7; n_shared = min over the two sides of the number of
            ligands with a >= 0.7 partner on the other side (stratum '1' / '>=2'); pair ligand cluster = cluster of
            the best-matching ligand pair (lower cluster id if the two differ);
            capped per pair ligand cluster at c = largest value <= 300 such that no cluster exceeds 10 % of the
            partition's positives (if no c >= 25 achieves that: c = 300 and the realised share is reported);
  negative  max Tanimoto < 0.3; sampled uniformly (seeded) to NEG_RATIO x positives.
Flags: promiscuous = either site's label CCD or a best-matching CCD is among the top-20 CCDs by number of train
  sites (qualifying sets); seen chemotype (val/test vs train): positive pair cluster occurs among train positive
  pair clusters; site_cluster_in_train for both sites.
Outputs
  data/splits/blips_sites.parquet          train/val sites with ligands; test sites WITHOUT ligand columns
  data/splits/blips_{train,val}_pairs.parquet
  data/sealed/blips_test_pairs.parquet, data/sealed/blips_test_sites.parquet   (chmod 000)
  data/splits/blips_split_counts.json      counts (test: counts only)
"""
from __future__ import annotations

import gzip
import json
import os
import stat
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.seeds import SEEDS  # noqa: E402
from pocketcompare.splitutil import (SEALED, SPLITS, SidGraph, butina, ecfp4_from_mol, load_homology,  # noqa: E402
                                     mol_from_smiles_list, name_components, sha256, tanimoto_matrix)

PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
MIN_HA = 10
POS_TC, NEG_TC, BUTINA_SIM = 0.7, 0.3, 0.6
MAX_SITES_PER_PROTEIN = 3
MAX_POS_PER_CLUSTER, MAX_CLUSTER_SHARE, MIN_CAP = 300, 0.10, 25
NEG_RATIO = 5
TOP_PROMISCUOUS = 20
SEED = SEEDS[0]


def additives() -> set[str]:
    out = set()
    for line in open(ROOT / "data/ref/additives.txt"):
        line = line.split("#")[0].strip()
        if line:
            out |= set(line.split())
    return out


def biolip_smiles() -> dict[str, str]:
    smi = {}
    with gzip.open(PD / "data/raw/biolip2/current/ligand.tsv.gz", "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            smi[f[0]] = f[4] if len(f) > 4 else ""
    return smi


def burrow_sites() -> pd.DataFrame:
    rows = []
    for split, part in (("train", "train"), ("dev", "val")):
        m = pd.read_csv(PD / f"data/processed/{split}/manifest.csv", dtype={"chain": str, "pdb": str},
                        keep_default_na=False, na_values={"resolution": ["", "NaN"]})  # chain 'NA' is a real id
        for r in m[m.status == "ok"].itertuples():
            d = np.load(PD / r.npz, allow_pickle=False)
            for s in range(len(d["site_residues"])):
                sel = d["lig_site"] == s
                rows.append(dict(site_id=f"burrow_{split}:{r.entry_id}:{s}", partition=part,
                                 node_id=f"burrow_{split}:{r.entry_id}", protein=r.entry_id, uniprot=r.uniprot,
                                 pdb_id=r.pdb, chain=r.chain, site_index=s, site_residues=str(d["site_residues"][s]),
                                 site_is_ion=bool(d["site_is_ion"][s]),
                                 all_ccds=";".join(sorted(set(d["lig_ccd"][sel].tolist())))))
    return pd.DataFrame(rows)


def af_sites() -> pd.DataFrame:
    a = pd.read_csv(PD / "data/processed/af/af_sites.csv")
    a = a[a.include.astype(bool)]
    lg = pd.read_csv(PD / "data/processed/af/af_ligands.csv")
    lg = lg[lg.status == "ok"]
    ccd = lg.groupby("site_name").resname.agg(lambda x: ";".join(sorted(set(x))))
    return pd.DataFrame(dict(site_id="af_set:" + a.site_name, partition="test", node_id="af_set:" + a.acc,
                             protein=a.acc, uniprot=a.acc, pdb_id=a.rep_chain.str.split("_").str[0],
                             chain=a.rep_chain.str.split("_").str[1], site_index=a.site_id,
                             site_residues=None, site_is_ion=(a.ion_prop == 1),
                             all_ccds=a.site_name.map(ccd).fillna(""), structure_id=a.structure_id,
                             site_name=a.site_name))


def cap_value(counts: np.ndarray) -> tuple[int, bool]:
    for c in range(MAX_POS_PER_CLUSTER, MIN_CAP - 1, -1):
        capped = np.minimum(counts, c)
        if capped.max() <= MAX_CLUSTER_SHARE * capped.sum():
            return c, True
    return MAX_POS_PER_CLUSTER, False


def make_pairs(S: pd.DataFrame, ccd_idx: dict, T: np.ndarray, ccd_cluster: np.ndarray, top: set, rng) -> tuple[pd.DataFrame, dict]:
    S = S.reset_index(drop=True)
    n, U = len(S), len(ccd_idx)
    Q = np.zeros((n, U), bool)
    for i, qs in enumerate(S.q_ccds):
        Q[i, [ccd_idx[c] for c in qs.split(";")]] = True
    # R[s, d] = max_{c in Q_s} T[c, d]
    R = np.zeros((n, U), np.float32)
    for i in range(n):
        R[i] = T[Q[i]].max(0)
    M = np.zeros((n, n), np.float32)
    for j in range(n):
        M[:, j] = R[:, Q[j]].max(1)
    B = (R >= POS_TC).astype(np.float32)
    Qf = Q.astype(np.float32)
    cnt_b = B @ Qf.T          # [a,b] = # ligands of b matched by a
    n_shared = np.minimum(cnt_b, cnt_b.T).astype(np.int32)
    grp = S.group_id.to_numpy()
    iu, ju = np.triu_indices(n, 1)
    diff = grp[iu] != grp[ju]
    iu, ju = iu[diff], ju[diff]
    mt = M[iu, ju]
    pos = mt >= POS_TC
    pi, pj = iu[pos], ju[pos]
    # best-matching ligand pair -> pair cluster
    pcl, best_a, best_b = [], [], []
    qidx = [np.where(Q[i])[0] for i in range(n)]
    for a, b in zip(pi, pj):
        sub = T[np.ix_(qidx[a], qidx[b])]
        x, y = np.unravel_index(np.argmax(sub), sub.shape)
        ca, cb = qidx[a][x], qidx[b][y]
        best_a.append(ca)
        best_b.append(cb)
        pcl.append(min(ccd_cluster[ca], ccd_cluster[cb]))
    inv = np.array(sorted(ccd_idx, key=ccd_idx.get))
    P = pd.DataFrame(dict(ia=pi, ib=pj, label=1, max_tc=M[pi, pj], n_shared=n_shared[pi, pj],
                          pair_cluster=np.array(pcl, dtype=np.int64), best_ccd_a=inv[best_a] if len(pi) else [],
                          best_ccd_b=inv[best_b] if len(pi) else []))
    n_pos_uncapped = len(P)
    vc = P.pair_cluster.value_counts()
    cap, ok10 = cap_value(vc.to_numpy()) if len(vc) else (MAX_POS_PER_CLUSTER, True)
    keep = []
    for c, g in P.groupby("pair_cluster", sort=True):
        idx = g.index.to_numpy()
        keep.append(idx[rng.permutation(len(idx))[:cap]] if len(idx) > cap else idx)
    P = P.loc[np.sort(np.concatenate(keep))] if keep else P
    # negatives: uniform over eligible pairs (different group, max Tc < NEG_TC)
    neg_ok = mt < NEG_TC
    ni_all, nj_all = iu[neg_ok], ju[neg_ok]
    n_neg = min(NEG_RATIO * len(P), len(ni_all))
    sel = np.sort(rng.choice(len(ni_all), size=n_neg, replace=False)) if n_neg else np.array([], int)
    N = pd.DataFrame(dict(ia=ni_all[sel], ib=nj_all[sel], label=0, max_tc=M[ni_all[sel], nj_all[sel]], n_shared=0,
                          pair_cluster=-1, best_ccd_a=None, best_ccd_b=None))
    out = pd.concat([P, N], ignore_index=True)
    for side in ("a", "b"):
        i = out[f"i{side}"].to_numpy()
        out[f"site_{side}"] = S.site_id.to_numpy()[i]
        out[f"protein_{side}"] = S.protein.to_numpy()[i]
        out[f"group_{side}"] = S.group_id.to_numpy()[i]
        out[f"label_ccd_{side}"] = S.label_ccd.to_numpy()[i]
        out[f"site_cluster_{side}"] = S.label_cluster.to_numpy()[i]
    out["n_shared_stratum"] = np.where(out.label == 1, np.where(out.n_shared >= 2, ">=2", "1"), None)
    out["promiscuous"] = (out.label_ccd_a.isin(top) | out.label_ccd_b.isin(top)
                          | out.best_ccd_a.isin(top) | out.best_ccd_b.isin(top))
    out = out.drop(columns=["ia", "ib"])
    stats = dict(n_pos_uncapped=int(n_pos_uncapped), cluster_cap=int(cap), cap_meets_10pct=bool(ok10),
                 n_neg_eligible=int(len(ni_all)), n_ambiguous_dropped=int(((mt >= NEG_TC) & (mt < POS_TC)).sum()))
    return out, stats


def main():
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
    rng = np.random.default_rng(SEED)
    nodes, edges = load_homology()
    g = SidGraph(nodes, edges)
    sid = dict(zip(nodes.node_id, nodes.sid))
    add = additives()
    smi = biolip_smiles()

    S = pd.concat([burrow_sites(), af_sites()], ignore_index=True)
    ccds = sorted({c for s in S.all_ccds for c in s.split(";") if c})
    mols = {c: mol_from_smiles_list(smi[c]) if smi.get(c) else None for c in ccds}
    ha = {c: (m.GetNumHeavyAtoms() if m is not None else None) for c, m in mols.items()}

    def why(c):
        if ha[c] is None:
            return "no_smiles"
        if ha[c] <= 1:
            return "ion"
        if c in add:
            return "additive"
        if ha[c] < MIN_HA:
            return "small"
        return "ok"
    reason = {c: why(c) for c in ccds}
    S["q_ccds"] = [";".join(sorted(c for c in s.split(";") if c and reason[c] == "ok")) for s in S.all_ccds]

    def site_reason(r):
        if r.q_ccds:
            return "ok"
        rs = {reason[c] for c in r.all_ccds.split(";") if c}
        if not rs:
            return "no_ligand"
        if rs <= {"ion"}:
            return "ion_only"
        for k in ("additive", "small", "no_smiles"):
            if k in rs:
                return f"{k}_and_less"
        return "other"
    S["exclusion"] = [site_reason(r) for r in S.itertuples()]
    counts = {"site_exclusion": S.groupby(["partition", "exclusion"]).size().unstack(fill_value=0).to_dict(orient="index")}
    S = S[S.exclusion == "ok"].copy()

    # ligand fingerprints, label ligand, Butina clusters
    qual = sorted({c for s in S.q_ccds for c in s.split(";")})
    ccd_idx = {c: i for i, c in enumerate(qual)}
    fps = np.array([ecfp4_from_mol(mols[c]) for c in qual])
    T = tanimoto_matrix(fps)
    ccd_cluster = butina(T, BUTINA_SIM)
    S["label_ccd"] = [max(s.split(";"), key=lambda c: (ha[c], c)) for s in S.q_ccds]
    S["label_ha"] = S.label_ccd.map(ha)
    S["label_smiles"] = S.label_ccd.map(lambda c: smi[c].split(";")[0].strip())
    S["label_cluster"] = S.label_ccd.map(lambda c: int(ccd_cluster[ccd_idx[c]]))
    S["n_qualifying"] = S.q_ccds.str.count(";") + 1

    # homology: remove train/val proteins with direct edges to the test sets
    tm = pd.read_parquet(SPLITS / "tough_m1_pockets_split.parquet")
    targets = {"tough_m1_test": set(tm[tm.partition == "test"].sid),
               "prospeccts": set(nodes[nodes.dataset == "prospeccts"].sid),
               "vertex": set(nodes[nodes.dataset == "vertex"].sid),
               "blips_test_af_set": set(nodes[nodes.dataset == "af_set"].sid),
               "ppi_l_test": set(nodes[(nodes.dataset == "ppi_l")
                                       & nodes.ppi_split.fillna("").str.contains("test")].sid)}
    S["sid"] = S.node_id.map(sid)
    assert S.sid.notna().all(), S[S.sid.isna()].node_id.unique()[:10]
    tv = S.partition.isin(["train", "val"])
    prot = S[tv].drop_duplicates("node_id")[["node_id", "sid", "partition"]].reset_index(drop=True)
    for k, tg in targets.items():
        prot[f"touch_{k}"] = g.touches(prot.sid, tg).values
    tcols = [f"touch_{k}" for k in targets]
    prot["removed_test_homolog"] = prot[tcols].any(axis=1)
    counts["trainval_proteins_removed"] = {
        p: {"n_proteins_before": int((prot.partition == p).sum()),
            **{k: int(prot[(prot.partition == p)][k].sum()) for k in tcols},
            "any": int(prot[(prot.partition == p)].removed_test_homolog.sum())} for p in ("train", "val")}
    keep_nodes = set(prot[~prot.removed_test_homolog].node_id)
    # train/val component separation
    rem = prot[~prot.removed_test_homolog].copy()
    comp = g.components(rem.sid)
    rem["comp"] = rem.sid.map(comp)
    mixed = rem.groupby("comp").partition.nunique() > 1
    drop_val = rem[rem.comp.isin(mixed[mixed].index) & (rem.partition == "val")].node_id
    counts["val_proteins_dropped_sharing_component_with_train"] = int(len(drop_val))
    keep_nodes -= set(drop_val)
    S = S[~tv | S.node_id.isin(keep_nodes)].copy()

    # groups within each partition
    S["group_id"] = None
    for p in ("train", "val", "test"):
        m = S.partition == p
        cm = g.components(S.loc[m, "sid"])
        S.loc[m, "group_id"] = name_components(S.loc[m, "sid"].map(cm), f"blips_{p}").values

    # per-protein site cap (distinct label clusters first, then seeded order)
    S = S.sort_values("site_id").reset_index(drop=True)
    S["_r"] = rng.permutation(len(S))
    keep = []
    for _, gp in S.sort_values(["protein", "_r"]).groupby("protein", sort=True):
        chosen, seen_cl = [], set()
        for i, r in gp.iterrows():
            if r.label_cluster not in seen_cl and len(chosen) < MAX_SITES_PER_PROTEIN:
                chosen.append(i)
                seen_cl.add(r.label_cluster)
        for i in gp.index:
            if len(chosen) >= MAX_SITES_PER_PROTEIN:
                break
            if i not in chosen:
                chosen.append(i)
        keep += chosen
    counts["sites_before_protein_cap"] = S.partition.value_counts().to_dict()
    S = S.loc[sorted(keep)].drop(columns=["_r"]).reset_index(drop=True)

    # promiscuous CCDs (train sites, qualifying sets)
    tr_ccd = pd.Series([c for s in S[S.partition == "train"].q_ccds for c in s.split(";")]).value_counts()
    top = set(tr_ccd.head(TOP_PROMISCUOUS).index)
    counts["top20_promiscuous_ccds"] = {c: int(tr_ccd[c]) for c in tr_ccd.head(TOP_PROMISCUOUS).index}

    pairs, stats = {}, {}
    for p in ("train", "val", "test"):
        pairs[p], stats[p] = make_pairs(S[S.partition == p], ccd_idx, T, ccd_cluster, top, rng)
    train_pos_cl = set(pairs["train"].loc[pairs["train"].label == 1, "pair_cluster"])
    train_site_cl = set(S[S.partition == "train"].label_cluster)
    S["cluster_in_train"] = S.label_cluster.isin(train_site_cl)
    for p, df in pairs.items():
        df["chemotype_seen"] = np.where(df.label == 1, df.pair_cluster.isin(train_pos_cl), None)
        df["site_clusters_in_train"] = df.site_cluster_a.isin(train_site_cl) & df.site_cluster_b.isin(train_site_cl)
        df.insert(0, "pair_id", [f"blips_{p}:{i}" for i in range(len(df))])

    # counts
    for p in ("train", "val", "test"):
        s, df = S[S.partition == p], pairs[p]
        pos = df[df.label == 1]
        vc = pos.pair_cluster.value_counts()
        counts[p] = dict(n_sites=int(len(s)), n_proteins=int(s.protein.nunique()), n_groups=int(s.group_id.nunique()),
                         largest_group_proteins=int(s.drop_duplicates("protein").group_id.value_counts().max()),
                         largest_group_frac=round(float(s.drop_duplicates("protein").group_id.value_counts().max()
                                                        / s.protein.nunique()), 4),
                         n_site_ligand_clusters=int(s.label_cluster.nunique()),
                         n_pos=int(len(pos)), n_neg=int((df.label == 0).sum()),
                         n_pos_shared_1=int((pos.n_shared_stratum == "1").sum()),
                         n_pos_shared_ge2=int((pos.n_shared_stratum == ">=2").sum()),
                         n_pos_ligand_clusters=int(len(vc)),
                         max_pos_cluster_share=round(float(vc.iloc[0] / len(pos)), 4) if len(pos) else None,
                         n_pos_promiscuous=int(pos.promiscuous.sum()), n_neg_promiscuous=int(df[df.label == 0].promiscuous.sum()),
                         **stats[p])
        if p != "train":
            counts[p].update(n_pos_chemotype_seen=int(pos.chemotype_seen.astype(bool).sum()),
                             n_pos_chemotype_unseen=int((~pos.chemotype_seen.astype(bool)).sum()),
                             n_sites_cluster_in_train=int(s.cluster_in_train.sum()),
                             n_site_clusters_unseen=int(len(set(s.label_cluster) - train_site_cl)))
    counts["n_qualifying_ccds"] = len(qual)
    counts["n_ccd_clusters"] = int(len(set(ccd_cluster)))
    counts["params"] = dict(min_heavy_atoms=MIN_HA, pos_tc=POS_TC, neg_tc=NEG_TC, butina_similarity=BUTINA_SIM,
                            max_sites_per_protein=MAX_SITES_PER_PROTEIN, max_pos_per_cluster=MAX_POS_PER_CLUSTER,
                            max_cluster_share=MAX_CLUSTER_SHARE, neg_ratio=NEG_RATIO, seed=SEED,
                            fingerprint="ECFP4 Morgan r=2 2048 bits, no chirality (RDKit MorganGenerator)",
                            min_burrow_points="NOT applied (needs the point cache; PI to apply at descriptor time)")

    # write
    site_cols = ["site_id", "partition", "node_id", "sid", "protein", "uniprot", "pdb_id", "chain", "site_index",
                 "site_residues", "structure_id", "site_name", "group_id", "site_is_ion"]
    lig_cols = ["all_ccds", "q_ccds", "n_qualifying", "label_ccd", "label_ha", "label_smiles", "label_cluster",
                "cluster_in_train"]
    trv = S[S.partition != "test"]
    pub = pd.concat([trv[site_cols + lig_cols], S[S.partition == "test"][site_cols]], ignore_index=True)
    pub.to_parquet(SPLITS / "blips_sites.parquet", index=False)
    pairs["train"].to_parquet(SPLITS / "blips_train_pairs.parquet", index=False)
    pairs["val"].to_parquet(SPLITS / "blips_val_pairs.parquet", index=False)
    mode = stat.S_IMODE(os.stat(SEALED).st_mode)
    try:
        os.chmod(SEALED, mode | stat.S_IWUSR)
        for name, df in (("blips_test_pairs.parquet", pairs["test"]),
                         ("blips_test_sites.parquet", S[S.partition == "test"][site_cols + lig_cols])):
            dest = SEALED / name
            if dest.exists():
                os.chmod(dest, 0o600)
            df.to_parquet(dest, index=False)
            counts[f"sealed_sha256:{name}"] = sha256(dest)
            os.chmod(dest, 0)
    finally:
        os.chmod(SEALED, mode)
    (SPLITS / "blips_split_counts.json").write_text(json.dumps(counts, indent=1, default=str))
    print(json.dumps(counts, indent=1, default=str))


if __name__ == "__main__":
    main()
