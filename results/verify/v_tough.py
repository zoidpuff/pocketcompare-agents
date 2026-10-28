"""Independent re-derivation of C1a / C1b / C1-D, B0 (+ shipped-pocket size variants), shuffled control."""
import json
import os
import re
import sys

os.environ.setdefault("OMP_NUM_THREADS", "16")
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify")
from vlib import ROOT, boot_paired, components_from_labels, l2n, pair_cos, read_sealed, zcos_embed  # noqa

OUT = ROOT / "results/verify"
res = {}

pairs, h = read_sealed("tough_m1_test_pairs.parquet", "verify C1a/C1b/C1-D/B0 (independent verifier)")
res["pairs_sha256"] = h
res["pair_columns"] = list(pairs.columns)
split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
P = split[split.partition == "test"].sort_values("pocket_id").reset_index(drop=True)
pos = {p: i for i, p in enumerate(P.pocket_id)}
assert pairs.pocket_a.isin(pos).all() and pairs.pocket_b.isin(pos).all()
ia, ib = pairs.pocket_a.map(pos).to_numpy(), pairs.pocket_b.map(pos).to_numpy()
y = pairs.label.to_numpy().astype(int)
res["n_pool_pockets"] = len(P)
res["n_pockets_in_pairs"] = int(len(set(ia) | set(ib)))
res["n_pairs"], res["n_pos"], res["n_neg"] = len(y), int(y.sum()), int((1 - y).sum())
res["n_self_pairs"] = int((ia == ib).sum())
res["n_dup_pairs"] = int(pd.DataFrame({"a": np.minimum(ia, ib), "b": np.maximum(ia, ib)}).duplicated().sum())

# units: components of (ligand cluster U homology group) over the test pool
unit = components_from_labels(P.ligand_cluster.to_numpy(), P.group_id.to_numpy())
res["n_units_pool"] = int(unit.max() + 1)
res["n_units_in_pairs"] = int(len(np.unique(np.concatenate([unit[ia], unit[ib]]))))
ua, ub = unit[ia], unit[ib]

ix = pd.read_parquet(ROOT / "data/processed/cache/points/tough_m1/index.parquet").set_index("pocket_id").reindex(P.pocket_id)
ok = (ix.status == "ok").to_numpy()
dmatch = ok & ((ix.d_coverage.to_numpy(float) >= 0.3) | (ix.d_precision.to_numpy(float) >= 0.5))
dset = dmatch[ia] & dmatch[ib]
res["cache_ok_all"] = bool(ok.all())
res["n_dmatch_pockets"] = int(dmatch.sum())
res["n_D_common_pairs"], res["n_D_common_pos"] = int(dset.sum()), int(y[dset].sum())

# ---------------- final method: own numpy implementation from stored part descriptors + weights
stats = json.load(open(ROOT / "results/models/a4b/n1_linear/input_stats.json"))
heads = [dict(np.load(ROOT / f"results/models/a4b/n1_linear/seed{s}.npz")) for s in (0, 1, 2)]
ids = pd.read_parquet(ROOT / "data/processed/descriptors/tough_m1/defrob/ids.parquet")
row = pd.Series(np.arange(len(ids)), index=ids.pocket_id).loc[P.pocket_id].to_numpy()


def parts(loc):
    sph = np.load(ROOT / f"data/processed/descriptors/tough_m1/defrob/{loc}_sph8.npz")
    base = np.load(ROOT / f"data/processed/descriptors/tough_m1/defrob/{loc}_base.npz")
    out = []
    for src in ("a1", "env"):
        M = sph[src][row].astype(np.float64)
        B = base[src][row].astype(np.float64)
        fb = ~np.isfinite(M).any(1) & np.isfinite(B).any(1)
        M[fb] = B[fb]
        out.append(M)
    return out


def my_embed(mats):
    Z = []
    for k, M in enumerate(mats):
        mu, sd = np.asarray(stats["mean"][k]), np.asarray(stats["std"][k])
        z = np.zeros_like(M)
        g = sd > 0
        z[:, g] = (M[:, g] - mu[g]) / sd[g]
        Z.append(np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0))
    X = np.clip(np.concatenate(Z, 1), -5, 5)
    per_seed = [l2n(X @ hd["w2"].astype(np.float64).T + hd["b2"].astype(np.float64)) for hd in heads]
    avail = np.ones(len(X), bool)
    for M in mats:
        avail &= np.isfinite(M).any(1)
    return per_seed, avail


