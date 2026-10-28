"""Spot checks: Vertex FINAL-L AUC, BLiPS-test FINAL-L AUC, PPIPS-test FINAL P-ortho MRR, TOUGH-M1 full-minus-dev
B0 (+ shipped fpocket / ligand-size variants).  Verifier code."""
import json
import re
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify")
from vlib import ROOT, final_scores, final_seed_embeddings, read_sealed  # noqa

summ = pd.read_parquet(ROOT / "results/final/final_summary.parquet")
FIN = "pocketcompare-final:A4b:n1_linear|raw"


def rep(set_, arm="FINAL", cfg=FIN, var="raw", mode="L", sub="all", col="auc"):
    r = summ[(summ.set == set_) & (summ.arm == arm) & (summ.config == cfg) & (summ.variant == var)
             & (summ["mode"] == mode) & (summ.subset == sub)]
    return [float(r[col].iloc[0]), int(r.n_pairs.iloc[0])] if len(r) else None


def okmask(ds, pid):
    ix = pd.read_parquet(ROOT / f"data/processed/cache/points/{ds}/index.parquet").set_index("pocket_id").reindex(pid)
    return (ix.status == "ok").to_numpy(), ix


out = {}
# ------------------------------------------------------------------ Vertex
vp, _ = read_sealed("vertex_pairs.parquet", "verify spot check Vertex AUC (verifier)")
pid = sorted(set(vp.pocket_a) | set(vp.pocket_b))
pos = {p: i for i, p in enumerate(pid)}
ia, ib = vp.pocket_a.map(pos).to_numpy(), vp.pocket_b.map(pos).to_numpy()
ok, _ = okmask("vertex", pid)
s = final_scores("vertex", "L", pid, ok, ia, ib)
g = pd.DataFrame({"pp": vp.protein_pair.to_numpy(), "s": s, "y": vp.label.astype(int).to_numpy()}).groupby("pp")
agg = pd.DataFrame({"s": g.s.max(), "y": g.y.max(), "ymin": g.y.min()})
m = agg.s.notna()
out["vertex"] = {"n_protein_pairs": int(len(agg)), "n_scored": int(m.sum()), "n_pos": int(agg.y[m].sum()),
                 "label_conflicts": int((agg.y != agg.ymin).sum()),
                 "auc_final_L": float(roc_auc_score(agg.y[m], agg.s[m])), "reported": rep("vertex")}

# ------------------------------------------------------------------ BLiPS-test (holo, L)
bp, _ = read_sealed("blips_test_pairs.parquet", "verify spot check BLiPS-test AUC (verifier)")
bs, _ = read_sealed("blips_test_sites.parquet", "verify spot check BLiPS-test AUC (verifier)")
exc = pd.read_parquet(ROOT / "data/splits/blips_test_exclusions_v2.parquet")
exs = set(exc.site_id[exc.excluded])
S = sorted(set(bs.site_id) - exs)
bp = bp[bp.site_a.isin(S) & bp.site_b.isin(S)].reset_index(drop=True)
pos = {p: i for i, p in enumerate(S)}
ia, ib = bp.site_a.map(pos).to_numpy(), bp.site_b.map(pos).to_numpy()
ok, _ = okmask("blips_test_holo", S)
s = final_scores("blips_test_holo", "L", S, ok, ia, ib)
y = bp.label.astype(int).to_numpy()
m = np.isfinite(s)
out["blips_test"] = {"n_sites": len(S), "n_excluded": len(exs), "n_pairs": int(m.sum()), "n_pos": int(y[m].sum()),
                     "auc_final_L": float(roc_auc_score(y[m], s[m])), "reported": rep("blips_test")}

