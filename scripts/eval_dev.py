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

BLiPS-val v2 (``--dataset blips``) — choices fixed BEFORE the first BLiPS/PPIPS run (2026-10-27, eval agent 2)
----------------------------------------------------------------------------------------------------------
* Pairs data/splits/blips_val_pairs_v2.parquet (563 pos / 2,815 neg), pockets = the 511 val sites of
  blips_sites_v2 (point cache ``blips``).  Arms B0, B0m, B1 (default, learned), B4 (z / raw), A1 (16 configs +
  default_bw), random control; raw and CSLS (background = all val pockets of the mode); L and D mode (D-set = both
  sites D-matched, coverage >= 0.3 OR precision >= 0.5; worst-case + miss rates on all pairs of the subset).
* Positive cluster (cb-AUC) = ``pair_cluster`` (Butina 0.6 cluster of the shared ligand, the cap unit).
* Units: (hom) homology group ``group_id`` and (lig) Butina cluster of the site's label ligand ``label_cluster``;
  every CI is computed under both and the WIDER one is reported (``evaluate.wider_ci``); both are kept as columns.
  B0m cross-fitting folds use the homology-group units.
* Subsets (all with all negatives unless stated): all; no_promiscuous (drop every pair with ``promiscuous``,
  pos and neg); n_shared_1 / n_shared_ge2 (positives of that stratum + all negatives); chemotype_unseen /
  chemotype_seen (positives with that ``chemotype_seen`` flag + all negatives).  Strata (5,20) iff >= 500 pos.
* A1 selection (amendment D11): objective = mean of the four cluster-balanced AUCs {TOUGH-M1-dev L, TOUGH-M1-dev D,
  BLiPS-val L, BLiPS-val D}, raw cosine, candidates = 16 grid configs + default_bw.  SE: one generic vertex
  bootstrap per dataset whose statistic is the pair (cb_L, cb_D) evaluated with the SAME replicate weights (D on the
  D-set subset of the pairs), so the L/D correlation is kept; TOUGH-M1 (units: ligand cluster ∪ homology group,
  seed SEEDS[0]) and BLiPS (seed [SEEDS[0], 1]) are bootstrapped independently and combined replicate-by-replicate
  (replicate b of the mean = mean of the four replicate-b values; as ``evaluate.macro_paired_bootstrap``).  The
  BLiPS unit definition giving the larger SE of the best candidate's mean is used.  One-SE rule as before.

PPIPS-val (``--dataset ppips``) — fixed BEFORE the first run
------------------------------------------------------------
* Pockets = merged region-rule pockets (D mode only).  Every z-score (B1, B4-z, A1) and the A2 reference fit use
  PPIPS-TRAIN pockets only; CSLS background = all val pockets (k = 10).  Arms: B0 (−|Δ log V|), B1 default /
  learned, B4 z / raw, A1 chosen (D11) + default, A2 {fragments, leadlike} × {rank, le_resid, ifp}.
* P-ortho: query -> rank of its Jaccard >= 0.5 counterpart among ALL pockets of the partner complex
  (``evaluate.retrieval_metrics``, pessimistic ties); top-1, top-3, MRR.  P-sym: each pair in both directions;
  candidates = all other val pockets; rank percentile = 1 − (rank − 1) / (N_val − 2); reported for all pairs and
  interface pairs.  Bootstrap units = complex homology group (``ppips_complex_splits.group``) of the query.
* PPI sub-hypothesis (DESIGN §3 A2, pre-registered direction fragments > lead-like): paired Δ (fragments −
  lead-like) of P-ortho MRR and top-1 per A2 block, raw and CSLS.  Verdict rule: SUPPORTED iff, for the raw
  variant, at least one block has Holm-adjusted (3 blocks) one-sided bootstrap p < 0.05 for Δ MRR and no block has
  Δ MRR with 95 % CI entirely < 0; otherwise NOT SUPPORTED.  Buriedness tertiles (``bur16_L`` of the query pocket,
  edges from the val queries) reported descriptively (lowest tertile = shallow).
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
    arms = frozenset({"B0", "B0p", "B5T", "B1", "A1", "B4", "B5", "A2", "CTRL"})   # arms build_vectors computes
    native: dict = {}
    global_scores: dict = {}

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
    """BLiPS-val v2 (D9 re-split).  Extra attributes: ``unit_defs`` {hom, lig: unit per pocket} (two bootstrap unit
    definitions, wider CI reported) and ``subsets`` {name: pair mask}.  ``pockets.unit`` = homology-group units
    (used for the B0m cross-fitting folds).  No native or global scores; arms without BLiPS inputs are skipped."""
    name = "blips"
    split = "val"
    arms = frozenset({"B0", "B1", "A1", "B4", "CTRL"})

    def load(self):
        self.inputs = []
        f_pairs = ROOT / "data/splits/blips_val_pairs_v2.parquet"
        f_sites = ROOT / "data/splits/blips_sites_v2.parquet"
        f_index = ROOT / "data/processed/cache/points/blips/index.parquet"
        f_ids = ROOT / "data/processed/descriptors/blips/a1_default_L.ids.parquet"
        self.inputs += [f_pairs, f_sites, f_index, f_ids]
        pairs = pd.read_parquet(f_pairs)
        sites = pd.read_parquet(f_sites)
        index = pd.read_parquet(f_index)
        ids = pd.read_parquet(f_ids)
        val = sites[sites.partition == "val"].sort_values("site_id").reset_index(drop=True)
        ix = index.set_index("pocket_id").loc[val.site_id]
        if not (ix.status == "ok").all():
            raise RuntimeError("val site without a point-cache entry")
        P = pd.DataFrame({"pocket_id": val.site_id.to_numpy(), "group_id": val.group_id.to_numpy(),
                          "label_cluster": val.label_cluster.to_numpy()})
        P["logv_L"] = np.log(ix.volume_A3.to_numpy(float))
        P["logv_D"] = np.log(np.clip(ix.d_volume_A3.to_numpy(float), 1.0, None))
        P["d_coverage"] = ix.d_coverage.to_numpy(float)
        P["d_precision"] = ix.d_precision.to_numpy(float)
        P["d_match"] = (P.d_coverage >= 0.3) | (P.d_precision >= 0.5)              # DESIGN §2.2 / D3
        P["desc_row"] = pd.Series(np.arange(len(ids)), index=ids.pocket_id).loc[P.pocket_id].to_numpy()
        hom = pd.factorize(P.group_id)[0]
        lig = pd.factorize(P.label_cluster)[0]
        P["unit"] = hom
        self.unit_defs = {"hom": hom, "lig": lig}
        self.pockets = P
        pos = {p: i for i, p in enumerate(P.pocket_id)}
        if not (pairs.site_a.isin(pos) & pairs.site_b.isin(pos)).all():
            raise RuntimeError("val pair with a non-val site")
        self.pairs = pairs.assign(y=pairs.label.astype(int))
        self.ia = pairs.site_a.map(pos).to_numpy()
        self.ib = pairs.site_b.map(pos).to_numpy()
        y = self.pairs.y.to_numpy() == 1
        self.pos_cluster = pairs.pair_cluster.to_numpy()
        neg = ~y
        cs = pairs.chemotype_seen.to_numpy()
        self.subsets = {
            "all": np.ones(len(y), bool),
            "no_promiscuous": ~pairs.promiscuous.to_numpy(bool),
            "n_shared_1": neg | (y & (pairs.n_shared.to_numpy() == 1)),
            "n_shared_ge2": neg | (y & (pairs.n_shared.to_numpy() >= 2)),
            "chemotype_seen": neg | (y & (cs == True)),  # noqa: E712 (object column)
            "chemotype_unseen": neg | (y & (cs == False)),  # noqa: E712
        }
        return self

    def test_units(self) -> dict:
        return {}


