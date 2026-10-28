#!/usr/bin/env bash
# Regression test: the tier-1/2 work list of this make_worklist.py is byte-identical to the one of commit OLD
# (default 24d1c8f, the version the first tier-1/2 run used), and adding a Foldcomp tier 3 to an existing
# OUT_ROOT keeps every tier-1/2 row (unit_id, sources, member ranges) and puts tier 3 after them.
#   TAR_INDEX_DIR=<cached tar indices> NCBI_DIR=<taxdump> bash afdb/test_worklist_compat.sh
# The tier-3 part uses a tiny Foldcomp DB of the first 400 afdb_uniprot_v4 entries (make_tiny_foldcomp.py).
set -euo pipefail
OLD="${OLD:-24d1c8f}"
T="${COMPAT_ROOT:-/cluster/project/beltrao/gmagnus/pocket_compare/release/afdb_smoke/compat}"
export OUT_ROOT="$T"
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
PY="$ENV_DIR/bin/python"
REPO="$(cd "$AFDB_DIR/.." && pwd)"
rm -rf "$T"; mkdir -p "$T/old_code" "$T/A" "$T/B" "$T/C"
for f in make_worklist.py afdb_common.py species_order.tsv; do
    git -C "$REPO" show "$OLD:afdb/$f" > "$T/old_code/$f"
done
echo "[compat] old ($OLD) vs new make_worklist.py, --tiers 1,2"
OUT_ROOT="$T/A" "$PY" "$T/old_code/make_worklist.py" --tiers 1,2 2>&1 | tail -3
OUT_ROOT="$T/B" "$PY" "$AFDB_DIR/make_worklist.py" --tiers 1,2 2>&1 | tail -3
for f in worklist.parquet worklist.tsv skip_accessions.txt; do
    cmp "$T/A/$f" "$T/B/$f" && echo "[compat] $f byte-identical"
done

FC="$T/foldcomp" DB=afdb_uniprot_v4          # 400 real entries of the tier-3 database (one ranged download)
"$PY" "$AFDB_DIR/make_tiny_foldcomp.py" "$FC" --db "$DB" --n 400
if [[ -f "$FC/$DB.index" && -f "$FC/uniprot_taxid.parquet" ]]; then
    echo "[compat] adding a Foldcomp tier 3 ($FC/$DB) to the old work list, with done markers for tiers 1-2"
    cp "$T/A/worklist.parquet" "$T/A/skip_accessions.txt" "$T/C/"
    mkdir -p "$T/C/state/done" "$T/C/state/failed"
    "$PY" - "$T/C" <<'EOF'
import json, sys
import pandas as pd
root = sys.argv[1]
wl = pd.read_parquet(f"{root}/worklist.parquet")
for r in wl.itertuples():
    json.dump({"unit_id": r.unit_id, "tier": r.tier, "source": r.source}, open(f"{root}/state/done/{r.unit_id}.json", "w"))
json.dump({"unit_id": len(wl), "tier": 3, "error": "old GCS failure"}, open(f"{root}/state/failed/{len(wl)}.json", "w"))
EOF
    OUT_ROOT="$T/C" FOLDCOMP_DIR="$FC" FOLDCOMP_DB="$DB" TIER3_SOURCE=foldcomp \
        "$PY" "$AFDB_DIR/make_worklist.py" --tiers 1,2,3 2>&1 | grep -E "previous|moved|tier [0-9]:"
    "$PY" - "$T/A/worklist.parquet" "$T/C/worklist.parquet" "$T/C" <<'EOF'
import sys
from pathlib import Path
import pandas as pd
a, c = pd.read_parquet(sys.argv[1]), pd.read_parquet(sys.argv[2])
c12 = c[c.tier <= 2].reset_index(drop=True)
assert c12.drop(columns=["source_taxids", "source_sizes"]).equals(a.drop(columns=["source_taxids", "source_sizes"]))
assert [list(x) for x in c12.sources] == [list(x) for x in a.sources]
assert [list(x) for x in c12.source_taxids] == [list(x) for x in a.source_taxids]
t3 = c[c.tier == 3]
assert len(t3) and t3.unit_id.min() == a.unit_id.max() + 1 and (t3.source_type == "foldcomp").all()
assert not list(Path(sys.argv[3], "state/failed").glob("*.json")), "the old tier-3 failed marker was not moved"
print(f"[compat] tier-1/2 rows identical ({len(a)} units); tier 3: {len(t3)} Foldcomp units from unit_id "
      f"{t3.unit_id.min()}; old failed marker moved to state/superseded/")
EOF
else
    echo "[compat] could not build the tiny Foldcomp DB: tier-3 part FAILED" >&2; exit 1
fi
rm -rf "$T"
echo "[compat] PASSED"
