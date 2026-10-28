#!/usr/bin/env bash
# pocketcompare over the AlphaFold DB: one array task = one node = one worker.py (4 GPU shards x 15 workers).
# Submit with `bash afdb/submit.sh` (checks the environment and the work list, sets --output under $OUT_ROOT and
# passes --tiers). Resubmitting resumes: finished units have done markers, claims of dead jobs are reclaimed.
#SBATCH --job-name=pocketcompare-afdb
#SBATCH --array=0-3
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --mem-per-cpu=3G
#SBATCH --time=7-00:00:00
#SBATCH --partition=es_biol
#SBATCH --account=es_biol
#SBATCH --gpus=rtx_4090:4
#SBATCH --tmp=200G
#SBATCH --signal=B:USR1@900
#SBATCH --output=/cluster/scratch/gmagnusson/pocketcompare_afdb/logs/%x_%A_%a.out
set -uo pipefail

AFDB_DIR="${AFDB_DIR:-/cluster/project/beltrao/gmagnus/pocket_compare/release/pocketcompare/afdb}"
source "$AFDB_DIR/config.sh"
source "$ENV_DIR/bin/activate"
# Euler compute nodes reach the internet (GCS, tier 3) only through the ETH proxy
if [[ -z "${https_proxy:-}" ]] && command -v module >/dev/null 2>&1; then module load eth_proxy 2>/dev/null || true; fi

export TMPDIR="${TMPDIR:-/tmp}"
export NUMBA_CACHE_DIR="$TMPDIR/numba_cache" TRITON_CACHE_DIR="$TMPDIR/triton_cache"
mkdir -p "$NUMBA_CACHE_DIR" "$TRITON_CACHE_DIR" "$OUT_ROOT/logs"
cp -r "$ENV_DIR/numba_cache/." "$NUMBA_CACHE_DIR/" 2>/dev/null || true      # warm cache from setup_env.sh
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

echo "[afdb.sbatch] job ${SLURM_ARRAY_JOB_ID:-?}_${SLURM_ARRAY_TASK_ID:-?} (${SLURM_JOB_ID:-?}) on $(hostname) $(date)"
echo "[afdb.sbatch] OUT_ROOT=$OUT_ROOT ENV_DIR=$ENV_DIR TMPDIR=$TMPDIR ($(df -h "$TMPDIR" | awk 'NR==2{print $4}') free)"
echo "[afdb.sbatch] GPUs: ${CUDA_VISIBLE_DEVICES:-none}; worker args: ${WORKER_ARGS:-}"
nvidia-smi -L || true

# stagger the array tasks a little so they do not all list/claim at the same instant
sleep $(( ${SLURM_ARRAY_TASK_ID:-0} * 5 ))
python "$AFDB_DIR/worker.py" ${WORKER_ARGS:-} &
pid=$!
trap 'echo "[afdb.sbatch] USR1 (time limit near): worker stops claiming"; kill -USR1 $pid' USR1
trap 'echo "[afdb.sbatch] TERM: worker releases its claims"; kill -TERM $pid' TERM
rc=0
while true; do                      # `wait` returns early when a trapped signal arrives: wait again
    wait $pid; rc=$?
    kill -0 $pid 2>/dev/null || break
done
echo "[afdb.sbatch] worker exited with $rc at $(date)"
rm -rf "$NUMBA_CACHE_DIR" "$TRITON_CACHE_DIR"
exit $rc
