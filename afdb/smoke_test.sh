#!/usr/bin/env bash
# End-to-end smoke test of the AFDB pipeline on a tiny work list, on 1-2 GPUs (~3 min after setup_env.sh):
#   tier 1: 200 ECOLI + 200 HUMAN models (2 units, 2 describe batches each; the ECOLI unit with --runner cli)
#   tier 3: one packed "GCS" unit of 2 tars served by a local mock of the bucket (afdb/mock_gcs_server.py):
#           40 METJA models streamed in 'r|' mode (first download cut short -> restart and skip), 3 CAMJE
#           models fetched in memory, .pdb.gz members (skipped) and 3 HUMAN models (skipped: tier 1 accessions)
# Checks: all units done, member accounting, filters, fp16 table format, a stale claim is reclaimed, a re-run
# has nothing to do, status.py, build_index.py (flat + IVF-PQ) + `pocketcompare search`, and that the stored
# fingerprints of 5 structures equal a direct `pocketcompare describe` (reference CPU backend), max |diff| <= 1e-3.
#   bash afdb/smoke_test.sh                                     # SMOKE_ROOT, SMOKE_DEVICES, KEEP=1 to keep outputs
set -euo pipefail
export OUT_ROOT="${SMOKE_ROOT:-/cluster/project/beltrao/gmagnus/pocket_compare/release/afdb_smoke/smoke}"
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"      # TAR_INDEX_DIR / NCBI_DIR default to $OUT_ROOT/...: pass
                                                       # existing ones to skip re-indexing / re-downloading
DEVICES="${SMOKE_DEVICES:-cuda:0,cuda:1}"
WPS="${SMOKE_WORKERS:-8}"
PY="$ENV_DIR/bin/python"
say() { echo "[smoke $(date +%H:%M:%S)] $*"; }
[[ -x "$PY" ]] || { echo "no environment at $ENV_DIR: run afdb/setup_env.sh first" >&2; exit 1; }
rm -rf "$OUT_ROOT"; mkdir -p "$OUT_ROOT"
WORK="$OUT_ROOT/_tmp"; mkdir -p "$WORK"
export TMPDIR="$WORK" NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-$ENV_DIR/numba_cache}"
srv=""
cleanup() { [[ -n "$srv" ]] && kill "$srv" 2>/dev/null || true; }
trap cleanup EXIT

say "1/8 mock GCS bucket"
MOCK="$OUT_ROOT/mock_gcs"; mkdir -p "$MOCK/proteomes"
"$PY" - "$AFDB_LOCAL" "$MOCK" <<'EOF'
import io, sys, tarfile
from pathlib import Path
src, mock = Path(sys.argv[1]), Path(sys.argv[2])
def members(tar, n, start=0, cif_only=False):
    out = []
    with tarfile.open(tar) as tf:
        k = 0
        for m in tf:
            if cif_only and not m.name.endswith(".cif.gz"):
                continue
            if m.name.endswith(".cif.gz"):
                k += 1
            if k <= start:
                continue
            if k > start + n:
                break
            out.append((m.name, tf.extractfile(m).read()))
    return out
def write(name, items):
    with tarfile.open(mock / "proteomes" / name, "w") as tf:
        for n, d in items:
            ti = tarfile.TarInfo(n); ti.size = len(d); tf.addfile(ti, io.BytesIO(d))
metja = members(src / "UP000000805_243232_METJA_v6.tar", 40)                    # 40 cif.gz + 40 pdb.gz
human = members(src / "UP000005640_9606_HUMAN_v6.tar", 3, start=500, cif_only=True)
write("proteome-tax_id-243232-0_v4.tar", metja[:20] + human + metja[20:])
write("proteome-tax_id-192222-0_v4.tar", members(src / "UP000000799_192222_CAMJE_v6.tar", 3, cif_only=True))
with open(mock / "listing.tsv", "w") as fh:
    for p in sorted((mock / "proteomes").glob("*.tar")):
        fh.write(f"proteomes/{p.name}\t{p.stat().st_size}\n")
    fh.write("proteomes/proteome-tax_id-243232-0_v3.tar\t123456\n")            # older version: must be ignored
print("mock tars:", sorted(p.name for p in (mock / "proteomes").glob("*.tar")))
EOF
"$PY" "$AFDB_DIR/mock_gcs_server.py" "$MOCK" --port-file "$MOCK/port" --truncate-first 1500000 &
srv=$!
for _ in $(seq 50); do [[ -f "$MOCK/port" ]] && break; sleep 0.2; done
export GCS_BASE_URL="http://127.0.0.1:$(cat "$MOCK/port")" GCS_SMALL_BYTES=1000000

