# Results

Compact copies of the evaluation tables of the frozen method. Source: the research repository's `REPORT.md`
(2026-10-28; section numbers given per table), whose numbers are tagged to result files (`results/final/…`,
`results/pdbt/…`) and were re-derived by an independent verifier with its own code. The method was frozen (commit
e5a6f35, tag `freeze-v1`) before a single evaluation on sealed test sets.

**Arms.** FINAL = this method (A4b:n1_linear, raw cosine). N1 = its non-learned 627-d input descriptor (equal-weight
block cosine). L4 = a point-cloud EGNN candidate (more complex; not shipped). A1 = the typed volumetric fingerprint on
the raw site. B0 = pocket size only (−|Δ log volume|). B1 = BURROW's own 45 size-free pocket descriptors. B4 = ESM-2
mean embedding of the lining residues. B5 = EPoCS. B5-T = scores shipped with TOUGH-M1 (APoc / G-LoSA / SiteEngine).
B0′ = global fold similarity. **L mode** = pocket cut as a 4 Å shell around the bound ligand (literature convention);
**D mode** = the BURROW-detected pocket at the site (the deployment setting; the ligand picks the pocket).
**strat** = AUC within 5 × 20 size strata; **cb** = cluster-balanced AUC (ligand clusters weighted equally).

**Leakage control.** No test protein or homologue (MMseqs2 ≥ 30 % identity, or Foldseek TM ≥ 0.5 both ways) was used
for training the head or BURROW. This removed 76 % of TOUGH-M1, so TOUGH-M1 numbers here are **not** comparable with
published full-set numbers.

## Confirmatory claims (REPORT §4.2; Holm family, one-sided α = 0.05, smallest effect of interest 0.03)

| claim | set / mode | comparison | FINAL | ref | Δ [95 % CI] | Holm p | outcome |
|---|---|---|---|---|---|---|---|
| **C1-D** | TOUGH-M1-test, D (21,410 pairs, 102 units) | FINAL − B1 | 0.699 | 0.546 | **+0.154** [+0.050, +0.289] | 0.024 | rejected H0; robust (verifier p 0.0084–0.0095) |
| C1a | TOUGH-M1-test, L (24,337 pairs, 112 units) | FINAL − B1 | 0.698 | 0.568 | +0.129 [+0.015, +0.208] | 0.0495 | borderline; Monte-Carlo-fragile |
| C1b | TOUGH-M1-test, L | FINAL − B4 (ESM-2) | 0.698 | 0.568 | +0.130 [+0.012, +0.251] | 0.0495 | borderline; Monte-Carlo-fragile |
| C2 | ProSPECCTs P5.2 + P6.2 + P7, L | macro FINAL − B1 | 0.740 | 0.718 | +0.022 [−0.064, +0.113] | 0.267 | **not supported** |

C1-D coverage: 940 of 1,045 pockets have a detected match; 14.4 % of positive pairs fall outside the common set
(worst case, counting them as failures: FINAL 0.537 vs B1 0.419). P6.2 ≡ P6 after cofactor stripping.

## Temporal replication on fresh data (REPORT §4.11; PREREG2, confirmatory)

987 ligand sites in PDB entries released after 2025-11-12 (after every training source), 316 homology groups;
every protein with an edge to any training source removed. D-mode common set: 6,171 pairs (1,060 positive).

| claim | AUC a | AUC b | Δ [95 % CI] | Holm p | outcome |
|---|---|---|---|---|---|
| R1 FINAL − B1 | 0.752 | 0.671 | **+0.081** [+0.028, +0.132] | 0.003 | **replicates** |
| R2 FINAL + L4 fusion − FINAL | 0.762 | 0.752 | +0.010 [−0.010, +0.032] | 0.34 | not supported |
| R3 L4 − FINAL | 0.730 | 0.752 | −0.022 [−0.061, +0.018] | 0.86 | not supported |

L mode: FINAL 0.774 vs B1 0.760 (Δ +0.014 [−0.029, +0.057]): on fresh data the gain over B1 is a detected-pocket gain.

## TOUGH-M1-test, all arms (REPORT §4.3)

