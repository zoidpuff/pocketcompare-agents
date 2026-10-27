# Definition robustness: ligand-free site shapers × robust blocks (D11) — 2026-10-27

TOUGH-M1-dev (731 pockets; L: 9,829 pairs, D: 7,866 D-set pairs). Metrics come from the frozen `evaluate.py`.
CIs are 95 % joint vertex bootstraps (B = 1000, seed 0, units = ligand cluster ∪ homology group). 36 distinct
variants were logged to `results/trials.tsv` (arm `A1R-explore`).
Notation: `desc@def`.
- `base` = L ligand shell / D merged BURROW pocket (as in the dev eval). `U` = D located by the single best-covering
  sub-pocket instead of the merged pocket.
- **sph8** = all buried points (bur10 ≥ 0.5) within 8 Å of the bur16⁴-weighted centroid of the located set.
- res = residue shell; core8 = located set ∩ 8 Å.
- env = new protein-side block (113 d): vol-weighted and bur16⁴-weighted means of `hit_*`, `n4_rg_*`, `f8_*`, `f12_*`
  composition, plus a first-hit chemistry × buriedness-tertile histogram.
- Multi-part variants use a 1:1 block cosine.
- cross = labelled pairs scored L-query vs D-target. agree = label-free retrieval AUC of a site's own D descriptor
  from its L descriptor among the 655 matched dev pockets.

| variant | dims | cb L | cb D | **mean** | strat L | strat D | cross cb | agree | ms L / D |
|---|---|---|---|---|---|---|---|---|---|
| a1pair@base (ref = dev pick) | 392 | 0.798 | 0.541 | 0.670 | 0.732 | 0.564 | 0.647 | 0.765 | 5.7 / 2.1 |
| a1@base / a1@baseU | 514 | 0.794 | 0.549 / 0.557 | 0.672 / 0.676 | 0.732 | 0.560 / 0.590 | 0.664 / – | 0.777 / 0.804 | 5.7 / 2.0 |
| b1@base | 45 | 0.632 | 0.620 | 0.626 | 0.630 | 0.614 | 0.662 | 0.949 | 1.3 / 1.1 |
| a1@core8U | 514 | 0.743 | 0.566 | 0.654 | 0.735 | 0.592 | – | 0.816 | 4.6 / 2.1 |
| a1@resU | 514 | 0.657 | 0.580 | 0.619 | 0.666 | 0.624 | – | 0.937 | 19 / 11 |
| a1@sph6U / sph8U / sph10U | 514 | 0.642 / 0.626 / 0.629 | 0.635 / 0.642 / 0.606 | 0.639 / 0.634 / 0.617 | 0.666 / 0.655 / 0.615 | 0.630 / 0.636 / 0.630 | – | 0.944 / 0.966 / 0.981 | 3–8 |
| a1pair@sph8U / a1hist@sph8U | 392 / 27 | 0.621 / 0.556 | 0.630 / 0.598 | 0.626 / 0.577 | 0.649 / 0.570 | 0.633 / 0.566 | – | 0.957 / 0.979 | 5 |
| b1@sph8U | 45 | 0.637 | 0.654 | 0.646 | 0.650 | 0.646 | 0.662 | 0.995 | 1.4 |
| env@base / env@baseU | 113 | 0.661 | 0.627 / 0.643 | 0.644 / 0.652 | 0.650 | 0.632 / 0.638 | – | 0.976 / 0.982 | 0.2 / 0.1 |
| env@sph8U (sph6U, sph10U, resU ≤ ±0.01) | 113 | 0.637 | 0.655 | 0.646 | 0.669 | 0.664 | 0.660 | 0.997 | 0.3 |
| **a1@baseU + env@sph8U** | 627 | 0.756 | 0.631 | **0.693** <!-- src: results/explore/definition_robustness/eval_final_cross.parquet#cb_mean[variant=a1@baseU+env@sph8U] --> | 0.729 | 0.650 | **0.726** | 0.982 | 6.1 / 2.3 |
| a1@baseU + a1@sph8U + env@sph8U | 1141 | 0.732 | 0.650 | 0.691 | 0.717 | 0.658 | 0.718 | 0.988 | 11 / 7 |
| a1pair@base + env@sph8U | 505 | 0.762 | 0.616 | 0.689 | 0.732 | 0.631 | – | 0.970 | 6.1 / 2.5 |
| a1@core8U + env@sph8U | 627 | 0.717 | 0.635 | 0.676 | 0.725 | 0.651 | 0.708 | 0.984 | 4.9 / 2.5 |
| **a1@sph8U + env@sph8U** (ligand-free) | 627 | 0.648 | **0.672** <!-- src: results/explore/definition_robustness/eval_final_cross.parquet#cb_D[variant=a1@sph8U+env@sph8U] --> | 0.660 | 0.681 | **0.669** | 0.676 | **0.996** | 5.2 / 4.9 |
| same, D = set-max over all sub-pockets (no oracle) | 627 | 0.648 | 0.663 | 0.655 | 0.681 | 0.667 | – | 0.995 | 5.6/member |
| same, D centre from merged pocket (`@sph8`) | 627 | 0.648 | 0.652 | 0.650 | 0.681 | 0.669 | 0.666 | 0.989 | 5.2 |

