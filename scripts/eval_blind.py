#!/usr/bin/env python
"""Blind deployment test (DESIGN §2.7; secondary, reported).  No ligand guidance anywhere in the query/pool.

    python scripts/eval_blind.py --set val                                   # dry run: BLiPS-val v2 sites with an AF model
    FINAL_EVAL=1 python scripts/eval_blind.py --set test --pairs <blips_test_pairs>   # PI / final_eval only (NOT run here)

Set  = the sites of the chosen partition that have an AF model (adapter of scripts/eval_af_robustness.py: val ->
       BLiPS-val v2 sites with a pocket_detect af_train model; test -> BLiPS-test af_set, exclusions v2).  The AF models
       of the set are the "proteins"; the labelled ligand-sharing pairs (val pairs v2 / the sealed test pairs, supplied
       by the PI: this script never opens data/sealed) restricted to pairs whose two sites are both in the set.
Pool = ALL BURROW region-rule pockets of every AF model (AF mode, no ligand): merged (pockets.merge_pockets 'region'),
       >= 10 points (drops the single-point metal candidates).  Every pool pocket is described with the final method
       (configs/final_method.yaml via pocketcompare.method.raw_parts/embed: base = the merged pocket, sph8 shaper) and
       with B1 (default, z-scored on the pool; label-free) and B0 (size) for reference.  B4 needs ESM-2 on a GPU and is
       not computed here (documented gap).
Truth (the ONLY use of the ligand): site -> its detected pocket = the pool pocket of the site's AF model with the highest
       coverage of the (transferred) ligand's 4 Å shell, matched iff coverage >= 0.3 or precision >= 0.5 (the D-mode rule).
Queries: for every labelled positive pair (a, b), both directions: query = a's matched pocket, candidates = all pool
       pockets of ALL OTHER models (variant 'xgrp' also drops the candidates of the query's homology group).  Target =
       b's matched pocket; the other positive partners' matched pockets of the same query are removed from the
       candidates (filtered rank); ties count against the method (pessimistic).  Metrics per (query, partner) pair, macro
       mean: hit@1/10/100, MRR, AUC(target vs all non-partner candidates); detection recall = fraction of set sites
       whose matched pocket exists.  Conditional (both sites detected) and unconditional (undetected pair = miss: hit/MRR 0,
       AUC 0.5) numbers.  CIs: vertex bootstrap over homology groups (units of both endpoints, evaluate.py), paired
       final - B1 difference on the same replicates.
Outputs results/dev/blind_val/ (final/blind_test for test): metrics.csv/.parquet, pairs.parquet (per directed pair),
pockets.parquet (the pool), details.json; trials arm "blind_dev" (dev) / "blind" (test).
"""
from __future__ import annotations

import os

if __name__ != "__main__":                       # spawned workers: one core each
    for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[_v] = "1"
else:
    os.environ.setdefault("POCKETCOMPARE_THREADS", "12")
    os.environ.setdefault("NUMBA_NUM_THREADS", "12")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

MIN_POINTS = 10
D_MIN_COV, D_MIN_PREC = 0.3, 0.5
ARMS = ("final", "B1", "B0")
KS = (1, 10, 100)
METRICS = ("hit1", "hit10", "hit100", "mrr", "auc")
_W = {}


def _init_worker():
    from pocketcompare import method as M
    _W["m"] = M.Method()


# ====================================================================================== per-model description
def _describe_model(task):
    """All pool pockets of one AF model + the pocket match of each set site (the only ligand use)."""
    from pocketcompare import pockets as pk
    from pocketcompare.descriptors import a1 as A1
    from pocketcompare.descriptors import baselines as BL
    m = _W["m"]
    out = {"model": task["model"], "error": None, "pockets": [], "sites": {}}
    try:
        fs = pk.Featurized.load(task["cache"])
        at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
        merged = [(k, mp) for k, mp in enumerate(pk.merge_pockets(fs, "region")) if len(mp.idx) >= MIN_POINTS]
        for k, mp in merged:
            out["pockets"].append({"merged_index": k, "n_points": int(len(mp.idx)), "volume_A3": float(mp.volume_A3),
                                   "score": float(mp.score), "parts": m.raw_parts(fs, mp.idx, at),
                                   "b1": BL.b1_descriptor(fs, mp.idx, learned=False, residues=[])[0]})
        for sid, lig in task["sites"]:
            rec = {"matched": False, "pocket": -1, "cov": 0.0, "prec": 0.0}
            if merged:
                L = pk.lmode_from_ligand(fs, np.asarray(lig, np.float64).reshape(-1, 3))
                if len(L.idx):
                    cov = [pk.coverage(fs, L.idx, mp.idx) for _, mp in merged]
                    j = min(range(len(merged)), key=lambda i: (-cov[i], -merged[i][1].score, merged[i][0]))
                    prec = pk.coverage(fs, merged[j][1].idx, L.idx)
                    rec = {"matched": bool(cov[j] >= D_MIN_COV or prec >= D_MIN_PREC), "pocket": j,
                           "cov": float(cov[j]), "prec": float(prec)}
            out["sites"][sid] = rec
    except Exception as e:  # noqa: BLE001
        out["error"] = repr(e)
    return out


