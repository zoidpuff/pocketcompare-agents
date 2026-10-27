#!/usr/bin/env python
"""Positive control for the feasibility pipeline: re-dock crystal ligands into their BURROW box with our receptor
prep and the fast presets; report top-pose heavy-atom RMSD (symmetry-aware) to the crystal pose.
Ligands: benzamidine (3PTB, S1 pocket p2), 4-hydroxytamoxifen (3ERT p1). Ligand built from SMILES (RDKit ETKDG,
seed 0), crystal coordinates read from the mmCIF in the local PDB mirror.
"""
import json
import sys

import gemmi
import numpy as np
import pandas as pd
import torch
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolAlign

sys.path.insert(0, "scripts/feasibility")
from dock_panel import PRESETS, run, search_cfg  # noqa: E402
from adock.config import load_config  # noqa: E402
from adock.screen import prepare_ligands  # noqa: E402

CASES = [("3ptb", "A", "BEN", "NC(=N)c1ccccc1", "3ptb_A_p2"),
         ("3ert", "A", "OHT", "CN(C)CCOc1ccc(cc1)/C(=C(/CC)c1ccccc1)c1ccc(O)cc1", "3ert_A_p1")]
cfg = load_config()
pk = pd.read_csv("results/feasibility/pockets.tsv", sep="\t").set_index("pocket_id")
dev = "cuda" if torch.cuda.is_available() else "cpu"
for pid, ch, resn, smi, pocket in CASES:
    st = gemmi.read_structure(f"/cluster/scratch/jjaenes/pdb/{pid[1:3]}/{pid}.cif.gz")
    res = [r for r in st[0][ch] if r.name == resn][0]
    xtal = {a.name: np.array(a.pos.tolist()) for a in res if a.element.name != "H"}
    ref = Chem.MolFromSmiles(smi)
    mh = Chem.AddHs(ref); ps = AllChem.ETKDGv3(); ps.randomSeed = 0; AllChem.EmbedMolecule(mh, ps); AllChem.MMFFOptimizeMolecule(mh)
    # crystal reference molecule: assign crystal coordinates by bond-order template on a PDB block
    pdb_block = "".join(f"HETATM{i + 1:5d} {n:<4s} {resn} A   1    {x[0]:8.3f}{x[1]:8.3f}{x[2]:8.3f}  1.00  0.00          "
                        f"{''.join(c for c in n if c.isalpha())[0]:>2s}\n" for i, (n, x) in enumerate(xtal.items()))
    xm = Chem.MolFromPDBBlock(pdb_block, proximityBonding=True)
    xm = AllChem.AssignBondOrdersFromTemplate(ref, xm)
    p = pk.loc[pocket].to_dict(); p["pocket_id"] = pocket
    box = json.loads(p["box"]); inside = all(np.all(np.abs(x - np.array(box["center"])) <= np.array(box["size"]) / 2) for x in xtal.values())
    for preset in ["v2_fast", "frag_lite_np", "frag_xlite_np", "frag_scan"]:
        preps = prepare_ligands([mh], cfg, 0)
        rm = []
        for seed in (0, 1, 2):
            out, _ = run([p], preps, cfg, search_cfg(cfg, preset), seed, dev, "per_pocket", 4096)
            _, _, r = out[0]
            j = int(np.argmin(r["affinity"]))
            pose = Chem.Mol(preps[0].mol); conf = pose.GetConformer()
            for k, xyz in enumerate(r["coords"][j][:pose.GetNumAtoms()]):
                conf.SetAtomPosition(k, xyz.tolist())
            pose = Chem.RemoveHs(pose)
            rm.append((rdMolAlign.CalcRMS(pose, xm), float(r["affinity"][j])))
        print(f"{pid} {resn} in {pocket} (crystal ligand inside box: {inside}) {preset:14s} top-pose RMSD per seed "
              f"{[round(x, 2) for x, _ in rm]} A, affinity {[round(e, 2) for _, e in rm]}")