class PpipsVal(DevDataset):
    """PPIPS-val (retrieval tasks, D mode only).  ``pockets`` = ALL PPIPS pockets (train rows are the z-score / A2
    reference, never evaluated); ``val`` / ``train`` masks; ``ortho`` and ``sym`` = the val task tables."""
    name = "ppips"
    split = "val"

    def load(self):
        self.inputs = []
        f_pk = ROOT / "data/processed/ppi/ppips/pockets.parquet"
        f_cs = ROOT / "data/splits/ppips_complex_splits.parquet"
        f_geom = ROOT / "data/processed/docking/ppips/pocket_geom.parquet"
        f_ids = ROOT / "data/processed/descriptors/ppips/a1_default_D.ids.parquet"
        f_q = ROOT / "data/splits/ppips_ortho_queries_val.parquet"
        f_s = ROOT / "data/splits/ppips_sym_pairs_val.parquet"
        self.inputs += [f_pk, f_cs, f_geom, f_ids, f_q, f_s]
        pk = pd.read_parquet(f_pk)
        geom = pd.read_parquet(f_geom)
        ids = pd.read_parquet(f_ids)
        cs = pd.read_parquet(f_cs)
        if not ((geom.pocket_id.to_numpy() == pk.pocket_id.to_numpy()).all()
                and (ids.pocket_id.to_numpy() == pk.pocket_id.to_numpy()).all()):
            raise RuntimeError("PPIPS pocket tables are not row-aligned")
        P = pk[["pocket_id", "complex", "is_interface", "split", "volume_A3", "f_min"]].copy()
        P["group"] = P.complex.map(dict(zip(cs.complex, cs.group)))
        P["logv"] = np.log(np.clip(P.volume_A3.to_numpy(float), 1.0, None))
        P["bur16"] = geom.bur16_L.to_numpy(float)
        P["desc_row"] = np.arange(len(P))
        self.pockets = P
        self.geom = geom
        self.val = (P.split == "val").to_numpy()
        self.train = (P.split == "train").to_numpy()
        self.ortho = pd.read_parquet(f_q)
        self.sym = pd.read_parquet(f_s)
        return self


DATASETS = {"tough_m1": ToughM1Dev, "blips": BlipsVal, "ppips": PpipsVal}


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
    if "B5" not in ds.arms:     # BLiPS: no B5 / A2 inputs
        rng = np.random.default_rng(SEEDS[0])
        M = rng.normal(size=(len(P), 128))
        raw, _ = cosine_vectors(M, allp, ia, ib, csls=False)
        vecs.append(Vec("CTRL", "random128", "control", "L", raw, 128, "Gaussian random 128-d vectors, cosine"))
        return vecs, meta
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


def _safe_generic_task(args):
    """As _generic_task, but a statistic whose replicates are all degenerate (tiny subsets) gives None."""
    try:
        return _generic_task(args)
    except ValueError:
        return args[0], None


def run_generic(tasks, threads, log, fn=_generic_task):
    out = {}
    t0 = time.time()
    with mp.get_context("spawn").Pool(threads, initializer=_pool_init) as pool:
        for i, (k, r) in enumerate(pool.imap_unordered(fn, tasks, chunksize=1)):
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
    ap.add_argument("--a1-chosen", default=None,
                    help="ppips only: A1 config chosen under D11 (default: read results/dev/blips_val_details.json)")
    args = ap.parse_args()
    os.environ["POCKETCOMPARE_THREADS"] = str(args.threads)
    if args.dataset == "blips":
        return main_blips(args)
    if args.dataset == "ppips":
        return main_ppips(args)
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


# ============================================================================================ BLiPS-val (v2)
UNIT_NAMES = {"hom": "homology group", "lig": "Butina ligand cluster (label ligand)"}


def _wider(per: dict):
    """{unit: BootstrapResult | None} -> (BootstrapResult with the wider CI, its unit) or (None, None)."""
    ok = {u: r for u, r in per.items() if r is not None}
    if not ok:
        return None, None
    w = ev.wider_ci(*ok.values())
    return w, next(u for u, r in ok.items() if r is w)


def _ci_cols(row, prefix, per):
    """Write <prefix>_lo/_hi/_se (wider CI), <prefix>_ci_unit and per-unit lo/hi columns into ``row``."""
    w, wu = _wider(per)
    row[f"{prefix}_lo"] = w.ci_low if w else np.nan
    row[f"{prefix}_hi"] = w.ci_high if w else np.nan
    row[f"{prefix}_se"] = w.se if w else np.nan
    row[f"{prefix}_ci_unit"] = wu
    for u, r in per.items():
        row[f"{prefix}_lo_{u}"] = r.ci_low if r is not None else np.nan
        row[f"{prefix}_hi_{u}"] = r.ci_high if r is not None else np.nan
    return w


def _select_task(a):
    """Joint (cb_L, cb_D) generic bootstrap with identical replicate weights (D on the D-set pairs)."""
    key, y, sL, sD, dmask, pc, ci, cj, B, seed = a

    def fn(w):
        return [ev.cluster_balanced_auc(y, sL, pc, w)["auc_cb"],
                ev.cluster_balanced_auc(y[dmask], sD[dmask], pc[dmask], w[dmask])["auc_cb"]]

    res = ev.vertex_bootstrap_generic(fn, ci, cj, B=B, seed=seed, names=["cb_L", "cb_D"])
    return key, {r.name: r for r in res}


def _a1_raw(ds):
    """{(config, mode): raw cosine per pair} for the 16 grid configs + default_bw (as build_vectors)."""
    P, ia, ib = ds.pockets, ds.ia, ds.ib
    allp, dm = np.ones(len(P), bool), P.d_match.to_numpy()
    out, dims = {}, {}
    for cfg in _a1_grid():
        for mode in ("L", "D"):
            M, lay = ds.descriptor("a1", cfg, mode)
            av = allp if mode == "L" else dm
            out[(cfg, mode)], _ = cosine_vectors(M, av, ia, ib, csls=False)
            dims[cfg] = M.shape[1]
            if cfg == "default":
                out[("default_bw", mode)], _ = cosine_vectors(M, av, ia, ib, layout=lay, block_weights=A1_BW,
                                                              csls=False)
                dims["default_bw"] = M.shape[1]
    return out, dims


