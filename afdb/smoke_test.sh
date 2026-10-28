#!/usr/bin/env bash
# End-to-end smoke test of the AFDB pipeline on a tiny work list, on 1-2 GPUs (~2-3 min after setup_env.sh).
# Part A (default tier-3 source, Foldcomp):
#   tier 1: 200 ECOLI + 200 HUMAN models (2 units, 2 describe batches each; the ECOLI unit with --runner cli)
#   tier 3: a tiny real Foldcomp database: the first 300 entries of afdb_swissprot_v4 (one ranged download of
#           ~1.4 MB + its .index/.lookup), taxids from the UniProt REST API (one accession deliberately left out:
#           it must land in the "unclassified" group), ordered and packed into units by make_worklist.py
#   checks: all units done, entry accounting (tier-1 accessions skipped), taxids and `source` columns, filters,
#           fp16 format, a stale claim is reclaimed, a re-run has nothing to do, status.py, build_index.py (flat +
#           IVF-PQ) + `pocketcompare search`, and that the stored fingerprints of 5 structures (2 tier-1 models,
#           3 decompressed Foldcomp entries) equal a direct `pocketcompare describe` (reference CPU backend),
#           max |diff| <= 1e-3
# Part B (SMOKE_GCS=1, default): TIER3_SOURCE=gcs against a local mock of the bucket (afdb/mock_gcs_server.py):
#   one packed unit of 2 tars, the first download cut short (restart and skip), .pdb.gz members and tier-1
#   accessions skipped.
#   bash afdb/smoke_test.sh            # SMOKE_ROOT, SMOKE_DEVICES, SMOKE_GCS=0, KEEP=1 to keep the test inputs
set -euo pipefail
SMOKE_ROOT="${SMOKE_ROOT:-/cluster/project/beltrao/gmagnus/pocket_compare/release/afdb_smoke/smoke}"
export OUT_ROOT="$SMOKE_ROOT"
unset FOLDCOMP_DIR TIER3_SOURCE
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"      # TAR_INDEX_DIR / NCBI_DIR default to $OUT_ROOT/...: pass
                                                       # existing ones to skip re-indexing / re-downloading
NGPU=$(nvidia-smi -L 2>/dev/null | wc -l)
DEVICES="${SMOKE_DEVICES:-$( [[ "$NGPU" -ge 2 ]] && echo cuda:0,cuda:1 || echo cuda:0 )}"
WPS="${SMOKE_WORKERS:-8}"
PY="$ENV_DIR/bin/python"
say() { echo "[smoke $(date +%H:%M:%S)] $*"; }
[[ -x "$PY" ]] || { echo "no environment at $ENV_DIR: run afdb/setup_env.sh first" >&2; exit 1; }
rm -rf "$SMOKE_ROOT"; mkdir -p "$SMOKE_ROOT"
WORK="$SMOKE_ROOT/_tmp"; mkdir -p "$WORK"
export TMPDIR="$WORK" NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-$ENV_DIR/numba_cache}"
srv=""
cleanup() { [[ -n "$srv" ]] && kill "$srv" 2>/dev/null || true; }
trap cleanup EXIT
WARGS=(--devices "$DEVICES" --workers-per-shard "$WPS" --batch-structures 120 --log-every 20 --fc-procs 2)

# ================================================================================================ part A: Foldcomp
say "A1 tiny Foldcomp database (300 afdb_swissprot_v4 entries) + taxid map"
export FOLDCOMP_DIR="$SMOKE_ROOT/foldcomp" FOLDCOMP_DB=afdb_swissprot_v4 TIER3_SOURCE=foldcomp
"$PY" "$AFDB_DIR/make_tiny_foldcomp.py" "$FOLDCOMP_DIR" --db afdb_swissprot_v4 --n 300 --drop-one

