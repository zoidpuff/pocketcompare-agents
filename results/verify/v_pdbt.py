"""Independent re-derivation of PREREG2 R1 / R2 / R3 on PDB-T (D-mode common set) + exclusion / training-table checks."""
import hashlib
import json
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify")
from vlib import ROOT, boot_paired, desc_matrix, final_seed_embeddings, pair_cos, read_sealed, zcos_embed  # noqa

r = {}
exp = [l.split()[0] for l in (ROOT / "data/sealed_SHA256SUMS.txt").read_text().splitlines()
       if l.strip().endswith("data/sealed/pdbt_pairs.parquet")]
pairs, h = read_sealed("pdbt_pairs.parquet", "verify PREREG2 R1/R2/R3 (independent verifier)")
r["sha256"], r["sha256_expected"], r["sha256_ok"] = h, exp, h in exp
r["pair_columns"] = list(pairs.columns)
ca, cb = ("site_a", "site_b") if "site_a" in pairs else ("pocket_a", "pocket_b")

S = pd.read_parquet(ROOT / "data/splits/pdbt_sites.parquet")
r["n_sites_file"], r["n_excluded"] = len(S), int(S.excluded.sum())
D25 = {"pdbt:32qr_A:0", "pdbt:9kmd_H:0", "pdbt:9l3u_A:0", "pdbt:9lo8_O:0", "pdbt:9lqe_B:0", "pdbt:9qmf_C:0",
       "pdbt:9s30_A:0", "pdbt:9s30_A:1", "pdbt:9woj_C:0"}   # chains named in audit_splits.md "PDB-T audit" (D25)
exc = set(S.site_id[S.excluded])
r["excluded_equals_audit_list"] = exc == D25
r["excluded_flag_equals_audit_tm_boundary"] = bool((S.excluded == S.excluded_audit_tm_boundary).all())
keep_sites = S[~S.excluded].sort_values("site_id").reset_index(drop=True)
kp = pairs[ca].isin(keep_sites.site_id) & pairs[cb].isin(keep_sites.site_id)
r["n_pairs_file"], r["n_pairs_dropped"], r["n_pos_dropped"] = len(pairs), int((~kp).sum()), int(pairs.label[~kp].sum())
r["pairs_with_unknown_site"] = int((~(pairs[ca].isin(S.site_id) & pairs[cb].isin(S.site_id))).sum())
pairs = pairs[kp].reset_index(drop=True)
pid = keep_sites.site_id.tolist()
pos = {p: i for i, p in enumerate(pid)}
ia, ib = pairs[ca].map(pos).to_numpy(), pairs[cb].map(pos).to_numpy()
y = pairs.label.astype(int).to_numpy()
unit = pd.factorize(keep_sites.hom_component)[0]

ix = pd.read_parquet(ROOT / "data/processed/cache/points/pdbt/index.parquet").set_index("pocket_id").reindex(pid)
ok = (ix.status == "ok").to_numpy()
dm = ok & ((ix.d_coverage.to_numpy(float) >= 0.3) | (ix.d_precision.to_numpy(float) >= 0.5))
dset = dm[ia] & dm[ib]
r.update(n_sites_pool=len(pid), n_dmatch=int(dm.sum()), n_pairs=len(y), n_pos=int(y.sum()),
         n_pairs_D=int(dset.sum()), n_pos_D=int(y[dset].sum()))

# --- FINAL (own numpy), D = best sub-pocket U, pool = D-matched
seeds, av = final_seed_embeddings("pdbt", "U", pid)
avF = av & dm
sF = np.mean([pair_cos(E, ia, ib) for E in seeds], 0)
sF[~(avF[ia] & avF[ib])] = np.nan
# --- L4 stored embeddings (U), pool = D-matched
ids = pd.read_parquet(ROOT / "data/processed/descriptors/pdbt/a1r/ids.parquet").pocket_id
EL_all = np.load(ROOT / "data/processed/l4_emb/egnn_small/emb_pdbt_U.npy")
rr = pd.Series(np.arange(len(ids)), index=ids.to_numpy()).reindex(pid).to_numpy()
EL = np.zeros((len(pid), EL_all.shape[1]))
g = ~pd.isna(rr)
EL[g] = EL_all[rr[g].astype(int)]
avL = g & (np.linalg.norm(EL, axis=1) > 0) & dm
r["l4_norm_range"] = [float(np.linalg.norm(EL[avL], axis=1).min()), float(np.linalg.norm(EL[avL], axis=1).max())]
sL = pair_cos(EL, ia, ib)
sL[~(avL[ia] & avL[ib])] = np.nan
rows = np.where(avL)[0]
Sm = EL[rows] @ EL[rows].T
np.fill_diagonal(Sm, -np.inf)
rad = np.full(len(pid), np.nan)
rad[rows] = np.sort(Sm, 1)[:, -10:].mean(1)
sLc = sL - 0.5 * (rad[ia] + rad[ib])
# --- FUSION: 0.5 z(cos FINAL) + 0.5 z(cos L4); z fitted on BLiPS-train v2 pairs (refit here, L + D-matched D pooled)
tp = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
bs = sorted(set(tp.site_a) | set(tp.site_b))
bpos = {p: i for i, p in enumerate(bs)}
ja, jb = tp.site_a.map(bpos).to_numpy(), tp.site_b.map(bpos).to_numpy()
bix = pd.read_parquet(ROOT / "data/processed/cache/points/blips/index.parquet").set_index("pocket_id").reindex(bs)
bok = (bix.status == "ok").to_numpy()
bdm = bok & ((bix.d_coverage.to_numpy(float) >= 0.3) | (bix.d_precision.to_numpy(float) >= 0.5))
bids = pd.read_parquet(ROOT / "data/processed/descriptors/blips/a1r/ids.parquet").pocket_id
cA, cL = [], []
for loc, pool in (("L", bok), ("U", bdm)):
    se, a_ = final_seed_embeddings("blips", loc, bs)
    s1 = np.mean([pair_cos(E, ja, jb) for E in se], 0)
    M = np.load(ROOT / f"data/processed/l4_emb/egnn_small/emb_blips_{loc}.npy")
    q = pd.Series(np.arange(len(bids)), index=bids.to_numpy()).reindex(bs).to_numpy()
    E2 = np.zeros((len(bs), M.shape[1]))
    gg = ~pd.isna(q)
    E2[gg] = M[q[gg].astype(int)]
    a2 = gg & (np.linalg.norm(E2, axis=1) > 0)
    s2 = pair_cos(E2, ja, jb)
    m = (a_ & pool & a2)[ja] & (a_ & pool & a2)[jb]
    cA.append(s1[m]); cL.append(s2[m])
