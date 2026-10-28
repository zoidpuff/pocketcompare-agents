#!/usr/bin/env bash
# One-command reproduction of pocket_compare.  See README.md "Reproduce" for the annotated step list.
#
#   bash scripts/reproduce_all.sh smoke            # < 5 min: tests, describe/compare demo, report check, freeze hashes
#   bash scripts/reproduce_all.sh all              # every stage below, in order (days; run detached, see LESSONS.md)
#   bash scripts/reproduce_all.sh <stage> [...]    # one or more stages
#   stages: env data splits caches descriptors dev train select final prereg2 proteome release
#
# Each stage logs to logs/reproduce_<stage>.log and writes logs/reproduce_<stage>.done on success; a stage with a
# .done marker is skipped (FORCE=1 to redo).  Individual scripts are themselves resumable where they say so.
# Env knobs: THREADS (default 8), A4B_DEVICES / L4_DEVICES (GPU ids, default cuda:0,cuda:1 / cuda:2,cuda:3),
#            L4_AUDIT_PASSED=1 (required for the L4 step: only after the PI's go).
# This script NEVER sets FINAL_EVAL=1 and never touches data/sealed/ itself; stages final and prereg2 only print
# instructions for the PI.  (Split/dataset scripts called in `data`/`splits` read sealed labels by design.)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
mkdir -p logs
THREADS=${THREADS:-8}
A4B_DEVICES=${A4B_DEVICES:-cuda:0,cuda:1}
L4_DEVICES=${L4_DEVICES:-cuda:2,cuda:3}
EX=${BURROW_EXAMPLES:-/cluster/project/beltrao/gmagnus/pocket_detect/release/burrow/examples}
unset FINAL_EVAL

activate() {
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/tmp/numba_cache}
  export OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS OPENBLAS_NUM_THREADS=$THREADS NUMBA_NUM_THREADS=$THREADS
}

run_stage() {  # run_stage <name>: skip if done, log, mark done
  local s=$1 log=logs/reproduce_$1.log done=logs/reproduce_$1.done
  if [[ -f $done && ${FORCE:-0} != 1 ]]; then echo "[$s] already done (FORCE=1 to redo)"; return 0; fi
  echo "[$s] start $(date +%T) -> $log"
  ( set -euo pipefail; activate; "stage_$s" ) > "$log" 2>&1 || { echo "[$s] FAILED, see $log"; return 1; }
  date -Is > "$done"; echo "[$s] ok"
}

stage_env() {
  [[ -d .venv ]] || python3 -m venv .venv
  activate
  python -c "import pocketcompare" 2>/dev/null || pip install -e '.[dev]' 2>/dev/null || pip install -e .
  python -c "import pocketcompare, numpy, faiss; print('pocketcompare ok')"
  ls tools/foldseek tools/mmseqs >/dev/null
  (cd tools && sha256sum -c SHA256SUMS) || echo "WARN: tools checksum mismatch"
}

stage_data() {
  for d in prospeccts tough_m1 vertex tough_c1 klifs; do python scripts/data/fetch_$d.py; done
  python scripts/data/build_benchmarks.py
  python scripts/data/check_benchmarks.py
  bash scripts/ppi/run_all.sh
  bash scripts/ppi/run_ppi_datasets.sh
  python scripts/data/prep_blips_pockets.py --part trainval
  python scripts/data/prep_blips_pockets.py --part test
}

stage_splits() {  # homology graph + all splits + verify (~1.5 h)
  THREADS=$THREADS bash scripts/data/run_splits.sh
  python scripts/data/verify_splits.py
}

stage_caches() {  # label-free BURROW point caches
  for ds in tough_m1 blips blips_test_holo blips_test_af; do
    python scripts/build_point_cache.py --dataset "$ds" --workers "$THREADS"
  done
  bash scripts/run_final_prep_cache.sh
}

stage_descriptors() {
  for arm in a1 b1; do
    python scripts/compute_descriptors.py --dataset tough_m1 --arm $arm --config all --mode both --workers "$THREADS"
  done
  python scripts/compute_descriptors.py --dataset tough_m1 --arm b0 --mode both --workers "$THREADS"
  bash scripts/run_blips_ppips_desc.sh
  python scripts/compute_esm.py --dataset tough_m1
  bash scripts/run_blips_ppips_esm.sh
  for ds in tough_m1 blips ppips; do python scripts/compute_n_inputs.py --dataset "$ds" --workers "$THREADS"; done
  bash scripts/run_final_prep_desc.sh
  bash envs/run_epocs_full.sh
  python scripts/collect_epocs.py
}

stage_dev() {
  for ds in tough_m1 blips ppips; do
    python scripts/eval_dev.py --dataset "$ds" --out-suffix _v2splits --trial-tag splits_v2
  done
}