def select_a1_d11(args, bl, bl_V, log):
    """Amended A1 selection (D11): mean cb-AUC over {TOUGH-M1-dev L, D, BLiPS-val L, D}; one-SE rule."""
    grid = _a1_grid()
    order = {c: i for i, c in enumerate(grid + ["default_bw"])}
    cands = grid + ["default_bw"]
    tm = ToughM1Dev().load()
    tm_s, dims = _a1_raw(tm)
    tasks = []
    # TOUGH-M1-dev: harness units (ligand cluster ∪ homology group), seed SEEDS[0]
    y_t = tm.pairs.y.to_numpy().astype(bool)
    dm_t = tm.pockets.d_match.to_numpy()
    dset_t = dm_t[tm.ia] & dm_t[tm.ib]
    u_t = tm.pockets.unit.to_numpy()
    for c in cands:
        tasks.append((("tm", c, "u"), y_t, tm_s[(c, "L")], np.nan_to_num(tm_s[(c, "D")]), dset_t, tm.pos_cluster,
                      u_t[tm.ia], u_t[tm.ib], args.B, args.seed))
    y_b = bl.pairs.y.to_numpy().astype(bool)
    dm_b = bl.pockets.d_match.to_numpy()
    dset_b = dm_b[bl.ia] & dm_b[bl.ib]
    for c in cands:
        sL, sD = bl_V[f"A1|{c}|raw|L"].s, np.nan_to_num(bl_V[f"A1|{c}|raw|D"].s)
        for un, arr in bl.unit_defs.items():
            tasks.append((("bl", c, un), y_b, sL, sD, dset_b, bl.pos_cluster, arr[bl.ia], arr[bl.ib], args.B,
                          [args.seed, 1]))
    log(f"A1 selection (D11): {len(tasks)} joint (cb_L, cb_D) bootstraps")
    res = run_generic(tasks, args.threads, log, fn=_select_task)
    tm1 = {c: res[("tm", c, "u")] for c in cands}
    table, se_by_unit = {}, {}
    for un in bl.unit_defs:
        for c in cands:
            b = res[("bl", c, un)]
            comps = [tm1[c]["cb_L"], tm1[c]["cb_D"], b["cb_L"], b["cb_D"]]
            reps = np.mean(np.vstack([r.replicates for r in comps]), axis=0)     # NaN in any -> NaN
            est = float(np.mean([r.estimate for r in comps]))
            s = ev._summarise("mean_cb_4", est, reps, alpha=0.05, seed=args.seed, K=None)
            se_by_unit[(c, un)] = s
            table.setdefault(c, {"dims": dims[c], "mean_cb": est,
                                 "tm_L": comps[0].estimate, "tm_D": comps[1].estimate,
                                 "bl_L": comps[2].estimate, "bl_D": comps[3].estimate})
            table[c][f"se_{un}"] = s.se
            table[c][f"ci_{un}"] = [s.ci_low, s.ci_high]
            table[c][f"n_degenerate_{un}"] = s.n_degenerate
    best = max(cands, key=lambda c: table[c]["mean_cb"])
    un_used = max(bl.unit_defs, key=lambda u: se_by_unit[(best, u)].se)
    se_best = se_by_unit[(best, un_used)].se
    thr = table[best]["mean_cb"] - se_best
    within = [c for c in cands if table[c]["mean_cb"] >= thr]
    chosen = min(within, key=lambda c: (dims[c], order[c]))
    # old (TOUGH-M1-dev L only) rule for reference
    old_best = max(cands, key=lambda c: table[c]["tm_L"])
    sel = {"rule": "D11: mean cluster-balanced AUC over {TOUGH-M1-dev L, TOUGH-M1-dev D, BLiPS-val L, BLiPS-val D}, "
                   "raw cosine; one-SE rule (SE = sd of the replicate-wise mean of the four bootstrap replicates; "
                   "TOUGH-M1 and BLiPS bootstrapped independently; within a dataset L and D share replicate "
                   "weights); simplest = fewest dims, ties -> earlier grid entry",
           "best": best, "best_mean_cb": table[best]["mean_cb"], "se_best": se_best,
           "se_blips_unit_used": un_used, "threshold": thr,
           "within_one_se": sorted(within, key=lambda c: order[c]), "chosen": chosen,
           "previous_rule_best_tm_L": old_best, "candidates": table,
           "tm_units": int(len(np.unique(u_t))), "B": args.B,
           "seeds": {"tough_m1": args.seed, "blips": [args.seed, 1]}}
    log(f"A1 selection D11: best {best} mean_cb={table[best]['mean_cb']:.4f} SE={se_best:.4f} ({un_used}) -> "
        f"chosen {chosen}")
    return sel, tm.inputs


