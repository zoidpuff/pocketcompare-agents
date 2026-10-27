#!/usr/bin/env python
"""Development evaluation of every pocket-similarity arm on a dev split (DESIGN v2 §3, §4; amendment D6).

    python scripts/eval_dev.py --dataset tough_m1            # TOUGH-M1-dev, B = 2000, seed SEEDS[0]
    python scripts/eval_dev.py --dataset tough_m1 --B 50 --out <scratch> --no-trials     # smoke test

Reusable for BLiPS-val / PPIPS-val: everything dataset-specific lives in a ``DevDataset`` adapter (pairs + labels,
pocket table with bootstrap units, L-mode log volume, D-mode match flag, positive clusters, descriptor / docking
locations, natively shipped pair scores).  Only ``ToughM1Dev`` is implemented; ``BlipsVal`` documents what the
BLiPS adapter must provide.

All metrics come from the frozen ``pocketcompare.evaluate``; result files get provenance sidecars and every
evaluated arm / config / variant / mode is appended to ``results/trials.tsv`` (unless ``--no-trials``).

Analysis choices fixed in this file BEFORE the first run (not tuned afterwards)
------------------------------------------------------------------------------
* Units (vertex bootstrap): connected components of (ligand cluster ∪ homology group) over the partition's pockets.
  Positive cluster for the cluster-balanced AUC: connected component of the positive-pair graph (DESIGN §4).
* Size strata: covariate = L-mode log volume of both pockets (``evaluate.size_covariates``), n_bins = (5, 20)
  (D6), or (5, 5) if the evaluated pair set has < 500 positives.  Used for L- and D-mode alike.
* Similarities: z-score on the partition's pockets (label-free), cosine; CSLS k = 10 with background = all
  partition pockets available in that mode.  B5 (EPoCS) = -Euclidean on the raw embedding (as published).
  B4 primary = cosine of dev-z-scored embeddings (same treatment as B1); raw cosine reported as a variant.
* D-mode pair set = both pockets D-matched (coverage >= 0.3 OR precision >= 0.5).  Arms missing pockets inside
  it (A2 D-mode docked only coverage >= 0.3 pockets) are evaluated on their available pairs ("common" policy)
  with a worst-case bound; every D arm also gets a worst-case bound + miss rates by label on ALL dev pairs.
* A1 selection: one-SE rule on the cluster-balanced AUC, L-mode, raw cosine, candidates = the 16 grid configs +
  the pre-registered block-weighted scoring variant of ``default``; SE = vertex-bootstrap SE of the best
  candidate; simplest = fewest dims, ties -> earlier grid entry.  (BLiPS-val will be added to the selection mean.)
* Cross-fitting (B0m, fusions): units are assigned to 5 folds (seed SEEDS[0]; largest units first, each to the
  currently smallest fold).  The pairs whose endpoint folds are {k, l} are predicted by a model trained on the
  pairs with NO endpoint in fold k or l (fully unit-disjoint).  Model = StandardScaler + LogisticRegression
  (L2, C = 1) on features z-scored once over all evaluated pairs (label-free).  OOF score = x · β/‖β‖ without
  intercept.  DEVIATION (found in a B = 50 smoke run, before the B = 2000 run): the first implementation
  (per-fold scaler + decision_function with intercept) pooled scores whose fold-set intercepts differ because the
  training-set prevalence ranges 5–44 % (one unit holds 60 % of the dev pockets); it gave B0m stratified AUC 0.24
  and a cross-fitted A1-alone AUC of 0.43 vs 0.80 raw.  Its point metrics are kept in the details file
  ("crossfit_decision_diagnostic").  Bootstraps use the fixed OOF scores.
* A2 gate (DESIGN §3): primary = fusion(A1* + A2 fragments {rank, le_resid, ifp}) vs cross-fitted A1* alone,
  inputs = raw z-scored cosines, L-mode, metric = size-stratified AUC; PASS iff Δ >= 0.01 and the 95 %
  percentile-CI lower bound > 0.  Secondary: lead-like panel, both panels, CSLS inputs, Δ vs raw A1*.
* MDE (C1): SE of the paired Δ ROC-AUC (arm − B1, same CSLS treatment) on dev, scaled by
  sqrt(n_units_dev / n_units_test); test units from the pocket partition table only (test pairs stay sealed).
* B5-T (TOUGH-M1 shipped scores, computed by the original authors on their own pocket definitions): APoc c1 =
  PS-score (higher = similar, dataset.info), APoc c2 = P-value (lower = similar; Spearman -0.67 with PS-score,
  label-free) -> scored as -c2; G-LoSA c1 = GA-score (higher = similar, dataset.info).  SiteEngine c1..c3 are
  undocumented -> all three reported as shipped (higher value = more similar, unverified); none is selected.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.provenance import append_trial, git_state, sha256_file, write_result  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402
from pocketcompare.similarity import ZScorer, csls_r, embed, pair_scores  # noqa: E402

CSLS_K = 10
N_FOLDS = 5
A2_PANELS = ("fragments", "leadlike")
A2_BLOCKS = ("rank", "le_resid", "ifp")
A1_BW = {"hist": 1.0, "pair": 1.0, "usr": 1.0, "glob": 1.0, "size": 0.25}


# ============================================================================================ dataset adapters
class DevDataset:
    """Adapter interface.  After ``load()``:

    * ``pairs``: DataFrame (pocket_a, pocket_b, y ∈ {0,1}) — the evaluated dev pairs;
    * ``pockets``: DataFrame indexed 0..P-1 with pocket_id, unit, logv_L, d_match, desc_row (row in the
      descriptor arrays), in a fixed order; ``ia``/``ib`` = pair endpoints as indices into it;
    * ``pos_cluster``: positive cluster id per pair (only read for positives);
    * ``native``: {name: (scores per pair, note)} pair scores shipped with the benchmark (may be empty);
    * ``test_units()``: number of bootstrap units of the matching sealed test partition (label-free).
    """
    name = "abstract"
    split = "dev"

    def load(self):
        raise NotImplementedError

    def descriptor(self, arm: str, config: str, mode: str):
        """(matrix over self.pockets rows, layout or None) from data/processed/descriptors/<ds>/."""
        d = ROOT / "data/processed/descriptors" / self.name
        M = np.load(d / f"{arm}_{config}_{mode}.npy", mmap_mode="r")[self.pockets.desc_row.to_numpy()]
        lay = d / f"{arm}_{config}_{mode}.layout.json"
        self.inputs.append(d / f"{arm}_{config}_{mode}.npy")
        return np.asarray(M, np.float64), (json.loads(lay.read_text()) if lay.exists() else None)

    def docking_raw(self, panel: str, mode: str) -> pd.DataFrame:
        f = ROOT / "data/processed/docking" / self.name / f"{panel}{'' if mode == 'L' else '_dmode'}.parquet"
        self.inputs.append(f)
        df = pd.read_parquet(f)
        return df[df.pocket_id.isin(set(self.pockets.pocket_id))].reset_index(drop=True)

    def docking_meta(self) -> pd.DataFrame:
        f = ROOT / "data/processed/docking" / self.name / "pocket_geom.parquet"
        self.inputs.append(f)
        return pd.read_parquet(f)


def _components(n, edges):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    e = np.asarray(list(edges) + [(i, i) for i in range(n)], np.int64)
    g = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n))
    return connected_components(g, directed=False)[1]


def _shared_label_edges(labels):
    edges = []
    for _, idx in pd.Series(labels).groupby(pd.Series(labels)).groups.items():
        idx = list(idx)
        edges += [(idx[0], j) for j in idx[1:]]
    return edges


class ToughM1Dev(DevDataset):
    name = "tough_m1"

    def load(self):
        self.inputs = []
        f_pairs = ROOT / "data/splits/tough_m1_dev_pairs.parquet"
        f_split = ROOT / "data/splits/tough_m1_pockets_split.parquet"
        f_index = ROOT / "data/processed/cache/points/tough_m1/index.parquet"
        f_ids = ROOT / "data/processed/descriptors/tough_m1/a1_default_L.ids.parquet"
        self.inputs += [f_pairs, f_split, f_index, f_ids]
        pairs = pd.read_parquet(f_pairs)
        split = pd.read_parquet(f_split)
        index = pd.read_parquet(f_index)
        ids = pd.read_parquet(f_ids)
        self.split_table = split
        dev = split[split.partition == "dev"].sort_values("pocket_id").reset_index(drop=True)
        ix = index.set_index("pocket_id").loc[dev.pocket_id]
        if not (ix.status == "ok").all():
            raise RuntimeError("dev pocket without a point-cache entry")
        dev["logv_L"] = np.log(ix.volume_A3.to_numpy(float))
        dev["logv_D"] = np.log(np.clip(ix.d_volume_A3.to_numpy(float), 1.0, None))
        dev["d_coverage"] = ix.d_coverage.to_numpy(float)
        dev["d_precision"] = ix.d_precision.to_numpy(float)
        dev["d_match"] = (dev.d_coverage >= 0.3) | (dev.d_precision >= 0.5)        # DESIGN §2.2 / D3
        dev["desc_row"] = pd.Series(np.arange(len(ids)), index=ids.pocket_id).loc[dev.pocket_id].to_numpy()
        # bootstrap units: components of (ligand cluster ∪ homology group) over dev pockets
        dev["unit"] = _components(len(dev), _shared_label_edges(dev.ligand_cluster.to_numpy())
                                  + _shared_label_edges(dev.group_id.to_numpy()))
        self.pockets = dev
        pos = {p: i for i, p in enumerate(dev.pocket_id)}
        if not (pairs.pocket_a.isin(pos) & pairs.pocket_b.isin(pos)).all():
            raise RuntimeError("dev pair with a non-dev pocket")
        self.pairs = pairs.assign(y=pairs.label.astype(int))
        self.ia = pairs.pocket_a.map(pos).to_numpy()
        self.ib = pairs.pocket_b.map(pos).to_numpy()
        y = self.pairs.y.to_numpy() == 1
        pcomp = _components(len(dev), list(zip(self.ia[y], self.ib[y])))
        self.pos_cluster = pcomp[self.ia]
        self.native = {
            "apoc_ps": (pairs.apoc_c1.to_numpy(float), "APoc PS-score (apoc_c1; higher = similar; dataset.info)"),
            "apoc_negp": (-pairs.apoc_c2.to_numpy(float),
                          "−APoc P-value (apoc_c2; Spearman −0.67 with PS-score, label-free)"),
            "glosa_ga": (pairs.glosa_c1.to_numpy(float), "G-LoSA GA-score (glosa_c1; higher = similar; dataset.info)"),
            "siteengine_c1": (pairs.siteengine_c1.to_numpy(float), "SiteEngine column 1 as shipped (undocumented)"),
            "siteengine_c2": (pairs.siteengine_c2.to_numpy(float), "SiteEngine column 2 as shipped (undocumented)"),
            "siteengine_c3": (pairs.siteengine_c3.to_numpy(float), "SiteEngine column 3 as shipped (undocumented)"),
        }
        self.global_scores = {  # B0' (global similarity, from the benchmark lists)
            "tm_score": (pairs.tm_score.to_numpy(float), "Fr-TM-align TM-score (TOUGH-M1 list)"),
            "seq_identity": (pairs.seq_identity.to_numpy(float), "global sequence identity (TOUGH-M1 list)"),
        }
        return self

    def test_units(self) -> dict:
        """Units of TOUGH-M1-test from the partition table alone (no test pair is opened)."""
        t = self.split_table[self.split_table.partition == "test"].reset_index(drop=True)
        u = _components(len(t), _shared_label_edges(t.ligand_cluster.to_numpy())
                        + _shared_label_edges(t.group_id.to_numpy()))
        sizes = np.bincount(u)
        return {"n_pockets": int(len(t)), "n_units": int(len(sizes)), "largest_unit_pockets": int(sizes.max()),
                "n_homology_groups": int(t.group_id.nunique()), "n_ligand_clusters": int(t.ligand_cluster.nunique())}


class BlipsVal(DevDataset):
    """Placeholder.  BLiPS-val needs (after the D9 re-split): pairs from data/splits/blips_val_pairs.parquet;
    pockets = BLiPS sites (point cache + descriptors under data/processed/descriptors/blips/); TWO unit
    definitions (homology group; Butina ligand cluster) bootstrapped separately and combined with
    ``evaluate.wider_ci``; covariate = L-mode log volume; n_bins (5, 5) when < 500 positives; no native scores."""
    name = "blips"
    split = "val"

    def load(self):
        raise NotImplementedError("BLiPS-val adapter: descriptors and the D9 re-split are not available yet")


DATASETS = {"tough_m1": ToughM1Dev, "blips": BlipsVal}


# ============================================================================================== score vectors
@dataclass
class Vec:
    arm: str
    config: str
    variant: str          # raw | csls | native | crossfit | control
    mode: str             # L | D | native
    s: np.ndarray         # one score per dev pair, NaN = missing
    dims: int | None = None
    note: str = ""
    y_override: np.ndarray | None = None   # shuffled-label control only

    @property
    def key(self):
        return f"{self.arm}|{self.config}|{self.variant}|{self.mode}"


def cosine_vectors(M, avail, ia, ib, *, zscore=True, layout=None, block_weights=None, csls=True):
    """Raw cosine and CSLS scores over all pairs (NaN where a pocket is unavailable)."""
    rows = np.where(avail)[0]
    zs = ZScorer.fit(M[rows]) if zscore else None
    Er = embed(M[rows], zs, layout, block_weights)
    E = np.zeros((len(M), Er.shape[1]), np.float32)
    E[rows] = Er
    ok = avail[ia] & avail[ib]
    raw = np.full(len(ia), np.nan)
    raw[ok] = pair_scores(E, ia[ok], ib[ok])
    if not csls:
        return raw, None
    r = np.full(len(M), np.nan)
    r[rows] = csls_r(Er, Er, CSLS_K, query_ids=rows, bg_ids=rows)
    return raw, raw - 0.5 * (r[ia] + r[ib])


def neg_euclid_vectors(M, avail, ia, ib):
    rows = np.where(avail)[0]
    X = M[rows]
    sq = (X ** 2).sum(1)
    S = -np.sqrt(np.clip(sq[:, None] + sq[None, :] - 2 * X @ X.T, 0, None))
    np.fill_diagonal(S, -np.inf)
    r = np.full(len(M), np.nan)
    r[rows] = np.sort(S, axis=1)[:, -CSLS_K:].mean(1)
    ok = avail[ia] & avail[ib]
    raw = np.full(len(ia), np.nan)
    raw[ok] = -np.linalg.norm(M[ia[ok]] - M[ib[ok]], axis=1)
    return raw, raw - 0.5 * (r[ia] + r[ib])


def build_vectors(ds: DevDataset, log) -> tuple[list[Vec], dict]:
    from pocketcompare.descriptors.a2 import A2Config, A2Descriptor

    P, ia, ib = ds.pockets, ds.ia, ds.ib
    allp = np.ones(len(P), bool)
    dm = P.d_match.to_numpy()
    vecs: list[Vec] = []
    meta = {}
    # ---- B0 size only
    lv = P.logv_L.to_numpy()
    vecs.append(Vec("B0", "default", "raw", "L", -np.abs(lv[ia] - lv[ib]), 1, "−|Δ log V| (L-mode)"))
    ld = P.logv_D.to_numpy()
    s = np.where(dm[ia] & dm[ib], -np.abs(ld[ia] - ld[ib]), np.nan)
    vecs.append(Vec("B0", "default", "raw", "D", s, 1, "−|Δ log V| (D-mode volume)"))
    # ---- B0' global similarity, B5-T shipped scores
    for k, (s, note) in ds.global_scores.items():
        vecs.append(Vec("B0p", k, "native", "native", s, None, note))
    for k, (s, note) in ds.native.items():
        vecs.append(Vec("B5T", k, "native", "native", s, None, note))
    # ---- B1, A1 (cosine on z-scored descriptors)
    a1_configs = list(_a1_grid())
    for arm, configs in (("b1", ["default", "learned"]), ("a1", a1_configs)):
        for cfg in configs:
            for mode in ("L", "D"):
                M, lay = ds.descriptor(arm, cfg, mode)
                av = allp if mode == "L" else dm
                raw, cs = cosine_vectors(M, av, ia, ib)
                A = arm.upper()
                vecs += [Vec(A, cfg, "raw", mode, raw, M.shape[1]), Vec(A, cfg, "csls", mode, cs, M.shape[1])]
                if arm == "a1" and cfg == "default":
                    raw, cs = cosine_vectors(M, av, ia, ib, layout=lay, block_weights=A1_BW)
                    vecs += [Vec(A, "default_bw", "raw", mode, raw, M.shape[1], "block-weighted cosine"),
                             Vec(A, "default_bw", "csls", mode, cs, M.shape[1], "block-weighted cosine")]
            log(f"  {arm} {cfg} done")
    # ---- B4 ESM-2 lining-residue mean
    for mode in ("L", "D"):
        f = ROOT / "data/processed/descriptors" / ds.name / f"b4_esm2_{mode}.npy"
        ds.inputs.append(f)
        M = np.asarray(np.load(f, mmap_mode="r")[P.desc_row.to_numpy()], np.float64)
        av = allp if mode == "L" else dm
        raw, cs = cosine_vectors(M, av, ia, ib)
        vecs += [Vec("B4", "esm2", "raw", mode, raw, M.shape[1], "cosine, dev z-scored"),
                 Vec("B4", "esm2", "csls", mode, cs, M.shape[1], "cosine, dev z-scored")]
        raw, cs = cosine_vectors(M, av, ia, ib, zscore=False)
        vecs += [Vec("B4", "esm2_noz", "raw", mode, raw, M.shape[1], "cosine, raw embedding"),
                 Vec("B4", "esm2_noz", "csls", mode, cs, M.shape[1], "cosine, raw embedding")]
    log("  B4 done")
    # ---- B5 EPoCS (L only), −Euclidean
    f = ROOT / "data/processed/descriptors" / ds.name / "b5_epocs.npy"
    ds.inputs.append(f)
    M = np.asarray(np.load(f, mmap_mode="r")[P.desc_row.to_numpy()], np.float64)
    raw, cs = neg_euclid_vectors(M, allp, ia, ib)
    vecs += [Vec("B5", "epocs", "raw", "L", raw, M.shape[1], "−Euclidean (ESM-2 3B, Voronoi pocket)"),
             Vec("B5", "epocs", "csls", "L", cs, M.shape[1], "−Euclidean (ESM-2 3B, Voronoi pocket)")]
    log("  B5 done")
    # ---- A2 docking profiles: fit on the dev pockets of the mode (label-free), per block cosine
    geom = ds.docking_meta()
    a2_meta = {}
    for mode in ("L", "D"):
        for panel in A2_PANELS:
            raw_tab = ds.docking_raw(panel, mode)
            docked = set(raw_tab.pocket_id)
            ref = [p for p, m in zip(P.pocket_id, dm if mode == "D" else allp) if m and p in docked]
            cfg = A2Config(panel=panel) if mode == "L" else A2Config(panel=panel, volume_column="volume_D",
                                                                      buriedness_column="bur16_D")
            raw_tab = raw_tab[raw_tab.pocket_id.isin(set(ref))]
            desc = A2Descriptor(cfg).fit(raw_tab, geom, reference_pocket_ids=ref)
            V = desc.transform(raw_tab, geom)
            pos = pd.Series(np.arange(len(V.pocket_id)), index=V.pocket_id)
            av = P.pocket_id.isin(pos.index).to_numpy()
            a2_meta[f"{panel}_{mode}"] = {"n_reference_pockets": len(ref), "n_available": int(av.sum())}
            for blk in A2_BLOCKS:
                B = getattr(V, blk)
                M = np.zeros((len(P), B.shape[1]))
                M[av] = B[pos.loc[P.pocket_id[av]].to_numpy()]
                raw, cs = cosine_vectors(M, av, ia, ib)
                vecs += [Vec("A2", f"{panel}_{blk}", "raw", mode, raw, B.shape[1]),
                         Vec("A2", f"{panel}_{blk}", "csls", mode, cs, B.shape[1])]
            log(f"  A2 {panel} {mode} done")
    meta["a2"] = a2_meta
    # ---- negative control: random vectors (label-free)
    rng = np.random.default_rng(SEEDS[0])
    M = rng.normal(size=(len(P), 128))
    raw, _ = cosine_vectors(M, allp, ia, ib, csls=False)
    vecs.append(Vec("CTRL", "random128", "control", "L", raw, 128, "Gaussian random 128-d vectors, cosine"))
    return vecs, meta


def _a1_grid():
    import yaml
    g = yaml.safe_load((ROOT / "configs/a1_grid.yaml").read_text())
    return list(g["configs"].keys())


# ============================================================================================= cross-fitting
def unit_folds(units: np.ndarray, n_folds: int, seed: int) -> np.ndarray:
    """Fold per unit id: largest units first (random tie-break), each to the currently smallest fold."""
    uniq, sizes = np.unique(units, return_counts=True)
    tie = np.random.default_rng(seed).permutation(len(uniq))
    order = np.lexsort((tie, -sizes))
    load = np.zeros(n_folds)
    fold = np.empty(len(uniq), np.int64)
    for k in order:
        f = int(np.argmin(load))
        fold[k] = f
        load[f] += sizes[k]
    return fold[np.searchsorted(uniq, units)]


def cross_fit(X, y, fa, fb, n_folds=N_FOLDS, *, method="direction"):
    """Out-of-fold logistic-regression scores; fully unit-disjoint (see module docstring).

    ``method="direction"`` (used for every reported number): features z-scored once on all evaluated pairs
    (label-free), L2 logistic regression per fold-set, OOF score = x · β/‖β‖ (no intercept), so scores pooled
    over fold-sets live on one scale.  ``method="decision"`` (the first implementation, kept as a diagnostic):
    per-fold StandardScaler + ``decision_function`` incl. intercept — with the giant unit the training-set
    prevalence ranges 5–44 % across fold-sets and the pooled scores are dominated by the intercepts."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    sd = X.std(0)
    Xs = (X - X.mean(0)) / np.where(sd > 0, sd, 1.0)
    oof = np.full(len(y), np.nan)
    info, coefs = [], []
    for k in range(n_folds):
        for l in range(k, n_folds):
            test = ((fa == k) & (fb == l)) | ((fa == l) & (fb == k))
            if not test.any():
                continue
            train = ~np.isin(fa, [k, l]) & ~np.isin(fb, [k, l])
            if method == "direction":
                m = LogisticRegression(C=1.0, max_iter=5000).fit(Xs[train], y[train])
                b = m.coef_.ravel()
                oof[test] = Xs[test] @ (b / np.linalg.norm(b))
            else:
                m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))
                m.fit(X[train], y[train])
                oof[test] = m.decision_function(X[test])
                b = m[-1].coef_.ravel()
            coefs.append((b / np.linalg.norm(b)).tolist())
            info.append({"folds": [k, l], "n_test": int(test.sum()), "n_train": int(train.sum()),
                         "n_train_pos": int(y[train].sum())})
    assert np.isfinite(oof).all()
    return oof, {"method": method, "fits": info, "unit_coef_mean": np.mean(coefs, 0).tolist(),
                 "unit_coef_min": np.min(coefs, 0).tolist(), "unit_coef_max": np.max(coefs, 0).tolist()}


