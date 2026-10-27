# Blind deployment test (dry run on BLiPS-val v2) and PPI-L final-eval inputs (2026-10-28)

Nothing committed; `data/sealed/` not opened. Test paths exist and refuse without `FINAL_EVAL=1`; not run.

## 1. Blind test, BLiPS-val v2 dry run (`scripts/eval_blind.py --set val`, B = 2,000, 16 s)
Set: 239 val sites with an AF model, 157 AF models, pool = **817** BURROW region-rule merged pockets (>= 10 points; median 4 per model). 93 positive val pairs = 186 directed queries. Median candidates per query 810 (chance hit@100 ~ 12 %). 95 % CIs: vertex bootstrap over homology groups.

**Detection recall** (site -> detected pocket by the D rule, ligand used only for this): **0.615 [0.551, 0.683]** of all 239 sites; 0.667 [0.561, 0.776] for sites in positive pairs. Both ends detected for 84 of 186 directed pairs (45 %).

Partner retrieval, both sites detected (n = 84 directed pairs), candidates = pockets of all other proteins, other positives filtered:

| arm | hit@1 | hit@10 | hit@100 | MRR | AUC |
|---|---|---|---|---|---|
| final (N1) | 0.036 [0.00, 0.15] | 0.155 [0.00, 0.39] | 0.440 [0.13, 0.71] | 0.071 [0.01, 0.20] | 0.634 [0.41, 0.82] |
| B1 | 0.012 [0.00, 0.07] | 0.107 [0.00, 0.35] | 0.417 [0.13, 0.69] | 0.053 [0.01, 0.15] | 0.647 [0.41, 0.83] |
| B0 (size) | 0.000 | 0.036 | 0.071 | 0.013 | 0.439 [0.31, 0.57] |
| final - B1 | +0.024 [-0.06, +0.15] | +0.048 [-0.10, +0.29] | +0.024 [-0.16, +0.25] | +0.018 [-0.08, +0.17] | -0.013 [-0.12, +0.08] |

Unconditional (undetected pair = miss, n = 186): final hit@1/10/100 = 0.016 / 0.070 / 0.199, MRR 0.032, AUC 0.561 [0.46, 0.67]; B1 0.005 / 0.048 / 0.188, MRR 0.024, AUC 0.566; final - B1 AUC -0.006 [-0.056, +0.037]. Removing same-homology-group candidates changes nothing beyond the third decimal.

Reading: low detection recall (61 %) is the main ceiling, and the pair-level signal is weak: final is far above size (B0) and chance, but not distinguishable from B1 (all final - B1 CIs include 0, 42 unique pairs in about 40 homology groups). B4 not computed (ESM-2 needs the GPU); the script has no B4 arm yet.

Definitions chosen (not in DESIGN): query = the whole merged pocket (not the best sub-pocket as in D-mode dev); the match is among pool pockets (>= 10 points); ties count against the method; unlabelled ligand-sharing pairs (Tc 0.3-0.7) are not filtered from the candidates; B1 is z-scored on the pool.

Outputs: `results/dev/blind_val/{metrics.csv,metrics.parquet,pairs.parquet,pockets.parquet,details.json}`; trials arm `blind_dev` (split `blips_val_v2_af_blind`). Test: `FINAL_EVAL=1 python scripts/eval_blind.py --set test --pairs <blips_test_pairs>` (trial arm `blind`, output `results/final/blind_test`).

## 2. PPI-L inputs for the exploratory C3 at final eval
- New `scripts/ppi/14_ppil_index.py` writes the missing point-cache `index.parquet` (4,375 ok pockets, from `data/processed/ppi/ppil/pockets.parquet` + matched-pocket volume); 17 s.
- `compute_n_inputs.py --dataset ppi_l` (N1/N2 blocks, L + D; 4,375 / 4,375 sph8 ok, 0 errors, 12 s) and, for the references, A1 pair_only, B1 default, B0 in `data/processed/descriptors/ppi_l/`. B4 / B6 not computed.
- `scripts/final_eval.py`: the "not implemented" PPI-L branch is now `ppil_set` + `stage_ppil` (arms FINAL raw/CSLS, B1, A1 pair_only, B0; L and D; units homology group and ligand cluster; wider CI). Real run reads `ppi_l_test_pairs.parquet` through `Sealed.read`, dry run uses the val pairs (0 positives, so it records "too few positives"). `tests/test_final_eval.py`: 4 passed. The stage was exercised on a 20k-pair subsample of the train pairs (34 positives) as a code-path smoke test only (not evidence).
- **PI action:** add the sha256 of `data/sealed/ppi_l_test_pairs.parquet` (starts 8a10795f) to `data/sealed_SHA256SUMS.txt`; without it the real run records PPI-L as skipped (it does not abort). Test pairs are assumed to have the same columns as `ppi_l_pairs_val.parquet`. B6 (`ppi_l_test_b6`) is not scored.
