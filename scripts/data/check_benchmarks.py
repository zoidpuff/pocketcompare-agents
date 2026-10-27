#!/usr/bin/env python
"""Summarise processed benchmark tables: counts vs paper, PDB-mirror coverage,
cross-benchmark PDB-ID overlap. Writes results/benchmarks/benchmark_counts.json.
Usage: python scripts/data/check_benchmarks.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import pandas as pd  # noqa: E402

from pocketcompare.datasets import klifs, prospeccts, tough_c1, tough_m1, vertex  # noqa: E402
from pocketcompare.datasets.common import PDB_MIRROR, PROJECT_ROOT, RAW_DIR, du  # noqa: E402

out = {}
pp, pk = prospeccts.load()
out["prospeccts"] = prospeccts.counts(pp, pk).to_dict(orient="records")
tp, tk = tough_m1.load()
out["tough_m1"] = tough_m1.counts(tp, tk)
out["tough_m1"]["pocket_mcc_lt_0.5"] = int((tk.pocket_mcc < 0.5).sum())
out["tough_m1"]["pocket_mcc_median"] = float(tk.pocket_mcc.median())
vp, vk = vertex.load()
out["vertex"] = vertex.counts(vp, vk)
ck = tough_c1.load()
out["tough_c1"] = ck.groupby("subset").size().to_dict()
kk = klifs.load()
out["klifs"] = {"n_structures": len(kk), "n_pdb": int(kk.pdb_id.nunique()), "n_kinases": int(kk.kinase_ID.nunique())}

# PDB mirror coverage: which middle-2-char dirs are empty?
empty = sorted(d.name for d in PDB_MIRROR.iterdir() if d.is_dir() and not any(d.iterdir()))
out["pdb_mirror_empty_dirs"] = empty
ids = {
    "prospeccts": set(pk.loc[~pk.is_decoy & pk.pdb_id.notna(), "pdb_id"]),
    "tough_m1": set(tk.pdb_id), "vertex": set(vk.pdb_id), "tough_c1": set(ck.pdb_id),
    "klifs": set(kk.pdb_id),
}
cov = {}
for name, s in ids.items():
    miss = {i for i in s if not (PDB_MIRROR / i[1:3] / f"{i}.cif.gz").exists()}
    in_empty = {i for i in miss if i[1:3] in empty}
    cov[name] = {"n_pdb_ids": len(s), "missing": len(miss), "missing_in_empty_dirs": len(in_empty),
                 "missing_other": sorted(miss - in_empty)}
out["pdb_mirror_coverage"] = cov
names = list(ids)
out["pdb_overlap"] = {f"{a}&{b}": len(ids[a] & ids[b]) for i, a in enumerate(names) for b in names[i + 1:]}
out["disk_bytes"] = {d.name: du(d) for d in sorted(RAW_DIR.iterdir()) if d.is_dir()}
out["disk_bytes"]["processed"] = du(PROJECT_ROOT / "data" / "processed")
dest = PROJECT_ROOT / "results" / "benchmarks" / "benchmark_counts.json"
dest.write_text(json.dumps(out, indent=1, default=str))
pd.set_option("display.width", 200)
print(pd.DataFrame(out["prospeccts"]).to_string(index=False))
for k in ("tough_m1", "vertex", "tough_c1", "klifs", "pdb_overlap", "disk_bytes"):
    print(k, json.dumps(out[k], default=str))
for k, v in cov.items():
    print(k, {kk: (vv if kk != "missing_other" else (len(vv), vv[:15])) for kk, vv in v.items()})
