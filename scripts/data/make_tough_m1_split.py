#!/usr/bin/env python
"""TOUGH-M1 dev/test split (DESIGN §2.3, as amended in design round 2).

Groups  = connected components of the TOUGH-M1-only homology graph (group_id of dataset 'tough_m1' in
          data/splits/homology_nodes.parquet; edges = BURROW's MMseqs2 rule OR Foldseek TM >= 0.5 both ways).
BURROW  = BURROW train/dev representative chains + their assembly-partner chains.
Sealed  = ProSPECCTs, Vertex, BLiPS-test (= BURROW af_set, all proteins), PPI-L-test (ppi_l nodes whose ppi_split
          contains 'test').
A group is
  dev       if any member has a DIRECT edge (or identical sequence) to a BURROW chain and no member has one to a
            sealed test set,
  excluded  if it has direct edges to BURROW AND to a sealed test set (removed from both partitions),
  test      otherwise (BURROW-clean).
Pairs: within-partition only. Ligand clusters per pocket: ECFP4 (2048) of the shipped ligand SDF, Butina at
Tanimoto >= 0.6 over all 7,524 ligands (same convention as BLiPS).

SEALED INPUTS (read only here, permission restored to 000 immediately after reading, also on error):
  data/sealed/tough_m1_pairs.parquet; data/raw/tough_m1/downloads/{APoc,G-LoSA,SiteEngine}-TOUGH-M1_*.score
OUTPUTS
  data/splits/tough_m1_pockets_split.parquet   per pocket: partition, group, flags, ligand cluster (no labels)
  data/splits/tough_m1_dev_pairs.parquet       dev pairs with labels + shipped baseline scores
  data/sealed/tough_m1_test_pairs.parquet      test pairs (chmod 000)
  data/splits/tough_m1_split_counts.json       COUNTS only
stdout: counts only.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.splitutil import (SEALED, SPLITS, SidGraph, butina, ecfp4_from_mol, load_homology,  # noqa: E402
                                     sha256, tanimoto_matrix)

SEALED_PAIRS = SEALED / "tough_m1_pairs.parquet"
DL = ROOT / "data/raw/tough_m1/downloads"
TOOLS = ["APoc", "G-LoSA", "SiteEngine"]
BURROW_DS = ["burrow_train", "burrow_dev", "burrow_partner"]
SEALED_DS = ["prospeccts", "vertex", "af_set", "ppi_l_test"]
BUTINA_SIM = 0.6


@contextmanager
def temporarily_readable(paths):
    modes = {p: stat.S_IMODE(os.stat(p).st_mode) for p in paths}
    try:
        for p in paths:
            os.chmod(p, 0o400)
        yield
    finally:
        for p, m in modes.items():
            os.chmod(p, m)
        for p in paths:
            assert stat.S_IMODE(os.stat(p).st_mode) == 0, f"{p} not restored to 000"


@contextmanager
def writable_dir(d: Path):
    m = stat.S_IMODE(os.stat(d).st_mode)
    try:
        os.chmod(d, m | stat.S_IWUSR)
        yield
    finally:
        os.chmod(d, m)


def ligand_fps(pockets: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    fps, ok = [], []
    for lf in pockets.ligand_file:
        sdf = ROOT / str(lf).replace("00.pdb", "00.sdf")
        m = Chem.MolFromMolFile(str(sdf), sanitize=True)
        if m is None:  # partial sanitisation (valence problems in a few SDFs)
            m = Chem.MolFromMolFile(str(sdf), sanitize=False)
            if m is not None:
                m.UpdatePropertyCache(strict=False)
                Chem.GetSymmSSSR(m)
        fp = ecfp4_from_mol(m) if m is not None else None
        ok.append(fp is not None)
        fps.append(fp if fp is not None else np.zeros(2048, bool))
    return np.array(fps), np.array(ok)


def read_scores(tool: str) -> pd.DataFrame:
    """Shipped per-pair scores: first two tokens = pocket names, remaining numeric tokens kept in file order."""
    rows = []
    for lab in ("positive", "negative"):
        with open(DL / f"{tool}-TOUGH-M1_{lab}.score") as fh:
            for line in fh:
                t = line.split()
                if len(t) < 3:
                    continue
                vals = []
                for x in t[2:]:
                    try:
                        vals.append(float(x))
                    except ValueError:
                        vals.append(np.nan)
                rows.append((t[0], t[1], *vals))
    ncol = max(len(r) for r in rows) - 2
    cols = ["a", "b"] + [f"{tool.lower().replace('-', '')}_c{i + 1}" for i in range(ncol)]
    df = pd.DataFrame([r + (np.nan,) * (ncol + 2 - len(r)) for r in rows], columns=cols)
    df["key"] = [f"{min(a, b)}|{max(a, b)}" for a, b in zip(df.a, df.b)]
    n_dup = int(df.key.duplicated().sum())
    df = df.drop_duplicates("key").drop(columns=["a", "b"])
    print(f"  {tool}: {len(df)} scored pairs, {ncol} numeric column(s), {n_dup} duplicate keys dropped")
    return df


def main():
    dry = "--dry-run" in sys.argv  # partition + ligand clusters only; sealed inputs are not touched, nothing written
    nodes, edges = load_homology()
    g = SidGraph(nodes, edges)
    pk = pd.read_parquet(ROOT / "data/processed/benchmarks/tough_m1_pockets.parquet")
    tn = nodes[nodes.dataset == "tough_m1"].set_index("pocket_ids")
    pk = pk.join(tn[["node_id", "sid", "group_id"]], on="pocket_id")
    assert pk.node_id.notna().all(), "TOUGH-M1 pocket without homology node"
    pk["touch_burrow"] = g.touches(pk.sid, nodes[nodes.dataset.isin(BURROW_DS)].sid).values
    pk["touch_burrow_rep"] = g.touches(pk.sid, nodes[nodes.dataset.isin(BURROW_DS[:2])].sid).values
    sealed_sids = {ds: nodes[nodes.dataset == ds].sid for ds in SEALED_DS[:3]}
    sealed_sids["ppi_l_test"] = nodes[(nodes.dataset == "ppi_l")
                                      & nodes.get("ppi_split", pd.Series("", index=nodes.index)).fillna("").str.contains("test")].sid
    for ds in SEALED_DS:
        pk[f"touch_{ds}"] = g.touches(pk.sid, sealed_sids[ds]).values
    pk["touch_sealed"] = pk[[f"touch_{d}" for d in SEALED_DS]].any(axis=1)
    grp = pk.groupby("group_id")[["touch_burrow", "touch_sealed"]].any()
    grp["partition"] = np.where(grp.touch_burrow & grp.touch_sealed, "excluded",
                                np.where(grp.touch_burrow, "dev", "test"))
    pk["partition"] = pk.group_id.map(grp.partition)

    fps, ok = ligand_fps(pk)
    sim = tanimoto_matrix(fps)
    lab = butina(np.where(ok[:, None] & ok[None, :], sim, 0.0), BUTINA_SIM)
    pk["ligand_fp_ok"] = ok
    pk["ligand_cluster"] = [f"tm1lig:{c:04d}" if o else None for c, o in zip(lab, ok)]

    out = pk[["pocket_id", "node_id", "sid", "group_id", "partition", "touch_burrow", "touch_burrow_rep",
              *[f"touch_{d}" for d in SEALED_DS], "touch_sealed", "ligand_cluster", "ligand_fp_ok"]]
    if dry:
        print({p: int((pk.partition == p).sum()) for p in ("dev", "test", "excluded")},
              {p: int(pk[pk.partition == p].ligand_cluster.nunique()) for p in ("dev", "test", "excluded")})
        return
    out.to_parquet(SPLITS / "tough_m1_pockets_split.parquet", index=False)

    # ---- sealed: pairs + shipped baseline scores (temporarily readable, restored to 000)
    score_files = [DL / f"{t}-TOUGH-M1_{l}.score" for t in TOOLS for l in ("positive", "negative")]
    print("reading sealed inputs (counts only)")
    with temporarily_readable([SEALED_PAIRS, *score_files]):
        pairs = pd.read_parquet(SEALED_PAIRS)
        scores = [read_scores(t) for t in TOOLS]
    part = dict(zip(pk.pocket_id, pk.partition))
    pa, pb = pairs.pocket_a.map(part), pairs.pocket_b.map(part)
    pairs["partition"] = np.where(pa == pb, pa, "cross")
    na = pairs.pocket_a.str.split(":").str[1]
    nb = pairs.pocket_b.str.split(":").str[1]
    pairs["key"] = [f"{min(a, b)}|{max(a, b)}" for a, b in zip(na, nb)]
    for s in scores:
        pairs = pairs.merge(s, on="key", how="left")
    lc = dict(zip(pk.pocket_id, pk.ligand_cluster))
    gid = dict(zip(pk.pocket_id, pk.group_id))
    pairs["ligand_cluster_a"] = pairs.pocket_a.map(lc)
    pairs["ligand_cluster_b"] = pairs.pocket_b.map(lc)
    pairs["group_a"] = pairs.pocket_a.map(gid)
    pairs["group_b"] = pairs.pocket_b.map(gid)
    pairs = pairs.drop(columns=["key"])
    score_cols = [c for c in pairs.columns if c.startswith(("apoc_", "glosa_", "siteengine_"))]

    counts = {"n_pockets_total": int(len(pk)), "n_groups_total": int(pk.group_id.nunique()),
              "n_pairs_total": int(len(pairs)), "sealed_test_sets_used": SEALED_DS,
              "n_ppi_l_test_nodes": int(len(sealed_sids["ppi_l_test"])), "butina_similarity": BUTINA_SIM,
              "n_ligands_fp_failed": int((~ok).sum()), "score_columns": score_cols}
    for p in ("dev", "test", "excluded"):
        sub = pk[pk.partition == p]
        pp = pairs[pairs.partition == p]
        counts[p] = {"n_pockets": int(len(sub)), "n_groups": int(sub.group_id.nunique()),
                     "largest_group": int(sub.group_id.value_counts().max()) if len(sub) else 0,
                     "n_ligand_clusters": int(sub.ligand_cluster.nunique()),
                     "n_pos": int((pp.label == 1).sum()), "n_neg": int((pp.label == 0).sum()),
                     "n_pairs_with_all_scores": int(pp[score_cols].notna().all(axis=1).sum()) if p != "excluded" else None,
                     "n_pockets_touch_burrow_rep_only_via_partner": int((sub.touch_burrow & ~sub.touch_burrow_rep).sum())}
        top = sub.ligand_cluster.value_counts()
        counts[p]["largest_ligand_cluster_frac_of_pockets"] = round(float(top.iloc[0] / len(sub)), 4) if len(sub) else None
    counts["n_pairs_cross_partition_dropped"] = int((pairs.partition == "cross").sum())
    counts["n_pairs_involving_excluded"] = int(((pa == "excluded") | (pb == "excluded")).sum())
    counts["excluded_reason"] = {d: int(pk[(pk.partition == "excluded")][f"touch_{d}"].sum()) for d in SEALED_DS}
    counts["n_test_pockets_touching_sealed"] = int(pk[pk.partition == "test"].touch_sealed.sum())

    dev = pairs[pairs.partition == "dev"].drop(columns=["partition"]).reset_index(drop=True)
    test = pairs[pairs.partition == "test"].drop(columns=["partition"]).reset_index(drop=True)
    dev.to_parquet(SPLITS / "tough_m1_dev_pairs.parquet", index=False)
    dest = SEALED / "tough_m1_test_pairs.parquet"
    with writable_dir(SEALED):
        if dest.exists():
            os.chmod(dest, 0o600)
        test.to_parquet(dest, index=False)
        counts["sealed_test_pairs_sha256"] = sha256(dest)
        os.chmod(dest, 0)
    del pairs, test
    (SPLITS / "tough_m1_split_counts.json").write_text(json.dumps(counts, indent=1))
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main()
