#!/usr/bin/env bash
# Check the environment and the work list, then submit the AFDB array job (one task per node).
#   bash afdb/submit.sh                       # all tiers in the work list, 4 nodes
#   bash afdb/submit.sh --tiers 1             # tier 1 only (then e.g. --tiers 2, --tiers 3, or all)
#   bash afdb/submit.sh --tiers 1,2 --nodes 2 -- --time=1-00:00:00     # args after -- go to sbatch
#   bash afdb/submit.sh --retry-failed        # also re-run units that have a failed marker
#   DRY=1 bash afdb/submit.sh ...             # print the sbatch command only
# Resubmitting is safe at any time: finished units are skipped, claims of jobs that are gone are reclaimed.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
TIERS="" NODES="$SLURM_NODES" EXTRA=() RETRY=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tiers) TIERS="$2"; shift 2 ;;
        --nodes) NODES="$2"; shift 2 ;;
        --retry-failed) RETRY=1; shift ;;
        --) shift; EXTRA=("$@"); break ;;
        *) echo "unknown option $1" >&2; exit 2 ;;
    esac
done
die() { echo "submit.sh: $*" >&2; exit 1; }

[[ -x "$ENV_DIR/bin/python" ]] || die "no environment at $ENV_DIR (run: bash afdb/setup_env.sh)"
"$ENV_DIR/bin/python" -c "import pocketcompare, pocketdetect, faiss, torch" 2>/dev/null \
    || die "environment $ENV_DIR is incomplete (run: bash afdb/setup_env.sh)"
[[ -f "$OUT_ROOT/worklist.parquet" ]] || die "no work list at $OUT_ROOT/worklist.parquet (run: python afdb/make_worklist.py)"
mkdir -p "$OUT_ROOT/logs" || die "cannot create $OUT_ROOT/logs"
touch "$OUT_ROOT/logs/.write_test" && rm -f "$OUT_ROOT/logs/.write_test" || die "$OUT_ROOT is not writable"

# summary of what will run, and a download test when GCS units (tier 3) are in scope
"$ENV_DIR/bin/python" - "$OUT_ROOT" "$TIERS" <<'EOF'
import sys, json, os, urllib.request, urllib.parse
import pandas as pd
root, tiers = sys.argv[1], sys.argv[2]
wl = pd.read_parquet(f"{root}/worklist.parquet", columns=["unit_id", "tier", "source_type", "source", "sources",
                                                          "est_structures"])
if tiers:
    wl = wl[wl.tier.isin([int(t) for t in tiers.split(",")])]
done = {int(f[:-5]) for f in os.listdir(f"{root}/state/done")} if os.path.isdir(f"{root}/state/done") else set()
todo = wl[~wl.unit_id.isin(done)]
print(f"submit.sh: {len(wl)} units in scope, {len(todo)} not done, ~{todo.est_structures.sum():,} structures")
f = todo[todo.source_type == "foldcomp"]
for db, sources in sorted({(r.source, r.sources[0]) for r in f.itertuples()}):
    d = os.environ.get("FOLDCOMP_DIR") or f"{root}/foldcomp"
    data, idx, ent = f"{d}/{db}", f"{d}/{db}.index", f"{root}/{sources}"
    for p in (data, idx, ent):
        if not os.path.exists(p):
            sys.exit(f"submit.sh: {p} missing (run afdb/fetch_foldcomp.sbatch, then make_worklist.py)")
    with open(idx, "rb") as fh:                            # entries are contiguous: the last one ends the file
        fh.seek(max(0, os.path.getsize(idx) - 4096))
        _, off, ln = fh.read().strip().split(b"\n")[-1].split(b"\t")
    if int(off) + int(ln) != os.path.getsize(data):
        sys.exit(f"submit.sh: {data} is incomplete ({os.path.getsize(data):,} B, index ends at {int(off) + int(ln):,})")
    print(f"submit.sh: Foldcomp {db} complete ({os.path.getsize(data) / 1e12:.2f} TB)")
g = todo[todo.source_type == "gcs_tar"]
if len(g) and os.environ.get("TIER3_SOURCE") == "gcs":
    base = os.environ.get("GCS_BASE_URL") or f"https://storage.googleapis.com/{os.environ.get('GCS_BUCKET')}"
    name = g.sources.iloc[0][0]
    url = f"{base}/{urllib.parse.quote(name)}"
    hdr = {"Range": "bytes=0-1023"}
    cmd = os.environ.get("GCS_AUTH_CMD")
    if cmd:
        import subprocess
        hdr["Authorization"] = "Bearer " + subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()
    if os.environ.get("GCS_USER_PROJECT"):
        url += "?userProject=" + os.environ["GCS_USER_PROJECT"]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=60) as r:
            r.read(1024)
        print(f"submit.sh: GCS download test OK ({name})")
    except Exception as e:  # noqa: BLE001
        print(f"submit.sh: GCS download test FAILED for {url}: {e}\n"
              "  Tier-3 units would fail. Anonymous downloads from the bucket were denied (HTTP 403) when this was "
              "built (2026-10-28).\n  Options: GCS_AUTH_CMD='gcloud auth print-access-token' (+ GCS_USER_PROJECT=<project> "
              "if the bucket is requester-pays),\n  or a mirror via GCS_BASE_URL, or submit --tiers 1,2 only. "
              "Set SKIP_GCS_CHECK=1 to submit anyway.", file=sys.stderr)
        if os.environ.get("SKIP_GCS_CHECK") != "1":
            sys.exit(3)
EOF

WARGS=""
[[ -n "$TIERS" ]] && WARGS="--tiers $TIERS"
[[ "$RETRY" == 1 ]] && WARGS="$WARGS --retry-failed"
export AFDB_DIR WORKER_ARGS="$WARGS"     # passed through the environment (sbatch --export splits values at commas)
cmd=(sbatch --array=0-$((NODES - 1)) --output="$OUT_ROOT/logs/%x_%A_%a.out" --export=ALL "${EXTRA[@]}"
     "$AFDB_DIR/afdb.sbatch")
echo "submit.sh: WORKER_ARGS='$WORKER_ARGS' OUT_ROOT=$OUT_ROOT ${cmd[*]}"
[[ "${DRY:-0}" == 1 ]] && exit 0
cp "$AFDB_DIR/POCKETOME.md" "$OUT_ROOT/POCKETOME.md" 2>/dev/null || true   # data guide next to the data
"${cmd[@]}"
echo "submit.sh: monitor with  python $AFDB_DIR/status.py   and   tail -f $OUT_ROOT/logs/pocketcompare-afdb_*.out"
