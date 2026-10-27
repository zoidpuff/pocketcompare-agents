# Dev evaluation on BLiPS-val v2 and PPIPS-val, plus A1 selection under D11 (eval agent, 2026-10-27)

Commands: `scripts/eval_dev.py --dataset blips` (398 s) and `--dataset ppips` (24 s), with B = 2000, seed 0 and 16 threads.
- **Results:** `results/dev/{blips_val,ppips_val}_summary.{parquet,md}`, `*_details.json` (selection, comparisons, L-vs-D, CSLS, hypothesis) and `blips_val_replicates.parquet`, all with `.prov.json`.
- **Trials:** 88 + 25 rows appended to `results/trials.tsv`.
- **TOUGH-M1 path:** byte-identical after the change (B = 50 before/after: summary, details, md and sorted replicates are equal).
- Nothing is committed and `data/sealed/` was not opened.

## BLiPS-val v2: 511 sites, 563 pos / 2,815 neg pairs, 48 positive clusters
Raw cosine throughout. Each CI is the wider of two vertex bootstraps: homology-group units (256; largest 12 sites) and label-ligand Butina units (187; largest 78). The homology-group CI was wider in almost every row.
- **L mode:** all pairs, strata 5 × 20.
- **D mode:** D-set = both sites D-matched: 385/511 sites, 1,858 pairs, 313 pos, so strata are 5 × 5 by the D6 rule.
- **D-mode misses:** 44.4 % of positives and 45.1 % of negatives.

| arm | L ROC-AUC [CI] | L cb-AUC | L strat. AUC [CI] | D ROC-AUC [CI] | D strat. AUC | D worst-case |
|---|---|---|---|---|---|---|
| B0 size | 0.659 [0.585, 0.721] | 0.646 | 0.511 [0.456, 0.563] | 0.525 | 0.520 | 0.160 |
| B0m (cross-fitted diagnostic) | 0.651 | 0.621 | **0.481** [0.399, 0.569] ✓ | — | — | — |
| B1 BURROW | 0.687 [0.623, 0.751] | 0.641 | 0.674 [0.598, 0.751] | 0.676 [0.582, 0.763] | 0.671 | 0.206 |
| B4 ESM-2 (z) | 0.679 [0.591, 0.776] | 0.686 | 0.676 [0.589, 0.774] | **0.698** [0.606, 0.790] | **0.699** | 0.213 |
| A1 pair_only (chosen) | **0.775** [0.721, 0.824] | 0.706 | **0.741** [0.674, 0.803] | 0.555 [0.477, 0.640] | 0.545 | 0.169 |
| A1 default | 0.775 [0.719, 0.823] | 0.713 | 0.742 [0.678, 0.805] | 0.555 | 0.548 | 0.169 |
| random control | 0.499 | 0.511 | 0.496 | — | — | — |

- **The D11 ligand-imprint finding replicates on an independent set.**
  - On the same 1,858 D-set pairs, A1 pair_only drops from AUC 0.823 (L) to 0.555 (D): Δ −0.268 [−0.359, −0.175].
  - B1 loses only −0.046 [−0.112, +0.021], B4 −0.000 and B0 −0.164.
  - The only A1 block that is stable across modes is hist_only (0.617 → 0.597).
  - Why B4 is mode-invariant: the ESM mean embeddings of the L and D residue sets have a per-pocket cosine of 0.90, so B4 is dominated by protein context.
- **Paired comparisons (Δ ROC-AUC, Δ stratified AUC):**

  | comparison | mode | Δ ROC-AUC [CI] | Δ stratified AUC [CI] |
  |---|---|---|---|
  | A1 − B1 | L | +0.088 [+0.027, +0.138] | +0.067 [−0.009, +0.112] |
  | A1 − B1 | D | −0.121 [−0.229, 0.000] | −0.126 [−0.245, +0.006] |
  | A1 − B4 | D | −0.144 [−0.259, −0.030] | −0.154 [−0.276, −0.035] |
- **CSLS:**
  - A1 and B1: |Δ AUC| ≤ 0.005 (n.s.).
  - B4: −0.023 (L) and −0.044 (D), both n.s.
- **Subsets** (stratified AUC; L / D):

  | subset | positives | A1 pair_only | B1 | B4 | B0m (L) |
  |---|---|---|---|---|---|
  | without top-20 promiscuous CCDs | 311 | 0.732 / 0.567 | 0.696 / 0.656 | 0.720 / 0.717 | 0.504 |
  | n_shared ≥ 2 | 10 | 0.767 [0.54, 0.96] | 0.714 | 0.736 | — |
  | unseen chemotype | 13 | 0.633 [0.22, 0.87] | 0.535 | 0.834 | — |

  - n_shared = 1 (553 positives) is the same as "all" to within 0.002.
  - The n_shared ≥ 2 and unseen-chemotype subsets are too small to interpret.

## A1 selection under the amended objective (D11) → **pair_only (unchanged)**
**Objective:** mean cb-AUC over {TOUGH-M1-dev L, TOUGH-M1-dev D, BLiPS-val L, BLiPS-val D}, raw cosine. Candidates are the 16 grid configs plus default_bw.

