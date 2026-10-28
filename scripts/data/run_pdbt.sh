#!/bin/bash
# PDB-T build (PREREG2; scripts/data/build_pdbt.py docstring).  <= 24 CPU threads, no GPU, no method output.
# Order: enumerate -> CCD -> sites -> leakage/homology -> label-free pocket table + point cache ->
#        pairs + gate + seal (one step) -> label-free descriptors for the frozen arms.
cd /cluster/project/beltrao/gmagnus/pocket_compare
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1
set -e
python scripts/data/pdbt_enumerate.py --workers 24
python scripts/data/build_pdbt.py --stage ccd
python scripts/data/build_pdbt.py --stage sites --workers 24
python scripts/data/pdbt_homology.py --threads 24
python scripts/data/build_pdbt.py --stage pockets
python scripts/build_point_cache.py --dataset pdbt --workers 22
python scripts/data/build_pdbt.py --stage pairs          # writes results/pdbt/gate.json, then seals the pairs
# label-free descriptors (point cache only; never the sealed pairs)
python scripts/compute_descriptors.py --dataset pdbt --arm a1r --mode both --workers 22
python scripts/compute_descriptors.py --dataset pdbt --arm b1 --config default --mode both --workers 22
python scripts/compute_descriptors.py --dataset pdbt --arm b0 --mode both --workers 22
python scripts/compute_descriptors.py --dataset pdbt --arm a1 --config pair_only,default --mode both --workers 22
python scripts/compute_n_inputs.py --dataset pdbt --workers 22
python scripts/l4_extract.py --dataset pdbt --workers 22
date +%F_%T > logs/pdbt_build.done
