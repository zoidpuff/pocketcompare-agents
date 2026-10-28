
# pocketcompare — fast, fold-independent pocket similarity on BURROW

`pocketcompare` turns every BURROW pocket of a protein structure (a PDB entry, an AlphaFold model or a predicted
dimer) into a 384-d unit vector. Two pockets are compared by cosine, and large collections are searched with FAISS.
The descriptor is ligand-free and uses neither sequence nor fold.

The final method is **A4b:n1_linear**: a linear, 3-seed contrastive projection of A1(sph8) + env(sph8). It is
configured in `configs/final_method.yaml`, and the config, weights and statistics are sha256-verified on load.
Cost is ≈ 3.5 ms per pocket after BURROW and ≈ 0.1 µs per pair in batched search.

See `REPORT.md` for the method, results and limitations. Test-set results: see REPORT.md.

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

## Command line

`pip install -e .` installs the console script `pocketcompare` (also `python -m pocketcompare`).
Handover notes for downstream users are in `docs/FINGERPRINTS.md`.

```bash
pocketcompare describe structures/ --af-mode --workers 22 -o pockets.parquet   # every pocket of every structure
pocketcompare describe structures/ --af-mode --device cuda:0 --workers 22 -o pockets.parquet   # BURROW on the GPU
pocketcompare describe 1abc.cif.gz --ligand lig.sdf -o site.parquet           # one ligand-defined site (L mode)
pocketcompare describe 1abc.cif.gz --residues A:719,A:725 --locate burrow -o d.parquet   # BURROW pocket at a site
pocketcompare compare site.parquet pockets.parquet --top 5 -o pairs.tsv       # or two structures; --matrix S.npy
pocketcompare index pockets.parquet -o idx_flat/                              # exact (IndexFlatIP)
pocketcompare index pockets.parquet -o idx_pq/ --kind ivfpq                   # OPQ64 + IVF + PQ64 + fp16 re-rank vectors
pocketcompare search site.parquet idx_pq/ -k 10 --rerank 100 -o hits.parquet
```

- `describe` writes one row per pocket: `pocket_id`, `burrow_rank`, `burrow_score`, `members`, `residues`,
  `center_{x,y,z}`, `volume_A3`, `site_volume_A3`, `plddt_{mean,min,frac_lt70}` (with `--af-mode`), `ok` and
  the 384-d `fingerprint`. A sidecar `<out>.structures.parquet` has the status and timings of each structure.
- The backends `--backend ref` (default), `--backend fast` and `--device cuda:N` give identical fingerprints.
- Read a table in Python with `pocketcompare.fpindex.read_table(path)`, which returns (metadata, (n, 384) array,
  method record).

## Quickstart (Python API)

The API lives in `src/pocketcompare/method.py`.

```python
from pocketcompare import method

# 1. Every pocket of a structure (deployment): merged BURROW region-rule pockets with >= 10 points
V, info = method.describe_all("1abc.cif.gz")                       # V: (n, 384) float32; info: burrow_rank, residues, center_*, ...
W, _ = method.describe_all("AF-P00918-F1-model_v6.cif.gz", af_mode=True)   # AlphaFold model (BURROW AF mode)

# 2. A known site
v = method.describe("1abc.cif.gz", site="ligand.sdf")              # ligand file (.sdf/.mol V2000 or .pdb HETATM)
v = method.describe("1abc.cif.gz", site=xyz)                       # (n, 3) ligand heavy-atom coordinates
v = method.describe("1abc.cif.gz", site=["A:719", "A:725"])        # residue list "chain:num"
v = method.describe("1abc.cif.gz", site="ligand.sdf", locate="burrow")  # the BURROW pocket at the ligand (D mode)

# 3. Compare
s = method.similarity(v[0], W[0])     # float, cosine (higher = more similar)
S = method.similarity(v, V)           # (1, n) matrix
```

Notes:
- **Which pockets `describe_all` describes.** BURROW region-rule pockets are merged (touch ≤ 1.5 Å or
  residue Jaccard ≥ 0.3). Merged pockets with fewer than 10 points are dropped. Each remaining merged pocket is
  described by sph8 around its bur16⁴ centroid. This is the unit of the proteome release and the blind test.
  - `unit="member"` describes every region sub-pocket instead. This equals `describe(structure)` with no site,
    which keeps the older behaviour.
