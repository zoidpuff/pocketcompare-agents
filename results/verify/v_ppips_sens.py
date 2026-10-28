"""Sensitivity: C1a/C1b on TOUGH-M1-test pairs whose pockets have no direct homology edge to PPIPS-train chains
(A4b training data).  Verifier code."""
import json
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify")
from vlib import ROOT, boot_paired, components_from_labels, desc_matrix, final_scores, pair_cos, read_sealed, zcos_embed  # noqa

pairs, _ = read_sealed("tough_m1_test_pairs.parquet", "verify: sensitivity to PPIPS-train homology (verifier)")
split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
P = split[split.partition == "test"].sort_values("pocket_id").reset_index(drop=True)
pos = {p: i for i, p in enumerate(P.pocket_id)}
ia, ib = pairs.pocket_a.map(pos).to_numpy(), pairs.pocket_b.map(pos).to_numpy()
y = pairs.label.astype(int).to_numpy()
unit = components_from_labels(P.ligand_cluster.to_numpy(), P.group_id.to_numpy())

nodes = pd.read_parquet(ROOT / "data/splits/homology_nodes.parquet")
pk = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
dim = nodes[nodes.dataset == "dimers"]
dim = dim.assign(cx=dim.node_id.str.split(":").str[1].str.rsplit("_", n=1).str[0])
S = set(dim.sid[dim.cx.isin(set(pk.complex[pk.split == "train"]))])
edges = pd.read_parquet(ROOT / "data/splits/homology_edges.parquet", columns=["sid_a", "sid_b"])
ts = set(P.sid)
hit = set(edges.sid_a[edges.sid_a.isin(ts) & edges.sid_b.isin(S)]) | set(edges.sid_b[edges.sid_b.isin(ts) & edges.sid_a.isin(S)]) | (ts & S)
flag = P.sid.isin(hit).to_numpy()
ok = np.ones(len(P), bool)
sF = final_scores("tough_m1", "L", P.pocket_id, ok, ia, ib)
sB1 = pair_cos(zcos_embed(desc_matrix("tough_m1", "b1_default_L", P.pocket_id), ok), ia, ib)
sB4 = pair_cos(zcos_embed(desc_matrix("tough_m1", "b4_esm2_L", P.pocket_id, "b4_esm2_ids.parquet"), ok), ia, ib)
inpairs = np.zeros(len(P), bool)
inpairs[ia] = inpairs[ib] = True
m = ~flag[ia] & ~flag[ib]
r = {"n_test_pockets_with_edge_to_ppips_train": int(flag.sum()), "of_pockets_in_pairs": int((flag & inpairs).sum()),
     "n_pockets_in_pairs": int(inpairs.sum()), "n_pairs_clean": int(m.sum()), "n_pos_clean": int(y[m].sum())}
for nm, sb in (("C1a_clean", sB1), ("C1b_clean", sB4)):
    q = boot_paired(y[m], sF[m], sb[m], unit[ia][m], unit[ib][m], B=2000, seed=99)
    q.pop("boot")
    r[nm] = q
r["final_auc_pairs_touching_ppips_homologues"] = float(roc_auc_score(y[~m], sF[~m]))
json.dump(r, open(ROOT / "results/verify/v_ppips_sens.json", "w"), indent=1, default=float)
print(json.dumps(r, indent=1, default=float))
