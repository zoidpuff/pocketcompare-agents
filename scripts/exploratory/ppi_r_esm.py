#!/usr/bin/env python
"""EXPLORATORY (post-test). B4 ESM-2 L-mode pocket embeddings for PPI-L TRAIN+VAL pockets only (PPI-R task).

Same recipe as scripts/compute_esm.py (generic branch): ESM-2 650M last layer, mean over the L-mode lining residues
(data/splits/ppi_l_pockets.parquet ``lining_residues``), chains embedded separately, sequence-hash cache shared with
the project cache.  PPI-L test pockets are not processed.  Output: data/processed/exploratory/ppi_r/b4_esm2_L_ppil.npz
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.descriptors import esm_pocket as ep  # noqa: E402


def main(device="cuda:1"):
    t0 = time.time()
    P = pd.read_parquet(ROOT / "data/splits/ppi_l_pockets.parquet")
    P = P[P.split.isin(["train", "val"])].reset_index(drop=True)
    emb = ep.ESMEmbedder(device, ROOT / "data/processed/esm")
    L = np.full((len(P), ep.DIM), np.nan, np.float32)
    err = [None] * len(P)
    for k_s, (path, g) in enumerate(P.groupby("structure_path", sort=True)):
        try:
            chains = ep.chain_residues(path)
            need = {x.partition(":")[0] for res in g.lining_residues for x in str(res).split()}
            chains = {c: v for c, v in chains.items() if c in need} or chains
            embs = {c: emb.embed_chain(sq) for c, (sq, _) in chains.items()}
            for k, res in zip(g.index, g.lining_residues):
                v, nf, nm = ep.pool_pocket(chains, embs, str(res).split())
                if v is not None:
                    L[k] = v
        except Exception as e:  # noqa: BLE001
            for k in g.index:
                err[k] = repr(e)[:200]
        if k_s % 200 == 0:
            print(k_s, f"{time.time() - t0:.0f}s", flush=True)
    out = ROOT / "data/processed/exploratory/ppi_r"
    out.mkdir(parents=True, exist_ok=True)
    np.savez(out / "b4_esm2_L_ppil.npz", pocket_id=P.pocket_id.to_numpy().astype(str), L=L,
             error=np.array([e or "" for e in err]))
    print(f"done {len(P)} pockets, {int(np.isfinite(L[:, 0]).sum())} embedded, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(*sys.argv[1:])