def main_blips(args):
    t_start = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = "blips_val"

    def log(msg):
        print(f"[{time.time() - t_start:7.1f}s] {msg}", flush=True)

    ds = BlipsVal().load()
    P, ia, ib = ds.pockets, ds.ia, ds.ib
    y_all = ds.pairs.y.to_numpy().astype(bool)
    lv = P.logv_L.to_numpy()
    cov_all = ev.size_covariates(lv[ia], lv[ib])
    pc_all = ds.pos_cluster
    dm = P.d_match.to_numpy()
    dset = dm[ia] & dm[ib]
    UD = {u: (a[ia], a[ib]) for u, a in ds.unit_defs.items()}
    subsets = ds.subsets
    log(f"{len(P)} sites, {len(y_all)} pairs ({y_all.sum()} pos); units hom {len(np.unique(ds.unit_defs['hom']))}, "
        f"lig {len(np.unique(ds.unit_defs['lig']))}; D-matched sites {dm.sum()}; D-set {dset.sum()} pairs "
        f"({(dset & y_all).sum()} pos)")
    vecs, meta = build_vectors(ds, log)
    ufold = unit_folds(P.unit.to_numpy(), N_FOLDS, args.seed)
    fa, fb = ufold[ia], ufold[ib]
    Xb0 = np.column_stack([lv[ia] + lv[ib], np.abs(lv[ia] - lv[ib])])
    oof, b0m_info = cross_fit(Xb0, y_all.astype(int), fa, fb)
    vecs.append(Vec("B0m", "logit_sum_absdiff", "crossfit", "L", oof, 2,
                    "diagnostic; must be 0.5 ± 0.03 stratified (folds: homology-group units)"))
    meta["b0m"] = b0m_info
    for v in vecs:
        if v.mode != "D" and np.isnan(v.s).any():
            raise RuntimeError(f"{v.key}: NaN scores in a complete mode")
    V = {v.key: v for v in vecs}
    log(f"{len(vecs)} score vectors built")

    def eval_set(v):
        return (dset & ~np.isnan(v.s)) if v.mode == "D" else np.ones(len(y_all), bool)

    def ok_mask(m):
        n = int(y_all[m].sum())
        return 0 < n < int(m.sum())

    tasks = []
    for v in vecs:
        for sn, sm in subsets.items():
            m = eval_set(v) & sm
            if not ok_mask(m):
                continue
            for un, (ci, cj) in UD.items():
                tasks.append((f"{v.key}#{sn}#{un}", y_all[m], v.s[m], pc_all[m], cov_all[m], ci[m], cj[m], args.B,
                              args.seed))
    log(f"generic bootstrap (cb + strat) for {len(tasks)} vector × subset × unit tasks, B={args.B}")
    gen = run_generic(tasks, args.threads, log, fn=_safe_generic_task)

    # ---------------------------------------------------------------- table rows
    log("fast-path bootstrap and table")
    rows = []
    for v in vecs:
        for sn, sm in subsets.items():
            m = eval_set(v) & sm
            if not ok_mask(m):
                continue
            y, s = y_all[m], v.s[m]
            pm = point_metrics(y, s, pc_all[m], cov_all[m])
            fast = {un: ev.vertex_bootstrap(y, s, ci[m], cj[m], B=args.B, seed=args.seed, n_threads=args.threads)
                    for un, (ci, cj) in UD.items()}
            row = {"key": v.key, "subset": sn, "arm": v.arm, "config": v.config, "variant": v.variant,
                   "mode": v.mode, "pairset": "D-set (both D-matched)" if v.mode == "D" else "all val pairs",
                   "dims": v.dims, "note": v.note, "n_pairs": int(m.sum()), "n_pos": pm["n_pos"],
                   "n_neg": pm["n_neg"], "auc": pm["auc"], "ap": pm["ap"], "prevalence": pm["prevalence"],
                   "ap_lift": pm["ap_lift"], "pauc_mcclish": pm["pauc_mcclish"], "pauc_raw": pm["pauc_raw"],
                   "auc_cb": pm["auc_cb"], "auc_strat": pm["auc_strat"], "strat_n_bins": pm["strat_n_bins"],
                   "strat_n_strata_dropped": pm["strat_n_strata_dropped"],
                   "strat_frac_pos_dropped": pm["strat_frac_pos_dropped"],
                   "n_units_hom": fast["hom"]["auc"].n_clusters, "n_units_lig": fast["lig"]["auc"].n_clusters,
                   "B": args.B, "seed": args.seed}
            for metric in ("auc", "ap"):
                _ci_cols(row, metric, {un: fast[un][metric] for un in UD})
            for metric in ("auc_cb", "auc_strat"):
                _ci_cols(row, metric, {un: (None if gen.get(f"{v.key}#{sn}#{un}") is None
                                            else gen[f"{v.key}#{sn}#{un}"][metric]) for un in UD})
            if v.mode == "D":   # worst-case bound + miss rates over ALL pairs of the subset
                ys, ss = y_all[sm], v.s[sm]
                wc, _ = ev.worst_case(ys, ss)
                wm = ev.binary_metrics(ys, wc)
                mall = ev.missing_summary(ys, {"s": ss})["s"]
                row.update(auc_worst_all=wm["auc"], ap_worst_all=wm["ap"], miss_rate_pos_all=mall["miss_rate_pos"],
                           miss_rate_neg_all=mall["miss_rate_neg"])
            rows.append(row)
    summary = pd.DataFrame(rows)

    # ---------------------------------------------------------------- A1 selection (D11)
    sel, tm_inputs = select_a1_d11(args, ds, V, log)
    chosen = sel["chosen"]

    def gdelta(ka, kb, metric, un, sn="all"):
        ga, gb = gen.get(f"{ka}#{sn}#{un}"), gen.get(f"{kb}#{sn}#{un}")
        if ga is None or gb is None:
            return None
        ra, rb = ga[metric], gb[metric]
        return ev._summarise(metric, ra.estimate - rb.estimate, ra.replicates - rb.replicates, alpha=0.05,
                             seed=args.seed, K=ra.n_clusters, diff=True)

    def paired(ka, kb, label):
        va, vb = V[ka], V[kb]
        m = eval_set(va)
        assert (m == eval_set(vb)).all()
        r = {"comparison": label, "a": ka, "b": kb, "n_pairs": int(m.sum())}
        per = {un: ev.paired_bootstrap(y_all[m], va.s[m], vb.s[m], ci[m], cj[m], B=args.B, seed=args.seed,
                                       n_threads=args.threads)["delta_auc"] for un, (ci, cj) in UD.items()}
        w = _ci_cols(r, "delta_auc", per)
        r["delta_auc"] = w.estimate
        r["p_auc"] = w.p_value
        for metric in ("auc_cb", "auc_strat"):
            per = {un: gdelta(ka, kb, metric, un) for un in UD}
            w = _ci_cols(r, f"delta_{metric}", per)
            r[f"delta_{metric}"] = w.estimate if w else np.nan
        return r

    lvd = []
    for v in vecs:
        if v.mode != "D" or v.key[:-1] + "L" not in V:
            continue
        kL = v.key[:-1] + "L"
        m = dset & ~np.isnan(v.s)
        per = {un: ev.paired_bootstrap(y_all[m], v.s[m], V[kL].s[m], ci[m], cj[m], B=args.B, seed=args.seed,
                                       n_threads=args.threads)["delta_auc"] for un, (ci, cj) in UD.items()}
        pmL = point_metrics(y_all[m], V[kL].s[m], pc_all[m], cov_all[m])
        pmD = point_metrics(y_all[m], v.s[m], pc_all[m], cov_all[m])
        r = {"arm": v.arm, "config": v.config, "variant": v.variant, "n_pairs": int(m.sum()), "auc_L": pmL["auc"],
             "auc_D": pmD["auc"], "auc_strat_L": pmL["auc_strat"], "auc_strat_D": pmD["auc_strat"],
             "auc_cb_L": pmL["auc_cb"], "auc_cb_D": pmD["auc_cb"]}
        w = _ci_cols(r, "delta", per)
        r["delta_auc_D_minus_L"] = w.estimate
        lvd.append(r)
    lvd = pd.DataFrame(lvd)
    csls_df = pd.DataFrame([paired(v.key, v.key.replace("|csls|", "|raw|"), "csls - raw")
                            for v in vecs if v.variant == "csls"])
    comps = []
    a1s = [chosen] + (["default"] if chosen != "default" else [])
    for mode in ("L", "D"):
        for var in ("raw", "csls"):
            for c in a1s:
                comps.append(paired(f"A1|{c}|{var}|{mode}", f"B1|default|{var}|{mode}", f"A1 {c} - B1"))
                comps.append(paired(f"A1|{c}|{var}|{mode}", f"B4|esm2|{var}|{mode}", f"A1 {c} - B4"))
            comps.append(paired(f"B1|default|{var}|{mode}", f"B4|esm2|{var}|{mode}", "B1 - B4"))
    comps = pd.DataFrame(comps)

    # ---------------------------------------------------------------- outputs
    details = {"dataset": "blips", "split": "val", "version": "v2", "B": args.B, "seed": args.seed,
               "n_pockets": int(len(P)), "n_pairs": int(len(y_all)), "n_pos": int(y_all.sum()),
               "units": {un: {"name": UNIT_NAMES[un], "n": int(len(np.unique(a))),
                              "largest": int(np.bincount(a).max())} for un, a in ds.unit_defs.items()},
               "pos_clusters": {"n": int(len(np.unique(pc_all[y_all]))),
                                "top_share": float(pd.Series(pc_all[y_all]).value_counts(normalize=True).iloc[0])},
               "subsets": {sn: {"n_pairs": int(sm.sum()), "n_pos": int((sm & y_all).sum())}
                           for sn, sm in subsets.items()},
               "d_mode": {"n_sites_matched": int(dm.sum()), "n_pairs_dset": int(dset.sum()),
                          "n_pos_dset": int((dset & y_all).sum())},
               "selection": sel, "build": meta, "lvd": lvd.to_dict(orient="records"),
               "csls": csls_df.to_dict(orient="records"), "comparisons": comps.to_dict(orient="records")}
    cfg = {"dataset": "blips", "split": "val_v2", "B": args.B, "seed": args.seed, "csls_k": CSLS_K, "n_folds": N_FOLDS,
           "strata": "(5,20) if n_pos >= 500 else (5,5)", "a1_grid": "configs/a1_grid.yaml",
           "units": "wider CI of {homology group, Butina ligand cluster}", "pos_cluster": "pair_cluster"}
    inputs = sorted(set(map(str, ds.inputs + tm_inputs)) | {str(ROOT / "src/pocketcompare/similarity.py"),
                                                           str(ROOT / "configs/a1_grid.yaml")})
    common = dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=inputs, seed=args.seed, device="cpu",
                  start_time=t_start)
    f_sum = out / f"{tag}_summary.parquet"
    write_result(f_sum, summary, **common)
    write_result(out / f"{tag}_details.json", details, **common)
    reps = {}
    for k, g in gen.items():
        if g is not None and "#all#" in k:
            for m_, r in g.items():
                reps[f"{k}::{m_}"] = r.replicates
    write_result(out / f"{tag}_replicates.parquet", pd.DataFrame(reps), **common)
    f_md = out / f"{tag}_summary.md"
    f_md.write_text(render_md_blips(summary, lvd, csls_df, comps, sel, details))
    prov = {"result": str(f_md), "result_sha256": sha256_file(f_md), **git_state(), "script": str(Path(__file__)),
            "script_sha256": sha256_file(__file__), "args": sys.argv[1:], "config": cfg,
            "evaluate_sha256": ev.module_sha256(), "derived_from": [str(f_sum), str(out / f"{tag}_details.json")],
            "seed": args.seed, "wall_seconds": round(time.time() - t_start, 1)}
    (out / f"{tag}_summary.md.prov.json").write_text(json.dumps(prov, indent=2, default=str) + "\n")
    if not args.no_trials:
        for r in rows:
            if r["subset"] != "all":
                continue
            metrics = {k: r[k] for k in ("n_pairs", "n_pos", "auc", "auc_lo", "auc_hi", "ap", "ap_lift",
                                         "pauc_mcclish", "auc_cb", "auc_cb_lo", "auc_cb_hi", "auc_strat",
                                         "auc_strat_lo", "auc_strat_hi", "auc_ci_unit")}
            append_trial(r["arm"], {"config": r["config"], "variant": r["variant"], "mode": r["mode"],
                                    "pairset": r["pairset"], "B": args.B, "seed": args.seed,
                                    "units": "wider of hom/lig", "data": "blips_val_v2"},
                         "blips_val", metrics, f_sum)
    log(f"done: {f_sum}")


