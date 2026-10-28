"""Independent C2 re-derivation + ProSPECCTs sanity (D1/D1.2/D2) + P6 vs P6.2 investigation."""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify")
from vlib import ROOT, final_scores, desc_matrix, pair_cos, read_sealed, unit_weights, zcos_embed  # noqa

res = {}
pairs, h = read_sealed("prospeccts_pairs.parquet", "verify C2 + ProSPECCTs sanity + P6/P6.2 (independent verifier)")
res["sha256"] = h
res["columns"] = list(pairs.columns)
tab = pd.read_parquet(ROOT / "data/processed/benchmarks/prospeccts_pockets.parquet").set_index("pocket_id")

# --- own subset identification from the pocket source directory (+ phosphate flag for D5 vs D5.2)
DIR2SUB = {"identical_structures": "P1", "identical_structures_similar_ligands": "P1.2", "NMR_structures": "P2",
           "decoy_rational_structures": "P3", "decoy_shape_structures": "P4", "kahraman_structures": "P5.2",
           "barelier_structures": "P6", "barelier_structures_cofactors": "P6.2", "review_structures": "P7"}
da = pairs.pocket_a.str.split(":").str[1].str.split("/").str[0]
db = pairs.pocket_b.str.split(":").str[1].str.split("/").str[0]
res["pairs_with_mixed_dirs_by_reported_subset"] = pairs[da != db].subset.value_counts().to_dict()
own = da.map(DIR2SUB)
# decoy pairs: query from identical_structures dir paired with decoy dir -> use the decoy dir
own = np.where(da != db, db.map(DIR2SUB), own)
res["reported_subset_counts"] = pairs.subset.value_counts().to_dict()
cmp_ = pd.crosstab(pairs.subset, own)
res["crosstab_reported_vs_own"] = {r: {c: int(v) for c, v in cmp_.loc[r].items() if v} for r in cmp_.index}

# self-pairs: identical pocket id; also same PDB entry + chain
self_id = (pairs.pocket_a == pairs.pocket_b).to_numpy()
pa = tab.reindex(pairs.pocket_a)
pb = tab.reindex(pairs.pocket_b)
self_pdb = (pa.pdb_id.to_numpy() == pb.pdb_id.to_numpy()) & (pa.chain.to_numpy() == pb.chain.to_numpy())
res["self_counts"] = {s: {"is_self_col": int(pairs.is_self[pairs.subset == s].sum()),
                          "same_pocket_id": int(self_id[pairs.subset == s].sum()),
                          "same_pdb_chain": int(self_pdb[(pairs.subset == s).to_numpy()].sum())}
                      for s in sorted(pairs.subset.unique())}
res["is_self_equals_same_id"] = bool((pairs.is_self.to_numpy(bool) == self_id).all())

# --- P6 vs P6.2 pair-table identity (after stripping the directory)
def canon(df):
    a = df.pocket_a.str.split("/").str[-1]
    b = df.pocket_b.str.split("/").str[-1]
    return pd.DataFrame({"a": np.minimum(a, b), "b": np.maximum(a, b), "y": df.label.astype(int).to_numpy()}
                        ).sort_values(["a", "b"]).reset_index(drop=True)


p6, p62 = canon(pairs[pairs.subset == "P6"]), canon(pairs[pairs.subset == "P6.2"])
res["P6_vs_P62"] = {"n_P6": len(p6), "n_P62": len(p62), "identical_pairs_and_labels": bool(p6.equals(p62)),
                    "n_pos": int(p6.y.sum())}

# --- homology units (own mapping: homology_nodes pocket_ids -> group; decoy/unmapped -> parent PDB group or own)
nodes = pd.read_parquet(ROOT / "data/splits/homology_nodes.parquet", columns=["dataset", "pdb_id", "chain", "pocket_ids",
                                                                              "sid", "group_id"])
pr = nodes[nodes.dataset == "prospeccts"].copy()
ex = pr.assign(pid=pr.pocket_ids.str.split(";")).explode("pid")
grp = {}
for r in ex.itertuples():
    if r.pid not in grp or r.chain == tab.chain.get(r.pid):
        grp[r.pid] = r.group_id
by_pdb = pr.groupby("pdb_id").group_id.first()

# BURROW-clean flag (own): node sid has no direct edge to a BURROW train/dev/partner sid
edges = pd.read_parquet(ROOT / "data/splits/homology_edges.parquet", columns=["sid_a", "sid_b"])
bsid = set(nodes.sid[nodes.dataset.isin(["burrow_train", "burrow_dev", "burrow_partner"])])
touch = set(edges.sid_b[edges.sid_a.isin(bsid)]) | set(edges.sid_a[edges.sid_b.isin(bsid)]) | bsid
sid_of = {}
for r in ex.itertuples():
    if r.pid not in sid_of or r.chain == tab.chain.get(r.pid):
        sid_of[r.pid] = r.sid
sid_by_pdb = pr.groupby("pdb_id").sid.first()


def unit_of(p):
    if p in grp:
        return grp[p]
    pdb = tab.pdb_id.get(p)
    return by_pdb.get(pdb, f"own:{p}")


def clean_of(p):
    s = sid_of.get(p)
    if s is None:
        s = sid_by_pdb.get(tab.pdb_id.get(p))
    return s is not None and s not in touch


ix = pd.read_parquet(ROOT / "data/processed/cache/points/prospeccts/index.parquet").set_index("pocket_id")
summ = pd.read_parquet(ROOT / "results/final/final_summary.parquet")
FIN = "pocketcompare-final:A4b:n1_linear|raw"