**How the SE is combined:**
1. **Within each dataset**, one generic vertex bootstrap returns the pair (cb_L, cb_D) under the same replicate weights, with D evaluated on the D-set subset of those pairs. This keeps the L/D correlation.
2. **Across datasets**, TOUGH-M1 (union units, seed 0) and BLiPS (seed [0, 1]) are bootstrapped independently. Replicate b of the objective is the mean of the four replicate-b values (as in `macro_paired_bootstrap`). SE = SD over replicates.
3. **BLiPS unit choice:** the unit definition giving the larger SE for the best config is used (homology: 0.0205; ligand: 0.0193).

**Result:**
- **Best:** no_hellinger, mean 0.6565 (0.790 / 0.552 / 0.721 / 0.563).
- **Threshold:** 0.636. Twelve configs fall within one SE.
- **Choice:** the simplest of them is **pair_only** (392 dims), mean 0.6522 (0.798 / 0.541 / 0.706 / 0.564).
- **Configs outside one SE:** default_bw 0.632, untyped 0.631, usr_only 0.613, hist_only 0.596, glob_only 0.572.

**Caveat:** the objective is dominated by L-mode variance. All grid configs except hist_only sit between 0.51 and 0.58 cb in D mode. hist_only is the best in D (0.597 / 0.604) but the worst in L. The config grid cannot buy definition robustness; that needs the D11 development track.

## PPIPS-val (D-mode region pockets; z-scores and the A2 fit on PPIPS-train pockets only)
**Setup:**
- **P-ortho:** 95 queries (69 query pockets) in only **13 homology-group units**; median 8 candidates. Chance levels: top-1 0.142, top-3 0.420, MRR 0.352.
- **P-sym:** 732 queries (366 pairs × 2 directions) against 2,471 other val pockets, 26 units.

| arm (raw) | P-ortho top-1 [CI] | top-3 | MRR [CI] | P-sym percentile [CI] | P-sym percentile, interface |
|---|---|---|---|---|---|
| B0 size | 0.221 [0.152, 0.321] | 0.505 | 0.426 [0.349, 0.506] | 0.768 [0.750, 0.789] | 0.766 |
| B1 default | 0.632 [0.418, 0.788] | 0.863 | 0.764 [0.601, 0.879] | 0.998 | 0.997 |
| B4 ESM-2 (z) | **0.884** [0.767, 0.984] | 1.000 | **0.942** [0.883, 0.992] | 1.000 | 1.000 |
| A1 pair_only (chosen) | 0.358 [0.270, 0.457] | 0.726 | 0.563 [0.494, 0.644] | 0.932 | 0.925 |
| A1 default | 0.432 [0.356, 0.538] | 0.800 | 0.633 [0.566, 0.710] | 0.944 | 0.941 |
| A2 fragments IFP (CSLS) | 0.421 (0.526) | 0.737 | 0.619 (0.678) | 0.980 | 0.976 |
| A2 lead-like IFP (CSLS) | 0.347 (0.411) | 0.695 | 0.544 (0.600) | 0.979 | 0.976 |
| A2 frag rank / LE-resid | 0.326 / 0.242 | 0.53 / 0.55 | 0.482 / 0.447 | 0.920 / 0.936 | — |

- **P-ortho:** cross-species interolog transfer at < 30 % identity favours the sequence-embedding baseline (B4 MRR 0.94). B1 follows at 0.76 and A1 trails at 0.56–0.63. This task does not test fold independence.
- **P-sym:** the sanity check (≥ 0.9) passes for every arm except B0. B4 = 1.000 is trivial because the copies have identical sequence.
- **D11 choice on PPIPS:** pair_only is worse than default here (MRR −0.07).

**PPI sub-hypothesis (pre-registered: fragments > lead-like) → NOT SUPPORTED.** The verdict rule was fixed in the script docstring before the run. Paired Δ MRR (fragments − lead-like), raw, all 95 interface queries:

| block | Δ MRR [CI] | Holm p |
|---|---|---|
| rank | −0.004 [−0.097, +0.073] | 0.50 |
| LE-resid | +0.045 [−0.034, +0.100] | 0.28 |
| IFP | +0.074 [−0.031, +0.170] | 0.25 |

- The point estimates favour fragments for two of the three blocks, and also with CSLS (IFP +0.079), but no CI excludes 0.
- **Shallowest bur16 tertile** (query bur16 < 0.901; 31 queries, 9 units):
  - IFP +0.133 [−0.065, +0.317];
  - LE-resid +0.042;
  - rank −0.008.
- **Only CI excluding 0:** LE-resid in the middle tertile, +0.140 [+0.038, +0.263]. This is descriptive and uncorrected.
- With 13 units the test is underpowered. This is a non-confirmation, not a refutation.

## Choices and deviations (all fixed in the script docstring before the first run)
- **cb-AUC cluster** = `pair_cluster` (Butina cluster of the shared ligand).
- **B0m folds** use homology-group units.
- **Strata:** 5 × 5 whenever a subset has < 500 positives (D-set, no_promiscuous).
- **Selection replicates:** the TOUGH-M1 D-mode replicates are recomputed with all-pair units, which is needed for the L/D pairing. The D point values reproduce `tough_m1_dev_summary`.
- **PPIPS z-scoring** uses train-pocket statistics (TOUGH-M1-dev used the dev pool, label-free).
- **Skipped:**
  - Foldseek-local and B0′, which are not meaningful within one partner complex;
  - the `positives_overlap` variant (only 3 extra positives in val);
  - A2 on BLiPS (no docking exists).
- **Concurrent `pockets.py` / `a1r.py` edits:** they do not affect these results. Descriptors were precomputed and only `.npy` files plus `a2.py` are read.
