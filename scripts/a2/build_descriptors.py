#!/usr/bin/env python
"""A2: build the descriptor blocks for every TOUGH-M1 pocket and run the label-free size-confound diagnostics.

The reference pocket set (on which the non-binder threshold, the LE regression coefficients and every z-score
statistic are fitted) must be given explicitly.  The default file is a deterministic SEEDS[0] sample of 2,000
TOUGH-M1 pockets, written by this script if missing; **at evaluation time the caller must pass the split's own
reference set instead** (DESIGN §3/§4).

  python scripts/a2/build_descriptors.py --panels fragments,leadlike
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.descriptors.a2 import A2Config, A2Descriptor, load_raw  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402

BASE = ROOT / "data/processed/docking/tough_m1"
OUT = ROOT / "results/a2"


def reference_ids(path: Path, pockets: np.ndarray, n: int) -> np.ndarray:
    if path.exists():
        return np.array(path.read_text().split())
    rng = np.random.default_rng(SEEDS[0])
    ref = np.sort(rng.choice(np.sort(pockets), size=min(n, len(pockets)), replace=False))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(ref) + "\n")
    return ref


def diagnostics(X: np.ndarray, logv: np.ndarray, bur: np.ndarray, rng) -> dict:
    Xc = X - X.mean(0, keepdims=True)
    sd = Xc.std(0, keepdims=True)
    Xs = Xc / np.where(sd > 1e-8, sd, 1.0)
    u, s, _ = np.linalg.svd(Xs, full_matrices=False)
    pc1 = u[:, 0] * s[0]
    var = (s ** 2) / (s ** 2).sum()
    # cosine pair similarity vs size similarity on a random pair sample (no labels involved)
    n = len(X)
    i = rng.integers(0, n, 200_000)
    j = rng.integers(0, n, 200_000)
    keep = i != j
    i, j = i[keep], j[keep]
    Xn = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-8)
    cos = (Xn[i] * Xn[j]).sum(1)
    dvol = np.abs(logv[i] - logv[j])
    return dict(pc1_var_frac=round(float(var[0]), 4), pc5_var_frac=round(float(var[:5].sum()), 4),
                pc1_spearman_logvol=round(float(spearmanr(pc1, logv).statistic), 4),
                pc1_spearman_bur=round(float(spearmanr(pc1, bur).statistic), 4),
                cos_vs_absdlogvol_spearman=round(float(spearmanr(cos, dvol).statistic), 4),
                cos_mean=round(float(cos.mean()), 4), cos_p90=round(float(np.percentile(cos, 90)), 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panels", default="fragments,leadlike")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--reference", default="results/a2/reference_pockets.txt")
    ap.add_argument("--n_reference", type=int, default=2000)
    ap.add_argument("--mode", default="L", choices=["L", "D"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    geom = pd.read_parquet(BASE / "pocket_geom.parquet")
    rng = np.random.default_rng(SEEDS[0])
    report = {"reference_file": a.reference, "panels": {}}

    for panel in a.panels.split(","):
        raw = load_raw(BASE / f"{panel}{a.suffix}.parquet")
        pockets = raw.pocket_id.unique()
        ref = reference_ids(ROOT / a.reference, pockets, a.n_reference)
        report["n_reference"] = int(len(ref))
        cfg = A2Config(panel=panel, volume_column=f"volume_{a.mode}", buriedness_column=f"bur16_{a.mode}")
        d = A2Descriptor(cfg).fit(raw, geom, reference_pocket_ids=ref)
        d.save(OUT / f"{panel}{a.suffix}_ref.npz")
        X = d.transform(raw, geom)
        np.savez_compressed(OUT / f"a2_{panel}{a.suffix}_descriptors.npz", pocket_id=X.pocket_id,
                            mol_id=X.mol_id, rank=X.rank, le_resid=X.le_resid, ifp=X.ifp)
        g = geom.set_index("pocket_id").loc[X.pocket_id]
        logv = np.log(g[f"volume_{a.mode}"].to_numpy())
        bur = g[f"bur16_{a.mode}"].to_numpy()
        # baseline for comparison: the raw score matrix, double-centred ("dz" of the feasibility report)
        S = raw.pivot(index="pocket_id", columns="mol_id", values="score").loc[X.pocket_id].to_numpy()
        dz = S - S.mean(0, keepdims=True)
        dz = (dz - dz.mean(1, keepdims=True)) / np.maximum(dz.std(1, keepdims=True), 1e-8)
        blocks = dict(raw_score_dz=dz, rank=X.rank, le_resid=X.le_resid, ifp=X.ifp,
                      all=X.concat(("rank", "le_resid", "ifp")))
        report["panels"][panel] = {k: diagnostics(v, logv, bur, np.random.default_rng(SEEDS[0]))
                                   for k, v in blocks.items()}
        report["panels"][panel]["dims"] = {k: int(v.shape[1]) for k, v in blocks.items()}
        report["panels"][panel]["bytes_float32_per_pocket"] = int(blocks["all"].shape[1] * 4)
    (OUT / f"descriptor_diagnostics_{a.mode}{a.suffix}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
