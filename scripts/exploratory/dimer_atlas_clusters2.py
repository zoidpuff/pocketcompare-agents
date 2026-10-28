#!/usr/bin/env python
"""EXPLORATORY (post-test) demo — ADDED AFTER the first clustering (dimer_atlas.py) gave 29 coarse Louvain
communities (largest 6,468) because the cos >= tau_pair (0.59) kNN graph is almost fully connected.
Stricter graph: MUTUAL top-10 neighbours (other structures) with cosine >= 0.80 (> p99.9 of interface x BLiPS
pairs, 0.72); Louvain (seed 0, resolution 1).  Cross-family = >= 5 distinct chain-group families and no family
> 30 % of members.  Symmetric homodimer copies sit in the same structure and are not linked."""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare import fpindex as FX  # noqa: E402
import faiss, networkx as nx  # noqa: E402
D = ROOT / "data/processed/dimer_atlas"; OUT = ROOT / "results/exploratory/dimer_atlas"
t0 = time.time()
M, V, _ = FX.read_table(D / "atlas_interface_pockets.parquet")
C = pd.read_parquet(D / "interface_clusters.parquet")
assert (C.pocket_id.to_numpy() == M.pocket_id.to_numpy()).all()
ix = faiss.IndexFlatIP(V.shape[1]); ix.add(V)
Dk, Ik = ix.search(V, 31)
st = M.structure_stem.to_numpy()
nb = []
for i in range(len(V)):
    s = [(int(j), float(d)) for j, d in zip(Ik[i], Dk[i]) if j != i and st[j] != st[i]][:10]
    nb.append(dict(s))
G = nx.Graph(); G.add_nodes_from(range(len(V)))
for i in range(len(V)):
    for j, d in nb[i].items():
        if d >= 0.80 and i in nb[j]:
            G.add_edge(i, j, weight=d)
comms = nx.community.louvain_communities(G, weight="weight", resolution=1.0, seed=0)
lab = np.full(len(V), -1)
for k, c in enumerate(sorted(comms, key=len, reverse=True)):
    lab[list(c)] = k
C["cluster_strict"] = lab
C["structure_stem"] = st
C["gene_pair"] = C.pair
cs = C.groupby("cluster_strict").agg(n=("pocket_id", "size"), n_dimers=("structure_stem", "nunique"),
        n_families=("family", "nunique"), organisms=("organism", lambda x: ",".join(sorted(set(x)))),
        median_ipTM=("ipTM", "median"), median_nn_mod_cos=("nn_mod_cos", "median"),
        top_pairs=("pair", lambda x: ", ".join(x.value_counts().index[:6])))
cs["max_family_share"] = C.groupby("cluster_strict").family.agg(lambda x: x.value_counts(normalize=True).iloc[0])
cs = cs.sort_values("n", ascending=False)
cs.to_csv(D / "clusters_strict.tsv", sep="\t", float_format="%.3f")
cs.head(50).to_csv(OUT / "clusters_strict_top50.tsv", sep="\t", float_format="%.3f")
C.to_parquet(D / "interface_clusters.parquet", index=False)
ge = cs[cs.n >= 10]
cross = ge[(ge.n_families >= 5) & (ge.max_family_share <= 0.3)].sort_values("n", ascending=False)
cross.head(15).to_csv(OUT / "clusters_strict_cross_family_top.tsv", sep="\t", float_format="%.3f")
summ = {"EXPLORATORY": True, "added_after_first_clustering": True, "n_edges": G.number_of_edges(),
        "n_pockets_with_edge": int(sum(1 for n in G.nodes if G.degree(n))), "n_clusters_total": int(len(cs)),
        "n_singletons": int((cs.n == 1).sum()), "n_clusters_ge2": int((cs.n >= 2).sum()),
        "n_clusters_ge10": int(len(ge)), "frac_pockets_in_ge10": float(ge.n.sum() / len(C)),
        "n_cross_family_ge10": int(len(cross)), "largest": int(cs.n.iloc[0]), "wall_s": time.time() - t0}
(OUT / "clusters_strict_summary.json").write_text(json.dumps(summ, indent=1))
print(json.dumps(summ, indent=1)); print(cs.head(12).to_string()); print(cross.head(8).to_string())
