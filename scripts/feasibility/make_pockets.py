#!/usr/bin/env python
"""Prepare receptors + BURROW pockets + docking boxes for the fragment-docking feasibility study.

For each PDB entry (local mirror /cluster/scratch/jjaenes/pdb): keep one chain, polymer only (ligands, ions, waters
removed; modified residues kept), write PDB; run BURROW (`pocket_representations`, ranker all, preset default,
model output floor). Keep the top-3 ranked pockets plus the pocket that best matches the native site (residues
<= 4 A of the native ligand; for an apo entry the site residues of a homologous holo entry with the same numbering).
Box = pocket point extent +/- MARGIN A, each side >= MIN_SIDE A.
Output: results/feasibility/receptors/*.pdb, results/feasibility/pockets.tsv, pockets_burrow_descriptors.tsv
(76 BURROW descriptors), pocket_points.npz (pocket point coordinates, input frame).
"""
import json
import time
from pathlib import Path

import gemmi
import numpy as np
import pandas as pd

from pocketdetect.burrow.export import pocket_representations

MIRROR = "/cluster/scratch/jjaenes/pdb/{mid}/{id}.cif.gz"
MARGIN, MIN_SIDE, TOPK = 3.0, 12.0, 3
# id, chain, native ligand resname (None: borrow site residues from `site_from`), site label, protein
ENTRIES = [
    ("1hck", "A", "ATP", None, "kinase_ATP", "CDK2"),
    ("1aq1", "A", "STU", None, "kinase_ATP", "CDK2"),
    ("1atp", "E", "ATP", None, "kinase_ATP", "PKA"),
    ("3ptb", "A", "BEN", None, "protease_S1", "trypsin"),
    ("2ptn", "A", None, "3ptb", "protease_S1", "trypsin"),
    ("1a6m", "A", "HEM", None, "heme", "myoglobin"),
    ("2cpp", "A", "HEM", None, "heme", "P450cam"),
    ("3ert", "A", "OHT", None, "NR_ligand", "ERalpha"),
    ("1byq", "A", "ADP", None, "HSP90_ATP", "HSP90"),
]
OUT = Path("results/feasibility")


def prep(pid, chain, lig):
    st = gemmi.read_structure(MIRROR.format(mid=pid[1:3], id=pid))
    st.setup_entities()
    model = st[0]
    lig_xyz = []
    for ch in model:
        if ch.name != chain:
            continue
        for r in ch:
            if lig and r.name == lig:
                lig_xyz += [a.pos.tolist() for a in r if a.element.name != "H"]
    for name in [c.name for c in model]:
        if name != chain:
            model.remove_chain(name)
    st.remove_ligands_and_waters()
    st.remove_hydrogens()
    st.remove_empty_chains()
    # keep first altloc only
    st.remove_alternative_conformations()
    path = OUT / "receptors" / f"{pid}_{chain}.pdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    st.write_pdb(str(path))
    ca = {(r.seqid.num): r for r in st[0][chain]}
    return path, np.array(lig_xyz), st


def site_residues(st, chain, lig_xyz, cut=4.0):
    res = set()
    for r in st[0][chain]:
        for a in r:
            if len(lig_xyz) and np.min(np.linalg.norm(lig_xyz - np.array(a.pos.tolist()), axis=1)) <= cut:
                res.add(f"{chain}:{r.seqid.num}{r.seqid.icode.strip()}")
                break
    return res


rows, native_sites, desc_rows, pts_out = [], {}, [], {}
for pid, chain, lig, site_from, label, prot in ENTRIES:
    path, lig_xyz, st = prep(pid, chain, lig)
    site = site_residues(st, chain, lig_xyz) if lig else native_sites[site_from]
    native_sites[pid] = site
    t0 = time.perf_counter()
    rep = pocket_representations(str(path), ranker="all", preset="default")
    tb = time.perf_counter() - t0
    pk, pts = rep["pockets"], rep["points"]
    jac = []
    for _, p in pk.iterrows():
        rs = set(p["residues"].split())
        jac.append(len(rs & site) / max(1, len(rs | site)))
    pk = pk.assign(jaccard_native=jac)
    nat_rank = int(pk.loc[pk.jaccard_native.idxmax(), "rank"])
    keep = sorted(set(pk["rank"].head(TOPK)) | {nat_rank})
    for rk in keep:
        p = pk[pk["rank"] == rk].iloc[0]
        xyz = pts.loc[rep["pocket_points"][rk], ["x", "y", "z"]].to_numpy()
        lo, hi = xyz.min(0) - MARGIN, xyz.max(0) + MARGIN
        size = np.maximum(hi - lo, MIN_SIDE)
        center = (lo + hi) / 2
        rows.append(dict(pocket_id=f"{pid}_{chain}_p{rk}", pdb=pid, chain=chain, protein=prot, rank=rk,
                         score=round(p["score"], 4), is_native=int(rk == nat_rank),
                         site_label=label if rk == nat_rank else "other",
                         jaccard_native=round(p["jaccard_native"], 3), n_points=int(p["n_points"]),
                         volume_A3=round(p["volume_A3"], 1), bur16_mean=round(p["bur16_mean"], 4),
                         depth_mean=round(p["depth_mean"], 3), escape=round(p["escape"], 4),
                         receptor=str(path), box=json.dumps({"center": center.round(3).tolist(), "size": size.round(3).tolist()}),
                         burrow_s=round(tb, 2)))
        pid_ = rows[-1]["pocket_id"]
        desc_rows.append(dict(pocket_id=pid_, **{k: p[k] for k in rep["descriptor_names"]}))
        pts_out[pid_] = xyz.astype(np.float32)
    print(pid, f"{tb:.1f}s", "native rank", nat_rank, "jac", round(max(jac), 2), flush=True)
df = pd.DataFrame(rows)
df.to_csv(OUT / "pockets.tsv", sep="\t", index=False)
pd.DataFrame(desc_rows).to_csv(OUT / "pockets_burrow_descriptors.tsv", sep="\t", index=False)
np.savez_compressed(OUT / "pocket_points.npz", **pts_out)
print(df[["pocket_id", "site_label", "score", "jaccard_native", "volume_A3", "bur16_mean", "box"]].to_string())
