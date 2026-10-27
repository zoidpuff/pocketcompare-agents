#!/bin/bash
# BLiPS + PPIPS label-free descriptors (A1 x16, B1 all, B0); completion marker logs/blips_ppips_desc.done
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
set -e
for ds in blips blips_test_holo blips_test_af ppips; do
  for arm in a1 b1 b0; do
    echo "=== $ds $arm $(date +%T)"
    python scripts/compute_descriptors.py --dataset $ds --arm $arm --config all --mode both --workers 23
  done
done
date +%F_%T > logs/blips_ppips_desc.done
