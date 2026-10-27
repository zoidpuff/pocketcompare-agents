#!/usr/bin/env bash
# PPI / AFDB-dimer pocket characterisation (reports/ppi_dimers.md). Run from anywhere; ~10 min total.
# Resources: 16 CPU workers, one GPU (cuda:3) for one timing run. Outputs under data/processed/dimers/ (git-ignored),
# numbers in results/ppi/summary.txt and data/processed/dimers/{inventory_summary.txt,orthology/summary.txt,ippidb/summary.txt}.
#   01 inventory of all 15,161 dimer files (manifests, chains, pLDDT, interface size, sequences)      ~1 min
#   02 stratified sample: 100 per organism x type (seed SEEDS[0]); monomer chains cut from the dimer files
#   03 BURROW CLI timing runs (AF mode, default preset; v2 floor and --min-score none; dimers and monomers)
#   04 full pocket lists with descriptors + point clouds (reference export; identical pockets, checked in 05)
#   05 analysis: interface classification, monomer comparison with control, homodimer symmetry
#   06 MMseqs2 interologs across human/yeast/E. coli (benchmark feasibility)
#   07 iPPI-DB cavity summary via REST API (benchmark feasibility; network; server rate-limits)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
source .venv/bin/activate
export NUMBA_CACHE_DIR=/tmp/numba_cache
python scripts/ppi/01_inventory.py --workers 16
python scripts/ppi/02_sample.py --n-per 100
bash scripts/ppi/03_run_burrow_cli.sh
python scripts/ppi/04_export_descriptors.py --workers 16
python scripts/ppi/05_analyze.py
python scripts/ppi/06_orthology_feasibility.py --threads 16
python scripts/ppi/07_ippidb_feasibility.py || echo "iPPI-DB fetch failed (server availability); rerun later"
