#!/usr/bin/env bash
# pocketcompare over the AlphaFold DB on CPU-only nodes: one array task = one node = one worker.py with
# CPU_SHARDS_PER_NODE CPU shards x WORKERS_PER_SHARD workers (Numba backend; same pockets and fingerprints as the
# GPU path). Runs alongside the GPU array on the same work list: units are shared through OUT_ROOT/state/claims.
# Submit with `bash afdb/submit.sh --cpu-nodes N` (sets --array, --output and WORKER_ARGS).
#SBATCH --job-name=pocketcompare-afdb-cpu
#SBATCH --array=0-3
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --mem-per-cpu=3G
#SBATCH --time=3-00:00:00
#SBATCH --account=es_biol
#SBATCH --tmp=200G
#SBATCH --signal=B:USR1@900
#SBATCH --output=/cluster/scratch/gmagnusson/pocketcompare_afdb/logs/%x_%A_%a.out

# the rest (environment, signal forwarding to the worker) is afdb.sbatch; exec keeps this shell's pid, so the
# USR1 / TERM that SLURM sends to the batch shell reach afdb.sbatch's traps
AFDB_DIR="${AFDB_DIR:-/cluster/project/beltrao/gmagnus/pocket_compare/release/pocketcompare/afdb}"
exec bash "$AFDB_DIR/afdb.sbatch"
