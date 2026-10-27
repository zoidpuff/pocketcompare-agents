#!/bin/bash
# Full human proteome with the two CPU backends (throughput comparison + full-scale equivalence of outputs).
# Detached: setsid nohup bash scripts/proteome/run_cpu_backends.sh > logs/proteome_cpu_backends.log 2>&1 &
# Marker: logs/proteome_cpu_backends.done
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
P=data/processed/proteome_human
for b in fastcpu refcpu; do
  echo "$b start $(date +%F_%T) load $(cut -d' ' -f1-3 /proc/loadavg)"
  python scripts/proteome/run_proteome.py --out $P/run_$b --backend $b --workers 22 --shard 500
done
date +%F_%T > logs/proteome_cpu_backends.done
