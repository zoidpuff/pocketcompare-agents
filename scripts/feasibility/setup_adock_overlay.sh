#!/usr/bin/env bash
# Cheapest route to run ADock (read-only sibling repo) from our container: reuse our project .venv (torch 2.6+cu124,
# rdkit, scipy, numpy, gemmi) and add the 4 missing pure-pip packages into a node-local overlay (~290 MB, ~10 s).
# The sibling's conda_envs/dock is a dangling symlink to /tmp/adock/envs/dock (node-local on another node): unusable.
# CUDA >= 12.8 is only needed for sm_120 (Blackwell); RTX 4090 = sm_89 works with cu124 torch + cupy-cuda12x, whose
# NVRTC comes from our venv's nvidia-cuda-nvrtc-cu12 wheel. Driver here: 580.178 (CUDA 13.0).
# Re-run on every new node (/tmp is not persistent).
set -euo pipefail
PC=/cluster/project/beltrao/gmagnus/pocket_compare
source "$PC/.venv/bin/activate"
mkdir -p /tmp/adock
uv pip install --target /tmp/adock/overlay --no-deps cupy-cuda12x==14.2.0 fastrlock==0.8.4 meeko==0.8.0 cuda-pathfinder==1.8.4
cat <<'MSG'
Then, in each shell:
  source /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/activate
  export NUMBA_CACHE_DIR=/tmp/numba_cache CUPY_CACHE_DIR=/tmp/adock/cupy_cache
  export PYTHONPATH=/tmp/adock/overlay:/cluster/work/beltrao/buhmanju/agentic_ai/workspaces/hackathon/autoresearch_docking/src
MSG
