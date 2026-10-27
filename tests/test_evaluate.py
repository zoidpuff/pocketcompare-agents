"""Tests of the frozen evaluation module (synthetic data only)."""
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

from pocketcompare import evaluate as ev
from pocketcompare.seeds import SEEDS

# hand example: positives .9 .4 .6, negatives .6 .1 .3
Y = np.array([1, 1, 0, 0, 1, 0])
S = np.array([0.9, 0.4, 0.6, 0.1, 0.6, 0.3])


# --------------------------------------------------------------------------------------------- basic metrics
def test_perfect_reversed_ties():
    y = np.array([0, 0, 1, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    assert ev.roc_auc(y, s) == 1.0
    assert ev.roc_auc(y, -s) == 0.0
    assert ev.roc_auc(y, np.zeros(5)) == 0.5
    assert ev.average_precision(y, s)["ap"] == 1.0
    assert ev.partial_auc(y, s)["pauc_mcclish"] == pytest.approx(1.0)
    assert ev.partial_auc(y, s)["pauc_raw"] == pytest.approx(0.1)
    ties = ev.partial_auc(y, np.zeros(5))
    assert ties["pauc_raw"] == pytest.approx(0.005) and ties["pauc_mcclish"] == pytest.approx(0.5)
    assert ev.average_precision(y, np.zeros(5))["ap"] == pytest.approx(0.6)  # = prevalence


def test_hand_example():
    # pairs won: .9 beats 3; .6 beats .1,.3 and ties .6 (2.5); .4 beats .1,.3 (2) -> 7.5/9
    assert ev.roc_auc(Y, S) == pytest.approx(7.5 / 9)
    # AP: thresholds .9 (P=1), .6 (one pos, P=2/3), .4 (P=3/4) -> (1 + 2/3 + 3/4)/3
    ap = ev.average_precision(Y, S)
    assert ap["ap"] == pytest.approx(29 / 36)
    assert ap["prevalence"] == 0.5 and ap["ap_lift"] == pytest.approx(29 / 18)


def test_against_sklearn_weighted(rng):
    for _ in range(20):
        n = int(rng.integers(20, 400))
        y = rng.random(n) < rng.uniform(0.1, 0.9)
        y[:2] = [True, False]
        s = np.round(rng.normal(size=n) + y, 1)  # many ties
        w = rng.integers(0, 4, n).astype(float)
        w[:2] = 1
        assert ev.roc_auc(y, s, w) == pytest.approx(roc_auc_score(y, s, sample_weight=w), abs=1e-12)
        assert ev.average_precision(y, s, w)["ap"] == pytest.approx(
            average_precision_score(y, s, sample_weight=w), abs=1e-12)
        for f in (0.01, 0.1, 0.5):
            assert ev.partial_auc(y, s, w, max_fpr=f)["pauc_mcclish"] == pytest.approx(
                roc_auc_score(y, s, sample_weight=w, max_fpr=f), abs=1e-12)


def test_ap_negative_target(rng):
    y = rng.random(300) < 0.8
    s = rng.normal(size=300) + y
    r = ev.average_precision(y, s, target="neg")
    assert r["ap"] == pytest.approx(average_precision_score(~y, -s))
    assert r["prevalence"] == pytest.approx(np.mean(~y))


def test_weights_equal_duplicated_rows(rng):
    n = 200
    y = rng.random(n) < 0.4
    s = np.round(rng.normal(size=n) + y, 1)
    cov = rng.normal(size=(n, 2))
    pc = rng.integers(0, 5, n)
    k = rng.integers(1, 4, n)
    yd, sd, covd, pcd = (np.repeat(a, k, axis=0) for a in (y, s, cov, pc))
    w = k.astype(float)
    assert ev.roc_auc(y, s, w) == pytest.approx(ev.roc_auc(yd, sd))
    assert ev.average_precision(y, s, w)["ap"] == pytest.approx(ev.average_precision(yd, sd)["ap"])
    assert ev.partial_auc(y, s, w)["pauc_raw"] == pytest.approx(ev.partial_auc(yd, sd)["pauc_raw"])
    assert ev.cluster_balanced_auc(y, s, pc, w)["auc_cb"] == pytest.approx(ev.cluster_balanced_auc(yd, sd, pcd)["auc_cb"])
    # stratified: bin edges are unweighted quantiles, so compare at fixed strata (1-D integer covariate)
    c = rng.integers(0, 4, n).astype(float)
    assert ev.stratified_auc(y, s, c, w, n_bins=4)["auc_strat"] == pytest.approx(
        ev.stratified_auc(yd, sd, np.repeat(c, k), n_bins=4)["auc_strat"])


def test_nan_refused_and_bad_input():
    s = S.copy()
    s[0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        ev.roc_auc(Y, s)
    with pytest.raises(ValueError):
        ev.roc_auc(np.ones(3), np.arange(3.0))  # one class
    with pytest.raises(ValueError):
        ev.roc_auc(np.array([0, 2, 1]), np.arange(3.0))
    with pytest.raises(ValueError):
        ev.roc_auc(Y, S, -np.ones(6))


# ------------------------------------------------------------------------------------- cluster-aware metrics
def test_cluster_balanced_is_mean_of_per_cluster(rng):
    n = 3000
    y = rng.random(n) < 0.4
    pc = np.where(y, rng.choice(6, n, p=[0.6, 0.2, 0.1, 0.05, 0.03, 0.02]), -1)
    s = rng.normal(size=n) + y * (pc == 0) * 2.0  # only the giant cluster is easy
    cb = ev.cluster_balanced_auc(y, s, pc)
    per = ev.per_cluster_auc(y, s, pc, k=10)
    assert cb["n_pos_clusters"] == 6 and len(per) == 6
    assert list(per["n_pos"]) == sorted(per["n_pos"], reverse=True)
    assert cb["auc_cb"] == pytest.approx(per["auc"].mean())
    assert ev.roc_auc(y, s) > cb["auc_cb"] + 0.1  # pair AUC dominated by the giant cluster
    assert len(ev.per_cluster_auc(y, s, pc, k=3)) == 3


def test_per_cluster_involving_and_neg_balance():
    y = np.array([1, 1, 1, 0, 0, 0, 0])
    pc = np.array(["A", "A", "B", "-", "-", "-", "-"])
    ci = np.array(["A", "A", "B", "A", "B", "B", "C"])
    cj = np.array(["A", "A", "B", "C", "C", "D", "D"])
    s = np.array([0.9, 0.8, 0.5, 0.6, 0.7, 0.1, 0.2])
    per = ev.per_cluster_auc(y, s, pc, negatives="involving", ci=ci, cj=cj).set_index("cluster")
    assert per.loc["A", "n_neg"] == 1 and per.loc["A", "auc"] == 1.0
    assert per.loc["B", "n_neg"] == 2 and per.loc["B", "auc"] == 0.5
    # negative groups balanced: neg group g1={0.6,0.7}, g2={0.1,0.2}
    ng = np.array(["", "", "", "g1", "g1", "g2", "g2"])
    r = ev.cluster_balanced_auc(y, s, pc, neg_cluster=ng)
    assert r["n_neg_groups"] == 2
    # A: wins all 4 -> 1;  B (0.5): loses to g1 (both), beats g2 -> 0.5 ; mean = 0.75
    assert r["auc_cb"] == pytest.approx(0.75)


# ----------------------------------------------------------------------------------------- stratified AUC
def test_stratified_hand_example():
    # covariate 0..8 in tertiles: stratum 0 = pos .9 vs neg .1,.2 -> AUC 1 (1 pos, 2 neg);
    # stratum 1 = pos .2,.3 vs neg .5 -> AUC 0 (2 pos, 1 neg); stratum 2 = only negatives (dropped, counted)
    y = np.array([1, 0, 0, 1, 1, 0, 0, 0, 0])
    s = np.array([0.9, 0.1, 0.2, 0.2, 0.3, 0.5, 0.4, 0.4, 0.1])
    c = np.arange(9.0)
    r = ev.stratified_auc(y, s, c, n_bins=3)
    assert r["n_strata"] == 3 and r["n_strata_used"] == 2 and r["n_strata_dropped"] == 1
    assert r["n_pairs_dropped"] == 3 and r["frac_pos_weight_dropped"] == 0
    assert r["auc_strat"] == pytest.approx((1 * 1 + 0 * 2) / 3)  # default weights = positives (1, 2)
    assert ev.stratified_auc(y, s, c, n_bins=3, weighting="equal")["auc_strat"] == pytest.approx(0.5)
    assert ev.stratified_auc(y, s, c, n_bins=3, weighting="min")["auc_strat"] == pytest.approx(0.5)  # min(1,2), min(2,1)
    # heavy ties at a quantile edge merge bins (documented): values {0,0,1,1,1,2,2} in tertiles -> 2 strata
    assert ev.stratified_auc(y[:7], s[:7], np.array([0, 0, 1, 1, 1, 2, 2.0]), n_bins=3)["n_strata"] == 2


def test_stratified_2d_crosses_bins(rng):
    n = 2000
    cov = rng.normal(size=(n, 2))
    y = rng.random(n) < 0.5
    r = ev.stratified_auc(y, rng.normal(size=n), cov, n_bins=(5, 4))
    assert r["n_strata"] == 20 and r["n_bins"] == [5, 4] and len(r["edges"]) == 2
    with pytest.raises(ValueError):
        ev.stratified_auc(y, rng.normal(size=n), cov, n_bins=(5, 4, 3))


def _size_confounded(rng, n=40000, sd_pos=0.3):
    lva = rng.normal(6.0, 0.6, n)
    y = rng.random(n) < 0.3
    lva = np.where(y, lva + 0.3, lva)  # positives enriched for large pockets
    d = np.where(y, rng.normal(0, sd_pos, n), rng.normal(0, 0.7, n))  # ... and for similar sizes
    return y, lva, lva + d


def test_stratified_kills_size_shortcut(rng):
    y, la, lb = _size_confounded(rng)
    cov = ev.size_covariates(la, lb)
    b0 = -np.abs(la - lb)  # size-ratio-only scorer (B0)
    pair = ev.roc_auc(y, b0)
    st = ev.stratified_auc(y, b0, cov)["auc_strat"]  # headline 5 x 5
    st_fine = ev.stratified_auc(y, b0, cov, n_bins=(5, 20))["auc_strat"]
    assert pair > 0.70
    assert st - 0.5 < 0.2 * (pair - 0.5)  # >= 80 % of the shortcut removed by 5 x 5 quintiles
    assert abs(st_fine - 0.5) < 0.02  # finer |dlogV| bins remove the residual
    absz = la + lb  # absolute-size scorer
    assert ev.roc_auc(y, absz) > 0.6 and abs(ev.stratified_auc(y, absz, cov)["auc_strat"] - 0.5) < 0.05
    # a size-independent informative scorer keeps its AUC under stratification
    good = rng.normal(size=len(y)) + 1.0 * y
    assert abs(ev.stratified_auc(y, good, cov)["auc_strat"] - ev.roc_auc(y, good)) < 0.02


# ----------------------------------------------------------------------------------------------- retrieval
def test_retrieval():
    df = pd.DataFrame({
        "query": ["q1"] * 4 + ["q2"] * 3 + ["q3"] * 2 + ["q4"] * 2,
        "score": [0.9, 0.8, 0.1, 0.2, 0.5, 0.7, 0.5, 0.3, 0.2, np.nan, 0.1],
        "label": [1, 0, 0, 1, 1, 0, 0, 0, 0, 1, 0],
    })
    r = ev.retrieval_metrics(df, ks=(1, 2))
    rank = r["per_query"].set_index("query")["rank"]
    # q1: hit .9 first -> 1; q2: .7 above, tie at .5 -> pessimistic 3; q4: NaN hit -> -inf, below .1 -> 2
    assert rank.to_dict() == {"q1": 1, "q2": 3, "q4": 2}
    assert r["n_queries"] == 4 and r["n_queries_no_hit"] == 1 and r["n_missing_scores"] == 1
    assert r["top1"] == pytest.approx(1 / 3) and r["top2"] == pytest.approx(2 / 3)
    assert r["mrr"] == pytest.approx((1 + 1 / 3 + 1 / 2) / 3)
    ro = ev.retrieval_metrics(df, ks=(1,), ties="optimistic")
    assert ro["per_query"].set_index("query")["rank"]["q2"] == 2
    # constant scorer gets no credit under pessimistic ties
    df["score"] = 0.0
    assert ev.retrieval_metrics(df)["top1"] == 0.0


# ------------------------------------------------------------------------------------------- missing scores
def test_missing_policies(rng):
    n = 1000
    y = rng.random(n) < 0.5
    sa = rng.normal(size=n) + y
    sb = rng.normal(size=n) + 0.5 * y
    sa[rng.random(n) < 0.1] = np.nan
    sb[(rng.random(n) < 0.05) & ~y] = np.nan  # b fails on negatives only
    mask, counts = ev.common_set(y, {"a": sa, "b": sb})
    assert counts["n_total"] == n == counts["n_common"] + counts["n_dropped"]
    assert counts["n_dropped"] == counts["n_dropped_pos"] + counts["n_dropped_neg"]
    assert counts["per_method"]["b"]["n_missing_pos"] == 0
    assert counts["per_method"]["b"]["n_missing_neg"] == int(np.isnan(sb).sum())
    for s in (sa, sb):
        common = ev.roc_auc(y[mask], s[mask])
        wc, c = ev.worst_case(y, s)
        mi, _ = ev.min_impute(y, s)
        assert c["n_imputed"] == int(np.isnan(s).sum())
        assert ev.roc_auc(y, wc) <= common
        assert ev.roc_auc(y, wc) <= ev.roc_auc(y, mi)
        assert ev.average_precision(y, wc)["ap"] <= ev.average_precision(y[mask], s[mask])["ap"] + 1e-12
    # min-imputation rewards failing on negatives (reviews/round1_statistics.md M5)
    mi_b, _ = ev.min_impute(y, sb)
    assert ev.roc_auc(y, mi_b) > ev.roc_auc(y[~np.isnan(sb)], sb[~np.isnan(sb)])
    with pytest.raises(ValueError, match="NaN"):
        ev.summarize(y, {"a": sa})
    out = ev.summarize(y, {"a": sa, "b": sb}, missing="common")
    assert out["missing"]["n_kept"] == counts["n_common"]
    assert out["methods"]["a"]["n"] == counts["n_common"]
    out = ev.summarize(y, {"a": sa, "b": sb}, missing="worst")
    assert out["missing"]["imputed"]["a"]["n_imputed"] == int(np.isnan(sa).sum())


def test_summarize_all_metrics(rng):
    n = 2000
    y = rng.random(n) < 0.4
    s = rng.normal(size=n) + y
    out = ev.summarize(y, s, pos_cluster=rng.integers(0, 5, n),
                       covariate=ev.size_covariates(rng.normal(size=n), rng.normal(size=n)))
    m = out["methods"]["score"]
    for k in ("auc", "ap", "prevalence", "ap_lift", "pauc_mcclish", "pauc_raw", "auc_cb", "auc_strat"):
        assert np.isfinite(m[k])


# ------------------------------------------------------------------------------------------ vertex bootstrap
def _cluster_data(rng, K=40, neg_per_unit=12, mu=1.0, sd_a=0.5, sd_b=0.4):
    """Units with 1+Poisson(3) pockets; positives = within-unit pairs, negatives = random between-unit pairs.
    Score = mu + a_u + e (pos) or b_u + b_v + e (neg): unit effects create within-unit correlation."""
    n_u = 1 + rng.poisson(3, K)
    a, b = rng.normal(0, sd_a, K), rng.normal(0, sd_b, K)
    pos_u = np.repeat(np.arange(K), n_u * (n_u - 1) // 2)
    nu = rng.integers(0, K, K * neg_per_unit)
    nv = (nu + rng.integers(1, K, len(nu))) % K
    ci = np.concatenate([pos_u, nu])
    cj = np.concatenate([pos_u, nv])
    y = np.r_[np.ones(len(pos_u), bool), np.zeros(len(nu), bool)]
    s = np.r_[mu + a[pos_u], b[nu] + b[nv]] + rng.normal(0, 1, len(y))
    return y, s, ci, cj


def test_pair_weights_within_unit():
    counts = np.array([2.0, 0.0, 3.0])
    a = np.array([0, 0, 2, 1, 2])
    b = np.array([0, 2, 2, 2, 0])
    w = np.array([1.0, 1.0, 1.0, 1.0, 0.5])
    np.testing.assert_array_equal(ev.pair_bootstrap_weights(counts, a, b, w), [2.0, 6.0, 3.0, 0.0, 3.0])


def test_bootstrap_fast_equals_generic_and_manual(rng):
    y, s, ci, cj = _cluster_data(rng, K=25)
    w = rng.integers(1, 3, len(y)).astype(float)
    B = 64
    fast = ev.vertex_bootstrap(y, s, ci, cj, w, B=B)
    gen = ev.vertex_bootstrap_generic(lambda ww: [ev.roc_auc(y, s, ww), ev.average_precision(y, s, ww)["ap"]],
                                      ci, cj, w, B=B, names=["auc", "ap"])
    np.testing.assert_allclose(fast["auc"].replicates, gen[0].replicates, atol=1e-12)
    np.testing.assert_allclose(fast["ap"].replicates, gen[1].replicates, atol=1e-12)
    # manual replicate 0 with within-unit weight n_u and between-unit n_u * n_v
    uniq, codes = np.unique(np.concatenate([ci, cj]), return_inverse=True)
    a, b = codes[:len(ci)], codes[len(ci):]
    cnt = next(ev.bootstrap_counts(len(uniq), B, SEEDS[0]))[1][0]
    ww = np.where(a == b, cnt[a], cnt[a] * cnt[b]) * w
    assert fast["auc"].replicates[0] == pytest.approx(ev.roc_auc(y, s, ww))
    assert fast["auc"].estimate == pytest.approx(ev.roc_auc(y, s, w))


def test_bootstrap_numpy_kernel_matches_numba(rng):
    y, s, ci, cj = _cluster_data(rng, K=20)
    r = ev.vertex_bootstrap(y, s, ci, cj, B=40)
    old = ev.HAVE_NUMBA
    try:
        ev.HAVE_NUMBA = False
        r2 = ev.vertex_bootstrap(y, s, ci, cj, B=40)
    finally:
        ev.HAVE_NUMBA = old
    np.testing.assert_allclose(r["auc"].replicates, r2["auc"].replicates, atol=1e-12)
    np.testing.assert_allclose(r["ap"].replicates, r2["ap"].replicates, atol=1e-12)


def test_bootstrap_deterministic_and_thread_independent(rng):
    y, s, ci, cj = _cluster_data(rng, K=30)
    r1 = ev.vertex_bootstrap(y, s, ci, cj, B=300, n_threads=1)
    r4 = ev.vertex_bootstrap(y, s, ci, cj, B=300, n_threads=4)
    np.testing.assert_array_equal(r1["auc"].replicates, r4["auc"].replicates)
    r_other = ev.vertex_bootstrap(y, s, ci, cj, B=300, seed=SEEDS[1])
    assert not np.array_equal(r1["auc"].replicates, r_other["auc"].replicates)
    assert r1["auc"].seed == SEEDS[0] and r1["auc"].B == 300 and r1["auc"].n_clusters == 30


def test_paired_self_is_zero(rng):
    y, s, ci, cj = _cluster_data(rng)
    r = ev.paired_bootstrap(y, s, s.copy(), ci, cj, B=200)
    assert r["delta_auc"].estimate == 0 and np.all(r["delta_auc"].replicates == 0)
    assert r["delta_auc"].ci_low == 0 == r["delta_auc"].ci_high
    assert r["delta_auc"].p_value == 1.0
    assert np.all(r["delta_ap"].replicates == 0)


def test_paired_detects_real_difference(rng):
    y, s, ci, cj = _cluster_data(rng, K=80)
    better = s + 1.5 * y
    r = ev.paired_bootstrap(y, better, s, ci, cj, B=500)
    d = r["delta_auc"]
    assert d.estimate > 0 and d.ci_low > 0 and d.p_value == pytest.approx(1 / 501)
    assert d.lower_one_sided >= d.ci_low
    # paired SE is smaller than the unpaired combination for positively correlated scores
    assert d.se < np.hypot(r["auc_a"].se, r["auc_b"].se)
    # common-set missing policy is applied and reported
    s2 = s.copy()
    s2[:10] = np.nan
    r2 = ev.paired_bootstrap(y, better, s2, ci, cj, B=50)
    assert r2["missing"]["n_dropped"] == 10 and r2["missing"]["policy"] == "common"


def test_degenerate_replicates_counted():
    # all positives in unit 0: replicates that do not draw unit 0 have no positives
    y = np.array([1, 1, 0, 0, 0, 0])
    ci = np.array([0, 0, 1, 2, 1, 3])
    cj = np.array([0, 0, 2, 3, 3, 4])
    s = np.array([0.9, 0.5, 0.4, 0.1, 0.6, 0.3])
    r = ev.vertex_bootstrap(y, s, ci, cj, B=500)["auc"]
    assert 0 < r.n_degenerate < 500 and r.n_valid + r.n_degenerate == 500
    # expected: degenerate iff unit 0 undrawn or no negative pair has both units drawn
    cnt = np.vstack([c for _, c in ev.bootstrap_counts(5, 500, SEEDS[0])])
    neg_ok = np.zeros(500, bool)
    for a, b in zip(ci[2:], cj[2:]):
        neg_ok |= (cnt[:, a] > 0) & (cnt[:, b] > 0)
    assert r.n_degenerate == int(np.sum((cnt[:, 0] == 0) | ~neg_ok))
    assert np.isnan(r.replicates).sum() == r.n_degenerate


def test_macro_paired_bootstrap(rng):
    subs = []
    for k in range(3):
        y, s, ci, cj = _cluster_data(rng, K=20 + 10 * k)
        subs.append(dict(name=f"D{k}", y=y, s_a=s + 0.5 * y, s_b=s, ci=ci, cj=cj))
    r = ev.macro_paired_bootstrap(subs, B=200)
    per = [ev.paired_bootstrap(d["y"], d["s_a"], d["s_b"], d["ci"], d["cj"], B=200, seed=[SEEDS[0], k])
           for k, d in enumerate(subs)]
    np.testing.assert_allclose(r["macro_delta_auc"].replicates,
                               np.mean([p["delta_auc"].replicates for p in per], axis=0), atol=1e-12)
    assert r["macro_delta_auc"].estimate == pytest.approx(np.mean([p["delta_auc"].estimate for p in per]))
    assert r["subsets"]["D1"]["delta_auc"].estimate == pytest.approx(per[1]["delta_auc"].estimate)
    assert r["macro_delta_auc"].p_value < 0.05
    # independent seeds per subset
    assert not np.array_equal(per[0]["auc_a"].replicates[:5], per[1]["auc_a"].replicates[:5])
    same = [dict(d, s_a=d["s_b"]) for d in subs]
    assert ev.macro_paired_bootstrap(same, B=50)["macro_delta_auc"].p_value == 1.0


@pytest.mark.slow
def test_bootstrap_coverage():
    """Percentile vertex-bootstrap 95 % CI covers the superpopulation AUC in >= 93 % of 200 datasets."""
    rng = np.random.default_rng(SEEDS[0])
    y, s, _, _ = _cluster_data(rng, K=40000)  # superpopulation truth (ratio-estimator limit)
    truth = ev.roc_auc(y, s)
    cover, n_rep = 0, 200
    for _ in range(n_rep):
        y, s, ci, cj = _cluster_data(rng, K=60)
        r = ev.vertex_bootstrap(y, s, ci, cj, B=500)["auc"]
        cover += r.ci_low <= truth <= r.ci_high
    assert cover / n_rep >= 0.93, (cover, truth)


def test_wider_ci(rng):
    y, s, ci, cj = _cluster_data(rng, K=40)
    coarse = ev.vertex_bootstrap(y, s, ci, cj, B=200)["auc"]
    pid = np.arange(len(y))
    fine = ev.vertex_bootstrap(y, s, pid, pid, B=200)["auc"]  # pair-level units: narrower
    assert ev.wider_ci(fine, coarse) is coarse
    with pytest.raises(ValueError):
        ev.wider_ci(coarse, ev.vertex_bootstrap(y, -s, ci, cj, B=10)["auc"])


# ----------------------------------------------------------------------------------------- holm, mde
def test_holm_hand_example():
    r = ev.holm([0.01, 0.04, 0.03, 0.005])
    # sorted .005*4=.02, .01*3=.03, .03*2=.06, .04*1=.04 -> monotone .06
    np.testing.assert_allclose(r["p_adjusted"], [0.03, 0.06, 0.06, 0.02])
    assert list(r["reject"]) == [True, False, False, True]
    assert ev.holm([0.5, 0.9])["p_adjusted"].max() == 1.0


def test_mde():
    assert ev.mde(0.01) == pytest.approx((1.6448536 + 0.8416212) * 0.01, rel=1e-6)
    assert ev.mde(0.01, sided=2) == pytest.approx((1.959964 + 0.8416212) * 0.01, rel=1e-6)
    r = ev.mde_scaled(0.02, n_units_dev=100, n_units_test=400)
    assert r["se_test"] == pytest.approx(0.01) and r["mde"] == pytest.approx(ev.mde(0.01))


def test_module_hash_stable():
    assert ev.module_sha256() == ev.module_sha256() and len(ev.module_sha256()) == 64
