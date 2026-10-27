#!/usr/bin/env python
"""Sensitivity of the split sizes to the structural edge threshold (no labels read; counts only).

For edge rule = BURROW MMseqs2 rule OR Foldseek min(qTM, tTM) >= t (t in 0.5 [adopted], 0.6, 0.7, 0.8, none):
  TOUGH-M1: pockets per partition (dev / test / excluded) and largest TOUGH-M1 component;
  BLiPS:    BURROW train/dev proteins removed for direct edges to the sealed test sets (TOUGH-M1-test taken from the
            adopted split, ProSPECCTs, Vertex, af_set, PPI-L-test); largest BLiPS-test component.
Writes data/splits/split_sensitivity.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.splitutil import SPLITS, SidGraph, load_homology  # noqa: E402


def main():
    n, e = load_homology()
    t = n[n.dataset == "tough_m1"]
    burrow = n[n.dataset.isin(["burrow_train", "burrow_dev", "burrow_partner"])].sid
    ppi_test = n[(n.dataset == "ppi_l") & n.ppi_split.fillna("").str.contains("test")].sid
    sealed = pd.concat([n[n.dataset.isin(["prospeccts", "vertex", "af_set"])].sid, ppi_test])
    tm_test = pd.read_parquet(SPLITS / "tough_m1_pockets_split.parquet").query("partition == 'test'").sid
    tv = n[n.dataset.isin(["burrow_train", "burrow_dev"])]
    test_targets = pd.concat([tm_test, n[n.dataset.isin(["prospeccts", "vertex", "af_set"])].sid, ppi_test])
    af = n[(n.dataset == "af_set") & (n.af_status == "included")]
    out = {}
    for thr in (0.5, 0.6, 0.7, 0.8, None):
        m = e.seq_edge.to_numpy() | ((e.tm_min.fillna(0).to_numpy() >= thr) if thr else False)
        g = SidGraph(n, e[m])
        tt = t.assign(grp=t.sid.map(g.components(t.sid)), b=g.touches(t.sid, burrow).values,
                      s=g.touches(t.sid, sealed).values)
        gr = tt.groupby("grp")[["b", "s"]].any()
        part = tt.grp.map(pd.Series(np.where(gr.b & gr.s, "excluded", np.where(gr.b, "dev", "test")), index=gr.index))
        rem = g.touches(tv.sid, test_targets)
        afc = af.sid.map(g.components(af.sid)).value_counts()
        out[f"seq_or_tm>={thr}" if thr else "seq_only"] = dict(
            tough_m1=part.value_counts().to_dict(), tough_m1_largest_component=int(tt.grp.value_counts().iloc[0]),
            burrow_trainval_proteins=int(len(tv)), burrow_trainval_removed=int(rem.sum()),
            af_set_largest_component_frac=round(float(afc.iloc[0] / len(af)), 4))
        print(thr, out[list(out)[-1]])
    (SPLITS / "split_sensitivity.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
