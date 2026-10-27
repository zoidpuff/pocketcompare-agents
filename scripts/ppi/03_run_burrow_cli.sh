#!/usr/bin/env bash
# Run the BURROW CLI (AF mode, default preset) on the dimer sample and its monomers, and time it (task 2).
# Configs: {dimers, monomers} x {v2 output floor (default), --min-score none (full list)} on 16 CPU workers,
# plus dimers/default on one GPU (cuda:3, 8 workers) for a GPU timing. One warm-up run first (Numba compile).
# Outputs: data/processed/dimers/sample/cli/<config>/ (CSV + points) and .../cli/timing.tsv
# Usage: bash scripts/ppi/03_run_burrow_cli.sh   (after 02_sample.py)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
source "$ROOT/.venv/bin/activate"
export NUMBA_CACHE_DIR=/tmp/numba_cache
S="$ROOT/data/processed/dimers/sample"
C="$S/cli"
mkdir -p "$C"
W=16
# warm-up (compile caches), not timed
python -m pocketdetect.burrow predict "$(head -1 "$S/inputs/dimers.list")" --out /tmp/ppi_warm --af-mode >/dev/null 2>&1 || true
echo -e "config\tn_inputs\twall_s\tdevice\tworkers" > "$C/timing.tsv"
run () {  # name list device extra...
  local name=$1 list=$2 dev=$3; shift 3
  rm -rf "$C/$name"
  local n; n=$(wc -l < "$list")
  local t0; t0=$(date +%s.%N)
  python -m pocketdetect.burrow predict "@$list" --out "$C/$name" --af-mode --workers "$W" --device "$dev" "$@" \
    > "$C/$name.log" 2>&1
  local t1; t1=$(date +%s.%N)
  echo -e "$name\t$n\t$(python -c "print(round($t1 - $t0, 2))")\t$dev\t$W" | tee -a "$C/timing.tsv"
}
run dimer_default "$S/inputs/dimers.list" cpu
run dimer_full "$S/inputs/dimers.list" cpu --min-score none
run mono_default "$S/inputs/monomers.list" cpu
run mono_full "$S/inputs/monomers.list" cpu --min-score none
W=8 run dimer_default_gpu "$S/inputs/dimers.list" cuda:3
echo done > "$C/DONE"
