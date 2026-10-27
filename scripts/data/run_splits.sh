#!/usr/bin/env bash
# Rebuild the homology graph and every split in dependency order, verify, and write data/splits/SHA256SUMS.txt.
# Run detached:  nohup bash scripts/data/run_splits.sh > logs/run_splits.log 2>&1 &
# ~1.5 h on 24 threads (exhaustive Foldseek dominates). Point caches / descriptors are read, never written.
set -euo pipefail
cd "$(dirname "$0")/../.."
source .venv/bin/activate
THREADS=${THREADS:-24}
WORK=${WORK:-/tmp/gm_splits/homology}
python -m pocketcompare.datasets.tough_m1                        # pocket table only (labels stay sealed)
python scripts/data/build_homology_graph.py --threads "$THREADS" --work "$WORK"
python scripts/data/make_tough_m1_split.py                       # only reader of the sealed TOUGH-M1 pairs/scores
python scripts/data/make_blips_split.py                          # BLiPS v1 (+ sealed BLiPS-test pairs)
python scripts/data/blips_test_exclusions.py                     # < 10 BURROW points on BLiPS-test (ids only)
python scripts/data/make_blips_resplit_v2.py                     # D9 re-split of pooled v1 train+val
python scripts/ppi/21_ppips_homology.py --threads "$THREADS"     # PPIPS own groups (delete its foldseek.tsv to redo)
python scripts/ppi/22_ppips_build.py --workers 16                # PPIPS splits (+ sealed PPIPS test files)
python scripts/data/ppips_burrow_flags.py --threads "$THREADS" --work "$WORK"
python scripts/data/verify_splits.py
python scripts/data/split_sensitivity.py
python scripts/data/compare_split_versions.py HEAD
python scripts/data/write_split_sums.py
python scripts/data/verify_splits.py                             # re-run: now also checks SHA256SUMS.txt
touch logs/run_splits.done
