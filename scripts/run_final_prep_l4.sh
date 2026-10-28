#!/bin/bash
# Label-free N1 (a1r) inputs + L4 point sets for the sealed external sets, then B0' refresh on the rebuilt splits.
# Marker: logs/final_prep_l4.done
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
set -e
for ds in prospeccts vertex; do
  echo "=== $ds a1r $(date +%T)"; python scripts/compute_descriptors.py --dataset $ds --arm a1r --mode both --workers 22 --label-free-structures
  echo "=== $ds l4 points $(date +%T)"; python scripts/l4_extract.py --dataset $ds --workers 22
done
echo "=== b0prime $(date +%T)"; python scripts/data/b0prime_foldseek.py --sets tough_m1_test,tough_m1_dev,blips_val --threads 22
date +%F_%T > logs/final_prep_l4.done