say "2/8 work list"
"$PY" "$AFDB_DIR/make_worklist.py" --tiers 1,3 --tier1-codes ECOLI,HUMAN --limit-per-source 200 \
    --unit-structures 200 --no-swissprot --gcs-listing "$MOCK/listing.tsv" --nodes 1
cat "$OUT_ROOT/worklist.tsv" | cut -f1-4,10-11,14-15

say "3/8 a stale claim (dead pid on this host) on the GCS unit"
mkdir -p "$OUT_ROOT/state/claims/2"
echo "{\"host\": \"$(hostname)\", \"pid\": 999999999, \"t\": $(date +%s), \"slurm_job_id\": null}" \
    > "$OUT_ROOT/state/claims/2/claim.json"

say "4/8 worker: ECOLI unit with --runner cli, then the rest with the persistent runner"
WARGS=(--devices "$DEVICES" --workers-per-shard "$WPS" --batch-structures 120 --log-every 20)
"$PY" "$AFDB_DIR/worker.py" "${WARGS[@]}" --runner cli --tiers 1 --max-units 1
"$PY" "$AFDB_DIR/worker.py" "${WARGS[@]}" --runner persistent
say "re-run (must find nothing to do)"
"$PY" "$AFDB_DIR/worker.py" "${WARGS[@]}" 2>&1 | tee "$WORK/rerun.log" | tail -2
grep -q "0 units done" "$WORK/rerun.log"

say "5/8 output checks"
"$PY" - "$OUT_ROOT" <<'EOF'
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
root = Path(sys.argv[1])
wl = pd.read_parquet(root / "worklist.parquet")
assert len(wl) == 3 and list(wl.tier) == [1, 1, 3], wl
assert all((root / "state/done" / f"{u}.json").exists() for u in wl.unit_id), "missing done markers"
assert not list((root / "state/failed").glob("*.json")), "failed units"
assert not [p for p in (root / "state/claims").iterdir() if not p.name.startswith(".")], "claims left behind"
d = {u: json.loads((root / "state/done" / f"{u}.json").read_text()) for u in wl.unit_id}
assert d[0]["structures"] == 200 and d[1]["structures"] == 200, (d[0]["structures"], d[1]["structures"])
assert d[0]["runner"] == "cli" and d[1]["runner"] == "persistent"
g = d[2]["extract"]
assert d[2]["structures"] == 43 and g["skipped_earlier_tier"] == 3 and g["non_model"] == 40, g
assert g["http_retries"] >= 1, "the truncated download was not retried"
assert wl.sources[2].tolist() == ["proteomes/proteome-tax_id-243232-0_v4.tar", "proteomes/proteome-tax_id-192222-0_v4.tar"] or \
       sorted(wl.sources[2].tolist()) == sorted(["proteomes/proteome-tax_id-243232-0_v4.tar", "proteomes/proteome-tax_id-192222-0_v4.tar"])
for u, t in zip(wl.unit_id, wl.tier):
    p = root / f"pockets/tier{t}/{u:06d}.parquet"
    s = pd.read_parquet(root / f"structures/tier{t}/{u:06d}.parquet")
    tab = pq.read_table(p)
    V = np.asarray(tab["fingerprint"].combine_chunks().flatten()).reshape(-1, 384)      # the 3-line loader
    assert V.dtype == np.float16 and len(V) == d[u]["pockets_kept"] == s.n_pockets_kept.sum()
    n = np.linalg.norm(V.astype(np.float32), axis=1)
    assert np.all(np.abs(n - 1) < 2e-3), "not unit norm"
    m = tab.drop(["fingerprint"]).to_pandas()
    assert (m.burrow_score >= 0.03).all() and (m.plddt_mean >= 70).all()
    assert (s.status == "ok").all(), s[s.status != "ok"]
    dr = d[u]["dropped"]
    assert d[u]["pockets_all"] - d[u]["pockets_kept"] == dr["not_describable"] + dr["score_lt_min"] + dr["plddt_lt_min"]
    print(f"unit {u} tier {t}: {len(s)} structures, {d[u]['pockets_all']} -> {len(m)} pockets "
          f"(score {dr['score_lt_min']}, pLDDT {dr['plddt_lt_min']}, zero {dr['not_describable']} dropped); "
          f"taxa {sorted(s.taxid.unique().tolist())[:4]}; versions {sorted(s.model_version.unique().tolist())}")
from pocketcompare import fpindex as FX
meta, V32, rec = FX.read_table(root / "pockets/tier1/000000.parquet")
assert rec["method"].startswith("pocketcompare-final") and V32.dtype == np.float32
print("OK outputs")
EOF