def describe_models(sites, workers, log):
    from eval_af_robustness import _featurize_one
    models = {}
    for r in sites.itertuples():
        models.setdefault(r.af_cache, {"structure": r.af_structure, "chains": getattr(r, "af_chains", None),
                                       "sites": [], "group": r.group_id})
        models[r.af_cache]["sites"].append((r.site_id, r.af_lig))
    ctx = get_context("spawn")
    missing = [(c, v["structure"], None if v["chains"] is None else list(v["chains"]), True)
               for c, v in models.items() if not Path(c).exists()]
    if missing:
        log(f"featurizing {len(missing)} missing AF models")
        with ProcessPoolExecutor(workers, mp_context=ctx) as ex:
            for p, e in ex.map(_featurize_one, missing, chunksize=2):
                if e:
                    log(f"  FAIL {p}: {e}")
    tasks = [{"model": c, "cache": c, "sites": v["sites"]} for c, v in models.items() if Path(c).exists()]
    t0 = time.time()
    with ProcessPoolExecutor(workers, mp_context=ctx, initializer=_init_worker) as ex:
        res = list(ex.map(_describe_model, tasks, chunksize=2))
    log(f"described {len(res)} AF models in {time.time() - t0:.0f}s, {sum(r['error'] is not None for r in res)} errors")
    return models, {r["model"]: r for r in res}


# ====================================================================================== pool + vectors
def build_pool(sites, models, desc):
    from pocketcompare import method as M
    from pocketcompare.similarity import ZScorer, embed
    rows, parts, b1 = [], [], []
    site_pocket = {}
    for mi, (c, v) in enumerate(models.items()):
        d = desc.get(c)
        if d is None or d["error"]:
            continue
        base = len(rows)
        for pr in d["pockets"]:
            rows.append({"pocket_id": f"{Path(c).stem}:m{pr['merged_index']}", "model": c, "model_index": mi,
                         "group_id": v["group"], "n_points": pr["n_points"], "volume_A3": pr["volume_A3"],
                         "score": pr["score"]})
            parts.append(pr["parts"])
            b1.append(pr["b1"])
        for sid, rec in d["sites"].items():
            site_pocket[sid] = (base + rec["pocket"]) if rec["matched"] else -1
    pool = pd.DataFrame(rows)
    method = M.Method()
    mats = [np.vstack([p[k] for p in parts]) for k in range(len(method.parts))]
    E = method.embed(mats)
    okF = np.linalg.norm(E, axis=1) > 0
    E[~okF] = np.nan
    B = np.vstack(b1)
    z = ZScorer.fit(B)
    EB = np.asarray(embed(B, z), np.float32)
    return pool, {"final": E, "B1": EB, "B0": np.log(pool.volume_A3.to_numpy() + 1.0)[:, None]}, site_pocket


def sim_rows(arm, V, q_idx):
    if arm == "B0":
        return -np.abs(V[q_idx][:, :1] - V[:, :1].T)
    return V[q_idx] @ V.T


