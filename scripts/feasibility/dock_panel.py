#!/usr/bin/env python
"""Dock a fragment panel into BURROW pockets with ADock (feasibility / cost study; ADock is read-only, imported).

Env (see reports/fragment_docking_feasibility.md):
  source .venv/bin/activate
  export PYTHONPATH=/tmp/adock/overlay:$ADOCK/src CUPY_CACHE_DIR=/tmp/adock/cupy_cache
Modes:
  --layout per_pocket : like adock.screen.dock_screen: one grid set per pocket, all fragments in one batch.
  --layout multi      : ALL (pocket, fragment) pairs in one Problem (one grid per pocket, rec_idx per pair),
                        searched in chunks of --chunk pairs. Ligand prep done once for the panel.
Presets: any ADock kernel preset (v2_fast, v2_default) or a custom one from PRESETS below.
Writes results/feasibility/scores_<tag>.tsv (one row per pocket x fragment x seed) and appends timing rows to
results/feasibility/timing.tsv.
"""
import argparse
import json
import os
import resource
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from rdkit import Chem

from adock.config import load_config, sf_params
from adock.grid import make_gridset
from adock.ligand import LigandBatch
from adock.scoring import PairPotential
from adock.screen import prepare_ligands
from adock.search import Problem, dock_problem, pad_receptors
from adock.typing import type_receptor

# custom lighter presets derived from v2_fast (fragments: <= 18 heavy atoms, <= 3 torsions)
PRESETS = {
    "frag_lite": dict(n_chains=32, mc_steps=64, mc_segment=32, stageA_conformers=4, stageA_rotations=192,
                      polish_top=8, polish_iters=40, final_bfgs_iters=50, min_total_chains=0, n_out=3),
    "frag_xlite": dict(n_chains=16, mc_steps=32, mc_segment=32, stageA_conformers=2, stageA_rotations=96,
                       polish_top=4, polish_iters=20, final_bfgs_iters=30, min_total_chains=0, n_out=1),
}
# rigid-ish scan: Stage A rigid enumeration (2 conformers x 96 rotations x lattice) + 20 BFGS steps, no MC, no polish
PRESETS["frag_scan"] = dict(n_chains=8, mc_steps=0, stageA_conformers=2, stageA_rotations=96, polish_top=0,
                            final_bfgs_iters=20, bfgs_iters=0, min_total_chains=0, n_out=1)
# "_nn": exact polish without per-ligand receptor neighbour lists (that Python loop dominates wall time for
# fragments: adock.mckernel.receptor_neighbours); "_np": no exact polish at all (final rescoring is still exact).
for _k in ["frag_lite", "frag_xlite", "v2_fast"]:
    _b = PRESETS.get(_k, {})
    PRESETS[_k + "_nn"] = dict(_b, polish_nbr_margin=0.0)
    PRESETS[_k + "_np"] = dict(_b, polish_top=0)


def cpu_s():
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def sync(dev):
    if dev.startswith("cuda"):
        torch.cuda.synchronize()


def search_cfg(cfg, preset):
    if preset in PRESETS:
        return dict(cfg["search"]["v2_fast"], **PRESETS[preset])
    return cfg["search"][cfg.get("mode_aliases", {}).get(preset, preset)]


