#!/usr/bin/env python
"""BLiPS D9 re-split (RESEARCH_TREE D9): pooled BLiPS train+val re-split 80/20 by homology component.

RULE (fixed before this script was first run, 2026-10-27; no label-derived quantity other than the stated
objective is looked at):
  Pool      the non-test rows of data/splits/blips_sites.parquet (v1 train 2,699 + val 163 sites; v1 test-homology
            removal and the <= 3 sites/protein cap already applied there and NOT redone), minus the sites failing
            the DESIGN §2.6 exclusion "sites with < 10 BURROW points" (L-mode points of the point cache
            data/processed/cache/points/blips/index.parquet; sites whose L-mode pocket could not be built are
            excluded too).  The 53 v1 val proteins dropped for sharing a component with v1 train are NOT restored.
  Units     homology components = the split agent's BLiPS group ids (group_id).  v1 train and val share no
            component, so the pooled components are the union of both; this is re-checked with the homology graph
            (D15: every component of the pooled proteins' subgraph must lie inside one group id, else abort; a group
            may contain several pooled components when its connecting proteins were excluded).
  Candidates 20 assignments k = 0..19; seed_k = numpy SeedSequence(SEEDS[0]).generate_state(20)[k];
            components sorted by group id, permuted with default_rng(seed_k); val = the first round(0.2 * n_comp)
            components of the permutation, train = the rest (80/20 of components).
  Choice    feasible = val holds 15-25 % of the pooled sites (inclusive).  Among feasible candidates choose the one
            maximising the number of distinct positive pair ligand clusters in val (positives by the v1 pair rule
            of make_blips_split.make_pairs before the per-cluster cap; the cap never removes a cluster); ties -> the
            lowest k.  No feasible candidate -> abort.
  Pairs     rebuilt with make_blips_split.make_pairs unchanged (same label rules, Butina clusters, caps, 5x
            negatives; pairs only within a partition, so cross-split pairs are dropped), rng = default_rng(SEEDS[0]),
            train first, then val.  Ligand universe / Tanimoto matrix / Butina clusters are recomputed exactly as in
            make_blips_split (all partitions' qualifying CCDs; af_set ligands from pocket_detect af_ligands.csv,
            the same public source the v1 builder read; the sealed files are not opened) and the pooled sites'
            label_cluster must reproduce v1 (else abort).  The top-20 promiscuous CCD list is the v1 list
            (blips_split_counts.json) so the flag stays identical to the sealed test pairs.  chemotype_seen and
            cluster_in_train are recomputed against v2 train.
Outputs  data/splits/blips_sites_v2.parquet (pooled non-test rows incl. excluded ones: partition = train | val |
         excluded_lt10 | excluded_no_pocket | excluded_not_cached (D15: not in the point cache); partition_v1 kept), data/splits/blips_{train,val}_pairs_v2.parquet,
         data/splits/blips_split_counts_v2.json.
Usage: python scripts/data/make_blips_resplit_v2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/data"))
import make_blips_split as MB  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402
from pocketcompare.splitutil import (SPLITS, SidGraph, butina, ecfp4_from_mol, load_homology,  # noqa: E402
                                     mol_from_smiles_list, tanimoto_matrix)

N_CAND = 20
VAL_FRAC_COMP = 0.20
VAL_SITE_MIN, VAL_SITE_MAX = 0.15, 0.25
MIN_POINTS = 10
CACHE_INDEX = ROOT / "data/processed/cache/points/blips/index.parquet"


def ligand_universe():
    """Exactly make_blips_split.main's qualifying-CCD universe, Tanimoto matrix and Butina clusters."""
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
    add, smi = MB.additives(), MB.biolip_smiles()
    A = pd.concat([MB.burrow_sites(), MB.af_sites()], ignore_index=True)
    ccds = sorted({c for s in A.all_ccds for c in s.split(";") if c})
    mols = {c: mol_from_smiles_list(smi[c]) if smi.get(c) else None for c in ccds}
    ha = {c: (m.GetNumHeavyAtoms() if m is not None else None) for c, m in mols.items()}
    ok = {c for c in ccds if ha[c] is not None and ha[c] > 1 and c not in add and ha[c] >= MB.MIN_HA}
    qsets = [";".join(sorted(c for c in s.split(";") if c in ok)) for s in A.all_ccds]
    qual = sorted({c for s in qsets if s for c in s.split(";")})
    ccd_idx = {c: i for i, c in enumerate(qual)}
    T = tanimoto_matrix(np.array([ecfp4_from_mol(mols[c]) for c in qual]))
    return ccd_idx, T, butina(T, MB.BUTINA_SIM)


