#!/bin/bash
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate
set -e
for ds in blips blips_test_holo blips_test_af ppips; do
  echo "=== $ds $(date +%T)"
  python scripts/compute_esm.py --dataset $ds --device cuda:1
done
date +%F_%T > logs/blips_ppips_esm.done
