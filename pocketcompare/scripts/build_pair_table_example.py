#!/usr/bin/env python
"""Write a tiny example of the two inputs of ``scripts/train_head.py`` from the example structures.

    python scripts/build_pair_table_example.py --out examples/out/train_demo
    python scripts/train_head.py --pockets examples/out/train_demo/pockets.parquet \\
        --pairs examples/out/train_demo/pairs.tsv --out examples/out/train_demo/head --holdout 0 --max-epochs 3

It only demonstrates the file formats: a handful of pairs is not training data.  Contents:
* ``pockets.parquet`` -- every pocket of the three example structures (``describe_all``) plus the progesterone site
  of 1A28 described twice: as its ligand shell (``1a28_A:site_L``) and as the BURROW pocket at the ligand
  (``1a28_A:site_D``), with the raw N1 descriptor (column ``n1``), as written by ``pocketcompare describe --n1``;
* ``pairs.tsv`` -- columns pocket_a, pocket_b, label, group_a, group_b, source:
  - ``ld``: the ligand-shell and BURROW-pocket descriptions of the same site (positive);
  - ``ligand``: the 1A28 site vs the steroid pocket of the receptor's AlphaFold model (positive: same ligand),
    vs the other pockets of both AlphaFold models (negatives, as an illustration only: unlabelled pockets are not
    known non-binders).
  Groups: the progesterone receptor entries share group ``PR`` (1A28 is its crystal structure); carbonic
  anhydrase is ``CA2``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

EX = Path(__file__).resolve().parents[1] / "examples"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(EX / "out/train_demo"))
    a = ap.parse_args(argv)
    from pocketcompare import fpindex as FX
    from pocketcompare import method
    M = method.default()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, V, N = [], [], []
    for f, af, grp in (("pdb/1a28_A.pdb", False, "PR"), ("afdb/AF-P06401-F1-model_v6.cif.gz", True, "PR"),
                       ("afdb/AF-P00918-F1-model_v6.cif.gz", True, "CA2")):
        E, info, R = M.describe_all(EX / f, af_mode=af, return_n1=True)
        stem = Path(f).name.split(".")[0]
        info.insert(0, "pocket_id", [f"{stem}:m{k}" for k in info.merged_index])
        info["group"] = grp
        rows.append(info[["pocket_id", "group", "burrow_rank", "residues"]])
        V.append(E)
        N.append(R)
    for loc, tag in (("shell", "L"), ("burrow", "D")):
        E, info, R = M.describe(EX / "pdb/1a28_A.pdb", site=str(EX / "pdb/1a28_STR.pdb"), locate=loc,
                                return_info=True, return_n1=True)
        rows.append(pd.DataFrame({"pocket_id": [f"1a28_A:site_{tag}"], "group": ["PR"],
                                  "burrow_rank": [info.get("burrow_rank", pd.Series([-1]))[0]],
                                  "residues": [""]}))
        V.append(E)
        N.append(R)
    meta = pd.concat(rows, ignore_index=True)
    V, N = np.vstack(V), np.vstack(N)
    FX.write_table(out / "pockets.parquet", meta, V, FX.method_record(M), n1=N)

    grp = dict(zip(meta.pocket_id, meta.group))
    q = "1a28_A:site_L"
    s = V[meta.pocket_id.tolist().index(q)] @ V.T
    af = meta.pocket_id.str.startswith("AF-").to_numpy()
    pr = meta.pocket_id.str.startswith("AF-P06401").to_numpy()
    hit = meta.pocket_id[pr].iloc[int(np.argmax(s[pr]))]          # the receptor model's steroid pocket
    pairs = [("1a28_A:site_L", "1a28_A:site_D", 1, "ld"), (q, hit, 1, "ligand"), ("1a28_A:site_D", hit, 1, "ligand")]
    pairs += [(q, p, 0, "ligand") for p in meta.pocket_id[af] if p != hit]
    df = pd.DataFrame(pairs, columns=["pocket_a", "pocket_b", "label", "source"])
    df["group_a"], df["group_b"] = df.pocket_a.map(grp), df.pocket_b.map(grp)
    df = df[["pocket_a", "pocket_b", "label", "group_a", "group_b", "source"]]
    df.to_csv(out / "pairs.tsv", sep="\t", index=False)
    print(df.to_string(index=False))
    print(f"-> {out}/pockets.parquet ({len(meta)} pockets), {out}/pairs.tsv ({len(df)} pairs)")


if __name__ == "__main__":
    main()
