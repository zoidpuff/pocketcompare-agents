#!/usr/bin/env python
"""Collect EPoCS pocket embeddings (run from envs/epocs, see DATA.md) into b5_epocs.npy aligned to b4 ids."""
import json, pickle, sys, time
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
run = Path(sys.argv[1]); dataset = sys.argv[2] if len(sys.argv) > 2 else "tough_m1"
out = ROOT / f"data/processed/descriptors/{dataset}"
b = pd.read_parquet(ROOT / f"data/processed/benchmarks/{dataset}_pockets.parquet").set_index("pocket_id")
ids = pd.read_parquet(out / "b4_esm2_ids.parquet")
X = np.full((len(ids), 2560), np.nan, np.float32); ok = []
for k, pid in enumerate(ids.pocket_id):
    f = run / "pocket_embeddings" / (Path(b.loc[pid, "ligand_file"]).stem + ".pkl")
    if f.exists():
        X[k] = pickle.load(open(f, "rb")); ok.append(True)
    else: ok.append(False)
ids = ids[["pocket_id", "structure_key"]].assign(has_epocs=ok)
np.save(out / "b5_epocs.npy", X); ids.to_parquet(out / "b5_epocs_ids.parquet")
(out / "b5_epocs_provenance.json").write_text(json.dumps(dict(
    tool="EPoCS", commit="bc9e15c89ef2078d8559b0f34a4d35bde40a44bb", esm="esm2_t36_3B_UR50D", dim=2560,
    metric="Euclidean (as published)", n_pockets=len(ids), n_embedded=int(sum(ok)), run_dir=str(run),
    time=time.strftime("%Y-%m-%dT%H:%M:%S")), indent=1))
print(len(ids), sum(ok))