# ====================================================================================== ranking
def rank_pairs(pool, V, site_pocket, pairs, sites):
    """One record per directed positive pair (a -> b) per arm/variant."""
    grp = pool.group_id.to_numpy()
    mod = pool.model_index.to_numpy()
    sg = sites.set_index("site_id").group_id
    pos = pairs[pairs.label == 1]
    directed = pd.concat([pos[["site_a", "site_b"]].rename(columns={"site_a": "q", "site_b": "t"}),
                          pos[["site_b", "site_a"]].rename(columns={"site_b": "q", "site_a": "t"})],
                         ignore_index=True)
    partners = directed.groupby("q").t.apply(list).to_dict()
    recs = []
    for r in directed.itertuples():
        pq, pt = site_pocket.get(r.q, -1), site_pocket.get(r.t, -1)
        base = {"query": r.q, "target": r.t, "g_q": sg[r.q], "g_t": sg[r.t], "q_detected": pq >= 0,
                "t_detected": pt >= 0, "both": pq >= 0 and pt >= 0 and pq != pt}
        if base["both"]:
            others = {site_pocket.get(o, -1) for o in partners[r.q] if o != r.t} - {-1, pt}
            for arm in ARMS:
                if np.isnan(V[arm][[pq, pt]]).any():
                    base["both"] = False
                    break
        recs.append((base, pq, pt, others if base["both"] else None))
    out = []
    for base, pq, pt, others in recs:
        row = dict(base)
        if base["both"]:
            for arm in ARMS:
                s = sim_rows(arm, V[arm], [pq])[0]
                for variant in ("all", "xgrp"):
                    cand = mod != mod[pq]
                    if variant == "xgrp":
                        cand &= grp != grp[pq]
                    cand = cand & np.isfinite(s)
                    if others:
                        cand[list(others)] = False
                    cand[pt] = False
                    n = int(cand.sum())
                    if n == 0:
                        continue
                    sc, st = s[cand], s[pt]
                    rank = 1 + int((sc >= st).sum())                  # pessimistic ties
                    auc = float((sc < st).mean() + 0.5 * (sc == st).mean())
                    row.update({f"{arm}|{variant}|rank": rank, f"{arm}|{variant}|n_cand": n,
                                f"{arm}|{variant}|auc": auc})
        out.append(row)
    return pd.DataFrame(out)


def metric_matrix(P, arm, variant, conditional):
    """(n_pairs, 5) per-pair values hit1, hit10, hit100, mrr, auc (NaN = pair not evaluable for this variant).
    Unconditional: undetected / non-evaluable pairs score 0 (0.5 for AUC)."""
    r = P.get(f"{arm}|{variant}|rank")
    a = P.get(f"{arm}|{variant}|auc")
    if r is None:
        return np.full((len(P), 5), np.nan)
    r, a = r.to_numpy(float), a.to_numpy(float)
    M = np.column_stack([(r <= 1), (r <= 10), (r <= 100), 1.0 / r, a]).astype(float)
    bad = ~np.isfinite(r)
    M[bad] = np.nan
    if not conditional:
        M[bad] = np.array([0, 0, 0, 0, 0.5])
    return M


def boot_table(P, variant, conditional, B, seed):
    """Weighted means + vertex-bootstrap CIs (homology groups of query and target) for every arm and final - B1."""
    from pocketcompare import evaluate as ev
    mats = {arm: metric_matrix(P, arm, variant, conditional) for arm in ARMS}
    keep = np.isfinite(mats["final"][:, 0]) if conditional else np.ones(len(P), bool)
    for arm in ARMS:
        keep &= np.isfinite(mats[arm][:, 0]) if conditional else True
    if keep.sum() < 3:
        return []
    X = {a: m[keep] for a, m in mats.items()}
    ci, cj = P.g_q.to_numpy()[keep], P.g_t.to_numpy()[keep]
    names = [f"{a}|{m}" for a in ARMS for m in METRICS] + [f"final-B1|{m}" for m in METRICS]

    def fn(w):
        sw = w.sum()
        if sw <= 0:
            raise ValueError("empty replicate")
        v = [float(w @ X[a][:, k] / sw) for a in ARMS for k in range(5)]
        return np.array(v + [v[k] - v[5 + k] for k in range(5)])
    res = ev.vertex_bootstrap_generic(fn, ci, cj, B=B, seed=seed, names=names)
    rows = []
    for r in res:
        arm, metric = r.name.split("|")
        rows.append({"variant": variant, "conditional": conditional, "arm": arm, "metric": metric,
                     "estimate": r.estimate, "ci_low": r.ci_low, "ci_high": r.ci_high,
                     "n_pairs": int(keep.sum()), "n_units": r.n_clusters})
    return rows


def detection_table(sites, site_pocket, pairs, B, seed):
    from pocketcompare import evaluate as ev
    det = np.array([site_pocket.get(s, -1) >= 0 for s in sites.site_id])
    grp = sites.group_id.to_numpy()
    in_pos = sites.site_id.isin(set(pairs[pairs.label == 1].site_a) | set(pairs[pairs.label == 1].site_b)).to_numpy()
    rows = []
    for name, m in (("all_sites", np.ones(len(sites), bool)), ("sites_in_positive_pairs", in_pos)):
        if m.sum() < 3:
            continue
        r = ev.vertex_bootstrap_generic(lambda w: float(w @ det[m] / w.sum()), grp[m], grp[m], B=B, seed=seed,
                                        names=["recall"])[0]
        rows.append({"variant": "detection", "conditional": True, "arm": name, "metric": "recall",
                     "estimate": r.estimate, "ci_low": r.ci_low, "ci_high": r.ci_high, "n_pairs": int(m.sum()),
                     "n_units": r.n_clusters})
    return rows


