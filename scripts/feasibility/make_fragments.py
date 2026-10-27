#!/usr/bin/env python
"""Build a diverse fragment panel (feasibility study only).

Source: RDKit-distributed NCI subset `rdkit/Data/NCI/first_5K.smi` (first 5000 compounds of the NCI/DTP open
database; NCI data are public domain, RDKit is BSD-3). Filters (Rule-of-3-like): largest fragment, neutral formal
charges, elements C/N/O/S/F/Cl/Br, MW 100-250, 7-18 heavy atoms, >=1 ring, <=3 rotatable bonds, HBD<=3, HBA<=4,
cLogP<=3.5, no PAINS. Diversity: RDKit MaxMinPicker on Morgan r2 2048 fingerprints, seed 0. 3D: ETKDGv3 seed 0 +
MMFF94 minimisation, explicit H.
Usage: python make_fragments.py --n 64 --out results/feasibility/fragments.sdf
"""
import argparse
from pathlib import Path

from rdkit import Chem, RDConfig
from rdkit.Chem import AllChem, Descriptors, Crippen, rdMolDescriptors, FilterCatalog
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit.SimDivFilters.rdSimDivPickers import MaxMinPicker

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=64)
ap.add_argument("--out", default="results/feasibility/fragments.sdf")
a = ap.parse_args()

src = Path(RDConfig.RDDataDir) / "NCI" / "first_5K.smi"
params = FilterCatalog.FilterCatalogParams(); params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
pains = FilterCatalog.FilterCatalog(params)
lfc = rdMolStandardize.LargestFragmentChooser(); unch = rdMolStandardize.Uncharger()
ok_el = {6, 7, 8, 9, 16, 17, 35, 1}
seen, pool = set(), []
for line in src.read_text().splitlines():
    smi, nid = line.split()[:2]
    m = Chem.MolFromSmiles(smi)
    if m is None:
        continue
    m = unch.uncharge(lfc.choose(m))
    if any(at.GetFormalCharge() != 0 for at in m.GetAtoms()) and not m.HasSubstructMatch(Chem.MolFromSmarts("[N+](=O)[O-]")):
        continue
    if any(at.GetAtomicNum() not in ok_el for at in m.GetAtoms()):
        continue
    mw, ha = Descriptors.MolWt(m), m.GetNumHeavyAtoms()
    if not (100 <= mw <= 250 and 7 <= ha <= 18):
        continue
    if rdMolDescriptors.CalcNumRings(m) < 1 or rdMolDescriptors.CalcNumRotatableBonds(m) > 3:
        continue
    if rdMolDescriptors.CalcNumHBD(m) > 3 or rdMolDescriptors.CalcNumHBA(m) > 4 or Crippen.MolLogP(m) > 3.5:
        continue
    if pains.HasMatch(m):
        continue
    can = Chem.MolToSmiles(m)
    if can in seen:
        continue
    seen.add(can); pool.append((can, nid, m))
gen = AllChem.GetMorganGenerator(radius=2, fpSize=2048)
fps = [gen.GetFingerprint(m) for _, _, m in pool]
pick = list(MaxMinPicker().LazyBitVectorPick(fps, len(fps), a.n, seed=0))
out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
w = Chem.SDWriter(str(out)); n = 0
for i in pick:
    can, nid, m = pool[i]
    mh = Chem.AddHs(m)
    ps = AllChem.ETKDGv3(); ps.randomSeed = 0
    if AllChem.EmbedMolecule(mh, ps) != 0:
        continue
    AllChem.MMFFOptimizeMolecule(mh)
    mh.SetProp("_Name", f"NSC_{nid}"); mh.SetProp("smiles", can); mh.SetProp("MW", f"{Descriptors.MolWt(m):.1f}")
    w.write(mh); n += 1
w.close()
print(f"pool after filters: {len(pool)}; picked {len(pick)}; written {n} -> {out}")
