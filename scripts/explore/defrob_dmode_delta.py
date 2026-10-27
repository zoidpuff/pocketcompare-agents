#!/usr/bin/env python
"""Paired D-mode deltas (cb-AUC, stratified AUC; same vertex-bootstrap replicates, B = 1000) of the D11 finalists
vs A1 pair_only (base) and vs B1 (base, the C1-D comparator).  Variants were already logged by defrob_eval.py; this
adds the paired D-mode Δ only (one summary trials row)."""
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "scripts/explore")]
import defrob_eval as R  # noqa: E402
from eval_dev import n_bins_for  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.provenance import append_trial, write_result  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402

FINAL = ["a1@baseU+env@sph8U", "a1@sph8U+env@sph8U", "env@sph8U", "a1@baseU+a1@sph8U+env@sph8U"]
REFS = ["a1pair@base", "b1@base"]


def task(a):
    v, y, s, refs, pc, cov, ci, cj = a
    nb = n_bins_for(y)

    def fn(w):
        out = []
        for r in refs:
            out += [ev.cluster_balanced_auc(y, s, pc, w)["auc_cb"] - ev.cluster_balanced_auc(y, r, pc, w)["auc_cb"],
                    ev.stratified_auc(y, s, cov, w, n_bins=nb)["auc_strat"]
                    - ev.stratified_auc(y, r, cov, w, n_bins=nb)["auc_strat"]]
        return out
    names = [f"d_{m}_D_vs_{r}" for r in REFS for m in ("cb", "strat")]
    return v, ev.vertex_bootstrap_generic(fn, ci, cj, B=1000, seed=SEEDS[0], names=names, diff=True)


if __name__ == "__main__":
    ds, rows = R.setup()
    P = ds.pockets
    dm = P.d_match.to_numpy()
    m = dm[ds.ia] & dm[ds.ib]
    y = ds.pairs.y.to_numpy().astype(bool)[m]
    sc = {v: R.mode_scores(R.variant_parts(v), "D", ds, rows, dm)[0][m] for v in FINAL + REFS}
    ci, cj = P.unit.to_numpy()[ds.ia][m], P.unit.to_numpy()[ds.ib][m]
    cov = ev.size_covariates(P.logv_L.to_numpy()[ds.ia], P.logv_L.to_numpy()[ds.ib])[m]
    tasks = [(v, y, sc[v], [sc[r] for r in REFS], ds.pos_cluster[m], cov, ci, cj) for v in FINAL]
    with mp.get_context("spawn").Pool(len(tasks)) as pool:
        res = dict(pool.map(task, tasks))
    recs = [{"variant": v, "stat": r.name, "estimate": r.estimate, "lo": r.ci_low, "hi": r.ci_high,
             "p_one_sided": r.p_value} for v, rr in res.items() for r in rr]
    df = pd.DataFrame(recs)
    out = R.OUT / "dmode_deltas.parquet"
    write_result(out, df, script=__file__, args=sys.argv, config={"final": FINAL, "refs": REFS, "B": 1000},
                 inputs=list(ds.inputs), seed=SEEDS[0], device="cpu")
    append_trial("A1R-explore", {"analysis": "paired D-mode deltas of finalists", "final": FINAL, "refs": REFS,
                                 "B": 1000, "seed": SEEDS[0]}, "tough_m1_dev",
                 {f"{r['variant']}|{r['stat']}": round(r["estimate"], 4) for r in recs}, out)
    print(df.round(3).to_string(index=False))
