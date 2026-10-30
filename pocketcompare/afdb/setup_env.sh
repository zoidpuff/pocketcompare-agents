#!/usr/bin/env bash
# Build (or check) the pocketcompare AFDB environment. Idempotent: re-running only installs what is missing.
#   bash afdb/setup_env.sh            # on the Euler host (login node is fine; GPU self-test runs if a GPU is visible)
#   FORCE=1 bash afdb/setup_env.sh    # recreate the venv from scratch
# Uses uv-managed CPython (installed under $UV_PYTHON_INSTALL_DIR on project storage), never the system Python,
# so the same venv works on the Euler host and inside containers that mount /cluster/project.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

say() { echo "[setup_env] $*"; }

# ---- uv
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    say "installing uv to ~/.local/bin"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$HOME/.local/bin" INSTALLER_NO_MODIFY_PATH=1 sh
fi
say "uv: $(command -v uv) ($(uv --version))"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/uv-cache-$(id -un)}"
export UV_LINK_MODE=copy            # cache and venv are on different file systems

# ---- uv-managed CPython + venv
mkdir -p "$UV_PYTHON_INSTALL_DIR" "$(dirname "$ENV_DIR")"
uv python install "$PYTHON_VERSION"
PY=$(uv python find --managed-python "$PYTHON_VERSION")
say "python: $PY"
if [[ "${FORCE:-0}" == 1 && -d "$ENV_DIR" ]]; then say "FORCE=1: removing $ENV_DIR"; rm -rf "$ENV_DIR"; fi
if [[ ! -x "$ENV_DIR/bin/python" ]]; then
    uv venv --python "$PY" --managed-python "$ENV_DIR"
