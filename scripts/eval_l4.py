#!/usr/bin/env python
"""Dev evaluation of the L4 candidates through scripts/eval_dev.py's PREREG §1 final selection (unchanged code).

    python scripts/eval_l4.py                         # N1/N2 (+ pool sensitivity) + every L4 model of configs/a4_grid.yaml
    python scripts/eval_l4.py --with-a4b              # ... + every A4b model (the full PREREG §1 candidate set)
    python scripts/eval_l4.py --B 20 --no-trials --models <dir> --out <scratch>     # smoke test

This wrapper only extends ``eval_dev.fs_candidates`` / ``eval_dev.fs_embed`` with the L4 candidates and then calls
``eval_dev.main_final_select`` (objective BLiPS-val D cb-AUC, homology-group SE, one-SE rule, guards BLiPS-val L
and TOUGH-M1-dev D >= B1, PPIPS-val P-ortho / P-sym; trials appended to results/trials.tsv with arm ``L4``).
L4 candidates: kind "learned", stored dims = out_dim x 3 seeds, grid order after every A4b config (so at equal
dims an A4b model is "simpler", PREREG A1).  Embeddings = results/models/l4/<config>/emb_<dataset>_<loc>.npy
(scripts/train_l4.py; rows = pocketcompare.a4b.ids_table order; locators L, U (BLiPS / TOUGH-M1 D mode), D (PPIPS)).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_dev as E  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402

_orig_candidates = E.fs_candidates
_orig_embed = E.fs_embed
OPTS = {"models": ROOT / "results/models/l4", "with_a4b": False}


def fs_candidates(which):
    import yaml
    out = _orig_candidates("all" if OPTS["with_a4b"] else "nonlearned")
    grid = yaml.safe_load((ROOT / "configs/a4_grid.yaml").read_text())
    for k, name in enumerate(grid["configs"]):
        d = Path(OPTS["models"]) / name
        if not (d / "config.json").exists():
            raise FileNotFoundError(f"L4 model {name} missing ({d})")
        cfg = json.loads((d / "config.json").read_text())
        out.append(E.Cand(f"L4:{name}", "learned", "L4", cfg["out_dim"] * len(cfg["seeds"]), 30 + k, str(d)))
    return out


def fs_embed(c, dataset, mode, pocket_ids, avail_mode):
    if c.inp != "L4":
        return _orig_embed(c, dataset, mode, pocket_ids, avail_mode)
    from pocketcompare import a4b as A4
    loc = "L" if mode == "L" else ("D" if dataset == "ppips" else "U")
    M = np.load(Path(c.model_dir) / f"emb_{dataset}_{loc}.npy")
    ids = A4.ids_table(dataset).pocket_id
    row = pd.Series(np.arange(len(ids)), index=ids).loc[list(pocket_ids)].to_numpy()
    Em = np.asarray(M[row], np.float32)
    av = (np.linalg.norm(Em, axis=1) > 0) & np.asarray(avail_mode, bool)
    Em[~av] = 0.0
    return Em, av


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--with-a4b", action="store_true")
    ap.add_argument("--models", default=str(OPTS["models"]))
    ap.add_argument("--B", type=int, default=ev.DEFAULT_B)
    ap.add_argument("--seed", type=int, default=SEEDS[0])
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--out", default=str(ROOT / "results/dev/l4"))
    ap.add_argument("--no-trials", action="store_true")
    a = ap.parse_args()
    OPTS.update(models=a.models, with_a4b=a.with_a4b)
    E.fs_candidates, E.fs_embed = fs_candidates, fs_embed
    os.environ["POCKETCOMPARE_THREADS"] = str(a.threads)
    args = argparse.Namespace(candidates="all_l4" if a.with_a4b else "nonlearned_l4", B=a.B, seed=a.seed,
                              threads=a.threads, out=a.out, no_trials=a.no_trials)
    E.main_final_select(args)


if __name__ == "__main__":
    main()