# ================================================================================================= metrics
def n_bins_for(y):
    return (5, 20) if int(np.sum(y)) >= 500 else (5, 5)


def point_metrics(y, s, pc, cov):
    nb = n_bins_for(y)
    r = ev.binary_metrics(y, s)
    r["auc_cb"] = ev.cluster_balanced_auc(y, s, pc)["auc_cb"]
    st = ev.stratified_auc(y, s, cov, n_bins=nb)
    r.update(auc_strat=st["auc_strat"], strat_n_bins=f"{nb[0]}x{nb[1]}", strat_n_strata=st["n_strata"],
             strat_n_strata_dropped=st["n_strata_dropped"], strat_frac_pos_dropped=st["frac_pos_weight_dropped"])
    return r


def _generic_task(args):
    key, y, s, pc, cov, ci, cj, B, seed = args
    nb = n_bins_for(y)

    def fn(w):
        return [ev.cluster_balanced_auc(y, s, pc, w)["auc_cb"], ev.stratified_auc(y, s, cov, w, n_bins=nb)["auc_strat"]]

    res = ev.vertex_bootstrap_generic(fn, ci, cj, B=B, seed=seed, names=["auc_cb", "auc_strat"])
    return key, {r.name: r for r in res}


def _pool_init():
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(1)
    except ImportError:
        pass