say "A2 work list (tier 1: ECOLI + HUMAN, tier 3: Foldcomp)"
"$PY" "$AFDB_DIR/make_worklist.py" --tiers 1,3 --tier1-codes ECOLI,HUMAN --limit-per-source 200 \
    --unit-structures 200 --no-swissprot --nodes 1
cut -f1-4,10-12,15 "$OUT_ROOT/worklist.tsv"

say "A3 a stale claim (dead pid on this host) on the first Foldcomp unit"
mkdir -p "$OUT_ROOT/state/claims/2"
echo "{\"host\": \"$(hostname)\", \"pid\": 999999999, \"t\": $(date +%s), \"slurm_job_id\": null}" \
    > "$OUT_ROOT/state/claims/2/claim.json"

say "A4 worker: ECOLI unit with --runner cli, then the rest with the persistent runner; then a re-run"
"$PY" "$AFDB_DIR/worker.py" "${WARGS[@]}" --runner cli --tiers 1 --max-units 1
"$PY" "$AFDB_DIR/worker.py" "${WARGS[@]}" --runner persistent
"$PY" "$AFDB_DIR/worker.py" "${WARGS[@]}" 2>&1 | tee "$WORK/rerun.log" | tail -1
grep -q "0 units done" "$WORK/rerun.log"

say "A5 output checks"
"$PY" - "$OUT_ROOT" <<'EOF'
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq
root = Path(sys.argv[1])
fc = root / "foldcomp"
wl = pd.read_parquet(root / "worklist.parquet")
assert list(wl.tier[:2]) == [1, 1] and (wl.tier[2:] == 3).all() and len(wl) >= 4, wl
assert all((root / "state/done" / f"{u}.json").exists() for u in wl.unit_id), "missing done markers"
assert not list((root / "state/failed").glob("*.json")), "failed units"
assert not [p for p in (root / "state/claims").iterdir() if not p.name.startswith(".")], "claims left behind"
d = {u: json.loads((root / "state/done" / f"{u}.json").read_text()) for u in wl.unit_id}
assert d[0]["structures"] == 200 and d[1]["structures"] == 200 and d[0]["runner"] == "cli"
# tier-3 accounting: every entry of the tiny DB whose accession is not in tier 1 is described exactly once
skip = set(pd.read_csv(root / "skip_accessions.txt", sep="\t", header=None)[0])
lk = pd.read_csv(fc / "afdb_swissprot_v4.lookup", sep="\t", header=None, names=["key", "name", "f"])
lk["acc"] = lk.name.str.split("-").str[1]
want = set(lk.acc[~lk.acc.isin(skip)])
S3 = pd.concat([pd.read_parquet(root / f"structures/tier3/{u:06d}.parquet") for u in wl.unit_id[wl.tier == 3]])
assert set(S3.accession) == want and len(S3) == len(want), (len(S3), len(want))
tax = pd.read_parquet(fc / "uniprot_taxid.parquet").set_index("accession").taxid
drop = (fc / "smoke_dropped_accession.txt").read_text()
exp = S3.accession.map(tax).fillna(0).astype(int)
assert (S3.taxid.to_numpy() == exp.to_numpy()).all(), "taxid mismatch"
assert drop not in want or int(S3.set_index("accession").taxid[drop]) == 0
assert (S3.source == "foldcomp:afdb_swissprot_v4").all() and (S3.model_version == 4).all()
assert (S3.status == "ok").all(), S3[S3.status != "ok"]
assert S3.n_res.min() > 0 and S3.plddt_mean.between(0, 100).all()
print(f"tier 3: {len(lk)} entries, {len(lk) - len(want)} skipped (tier-1 accessions), {len(S3)} described in "
      f"{(wl.tier == 3).sum()} units, {S3.taxid.nunique()} taxa, {(S3.taxid == 0).sum()} unclassified")
