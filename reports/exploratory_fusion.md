EXPLORATORY — post-test; not a confirmatory result

# Score fusion of FINAL (A4b:n1_linear raw) and L4:egnn_small raw (2026-10-28)

**Question.** The test numbers showed that L4 is stronger on BLiPS, the ProSPECCTs decoy subsets P3/P4 and PPIPS, while A4b is stronger on TOUGH-M1 D. Does a score-level fusion of the two help? Everything below was motivated by test data, so it is exploratory and changes no PREREG claim.

**Protocol** (fixed in the header of `scripts/explore/fusion_a4b_l4.py` before any fused score existed)
- **Fused score:** s = w·z(cos_A4b) + (1−w)·z(cos_L4), with both cosines raw.
- **z-scoring (declared):** each method's μ/σ is fitted on all 41,952 BLiPS-train v2 pairs, L-mode and D-mode pooled. σ_A = 0.280 and σ_L = 0.246; the two cosines correlate at r = 0.72.
- **Implementation:** the fused score is the inner product of the concatenation [√(w/σ_A)·e_A, √((1−w)/σ_L)·e_L], 768 dims. This lets every eval_dev / final_eval code path run unchanged.
- **Choosing w:** on dev only, among w ∈ {0.25, 0.5, 0.75}, by BLiPS-val D-mode cb-AUC with the one-SE rule (prefer w = 0.5 if it is within one SE). Best was w = 0.25 at 0.761 (SE 0.039), so the threshold is 0.722. w = 0.5 scored 0.761, so **w\* = 0.5**.
- **Test:** one look, w\* only. 7 sealed reads, logged in `results/exploratory/unseal_log.tsv`; all hashes OK and all files back at mode 000.
- **Sanity check:** FINAL and L4 were recomputed on the same code path and match `results/final` exactly (130 rows, max |Δ| = 0).

**Dev** (cb-AUC; Δ is fused − FINAL with shared bootstrap weights, homology-group / TOUGH units)

| | BLiPS-val D | BLiPS-val L | TM-dev D | TM-dev L | PPIPS-val MRR |
|---|---|---|---|---|---|
| FINAL / L4 | 0.737 / 0.748 | 0.718 / 0.760 | 0.721 / 0.660 | 0.720 / 0.688 | 0.719 / 0.831 |
| fused w = 0.25 / **0.50** / 0.75 | 0.761 / **0.761** / 0.753 | 0.769 / **0.765** / 0.745 | 0.691 / **0.714** / 0.723 | 0.713 / **0.728** / 0.729 | 0.825 / **0.816** / 0.776 |
| Δ, w = 0.5 [95 % CI] | +0.024 [−0.004, +0.064] | +0.046 [+0.014, +0.079] | −0.007 [−0.051, +0.019] | +0.008 [−0.033, +0.025] | +0.097 (point estimate) |

The un-normalised raw sum at w = 0.5 is a dev-only sensitivity check and was never selected. It is nearly identical: 0.760 / 0.763 / 0.715 / 0.729.

**Test, one look, w = 0.5** (ROC-AUC; paired Δ fused − FINAL, vertex bootstrap B = 2000, the wider CI over final_eval's unit definitions, common set)

| set | fused | FINAL | Δ [95 % CI] |
|---|---|---|---|
| TOUGH-M1-test L | 0.723 | 0.698 | +0.026 [−0.031, +0.052] (cb +0.028 [−0.017, +0.042]) |
| TOUGH-M1-test D | 0.693 | 0.699 | **−0.007 [−0.038, +0.009]** (cb +0.027 [−0.046, +0.039]) |
| BLiPS-test L / D | 0.755 / 0.757 | 0.726 / 0.728 | +0.030 [+0.015, +0.042] / +0.029 [+0.015, +0.042] |
| BLiPS-test AF L / D | 0.760 / 0.762 | 0.730 / 0.723 | +0.029 [+0.017, +0.039] / +0.039 [+0.025, +0.054]; fused holo − AF −0.004 / −0.009 (CIs include 0) |
| ProSPECCTs P3 / P4, L (no self-pairs) | 0.780 / 0.770 | 0.718 / 0.707 | +0.062 [+0.038, +0.081] / +0.064 [+0.036, +0.084]; D +0.036 / +0.050 |
| ProSPECCTs P1 / P2, L | 0.996 / 1.000 | 0.989 / 0.998 | +0.007 [−0.002, +0.033] / +0.001 [+0.000, +0.005] |
| ProSPECCTs P5 / P5.2 / P6 / P7, L (C2 subsets) | 0.700 / 0.689 / 0.662 / 0.895 | 0.717 / 0.709 / 0.622 / 0.890 | −0.016 / −0.019 [−0.043, +0.006] / +0.040 / +0.004 (all CIs include 0) |
| Vertex (protein pairs) | 0.847 | 0.822 | +0.025 [−0.011, +0.056] |
| PPIPS-test P-ortho MRR / top-1 | 0.743 / 0.595 | 0.683 / 0.542 | +0.059 [+0.008, +0.108] / +0.052 [−0.020, +0.123] (12 query groups) |

Not run: TOUGH-M1 full-minus-dev, because learned arms are not reported there (D8), and PPI-L, which was skipped in the final run too. The P6 / P6.2 D-mode set has 4 pairs and is meaningless.

**Runtime** (BURROW featurisation of about 0.43 s/pocket is shared and not counted)
- **Fused, per D pocket:** about 8.9 ms with a GPU for L4, or about 55 ms on 1 CPU thread. This is 15–16× the 3.5 ms of FINAL on CPU.
  - A4b: 3.5 ms.
  - L4 point-set extraction: about 4.8 ms.
  - L4 forward: 0.54 ms on GPU or 47 ms on 1 CPU thread.
- **Storage:** 3,072 bytes per pocket, against 1,536.
- **Pair scoring:** 1.15 µs per pair at 768 dims, against 0.65 µs at 384 dims, batched on this node.

**Reading.**
- **Where fusion helps:** it is better or equal on everything where L4 was better, without losing L4's in-distribution gains. That covers BLiPS including AF models, the ProSPECCTs decoys P3/P4, PPIPS and Vertex.
- **Where it does not:** it gives up nothing measurable on TOUGH-M1 D, but it does not improve it either. TOUGH-M1 D is the deployment-mode, fold-independent set and our cleanest confirmatory endpoint (C1-D). Its ROC Δ is −0.007, and the cb Δ is positive with a CI that includes 0.
- **Why the gains are suspect:** the gains are on sets that motivated the analysis, so they are biased by selection on test outcomes. The L-mode TOUGH-M1 gain (+0.026) is in the ligand-imprinted mode.
- **Cost:** fusion needs the L4 stack (a GPU, or 47 ms/pocket on CPU).
- **Recommendation:** do not replace FINAL. If wanted, ship fusion as an optional "accuracy" mode. Any claim for it would need a fresh held-out set.

Files: `results/exploratory/fusion/` (`dev/`, `test_{summary,deltas,ppips,details}`, `fusion_{scales,runtime}.json`, each with `.prov.json`). Trials: 107 rows tagged `exploratory_posttest` (40 dev, 67 test).
