#!/usr/bin/env python
"""Final (confirmatory) evaluation — PREREG.md §2 claims and §3 reported items, with the §4 rules.

Real run (PI only):
    FINAL_EVAL=1 python scripts/final_eval.py                      # reads the committed FREEZE.json
Dry run on dev data (identical code path; sealed files are never touched):
    python scripts/final_eval.py --dryrun-dev [--B 2000] [--threads 16]
Write a FREEZE.json template for the current HEAD (PI reviews + commits it):
    python scripts/final_eval.py --write-freeze
Preflight of the real run (all FREEZE / worktree / hash checks, exits before any sealed file is opened):
    FINAL_EVAL=1 python scripts/final_eval.py --check-only

Guards of the real run
----------------------
* ``FINAL_EVAL=1`` is required; FREEZE.json must be committed and unmodified; the main tree must be clean (tracked
  files).  FREEZE.json = {commit, method_config, method_config_sha256, weights: {path: sha256}, evaluate_sha256,
  prereg_sha256, final_eval_sha256}.  Any mismatch -> refuse.
* The evaluation runs from a git worktree at FREEZE.commit (created next to the repo; git-ignored data
  directories are symlinked into it) and re-checks every hash there: evaluate.py must equal FREEZE and the PREREG §4
  constant f22d0296…; PREREG.md, configs/final_method.yaml, model weights and this script must equal FREEZE.
* Sealed files (data/sealed/, chmod 000) are opened one at a time: chmod 400 -> sha256 check against
  data/sealed_SHA256SUMS.txt -> read into memory -> chmod 000 (in a finally); every access is appended to
  results/final/unseal_log.tsv.  Results are written to <worktree>/results/final/ (provenance sidecars; the
  provenance module refuses a dirty tree) and copied to <repo>/results/final/ for the PI to commit.

Final method (pluggable)
------------------------
configs/final_method.yaml (``module:`` default ``pocketcompare.method``) is loaded with ``module.load(cfg, root)``
which must return an object with
    name: str; is_learned: bool; csls: bool                       # csls -> CSLS k=10, background = evaluated pool
    weight_files() -> list[Path]                                  # hashed into FREEZE.json
    embed(store, dataset, mode, pocket_ids) -> (n, d) array        # unit rows, NaN rows = unavailable
``store`` is a ``pocketcompare.descstore.DescriptorStore``; ``pocket_ids`` is the evaluated split's pocket pool of
that mode (the only allowed background for label-free normalisation); similarity = inner product.
Until A4b delivers ``pocketcompare.method``, ``--dryrun-dev`` uses the stand-in ``A1 pair_only`` (z-score on the
pool, cosine, raw) — the real run refuses the stand-in.

What is computed (fixed here before any test use; PREREG wins where this text is less specific)
--------------------------------------------------------------------------------------------
Claims (one-sided, paired vertex bootstrap B = 2000, seed SEEDS[0]; Holm over {C1a, C1b, C1-D, C2}, α = 0.05):
  C1a  TOUGH-M1-test L: ROC-AUC(final) − ROC-AUC(B1); units = components of (ligand cluster ∪ homology group).
  C1b  same vs B4 (ESM-2 lining-residue mean, z-scored cosine).  B1/B4 get the final method's CSLS treatment.
  C1-D TOUGH-M1-test D (both pockets matched: coverage ≥ 0.3 or precision ≥ 0.5; common set of final and B1).
  C2   ProSPECCTs P5.2 + P6.2 + P7, self-pairs removed, L: macro Δ(final − B1), independent bootstrap per subset
       (seed [SEEDS[0], k]), units = homology group (ProSPECCTs graph; decoys / unmapped pockets = own unit).
  Reported with each Δ: 95 % CI, one-sided 95 % lower bound vs SESOI 0.03, p, Holm-adjusted p, MDE note (dev).
Reported (not in Holm):
  TOUGH-M1-test L and D: every arm (final, B0, B0m [logistic on (log va + log vb, |Δ|) fit on TOUGH-M1-dev pairs],
    B0' Foldseek global TM (data/processed/b0prime) and the TOUGH-M1 list TM / identity, B1, B4 (z, raw), B5 EPoCS,
    B5-T shipped APoc / G-LoSA / SiteEngine columns, A1 pair_only, random control; raw and CSLS) with ROC-AUC, AP
    (lift), McClish pAUC, cluster-balanced AUC, 2-D size-stratified AUC (5 × 20; 5 × 5 if < 500 pos), CIs; per-cluster
    AUC (10 largest positive clusters) for final and B1; D-mode worst-case bound and miss rates.
  TOUGH-M1 full minus dev (L, non-learned arms only; final included only if not learned): AUC/AP CIs, point cb/strat.
  ProSPECCTs, all 10 subsets (+ P3/P4 5-substitution sets), with and without self-pairs, L; D on the BURROW-clean
    subset (pockets without a direct homology edge to BURROW train/dev/partner chains; both pockets D-matched).
    Pool (z-score / CSLS background) = the subset's pockets.  Units = homology group.
  Vertex (L): protein-pair score = max over its pocket pairs (DeeplyTough / Chen et al.), ROC-AUC, AP (positives)
    and AP with negatives as target; units = homology group of the UniProt (own unit if unmapped).
  BLiPS-test (L, D; exclusions blips_test_exclusions_v2; chemotype_seen recomputed vs BLiPS-train v2): as BLiPS-val;
    CI = wider of homology-group / ligand-cluster units.  C5: final (and B1, B4) on holo vs AF-model pockets, paired
    Δ AUC (holo − AF) with the wider CI; strata: holo release ≥ 2018-05-01 (pair: both sites post / both pre /
    mixed) and pLDDT band of the pair (min of the two sites' AF site pLDDT: < 70, 70–90, ≥ 90).
  PPIPS-test: P-ortho top-1 / top-3 / MRR and P-sym percentile (as PPIPS-val; z-score on PPIPS-train).
  PPI-L test (exploratory): run iff its descriptors exist, else recorded as skipped.
  Runtime per pocket (BURROW featurisation + descriptor), per pair, bytes/pocket; proteome demo / PQ recall@10 are
    collected from results/proteome/ when present.
Missing pockets: primary = common pair set; worst-case bound (missing positive −inf, negative +inf) and miss rates
by label are always reported (evaluate.py policies).

Dry run (--dryrun-dev): TOUGH-M1-test -> TOUGH-M1-dev, BLiPS-test -> BLiPS-val v2 (holo stands in for AF, so the
C5 Δ is 0 by construction), PPIPS-test -> PPIPS-val, C2 -> macro over {TOUGH-M1-dev, BLiPS-val} (L, homology-group
units).  ProSPECCTs, Vertex and TOUGH-M1-full have no dev analogue: their code paths run on SYNTHETIC random labels
over the real label-free pocket tables (numbers ≈ 0.5, flagged ``synthetic``).  The dev numbers of B1 / A1 in
results/dev/ must be reproduced; the maximum deviation is written to reproduction_check.json.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import importlib
import json
import multiprocessing as mp
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_dev as ED  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.descstore import DescriptorStore  # noqa: E402
from pocketcompare.provenance import git_state, sha256_file, write_result  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402
from pocketcompare.similarity import ZScorer, csls_r, embed, pair_scores  # noqa: E402

PREREG_EVALUATE_SHA256 = "f22d02967c08d706d8a6081865a8ba40f491340e87e205826e32f8206f65707b"
CSLS_K = ED.CSLS_K
SESOI = 0.03
METHOD_CFG = ROOT / "configs/final_method.yaml"
SEALED_DIR = ROOT / "data/sealed"
SEALED_SUMS = ROOT / "data/sealed_SHA256SUMS.txt"
SPLIT_SUMS = ROOT / "data/splits/SHA256SUMS.txt"
SEALED_NEEDED = ("tough_m1_test_pairs.parquet", "prospeccts_pairs.parquet", "blips_test_pairs.parquet",
                 "blips_test_sites.parquet", "vertex_pairs.parquet", "tough_m1_pairs.parquet",
                 "ppips_test_queries.parquet", "ppips_sym_test_pairs.parquet")
WORKTREE_LINKS = ("data/processed", "data/sealed", "data/raw", "data/splits/homology_edges.parquet", "tools",
                  "results/dev", "results/proteome", "results/models")
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


# ============================================================================================ sealed access
class Sealed:
    """Temporary unsealing of data/sealed/<name> with sha256 check and an append-only access log."""

    def __init__(self, log_path: Path, enabled: bool):
        self.log_path, self.enabled = log_path, enabled
        self.expected = {}
        for sums in (SEALED_SUMS, SPLIT_SUMS):
            if sums.exists():
                for line in sums.read_text().splitlines():
                    if line.strip() and not line.startswith("#"):
                        h, p = line.split(None, 1)
                        if Path(p.strip()).parent.name == "sealed":
                            self.expected.setdefault(Path(p.strip()).name, h)
        self.accessed = []

    def read(self, name: str, purpose: str) -> pd.DataFrame:
        if not self.enabled:
            raise RuntimeError(f"sealed access to {name} outside a FINAL_EVAL run (dry run must never get here)")
        p = SEALED_DIR / name
        mode0 = oct(os.stat(p).st_mode & 0o777)
        t = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        os.chmod(p, 0o400)
        try:
            sha = sha256_file(p)
            exp = self.expected.get(name)
            if exp is None or sha != exp:
                raise RuntimeError(f"sealed file {name}: sha256 {sha} != recorded {exp}")
            df = pd.read_parquet(p)
        finally:
            os.chmod(p, 0)
        mode1 = oct(os.stat(p).st_mode & 0o777)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.log_path.exists()
        with open(self.log_path, "a") as fh:
            if new:
                fh.write("time\tfile\tsha256\tsha256_ok\tmode_before\tmode_after\trows\tpurpose\tuser\thost\tpid\t"
                         "git_commit\n")
            fh.write(f"{t}\tdata/sealed/{name}\t{sha}\tTrue\t{mode0}\t{mode1}\t{len(df)}\t{purpose}\t"
                     f"{getpass.getuser()}\t{socket.gethostname()}\t{os.getpid()}\t{git_state()['git_commit']}\n")
        self.accessed.append(name)
        log(f"unsealed {name} ({len(df)} rows) for {purpose}; mode restored {mode1}")
        return df


# ============================================================================================ final method
class StandinA1PairOnly:
    """Stand-in final method (dry run only): A1 pair_only, z-scored on the pool, cosine, no CSLS."""
    name = "standin:A1|pair_only"
    is_learned = False
    csls = False

    def weight_files(self):
        return []

    def embed(self, store, dataset, mode, pocket_ids):
        M = store.matrix(dataset, f"a1_pair_only_{mode}", pocket_ids)
        ok = np.isfinite(M).all(1)
        E = np.full((len(M), M.shape[1]), np.nan, np.float32)
        if ok.any():
            E[ok] = embed(M[ok], ZScorer.fit(M[ok]))
        return E


class MethodAdapter:
    """Adapter for ``pocketcompare.method.Method`` (A4b agent's API: ``raw_parts`` / ``embed(mats)`` with fixed,
    shipped part statistics).  Part matrices come from the label-free precomputed blocks: the A4b inputs
    data/processed/descriptors/<ds>/a1r (pocketcompare.a4b.raw_parts) where present, else the identical
    n_inputs_{L,D}.npz blocks of scripts/compute_n_inputs.py (same locators: L shell, D = best sub-pocket U)."""
    BLOCK = {("a1", "sph8"): "a1_sph8", ("env", "sph8"): "env_sph8", ("a1", "base"): "a1_base"}

    def __init__(self, m, cfg):
        self.m, self.cfg = m, cfg
        self.name = str(cfg.get("name", "final"))
        self.is_learned = cfg.get("kind") == "learned"
        self.csls = bool(getattr(m, "csls", cfg.get("variant") == "csls"))

    def weight_files(self):
        fs = [ROOT / f for f in self.cfg.get("files_sha256", {})] + [ROOT / f for f in self.cfg.get("model_files", [])]
        if self.cfg.get("input_stats"):
            fs.append(ROOT / self.cfg["input_stats"])
        return sorted(set(fs))

    def raw_parts(self, store, dataset, mode, pocket_ids):
        from pocketcompare import a4b as A4
        if A4.a1r_dir(dataset).exists():
            ids = set(A4.ids_table(dataset).pocket_id)
            pid = list(pocket_ids)
            have = np.array([p in ids for p in pid])
            out = [np.full((len(pid), 514 if src == "a1" else 113), np.nan) for src, _ in self.m.parts]
            if have.any():
                got = A4.raw_parts(dataset, mode, [p for p, h in zip(pid, have) if h], self.m.inp)
                for k in range(len(out)):
                    out[k][have] = got[k]
            return out
        return [store.matrix(dataset, f"n_inputs_{mode}:{self.BLOCK[part]}", pocket_ids) for part in self.m.parts]

    def embed(self, store, dataset, mode, pocket_ids):
        mats = self.raw_parts(store, dataset, mode, pocket_ids)
        E = np.asarray(self.m.embed(mats), np.float32)
        ok = np.ones(len(E), bool)
        for M in mats:
            ok &= np.isfinite(M).any(1)
        E[~ok] = np.nan
        return E


def load_method(allow_standin: bool, force_standin: bool = False):
    if METHOD_CFG.exists() and not force_standin:
        import yaml
        cfg = yaml.safe_load(METHOD_CFG.read_text())
        mod = importlib.import_module(cfg.get("module", "pocketcompare.method"))
        if hasattr(mod, "load"):
            return mod.load(cfg, ROOT), sha256_file(METHOD_CFG)
        return MethodAdapter(mod.Method(METHOD_CFG), cfg), sha256_file(METHOD_CFG)
    if not allow_standin:
        raise SystemExit(f"{METHOD_CFG} missing: the real run needs the frozen final method")
    log(f"{METHOD_CFG.name} absent -> stand-in final method {StandinA1PairOnly.name}")
    return StandinA1PairOnly(), None


# ============================================================================================ pair sets
@dataclass
class PairSet:
    name: str                 # result label, e.g. tough_m1_test
    dataset: str              # descriptor dataset
    pockets: pd.DataFrame     # pocket_id, logv_L, logv_D, d_match, + unit columns
    ia: np.ndarray
    ib: np.ndarray
    y: np.ndarray
    units: dict               # {unit name: per-pocket integer array}
    pos_cluster: np.ndarray | None = None
    subsets: dict = field(default_factory=dict)
    native: dict = field(default_factory=dict)   # {(arm, config): (scores, note)}
    synthetic: bool = False
    pairs: pd.DataFrame | None = None
    d_allowed: np.ndarray | None = None           # per pocket: may enter D mode (e.g. BURROW-clean)

    @property
    def pair_units(self):
        return {u: (a[self.ia], a[self.ib]) for u, a in self.units.items()}

    @property
    def dset(self):
        dm = self.pockets.d_match.to_numpy(bool)
        if self.d_allowed is not None:
            dm = dm & self.d_allowed
        return dm[self.ia] & dm[self.ib]

    @property
    def cov(self):
        lv = self.pockets.logv_L.to_numpy()
        return ev.size_covariates(lv[self.ia], lv[self.ib])


def _index(ds):
    return pd.read_parquet(ROOT / f"data/processed/cache/points/{ds}/index.parquet").set_index("pocket_id")


def _attach_geometry(P: pd.DataFrame, ds: str) -> pd.DataFrame:
    ix = _index(ds).reindex(P.pocket_id)
    ok = (ix.status == "ok").to_numpy()
    P = P.copy()
    P["cache_ok"] = ok
    P["logv_L"] = np.log(np.clip(ix.volume_A3.to_numpy(float), 1.0, None))
    P["logv_D"] = np.log(np.clip(ix.d_volume_A3.to_numpy(float), 1.0, None))
    P["d_coverage"] = ix.d_coverage.to_numpy(float)
    P["d_precision"] = ix.d_precision.to_numpy(float)
    P["d_match"] = ok & ((P.d_coverage >= 0.3) | (P.d_precision >= 0.5)).to_numpy()    # DESIGN §2.2 / D3
    return P


def _pairs_index(P, pairs, ca="pocket_a", cb="pocket_b"):
    pos = {p: i for i, p in enumerate(P.pocket_id)}
    if not (pairs[ca].isin(pos) & pairs[cb].isin(pos)).all():
        raise RuntimeError("pair with a pocket outside the pool")
    return pairs[ca].map(pos).to_numpy(), pairs[cb].map(pos).to_numpy()


def tough_set(name, pairs, pocket_filter) -> PairSet:
    """TOUGH-M1 partition (as eval_dev.ToughM1Dev): units = components of (ligand cluster ∪ homology group)."""
    split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
    P = split[pocket_filter(split)].sort_values("pocket_id").reset_index(drop=True)
    P = _attach_geometry(P, "tough_m1")
    if not P.cache_ok.all():
        raise RuntimeError("TOUGH-M1 pocket without a point-cache entry")
    unit = ED._components(len(P), ED._shared_label_edges(P.ligand_cluster.to_numpy())
                          + ED._shared_label_edges(P.group_id.to_numpy()))
    P["unit"] = unit
    ia, ib = _pairs_index(P, pairs)
    y = pairs.label.to_numpy().astype(int)
    pcomp = ED._components(len(P), list(zip(ia[y == 1], ib[y == 1])))
    ps = PairSet(name, "tough_m1", P, ia, ib, y, {"u": unit}, pos_cluster=pcomp[ia], pairs=pairs,
                 subsets={"all": np.ones(len(y), bool)})
    nat = {}
    if "apoc_c1" in pairs:
        nat.update({
            ("B5T", "apoc_ps"): (pairs.apoc_c1.to_numpy(float), "APoc PS-score (apoc_c1)"),
            ("B5T", "apoc_negp"): (-pairs.apoc_c2.to_numpy(float), "−APoc P-value (apoc_c2)"),
            ("B5T", "glosa_ga"): (pairs.glosa_c1.to_numpy(float), "G-LoSA GA-score (glosa_c1)"),
            **{("B5T", f"siteengine_c{k}"): (pairs[f"siteengine_c{k}"].to_numpy(float),
                                             f"SiteEngine column {k} as shipped (undocumented)") for k in (1, 2, 3)}})
    if "tm_score" in pairs:
        nat[("B0p", "tm_score")] = (pairs.tm_score.to_numpy(float), "Fr-TM-align TM-score (TOUGH-M1 list)")
        nat[("B0p", "seq_identity")] = (pairs.seq_identity.to_numpy(float), "global sequence identity (TOUGH-M1 list)")
    ps.native = nat
    return ps


def tough_test_units() -> dict:
    split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
    t = split[split.partition == "test"].reset_index(drop=True)
    u = ED._components(len(t), ED._shared_label_edges(t.ligand_cluster.to_numpy())
                       + ED._shared_label_edges(t.group_id.to_numpy()))
    return {"n_units": int(u.max() + 1)}


def blips_set(name, pairs, sites, cache_ds, desc_ds, exclusions=None, allow_missing=False) -> PairSet:
    """BLiPS (as eval_dev.BlipsVal): units hom (homology group) and lig (Butina cluster of the label ligand)."""
    S = sites.sort_values("site_id").reset_index(drop=True)
    if exclusions is not None:
        S = S[~S.site_id.isin(exclusions)].reset_index(drop=True)
        pairs = pairs[pairs.site_a.isin(set(S.site_id)) & pairs.site_b.isin(set(S.site_id))].reset_index(drop=True)
    P = pd.DataFrame({"pocket_id": S.site_id.to_numpy(), "group_id": S.group_id.to_numpy(),
                      "label_cluster": S.label_cluster.to_numpy()})
    P = _attach_geometry(P, cache_ds)
    if not P.cache_ok.all() and not allow_missing:
        raise RuntimeError(f"{name}: site without a point-cache entry")
    hom, lig = pd.factorize(P.group_id)[0], pd.factorize(P.label_cluster)[0]
    P["unit"] = hom
    ia, ib = _pairs_index(P, pairs, "site_a", "site_b")
    y = pairs.label.to_numpy().astype(int)
    yb = y == 1
    cs = pairs.chemotype_seen.to_numpy()
    neg = ~yb
    subsets = {"all": np.ones(len(y), bool), "no_promiscuous": ~pairs.promiscuous.to_numpy(bool),
               "n_shared_1": neg | (yb & (pairs.n_shared.to_numpy() == 1)),
               "n_shared_ge2": neg | (yb & (pairs.n_shared.to_numpy() >= 2)),
               "chemotype_seen": neg | (yb & (cs == True)),  # noqa: E712
               "chemotype_unseen": neg | (yb & (cs == False))}  # noqa: E712
    return PairSet(name, desc_ds, P, ia, ib, y, {"hom": hom, "lig": lig}, pos_cluster=pairs.pair_cluster.to_numpy(),
                   subsets=subsets, pairs=pairs)


_PU_CACHE = {}


def prospeccts_units(P: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(homology-group unit per pocket, BURROW-clean flag per pocket) from the committed homology graph."""
    if "maps" not in _PU_CACHE:
        _PU_CACHE["maps"] = _prospeccts_maps()
    grp, sid, by_pdb, touch, tab = _PU_CACHE["maps"]
    g, clean = [], []
    for p in P.pocket_id:
        if p in grp:
            g.append(grp[p]), clean.append(sid[p] not in touch)
        else:   # decoys (no node): the parent entry's group via the PDB id; else own unit, not BURROW-clean
            pdb = tab.pdb_id.get(p)
            if pdb is not None and pdb in by_pdb.index:
                g.append(by_pdb.group_id[pdb]), clean.append(by_pdb.sid[pdb] not in touch)
            else:
                g.append(f"own:{p}"), clean.append(False)
    return pd.factorize(pd.Series(g))[0], np.asarray(clean, bool)


