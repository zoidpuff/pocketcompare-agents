#!/usr/bin/env bash
# L4 full pipeline AFTER the PI's go ("splits final + audit passed"): re-extract points (splits may have changed
# site membership; extraction is label-free and ~1 min), train the 6 pre-declared configs x SEEDS[:3] on cuda:2/3,
# benchmark inference, run the PREREG §1 dev evaluation.  Detached usage (LESSONS 10):
#   nohup bash scripts/run_l4.sh > logs/l4_run.log 2>&1 & echo $! > logs/l4_run.pid
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export NUMBA_CACHE_DIR=/tmp/numba_cache
: "${L4_AUDIT_PASSED:?set L4_AUDIT_PASSED=1 only after the PI's go}"
python scripts/l4_extract.py --dataset all --workers 16
python scripts/train_l4.py --all --devices cuda:2,cuda:3
python scripts/bench_l4.py --models results/models/l4 --device cuda:2
python scripts/eval_l4.py --threads 16
touch logs/l4_run.done
