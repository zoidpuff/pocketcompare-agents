"""The single frozen evaluation module of pocketcompare (DESIGN §4, §5).

Every number in a report is computed by a function in this file; its sha256 is recorded in every result sidecar
(``pocketcompare.provenance``).  Changing this file after the first result invalidates all results.

Conventions
-----------
* ``y`` is a binary label per pair (1 = positive, "similar"), ``s`` a real score (higher = more similar), ``w`` an
  optional non-negative pair weight (default 1).  All metrics are *weighted* metrics: a pair with weight 2 counts
  exactly like two copies of that pair.
* Ties count one half (Mann-Whitney convention), i.e. the ROC curve runs diagonally through a block of tied scores.
* **Missing scores** (method failures) are ``NaN``.  The low-level metric functions *refuse* NaN (``ValueError``) so
  nothing is ever dropped silently.  Use :func:`apply_missing_policy` / :func:`common_set` / :func:`worst_case` /
  :func:`min_impute`, which return the transformed arrays *and* the counts of what was done, or the high-level
  :func:`summarize` / :func:`paired_bootstrap` which take ``missing=...`` and report counts in their output.
  - ``"common"``  : keep only pairs where every compared method has a score (primary for paired comparisons).
  - ``"worst"``   : worst-case bound: a missing positive scores ``-inf``, a missing negative ``+inf``.
  - ``"min"``     : deployment figure: every missing score is ``-inf`` (minimum similarity).  Not neutral: it rewards
                    failing on negatives (reviews/round1_statistics.md M5); report next to ``common`` and ``worst``.
  - ``"raise"``   : (default) refuse NaN.

Metric definitions (all support pair weights)
---------------------------------------------
* ROC-AUC: P(s+ > s-) + 0.5 P(s+ = s-) under the weighted pair distributions (equals sklearn ``roc_auc_score`` with
  ``sample_weight``).
* Average precision (PR-AUC): AP = sum_k (R_k - R_{k-1}) P_k over distinct score thresholds in descending order
  (step-function, no interpolation; equals sklearn ``average_precision_score``).  Reported with the (weighted)
  prevalence pi = W+ / (W+ + W-) and AP lift = AP / pi (AP of a random scorer is ~pi).  ``target="neg"`` scores AP
  with negatives as the target class (useful when positives dominate, e.g. Vertex).
* Partial ROC-AUC over FPR in [0, max_fpr] (default 0.1), trapezoidal with linear interpolation at max_fpr.  Both
  are returned: ``pauc_raw`` = the raw area (range [0, max_fpr]) and ``pauc_mcclish`` = McClish (1989)
  standardisation 0.5 * (1 + (A - A_min)/(A_max - A_min)) with A_min = max_fpr^2/2 (chance) and A_max = max_fpr,
  so 0.5 = chance and 1 = perfect (identical to sklearn ``roc_auc_score(max_fpr=...)``).  **McClish is the headline
  pAUC**; raw is kept for completeness.
* Cluster-balanced AUC (:func:`cluster_balanced_auc`): every positive pair carries a *positive cluster* label (on
  TOUGH-M1 the ligand cluster = connected component of the positive graph, shared by both pockets).  Each positive
  pair gets weight w / W+_c where W+_c is the total weight of positives in its cluster; negatives keep their weight
  (uniform by default).  Hence every positive cluster contributes the same total weight and

      AUC_cb = (1/C) * sum_c AUC(positives of cluster c  vs  all negatives),

  the unweighted mean of per-cluster AUCs (identity tested).  Optionally ``neg_cluster`` balances negatives in the
  same way (each negative group gets equal total weight).
* Per-cluster AUC (:func:`per_cluster_auc`): for the k largest positive clusters (by positive weight), AUC of that
  cluster's positives against all negatives (default; consistent with AUC_cb) or against only the negatives that
  involve the cluster (``negatives="involving"``, needs per-pair cluster labels ``ci``, ``cj``).
* Size-stratified AUC (:func:`stratified_auc`; DESIGN round 2): generic API = covariate array (n_pairs x k) +
  number of quantile bins per column.  Each column is cut into quantile bins with edges from the evaluated pairs
  (both classes, unweighted quantiles; duplicate edges merged) and the bins are crossed.  **Default (headline)
  strata: quintiles of the pair's mean log-volume x quintiles of |delta log-volume|** (:func:`size_covariates`,
  ``n_bins=(5, 5)``).  The AUC is computed inside each stratum with >= 1 positive and >= 1 negative; strata lacking
  a class are dropped and counted (strata and pairs, and the positive weight lost).  Strata AUCs are averaged
  with weight proportional to the stratum's positive weight W+_h (default ``weighting="pos"``; the Janes & Pepe
  2008 covariate-adjusted AUC: the probability that a positive outranks a negative of the same stratum, averaged
  over the positives' covariate distribution).  ``"min"`` (min(W+_h, W-_h)) and ``"equal"`` exist as
  sensitivity options.
* Retrieval (:func:`retrieval_metrics`): per query, rank r of the best-scoring true hit among all candidates of the
  query; ties are broken **pessimistically** (r = 1 + #non-hits with score >= best hit score), so a constant scorer
  gets no credit.  top-k = mean(r <= k), MRR = mean(1/r) over queries with >= 1 hit (queries without hits are
  counted and excluded).

Uncertainty: two-way "vertex" cluster bootstrap
-----------------------------------------------
Each pair (i, j) has cluster labels (c_i, c_j) (ligand cluster on TOUGH-M1, homology group on BLiPS/PPI).  One
replicate draws K clusters with replacement from the K distinct clusters (counts n_c ~ Multinomial(K, 1/K)); a
between-unit pair (c_i != c_j) gets weight w * n_{c_i} * n_{c_j}; **a within-unit pair (c_i == c_j = u) gets
weight w * n_u** (DESIGN round 2: the pair is internal to one resampled unit and is copied once per copy of that
unit, not n_u^2 times); pairs with an undrawn unit drop out.  The weighted metric is computed per replicate;
replicates with zero positive or zero negative weight are *degenerate*, counted and excluded.  CIs are percentile
intervals (default 95 %); the one-sided p-value for H0: Delta <= 0 is (1 + #{Delta_b <= 0}) / (B_valid + 1).  The
paired version uses identical replicate weights for all methods.  Replicate counts come from
``numpy.random.default_rng(seed)`` (default SEEDS[0]) generated in fixed-size chunks, so results do not depend on
the number of threads.  Fast path (AUC, AP): pairs are sorted once per method; one replicate is a single O(n)
pass over the sorted pairs with on-the-fly weights (numba, parallel over replicates).  Any other metric can be
bootstrapped with identical replicate weights via :func:`vertex_bootstrap_generic` (slow, Python loop).
:func:`macro_paired_bootstrap` (claim C2) bootstraps several subsets independently (seed stream
``[seed, subset_index]``) and averages the per-subset Delta replicate-by-replicate (same replicate index b); the
independence assumption is exact only if the subsets share no units.
"""
from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass, field
from typing import Callable, Mapping, Sequence