def run(pockets, preps, cfg, scfg, seed, dev, layout, chunk):
    """Returns (list of (pocket_idx, frag_idx, result), timing dict)."""
    sfp = sf_params(cfg, "vina")
    ok = [i for i, p in enumerate(preps) if p is not None]
    lt = np.unique(np.concatenate([preps[i].types[preps[i].types >= 0] for i in ok]))
    pot = PairPotential(sfp, dev)
    tm = {"rec_s": 0.0, "grid_s": 0.0, "search_s": 0.0}
    out = []
    groups = [[k] for k in range(len(pockets))] if layout == "per_pocket" else [list(range(len(pockets)))]
    for g in groups:
        t0 = time.perf_counter()
        recs = []
        for k in g:
            box = json.loads(pockets[k]["box"])
            c, s = np.asarray(box["center"], float), np.asarray(box["size"], float)
            xyz, types = type_receptor(pockets[k]["receptor"], cfg, center=c, half_extent=s / 2)
            recs.append({"rec_xyz": xyz, "rec_types": types, "center": c, "size": s})
        t1 = time.perf_counter()
        gs = make_gridset(recs, sfp, cfg["grid"]["spacing"], cfg["grid"]["out_of_box_penalty"], device=dev,
                          lig_types=[lt] * len(recs))
        prec = pad_receptors(recs, dev)
        sync(dev)
        t2 = time.perf_counter()
        pairs = [(gi, i) for gi in range(len(g)) for i in ok]
        for b0 in range(0, len(pairs), chunk):
            pp = pairs[b0:b0 + chunk]
            lb = LigandBatch([preps[i] for _, i in pp], dev)
            ridx = torch.tensor([gi for gi, _ in pp], dtype=torch.long, device=dev)
            prob = Problem(gs, lb, ridx, pot, rec=prec)
            bc = torch.tensor(np.array([recs[gi]["center"] for gi, _ in pp]), dtype=torch.float32, device=dev)
            res = dock_problem(prob, bc, [recs[gi]["size"] for gi, _ in pp], scfg, seed=seed)
            out += [(g[gi], i, r) for (gi, i), r in zip(pp, res)]
        sync(dev)
        t3 = time.perf_counter()
        tm["rec_s"] += t1 - t0; tm["grid_s"] += t2 - t1; tm["search_s"] += t3 - t2
    return out, tm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pockets", default="results/feasibility/pockets.tsv")
    ap.add_argument("--fragments", default="results/feasibility/fragments.sdf")
    ap.add_argument("--n_frag", type=int, default=64)
    ap.add_argument("--n_pockets", type=int, default=0, help="0 = all")
    ap.add_argument("--preset", default="v2_fast")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--layout", default="per_pocket", choices=["per_pocket", "multi"])
    ap.add_argument("--chunk", type=int, default=4096)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--no_scores", action="store_true")
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    os.environ["ADOCK_CPU_THREADS"] = str(a.threads)
    cfg = load_config()
    scfg = search_cfg(cfg, a.preset)
    pk = pd.read_csv(a.pockets, sep="\t")
    if a.n_pockets:
        pk = pk.head(a.n_pockets)
    pockets = pk.to_dict("records")
    mols = [m for m in Chem.SDMolSupplier(a.fragments, removeHs=False)][:a.n_frag]
    t0 = time.perf_counter()
    preps = prepare_ligands(mols, cfg, 0)
    prep_s = time.perf_counter() - t0
    nfail = sum(p is None for p in preps)
    # warm-up (kernel compile / caches), untimed
    run(pockets[:1], preps[:4], cfg, scfg, 0, a.device, "per_pocket", a.chunk)
    rows, trows = [], []
    for seed in [int(s) for s in a.seeds.split(",")]:
        c0, w0 = cpu_s(), time.perf_counter()
        out, tm = run(pockets, preps, cfg, scfg, seed, a.device, a.layout, a.chunk)
        wall, cpu = time.perf_counter() - w0, cpu_s() - c0
        n = len(out)
        trows.append(dict(timestamp=time.strftime("%F %T"), tag=a.tag, preset=a.preset, device=a.device,
                          threads=a.threads, layout=a.layout, seed=seed, n_pockets=len(pockets),
                          n_frag=len(mols) - nfail, n_pairs=n, wall_s=round(wall, 3),
                          ms_per_pair=round(1000 * wall / n, 3), cpu_s_per_pair=round(cpu / n, 4),
                          lig_prep_s_once=round(prep_s, 3), **{k: round(v, 3) for k, v in tm.items()},
                          load1=os.getloadavg()[0], host=os.uname().nodename))
        print(json.dumps(trows[-1]), flush=True)
        for k, i, r in out:
            j = int(np.argmin(r["affinity"]))
            rows.append(dict(pocket_id=pockets[k]["pocket_id"], frag=i, frag_name=mols[i].GetProp("_Name"),
                             seed=seed, affinity=float(r["affinity"][j]), inter=float(r["inter"][j]),
                             n_heavy=mols[i].GetNumHeavyAtoms(),
                             pose_centroid=json.dumps(np.round(r["coords"][j][:preps[i].n][preps[i].heavy].mean(0), 2).tolist())))
    od = Path("results/feasibility")
    if not a.no_scores:
        pd.DataFrame(rows).to_csv(od / f"scores_{a.tag}.tsv", sep="\t", index=False)
    tp = od / "timing.tsv"
    df = pd.DataFrame(trows)
    if tp.exists():
        df = pd.concat([pd.read_csv(tp, sep="\t"), df], ignore_index=True)
    df.to_csv(tp, sep="\t", index=False)


if __name__ == "__main__":
    main()