def render_md_blips(summary, lvd, csls_df, comps, sel, details) -> str:
    L = ["# blips-val (v2) — all arms (auto-generated by scripts/eval_dev.py --dataset blips)", "",
         f"Pairs {details['n_pairs']} ({details['n_pos']} pos), {details['n_pockets']} sites; units hom "
         f"{details['units']['hom']['n']} / lig {details['units']['lig']['n']}; positive clusters "
         f"{details['pos_clusters']['n']} (top share {details['pos_clusters']['top_share']:.3f}); D-set "
         f"{details['d_mode']['n_pairs_dset']} pairs ({details['d_mode']['n_pos_dset']} pos). B = {details['B']}. "
         "CIs: 95 % vertex bootstrap, the wider of homology-group (h) and ligand-cluster (l) units (column 'u').", ""]
    for sn in summary.subset.unique():
        sub = summary[summary.subset == sn]
        d = details["subsets"][sn]
        L += [f"## Subset `{sn}` ({d['n_pairs']} pairs, {d['n_pos']} pos)", "",
              "| arm | config | variant | mode | n pairs (pos) | ROC-AUC [CI] u | AP (lift) | cb-AUC [CI] u | "
              "strat. AUC [CI] u | worst-case AUC |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in sub.itertuples():
            L.append(f"| {r.arm} | {r.config} | {r.variant} | {r.mode} | {r.n_pairs} ({r.n_pos}) | {_f(r.auc)} "
                     f"[{_f(r.auc_lo)}, {_f(r.auc_hi)}] {str(r.auc_ci_unit)[:1]} | {_f(r.ap)} ({_f(r.ap_lift, 2)}) | "
                     f"{_f(r.auc_cb)} [{_f(r.auc_cb_lo)}, {_f(r.auc_cb_hi)}] {str(r.auc_cb_ci_unit)[:1]} | "
                     f"{_f(r.auc_strat)} [{_f(r.auc_strat_lo)}, {_f(r.auc_strat_hi)}] "
                     f"{str(r.auc_strat_ci_unit)[:1]} | {_f(getattr(r, 'auc_worst_all', np.nan))} |")
        L.append("")
    L += ["## A1 selection (D11)", "", sel["rule"], "",
          f"best **{sel['best']}** (mean cb {sel['best_mean_cb']:.4f}, SE {sel['se_best']:.4f}, BLiPS units "
          f"{sel['se_blips_unit_used']}); within one SE: {', '.join(sel['within_one_se'])}; **chosen "
          f"{sel['chosen']}** (previous TOUGH-M1-L-only best: {sel['previous_rule_best_tm_L']}).", "",
          "| config | dims | TM-dev L | TM-dev D | BLiPS L | BLiPS D | mean | SE (hom) | SE (lig) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for c, t in sorted(sel["candidates"].items(), key=lambda kv: -kv[1]["mean_cb"]):
        L.append(f"| {c} | {t['dims']} | {t['tm_L']:.3f} | {t['tm_D']:.3f} | {t['bl_L']:.3f} | {t['bl_D']:.3f} | "
                 f"{t['mean_cb']:.4f} | {t['se_hom']:.4f} | {t['se_lig']:.4f} |")
    L += ["", "## Paired comparisons (all pairs / D-set)", "",
          "| comparison | a | n | Δ AUC [CI] u | Δ cb [CI] | Δ strat [CI] |", "|---|---|---|---|---|---|"]
    for r in comps.itertuples():
        L.append(f"| {r.comparison} | {r.a} | {r.n_pairs} | {r.delta_auc:+.3f} [{r.delta_auc_lo:+.3f}, "
                 f"{r.delta_auc_hi:+.3f}] {str(r.delta_auc_ci_unit)[:1]} | {r.delta_auc_cb:+.3f} "
                 f"[{r.delta_auc_cb_lo:+.3f}, {r.delta_auc_cb_hi:+.3f}] | {r.delta_auc_strat:+.3f} "
                 f"[{r.delta_auc_strat_lo:+.3f}, {r.delta_auc_strat_hi:+.3f}] |")
    L += ["", "## CSLS − raw (paired)", "", "| key | Δ AUC [CI] | Δ cb [CI] | Δ strat [CI] |", "|---|---|---|---|"]
    for r in csls_df.itertuples():
        L.append(f"| {r.a} | {r.delta_auc:+.3f} [{r.delta_auc_lo:+.3f}, {r.delta_auc_hi:+.3f}] | "
                 f"{r.delta_auc_cb:+.3f} [{r.delta_auc_cb_lo:+.3f}, {r.delta_auc_cb_hi:+.3f}] | "
                 f"{r.delta_auc_strat:+.3f} [{r.delta_auc_strat_lo:+.3f}, {r.delta_auc_strat_hi:+.3f}] |")
    L += ["", "## D − L on the D-set (paired)", "", "| arm | config | variant | n | AUC L | AUC D | Δ [CI] | strat L | "
          "strat D |", "|---|---|---|---|---|---|---|---|---|"]
    for r in lvd.itertuples():
        L.append(f"| {r.arm} | {r.config} | {r.variant} | {r.n_pairs} | {r.auc_L:.3f} | {r.auc_D:.3f} | "
                 f"{r.delta_auc_D_minus_L:+.3f} [{r.delta_lo:+.3f}, {r.delta_hi:+.3f}] | {r.auc_strat_L:.3f} | "
                 f"{r.auc_strat_D:.3f} |")
    return "\n".join(L) + "\n"


# ================================================================================================ PPIPS-val
def _wmean(x, w):
    sw = float(np.sum(w))
    return float(np.dot(w, x) / sw) if sw > 0 else np.nan


def _boot_means(cols: dict, units, B, seed, diff=False):
    """Vertex bootstrap (units = query homology group; within-unit weight n_u) of weighted means of per-query
    columns.  Returns {name: BootstrapResult | None}."""
    names = list(cols)
    X = np.column_stack([np.asarray(cols[n], float) for n in names])
    if len(np.unique(units)) < 2:
        return {n: None for n in names}

    def fn(w):
        return [_wmean(X[:, k], w) for k in range(X.shape[1])]

    try:
        res = ev.vertex_bootstrap_generic(fn, units, units, B=B, seed=seed, names=names, diff=diff)
    except ValueError:
        return {n: None for n in names}
    return {r.name: r for r in res}


def main_ppips(args):
    from pocketcompare.descriptors.a2 import A2Config, A2Descriptor

    t_start = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = "ppips_val"

    def log(msg):
        print(f"[{time.time() - t_start:7.1f}s] {msg}", flush=True)

    ds = PpipsVal().load()
    P = ds.pockets
    chosen = args.a1_chosen
    if chosen is None:
        f_sel = Path(args.out) / "blips_val_details.json"
        chosen = json.loads(f_sel.read_text())["selection"]["chosen"]
        ds.inputs.append(f_sel)
    pid = {p: i for i, p in enumerate(P.pocket_id)}
    val_idx = np.where(ds.val)[0]
    ref = ds.train | ds.val                                  # rows that are embedded at all (test rows untouched)
    members = P.groupby("complex").indices
    n_val = len(val_idx)
    log(f"PPIPS: {len(P)} pockets (train {ds.train.sum()}, val {n_val}); ortho queries {len(ds.ortho)}, "
        f"sym pairs {len(ds.sym)}; A1 chosen = {chosen}")

    # ---- P-ortho long table (query -> all pockets of the partner complex)
    Q = ds.ortho.reset_index(drop=True)
    oq, oc, ol = [], [], []
    for k, r in enumerate(Q.itertuples()):
        cand = members[r.partner_complex]
        posset = set(r.positives)
        oq += [k] * len(cand)
        oc += list(cand)
        ol += [P.pocket_id.iat[c] in posset for c in cand]
    oq, oc, ol = np.asarray(oq), np.asarray(oc), np.asarray(ol)
    q_pk = Q["query"].map(pid).to_numpy()
    o_i = q_pk[oq]
    q_unit = Q.query_complex.map(dict(zip(P.complex, P.group))).to_numpy()
    q_bur = P.bur16.to_numpy()[q_pk]
    tert_edges = np.quantile(q_bur, [1 / 3, 2 / 3])
    q_tert = np.searchsorted(tert_edges, q_bur, side="right")        # 0 = shallowest
    n_cand = Q.n_candidates.to_numpy()
    if not (np.bincount(oq) == n_cand).all():
        raise RuntimeError("candidate count mismatch")
    # ---- P-sym long table (both directions; candidates = all other val pockets)
    S_ = ds.sym.reset_index(drop=True)
    a_i, b_i = S_.pocket_a.map(pid).to_numpy(), S_.pocket_b.map(pid).to_numpy()
    sq, sh = np.concatenate([a_i, b_i]), np.concatenate([b_i, a_i])
    s_if = np.concatenate([S_.interface.to_numpy(bool)] * 2)
    s_unit = np.concatenate([S_.complex.map(dict(zip(P.complex, P.group))).to_numpy()] * 2)
    rep_q = np.repeat(np.arange(len(sq)), n_val)
    rep_c = np.tile(val_idx, len(sq))
    keep = rep_c != sq[rep_q]
    rep_q, rep_c = rep_q[keep], rep_c[keep]
    rep_l = rep_c == sh[rep_q]
    s_i = sq[rep_q]
    rep_col = np.searchsorted(val_idx, rep_c)
    log(f"ortho long table {len(oq)} rows; sym long table {len(rep_q)} rows")

    # ---- score sources: name -> (E over all rows or None, note); B0 handled separately
    def emb(M, zscore=True, layout=None, bw=None):
        M = np.asarray(M, np.float64)
        zs = ZScorer.fit(M[ds.train]) if zscore else None
        Er = embed(M[ref], zs, layout, bw)
        E = np.zeros((len(M), Er.shape[1]), np.float32)
        E[ref] = Er
        return E

    sources = []
    for cfg in ("default", "learned"):
        M, _ = ds.descriptor("b1", cfg, "D")
        sources.append(("B1", cfg, emb(M), M.shape[1], "cosine, PPIPS-train z-score"))
    f = ROOT / "data/processed/descriptors/ppips/b4_esm2_D.npy"
    ds.inputs.append(f)
    M = np.load(f)
    sources.append(("B4", "esm2", emb(M), M.shape[1], "cosine, PPIPS-train z-score"))
    sources.append(("B4", "esm2_noz", emb(M, zscore=False), M.shape[1], "cosine, raw embedding"))
    for cfg in dict.fromkeys(["default", chosen]):
        base = "default" if cfg == "default_bw" else cfg
        M, lay = ds.descriptor("a1", base, "D")
        E = emb(M, layout=lay, bw=A1_BW) if cfg == "default_bw" else emb(M)
        sources.append(("A1", cfg + (" (chosen)" if cfg == chosen else ""), E, M.shape[1],
                        "cosine, PPIPS-train z-score"))
    log("B1/B4/A1 embeddings done")
    geom = ds.docking_meta()
    a2_meta = {}
    train_ids = P.pocket_id[ds.train].tolist()
    for panel in A2_PANELS:
        f = ROOT / "data/processed/docking/ppips" / f"{panel}.parquet"
        ds.inputs.append(f)
        raw_tab = pd.read_parquet(f)
        raw_tab = raw_tab[raw_tab.split.isin(["train", "val"])]
        desc = A2Descriptor(A2Config(panel=panel)).fit(raw_tab, geom, reference_pocket_ids=train_ids)
        Vv = desc.transform(raw_tab, geom)
        rows_ = pd.Series(np.arange(len(Vv.pocket_id)), index=Vv.pocket_id)
        av = P.pocket_id.isin(rows_.index).to_numpy()
        if not (av == ref).all():
            raise RuntimeError(f"A2 {panel}: docking coverage differs from train+val")
        a2_meta[panel] = {"n_reference_pockets": len(train_ids), "nonbinder_threshold":
                          desc.nonbinder_threshold_.tolist()}
        for blk in A2_BLOCKS:
            Bk = getattr(Vv, blk)
            M = np.zeros((len(P), Bk.shape[1]))
            M[av] = Bk[rows_.loc[P.pocket_id[av]].to_numpy()]
            sources.append(("A2", f"{panel}_{blk}", emb(M), Bk.shape[1], "A2 fit on PPIPS-train; cosine"))
        log(f"  A2 {panel} done")
        del raw_tab

    # ---- evaluate
    lv = P.logv.to_numpy()
    results, perq = [], {}

    def run_one(arm, cfg, variant, so, ss, dims, note):
        ro = ev.retrieval_metrics(pd.DataFrame({"query": oq, "score": so, "label": ol}), ks=(1, 3))
        pq = ro["per_query"].set_index("query").reindex(np.arange(len(Q)))
        if pq["rank"].isna().any():
            raise RuntimeError("ortho query without a hit")
        rk = pq["rank"].to_numpy(float)
        o_top1, o_top3, o_rr = (rk <= 1).astype(float), (rk <= 3).astype(float), 1.0 / rk
        rs = ev.retrieval_metrics(pd.DataFrame({"query": rep_q, "score": ss, "label": rep_l}), ks=(1, 10))
        ps = rs["per_query"].set_index("query").reindex(np.arange(len(sq)))
        rks = ps["rank"].to_numpy(float)
        s_pct = 1.0 - (rks - 1) / (n_val - 2)
        s_top1 = (rks <= 1).astype(float)
        key = f"{arm}|{cfg}|{variant}"
        perq[key] = {"o_top1": o_top1, "o_top3": o_top3, "o_rr": o_rr, "s_pct": s_pct, "s_top1": s_top1}
        bo = _boot_means({"top1": o_top1, "top3": o_top3, "mrr": o_rr}, q_unit, args.B, args.seed)
        bs = _boot_means({"pct": s_pct, "top1": s_top1}, s_unit, args.B, args.seed)
        bsi = _boot_means({"pct": s_pct[s_if], "top1": s_top1[s_if]}, s_unit[s_if], args.B, args.seed)
        row = {"key": key, "arm": arm, "config": cfg, "variant": variant, "dims": dims, "note": note,
               "ortho_n_queries": int(len(Q)), "ortho_n_units": int(len(np.unique(q_unit))),
               "ortho_n_missing_scores": ro["n_missing_scores"]}
        for m_, x in (("top1", o_top1), ("top3", o_top3), ("mrr", o_rr)):
            r = bo[m_]
            row.update({f"ortho_{m_}": float(x.mean()), f"ortho_{m_}_lo": r.ci_low if r else np.nan,
                        f"ortho_{m_}_hi": r.ci_high if r else np.nan})
        for t in range(3):
            mk = q_tert == t
            row[f"ortho_mrr_bur_t{t + 1}"] = float(o_rr[mk].mean())
            row[f"ortho_top1_bur_t{t + 1}"] = float(o_top1[mk].mean())
        for typ in ("hetero", "homo"):
            mk = (Q.type == typ).to_numpy()
            row[f"ortho_mrr_{typ}"] = float(o_rr[mk].mean())
        for lab, b_, mk in (("all", bs, np.ones(len(sq), bool)), ("if", bsi, s_if)):
            row[f"sym_{lab}_n_queries"] = int(mk.sum())
            for m_, x in (("pct", s_pct), ("top1", s_top1)):
                r = b_[m_]
                row.update({f"sym_{lab}_{m_}": float(x[mk].mean()), f"sym_{lab}_{m_}_lo": r.ci_low if r else np.nan,
                            f"sym_{lab}_{m_}_hi": r.ci_high if r else np.nan})
            row[f"sym_{lab}_median_pct"] = float(np.median(s_pct[mk]))
        row["sym_n_units"] = int(len(np.unique(s_unit)))
        results.append(row)

    # B0 (size only, no CSLS)
    run_one("B0", "default", "raw", -np.abs(lv[o_i] - lv[oc]), -np.abs(lv[s_i] - lv[rep_c]), 1,
            "−|Δ log V| (region-pocket volume)")
    for arm, cfg, E, dims, note in sources:
        r = np.full(len(P), np.nan)
        r[val_idx] = csls_r(E[val_idx], E[val_idx], CSLS_K, query_ids=val_idx, bg_ids=val_idx)
        so = pair_scores(E, o_i, oc).astype(np.float64)
        ss = (E[sq] @ E[val_idx].T).astype(np.float64)[rep_q, rep_col]     # = pair_scores(E, s_i, rep_c)
        run_one(arm, cfg, "raw", so, ss, dims, note)
        run_one(arm, cfg, "csls", so - 0.5 * (r[o_i] + r[oc]), ss - 0.5 * (r[s_i] + r[rep_c]), dims,
                note + "; CSLS bg = val pockets")
        log(f"  {arm} {cfg} evaluated")
    # chance level (random scorer, expectation): one positive among n candidates
    chance = {"ortho_top1": float(np.mean(1.0 / n_cand)), "ortho_top3": float(np.mean(np.minimum(3, n_cand) / n_cand)),
              "ortho_mrr": float(np.mean([np.sum(1.0 / np.arange(1, n + 1)) / n for n in n_cand])),
              "sym_pct": 0.5, "sym_top1": 1.0 / (n_val - 1)}
    summary = pd.DataFrame(results)

    # ---- PPI sub-hypothesis: fragments − lead-like on P-ortho (paired, same replicates)
    hyp = []
    for var in ("raw", "csls"):
        for blk in A2_BLOCKS:
            fq, lq = perq[f"A2|fragments_{blk}|{var}"], perq[f"A2|leadlike_{blk}|{var}"]
            d_rr, d_t1 = fq["o_rr"] - lq["o_rr"], fq["o_top1"] - lq["o_top1"]
            for strat, mk in [("all", np.ones(len(Q), bool))] + [(f"bur_t{t + 1}", q_tert == t) for t in range(3)]:
                b_ = _boot_means({"d_mrr": d_rr[mk], "d_top1": d_t1[mk]}, q_unit[mk], args.B, args.seed, diff=True)
                h = {"block": blk, "variant": var, "stratum": strat, "n_queries": int(mk.sum()),
                     "n_units": int(len(np.unique(q_unit[mk]))), "mrr_frag": float(fq["o_rr"][mk].mean()),
                     "mrr_lead": float(lq["o_rr"][mk].mean())}
                for m_, x in (("d_mrr", d_rr), ("d_top1", d_t1)):
                    r = b_[m_]
                    h.update({m_: float(x[mk].mean()), f"{m_}_lo": r.ci_low if r else np.nan,
                              f"{m_}_hi": r.ci_high if r else np.nan, f"{m_}_p": r.p_value if r else np.nan})
                hyp.append(h)
    hyp = pd.DataFrame(hyp)
    prim = hyp[(hyp.variant == "raw") & (hyp.stratum == "all")].set_index("block").loc[list(A2_BLOCKS)]
    holm = ev.holm(prim.d_mrr_p.to_numpy())
    supported = bool(holm["reject"].any() and not (prim.d_mrr_hi < 0).any())
    verdict = {"rule": "SUPPORTED iff (raw variant, all queries) at least one block has Holm-adjusted (3 blocks) "
                       "one-sided p < 0.05 for Δ MRR (fragments − lead-like) and no block has its 95 % CI < 0",
               "blocks": list(A2_BLOCKS), "p_one_sided": prim.d_mrr_p.tolist(),
               "p_holm": holm["p_adjusted"].tolist(), "d_mrr": prim.d_mrr.tolist(),
               "verdict": "SUPPORTED" if supported else "NOT SUPPORTED"}
    log(f"PPI sub-hypothesis: {verdict['verdict']} (Δ MRR {np.round(prim.d_mrr.to_numpy(), 3).tolist()}, "
        f"Holm p {np.round(holm['p_adjusted'], 3).tolist()})")

    details = {"dataset": "ppips", "split": "val", "B": args.B, "seed": args.seed, "a1_chosen": chosen,
               "n_pockets_val": int(n_val), "n_pockets_train_reference": int(ds.train.sum()),
               "ortho": {"n_queries": int(len(Q)), "n_unique_query_pockets": int(len(np.unique(q_pk))),
                         "n_units": int(len(np.unique(q_unit))), "candidates_median": float(np.median(n_cand)),
                         "bur16_tertile_edges": tert_edges.tolist(),
                         "type_counts": Q.type.value_counts().to_dict()},
               "sym": {"n_pairs": int(len(S_)), "n_interface_pairs": int(S_.interface.sum()),
                       "n_queries": int(len(sq)), "n_units": int(len(np.unique(s_unit)))},
               "chance": chance, "a2": a2_meta, "hypothesis": hyp.to_dict(orient="records"),
               "hypothesis_verdict": verdict}
    cfg = {"dataset": "ppips", "split": "val", "B": args.B, "seed": args.seed, "csls_k": CSLS_K,
           "reference": "PPIPS-train pockets (z-score, A2 fit)", "units": "complex homology group of the query",
           "a1_chosen": chosen}
    inputs = sorted(set(map(str, ds.inputs)) | {str(ROOT / "src/pocketcompare/descriptors/a2.py"),
                                               str(ROOT / "src/pocketcompare/similarity.py")})
    common = dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=inputs, seed=args.seed, device="cpu",
                  start_time=t_start)
    f_sum = out / f"{tag}_summary.parquet"
    write_result(f_sum, summary, **common)
    write_result(out / f"{tag}_details.json", details, **common)
    f_md = out / f"{tag}_summary.md"
    f_md.write_text(render_md_ppips(summary, hyp, verdict, details))
    prov = {"result": str(f_md), "result_sha256": sha256_file(f_md), **git_state(), "script": str(Path(__file__)),
            "script_sha256": sha256_file(__file__), "args": sys.argv[1:], "config": cfg,
            "evaluate_sha256": ev.module_sha256(), "derived_from": [str(f_sum), str(out / f"{tag}_details.json")],
            "seed": args.seed, "wall_seconds": round(time.time() - t_start, 1)}
    (out / f"{tag}_summary.md.prov.json").write_text(json.dumps(prov, indent=2, default=str) + "\n")
    if not args.no_trials:
        for r in results:
            metrics = {k: r[k] for k in ("ortho_n_queries", "ortho_top1", "ortho_top1_lo", "ortho_top1_hi",
                                         "ortho_top3", "ortho_mrr", "ortho_mrr_lo", "ortho_mrr_hi", "sym_all_pct",
                                         "sym_all_pct_lo", "sym_all_pct_hi", "sym_all_top1", "sym_if_pct")}
            append_trial(r["arm"], {"config": r["config"], "variant": r["variant"], "mode": "D",
                                    "task": "P-ortho + P-sym", "B": args.B, "seed": args.seed,
                                    "reference": "ppips_train"}, "ppips_val", metrics, f_sum)
    log(f"done: {f_sum}")


def render_md_ppips(summary, hyp, verdict, details) -> str:
    c = details["chance"]
    o = details["ortho"]
    L = ["# ppips-val — P-ortho / P-sym (auto-generated by scripts/eval_dev.py --dataset ppips)", "",
         f"P-ortho: {o['n_queries']} queries ({o['n_unique_query_pockets']} query pockets), {o['n_units']} units "
         f"(complex homology groups), median {o['candidates_median']:.0f} candidates; chance top-1 "
         f"{c['ortho_top1']:.3f}, top-3 {c['ortho_top3']:.3f}, MRR {c['ortho_mrr']:.3f}. P-sym: "
         f"{details['sym']['n_queries']} queries ({details['sym']['n_interface_pairs']} interface pairs × 2) over "
         f"{details['n_pockets_val']} val pockets, {details['sym']['n_units']} units; chance percentile 0.5. "
         f"B = {details['B']}. A1 chosen (D11) = {details['a1_chosen']}.", "",
         "| arm | config | variant | ortho top-1 [CI] | top-3 [CI] | MRR [CI] | MRR bur T1/T2/T3 | sym pct all [CI] | "
         "sym top-1 all | sym pct interface [CI] |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in summary.itertuples():
        L.append(f"| {r.arm} | {r.config} | {r.variant} | {_f(r.ortho_top1)} [{_f(r.ortho_top1_lo)}, "
                 f"{_f(r.ortho_top1_hi)}] | {_f(r.ortho_top3)} [{_f(r.ortho_top3_lo)}, {_f(r.ortho_top3_hi)}] | "
                 f"{_f(r.ortho_mrr)} [{_f(r.ortho_mrr_lo)}, {_f(r.ortho_mrr_hi)}] | {_f(r.ortho_mrr_bur_t1, 2)}/"
                 f"{_f(r.ortho_mrr_bur_t2, 2)}/{_f(r.ortho_mrr_bur_t3, 2)} | {_f(r.sym_all_pct)} "
                 f"[{_f(r.sym_all_pct_lo)}, {_f(r.sym_all_pct_hi)}] | {_f(r.sym_all_top1)} | {_f(r.sym_if_pct)} "
                 f"[{_f(r.sym_if_pct_lo)}, {_f(r.sym_if_pct_hi)}] |")
    L += ["", "## PPI sub-hypothesis: fragments − lead-like (P-ortho, paired)", "", verdict["rule"], "",
          f"**Verdict: {verdict['verdict']}** (Holm p {', '.join(f'{p:.3f}' for p in verdict['p_holm'])} for "
          f"{', '.join(verdict['blocks'])}).", "",
          "| block | variant | stratum | n (units) | MRR frag | MRR lead | Δ MRR [CI] p | Δ top-1 [CI] |",
          "|---|---|---|---|---|---|---|---|"]
    for r in hyp.itertuples():
        L.append(f"| {r.block} | {r.variant} | {r.stratum} | {r.n_queries} ({r.n_units}) | {r.mrr_frag:.3f} | "
                 f"{r.mrr_lead:.3f} | {r.d_mrr:+.3f} [{r.d_mrr_lo:+.3f}, {r.d_mrr_hi:+.3f}] {_f(r.d_mrr_p)} | "
                 f"{r.d_top1:+.3f} [{r.d_top1_lo:+.3f}, {r.d_top1_hi:+.3f}] |")
    L += ["", f"Buriedness tertiles (bur16 of the query pocket; T1 = shallowest), edges "
              f"{', '.join(f'{e:.3f}' for e in o['bur16_tertile_edges'])}."]
    return "\n".join(L) + "\n"


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
