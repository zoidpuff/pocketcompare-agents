"""Vertex set loader (Chen et al. 2016, J Chem Inf Model 56:1734, doi:10.1021/acs.jcim.6b00118).

Raw: data/raw/vertex/extracted/acs_si/protein_pairs.tsv (ACS SI via figshare), columns
  Pocket_1 HET_1 IniProt_AC_1 UniProt_ID_1 Name_1 Pocket_2 HET_2 IniProt_AC_2 UniProt_ID_2 Name_2 Set
Pocket ids look like '3OOG_1' = PDB entry + site index; HET = ligand chemical
component defining the site. Set: 1 = proteins share a common active ligand
(positive), 0 = negative. Labels are defined at the PROTEIN (UniProt) pair
level; the benchmark scores each protein pair by the best of its k x l
pocket-pair scores (Chen et al. Fig 1B; DeeplyTough).

The ACS file does NOT ship structures or say which instance of HET is meant
by the site index. We record (pdb_id, site_index, het) as the benchmark's
pocket definition and check the entry and HET code in the local PDB mirror.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from .common import PROCESSED_DIR, pdb_mirror_path, raw_dir, write_tables

NAME = "vertex"
TSV = raw_dir(NAME) / "extracted" / "acs_si" / "protein_pairs.tsv"

# DeeplyTough (Simonovsky & Meyers 2020) text: 6,598 positive and 379 negative
# protein pairs from 6,029 structures; 1,461,668 positive and 102,935 negative
# pocket comparisons.
PAPER_COUNTS = {"n_structures": 6029, "n_pos_protein_pairs": 6598, "n_neg_protein_pairs": 379,
                "n_pos_pocket_pairs": 1461668, "n_neg_pocket_pairs": 102935}


def _het_instances(args: tuple[str, str]) -> tuple[str, str, int | None, str]:
    """Count residues named `het` in the mirror mmCIF (cheap text scan of atom_site)."""
    pdb_id, het = args
    path = pdb_mirror_path(pdb_id)
    if not path.exists():
        return pdb_id, het, None, ""
    seen = set()
    chains = set()
    try:
        import gemmi
        st = gemmi.read_structure(str(path))
        for ch in st[0]:
            for res in ch:
                if res.name == het:
                    seen.add((ch.name, str(res.seqid)))
                    chains.add(ch.name)
    except Exception as e:  # noqa: BLE001
        return pdb_id, het, -1, f"error:{e}"
    return pdb_id, het, len(seen), ";".join(f"{c}:{s}" for c, s in sorted(seen))


def build(write: bool = True, n_workers: int = 16) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(TSV, sep="\t", dtype=str)
    df.columns = ["p1", "het1", "ac1", "uid1", "name1", "p2", "het2", "ac2", "uid2", "name2", "set"]
    pockets = pd.concat([
        df[["p1", "het1", "ac1", "uid1", "name1"]].set_axis(["name", "het", "uniprot_ac", "uniprot_id", "protein_name"], axis=1),
        df[["p2", "het2", "ac2", "uid2", "name2"]].set_axis(["name", "het", "uniprot_ac", "uniprot_id", "protein_name"], axis=1),
    ]).drop_duplicates()
    n_conflict = pockets.name.duplicated().sum()
    assert n_conflict == 0, f"{n_conflict} pocket ids with conflicting metadata"
    pockets["pdb_id"] = pockets.name.str.split("_").str[0].str.lower()
    pockets["site_index"] = pockets.name.str.split("_").str[1].astype(int)
    with ProcessPoolExecutor(n_workers) as ex:
        res = list(ex.map(_het_instances, zip(pockets.pdb_id, pockets.het), chunksize=32))
    hmap = {(p, h): (n, inst) for p, h, n, inst in res}
    pockets["n_het_instances_in_mirror"] = [hmap[(p, h)][0] for p, h in zip(pockets.pdb_id, pockets.het)]
    pockets["het_instances"] = [hmap[(p, h)][1] for p, h in zip(pockets.pdb_id, pockets.het)]
    pockets["in_pdb_mirror"] = [pdb_mirror_path(p).exists() for p in pockets.pdb_id]
    pockets["structure_path"] = [str(pdb_mirror_path(p)) if ok else None
                                 for p, ok in zip(pockets.pdb_id, pockets.in_pdb_mirror)]
    pockets["pocket_id"] = f"{NAME}:" + pockets.name
    pockets["dataset"] = NAME
    pockets["subset"] = "Vertex"
    pockets["chain"] = None
    pockets["pocket_def_type"] = "ligand_het_site"
    pockets["pocket_def"] = "HET:" + pockets.het + ";site_index:" + pockets.site_index.astype(str)
    pockets["pocket_file"] = None
    pockets["ligand_file"] = None
    pockets["ligand_resname"] = pockets.het
    pockets["file_missing"] = ~pockets.in_pdb_mirror
    lead = ["pocket_id", "dataset", "subset", "name", "pdb_id", "chain", "structure_path",
            "pocket_def_type", "pocket_def", "pocket_file", "ligand_file", "ligand_resname"]
    pockets = pockets[lead + [c for c in pockets.columns if c not in lead]].reset_index(drop=True)

    pairs = pd.DataFrame({
        "pocket_a": f"{NAME}:" + df.p1, "pocket_b": f"{NAME}:" + df.p2,
        "label": df["set"].astype("int8"), "subset": "Vertex", "source_label": "Set=" + df["set"],
        "is_self": df.p1 == df.p2,
        "uniprot_a": df.ac1, "uniprot_b": df.ac2,
    })
    a, b = pairs.uniprot_a, pairs.uniprot_b
    pairs["protein_pair"] = a.where(a < b, b) + "|" + b.where(a < b, a)
    pairs.insert(0, "pair_id", [f"{NAME}:{i}" for i in range(len(pairs))])
    if write:
        write_tables(NAME, pairs, pockets)
    return pairs, pockets


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    return (pd.read_parquet(PROCESSED_DIR / f"{NAME}_pairs.parquet"),
            pd.read_parquet(PROCESSED_DIR / f"{NAME}_pockets.parquet"))


def counts(pairs: pd.DataFrame, pockets: pd.DataFrame) -> dict:
    pp = pairs.groupby("protein_pair").label.agg(["min", "max"])
    key = pd.DataFrame({"x": pairs[["pocket_a", "pocket_b"]].min(axis=1),
                        "y": pairs[["pocket_a", "pocket_b"]].max(axis=1)})
    return {
        "n_pockets": len(pockets), "n_structures": int(pockets.pdb_id.nunique()),
        "n_uniprot": int(pockets.uniprot_ac.nunique()),
        "n_pos_pocket_pairs": int(pairs.label.sum()), "n_neg_pocket_pairs": int((pairs.label == 0).sum()),
        "n_pos_protein_pairs": int((pp["min"] == 1).sum()), "n_neg_protein_pairs": int((pp["max"] == 0).sum()),
        "n_protein_pairs_conflicting": int((pp["min"] != pp["max"]).sum()),
        "n_same_uniprot_pairs": int((pairs.uniprot_a == pairs.uniprot_b).sum()),
        "n_self_pocket_pairs": int(pairs.is_self.sum()),
        "n_duplicate_unordered_pocket_pairs": int(key.duplicated().sum()),
        "n_structures_in_mirror": int(pockets.drop_duplicates("pdb_id").in_pdb_mirror.sum()),
        "n_pockets_het_absent_in_mirror": int((pockets.n_het_instances_in_mirror == 0).sum()),
        "n_pockets_site_index_gt_het_instances": int((pockets.site_index > pockets.n_het_instances_in_mirror.fillna(1e9)).sum()),
        **{f"paper_{k}": v for k, v in PAPER_COUNTS.items()},
    }


if __name__ == "__main__":
    p, k = build()
    for kk, v in counts(p, k).items():
        print(f"{kk:40s} {v}")
