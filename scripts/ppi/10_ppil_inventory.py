#!/usr/bin/env python
"""PPI-L step 1: inventory of the Pasteur PPI pocketome (Moine-Franel et al. 2024; data/raw/ppi_pocketome,
fetched by scripts/data/fetch_ppi_pocketome.py).  Untrusted data: only parsed (CSV, SDF/mol2 text).

Labels (from the CSV / cavity names):
  HD    : VolSite cavities of PDB heterodimers, 'orthosteric' (= at the PPI interface, within one partner) or
          'nonorthosteric' (elsewhere on the chain)  -- ligand-free
  PLOC  : liganded cavity, ligand = iPPI-DB modulator, orthosteric competitive (binds the PPI interface)
  PLONC : liganded, orthosteric non-competitive
  PLA   : liganded, allosteric
One PPI-L pocket = one ligand instance (pdb, chain, ligand CCD id, residue number).  Its cavities (VolSite
may split a site) are listed; label = label of the cavities (unique in practice; checked).
Ligand chemistry: RDKit from the ligand SDF shipped with the entry (PDBe ModelServer export, PDB frame);
fallback mol2.  ECFP4 = Morgan radius 2, 2048 bits.  Chemotype clusters = Butina on Tanimoto distance,
cutoff 0.6 (members Tc >= 0.4 to the centroid).
Writes data/processed/ppi/ppil/{cavities.parquet, ligand_instances.parquet}, results/ppi/ppil_inventory.json.
Usage: python scripts/ppi/10_ppil_inventory.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem, rdMolDescriptors
from rdkit.ML.Cluster import Butina

RDLogger.DisableLog("rdApp.*")
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/ppi_pocketome/extracted/ippidb-pdb-analyses-042023-zenodo"
OUT = ROOT / "data/processed/ppi/ppil"
PDB_MIRROR = Path("/cluster/scratch/jjaenes/pdb")
LABEL = {"orthosteric_competitive": "PLOC", "orthosteric_noncompetitive": "PLONC", "allosteric": "PLA"}
PL_RE = re.compile(r"^(?P<pdb>\w{4})-(?P<chain>[^-]+)-(?P<uniprot>.+)-(?P<lig>[^-]+)-(?P<resnum>-?\d+)"
                   r"_CAVITY_N(?P<cav>\d+)_liganded_(?P<label>.+)$")
HD_RE = re.compile(r"^(?P<pdb>\w{4})-(?P<chains>[^-]+)-(?P<u1>.+?)-(?P<u2>[^-]+)-within(?P<chain>[^_]+)"
                   r"_CAVITY_N(?P<cav>\d+)_(?P<label>.+)$")


def mol_from_files(pdb, chain, lig, resnum):
    stem = RAW / pdb / f"{pdb}_{chain}_{lig}_{resnum}"
    for suf, fn in ((".sdf", Chem.MolFromMolFile), (".mol2", Chem.MolFromMol2File)):
        p = stem.with_suffix(suf)
        if p.exists():
            m = fn(str(p), sanitize=True, removeHs=True)
            if m is None and suf == ".sdf":
                m = fn(str(p), sanitize=False, removeHs=False)
                if m is not None:
                    try:
                        m.UpdatePropertyCache(strict=False)
                        Chem.SanitizeMol(m, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
                        m = Chem.RemoveHs(m, sanitize=False)
                        m.UpdatePropertyCache(strict=False)
                        Chem.GetSymmSSSR(m)
                    except Exception:  # noqa: BLE001
                        m = None
            if m is not None:
                return m, str(p.relative_to(ROOT)), suf
    return None, None, None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for key, lab in LABEL.items():
        d = pd.read_csv(RAW / f"PL_part8_20230317_matrix_liganded_{key}.csv")
        c = pd.read_csv(RAW / f"PL_part8_20230317_matrix_liganded_{key}__complete.csv",
                        usecols=["Cavity", "pfam_accession", "pfam_name", "cath", "cath_name"])
        d = d.merge(c.drop_duplicates("Cavity"), on="Cavity", how="left")
        d = d.copy()
        d["source_label"] = key
        rows.append(d)
    PL = pd.concat(rows, ignore_index=True)
    desc_cols = [c for c in pd.read_csv(RAW / "HD_part8_20230317_matrix_orthosteric.csv", nrows=1).columns
                 if c != "Cavity"]
    parsed = PL.Cavity.str.extract(PL_RE)
    assert parsed.pdb.notna().all(), PL.Cavity[parsed.pdb.isna()].head()
    PL = pd.concat([PL, parsed.drop(columns=["label"])], axis=1).copy()
    PL["label"] = PL.source_label.map(LABEL)
    PL["pocket_id"] = PL.pdb + ":" + PL.chain + ":" + PL.lig + ":" + PL.resnum
    PL["kind"] = "PL"
    HD = pd.read_csv(RAW / "HD_part8_20230317_matrix_orthosteric.csv")
    hp = HD.Cavity.str.extract(HD_RE)
    HD = pd.concat([HD, hp], axis=1)
    HD["kind"] = "HD"
    cav = pd.concat([PL[["Cavity", "kind", "label", "pocket_id", "pdb", "chain", "uniprot"] + desc_cols],
                     HD.assign(label="HD_" + HD.label.astype(str))[["Cavity", "kind", "label", "pdb", "chain"]
                                                                  + desc_cols]], ignore_index=True)
    cav.to_parquet(OUT / "cavities.parquet", index=False)

    # one row per ligand instance
    g = PL.groupby("pocket_id", sort=True)
    L = g.agg(pdb=("pdb", "first"), chain=("chain", "first"), uniprot=("uniprot", "first"), lig=("lig", "first"),
              resnum=("resnum", "first"), labels=("label", lambda s: ",".join(sorted(set(s)))),
              cavities=("Cavity", lambda s: ";".join(sorted(s))), n_cavities=("Cavity", "size"),
              cavity_volume=("Volume", "sum"), pfam_accession=("pfam_accession", "first"),
              pfam_name=("pfam_name", "first"), cath=("cath", "first")).reset_index()
    L["label"] = L.labels.where(~L.labels.str.contains(","), "MIXED")
    smi, ha, src, fps, ik = [], [], [], [], []
    for r in L.itertuples():
        m, p, _ = mol_from_files(r.pdb, r.chain, r.lig, r.resnum)
        if m is None:
            smi.append(None), ha.append(np.nan), src.append(None), fps.append(None), ik.append(None)
            continue
        smi.append(Chem.MolToSmiles(m))
        ha.append(m.GetNumHeavyAtoms())
        src.append(p)
        fps.append(AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048))
        try:
            ik.append(Chem.MolToInchiKey(m))
        except Exception:  # noqa: BLE001
            ik.append(None)
    L["smiles"], L["heavy_atoms"], L["ligand_file"], L["inchikey"] = smi, ha, src, ik
    L["structure_path"] = [str(PDB_MIRROR / p[1:3] / f"{p}.cif.gz") for p in L.pdb]
    L["in_pdb_mirror"] = [Path(p).exists() for p in L.structure_path]
    # chemotype clusters over distinct molecules (by canonical SMILES)
    ok = L.smiles.notna()
    uniq = L.loc[ok].drop_duplicates("smiles")[["smiles"]].reset_index(drop=True)
    fp_of = {s: f for s, f in zip(L.smiles, fps) if s is not None}
    ufp = [fp_of[s] for s in uniq.smiles]
    dists = []
    for i in range(1, len(ufp)):
        sims = DataStructs.BulkTanimotoSimilarity(ufp[i], ufp[:i])
        dists.extend(1 - x for x in sims)
    cl = Butina.ClusterData(dists, len(ufp), 0.6, isDistData=True)
    cid = np.empty(len(ufp), int)
    for k, c in enumerate(cl):
        cid[list(c)] = k
    uniq["ligand_cluster"] = cid
    uniq["mol_id"] = np.arange(len(uniq))
    L = L.merge(uniq, on="smiles", how="left")
    fpbits = [np.frombuffer(DataStructs.BitVectToText(f).encode(), np.uint8) - 48 if f is not None else None
              for f in fps]
    L["ecfp4_onbits"] = [np.flatnonzero(b).astype(np.int16) if b is not None else np.zeros(0, np.int16)
                         for b in fpbits]
    L.to_parquet(OUT / "ligand_instances.parquet", index=False)

    q = L[ok & (L.heavy_atoms >= 12)]
    inv = {
        "cavities_PL_by_label": PL.label.value_counts().to_dict(),
        "cavities_HD_by_label": HD.label.value_counts().to_dict(),
        "HD_pdb_entries": int(HD.pdb.nunique()),
        "n_descriptors": len(desc_cols),
        "ligand_instances": int(len(L)), "ligand_instances_by_label": L.label.value_counts().to_dict(),
        "ligand_parsed": int(ok.sum()), "ligand_ge12_heavy_atoms": int(len(q)),
        "in_pdb_mirror": int(L.in_pdb_mirror.sum()),
        "distinct_ccd_ids": int(L.lig.nunique()), "distinct_molecules": int(len(uniq)),
        "distinct_molecules_ge12HA": int(q.smiles.nunique()),
        "ligand_clusters_butina0.6": int(len(cl)), "ligand_clusters_ge12HA": int(q.ligand_cluster.nunique()),
        "pdb_entries": int(L.pdb.nunique()), "uniprot": int(L.uniprot.nunique()),
        "pfam_families": int(L.pfam_accession.nunique()),
        "pfam_missing": int(L.pfam_accession.isna().sum()),
        "top_uniprot": L.uniprot.value_counts().head(15).to_dict(),
        "top_pfam": L.pfam_name.value_counts().head(15).to_dict(),
        "top_ccd": L.lig.value_counts().head(15).to_dict(),
        "heavy_atoms_q": L.heavy_atoms.quantile([.05, .25, .5, .75, .95]).to_dict(),
    }
    (ROOT / "results/ppi").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/ppi/ppil_inventory.json").write_text(json.dumps(inv, indent=1, default=str))
    print(json.dumps(inv, indent=1, default=str))


if __name__ == "__main__":
    main()
