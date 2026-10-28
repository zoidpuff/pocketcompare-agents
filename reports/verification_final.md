# Verification of the final held-out evaluation (independent verifier, 2026-10-28)

How I checked: I wrote my own code in `results/verify/` (`vlib.py`, `v_tough.py`, `v_tough_mc.py`, `v_prospeccts.py`, `v_leak.py`, `v_ppips_sens.py`, `v_spot.py`; outputs in `*.json`). It does not import `final_eval.py` or `evaluate.py`. AUCs come from `sklearn.roc_auc_score`, and the vertex bootstrap is my own (multinomial unit counts, pair weight c_u or c_u·c_v, B = 2000, different seeds). I re-derived the units, the D common set, the ProSPECCTs subsets and self-pairs, and the homology groups myself.

The final-method scores were recomputed from the stored part descriptors and the seed weights (z → clip ±5 → linear → L2, mean of the three 128-d seed cosines). They match the method API that final_eval used: max |Δscore| = 1.8e-7 (L) and 2.0e-7 (D).

Sealed files: 9 reads, each logged in `results/verify/unseal_log.tsv`. Every sha256 matched the recorded hash, and every file was back at mode 000 after its read.

| # | check | reported | verifier | verdict |
|---|---|---|---|---|
| 1 | C1a AUC final / B1; Δ | 0.697590 / 0.568358; +0.12923 | 0.697590 / 0.568358; +0.12923 | **PASS** |
| | C1a CI; p | [+0.015, +0.208]; 0.0165 | [+0.023, +0.206]; 0.0145 (B = 20k: [+0.013, +0.204]; 0.0164) | PASS (within MC error) |
| | C1b B4 AUC; Δ; p | 0.568077; +0.12951; 0.0185 | 0.568077; +0.12951; 0.0195 (20k: 0.0171) | **PASS** |
| 2 | C1-D common set (pairs / pos / units) | 21,410 / 8,702 / 102 | 21,410 / 8,702 / 102 (940 of 1,045 pockets D-matched) | **PASS** |
| | C1-D AUCs; Δ; p | 0.699485 / 0.545817; +0.15367; 0.0060 | identical in float32; +0.15367; 0.0095 (20k: 0.0084) | **PASS** |
| 3 | C2 per subset Δ (P5.2 / P6.2 / P7) | +0.0468 / +0.0147 / +0.0055 | identical (9,900 / 62 / 56,350 pairs; 91 / 82 / 615 units) | **PASS** |
| | C2 macro Δ; CI; p | +0.02233; [−0.064, +0.113]; 0.267 | +0.02233; [−0.053, +0.110]; 0.249 | **PASS** |
| 4 | Holm (C1-D, C1a, C1b, C2) | 0.024, 0.0495, 0.0495, 0.267 → R R R A | 0.038, 0.043, 0.043, 0.249 → R R R A (20k: 0.034, 0.049, 0.049) | **PASS, but fragile** (see below) |
| 5 | ProSPECCTs D1 / D1.2 / D2, final, L, no self-pairs | 0.989 / 1.000 / 0.998 | 0.98921 / 1.0 / 0.99843 (same to 1e-8) | PASS |
| | Shuffled-label AUC, final, TOUGH-M1-test | — | 0.492 | PASS |
| | B0, TOUGH-M1-test, L / D | 0.7965 / 0.5555 | 0.7965 / 0.5555 | PASS |
| | Counts vs SPLITS.md (pool 1,045; 10,160 pos / 14,177 neg) | — | identical; 0 self-pairs, 0 duplicates; 922 pockets appear in pairs | PASS (PREREG §2 says "1,014 pockets", which is out of date) |
| | Test vs dev / BLiPS-train v2 (pocket id, PDB+chain, sid, direct homology edge) | — | 0 / 0 / 0 / 0 for both. Shared PDB ids with different chains: 1 (dev), 2 (BLiPS-train), none homologous | PASS |
| | A4b training data (train_a4b.py sha = config `script_sha256`) | — | Only BLiPS-train v2 sites and pairs plus PPIPS-train pockets and pairs. input_stats refit on BLiPS-train L+U reproduces exactly (n = 4,636, Δ = 0). No test item. | PASS (note: 66 test pockets have direct homology edges to PPIPS-train chains. Without them C1a Δ = +0.135, p = 0.005; C1b Δ = +0.132, p = 0.026) |
| 6 | Vertex final L AUC (6,931 protein pairs) | 0.821922 | 0.821922 | PASS |
| | BLiPS-test final L AUC (41,438 pairs) | 0.725843 | 0.725843 | PASS |
| | PPIPS-test P-ortho MRR / top-1 (153 queries) | 0.6832 / 0.5425 | 0.6832 / 0.5425 (no ties) | PASS |

