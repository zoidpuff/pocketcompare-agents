#!/usr/bin/env bash
# Fetch the tier-3 inputs (Foldcomp afdb_uniprot_v4 1.1 TB, UniProt idmapping + 2021_04 taxids, NCBI taxdump) into
# $FOLDCOMP_DIR. CPU only. Measured from Euler: ~190 MB/s with 16 ranged streams, so the database takes ~2 h,
# the 2021_04 taxids ~15 min of download + ~1-2 h of parsing. Resumable: resubmit after a failure or time-out.
#   sbatch afdb/fetch_foldcomp.sbatch                         # default databases
#   FETCH_ARGS="--dbs afdb_uniprot_v4 afdb_rep_v4" sbatch afdb/fetch_foldcomp.sbatch   # + representatives (TIER_REPS)
#SBATCH --job-name=pocketcompare-fetch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=4G
#SBATCH --time=24:00:00
#SBATCH --account=es_biol
#SBATCH --tmp=20G
#SBATCH --output=/cluster/scratch/gmagnusson/pocketcompare_afdb/logs/%x_%j.out
set -uo pipefail
AFDB_DIR="${AFDB_DIR:-/cluster/project/beltrao/gmagnus/pocket_compare/release/pocketcompare/afdb}"
source "$AFDB_DIR/config.sh"
if [[ -z "${https_proxy:-}" ]] && command -v module >/dev/null 2>&1; then module load eth_proxy 2>/dev/null || true; fi
mkdir -p "$FOLDCOMP_DIR" "$OUT_ROOT/logs"
# scratch is Lustre: stripe the 1.1 TB database over several storage targets (new files only; ignored elsewhere)
command -v lfs >/dev/null 2>&1 && lfs setstripe -c 8 "$FOLDCOMP_DIR" 2>/dev/null && lfs getstripe -d "$FOLDCOMP_DIR"
echo "[fetch_foldcomp.sbatch] $(hostname) $(date); FOLDCOMP_DIR=$FOLDCOMP_DIR; free: $(df -h "$FOLDCOMP_DIR" | awk 'NR==2{print $4}')"
"$ENV_DIR/bin/python" "$AFDB_DIR/fetch_foldcomp.py" ${FETCH_ARGS:-}
rc=$?
ls -la "$FOLDCOMP_DIR"
echo "[fetch_foldcomp.sbatch] exit $rc at $(date)"
exit $rc
