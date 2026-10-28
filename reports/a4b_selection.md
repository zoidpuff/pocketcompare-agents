# A4b learned metric and PREREG §1 final-method selection (2026-10-28, D18 splits)

## Result
- **Selected: A4b:n1_base, raw cosine.**
  - The model is an MLP head on N1 = [A1(sph8) | env(sph8)] (627 → 512 → LayerNorm/GELU → 128).
  - Its score is the mean cosine of a 3-seed ensemble. Each pocket is stored as a 384-d vector.
  - Config: `configs/final_method.yaml`. Weights: `results/models/a4b/n1_base/` (3 × 1.5 MB, sha256 in the config).
- **Scores of the selected method (dev, B = 2,000):**
  - BLiPS-val D cb-AUC 0.717 [0.633, 0.783], SE 0.038 (homology-group units).
  - BLiPS-val L cb-AUC 0.702.
  - TOUGH-M1-dev cb-AUC: D 0.687, L 0.695.
  - PPIPS-val P-ortho MRR 0.694; P-sym percentile 0.999.
- **Rule outcome:**
  - The best candidate was A4b:n2_linear with CSLS: 0.751, SE 0.036, so the threshold is 0.715.
  - The best non-learned candidate (N2 raw, 0.704) falls just below it, so the one-SE rule moves to learned candidates.
  - Every A4b model has 384 stored dims. The tie-break goes raw before CSLS, then grid order, which gives n1_base raw.
  - Both guards hold. BLiPS L: 0.702 ≥ B1's 0.701 (a margin of only 0.001). TOUGH-M1-dev D: 0.687 ≥ 0.617.
- **Runtime** (1 thread, BURROW excluded; `results/dev/final_method_runtime.json`):
  - 3.5 ms per D pocket (p90 4.6 ms), including the 64 µs A4b forward; 6.1 ms per L site.
  - 0.10 µs per pair when scored batched against 1 M vectors; 1.5 kB per pocket.
- **L4 is not included.** No L4 models or trials existed when this ran. The selection must be re-run with `scripts/eval_l4.py --with-a4b` once they arrive (see Caveats).

## Candidate table (BLiPS-val D cb is the objective; `results/dev/final_select_all_summary.md` has all 36 rows)
| candidate | BLiPS D cb (SE) | BLiPS L cb | TM-dev D cb | TM-dev L cb | PPIPS MRR | within 1 SE / guards |
|---|---|---|---|---|---|---|
| B1 raw (ref) | 0.648 (0.040) | 0.701 | 0.617 | 0.639 | 0.761 | – |
| B4 raw / CSLS (ref) | 0.670 / 0.711 | 0.641 / 0.687 | 0.598 / 0.588 | 0.602 / 0.610 | 0.986 / 0.973 | – |
| N1 raw / CSLS | 0.697 / 0.700 (0.040) | 0.706 / 0.720 | 0.667 / 0.667 | 0.656 / 0.658 | 0.790 / 0.782 | no / ✓ |
| N2 raw / CSLS | 0.704 / 0.701 (0.039) | 0.738 / 0.750 | 0.646 / 0.655 | 0.719 / 0.718 | 0.803 / 0.811 | no / ✓ |
| **A4b n1_base raw** / CSLS | **0.717** / 0.731 (0.038) | 0.702 / 0.710 | 0.687 / 0.677 | 0.695 / 0.693 | 0.694 / 0.694 | ✓ / ✓ |
| A4b n1_linear raw / CSLS | 0.737 / 0.748 | 0.718 / 0.721 | 0.721 / 0.711 | 0.720 / 0.717 | 0.719 / 0.717 | ✓ / ✓ |
| A4b n2_base raw / CSLS | 0.720 / 0.731 | 0.747 / 0.747 | 0.707 / 0.693 | 0.742 / 0.741 | 0.748 / 0.727 | ✓ / ✓ |
| A4b n2_linear raw / CSLS (best) | 0.741 / **0.751** (0.036) | 0.749 / 0.755 | 0.712 / 0.702 | 0.752 / 0.754 | 0.756 / 0.755 | ✓ / ✓ |
| other A4b (graded, reg, noppi, nce; ×2 inputs) | 0.692–0.739 | 0.695–0.749 | 0.672–0.718 | 0.688–0.747 | 0.62–0.75 | n1_graded raw and n2_noppi raw fail the L guard |