# ------------------------------------------------------------------ PPIPS-test P-ortho MRR (FINAL raw, D)
Q, _ = read_sealed("ppips_test_queries.parquet", "verify spot check PPIPS-test MRR (verifier)")
P = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
ref = P.split.isin(["train", "test"]).to_numpy()
seeds, avail = final_seed_embeddings("ppips", "D", P.pocket_id[ref].tolist())
E = np.full((len(P), 384), np.nan)
E[ref] = np.concatenate(seeds, 1) / np.sqrt(3)
pidx = {p: i for i, p in enumerate(P.pocket_id)}
members = P.groupby("complex").indices
rr_opt, rr_pes, top1 = [], [], []
for r in Q.itertuples():
    cand = members[r.partner_complex]
    q = E[pidx[r.query]]
    sc = E[cand] @ q
    lab = np.isin(P.pocket_id.to_numpy()[cand], list(r.positives))
    best = sc[lab].max()
    rk_o = 1 + (sc[~lab] > best).sum()
    rk_p = 1 + (sc[~lab] >= best).sum()
    rr_opt.append(1 / rk_o)
    rr_pes.append(1 / rk_p)
    top1.append(rk_o == 1)
pr = pd.read_parquet(ROOT / "results/final/final_ppips.parquet")
prow = pr[(pr.arm == "FINAL") & (pr.variant == "raw")]
out["ppips_test"] = {"n_queries": len(Q), "mrr_final_raw": float(np.mean(rr_opt)), "mrr_ties_pessimistic": float(np.mean(rr_pes)),
                     "top1": float(np.mean(top1)), "reported_mrr": float(prow.ortho_mrr.iloc[0]),
                     "reported_top1": float(prow.ortho_top1.iloc[0])}

# ------------------------------------------------------------------ TOUGH-M1 full minus dev: B0 variants
full, _ = read_sealed("tough_m1_pairs.parquet", "verify B0 on TOUGH-M1 full-minus-dev (verifier)")
split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
dev = set(split.pocket_id[split.partition == "dev"])
full = full[~full.pocket_a.isin(dev) & ~full.pocket_b.isin(dev)].reset_index(drop=True)
pid = sorted(split.pocket_id[split.partition != "dev"])
pos = {p: i for i, p in enumerate(pid)}
ia, ib = full.pocket_a.map(pos).to_numpy(), full.pocket_b.map(pos).to_numpy()
y = full.label.astype(int).to_numpy()
ok, ix = okmask("tough_m1", pid)
dm = ok & ((ix.d_coverage.to_numpy(float) >= 0.3) | (ix.d_precision.to_numpy(float) >= 0.5))
pl = pd.read_csv(ROOT / "data/raw/tough_m1/downloads/TOUGH-M1_pocket.list", sep=r"\s+", header=None,
                 names=["name", "idx", "mcc"], dtype={"name": str}).set_index("name")
fv, fr = [], []
for p in pid:
    nm = p.split(":")[1]
    k = int(pl.idx[nm])
    txt = (ROOT / f"data/raw/tough_m1/extracted/TOUGH-M1_dataset/{nm}/{nm}.fpocket").read_text(errors="replace")
    blk = re.search(rf"^Pocket {k} :(.*?)(?=^Pocket \d+ :|\Z)", txt, re.S | re.M).group(1)
    fv.append(float(re.search(r"Volume :\s+([\d.]+)", blk).group(1)))
    fr.append(float(len(re.search(rf"^POCKET {k} (.*)$", txt, re.M).group(1).split())))
V = {"L_shell_volume": ix.volume_A3.to_numpy(float), "D_volume": ix.d_volume_A3.to_numpy(float),
     "residue_list_points_volume": ix.alt_volume_A3.to_numpy(float), "fpocket_volume_shipped": np.array(fv),
     "fpocket_n_residues_shipped": np.array(fr), "ligand_heavy_atoms": ix.n_ligand_atoms.to_numpy(float)}
b0 = {"n_pairs": len(y), "n_pos": int(y.sum())}
for k, v in V.items():
    lv = np.log(np.clip(v, 1, None))
    sc = -np.abs(lv[ia] - lv[ib])
    mm = np.isfinite(sc) & ((dm[ia] & dm[ib]) if k == "D_volume" else True)
    b0[k] = [float(roc_auc_score(y[mm], sc[mm])), int(mm.sum())]
b0["reported_B0_L"] = rep("tough_m1_full_minus_dev", "B0", "default")
# published-method comparison inside the same file: shipped TM-score / seq identity columns
b0["tm_score_auc"] = float(roc_auc_score(y, full.tm_score.to_numpy(float)))
out["tough_full_minus_dev_B0"] = b0
json.dump(out, open(ROOT / "results/verify/v_spot.json", "w"), indent=1, default=float)
print(json.dumps(out, indent=1, default=float))