def run_generic(tasks, threads, log):
    out = {}
    t0 = time.time()
    with mp.get_context("spawn").Pool(threads, initializer=_pool_init) as pool:
        for i, (k, r) in enumerate(pool.imap_unordered(_generic_task, tasks, chunksize=1)):
            out[k] = r
            if (i + 1) % 20 == 0:
                log(f"    generic bootstrap {i + 1}/{len(tasks)} ({time.time() - t0:.0f} s)")
    return out


# ==================================================================================================== main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dataset", default="tough_m1", choices=sorted(DATASETS))
    ap.add_argument("--B", type=int, default=ev.DEFAULT_B)
    ap.add_argument("--seed", type=int, default=SEEDS[0])
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--out", default=str(ROOT / "results/dev"))
    ap.add_argument("--no-trials", action="store_true", help="do not append to results/trials.tsv (smoke tests)")
    args = ap.parse_args()
    os.environ["POCKETCOMPARE_THREADS"] = str(args.threads)
    t_start = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{args.dataset}_dev"

    def log(msg):
        print(f"[{time.time() - t_start:7.1f}s] {msg}", flush=True)

    ds = DATASETS[args.dataset]().load()
    P = ds.pockets
    y_all = ds.pairs.y.to_numpy().astype(bool)
    ci_all, cj_all = P.unit.to_numpy()[ds.ia], P.unit.to_numpy()[ds.ib]
    cov_all = ev.size_covariates(P.logv_L.to_numpy()[ds.ia], P.logv_L.to_numpy()[ds.ib])
    pc_all = ds.pos_cluster
    dm = P.d_match.to_numpy()
    dset = dm[ds.ia] & dm[ds.ib]
    unit_sizes = np.bincount(P.unit.to_numpy())
    units_in_pairs = np.unique(np.concatenate([ci_all, cj_all]))
    log(f"{len(P)} pockets, {len(y_all)} pairs ({y_all.sum()} pos); {len(unit_sizes)} units "
        f"(largest {unit_sizes.max()} pockets), {len(units_in_pairs)} units in pairs; D-set {dset.sum()} pairs")

    vecs, meta = build_vectors(ds, log)
    # B0m diagnostic: cross-fitted logistic on (log va + log vb, |Δ log v|)
    ufold = unit_folds(P.unit.to_numpy(), N_FOLDS, args.seed)
    fa, fb = ufold[ds.ia], ufold[ds.ib]
    lv = P.logv_L.to_numpy()
    Xb0 = np.column_stack([lv[ds.ia] + lv[ds.ib], np.abs(lv[ds.ia] - lv[ds.ib])])
    oof, b0m_info = cross_fit(Xb0, y_all.astype(int), fa, fb)
    vecs.append(Vec("B0m", "logit_sum_absdiff", "crossfit", "L", oof, 2, "diagnostic; must be 0.5 ± 0.03 stratified"))
    meta["b0m"] = b0m_info
    meta["folds"] = {"pockets_per_fold": np.bincount(ufold, minlength=N_FOLDS).tolist(),
                     "pairs_per_foldset": None}
    for v in vecs:  # L-mode / native vectors must be complete
        if v.mode != "D" and np.isnan(v.s).any():
            raise RuntimeError(f"{v.key}: {int(np.isnan(v.s).sum())} NaN scores in a complete mode")
    log(f"{len(vecs)} score vectors built")

    # ------------------------------------------------------------------ evaluation records
    def eval_sets(v: Vec):
        """Primary evaluation mask (pairs) for a vector."""
        if v.mode == "D":
            return dset & ~np.isnan(v.s)
        return np.ones(len(y_all), bool)

    def generic_args(key, v: Vec, mask, y=None):
        y = (y_all if y is None else y)[mask]
        return (key, y, v.s[mask], pc_all[mask], cov_all[mask], ci_all[mask], cj_all[mask], args.B, args.seed)

    tasks = [generic_args(v.key, v, eval_sets(v)) for v in vecs]
    log(f"generic bootstrap (cluster-balanced + stratified AUC) for {len(tasks)} vectors, B={args.B}")
    gen = run_generic(tasks, args.threads, log)

    # ------------------------------------------------------------------ A1 selection (one-SE, cb-AUC, L raw)
    grid = _a1_grid()
    cands = [v for v in vecs if v.arm == "A1" and v.mode == "L" and v.variant == "raw"]
    order = {c: i for i, c in enumerate(grid + ["default_bw"])}
    cb = {v.config: point_metrics(y_all, v.s, pc_all, cov_all)["auc_cb"] for v in cands}
    best = max(cb, key=cb.get)
    se_best = gen[f"A1|{best}|raw|L"]["auc_cb"].se
    within = [v for v in cands if cb[v.config] >= cb[best] - se_best]
    chosen = min(within, key=lambda v: (v.dims, order[v.config])).config
    sel = {"rule": "one-SE on cluster-balanced AUC (TOUGH-M1-dev only; BLiPS-val to be added), L-mode raw cosine; "
                   "simplest = fewest dims, ties -> earlier grid entry",
           "best": best, "best_auc_cb": cb[best], "se_best": se_best, "threshold": cb[best] - se_best,
           "within_one_se": sorted([v.config for v in within], key=lambda c: order[c]),
           "chosen": chosen, "candidates": {c: {"auc_cb": cb[c], "dims": next(v.dims for v in cands if v.config == c)}
                                            for c in cb}}
    log(f"A1 selection: best {best} cb={cb[best]:.4f} SE={se_best:.4f} -> chosen {chosen}")

    # ------------------------------------------------------------------ fusions (cross-fitted, L-mode)
    V = {v.key: v for v in vecs}

    def S(arm, cfg, var):
        return V[f"{arm}|{cfg}|{var}|L"].s

    fusions = {}
    for var in ("raw", "csls"):
        a1 = S("A1", chosen, var)
        frag = [S("A2", f"fragments_{b}", var) for b in A2_BLOCKS]
        lead = [S("A2", f"leadlike_{b}", var) for b in A2_BLOCKS]
        b1 = S("B1", "default", var)
        b4 = S("B4", "esm2", var)
        fusions[f"A1|{var}"] = [a1]
        fusions[f"A1+A2frag|{var}"] = [a1, *frag]
        fusions[f"A1+A2lead|{var}"] = [a1, *lead]
        fusions[f"A1+A2both|{var}"] = [a1, *frag, *lead]
        fusions[f"A1+B1|{var}"] = [a1, b1]
        fusions[f"A1+B1+A2frag|{var}"] = [a1, b1, *frag]
        fusions[f"A1+A2frag+B4|{var}"] = [a1, *frag, b4]
    fus_vecs, fus_info = [], {}
    for name, cols in fusions.items():
        combo, var = name.split("|")
        oof, info = cross_fit(np.column_stack(cols), y_all.astype(int), fa, fb)
        fus_info[name] = info
        fus_vecs.append(Vec("FUSION", f"{combo}[A1={chosen}]", f"crossfit_{var}", "L", oof, len(cols)))
    meta["fusion"] = fus_info
    diag = {}
    for name, X in (("B0m", Xb0), ("A1|raw", np.column_stack(fusions["A1|raw"])),
                    ("A1+A2frag|raw", np.column_stack(fusions["A1+A2frag|raw"]))):
        o, _ = cross_fit(X, y_all.astype(int), fa, fb, method="decision")
        diag[name] = point_metrics(y_all, o, pc_all, cov_all)
    meta["crossfit_decision_diagnostic"] = diag
    meta["folds"]["pairs_per_foldset"] = fus_info[f"A1|raw"]["fits"]
    # shuffled-label control on the chosen A1 (raw)
    rng = np.random.default_rng(SEEDS[0])
    y_shuf = rng.permutation(y_all)
    ctrl_shuf = Vec("CTRL", f"shuffled_labels[A1={chosen}]", "control", "L", S("A1", chosen, "raw"),
                    None, "labels permuted across pairs (seed SEEDS[0])", y_override=y_shuf)
    extra = fus_vecs + [ctrl_shuf]
    log(f"generic bootstrap for {len(extra)} fusion/control vectors")
    gen.update(run_generic([generic_args(v.key, v, eval_sets(v), v.y_override) for v in extra], args.threads, log))
    vecs += extra
    V = {v.key: v for v in vecs}

    # ------------------------------------------------------------------ fast path + table rows (numba, main proc)
    log("fast-path bootstrap (AUC, AP) and table")
    rows = []
    for v in vecs:
        y = y_all if v.y_override is None else v.y_override
        mask = eval_sets(v)
        pm = point_metrics(y[mask], v.s[mask], pc_all[mask], cov_all[mask])
        fb_ = ev.vertex_bootstrap(y[mask], v.s[mask], ci_all[mask], cj_all[mask], B=args.B, seed=args.seed,
                                  n_threads=args.threads)
        g = gen[v.key]
        ref_mask = dset if v.mode == "D" else np.ones(len(y), bool)
        miss = ev.missing_summary(y[ref_mask], {"s": v.s[ref_mask]})["s"]
        row = {"key": v.key, "arm": v.arm, "config": v.config, "variant": v.variant, "mode": v.mode,
               "pairset": "D-set (both D-matched)" if v.mode == "D" else "all dev pairs", "dims": v.dims,
               "note": v.note, "n_pairs": int(mask.sum()), "n_pos": pm["n_pos"], "n_neg": pm["n_neg"],
               "n_missing_in_set_pos": miss["n_missing_pos"], "n_missing_in_set_neg": miss["n_missing_neg"],
               "auc": pm["auc"], "auc_lo": fb_["auc"].ci_low, "auc_hi": fb_["auc"].ci_high, "auc_se": fb_["auc"].se,
               "ap": pm["ap"], "ap_lo": fb_["ap"].ci_low, "ap_hi": fb_["ap"].ci_high, "prevalence": pm["prevalence"],
               "ap_lift": pm["ap_lift"], "pauc_mcclish": pm["pauc_mcclish"], "pauc_raw": pm["pauc_raw"],
               "auc_cb": pm["auc_cb"], "auc_cb_lo": g["auc_cb"].ci_low, "auc_cb_hi": g["auc_cb"].ci_high,
               "auc_cb_se": g["auc_cb"].se, "auc_strat": pm["auc_strat"], "auc_strat_lo": g["auc_strat"].ci_low,
               "auc_strat_hi": g["auc_strat"].ci_high, "auc_strat_se": g["auc_strat"].se,
               "strat_n_bins": pm["strat_n_bins"], "strat_n_strata_dropped": pm["strat_n_strata_dropped"],
               "strat_frac_pos_dropped": pm["strat_frac_pos_dropped"], "n_units": fb_["auc"].n_clusters,
               "n_degenerate": fb_["auc"].n_degenerate, "B": args.B, "seed": args.seed}
        if v.mode == "D":   # worst-case bound + miss rates over ALL dev pairs
            wc, _ = ev.worst_case(y_all, v.s)
            wm = ev.binary_metrics(y_all, wc)
            mall = ev.missing_summary(y_all, {"s": v.s})["s"]
            row.update(auc_worst_all=wm["auc"], ap_worst_all=wm["ap"], miss_rate_pos_all=mall["miss_rate_pos"],
                       miss_rate_neg_all=mall["miss_rate_neg"])
        rows.append(row)
    summary = pd.DataFrame(rows)

    # L-mode arms re-evaluated on the D-set (same pairs as D-mode -> L vs D comparison)
    lvd = []
    for v in vecs:
        if v.mode != "D":
            continue
        kL = v.key[:-1] + "L"
        if kL not in V:
            continue
        m = dset & ~np.isnan(v.s)
        pr = ev.paired_bootstrap(y_all[m], v.s[m], V[kL].s[m], ci_all[m], cj_all[m], B=args.B, seed=args.seed,
                                 n_threads=args.threads)
        pmL = point_metrics(y_all[m], V[kL].s[m], pc_all[m], cov_all[m])
        pmD = point_metrics(y_all[m], v.s[m], pc_all[m], cov_all[m])
        lvd.append({"arm": v.arm, "config": v.config, "variant": v.variant, "n_pairs": int(m.sum()),
                    "auc_L": pmL["auc"], "auc_D": pmD["auc"], "delta_auc_D_minus_L": pr["delta_auc"].estimate,
                    "delta_lo": pr["delta_auc"].ci_low, "delta_hi": pr["delta_auc"].ci_high,
                    "auc_strat_L": pmL["auc_strat"], "auc_strat_D": pmD["auc_strat"],
                    "auc_cb_L": pmL["auc_cb"], "auc_cb_D": pmD["auc_cb"]})
    lvd = pd.DataFrame(lvd)

    # CSLS effect (paired, same pairs): AUC via fast paired bootstrap; cb / strat via paired generic replicates
    def gdelta(ka, kb, metric, name):
        ra, rb = gen[ka][metric], gen[kb][metric]
        return ev._summarise(name, ra.estimate - rb.estimate, ra.replicates - rb.replicates, alpha=0.05,
                             seed=args.seed, K=ra.n_clusters, diff=True)

    csls_rows = []
    for v in vecs:
        if v.variant != "csls":
            continue
        kr = v.key.replace("|csls|", "|raw|")
        m = eval_sets(v) & eval_sets(V[kr])
        if not (m == eval_sets(v)).all() or not (m == eval_sets(V[kr])).all():
            continue
        pr = ev.paired_bootstrap(y_all[m], v.s[m], V[kr].s[m], ci_all[m], cj_all[m], B=args.B, seed=args.seed,
                                 n_threads=args.threads)
        dcb = gdelta(v.key, kr, "auc_cb", "d_cb")
        dst = gdelta(v.key, kr, "auc_strat", "d_strat")
        csls_rows.append({"arm": v.arm, "config": v.config, "mode": v.mode,
                          "delta_auc": pr["delta_auc"].estimate, "delta_auc_lo": pr["delta_auc"].ci_low,
                          "delta_auc_hi": pr["delta_auc"].ci_high, "delta_cb": dcb.estimate, "delta_cb_lo": dcb.ci_low,
                          "delta_cb_hi": dcb.ci_high, "delta_strat": dst.estimate, "delta_strat_lo": dst.ci_low,
                          "delta_strat_hi": dst.ci_high})
    csls_df = pd.DataFrame(csls_rows)

    # ------------------------------------------------------------------ A2 gate
    gate = {}
    for var in ("raw", "csls"):
        base = f"FUSION|A1[A1={chosen}]|crossfit_{var}|L"
        for combo in ("A1+A2frag", "A1+A2lead", "A1+A2both", "A1+B1", "A1+B1+A2frag", "A1+A2frag+B4"):
            k = f"FUSION|{combo}[A1={chosen}]|crossfit_{var}|L"
            d = gdelta(k, base, "auc_strat", "delta_strat")
            pr = ev.paired_bootstrap(y_all, V[k].s, V[base].s, ci_all, cj_all, B=args.B, seed=args.seed,
                                     n_threads=args.threads)
            d_raw = gdelta(k, f"A1|{chosen}|{var}|L", "auc_strat", "delta_strat_vs_uncrossfitted_A1")
            gate[f"{combo}|{var}"] = {
                "delta_strat_vs_cf_A1": d.to_dict(), "delta_auc_vs_cf_A1": pr["delta_auc"].to_dict(),
                "delta_strat_vs_raw_A1": d_raw.to_dict(),
                "pass": bool(d.estimate >= 0.01 and d.ci_low > 0) if "A2" in combo and "B" not in combo else None}
    gate_primary = gate["A1+A2frag|raw"]
    log(f"A2 gate (primary): Δ strat = {gate_primary['delta_strat_vs_cf_A1']['estimate']:.4f} "
        f"[{gate_primary['delta_strat_vs_cf_A1']['ci_low']:.4f}, {gate_primary['delta_strat_vs_cf_A1']['ci_high']:.4f}]"
        f" -> {'PASS' if gate_primary['pass'] else 'FAIL'}")

    # ------------------------------------------------------------------ MDE for C1
    tu = ds.test_units()
    n_units_dev = int(len(unit_sizes))
    single = summary[(summary["mode"] == "L") & summary.arm.isin(["A1", "A2"])
                     & summary.variant.isin(["raw", "csls"])]
    top = single.sort_values("auc", ascending=False).iloc[0]
    mde = {"n_units_dev_pockets": n_units_dev, "n_units_dev_in_pairs": int(len(units_in_pairs)), "test": tu,
           "comparisons": {}}
    for label, (arm, cfg, var) in {"best_single_arm": (top.arm, top.config, top.variant),
                                   "chosen_A1_raw": ("A1", chosen, "raw")}.items():
        for base in ("B1|default", "B4|esm2"):
            kb = f"{base}|{var}|L"
            pr = ev.paired_bootstrap(y_all, V[f"{arm}|{cfg}|{var}|L"].s, V[kb].s, ci_all, cj_all, B=args.B,
                                     seed=args.seed, n_threads=args.threads)
            se = pr["delta_auc"].se
            mde["comparisons"][f"{label}:{arm}|{cfg}|{var} - {kb}"] = {
                "delta_auc_dev": pr["delta_auc"].to_dict(),
                "mde_test": ev.mde_scaled(se, n_units_dev, tu["n_units"]),
                "mde_test_if_units_were_homology_groups": ev.mde_scaled(se, n_units_dev, tu["n_homology_groups"]),
                "mde_dev": ev.mde(se)}

    # ------------------------------------------------------------------ write outputs
    details = {"dataset": args.dataset, "split": ds.split, "B": args.B, "seed": args.seed,
               "n_pockets": int(len(P)), "n_pairs": int(len(y_all)), "n_pos": int(y_all.sum()),
               "units": {"n": n_units_dev, "largest": int(unit_sizes.max()),
                         "sizes_top10": np.sort(unit_sizes)[::-1][:10].tolist(),
                         "frac_pairs_within_unit": float(np.mean(ci_all == cj_all)),
                         "frac_pairs_touching_largest": float(np.mean((ci_all == np.argmax(unit_sizes))
                                                                      | (cj_all == np.argmax(unit_sizes))))},
               "pos_clusters": {"n": int(len(np.unique(pc_all[y_all]))),
                                "top_share": float(pd.Series(pc_all[y_all]).value_counts(normalize=True).iloc[0])},
               "d_mode": {"n_pockets_matched": int(dm.sum()), "n_pairs_dset": int(dset.sum()),
                          "n_pos_dset": int((dset & y_all).sum())},
               "selection": sel, "gate": gate, "mde": mde, "build": meta,
               "native_score_notes": {k: n for k, (_, n) in ds.native.items()},
               "lvd": lvd.to_dict(orient="records"), "csls": csls_df.to_dict(orient="records")}
    cfg = {"dataset": args.dataset, "B": args.B, "seed": args.seed, "csls_k": CSLS_K, "n_folds": N_FOLDS,
           "strata": "(5,20) if n_pos >= 500 else (5,5)", "a1_grid": "configs/a1_grid.yaml"}
    inputs = sorted(set(map(str, ds.inputs)) | {str(ROOT / "src/pocketcompare/descriptors/a2.py"),
                                               str(ROOT / "src/pocketcompare/similarity.py"),
                                               str(ROOT / "configs/a1_grid.yaml")})
    common = dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=inputs, seed=args.seed, device="cpu",
                  start_time=t_start)
    f_sum = out / f"{tag}_summary.parquet"
    write_result(f_sum, summary, **common)
    write_result(out / f"{tag}_details.json", details, **common)
    reps = {}
    for k, g in gen.items():
        for m_, r in g.items():
            reps[f"{k}::{m_}"] = r.replicates
    write_result(out / f"{tag}_replicates.parquet", pd.DataFrame(reps), **common)
    f_md = out / f"{tag}_summary.md"
    f_md.write_text(render_md(summary, lvd, csls_df, sel, gate, mde, details))
    prov = {"result": str(f_md), "result_sha256": sha256_file(f_md), **git_state(), "script": str(Path(__file__)),
            "script_sha256": sha256_file(__file__), "args": sys.argv[1:], "config": cfg,
            "evaluate_sha256": ev.module_sha256(), "derived_from": [str(f_sum), str(out / f"{tag}_details.json")],
            "seed": args.seed, "wall_seconds": round(time.time() - t_start, 1)}
    (out / f"{tag}_summary.md.prov.json").write_text(json.dumps(prov, indent=2, default=str) + "\n")
    if not args.no_trials:
        for r in rows:
            metrics = {k: r[k] for k in ("n_pairs", "n_pos", "auc", "auc_lo", "auc_hi", "ap", "ap_lift",
                                         "pauc_mcclish", "auc_cb", "auc_cb_lo", "auc_cb_hi", "auc_strat",
                                         "auc_strat_lo", "auc_strat_hi")}
            append_trial(r["arm"], {"config": r["config"], "variant": r["variant"], "mode": r["mode"],
                                    "pairset": r["pairset"], "B": args.B, "seed": args.seed},
                         f"{args.dataset}_{ds.split}", metrics, f_sum)
    log(f"done: {f_sum}")


