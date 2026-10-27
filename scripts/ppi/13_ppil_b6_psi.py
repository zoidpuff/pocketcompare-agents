#!/usr/bin/env python
"""PPI-L step 4: baseline B6 (PSI, Moine-Franel et al. 2024) for every PPI-L pair.  Runs only after the C3 gate
has been recorded (results/ppi/ppil_gate.json from 12_).

Why recomputed and not extracted: the pocketome's precomputed PSI distances exist only through the iPPI-DB REST
endpoint /api/distance/ (1,813,044 records, each embedding both full cavity objects; no server-side filter by
cavity; ~78 nearest neighbours per cavity, i.e. a kNN list, not a matrix -> it cannot cover our negative pairs).
PSI = Euclidean distance between cavities on the 108 VolSite/shape descriptors of the pocketome CSVs, each
z-scored over all distinct cavities (HD + PL).  Check against 300 API records
(data/raw/ppi_pocketome/api/distance_sample.json): Pearson r = 0.959, median ratio 0.999 (not exact: the
authors' standardisation population is not documented) -> reported as "B6 (PSI, re-implemented)".
Pocket-level score = -min distance over the pocket's cavity pairs (a ligand may span several VolSite cavities).
Writes data/processed/ppi/ppil/b6_psi_{train,val}.parquet and data/sealed/ppi_l_test_b6.parquet (chmod 000),
results/ppi/ppil_b6_check.json.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PPIL = ROOT / "data/processed/ppi/ppil"
SEALED = ROOT / "data/sealed"
META = {"Cavity", "kind", "label", "pocket_id", "pdb", "chain", "uniprot", "base"}


def main() -> None:
    if not (ROOT / "results/ppi/ppil_gate.json").exists():
        raise SystemExit("C3 gate not recorded yet (run 12_ppil_split_pairs.py first)")
    C = pd.read_parquet(PPIL / "cavities.parquet")
    C["base"] = C.Cavity.str.replace(r"_(orthosteric|nonorthosteric|liganded_.*)$", "", regex=True)
    desc = [c for c in C.columns if c not in META]
    U = C.drop_duplicates("base").set_index("base")[desc].astype(float)
    Z = ((U - U.mean()) / U.std().replace(0, 1)).fillna(0)
    s = json.load(open(ROOT / "data/raw/ppi_pocketome/api/distance_sample.json"))
    calc = np.array([np.linalg.norm(Z.loc[a].values - Z.loc[b].values) for a, b, _ in s])
    ref = np.array([d for _, _, d in s])
    chk = {"n": len(s), "pearson_r": float(np.corrcoef(calc, ref)[0, 1]), "median_ratio": float(np.median(calc / ref))}
    (ROOT / "results/ppi/ppil_b6_check.json").write_text(json.dumps(chk, indent=1))
    print("[b6] check vs API", chk, flush=True)
    L = pd.read_parquet(PPIL / "ligand_instances.parquet", columns=["pocket_id", "cavities"])
    rows = {r.pocket_id: [Z.index.get_loc(c) for c in
                          pd.Series(r.cavities.split(";")).str.replace(r"_(liganded_.*)$", "", regex=True)]
            for r in L.itertuples()}
    Zv = Z.values

    def score(df: pd.DataFrame) -> pd.DataFrame:
        out = np.empty(len(df))
        for k, (a, b) in enumerate(zip(df.pocket_a, df.pocket_b)):
            A, B = Zv[rows[a]], Zv[rows[b]]
            out[k] = -np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)).min()
        return pd.DataFrame({"pocket_a": df.pocket_a.values, "pocket_b": df.pocket_b.values, "b6_psi": out})
    for s_ in ("train", "val"):
        p = pd.read_parquet(ROOT / f"data/splits/ppi_l_pairs_{s_}.parquet", columns=["pocket_a", "pocket_b"])
        score(p).to_parquet(PPIL / f"b6_psi_{s_}.parquet", index=False)
    # test: read the sealed pair ids only to score them; scores go back into data/sealed (no labels read)
    mode = SEALED.stat().st_mode & 0o7777
    f = SEALED / "ppi_l_test_pairs.parquet"
    os.chmod(SEALED, mode | 0o700)
    try:
        os.chmod(f, 0o400)
        p = pd.read_parquet(f, columns=["pocket_a", "pocket_b"])
        os.chmod(f, 0o000)
        o = SEALED / "ppi_l_test_b6.parquet"
        if o.exists():
            os.chmod(o, 0o600)
        score(p).to_parquet(o, index=False)
        print(f"[sealed] ppi_l_test_b6.parquet sha256 {hashlib.sha256(o.read_bytes()).hexdigest()}", flush=True)
        os.chmod(o, 0o000)
    finally:
        os.chmod(SEALED, mode)


if __name__ == "__main__":
    main()
