
# pocketcompare — fast, fold-independent pocket similarity on BURROW

`pocketcompare` turns every BURROW pocket of a protein structure (a PDB entry, an AlphaFold model or a predicted
dimer) into a 384-d unit vector. Two pockets are compared by cosine, and large collections are searched with FAISS.
The descriptor is ligand-free and uses neither sequence nor fold.

The final method is **A4b:n1_linear**: a linear, 3-seed contrastive projection of A1(sph8) + env(sph8). It is
configured in `configs/final_method.yaml`, and the config, weights and statistics are sha256-verified on load.
Cost is ≈ 3.5 ms per pocket after BURROW and ≈ 0.1 µs per pair in batched search.

See `REPORT.md` for the method, results and limitations. Test-set results are pending the final evaluation.

## Install

Requirements:
- Python ≥ 3.11 (tested with 3.12.3) and `uv`.
- BURROW (`pocketdetect`, from `../pocket_detect/src`). It is imported through a `.pth` file, not installed.

```bash
cd pocket_compare
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e .                      # pyproject declares no dependencies; install them explicitly:
uv pip install numpy scipy pandas pyarrow scikit-learn numba gemmi rdkit pyyaml networkx
uv pip install faiss-gpu-cu12            # or faiss-cpu
uv pip install torch                     # needed only to train A4b/L4 or run L4
uv pip install transformers              # needed only for the B4 ESM-2 baseline
echo "$(realpath ../pocket_detect/src)" > .venv/lib/python3.12/site-packages/pocketdetect.pth
export NUMBA_CACHE_DIR=/tmp/numba_cache
pytest tests/test_method.py              # API tests (two need the 1a28 example + PDB mirror)
```

Tested versions: numpy 2.5.4, pandas 3.1.0, pyarrow 26.0.0, scipy 1.18.1, scikit-learn 1.9.1, numba 0.68.0,
gemmi 0.7.5, rdkit 2026.9.1, pyyaml 6.0.3, networkx 3.7, torch 2.6.0, faiss-gpu-cu12 1.14.1.

Rebuilding the splits also needs MMseqs2 and Foldseek, whose binaries are in `tools/` (see `tools/SHA256SUMS`).
Dataset sources, versions, checksums and licences are listed in `DATA.md`. ProSPECCTs must never be
redistributed.

## Quickstart (Python API)

There is no command-line wrapper. The API lives in `src/pocketcompare/method.py`.

```python
from pocketcompare import method

# 1. Every BURROW pocket of a structure (deployment / "D" mode): one row per region-rule pocket
V, info = method.describe("1abc.cif.gz", return_info=True)        # V: (n, 384) float32; info: burrow_rank, volume_A3, ok, time_ms
W = method.describe("AF-P00918-F1-model_v6.cif.gz", af_mode=True)  # AlphaFold model (BURROW AF mode)

# 2. A known site
v = method.describe("1abc.cif.gz", site="ligand.sdf")              # ligand file (.sdf/.mol V2000 or .pdb HETATM)
v = method.describe("1abc.cif.gz", site=xyz)                       # (n, 3) ligand heavy-atom coordinates
v = method.describe("1abc.cif.gz", site=["A:719", "A:725"])        # residue list "chain:num"
v = method.describe("1abc.cif.gz", site="ligand.sdf", locate="burrow")  # describe the BURROW pocket that covers the ligand

# 3. Compare
s = method.similarity(v[0], W[0])     # float, cosine (higher = more similar)
S = method.similarity(v, V)           # (1, n) matrix
```

Notes:
- `describe` accepts a path, a loaded gemmi `Structure` or a pre-featurised `pockets.Featurized`.
- Dimers are passed as ordinary two-chain files. Use `chains=` to restrict the chains.
- `pockets="region" | "v2" | "full"` selects BURROW's pocket list; the default is `region`.
- Rows with `info.ok == False` are zero vectors (no buried points).
- The first call pays for imports and Numba compilation, ~15 s on our nodes. Later calls cost BURROW time plus
a few ms per pocket.

## Build a FAISS index over a directory

```python
import glob, numpy as np, pandas as pd, faiss
from pocketcompare import method

vecs, meta = [], []
for f in sorted(glob.glob("structures/*.cif.gz")):
  V, info = method.describe(f, af_mode=True, return_info=True)   # af_mode=True for AlphaFold models
  info["structure"] = f
  keep = info["ok"].to_numpy()
  vecs.append(V[keep]); meta.append(info[keep])
X = np.vstack(vecs).astype(np.float32)
meta = pd.concat(meta, ignore_index=True)

index = faiss.IndexFlatIP(X.shape[1])         # exact cosine (vectors are unit-norm)
index.add(X)
faiss.write_index(index, "pockets.faiss"); meta.to_parquet("pockets_meta.parquet")

q = method.describe("query.pdb", site="ligand.sdf").astype(np.float32)
D, I = index.search(q, 10)                    # top-10 similar pockets
print(meta.iloc[I[0]][["structure", "burrow_rank", "volume_A3"]].assign(score=D[0]))
```

For millions of pockets, use a compressed index with exact re-ranking:
- e.g. `faiss.index_factory(384, "OPQ64,IVF4096,PQ64", faiss.METRIC_INNER_PRODUCT)`;
- train it on ~100 k vectors;
- search with `nprobe` 16–64, then re-rank the top-100 against fp16 copies of the vectors.

