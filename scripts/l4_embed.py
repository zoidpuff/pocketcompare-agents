#!/usr/bin/env python
"""L4 ensemble embeddings of every pocket of a dataset, from a trained model dir (label-free inference).

    python scripts/l4_embed.py --model results/models/l4/egnn_small --datasets all --device cuda:2

Uses scripts/train_l4.py's own ``load_models`` / ``ensemble_embed`` (point sets data/processed/l4/<dataset>, rows =
pocketcompare.a4b.ids_table order, locators L / U (D mode) / D (PPIPS)).  Writes
data/processed/l4_emb/<model>/emb_<dataset>_<loc>.npy (+ ids.json with the sha256s and, for datasets the training run
already embedded, the max |difference| to the model dir's emb_*.npy as a reproducibility check).  The model dir is
not modified.  Reads no label or pair file; the sealed external sets are covered only via their label-free point sets.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import train_l4 as T  # noqa: E402
from pocketcompare import a4b as A4  # noqa: E402
from pocketcompare.provenance import sha256_file  # noqa: E402

DATASETS = ("tough_m1", "blips", "blips_test_holo", "blips_test_af", "ppips", "prospeccts", "vertex")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default=str(ROOT / "results/models/l4/egnn_small"))
    ap.add_argument("--datasets", default="all")
    ap.add_argument("--device", default="cuda:2")
    a = ap.parse_args()
    t0 = time.time()
    mdir = Path(a.model)
    out = ROOT / "data/processed/l4_emb" / mdir.name
    out.mkdir(parents=True, exist_ok=True)
    models, cfg, sc, n1s = T.load_models(mdir, a.device)
    info = {"model": str(mdir), "device": a.device, "files": {}, "check_vs_model_dir": {}}
    for ds in (DATASETS if a.datasets == "all" else a.datasets.split(",")):
        if not (ROOT / "data/processed/l4" / ds / "ids.parquet").exists():
            info["files"][ds] = "no point sets"
            continue
        ids = A4.ids_table(ds).pocket_id.tolist()
        for loc in (("D",) if ds == "ppips" else ("L", "U")):
            E, av = T.ensemble_embed(models, cfg, sc, n1s, ds, loc, ids, a.device)
            f = out / f"emb_{ds}_{loc}.npy"
            np.save(f, E)
            info["files"][f.name] = {"sha256": sha256_file(f), "n": int(len(E)), "n_available": int(av.sum())}
            ref = mdir / f.name
            if ref.exists():
                R = np.load(ref)
                info["check_vs_model_dir"][f.name] = float(np.abs(R - E).max()) if R.shape == E.shape else "shape"
            print(f"{f.name}: {E.shape}, available {av.sum()}", flush=True)
    info["wall_s"] = round(time.time() - t0, 1)
    (out / "ids.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info["check_vs_model_dir"], indent=1))


if __name__ == "__main__":
    main()
