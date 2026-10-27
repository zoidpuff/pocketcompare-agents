# Dev evaluation of all arms on TOUGH-M1-dev (eval agent, 2026-10-27)

`scripts/eval_dev.py --dataset tough_m1` (B = 2000, seed 0, 16 threads, 174 s). Results: `results/dev/tough_m1_dev_summary.{parquet,md}`,
`tough_m1_dev_details.json` (selection, gate, MDE, folds), `tough_m1_dev_replicates.parquet`, all with `.prov.json`; 137 rows
appended to `results/trials.tsv`. Dev = 731 pockets, 9,829 pairs (3,366 pos, prevalence 0.342). Full table (137 rows,
incl. all 16 A1 configs in L and D mode) in the summary md. Not committed.

## Main table (L-mode unless noted; CIs = 95 % vertex bootstrap, units = ligand cluster ∪ homology group)

| arm | ROC-AUC [CI] | AP (lift) | pAUC₀.₁ | cluster-bal. AUC [CI] | size-strat. AUC [CI] |
|---|---|---|---|---|---|
| B0 size, −abs(Δ log V) | 0.780 [0.696, 0.844] | 0.574 (1.68) | 0.552 | 0.766 [0.729, 0.833] | 0.520 [0.457, 0.573] |
| B0m size logistic (cross-fitted) | 0.857 [0.824, 0.959] | 0.704 (2.06) | 0.625 | 0.881 [0.849, 0.930] | **0.489** [0.420, 0.709] |
| B0′ global TM-score | 0.508 [0.455, 0.593] | 0.344 (1.01) | 0.500 | 0.539 [0.422, 0.585] | 0.493 [0.439, 0.640] |
| B1 BURROW descriptors | 0.643 [0.549, 0.664] | 0.465 (1.36) | 0.531 | 0.632 [0.584, 0.701] | 0.630 [0.461, 0.659] |
| B4 ESM-2, z-scored cosine | 0.601 [0.514, 0.625] | 0.431 (1.26) | 0.522 | 0.624 [0.558, 0.680] | 0.600 [0.483, 0.632] |
| B4 ESM-2, raw cosine | 0.575 [0.480, 0.624] | 0.404 (1.18) | 0.516 | 0.572 [0.483, 0.634] | 0.575 [0.497, 0.670] |
| B5 EPoCS (−Euclidean) | 0.599 [0.429, 0.642] | 0.429 (1.25) | 0.524 | 0.552 [0.466, 0.610] | 0.592 [0.384, 0.640] |
| B5-T APoc PS-score | 0.600 [0.441, 0.630] | 0.420 (1.23) | 0.517 | 0.506 [0.469, 0.609] | 0.582 [0.358, 0.619] |
| B5-T APoc −P-value | 0.585 [0.450, 0.616] | 0.414 (1.21) | 0.516 | 0.527 [0.465, 0.597] | 0.571 [0.404, 0.607] |
| B5-T G-LoSA GA-score | 0.646 [0.432, 0.693] | 0.465 (1.36) | 0.531 | 0.577 [0.478, 0.636] | 0.611 [0.318, 0.667] |
| B5-T SiteEngine c1 † | 0.680 [0.624, 0.781] | 0.435 (1.27) | 0.500 | 0.675 [0.603, 0.725] | 0.672 [0.493, 0.705] |
| B5-T SiteEngine c2 † | 0.595 [0.203, 0.649] | 0.450 (1.32) | 0.541 | 0.413 [0.331, 0.487] | 0.654 [0.278, 0.708] |
| B5-T SiteEngine c3 † | 0.469 [0.298, 0.500] | 0.306 (0.89) | 0.481 | 0.327 [0.272, 0.377] | 0.489 [0.312, 0.525] |
| **A1 pair_only (chosen)** | 0.795 [0.768, 0.873] | 0.635 (1.85) | 0.598 | 0.798 [0.772, 0.876] | 0.732 [0.599, 0.795] |
| A1 no_bur (best cb-AUC) | 0.794 [0.766, 0.884] | 0.634 (1.85) | 0.595 | 0.800 [0.773, 0.878] | 0.735 [0.608, 0.794] |
| A1 default | 0.788 [0.760, 0.876] | 0.625 (1.82) | 0.590 | 0.794 [0.766, 0.872] | 0.732 [0.597, 0.789] |
| A1 untyped / hist_only | 0.727 / 0.546 | 0.522 / 0.380 | 0.541 / 0.509 | 0.748 / 0.558 | 0.649 / 0.522 |
| A2 fragments rank / LE-resid / IFP | 0.562 / 0.565 / 0.592 | 0.382 / 0.370 / 0.411 | 0.504 / 0.496 / 0.517 | 0.561 / 0.596 / 0.598 | 0.560 / 0.537 / 0.600 |
| A2 fragments IFP, CSLS | 0.632 [0.537, 0.660] | 0.462 (1.35) | 0.533 | 0.633 [0.591, 0.723] | 0.625 [0.477, 0.664] |
| A2 lead-like rank / LE-resid / IFP | 0.570 / 0.620 / 0.578 | 0.407 / 0.409 / 0.408 | 0.522 / 0.508 / 0.517 | 0.568 / 0.697 / 0.573 | 0.535 / 0.506 / 0.586 |
| Fusion A1 + A2 frag (cross-fitted) | 0.789 [0.760, 0.868] | 0.613 (1.79) | 0.583 | 0.796 [0.768, 0.871] | 0.722 [0.590, 0.784] |
| Fusion A1 + B1 / A1 + B1 + A2 / A1 + A2 + B4 | 0.787 / 0.784 / 0.791 | 0.594 / 0.588 / 0.616 | 0.569 / 0.565 / 0.584 | 0.797 / 0.795 / 0.804 | 0.716 / 0.713 / 0.728 |
| Control: random vectors | 0.506 [0.430, 0.520] | 0.346 (1.01) | 0.500 | 0.488 | 0.499 |
| Control: shuffled labels (A1) | 0.499 [0.485, 0.537] | 0.345 (1.01) | 0.503 | 0.489 | 0.501 |