**Paired Δ cb-AUC, selected − reference** (shared bootstrap weights, 95 % CI, one-sided p):

| | BLiPS-val D | BLiPS-val L | TM-dev D | TM-dev L |
|---|---|---|---|---|
| vs B1 | +0.069 [−0.029, +0.132] (p 0.09) | +0.001 | +0.070 [−0.012, +0.128] (p 0.04) | +0.056 |
| vs N1 | +0.020 [−0.060, +0.088] (p 0.34) | −0.005 | +0.020 | +0.039 |
| vs B4 | +0.047 | +0.061 | +0.089 [+0.010, +0.155] | +0.093 |

## What was done
1. **Descriptors** (`compute_descriptors.py --arm a1r`; label-free).
   - Computed for BLiPS train+val (2,862 sites, L and U), BLiPS-test holo (3,606) and AF (3,603), and PPIPS (20,497, D). 0 errors, 5–35 s on 23 workers.
   - TOUGH-M1 reuses the defrob arrays. A 24-pocket recompute was bit-identical.
   - Time per pocket: A1(sph8) 4.5–4.9 ms, env 0.15 ms, shaper 0.2–0.5 ms, plus atom typing 0.5 ms per structure.
2. **Step 2 re-run on the D18 splits** (`eval_dev.py --dataset final_select`).
   - Inputs are z-scored with BLiPS-train L+U statistics; this is the shipped scaling.
   - The reference rows reproduce the earlier per-dataset runs exactly.
3. **A4b training** (`scripts/train_a4b.py`; grid pre-declared in `configs/a4b_grid.yaml` before any fit; 12 configs × SEEDS[:3]; cuda:0/1; 2 min in total).
   - Training data: 6,992 BLiPS-train positives, 1,602 L↔D same-site positives and 3,177 PPIPS-train P-sym/P-ortho positives.
   - Loss: InfoNCE with masked in-batch negatives, plus BCE on balanced labelled pairs.
   - Early stopping uses 10 % of BLiPS-train homology groups.
   - Best epochs mostly come early (0–8; one seed reached 20). The heads fit quickly and the early-stopping score stops improving after a few epochs. Hold-out ES ranged 0.76–0.83.
4. **API.**
   - `src/pocketcompare/method.py`: `describe(structure, site=None|ligand file|xyz|residues, af_mode=…)` and `similarity(a, b[, background])`.
   - `tests/test_method.py`: 6 tests pass. They check that the API reproduces the evaluated vectors in L and D mode, that a rigid motion leaves similarity > 0.995, that repeated calls are bit-identical, that self-similarity is 1 and the maximum, and that a wrong sha256 is rejected.

## Caveats and deviations
- **sph8 fallback**, declared before seeing its effect. One fully exposed BLiPS-val site has an empty sph8 set, and the sph8 parts are then computed on the located set. This affects one site in all data, in both the evaluation and the API.
  - **Action for L4:** L4 gives this site a zero vector, which makes `main_final_select` stop with a NaN error. L4 must mirror the fallback before its joint run.
- **The tie-break carried the choice.** Fewer parameters, instead of grid order, would have picked n1_linear raw (0.737).
- **Learning is not a demonstrated gain.**
  - The learned-over-N1 gain is small: +0.020 with a CI that includes 0.
  - The best score is a maximum over 24 learned variants, which inflates the threshold by selection.
  - The learned head lowers PPIPS P-ortho MRR: 0.694 vs N1's 0.790 and B1's 0.761 (reported only; this metric has no guard).
- **128 BLiPS sites left out.** The `excluded_not_cached` sites remain excluded. Adding them would require re-running `make_blips_resplit_v2.py`, which redraws the frozen split. Computing their descriptors alone is cheap.
- **Commit:** `results/models/a4b/` is 64 MB. Committing only `n1_base/` plus the other configs' `config.json`/`train_log.json` should suffice.
