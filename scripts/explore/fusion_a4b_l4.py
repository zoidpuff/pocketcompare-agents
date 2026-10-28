#!/usr/bin/env python
"""EXPLORATORY — post-test; not a confirmatory result.  Score-level fusion of the final method and L4.

    python scripts/explore/fusion_a4b_l4.py --phase dev   [--B 2000] [--threads 16]    # scales + dev table + w choice
    python scripts/explore/fusion_a4b_l4.py --phase test  [--B 2000] [--threads 16]    # ONE exploratory test look
    python scripts/explore/fusion_a4b_l4.py --phase runtime

Context: the confirmatory final evaluation is done (results/final/, reports/verification_final.md).  The test
numbers of FINAL (A4b:n1_linear raw) and of the descriptive arm L4:egnn_small have been seen, which motivated this
question (L4 better on BLiPS, ProSPECCTs decoys P3/P4, PPIPS; A4b better on TOUGH-M1 D).  Everything here is
therefore post hoc and EXPLORATORY; no result changes any PREREG claim.

PROTOCOL (fixed in this header before any fused score was computed)
------------------------------------------------------------------
Components (both RAW cosine, no CSLS; frozen weights / embeddings, nothing re-trained):
  cos_A = FINAL A4b:n1_linear raw (configs/final_method.yaml through final_eval.MethodAdapter / eval_dev.fs_embed);
  cos_L = L4:egnn_small raw (3-seed mean cosine; data/processed/l4_emb/egnn_small = results/models/l4/egnn_small).
Fused score (DECLARED PRIMARY: per-method z-scoring of the pair-score distribution):
  s_w = w * (cos_A - mu_A) / sd_A + (1 - w) * (cos_L - mu_L) / sd_L,   w in {0.25, 0.50, 0.75}
  mu, sd = mean / std of each method's raw pair cosine over ALL BLiPS-train v2 labelled pairs
  (data/splits/blips_train_pairs_v2.parquet; L-mode pairs and D-mode pairs with both sites D-matched, pooled).
  Reason for z-scoring: the two heads were trained separately, so their cosine spreads differ and w would otherwise
  not be a relative weight.  The constants mu only shift the score (rank-invariant); implemented exactly as the
  inner product of the concatenated embedding [sqrt(w/sd_A) e_A, sqrt((1-w)/sd_L) e_L] (768 stored dims), so every
  final_eval / eval_dev code path (pools, D-sets, missing policy) applies unchanged.  A pocket is scored only if
  BOTH components exist (otherwise NaN -> common-set policy).
  Dev-only sensitivity (never selected, never taken to test): un-normalised raw sum, w = 0.5.
Selection of w (DEV ONLY; PREREG §1 machinery = eval_dev.main_final_select, B = 2000, seed 0):
  objective BLiPS-val v2 D-mode cluster-balanced ROC-AUC, SE = homology-group vertex bootstrap;
  best = argmax_w; threshold = best - SE(best); if w = 0.50 >= threshold -> w* = 0.50, else w* = best.
  PREREG guards (BLiPS-val L cb >= B1, TOUGH-M1-dev D cb >= B1) are reported, not used.
Dev report: all w on BLiPS-val L/D, TOUGH-M1-dev D (and L), PPIPS-val (P-ortho MRR/top-1, P-sym) + paired dev
  Delta cb-AUC (fused w* - FINAL) on the shared replicate weights.
ONE exploratory test look, w* only (refuses to run twice; w* read from the dev selection file, no CLI override):
  sealed files read via final_eval.Sealed (chmod 400 -> sha256 check -> read -> chmod 000), every access logged to
  results/exploratory/unseal_log.tsv.  Sets and metrics = final_eval's code paths (imported, final_eval.py not
  modified): TOUGH-M1-test L/D, ProSPECCTs all 10 subsets (+ P3/P4 5-sub; L; D on the BURROW-clean subset),
  Vertex (protein pair = max over pocket pairs), BLiPS-test L/D + AF-model pockets (L/D), PPIPS-test.  Not run:
  TOUGH-M1 full-minus-dev (learned arms are not reported there, D8), PPI-L (skipped in the final run).
  FINAL and L4 raw are recomputed on the same code path (must reproduce results/final/final_summary.parquet).
  Paired Delta (fused w* - FINAL), vertex bootstrap B = 2000, seed 0, same units as final_eval (wider CI over unit
  definitions), common set: ROC-AUC on TOUGH-M1-test L/D, BLiPS-test L/D/AF-L/AF-D, each ProSPECCTs subset (L
  no_self; D clean where >= 2 classes), Vertex; cb-AUC Delta on TOUGH-M1-test and BLiPS-test; PPIPS-test Delta
  P-ortho MRR and top-1 (query-group units).  No multiplicity correction; CIs are descriptive.
Runtime: A4b (dev runtime json) + L4 (results/models/l4/bench.json, point-set extraction from data/processed/l4)
  + 768-d pair scoring measured here.
Trials: one row per fused (w, variant, set, mode) in results/trials.tsv, config tag 'exploratory_posttest'.
Outputs: results/exploratory/fusion/ (provenance sidecars), report reports/exploratory_fusion.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_dev as ED  # noqa: E402
import final_eval as FE  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.provenance import append_trial, sha256_file, write_result  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402
from pocketcompare.similarity import pair_scores  # noqa: E402

OUT = ROOT / "results/exploratory/fusion"
UNSEAL_LOG = ROOT / "results/exploratory/unseal_log.tsv"
SCALES = OUT / "fusion_scales.json"
SELECTION = OUT / "dev/fusion_selection.json"
TAG = "exploratory_posttest"
WS = (0.25, 0.5, 0.75)
A4B_DIR = ROOT / "results/models/a4b/n1_linear"
L4_DIR = ROOT / "results/models/l4/egnn_small"
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


def common_prov(args, config, inputs=()):
    return dict(script=__file__, args=sys.argv[1:], config=config, inputs=[str(p) for p in inputs], seed=args.seed,
                device="cpu", start_time=T0)


# ============================================================================================ components
def a4b_cand():
    cfg = json.loads((A4B_DIR / "config.json").read_text())
    return ED.Cand("A4b:n1_linear", "learned", cfg["input"], cfg["out_dim"] * len(cfg["seeds"]), 10, str(A4B_DIR))


def l4_cand():
    cfg = json.loads((L4_DIR / "config.json").read_text())
    return ED.Cand("L4:egnn_small", "learned", "L4", cfg["out_dim"] * len(cfg["seeds"]), 30, str(L4_DIR))


def l4_dev_embed(dataset, mode, pocket_ids, avail_mode):
    """As scripts/eval_l4.fs_embed (rows of results/models/l4/egnn_small/emb_<ds>_<loc>.npy)."""
    from pocketcompare import a4b as A4
    loc = "L" if mode == "L" else ("D" if dataset == "ppips" else "U")
    M = np.load(L4_DIR / f"emb_{dataset}_{loc}.npy")
    ids = A4.ids_table(dataset).pocket_id
    row = pd.Series(np.arange(len(ids)), index=ids).loc[list(pocket_ids)].to_numpy()
    Em = np.asarray(M[row], np.float32)
    av = (np.linalg.norm(Em, axis=1) > 0) & np.asarray(avail_mode, bool)
    Em[~av] = 0.0
    return Em, av


def fuse(EA, EL, w, sdA, sdL):
    """Concatenated embedding whose inner product = w cosA / sdA + (1 - w) cosL / sdL."""
    return np.concatenate([np.sqrt(w / sdA) * EA, np.sqrt((1 - w) / sdL) * EL], axis=1).astype(np.float32)


# ============================================================================================ scales
def fit_scales(args):
    """mu / sd of raw pair cosines of FINAL and L4 over BLiPS-train v2 pairs (L + D-matched D pooled)."""
    if SCALES.exists():
        log(f"{SCALES} exists -> reused (fixed once)")
        return json.loads(SCALES.read_text())
    tp = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
    sites = sorted(set(tp.site_a) | set(tp.site_b))
    P = FE._attach_geometry(pd.DataFrame({"pocket_id": sites}), "blips")
    pos = {p: i for i, p in enumerate(P.pocket_id)}
    ia, ib = tp.site_a.map(pos).to_numpy(), tp.site_b.map(pos).to_numpy()
    out = {"source": "data/splits/blips_train_pairs_v2.parquet", "n_pairs_total": int(len(tp)), "per_mode": {}}
    pooled = {"A": [], "L": []}
    for mode in ("L", "D"):
        avail = P.cache_ok.to_numpy() if mode == "L" else P.d_match.to_numpy(bool)
        EA, avA = ED.fs_embed(a4b_cand(), "blips", mode, P.pocket_id.to_numpy(), avail)
        EL, avL = l4_dev_embed("blips", mode, P.pocket_id.to_numpy(), avail)
        ok = (avA & avL)[ia] & (avA & avL)[ib]
        sA = pair_scores(EA, ia[ok], ib[ok]).astype(np.float64)
        sL = pair_scores(EL, ia[ok], ib[ok]).astype(np.float64)
        out["per_mode"][mode] = {"n_pairs": int(ok.sum()), "mu_A": sA.mean(), "sd_A": sA.std(), "mu_L": sL.mean(),
                                 "sd_L": sL.std(), "pearson": float(np.corrcoef(sA, sL)[0, 1])}
        pooled["A"].append(sA), pooled["L"].append(sL)
    sA, sL = np.concatenate(pooled["A"]), np.concatenate(pooled["L"])
    out.update(mu_A=float(sA.mean()), sd_A=float(sA.std()), mu_L=float(sL.mean()), sd_L=float(sL.std()),
               n_pairs_pooled=int(len(sA)), pearson_pooled=float(np.corrcoef(sA, sL)[0, 1]))
    write_result(SCALES, out, **common_prov(args, {"task": "fusion scales", "tag": TAG},
                                            [ROOT / "data/splits/blips_train_pairs_v2.parquet"]))
    log(f"scales: {json.dumps({k: out[k] for k in ('mu_A', 'sd_A', 'mu_L', 'sd_L', 'pearson_pooled')})}")
    return out


# ============================================================================================ dev
def _dcb_task(a):
    """Paired Delta cb-AUC (a - b) with shared vertex-bootstrap weights."""
    key, y, sa, sb, pc, ci, cj, B, seed = a

    def fn(w):
        return [ev.cluster_balanced_auc(y, sa, pc, w)["auc_cb"] - ev.cluster_balanced_auc(y, sb, pc, w)["auc_cb"]]

    try:
        r = ev.vertex_bootstrap_generic(fn, ci, cj, B=B, seed=seed, names=["d_auc_cb"], diff=True)[0]
    except ValueError:
        return key, None
    return key, r


def phase_dev(args):
    sc = fit_scales(args)
    a4, l4 = a4b_cand(), l4_cand()
    fused = [ED.Cand(f"FUSEz:w{w:.2f}", "learned", "FUSE", 768, 50 + k) for k, w in enumerate(WS)]
    sens = [ED.Cand("FUSEraw:w0.50", "sensitivity", "FUSE", 768, 60)]
    wmap = {c.name: (w, sc["sd_A"], sc["sd_L"]) for c, w in zip(fused, WS)}
    wmap["FUSEraw:w0.50"] = (0.5, 1.0, 1.0)
    orig_embed = ED.fs_embed

    def fs_embed(c, dataset, mode, pocket_ids, avail_mode):
        if c.inp == "L4":
            return l4_dev_embed(dataset, mode, pocket_ids, avail_mode)
        if c.inp == "FUSE":
            w, sdA, sdL = wmap[c.name]
            EA, avA = orig_embed(a4, dataset, mode, pocket_ids, avail_mode)
            EL, avL = l4_dev_embed(dataset, mode, pocket_ids, avail_mode)
            av = avA & avL
            E = fuse(EA, EL, w, sdA, sdL)
            E[~av] = 0.0
            return E, av
        return orig_embed(c, dataset, mode, pocket_ids, avail_mode)

    n1 = ED.Cand("N1", "nonlearned", "N1", 627, 0)          # main_final_select's focus deltas need N1
    ED.fs_candidates = lambda which: [n1, a4, l4] + fused + sens
    ED.fs_embed = fs_embed
    os.environ["POCKETCOMPARE_THREADS"] = str(args.threads)
    dev_out = OUT / "dev"
    ns = argparse.Namespace(candidates="fusion", B=args.B, seed=args.seed, threads=args.threads, out=str(dev_out),
                            no_trials=True)
    ED.main_final_select(ns)
    ctab = pd.read_parquet(dev_out / "final_select_fusion_candidates.parquet")
    summ = pd.read_parquet(dev_out / "final_select_fusion_summary.parquet")
    pp = pd.read_parquet(dev_out / "final_select_fusion_ppips.parquet")

    # ------------------------------------------------ w selection (declared rule)
    R = ctab[(ctab.variant == "raw")].set_index("cand")
    F = R.loc[[c.name for c in fused]]
    best = F.bl_D_cb.idxmax()
    thr = float(F.loc[best, "bl_D_cb"] - F.loc[best, "bl_D_cb_se"])
    w_star = 0.5 if F.loc["FUSEz:w0.50", "bl_D_cb"] >= thr else wmap[best][0]
    b1 = R.loc["B1"]
    sel = {"rule": "argmax_w BLiPS-val D cb (raw, z-scored fusion); threshold = best - SE_hom(best); prefer w = 0.5 "
                   "if within one SE", "best": best, "best_bl_D_cb": float(F.loc[best, "bl_D_cb"]),
           "se_best": float(F.loc[best, "bl_D_cb_se"]), "threshold": thr, "w_star": w_star,
           "candidate": f"FUSEz:w{w_star:.2f}", "scales": {k: sc[k] for k in ("mu_A", "sd_A", "mu_L", "sd_L")},
           "guards_reported_not_used": {c: {"blips_L_ge_B1": bool(F.loc[c, "bl_L_cb"] >= b1.bl_L_cb),
                                            "tm_D_ge_B1": bool(F.loc[c, "tm_D_cb"] >= b1.tm_D_cb)} for c in F.index},
           "B": args.B, "seed": args.seed, "tag": TAG}
    log(f"selection: {sel}")

    # ------------------------------------------------ paired dev Delta cb (fused - FINAL), shared weights
    bl, tm = ED.BlipsVal().load(), ED.ToughM1Dev().load()
    tasks, meta = [], []
    for name, ds in (("blips", bl), ("tough_m1", tm)):
        P = ds.pockets
        y = ds.pairs.y.to_numpy().astype(bool)
        dm = P.d_match.to_numpy()
        units = {"hom": ds.unit_defs["hom"], "lig": ds.unit_defs["lig"]} if name == "blips" else {"u": P.unit.to_numpy()}
        for mode in ("L", "D"):
            avail = np.ones(len(P), bool) if mode == "L" else dm
            m = np.ones(len(y), bool) if mode == "L" else dm[ds.ia] & dm[ds.ib]
            sv = {}
            for c in [a4] + fused:
                E, av = fs_embed(c, name, mode, P.pocket_id.to_numpy(), avail)
                sv[c.name], _ = ED.fs_scores(E, av, ds.ia, ds.ib)
            for c in fused:
                for un, arr in units.items():
                    k = (c.name, name, mode, un)
                    tasks.append((k, y[m], sv[c.name][m], sv[a4.name][m], ds.pos_cluster[m], arr[ds.ia][m],
                                  arr[ds.ib][m], args.B, args.seed))
                    meta.append(k)
    res = ED.run_generic(tasks, args.threads, log, fn=_dcb_task)
    drows = []
    for c in fused:
        for name in ("blips", "tough_m1"):
            for mode in ("L", "D"):
                per = {k[3]: res[k] for k in meta if k[:3] == (c.name, name, mode)}
                w_, wu = ED._wider(per)
                sel_un = "hom" if name == "blips" else "u"
                r = per[sel_un]
                drows.append({"a": c.name, "b": "FINAL(A4b:n1_linear raw)", "dataset": name, "mode": mode,
                              "metric": "auc_cb", "delta": r.estimate, "lo_selunit": r.ci_low, "hi_selunit": r.ci_high,
                              "se_selunit": r.se, "p_one_sided_selunit": r.p_value, "lo_wider": w_.ci_low,
                              "hi_wider": w_.ci_high, "wider_unit": wu})
    deltas = pd.DataFrame(drows)
    cfgd = {"task": "fusion dev", "tag": TAG, "B": args.B, "seed": args.seed, "ws": list(WS),
            "scales_sha256": sha256_file(SCALES)}
    write_result(dev_out / "fusion_dev_deltas.parquet", deltas, **common_prov(args, cfgd, [SCALES]))
    write_result(SELECTION, sel, **common_prov(args, cfgd, [SCALES, dev_out / "final_select_fusion_candidates.parquet"]))

    # ------------------------------------------------ trials (fused rows only)
    n = 0
    for r in summ[summ.cand.str.startswith("FUSE")].itertuples():
        conf = {"candidate": r.cand, "variant": r.variant, "mode": r.mode, "B": args.B, "seed": args.seed,
                "task": "fusion dev (final_select machinery)", "tag": TAG, "scales": "blips_train_pairs_z"
                if r.cand.startswith("FUSEz") else "none"}
        split = f"{r.dataset}_{'val' if r.dataset == 'blips' else 'dev'}"
        append_trial("FUSE", conf, split, {k: getattr(r, k) for k in summ.columns
                                           if k.startswith(("auc", "n_", "ap")) and pd.notna(getattr(r, k))},
                     dev_out / "final_select_fusion_summary.parquet")
        n += 1
    for r in pp[pp.cand.str.startswith("FUSE")].itertuples():
        conf = {"candidate": r.cand, "variant": r.variant, "mode": "D", "B": args.B, "seed": args.seed,
                "task": "fusion dev P-ortho + P-sym", "tag": TAG}
        append_trial("FUSE", conf, "ppips_val", {k: getattr(r, k) for k in pp.columns if k.startswith(("ortho", "sym"))},
                     dev_out / "final_select_fusion_ppips.parquet")
        n += 1
    log(f"{n} trial rows appended; w* = {w_star}")


# ============================================================================================ test
class FusedMethod:
    """final_eval method interface (embed -> unit-free rows, NaN = unavailable); inner product = fused score."""
    is_learned = True
    csls = False

    def __init__(self, final, w, sdA, sdL):
        self.final, self.w, self.sdA, self.sdL = final, w, sdA, sdL
        self.l4 = FE.ExtraArm("L4", f"L4:{FE.L4_MODEL}", True, "raw", FE._l4_embed)
        self.name = f"FUSEz:w{w:.2f}(A4b:n1_linear raw + L4:egnn_small raw)"

    def weight_files(self):
        return self.final.weight_files()

    def embed(self, store, dataset, mode, pocket_ids):
        EA = np.asarray(self.final.embed(store, dataset, mode, pocket_ids), np.float32)
        EL = np.asarray(self.l4.embed(store, dataset, mode, pocket_ids), np.float32)
        ok = np.isfinite(EA).all(1) & np.isfinite(EL).all(1)
        E = fuse(np.nan_to_num(EA), np.nan_to_num(EL), self.w, self.sdA, self.sdL)
        E[~ok] = np.nan
        return E


def raw_vecs(ps, arms, store, modes, dataset=None):
    out = []
    for arm, m in arms:
        out += [v for v in FE._method_vectors(ps, m, store, modes, dataset, arm, f"{arm} (exploratory fusion run)")
                if v.variant == "raw"]
    return out


def dpair(ps, sa, sb, args, mask=None, units=None, y=None):
    try:
        return FE.paired(ps.y if y is None else y, sa, sb, ps.pair_units if units is None else units, args, mask=mask)
    except ValueError as e:
        return {"error": str(e)}


def dcb(ps, sa, sb, args, mask=None):
    m = np.isfinite(sa) & np.isfinite(sb)
    if mask is not None:
        m &= mask
    y = ps.y.astype(bool)
    per = {}
    for un, (ci, cj) in ps.pair_units.items():
        per[un] = _dcb_task((un, y[m], sa[m], sb[m], ps.pos_cluster[m], ci[m], cj[m], args.B, args.seed))[1]
    w, wu = ED._wider(per)
    if w is None:
        return {"error": "degenerate"}
    return {"n_pairs": int(m.sum()), "delta": w.estimate, "ci_low": w.ci_low, "ci_high": w.ci_high, "se": w.se,
            "p_one_sided": w.p_value, "ci_unit": wu}


def ppips_rr(split, ortho, method, store):
    """Per-query P-ortho reciprocal rank (as final_eval.stage_ppips) for the paired PPIPS Delta."""
    P = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
    cs = pd.read_parquet(ROOT / "data/splits/ppips_complex_splits.parquet")
    P = P[["pocket_id", "complex", "split"]].copy()
    P["group"] = P.complex.map(dict(zip(cs.complex, cs.group)))
    pid = {p: i for i, p in enumerate(P.pocket_id)}
    ref = ((P.split == "train") | (P.split == split)).to_numpy()
    members = P.groupby("complex").indices
    Q = ortho.reset_index(drop=True)
    oq, oc, ol = [], [], []
    for k, r in enumerate(Q.itertuples()):
        cand = members[r.partner_complex]
        posset = set(r.positives)
        oq += [k] * len(cand)
        oc += list(cand)
        ol += [P.pocket_id.iat[c] in posset for c in cand]
    oq, oc, ol = np.asarray(oq), np.asarray(oc), np.asarray(ol)
    o_i = Q["query"].map(pid).to_numpy()[oq]
    q_unit = Q.query_complex.map(dict(zip(P.complex, P.group))).to_numpy()
    Ef = np.asarray(method.embed(store, "ppips", "D", P.pocket_id.to_numpy()[ref]), np.float32)
    E = np.zeros((len(P), Ef.shape[1]), np.float32)
    E[ref] = np.nan_to_num(Ef)
    so = pair_scores(E, o_i, oc).astype(np.float64)
    ro = ev.retrieval_metrics(pd.DataFrame({"query": oq, "score": so, "label": ol}), ks=(1, 3))
    rk = ro["per_query"].set_index("query").reindex(np.arange(len(Q)))["rank"].to_numpy(float)
    return 1.0 / rk, q_unit


def _res(r):
    return None if r is None else {"delta": r.estimate, "ci_low": r.ci_low, "ci_high": r.ci_high, "se": r.se,
                                   "p_one_sided": r.p_value, "n_units": r.n_clusters}


def phase_test(args):
    if (OUT / "test_summary.parquet").exists():
        raise SystemExit("the exploratory test look has already been taken (results/exploratory/fusion/"
                         "test_summary.parquet exists); refusing a second look")
    sel = json.loads(SELECTION.read_text())
    sc = json.loads(SCALES.read_text())
    w = float(sel["w_star"])
    final, cfg_sha = FE.load_method(allow_standin=False)
    fused = FusedMethod(final, w, sc["sd_A"], sc["sd_L"])
    l4raw = FE.ExtraArm("L4", f"L4:{FE.L4_MODEL}", True, "raw", FE._l4_embed)
    arms = [("FUSED", fused), ("FINAL", final), ("L4", l4raw)]
    log(f"test look: {fused.name}; final {final.name} (config sha {cfg_sha[:12]})")
    store = FE.DescriptorStore(ROOT)
    sealed = FE.Sealed(UNSEAL_LOG, enabled=True)
    tabs, deltas, details = [], [], {"method": fused.name, "w": w, "scales": sc, "selection": sel, "B": args.B,
                                     "seed": args.seed, "tag": TAG, "label": "EXPLORATORY — post-test"}

    def kv(vecs, arm):
        return {v.mode: v.s for v in vecs if v.arm == arm}

    def add(set_, comp, metric, r, **kw):
        deltas.append({"set": set_, "comparison": comp, "metric": metric, **kw, **r})

    comp = "FUSED − FINAL"
    # ---------------------------------------------------------------- TOUGH-M1-test
    tp = sealed.read("tough_m1_test_pairs.parquet", "EXPLORATORY post-test fusion (A4b+L4): TOUGH-M1-test")
    tm = FE.tough_set("tough_m1_test", tp, lambda s: s.partition == "test")
    vecs = raw_vecs(tm, arms, store, ("L", "D"))
    tab, _ = FE.evaluate_vectors(tm.name, vecs, tm.y, tm.pair_units, tm.pos_cluster, tm.cov, tm.dset, tm.subsets, args)
    tabs.append(tab)
    F_, A_ = kv(vecs, "FUSED"), kv(vecs, "FINAL")
    for mode in ("L", "D"):
        mk = tm.dset if mode == "D" else None
        add(tm.name, comp, "auc", dpair(tm, F_[mode], A_[mode], args, mask=mk), mode=mode, subset="all")
        add(tm.name, comp, "auc_cb", dcb(tm, F_[mode], A_[mode], args, mask=mk), mode=mode, subset="all")
    log("TOUGH-M1-test done")
    # ---------------------------------------------------------------- ProSPECCTs
    pp = sealed.read("prospeccts_pairs.parquet", "EXPLORATORY post-test fusion (A4b+L4): ProSPECCTs")
    for ps in FE.prospeccts_sets(pp, synthetic=False):
        vecs = raw_vecs(ps, arms, store, ("L", "D"))
        cov = ps.cov if int(ps.y.sum()) >= 20 else None
        tab, _ = FE.evaluate_vectors(ps.name, vecs, ps.y, ps.pair_units, None, cov, ps.dset, ps.subsets, args,
                                     generic_filter=lambda v: v.variant in ("raw", "native"))
        tabs.append(tab)
        F_, A_ = kv(vecs, "FUSED"), kv(vecs, "FINAL")
        for sn in [s for s in ps.subsets if "no_self" in s]:
            add(ps.name, comp, "auc", dpair(ps, F_["L"], A_["L"], args, mask=ps.subsets[sn]), mode="L", subset=sn)
            if "D" in F_ and "D" in A_:
                add(ps.name, comp, "auc", dpair(ps, F_["D"], A_["D"], args, mask=ps.subsets[sn] & ps.dset),
                    mode="D", subset=sn)
        log(f"{ps.name} done")
    # ---------------------------------------------------------------- BLiPS-test (+ AF)
    bp = sealed.read("blips_test_pairs.parquet", "EXPLORATORY post-test fusion (A4b+L4): BLiPS-test")
    bs = sealed.read("blips_test_sites.parquet", "EXPLORATORY post-test fusion (A4b+L4): BLiPS-test sites")
    exc = pd.read_parquet(ROOT / "data/splits/blips_test_exclusions_v2.parquet")
    trp = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
    seen = set(trp.pair_cluster[trp.label == 1])
    bp = bp.copy()
    bp["chemotype_seen"] = np.where(bp.label == 1, bp.pair_cluster.isin(seen), None)
    xs = set(exc.site_id[exc.excluded])
    bl = FE.blips_set("blips_test", bp, bs, "blips_test_holo", "blips_test_holo", exclusions=xs)
    af = FE.blips_set("blips_test", bp, bs, "blips_test_af", "blips_test_af", exclusions=xs, allow_missing=True)
    vecs = raw_vecs(bl, arms, store, ("L", "D"))
    tab, _ = FE.evaluate_vectors(bl.name, vecs, bl.y, bl.pair_units, bl.pos_cluster, bl.cov, bl.dset, bl.subsets, args)
    tabs.append(tab)
    avecs = raw_vecs(af, arms, store, ("L", "D"), dataset=af.dataset)
    atab, _ = FE.evaluate_vectors(bl.name + "_af", avecs, af.y, af.pair_units, af.pos_cluster, af.cov, af.dset,
                                  {"all": af.subsets["all"]}, args)
    tabs.append(atab)
    F_, A_, Fa, Aa = kv(vecs, "FUSED"), kv(vecs, "FINAL"), kv(avecs, "FUSED"), kv(avecs, "FINAL")
    for mode in ("L", "D"):
        add(bl.name, comp, "auc", dpair(bl, F_[mode], A_[mode], args, mask=bl.dset if mode == "D" else None),
            mode=mode, subset="all")
        add(bl.name, comp, "auc_cb", dcb(bl, F_[mode], A_[mode], args, mask=bl.dset if mode == "D" else None),
            mode=mode, subset="all")
        add(bl.name + "_af", comp, "auc", dpair(af, Fa[mode], Aa[mode], args, mask=af.dset if mode == "D" else None),
            mode=mode, subset="all")
        add(bl.name + "_af", comp, "auc_cb", dcb(af, Fa[mode], Aa[mode], args, mask=af.dset if mode == "D" else None),
            mode=mode, subset="all")
        dm = (bl.dset & af.dset) if mode == "D" else None
        add(bl.name, "FUSED holo − FUSED AF (C5 analogue)", "auc", dpair(bl, F_[mode], Fa[mode], args, mask=dm),
            mode=mode, subset="all")
    log("BLiPS-test done")
    # ---------------------------------------------------------------- Vertex
    vp = sealed.read("vertex_pairs.parquet", "EXPLORATORY post-test fusion (A4b+L4): Vertex")
    vs = FE.vertex_set(vp, synthetic=False)
    vecs = raw_vecs(vs, arms, store, ("L",))
    codes, _ = pd.factorize(vs.pairs.protein_pair.to_numpy())
    y = pd.Series(vs.y).groupby(codes).max().to_numpy()
    unit = vs.pockets.unit.to_numpy()
    first = pd.Series(np.arange(len(codes))).groupby(codes).first().to_numpy()
    ci, cj = unit[vs.ia[first]], unit[vs.ib[first]]
    pvecs = [FE.Vec(v.arm, v.config, v.variant, v.mode, pd.Series(v.s).groupby(codes).max().to_numpy(), v.dims,
                    v.note + "; protein pair = max over pocket pairs") for v in vecs]
    tab, _ = FE.evaluate_vectors("vertex", pvecs, y, {"hom": (ci, cj)}, None, None, np.zeros(len(y), bool),
                                 {"all": np.ones(len(y), bool)}, args, ap_neg=True)
    tabs.append(tab)
    F_, A_ = kv(pvecs, "FUSED"), kv(pvecs, "FINAL")
    add("vertex", comp, "auc", dpair(vs, F_["L"], A_["L"], args, units={"hom": (ci, cj)}, y=y), mode="L", subset="all")
    log("Vertex done")
    # ---------------------------------------------------------------- PPIPS-test
    q = sealed.read("ppips_test_queries.parquet", "EXPLORATORY post-test fusion (A4b+L4): PPIPS-test P-ortho")
    s = sealed.read("ppips_sym_test_pairs.parquet", "EXPLORATORY post-test fusion (A4b+L4): PPIPS-test P-sym")
    ptab = FE.stage_ppips("test", q, s, fused, store, args)
    ptab.loc[ptab.arm == "FINAL", "arm"] = "FUSED"        # stage_ppips labels the passed method FINAL
    ptab = ptab[(ptab.arm.isin(["FUSED", "L4"]))].copy()
    rrF, qu = ppips_rr("test", q, fused, store)
    rrA, _ = ppips_rr("test", q, final, store)
    bo = ED._boot_means({"mrr": rrF - rrA, "top1": (rrF == 1).astype(float) - (rrA == 1).astype(float)}, qu,
                        args.B, args.seed, diff=True)
    for k in ("mrr", "top1"):
        add("ppips_test", comp, f"ortho_{k}", _res(bo[k]) or {"error": "degenerate"}, mode="D", subset="all",
            a=float((rrF if k == "mrr" else (rrF == 1)).mean()), b=float((rrA if k == "mrr" else (rrA == 1)).mean()))
    log("PPIPS-test done")
    details["sealed_files_accessed"] = sealed.accessed
    # ---------------------------------------------------------------- reproduction check vs results/final
    summary = pd.concat(tabs, ignore_index=True)
    ref = pd.read_parquet(ROOT / "results/final/final_summary.parquet")
    ref = ref[((ref.arm == "FINAL") | (ref.arm == "L4")) & (ref.variant == "raw")]
    mine = summary[summary.arm.isin(["FINAL", "L4"])].copy()
    mine["k2"] = mine.arm + "|" + mine.variant + "|" + mine["mode"]
    ref = ref.assign(k2=ref.arm + "|" + ref.variant + "|" + ref["mode"])
    j = mine.merge(ref, on=["set", "subset", "k2"], suffixes=("", "_ref"))
    cols = ["auc", "auc_lo", "auc_hi", "ap", "auc_cb", "auc_strat", "auc_cb_lo", "auc_cb_hi"]
    dev_ = max(float(np.nanmax(np.abs(j[c].to_numpy(float) - j[c + "_ref"].to_numpy(float)))) if j[c].notna().any()
               else 0.0 for c in cols)
    details["reproduction_vs_results_final"] = {"rows_compared": int(len(j)), "rows_mine": int(len(mine)),
                                                "max_abs_deviation": dev_, "metrics": cols}
    log(f"reproduction vs results/final: {len(j)} rows, max |dev| {dev_:.2e}")
    D = pd.DataFrame(deltas)
    cfg = {"task": "fusion exploratory test look", "tag": TAG, "w": w, "scales_sha256": sha256_file(SCALES),
           "selection_sha256": sha256_file(SELECTION), "final_method_config_sha256": cfg_sha, "B": args.B,
           "seed": args.seed}
    inputs = [SCALES, SELECTION, FE.METHOD_CFG]
    write_result(OUT / "test_summary.parquet", summary, **common_prov(args, cfg, inputs))
    write_result(OUT / "test_deltas.parquet", D, **common_prov(args, cfg, inputs))
    write_result(OUT / "test_ppips.parquet", ptab, **common_prov(args, cfg, inputs))
    write_result(OUT / "test_details.json", details, **common_prov(args, cfg, inputs))
    n = 0
    for r in summary[summary.arm == "FUSED"].itertuples():
        conf = {"candidate": f"FUSEz:w{w:.2f}", "variant": "raw", "mode": r.mode, "subset": r.subset, "B": args.B,
                "seed": args.seed, "task": "fusion exploratory test look", "tag": TAG}
        append_trial("FUSE", conf, r.set, {k: getattr(r, k) for k in ("auc", "auc_lo", "auc_hi", "ap", "auc_cb",
                                                                      "auc_strat", "n_pairs", "n_pos")
                                           if pd.notna(getattr(r, k, np.nan))}, OUT / "test_summary.parquet")
        n += 1
    for r in ptab[ptab.arm == "FUSED"].itertuples():
        conf = {"candidate": f"FUSEz:w{w:.2f}", "variant": r.variant, "mode": "D", "B": args.B, "seed": args.seed,
                "task": "fusion exploratory test look P-ortho + P-sym", "tag": TAG}
        append_trial("FUSE", conf, "ppips_test", {k: getattr(r, k) for k in ptab.columns
                                                  if k.startswith(("ortho", "sym"))}, OUT / "test_ppips.parquet")
        n += 1
    log(f"{n} trial rows appended; done")


# ============================================================================================ runtime
def phase_runtime(args):
    rt = json.loads((ROOT / "results/dev/final_method_runtime.json").read_text())
    bench = json.loads((ROOT / "results/models/l4/bench.json").read_text())["egnn_small"]
    ext = {}
    for f in sorted((ROOT / "data/processed/l4").glob("*/summary.json")):
        d = json.loads(f.read_text())
        ext[f.parent.name] = {f"{loc}_{k}": v for loc, sub in d.items() if isinstance(sub, dict)
                              for k, v in sub.items() if str(k).startswith("t_ms")}
    rng = np.random.default_rng(SEEDS[0])
    out = {}
    for dims in (384, 768):
        E = rng.normal(size=(20000, dims)).astype(np.float32)
        i, j = rng.integers(0, len(E), 1_000_000), rng.integers(0, len(E), 1_000_000)
        ts = []
        for _ in range(3):
            t0 = time.perf_counter()
            pair_scores(E, i, j)
            ts.append(time.perf_counter() - t0)
        out[f"pair_us_batched_1M_{dims}d"] = float(np.median(ts))
    res = {"a4b_final_method_runtime_json": rt, "l4_egnn_small_bench": bench, "l4_point_set_extraction": ext,
           **out, "fused_bytes_per_pocket_float32": 768 * 4,
           "note": "fused per-pocket cost = A4b descriptor+embed + L4 point-set extraction + L4 forward (GPU or "
                   "CPU); BURROW featurisation shared and excluded"}
    write_result(OUT / "fusion_runtime.json", res, **common_prov(args, {"task": "fusion runtime", "tag": TAG}))
    log(json.dumps(res, default=str)[:2000])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--phase", choices=["dev", "test", "runtime"], required=True)
    ap.add_argument("--B", type=int, default=ev.DEFAULT_B)
    ap.add_argument("--seed", type=int, default=SEEDS[0])
    ap.add_argument("--threads", type=int, default=16)
    args = ap.parse_args()
    os.environ["POCKETCOMPARE_THREADS"] = str(args.threads)
    {"dev": phase_dev, "test": phase_test, "runtime": phase_runtime}[args.phase](args)


if __name__ == "__main__":
    main()
