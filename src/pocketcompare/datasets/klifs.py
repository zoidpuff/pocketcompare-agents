"""KLIFS kinase-pocket metadata loader (Kanev et al. 2021, NAR 49:D562; https://klifs.net).

Not a pair benchmark: writes only data/processed/benchmarks/klifs_pockets.parquet
(one row per KLIFS structure = PDB entry + chain + altloc). Pocket definition =
KLIFS 85-residue pocket (`pocket` alignment string; '_' = gap). Residue
numbers are not included (needs one /structure_get_pocket call per structure).
"""
from __future__ import annotations

import json

import pandas as pd

from .common import PROCESSED_DIR, in_pdb_mirror, raw_dir

NAME = "klifs"
DL = raw_dir(NAME) / "downloads"


def build(write: bool = True) -> pd.DataFrame:
    s = pd.DataFrame(json.loads((DL / "structures_list.json").read_text()))
    k = pd.DataFrame(json.loads((DL / "kinase_information.json").read_text()))
    k = k[["kinase_ID", "family", "group", "uniprot"]] if "uniprot" in k else k[["kinase_ID", "family", "group"]]
    s = s.merge(k, on="kinase_ID", how="left")
    s["pocket_id"] = NAME + ":" + s.structure_ID.astype(str)
    s["dataset"] = NAME
    s["subset"] = s["group"]
    s["pdb_id"] = s.pdb.str.lower()
    s["structure_path"] = None
    s["pocket_def_type"] = "klifs_85"
    s["pocket_def"] = s.pocket
    s["ligand_resname"] = s.ligand.replace({0: None, "0": None})
    s["in_pdb_mirror"] = [in_pdb_mirror(p) for p in s.pdb_id]
    s = s.astype({c: "string" for c in s.columns if s[c].dtype == object})
    if write:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        s.to_parquet(PROCESSED_DIR / f"{NAME}_pockets.parquet", index=False)
    return s


def load() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / f"{NAME}_pockets.parquet")


if __name__ == "__main__":
    s = build()
    print("structures:", len(s), "PDB entries:", s.pdb_id.nunique(), "kinases:", s.kinase_ID.nunique(),
          "human:", int((s.species == "Human").sum()), "in mirror:", int(s.in_pdb_mirror.sum()))