cA, cL = np.concatenate(cA), np.concatenate(cL)
sc = {"mu_A": cA.mean(), "sd_A": cA.std(), "mu_L": cL.mean(), "sd_L": cL.std(), "n": len(cA)}
stored = json.load(open(ROOT / "results/exploratory/fusion/fusion_scales.json"))
r["fusion_scales_refit"] = sc
r["fusion_scales_max_abs_diff"] = max(abs(sc[k] - stored[k]) for k in ("mu_A", "sd_A", "mu_L", "sd_L"))
sFu = 0.5 * (sF - stored["mu_A"]) / stored["sd_A"] + 0.5 * (sL - stored["mu_L"]) / stored["sd_L"]
# --- B1: pool (D-matched) z-scored cosine
sB1 = pair_cos(zcos_embed(desc_matrix("pdbt", "b1_default_D", pid), dm), ia, ib)

rep = json.load(open(ROOT / "results/pdbt/claims.json"))["claims"]
claims = {}
for cid, sa, sb in (("R1", sF, sB1), ("R2", sFu, sF), ("R3", sLc, sF)):
    m = dset & np.isfinite(sa) & np.isfinite(sb)
    q = boot_paired(y[m], sa[m], sb[m], unit[ia][m], unit[ib][m], B=2000, seed=31337)
    q.pop("boot")
    q["n_pairs"], q["n_pos"] = int(m.sum()), int(y[m].sum())
    q["reported"] = {k: rep[cid][k] for k in ("auc_a", "auc_b", "delta", "ci_low", "ci_high", "p_one_sided",
                                              "p_holm", "n_pairs", "n_pos", "n_units")}
    q["max_abs_point_diff"] = max(abs(q["auc_a"] - rep[cid]["auc_a"]), abs(q["auc_b"] - rep[cid]["auc_b"]))
    claims[cid] = q
ps = {c: claims[c]["p"] for c in claims}
order = sorted(ps, key=ps.get)
run = 0
for k, c in enumerate(order):
    run = max(run, min(1.0, (len(order) - k) * ps[c]))
    claims[c]["p_holm"], claims[c]["reject"] = run, run <= 0.05
r["claims"] = claims

# --- PDB-T site ids / PDB chains in training tables
tabs = {"blips_sites_v2": pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet").site_id,
        "blips_train_pairs_v2": pd.concat([tp.site_a, tp.site_b]),
        "blips_val_pairs_v2": pd.concat([pd.read_parquet(ROOT / "data/splits/blips_val_pairs_v2.parquet")[c]
                                         for c in ("site_a", "site_b")]),
        "ppips_pockets": pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet").pocket_id,
        "tough_m1_pockets_split": pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet").pocket_id,
        "tough_m1_dev_pairs": pd.concat([pd.read_parquet(ROOT / "data/splits/tough_m1_dev_pairs.parquet")[c]
                                         for c in ("pocket_a", "pocket_b")])}
allsite = set(S.site_id)
r["pdbt_ids_in_training_tables"] = {k: int(v.isin(allsite).sum()) for k, v in tabs.items()}
bl = pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet")
nodes = pd.read_parquet(ROOT / "data/splits/homology_nodes.parquet", columns=["dataset", "pdb_id", "chain", "sid"])
tr_nodes = nodes[nodes.dataset.isin(["burrow_train", "burrow_dev", "burrow_partner"])]
key = set(zip(S.pdb_id.str.lower(), S.chain))
r["pdbt_pdbchain_in_blips_v2"] = len(key & set(zip(bl.pdb_id.str.lower(), bl.chain)))
r["pdbt_pdbchain_in_burrow_nodes"] = len(key & set(zip(tr_nodes.pdb_id.dropna().str.lower(), tr_nodes.chain)))
r["pdbt_pdb_in_burrow_or_blips"] = len(set(S.pdb_id.str.lower()) & (set(bl.pdb_id.str.lower())
                                                                   | set(tr_nodes.pdb_id.dropna().str.lower())))
r["pdbt_sid_in_training_sids"] = len(set(S.sid) & (set(bl.sid) | set(tr_nodes.sid)))
r["min_release_date"] = str(S.release_date.min())
json.dump(r, open(ROOT / "results/verify/v_pdbt.json", "w"), indent=1, default=float)
print(json.dumps(r, indent=1, default=float))