import numpy as np

from pocketcompare.seeds import SEEDS

try:  # numba is in the project env; a pure-numpy fallback keeps the module importable without it.
    import numba
    from numba import njit, prange

    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    HAVE_NUMBA = False

DEFAULT_B = 2000
DEFAULT_SEED = SEEDS[0]
_CHUNK = 128  # replicates per RNG chunk (fixed => results independent of thread count)

__all__ = [
    "roc_auc", "average_precision", "partial_auc", "binary_metrics", "cluster_balanced_auc", "per_cluster_auc",
    "stratified_auc", "retrieval_metrics", "missing_summary", "common_set", "worst_case", "min_impute",
    "apply_missing_policy", "vertex_bootstrap", "paired_bootstrap", "vertex_bootstrap_generic",
    "bootstrap_counts", "holm", "mde", "mde_scaled", "summarize", "BootstrapResult", "size_covariates",
    "macro_paired_bootstrap", "pair_bootstrap_weights", "wider_ci",
]


# ----------------------------------------------------------------------------------------------------- validation
def _as_arrays(y, s, w=None, *, allow_nan=False):
    y = np.asarray(y)
    s = np.asarray(s, dtype=np.float64)
    if y.ndim != 1 or s.shape != y.shape:
        raise ValueError(f"y and s must be 1-D of equal length, got {y.shape} and {s.shape}")
    if y.dtype != bool:
        u = np.unique(y)
        if not np.all(np.isin(u, (0, 1))):
            raise ValueError(f"labels must be binary 0/1, got values {u[:10]}")
    y = y.astype(bool)
    if not allow_nan and np.isnan(s).any():
        raise ValueError(f"{int(np.isnan(s).sum())} NaN scores: choose a missing-score policy "
                         "(common_set / worst_case / min_impute) instead of dropping silently")
    if w is None:
        w = np.ones(len(y), dtype=np.float64)
    else:
        w = np.asarray(w, dtype=np.float64)
        if w.shape != y.shape:
            raise ValueError("weights must have the same shape as y")
        if not np.all(np.isfinite(w)) or (w < 0).any():
            raise ValueError("weights must be finite and >= 0")
    return y, s, w


def _need_both(y, w):
    wp, wn = float(w[y].sum()), float(w[~y].sum())
    if wp <= 0 or wn <= 0:
        raise ValueError(f"need positive and negative weight > 0 (W+={wp}, W-={wn})")
    return wp, wn


# ------------------------------------------------------------------------------------------------- core metrics
def _grouped_desc(y, s, w):
    """Sort by descending score; return per tie-group positive/negative weights and cumulative sums."""
    order = np.argsort(-s, kind="mergesort")
    ss = s[order]
    wp_sorted = np.where(y[order], w[order], 0.0)
    wn_sorted = np.where(y[order], 0.0, w[order])
    end = np.ones(len(ss), dtype=bool)
    end[:-1] = ss[1:] != ss[:-1]
    tp = np.cumsum(wp_sorted)[end]
    fp = np.cumsum(wn_sorted)[end]
    pos_g = np.diff(tp, prepend=0.0)
    neg_g = np.diff(fp, prepend=0.0)
    return tp, fp, pos_g, neg_g


def roc_auc(y, s, w=None) -> float:
    """Weighted ROC-AUC with ties = 1/2."""
    y, s, w = _as_arrays(y, s, w)
    wp, wn = _need_both(y, w)
    tp, fp, pos_g, neg_g = _grouped_desc(y, s, w)
    fp_before = fp - neg_g
    # pairs where the positive is NOT ranked strictly above the negative, ties counted 1/2
    bad = float(np.sum(pos_g * (fp_before + 0.5 * neg_g)))
    return 1.0 - bad / (wp * wn)


def average_precision(y, s, w=None, *, target: str = "pos") -> dict:
    """Weighted average precision (step-function PR-AUC) with prevalence and lift.

    ``target="neg"`` evaluates AP with negatives as the target class (scores negated)."""
    y, s, w = _as_arrays(y, s, w)
    if target == "neg":
        y, s = ~y, -s
    elif target != "pos":
        raise ValueError("target must be 'pos' or 'neg'")
    wp, wn = _need_both(y, w)
    tp, fp, pos_g, _ = _grouped_desc(y, s, w)
    den = tp + fp
    prec = np.divide(tp, den, out=np.zeros_like(tp), where=den > 0)
    ap = float(np.sum(pos_g * prec) / wp)
    prev = wp / (wp + wn)
    return {"ap": ap, "prevalence": prev, "ap_lift": ap / prev, "target": target}


