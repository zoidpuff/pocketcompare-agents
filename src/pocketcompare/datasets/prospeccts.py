"""ProSPECCTs loader (Ehrt, Brinkjost & Koch 2018, PLoS Comput Biol 14:e1006483).

Raw layout (after scripts/data/fetch_prospeccts.py):
  data/raw/prospeccts/extracted/<archive>/<csv>           pair lists "a,b,active|inactive"
  data/raw/prospeccts/extracted/<archive>/<structdir>/X.pdb  protein + ONE ligand renamed 'LIG'

Pocket definition used by the benchmark: the single HETATM residue named LIG
in each PDB file (paper: site = residues within 5 A of any LIG atom; other
HETATMs removed except in barelier_structures_cofactors). We record the LIG
residue (chain, resnum) as the pocket definition; we do not compute residues.

Subsets (paper numbering, Table 2):
  P1   identical_structures            P1.2 identical_structures_similar_ligands
  P2   NMR_structures                  P3   decoy_rational_structures (+decoy_structures.csv)
  P4   decoy_shape_structures (+decoy_structures.csv)
  P5   Kahraman without the 20 phosphate sites (80x80)   P5.2 full Kahraman (100x100)
  P6   barelier_structures             P6.2 barelier_structures_cofactors
  P7   review_structures
Notes:
  * Pair lists are ORDERED and include self-pairs (all-vs-all incl. diagonal),
    exactly as distributed; the paper's counts are computed the same way.
  * decoy/decoy_structures/ is a third decoy set not mentioned in the README
    (differs from both rational and shape decoys); it is not used here.
  * Decoy file names <G><n><idx><chain>: G=group letter, n=number of
    substitutions (1..5). The paper's main P3/P4 results use only n=5
    (13,430 active / 13,430 inactive); column `decoy_nsub` allows that filter.
  * P5 phosphate sites are identified as LIG residues consisting of exactly
    one P and four O atoms (derived here; checked against paper counts).
"""
from __future__ import annotations

import gzip
from collections import Counter
from pathlib import Path

import pandas as pd

from .common import PROCESSED_DIR, in_pdb_mirror, raw_dir, rel, write_tables

NAME = "prospeccts"
EXTRACTED = raw_dir(NAME) / "extracted"

# subset -> (archive dir, csv, structure dir)
SUBSETS = {
    "P1": ("identical_structures", "identical_structures.csv", "identical_structures"),
    "P1.2": ("identical_structures_similar_ligands", "identical_structures_similar_ligands.csv",
             "identical_structures_similar_ligands"),
    "P2": ("NMR_structures", "NMR_structures.csv", "NMR_structures"),
    "P3": ("decoy", "decoy_structures.csv", "decoy_rational_structures"),
    "P4": ("decoy", "decoy_structures.csv", "decoy_shape_structures"),
    "P5": ("kahraman_structures", "kahraman_structures.csv", "kahraman_structures"),
    "P5.2": ("kahraman_structures", "kahraman_structures.csv", "kahraman_structures"),
    "P6": ("barelier_structures", "barelier_structures.csv", "barelier_structures"),
    "P6.2": ("barelier_structures", "barelier_structures.csv", "barelier_structures_cofactors"),
    "P7": ("review_structures", "review_structures.csv", "review_structures"),
}

# Ehrt et al. 2018, Table 2 (active, inactive); P3/P4 complete set and 5-substitution set.
PAPER_COUNTS = {
    "P1": (13430, 92846), "P1.2": (241, 1784), "P2": (7729, 100512),
    "P3": (13430, 67150), "P4": (13430, 67150), "P5": (920, 5480),
    "P5.2": (1320, 8680), "P6": (19, 43), "P6.2": (19, 43), "P7": (115, 56284),
}
PAPER_COUNTS_5SUB = {"P3": (13430, 13430), "P4": (13430, 13430)}
# Paper Table 8 / text: number of structures per set (None = not stated).
PAPER_N_STRUCTURES = {"P1": 326, "P5.2": 100, "P5": 80, "P6": 115, "P7": 1151}


def _parse_pdb(path: Path) -> dict:
    header_id = None
    lig_atoms, lig_res = [], set()
    chains = set()
    n_models = 0
    with open(path, errors="replace") as fh:
        for line in fh:
            rec = line[:6]
            if rec.startswith("HEADER"):
                header_id = line[62:66].strip() or None
            elif rec.startswith("MODEL"):
                n_models += 1
            elif rec.startswith(("ATOM  ", "HETATM")):
                if line[17:20].strip() == "LIG":
                    lig_res.add((line[21], line[22:27].strip()))
                    el = line[76:78].strip() or line[12:14].strip().lstrip("0123456789")[:1]
                    lig_atoms.append(el.upper())
                elif rec == "ATOM  ":
                    chains.add(line[21])
    return {"header_id": header_id, "lig_res": sorted(lig_res), "lig_elements": lig_atoms,
            "protein_chains": "".join(sorted(chains)), "n_models": n_models}


def _is_phosphate(elements: list[str]) -> bool:
    c = Counter(elements)
    return len(elements) == 5 and c.get("P", 0) == 1 and c.get("O", 0) == 4