subsets = {}
for sub in ["P1", "P1.2", "P2", "P3", "P4", "P5", "P5.2", "P6", "P6.2", "P7"]:
    pp = pairs[pairs.subset == sub].reset_index(drop=True)
    pid = sorted(set(pp.pocket_a) | set(pp.pocket_b))
    pos = {p: i for i, p in enumerate(pid)}
    ia, ib = pp.pocket_a.map(pos).to_numpy(), pp.pocket_b.map(pos).to_numpy()
    y = pp.label.astype(int).to_numpy()
    g = ix.reindex(pid)
    okc = (g.status == "ok").to_numpy()
    dm = okc & ((g.d_coverage.to_numpy(float) >= 0.3) | (g.d_precision.to_numpy(float) >= 0.5))
    clean = np.array([clean_of(p) for p in pid])
    dpool = dm & clean
    u = pd.factorize(pd.Series([unit_of(p) for p in pid]))[0]
    sF = final_scores("prospeccts", "L", pid, okc, ia, ib)
    sFD = final_scores("prospeccts", "U", pid, dpool, ia, ib)
    sB1 = pair_cos(zcos_embed(desc_matrix("prospeccts", "b1_default_L", pid), okc), ia, ib)
    noself = ia != ib
    d = {"n_pairs": len(y), "n_pockets": len(pid), "n_self": int((~noself).sum()), "n_units": int(u.max() + 1)}
    for nm, s in (("FINAL_L", sF), ("B1_L", sB1)):
        for tag, m0 in (("with_self", np.ones(len(y), bool)), ("no_self", noself)):
            m = m0 & np.isfinite(s)
            d[f"{nm}_{tag}"] = float(roc_auc_score(y[m], s[m])) if 0 < y[m].sum() < m.sum() else None
            d[f"{nm}_{tag}_n"] = int(m.sum())
    for tag, m0 in (("with_self", np.ones(len(y), bool)), ("no_self", noself)):
        m = m0 & np.isfinite(sFD)
        d[f"FINAL_D_{tag}_n"], d[f"FINAL_D_{tag}_npos"] = int(m.sum()), int(y[m].sum())
        d[f"FINAL_D_{tag}"] = float(roc_auc_score(y[m], sFD[m])) if 0 < y[m].sum() < m.sum() else None
    d["n_burrow_clean_pockets"], d["n_dmatch_pockets"], d["n_D_pool"] = int(clean.sum()), int(dm.sum()), int(dpool.sum())
    rs = summ[(summ.set == f"prospeccts_{sub}") & (summ.config.isin([FIN, "default"])) & (summ.variant == "raw")]
    d["reported"] = {f"{a.arm}|{a.subset}|{a.mode}": [float(a.auc), int(a.n_pairs)] for a in rs.itertuples()
                     if a.arm in ("FINAL", "B1")}
    subsets[sub] = d
    if sub in ("P5.2", "P6.2", "P7"):
        m = noself & np.isfinite(sF) & np.isfinite(sB1)
        subsets[sub]["_c2"] = (y[m], sF[m], sB1[m], u[ia][m], u[ib][m])
res["subsets"] = {k: {kk: vv for kk, vv in v.items() if kk != "_c2"} for k, v in subsets.items()}

# --- C2: macro delta with independent per-subset vertex bootstrap (homology-group units)
B = 2000
deltas, boots, ndeg = {}, {}, 0
for k, sub in enumerate(("P5.2", "P6.2", "P7")):
    y, sa, sb, ua, ub = subsets[sub]["_c2"]
    deltas[sub] = roc_auc_score(y, sa) - roc_auc_score(y, sb)
    units, inv = np.unique(np.concatenate([ua, ub]), return_inverse=True)
    ja, jb = inv[:len(ua)], inv[len(ua):]
    nu = len(units)
    rng = np.random.default_rng([4242, k])
    bt = np.full(B, np.nan)
    for b in range(B):
        c = rng.multinomial(nu, np.full(nu, 1.0 / nu))
        w = unit_weights(c, ja, jb)
        m = w > 0
        if y[m].min() == y[m].max():
            continue
        bt[b] = roc_auc_score(y[m], sa[m], sample_weight=w[m]) - roc_auc_score(y[m], sb[m], sample_weight=w[m])
    boots[sub] = bt
    res.setdefault("c2_per_subset", {})[sub] = {"delta": deltas[sub], "n_pairs": len(y), "n_units": nu,
                                                "auc_final": roc_auc_score(y, sa), "auc_b1": roc_auc_score(y, sb),
                                                "ci": [float(np.nanquantile(bt, .025)), float(np.nanquantile(bt, .975))],
                                                "n_degenerate": int(np.isnan(bt).sum())}
macro = np.mean(list(deltas.values()))
mb = np.mean([boots[s] for s in boots], 0)
mb = mb[np.isfinite(mb)]
res["C2"] = {"macro_delta": macro, "ci": [float(np.quantile(mb, .025)), float(np.quantile(mb, .975))],
             "lower95": float(np.quantile(mb, .05)), "se": float(mb.std(ddof=1)),
             "p": float((1 + (mb <= 0).sum()) / (len(mb) + 1)), "n_valid": int(len(mb))}
json.dump(res, open(ROOT / "results/verify/v_prospeccts.json", "w"), indent=1, default=float)
print(json.dumps(res, indent=1, default=float))
