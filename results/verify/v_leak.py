"""Leakage checks for TOUGH-M1-test vs TOUGH-M1-dev, BLiPS-train v2 and the A4b training data (verifier)."""
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify")
from vlib import ROOT  # noqa

r = {}
split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
nodes = pd.read_parquet(ROOT / "data/splits/homology_nodes.parquet")
tm = nodes[nodes.dataset == "tough_m1"].set_index("node_id")
split = split.join(tm[["pdb_id", "chain"]], on="node_id")
test, dev = split[split.partition == "test"], split[split.partition == "dev"]
key = lambda d: set(zip(d.pdb_id.str.lower(), d.chain))  # noqa
r["test_dev_pocket_id_overlap"] = len(set(test.pocket_id) & set(dev.pocket_id))
r["test_dev_pdbchain_overlap"] = len(key(test) & key(dev))
r["test_dev_pdb_overlap"] = len(set(test.pdb_id) & set(dev.pdb_id))
r["test_dev_sid_overlap"] = len(set(test.sid) & set(dev.sid))
r["test_dev_group_overlap"] = len(set(test.group_id) & set(dev.group_id))

bl = pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet")
btr = bl[bl.partition == "train"]
r["blips_train_sites"] = len(btr)
r["test_blipstrain_pdbchain_overlap"] = len(key(test) & set(zip(btr.pdb_id.str.lower(), btr.chain)))
r["test_blipstrain_pdb_overlap"] = len(set(test.pdb_id.str.lower()) & set(btr.pdb_id.str.lower()))
r["test_blipstrain_sid_overlap"] = len(set(test.sid) & set(btr.sid))
r["test_blipsall_v2_pdbchain_overlap"] = len(key(test) & set(zip(bl.pdb_id.str.lower(), bl.chain)))

# A4b training entities: BLiPS-train v2 sites (+ pairs), PPIPS-train pockets / pairs
pairs = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
r["blips_train_pairs_sites_all_train"] = bool(pairs.site_a.isin(btr.site_id).all() and pairs.site_b.isin(btr.site_id).all())
pk = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
cs = pd.read_parquet(ROOT / "data/splits/ppips_complex_splits.parquet").set_index("complex")
pt = pk[pk.split == "train"]
r["ppips_train_pockets"] = len(pt)
r["ppips_train_pocket_split_consistent"] = bool((cs.split.reindex(pt.complex).to_numpy() == "train").all())
sym = pd.read_parquet(ROOT / "data/splits/ppips_sym_pairs_train.parquet")
orth = pd.read_parquet(ROOT / "data/splits/ppips_ortho_queries_train.parquet")
ok = set(pt.pocket_id)
r["ppips_train_pairs_in_train_pockets"] = bool(sym.pocket_a.isin(ok).all() and sym.pocket_b.isin(ok).all()
                                               and orth["query"].isin(ok).all()
                                               and all(q in ok for qs in orth.positives for q in qs))
dim = nodes[nodes.dataset == "dimers"]
dim = dim.assign(cx=dim.node_id.str.split(":").str[1].str.rsplit("_", n=1).str[0])
ppips_train_sids = set(dim.sid[dim.cx.isin(set(pt.complex))])
r["ppips_train_complexes_mapped_to_nodes"] = int(dim.cx.isin(set(pt.complex)).sum())
# direct homology edges from TOUGH-M1-test chains to training entities
edges = pd.read_parquet(ROOT / "data/splits/homology_edges.parquet", columns=["sid_a", "sid_b"])
ts = set(test.sid)


def n_edges(S):
    return int(((edges.sid_a.isin(ts) & edges.sid_b.isin(S)) | (edges.sid_b.isin(ts) & edges.sid_a.isin(S))).sum()
               + len(ts & S))


r["direct_edges_test_to_blips_train"] = n_edges(set(btr.sid))
r["direct_edges_test_to_ppips_train"] = n_edges(ppips_train_sids)
r["direct_edges_test_to_dev"] = n_edges(set(dev.sid))
r["test_sealed_flags"] = test[["touch_burrow", "touch_sealed"]].sum().astype(int).to_dict()

# input_stats re-fit check (z-score statistics = BLiPS-train v2 L + D rows)
st = json.load(open(ROOT / "results/models/a4b/n1_linear/input_stats.json"))
ids = pd.read_parquet(ROOT / "data/processed/descriptors/blips/a1r/ids.parquet")
row = pd.Series(np.arange(len(ids)), index=ids.pocket_id).loc[sorted(btr.site_id)].to_numpy()
mx = []
for k, src in enumerate(("a1", "env")):
    Ms = []
    for loc in ("L", "U"):
        sph = np.load(ROOT / f"data/processed/descriptors/blips/a1r/{loc}_sph8.npz")[src][row].astype(float)
        base = np.load(ROOT / f"data/processed/descriptors/blips/a1r/{loc}_base.npz")[src][row].astype(float)
        fb = ~np.isfinite(sph).any(1) & np.isfinite(base).any(1)
        sph[fb] = base[fb]
        Ms.append(sph)
    M = np.concatenate(Ms)
    M = M[np.isfinite(M).any(1)]
    mx.append(float(np.nanmax(np.abs(np.nanmean(M, 0) - np.asarray(st["mean"][k])))))
    r[f"input_stats_n_ref_{src}"] = [int(len(M)), int(st["n_ref"][k])]
r["input_stats_mean_max_abs_diff_refit_on_blips_train"] = mx
json.dump(r, open(ROOT / "results/verify/v_leak.json", "w"), indent=1)
print(json.dumps(r, indent=1))