def _prospeccts_maps():
    nodes = pd.read_parquet(ROOT / "data/splits/homology_nodes.parquet",
                            columns=["dataset", "pdb_id", "chain", "pocket_ids", "sid", "group_id"])
    pr = nodes[nodes.dataset == "prospeccts"].copy()
    pr["pid"] = pr.pocket_ids.str.split(";")
    ex = pr.explode("pid")
    tab = pd.read_parquet(ROOT / "data/processed/benchmarks/prospeccts_pockets.parquet",
                          columns=["pocket_id", "pdb_id", "chain"]).set_index("pocket_id")
    edges = pd.read_parquet(ROOT / "data/splits/homology_edges.parquet", columns=["sid_a", "sid_b"])
    bsid = set(nodes.sid[nodes.dataset.isin(["burrow_train", "burrow_dev", "burrow_partner"])])
    touch = set(edges.sid_b[edges.sid_a.isin(bsid)]) | set(edges.sid_a[edges.sid_b.isin(bsid)]) | bsid
    grp, sid = {}, {}
    for r in ex.itertuples():
        ch = tab.chain.get(r.pid)
        if r.pid not in grp or r.chain == ch:
            grp[r.pid], sid[r.pid] = r.group_id, r.sid
    by_pdb = pr.groupby("pdb_id").agg(group_id=("group_id", "first"), sid=("sid", "first"))
    return grp, sid, by_pdb, touch, tab