† SiteEngine columns are undocumented; all three are reported as shipped (higher = similar, unverified). B5-T scores
come from the original authors' own pocket definitions.

## Findings
1. **A1 selection** (one-SE rule on cb-AUC, L-mode raw, TOUGH-M1-dev only; BLiPS-val still to be added). The best
   config is no_bur (cb 0.800, SE 0.029). Eleven configs fall within one SE, and the rule picks **pair_only**
   (392 dims). The block-weighted cosine is worse (cb 0.705).
2. **A2 gate: FAIL.** The primary test fuses A1 with the three A2 fragment blocks (raw z-scored cosines,
   cross-fitted) and compares it with cross-fitted A1 alone. Δ size-stratified AUC = −0.0097 <!-- src: results/dev/tough_m1_dev_details.json#gate.A1+A2frag|raw.delta_strat_vs_cf_A1.estimate -->
   [−0.027, +0.007];
   Δ ROC-AUC = −0.007 [−0.011, −0.001]. Every A2 fusion has a negative Δ: lead-like, both panels, the CSLS
   inputs, and the fusion with B1 or B4. As a standalone arm, A2 fragment-IFP (+CSLS) reaches stratified AUC
   0.625, on par with B1. However, it adds nothing on top of A1.
3. **Size shortcut is huge on dev.** Pocket size alone gives AUC 0.78 (B0) and 0.857 (B0m), so pair ROC-AUC
   alone is not informative here. The B0m diagnostic passes: stratified AUC 0.489, within 0.5 ± 0.03. A1 keeps
   a stratified AUC of 0.732, but its pair AUC of 0.795 is below the pure-size B0m.
4. **L vs D: the A1 signal is largely a ligand imprint.** On the same 7,866 D-set pairs (paired), A1 pair_only
   drops from AUC 0.808 (L) to 0.560 (D): Δ −0.249 [−0.366, −0.217]; stratified AUC drops 0.754 → 0.564.
   B0 drops 0.788 → 0.530. B1 loses only 0.061 and B4 only 0.024. L-mode pockets are the 4 Å ligand shell, so
   their volume and internal distance distribution encode ligand size and shape, which is what the labels
   measure. In D-mode, B1 (0.615) and B4 (0.600) beat A1 (0.56). A2-IFP is stable across modes (0.62–0.66),
   but on fewer pairs. **This threatens the interpretation of C1a (L-mode headline): an A1 > B1 result on test
   would partly reflect pocket definition, not pocket similarity.**