On the human proteome demo (627-d N1 vectors), 64-byte codes alone gave recall@10 0.81–0.85, and re-ranking gave
0.995. This has not yet been re-measured for the 384-d final vectors. The proteome pipeline itself is in
`scripts/proteome/`.

## Reproduce

Run everything from the project root with `.venv` active and `NUMBA_CACHE_DIR` set. Long jobs should run detached
(see LESSONS.md). Sealed test labels live in `data/sealed/` (chmod 000) and are read only by
`scripts/final_eval.py`.

1. **Public benchmarks**
 - `python scripts/data/fetch_{prospeccts,tough_m1,vertex,tough_c1,klifs}.py`
 - `python scripts/data/build_benchmarks.py`
 - `python scripts/data/check_benchmarks.py`
2. **PPI data**
 - `bash scripts/ppi/run_all.sh` (dimer characterisation)
 - `bash scripts/ppi/run_ppi_datasets.sh` (PPI-L + PPIPS; seals their test files)
3. **BLiPS sites**
 - `python scripts/data/prep_blips_pockets.py --part trainval`
 - `python scripts/data/prep_blips_pockets.py --part test`
4. **BURROW point caches (label-free)**
 - `python scripts/build_point_cache.py --dataset {tough_m1,blips,blips_test_holo,blips_test_af} --workers 32`
 - `bash scripts/run_final_prep_cache.sh` (ProSPECCTs/Vertex with `--label-free-structures`)
5. **Homology graph and all splits** (~1.5 h): `bash scripts/data/run_splits.sh`
 - This runs `build_homology_graph.py`, `make_tough_m1_split.py`, `make_blips_split.py`,
   `blips_test_exclusions.py`, `make_blips_resplit_v2.py`, `scripts/ppi/21_ppips_homology.py`,
   `scripts/ppi/22_ppips_build.py`, `ppips_burrow_flags.py`, `verify_splits.py` and `split_sensitivity.py`.
6. **Descriptors**
 - `python scripts/compute_descriptors.py --dataset tough_m1 --arm {a1,b1} --config all --mode both --workers 12`
   and `--arm b0 --mode both`
 - `bash scripts/run_blips_ppips_desc.sh`
 - `python scripts/compute_esm.py --dataset tough_m1`
 - `bash scripts/run_blips_ppips_esm.sh`
 - `python scripts/compute_n_inputs.py --dataset <ds> --workers 22`
 - `bash scripts/run_final_prep_desc.sh`
 - EPoCS: `envs/run_epocs_full.sh`, then `scripts/collect_epocs.py`
7. **A2 fragment docking** (gated, negative)
 - `python scripts/a2/build_panels.py --stage pool`, then `--stage pick`
 - `python scripts/a2/prep_pockets.py`
 - `scripts/a2/run_dock.sh raw_L L 0` (and D mode; `A2_DATASET=ppips` for PPIPS)
 - `python scripts/a2/aggregate.py`
 - `python scripts/a2/build_descriptors.py`
8. **Dev evaluation**
 - `python scripts/eval_dev.py --dataset {tough_m1,blips,ppips} --out-suffix _v2splits --trial-tag splits_v2`
9. **A4b**
 - `python scripts/train_a4b.py --all --devices cuda:0,cuda:1`
 - `python scripts/eval_dev.py --dataset final_select --candidates all`
10. **L4**: `L4_AUDIT_PASSED=1 bash scripts/run_l4.sh`
  - This runs `l4_extract.py`, `train_l4.py --all`, `bench_l4.py` and `eval_l4.py`; `eval_l4.py --with-a4b` runs
    the joint selection.
11. **Final method config**: `python scripts/write_final_method.py --selection results/dev/final_select_pi.json`
  (writes `configs/final_method.yaml`)
12. **Runtime, robustness, blind dry run**
  - `python scripts/bench_method.py --n-structures 200`
  - `python scripts/eval_af_robustness.py --set val`
  - `python scripts/eval_blind.py --set val`
13. **Proteome demo**
  - `python scripts/proteome/index_tar.py`
  - `bash scripts/proteome/run_stage1.sh`
  - `bash scripts/proteome/run_cpu_backends.sh`
  - `python scripts/proteome/index_search.py`
  - `python scripts/proteome/sanity_jitter.py`
  - `python scripts/proteome/sanity_family.py`
  - `python scripts/proteome/summarize.py`
  - `python scripts/proteome/write_sidecars.py`
14. **Final evaluation** (PI only)
  - `python scripts/final_eval.py --dryrun-dev`
  - commit, then `python scripts/final_eval.py --write-freeze`
  - commit FREEZE.json
  - `FINAL_EVAL=1 python scripts/final_eval.py --check-only`
  - `FINAL_EVAL=1 python scripts/final_eval.py --threads 16`
  - optionally `FINAL_EVAL=1 python scripts/eval_af_robustness.py --set test --pairs <...>` and
    `scripts/eval_blind.py --set test --pairs <...>`
15. **Report check**: `python scripts/check_report.py REPORT.md`

Every result file has a `.prov.json` sidecar recording commit, inputs, seeds and the evaluate.py hash. The seeds