def prospeccts_sets(pairs: pd.DataFrame, synthetic: bool) -> list[PairSet]:
    """One PairSet per subset (pool = the subset's pockets); subsets: all / no_self (+ P3/P4 5sub variants)."""
    out = []
    for sub in ["P1", "P1.2", "P2", "P3", "P4", "P5", "P5.2", "P6", "P6.2", "P7"]:
        pp = pairs[pairs.subset == sub].reset_index(drop=True)
        if not len(pp):
            continue
        P = pd.DataFrame({"pocket_id": sorted(set(pp.pocket_a) | set(pp.pocket_b))})
        P = _attach_geometry(P, "prospeccts")
        hom, clean = prospeccts_units(P)
        P["unit"], P["burrow_clean"] = hom, clean
        ia, ib = _pairs_index(P, pp)
        y = pp.label.to_numpy().astype(int)
        selfm = pp.is_self.to_numpy(bool)
        subsets = {"with_self": np.ones(len(y), bool), "no_self": ~selfm}
        if sub in ("P3", "P4"):
            n5 = (y == 1) | (pp.decoy_nsub.fillna(0).to_numpy() == 5)
            subsets.update({"5sub_with_self": n5, "5sub_no_self": n5 & ~selfm})
        out.append(PairSet(f"prospeccts_{sub}", "prospeccts", P, ia, ib, y, {"hom": hom}, subsets=subsets,
                           synthetic=synthetic, pairs=pp, d_allowed=clean))
    return out


def vertex_set(pairs: pd.DataFrame, synthetic: bool) -> PairSet:
    tab = pd.read_parquet(ROOT / "data/processed/benchmarks/vertex_pockets.parquet",
                          columns=["pocket_id", "uniprot_ac"])
    P = pd.DataFrame({"pocket_id": sorted(set(pairs.pocket_a) | set(pairs.pocket_b))})
    P = _attach_geometry(P, "vertex")
    up = tab.set_index("pocket_id").uniprot_ac.reindex(P.pocket_id).to_numpy()
    P["uniprot"] = up
    nodes = pd.read_parquet(ROOT / "data/splits/homology_nodes.parquet", columns=["dataset", "uniprot", "group_id"])
    vg = nodes[nodes.dataset == "vertex"].dropna(subset=["uniprot"]).groupby("uniprot").group_id.agg(
        lambda s: s.value_counts().index[0])
    ug = [vg.get(u, f"own:{u}") for u in up]
    P["unit"] = pd.factorize(pd.Series(ug))[0]
    ia, ib = _pairs_index(P, pairs)
    y = pairs.label.to_numpy().astype(int)
    return PairSet("vertex", "vertex", P, ia, ib, y, {"hom": P.unit.to_numpy()}, subsets={"all": np.ones(len(y), bool)},
                   synthetic=synthetic, pairs=pairs)


