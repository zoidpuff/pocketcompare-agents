#!/bin/bash
# EXPLORATORY (post-test) dimer interface-pocket atlas: describe all 15,161 AFDB dimers with the final method (CLI,
# AF mode, fast GPU backend), two shards on cuda:0 / cuda:1, 11 CPU workers each (22 total).
set -e
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
D=/cluster/project/beltrao/gmagnus/dimers
O=data/processed/dimer_atlas
date +%s > $O/start_epoch
( /usr/bin/time -v pocketcompare describe $D/afdb_human_dimers/homodimers $D/afdb_yeast_dimers $D/afdb_ecoli_dimers/homodimers \
    --af-mode --device cuda:0 --workers 11 -o $O/shard0.parquet ) > logs/dimer_atlas_shard0.log 2>&1 &
( /usr/bin/time -v pocketcompare describe $D/afdb_human_dimers/heterodimers $D/afdb_ecoli_dimers/heterodimers \
    --af-mode --device cuda:1 --workers 11 -o $O/shard1.parquet ) > logs/dimer_atlas_shard1.log 2>&1 &
wait
date +%s > $O/end_epoch