fi
case "$(readlink -f "$ENV_DIR/bin/python")" in
    "$UV_PYTHON_INSTALL_DIR"/*) ;;
    *) echo "ERROR: $ENV_DIR/bin/python -> $(readlink -f "$ENV_DIR/bin/python") is not uv-managed; FORCE=1 to rebuild" >&2; exit 1 ;;
esac
export VIRTUAL_ENV="$ENV_DIR"
UVPIP=(uv pip install --python "$ENV_DIR/bin/python")

# ---- GPU stack first (cu124 wheels; same versions as development: torch 2.6.0+cu124, triton 3.2.0)
if ! "$ENV_DIR/bin/python" -c "import torch, triton; assert torch.__version__.startswith('$TORCH_VERSION')" 2>/dev/null; then
    "${UVPIP[@]}" --index-url "$TORCH_INDEX" "torch==$TORCH_VERSION" "triton==$TRITON_VERSION"
fi

# ---- BURROW (read-only source tree: build from a temporary copy of the files a wheel needs)
want_burrow=$(sed -n 's/^version = "\(.*\)"/\1/p' "$BURROW_SRC/pyproject.toml" | head -1)
have_burrow=$("$ENV_DIR/bin/python" -c "import importlib.metadata as m; print(m.version('burrow-pockets'))" 2>/dev/null || true)
if [[ "$have_burrow" != "$want_burrow" || "${FORCE_BURROW:-0}" == 1 ]]; then
    tmp=$(mktemp -d)
    cp -r "$BURROW_SRC/pyproject.toml" "$BURROW_SRC/README.md" "$BURROW_SRC/LICENSE" "$BURROW_SRC/src" "$tmp/"
    find "$tmp" -name __pycache__ -prune -exec rm -rf {} +
    "${UVPIP[@]}" --reinstall-package burrow-pockets "$tmp"
    rm -rf "$tmp"
fi

# ---- pocketcompare[search] (non-editable: the venv keeps working if the checkout changes)
if [[ "$POCKETCOMPARE_SRC" == git+* ]]; then pc_spec="pocketcompare[search] @ $POCKETCOMPARE_SRC"; else
    pc_spec="pocketcompare[search] @ file://$POCKETCOMPARE_SRC"; fi
# reinstall only when the package itself changed (src/, configs/, models/, pyproject.toml): commits to afdb/ do not
# trigger a reinstall, so re-running this script never swaps files under running jobs for nothing. The stamp holds
# a commit; it matches if that commit has the same package trees (src, configs, models, pyproject.toml).
pkg_id() { (cd "$AFDB_DIR/.." && git rev-parse "$1:src" "$1:configs" "$1:models" "$1:pyproject.toml" 2>/dev/null) | sha1sum; }
want_pc=$(cd "$AFDB_DIR/.." && git rev-parse HEAD 2>/dev/null || echo unknown)
stamp="$ENV_DIR/.pocketcompare_installed_from"
have_pc=$(cat "$stamp" 2>/dev/null || true)
if ! "$ENV_DIR/bin/python" -c "import pocketcompare, faiss" 2>/dev/null || [[ -z "$have_pc" ]] || \
   [[ "$(pkg_id "$have_pc")" != "$(pkg_id HEAD)" ]]; then
    "${UVPIP[@]}" --reinstall-package pocketcompare "$pc_spec"
    echo "$want_pc" > "$stamp"
fi
# small helpers used by the AFDB tools (already dependencies, listed for clarity)
"${UVPIP[@]}" --quiet "pyarrow==26.0.0" "pandas==3.1.0" "numpy==2.5.4"
# tier 3 from Foldcomp: decompression (foldcomp) and the 214 M-entry work list (duckdb)
"${UVPIP[@]}" --quiet "foldcomp==1.0.0" "duckdb==2.0.0"

# ---- warm the Numba cache (shared; afdb.sbatch copies it to node-local $TMPDIR)
export NUMBA_CACHE_DIR="$ENV_DIR/numba_cache"
mkdir -p "$NUMBA_CACHE_DIR"
EXAMPLE="$POCKETCOMPARE_SRC/examples/afdb/AF-P00918-F1-model_v6.cif.gz"
[[ -f "$EXAMPLE" ]] || EXAMPLE=$(ls "$AFDB_DIR"/../examples/afdb/*.cif.gz | head -1)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
say "self-test (CPU, fast backend; first run compiles the Numba kernels)"
t0=$(date +%s)
"$ENV_DIR/bin/pocketcompare" describe "$EXAMPLE" --af-mode --backend fast -o "$work/cpu.parquet"
"$ENV_DIR/bin/pocketcompare" describe "$EXAMPLE" --af-mode --backend ref -o "$work/ref.parquet"
say "CPU self-test done in $(( $(date +%s) - t0 )) s"
gpu=0
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1 && \
   "$ENV_DIR/bin/python" -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    gpu=1
    say "self-test (GPU cuda:0)"
    "$ENV_DIR/bin/pocketcompare" describe "$EXAMPLE" --af-mode --device cuda:0 -o "$work/gpu.parquet"
else
    say "no GPU visible: GPU self-test skipped (run setup_env.sh again on a GPU node to test it)"
fi
"$ENV_DIR/bin/python" - "$work" "$gpu" <<'EOF'
import sys, numpy as np
from pocketcompare import fpindex as FX
w, gpu = sys.argv[1], sys.argv[2] == "1"
_, R, rec = FX.read_table(f"{w}/ref.parquet")
for name in ["cpu"] + (["gpu"] if gpu else []):
    _, V, _ = FX.read_table(f"{w}/{name}.parquet")
    d = float(np.abs(V - R).max()) if V.shape == R.shape else float("inf")
    print(f"[setup_env] {name} vs ref: {len(V)} pockets, max |diff| {d:.2e}")
    assert d <= 1e-5, f"{name} backend disagrees with the reference backend"
print("[setup_env] method:", rec.get("method"), "config sha256", rec.get("config_sha256", "")[:12])
EOF

# ---- versions
"$ENV_DIR/bin/python" - <<'EOF'
import sys, importlib.metadata as m
pk = ["pocketcompare", "burrow-pockets", "numpy", "scipy", "pandas", "pyarrow", "numba", "llvmlite", "gemmi",
      "lightgbm", "faiss-cpu", "torch", "triton", "foldcomp", "duckdb"]
print("[setup_env] python", sys.version.split()[0], sys.executable)
print("[setup_env] " + "  ".join(f"{p}={m.version(p)}" for p in pk))
import torch
print("[setup_env] torch CUDA", torch.version.cuda, "| GPUs visible:", torch.cuda.device_count())
EOF
say "OK: activate with  source $ENV_DIR/bin/activate"
