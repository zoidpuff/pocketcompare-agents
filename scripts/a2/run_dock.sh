#!/usr/bin/env bash
# A2: launch the TOUGH-M1 docking shards (4 processes on each of cuda:0 and cuda:2; <= 8 CPU workers).
# Env: A2_DATASET (tough_m1|ppips), A2_GPUS (8 space-separated physical GPU ids, one per shard).
# Usage: scripts/a2/run_dock.sh <out_subdir> <mode L|D> <seeds csv> [extra args...]
#   scripts/a2/run_dock.sh raw_repro_L L 0,1,2 --subset data/processed/docking/tough_m1/repro_subset.txt --save_poses
#   scripts/a2/run_dock.sh raw_L L 0
set -euo pipefail
PC=/cluster/project/beltrao/gmagnus/pocket_compare
cd "$PC"
source .venv/bin/activate
export NUMBA_CACHE_DIR=/tmp/numba_cache CUPY_CACHE_DIR=/tmp/adock/cupy_cache
export PYTHONPATH=/tmp/adock/overlay:/cluster/work/beltrao/buhmanju/agentic_ai/workspaces/hackathon/autoresearch_docking/src
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

OUTSUB=$1; MODE=$2; SEEDS=$3; shift 3
DATASET=${A2_DATASET:-tough_m1}
OUT="data/processed/docking/$DATASET/$OUTSUB"
mkdir -p "$OUT" logs
LOGTAG="${DATASET}_${OUTSUB}"; [ "$DATASET" = tough_m1 ] && LOGTAG="$OUTSUB"
rm -f "logs/a2_${LOGTAG}.done"
# ADock's cupy kernels run on cupy's *current* device, which is 0 regardless of the torch device string, so a
# process pinned to cuda:2 ends up with tensors on two GPUs (device-side assert). Pin with CUDA_VISIBLE_DEVICES
# and always address cuda:0 inside the process.
read -r -a GPUS <<< "${A2_GPUS:-0 2 0 2 0 2 0 2}"
PIDS=()
for s in 0 1 2 3 4 5 6 7; do
  CUDA_VISIBLE_DEVICES="${GPUS[$s]}" nohup python scripts/a2/dock_tough_m1.py --mode "$MODE" --device cuda:0 \
      --shard "$s" --nshards 8 \
      --seeds "$SEEDS" --out "$OUT" --threads 2 --geom_dir "data/processed/docking/$DATASET" "$@" > "logs/a2_${LOGTAG}_shard${s}.log" 2>&1 &
  PIDS+=($!)
done
printf "%s\n" "${PIDS[@]}" > "logs/a2_${LOGTAG}.pids"
echo "launched: ${PIDS[*]}"
wait
echo "done $(date -Is)" > "logs/a2_${LOGTAG}.done"