# ============================================================================================ synthetic labels
def synthetic_prospeccts(rng) -> pd.DataFrame:
    t = pd.read_parquet(ROOT / "data/processed/benchmarks/prospeccts_pockets.parquet",
                        columns=["pocket_id", "subset", "decoy_nsub"])
    rows = []
    for sub in ["P1", "P1.2", "P2", "P3", "P4", "P5", "P5.2", "P6", "P6.2", "P7"]:
        ids = t.pocket_id[t.subset.fillna("").str.split(",").map(lambda s: sub in s)].to_numpy()
        n = min(3000, len(ids) * 10)
        a, b = rng.choice(ids, n), rng.choice(ids, n)
        k = max(1, n // 20)
        b[:k] = a[:k]                                         # some self-pairs
        nsub = t.set_index("pocket_id").decoy_nsub.reindex(b).to_numpy()
        rows.append(pd.DataFrame({"pocket_a": a, "pocket_b": b, "label": rng.random(n) < 0.3, "subset": sub,
                                  "is_self": a == b, "decoy_nsub": nsub}))
    return pd.concat(rows, ignore_index=True).astype({"label": int})


def synthetic_vertex(rng) -> pd.DataFrame:
    t = pd.read_parquet(ROOT / "data/processed/benchmarks/vertex_pockets.parquet", columns=["pocket_id", "uniprot_ac"])
    by = t.groupby("uniprot_ac").pocket_id.apply(list)
    ups = by.index.to_numpy()
    rows = []
    for _ in range(1500):
        u, v = rng.choice(ups, 2, replace=False)
        lab = int(rng.random() < 0.9)
        for a in by[u]:
            for b in by[v]:
                rows.append((a, b, lab, u, v))
    df = pd.DataFrame(rows, columns=["pocket_a", "pocket_b", "label", "uniprot_a", "uniprot_b"])
    a, b = df.uniprot_a, df.uniprot_b
    df["protein_pair"] = a.where(a < b, b) + "|" + b.where(a < b, a)
    df["is_self"] = df.pocket_a == df.pocket_b
    return df


def synthetic_tough_full(rng) -> pd.DataFrame:
    s = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet", columns=["pocket_id", "partition"])
    ids = s.pocket_id[s.partition != "dev"].to_numpy()
    n = 30000
    a, b = rng.choice(ids, n), rng.choice(ids, n)
    keep = a != b
    return pd.DataFrame({"pocket_a": a[keep], "pocket_b": b[keep], "label": (rng.random(keep.sum()) < 0.45).astype(int),
                         "tm_score": rng.random(keep.sum()), "seq_identity": rng.random(keep.sum())})


# ============================================================================================ score vectors
Vec = ED.Vec


def _embed_scores(E_rows, rows, n, ia, ib, csls):
    """Raw + CSLS pair scores from unit embeddings of the pool rows (exactly as eval_dev.cosine_vectors)."""
    E = np.zeros((n, E_rows.shape[1]), np.float32)
    E[rows] = E_rows
    avail = np.zeros(n, bool)
    avail[rows] = True
    ok = avail[ia] & avail[ib]
    raw = np.full(len(ia), np.nan)
    raw[ok] = pair_scores(E, ia[ok], ib[ok])
    if not csls:
        return raw, None
    r = np.full(n, np.nan)
    r[rows] = csls_r(E_rows, E_rows, CSLS_K, query_ids=rows, bg_ids=rows)
    return raw, raw - 0.5 * (r[ia] + r[ib])


def final_vectors(ps: PairSet, method, store, modes=("L", "D"), dataset=None):
    ds = dataset or ps.dataset
    P = ps.pockets
    out = []
    for mode in modes:
        pool = P.cache_ok.to_numpy() if mode == "L" else P.d_match.to_numpy(bool)
        if mode == "D" and ps.d_allowed is not None:
            pool = pool & ps.d_allowed
        idx = np.where(pool)[0]
        if len(idx) <= CSLS_K + 1:
            continue
        E = np.asarray(method.embed(store, ds, mode, P.pocket_id.to_numpy()[idx]), np.float32)
        okr = np.isfinite(E).all(1)
        rows = idx[okr]
        raw, cs = _embed_scores(E[okr], rows, len(P), ps.ia, ps.ib, True)
        out.append(Vec("FINAL", method.name, "raw", mode, raw, E.shape[1], "final method"))
        out.append(Vec("FINAL", method.name, "csls", mode, cs, E.shape[1], "final method + CSLS (pool)"))
    return out


def descriptor_vectors(ps: PairSet, store, specs, modes=("L", "D"), dataset=None):
    """specs: [(arm, config, stem_prefix, zscore)] -> raw + CSLS cosine Vecs (eval_dev.cosine_vectors)."""
    ds = dataset or ps.dataset
    P = ps.pockets
    out = []
    for arm, cfg, stem, z in specs:
        for mode in modes:
            st = f"{stem}_{mode}"
            if not store.available(ds, st):
                continue
            M = store.matrix(ds, st, P.pocket_id)
            pool = P.cache_ok.to_numpy() if mode == "L" else P.d_match.to_numpy(bool)
            if mode == "D" and ps.d_allowed is not None:
                pool = pool & ps.d_allowed
            av = pool & np.isfinite(M).all(1)
            if av.sum() <= CSLS_K + 1:
                continue
            M = np.where(np.isfinite(M), M, 0.0)
            raw, cs = ED.cosine_vectors(M, av, ps.ia, ps.ib, zscore=z)
            note = "cosine, pool z-scored" if z else "cosine, raw"
            out += [Vec(arm, cfg, "raw", mode, raw, M.shape[1], note), Vec(arm, cfg, "csls", mode, cs, M.shape[1], note)]
    return out


BASE_SPECS = [("B1", "default", "b1_default", True), ("B4", "esm2", "b4_esm2", True),
              ("B4", "esm2_noz", "b4_esm2", False), ("A1", "pair_only", "a1_pair_only", True)]


def b0_vectors(ps: PairSet):
    P, ia, ib = ps.pockets, ps.ia, ps.ib
    lv, ld = P.logv_L.to_numpy(), P.logv_D.to_numpy()
    okL = P.cache_ok.to_numpy()
    sL = np.where(okL[ia] & okL[ib], -np.abs(lv[ia] - lv[ib]), np.nan)
    dset = ps.dset
    sD = np.where(dset, -np.abs(ld[ia] - ld[ib]), np.nan)
    return [Vec("B0", "default", "raw", "L", sL, 1, "−|Δ log V| (L-mode)"),
            Vec("B0", "default", "raw", "D", sD, 1, "−|Δ log V| (D-mode volume)")]


def b0p_foldseek(ps: PairSet, set_name: str):
    kf = ROOT / f"data/processed/b0prime/{set_name}_keys.parquet"
    tf = ROOT / f"data/processed/b0prime/{set_name}_tm.parquet"
    if not (kf.exists() and tf.exists()):
        return [], {"b0p_foldseek": f"missing {kf.name}"}
    keys = pd.read_parquet(kf).set_index("pocket_id").chain_key
    tm = pd.read_parquet(tf, columns=["key_a", "key_b", "tm_mean"])
    lut = dict(zip(zip(tm.key_a, tm.key_b), tm.tm_mean))
    ka = keys.reindex(ps.pockets.pocket_id).to_numpy()
    s = np.full(len(ps.ia), np.nan)
    n_nohit = 0
    for k, (i, j) in enumerate(zip(ps.ia, ps.ib)):
        a, b = ka[i], ka[j]
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        if a == b:
            s[k] = 1.0
            continue
        v = lut.get((a, b) if a < b else (b, a))
        if v is None or not np.isfinite(v):
            n_nohit += 1
            v = 0.0
        s[k] = v
    return ([Vec("B0p", "foldseek_tm", "native", "native", s, None, "Foldseek global TM (mean of qTM, tTM)")],
            {"b0p_foldseek_pairs_without_hit_set_to_0": n_nohit, "b0p_foldseek_missing": int(np.isnan(s).sum())})


def random_vec(ps: PairSet):
    rng = np.random.default_rng(SEEDS[0])
    M = rng.normal(size=(len(ps.pockets), 128))
    raw, _ = ED.cosine_vectors(M, np.ones(len(M), bool), ps.ia, ps.ib, csls=False)
    return Vec("CTRL", "random128", "control", "L", raw, 128, "Gaussian random 128-d vectors, cosine")


# ============================================================================================ evaluation core
def _gtask(a):
    key, y, s, pc, cov, ci, cj, B, seed = a
    nb = ED.n_bins_for(y)
    names = (["auc_cb"] if pc is not None else []) + (["auc_strat"] if cov is not None else [])

    def fn(w):
        out = []
        if pc is not None:
            out.append(ev.cluster_balanced_auc(y, s, pc, w)["auc_cb"])
        if cov is not None:
            out.append(ev.stratified_auc(y, s, cov, w, n_bins=nb)["auc_strat"])
        return out

    try:
        res = ev.vertex_bootstrap_generic(fn, ci, cj, B=B, seed=seed, names=names)
    except ValueError:
        return key, None
    return key, {r.name: r for r in res}


def _ok_mask(y, m):
    n = int(y[m].sum())
    return 0 < n < int(m.sum())


def eval_set(v: Vec, dset):
    base = dset if v.mode == "D" else np.ones(len(v.s), bool)
    return base & np.isfinite(v.s)


def evaluate_vectors(name, vecs, y_all, units, pc_all, cov_all, dset, subsets, args, *, generic_filter=None,
                     synthetic=False, ap_neg=False):
    """One row per (vector, subset): point metrics + vertex-bootstrap CIs (wider over unit definitions)."""
    y_all = np.asarray(y_all).astype(bool)
    tasks = []
    for v in vecs:
        if generic_filter is not None and not generic_filter(v):
            continue
        if pc_all is None and cov_all is None:
            continue
        for sn, sm in subsets.items():
            m = eval_set(v, dset) & sm
            if not _ok_mask(y_all, m):
                continue
            for un, (ci, cj) in units.items():
                tasks.append((f"{v.key}#{sn}#{un}", y_all[m], v.s[m], None if pc_all is None else pc_all[m],
                              None if cov_all is None else cov_all[m], ci[m], cj[m], args.B, args.seed))
    gen = ED.run_generic(tasks, args.threads, log, fn=_gtask) if tasks else {}
    rows = []
    for v in vecs:
        for sn, sm in subsets.items():
            m = eval_set(v, dset) & sm
            if not _ok_mask(y_all, m):
                continue
            y, s = y_all[m], v.s[m]
            r = ev.binary_metrics(y, s)
            row = {"set": name, "key": v.key, "subset": sn, "arm": v.arm, "config": v.config, "variant": v.variant,
                   "mode": v.mode, "dims": v.dims, "note": v.note, "synthetic": synthetic, "n_pairs": int(m.sum()),
                   "n_pos": r["n_pos"], "n_neg": r["n_neg"], "auc": r["auc"], "ap": r["ap"],
                   "prevalence": r["prevalence"], "ap_lift": r["ap_lift"], "pauc_mcclish": r["pauc_mcclish"],
                   "pauc_raw": r["pauc_raw"], "B": args.B, "seed": args.seed}
            if ap_neg:
                row["ap_neg_target"] = ev.average_precision(y, s, target="neg")["ap"]
            if pc_all is not None:
                row["auc_cb"] = ev.cluster_balanced_auc(y, s, pc_all[m])["auc_cb"]
            if cov_all is not None:
                nb = ED.n_bins_for(y)
                st = ev.stratified_auc(y, s, cov_all[m], n_bins=nb)
                row.update(auc_strat=st["auc_strat"], strat_n_bins=f"{nb[0]}x{nb[1]}",
                           strat_n_strata_dropped=st["n_strata_dropped"],
                           strat_frac_pos_dropped=st["frac_pos_weight_dropped"])
            fast = {un: ev.vertex_bootstrap(y, s, ci[m], cj[m], B=args.B, seed=args.seed, n_threads=args.threads)
                    for un, (ci, cj) in units.items()}
            for un in units:
                row[f"n_units_{un}"] = fast[un]["auc"].n_clusters
            for metric in ("auc", "ap"):
                ED._ci_cols(row, metric, {un: fast[un][metric] for un in units})
            for metric in ("auc_cb", "auc_strat"):
                if metric in row:
                    ED._ci_cols(row, metric, {un: (None if gen.get(f"{v.key}#{sn}#{un}") is None
                                                   else gen[f"{v.key}#{sn}#{un}"].get(metric)) for un in units})
            ys, ss = y_all[sm], v.s[sm]
            ref = (dset & sm) if v.mode == "D" else sm
            miss = ev.missing_summary(y_all[ref], {"s": v.s[ref]})["s"]
            row.update(n_missing_in_ref_pos=miss["n_missing_pos"], n_missing_in_ref_neg=miss["n_missing_neg"])
            if np.isnan(ss).any():
                wc, _ = ev.worst_case(ys, ss)
                wm = ev.binary_metrics(ys, wc)
                mall = ev.missing_summary(ys, {"s": ss})["s"]
                row.update(auc_worst_all=wm["auc"], ap_worst_all=wm["ap"], miss_rate_pos_all=mall["miss_rate_pos"],
                           miss_rate_neg_all=mall["miss_rate_neg"])
            rows.append(row)
    return pd.DataFrame(rows), gen


def paired(y, sa, sb, units, args, mask=None):
    """Paired Δ ROC-AUC (a − b) on the common set; {unit: BootstrapResult} and the wider one."""
    y = np.asarray(y).astype(bool)
    m = np.isfinite(sa) & np.isfinite(sb)
    if mask is not None:
        m &= mask
    per = {un: ev.paired_bootstrap(y[m], sa[m], sb[m], ci[m], cj[m], B=args.B, seed=args.seed,
                                   n_threads=args.threads) for un, (ci, cj) in units.items()}
    d = {un: r["delta_auc"] for un, r in per.items()}
    w, wu = ED._wider(d)
    first = next(iter(per.values()))
    return {"n_pairs": int(m.sum()), "n_pos": int(y[m].sum()), "auc_a": first["auc_a"].estimate,
            "auc_b": first["auc_b"].estimate, "delta": w.estimate, "ci_low": w.ci_low, "ci_high": w.ci_high,
            "lower_one_sided_95": w.lower_one_sided, "se": w.se, "p_one_sided": w.p_value, "ci_unit": wu,
            "n_units": w.n_clusters, "n_degenerate": w.n_degenerate,
            "n_pairs_dropped_not_common": int((~(np.isfinite(sa) & np.isfinite(sb)) & (np.ones(len(y), bool)
                                                if mask is None else mask)).sum())}


def V(vecs):
    return {v.key: v for v in vecs}


# ============================================================================================ stages
def stage_tough(ps: PairSet, method, store, args, ref_dev: PairSet | None, b0p_set: str):
    log(f"[{ps.name}] {len(ps.pockets)} pockets, {len(ps.y)} pairs ({ps.y.sum()} pos), units "
        f"{len(np.unique(ps.units['u']))}, D-set {ps.dset.sum()}")
    vecs = final_vectors(ps, method, store)
    vecs += b0_vectors(ps)
    vecs += descriptor_vectors(ps, store, BASE_SPECS)
    if store.available("tough_m1", "b5_epocs"):
        M = store.matrix("tough_m1", "b5_epocs", ps.pockets.pocket_id)
        raw, cs = ED.neg_euclid_vectors(np.nan_to_num(M), np.isfinite(M).all(1), ps.ia, ps.ib)
        vecs += [Vec("B5", "epocs", "raw", "L", raw, M.shape[1], "−Euclidean (EPoCS)"),
                 Vec("B5", "epocs", "csls", "L", cs, M.shape[1], "−Euclidean (EPoCS)")]
    for (arm, cfg), (s, note) in ps.native.items():
        vecs.append(Vec(arm, cfg, "native", "native", s, None, note))
    fs_vecs, fs_info = b0p_foldseek(ps, b0p_set)
    vecs += fs_vecs
    # B0m: logistic on (log va + log vb, |Δ log v|) fit on TOUGH-M1-dev pairs (direction score, no intercept)
    ref = ref_dev if ref_dev is not None else ps
    lv_r = ref.pockets.logv_L.to_numpy()
    Xr = np.column_stack([lv_r[ref.ia] + lv_r[ref.ib], np.abs(lv_r[ref.ia] - lv_r[ref.ib])])
    mu, sd = Xr.mean(0), Xr.std(0)
    from sklearn.linear_model import LogisticRegression
    b = LogisticRegression(C=1.0, max_iter=5000).fit((Xr - mu) / sd, ref.y).coef_.ravel()
    lv = ps.pockets.logv_L.to_numpy()
    X = np.column_stack([lv[ps.ia] + lv[ps.ib], np.abs(lv[ps.ia] - lv[ps.ib])])
    vecs.append(Vec("B0m", "logit_sum_absdiff", "devfit", "L", ((X - mu) / sd) @ (b / np.linalg.norm(b)), 2,
                    "fit on TOUGH-M1-dev pairs" + (" (in-sample in the dry run)" if ref_dev is None else "")))
    vecs.append(random_vec(ps))
    log(f"[{ps.name}] {len(vecs)} vectors; bootstrap")
    tab, gen = evaluate_vectors(ps.name, vecs, ps.y, ps.pair_units, ps.pos_cluster, ps.cov, ps.dset, ps.subsets,
                                args, synthetic=ps.synthetic)
    # per-cluster AUC (10 largest positive clusters), final + B1
    pcl = {}
    for k in (f"FINAL|{method.name}|raw|L", "B1|default|raw|L"):
        v = V(vecs).get(k)
        if v is not None:
            pcl[k] = ev.per_cluster_auc(ps.y.astype(bool), v.s, ps.pos_cluster, k=10)
    return vecs, tab, {"b0p": fs_info, "per_cluster_auc": pcl}


def claims_tough(ps: PairSet, vecs, method, args):
    Vv = V(vecs)
    var = "csls" if method.csls else "raw"
    units = ps.pair_units
    out = {}
    fL, fD = Vv[f"FINAL|{method.name}|{var}|L"].s, Vv.get(f"FINAL|{method.name}|{var}|D")
    out["C1a"] = {"set": ps.name, "mode": "L", "comparison": f"FINAL[{var}] − B1 default[{var}]",
                  **paired(ps.y, fL, Vv[f"B1|default|{var}|L"].s, units, args)}
    out["C1b"] = {"set": ps.name, "mode": "L", "comparison": f"FINAL[{var}] − B4 esm2 (z)[{var}]",
                  **paired(ps.y, fL, Vv[f"B4|esm2|{var}|L"].s, units, args)}
    out["C1-D"] = {"set": ps.name, "mode": "D (both D-matched; common set)",
                   "comparison": f"FINAL[{var}] − B1 default[{var}]",
                   **paired(ps.y, fD.s, Vv[f"B1|default|{var}|D"].s, units, args, mask=ps.dset)}
    return out


def claim_c2(subsets: list[tuple[str, PairSet, list]], method, args, label):
    var = "csls" if method.csls else "raw"
    subs = []
    for nm, ps, vecs in subsets:
        Vv = V(vecs)
        m = ps.subsets.get("no_self", np.ones(len(ps.y), bool))
        ci, cj = ps.pair_units["hom"]
        subs.append({"name": nm, "y": ps.y[m], "s_a": Vv[f"FINAL|{method.name}|{var}|L"].s[m],
                     "s_b": Vv[f"B1|default|{var}|L"].s[m], "ci": ci[m], "cj": cj[m]})
    r = ev.macro_paired_bootstrap(subs, B=args.B, seed=args.seed, n_threads=args.threads)
    d = r["macro_delta_auc"]
    return {"set": label, "mode": "L, self-pairs removed", "comparison": f"macro FINAL[{var}] − B1 default[{var}]",
            "delta": d.estimate, "ci_low": d.ci_low, "ci_high": d.ci_high, "lower_one_sided_95": d.lower_one_sided,
            "se": d.se, "p_one_sided": d.p_value, "n_units": d.n_clusters, "n_degenerate": d.n_degenerate,
            "auc_a": r["macro_auc_a"].estimate, "auc_b": r["macro_auc_b"].estimate,
            "per_subset": {k: {"delta": v["delta_auc"].estimate, "ci": [v["delta_auc"].ci_low, v["delta_auc"].ci_high],
                               "auc_final": v["auc_a"], "auc_b1": v["auc_b"], "n_units": v["n_units"],
                               "missing": {kk: (int(vv) if isinstance(vv, (int, np.integer)) else vv)
                                           for kk, vv in v["missing"].items()}}
                           for k, v in r["subsets"].items()}}


def stage_prospeccts(sets: list[PairSet], method, store, args):
    tabs, keep, info = [], {}, {}
    for ps in sets:
        log(f"[{ps.name}] {len(ps.pockets)} pockets, {len(ps.y)} pairs, BURROW-clean pockets "
            f"{int(ps.d_allowed.sum())}, D-set {ps.dset.sum()}")
        vecs = final_vectors(ps, method, store) + b0_vectors(ps) + descriptor_vectors(ps, store, BASE_SPECS)
        fsv, fsi = b0p_foldseek(ps, "prospeccts")
        vecs += fsv
        info[ps.name] = fsi
        npos = int(ps.y.sum())
        cov = ps.cov if npos >= 20 else None
        tab, _ = evaluate_vectors(ps.name, vecs, ps.y, ps.pair_units, None, cov, ps.dset, ps.subsets, args,
                                  generic_filter=lambda v: v.variant in ("raw", "native"), synthetic=ps.synthetic)
        tabs.append(tab)
        keep[ps.name] = (ps, vecs)
    return pd.concat(tabs, ignore_index=True), keep, info


def stage_vertex(ps: PairSet, method, store, args):
    log(f"[vertex] {len(ps.pockets)} pockets, {len(ps.y)} pocket pairs")
    vecs = final_vectors(ps, method, store, modes=("L",)) + b0_vectors(ps)[:1] \
        + descriptor_vectors(ps, store, BASE_SPECS, modes=("L",))
    fsv, fsi = b0p_foldseek(ps, "vertex")
    vecs += fsv
    pr = ps.pairs.protein_pair.to_numpy()
    codes, uniq = pd.factorize(pr)
    lab = pd.Series(ps.y).groupby(codes).agg(["min", "max"])
    y = lab["max"].to_numpy()
    n_conf = int((lab["min"] != lab["max"]).sum())
    unit = ps.pockets.unit.to_numpy()
    first = pd.Series(np.arange(len(codes))).groupby(codes).first().to_numpy()
    ci, cj = unit[ps.ia[first]], unit[ps.ib[first]]
    pvecs = []
    for v in vecs:
        s = pd.Series(v.s).groupby(codes).max().to_numpy()          # NaN skipped; all-NaN -> NaN
        pvecs.append(Vec(v.arm, v.config, v.variant, "L" if v.mode == "native" else v.mode, s, v.dims,
                         v.note + "; protein pair = max over pocket pairs"))
    tab, _ = evaluate_vectors("vertex", pvecs, y, {"hom": (ci, cj)}, None, None, np.zeros(len(y), bool),
                              {"all": np.ones(len(y), bool)}, args, synthetic=ps.synthetic, ap_neg=True)
    return tab, {"n_protein_pairs": int(len(y)), "n_pos": int(y.sum()), "n_label_conflicts": n_conf,
                 "n_pocket_pairs": int(len(ps.y)), **fsi}


def stage_blips(ps: PairSet, af: PairSet | None, method, store, args, rel_dates, plddt):
    log(f"[{ps.name}] {len(ps.pockets)} sites, {len(ps.y)} pairs ({ps.y.sum()} pos); D-set {ps.dset.sum()}")
    specs = [s for s in BASE_SPECS if s[1] != "esm2_noz"]
    vecs = final_vectors(ps, method, store) + b0_vectors(ps) + descriptor_vectors(ps, store, specs)
    fsv, fsi = b0p_foldseek(ps, "blips_test_holo" if ps.name.endswith("test") else "blips_val")
    vecs += fsv
    tab, gen = evaluate_vectors(ps.name, vecs, ps.y, ps.pair_units, ps.pos_cluster, ps.cov, ps.dset, ps.subsets,
                                args, synthetic=ps.synthetic)
    c5 = {}
    if af is not None:
        avecs = final_vectors(af, method, store, dataset=af.dataset) + descriptor_vectors(af, store, specs,
                                                                                         dataset=af.dataset)
        Va, Vh = V(avecs), V(vecs)
        # pair strata: holo release date and AF site pLDDT
        d = rel_dates.reindex(ps.pockets.pocket_id).to_numpy()
        post = d >= np.datetime64("2018-05-01")
        pa, pb = post[ps.ia], post[ps.ib]
        rel = np.where(pa & pb, "post", np.where(~pa & ~pb, "pre", "mixed"))
        pl = plddt.reindex(ps.pockets.pocket_id).to_numpy(float)
        pmin = np.fmin(pl[ps.ia], pl[ps.ib])
        band = np.where(pmin >= 90, "ge90", np.where(pmin >= 70, "70_90", np.where(np.isfinite(pmin), "lt70", "na")))
        strata = {"all": np.ones(len(ps.y), bool),
                  **{f"release_{k}": rel == k for k in ("post", "pre", "mixed")},
                  **{f"plddt_{k}": band == k for k in ("ge90", "70_90", "lt70")}}
        for key in [k for k in Vh if k.split("|")[0] in ("FINAL", "B1", "B4") and k.split("|")[2] == "raw"
                    and k.split("|")[1] in (method.name, "default", "esm2")]:
            if key not in Va:
                continue
            for sn, sm in strata.items():
                if not _ok_mask(ps.y.astype(bool), sm & np.isfinite(Vh[key].s) & np.isfinite(Va[key].s)):
                    continue
                dm = ps.dset & af.dset if key.endswith("|D") else None
                mask = sm if dm is None else (sm & dm)
                try:
                    c5[f"{key}#{sn}"] = paired(ps.y, Vh[key].s, Va[key].s, ps.pair_units, args, mask=mask)
                except ValueError as e:
                    c5[f"{key}#{sn}"] = {"error": str(e)}
        atab, _ = evaluate_vectors(ps.name + "_af", avecs, af.y, af.pair_units, af.pos_cluster, af.cov, af.dset,
                                   {"all": af.subsets["all"]}, args, synthetic=ps.synthetic)
        tab = pd.concat([tab, atab], ignore_index=True)
    return tab, {"c5_holo_minus_af": c5, "b0p": fsi}


def stage_ppips(split: str, ortho: pd.DataFrame, sym: pd.DataFrame, method, store, args):
    """P-ortho / P-sym exactly as eval_dev.main_ppips, for the given split (z-score on PPIPS-train)."""
    P = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
    cs = pd.read_parquet(ROOT / "data/splits/ppips_complex_splits.parquet")
    P = P[["pocket_id", "complex", "is_interface", "split", "volume_A3"]].copy()
    P["group"] = P.complex.map(dict(zip(cs.complex, cs.group)))
    P["logv"] = np.log(np.clip(P.volume_A3.to_numpy(float), 1.0, None))
    pid = {p: i for i, p in enumerate(P.pocket_id)}
    tr = (P.split == "train").to_numpy()
    ev_ = (P.split == split).to_numpy()
    eval_idx = np.where(ev_)[0]
    ref = tr | ev_
    members = P.groupby("complex").indices
    n_eval = len(eval_idx)
    Q = ortho.reset_index(drop=True)
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
    S_ = sym.reset_index(drop=True)
    a_i, b_i = S_.pocket_a.map(pid).to_numpy(), S_.pocket_b.map(pid).to_numpy()
    sq, sh = np.concatenate([a_i, b_i]), np.concatenate([b_i, a_i])
    s_unit = np.concatenate([S_.complex.map(dict(zip(P.complex, P.group))).to_numpy()] * 2)
    rep_q = np.repeat(np.arange(len(sq)), n_eval)
    rep_c = np.tile(eval_idx, len(sq))
    keep = rep_c != sq[rep_q]
    rep_q, rep_c = rep_q[keep], rep_c[keep]
    rep_l = rep_c == sh[rep_q]
    s_i = sq[rep_q]
    rep_col = np.searchsorted(eval_idx, rep_c)

    def emb(M, zscore=True):
        M = np.asarray(M, np.float64)
        zs = ZScorer.fit(M[tr]) if zscore else None
        Er = embed(M[ref], zs)
        E = np.zeros((len(M), Er.shape[1]), np.float32)
        E[ref] = Er
        return E

    sources = []
    for arm, cfg, stem, z in [("B1", "default", "b1_default_D", True), ("B4", "esm2", "b4_esm2_D", True),
                              ("A1", "pair_only", "a1_pair_only_D", True)]:
        if store.available("ppips", stem):
            M = store.matrix("ppips", stem, P.pocket_id)
            sources.append((arm, cfg, emb(M, z), M.shape[1]))
    # final method: embedded on train+eval pockets (pool); method-level normalisation sees exactly that pool
    Ef = np.asarray(method.embed(store, "ppips", "D", P.pocket_id.to_numpy()[ref]), np.float32)
    if np.isfinite(Ef).all():
        E = np.zeros((len(P), Ef.shape[1]), np.float32)
        E[ref] = Ef
        sources.append(("FINAL", method.name, E, Ef.shape[1]))
    lv = P.logv.to_numpy()
    rows = []

    def run_one(arm, cfg, variant, so, ss, dims):
        ro = ev.retrieval_metrics(pd.DataFrame({"query": oq, "score": so, "label": ol}), ks=(1, 3))
        rk = ro["per_query"].set_index("query").reindex(np.arange(len(Q)))["rank"].to_numpy(float)
        o_top1, o_top3, o_rr = (rk <= 1).astype(float), (rk <= 3).astype(float), 1.0 / rk
        rs = ev.retrieval_metrics(pd.DataFrame({"query": rep_q, "score": ss, "label": rep_l}), ks=(1, 10))
        rks = rs["per_query"].set_index("query").reindex(np.arange(len(sq)))["rank"].to_numpy(float)
        s_pct = 1.0 - (rks - 1) / (n_eval - 2)
        bo = ED._boot_means({"top1": o_top1, "top3": o_top3, "mrr": o_rr}, q_unit, args.B, args.seed)
        bs = ED._boot_means({"pct": s_pct}, s_unit, args.B, args.seed)
        row = {"set": f"ppips_{split}", "key": f"{arm}|{cfg}|{variant}", "arm": arm, "config": cfg,
               "variant": variant, "mode": "D", "dims": dims, "ortho_n_queries": int(len(Q)),
               "ortho_n_units": int(len(np.unique(q_unit)))}
        for m_, x in (("top1", o_top1), ("top3", o_top3), ("mrr", o_rr)):
            r = bo[m_]
            row.update({f"ortho_{m_}": float(x.mean()), f"ortho_{m_}_lo": r.ci_low if r else np.nan,
                        f"ortho_{m_}_hi": r.ci_high if r else np.nan})
        r = bs["pct"]
        row.update(sym_all_pct=float(s_pct.mean()), sym_all_pct_lo=r.ci_low if r else np.nan,
                   sym_all_pct_hi=r.ci_high if r else np.nan, sym_n_queries=int(len(sq)))
        rows.append(row)

    run_one("B0", "default", "raw", -np.abs(lv[o_i] - lv[oc]), -np.abs(lv[s_i] - lv[rep_c]), 1)
    for arm, cfg, E, dims in sources:
        r = np.full(len(P), np.nan)
        r[eval_idx] = csls_r(E[eval_idx], E[eval_idx], CSLS_K, query_ids=eval_idx, bg_ids=eval_idx)
        so = pair_scores(E, o_i, oc).astype(np.float64)
        ss = (E[sq] @ E[eval_idx].T).astype(np.float64)[rep_q, rep_col]
        run_one(arm, cfg, "raw", so, ss, dims)
        run_one(arm, cfg, "csls", so - 0.5 * (r[o_i] + r[oc]), ss - 0.5 * (r[s_i] + r[rep_c]), dims)
    log(f"[ppips_{split}] {len(Q)} ortho queries, {len(sq)} sym queries, {len(rows)} rows")
    return pd.DataFrame(rows)


def stage_runtime(method, store, test_pockets: pd.Series):
    out = {}
    tim = pd.read_parquet(ROOT / "data/processed/cache/points/tough_m1/timing.parquet")
    idx = _index("tough_m1").reindex(test_pockets)
    t = tim.set_index("structure_key").reindex(idx.structure_key)
    fresh = t[(~t.cached.astype(bool)) & (t.status == "ok")] if "cached" in t else t
    if len(fresh):
        out["burrow_featurise_s_per_pocket_median"] = float(fresh.total_s.median())
    for stem in ("a1_pair_only_L", "b1_default_L"):
        f = ROOT / f"data/processed/descriptors/tough_m1/{stem}.ids.parquet"
        if f.exists():
            ids = pd.read_parquet(f).set_index("pocket_id").reindex(test_pockets)
            out[f"{stem}_ms_per_pocket_median"] = float(ids.time_ms.median())
    if hasattr(method, "runtime"):
        out["final_method"] = method.runtime()
    E = np.asarray(method.embed(store, "tough_m1", "L", test_pockets.to_numpy()), np.float32)
    E = E[np.isfinite(E).all(1)]
    rng = np.random.default_rng(SEEDS[0])
    i, j = rng.integers(0, len(E), 1_000_000), rng.integers(0, len(E), 1_000_000)
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        pair_scores(E, i, j)
        ts.append(time.perf_counter() - t0)
    out["pair_us_median_of_3"] = float(np.median(ts)) / 1e6 * 1e6
    out["final_dims"] = int(E.shape[1])
    out["bytes_per_pocket_float32"] = int(4 * E.shape[1])
    prot = {}
    for f in sorted((ROOT / "results/proteome").glob("*.json")) if (ROOT / "results/proteome").exists() else []:
        try:
            prot[f.name] = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            pass
    out["proteome"] = prot or "missing (results/proteome/*.json not found)"
    return out


# ============================================================================================ freeze / worktree
def git(*a, cwd=ROOT):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def tracked_clean(cwd=ROOT) -> bool:
    return git("status", "--porcelain", "--untracked-files=no", cwd=cwd) == ""


def write_freeze():
    if not METHOD_CFG.exists():
        raise SystemExit(f"{METHOD_CFG} missing")
    method, cfg_sha = load_method(False)
    fr = {"commit": git("rev-parse", "HEAD"), "method_config": str(METHOD_CFG.relative_to(ROOT)),
          "method_config_sha256": cfg_sha, "method_name": method.name, "method_is_learned": bool(method.is_learned),
          "weights": {str(Path(p).resolve().relative_to(ROOT)) if Path(p).resolve().is_relative_to(ROOT) else str(p):
                      sha256_file(p) for p in method.weight_files()},
          "evaluate_sha256": sha256_file(ROOT / "src/pocketcompare/evaluate.py"),
          "prereg_sha256": sha256_file(ROOT / "PREREG.md"),
          "final_eval_sha256": sha256_file(Path(__file__)),
          "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tree_clean_at_creation": tracked_clean()}
    (ROOT / "FREEZE.json").write_text(json.dumps(fr, indent=1) + "\n")
    print(json.dumps(fr, indent=1))
    print("Review, then commit FREEZE.json (it must name a commit that already contains everything above).")


def verify_freeze(fr: dict, method, cfg_sha, here: Path):
    errs = []
    ev_sha = sha256_file(here / "src/pocketcompare/evaluate.py")
    if ev_sha != fr.get("evaluate_sha256") or ev_sha != PREREG_EVALUATE_SHA256:
        errs.append(f"evaluate.py {ev_sha} vs FREEZE {fr.get('evaluate_sha256')} / PREREG {PREREG_EVALUATE_SHA256}")
    if fr.get("prereg_sha256") and sha256_file(here / "PREREG.md") != fr["prereg_sha256"]:
        errs.append("PREREG.md sha256 differs from FREEZE")
    if cfg_sha != fr.get("method_config_sha256"):
        errs.append(f"method config sha {cfg_sha} != FREEZE {fr.get('method_config_sha256')}")
    if fr.get("final_eval_sha256") and sha256_file(Path(__file__)) != fr["final_eval_sha256"]:
        errs.append("scripts/final_eval.py differs from FREEZE")
    for p, h in fr.get("weights", {}).items():
        q = Path(p) if Path(p).is_absolute() else here / p
        if not q.exists() or sha256_file(q) != h:
            errs.append(f"weights {p}: missing or sha256 mismatch")
    wf = {str(Path(p).resolve()) for p in method.weight_files()}
    fw = {str((Path(p) if Path(p).is_absolute() else here / p).resolve()) for p in fr.get("weights", {})}
    if wf != fw:
        errs.append(f"method weight files {sorted(wf)} != FREEZE weights {sorted(fw)}")
    if errs:
        raise SystemExit("FREEZE verification failed:\n  " + "\n  ".join(errs))


def enter_worktree(fr: dict, argv) -> int:
    """From the main checkout: checks, create the worktree at FREEZE.commit, re-run there, copy results back."""
    if git("ls-files", "FREEZE.json") != "FREEZE.json" or git("diff", "HEAD", "--", "FREEZE.json"):
        raise SystemExit("FREEZE.json must be committed and unmodified")
    if not tracked_clean():
        raise SystemExit("main tree has uncommitted changes to tracked files; refusing")
    commit = fr["commit"]
    git("cat-file", "-e", f"{commit}^{{commit}}")
    wt = ROOT.parent / f"{ROOT.name}_final_{commit[:10]}"
    if not wt.exists():
        git("worktree", "add", "--detach", str(wt), commit)
    if git("rev-parse", "HEAD", cwd=wt) != commit:
        raise SystemExit(f"worktree {wt} is not at {commit}")
    for rel in WORKTREE_LINKS:
        src, dst = ROOT / rel, wt / rel
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.symlink_to(src)
    shutil.copy2(ROOT / "FREEZE.json", wt / "FREEZE.json") if not (wt / "FREEZE.json").exists() else None
    env = dict(os.environ, FINAL_EVAL_WORKTREE=commit, POCKETCOMPARE_MAIN_ROOT=str(ROOT))
    log(f"running in worktree {wt} at {commit}")
    rc = subprocess.run([sys.executable, str(wt / "scripts/final_eval.py"), *argv], cwd=wt, env=env).returncode
    if rc == 0 and (wt / "results/final").exists():
        dst = ROOT / "results/final"
        dst.mkdir(parents=True, exist_ok=True)
        for f in (wt / "results/final").iterdir():
            shutil.copy2(f, dst / f.name)
        log(f"results copied to {dst}")
    return rc


# ============================================================================================ main
def run(args, real: bool, method, cfg_sha, sealed: Sealed, out: Path):
    store = DescriptorStore(ROOT)
    rng = np.random.default_rng(SEEDS[0])
    tabs, details = [], {"mode": "FINAL" if real else "DRYRUN-DEV", "method": method.name,
                         "method_is_learned": bool(method.is_learned), "method_csls": bool(method.csls),
                         "method_config_sha256": cfg_sha, "B": args.B, "seed": args.seed}
    split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
    dev_pairs = pd.read_parquet(ROOT / "data/splits/tough_m1_dev_pairs.parquet")
    tm_dev = tough_set("tough_m1_dev", dev_pairs, lambda s: s.partition == "dev")
    # ---------------------------------------------------------------- TOUGH-M1-test (C1a, C1b, C1-D)
    if real:
        tp = sealed.read("tough_m1_test_pairs.parquet", "C1a/C1b/C1-D + TOUGH-M1-test reported items")
        tm = tough_set("tough_m1_test", tp, lambda s: s.partition == "test")
        tvecs, ttab, tinfo = stage_tough(tm, method, store, args, tm_dev, "tough_m1_test")
    else:
        tm = tm_dev
        tvecs, ttab, tinfo = stage_tough(tm, method, store, args, None, "tough_m1_dev")
    tabs.append(ttab)
    details[tm.name] = tinfo
    claims = claims_tough(tm, tvecs, method, args)
    # ---------------------------------------------------------------- ProSPECCTs (C2 + all subsets)
    pp = (sealed.read("prospeccts_pairs.parquet", "C2 + ProSPECCTs reported items") if real
          else synthetic_prospeccts(rng))
    psets = prospeccts_sets(pp, synthetic=not real)
    ptab, pkeep, pinfo = stage_prospeccts(psets, method, store, args)
    tabs.append(ptab)
    details["prospeccts"] = pinfo
    if real:
        claims["C2"] = claim_c2([(k, *pkeep[f"prospeccts_{k}"]) for k in ("P5.2", "P6.2", "P7")], method, args,
                                "ProSPECCTs P5.2 + P6.2 + P7")
    # ---------------------------------------------------------------- BLiPS (test / val)
    sites2 = pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet")
    rd = pd.read_parquet(ROOT / "data/processed/benchmarks/blips_holo_release_dates.parquet")
    if real:
        bp = sealed.read("blips_test_pairs.parquet", "BLiPS-test reported items + C5")
        bs = sealed.read("blips_test_sites.parquet", "BLiPS-test site groups / label clusters")
        exc = pd.read_parquet(ROOT / "data/splits/blips_test_exclusions_v2.parquet")
        trp = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
        seen = set(trp.pair_cluster[trp.label == 1])
        bp = bp.copy()
        bp["chemotype_seen"] = np.where(bp.label == 1, bp.pair_cluster.isin(seen), None)   # vs BLiPS-train v2
        bl = blips_set("blips_test", bp, bs, "blips_test_holo", "blips_test_holo",
                       exclusions=set(exc.site_id[exc.excluded]))
        af = blips_set("blips_test", bp, bs, "blips_test_af", "blips_test_af", exclusions=set(exc.site_id[exc.excluded]),
                       allow_missing=True)
        afp = pd.read_parquet(ROOT / "data/processed/benchmarks/blips_test_af_pockets.parquet",
                              columns=["pocket_id", "site_plddt_mean"]).set_index("pocket_id").site_plddt_mean
        rdt = rd[rd.dataset == "blips_test_holo"].set_index("pocket_id").release_date
    else:
        vp = pd.read_parquet(ROOT / "data/splits/blips_val_pairs_v2.parquet")
        vs = sites2[sites2.partition == "val"]
        bl = blips_set("blips_val", vp, vs, "blips", "blips")
        af = blips_set("blips_val", vp, vs, "blips", "blips")            # holo stands in for AF (Δ = 0)
        afp = pd.Series(80.0, index=vs.site_id)
        rdt = rd[rd.dataset == "blips"].set_index("pocket_id").release_date
    btab, binfo = stage_blips(bl, af, method, store, args, rdt, afp)
    tabs.append(btab)
    details[bl.name] = binfo
    if not real:   # C2 stand-in: macro over {TOUGH-M1-dev, BLiPS-val}, L, homology-group units
        bl_vecs = final_vectors(bl, method, store, modes=("L",)) + descriptor_vectors(bl, store, BASE_SPECS[:1],
                                                                                     modes=("L",))
        tmh = PairSet(tm.name, tm.dataset, tm.pockets, tm.ia, tm.ib, tm.y,
                      {"hom": pd.factorize(tm.pockets.group_id)[0]}, subsets={})
        blh = PairSet(bl.name, bl.dataset, bl.pockets, bl.ia, bl.ib, bl.y, {"hom": bl.units["hom"]}, subsets={})
        claims["C2"] = claim_c2([("tough_m1_dev", tmh, tvecs), ("blips_val", blh, bl_vecs)], method, args,
                                "DRY RUN stand-in: macro over TOUGH-M1-dev + BLiPS-val (L)")
    # ---------------------------------------------------------------- Holm
    ids = ["C1a", "C1b", "C1-D", "C2"]
    h = ev.holm([claims[c]["p_one_sided"] for c in ids], alpha=0.05)
    for c, pa, rj in zip(ids, h["p_adjusted"], h["reject"]):
        claims[c].update(p_holm=float(pa), reject_h0_holm=bool(rj),
                         lower_bound_ge_sesoi=bool(claims[c]["lower_one_sided_95"] >= SESOI), sesoi=SESOI)
    # ---------------------------------------------------------------- Vertex
    vp_ = sealed.read("vertex_pairs.parquet", "Vertex reported items") if real else synthetic_vertex(rng)
    vtab, vinfo = stage_vertex(vertex_set(vp_, synthetic=not real), method, store, args)
    tabs.append(vtab)
    details["vertex"] = vinfo
    # ---------------------------------------------------------------- TOUGH-M1 full minus dev (non-learned only)
    if real:
        full = sealed.read("tough_m1_pairs.parquet", "TOUGH-M1 full-minus-dev (literature-comparable, D8)")
    else:
        full = synthetic_tough_full(rng)
    devset = set(split.pocket_id[split.partition == "dev"])
    full = full[~full.pocket_a.isin(devset) & ~full.pocket_b.isin(devset)].reset_index(drop=True)
    fm = tough_set("tough_m1_full_minus_dev", full, lambda s: s.partition != "dev")
    fm.synthetic = not real
    fvecs = (final_vectors(fm, method, store, modes=("L",)) if not method.is_learned else []) \
        + b0_vectors(fm)[:1] + descriptor_vectors(fm, store, BASE_SPECS, modes=("L",))
    if store.available("tough_m1", "b5_epocs"):
        M = store.matrix("tough_m1", "b5_epocs", fm.pockets.pocket_id)
        raw, _ = ED.neg_euclid_vectors(np.nan_to_num(M), np.isfinite(M).all(1), fm.ia, fm.ib)
        fvecs.append(Vec("B5", "epocs", "raw", "L", raw, M.shape[1], "−Euclidean (EPoCS)"))
    for (arm, cfg), (s, note) in fm.native.items():
        fvecs.append(Vec(arm, cfg, "native", "native", s, None, note))
    ftab, _ = evaluate_vectors(fm.name, fvecs, fm.y, fm.pair_units, None, None, fm.dset, fm.subsets, args,
                               synthetic=fm.synthetic)
    yb = fm.y.astype(bool)
    for i, v in enumerate(fvecs):   # point cb / strat (no generic bootstrap at this size)
        m = eval_set(v, fm.dset)
        k = ftab.index[(ftab.key == v.key)]
        if len(k):
            ftab.loc[k, "auc_cb"] = ev.cluster_balanced_auc(yb[m], v.s[m], fm.pos_cluster[m])["auc_cb"]
            ftab.loc[k, "auc_strat"] = ev.stratified_auc(yb[m], v.s[m], fm.cov[m], n_bins=ED.n_bins_for(yb[m]))["auc_strat"]
    tabs.append(ftab)
    # ---------------------------------------------------------------- PPIPS
    if real:
        q = sealed.read("ppips_test_queries.parquet", "PPIPS-test P-ortho")
        s = sealed.read("ppips_sym_test_pairs.parquet", "PPIPS-test P-sym")
        ptab2 = stage_ppips("test", q, s, method, store, args)
    else:
        ptab2 = stage_ppips("val", pd.read_parquet(ROOT / "data/splits/ppips_ortho_queries_val.parquet"),
                            pd.read_parquet(ROOT / "data/splits/ppips_sym_pairs_val.parquet"), method, store, args)
    # ---------------------------------------------------------------- PPI-L (exploratory)
    if store.available("ppi_l", "b1_default_L"):
        details["ppi_l"] = "descriptors present but the PPI-L stage is not implemented in this version"
    else:
        details["ppi_l"] = "skipped: no PPI-L descriptors (data/processed/descriptors/ppi_l); exploratory per D7"
    # ---------------------------------------------------------------- runtime
    details["runtime"] = stage_runtime(method, store, tm.pockets.pocket_id)
    details["mde_reference"] = "dev-derived MDE ≈ 0.13 for C1 (results/dev/tough_m1_dev_details.json#mde)"
    details["sealed_files_accessed"] = sealed.accessed
    summary = pd.concat(tabs, ignore_index=True)
    return summary, ptab2, claims, details, store


def render_md(summary, ppips, claims, details) -> str:
    L = [f"# Final evaluation — {details['mode']}", "",
         f"Method `{details['method']}` (learned: {details['method_is_learned']}, CSLS: {details['method_csls']}); "
         f"B = {details['B']}, seed {details['seed']}.", "", "## Claims (Holm over C1a, C1b, C1-D, C2; one-sided α 0.05)",
         "", "| claim | set | comparison | n | AUC final | AUC ref | Δ [95 % CI] | lower 95 % | p | p Holm | reject | ≥ SESOI |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c, r in claims.items():
        L.append(f"| {c} | {r['set']} | {r['comparison']} | {r.get('n_pairs', r.get('n_units', ''))} | "
                 f"{r['auc_a']:.3f} | {r['auc_b']:.3f} | {r['delta']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] | "
                 f"{r['lower_one_sided_95']:+.3f} | {r['p_one_sided']:.4f} | {r.get('p_holm', np.nan):.4f} | "
                 f"{r.get('reject_h0_holm')} | {r.get('lower_bound_ge_sesoi')} |")
    for sname in summary.set.unique():
        sub = summary[(summary.set == sname)]
        syn = " (SYNTHETIC labels — code-path check only)" if sub.synthetic.any() else ""
        L += ["", f"## {sname}{syn}", "", "| subset | arm | config | variant | mode | n (pos) | ROC-AUC [CI] | AP (lift) | "
              "pAUC | cb-AUC [CI] | strat [CI] | worst |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sub.itertuples():
            g = lambda k: getattr(r, k, np.nan)  # noqa: E731
            L.append(f"| {r.subset} | {r.arm} | {r.config} | {r.variant} | {r.mode} | {r.n_pairs} ({r.n_pos}) | "
                     f"{ED._f(r.auc)} [{ED._f(g('auc_lo'))}, {ED._f(g('auc_hi'))}] | {ED._f(r.ap)} "
                     f"({ED._f(r.ap_lift, 2)}) | {ED._f(r.pauc_mcclish)} | {ED._f(g('auc_cb'))} [{ED._f(g('auc_cb_lo'))}, "
                     f"{ED._f(g('auc_cb_hi'))}] | {ED._f(g('auc_strat'))} [{ED._f(g('auc_strat_lo'))}, "
                     f"{ED._f(g('auc_strat_hi'))}] | {ED._f(g('auc_worst_all'))} |")
    L += ["", f"## PPIPS ({ppips.set.iloc[0] if len(ppips) else '-'})", "",
          "| arm | config | variant | ortho top-1 [CI] | top-3 | MRR [CI] | P-sym pct [CI] |", "|---|---|---|---|---|---|---|"]
    for r in ppips.itertuples():
        L.append(f"| {r.arm} | {r.config} | {r.variant} | {ED._f(r.ortho_top1)} [{ED._f(r.ortho_top1_lo)}, "
                 f"{ED._f(r.ortho_top1_hi)}] | {ED._f(r.ortho_top3)} | {ED._f(r.ortho_mrr)} [{ED._f(r.ortho_mrr_lo)}, "
                 f"{ED._f(r.ortho_mrr_hi)}] | {ED._f(r.sym_all_pct)} [{ED._f(r.sym_all_pct_lo)}, {ED._f(r.sym_all_pct_hi)}] |")
    L += ["", "## Runtime", "", "```", json.dumps(details.get("runtime"), indent=1, default=str)[:3000], "```"]
    return "\n".join(L) + "\n"


REPRO_METRICS = ["auc", "auc_lo", "auc_hi", "ap", "ap_lo", "ap_hi", "pauc_mcclish", "auc_cb", "auc_cb_lo", "auc_cb_hi",
                 "auc_strat", "auc_strat_lo", "auc_strat_hi"]


def reproduction_check(summary, ppips, method) -> dict:
    """Dry run: B1 / A1 (and the stand-in FINAL) rows vs results/dev/*_summary.parquet."""
    out = {"compared": [], "max_abs_deviation": 0.0}
    sets = [("tough_m1_dev", ROOT / "results/dev/tough_m1_dev_summary.parquet", None),
            ("blips_val", ROOT / "results/dev/blips_val_summary.parquet", "subset")]
    for sname, f, subcol in sets:
        dev = pd.read_parquet(f)
        mine = summary[summary.set == sname]
        for arm, cfg in (("B1", "default"), ("A1", "pair_only"), ("FINAL", method.name)):
            dcfg = "pair_only" if arm == "FINAL" else cfg
            darm = "A1" if arm == "FINAL" else arm
            for var in ("raw", "csls"):
                for mode in ("L", "D"):
                    a = mine[(mine.arm == arm) & (mine.config == cfg) & (mine.variant == var) & (mine["mode"] == mode)]
                    b = dev[(dev.arm == darm) & (dev.config == dcfg) & (dev.variant == var) & (dev["mode"] == mode)]
                    if arm == "FINAL" and method.name != StandinA1PairOnly.name:
                        continue
                    if subcol:
                        a = a.set_index("subset")
                        b = b.set_index("subset")
                        keys = sorted(set(a.index) & set(b.index))
                    else:
                        a = a.assign(subset="all").set_index("subset")
                        b = b.assign(subset="all").set_index("subset")
                        keys = ["all"] if len(a) and len(b) else []
                    for k in keys:
                        dev_ = {m: float(b.loc[k, m]) for m in REPRO_METRICS if m in b.columns}
                        me = {m: float(a.loc[k, m]) for m in dev_ if m in a.columns}
                        dmax = max(abs(me[m] - dev_[m]) for m in me if np.isfinite(dev_[m]) and np.isfinite(me[m]))
                        out["compared"].append({"set": sname, "arm": arm, "variant": var, "mode": mode, "subset": k,
                                                "max_abs_dev": dmax, "n_metrics": len(me)})
                        out["max_abs_deviation"] = max(out["max_abs_deviation"], dmax)
    devp = pd.read_parquet(ROOT / "results/dev/ppips_val_summary.parquet")
    for arm, dcfg in (("B1", "default"), ("A1", "pair_only (chosen)")):
        for var in ("raw", "csls"):
            a = ppips[(ppips.arm == arm) & (ppips.variant == var)]
            b = devp[(devp.arm == arm) & (devp.config == dcfg) & (devp.variant == var)]
            if len(a) and len(b):
                cols = [c for c in ("ortho_top1", "ortho_top1_lo", "ortho_top1_hi", "ortho_top3", "ortho_mrr",
                                    "ortho_mrr_lo", "ortho_mrr_hi", "sym_all_pct", "sym_all_pct_lo", "sym_all_pct_hi")]
                dmax = max(abs(float(a.iloc[0][c]) - float(b.iloc[0][c])) for c in cols)
                out["compared"].append({"set": "ppips_val", "arm": arm, "variant": var, "mode": "D", "subset": "all",
                                        "max_abs_dev": dmax, "n_metrics": len(cols)})
                out["max_abs_deviation"] = max(out["max_abs_deviation"], dmax)
    # FINAL vs the A4b agent's own dev numbers of the configured candidate (point metrics; different code path)
    fsel = ROOT / "results/dev/final_select_nonlearned_summary.parquet"
    cand = getattr(method, "cfg", {}).get("candidate")
    out["final_vs_a4b_selection"] = []
    if fsel.exists() and cand:
        ref = pd.read_parquet(fsel)
        for sname, dsn in (("tough_m1_dev", "tough_m1"), ("blips_val", "blips")):
            for var in ("raw", "csls"):
                for mode in ("L", "D"):
                    a = summary[(summary.set == sname) & (summary.arm == "FINAL") & (summary.variant == var)
                                & (summary["mode"] == mode) & (summary.subset == "all")]
                    b = ref[(ref.cand == cand) & (ref.variant == var) & (ref.dataset == dsn) & (ref["mode"] == mode)]
                    if len(a) and len(b):
                        d = {m: abs(float(a.iloc[0][m]) - float(b.iloc[0][m])) for m in ("auc", "ap", "auc_cb", "auc_strat")}
                        out["final_vs_a4b_selection"].append({"set": sname, "variant": var, "mode": mode,
                                                              "n_pairs": int(a.iloc[0].n_pairs),
                                                              "n_pairs_a4b": int(b.iloc[0].n_pairs), **d})
    out["n_rows_compared"] = len(out["compared"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dryrun-dev", action="store_true")
    ap.add_argument("--write-freeze", action="store_true")
    ap.add_argument("--B", type=int, default=ev.DEFAULT_B)
    ap.add_argument("--seed", type=int, default=SEEDS[0])
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--out", default=None)
    ap.add_argument("--standin", action="store_true", help="dry run only: force the A1 pair_only stand-in method")
    ap.add_argument("--check-only", action="store_true",
                    help="real run preflight: every FREEZE / worktree / hash check, then exit before any unsealing")
    args = ap.parse_args()
    os.environ["POCKETCOMPARE_THREADS"] = str(args.threads)
    if args.write_freeze:
        return write_freeze()
    real = not args.dryrun_dev
    if real:
        if os.environ.get("FINAL_EVAL") != "1":
            raise SystemExit("FINAL_EVAL=1 is required for the real final evaluation (use --dryrun-dev otherwise)")
        fp = ROOT / "FREEZE.json"
        if not fp.exists():
            raise SystemExit("FREEZE.json missing (python scripts/final_eval.py --write-freeze, review, commit)")
        fr = json.loads(fp.read_text())
        if os.environ.get("FINAL_EVAL_WORKTREE") != fr["commit"]:
            return enter_worktree(fr, sys.argv[1:])
        if git("rev-parse", "HEAD") != fr["commit"] or not tracked_clean():
            raise SystemExit("worktree is not clean at the frozen commit")
        method, cfg_sha = load_method(False)
        verify_freeze(fr, method, cfg_sha, ROOT)
        nohash = [n for n in SEALED_NEEDED if n not in Sealed(Path("/dev/null"), False).expected]
        if nohash:
            raise SystemExit(f"no recorded sha256 for sealed file(s) {nohash}: add them to {SEALED_SUMS.name}")
        if args.check_only:
            log(f"preflight OK: worktree {ROOT} at {fr['commit']}, evaluate.py / PREREG / method config / weights / "
                "final_eval.py hashes match FREEZE.json; no sealed file was opened")
            return 0
        out = ROOT / "results/final"
    else:
        method, cfg_sha = load_method(True, force_standin=args.standin)
        out = Path(args.out) if args.out else ROOT / "results/final_dryrun"
    out.mkdir(parents=True, exist_ok=True)
    sealed = Sealed(out / "unseal_log.tsv", enabled=real)
    summary, ppips, claims, details, store = run(args, real, method, cfg_sha, sealed, out)
    tag = "final" if real else "dryrun"
    cfg = {"mode": details["mode"], "B": args.B, "seed": args.seed, "csls_k": CSLS_K, "sesoi": SESOI,
           "method": method.name, "method_config_sha256": cfg_sha, "prereg": "PREREG.md §2–§4"}
    inputs = sorted({str(p) for p in store.inputs} | {str(ROOT / "PREREG.md"), str(ROOT / "scripts/eval_dev.py")})
    common = dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=inputs, seed=args.seed, device="cpu",
                  start_time=T0)
    write_result(out / f"{tag}_summary.parquet", summary, **common)
    write_result(out / f"{tag}_ppips.parquet", ppips, **common)
    write_result(out / f"{tag}_claims.json", claims, **common)
    write_result(out / f"{tag}_details.json", details, **common)
    md = out / f"{tag}_report.md"
    md.write_text(render_md(summary, ppips, claims, details))
    prov = {"result": str(md), "result_sha256": sha256_file(md), **git_state(), "script": str(Path(__file__)),
            "script_sha256": sha256_file(__file__), "args": sys.argv[1:], "config": cfg,
            "evaluate_sha256": ev.module_sha256(), "derived_from": [str(out / f"{tag}_summary.parquet"),
                                                                    str(out / f"{tag}_claims.json")]}
    (out / f"{tag}_report.md.prov.json").write_text(json.dumps(prov, indent=2, default=str) + "\n")
    if not real:
        rep = reproduction_check(summary, ppips, method)
        write_result(out / "reproduction_check.json", rep, **common)
        log(f"reproduction check: {rep['n_rows_compared']} rows, max |deviation| = {rep['max_abs_deviation']:.3g}")
    log("claims: " + "; ".join(f"{c} Δ {r['delta']:+.3f} p {r['p_one_sided']:.4f} Holm {r['p_holm']:.4f}"
                               for c, r in claims.items()))
    log(f"done -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