Reference rows from the dev eval: B0 size has cb 0.766 (L) and 0.484 (D), strat ≈ 0.52.

## Findings
1. **The amended objective still rewards the ligand imprint.** Ligand-free sites (sph/res) cap L-mode cb at
   0.62–0.66, against 0.80 for the 4 Å shell (B0 size alone reaches 0.766 in L). They lift D-mode instead.
   - So the best mean comes from a **hybrid**: the A1 void block on the located pocket plus env on the ligand-free
     sph8 site. Mean 0.693, Δ vs ref +0.024 [−0.039, +0.043].
   - The hybrid is not a size shortcut: strat-L stays 0.729 and strat-mean is 0.690 vs 0.648 for the ref.
   - It is also best cross-mode (0.726).
   - None of the Δmean CIs excludes 0, because of the giant unit (D12).
2. **D-mode gains are real.** These are paired D-set Δs (`dmode_deltas.parquet`), B = 1000.
   - **a1@sph8U+env@sph8U:** vs A1 ref +0.131 [+0.056, +0.185]; vs B1 (the C1-D comparator) +0.052 [−0.004, +0.134],
     one-sided p = 0.033. Stratified: +0.055 [−0.032, +0.149].
   - **Hybrid:** vs A1 +0.090 [+0.004, +0.128]; vs B1 +0.011.
   - **env alone:** vs B1 +0.035 at 0.3 ms/pocket.
3. **Which blocks are definition-robust (label-free agreement, base → sph8U).**
   - env 0.98 → 0.997 and B1 0.95 → 0.995 hardly depend on the point set.
   - A1 hist 0.84 → 0.98 is robust but uninformative (labelled mean 0.58).
   - A1 full/pair 0.77 → 0.96; glob 0.65 → 0.90; USR is the least robust (0.65 → 0.86).
   - Every shaper beats `base`: sph10 > sph8 > res ≈ sph6 ≫ core8 ≈ baseU. The unmerged locator U beats merged D
     for every block (screen: `screen_agreement.parquet`, 132 cells, label-free).
4. **What did not work.**
   - Residue mode: A1 mean 0.619, 3× slower (the residue shell is ~2× the ligand shell and noisy).
   - sph10: it dilutes the site (A1 cb-D 0.606).
   - core8: it keeps the imprint (D 0.566).
   - Up-weighting env (×2) or adding B1 to A1+env: Δ ≤ 0.003.
   - The env sub-blocks (mean/bur/hist) are interchangeable.
   - Merged-pocket centres cost −0.020 D vs U.
   - Set-to-set max over sub-pockets (item 1c) recovers most of the oracle U: −0.009 D. It is the ligand-free
     deployment version.
5. **Caveats.**
   - 36 variants selected on one dev set with a giant unit, so expect optimism of ~0.01–0.02.
   - D/U locators use the ligand to pick the pocket (the oracle proxy, as in DESIGN §2.2).
   - BLiPS-val is not yet in the selection mean.
   - The 38 trial rows tagged `variant_tag=batch1` are superseded by `batch1fix`. In batch1, six dev pockets whose
     D pocket is a single metal-candidate point were dropped instead of described. It was fixed before any later
     batch.

## Recommendation for the next stage (A4b)
- **Input to A4b:** the three-view vector [A1(located sub-pocket) | A1(sph8) | env(sph8)] (1,141 d, ~11 ms L /
  7 ms D).
  - Train it with the planned L↔D augmentation pairs, so the metric learns how much of the void view to trust.
  - Non-learned it already reaches mean 0.691, cross 0.718.
- **Non-learned carry-forward:**
  - (a) **a1@baseU + env@sph8U** (627 d) is the best on the amended objective and stratified mean.
  - (b) **a1@sph8 + env@sph8 on BURROW sub-pockets** (set-max in deployment) is the D-mode/AFDB and C1-D
    candidate.
- **Pocket definition for deployment:** describe BURROW *sub-pockets* (not merged pockets) via the 8 Å buried
  sphere around their bur16⁴ centroid. Drop the residue shaper and USR.

Code: `src/pocketcompare/pockets.py` (`shape_site`, `site_sphere`, `site_residue_shell`, `best_member`, …),
`src/pocketcompare/descriptors/a1r.py` (env), `tests/test_a1r.py` (10 tests: rigid-motion invariance of every
shaper and of env/A1 on sph8, centroid equivariance, nesting, point order), `scripts/explore/defrob_{compute,eval,
setmatch,dmode_delta}.py`. Descriptors for all 7,524 pockets × 18 site sets were computed in 106 s on 16 workers
(`data/processed/descriptors/tough_m1/defrob/`). Results: `results/explore/definition_robustness/*.parquet`
(+ `.prov.json`).