**The Holm result is fragile.** C1a and C1b pass only if the smaller of their two p-values is ≤ 0.05/3 = 0.0167. With B = 20,000 the bootstrap p is 0.0164 for C1a and 0.0171 for C1b. Across the ten 2,000-replicate blocks, p ranges from 0.012 to 0.022. So about 30–50 % of independent B = 2000 runs would not reject C1a/C1b at the family level. The pre-registered run (seed 0) does reject, and that reproduces. It should be reported as borderline. C1-D is robust.

**PI check (a): P6 and P6.2 give identical results.**
- **The source ships one pair list for both.** There is a single `barelier_structures.csv`. The README says D6 and D6.2 differ only in the structure folder: cofactors left out vs included. The sealed P6 and P6.2 pair tables are identical (62 pairs, 19 positive).
- **The loader assigns them correctly.** P6 points to `barelier_structures/`, P6.2 to `barelier_structures_cofactors/`, and 74 of the 115 files differ (the cofactor HETATM records are present).
- **The pipeline is where they become identical.** BURROW featurisation strips every non-protein heavy atom (`pockets.py:252`). As a result the point caches (n_points, volume, D coverage) and the descriptors are identical for all 115 pockets, so the AUCs are identical by construction.
- **Consequence:** the D6.2 "with cofactors" condition is never tested, and the P6.2 term in C2 is in effect D6.
- **D-mode values of 0.5 / 0.75 / 1.0:** 32 pockets are both BURROW-clean and D-matched, but only 4 pairs (2 positive) have both pockets in that set. Those AUCs are meaningless.

**PI check (b): B0 is a ligand-size imprint, not a property of TOUGH-M1 pockets.** I recomputed B0 = −|Δ log size| with several size measures (AUC on TOUGH-M1-test / on full-minus-dev):

| size measure | test | full-minus-dev |
|---|---|---|
| 4 Å ligand-shell volume (reported B0) | 0.796 | 0.815 |
| fpocket Volume of the shipped benchmark pocket | 0.478 | 0.555 |
| fpocket residue count of that pocket | 0.530 | 0.580 |
| BURROW points over the shipped residue list | 0.531 | 0.593 |
| D-mode volume | 0.555 | 0.543 |
| ligand heavy-atom count alone | **0.950** | **0.956** |

- The 4 Å ligand-shell volume tracks ligand size closely (Spearman 0.855).
- TOUGH-M1 positives are defined by ligand Tanimoto similarity, so their ligands have near-equal size: median |Δ log heavy atoms| is 0.03 for positives vs 0.72 for negatives.
- So the size shortcut comes from our ligand-defined L-mode, not from the benchmark's own pocket definitions.
- Every L-mode TOUGH-M1 number carries this imprint. B0m reaches 0.882 on test, and the list TM-score only 0.52 on full-minus-dev.
- The final method itself does not appear to ride it (L 0.698 vs D 0.699).
- C1-D is therefore the cleanest confirmatory claim.

**Verdict:** every headline number reproduces to ≤ 1e-8, or exactly at the float32 precision final_eval used. I found no computational error and no test leakage. The open caveats are the borderline Holm margin for C1a/C1b, P6.2 ≡ P6, and the L-mode ligand-size imprint.
