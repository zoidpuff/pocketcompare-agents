#!/usr/bin/env bash
# Rebuild the homology graph and every split, verify, and write data/splits/SHA256SUMS.txt.
# Run detached:  nohup bash scripts/data/run_splits.sh > logs/run_splits.log 2>&1 &
# Steps (order matters): pocket table fix -> homology graph -> TOUGH-M1 split -> BLiPS -> verify -> checksums.
set -euo pipefail
cd "$(dirname "$0")/../.."
source .venv/bin/activate
THREADS=${THREADS:-24}
python -m pocketcompare.datasets.tough_m1                       # pocket table only (labels stay sealed)
python scripts/data/build_homology_graph.py --threads "$THREADS" --work "${WORK:-/tmp/gm_splits/homology}"
python scripts/data/make_tough_m1_split.py                      # only reader of the sealed TOUGH-M1 pairs/scores
python scripts/data/make_blips_split.py
python scripts/data/verify_splits.py
python scripts/data/split_sensitivity.py
python scripts/data/write_split_sums.py
python scripts/data/verify_splits.py   # re-run: now also checks SHA256SUMS.txt
touch logs/run_splits.done