def val_clusters(S: pd.DataFrame, ccd_idx, T, ccd_cluster) -> int:
    """# distinct positive pair clusters among val sites (cap-independent)."""
    P, _ = MB.make_pairs(S, ccd_idx, T, ccd_cluster, set(), np.random.default_rng(0))
    return int(P.loc[P.label == 1, "pair_cluster"].nunique())


def main():
    S0 = pd.read_parquet(SPLITS / "blips_sites.parquet")
    S0 = S0[S0.partition != "test"].copy().rename(columns={"partition": "partition_v1"})
    v1 = json.loads((SPLITS / "blips_split_counts.json").read_text())
    top = set(v1["top20_promiscuous_ccds"])
    counts: dict = {"rule": "see script header", "n_pool_v1_sites": int(len(S0))}

    # ---- DESIGN exclusion: < 10 BURROW points (L-mode, point cache)
    idx = pd.read_parquet(CACHE_INDEX, columns=["pocket_id", "status", "n_points", "failure_reason"])
    cached = S0.site_id.isin(set(idx.pocket_id)).to_numpy()
    idx = idx.set_index("pocket_id").reindex(S0.site_id)
    S0["n_lmode_points"] = idx.n_points.to_numpy()
    no_pocket = cached & (idx.status != "ok").to_numpy()
    lt10 = cached & ~no_pocket & (S0.n_lmode_points.fillna(0).to_numpy() < MIN_POINTS)
    # D15: sites re-admitted by the rebuilt graph that the point cache never saw are NOT "no pocket": separate label
    # (the cache is not extended here; extend it and rerun this script to include them)
    S0["partition"] = np.where(~cached, "excluded_not_cached", np.where(no_pocket, "excluded_no_pocket",
                                                                        np.where(lt10, "excluded_lt10", "pool")))
    counts["excluded_by_v1_partition"] = S0.groupby(["partition_v1", "partition"]).size().unstack(fill_value=0) \
        .to_dict(orient="index")
    S = S0[S0.partition == "pool"].copy()

    # ---- components (= v1 group ids) re-checked on the homology graph
    nodes, edges = load_homology()
    g = SidGraph(nodes, edges)
    cm = g.components(S.sid)
    comp = S.sid.map(cm)
    ct = pd.crosstab(comp, S.group_id).astype(bool)
    # D15: every pooled component lies inside ONE v1 group (the leakage-relevant direction). A v1 group may fall
    # apart into several pooled components when its connecting proteins are excluded; units stay the whole v1 group
    # (coarser, conservative). Report how often.
    assert ct.sum(axis=1).max() == 1, "a pooled homology component spans two v1 groups"
    counts["v1_groups_split_into_several_pooled_components"] = int((ct.sum(axis=0) > 1).sum())
    comps = np.array(sorted(S.group_id.unique()))
    n_val_comp = int(round(VAL_FRAC_COMP * len(comps)))

    # ---- ligand universe (reproduces v1 clusters)
    ccd_idx, T, ccd_cluster = ligand_universe()
    lc = S.label_ccd.map(lambda c: int(ccd_cluster[ccd_idx[c]]))
    assert (lc.to_numpy() == S.label_cluster.astype(int).to_numpy()).all(), "v1 label clusters not reproduced"

    # ---- candidates
    seeds = np.random.SeedSequence(SEEDS[0]).generate_state(N_CAND)
    cands = []
    for k, sd in enumerate(seeds):
        perm = np.random.default_rng(int(sd)).permutation(len(comps))
        val_c = set(comps[perm[:n_val_comp]])
        isval = S.group_id.isin(val_c)
        frac = float(isval.mean())
        feas = VAL_SITE_MIN <= frac <= VAL_SITE_MAX
        ncl = val_clusters(S[isval], ccd_idx, T, ccd_cluster) if feas else None
        cands.append(dict(k=k, seed=int(sd), val_site_frac=round(frac, 4), n_val_sites=int(isval.sum()),
                          feasible=bool(feas), n_val_pos_clusters=ncl, val_groups=sorted(val_c)))
        print(f"cand {k:2d} seed {int(sd)} val sites {int(isval.sum())} ({frac:.3f}) feasible {feas} "
              f"val pos clusters {ncl}", flush=True)
    feas = [c for c in cands if c["feasible"]]
    if not feas:
        raise SystemExit("no feasible candidate (val 15-25 % of sites) -- rule says abort")
    best = max(feas, key=lambda c: (c["n_val_pos_clusters"], -c["k"]))
    counts["candidates"] = [{k: v for k, v in c.items() if k != "val_groups"} for c in cands]
    counts["chosen_candidate"] = best["k"]
    print(f"chosen candidate {best['k']} ({best['n_val_pos_clusters']} val positive clusters)", flush=True)
    S["partition"] = np.where(S.group_id.isin(set(best["val_groups"])), "val", "train")

    # ---- pairs (v1 functions, unchanged rules)
    rng = np.random.default_rng(SEEDS[0])
    pairs, stats = {}, {}
    for p in ("train", "val"):
        pairs[p], stats[p] = MB.make_pairs(S[S.partition == p], ccd_idx, T, ccd_cluster, top, rng)
    train_pos_cl = set(pairs["train"].loc[pairs["train"].label == 1, "pair_cluster"])
    train_site_cl = set(S[S.partition == "train"].label_cluster)
    S["cluster_in_train"] = S.label_cluster.isin(train_site_cl)
    for p, df in pairs.items():
        df["chemotype_seen"] = np.where(df.label == 1, df.pair_cluster.isin(train_pos_cl), None)
        df["site_clusters_in_train"] = df.site_cluster_a.isin(train_site_cl) & df.site_cluster_b.isin(train_site_cl)
        df.insert(0, "pair_id", [f"blips_{p}_v2:{i}" for i in range(len(df))])
    for p in ("train", "val"):
        s, df = S[S.partition == p], pairs[p]
        pos = df[df.label == 1]
        vc = pos.pair_cluster.value_counts()
        prot = s.drop_duplicates("protein")
        counts[p] = dict(n_sites=int(len(s)), n_proteins=int(s.protein.nunique()), n_groups=int(s.group_id.nunique()),
                         n_from_v1_train=int((s.partition_v1 == "train").sum()),
                         n_from_v1_val=int((s.partition_v1 == "val").sum()),
                         largest_group_proteins=int(prot.group_id.value_counts().max()),
                         n_site_ligand_clusters=int(s.label_cluster.nunique()),
                         n_pos=int(len(pos)), n_neg=int((df.label == 0).sum()),
                         n_pos_shared_1=int((pos.n_shared_stratum == "1").sum()),
                         n_pos_shared_ge2=int((pos.n_shared_stratum == ">=2").sum()),
                         n_pos_ligand_clusters=int(len(vc)),
                         max_pos_cluster_share=round(float(vc.iloc[0] / len(pos)), 4) if len(pos) else None,
                         n_pos_promiscuous=int(pos.promiscuous.sum()), **stats[p])
        if p == "val":
            counts[p].update(n_pos_chemotype_seen=int(pos.chemotype_seen.astype(bool).sum()),
                             n_pos_chemotype_unseen=int((~pos.chemotype_seen.astype(bool)).sum()),
                             n_site_clusters_unseen=int(len(set(s.label_cluster) - train_site_cl)))
    counts["val_site_frac"] = round(float((S.partition == "val").mean()), 4)
    counts["val_component_frac"] = round(n_val_comp / len(comps), 4)
    counts["n_components"] = int(len(comps))

    out = pd.concat([S, S0[S0.partition != "pool"]], ignore_index=True).sort_values("site_id").reset_index(drop=True)
    out.to_parquet(SPLITS / "blips_sites_v2.parquet", index=False)
    pairs["train"].to_parquet(SPLITS / "blips_train_pairs_v2.parquet", index=False)
    pairs["val"].to_parquet(SPLITS / "blips_val_pairs_v2.parquet", index=False)
    (SPLITS / "blips_split_counts_v2.json").write_text(json.dumps(counts, indent=1, default=str))
    print(json.dumps({k: v for k, v in counts.items() if k != "candidates"}, indent=1, default=str))


if __name__ == "__main__":
    main()