for u, t in zip(wl.unit_id, wl.tier):
    p = root / f"pockets/tier{t}/{u:06d}.parquet"
    s = pd.read_parquet(root / f"structures/tier{t}/{u:06d}.parquet")
    tab = pq.read_table(p)
    V = np.asarray(tab["fingerprint"].combine_chunks().flatten()).reshape(-1, 384)      # the 3-line loader
    assert V.dtype == np.float16 and len(V) == d[u]["pockets_kept"] == s.n_pockets_kept.sum()
    assert np.all(np.abs(np.linalg.norm(V.astype(np.float32), axis=1) - 1) < 2e-3), "not unit norm"
    m = tab.drop(["fingerprint"]).to_pandas()
    assert (m.burrow_score >= 0.03).all() and (m.plddt_mean >= 70).all()
    assert len(m) == 0 or m.source.nunique() == 1 and m.source.iloc[0] == s.source.iloc[0]
    assert s.source.iloc[0] == ("afdb_v6_tar" if t == 1 else "foldcomp:afdb_swissprot_v4")
    dr = d[u]["dropped"]
    assert d[u]["pockets_all"] - d[u]["pockets_kept"] == dr["not_describable"] + dr["score_lt_min"] + dr["plddt_lt_min"]
    print(f"unit {u} tier {t}: {len(s)} structures, {d[u]['pockets_all']} -> {len(m)} pockets; source "
          f"{s.source.iloc[0]}; taxa {sorted(s.taxid.unique().tolist())[:4]}")
from pocketcompare import fpindex as FX
meta, V32, rec = FX.read_table(root / "pockets/tier1/000000.parquet")
assert rec["method"].startswith("pocketcompare-final") and V32.dtype == np.float32
print("OK outputs")
EOF

say "A6 fingerprints vs a direct pocketcompare describe (reference CPU backend) of 5 structures"
"$PY" - "$OUT_ROOT" <<'EOF'
import os, sys
from pathlib import Path
import pandas as pd, foldcomp
root = Path(sys.argv[1])
wl = pd.read_parquet(root / "worklist.parquet").set_index("unit_id")
d = root / "_tmp/direct"; d.mkdir(parents=True, exist_ok=True)
picked = []
for u, n in ((0, 1), (1, 1), (2, 2), (int(wl.index[-1]), 1)):
    s = pd.read_parquet(root / f"structures/tier{wl.loc[u, 'tier']}/{u:06d}.parquet")
    picked += [(u, x) for x in s[s.n_pockets_kept > 0].structure_stem.iloc[:n]]
fcidx = pd.read_csv(root / "foldcomp/afdb_swissprot_v4.index", sep="\t", header=None, names=["key", "off", "len"])
fclk = pd.read_csv(root / "foldcomp/afdb_swissprot_v4.lookup", sep="\t", header=None, names=["key", "name", "f"])
fc = fcidx.merge(fclk, on="key").set_index("name")
for u, stem in picked:
    r = wl.loc[u]
    if r.source_type == "local_tar":                     # by offset from the tar index (no full tar scan)
        ix = pd.read_parquet(Path(os.environ["TAR_INDEX_DIR"]) / (Path(r.source).name + ".parquet")).set_index("name")
        off, size = ix.loc[f"{stem}.cif.gz", ["offset_data", "size"]]
        with open(r.source, "rb") as fh:
            fh.seek(int(off))
            (d / f"{stem}.cif.gz").write_bytes(fh.read(int(size)))
    else:                                                 # decompress the entry straight from the database file
        off, ln = fc.loc[stem, ["off", "len"]]
        with open(root / "foldcomp/afdb_swissprot_v4", "rb") as fh:
            fh.seek(int(off))
            name, pdb = foldcomp.decompress(fh.read(int(ln)))
        (d / f"{stem}.pdb").write_text(pdb)
print("picked", [p[1] for p in picked])
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
print(f"{dm.structure_stem.nunique()} structures ({dm.structure.str.endswith('.pdb').groupby(dm.structure_stem).first().sum()} "
      f"Foldcomp), {len(dm)} kept pockets: max |stored fp16 - direct fp32| = {diff:.2e}")