scores = {}
for mode, loc, pool in (("L", "L", ok), ("D", "U", dmatch)):
    mats = parts(loc)
    per_seed, avail = my_embed(mats)
    av = avail & pool
    s = np.mean([pair_cos(E, ia, ib) for E in per_seed], 0)          # mean of 3 per-seed 128-d cosines
    s[~(av[ia] & av[ib])] = np.nan
    scores[f"FINAL_{mode}"] = s
    # method API (what final_eval used): Method.embed on pocketcompare.a4b.raw_parts
    sys.path.insert(0, str(ROOT / "src"))
    from pocketcompare import a4b as A4
    from pocketcompare.method import Method
    m = Method()
    E_api = m.embed(A4.raw_parts("tough_m1", mode, P.pocket_id.tolist(), "N1")).astype(np.float32)
    s_api = np.einsum("nd,nd->n", E_api[ia], E_api[ib]).astype(np.float32)
    mm = np.isfinite(s)
    res[f"final_{mode}_max_abs_diff_own_vs_api"] = float(np.max(np.abs(s[mm] - s_api[mm])))
    res[f"final_{mode}_api_dims"] = int(E_api.shape[1])
    scores[f"FINAL_{mode}_api32"] = np.where(mm, s_api, np.nan)

# ---------------- B1 / B4: z-score on pool, cosine
for arm, stem, idsf, z in (("B1", "b1_default", None, True), ("B4", "b4_esm2", "b4_esm2_ids.parquet", True),
                           ("B4noz", "b4_esm2", "b4_esm2_ids.parquet", False)):
    for mode, pool in (("L", ok), ("D", dmatch)):
        A = np.load(ROOT / f"data/processed/descriptors/tough_m1/{stem}_{mode}.npy")
        idp = ROOT / f"data/processed/descriptors/tough_m1/{idsf or f'{stem}_{mode}.ids.parquet'}"
        ii = pd.read_parquet(idp, columns=["pocket_id"]).pocket_id
        r = pd.Series(np.arange(len(ii)), index=ii.to_numpy()).reindex(P.pocket_id).to_numpy()
        M = np.full((len(P), A.shape[1]), np.nan)
        g = ~pd.isna(r)
        M[g] = A[r[g].astype(int)]
        if z:
            E = zcos_embed(M, pool)
        else:
            av = pool & np.isfinite(M).all(1)
            E = np.full(M.shape, np.nan)
            E[av] = l2n(M[av])
        scores[f"{arm}_{mode}"] = pair_cos(E, ia, ib)

# ---------------- AUCs vs reported
summ = pd.read_parquet(ROOT / "results/final/final_summary.parquet")
summ = summ[(summ.set == "tough_m1_test") & (summ.subset == "all")]


def rep(arm, cfg, var, mode):
    r = summ[(summ.arm == arm) & (summ.config == cfg) & (summ.variant == var) & (summ["mode"] == mode)]
    return float(r.auc.iloc[0]) if len(r) else None


aucs = {}
fin = "pocketcompare-final:A4b:n1_linear|raw"
for key, (arm, cfg, mode) in {"FINAL_L": ("FINAL", fin, "L"), "FINAL_D": ("FINAL", fin, "D"),
                               "B1_L": ("B1", "default", "L"), "B1_D": ("B1", "default", "D"),
                               "B4_L": ("B4", "esm2", "L"), "B4_D": ("B4", "esm2", "D"),
                               "B4noz_L": ("B4", "esm2_noz", "L")}.items():
    s = scores[key]
    m = np.isfinite(s) & (dset if mode == "D" else True)
    a = roc_auc_score(y[m], s[m])
    a32 = roc_auc_score(y[m], s[m].astype(np.float32))
    aucs[key] = {"n": int(m.sum()), "auc": a, "auc_float32": a32, "reported": rep(arm, cfg, "raw", mode)}
for mode in ("L", "D"):
    s = scores[f"FINAL_{mode}_api32"]
    m = np.isfinite(s) & (dset if mode == "D" else True)
    aucs[f"FINAL_{mode}_api32"] = {"n": int(m.sum()), "auc": roc_auc_score(y[m], s[m])}

# ---------------- B0 size baselines
lvL = np.log(np.clip(ix.volume_A3.to_numpy(float), 1, None))
lvD = np.log(np.clip(ix.d_volume_A3.to_numpy(float), 1, None))
lvAlt = np.log(np.clip(ix.alt_volume_A3.to_numpy(float), 1, None))
nlig = np.log(ix.n_ligand_atoms.to_numpy(float))
nres = np.log(ix.n_lining_res.to_numpy(float).clip(1))

