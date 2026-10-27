#!/usr/bin/env python
"""Provenance sidecars (``pocketcompare.provenance.write_result``) for results/proteome/*.json.

The producing scripts wrote plain JSON; this re-writes each file with identical content plus ``<file>.prov.json``
(script = the producer, inputs = the data it read; ``extra.note`` says the sidecar was added afterwards), so that
reports/proteome_demo.md can be checked with scripts/check_report.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.provenance import write_result  # noqa: E402

R = ROOT / "results/proteome"
P = ROOT / "data/processed/proteome_human"
S = ROOT / "scripts/proteome"
IX = P / "index"
PRODUCERS = {
    "summary.json": ("summarize.py", [P / "members.json", P / "run_gpu/run.json", P / "run_fastcpu/run.json",
                                      P / "run_refcpu/run.json", R / "index_search.json", IX / "pockets.parquet"]),
    "index_search.json": ("index_search.py", [P / "zstats.npz", IX / "pockets.parquet", IX / "emb.npy",
                                              IX / "knn_exact_I.npy"]),
    "sanity_jitter.json": ("sanity_jitter.py", [IX / "emb.npy", IX / "pockets.parquet", IX / "sanity_jitter.parquet"]),
    "sanity_family.json": ("sanity_family.py", [IX / "pockets.parquet", IX / "knn_exact_I.npy",
                                                IX / "knn_csls_db_I.npy"]),
    "backend_equivalence.json": ("compare_backends.py", [P / "run_gpu/run.json", P / "run_fastcpu/run.json",
                                                         P / "run_refcpu/run.json"]),
    "fast_equivalence.json": ("check_fast_equivalence.py", []),
}


def main():
    for name, (script, inputs) in PRODUCERS.items():
        f = R / name
        if not f.exists():
            continue
        obj = json.loads(f.read_text())
        write_result(f, obj, script=S / script, args=[], config={"producer": script}, inputs=[p for p in inputs if p.exists()],
                     seed=0, device="see result", extra={"note": f"sidecar added afterwards by write_sidecars.py; "
                                                                 f"result produced by scripts/proteome/{script}"})
        print("sidecar", f)


if __name__ == "__main__":
    main()
