#!/usr/bin/env bash
# PPI datasets (reports/ppi_datasets.md): PPI-L from the Pasteur PPI pocketome, PPIPS (P-sym, P-ortho) from the
# AFDB dimers. Re-runnable; every step skips work whose outputs exist. 16 CPU workers, no GPU. ~25 min + download.
#   fetch  scripts/data/fetch_ppi_pocketome.py   11 GB archive (Zenodo, md5-checked), selective extraction  ~15 min
#   10     PPI-L inventory: labels, ligand instances, SMILES/ECFP4, Butina chemotypes                       ~1 min
#   11     PPI-L pocket table + BURROW point cache (L-mode on the HET modulator, PDB mirror, ligand chain)  ~2 min
#   12     PPI-L homology (MMseqs2 + Foldseek), group split, pairs, C3 gate (counts only), sealed test pairs ~10 min
#   13     B6 (PSI re-implemented on the 108 pocketome descriptors) after the gate                         ~2 min
#   20     PPIPS: BURROW AF mode on the 1,991 dimers of cross-species interolog pairs (< 30 % identity)   ~3 min
#   21     PPIPS chain alignments (MMseqs2 with alignments) + Foldseek, protein homology groups            ~10 min
#   22     PPIPS pockets, P-sym pairs, P-ortho queries, splits, sealed test files                          ~2 min
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
source .venv/bin/activate
export NUMBA_CACHE_DIR=/tmp/numba_cache
python -I scripts/data/fetch_ppi_pocketome.py
python scripts/ppi/10_ppil_inventory.py
python scripts/ppi/11_ppil_pockets.py --workers 14
python scripts/ppi/12_ppil_split_pairs.py --threads 16
python scripts/ppi/13_ppil_b6_psi.py
python scripts/ppi/20_ppips_featurize.py --workers 14
python scripts/ppi/21_ppips_homology.py --threads 16
python scripts/ppi/22_ppips_build.py --workers 16
