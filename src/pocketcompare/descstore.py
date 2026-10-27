"""Read-only access to precomputed, label-free pocket descriptors (data/processed/descriptors/<dataset>/).

Used by scripts/final_eval.py and by final-method plug-ins (``pocketcompare.method``) so that every arm reads its
inputs the same way.  Rows are looked up by pocket id (never by position), missing pockets give NaN rows.

    store = DescriptorStore(root)
    M = store.matrix("tough_m1", "a1_pair_only_L", pocket_ids)        # <arm>_<config>_<mode>.npy + .ids.parquet
    M = store.matrix("tough_m1", "b4_esm2_D", pocket_ids)             # b4_esm2_{L,D}.npy + b4_esm2_ids.parquet
    M = store.matrix("tough_m1", "n_inputs_L:a1_sph8", pocket_ids)    # n_inputs_{L,D}.npz block + n_inputs_ids
    lay = store.layout("tough_m1", "a1_default_L")                    # block layout (json) or None
    store.inputs                                                      # every file read (for provenance)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


class DescriptorStore:
    def __init__(self, root):
        self.root = Path(root)
        self.base = self.root / "data/processed/descriptors"
        self.inputs: list[Path] = []
        self._ids: dict = {}
        self._arr: dict = {}

    def _files(self, dataset: str, stem: str):
        d = self.base / dataset
        if stem.startswith("n_inputs_"):
            mode, _, block = stem[len("n_inputs_"):].partition(":")
            return d / f"n_inputs_{mode}.npz", d / "n_inputs_ids.parquet", block
        if stem.startswith("b4_esm2_") or stem.startswith("b5_epocs"):
            prefix = "b4_esm2" if stem.startswith("b4") else "b5_epocs"
            return d / f"{stem}.npy", d / f"{prefix}_ids.parquet", None
        return d / f"{stem}.npy", d / f"{stem}.ids.parquet", None

    def available(self, dataset: str, stem: str) -> bool:
        f, i, _ = self._files(dataset, stem)
        return f.exists() and i.exists()

    def _load(self, dataset: str, stem: str):
        f, i, block = self._files(dataset, stem)
        key = (str(f), block)
        if key not in self._arr:
            if f.suffix == ".npz":
                with np.load(f) as z:
                    self._arr[key] = np.asarray(z[block])
            else:
                self._arr[key] = np.load(f, mmap_mode="r")
            self.inputs += [f, i]
        if str(i) not in self._ids:
            ids = pd.read_parquet(i, columns=["pocket_id"])
            if ids.pocket_id.duplicated().any():
                raise RuntimeError(f"{i}: duplicated pocket ids")
            self._ids[str(i)] = pd.Series(np.arange(len(ids)), index=ids.pocket_id.to_numpy())
        return self._arr[key], self._ids[str(i)]

    def matrix(self, dataset: str, stem: str, pocket_ids) -> np.ndarray:
        """(len(pocket_ids), d) float64; NaN rows for pockets without a descriptor."""
        A, pos = self._load(dataset, stem)
        pid = pd.Index(np.asarray(pocket_ids, dtype=object))
        r = pos.reindex(pid).to_numpy()
        ok = ~pd.isna(r)
        out = np.full((len(pid), A.shape[1]), np.nan)
        if ok.any():
            out[ok] = np.asarray(A[r[ok].astype(np.int64)], np.float64)
        return out

    def layout(self, dataset: str, stem: str):
        f = self.base / dataset / f"{stem}.layout.json"
        return json.loads(f.read_text()) if f.exists() else None


__all__ = ["DescriptorStore"]