5. **CSLS effect:** small and mostly inside the CIs. For A1 in L-mode it is −0.002 to −0.013 AUC (slightly
   harmful); in D-mode it is +0.005 to +0.017. It helps A2-IFP (+0.040 [+0.005, +0.060] for fragments). It hurts
   B4-z (−0.061) and B5 (−0.044) in AUC, although their cb-AUC rises.
6. **D-mode coverage:** 655/731 dev pockets are D-matched, giving 7,866 pairs. Miss rates over all dev pairs are
   16.1 % of positives and 22.0 % of negatives. The worst-case A1-D AUC is 0.366. A2 D-mode docking covered
   only the coverage ≥ 0.3 pockets (537), so it misses 40.8 % of positives and 58.5 % of negatives.
7. **MDE (C1a).** Units are components of ligand cluster ∪ homology group: dev has 146, with one unit holding
   438 of 731 pockets and touching 58 % of pairs; test has **141, with one unit holding 710 of 1,014 pockets**.
   The dev Δ ROC-AUC of A1 − B1 is +0.152 [+0.126, +0.283], SE 0.050, which gives an **MDE on test of 0.127** <!-- src: results/dev/tough_m1_dev_details.json#mde.comparisons.chosen_A1_raw:A1|pair_only|raw - B1|default|raw|L.mde_test.mde -->. That is four times the 0.03 SESOI. For
   reference, the MDE would be 0.065 if the units were the 530 homology groups. For A1 − B4 the dev Δ is
   +0.194 and the MDE 0.136. Because of the giant unit, the bootstrap distributions are skewed: point estimates
   sit near the lower CI bound, and some CIs are very wide (SiteEngine c2: [0.20, 0.65]).
8. **Controls pass** (random vectors 0.506; shuffled labels 0.499). The global TM-score (B0′) is 0.508, as
   TOUGH-M1's construction intends.

## Deviations and disclosures
- **Cross-fitting fix.** In a B = 50 smoke run (scratch, not in trials.tsv), the first implementation (per-fold
  scaler + `decision_function` with intercept) pooled out-of-fold scores whose intercepts differ across
  fold-sets. Because of the giant unit, training prevalence ranged from 5 % to 44 %. The result was B0m stratified
  AUC 0.24 and cross-fitted A1 0.43 vs 0.80 raw. I changed it to: features z-scored once (label-free), and an
  out-of-fold score of x·β/‖β‖ without intercept. Both versions of the smoke gate were negative. The old
  version's point metrics are kept in `details.build.crossfit_decision_diagnostic`.
- **Shipped scores seen early.** Before fixing the orientations, I computed the label AUCs of all six shipped
  score columns in an exploratory check. Orientations then came from documentation: dataset.info gives
  PS-score and GA-score. The P-value orientation came from a label-free Spearman of −0.67 with the PS-score.
  SiteEngine is reported as shipped, every column included, so nothing was chosen post hoc.
- **Choices fixed before the run** (script docstring):
  - The positive cluster for cb-AUC is the component of the positive-pair graph (76 clusters; the largest has
    25 % of positives).
  - B4's primary variant is the z-scored cosine, with the raw cosine reported alongside.
  - The default_bw scoring variant was added to the A1 candidates.
  - Cross-fitting is unit-disjoint per fold-pair.
- **Units.** The units I computed for test (141) differ from the brief's "530 groups / 302 clusters"; those
  are the counts of the individual graphs, not of their union.

## Suggestions (not run; outside the pre-registered grid)
- Make the D-mode (or a ligand-agnostic L-mode, e.g. pocket = residues within 4 Å of the ligand + bur10 ≥ 0.5,
  which the adapter already has as `alt_*`) a co-headline for C1. At minimum, report C1 in D-mode next to L.
- Revisit the TOUGH-M1 unit definition before unsealing. With a 70 %-of-test giant unit, C1a has about 0.13 MDE.
  Options are the homology-group units with ligand-cluster units as a second definition (and the wider CI), as
  in BLiPS.
- Dock A2 D-mode for the 118 precision-only matched dev pockets. Consider the planned Boltzmann top-3 IFP only
  if A2 is revisited for PPI.
- `glosa_c1` has 172 zeros and SiteEngine has 32. They may be tool failures coded as 0 and should be checked in
  the OSF files.
