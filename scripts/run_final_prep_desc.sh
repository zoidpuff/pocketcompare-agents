#!/bin/bash
# Label-free descriptors for final evaluation (runs after logs/final_prep_cache.done).
# CPU: A1 (pair_only, default) / B1 (all) / B0 for prospeccts + vertex; N1/N2 input blocks for every evaluated set.
# GPU (cuda:1, serial, short): B4 ESM-2 for prospeccts + vertex.   Marker: logs/final_prep_desc.done
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
set -e
while [ ! -f logs/final_prep_cache.done ]; do sleep 30; done
for ds in prospeccts vertex; do
  echo "=== $ds a1 $(date +%T)"; python scripts/compute_descriptors.py --dataset $ds --arm a1 --config pair_only,default --mode both --workers 22 --label-free-structures
  echo "=== $ds b1 $(date +%T)"; python scripts/compute_descriptors.py --dataset $ds --arm b1 --config all --mode both --workers 22 --label-free-structures
  echo "=== $ds b0 $(date +%T)"; python scripts/compute_descriptors.py --dataset $ds --arm b0 --mode both --workers 22 --label-free-structures
  echo "=== $ds n_inputs $(date +%T)"; python scripts/compute_n_inputs.py --dataset $ds --workers 22 --label-free-structures
done
for ds in tough_m1 blips blips_test_holo blips_test_af; do
  echo "=== $ds n_inputs $(date +%T)"; python scripts/compute_n_inputs.py --dataset $ds --workers 22
done
for ds in prospeccts vertex; do
  echo "=== $ds esm $(date +%T)"; python scripts/compute_esm.py --dataset $ds --device cuda:1 --label-free-structures
done
date +%F_%T > logs/final_prep_desc.done
