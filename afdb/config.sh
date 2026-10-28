# pocketcompare over the AlphaFold DB on Euler: every path and knob in one place.
# Sourced by setup_env.sh, submit.sh, afdb.sbatch and smoke_test.sh. Every value can be overridden from the
# environment (e.g. `OUT_ROOT=/some/dir bash submit.sh`); the Python tools read the same variables.

AFDB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"            # this folder (afdb/)

# ---- storage
export OUT_ROOT="${OUT_ROOT:-/cluster/scratch/gmagnusson/pocketcompare_afdb}"   # purged by age: copy finished tiers away
export ENV_DIR="${ENV_DIR:-/cluster/project/beltrao/gmagnus/pocket_compare/envs/pocketcompare-afdb}"
# uv-managed CPython lives on project storage so the same venv works inside containers and on the Euler host
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/cluster/project/beltrao/gmagnus/pocket_compare/envs/uv-python}"
export PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

# ---- inputs and code
export AFDB_LOCAL="${AFDB_LOCAL:-/cluster/work/beltrao/shared/alphafold/v6}"          # 46 proteome tars + Swiss-Prot
export GCS_BUCKET="${GCS_BUCKET:-public-datasets-deepmind-alphafold-v4}"              # the rest of AFDB (v3/v4 models)
export BURROW_SRC="${BURROW_SRC:-/cluster/project/beltrao/gmagnus/pocket_detect/release/burrow}"   # read-only is fine
export POCKETCOMPARE_SRC="${POCKETCOMPARE_SRC:-$(cd "$AFDB_DIR/.." && pwd)}"   # or git+https://github.com/zoidpuff/pocketcompare
export TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu124}"
export TORCH_VERSION="${TORCH_VERSION:-2.6.0}"
export TRITON_VERSION="${TRITON_VERSION:-3.2.0}"

# ---- tier 3 downloads (GCS). Anonymous downloads were denied (HTTP 403) on 2026-10-28 although listing worked:
# set GCS_AUTH_CMD (e.g. 'gcloud auth print-access-token') and, for a requester-pays bucket, GCS_USER_PROJECT.
export GCS_BASE_URL="${GCS_BASE_URL:-https://storage.googleapis.com/$GCS_BUCKET}"   # or a mirror
export GCS_AUTH_CMD="${GCS_AUTH_CMD:-}"                # command printing an OAuth bearer token (empty = anonymous)
export GCS_USER_PROJECT="${GCS_USER_PROJECT:-}"        # billing project for requester-pays access (empty = none)
export GCS_FETCH_THREADS="${GCS_FETCH_THREADS:-32}"    # parallel downloads of small tars (most hold 1-10 models)
export GCS_SMALL_BYTES="${GCS_SMALL_BYTES:-16777216}"  # tars up to this size are fetched whole; larger ones streamed

# ---- per-node parallelism (measured: 4 shards x 15 workers ~ 380 structures/s on 64 cores + 4 x RTX 4090)
export SHARDS_PER_NODE="${SHARDS_PER_NODE:-4}"        # concurrent `pocketcompare describe` runs = GPUs used
export WORKERS_PER_SHARD="${WORKERS_PER_SHARD:-15}"   # CPU worker processes per describe run
export GPU_BATCH="${GPU_BATCH:-16}"                    # structures per GPU featurisation batch (describe --batch)
export BATCH_STRUCTURES="${BATCH_STRUCTURES:-4000}"    # structures per describe call (one $TMPDIR batch dir)
export PREFETCH_BATCHES="${PREFETCH_BATCHES:-4}"       # extracted batches waiting for a free GPU slot
export EXTRACT_THREADS="${EXTRACT_THREADS:-4}"         # units extracted/downloaded concurrently per node
export RUNNER="${RUNNER:-persistent}"                  # persistent (describe_server.py) | cli (pocketcompare describe per batch)

# ---- work units (make_worklist.py)
export UNIT_STRUCTURES="${UNIT_STRUCTURES:-4000}"      # local tars: models per unit; GCS tars are packed to ~this
export GCS_UNIT_MAX_TARS="${GCS_UNIT_MAX_TARS:-2000}"  # at most this many (small) GCS tars per unit
export GCS_BYTES_PER_MODEL="${GCS_BYTES_PER_MODEL:-0}" # 0 = calibrated default (120.9 kB/model in the v4 tars)
export TAR_INDEX_DIR="${TAR_INDEX_DIR:-$OUT_ROOT/tar_index}"   # member index of the local tars (built once)
export NCBI_DIR="${NCBI_DIR:-$OUT_ROOT/ncbi}"                  # NCBI new_taxdump (rankedlineage.dmp, merged.dmp)

# ---- pocket filters (worker.py; counts dropped by each rule are recorded per unit)
export MIN_POINTS="${MIN_POINTS:-10}"                  # merged BURROW pocket size (method default)
export MIN_SCORE="${MIN_SCORE:-0.03}"                  # BURROW score floor
export MIN_PLDDT="${MIN_PLDDT:-70}"                    # mean pLDDT of the lining residues

# ---- robustness
export STALE_HOURS="${STALE_HOURS:-24}"                # a claim older than this is reclaimed even if its job runs
export HTTP_RETRIES="${HTTP_RETRIES:-8}"               # GCS download attempts per tar (restart + skip done members)
export HTTP_TIMEOUT="${HTTP_TIMEOUT:-300}"             # seconds without data before a GCS request is retried
export DESCRIBE_RETRIES="${DESCRIBE_RETRIES:-1}"       # re-runs of a failed describe call

# ---- threads: one per worker process (without these caps one shard runs 2x slower)
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

# ---- SLURM (afdb.sbatch reads the account/partition from its #SBATCH lines; these are for submit.sh)
export SLURM_NODES="${SLURM_NODES:-4}"                 # array tasks = nodes