stage_train() {  # A4b and L4 (GPU)
  python scripts/train_a4b.py --all --devices "$A4B_DEVICES"
  python scripts/eval_dev.py --dataset final_select --candidates all
  if [[ ${L4_AUDIT_PASSED:-0} == 1 ]]; then
    L4_AUDIT_PASSED=1 bash scripts/run_l4.sh
  else
    echo "SKIP L4: set L4_AUDIT_PASSED=1 (only after the PI's go) and rerun 'train' with FORCE=1"
  fi
}

stage_select() {
  python scripts/write_final_method.py --selection results/dev/final_select_pi.json
  python scripts/bench_method.py --n-structures 200
  python scripts/eval_af_robustness.py --set val
  python scripts/eval_blind.py --set val
}

stage_final() {
  cat <<'MSG'
FINAL EVALUATION is PI-only (sealed test labels).  Not run here.  As the PI, in order:
  python scripts/final_eval.py --dryrun-dev
  git commit ...; python scripts/final_eval.py --write-freeze; git commit FREEZE.json; git tag freeze-v1
  FINAL_EVAL=1 python scripts/final_eval.py --check-only
  FINAL_EVAL=1 python scripts/final_eval.py --threads 16
  (optional) FINAL_EVAL=1 python scripts/eval_af_robustness.py --set test --pairs <...>
             FINAL_EVAL=1 python scripts/eval_blind.py --set test --pairs <...>
MSG
}

stage_prereg2() {
  cat <<'MSG'
PREREG2 analyses are PI-only (sealed labels; FINAL_EVAL=1).  Not run here.
Follow PREREG2.md after the final evaluation has been committed; see REPORT.md and RESEARCH_TREE.md for status.
MSG
}

stage_proteome() {
  python scripts/proteome/index_tar.py
  bash scripts/proteome/run_stage1.sh
  bash scripts/proteome/run_cpu_backends.sh
  python scripts/proteome/index_search.py
  python scripts/proteome/sanity_jitter.py
  python scripts/proteome/sanity_family.py
  python scripts/proteome/summarize.py
  python scripts/proteome/write_sidecars.py
}

stage_release() {
  python -m pytest -q tests/test_method_eval_consistency.py tests/test_cli.py
  python scripts/tooling/bench_describe.py --n 2000 --workers "$THREADS" --device "${RELEASE_DEVICE:-cuda:0}"
  python scripts/proteome/release_final_head.py --threads "$THREADS"
  python scripts/check_report.py REPORT.md
}

stage_smoke() {  # < 5 min
  local t0=$SECONDS tmp; tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' RETURN
  echo "== unit tests"
  python -m pytest -q -x -m "not slow and not gpu" tests
  echo "== describe + compare on BURROW examples"
  python -m pocketcompare describe "$EX/1a28_A.pdb" -o "$tmp/a.parquet"
  python -m pocketcompare describe "$EX/AF-P00918-F1-model_v6.cif.gz" --af-mode -o "$tmp/b.parquet"
  python -m pocketcompare compare "$tmp/a.parquet" "$tmp/b.parquet" --top 5 -o "$tmp/pairs.tsv"
  head -4 "$tmp/pairs.tsv"
  echo "== report check"
  python scripts/check_report.py REPORT.md
  echo "== FREEZE.json hashes vs tag freeze-v1"
  python - <<'PY'
import json, subprocess, hashlib, sys
fz = json.load(open("FREEZE.json"))
files = {fz["method_config"]: fz["method_config_sha256"], **fz["weights"]}
bad = 0
for p, h in files.items():
    blob = subprocess.run(["git", "show", f"freeze-v1:{p}"], capture_output=True, check=True).stdout
    got = hashlib.sha256(blob).hexdigest()
    ok = got == h
    bad += not ok
    print(("OK  " if ok else "BAD ") + p)
for k, p in [("evaluate_sha256", "src/pocketcompare/evaluate.py"), ("prereg_sha256", "PREREG.md"),
             ("final_eval_sha256", "scripts/final_eval.py")]:
    r = subprocess.run(["git", "show", f"freeze-v1:{p}"], capture_output=True)
    if r.returncode:
        print("SKIP", p, "(not at tag)"); continue
    ok = hashlib.sha256(r.stdout).hexdigest() == fz[k]
    bad += not ok
    print(("OK  " if ok else "BAD ") + p)
sys.exit(1 if bad else 0)
PY
  echo "SMOKE PASSED in $((SECONDS - t0)) s"
}

STAGES=(env data splits caches descriptors dev train select final prereg2 proteome release)
[[ $# -ge 1 ]] || { sed -n 2,13p "$0"; exit 1; }
if [[ $1 == smoke ]]; then ( activate; stage_smoke ) 2>&1 | tee logs/reproduce_smoke.log; exit "${PIPESTATUS[0]}"; fi
if [[ $1 == all ]]; then set -- "${STAGES[@]}"; fi
for s in "$@"; do
  [[ " ${STAGES[*]} " == *" $s "* ]] || { echo "unknown stage $s"; exit 2; }
  if [[ $s == final || $s == prereg2 ]]; then ( "stage_$s" ) | tee "logs/reproduce_$s.log"; else run_stage "$s"; fi
done