| arm | L ROC | L cb | L strat | D ROC | D cb | D strat |
|---|---|---|---|---|---|---|
| **FINAL** | 0.698 | 0.665 | 0.719 | 0.699 | 0.650 | 0.717 |
| N1 (non-learned parent) | 0.692 | 0.627 | 0.675 | 0.655 | 0.615 | 0.641 |
| L4 egnn_small, raw | 0.701 | 0.680 | 0.726 | 0.642 | 0.671 | 0.668 |
| A1 pair_only (ligand-shell fingerprint) | 0.709 | 0.773 | 0.642 | 0.500 | 0.523 | 0.520 |
| B1 BURROW descriptors | 0.568 | 0.624 | 0.567 | 0.546 | 0.564 | 0.552 |
| B4 ESM-2 | 0.568 | 0.641 | 0.573 | 0.545 | 0.636 | 0.554 |
| B5 EPoCS | 0.671 | 0.605 | 0.676 | — | — | — |
| B0 size −\|Δ log V\| | 0.796 | 0.785 | 0.504 | 0.555 | 0.541 | 0.564 |
| B5-T G-LoSA (own pockets) | 0.712 | 0.594 | 0.658 | | | |
| B5-T SiteEngine (own pockets) | 0.692 | 0.658 | 0.613 | | | |
| B5-T APoc PS-score / −log p (own pockets) | 0.602 / 0.630 | 0.539 / 0.548 | 0.546 / 0.604 | | | |
| B0′ TM-score shipped with TOUGH-M1 | 0.439 | 0.508 | 0.453 | | | |
| control: random vectors | 0.504 | 0.474 | 0.505 | | | |

## The ligand-size imprint (REPORT §4.4)

| size measure used as a score, −\|Δ\| | TOUGH-M1-test | TOUGH-M1 full minus dev |
|---|---|---|
| 4 Å ligand-shell volume (B0, L mode) | 0.796 | 0.815 |
| fpocket volume of TOUGH-M1's shipped pocket | 0.478 | 0.555 |
| D-mode (BURROW-detected) volume | 0.555 | 0.543 |
| **ligand heavy-atom count alone** | **0.950** | **0.956** |

TOUGH-M1 positives share ligands by Tanimoto similarity, so their ligands are nearly the same size; a 4 Å shell
inherits ligand size (Spearman 0.855 with shell volume). Ligand-defined (L-mode) benchmark numbers, ours and
published, therefore overstate pocket similarity. The A1 fingerprint on the raw shell collapses from 0.709 (L) to
0.500 (D); FINAL, which describes the sph8 site, is the same in both (0.698 / 0.699).

## BLiPS-test: holo structures and AlphaFold models (REPORT §4.6)

| arm | holo L ROC / cb / strat | holo D ROC / cb / strat | AF L ROC | AF D ROC | holo L, unseen chemotype |
|---|---|---|---|---|---|
| **FINAL** | 0.726 / 0.676 / 0.720 | 0.728 / 0.712 / 0.722 | 0.730 | 0.723 | 0.685 |
| N1 | 0.702 / 0.676 / 0.697 | 0.683 / 0.702 / 0.677 | 0.698 | 0.687 | 0.683 |
| L4 raw | 0.738 / 0.665 / 0.733 | 0.740 / 0.699 / 0.735 | 0.741 | 0.752 | 0.715 |
| B1 | 0.736 / 0.717 / 0.727 | 0.648 / 0.665 / 0.642 | 0.727 | 0.658 | 0.770 |
| B4 ESM-2 | 0.679 / 0.682 / 0.678 | 0.655 / 0.707 / 0.654 | 0.665 | 0.643 | 0.717 |
| B0 size | 0.605 / 0.612 / 0.502 | 0.568 / 0.569 / 0.565 | — | — | 0.576 |

Paired holo − AF Δ for FINAL (computed post hoc with the frozen functions): L −0.004 [−0.020, +0.010], D +0.004
[−0.016, +0.028], both inside ±0.03: no AlphaFold penalty. Unseen chemotypes are FINAL's weak spot.

## ProSPECCTs, all subsets (REPORT §4.7; ROC-AUC, L mode, self-pairs removed)

| arm | P1 | P1.2 | P2 | P3 | P4 | P5 | P5.2 | P6 (≡ P6.2) | P7 |
|---|---|---|---|---|---|---|---|---|---|
| **FINAL** | 0.989 | 1.000 | 0.998 | 0.718 | 0.707 | 0.717 | 0.709 | 0.622 | 0.890 |
| N1 | 0.991 | 1.000 | 0.994 | 0.707 | 0.698 | 0.708 | 0.680 | 0.693 | 0.892 |
| L4 raw | 0.996 | 1.000 | 1.000 | 0.853 | 0.848 | 0.647 | 0.637 | 0.649 | 0.849 |
| B1 | 0.991 | 1.000 | 0.999 | 0.726 | 0.694 | 0.679 | 0.662 | 0.607 | 0.885 |
| B4 ESM-2 | 1.000 | 1.000 | 1.000 | 0.758 | 0.794 | 0.624 | 0.650 | 0.433 | 0.832 |
| B0 size | 0.608 | 0.798 | 0.798 | 0.573 | 0.553 | 0.645 | 0.707 | 0.561 | 0.644 |
| B0′ Foldseek TM | 1.000 | 1.000 | 0.998 | 0.440 | 0.440 | 0.519 | 0.522 | 0.343 | 0.782 |

