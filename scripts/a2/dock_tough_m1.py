#!/usr/bin/env python
"""A2: dock the fragment and lead-like panels into TOUGH-M1 pockets with ADock (DESIGN §3 A2).

Protocol (fixed, DESIGN §3 A2 + reviews/round1_domain.md §2):
  * stock Vina weights, rigid receptor, ADock preset ``frag_lite_np`` (32 chains x 64 MC steps, no exact polish);
  * **fixed 12 A cubic box** centred on the pocket centre (L-mode: volume-weighted centroid of the L-mode
    BURROW points; D-mode: the same for the matched merged region-rule pocket) -- the box is NOT a function
    of pocket size;
  * both panels are docked in one batch per pocket (one receptor typing + one grid set), so the panels are
    matched on compute and on receptor preparation;
  * per molecule we keep the best-affinity pose and record: affinity, inter, ligand efficiency, the pose
    centroid's distance to the nearest pocket point (pose-in-pocket check, 2 A), interaction-type contact
    counts and the buried fraction.

Receptor files: the TOUGH-M1 ``<key>.pdb`` are already protein-only (0 HETATM, no waters, no hydrogens), i.e.
the same protein view the pocket adapter featurised.

Env:  source .venv/bin/activate
      export NUMBA_CACHE_DIR=/tmp/numba_cache CUPY_CACHE_DIR=/tmp/adock/cupy_cache
      export PYTHONPATH=/tmp/adock/overlay:$ADOCK/src
Usage (one shard):
  python scripts/a2/dock_tough_m1.py --mode L --device cuda:0 --shard 0 --nshards 8 --seeds 0 \
      --out data/processed/docking/tough_m1/raw_L
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from rdkit import Chem, RDLogger
from scipy.spatial import cKDTree

RDLogger.DisableLog("rdApp.*")
ROOT = Path(__file__).resolve().parents[2]

BOX_SIDE = 12.0            # fixed cubic box (PocketVec; reviews/round1_domain.md §2)
IN_POCKET_CUT = 2.0        # pose centroid within 2 A of a pocket point
HB_CUT, APOLAR_CUT, AROM_CUT, CHARGE_CUT, BURY_CUT = 3.5, 4.5, 5.0, 5.0, 6.0
BURY_MIN_NB = 12           # a ligand heavy atom is "buried" with >= 12 receptor heavy atoms within BURY_CUT
PANELS = ("fragments_v1", "leadlike_v1")

# ADock preset frag_lite_np (feasibility report: 0.82 ms/pair/GPU, seed r 0.98, redock RMSD 0.3-1.2 A)
FRAG_LITE_NP = dict(n_chains=32, mc_steps=64, mc_segment=32, stageA_conformers=4, stageA_rotations=192,
                    polish_top=0, polish_iters=40, final_bfgs_iters=50, min_total_chains=0, n_out=3)

AROMATIC_RES = {"PHE": {"CG", "CD1", "CD2", "CE1", "CE2", "CZ"},
                "TYR": {"CG", "CD1", "CD2", "CE1", "CE2", "CZ"},
                "TRP": {"CG", "CD1", "CD2", "NE1", "CE2", "CE3", "CZ2", "CZ3", "CH2"},
                "HIS": {"CG", "ND1", "CD2", "CE1", "NE2"}}
POS_RES = {"ARG": {"NE", "CZ", "NH1", "NH2"}, "LYS": {"NZ"}}
NEG_RES = {"ASP": {"CG", "OD1", "OD2"}, "GLU": {"CD", "OE1", "OE2"}}


# --------------------------------------------------------------------------- receptor annotation
def annotate_receptor(pdb_path, cfg, center, half, rec_xyz):
    """Aromatic / +1 / -1 masks for the typed receptor atoms returned by adock.typing.type_receptor."""
    from adock.typing import read_pdb
    pdb = read_pdb(pdb_path, set(cfg["water_resnames"]))
    margin = half + max(p["cutoff"] for p in cfg["scoring"].values()) + 3.0
    keep = np.all(np.abs(pdb["xyz"] - np.asarray(center)) <= margin, axis=1)
    xyz, resn, name = pdb["xyz"][keep], pdb["resn"][keep], pdb["name"][keep]
    lut = {}
    for k in range(len(xyz)):
        lut.setdefault(tuple(np.round(xyz[k], 3)), k)
    idx = np.array([lut.get(tuple(np.round(p.astype(np.float64), 3)), -1) for p in rec_xyz], dtype=np.int64)
    ok = idx >= 0
    arom = np.zeros(len(rec_xyz), bool)
    pos = np.zeros(len(rec_xyz), bool)
    neg = np.zeros(len(rec_xyz), bool)
    for i in np.where(ok)[0]:
        rn, nm = resn[idx[i]], name[idx[i]]
        arom[i] = nm in AROMATIC_RES.get(rn, ())
        pos[i] = nm in POS_RES.get(rn, ())
        neg[i] = nm in NEG_RES.get(rn, ()) or nm == "OXT"
    return arom, pos, neg, float(ok.mean())


# --------------------------------------------------------------------------- ligand annotation
def ligand_annotation(preps, mols, cfg):
    idx = cfg["_xs_index"]
    don = {idx[t] for t in ("N_D", "N_DA", "O_D", "O_DA")}
    acc = {idx[t] for t in ("N_A", "N_DA", "O_A", "O_DA")}
    apol = {idx[t] for t in ("C_H", "F_H", "Cl_H", "Br_H", "I_H")}
    out = []
    for p, m in zip(preps, mols):
        if p is None:
            out.append(None)
            continue
        hv = np.where(p.heavy)[0]
        t = p.types[hv]
        mh = p.mol
        out.append(dict(hv=hv, n_heavy=len(hv),
                        don=np.isin(t, list(don)), acc=np.isin(t, list(acc)), apol=np.isin(t, list(apol)),
                        arom=np.array([mh.GetAtomWithIdx(int(i)).GetIsAromatic() for i in hv]),
                        pos=np.array([mh.GetAtomWithIdx(int(i)).GetFormalCharge() > 0 for i in hv]),
                        neg=np.array([mh.GetAtomWithIdx(int(i)).GetFormalCharge() < 0 for i in hv])))
    return out


def receptor_masks(rec_types, cfg, arom, pos, neg):
    idx = cfg["_xs_index"]
    don = np.isin(rec_types, [idx[t] for t in ("N_D", "N_DA", "O_D", "O_DA", "Met_D")])
    acc = np.isin(rec_types, [idx[t] for t in ("N_A", "N_DA", "O_A", "O_DA")])
    apol = np.isin(rec_types, [idx[t] for t in ("C_H", "F_H", "Cl_H", "Br_H", "I_H")])
    return dict(don=don, acc=acc, apol=apol, arom=arom, pos=pos, neg=neg)


def contact_profile(poses, anns, rec_xyz, rmask):
    """poses: list of (n_heavy, 3) best-pose heavy coordinates. Returns dict of per-molecule arrays."""
    n = len(poses)
    lig_xyz = np.concatenate(poses) if n else np.zeros((0, 3), np.float32)
    owner = np.concatenate([np.full(len(p), i, np.int64) for i, p in enumerate(poses)]) if n else np.zeros(0, np.int64)
    cat = lambda k: np.concatenate([a[k] for a in anns])
    lb = {k: cat(k) for k in ("don", "acc", "apol", "arom", "pos", "neg")}
    tl, tr = cKDTree(lig_xyz), cKDTree(rec_xyz)
    pairs = tl.sparse_distance_matrix(tr, BURY_CUT, output_type="ndarray")
    i, j, d = pairs["i"], pairs["j"], pairs["v"]
    o = owner[i]

    def count(mask):
        return np.bincount(o[mask], minlength=n).astype(np.int32)

    hbd = count((d <= HB_CUT) & lb["don"][i] & rmask["acc"][j])
    hba = count((d <= HB_CUT) & lb["acc"][i] & rmask["don"][j])
    apolar = count((d <= APOLAR_CUT) & lb["apol"][i] & rmask["apol"][j])
    aromatic = count((d <= AROM_CUT) & lb["arom"][i] & rmask["arom"][j])
    charged = count((d <= CHARGE_CUT) & ((lb["pos"][i] & rmask["neg"][j]) | (lb["neg"][i] & rmask["pos"][j])))
    nb = np.bincount(i, minlength=len(lig_xyz))
    buried_atom = nb >= BURY_MIN_NB
    nat = np.bincount(owner, minlength=n)
    bf = np.bincount(owner, weights=buried_atom.astype(float), minlength=n) / np.maximum(nat, 1)
    return dict(hbond_donor=hbd, hbond_acceptor=hba, apolar=apolar, aromatic=aromatic, charged=charged,
                buried_frac=bf.astype(np.float32))


# --------------------------------------------------------------------------- main worker
def load_panels(panel_dir: Path, panels=PANELS):
    mols, meta = [], []
    for panel in panels:
        sup = Chem.SDMolSupplier(str(panel_dir / f"{panel}.sdf"), removeHs=False)
        info = pd.read_csv(panel_dir / f"{panel}.csv").set_index("mol_id")
        for m in sup:
            if m is None:
                continue
            mols.append(m)
            mid = m.GetProp("_Name")
            meta.append(dict(panel=panel.split("_")[0], mol_id=mid,
                             n_heavy=int(info.loc[mid, "n_heavy"]), pharm_class=info.loc[mid, "pharm_class"]))
    return mols, pd.DataFrame(meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="L", choices=["L", "D"])
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--subset", default="", help="file with pocket_ids (one per line) to restrict to")
    ap.add_argument("--save_poses", action="store_true")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--panels", default=",".join(PANELS), help="per-panel timing runs")
    ap.add_argument("--geom_dir", default="data/processed/docking/tough_m1",
                    help="dir with pocket_geom.{npz,parquet} (tough_m1 or ppips)")
    a = ap.parse_args()

    torch.set_num_threads(a.threads)
    os.environ["ADOCK_CPU_THREADS"] = str(a.threads)
    from adock.config import load_config, sf_params
    from adock.grid import make_gridset
    from adock.ligand import LigandBatch
    from adock.scoring import PairPotential
    from adock.screen import prepare_ligands
    from adock.search import Problem, dock_problem, pad_receptors
    from adock.typing import type_receptor

    cfg = load_config()
    scfg = dict(cfg["search"]["v2_fast"], **FRAG_LITE_NP)
    sfp = sf_params(cfg, "vina")
    seeds = [int(s) for s in a.seeds.split(",")]
    outdir = ROOT / a.out
    outdir.mkdir(parents=True, exist_ok=True)

    geom = np.load(ROOT / a.geom_dir / "pocket_geom.npz", allow_pickle=False)
    scal = pd.read_parquet(ROOT / a.geom_dir / "pocket_geom.parquet")
    pid = geom["pocket_id"]
    sel = np.ones(len(pid), bool)
    if a.subset:
        keep = set(Path(ROOT / a.subset).read_text().split())
        sel &= np.array([p in keep for p in pid])
    if a.mode == "D":
        sel &= scal["d_matched"].to_numpy()
    rows_all = np.where(sel)[0]
    mine = rows_all[a.shard::a.nshards]
    if a.limit:
        mine = mine[:a.limit]
    print(f"shard {a.shard}/{a.nshards} mode {a.mode}: {len(mine)} pockets, seeds {seeds}", flush=True)

    mols, pmeta = load_panels(ROOT / "data/ref/panels", tuple(a.panels.split(",")))
    preps = prepare_ligands(mols, cfg, 0)
    bad = [i for i, p in enumerate(preps) if p is None]
    if bad:
        print(f"ligand prep failed for {len(bad)} molecules: {[pmeta.mol_id[i] for i in bad]}", flush=True)
    ok = [i for i, p in enumerate(preps) if p is not None]
    anns = ligand_annotation(preps, mols, cfg)
    lt = np.unique(np.concatenate([preps[i].types[preps[i].types >= 0] for i in ok]))
    pot = PairPotential(sfp, a.device)

    pts_key = "l_points" if a.mode == "L" else "d_points"
    ptr_key = "l_indptr" if a.mode == "L" else "d_indptr"
    ctr_key = "center_L" if a.mode == "L" else "center_D"
    P, PTR, CTR = geom[pts_key], geom[ptr_key], geom[ctr_key]

    rows, poses_out, t_start = [], {}, time.perf_counter()
    t_rec = t_grid = t_search = t_feat = 0.0
    n_fail = 0
    match_fracs = []
    for n_done, k in enumerate(mine):
        pocket = str(pid[k])
        try:
            c = CTR[k].astype(np.float64)
            size = np.full(3, BOX_SIDE)
            t0 = time.perf_counter()
            rxyz, rtypes = type_receptor(scal["receptor"].iloc[k], cfg, center=c, half_extent=size / 2)
            if len(rxyz) == 0:
                raise RuntimeError("no receptor atoms in box")
            arom, pos, neg, mf = annotate_receptor(scal["receptor"].iloc[k], cfg, c, BOX_SIDE / 2, rxyz)
            match_fracs.append(mf)
            rmask = receptor_masks(rtypes, cfg, arom, pos, neg)
            rec = {"rec_xyz": rxyz, "rec_types": rtypes, "center": c, "size": size}
            t1 = time.perf_counter()
            gs = make_gridset([rec], sfp, cfg["grid"]["spacing"], cfg["grid"]["out_of_box_penalty"],
                              device=a.device, lig_types=[lt])
            prec = pad_receptors([rec], a.device)
            tg = time.perf_counter()
            lb = LigandBatch([preps[i] for i in ok], a.device)
            ridx = torch.zeros(len(ok), dtype=torch.long, device=a.device)
            prob = Problem(gs, lb, ridx, pot, rec=prec)
            bc = torch.tensor(np.tile(c, (len(ok), 1)), dtype=torch.float32, device=a.device)
            ppts = P[PTR[k]:PTR[k + 1]]
            ptree = cKDTree(ppts) if len(ppts) else None
            for seed in seeds:
                t2 = time.perf_counter()
                res = dock_problem(prob, bc, [size] * len(ok), scfg, seed=seed)
                torch.cuda.synchronize(a.device) if a.device.startswith("cuda") else None
                t3 = time.perf_counter()
                best, aff, inter = [], [], []
                for li, i in enumerate(ok):
                    r = res[li]
                    b = int(np.argmin(r["affinity"]))
                    best.append(r["coords"][b][anns[i]["hv"]].astype(np.float32))
                    aff.append(float(r["affinity"][b]))
                    inter.append(float(r["inter"][b]))
                cen = np.stack([p.mean(0) for p in best])
                dist = ptree.query(cen)[0] if ptree is not None else np.full(len(best), np.inf)
                prof = contact_profile(best, [anns[i] for i in ok], rxyz, rmask)
                nh = np.array([anns[i]["n_heavy"] for i in ok], np.int32)
                aff = np.asarray(aff, np.float32)
                rows.append(pd.DataFrame(dict(
                    pocket_id=pocket, seed=np.int16(seed),
                    panel=pmeta.panel.to_numpy()[ok], mol_id=pmeta.mol_id.to_numpy()[ok],
                    n_heavy=nh, score=aff, inter=np.asarray(inter, np.float32),
                    le=(aff / nh).astype(np.float32),
                    pose_dist_pocket=dist.astype(np.float32), in_pocket=dist <= IN_POCKET_CUT,
                    **{k2: v for k2, v in prof.items()})))
                if a.save_poses:
                    poses_out[f"{pocket}|{seed}"] = np.concatenate(best).astype(np.float32)
                t_search += t3 - t2
                t_feat += time.perf_counter() - t3
            t_rec += t1 - t0
            t_grid += tg - t1
        except Exception as e:  # noqa: BLE001
            n_fail += 1
            print(f"FAIL {pocket}: {type(e).__name__}: {e}", flush=True)
        if (n_done + 1) % 50 == 0:
            el = time.perf_counter() - t_start
            print(f"  {n_done + 1}/{len(mine)}  {el:.0f}s  {el / (n_done + 1):.3f} s/pocket "
                  f"(rec {t_rec / (n_done + 1):.3f} grid {t_grid / (n_done + 1):.3f} "
                  f"search {t_search / (n_done + 1):.3f} feat {t_feat / (n_done + 1):.3f})", flush=True)

    df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    tag = f"shard{a.shard:02d}"
    df.to_parquet(outdir / f"{tag}.parquet", index=False)
    if a.save_poses:
        np.savez_compressed(outdir / f"{tag}_poses.npz", **poses_out)
    wall = time.perf_counter() - t_start
    stats = dict(shard=a.shard, nshards=a.nshards, mode=a.mode, device=a.device, seeds=seeds,
                 n_pockets=len(mine), n_fail=n_fail, n_rows=len(df), wall_s=round(wall, 1),
                 s_per_pocket=round(wall / max(1, len(mine)), 4),
                 s_rec=round(t_rec, 1), s_grid=round(t_grid, 1), s_search=round(t_search, 1),
                 s_feat=round(t_feat, 1), n_mols=len(ok), preset="frag_lite_np", box_side=BOX_SIDE,
                 panels=a.panels, rec_annot_match=round(float(np.mean(match_fracs)) if match_fracs else 0.0, 5),
                 host=os.uname().nodename)
    (outdir / f"{tag}.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats), flush=True)


if __name__ == "__main__":
    main()
