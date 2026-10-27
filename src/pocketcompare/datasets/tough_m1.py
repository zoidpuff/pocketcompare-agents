"""TOUGH-M1 loader (Govindaraj & Brylinski 2018, BMC Bioinformatics 19:91).

Raw layout (scripts/data/fetch_tough_m1.py):
  downloads/TOUGH-M1_{positive,negative}.list  "idA idB seqid TMscore ligandTc"
  downloads/TOUGH-M1_pocket.list               "id best_pocket_index MCC"
  extracted/TOUGH-M1_dataset/<id>/<id>.pdb     single chain, renumbered from 1, chain 'A'
  extracted/TOUGH-M1_dataset/<id>/<id>00.pdb   bound ligand (resname LIG)
  extracted/TOUGH-M1_dataset/<id>/<id>.fpocket fpocket 2.0 output; 'POCKET n r1 r2 ...'
                                               lines list residue numbers of pocket n

Pocket definition used by the benchmark: the fpocket 2.0 pocket with index
`best_pocket_index` (the one best overlapping the ligand-binding residues;
MCC given). We record its residue list (numbering of the TOUGH-M1 .pdb file,
NOT of the original PDB entry) and the ligand file.
Labels: positive.list -> 1, negative.list -> 0 (as distributed).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import PROCESSED_DIR, in_pdb_mirror, raw_dir, rel, write_tables

NAME = "tough_m1"
DL = raw_dir(NAME) / "downloads"
ROOT = raw_dir(NAME) / "extracted" / "TOUGH-M1_dataset"

# OSF wiki / paper: 7524 targets, 505,116 positive, 556,810 negative pairs.
PAPER_COUNTS = {"n_pockets": 7524, "n_pos": 505116, "n_neg": 556810}


def _read_pairs(path: Path, label: int) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", header=None,
                     names=["a", "b", "seq_identity", "tm_score", "ligand_tc"],
                     dtype={"a": str, "b": str})
    df["label"] = label
    df["source_label"] = "positive" if label else "negative"
    return df


def _fpocket_residues(path: Path) -> dict[int, list[str]]:
    out = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            if line.startswith("POCKET "):
                tok = line.split()
                out[int(tok[1])] = tok[2:]
    return out


def build(write: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    pl = pd.read_csv(DL / "TOUGH-M1_pocket.list", sep=r"\s+", header=None,
                     names=["name", "pocket_index", "pocket_mcc"], dtype={"name": str})
    rows = []
    for r in pl.itertuples(index=False):
        d = ROOT / r.name
        prot, lig, fp = d / f"{r.name}.pdb", d / f"{r.name}00.pdb", d / f"{r.name}.fpocket"
        res = _fpocket_residues(fp) if fp.exists() else {}
        resids = res.get(int(r.pocket_index))
        pdb_id = r.name[:4].lower()
        rows.append({
            "pocket_id": f"{NAME}:{r.name}", "dataset": NAME, "subset": "TOUGH-M1",
            "name": r.name, "pdb_id": pdb_id, "chain": r.name[4] if len(r.name) > 4 else None,
            "structure_path": rel(prot) if prot.exists() else None,
            "pocket_def_type": "residue_list",
            "pocket_def": ("A:" + ",".join(resids)) if resids else None,
            "pocket_file": rel(fp) if fp.exists() else None,
            "ligand_file": rel(lig) if lig.exists() else None,
            "ligand_resname": "LIG",
            "fpocket_index": int(r.pocket_index), "pocket_mcc": float(r.pocket_mcc),
            "n_pocket_residues": len(resids) if resids else 0,
            "n_fpocket_pockets": len(res),
            "in_pdb_mirror": in_pdb_mirror(pdb_id),
            "file_missing": not (prot.exists() and lig.exists() and fp.exists()),
        })
    pockets = pd.DataFrame(rows)
    pos = _read_pairs(DL / "TOUGH-M1_positive.list", 1)
    neg = _read_pairs(DL / "TOUGH-M1_negative.list", 0)
    pairs = pd.concat([pos, neg], ignore_index=True)
    pairs["pocket_a"] = f"{NAME}:" + pairs["a"]
    pairs["pocket_b"] = f"{NAME}:" + pairs["b"]
    pairs["subset"] = "TOUGH-M1"
    pairs["is_self"] = pairs["a"] == pairs["b"]
    pairs["label"] = pairs["label"].astype("int8")
    pairs.insert(0, "pair_id", [f"{NAME}:{i}" for i in range(len(pairs))])
    pairs = pairs[["pair_id", "pocket_a", "pocket_b", "label", "subset", "source_label",
                   "is_self", "seq_identity", "tm_score", "ligand_tc"]]
    if write:
        write_tables(NAME, pairs, pockets)
    return pairs, pockets


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    return (pd.read_parquet(PROCESSED_DIR / f"{NAME}_pairs.parquet"),
            pd.read_parquet(PROCESSED_DIR / f"{NAME}_pockets.parquet"))


def counts(pairs: pd.DataFrame, pockets: pd.DataFrame) -> dict:
    key = pairs[["pocket_a", "pocket_b"]].apply(lambda s: s.str.slice(0), axis=0)
    unordered = pd.DataFrame({"x": key.min(axis=1), "y": key.max(axis=1), "label": pairs.label})
    in_pairs = set(pairs.pocket_a) | set(pairs.pocket_b)
    return {
        "n_pockets": len(pockets), "n_pockets_in_pairs": len(in_pairs),
        "n_pos": int(pairs.label.sum()), "n_neg": int((pairs.label == 0).sum()),
        "n_self": int(pairs.is_self.sum()),
        "n_duplicate_unordered": int(unordered.duplicated(["x", "y"]).sum()),
        "n_conflicting_labels": int(unordered.groupby(["x", "y"]).label.nunique().gt(1).sum()),
        "n_pairs_unknown_pocket": int((~pairs.pocket_a.isin(pockets.pocket_id)
                                       | ~pairs.pocket_b.isin(pockets.pocket_id)).sum()),
        "n_pockets_missing_files": int(pockets.file_missing.sum()),
        "n_pockets_no_residues": int((pockets.n_pocket_residues == 0).sum()),
        "n_in_pdb_mirror": int(pockets.in_pdb_mirror.sum()),
        **{f"paper_{k}": v for k, v in PAPER_COUNTS.items()},
    }


if __name__ == "__main__":
    p, k = build()
    for kk, v in counts(p, k).items():
        print(f"{kk:28s} {v}")
