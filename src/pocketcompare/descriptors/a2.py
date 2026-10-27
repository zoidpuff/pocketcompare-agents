"""A2 — docking-profile pocket descriptor (DESIGN §3 "A2").

Turns the raw per-pocket x per-molecule docking table written by ``scripts/a2/dock_tough_m1.py`` into three
descriptor blocks:

(a) ``rank``      PocketVec-style rank vector over the panel (most negative score = rank 1), with explicit
                  **non-binder bins**: a molecule is a non-binder if its score is above the panel's
                  ``nonbinder_quantile`` score (default: the 90th percentile of the panel's scores on the
                  reference set) or if its best pose left the pocket (pose centroid > 2 A from any pocket
                  point, flag ``in_pocket``).  Non-binders are binned, after the N binder ranks, to
                  N+1 (score bin), N+2 (out-of-pocket bin) and N+3 (missing / docking failure), as PocketVec
                  bins its non-binders to 129/130/131.
(b) ``le_resid``  ligand efficiency (score / heavy atoms) **residualised on log pocket volume and mean
                  buriedness** (per molecule: OLS LE ~ 1 + log V + buriedness) and then z-scored per molecule.
(c) ``ifp``       pose interaction profile: per molecule x contact type (H-bond donor matched, H-bond acceptor
                  matched, apolar, aromatic, charged, buried fraction) of the best pose, counts divided by the
                  molecule's heavy-atom count, z-scored per (molecule, type) and flattened.

**All fitted statistics — the non-binder threshold, the LE regression coefficients, and every z-score mean and
standard deviation — are estimated on a reference pocket set that the caller must pass explicitly.**  There is
deliberately no "fit on all pockets" default: at evaluation time that would leak the evaluation set into the
descriptor.  ``fit`` raises if ``reference_pocket_ids`` is missing or empty.

    ref = A2Descriptor(A2Config(panel="fragments")).fit(raw_train, pockets, reference_pocket_ids=train_ids)
    X   = ref.transform(raw_any, pockets)        # -> A2Vectors(pocket_id, rank, le_resid, ifp, concat())
    ref.save("results/a2/fragments_ref.npz");  A2Descriptor.load(...)
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

CONTACT_FEATURES = ("hbond_donor", "hbond_acceptor", "apolar", "aromatic", "charged", "buried_frac")
#: contact columns that are counts (scaled by heavy atoms when ``ifp_per_heavy``); ``buried_frac`` already is one
COUNT_FEATURES = ("hbond_donor", "hbond_acceptor", "apolar", "aromatic", "charged")
BLOCKS = ("rank", "le_resid", "ifp")
EPS = 1e-8


@dataclass(frozen=True)
class A2Config:
    panel: str                                   # "fragments" | "leadlike" (value of the raw `panel` column)
    nonbinder_quantile: float = 0.90             # DESIGN: non-binder = score above the panel's 90th percentile
    nonbinder_scope: str = "panel"               # "panel": one threshold for the panel; "molecule": per molecule
    use_in_pocket: bool = True                   # out-of-pocket poses are non-binders too
    rank_center: bool = False                    # subtract the reference mean rank per molecule (ablation)
    ifp_per_heavy: bool = True                   # divide contact counts by the molecule's heavy-atom count
    blocks: tuple = BLOCKS
    seed_agg: str = "mean"                       # how several seeds in the raw table are combined
    # columns of the pocket_meta table (data/processed/docking/tough_m1/pocket_geom.parquet);
    # use volume_D / bur16_D for a D-mode run
    volume_column: str = "volume_L"
    buriedness_column: str = "bur16_L"

    def __post_init__(self):
        if self.nonbinder_scope not in ("panel", "molecule"):
            raise ValueError("nonbinder_scope must be 'panel' or 'molecule'")
        if not set(self.blocks) <= set(BLOCKS):
            raise ValueError(f"unknown block in {self.blocks}")


@dataclass
class A2Vectors:
    pocket_id: np.ndarray
    mol_id: np.ndarray
    rank: np.ndarray | None = None               # (P, M)
    le_resid: np.ndarray | None = None           # (P, M)
    ifp: np.ndarray | None = None                # (P, M * len(CONTACT_FEATURES))
    feature_names: dict = field(default_factory=dict)

    def concat(self, blocks: Sequence[str] | None = None) -> np.ndarray:
        blocks = blocks or [b for b in BLOCKS if getattr(self, b) is not None]
        return np.concatenate([np.asarray(getattr(self, b), np.float32) for b in blocks], axis=1)

    def names(self, blocks: Sequence[str] | None = None) -> list:
        blocks = blocks or [b for b in BLOCKS if getattr(self, b) is not None]
        return [n for b in blocks for n in self.feature_names[b]]


# --------------------------------------------------------------------------- raw table helpers
def load_raw(path, panel: str | None = None, seeds: Iterable[int] | None = None) -> pd.DataFrame:
    """Read the shard parquets of one docking run (a directory) or a single parquet file."""
    path = Path(path)
    files = sorted(path.glob("shard*.parquet")) if path.is_dir() else [path]
    if not files:
        raise FileNotFoundError(f"no docking parquet under {path}")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    if panel is not None:
        df = df[df.panel == panel]
    if seeds is not None:
        df = df[df.seed.isin(list(seeds))]
    return df.reset_index(drop=True)


def _aggregate_seeds(df: pd.DataFrame, how: str) -> pd.DataFrame:
    if df["seed"].nunique() <= 1:
        return df.drop(columns=["seed"])
    num = ["score", "inter", "le", "pose_dist_pocket", *CONTACT_FEATURES]
    agg = {c: how for c in num if c in df.columns}
    agg["in_pocket"] = "mean"
    agg["n_heavy"] = "first"
    out = df.groupby(["pocket_id", "mol_id"], sort=False).agg(agg).reset_index()
    out["in_pocket"] = out["in_pocket"] >= 0.5
    return out


def _matrix(df: pd.DataFrame, value: str, pockets: Sequence[str], mols: Sequence[str]) -> np.ndarray:
    piv = df.pivot(index="pocket_id", columns="mol_id", values=value)
    return piv.reindex(index=pockets, columns=mols).to_numpy(dtype=np.float64)


def _prepare(df: pd.DataFrame, cfg: A2Config):
    df = df[df.panel == cfg.panel] if "panel" in df.columns else df
    if df.empty:
        raise ValueError(f"no rows for panel {cfg.panel!r}")
    if "seed" in df.columns:
        df = _aggregate_seeds(df, cfg.seed_agg)
    pockets = np.asarray(sorted(df.pocket_id.unique()))
    mols = np.asarray(sorted(df.mol_id.unique()))
    return df, pockets, mols


def _pocket_covariates(pocket_meta: pd.DataFrame, pockets: Sequence[str], cfg: A2Config) -> np.ndarray:
    m = pocket_meta.set_index("pocket_id").reindex(pockets)
    if m[[cfg.volume_column, cfg.buriedness_column]].isna().any().any():
        missing = m.index[m[cfg.volume_column].isna()].tolist()[:5]
        raise ValueError(f"pocket_meta misses volume/buriedness for e.g. {missing}")
    v = np.log(np.clip(m[cfg.volume_column].to_numpy(float), 1.0, None))
    b = m[cfg.buriedness_column].to_numpy(float)
    return np.column_stack([np.ones(len(m)), v, b])


# --------------------------------------------------------------------------- descriptor
class A2Descriptor:
    """Fit on a reference pocket set, transform any pocket set.  See the module docstring."""

    def __init__(self, config: A2Config):
        self.cfg = config
        self.mol_id_: np.ndarray | None = None
        self.n_ref_: int = 0
        self.nonbinder_threshold_: np.ndarray | None = None     # scalar array (panel) or (M,) (molecule)
        self.le_coef_: np.ndarray | None = None                 # (M, 3)
        self.le_mu_: np.ndarray | None = None                   # (M,)
        self.le_sd_: np.ndarray | None = None
        self.ifp_mu_: np.ndarray | None = None                  # (M, F)
        self.ifp_sd_: np.ndarray | None = None
        self.rank_mu_: np.ndarray | None = None                 # (M,)

    # ---- fit
    def fit(self, raw: pd.DataFrame, pocket_meta: pd.DataFrame,
            reference_pocket_ids: Sequence[str] | None = None) -> "A2Descriptor":
        if reference_pocket_ids is None or len(reference_pocket_ids) == 0:
            raise ValueError("A2Descriptor.fit needs an explicit, non-empty reference_pocket_ids "
                             "(fitting on all pockets is not allowed at evaluation time, DESIGN §3/§4)")
        ref = set(map(str, reference_pocket_ids))
        raw = raw[raw.pocket_id.isin(ref)]
        if raw.empty:
            raise ValueError("none of reference_pocket_ids occur in the raw docking table")
        df, pockets, mols = _prepare(raw, self.cfg)
        self.mol_id_, self.n_ref_ = mols, len(pockets)
        cfg = self.cfg

        S = _matrix(df, "score", pockets, mols)
        if cfg.nonbinder_scope == "panel":
            self.nonbinder_threshold_ = np.array([np.nanquantile(S, cfg.nonbinder_quantile)])
        else:
            self.nonbinder_threshold_ = np.nanquantile(S, cfg.nonbinder_quantile, axis=0)

        # (a) reference mean rank per molecule (only used when rank_center)
        R = self._ranks(df, pockets, mols)
        self.rank_mu_ = np.nanmean(R, axis=0)

        # (b) LE residualisation, fitted per molecule on the reference pockets
        X = _pocket_covariates(pocket_meta, pockets, cfg)
        LE = _matrix(df, "le", pockets, mols)
        coef = np.zeros((len(mols), X.shape[1]))
        mu = np.zeros(len(mols))
        sd = np.ones(len(mols))
        for j in range(len(mols)):
            y = LE[:, j]
            ok = np.isfinite(y)
            if ok.sum() > X.shape[1]:
                coef[j] = np.linalg.lstsq(X[ok], y[ok], rcond=None)[0]
            r = y - X @ coef[j]
            mu[j] = np.nanmean(r)
            s = np.nanstd(r)
            sd[j] = s if s > EPS else 1.0
        self.le_coef_, self.le_mu_, self.le_sd_ = coef, mu, sd

        # (c) interaction profile statistics
        P = self._ifp_raw(df, pockets, mols)
        self.ifp_mu_ = np.nanmean(P, axis=0)
        s = np.nanstd(P, axis=0)
        self.ifp_sd_ = np.where(s > EPS, s, 1.0)
        return self

    # ---- transform
    def transform(self, raw: pd.DataFrame, pocket_meta: pd.DataFrame) -> A2Vectors:
        if self.mol_id_ is None:
            raise RuntimeError("A2Descriptor is not fitted")
        cfg = self.cfg
        df, pockets, _ = _prepare(raw, cfg)
        mols = self.mol_id_
        out = A2Vectors(pocket_id=pockets, mol_id=mols)

        if "rank" in cfg.blocks:
            R = self._ranks(df, pockets, mols)
            if cfg.rank_center:
                R = R - self.rank_mu_[None, :]
            out.rank = R.astype(np.float32)
            out.feature_names["rank"] = [f"rank|{m}" for m in mols]

        if "le_resid" in cfg.blocks:
            X = _pocket_covariates(pocket_meta, pockets, cfg)
            LE = _matrix(df, "le", pockets, mols)
            Z = (LE - X @ self.le_coef_.T - self.le_mu_[None, :]) / self.le_sd_[None, :]
            out.le_resid = np.nan_to_num(Z, nan=0.0).astype(np.float32)
            out.feature_names["le_resid"] = [f"le|{m}" for m in mols]

        if "ifp" in cfg.blocks:
            P = self._ifp_raw(df, pockets, mols)
            Z = (P - self.ifp_mu_[None]) / self.ifp_sd_[None]
            out.ifp = np.nan_to_num(Z, nan=0.0).reshape(len(pockets), -1).astype(np.float32)
            out.feature_names["ifp"] = [f"ifp|{m}|{f}" for m in mols for f in CONTACT_FEATURES]
        return out

    def fit_transform(self, raw, pocket_meta, reference_pocket_ids) -> A2Vectors:
        return self.fit(raw, pocket_meta, reference_pocket_ids).transform(raw, pocket_meta)

    # ---- blocks
    def nonbinder_mask(self, df: pd.DataFrame, pockets, mols):
        """(score-bin mask, out-of-pocket mask, missing mask) — mutually exclusive, in that precedence."""
        S = _matrix(df, "score", pockets, mols)
        thr = self.nonbinder_threshold_
        thr = np.full(len(mols), thr[0]) if len(thr) == 1 else thr
        missing = ~np.isfinite(S)
        score_bin = np.isfinite(S) & (S > thr[None, :])
        if self.cfg.use_in_pocket and "in_pocket" in df.columns:
            ip = _matrix(df.assign(_ip=df.in_pocket.astype(float)), "_ip", pockets, mols)
            oop = np.isfinite(S) & (ip < 0.5) & ~score_bin
        else:
            oop = np.zeros_like(score_bin)
        return score_bin, oop, missing

    def _ranks(self, df: pd.DataFrame, pockets, mols) -> np.ndarray:
        """PocketVec-style rank vector with three non-binder bins at N+1, N+2, N+3."""
        S = _matrix(df, "score", pockets, mols)
        score_bin, oop, missing = self.nonbinder_mask(df, pockets, mols)
        nb = score_bin | oop | missing
        M = len(mols)
        R = np.empty_like(S)
        for i in range(S.shape[0]):
            row = S[i].copy()
            binder = ~nb[i]
            r = np.full(M, np.nan)
            if binder.any():
                # rankdata(method='max') over the binders only (PocketVec ties by 'max')
                r[binder] = pd.Series(row[binder]).rank(method="max").to_numpy()
            r[score_bin[i]] = M + 1
            r[oop[i]] = M + 2
            r[missing[i]] = M + 3
            R[i] = r
        return R

    def _ifp_raw(self, df: pd.DataFrame, pockets, mols) -> np.ndarray:
        nh = _matrix(df, "n_heavy", pockets, mols)
        cols = []
        for f in CONTACT_FEATURES:
            A = _matrix(df, f, pockets, mols)
            if self.cfg.ifp_per_heavy and f in COUNT_FEATURES:
                A = A / np.clip(nh, 1, None)
            cols.append(A)
        return np.stack(cols, axis=-1)        # (P, M, F)

    # ---- persistence
    def save(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, config=json.dumps(asdict(self.cfg), sort_keys=True),
                            mol_id=self.mol_id_, n_ref=self.n_ref_,
                            nonbinder_threshold=self.nonbinder_threshold_, le_coef=self.le_coef_,
                            le_mu=self.le_mu_, le_sd=self.le_sd_, ifp_mu=self.ifp_mu_, ifp_sd=self.ifp_sd_,
                            rank_mu=self.rank_mu_, contact_features=np.asarray(CONTACT_FEATURES))
        return path

    @classmethod
    def load(cls, path) -> "A2Descriptor":
        with np.load(path, allow_pickle=False) as z:
            cfg = json.loads(str(z["config"]))
            cfg["blocks"] = tuple(cfg["blocks"])
            d = cls(A2Config(**cfg))
            d.mol_id_ = z["mol_id"]
            d.n_ref_ = int(z["n_ref"])
            d.nonbinder_threshold_ = z["nonbinder_threshold"]
            d.le_coef_, d.le_mu_, d.le_sd_ = z["le_coef"], z["le_mu"], z["le_sd"]
            d.ifp_mu_, d.ifp_sd_ = z["ifp_mu"], z["ifp_sd"]
            d.rank_mu_ = z["rank_mu"]
        return d
