#!/usr/bin/env python
"""EXPLORATORY (post-test) — PPI-R: ligand-grounded PPI-modulator-pocket retrieval (proposed in D7).

PROTOCOL (declared 2026-10-28 ~06:20, before any similarity score was computed; nothing below was changed after
seeing scores — any later addition is marked "ADDED AFTER SCORES")
---------------------------------------------------------------------------------------------------------------
Question: does a pocket fingerprint recognise "PPI-modulator-pocket-ness" across protein families, i.e. do the
neighbours of a PPI-modulator pocket from OTHER homology groups tend to be PPI-modulator pockets rather than
ordinary (non-PPI) ligand pockets of the same size and buriedness?

Positives / queries (P): PPI-L primary pockets (data/splits/ppi_l_pockets.parquet; Pasteur pocketome, PLOC +
  PLONC, L mode = 4 Å shell of the modulator) with split in {train, val} and an L-mode descriptor (a1r has_L).
  PPI-L test pockets are dropped on load; data/sealed/ is never opened (no pair table is read at all).
Background (N): BLiPS v2 sites (data/splits/blips_sites_v2.parquet) with partition in {train, val}, L mode
  (ligand shell), L-mode descriptor available, and NO direct homology edge to ANY PPI-L chain (all PPI-L
  splits; global graph data/splits/homology_edges.parquet: MMseqs2 leakage rule OR Foldseek min-TM >= 0.5, plus
  identical sequences).  BLiPS sites are non-PPI ligand pockets by construction (not in the PPI-L pocketome);
  the homology exclusion also removes PPI-L targets' own non-modulator sites.
Matching rule (declared before scoring): covariates x = (log L-mode volume_A3, mean bur16 over the L-mode points),
  standardised with the mean / SD of P.  Greedy 1:1 nearest-neighbour matching WITHOUT replacement: P pockets in a
  seeded random order (SEEDS[0]); each takes the nearest unused background pocket (Euclidean on standardised x)
  if within a caliper of 0.25 (SD units); otherwise it stays unmatched (it is still a query and a positive).
  Balance reported as standardised mean differences (SMD) before / after; target |SMD| < 0.1.
Retrieval: for each query q in P, candidates = (P minus q minus every P pocket in q's PPI-L homology group
  [ppi_l_pockets.group]) ∪ matched N.  Label = candidate is in P.  Per-query metrics: ROC-AUC
  (evaluate.roc_auc), AP (evaluate.average_precision), precision@10, precision@50; chance = per-query prevalence.
  Summary = mean over queries (primary) and group-balanced mean (each PPI-L homology group weight 1; secondary).
CIs: homology-group bootstrap of the query mean with pocketcompare.evaluate.vertex_bootstrap_generic (units =
  the query's PPI-L group; B = 2000; seed 0); paired differences FINAL − X with the same replicates.
Arms (all L mode, raw inner product / cosine, no CSLS):
  FINAL = A4b:n1_linear (pocketcompare.method.Method().embed on the stored N1 parts, a1r L_sph8),
  N1    = non-learned A1(sph8)+env(sph8), BLiPS-train part statistics (a4b.embed_nonlearned),
  B1    = b1_default_L, z-scored over the evaluated pool (P ∪ matched N), cosine,
  B4    = ESM-2 650M mean over lining residues (SEQUENCE-based), z-scored over the pool, cosine
          (PPI-L: scripts/exploratory/ppi_r_esm.py, same recipe as compute_esm.py),
  controls: B0 = −|Δ log V_L| and BUR = −|Δ mean bur16| (should be ≈ 0.5 after matching), RANDOM.
Caveats declared up front: P and N come from different curation pipelines (Pasteur pocketome vs BioLiP); PPI-L has
  few, very large homology groups (bromodomains etc.), so the effective sample is ~67 query groups; this is a
  descriptive, exploratory analysis with no claim and no multiplicity control.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare import a4b as A4  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare import pockets as pk  # noqa: E402
from pocketcompare.descstore import DescriptorStore  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402
from pocketcompare.similarity import ZScorer, embed  # noqa: E402

OUT = ROOT / "results/exploratory/ppi_r"
DATA = ROOT / "data/processed/exploratory/ppi_r"
CALIPER = 0.25
B = 2000
KS = (10, 50)


def log(*a):
    print(*a, flush=True)


# ============================================================================================ pools
def mean_bur16(cache_file, idx):
    z = np.load(ROOT / cache_file if not str(cache_file).startswith("/") else cache_file, allow_pickle=False)
    names = list(z["feature_names"])
    f = z["feats"][:, names.index("bur16")]
    return float(np.mean(f[np.asarray(idx, np.int64)]))


def ppil_pool():
    P = pd.read_parquet(ROOT / "data/splits/ppi_l_pockets.parquet")
    P = P[P.split.isin(["train", "val"])].copy()           # test pockets never used
    ids = A4.ids_table("ppi_l").set_index("pocket_id")
    P = P[P.pocket_id.map(ids.has_L).fillna(False).astype(bool)]
    idx = pd.read_parquet(ROOT / "data/processed/cache/points/ppi_l/index.parquet",
                          columns=["pocket_id", "cache_file", "lmode_idx"]).set_index("pocket_id")
    P = P.join(idx[["lmode_idx"]], on="pocket_id")
    P["bur16"] = [mean_bur16(c, i) for c, i in zip(P.cache_file, P.lmode_idx)]
    return pd.DataFrame({"pocket_id": P.pocket_id, "set": "PPI", "dataset": "ppi_l", "group": "ppil:" + P.group,
                         "uniprot": P.uniprot, "label": P.label, "lig": P.lig, "volume_A3": P.volume_A3,
                         "bur16": P.bur16, "split": P.split}).reset_index(drop=True)


def blips_pool():
    S = pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet")
    S = S[S.partition.isin(["train", "val"])].copy()
    ids = A4.ids_table("blips").set_index("pocket_id")
    S = S[S.site_id.map(ids.has_L).fillna(False).astype(bool)]
    idx = pd.read_parquet(ROOT / "data/processed/cache/points/blips/index.parquet",
                          columns=["pocket_id", "cache_file", "lmode_idx", "volume_A3", "status"]).set_index("pocket_id")
    S = S.join(idx, on="site_id")
    S = S[S.status == "ok"]
    # homology exclusion: direct edge (or identical sequence) to ANY PPI-L chain
    nodes = pd.read_parquet(ROOT / "data/splits/homology_nodes.parquet", columns=["node_id", "dataset", "sid"])
    ppil_sids = set(nodes.sid[nodes.dataset == "ppi_l"])
    E = pd.read_parquet(ROOT / "data/splits/homology_edges.parquet", columns=["sid_a", "sid_b", "seq_edge", "fs_edge"])
    E = E[E.seq_edge | E.fs_edge]
    a_in, b_in = E.sid_a.isin(ppil_sids), E.sid_b.isin(ppil_sids)
    touch = ppil_sids | set(E.sid_b[a_in]) | set(E.sid_a[b_in])
    sid = S.node_id.map(nodes.set_index("node_id").sid)
    n0 = len(S)
    S["hom_ppil"] = sid.isin(touch).to_numpy() | sid.isna().to_numpy()
    excl = int(S.hom_ppil.sum())
    S = S[~S.hom_ppil]
    S["bur16"] = [mean_bur16(c, i) for c, i in zip(S.cache_file, S.lmode_idx)]
    out = pd.DataFrame({"pocket_id": S.site_id, "set": "BG", "dataset": "blips", "group": S.group_id,
                        "uniprot": S.uniprot, "label": "BG", "lig": S.label_ccd, "volume_A3": S.volume_A3,
                        "bur16": S.bur16, "split": S.partition}).reset_index(drop=True)
    return out, {"blips_trainval_L_ok": n0, "excluded_homologous_to_ppil": excl, "pool": len(out)}


def match(P, N, seed=SEEDS[0]):
    X = lambda d: np.column_stack([np.log(d.volume_A3.to_numpy()), d.bur16.to_numpy()])  # noqa: E731
    xp, xn = X(P), X(N)
    mu, sd = xp.mean(0), xp.std(0)
    zp, zn = (xp - mu) / sd, (xn - mu) / sd
    used = np.zeros(len(N), bool)
    mate = np.full(len(P), -1)
    for i in np.random.default_rng(seed).permutation(len(P)):
        d = np.sqrt(((zn - zp[i]) ** 2).sum(1))
        d[used] = np.inf
        j = int(np.argmin(d))
        if d[j] <= CALIPER:
            used[j] = True
            mate[i] = j

    def smd(a, b):
        return [float((a[:, k].mean() - b[:, k].mean()) / np.sqrt(0.5 * (a[:, k].var() + b[:, k].var())))
                for k in range(a.shape[1])]
    bal = {"covariates": ["log_volume_A3_L", "mean_bur16_L"], "caliper_sd": CALIPER,
           "n_ppi": len(P), "n_pool": len(N), "n_matched": int(used.sum()),
           "smd_before": smd(xp, xn), "smd_after": smd(xp, xn[used]),
           "smd_after_matched_ppi_only": smd(xp[mate >= 0], xn[used]),
           "median_volume_ppi_bg_pool_bg_matched": [float(np.median(P.volume_A3)), float(np.median(N.volume_A3)),
                                                    float(np.median(N.volume_A3[used]))],
           "median_bur16_ppi_bg_pool_bg_matched": [float(np.median(P.bur16)), float(np.median(N.bur16)),
                                                   float(np.median(N.bur16[used]))]}
    return used, mate, bal


# ============================================================================================ embeddings
def embeddings(T):
    """{arm: (n, d) unit vectors (rows NaN if missing)} for the evaluated pool T (rows: ppi_l then blips)."""
    from pocketcompare.method import Method
    m = Method()
    store = DescriptorStore(ROOT)
    out = {}
    parts = {"FINAL": None, "N1": None}
    mats_all = []
    for ds in ("ppi_l", "blips"):
        sub = T[T.dataset == ds]
        mats_all.append(A4.raw_parts(ds, "L", sub.pocket_id.tolist(), "N1"))
    mats = [np.vstack([mats_all[0][k], mats_all[1][k]]) for k in range(2)]
    ok = A4.available(mats)
    E = m.embed(mats).astype(np.float32)
    E[~ok] = np.nan
    out["FINAL"] = E
    En = A4.embed_nonlearned(mats, A4.blips_train_scaler("N1")).astype(np.float32)
    En[~ok] = np.nan
    out["N1"] = En
    # B1 (pool z-scored cosine)
    b1 = np.vstack([store.matrix("ppi_l", "b1_default_L", T.pocket_id[T.dataset == "ppi_l"]),
                    store.matrix("blips", "b1_default_L", T.pocket_id[T.dataset == "blips"])])
    # B4 ESM-2 (PPI-L: exploratory npz; BLiPS: stored)
    z = np.load(DATA / "b4_esm2_L_ppil.npz")
    pos = pd.Series(np.arange(len(z["pocket_id"])), index=z["pocket_id"])
    r = pos.reindex(T.pocket_id[T.dataset == "ppi_l"]).to_numpy()
    b4p = np.full((len(r), z["L"].shape[1]), np.nan)
    okr = ~pd.isna(r)
    b4p[okr] = z["L"][r[okr].astype(np.int64)]
    b4 = np.vstack([b4p, store.matrix("blips", "b4_esm2_L", T.pocket_id[T.dataset == "blips"])])
    for name, M in (("B1", b1), ("B4", b4)):
        av = np.isfinite(M).all(1)
        Er = embed(M[av], ZScorer.fit(M[av]))
        Eo = np.full((len(M), Er.shape[1]), np.nan, np.float32)
        Eo[av] = Er
        out[name] = Eo
    return out


# ============================================================================================ retrieval
def per_query(S, T, qrows, isP, grp):
    """Per-query metrics from a (n_q, n) score matrix (NaN = missing -> common set per arm handled by caller)."""
    rec = []
    for qi, q in enumerate(qrows):
        cand = np.ones(len(T), bool)
        cand[q] = False
        cand &= ~(isP & (grp == grp[q]))
        s = S[qi, cand]
        y = isP[cand]
        fin = np.isfinite(s)
        s, y = s[fin], y[fin]
        o = np.argsort(-s, kind="stable")
        r = {"auc": ev.roc_auc(y, s), "ap": ev.average_precision(y, s)["ap"], "prev": float(y.mean()),
             "n_cand": int(len(y))}
        for k in KS:
            r[f"p@{k}"] = float(y[o[:k]].mean())
        rec.append(r)
    return pd.DataFrame(rec)


def score_matrix(arm, T, qrows, Emb, rng):
    if arm in Emb:
        E = Emb[arm]
        return E[qrows] @ E.T
    if arm == "B0":
        lv = np.log(T.volume_A3.to_numpy())
        return -np.abs(lv[qrows][:, None] - lv[None, :])
    if arm == "BUR":
        b = T.bur16.to_numpy()
        return -np.abs(b[qrows][:, None] - b[None, :])
    if arm == "RANDOM":
        return rng.random((len(qrows), len(T)))
    raise KeyError(arm)


def boot(stat_by_q, groups, w0, names, diff=False):
    def fn(w):
        ww = w * w0
        if ww.sum() <= 0:
            return np.full(stat_by_q.shape[1], np.nan)
        return (stat_by_q * ww[:, None]).sum(0) / ww.sum()
    res = ev.vertex_bootstrap_generic(fn, groups, groups, B=B, seed=0, names=names, diff=diff)
    return {r.name: {"estimate": r.estimate, "ci_low": r.ci_low, "ci_high": r.ci_high, "se": r.se,
                     **({"p_one_sided": r.p_value} if diff else {}), "n_units": r.n_clusters} for r in res}


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    P = ppil_pool()
    N, ninfo = blips_pool()
    used, mate, bal = match(P, N)
    bal.update(ninfo)
    log(json.dumps(bal, indent=1))
    T = pd.concat([P, N[used]], ignore_index=True)
    T.to_parquet(DATA / "ppi_r_pool.parquet", index=False)
    (OUT / "matching.json").write_text(json.dumps(bal, indent=1))
    # ------------------------------------------------------------------ scores (after the protocol + matching)
    Emb = embeddings(T)
    isP = (T.set == "PPI").to_numpy()
    grp = T.group.to_numpy()
    arms = ["FINAL", "N1", "B1", "B4", "B0", "BUR", "RANDOM"]
    avail = np.ones(len(T), bool)
    for a in ("FINAL", "N1", "B1", "B4"):
        avail &= np.isfinite(Emb[a]).all(1)
    log("common-set availability", int(avail.sum()), "/", len(T))
    for a in ("FINAL", "N1", "B1", "B4"):
        Emb[a][~avail] = np.nan          # common set: a pocket missing in any arm is dropped for all arms
    qrows = np.flatnonzero(isP & avail)
    rng = np.random.default_rng(SEEDS[0])
    PQ = {}
    for a in arms:
        S = score_matrix(a, T, qrows, Emb, rng)
        S[:, ~avail] = np.nan
        PQ[a] = per_query(S, T, qrows, isP, grp)
        log(a, PQ[a][["auc", "ap", "p@10", "p@50", "prev"]].mean().round(3).to_dict(), f"{time.time() - t0:.0f}s")
    qg = grp[qrows]
    cnt = pd.Series(qg).value_counts()
    w_gb = 1.0 / pd.Series(qg).map(cnt).to_numpy()
    mets = ["auc", "ap", "p@10", "p@50", "prev"]
    summary = {"protocol": "see scripts/exploratory/ppi_r.py docstring", "EXPLORATORY": True,
               "n_queries": int(len(qrows)), "n_query_groups": int(len(cnt)), "n_pool": int(avail.sum()),
               "n_ppi": int((isP & avail).sum()), "n_bg": int((~isP & avail).sum()), "B": B, "arms": {}, "paired": {}}
    for wname, w0 in (("query_mean", np.ones(len(qrows))), ("group_balanced", w_gb)):
        for a in arms:
            summary["arms"].setdefault(a, {})[wname] = boot(PQ[a][mets].to_numpy(), qg, w0, mets)
        for a in ("N1", "B1", "B4", "B0"):
            D = PQ["FINAL"][mets[:4]].to_numpy() - PQ[a][mets[:4]].to_numpy()
            summary["paired"].setdefault(f"FINAL-{a}", {})[wname] = boot(D, qg, w0, mets[:4], diff=True)
    # per PPI-L group (FINAL vs B1), descriptive
    rows = []
    for g_, ix in pd.Series(np.arange(len(qrows))).groupby(qg):
        rows.append({"group": g_, "n_queries": len(ix), **{f"{a}_{m}": PQ[a][m].iloc[ix.to_numpy()].mean()
                                                            for a in ("FINAL", "B1", "B4") for m in ("auc", "p@10")}})
    pg = pd.DataFrame(rows).sort_values("n_queries", ascending=False)
    gname = T.drop_duplicates("group").set_index("group")
    pg.to_csv(OUT / "per_group.tsv", sep="\t", index=False, float_format="%.3f")
    # by label (PLOC / PLONC), FINAL
    lab = T.label.to_numpy()[qrows]
    summary["by_label_final_query_mean"] = {l_: PQ["FINAL"][lab == l_][mets].mean().to_dict() for l_ in ("PLOC", "PLONC")}
    for a in arms:
        d = PQ[a].copy()
        d.insert(0, "query", T.pocket_id.to_numpy()[qrows])
        d.insert(1, "group", qg)
        d.to_parquet(DATA / f"per_query_{a}.parquet", index=False)
    summary["wall_s"] = time.time() - t0
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    # compact table
    lines = ["# PPI-R (EXPLORATORY, post-test; PPI-L train+val only)", "",
             f"queries {len(qrows)} in {len(cnt)} PPI-L groups; pool {int(avail.sum())} = {int((isP & avail).sum())} "
             f"PPI + {int((~isP & avail).sum())} matched BLiPS background", "",
             "| arm | weighting | AUC [95% CI] | AP | P@10 | P@50 | prevalence |", "|---|---|---|---|---|---|---|"]
    for a in arms:
        for wname in ("query_mean", "group_balanced"):
            r = summary["arms"][a][wname]
            f = lambda k: f"{r[k]['estimate']:.3f} [{r[k]['ci_low']:.3f}, {r[k]['ci_high']:.3f}]"  # noqa: E731
            lines.append(f"| {a} | {wname} | {f('auc')} | {f('ap')} | {f('p@10')} | {f('p@50')} | "
                         f"{r['prev']['estimate']:.3f} |")
    lines += ["", "| paired | weighting | ΔAUC [CI] p | ΔAP | ΔP@10 | ΔP@50 |", "|---|---|---|---|---|---|"]
    for k, v in summary["paired"].items():
        for wname, r in v.items():
            f = lambda m: f"{r[m]['estimate']:+.3f} [{r[m]['ci_low']:+.3f}, {r[m]['ci_high']:+.3f}]"  # noqa: E731
            lines.append(f"| {k} | {wname} | {f('auc')} p={r['auc']['p_one_sided']:.3f} | {f('ap')} | {f('p@10')} | "
                         f"{f('p@50')} |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    log("\n".join(lines))


if __name__ == "__main__":
    main()
