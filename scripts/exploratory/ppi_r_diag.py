#!/usr/bin/env python
"""EXPLORATORY (post-test) PPI-R diagnostic — ADDED AFTER SCORES (not in the declared protocol).
Among each query's top-10 candidates that are PPI-L pockets (other homology groups), the share with the same Pfam
family as the query (remote-homology / same-family signal the PPI-L homology groups did not merge) and the share
with the same ligand cluster.  Arms FINAL and B4 (+ B1)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts/exploratory"))
import ppi_r  # noqa: E402
T = pd.read_parquet(ROOT / "data/processed/exploratory/ppi_r/ppi_r_pool.parquet")
P = pd.read_parquet(ROOT / "data/splits/ppi_l_pockets.parquet").set_index("pocket_id")
pf = T.pocket_id.map(P.pfam_name).fillna("").to_numpy()
lc = T.pocket_id.map(P.ligand_cluster).to_numpy()
Emb = ppi_r.embeddings(T)
isP = (T.set == "PPI").to_numpy(); grp = T.group.to_numpy()
q = np.flatnonzero(isP)
out = {}
for a in ("FINAL", "B4", "B1"):
    S = Emb[a][q] @ Emb[a].T
    same_pf, same_lc, ppi10 = [], [], []
    for k, i in enumerate(q):
        s = S[k].copy(); s[i] = -np.inf; s[isP & (grp == grp[i])] = -np.inf
        top = np.argsort(-s)[:10]
        tp = top[isP[top]]
        ppi10.append(isP[top].mean())
        if len(tp) and pf[i]:
            same_pf.append(np.mean(pf[tp] == pf[i]))
            same_lc.append(np.mean(lc[tp] == lc[i]))
    out[a] = {"p@10": float(np.mean(ppi10)), "share_top10_ppi_hits_same_pfam": float(np.mean(same_pf)),
              "share_top10_ppi_hits_same_ligand_cluster": float(np.nanmean(same_lc))}
# chance: share of other-group PPI pockets with the same Pfam, averaged over queries
ch = [np.mean(pf[isP & (grp != grp[i])] == pf[i]) for i in q if pf[i]]
out["chance_same_pfam_among_other_group_ppi"] = float(np.mean(ch))
print(json.dumps(out, indent=1))
(ROOT / "results/exploratory/ppi_r/diag_topk_family.json").write_text(json.dumps(out, indent=1))