P1/P1.2/P2 are ceiling sets (fold and sequence ≈ 1.0); P3/P4 are physicochemical/shape decoys (L4 clearly better);
P5–P7 test what is claimed, and FINAL is close to B1 there. ProSPECCTs data cannot be redistributed and is not part
of this repository.

## Vertex (REPORT §4.8; L mode, protein-pair maximum)

| | FINAL | N1 | L4 raw | A1 | B1 | B4 | B0 | B0′ Foldseek TM |
|---|---|---|---|---|---|---|---|---|
| ROC-AUC | 0.822 | 0.796 | 0.840 | 0.621 | 0.721 | 0.837 | 0.527 | 0.910 |

Vertex positives are largely homologous; it measures homology recovery, not fold-independent similarity.

## Protein–protein interface pockets: PPIPS-test (REPORT §4.9)

| arm | P-ortho top-1 | top-3 | MRR [95 % CI] | P-sym percentile |
|---|---|---|---|---|
| **FINAL** | 0.542 | 0.778 | 0.683 [0.607, 0.772] | 0.998 |
| N1 | 0.490 | 0.752 | 0.650 [0.551, 0.800] | 0.998 |
| L4 raw | 0.614 | 0.856 | 0.747 [0.594, 0.864] | 0.999 |
| B1 | 0.464 | 0.725 | 0.628 [0.502, 0.852] | 0.994 |
| B4 ESM-2 (sequence) | 0.908 | 1.000 | 0.954 [0.919, 1.000] | 1.000 |
| B0 size | 0.190 | 0.497 | 0.396 [0.302, 0.524] | 0.777 |

P-ortho (find the interolog's interface pocket among AlphaFold dimers) rewards sequence homology. The
ligand-grounded PPI test (PPI-L) had 3 positive test pairs and was not scored; an exploratory cross-family test of
PPI-modulator pockets was negative (FINAL AUC 0.552 [0.495, 0.590]).

## Blind deployment test (REPORT §4.10)

3,600 ligand sites on 2,295 BLiPS-test AlphaFold models; pool = all 13,876 merged BURROW pockets of those models.
BURROW detection recall 0.700 [0.676, 0.723]. With both partners detected (8,048 directed positive pairs): FINAL AUC
0.719 [0.684, 0.761] vs B1 0.688 and size 0.583; hit@100 0.078 (chance ≈ 0.007), MRR 0.009. Counting missed
detections as misses: FINAL 0.628, B1 0.610.

## Method selection on development data (REPORT §5; BLiPS-val, TOUGH-M1-dev, PPIPS-val)

| candidate | dims | BLiPS-val D cb (SE) | BLiPS-val L cb | TOUGH-M1-dev D cb | TOUGH-M1-dev L cb | PPIPS-val MRR |
|---|---|---|---|---|---|---|
| B1 BURROW descriptors | 45 | 0.648 (0.040) | 0.701 | 0.617 | 0.639 | 0.761 |
| B4 ESM-2 raw | 1280 | 0.670 | 0.641 | 0.598 | 0.602 | 0.986 |
| N1, non-learned | 627 | 0.697 (0.040) | 0.706 | 0.667 | 0.656 | 0.790 |
| A4b n1_base (MLP head) | 384 | 0.717 (0.038) | 0.702 | 0.687 | 0.695 | 0.694 |
| **A4b n1_linear (FINAL)** | 384 | **0.737** (0.038) | 0.718 | 0.721 | 0.720 | 0.719 |
| L4 egnn_small, CSLS | 384 | 0.756 (0.040) | 0.765 | 0.661 | 0.694 | 0.821 |

Pre-registered rule: among candidates within one SE of the best, the simplest. All heads store 384 dims; the
tie-break "fewest parameters" (picking n1_linear) was set by the PI after seeing this table (disclosed, D19).

## Runtime and scale (REPORT §7; [AFDB_COST.md](AFDB_COST.md))

| item | value |
|---|---|
| BURROW + describe, per structure, 1 core (AFDB human, 5.7 pockets) | median 0.42 s (ref CPU), 0.21 s (fast CPU), 0.13 s (GPU, RTX 4090) |
| descriptor + embedding per detected pocket (after BURROW) | median 3.5 ms (p90 4.6); ligand site 6.1 ms; head 64 µs |
| pair score, batched against 10⁶ vectors | 0.10–0.65 µs |
| storage per pocket | 1,536 B float32; 768 B fp16; 94 B OPQ64-IVF-PQ64 code |
| human AFDB v6 (23,586 models → 116,246 pockets) | 178 s on 2 × RTX 4090 + 22 CPU workers |
| search, 116 k pockets | exact 7.3 ms/query (1 thread); PQ nprobe 64 + re-rank of top-100: recall@10 0.987, 0.77 ms/query |
| full node (64 cores, 4 × RTX 4090) | 380 structures/s (GPU path), 234 structures/s (CPU only) |