assert diff <= 1e-3
print("OK fingerprints")
EOF

say "A7 status.py"
"$PY" "$AFDB_DIR/status.py"

say "A8 build_index.py (flat and IVF-PQ) + pocketcompare search"
"$PY" "$AFDB_DIR/build_index.py" --tiers 1,3 --kind flat -o "$OUT_ROOT/index/flat" --threads 8
"$PY" "$AFDB_DIR/build_index.py" --tiers 1,3 --kind ivfpq --nlist 8 -o "$OUT_ROOT/index/ivfpq" --save-vectors \
    --threads 8 2>&1 | grep -v "^WARNING clustering"
Q=$(ls "$OUT_ROOT"/pockets/tier3/*.parquet | head -1)
"$ENV_DIR/bin/pocketcompare" search "$Q" "$OUT_ROOT/index/ivfpq" -k 3 --print 4 -o "$WORK/hits.tsv"
"$PY" - "$WORK/hits.tsv" <<'EOF'
import sys
import pandas as pd
h = pd.read_csv(sys.argv[1], sep="\t")
top = h[h["rank"] == 1]
assert (top.query_id == top.hit_id).mean() > 0.95, "self hits missing"
print(f"OK search: {top.query_id.nunique()} queries, self-hit at rank 1 for {100 * (top.query_id == top.hit_id).mean():.0f} %")
EOF

# ================================================================================================ part B: GCS (mock)
if [[ "${SMOKE_GCS:-1}" == 1 ]]; then
export OUT_ROOT="$SMOKE_ROOT/gcs" TIER3_SOURCE=gcs
mkdir -p "$OUT_ROOT"
say "B1 mock GCS bucket"
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
EOF
"$PY" "$AFDB_DIR/mock_gcs_server.py" "$MOCK" --port-file "$MOCK/port" --truncate-first 1500000 &
srv=$!
for _ in $(seq 50); do [[ -f "$MOCK/port" ]] && break; sleep 0.2; done
export GCS_BASE_URL="http://127.0.0.1:$(cat "$MOCK/port")" GCS_SMALL_BYTES=1000000
say "B2 work list (tier 3 from the mock bucket) and worker"
"$PY" "$AFDB_DIR/make_worklist.py" --tiers 3 --tier1-codes ECOLI,HUMAN --no-swissprot \
    --gcs-listing "$MOCK/listing.tsv" --unit-structures 200 --nodes 1 2>&1 | grep -E "GCS|tier 3"
"$PY" "$AFDB_DIR/worker.py" "${WARGS[@]}" 2>&1 | grep -E "done:|stream|FAILED|finished"
"$PY" - "$OUT_ROOT" <<'EOF'
import json, sys
from pathlib import Path
import pandas as pd
root = Path(sys.argv[1])
wl = pd.read_parquet(root / "worklist.parquet")
assert len(wl) == 1 and wl.source_type[0] == "gcs_tar" and len(wl.sources[0]) == 2, wl
d = json.loads((root / "state/done/0.json").read_text())
g = d["extract"]
assert d["structures"] == 43 and g["skipped_earlier_tier"] == 3 and g["non_model"] == 40, g
assert g["http_retries"] >= 1, "the truncated download was not retried"
s = pd.read_parquet(root / "structures/tier3/000000.parquet")
assert (s.source == "gcs_v4_tar").all() and (s.status == "ok").all()
print(f"OK GCS path: {d['structures']} structures, {d['pockets_kept']} pockets, {g['http_retries']} HTTP retry")
EOF
kill "$srv" 2>/dev/null || true; srv=""
fi

if [[ "${KEEP:-0}" != 1 ]]; then rm -rf "$WORK" "$SMOKE_ROOT/gcs/mock_gcs" "$SMOKE_ROOT/gcs/_tmp"; fi
du -sh "$SMOKE_ROOT"
say "SMOKE TEST PASSED  (outputs in $SMOKE_ROOT)"