def _f(x, d=3):
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def render_md(summary, lvd, csls_df, sel, gate, mde, details) -> str:
    L = [f"# {details['dataset']}-{details['split']} — all arms (auto-generated by scripts/eval_dev.py)", "",
         f"Pairs {details['n_pairs']} ({details['n_pos']} pos); units {details['units']['n']} (largest "
         f"{details['units']['largest']} pockets); B = {details['B']}, seed {details['seed']}. CIs: 95 % vertex "
         "bootstrap percentile. Strat = 2-D size-stratified AUC (L-mode log volume).", "",
         "| arm | config | variant | mode | n pairs | ROC-AUC [CI] | AP (lift) | pAUC₀.₁ | cluster-bal. AUC [CI] | "
         "strat. AUC [CI] | worst-case AUC (all pairs) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in summary.itertuples():
        L.append(f"| {r.arm} | {r.config} | {r.variant} | {r.mode} | {r.n_pairs} | {_f(r.auc)} [{_f(r.auc_lo)}, "
                 f"{_f(r.auc_hi)}] | {_f(r.ap)} ({_f(r.ap_lift, 2)}) | {_f(r.pauc_mcclish)} | {_f(r.auc_cb)} "
                 f"[{_f(r.auc_cb_lo)}, {_f(r.auc_cb_hi)}] | {_f(r.auc_strat)} [{_f(r.auc_strat_lo)}, "
                 f"{_f(r.auc_strat_hi)}] | {_f(getattr(r, 'auc_worst_all', np.nan))} |")
    L += ["", f"## A1 selection\nbest {sel['best']} (cb {sel['best_auc_cb']:.4f}, SE {sel['se_best']:.4f}); within "
          f"one SE: {', '.join(sel['within_one_se'])}; **chosen {sel['chosen']}**.", "", "## A2 gate and fusions "
          "(Δ size-stratified AUC vs cross-fitted A1 alone)", "", "| fusion | inputs | Δ strat [CI] | Δ AUC [CI] | gate |",
          "|---|---|---|---|---|"]
    for k, g in gate.items():
        c, var = k.split("|")
        d, a = g["delta_strat_vs_cf_A1"], g["delta_auc_vs_cf_A1"]
        L.append(f"| {c} | {var} | {d['estimate']:+.4f} [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}] | "
                 f"{a['estimate']:+.4f} [{a['ci_low']:+.4f}, {a['ci_high']:+.4f}] | "
                 f"{'' if g['pass'] is None else ('PASS' if g['pass'] else 'FAIL')} |")
    L += ["", "## CSLS − raw (paired)", "", "| arm | config | mode | Δ AUC [CI] | Δ cb [CI] | Δ strat [CI] |",
          "|---|---|---|---|---|---|"]
    for r in csls_df.itertuples():
        L.append(f"| {r.arm} | {r.config} | {r.mode} | {r.delta_auc:+.3f} [{r.delta_auc_lo:+.3f}, {r.delta_auc_hi:+.3f}]"
                 f" | {r.delta_cb:+.3f} [{r.delta_cb_lo:+.3f}, {r.delta_cb_hi:+.3f}] | {r.delta_strat:+.3f} "
                 f"[{r.delta_strat_lo:+.3f}, {r.delta_strat_hi:+.3f}] |")
    L += ["", "## D − L on the D-set (paired)", "", "| arm | config | variant | n | AUC L | AUC D | Δ [CI] | strat L | "
          "strat D |", "|---|---|---|---|---|---|---|---|---|"]
    for r in lvd.itertuples():
        L.append(f"| {r.arm} | {r.config} | {r.variant} | {r.n_pairs} | {r.auc_L:.3f} | {r.auc_D:.3f} | "
                 f"{r.delta_auc_D_minus_L:+.3f} [{r.delta_lo:+.3f}, {r.delta_hi:+.3f}] | {r.auc_strat_L:.3f} | "
                 f"{r.auc_strat_D:.3f} |")
    L += ["", "## MDE (C1, one-sided α 0.05, power 0.8)", ""]
    for k, c in mde["comparisons"].items():
        d = c["delta_auc_dev"]
        L.append(f"- {k}: dev Δ {d['estimate']:+.4f} [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}], SE {d['se']:.4f} → "
                 f"MDE test {c['mde_test']['mde']:.4f} (units {c['mde_test']['n_units_dev']}→"
                 f"{c['mde_test']['n_units_test']})")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