def build(write: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    pocket_rows: dict[str, dict] = {}
    pair_frames = []
    for subset, (arch, csv, sdir) in SUBSETS.items():
        csv_path = EXTRACTED / arch / csv
        sroot = EXTRACTED / arch / sdir
        df = pd.read_csv(csv_path, header=None, names=["a", "b", "source_label"], dtype=str)
        df["source_label"] = df["source_label"].str.strip()
        assert set(df["source_label"]) <= {"active", "inactive"}, set(df["source_label"])
        names = sorted(set(df["a"]) | set(df["b"]))
        for nm in names:
            pid = f"{NAME}:{sdir}/{nm}"
            if pid in pocket_rows:
                continue
            path = sroot / f"{nm}.pdb"
            if not path.exists():
                pocket_rows[pid] = {"pocket_id": pid, "structure_path": None, "file_missing": True}
                continue
            info = _parse_pdb(path)
            is_decoy = sdir.startswith("decoy") and not (
                (EXTRACTED / "identical_structures" / "identical_structures" / f"{nm}.pdb").exists())
            if is_decoy or subset == "P2":
                pdb_id = (info["header_id"] or "").lower() or None
            else:
                pdb_id = nm[:4].lower()
            chain = nm[4] if len(nm) >= 5 else (info["lig_res"][0][0] if info["lig_res"] else None)
            lig = info["lig_res"]
            pocket_rows[pid] = {
                "pocket_id": pid, "dataset": NAME, "source_dir": f"{arch}/{sdir}", "name": nm,
                "pdb_id": pdb_id, "chain": chain, "structure_path": rel(path),
                "pocket_def_type": "ligand_residue",
                "pocket_def": ";".join(f"LIG:{c}:{r}" for c, r in lig),
                "pocket_file": None, "ligand_file": None, "ligand_resname": "LIG",
                "n_lig_residues": len(lig), "n_lig_atoms": len(info["lig_elements"]),
                "is_phosphate_site": _is_phosphate(info["lig_elements"]),
                "is_decoy": is_decoy,
                "decoy_nsub": int(nm[1]) if is_decoy else None,
                "n_models": info["n_models"], "protein_chains": info["protein_chains"],
                "in_pdb_mirror": bool(pdb_id) and not is_decoy and in_pdb_mirror(pdb_id),
                "file_missing": False,
            }
        df["pocket_a"] = f"{NAME}:{sdir}/" + df["a"]
        df["pocket_b"] = f"{NAME}:{sdir}/" + df["b"]
        df["label"] = (df["source_label"] == "active").astype("int8")
        df["subset"] = subset
        df["is_self"] = df["a"] == df["b"]
        if subset == "P5":
            phos = {n for n in names if pocket_rows[f"{NAME}:{sdir}/{n}"].get("is_phosphate_site")}
            df = df[~df["a"].isin(phos) & ~df["b"].isin(phos)].copy()
        if subset in ("P3", "P4"):
            df["decoy_nsub"] = [pocket_rows[p].get("decoy_nsub") for p in df["pocket_b"]]
        else:
            df["decoy_nsub"] = None
        pair_frames.append(df.drop(columns=["a", "b"]))
    pairs = pd.concat(pair_frames, ignore_index=True)
    pairs["decoy_nsub"] = pairs["decoy_nsub"].astype("Int8")
    pairs.insert(0, "pair_id", [f"{NAME}:{i}" for i in range(len(pairs))])
    pairs = pairs[["pair_id", "pocket_a", "pocket_b", "label", "subset", "source_label",
                   "is_self", "decoy_nsub"]]
    pockets = pd.DataFrame(list(pocket_rows.values()))
    pockets["decoy_nsub"] = pockets["decoy_nsub"].astype("Int8")
    # which subsets use each pocket
    use = pd.concat([pairs[["pocket_a", "subset"]].rename(columns={"pocket_a": "pocket_id"}),
                     pairs[["pocket_b", "subset"]].rename(columns={"pocket_b": "pocket_id"})])
    subs = use.drop_duplicates().groupby("pocket_id")["subset"].agg(lambda s: ",".join(sorted(s)))
    pockets["subset"] = pockets["pocket_id"].map(subs)
    if write:
        write_tables(NAME, pairs, pockets)
    return pairs, pockets


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (pairs, pockets) from data/processed/benchmarks/."""
    return (pd.read_parquet(PROCESSED_DIR / f"{NAME}_pairs.parquet"),
            pd.read_parquet(PROCESSED_DIR / f"{NAME}_pockets.parquet"))


def counts(pairs: pd.DataFrame, pockets: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for subset, g in pairs.groupby("subset", sort=False):
        ids = set(g["pocket_a"]) | set(g["pocket_b"])
        pa, pi = PAPER_COUNTS.get(subset, (None, None))
        rows.append({"subset": subset, "n_pockets": len(ids), "n_pos": int(g.label.sum()),
                     "n_neg": int((g.label == 0).sum()), "n_self": int(g.is_self.sum()),
                     "paper_pos": pa, "paper_neg": pi,
                     "paper_n_structures": PAPER_N_STRUCTURES.get(subset)})
        if subset in PAPER_COUNTS_5SUB:
            g5 = g[(g.label == 1) | (g.decoy_nsub == 5)]
            pa5, pi5 = PAPER_COUNTS_5SUB[subset]
            rows.append({"subset": subset + "_5sub", "n_pockets": len(set(g5.pocket_a) | set(g5.pocket_b)),
                         "n_pos": int(g5.label.sum()), "n_neg": int((g5.label == 0).sum()),
                         "n_self": int(g5.is_self.sum()), "paper_pos": pa5, "paper_neg": pi5,
                         "paper_n_structures": None})
    out = pd.DataFrame(rows)
    out["matches_paper"] = (out.n_pos == out.paper_pos) & (out.n_neg == out.paper_neg)
    return out


if __name__ == "__main__":
    p, k = build()
    pd.set_option("display.width", 200)
    print(counts(p, k).to_string(index=False))
    print("pockets:", len(k), "missing files:", int(k.file_missing.sum()),
          "in PDB mirror:", int(k.in_pdb_mirror.sum()), "decoys:", int(k.is_decoy.sum()))