# shipped fpocket pocket (TOUGH-M1 benchmark definition): Volume, #alpha spheres, #residues
pl = pd.read_csv(ROOT / "data/raw/tough_m1/downloads/TOUGH-M1_pocket.list", sep=r"\s+", header=None,
                 names=["name", "idx", "mcc"], dtype={"name": str}).set_index("name")
fp_vol, fp_nas, fp_nres = [], [], []
for pid in P.pocket_id:
    nm = pid.split(":")[1]
    k = int(pl.idx[nm])
    txt = (ROOT / f"data/raw/tough_m1/extracted/TOUGH-M1_dataset/{nm}/{nm}.fpocket").read_text(errors="replace")
    blk = re.search(rf"^Pocket {k} :(.*?)(?=^Pocket \d+ :|\Z)", txt, re.S | re.M).group(1)
    fp_vol.append(float(re.search(r"Volume :\s+([\d.]+)", blk).group(1)))
    fp_nas.append(float(re.search(r"Number of Alpha Spheres :\s+([\d.]+)", blk).group(1)))
    resl = re.search(rf"^POCKET {k} (.*)$", txt, re.M).group(1).split()
    fp_nres.append(float(len(resl)))
fp_vol, fp_nas, fp_nres = map(lambda v: np.log(np.asarray(v)), (fp_vol, fp_nas, fp_nres))


def b0(v, mask=None):
    s = -np.abs(v[ia] - v[ib])
    m = np.isfinite(s) if mask is None else (np.isfinite(s) & mask)
    return {"n": int(m.sum()), "auc": roc_auc_score(y[m], s[m])}


b0res = {"B0_L_volume(4A ligand shell)": b0(lvL), "B0_L_volume_reported": rep("B0", "default", "raw", "L"),
         "B0_D_volume(common D set)": b0(lvD, dset), "B0_D_reported": rep("B0", "default", "raw", "D"),
         "B0_D_volume(all pairs, D-volume even if unmatched)": b0(lvD),
         "B0_L_volume_on_D_common_set": b0(lvL, dset),
         "B0_alt_residue_list_points_volume": b0(lvAlt),
         "B0_L_n_lining_residues": b0(nres),
         "B0_ligand_heavy_atoms": b0(nlig),
         "B0_fpocket_shipped_volume": b0(fp_vol),
         "B0_fpocket_shipped_n_alpha_spheres": b0(fp_nas),
         "B0_fpocket_shipped_n_residues": b0(fp_nres)}
corr = pd.DataFrame({"L_vol": lvL, "D_vol": lvD, "alt_vol": lvAlt, "lig_atoms": nlig, "fp_vol": fp_vol,
                     "fp_nres": fp_nres}).corr(method="spearman")
b0res["spearman_per_pocket"] = corr.round(3).to_dict()
# positives vs negatives: ligand-size difference
b0res["median_abs_dlog_ligatoms_pos_neg"] = [float(np.median(np.abs(nlig[ia] - nlig[ib])[y == 1])),
                                             float(np.median(np.abs(nlig[ia] - nlig[ib])[y == 0]))]
res["b0"] = b0res

# ---------------- shuffled labels
rng = np.random.default_rng(7)
ysh = rng.permutation(y)
res["shuffled_label_auc_final_L"] = float(roc_auc_score(ysh, scores["FINAL_L"]))
res["aucs"] = aucs

# ---------------- claims bootstrap
B = 2000
claims = {}
for cid, a, b, mask in (("C1a", "FINAL_L", "B1_L", None), ("C1b", "FINAL_L", "B4_L", None),
                        ("C1-D", "FINAL_D", "B1_D", dset)):
    sa, sb = scores[a], scores[b]
    m = np.isfinite(sa) & np.isfinite(sb)
    if mask is not None:
        m &= mask
    r = boot_paired(y[m], sa[m], sb[m], ua[m], ub[m], B=B, seed=20261028)
    r.pop("boot")
    r["n_pairs"] = int(m.sum())
    claims[cid] = r
res["claims"] = claims
json.dump(res, open(OUT / "v_tough.json", "w"), indent=1, default=float)
print(json.dumps(res, indent=1, default=float))

# save pair-level arrays (scratchpad only) for the Monte-Carlo-error study
SCR = os.environ.get("VERIFY_SCRATCH")
if SCR:
    np.savez(os.path.join(SCR, "tough_scores.npz"), y=y, ua=ua, ub=ub, dset=dset,
             **{k: v for k, v in scores.items()})
