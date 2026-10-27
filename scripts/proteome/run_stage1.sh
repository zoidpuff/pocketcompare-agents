#!/bin/bash
# AFDB human proteome demo, stage 1 (BURROW + raw tier-1 descriptors) and the backend benchmark.
# Detached:  setsid nohup bash scripts/proteome/run_stage1.sh > logs/proteome_stage1.log 2>&1 &
# Marker: logs/proteome_stage1.done
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
P=data/processed/proteome_human
set -x
echo "start $(date +%F_%T) load $(cut -d' ' -f1-3 /proc/loadavg)"
# 1. full proteome: fast GPU backend, 2 GPUs x 11 CPU workers
python scripts/proteome/run_proteome.py --out $P/run_gpu --backend gpu --devices cuda:2,cuda:3 --workers-per-gpu 11 --batch 32 --shard 500
# 2. backend benchmark on the same random 1,000 models (seed 0), one after the other on the same node
for b in gpu fastcpu refcpu; do
  rm -rf $P/bench_$b
  python scripts/proteome/run_proteome.py --out $P/bench_$b --backend $b --devices cuda:2,cuda:3 --workers-per-gpu 11 --workers 22 --limit 1000 --sample 0 --shard 250
done
echo "end $(date +%F_%T) load $(cut -d' ' -f1-3 /proc/loadavg)"
date +%F_%T > logs/proteome_stage1.done
