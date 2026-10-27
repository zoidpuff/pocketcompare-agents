#!/usr/bin/env python
"""Definition-robustness exploration (D11): label-free L<->D agreement screen and labelled TOUGH-M1-dev evaluation.

    python scripts/explore/defrob_eval.py screen                      # label-free only (no labels opened)
    python scripts/explore/defrob_eval.py eval --variants v1,v2 ...   # labelled dev evaluation + trials.tsv rows

Inputs: data/processed/descriptors/tough_m1/defrob/*.npz (scripts/explore/defrob_compute.py).  Pairs, units,
positive clusters, size covariates and the D-set exactly as scripts/eval_dev.py (imported, not copied).

Fixed before the labelled run:
* a variant = list of parts (source a1|b1|env, block subset, L-mode set, D-mode set, weight).  One part -> cosine of
  the z-scored vector (as eval_dev).  Several parts -> each part z-scored and L2-normalised separately, weighted
  block cosine sum_b w_b cos_b / sum_b w_b (= FAISS-IP compatible concatenation).
* z-scoring: per mode, on the dev pockets available in that mode (label-free), as eval_dev.
* L-mode metrics on all dev pairs; D-mode on the D-set (both pockets D-matched: coverage >= 0.3 or precision >= 0.5,
  the merged-pocket rule, also used for the unmerged locator U).  Objective = mean of the two cluster-balanced AUCs;
  guard = size-stratified AUC (L-mode log-volume covariates, (5, 20) bins) per mode.
* Joint vertex bootstrap (units = ligand cluster ∪ homology group; B = 1000, seed SEEDS[0]) of cb_L, cb_D, mean,
  strat_L, strat_D and Δmean vs the reference variant (A1 pair_only on the base definitions).
* L<->D agreement (label-free): dev pockets with a D match; parts z-scored on the union of their L and D rows;
  per pocket the AUC of its own D descriptor among all matched dev pockets' D descriptors, scored against its L
  descriptor (mean over pockets; 0.5 = no agreement); also top-1 rate.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from eval_dev import ToughM1Dev, n_bins_for  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.provenance import append_trial, write_result  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402
from pocketcompare.similarity import ZScorer  # noqa: E402

DR = ROOT / "data/processed/descriptors/tough_m1/defrob"
OUT = ROOT / "results/explore/definition_robustness"
B_BOOT = 1000
A1_LAYOUT = {b["name"]: (b["start"], b["stop"]) for b in json.loads((DR / "a1_layout.json").read_text())} \
    if (DR / "a1_layout.json").exists() else {}
ENV_LAYOUT = {b["name"]: (b["start"], b["stop"]) for b in json.loads((DR / "env_layout.json").read_text())} \
    if (DR / "env_layout.json").exists() else {}
TIME_KEY = {"a1": "t_a1", "b1": "t_b1", "env": "t_env"}


# ------------------------------------------------------------------------------------------------ variants
def P(src, blocks=None, L="L_base", D="D_base", w=1.0):
    return {"src": src, "blocks": blocks, "L": L, "D": D, "w": w}


def defs(shaper, dloc="D"):
    return {"L": f"L_{shaper}", "D": f"{dloc}_{shaper}"}


DESC = {  # single-source descriptors (screen + labelled building blocks)
    "a1": ("a1", None), "a1pair": ("a1", ["pair"]), "a1hist": ("a1", ["hist"]), "a1usr": ("a1", ["usr"]),
    "a1glob": ("a1", ["glob"]), "a1nosize": ("a1", ["hist", "pair", "usr", "glob"]),
    "b1": ("b1", None), "env": ("env", None), "envmean": ("env", ["env_mean"]), "envbur": ("env", ["env_bur"]),
    "envhist": ("env", ["env_hist"]),
}
DEFS = {"base": defs("base"), "baseU": defs("base", "U")}
for _s in ("res", "sph6", "sph8", "sph10", "core8"):
    DEFS[_s] = defs(_s)
    DEFS[_s + "U"] = defs(_s, "U")


def single(desc, d):
    src, blocks = DESC[desc]
    return [P(src, blocks, **DEFS[d])]


def variant_parts(name: str):
    """'<desc>@<def>' or '+'-joined parts, each optionally '*w' weighted: 'a1pair@base+env@sph8U*0.5'."""
    parts = []
    for tok in name.split("+"):
        w = 1.0
        if "*" in tok:
            tok, ws = tok.split("*")
            w = float(ws)
        desc, d = tok.split("@")
        p = single(desc, d)[0]
        p["w"] = w
        parts.append(p)
    return parts


# ------------------------------------------------------------------------------------------------ data
_CACHE: dict = {}


def load_set(name):
    if name not in _CACHE:
        _CACHE[name] = dict(np.load(DR / f"{name}.npz"))
    return _CACHE[name]


def part_matrix(part, mode, rows):
    z = load_set(part[mode])
    M = z[part["src"]][rows].astype(np.float64)
    if part["blocks"]:
        lay = A1_LAYOUT if part["src"] == "a1" else ENV_LAYOUT
        M = np.concatenate([M[:, slice(*lay[b])] for b in part["blocks"]], 1)
    return M


def embed_parts(mats, weights, fit_rows):
    """Per part z-score (fit on ``fit_rows``), L2-normalise, scale by sqrt(w / sum w); concatenate."""
    out = []
    ws = np.asarray(weights, float)
    for M, w in zip(mats, ws):
        Z = ZScorer.fit(M[fit_rows]).transform(M)
        n = np.linalg.norm(Z, axis=1, keepdims=True)
        out.append(Z / np.where(n > 0, n, 1.0) * np.sqrt(w / ws.sum()))
    return np.concatenate(out, 1)


def mode_scores(parts, mode, ds, rows, avail):
    mats = [part_matrix(p, mode, rows) for p in parts]
    ok = avail.copy()
    for M in mats:
        ok &= np.isfinite(M).any(1)   # partial NaN -> 0 after z-scoring (as eval_dev)
    E = embed_parts(mats, [p["w"] for p in parts], np.flatnonzero(ok))
    s = np.full(len(ds.ia), np.nan)
    m = ok[ds.ia] & ok[ds.ib]
    s[m] = (E[ds.ia[m]] * E[ds.ib[m]]).sum(1)
    return s, ok, sum(M.shape[1] for M in mats)


def cross_scores(parts, ds, rows, dm):
    """Cross-mode pair score 0.5 * (cos(L_a, D_b) + cos(D_a, L_b)); parts z-scored on the union of the L rows and
    the D rows of the dev pockets (as ``agreement``).  NaN unless both pockets are D-matched."""
    mL = [part_matrix(p, "L", rows) for p in parts]
    mD = [part_matrix(p, "D", rows) for p in parts]
    ok = dm.copy()
    for M in mL + mD:
        ok &= np.isfinite(M).any(1)
    n = len(rows)
    fit = np.concatenate([np.flatnonzero(ok), n + np.flatnonzero(ok)])
    E = embed_parts([np.concatenate([a, b]) for a, b in zip(mL, mD)], [p["w"] for p in parts], fit)
    EL, ED = E[:n], E[n:]
    s = np.full(len(ds.ia), np.nan)
    m = ok[ds.ia] & ok[ds.ib]
    a, b = ds.ia[m], ds.ib[m]
    s[m] = 0.5 * ((EL[a] * ED[b]).sum(1) + (ED[a] * EL[b]).sum(1))
    return s


def agreement(parts, rows, dm):
    """Label-free L<->D agreement over D-matched dev pockets (see module docstring)."""
    mL = [part_matrix(p, "L", rows) for p in parts]
    mD = [part_matrix(p, "D", rows) for p in parts]
    ok = dm.copy()
    for M in mL + mD:
        ok &= np.isfinite(M).any(1)   # partial NaN -> 0 after z-scoring (as eval_dev)
    idx = np.flatnonzero(ok)
    n = len(idx)
    stacked = [np.concatenate([a[idx], b[idx]]) for a, b in zip(mL, mD)]
    E = embed_parts(stacked, [p["w"] for p in parts], np.arange(2 * n))
    EL, ED = E[:n], E[n:]
    S = EL @ ED.T
    d = np.diag(S)
    off = ~np.eye(n, dtype=bool)
    gt = ((S < d[:, None]) & off).sum(1) + 0.5 * ((S == d[:, None]) & off).sum(1)
    auc = gt / (n - 1)
    top1 = (S.argmax(1) == np.arange(n)).mean()
    return {"agree_auc": float(auc.mean()), "agree_top1": float(top1), "agree_n": int(n)}


def times(parts, rows, dm):
    t = {}
    for mode, m in (("L", np.ones(len(rows), bool)), ("D", dm)):
        tot = np.zeros(int(m.sum()))
        seen = set()
        for p in parts:
            z = load_set(p[mode])
            for k in ("t_shape", TIME_KEY[p["src"]]):
                if (p[mode], k) in seen:
                    continue
                seen.add((p[mode], k))
                tot += np.nan_to_num(z[k][rows][m])
        t[f"ms_{mode}"] = float(np.median(tot))
        t[f"ms_{mode}_p90"] = float(np.percentile(tot, 90))
    return t


# ------------------------------------------------------------------------------------------------ main
def setup():
    ds = ToughM1Dev().load()
    ids = pd.read_parquet(DR / "ids.parquet")
    pos = pd.Series(np.arange(len(ids)), index=ids.pocket_id)
    rows = pos.loc[ds.pockets.pocket_id].to_numpy()
    return ds, rows


def cmd_screen(args):
    ds, rows = setup()       # loads pairs too, but the screen uses no label (only pockets.d_match)
    dm = ds.pockets.d_match.to_numpy()
    recs = []
    for d in DEFS:
        for desc in DESC:
            parts = single(desc, d)
            a = agreement(parts, rows, dm)
            recs.append({"def": d, "desc": desc, **a, **times(parts, rows, dm),
                         "vol_L": float(np.nanmedian(load_set(DEFS[d]["L"])["vol_A3"][rows])),
                         "vol_D": float(np.nanmedian(load_set(DEFS[d]["D"])["vol_A3"][rows][dm]))})
        print(d, " ".join(f"{r['desc']}={r['agree_auc']:.3f}" for r in recs if r["def"] == d), flush=True)
    df = pd.DataFrame(recs)
    OUT.mkdir(parents=True, exist_ok=True)
    write_result(OUT / "screen_agreement.parquet", df, script=__file__, args=sys.argv, config={"defs": DEFS, "desc": DESC},
                 inputs=[DR / "ids.parquet"], seed=None, device="cpu")
    print(df.pivot(index="def", columns="desc", values="agree_auc").round(3).to_string())


def _boot_task(a):
    key, y, sL, sD, rL, rD, dset, pc, cov, ci, cj, B, seed, sX = a
    nb_L, nb_D = n_bins_for(y), n_bins_for(y[dset])

    def stats(s_L, s_D, w):
        cbL = ev.cluster_balanced_auc(y, s_L, pc, w)["auc_cb"]
        cbD = ev.cluster_balanced_auc(y[dset], s_D[dset], pc[dset], w[dset])["auc_cb"]
        stL = ev.stratified_auc(y, s_L, cov, w, n_bins=nb_L)["auc_strat"]
        stD = ev.stratified_auc(y[dset], s_D[dset], cov[dset], w[dset], n_bins=nb_D)["auc_strat"]
        return cbL, cbD, stL, stD

    def fn(w):
        cbL, cbD, stL, stD = stats(sL, sD, w)
        r = stats(rL, rD, w)
        out = [cbL, cbD, 0.5 * (cbL + cbD), stL, stD, 0.5 * (stL + stD), 0.5 * (cbL + cbD) - 0.5 * (r[0] + r[1]),
               0.5 * (stL + stD) - 0.5 * (r[2] + r[3])]
        if sX is not None:
            out += [ev.cluster_balanced_auc(y[dset], sX[dset], pc[dset], w[dset])["auc_cb"],
                    ev.stratified_auc(y[dset], sX[dset], cov[dset], w[dset], n_bins=nb_D)["auc_strat"]]
        return out

    names = ["cb_L", "cb_D", "cb_mean", "strat_L", "strat_D", "strat_mean", "d_cb_mean_vs_ref", "d_strat_mean_vs_ref"]
    if sX is not None:
        names += ["cb_X", "strat_X"]
    res = ev.vertex_bootstrap_generic(fn, ci, cj, B=B, seed=seed, names=names)
    return key, {r.name: r for r in res}


def _pool_init():
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(1)
    except ImportError:
        pass


REF = "a1pair@base"


def cmd_eval(args):
    ds, rows = setup()
    P_ = ds.pockets
    y = ds.pairs.y.to_numpy().astype(bool)
    dm = P_.d_match.to_numpy()
    dset = dm[ds.ia] & dm[ds.ib]
    ci, cj = P_.unit.to_numpy()[ds.ia], P_.unit.to_numpy()[ds.ib]
    cov = ev.size_covariates(P_.logv_L.to_numpy()[ds.ia], P_.logv_L.to_numpy()[ds.ib])
    pc = ds.pos_cluster
    allp = np.ones(len(P_), bool)
    names = [v for v in args.variants.split(",") if v]
    if REF not in names:
        names = [REF] + names
    S = {}
    meta = {}
    for v in names:
        parts = variant_parts(v)
        sL, okL, dim = mode_scores(parts, "L", ds, rows, allp)
        sD, okD, _ = mode_scores(parts, "D", ds, rows, dm)
        if np.isnan(sL).any():   # L-mode must be complete; fall back to the minimum (worst case) and record it
            meta.setdefault(v, {})["n_missing_L"] = int(np.isnan(sL).sum())
        sD_eval = np.where(dset, sD, np.nan)
        if np.isnan(sD_eval[dset]).any():
            meta.setdefault(v, {})["n_missing_D"] = int(np.isnan(sD_eval[dset]).sum())
        sX = None
        if args.cross:
            sX = cross_scores(parts, ds, rows, dm)
            sX = np.where(dset, np.nan_to_num(sX, nan=np.nanmin(sX[dset])), np.nan)
        S[v] = (np.nan_to_num(sL, nan=np.nanmin(sL)), np.nan_to_num(sD_eval, nan=np.nanmin(sD_eval[dset])), dim, parts,
                sX)
    rL, rD = S[REF][0], S[REF][1]
    tasks = [(v, y, s[0], s[1], rL, rD, dset, pc, cov, ci, cj, args.B, SEEDS[0], s[4]) for v, s in S.items()]
    t0 = time.time()
    with mp.get_context("spawn").Pool(min(args.threads, len(tasks)), initializer=_pool_init) as pool:
        boot = dict(pool.imap_unordered(_boot_task, tasks))
    print(f"bootstrap {len(tasks)} variants in {time.time() - t0:.0f}s", flush=True)
    recs = []
    for v, (sL, sD, dim, parts, sX) in S.items():
        b = boot[v]
        rec = {"variant": v, "dims": dim, "n_pairs_L": int(len(y)), "n_pairs_D": int(dset.sum()),
               "auc_L": ev.roc_auc(y, sL), "auc_D": ev.roc_auc(y[dset], sD[dset]), **meta.get(v, {})}
        for k, r in b.items():
            rec[k] = r.estimate
            rec[k + "_lo"] = r.ci_low
            rec[k + "_hi"] = r.ci_high
            rec[k + "_se"] = r.se
        rec.update(agreement(parts, rows, dm))
        rec.update(times(parts, rows, dm))
        recs.append(rec)
    df = pd.DataFrame(recs)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = args.tag
    path = OUT / f"eval_{tag}.parquet"
    cfg = {"variants": {v: S[v][3] for v in S}, "B": args.B, "seed": SEEDS[0], "ref": REF}
    write_result(path, df, script=__file__, args=sys.argv, config=cfg, inputs=list(ds.inputs) + [DR / "ids.parquet"],
                 seed=SEEDS[0], device="cpu")
    logged = set(args.logged.split(",")) if args.logged else set()
    if not args.no_trials:
        for r in recs:
            if r["variant"] == REF and args.skip_ref_trial:
                continue
            for mode in (("L", "D", "X") if args.cross else ("L", "D")):
                if mode != "X" and r["variant"] in logged:
                    continue           # L/D already logged in an earlier batch (identical numbers); log X only
                if mode == "X":
                    append_trial("A1R-explore", {"variant": r["variant"], "parts": S[r["variant"]][3], "mode": "X",
                                                 "pairset": "D-set, cross-mode 0.5*(cos(L_a,D_b)+cos(D_a,L_b))",
                                                 "B": args.B, "seed": SEEDS[0], "variant_tag": tag},
                                 "tough_m1_dev", {"auc_cb": r["cb_X"], "auc_cb_lo": r["cb_X_lo"], "auc_cb_hi": r["cb_X_hi"],
                                                  "auc_strat": r["strat_X"], "auc_strat_lo": r["strat_X_lo"],
                                                  "auc_strat_hi": r["strat_X_hi"], "n_pairs": r["n_pairs_D"],
                                                  "dims": r["dims"]}, path)
                    continue
                m = {"auc": r[f"auc_{mode}"], "auc_cb": r[f"cb_{mode}"], "auc_cb_lo": r[f"cb_{mode}_lo"],
                     "auc_cb_hi": r[f"cb_{mode}_hi"], "auc_strat": r[f"strat_{mode}"],
                     "auc_strat_lo": r[f"strat_{mode}_lo"], "auc_strat_hi": r[f"strat_{mode}_hi"],
                     "cb_mean_LD": r["cb_mean"], "cb_mean_LD_lo": r["cb_mean_lo"], "cb_mean_LD_hi": r["cb_mean_hi"],
                     "d_cb_mean_vs_ref": r["d_cb_mean_vs_ref"], "agree_auc": r["agree_auc"],
                     "n_pairs": r[f"n_pairs_{mode}"], "dims": r["dims"], "ms_per_pocket": r[f"ms_{mode}"]}
                append_trial("A1R-explore", {"variant": r["variant"], "parts": S[r["variant"]][3], "mode": mode,
                                             "pairset": "all dev pairs" if mode == "L" else "D-set (both D-matched)",
                                             "B": args.B, "seed": SEEDS[0], "ref": REF, "variant_tag": tag},
                             "tough_m1_dev", m, path)
    cols = ["variant", "dims", "cb_L", "cb_D", "cb_mean", "cb_mean_lo", "cb_mean_hi", "d_cb_mean_vs_ref",
            "d_cb_mean_vs_ref_lo", "d_cb_mean_vs_ref_hi", "strat_L", "strat_D", "agree_auc", "ms_L", "ms_D"]
    cols += [c for c in ("cb_X", "strat_X") if c in df]
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(df[cols].round(3).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("screen")
    e = sub.add_parser("eval")
    e.add_argument("--variants", required=True)
    e.add_argument("--tag", required=True)
    e.add_argument("--B", type=int, default=B_BOOT)
    e.add_argument("--threads", type=int, default=16)
    e.add_argument("--no-trials", action="store_true")
    e.add_argument("--logged", default="", help="variants whose L/D rows were logged earlier (log X rows only)")
    e.add_argument("--cross", action="store_true", help="also cross-mode (L query vs D target) metrics on the D-set")
    e.add_argument("--skip-ref-trial", action="store_true", help="reference already logged in an earlier batch")
    a = ap.parse_args()
    os.environ["POCKETCOMPARE_THREADS"] = "16"
    {"screen": cmd_screen, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
