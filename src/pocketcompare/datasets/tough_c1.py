"""TOUGH-C1 loader (Pu et al. 2019, DeepDrug3D, PLoS Comput Biol 15:e1006718; OSF enz69).

TOUGH-C1 is a pocket CLASSIFICATION benchmark (classes: nucleotide, heme,
steroid, control). It has no pair list, so only a pockets table is written
(data/processed/benchmarks/tough_c1_pockets.parquet). Deriving same-class
pairs would be our own label definition and is deliberately not done here.

Entries are '<pdb><chain><ligidx>' (e.g. 13pkA00): protein file
protein-<class>/<pdb><chain>.pdb (renumbered, as in TOUGH-M1), ligand file
ligand-<class>/<entry>.pdb. Pocket definitions provided by the benchmark:
  lpc-<class>.residues     "entry n res..."             ligand-contact residues (LPC)
  fpocket-<class>.residues "entry idx MCC n res..."      best fpocket pocket
We use the LPC residues as `pocket_def` and keep the fpocket pocket as extra columns.
"""
from __future__ import annotations

import pandas as pd

from .common import PROCESSED_DIR, in_pdb_mirror, raw_dir, rel

NAME = "tough_c1"
DL = raw_dir(NAME) / "downloads"
EX = raw_dir(NAME) / "extracted"
CLASSES = ["nucleotide", "heme", "steroid", "control"]
# DeepDrug3D paper / OSF: 1553 nucleotide, 596 heme, 69 steroid, 1946 control.
PAPER_COUNTS = {"nucleotide": 1553, "heme": 596, "steroid": 69, "control": 1946}


def _read_lpc(path):
    out = {}
    for line in open(path):
        t = line.split()
        if t:
            out[t[0]] = t[2:]
    return out


def _read_fpocket(path):
    out = {}
    for line in open(path):
        t = line.split()
        if t:
            out[t[0]] = (int(t[1]), float(t[2]), t[4:])
    return out


def build(write: bool = True) -> pd.DataFrame:
    rows = []
    for cls in CLASSES:
        lpc = _read_lpc(DL / f"lpc-{cls}.residues")
        fp = _read_fpocket(DL / f"fpocket-{cls}.residues")
        for entry in (DL / f"{cls}.list").read_text().split():
            prot = EX / f"protein-{cls}" / f"protein-{cls}" / f"{entry[:5]}.pdb"
            lig = EX / f"ligand-{cls}" / f"ligand-{cls}" / f"{entry}.pdb"
            f = fp.get(entry)
            res = lpc.get(entry)
            rows.append({
                "pocket_id": f"{NAME}:{entry}", "dataset": NAME, "subset": cls, "name": entry,
                "pdb_id": entry[:4].lower(), "chain": entry[4],
                "structure_path": rel(prot) if prot.exists() else None,
                "pocket_def_type": "residue_list",
                "pocket_def": ("A:" + ",".join(res)) if res else None,
                "pocket_file": None, "ligand_file": rel(lig) if lig.exists() else None,
                "ligand_resname": "LIG", "class_label": cls,
                "n_pocket_residues": len(res) if res else 0,
                "fpocket_index": f[0] if f else None, "fpocket_mcc": f[1] if f else None,
                "fpocket_residues": ",".join(f[2]) if f else None,
                "in_pdb_mirror": in_pdb_mirror(entry[:4]),
                "file_missing": not (prot.exists() and lig.exists()),
            })
    pockets = pd.DataFrame(rows)
    if write:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        pockets.to_parquet(PROCESSED_DIR / f"{NAME}_pockets.parquet", index=False)
    return pockets


def load() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / f"{NAME}_pockets.parquet")


if __name__ == "__main__":
    k = build()
    print(k.groupby("subset").agg(n=("pocket_id", "size"), missing=("file_missing", "sum"),
                                  in_mirror=("in_pdb_mirror", "sum"),
                                  no_res=("n_pocket_residues", lambda s: int((s == 0).sum()))))
    print("paper:", PAPER_COUNTS)
