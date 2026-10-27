"""Helpers shared by the split builders (scripts/data/make_*_split.py).

Homology: the graph written by scripts/data/build_homology_graph.py (sid-level edges; nodes with identical
sequences share a sid and are direct neighbours). Ligands: ECFP4 (Morgan radius 2, 2048 bits, no chirality),
Tanimoto via bit-count matrix products, Butina clustering (RDKit algorithm: centroids picked by descending
neighbour count, ties by index).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parents[2]
SPLITS = ROOT / "data" / "splits"
SEALED = ROOT / "data" / "sealed"


# ------------------------------------------------------------------------------------------- homology
def load_homology() -> tuple[pd.DataFrame, pd.DataFrame]:
    return (pd.read_parquet(SPLITS / "homology_nodes.parquet"), pd.read_parquet(SPLITS / "homology_edges.parquet"))


class SidGraph:
    """Undirected sid graph (edges = seq OR fs rule)."""

    def __init__(self, nodes: pd.DataFrame, edges: pd.DataFrame):
        self.sids = np.array(sorted(set(nodes.sid) | set(edges.sid_a) | set(edges.sid_b)))
        self.idx = {s: i for i, s in enumerate(self.sids)}
        a = edges.sid_a.map(self.idx).to_numpy()
        b = edges.sid_b.map(self.idx).to_numpy()
        n = len(self.sids)
        m = coo_matrix((np.ones(len(a), dtype=np.int8), (a, b)), shape=(n, n)).tocsr()
        self.adj = ((m + m.T) > 0).tocsr()

    def mask(self, sids) -> np.ndarray:
        m = np.zeros(len(self.sids), bool)
        m[[self.idx[s] for s in set(sids)]] = True
        return m

    def touches(self, sids, target_sids) -> pd.Series:
        """For each sid in `sids`: True if it equals a target sid or has a DIRECT edge to one."""
        t = self.mask(target_sids)
        hit = t | (self.adj @ t.astype(np.int32) > 0)
        return pd.Series([bool(hit[self.idx[s]]) for s in sids], index=getattr(sids, "index", None))

    def components(self, sids) -> dict[str, int]:
        """Connected components of the subgraph induced by `sids` (sid -> component id)."""
        keep = self.mask(sids)
        sub = self.adj[keep][:, keep]
        _, lab = connected_components(csr_matrix(sub), directed=False)
        kept = self.sids[keep]
        return {s: int(c) for s, c in zip(kept, lab)}


def name_components(labels: pd.Series, prefix: str) -> pd.Series:
    """Renumber component labels by size (largest = g00000), ties by first appearance in sorted order."""
    vc = labels.value_counts()
    order = sorted(vc.index, key=lambda c: (-vc[c], c))
    ren = {c: f"{prefix}:g{i:05d}" for i, c in enumerate(order)}
    return labels.map(ren)


# ------------------------------------------------------------------------------------------- ligands
def ecfp4_from_mol(mol) -> np.ndarray | None:
    from rdkit.Chem import rdFingerprintGenerator
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    if mol is None:
        return None
    return gen.GetFingerprintAsNumPy(mol).astype(bool)


def mol_from_smiles_list(smiles: str):
    """First parseable SMILES of a ';'-separated BioLiP list (sanitised; falls back to partial sanitisation)."""
    from rdkit import Chem
    for s in str(smiles).split(";"):
        s = s.strip()
        if not s:
            continue
        m = Chem.MolFromSmiles(s)
        if m is not None:
            return m
    for s in str(smiles).split(";"):
        m = Chem.MolFromSmiles(s.strip(), sanitize=False)
        if m is not None:
            try:
                m.UpdatePropertyCache(strict=False)
                Chem.GetSymmSSSR(m)
                return m
            except Exception:  # noqa: BLE001
                continue
    return None


def tanimoto_matrix(fa: np.ndarray, fb: np.ndarray | None = None) -> np.ndarray:
    """Dense Tanimoto between boolean fingerprint matrices (rows)."""
    fb = fa if fb is None else fb
    A = fa.astype(np.float32)
    B = fb.astype(np.float32)
    inter = A @ B.T
    na = A.sum(1)[:, None]
    nb = B.sum(1)[None, :]
    union = na + nb - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(union > 0, inter / union, 0.0)
    return t.astype(np.float32)


def butina(sim: np.ndarray, threshold: float) -> np.ndarray:
    """Butina clustering on a dense similarity matrix; neighbours = sim >= threshold. Returns cluster ids
    (0 = largest-neighbourhood centroid's cluster)."""
    n = sim.shape[0]
    nb = sim >= threshold
    np.fill_diagonal(nb, True)
    counts = nb.sum(1)
    order = sorted(range(n), key=lambda i: (-counts[i], i))
    lab = -np.ones(n, dtype=np.int64)
    c = 0
    for i in order:
        if lab[i] >= 0:
            continue
        members = np.where(nb[i] & (lab < 0))[0]
        lab[members] = c
        c += 1
    return lab


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
