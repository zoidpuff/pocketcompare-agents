#!/bin/bash
# Label-free point caches for the sealed external sets (structures + pocket tables only; no labels).
# Completion marker: logs/final_prep_cache.done
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
set -e
for ds in prospeccts vertex; do
  echo "=== cache $ds $(date +%T)"
  python scripts/build_point_cache.py --dataset $ds --label-free-structures --workers 22
done
date +%F_%T > logs/final_prep_cache.done