say "6/8 fingerprints vs a direct pocketcompare describe (reference CPU backend) of 5 structures"
"$PY" - "$OUT_ROOT" <<'EOF'
import sys, tarfile
from pathlib import Path
import numpy as np, pandas as pd
root = Path(sys.argv[1])
wl = pd.read_parquet(root / "worklist.parquet")
d = root / "_tmp/direct"; d.mkdir(parents=True, exist_ok=True)
pick = []
for u, t, n in ((0, 1, 2), (1, 1, 2), (2, 3, 1)):
    s = pd.read_parquet(root / f"structures/tier{t}/{u:06d}.parquet")
    s = s[s.n_pockets_kept > 0]
    pick += [(u, x, src) for x, src in zip(s.structure_stem.iloc[[0, -1][:n]], s.source.iloc[[0, -1][:n]])]
import os
for u, stem, src in pick:
    r = wl.set_index("unit_id").loc[u]
    if r.source_type == "local_tar":                     # by offset from the tar index (no full tar scan)
        ix = pd.read_parquet(Path(os.environ["TAR_INDEX_DIR"]) / (Path(r.source).name + ".parquet")).set_index("name")
        off, size = ix.loc[f"{stem}.cif.gz", ["offset_data", "size"]]
        with open(r.source, "rb") as fh:
            fh.seek(int(off))
            data = fh.read(int(size))
    else:
        with tarfile.open(root / "mock_gcs/proteomes" / src.split("/")[-1]) as tf:
            data = tf.extractfile(f"{stem}.cif.gz").read()
    (d / f"{stem}.cif.gz").write_bytes(data)
print("picked", [p[1] for p in pick])
EOF
"$ENV_DIR/bin/pocketcompare" describe "$OUT_ROOT/_tmp/direct" --af-mode --workers 5 -o "$OUT_ROOT/_tmp/direct.parquet"
"$PY" - "$OUT_ROOT" <<'EOF'
import sys
from pathlib import Path
import numpy as np, pandas as pd
from pocketcompare import fpindex as FX
root = Path(sys.argv[1])
dm, DV, _ = FX.read_table(root / "_tmp/direct.parquet")
keep = dm.ok & (dm.burrow_score >= 0.03) & (dm.plddt_mean >= 70)
dm, DV = dm[keep].reset_index(drop=True), DV[keep.to_numpy()]
frames = []
for p in sorted(root.glob("pockets/tier*/*.parquet")):
    m, V, _ = FX.read_table(p)
    frames.append(m.assign(_v=list(V)))
st = pd.concat(frames, ignore_index=True)
st = st[st.pocket_id.str.split(":").str[0].isin(set(dm.structure_stem))].set_index("pocket_id")
assert set(st.index) == set(dm.pocket_id), (sorted(set(st.index) ^ set(dm.pocket_id)))[:10]
S = np.stack(st.loc[dm.pocket_id, "_v"].to_numpy())
diff = float(np.abs(S - DV).max())
print(f"{dm.structure_stem.nunique()} structures, {len(dm)} kept pockets: max |stored fp16 - direct fp32| = {diff:.2e}")
assert diff <= 1e-3
print("OK fingerprints")
EOF

say "7/8 status.py"
"$PY" "$AFDB_DIR/status.py"

say "8/8 build_index.py (flat and IVF-PQ) + pocketcompare search"
"$PY" "$AFDB_DIR/build_index.py" --tiers 1,3 --kind flat -o "$OUT_ROOT/index/flat" --threads 8
"$PY" "$AFDB_DIR/build_index.py" --tiers 1,3 --kind ivfpq --nlist 8 -o "$OUT_ROOT/index/ivfpq" --save-vectors \
    --threads 8 2>&1 | grep -v "^WARNING clustering"
"$ENV_DIR/bin/pocketcompare" search "$OUT_ROOT/pockets/tier3/000002.parquet" "$OUT_ROOT/index/ivfpq" -k 3 --print 6 \
    -o "$WORK/hits.tsv"
"$PY" - "$OUT_ROOT" <<'EOF'
import sys
from pathlib import Path
import pandas as pd
h = pd.read_csv(Path(sys.argv[1]) / "_tmp/hits.tsv", sep="\t")
top = h[h["rank"] == 1]
assert (top.query_id == top.hit_id).mean() > 0.95, "self hits missing"
print(f"OK search: {top.query_id.nunique()} queries, self-hit at rank 1 for {100 * (top.query_id == top.hit_id).mean():.0f} %")
EOF

if [[ "${KEEP:-0}" != 1 ]]; then rm -rf "$MOCK" "$WORK"; fi
du -sh "$OUT_ROOT"
say "SMOKE TEST PASSED  (outputs in $OUT_ROOT)"