# ====================================================================================== main
def main(argv=None):
    from eval_af_robustness import adapter_blips_dev, adapter_blips_test
    from pocketcompare.provenance import append_trial, write_result
    from pocketcompare.seeds import SEEDS
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--set", choices=["val", "test"], required=True)
    ap.add_argument("--pairs", default=None, help="test only: BLiPS-test pairs parquet (sealed; supplied by the PI)")
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-trials", action="store_true")
    ap.add_argument("--seed", type=int, default=SEEDS[0])
    args = ap.parse_args(argv)
    args.workers = min(args.workers, 12)
    if args.set == "test" and os.environ.get("FINAL_EVAL") != "1":
        sys.exit("refusing: --set test needs FINAL_EVAL=1 (PI / final_eval wrapper only)")
    if args.set == "test" and not args.pairs:
        sys.exit("--set test needs --pairs (the sealed BLiPS-test pairs, supplied by the PI)")
    out = Path(args.out or ROOT / ("results/final/blind_test" if args.set == "test" else "results/dev/blind_val"))
    out.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    def log(m):
        print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

    if args.set == "test":
        sites, pairs = adapter_blips_test(args.pairs)
        split_label = "blips_test_af_blind"
    else:
        sites, pairs = adapter_blips_dev("val", None, args.seed)
        sites = sites[sites.role == "val"].reset_index(drop=True)
        split_label = "blips_val_v2_af_blind"
    pairs = pairs[pairs.site_a.isin(set(sites.site_id)) & pairs.site_b.isin(set(sites.site_id))].reset_index(drop=True)
    log(f"{split_label}: {len(sites)} sites, {sites.af_cache.nunique()} AF models, {len(pairs)} pairs "
        f"({int((pairs.label == 1).sum())} positive)")
    models, desc = describe_models(sites, args.workers, log)
    pool, V, site_pocket = build_pool(sites, models, desc)
    log(f"pool: {len(pool)} pockets from {pool.model.nunique()} models; "
        f"{sum(v >= 0 for v in site_pocket.values())}/{len(sites)} sites detected")
    P = rank_pairs(pool, V, site_pocket, pairs, sites)
    rows = detection_table(sites, site_pocket, pairs, args.B, args.seed)
    for variant in ("all", "xgrp"):
        for conditional in (True, False):
            rows += boot_table(P, variant, conditional, args.B, args.seed)
    R = pd.DataFrame(rows)
    R.to_csv(out / "metrics.csv", index=False)
    det = {"n_sites": int(len(sites)), "n_models": int(pool.model.nunique()), "n_pool_pockets": int(len(pool)),
           "pockets_per_model_median": float(pool.groupby("model").size().median()),
           "n_sites_detected": int(sum(v >= 0 for v in site_pocket.values())),
           "n_pairs_pos": int((pairs.label == 1).sum()), "n_directed_pos": int(len(P)),
           "n_directed_both_detected": int(P.both.sum()),
           "median_candidates": float(P["final|all|n_cand"].median()) if "final|all|n_cand" in P else None,
           "b4": "not computed (ESM-2 needs a GPU)", "n_model_errors": int(sum(d["error"] is not None
                                                                              for d in desc.values()))}
    (out / "details.json").write_text(json.dumps(det, indent=1))
    cfg = {"method": "configs/final_method.yaml", "arms": list(ARMS), "set": args.set, "B": args.B,
           "min_points": MIN_POINTS, "d_rule": [D_MIN_COV, D_MIN_PREC], "pool": "merged region-rule pockets, AF mode",
           **det}
    common = dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=[ROOT / "configs/final_method.yaml"],
                  seed=args.seed, device="cpu", start_time=t_start)
    write_result(out / "metrics.parquet", R, **common)
    write_result(out / "pairs.parquet", P, **common)
    write_result(out / "pockets.parquet", pool, **common)
    if not args.no_trials:
        arm_name = "blind" if args.set == "test" else "blind_dev"
        for (variant, cond, arm), g in R.groupby(["variant", "conditional", "arm"]):
            met = {}
            for r in g.itertuples():
                met[r.metric] = float(r.estimate)
                met[f"{r.metric}_lo"], met[f"{r.metric}_hi"] = float(r.ci_low), float(r.ci_high)
            met["n_pairs"] = int(g.n_pairs.iloc[0])
            append_trial(arm_name, {"config": cfg, "variant": variant, "conditional": bool(cond), "arm_method": arm},
                         split_label, met, out / "metrics.parquet")
    log(f"done in {time.time() - t_start:.0f}s; results in {out}")


if __name__ == "__main__":
    main()