def partial_auc(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
    """Partial ROC-AUC on FPR in [0, max_fpr]: raw area and McClish-standardised value (headline)."""
    if not 0 < max_fpr <= 1:
        raise ValueError("max_fpr must be in (0, 1]")
    y, s, w = _as_arrays(y, s, w)
    wp, wn = _need_both(y, w)
    tp, fp, _, _ = _grouped_desc(y, s, w)
    fpr = np.concatenate([[0.0], fp / wn])
    tpr = np.concatenate([[0.0], tp / wp])
    fpr[-1] = 1.0
    stop = int(np.searchsorted(fpr, max_fpr, side="right"))
    if stop >= len(fpr):
        raw = float(np.trapezoid(tpr, fpr))
    else:
        t_at = np.interp(max_fpr, fpr[stop - 1:stop + 1], tpr[stop - 1:stop + 1])
        raw = float(np.trapezoid(np.append(tpr[:stop], t_at), np.append(fpr[:stop], max_fpr)))
    a_min, a_max = 0.5 * max_fpr ** 2, max_fpr
    mcclish = 0.5 * (1 + (raw - a_min) / (a_max - a_min))
    return {"pauc_mcclish": mcclish, "pauc_raw": raw, "max_fpr": max_fpr}


def binary_metrics(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
    """ROC-AUC, AP (+prevalence, lift), pAUC (McClish + raw) and counts for one score vector (no NaN)."""
    y, s, w = _as_arrays(y, s, w)
    out = {"n": int(len(y)), "n_pos": int(y.sum()), "n_neg": int((~y).sum()),
           "w_pos": float(w[y].sum()), "w_neg": float(w[~y].sum()), "auc": roc_auc(y, s, w)}
    ap = average_precision(y, s, w)
    out.update(ap=ap["ap"], prevalence=ap["prevalence"], ap_lift=ap["ap_lift"])
    pa = partial_auc(y, s, w, max_fpr=max_fpr)
    out.update(pauc_mcclish=pa["pauc_mcclish"], pauc_raw=pa["pauc_raw"], max_fpr=max_fpr)
    return out


# ---------------------------------------------------------------------------------------- cluster-aware metrics
def _balance(labels, mask, w):
    """Return w with entries in ``mask`` rescaled so that each label group sums to 1 (others unchanged)."""
    out = w.copy()
    lab = np.asarray(labels)[mask]
    codes, uniq = _factorize(lab)
    tot = np.bincount(codes, weights=w[mask], minlength=len(uniq))
    sub = np.divide(w[mask], tot[codes], out=np.zeros(mask.sum()), where=tot[codes] > 0)
    out[mask] = sub
    return out, int((tot > 0).sum())


def _factorize(a):
    a = np.asarray(a)
    uniq, codes = np.unique(a, return_inverse=True)
    return codes.reshape(-1), uniq


def cluster_balanced_auc(y, s, pos_cluster, w=None, *, neg_cluster=None) -> dict:
    """Cluster-balanced ROC-AUC: each positive cluster has equal total weight (see module docstring).

    ``pos_cluster``: cluster id per pair (only read for positives).  ``neg_cluster``: optional group id per pair,
    read for negatives; if given, each negative group also gets equal total weight."""
    y, s, w = _as_arrays(y, s, w)
    wb, n_pc = _balance(pos_cluster, y, w)
    n_nc = None
    if neg_cluster is not None:
        wb, n_nc = _balance(neg_cluster, ~y, wb)
    return {"auc_cb": roc_auc(y, s, wb), "n_pos_clusters": n_pc, "n_neg_groups": n_nc}


def per_cluster_auc(y, s, pos_cluster, w=None, *, k: int = 10, negatives: str = "all", ci=None, cj=None):
    """AUC of each of the k largest positive clusters (by positive weight) against the negatives.

    ``negatives="all"``: all negatives; ``"involving"``: only negatives with ci == c or cj == c (needs ci, cj).
    Returns a pandas DataFrame sorted by cluster size (cluster, n_pos, w_pos, n_neg, auc)."""
    import pandas as pd

    y, s, w = _as_arrays(y, s, w)
    pc = np.asarray(pos_cluster)
    codes, uniq = _factorize(pc[y])
    wpos = np.bincount(codes, weights=w[y], minlength=len(uniq))
    top = np.argsort(-wpos, kind="mergesort")[:k]
    rows = []
    for t in top:
        c = uniq[t]
        pmask = y & (pc == c)
        if negatives == "all":
            nmask = ~y
        elif negatives == "involving":
            if ci is None or cj is None:
                raise ValueError("negatives='involving' needs ci and cj")
            nmask = ~y & ((np.asarray(ci) == c) | (np.asarray(cj) == c))
        else:
            raise ValueError("negatives must be 'all' or 'involving'")
        m = pmask | nmask
        ok = w[nmask].sum() > 0 and w[pmask].sum() > 0
        rows.append({"cluster": c, "n_pos": int(pmask.sum()), "w_pos": float(w[pmask].sum()),
                     "n_neg": int(nmask.sum()), "auc": roc_auc(y[m], s[m], w[m]) if ok else np.nan})
    return pd.DataFrame(rows)


def _quantile_bins(x, n_bins):
    edges = np.unique(np.quantile(x, np.linspace(0, 1, n_bins + 1)))
    inner = edges[1:-1]
    return np.searchsorted(inner, x, side="right"), edges


def size_covariates(log_vol_a, log_vol_b) -> np.ndarray:
    """Headline stratification covariates (n x 2): mean log-volume of the pair and |delta log-volume|."""
    a = np.asarray(log_vol_a, dtype=np.float64)
    b = np.asarray(log_vol_b, dtype=np.float64)
    return np.column_stack([0.5 * (a + b), np.abs(a - b)])


def stratified_auc(y, s, covariate, w=None, *, n_bins: int | Sequence[int] = (5, 5),
                   weighting: str = "pos") -> dict:
    """Covariate-stratified ROC-AUC (see module docstring).

    ``covariate``: (n,) or (n, k); ``n_bins``: int (same for every column) or one int per column.  Default:
    5 x 5 strata on :func:`size_covariates`, weights proportional to stratum positive weight.  Returns the
    stratified AUC, the per-stratum table and counts of dropped strata / pairs / positive weight."""
    y, s, w = _as_arrays(y, s, w)
    if weighting not in ("pos", "min", "equal"):
        raise ValueError("weighting must be 'pos', 'min' or 'equal'")
    x = np.asarray(covariate, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[0] != len(y) or not np.all(np.isfinite(x)):
        raise ValueError("covariate must be finite with one row per pair")
    nb = [int(n_bins)] * x.shape[1] if np.isscalar(n_bins) else [int(v) for v in n_bins]
    if len(nb) != x.shape[1]:
        raise ValueError(f"n_bins has {len(nb)} entries for {x.shape[1]} covariate columns")
    strata = np.zeros(len(y), dtype=np.int64)
    edges = []
    for d in range(x.shape[1]):
        b, e = _quantile_bins(x[:, d], nb[d])
        edges.append(e.tolist())
        strata = strata * (nb[d] + 1) + b
    codes, uniq = _factorize(strata)
    table, aucs, wts = [], [], []
    n_dropped_pairs, w_pos_dropped = 0, 0.0
    for h in range(len(uniq)):
        m = codes == h
        wp, wn = float(w[m & y].sum()), float(w[m & ~y].sum())
        row = {"stratum": int(uniq[h]), "n": int(m.sum()), "n_pos": int((m & y).sum()),
               "n_neg": int((m & ~y).sum()), "w_pos": wp, "w_neg": wn, "auc": np.nan}
        if wp > 0 and wn > 0:
            row["auc"] = roc_auc(y[m], s[m], w[m])
            aucs.append(row["auc"])
            wts.append({"min": min(wp, wn), "equal": 1.0, "pos": wp}[weighting])
        else:
            n_dropped_pairs += row["n"]
            w_pos_dropped += wp
        table.append(row)
    if not aucs:
        raise ValueError("no stratum contains both classes")
    wts = np.asarray(wts)
    return {"auc_strat": float(np.dot(aucs, wts) / wts.sum()), "weighting": weighting, "n_bins": nb,
            "n_strata": len(uniq), "n_strata_used": len(aucs), "n_strata_dropped": len(uniq) - len(aucs),
            "n_pairs_dropped": int(n_dropped_pairs), "frac_pos_weight_dropped": w_pos_dropped / float(w[y].sum()),
            "edges": edges, "strata": table}


# ------------------------------------------------------------------------------------------------------ retrieval
def retrieval_metrics(df, *, query_col="query", score_col="score", label_col="label", ks: Sequence[int] = (1, 10),
                      ties: str = "pessimistic") -> dict:
    """Top-k hit rate and MRR from a long query->candidate table (one row per query-candidate pair).

    NaN scores are treated as -inf (counted in ``n_missing``).  ``ties="pessimistic"`` (default) or
    ``"optimistic"``.  Returns summary metrics and a per-query DataFrame with the first-hit rank."""
    import pandas as pd

    d = pd.DataFrame({"q": df[query_col].to_numpy(), "s": np.asarray(df[score_col], dtype=np.float64),
                      "h": np.asarray(df[label_col]).astype(bool)})
    n_missing = int(d["s"].isna().sum())
    d["s"] = d["s"].fillna(-np.inf)
    best = d[d["h"]].groupby("q", sort=True)["s"].max().rename("best")
    n_q = int(d["q"].nunique())
    nh = d[~d["h"]].join(best, on="q", how="inner")
    gt = (nh["s"] > nh["best"]).groupby(nh["q"]).sum()
    eq = (nh["s"] == nh["best"]).groupby(nh["q"]).sum()
    per = best.to_frame()
    per["n_greater"] = gt.reindex(per.index, fill_value=0).astype(int)
    per["n_tied"] = eq.reindex(per.index, fill_value=0).astype(int)
    if ties == "pessimistic":
        per["rank"] = 1 + per["n_greater"] + per["n_tied"]
    elif ties == "optimistic":
        per["rank"] = 1 + per["n_greater"]
    else:
        raise ValueError("ties must be 'pessimistic' or 'optimistic'")
    out = {"n_queries": n_q, "n_queries_with_hit": int(len(per)), "n_queries_no_hit": n_q - int(len(per)),
           "n_missing_scores": n_missing, "ties": ties,
           "mrr": float(np.mean(1.0 / per["rank"])) if len(per) else np.nan}
    for k in ks:
        out[f"top{k}"] = float(np.mean(per["rank"] <= k)) if len(per) else np.nan
    out["per_query"] = per.reset_index().rename(columns={"q": "query"})
    return out


# --------------------------------------------------------------------------------------------- missing scores
def _score_dict(scores) -> dict[str, np.ndarray]:
    if isinstance(scores, Mapping):
        return {str(k): np.asarray(v, dtype=np.float64) for k, v in scores.items()}
    a = np.asarray(scores, dtype=np.float64)
    if a.ndim == 1:
        return {"score": a}
    return {f"m{i}": a[i] for i in range(a.shape[0])}


def missing_summary(y, scores) -> dict:
    """Per method: number and rate of missing (NaN) scores overall, among positives and among negatives."""
    y = np.asarray(y).astype(bool)
    out = {}
    for name, s in _score_dict(scores).items():
        miss = np.isnan(s)
        out[name] = {"n": int(len(s)), "n_missing": int(miss.sum()), "miss_rate": float(miss.mean()),
                     "n_missing_pos": int((miss & y).sum()), "n_missing_neg": int((miss & ~y).sum()),
                     "miss_rate_pos": float((miss & y).sum() / max(y.sum(), 1)),
                     "miss_rate_neg": float((miss & ~y).sum() / max((~y).sum(), 1))}
    return out


def common_set(y, scores) -> tuple[np.ndarray, dict]:
    """Mask of pairs where *all* methods have a finite-or-inf (non-NaN) score, plus counts."""
    y = np.asarray(y).astype(bool)
    sd = _score_dict(scores)
    mask = np.ones(len(y), dtype=bool)
    for s in sd.values():
        mask &= ~np.isnan(s)
    counts = {"n_total": int(len(y)), "n_common": int(mask.sum()), "n_dropped": int((~mask).sum()),
              "n_dropped_pos": int((~mask & y).sum()), "n_dropped_neg": int((~mask & ~y).sum()),
              "per_method": missing_summary(y, sd)}
    return mask, counts


def worst_case(y, s) -> tuple[np.ndarray, dict]:
    """Adversarial imputation: missing positives -> -inf, missing negatives -> +inf (lower bound on AUC/AP)."""
    y = np.asarray(y).astype(bool)
    s = np.asarray(s, dtype=np.float64).copy()
    miss = np.isnan(s)
    s[miss & y] = -np.inf
    s[miss & ~y] = np.inf
    return s, {"n_imputed": int(miss.sum()), "n_imputed_pos": int((miss & y).sum()),
               "n_imputed_neg": int((miss & ~y).sum())}


def min_impute(y, s) -> tuple[np.ndarray, dict]:
    """Deployment imputation: every missing score -> -inf (minimum similarity)."""
    y = np.asarray(y).astype(bool)
    s = np.asarray(s, dtype=np.float64).copy()
    miss = np.isnan(s)
    s[miss] = -np.inf
    return s, {"n_imputed": int(miss.sum()), "n_imputed_pos": int((miss & y).sum()),
               "n_imputed_neg": int((miss & ~y).sum())}


def apply_missing_policy(y, scores, missing: str = "raise"):
    """Apply one policy to all methods jointly.  Returns (mask, {name: scores[mask]}, counts).

    ``mask`` selects the pairs kept (all True except under ``"common"``)."""
    y = np.asarray(y).astype(bool)
    sd = _score_dict(scores)
    if missing == "raise":
        bad = {k: int(np.isnan(v).sum()) for k, v in sd.items() if np.isnan(v).any()}
        if bad:
            raise ValueError(f"NaN scores {bad}: pass missing='common'|'worst'|'min'")
        return np.ones(len(y), bool), sd, {"policy": "raise", "n_total": int(len(y)), "n_kept": int(len(y))}
    if missing == "common":
        mask, counts = common_set(y, sd)
        return mask, {k: v[mask] for k, v in sd.items()}, {"policy": "common", **counts, "n_kept": counts["n_common"]}
    fn = {"worst": worst_case, "min": min_impute}.get(missing)
    if fn is None:
        raise ValueError("missing must be 'raise', 'common', 'worst' or 'min'")
    out, per = {}, {}
    for k, v in sd.items():
        out[k], per[k] = fn(y, v)
    return np.ones(len(y), bool), out, {"policy": missing, "n_total": int(len(y)), "n_kept": int(len(y)),
                                        "imputed": per, "per_method": missing_summary(y, sd)}


# -------------------------------------------------------------------------------------------- vertex bootstrap
def _encode_clusters(ci, cj):
    ci, cj = np.asarray(ci), np.asarray(cj)
    if ci.shape != cj.shape or ci.ndim != 1:
        raise ValueError("ci and cj must be 1-D of equal length")
    codes, uniq = _factorize(np.concatenate([ci, cj]))
    n = len(ci)
    return codes[:n].astype(np.int64), codes[n:].astype(np.int64), len(uniq)


def pair_bootstrap_weights(counts, a, b, w):
    """Replicate pair weights: w * n_a * n_b for a != b, w * n_a for within-unit pairs (a == b)."""
    ca = counts[a]
    return np.where(a == b, ca, ca * counts[b]) * w


def bootstrap_counts(n_clusters: int, B: int = DEFAULT_B, seed=DEFAULT_SEED):
    """Yield (start, counts[chunk, K]) unit draw counts; deterministic given (K, B, seed).

    ``seed`` is anything ``numpy.random.default_rng`` accepts (int or list of ints)."""
    rng = np.random.default_rng(seed)
    p = np.full(n_clusters, 1.0 / n_clusters)
    for start in range(0, B, _CHUNK):
        b = min(_CHUNK, B - start)
        yield start, rng.multinomial(n_clusters, p, size=b).astype(np.float64)


if HAVE_NUMBA:
    @njit(parallel=True, cache=True)
    def _boot_kernel(cnt, ci_s, cj_s, w_s, y_s, end_s, out_auc, out_ap, offset):  # pragma: no cover (jit)
        nb = cnt.shape[0]
        nm, n = ci_s.shape
        for b in prange(nb):
            row = cnt[b]
            for m in range(nm):
                tp = 0.0
                fp = 0.0
                pg = 0.0
                ng = 0.0
                bad = 0.0
                ap = 0.0
                for k in range(n):
                    a = ci_s[m, k]
                    c = cj_s[m, k]
                    if a == c:
                        wk = row[a] * w_s[m, k]
                    else:
                        wk = row[a] * row[c] * w_s[m, k]
                    if y_s[m, k]:
                        pg += wk
                    else:
                        ng += wk
                    if end_s[m, k]:
                        bad += pg * (fp + 0.5 * ng)
                        tp += pg
                        fp += ng
                        if pg > 0.0:
                            ap += pg * tp / (tp + fp)
                        pg = 0.0
                        ng = 0.0
                if tp > 0.0 and fp > 0.0:
                    out_auc[offset + b, m] = 1.0 - bad / (tp * fp)
                    out_ap[offset + b, m] = ap / tp
                else:
                    out_auc[offset + b, m] = np.nan
                    out_ap[offset + b, m] = np.nan


def _boot_kernel_numpy(cnt, ci_s, cj_s, w_s, y_s, end_s, out_auc, out_ap, offset):
    for b in range(cnt.shape[0]):
        for m in range(ci_s.shape[0]):
            w = pair_bootstrap_weights(cnt[b], ci_s[m], cj_s[m], w_s[m])
            wp, wn = np.where(y_s[m], w, 0.0), np.where(y_s[m], 0.0, w)
            tp, fp = np.cumsum(wp)[end_s[m]], np.cumsum(wn)[end_s[m]]
            pg, ng = np.diff(tp, prepend=0.0), np.diff(fp, prepend=0.0)
            if tp[-1] > 0 and fp[-1] > 0:
                out_auc[offset + b, m] = 1 - np.sum(pg * (fp - ng + 0.5 * ng)) / (tp[-1] * fp[-1])
                den = tp + fp
                prec = np.divide(tp, den, out=np.zeros_like(tp), where=den > 0)
                out_ap[offset + b, m] = np.sum(pg * prec) / tp[-1]
            else:
                out_auc[offset + b, m] = np.nan
                out_ap[offset + b, m] = np.nan


def _replicates(y, S, ci, cj, w, B, seed, n_threads):
    """Bootstrap replicates of weighted AUC and AP for each row of S (m x n).  Returns (auc[B,m], ap[B,m], K)."""
    a, b_, K = _encode_clusters(ci, cj)
    m, n = S.shape
    ci_s = np.empty((m, n), np.int64)
    cj_s = np.empty((m, n), np.int64)
    w_s = np.empty((m, n), np.float64)
    y_s = np.empty((m, n), np.bool_)
    end_s = np.empty((m, n), np.bool_)
    for r in range(m):
        o = np.argsort(-S[r], kind="mergesort")
        ss = S[r][o]
        ci_s[r], cj_s[r], w_s[r], y_s[r] = a[o], b_[o], w[o], y[o]
        end_s[r, :-1] = ss[1:] != ss[:-1]
        end_s[r, -1] = True
    out_auc = np.full((B, m), np.nan)
    out_ap = np.full((B, m), np.nan)
    kernel = _boot_kernel if HAVE_NUMBA else _boot_kernel_numpy
    prev = None
    if HAVE_NUMBA:
        prev = numba.get_num_threads()
        numba.set_num_threads(max(1, min(n_threads or _default_threads(), numba.config.NUMBA_NUM_THREADS)))
    try:
        for start, cnt in bootstrap_counts(K, B, seed):
            kernel(cnt, ci_s, cj_s, w_s, y_s, end_s, out_auc, out_ap, start)
    finally:
        if prev is not None:
            numba.set_num_threads(prev)
    return out_auc, out_ap, K


def _default_threads():
    return int(os.environ.get("POCKETCOMPARE_THREADS", min(16, os.cpu_count() or 1)))


@dataclass
class BootstrapResult:
    """Point estimate + percentile CI from a vertex bootstrap of one quantity."""
    name: str
    estimate: float
    ci_low: float
    ci_high: float
    se: float
    lower_one_sided: float  # alpha-quantile (one-sided 1-alpha lower bound)
    B: int
    n_valid: int
    n_degenerate: int
    seed: int
    alpha: float
    n_clusters: int
    p_value: float | None = None  # one-sided H0: value <= 0 (only for differences)
    replicates: np.ndarray | None = field(default=None, repr=False)

    def to_dict(self, replicates: bool = False) -> dict:
        d = asdict(self)
        if not replicates:
            d.pop("replicates")
        elif d["replicates"] is not None:
            d["replicates"] = d["replicates"].tolist()
        return d


def _summarise(name, est, reps, *, alpha, seed, K, diff=False):
    v = reps[np.isfinite(reps)]
    B = len(reps)
    if len(v) == 0:
        raise ValueError("all bootstrap replicates degenerate")
    lo, hi = np.quantile(v, [alpha / 2, 1 - alpha / 2])
    p = float((1 + np.sum(v <= 0)) / (len(v) + 1)) if diff else None
    return BootstrapResult(name=name, estimate=float(est), ci_low=float(lo), ci_high=float(hi),
                           se=float(np.std(v, ddof=1)) if len(v) > 1 else np.nan,
                           lower_one_sided=float(np.quantile(v, alpha)), B=B, n_valid=int(len(v)),
                           n_degenerate=int(B - len(v)), seed=seed, alpha=alpha, n_clusters=K, p_value=p,
                           replicates=reps)


def vertex_bootstrap(y, s, ci, cj, w=None, *, B: int = DEFAULT_B, seed: int = DEFAULT_SEED, alpha: float = 0.05,
                     n_threads: int | None = None, missing: str = "raise") -> dict:
    """Two-way vertex cluster bootstrap of weighted ROC-AUC and AP for one method.

    Returns {"auc": BootstrapResult, "ap": BootstrapResult, "missing": counts}."""
    y = np.asarray(y).astype(bool)
    mask, sd, counts = apply_missing_policy(y, {"s": s}, missing)
    y, ci, cj = y[mask], np.asarray(ci)[mask], np.asarray(cj)[mask]
    y, s_, w = _as_arrays(y, sd["s"], None if w is None else np.asarray(w)[mask])
    auc_r, ap_r, K = _replicates(y, s_[None, :], ci, cj, w, B, seed, n_threads)
    return {"auc": _summarise("auc", roc_auc(y, s_, w), auc_r[:, 0], alpha=alpha, seed=seed, K=K),
            "ap": _summarise("ap", average_precision(y, s_, w)["ap"], ap_r[:, 0], alpha=alpha, seed=seed, K=K),
            "missing": counts}


def paired_bootstrap(y, s_a, s_b, ci, cj, w=None, *, B: int = DEFAULT_B, seed: int = DEFAULT_SEED,
                     alpha: float = 0.05, n_threads: int | None = None, missing: str = "common") -> dict:
    """Paired vertex bootstrap for Delta = metric(a) - metric(b) on the same pairs and the same replicates.

    Default missing policy is the common pair set (DESIGN §4).  Returns BootstrapResults for auc_a, auc_b,
    delta_auc (with one-sided p-value for Delta > 0), and the same for AP, plus missing-score counts."""
    y = np.asarray(y).astype(bool)
    mask, sd, counts = apply_missing_policy(y, {"a": s_a, "b": s_b}, missing)
    y, ci, cj = y[mask], np.asarray(ci)[mask], np.asarray(cj)[mask]
    w = None if w is None else np.asarray(w)[mask]
    y, sa, w = _as_arrays(y, sd["a"], w)
    sb = np.asarray(sd["b"], dtype=np.float64)
    auc_r, ap_r, K = _replicates(y, np.vstack([sa, sb]), ci, cj, w, B, seed, n_threads)
    est = {"auc_a": roc_auc(y, sa, w), "auc_b": roc_auc(y, sb, w),
           "ap_a": average_precision(y, sa, w)["ap"], "ap_b": average_precision(y, sb, w)["ap"]}
    kw = dict(alpha=alpha, seed=seed, K=K)
    return {"auc_a": _summarise("auc_a", est["auc_a"], auc_r[:, 0], **kw),
            "auc_b": _summarise("auc_b", est["auc_b"], auc_r[:, 1], **kw),
            "delta_auc": _summarise("delta_auc", est["auc_a"] - est["auc_b"], auc_r[:, 0] - auc_r[:, 1],
                                    diff=True, **kw),
            "ap_a": _summarise("ap_a", est["ap_a"], ap_r[:, 0], **kw),
            "ap_b": _summarise("ap_b", est["ap_b"], ap_r[:, 1], **kw),
            "delta_ap": _summarise("delta_ap", est["ap_a"] - est["ap_b"], ap_r[:, 0] - ap_r[:, 1], diff=True, **kw),
            "missing": counts}


def vertex_bootstrap_generic(fn: Callable[[np.ndarray], float | np.ndarray], ci, cj, w=None, *,
                             B: int = DEFAULT_B, seed: int = DEFAULT_SEED, alpha: float = 0.05,
                             names: Sequence[str] | None = None, diff: bool = False) -> list[BootstrapResult]:
    """Vertex bootstrap of any statistic ``fn(pair_weights) -> float | array`` (slow path, Python loop).

    Uses exactly the same replicate weights as :func:`vertex_bootstrap` for the same (clusters, B, seed), so it
    can be paired with fast-path results.  ``fn`` must accept zero weights; a NaN or a ValueError marks the
    replicate degenerate.  ``diff=True`` adds one-sided p-values (statistic is a difference)."""
    a, b_, K = _encode_clusters(ci, cj)
    w = np.ones(len(a)) if w is None else np.asarray(w, dtype=np.float64)
    est = np.atleast_1d(np.asarray(fn(w), dtype=np.float64))
    reps = np.full((B, len(est)), np.nan)
    for start, cnt in bootstrap_counts(K, B, seed):
        for r in range(cnt.shape[0]):
            ww = pair_bootstrap_weights(cnt[r], a, b_, w)
            try:
                reps[start + r] = np.atleast_1d(np.asarray(fn(ww), dtype=np.float64))
            except ValueError:
                pass
    names = list(names) if names is not None else [f"stat{i}" for i in range(len(est))]
    return [_summarise(names[i], est[i], reps[:, i], alpha=alpha, seed=seed, K=K, diff=diff)
            for i in range(len(est))]


def macro_paired_bootstrap(subsets: Sequence[Mapping], *, B: int = DEFAULT_B, seed: int = DEFAULT_SEED,
                           alpha: float = 0.05, n_threads: int | None = None, missing: str = "common") -> dict:
    """Macro-averaged paired Delta over several subsets (claim C2: ProSPECCTs D5.2 + D6.2 + D7).

    ``subsets``: sequence of dicts with keys y, s_a, s_b, ci, cj and optional w, name.  Each subset is bootstrapped
    independently (its own units; seed stream ``[seed, k]`` for subset k) and the macro statistic is the
    unweighted mean over subsets, combined replicate-by-replicate (replicate b of the macro = mean of replicate b
    of every subset).  A replicate degenerate in any subset is degenerate for the macro.  Returns macro
    BootstrapResults (auc_a, auc_b, delta_auc with one-sided p-value; same for AP) and the per-subset results."""
    per, reps = {}, {k: [] for k in ("auc_a", "auc_b", "ap_a", "ap_b")}
    est = {k: [] for k in reps}
    for k, sub in enumerate(subsets):
        name = str(sub.get("name", f"subset{k}"))
        y = np.asarray(sub["y"]).astype(bool)
        mask, sd, counts = apply_missing_policy(y, {"a": sub["s_a"], "b": sub["s_b"]}, missing)
        w = sub.get("w")
        y, sa, w = _as_arrays(y[mask], sd["a"], None if w is None else np.asarray(w)[mask])
        sb = np.asarray(sd["b"], dtype=np.float64)
        auc_r, ap_r, K = _replicates(y, np.vstack([sa, sb]), np.asarray(sub["ci"])[mask],
                                     np.asarray(sub["cj"])[mask], w, B, [int(seed), k], n_threads)
        e = {"auc_a": roc_auc(y, sa, w), "auc_b": roc_auc(y, sb, w),
             "ap_a": average_precision(y, sa, w)["ap"], "ap_b": average_precision(y, sb, w)["ap"]}
        r = {"auc_a": auc_r[:, 0], "auc_b": auc_r[:, 1], "ap_a": ap_r[:, 0], "ap_b": ap_r[:, 1]}
        kw = dict(alpha=alpha, seed=seed, K=K)
        per[name] = {"delta_auc": _summarise("delta_auc", e["auc_a"] - e["auc_b"], r["auc_a"] - r["auc_b"],
                                             diff=True, **kw),
                     "delta_ap": _summarise("delta_ap", e["ap_a"] - e["ap_b"], r["ap_a"] - r["ap_b"],
                                            diff=True, **kw),
                     "auc_a": e["auc_a"], "auc_b": e["auc_b"], "missing": counts, "n_units": K}
        for key in reps:
            reps[key].append(r[key])
            est[key].append(e[key])
    mean = {k: np.mean(np.vstack(v), axis=0) for k, v in reps.items()}  # NaN in any subset -> NaN
    pt = {k: float(np.mean(v)) for k, v in est.items()}
    K = sum(p["n_units"] for p in per.values())
    kw = dict(alpha=alpha, seed=seed, K=K)
    out = {f"macro_{k}": _summarise(f"macro_{k}", pt[k], mean[k], **kw) for k in reps}
    out["macro_delta_auc"] = _summarise("macro_delta_auc", pt["auc_a"] - pt["auc_b"],
                                        mean["auc_a"] - mean["auc_b"], diff=True, **kw)
    out["macro_delta_ap"] = _summarise("macro_delta_ap", pt["ap_a"] - pt["ap_b"], mean["ap_a"] - mean["ap_b"],
                                       diff=True, **kw)
    out["subsets"] = per
    return out


def wider_ci(*results: BootstrapResult) -> BootstrapResult:
    """Of several bootstraps of the same quantity under different unit definitions (e.g. homology group vs ligand
    cluster on BLiPS/PPI, DESIGN §4), return the one with the widest percentile CI (ties: the first)."""
    if not results:
        raise ValueError("need at least one result")
    est = {round(r.estimate, 12) for r in results}
    if len(est) != 1:
        raise ValueError("results disagree on the point estimate: not the same quantity")
    return max(results, key=lambda r: r.ci_high - r.ci_low)


# ------------------------------------------------------------------------------------------ multiplicity, power
def holm(pvals, alpha: float = 0.05) -> dict:
    """Holm (1979) step-down adjusted p-values (monotone, capped at 1) and rejections at ``alpha``."""
    p = np.asarray(pvals, dtype=np.float64)
    m = len(p)
    order = np.argsort(p, kind="mergesort")
    adj_sorted = np.maximum.accumulate((m - np.arange(m)) * p[order])
    adj = np.empty(m)
    adj[order] = np.minimum(adj_sorted, 1.0)
    return {"p_adjusted": adj, "reject": adj <= alpha, "alpha": alpha}


def _z(q):
    from scipy.stats import norm

    return float(norm.ppf(q))


def mde(se: float, *, alpha: float = 0.05, power: float = 0.80, sided: int = 1) -> float:
    """Minimum detectable effect ~ (z_{1-alpha/sided} + z_{power}) * SE (bootstrap SE of the difference)."""
    if sided not in (1, 2):
        raise ValueError("sided must be 1 or 2")
    return (_z(1 - alpha / sided) + _z(power)) * float(se)


def mde_scaled(se_dev: float, n_units_dev: int, n_units_test: int, **kw) -> dict:
    """MDE on test projected from the dev bootstrap SE: SE_test ~ SE_dev * sqrt(n_units_dev / n_units_test).

    (Cluster-bootstrap SE scales as 1/sqrt(number of resampling units).)  ``kw`` as for :func:`mde`."""
    se_test = float(se_dev) * math.sqrt(n_units_dev / n_units_test)
    return {"se_dev": float(se_dev), "se_test": se_test, "n_units_dev": int(n_units_dev),
            "n_units_test": int(n_units_test), "mde": mde(se_test, **kw)}


# -------------------------------------------------------------------------------------------------- one-stop
def summarize(y, scores, *, w=None, missing: str = "raise", pos_cluster=None, covariate=None,
              max_fpr: float = 0.1, n_bins=(5, 5)) -> dict:
    """All point metrics for each method under one missing-score policy, with counts.

    Optional: cluster-balanced AUC (``pos_cluster``) and size-stratified AUC (``covariate``, e.g. the output of
    :func:`size_covariates`; ``n_bins`` per column)."""
    y = np.asarray(y).astype(bool)
    mask, sd, counts = apply_missing_policy(y, scores, missing)
    ym = y[mask]
    wm = None if w is None else np.asarray(w, dtype=np.float64)[mask]
    out = {"missing": counts, "methods": {}}
    for name, s in sd.items():
        r = binary_metrics(ym, s, wm, max_fpr=max_fpr)
        if pos_cluster is not None:
            r["auc_cb"] = cluster_balanced_auc(ym, s, np.asarray(pos_cluster)[mask], wm)["auc_cb"]
        if covariate is not None:
            st = stratified_auc(ym, s, np.asarray(covariate)[mask], wm, n_bins=n_bins)
            r["auc_strat"] = st["auc_strat"]
            r["strat_n_pairs_dropped"] = st["n_pairs_dropped"]
            r["strat_n_strata_dropped"] = st["n_strata_dropped"]
        out["methods"][name] = r
    return out


def module_sha256() -> str:
    """sha256 of this file (recorded in every provenance sidecar)."""
    import hashlib

    with open(__file__, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()

