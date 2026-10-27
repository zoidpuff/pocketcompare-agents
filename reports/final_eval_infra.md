# Final-evaluation infrastructure (final-eval agent, 2026-10-27)

No file in `data/sealed/` and no chmod-000 file under `data/raw/` was opened, copied or chmod-ed; every check below
ran on dev data or on label-free tables. Nothing is committed.

## 1. Label-free preparation of the sealed external sets
- **PDB mirror:** 183 of the 201 previously missing Vertex entries are now present. 18 remain missing, all
  obsolete (`results/benchmarks/vertex_site_map_summary.json`).
- **`build_benchmarks.py` was not run.** It re-parses the raw label lists: the ProSPECCTs `*.csv` files and the
  Vertex `protein_pairs.tsv`, which are chmod 000. The pocket table was refreshed by
  `scripts/data/vertex_site_map.py` instead. That script reads only the pocket table and the mmCIF files; the old
  table is kept as `vertex_pockets.pre_sitemap.parquet`.
- **Vertex `site_index` → ligand instance**
  - The adapter's old guess, "k-th copy of the HET", is wrong. In all 184 multi-site entries the site indices run
    across *different* HET codes (e.g. 1kvl: 1, 2, 3 = THN, KCP, CLS). In 480 single-site pockets, k is larger than
    the number of HET copies.
  - The ACS paper and the SI description are blocked (HTTP 403). The only public re-implementation is DeeplyTough
    (`ligand_extract.py`; ignore list vendored in `data/ref/`). It defines site k as the k-th HETATM residue with
    ≥ 3 atoms that is not on its ignore list.
  - This rule reproduces the given HET at position k for 85 % of the k > 1 pockets; the HET-copy rule manages 36 %.
  - **Frozen rule:** use the DeeplyTough residue if its name equals the HET (5,616 pockets), else the k-th distinct
    ligand type (31), else the first copy of the HET (510, flagged). 43 pockets have no copy of the HET and are
    unresolved (`site_rule` column). `pockets.resolve_pocket` uses `site_het_instance`; its tests pass.
- **`--label-free-structures`** was added to `build_point_cache.py`, `compute_descriptors.py` and `compute_esm.py`.
  The script headers state that this mode reads no labels.
- **Point caches**
  - ProSPECCTs: 6,093 / 6,093 pockets (all 10 subsets, including 3,260 decoy pockets).
  - Vertex: 6,149 / 6,218. The 69 misses are 18 with no structure, 43 with the HET absent, and 8 where the HET is
    peptidic and stripped as protein.
- **Descriptors (0 failures):**
  - for ProSPECCTs and Vertex: A1 (`pair_only`, `default`), B1, B0 and B4 ESM-2 (cuda:1), in L and D;
  - for all evaluated sets: the N1/N2 blocks (`scripts/compute_n_inputs.py`), identical (max |Δ| = 0) to
    `defrob` / `a1r`.
- **B0′:** `scripts/data/b0prime_foldseek.py` writes per-set lookup tables to `data/processed/b0prime/`: TOUGH-M1
  test and dev, ProSPECCTs (all pockets), Vertex, BLiPS-test holo and BLiPS-val.
  - Foldseek 3Di+AA, exhaustive; score = mean of qTM and tTM.
  - **Caveat:** Spearman with TOUGH's Fr-TM-align on dev is only 0.31, because Foldseek gives about 0 for unrelated
    folds.
- **C5 strata:** holo release dates are in `blips_holo_release_dates.parquet`.

## 2. `scripts/final_eval.py`
- **What it computes:** PREREG §2 (C1a, C1b, C1-D, C2, Holm), all §3 items, and the §4 missing-score policy (common
  set + worst-case + miss rates). B1 and B4 get the final method's CSLS treatment.
- **What it refuses:** the real run stops without `FINAL_EVAL=1`, without a committed FREEZE.json, or on a dirty
  tree.
- **Worktree:** it runs in a worktree at FREEZE.commit with the data directories symlinked in, and there re-checks
  the hashes of `evaluate.py` (== FREEZE == the PREREG constant), PREREG, the method config, the weights and itself.
- **Unsealing:** each sealed file goes 400 → sha256 check → read → 000, and every access is logged to
  `results/final/unseal_log.tsv`. Outputs carry provenance sidecars.
- **Final method:** loaded from `configs/final_method.yaml` (currently N1 raw) through an adapter for the A4b
  `pocketcompare.method.Method`. A module exposing `load(cfg, root)` → `embed(store, dataset, mode, ids)` is used
  as-is. That interface is required for the L4 point-cloud candidate (PREREG Addendum A1).
- **Tested** (`tests/test_final_eval.py`, 4 pass):
  - a scratch-clone worktree preflight passes;
  - it refuses on a dirty tree, a tampered `evaluate.py` and tampered weights.

## 3. Dry run (`--dryrun-dev`, B = 2000; `results/final_dryrun/`, 14 min)
- **Reproduction against `results/dev/`:**
  - B1 and A1 (raw/CSLS × L/D) on TOUGH-M1-dev (8 rows), BLiPS-val (48 rows: all 6 subsets) and PPIPS-val (4):
    **max |deviation| = 5.6e-16** across all point estimates and CIs;
  - every other TOUGH-M1-dev arm (B0, B0′ list, B4, B5, B5-T, controls) matches exactly in its point metrics;
  - FINAL (N1) equals the A4b agent's own dev numbers (Δ = 0);
  - the A1 stand-in (`--standin`) equals the A1 rows exactly (132 rows, CIs included).
- **Synthetic labels:** ProSPECCTs, Vertex and TOUGH-M1-full have no dev analogue, so they ran on synthetic random
  labels as a code-path check only.
- **Dry-run claims (dev data; for orientation only):**

  | claim | Δ | one-sided p | Holm p |
  |---|---|---|---|
  | C1a | +0.051 | 0.11 | — |
  | C1b | +0.092 | 0.048 | — |
  | C1-D | +0.059 | 0.026 | — |
  | C2 stand-in | +0.033 | 0.025 | — |

  With Holm, none is significant (all ≥ 0.10).

## 4. Run the real thing (PI)
1. Commit the code and data tables (incl. `results/models/final/*`), then
   `python scripts/final_eval.py --write-freeze`.
2. Review and commit `FREEZE.json`.
3. Run the preflight: `FINAL_EVAL=1 python scripts/final_eval.py --check-only`.
4. Run the evaluation: `FINAL_EVAL=1 python scripts/final_eval.py --threads 16`. Results are copied to
   `results/final/`.

**What the PI must do**
- Add the PPIPS sealed hashes to `data/sealed_SHA256SUMS.txt`; the preflight refuses without them:
  ```
  7346812ba71161e63476a58367a88e65e3c432c1414514929bc39ad8694b74dd  data/sealed/ppips_test_queries.parquet
  e7915969d45ac96ac265f7659ad61f6e5f56a00453e2ae8e83e87c2b26ee16f0  data/sealed/ppips_sym_test_pairs.parquet
  ```
- Accept or reject the Vertex site rule, and the Foldseek B0′ definition (alternative: `--alignment-type 1`).
- PPI-L test is skipped because it has no index/descriptors (exploratory, D7).
- Note: `method.describe` locates D sites over *all* region pockets, while the evaluation (and A4b selection) use the
  best member of the matched merged pocket.