- **`locate="burrow"` matches the evaluation's D mode.** The site picks the merged region pocket that covers it
  best. Then the member of that pocket that covers it best is described. `tests/test_method_eval_consistency.py`
  checks that this reproduces the evaluated L and D vectors (max |Δ| ≈ 1e-7).
  - `locate="burrow_flat"` is the pre-2026-10-28 rule: the best-covering region pocket, without the merge step.
- `describe` accepts a path, a loaded gemmi `Structure` or a pre-featurised `pockets.Featurized`.
- Dimers are passed as ordinary two-chain files. Use `chains=` to restrict the chains.
- `pockets="region" | "v2" | "full"` selects BURROW's pocket list for `describe(site=None)`; the default is
  `region`.
- Rows with `info.ok == False` are zero vectors (no buried points).
- The first call pays for imports and Numba compilation, ~15 s on our nodes. Later calls cost BURROW time plus
a few ms per pocket.

## Build a FAISS index over a directory

Use `pocketcompare describe` → `index` → `search` (see "Command line"); the library behind it is
`pocketcompare.fpindex`. By hand:

```python
import glob, numpy as np, pandas as pd, faiss
from pocketcompare import method

vecs, meta = [], []
for f in sorted(glob.glob("structures/*.cif.gz")):
  V, info = method.describe_all(f, af_mode=True)                 # af_mode=True for AlphaFold models
  info["structure"] = f
  keep = info["ok"].to_numpy()
  vecs.append(V[keep]); meta.append(info[keep])
X = np.vstack(vecs).astype(np.float32)
meta = pd.concat(meta, ignore_index=True)

index = faiss.IndexFlatIP(X.shape[1])         # exact: the vectors are unit-norm, score = inner product
index.add(X)
q = method.describe("query.pdb", site="ligand.sdf").astype(np.float32)
D, I = index.search(q, 10)                    # top-10 similar pockets
print(meta.iloc[I[0]][["structure", "burrow_rank", "residues"]].assign(score=D[0]))
```

For millions of pockets, use `pocketcompare index --kind ivfpq`. It builds `OPQ64_384,IVF{nlist},PQ64` (64-byte
codes) and keeps fp16 copies of the vectors, so `search` can re-rank the top-100 exactly. Recall on the human
release is given in the next section.

## Release: human AFDB v6 fingerprints

`data/processed/release/human_afdb_v6/` holds 116,246 final-method fingerprints in 19,084 UniProt entries. They are
the merged region-rule pockets (≥ 10 points) of all AFDB v6 human models.
- **Contents:** `fingerprints.parquet` (metadata + 384-d vector) and FAISS indices: `index_flat/` (exact) and
  `index_opq_ivfpq/` (OPQ64 + IVF1024 + PQ64, with fp16 vectors for exact re-ranking). Checksums are in `SHA256SUMS`.
- **How they were made:** the frozen head was applied to the proteome demo's stored N1 descriptors; BURROW was not
  re-run.
- **Cross-check:** `method.describe_all` re-run on 40 random models reproduces the released vectors to 1.2e-7.
- **Search quality:** PQ alone gives recall@10 0.886 at nprobe 64. Exact re-ranking of the PQ top-100 gives
  **0.987** at 0.8 ms per query (1 thread). The flat index needs 7.3 ms.
- **Hubness:** raw top-10 in-degree skewness is 1.62. CSLS with database radii brings it to 0.55.

More details are in the folder's `README.md`, `results/release/human_afdb_v6.json` and `docs/FINGERPRINTS.md`
(the handover note for downstream teams).

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
14. **Tooling and release**
  - `pytest tests/test_method_eval_consistency.py tests/test_cli.py`
  - `python scripts/tooling/bench_describe.py --n 2000 --workers 22 --device cuda:0`
  - `CUDA_VISIBLE_DEVICES=1 python scripts/proteome/release_final_head.py --threads 16`
15. **Final evaluation** (PI only)
  - `python scripts/final_eval.py --dryrun-dev`
  - commit, then `python scripts/final_eval.py --write-freeze`
  - commit FREEZE.json
  - `FINAL_EVAL=1 python scripts/final_eval.py --check-only`
  - `FINAL_EVAL=1 python scripts/final_eval.py --threads 16`
  - optionally `FINAL_EVAL=1 python scripts/eval_af_robustness.py --set test --pairs <...>` and
    `scripts/eval_blind.py --set test --pairs <...>`
16. **Report check**: `python scripts/check_report.py REPORT.md`

Every result file has a `.prov.json` sidecar recording commit, inputs, seeds and the evaluate.py hash. The seeds
