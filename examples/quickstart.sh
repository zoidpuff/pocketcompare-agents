#!/usr/bin/env bash
# pocketcompare quickstart, command line.  Usage: bash examples/quickstart.sh [output directory]
# Needs `pip install pocketcompare[search]` (FAISS) for steps 5-6.  Runtime: ~1 min on one CPU core (the first
# call also compiles BURROW's Numba kernels, ~15 s, cached afterwards).
set -euo pipefail
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$EX/out}"
mkdir -p "$OUT"

echo "== 1. Describe a ligand-defined site: progesterone in the crystal structure 1A28 (chain A)"
pocketcompare describe "$EX/pdb/1a28_A.pdb" --ligand "$EX/pdb/1a28_STR.pdb" -o "$OUT/site.parquet"

echo "== 2. Describe all pockets of an AlphaFold model (progesterone receptor, AF mode = pLDDT-aware BURROW)"
pocketcompare describe "$EX/afdb/AF-P06401-F1-model_v6.cif.gz" --af-mode -o "$OUT/pr_af.parquet"

echo "== 3. Compare: which pocket of the AlphaFold model is most similar to the crystal-structure site?"
pocketcompare compare "$OUT/site.parquet" "$OUT/pr_af.parquet" --top 3 -o "$OUT/site_vs_pr_af.tsv"

echo "== 4. Describe every AlphaFold model in a folder (here: 2 models; use --workers N / --device cuda:0 for more)"
pocketcompare describe "$EX/afdb" --af-mode -o "$OUT/afdb.parquet"

echo "== 5. Build an exact FAISS index over the folder's pockets"
pocketcompare index "$OUT/afdb.parquet" -o "$OUT/afdb_index"

echo "== 6. Search the index with the crystal-structure site"
pocketcompare search "$OUT/site.parquet" "$OUT/afdb_index" -k 5 -o "$OUT/hits.tsv"

echo "outputs in $OUT"
