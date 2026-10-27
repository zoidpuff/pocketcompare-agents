#!/usr/bin/env python
"""Full-proteome output equality across backends (run_gpu vs run_fastcpu vs run_refcpu): per-pocket tables and raw
descriptors, ordered by (stem, merged_rank).  Output: results/proteome/backend_equivalence.json."""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data/processed/proteome_human"
COLS = ["stem", "merged_rank", "burrow_rank", "members", "score", "n_points", "volume_A3", "site_n_points", "cx", "cy",
        "cz", "residues", "plddt_mean"]


def load(run):
    ps, a1, env, st = [], [], [], []
    for f in sorted(glob.glob(str(P / run / "shards/*.pockets.parquet"))):
        b = f[:-len(".pockets.parquet")]
        ps.append(pd.read_parquet(f))
        z = np.load(b + ".desc.npz")
        a1.append(z["a1"])
        env.append(z["env"])
        st.append(pd.read_parquet(b + ".structs.parquet"))
    p = pd.concat(ps, ignore_index=True)
    o = np.lexsort((p.merged_rank.to_numpy(), p.stem.to_numpy()))
    return (p.iloc[o].reset_index(drop=True), np.concatenate(a1)[o], np.concatenate(env)[o],
            pd.concat(st, ignore_index=True))


def main():
    ref = load("run_gpu")
    out = {"n_pockets_gpu": len(ref[0])}
    for run in ("run_fastcpu", "run_refcpu"):
        if not (P / run / "DONE").exists():
            continue
        o = load(run)
        same_tab = len(o[0]) == len(ref[0]) and o[0][COLS].equals(ref[0][COLS])
        out[run] = dict(n_pockets=len(o[0]), table_identical=bool(same_tab),
                        a1_identical=bool(same_tab and np.array_equal(o[1], ref[1])),
                        env_identical=bool(same_tab and np.array_equal(o[2], ref[2])),
                        n_struct_errors=int((o[3].status != "ok").sum()),
                        errors=o[3][o[3].status != "ok"].error.str[:60].value_counts().to_dict())
        if (o[3].status != "ok").any():
            g = ref[3].set_index("stem")
            bad = o[3].stem[o[3].status != "ok"]
            out[run]["gpu_n_kept_of_error_structures"] = int(g.loc[bad, "n_kept"].sum())
            out[run]["gpu_n_atoms_of_error_structures_max"] = int(g.loc[bad, "n_atoms"].max())
    (ROOT / "results/proteome/backend_equivalence.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
