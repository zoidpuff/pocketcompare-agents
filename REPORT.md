# pocketcompare: fast, fold-independent pocket similarity on BURROW (final report)

Status: 2026-10-28. The method was frozen at commit e5a6f35 (`FREEZE.json`, tag `freeze-v1`) and evaluated once on
the sealed test sets (`results/final/`). An agent that did not produce the numbers re-derived every headline with its
own code (`reports/verification_final.md`). This report replaces `REPORT_draft.md`, which was written before the test.

Three kinds of result are kept apart. **Confirmatory** results are the four pre-registered Holm-family claims
(PREREG §2). **Reported** results are pre-registered descriptive metrics (PREREG §3). **EXPLORATORY (post-test)**
results were motivated by test numbers and carry no evidential weight (§8). Numbers carry `<!-- src: ... -->` tags;
`path#key` tags are checked by `python scripts/check_report.py REPORT.md`.

Arms: **FINAL** = A4b:n1_linear, raw cosine (the frozen method). **N1** = its non-learned input descriptor.
**L4** = point-cloud EGNN (best dev candidate, more complex). **A1** = typed volumetric fingerprint on the raw site.
**B0** = pocket size. **B1** = BURROW's own descriptors. **B4** = ESM-2 lining-residue embedding. **B5** = EPoCS.
**B5-T** = the APoc / G-LoSA / SiteEngine scores shipped with TOUGH-M1. **B0′** = global fold similarity.
**L-mode** = pocket cut as a 4 Å shell around the bound ligand. **D-mode** = the BURROW-detected pocket at the site.

---

## 1. Summary

- **Tool.** `pocketcompare` maps every BURROW pocket (PDB entry, AF model or dimer) to a 384-d unit vector. The pipeline is: ligand-free sph8 site → cavity + lining descriptor (N1, 627 d) → frozen linear contrastive head (A4b:n1_linear). Scores are cosines, searched with FAISS; no sequence, fold or ligand input is used.
- **C1-D (headline, robust).** On TOUGH-M1-test with detected pockets, FINAL scores ROC 0.699 <!-- src: results/final/final_claims.json#C1-D.auc_a --> against B1's 0.546 <!-- src: results/final/final_claims.json#C1-D.auc_b -->. Δ = +0.154 <!-- src: results/final/final_claims.json#C1-D.delta --> [+0.050 <!-- src: results/final/final_claims.json#C1-D.ci_low -->, +0.289 <!-- src: results/final/final_claims.json#C1-D.ci_high -->], Holm p 0.024 <!-- src: results/final/final_claims.json#C1-D.p_holm -->. The verifier reproduced it.
- **C1a/C1b (borderline).** In L-mode, Δ is +0.129 <!-- src: results/final/final_claims.json#C1a.delta --> against B1 and +0.130 <!-- src: results/final/final_claims.json#C1b.delta --> against ESM-2, Holm p 0.0495 <!-- src: results/final/final_claims.json#C1a.p_holm -->. Both are Monte-Carlo-fragile: 30–50 % of independent B = 2,000 bootstraps would not reject. <!-- src: reports/verification_final.md -->
- **C2 (not supported).** On ProSPECCTs P5.2/P6.2/P7, the macro Δ is +0.022 <!-- src: results/final/final_claims.json#C2.delta --> [−0.064 <!-- src: results/final/final_claims.json#C2.ci_low -->, +0.113 <!-- src: results/final/final_claims.json#C2.ci_high -->], p 0.27 <!-- src: results/final/final_claims.json#C2.p_holm -->.
- **Size-stratified.** FINAL scores 0.719 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=L] --> (L) and 0.717 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=D] --> (D). B1 scores 0.567 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B1,variant=raw,mode=L] -->, ESM-2 0.573 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B4,config=esm2,variant=raw,mode=L] --> and size alone 0.504 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B0,variant=raw,mode=L] -->. FINAL's ROC is the same in L and D.
- **AlphaFold.** On BLiPS-test, AF-model pockets score about the same as holo pockets: D 0.723 <!-- src: results/final/final_summary.parquet#auc[set=blips_test_af,subset=all,arm=FINAL,variant=raw,mode=D] --> vs 0.728 <!-- src: results/final/final_summary.parquet#auc[set=blips_test,subset=all,arm=FINAL,variant=raw,mode=D] -->. The paired holo − AF Δ (computed post hoc after a final_eval bug, DEV6) is −0.004 [−0.020, +0.010] (L) and +0.004 [−0.016, +0.028] (D): no AF penalty. <!-- src: reports/final_post_reported.md -->
- **Ligand imprint.** 4 Å ligand-shell pockets encode ligand size. Ligand heavy-atom count alone gives ROC 0.95 on TOUGH-M1-test, against 0.48–0.53 for TOUGH-M1's own fpocket pockets. <!-- src: reports/verification_final.md --> L-mode benchmark numbers, ours and published, therefore partly measure ligand size. Detected-pocket or size-stratified evaluation should be used instead.
- **Against published methods.** We scored their shipped scores on our TOUGH-M1-test partition. G-LoSA / SiteEngine / APoc reach raw ROC 0.712 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B5T,config=glosa_ga,mode=native] --> / 0.692 / 0.60–0.63 and stratified 0.658 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B5T,config=glosa_ga,mode=native] --> / 0.613 / 0.55–0.60. FINAL reaches 0.698 / 0.719: level on raw ROC and ahead after stratification, with no paired CI. FINAL scores a pair with one dot product.
- **Runtime.** After BURROW a pocket takes ≈ 3.5 <!-- src: results/dev/final_method_runtime.json#D_ms_per_pocket_median --> ms, and a structure 0.13–0.42 s end to end. A pair costs 0.1–0.7 µs, and storage is 1,536 B per pocket (94 B as PQ). The 116 k-pocket human AFDB set took ≈ 3 min on one node, and the exact all-vs-all top-50 search takes 0.41 <!-- src: results/release/human_afdb_v6.json#exact.all_vs_all_top50_gpu_s --> s on one GPU. Extrapolated to 200 M AFDB structures: ≈ 7,150 CPU-core-h + 223 <!-- src: results/proteome/summary.json#extrapolation_200M.gpu_hours --> GPU-h.
- **Negatives.** Fragment docking failed its gate. The ligand-grounded PPI test (PPI-L) was infeasible, with 3 test positives. PPI pockets are judged only by ortholog transfer (PPIPS), where ESM-2 wins (MRR 0.954 vs FINAL 0.683).
- **Temporal replication (PREREG2, fresh data).** On 987 ligand sites from PDB entries released after 2025-11-12
  (after every training source; 316 homology groups), FINAL scores D-mode ROC 0.752 <!-- src: results/pdbt/claims.json --> vs B1 0.671: Δ +0.081
  [+0.028, +0.132], Holm p 0.003 (R1, replicates). The exploratory fusion (+0.010, p 0.34) and L4 (−0.022) do
  **not** beat FINAL (R2/R3), vindicating the pre-registered choice of the simpler linear head. <!-- src: results/pdbt/report.md -->
- **Not best everywhere.** L4 wins on BLiPS, PPIPS and ProSPECCTs P3/P4. Sequence and fold win on homology-driven sets (Vertex, P1/P2).

---

## 2. Problem, scope, benchmarks

**Task.** Score whether two binding pockets are similar, meaning they bind the same or similar ligands, without
using sequence or fold. Pockets come from BURROW. The method must run at AFDB scale (≈ 200 M structures × ~5 pockets),
work on AlphaFold models and handle pockets at protein–protein interfaces.

**What "fold-independent" means here.**
- The method takes no sequence or fold input.
- In the primary benchmark (TOUGH-M1), positives and negatives are both structurally unrelated. Global TM-score
  scores 0.44 on our test partition (§4.3).
- No test protein, or homologue of one, was used in training or in BURROW's training data. Homology means MMseqs2
  ≥ 30 % identity, or Foldseek TM ≥ 0.5 in both directions.

**Pocket definitions.**
- **L-mode:** BURROW grid points within 4 Å of the benchmark ligand. This is the literature convention.
- **D-mode:** the BURROW-detected pocket that best covers the site (coverage ≥ 0.3 or precision ≥ 0.5). The ligand
  picks the pocket, so D-mode is an oracle-assisted proxy for deployment.

| set | role | test size | notes |
|---|---|---|---|
| TOUGH-M1, BURROW-clean split | C1a/C1b (L), C1-D (D) | 1,045 pockets; 24,337 pairs (10,160 pos) | dev = the 765 pockets in groups homologous to BURROW training; 5,714 pockets excluded by the leakage rule |
| ProSPECCTs D5.2 + D6.2 + D7, self-pairs removed | C2 (L) | 66,312 pairs | all 10 subsets reported |
| Vertex | reported (L) | 6,931 protein pairs | site rule = DeeplyTough's public rule (D17) |
| BLiPS (our BioLiP ligand-sharing pairs) | training, selection, reported test, AF robustness (C5) | 3,606 sites, 41,438 pairs (6,905 pos) | test = BURROW's held-out af_set; every site has an AF model |
| PPIPS (AFDB predicted dimers) | PPI training, reported | 153 P-ortho queries, 544 P-sym | P-ortho = cross-species interolog pocket retrieval |
| PPI-L (PPI-modulator pocketome) | planned C3 → exploratory | 3 positive test pairs | feasibility gate failed (D7) |
<!-- src: results/final/final_report.md, data/splits/SPLITS.md, reports/ppi_datasets.md -->

**The cost of leakage control.** 32 % of TOUGH-M1 proteins are homologous to BURROW training. The rule that
excludes groups touching both BURROW and a sealed set removes 76 % of TOUGH-M1. The test set is therefore ~1 k
pockets in 102–112 units, one of which holds most pockets. The dev-projected minimum detectable effect is
≈ 0.12–0.13 AUC, against a smallest effect of interest (SESOI) of 0.03. Our TOUGH-M1 numbers are **not** comparable
with published full-set numbers. <!-- src: RESEARCH_TREE.md D4 D8 D12, data/splits/SPLITS.md -->

---

## 3. The method (frozen: `configs/final_method.yaml`)

```
structure (PDB / AF model / dimer)
 │  BURROW featurisation (analytic point features only; ligands, waters, ions, cofactors stripped)   0.1–0.4 s
 ▼
site: D = BURROW pocket (deployment) │ L = 4 Å ligand shell │ residue list
 ▼
sph8 shaper: buried grid points (bur10 ≥ 0.5) within 8 Å of the buriedness-weighted centroid       < 0.5 ms
 ▼
A1 typed volumetric fingerprint (514 d) ⊕ env protein-environment block (113 d) = N1 (627 d)        ~3.5 ms
 ▼
z-score (BLiPS-train stats), clip ±5 → 3 linear heads 627→128 (seeds 0–2), L2 → concat/√3          64 µs
 ▼
384-d unit vector; score = inner product (= mean seed cosine); FAISS IndexFlatIP or OPQ-IVF-PQ
```
<!-- src: configs/final_method.yaml, reports/a4b_selection.md, reports/a1_descriptors.md, results/dev/final_method_runtime.json -->

- **sph8** describes the same object however the site was found, so it removes the ligand-shape imprint by
  construction. Label-free retrieval of a site's D vector from its L vector reaches AUC 0.996, against 0.765 for A1
  on the raw definitions. <!-- src: reports/definition_robustness.md -->
- **A1** has five blocks:
  - histograms of soft VolSite-like point types × buriedness;
  - Gaussian-binned pair distances for 28 type pairs;
  - USR-like shape moments;
  - global shape scalars;
  - log volume.

  It is exactly rigid-motion invariant (error ≤ 1.3e-7). **env** holds BURROW's lining chemistry and
  residue-group composition. <!-- src: reports/a1_descriptors.md -->
- **The head.** The linear head was trained contrastively (InfoNCE + BCE) on three kinds of pair:
  - 6,992 BLiPS-train ligand-sharing pairs;
  - 1,602 same-site L↔D pairs, which teach invariance to the pocket definition;
  - 3,177 PPIPS-train dimer-pocket pairs.

  It never saw TOUGH-M1, BLiPS-val, PPIPS-val or any test set. <!-- src: reports/a4b_selection.md -->
- **API and CLI.**
  - API: `method.describe`, `describe_all`, `similarity`.
  - CLI: `pocketcompare describe | compare | index | search`.
  - The config, weights and statistics are sha256-verified on load.
  - Usage is in README.md and docs/FINGERPRINTS.md.

---

## 4. Test-set results (frozen method, single evaluation)

### 4.1 Protocol
- **How it ran.** `scripts/final_eval.py` ran with FINAL_EVAL=1 from a worktree at the frozen commit, with evaluate.py
  at sha256 f22d0296…, B = 2,000 vertex-bootstrap replicates and seed 0.
- **Sealed files.** Nine sealed files were read, each logged with its hash (`results/final/unseal_log.tsv`).
- **Size stratification.** strat = AUC within 5 (mean log volume) × 20 (|Δ log volume|) bins.
- **cb.** cb = cluster-balanced AUC, which weights ligand clusters equally.
- **CSLS.** B1 and B4 get the same CSLS treatment as FINAL, which is none.

### 4.2 Confirmatory claims (Holm family, one-sided α = 0.05, H0: Δ ≤ 0, SESOI 0.03)

| claim | set / mode | comparison | FINAL | ref | Δ [95 % CI] | p | Holm p | reject | robustness |
|---|---|---|---|---|---|---|---|---|---|
| **C1-D** | TOUGH-M1-test, D (common set: 21,410 pairs, 102 units) | FINAL − B1 | 0.699 <!-- src: results/final/final_claims.json#C1-D.auc_a --> | 0.546 <!-- src: results/final/final_claims.json#C1-D.auc_b --> | +0.154 <!-- src: results/final/final_claims.json#C1-D.delta --> [+0.050 <!-- src: results/final/final_claims.json#C1-D.ci_low -->, +0.289 <!-- src: results/final/final_claims.json#C1-D.ci_high -->] | 0.0060 <!-- src: results/final/final_claims.json#C1-D.p_one_sided --> | 0.024 <!-- src: results/final/final_claims.json#C1-D.p_holm --> | yes | robust: verifier p 0.0095 (B = 2k), 0.0084 (B = 20k) |
| C1a | TOUGH-M1-test, L (24,337 pairs, 112 units) | FINAL − B1 | 0.698 <!-- src: results/final/final_claims.json#C1a.auc_a --> | 0.568 <!-- src: results/final/final_claims.json#C1a.auc_b --> | +0.129 <!-- src: results/final/final_claims.json#C1a.delta --> [+0.015 <!-- src: results/final/final_claims.json#C1a.ci_low -->, +0.208 <!-- src: results/final/final_claims.json#C1a.ci_high -->] | 0.0165 <!-- src: results/final/final_claims.json#C1a.p_one_sided --> | 0.0495 <!-- src: results/final/final_claims.json#C1a.p_holm --> | yes, borderline | MC-fragile: needs p ≤ 0.0167; B = 20k gives 0.0164 |
| C1b | TOUGH-M1-test, L | FINAL − B4 (ESM-2) | 0.698 | 0.568 <!-- src: results/final/final_claims.json#C1b.auc_b --> | +0.130 <!-- src: results/final/final_claims.json#C1b.delta --> [+0.012 <!-- src: results/final/final_claims.json#C1b.ci_low -->, +0.251 <!-- src: results/final/final_claims.json#C1b.ci_high -->] | 0.0185 <!-- src: results/final/final_claims.json#C1b.p_one_sided --> | 0.0495 <!-- src: results/final/final_claims.json#C1b.p_holm --> | yes, borderline | same; B = 20k gives 0.0171 |
| C2 | ProSPECCTs P5.2 + P6.2 + P7, L, no self-pairs | macro FINAL − B1 | 0.740 <!-- src: results/final/final_claims.json#C2.auc_a --> | 0.718 <!-- src: results/final/final_claims.json#C2.auc_b --> | +0.022 <!-- src: results/final/final_claims.json#C2.delta --> [−0.064 <!-- src: results/final/final_claims.json#C2.ci_low -->, +0.113 <!-- src: results/final/final_claims.json#C2.ci_high -->] | 0.267 <!-- src: results/final/final_claims.json#C2.p_one_sided --> | 0.267 <!-- src: results/final/final_claims.json#C2.p_holm --> | no | P6.2 ≡ P6 (DEV5) |
<!-- src: results/verify/v_holm.json, results/verify/v_tough_mc_C1a.json, reports/verification_final.md -->

How to read the claims:
- **C1-D is the result to cite.** It uses detected pockets, the deployment setting, on a fold-independent and
  BURROW-clean test, and it survives every re-analysis.
- **C1-D's coverage.**
  - 940 of 1,045 pockets have a D match.
  - 14.4 % <!-- src: results/final/final_summary.parquet#miss_rate_pos_all[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=D] --> of positive pairs fall outside the common set.
  - Scoring every missing pair as a failure gives FINAL a worst-case AUC of 0.537 <!-- src: results/final/final_summary.parquet#auc_worst_all[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=D] -->, against 0.419 for B1.
- **C1a/C1b are borderline.** Holm passes only if the smaller of their p-values is ≤ 0.05/3. Across ten 2,000-replicate
  blocks the verifier saw p from 0.012 to 0.022. Report them as "rejected in the pre-registered run, not robust to
  Monte-Carlo error". They are also L-mode results, which carry the ligand imprint (§4.4); FINAL's L and D AUCs are
  nonetheless equal.
- **DEV4 sensitivity.**
  - 66 TOUGH-M1-test pockets have homology edges to PPIPS-train chains used to train the head.
  - Without them, C1a is Δ +0.135 (p 0.005) and C1b is Δ +0.132 (p 0.026, CI lower bound −0.002).
  - The effect sizes do not change. <!-- src: results/verify/v_ppips_sens.json -->
- **C2 is not supported.**
  - Per-subset Δ: P5.2 +0.047 [+0.001, +0.095], P6.2 +0.015, P7 +0.006. <!-- src: results/final/final_claims.json -->
  - P6.2 is identical to P6 because BURROW strips the cofactors that distinguish them. The macro Δ therefore
    double-weights P6, and the "with cofactors" condition was never tested (DEV5).
  - The pre-registered PREREG text says "1,014 pockets" for TOUGH-M1-test. That number predates the split rebuild;
    the evaluated pool is 1,045.

### 4.3 TOUGH-M1-test, all arms (reported)

| arm | L ROC | L cb | L strat | D ROC | D cb | D strat |
|---|---|---|---|---|---|---|
| **FINAL** (A4b:n1_linear) | 0.698 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=L] --> | 0.665 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=L] --> | 0.719 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=L] --> | 0.699 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=D] --> | 0.650 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=D] --> | 0.717 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=FINAL,variant=raw,mode=D] --> |
| N1 (non-learned parent) | 0.692 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=N1,config=N1,variant=raw,mode=L] --> | 0.627 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=N1,config=N1,variant=raw,mode=L] --> | 0.675 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=N1,config=N1,variant=raw,mode=L] --> | 0.655 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=N1,config=N1,variant=raw,mode=D] --> | 0.615 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=N1,config=N1,variant=raw,mode=D] --> | 0.641 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=N1,config=N1,variant=raw,mode=D] --> |
| L4 egnn_small, CSLS (declared arm) | 0.653 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=csls,mode=L] --> | 0.688 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=csls,mode=L] --> | 0.695 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=csls,mode=L] --> | 0.604 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=csls,mode=D] --> | 0.668 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=csls,mode=D] --> | 0.644 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=csls,mode=D] --> |
| L4 egnn_small, raw | 0.701 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=raw,mode=L] --> | 0.680 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=raw,mode=L] --> | 0.726 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=raw,mode=L] --> | 0.642 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=raw,mode=D] --> | 0.671 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=raw,mode=D] --> | 0.668 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=L4,config=L4:egnn_small,variant=raw,mode=D] --> |
| A1 pair_only (4 Å shell fingerprint) | 0.709 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=A1,config=pair_only,variant=raw,mode=L] --> | 0.773 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=A1,config=pair_only,variant=raw,mode=L] --> | 0.642 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=A1,config=pair_only,variant=raw,mode=L] --> | 0.500 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=A1,config=pair_only,variant=raw,mode=D] --> | 0.523 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=A1,config=pair_only,variant=raw,mode=D] --> | 0.520 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=A1,config=pair_only,variant=raw,mode=D] --> |
| B1 BURROW descriptors | 0.568 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B1,config=default,variant=raw,mode=L] --> | 0.624 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B1,config=default,variant=raw,mode=L] --> | 0.567 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B1,config=default,variant=raw,mode=L] --> | 0.546 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B1,config=default,variant=raw,mode=D] --> | 0.564 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B1,config=default,variant=raw,mode=D] --> | 0.552 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B1,config=default,variant=raw,mode=D] --> |
| B4 ESM-2 (z) | 0.568 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B4,config=esm2,variant=raw,mode=L] --> | 0.641 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B4,config=esm2,variant=raw,mode=L] --> | 0.573 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B4,config=esm2,variant=raw,mode=L] --> | 0.545 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B4,config=esm2,variant=raw,mode=D] --> | 0.636 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B4,config=esm2,variant=raw,mode=D] --> | 0.554 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B4,config=esm2,variant=raw,mode=D] --> |
| B5 EPoCS | 0.671 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B5,config=epocs,variant=raw,mode=L] --> | 0.605 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B5,config=epocs,variant=raw,mode=L] --> | 0.676 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B5,config=epocs,variant=raw,mode=L] --> | — | — | — |
| B0 size −\|Δ log V\| | 0.796 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B0,config=default,variant=raw,mode=L] --> | 0.785 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B0,config=default,variant=raw,mode=L] --> | 0.504 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B0,config=default,variant=raw,mode=L] --> | 0.555 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B0,config=default,variant=raw,mode=D] --> | 0.541 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B0,config=default,variant=raw,mode=D] --> | 0.564 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B0,config=default,variant=raw,mode=D] --> |
| B0m size logistic (diagnostic) | 0.882 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B0m,config=logit_sum_absdiff,variant=devfit,mode=L] --> | 0.868 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B0m,config=logit_sum_absdiff,variant=devfit,mode=L] --> | 0.582 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B0m,config=logit_sum_absdiff,variant=devfit,mode=L] --> | — | — | — |
| B5-T G-LoSA (shipped GA-score) | 0.712 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B5T,config=glosa_ga,variant=native,mode=native] --> | 0.594 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B5T,config=glosa_ga,variant=native,mode=native] --> | 0.658 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B5T,config=glosa_ga,variant=native,mode=native] --> | own pockets | | |
| B5-T SiteEngine (shipped column 1) | 0.692 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B5T,config=siteengine_c1,variant=native,mode=native] --> | 0.658 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B5T,config=siteengine_c1,variant=native,mode=native] --> | 0.613 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B5T,config=siteengine_c1,variant=native,mode=native] --> | own pockets | | |
| B5-T APoc PS-score | 0.602 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B5T,config=apoc_ps,variant=native,mode=native] --> | 0.539 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B5T,config=apoc_ps,variant=native,mode=native] --> | 0.546 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B5T,config=apoc_ps,variant=native,mode=native] --> | own pockets | | |
| B5-T APoc −log p | 0.630 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B5T,config=apoc_negp,variant=native,mode=native] --> | 0.548 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B5T,config=apoc_negp,variant=native,mode=native] --> | 0.604 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B5T,config=apoc_negp,variant=native,mode=native] --> | own pockets | | |
| B0′ global Foldseek TM | 0.465 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B0p,config=foldseek_tm,variant=native,mode=native] --> | 0.484 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B0p,config=foldseek_tm,variant=native,mode=native] --> | 0.521 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B0p,config=foldseek_tm,variant=native,mode=native] --> | | | |
| B0′ TM-score shipped with TOUGH-M1 | 0.439 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=B0p,config=tm_score,variant=native,mode=native] --> | 0.508 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=B0p,config=tm_score,variant=native,mode=native] --> | 0.453 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=B0p,config=tm_score,variant=native,mode=native] --> | | | |
| control: random vectors | 0.504 <!-- src: results/final/final_summary.parquet#auc[set=tough_m1_test,subset=all,arm=CTRL,config=random128,variant=control,mode=L] --> | 0.474 <!-- src: results/final/final_summary.parquet#auc_cb[set=tough_m1_test,subset=all,arm=CTRL,config=random128,variant=control,mode=L] --> | 0.505 <!-- src: results/final/final_summary.parquet#auc_strat[set=tough_m1_test,subset=all,arm=CTRL,config=random128,variant=control,mode=L] --> | | | |

B5-T and B0′ rows use their own pocket definitions and scores. Their strata come from our L-mode volumes.

- **Size dominates raw ROC in L-mode.**
  - Size alone (B0) scores 0.796, and a two-feature size logistic fitted on dev (B0m) scores 0.882. Both beat every
    similarity method.
  - Stratification removes most of this: B0 drops to 0.504.
  - It does not remove all of it: B0m keeps 0.582 on test, outside the dev diagnostic band of 0.5 ± 0.03.
- **The ligand-shell fingerprint A1 collapses without the ligand.** It scores 0.709 in L-mode and 0.500 in D-mode.
  FINAL scores the same in both (0.698 / 0.699). This replicates the dev finding (§5).
- **The learned head appears to add over its input.** FINAL beats its non-learned input N1 in D-mode (0.699 vs 0.655 ROC;
  0.717 vs 0.641 strat), but no paired CI exists.
- **L4.** In L-mode, L4 raw is level with FINAL (0.701 ROC); the pre-declared CSLS variant is lower on ROC (0.653)
  and higher on cb. In D-mode both L4 variants are weaker on ROC (0.60–0.64) and level on cb (0.67).
- **The test is fold-independent.** Global fold (B0′) scores at or below chance, at 0.44–0.47, as TOUGH-M1 intends.
- **Against published methods.**
  - On raw ROC, G-LoSA (0.712) and SiteEngine (0.692) are level with FINAL.
  - After size stratification FINAL leads: 0.719 vs 0.658 (G-LoSA) and 0.613 (SiteEngine).
  - On cb-AUC, FINAL 0.665 vs SiteEngine 0.658 and G-LoSA 0.594.
  - We did not compute paired CIs against B5-T, so these are point comparisons.
  - B5-T's shipped scores on our partition are close to their published full-set values: APoc 0.65, SiteEngine 0.66,
    G-LoSA 0.69. <!-- src: LITERATURE.md -->
  - Published learned methods are not comparable: DeeplyTough reaches 0.91–0.93 when trained on TOUGH-M1, and ProFSA
    0.82 zero-shot. They use other pocket definitions and the full set, and in L-mode the full set's size signal alone
    scores 0.815 (§4.5).

### 4.4 The ligand-size imprint (reported; quantified by the verifier)

| size measure used as a score, −\|Δ\| | TOUGH-M1-test | full minus dev |
|---|---|---|
| 4 Å ligand-shell volume (our B0, L-mode) | 0.796 | 0.815 |
| fpocket volume of TOUGH-M1's shipped pocket | 0.478 | 0.555 |
| fpocket residue count of that pocket | 0.530 | 0.580 |
| D-mode (BURROW-detected) volume | 0.555 | 0.543 |
| **ligand heavy-atom count alone** | **0.950** | **0.956** |
<!-- src: reports/verification_final.md -->

**Why it happens.** TOUGH-M1 positives share ligands by Tanimoto similarity, so their ligands are nearly the same size:
median |Δ log heavy atoms| is 0.03 for positives against 0.72 for negatives. A 4 Å shell inherits ligand size
(Spearman 0.855 with shell volume). Any descriptor of a ligand-defined pocket can therefore score well by reading
ligand size.

**Implications.**
- The benchmark's own fpocket pockets do not carry the signal (0.48–0.58).
- The same effect appears on ProSPECCTs P5.2, where B0 scores 0.707 in L-mode, and on BLiPS. In D-mode it disappears.
- Ligand-defined (L-mode) benchmark numbers, ours and published, overstate pocket similarity.
- We recommend reporting detected-pocket or size-stratified AUCs, alongside a size-only baseline, as standard.

### 4.5 TOUGH-M1 full minus dev (reported; non-learned arms only, L-mode, literature context)

| arm | ROC | cb | strat |
|---|---|---|---|
| N1 (non-learned parent of FINAL) | 0.756 | 0.670 | 0.737 |
| A1 pair_only | 0.744 | 0.817 | 0.680 |
| B1 | 0.627 | 0.676 | 0.609 |
| B4 ESM-2 (z) | 0.587 | 0.624 | 0.590 |
| B5 EPoCS | 0.727 | 0.549 | 0.714 |
| B0 size | 0.815 | 0.780 | 0.511 |
| B0′ TM-score shipped | 0.520 | 0.527 | 0.524 |
| B0′ sequence identity shipped | 0.560 | 0.512 | 0.548 |
<!-- src: results/final/final_report.md -->

This set has 866,483 pairs and includes the BURROW-homologous pockets that the test excludes. Learned arms are not
reported here (D8). The non-learned parent N1 scores 0.756 raw and 0.737 stratified. Size alone scores 0.815,
level with the best published zero-shot number on full TOUGH-M1 (ProFSA 0.82, other pocket definition), which shows
how much an L-mode size signal carries.

### 4.6 BLiPS-test: holo and AlphaFold models (reported; C5)

| arm | holo L ROC / cb / strat | holo D ROC / cb / strat | AF L ROC | AF D ROC | holo L, unseen chemotype |
|---|---|---|---|---|---|
| **FINAL** | 0.726 / 0.676 / 0.720 | 0.728 / 0.712 / 0.722 | 0.730 | 0.723 | 0.685 |
| N1 | 0.702 / 0.676 / 0.697 | 0.683 / 0.702 / 0.677 | 0.698 | 0.687 | 0.683 |
| L4 CSLS (declared) | 0.740 / 0.693 / 0.735 | 0.744 / 0.726 / 0.740 | 0.739 | 0.753 | 0.730 |
| L4 raw | 0.738 / 0.665 / 0.733 | 0.740 / 0.699 / 0.735 | 0.741 | 0.752 | 0.715 |
| A1 pair_only | 0.750 / 0.693 / 0.732 | 0.577 / 0.622 / 0.574 | 0.749 | 0.556 | 0.750 |
| B1 | 0.736 / 0.717 / 0.727 | 0.648 / 0.665 / 0.642 | 0.727 | 0.658 | 0.770 |
| B4 ESM-2 (z) | 0.679 / 0.682 / 0.678 | 0.655 / 0.707 / 0.654 | 0.665 | 0.643 | 0.717 |
| B0 size | 0.605 / 0.612 / 0.502 | 0.568 / 0.569 / 0.565 | — | — | 0.576 |
<!-- src: results/final/final_report.md, results/final/final_summary.parquet -->

**Holo pockets.**
- In D-mode, FINAL (0.728) beats B1 (0.648) and B4 (0.655); L4 is slightly higher (0.740–0.744).
- In L-mode, A1 (0.750) and B1 (0.736) are level with or above FINAL (0.726). L-mode carries the imprint.
- **Unseen chemotypes are FINAL's weak spot** (1,458 positives, L-mode): FINAL 0.685, against B1 0.770 and B4 0.717.
  The learned head may have learned chemotype-specific directions from BLiPS-train.

**AlphaFold models (C5).**
- FINAL scores the same on AF-model pockets as on holo pockets: L 0.730 vs 0.726, D 0.723 vs 0.728. These are
  unpaired comparisons: the pair sets differ slightly, and the D sets differ by detection.
- **Paired holo − AF Δ for FINAL (pre-registered reported item, computed post hoc — DEV6).** `final_eval.py` selected
  C5 arms with `key.split("|")[1]`, and the method name contains `|`, so FINAL was silently skipped.
  `scripts/post_final_reported.py` imports the frozen functions (hash-checked) and fixes the selection; it reproduces
  final_eval's B1/B4 values exactly (max |dev| 0). FINAL: L −0.004 [−0.020, +0.010], D +0.004 [−0.016, +0.028]; both
  CIs inside the ±0.03 SESOI. Strata: holo released ≥ 2018-05-01 L −0.002 [−0.034, +0.027]; site pLDDT ≥ 90 L −0.009
  [−0.024, +0.008]; pLDDT 70–90 D +0.007 [−0.030, +0.059]; pLDDT < 70 uninformative (43 / 2 positives).
  <!-- src: reports/final_post_reported.md, results/final_post/c5_holo_minus_af.parquet -->
  - B1 D Δ = −0.013 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B1|default|raw|D#all.delta --> [−0.043 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B1|default|raw|D#all.ci_low -->, +0.016 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B1|default|raw|D#all.ci_high -->].
  - B1 L Δ = +0.010 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B1|default|raw|L#all.delta --> [−0.007 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B1|default|raw|L#all.ci_low -->, +0.024 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B1|default|raw|L#all.ci_high -->].
  - B4 L Δ = +0.013 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B4|esm2|raw|L#all.delta --> [+0.005 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B4|esm2|raw|L#all.ci_low -->, +0.020 <!-- src: results/final/final_details.json#blips_test.c5_holo_minus_af.B4|esm2|raw|L#all.ci_high -->]. This one is a small, CI-excluding loss on AF models.
- The exploratory fusion run (§8) computed the analogous paired Δ for the fused score: −0.004 (L) and −0.009 (D), both
  with CIs that include 0. That supports, without confirming, "no AF penalty" for FINAL.
- D-mode coverage is the bigger problem on BLiPS-test. Positive pairs outside the common set: 33.8 % <!-- src: results/final/final_summary.parquet#miss_rate_pos_all[set=blips_test,subset=all,arm=FINAL,variant=raw,mode=D] --> (holo); worst-case AUC 0.289.

### 4.7 ProSPECCTs, all subsets (reported; ROC-AUC, self-pairs removed)

| arm | P1 | P1.2 | P2 | P3 | P4 | P5 | P5.2 | P6 (≡ P6.2) | P7 |
|---|---|---|---|---|---|---|---|---|---|
| **FINAL** | 0.989 | 1.000 | 0.998 | 0.718 | 0.707 | 0.717 | 0.709 | 0.622 | 0.890 |
| N1 | 0.991 | 1.000 | 0.994 | 0.707 | 0.698 | 0.708 | 0.680 | 0.693 | 0.892 |
| L4 raw | 0.996 | 1.000 | 1.000 | 0.853 | 0.848 | 0.647 | 0.637 | 0.649 | 0.849 |
| A1 pair_only | 0.873 | 0.996 | 0.983 | 0.582 | 0.552 | 0.766 | 0.858 | 0.543 | 0.886 |
| B1 | 0.991 | 1.000 | 0.999 | 0.726 | 0.694 | 0.679 | 0.662 | 0.607 | 0.885 |
| B4 ESM-2 (z) | 1.000 | 1.000 | 1.000 | 0.758 | 0.794 | 0.624 | 0.650 | 0.433 | 0.832 |
| B0 size | 0.608 | 0.798 | 0.798 | 0.573 | 0.553 | 0.645 | 0.707 | 0.561 | 0.644 |
| B0′ Foldseek TM | 1.000 | 1.000 | 0.998 | 0.440 | 0.440 | 0.519 | 0.522 | 0.343 | 0.782 |
| FINAL, D mode | 0.978 | 0.841 | 0.979 | 0.678 | 0.655 | 0.647 | 0.621 | n/a (4 pairs) | 0.848 |
| B1, D mode | 0.846 | 0.745 | 0.934 | 0.598 | 0.604 | 0.502 | 0.472 | n/a (4 pairs) | 0.741 |
| positives L / D | 13,104 / 7,252 | 196 / 30 | 7,400 / 3,024 | 13,104 / 7,252 | 13,104 / 7,252 | 840 / 74 | 1,220 / 116 | 19 / 2 | 66 / 6 |
<!-- src: results/final/final_report.md -->

- **P1 / P1.2 / P2 are ceiling sets.** Global fold and sequence score ≈ 1.0 on them, so they do not test fold
  independence. Do not read them as a strength.
- **P3 / P4 (physicochemical / shape decoys).** L4 is clearly better (0.85), and FINAL is level with B1.
- **P5 / P5.2 / P6 / P7 test what we claim.** FINAL is 0.62–0.89, close to B1, with no significant gain (C2).
  P5.2's L-mode ranking is led by A1 (0.858) and B0 (0.707), which is the imprint again.
- **P6 ≡ P6.2.** Identical pair lists, identical descriptors after cofactor stripping (DEV5); one column is shown.
- **D-mode** uses BURROW-clean pockets only, and 45–91 % of positive pairs are missing.
  - The D-mode P6 value comes from 4 pairs (2 positive) and is meaningless.
  - P5/P5.2/P7 D values rest on 6–116 positives.
- **Published context** (other pocket definitions, with self-pairs): the best values are P5 0.76, P5.2 0.81,
  P6.2 0.76 and P7 0.88. <!-- src: LITERATURE.md -->

### 4.8 Vertex (reported; L-mode, protein-pair max)

| arm | FINAL | N1 | L4 raw | A1 | B1 | B4 | B0 | B0′ Foldseek TM |
|---|---|---|---|---|---|---|---|---|
| ROC-AUC (protein pairs) | 0.822 | 0.796 | 0.840 | 0.621 | 0.721 | 0.837 | 0.527 | 0.910 |
<!-- src: results/final/final_report.md -->

FINAL (0.822) beats B1 (0.721), but global Foldseek TM scores 0.910 and ESM-2 0.837. Vertex positives are largely
homologous, so it measures homology recovery, not fold-independent similarity. The published DeeplyTough value is
0.818–0.830. <!-- src: LITERATURE.md -->

### 4.9 PPI pockets: PPIPS-test and PPI-L (reported / exploratory)

| arm | P-ortho top-1 | top-3 | MRR [95 % CI] | P-sym percentile |
|---|---|---|---|---|
| **FINAL** | 0.542 | 0.778 | 0.683 [0.607, 0.772] | 0.998 |
| N1 | 0.490 | 0.752 | 0.650 [0.551, 0.800] | 0.998 |
| L4 raw | 0.614 | 0.856 | 0.747 [0.594, 0.864] | 0.999 |
| A1 pair_only | 0.359 | 0.667 | 0.546 [0.466, 0.680] | 0.932 |
| B1 | 0.464 | 0.725 | 0.628 [0.502, 0.852] | 0.994 |
| B4 ESM-2 (sequence) | 0.908 | 1.000 | 0.954 [0.919, 1.000] | 1.000 |
| B0 size | 0.190 | 0.497 | 0.396 [0.302, 0.524] | 0.777 |
<!-- src: results/final/final_report.md -->

**PPIPS-test.** 153 P-ortho queries in 12 units; 544 P-sym queries.
- On P-ortho (find the interolog's interface pocket), FINAL (MRR 0.683) beats B1 (0.628) and N1 (0.650).
- L4 (0.747) is better, and the sequence baseline B4 (0.954) dominates.
- P-ortho rewards sequence homology, so it does **not** test fold independence.
- P-sym (the symmetric copy in a homodimer) is a sanity check, and every structure-based arm passes it.
- By BURROW-homology flag (post hoc, DEV6; 136/251 test complexes have a BURROW-train/dev edge): FINAL P-ortho MRR
  0.683 with an edge and 0.683 without; B4 0.936 / 0.970 — BURROW homology does not drive the PPIPS result.
  <!-- src: reports/final_post_reported.md, results/final_post/ppips_burrow_strata.parquet -->

**PPI-L (exploratory).** The test split has 3 <!-- src: results/final/final_details.json#ppi_l.n_pos --> positive
pairs among 70,313. No score was computed ("too few positives"), and the set is uninformative. PPI-modulator
chemistry stays within target families: 4,312 within-UniProt positive pairs against 175 cross-group pairs across the
whole set. <!-- src: reports/ppi_datasets.md -->

### 4.10 Pre-registered reported items completed post hoc (DEV6) and the blind deployment test
Three reported items were missing from the final run (one bug, two omissions) and were computed afterwards with
`scripts/post_final_reported.py` (frozen method, no tuning, logged unseals): the paired C5 Δ (§4.6), the PPIPS strata
(§4.9) and the **blind deployment test** on BLiPS-test AF models:
- 3,600 sites on 2,295 AF models; the pool is all 13,876 merged BURROW pockets (median 13,859 candidates per query).
- BURROW detection recall 0.700 [0.676, 0.723].
- With both partners detected (8,048 directed positive pairs): FINAL AUC 0.719 [0.684, 0.761] vs B1 0.688 and size
  0.583; Δ FINAL − B1 +0.031 [−0.001, +0.057]. Early retrieval is low: hit@100 0.078 (chance ≈ 0.007), MRR 0.009.
- Counting missed detections as misses: FINAL 0.628, B1 0.610.
- Reading: in a fully ligand-free, proteome-like setting FINAL ranks true partners above random pockets but rarely in
  the top 10 of ~14k; detection (30 % of sites missed) and early precision are the bottlenecks.
<!-- src: reports/final_post_reported.md -->
ProSPECCTs results with self-pairs exist in `results/final/` but are not shown here.

---

### 4.11 Temporal replication on fresh data (PREREG2; confirmatory for R1–R3)
After the PREREG test sets were spent, PREREG2.md (committed before the set existed) defined **PDB-T**: ligand
sites in PDB entries released after 2025-11-12 (the BioLiP2 snapshot behind every training set), X-ray/EM ≤ 3 Å,
ligands ≥ 10 heavy atoms (additives excluded); every protein with a sequence or structure edge to any training
source removed (9,082 of 13,036 chains); pairs as in BLiPS; a feasibility gate (≥ 300 positives, ≥ 30 groups,
≥ 10 ligand clusters) recorded before any score. An independent audit passed; 9 boundary sites (min-TM 0.50–0.56)
were excluded before scoring (D25). Frozen artefacts only; no retraining. <!-- src: reports/pdbt_build.md, reports/audit_splits.md -->

| claim (D-mode common set, 6,171 pairs / 1,060 pos) | AUC a | AUC b | Δ [95 % CI] | Holm p | |
|---|---|---|---|---|---|
| R1 FINAL − B1 | 0.752 | 0.671 | +0.081 [+0.028, +0.132] | 0.003 | **replicates** |
| R2 FUSION − FINAL | 0.762 | 0.752 | +0.010 [−0.010, +0.032] | 0.34 | not supported |
| R3 L4 (CSLS) − FINAL | 0.730 | 0.752 | −0.022 [−0.061, +0.018] | 0.86 | not supported |
<!-- src: results/pdbt/report.md, results/pdbt/claims.json -->

- L-mode: FINAL 0.774 vs B1 0.760 (Δ +0.014 [−0.029, +0.057]) — on fresh data the gain over B1 is a D-mode gain,
  consistent with the ligand-imprint finding (L-mode flatters BURROW's own descriptors too).
- Size-stratified D-mode AUC: FINAL 0.752; cluster-balanced 0.699. 83 % of positives involve a ligand chemotype seen
  in BLiPS-train: the proteins are new, most chemotypes are not.
- Two aborted starts are disclosed (DEV7: pairs referencing the excluded sites; no score had been computed).
- **Independently verified** (reports/verification_final.md, "PDB-T verification"): own code reproduces all three
  point estimates (R2 AUC within 1.8e-7), Holm decisions unchanged; the 9 exclusions match D25; no PDB-T site, chain
  or sequence appears in any training table.

## 5. Development: how the method was chosen (dev/val only, rebuilt splits)

**Selection rule (PREREG §1).**
- Objective: BLiPS-val D-mode cb-AUC.
- One-SE rule: among candidates within one SE of the best, take the simplest.
- Guards: BLiPS-val L cb ≥ B1, and TOUGH-M1-dev D cb ≥ B1.

| candidate | dims | BLiPS-val D cb (SE) | BLiPS-val L cb | TM-dev D cb | TM-dev L cb | PPIPS-val P-ortho MRR |
|---|---|---|---|---|---|---|
| B1 BURROW descriptors | 45 | 0.648 (0.040) | 0.701 | 0.617 | 0.639 | 0.761 |
| B4 ESM-2 raw | 1280 | 0.670 | 0.641 | 0.598 | 0.602 | 0.986 |
| N1 = A1(sph8) + env(sph8), non-learned | 627 | 0.697 (0.040) | 0.706 | 0.667 | 0.656 | 0.790 |
| A4b:n1_base (MLP head) | 384 | 0.717 (0.038) | 0.702 | 0.687 | 0.695 | 0.694 |
| **A4b:n1_linear (FINAL)** | 384 | **0.737** <!-- src: results/dev/l4/final_select_all_l4_summary.parquet#auc_cb[cand=A4b:n1_linear,variant=raw,dataset=blips,mode=D] --> (0.038) | 0.718 | 0.721 <!-- src: results/dev/l4/final_select_all_l4_summary.parquet#auc_cb[cand=A4b:n1_linear,variant=raw,dataset=tough_m1,mode=D] --> | 0.720 | 0.719 |
| L4:egnn_small CSLS (best overall) | 384 | 0.756 (0.040) | 0.765 | 0.661 | 0.694 | 0.821 |
<!-- src: results/dev/l4/final_select_all_l4_summary.md -->

**Outcome.**
- The best candidate (L4, 0.756) set the threshold at 0.716.
- The non-learned N1 (0.697) and N2 (0.704) fell below it, so selection moved to learned candidates.
- All A4b and L4 heads store 384 dims. L4 counts as more complex than A4b.
- Among A4b heads, "simplest" was resolved as fewest parameters, which picks n1_linear (D19, §9).

**Dev findings that shaped the design.**
- **Ligand imprint.** On the same pairs, A1 dropped from L 0.793 to D 0.549 on TOUGH-M1-dev: Δ −0.244
  [−0.328, −0.186]. B1 lost 0.06. The drop replicated on BLiPS-val: −0.161 [−0.245, −0.082]. This led to amendment
  D11, made before any test use: claim C1-D was added and selection moved to D-mode. <!-- src: reports/dev_eval_v2splits.md -->
- **Size shortcut.** B0 scored 0.782 ROC on TOUGH-M1-dev and the B0m logistic 0.861. This motivated the
  pre-registered 5 × 20 size strata: in simulation, 5 × 5 strata left 0.539 for a pure size score (D6). <!-- src: reports/dev_eval_v2splits.md, reports/evaluate_module.md -->
- **Site shaping beat descriptor tuning.** 12–14 of 17 A1 configs were within one SE of each other, and none was
  robust in D-mode. sph8 + env lifted TOUGH-M1-dev D cb from 0.541 to 0.672 (old splits). <!-- src: reports/definition_robustness.md -->
- **Dev power was weak.** Most paired CIs against B1 included 0 at dev. For example, n1_base − B1 on BLiPS-val D
  was +0.069 [−0.029, +0.132]. The test confirmed the direction on TOUGH-M1 D (C1-D) with a larger effect.
  <!-- src: results/dev/l4/final_select_all_l4_summary.md -->

---

## 6. Negative and null results

- **Fragment-docking profiles (A2) failed the pre-registered gate (D10).**
  - *Setup.* ADock with stock Vina docked 128 fragments and 128 lead-like molecules into every TOUGH-M1 pocket:
    13,592 pockets, 0 failures, 0.30 GPU-s per pocket.
  - *Gate.* A1 + fragment block vs A1 had to gain ≥ 0.01 in size-stratified AUC. It gained −0.009 [−0.066, +0.023]
    (rebuilt splits); every variant was ≤ +0.002.
  - *Why.* Docking scores track pocket size and hydrophobicity: pocket means explain 57 % of score variance.
  - <!-- src: reports/a2_docking.md, reports/dev_eval_v2splits.md, reports/fragment_docking_feasibility.md -->
- **The PPI fragment sub-hypothesis was not supported.** The prediction was that fragments beat lead-like molecules
  on shallow interface pockets. On the rebuilt splits ΔMRR was −0.063 / −0.005 / −0.042 for the three score variants,
  Holm p = 1. The early positive trend was noise. <!-- src: reports/dev_eval_v2splits.md -->
- **The ligand-grounded PPI test (PPI-L) was infeasible (D7).** It had 3 positive test pairs, against a gate of ≥ 50.
  PPI-R, retrieval of modulator pockets across families, was designed but not built.
- **CSLS hub correction does not improve accuracy.**
  - On TOUGH-M1-test it lowers FINAL's ROC (0.641 vs 0.698 L).
  - At proteome scale it does reduce hubness: top-10 in-degree skewness falls from 1.62 to 0.55.
  - It is kept as a search option only. <!-- src: results/final/final_report.md, results/release/human_afdb_v6.json -->
- **B5 EPoCS (ESM-2 3B) ≈ B4.** It added no information over B4 at ~38 GPU-min of cost. <!-- src: reports/baselines_b4_b5.md -->
- **Learned heads lower PPI ortholog transfer on dev.** n1_linear scored 0.719 against N1's 0.790 on PPIPS-val.
  On test the order reversed (0.683 vs 0.650), within overlapping CIs.

---

## 7. Runtime and scale

| item | value | source |
|---|---|---|
| BURROW + describe, per structure, 1 core (AFDB human, 5.7 pockets) | median 0.42 s (ref CPU), 0.21 s (fast CPU), 0.13 s (GPU) | results/tooling/describe_runtime.json |
| throughput, 22 workers, end to end with FINAL | 34 / 55 / 56 structures/s (ref / fast / GPU; CPU-bound) | same |
| descriptor + embedding, per D pocket (excludes BURROW) | median 3.5 ms (p90 4.6); L site 6.1 ms; head 64 µs | results/dev/final_method_runtime.json (measured for sibling n1_base, same pipeline; the linear head is smaller) |
| applying the head to 116,246 stored N1 vectors | 1.34 s in total | results/release/human_afdb_v6.json |
| pair score, batched against 10⁶ vectors | 0.10–0.65 µs (node-dependent); 2.8 µs single call | results/dev/final_method_runtime.json, results/exploratory/fusion/fusion_runtime.json |
| storage per pocket | 1,536 B float32; 768 B fp16; 94 B OPQ64-IVF-PQ64 code | results/release/human_afdb_v6.json |
| human AFDB v6 (23,586 models → 116,246 pockets) | 132.8 structures/s, 716 pockets/s on 2 × RTX 4090 + 22 CPU workers (178 s) | results/proteome/summary.json |
| search, 116 k pockets | exact: 7.3 ms/query (1 CPU thread), all-vs-all top-50 0.41 s (1 GPU). PQ nprobe 64 + re-rank of top-100: recall@10 0.987, 0.77 ms/query | results/release/human_afdb_v6.json |
| AFDB 200 M structures (extrapolated, not run) | ≈ 0.95 × 10⁹ pockets; ≈ 7,150 CPU-core-h + 223 GPU-h (~4 h on 100 such nodes); fp16 vectors ≈ 0.73 TB, PQ index ≈ 0.09 TB; exact all-vs-all ≈ 9,400 GPU-h | results/proteome/summary.json (storage rescaled to 384 d) |
| alternatives | L4: +4.8 ms point extraction + 0.54 ms GPU / 47 ms CPU; B4 ESM-2: 0.06 s/pocket GPU; A2 docking: 0.30 GPU-s/pocket | reports/l4_pointnet.md, reports/baselines_b4_b5.md, reports/a2_docking.md |

The proteome throughput row used the N1 pipeline, with the head applied afterwards. BURROW and descriptor costs are
identical. <!-- src: reports/proteome_demo.md, reports/tooling.md -->

**C4 targets (reported):**
- ≤ 1 s per pocket including BURROW: met.
- ≤ 10 µs per pair: met.
- ≤ 512 B per pocket: met only with PQ codes. PQ codes alone reach recall@10 0.886, so a re-rank against 768 B fp16
  vectors is recommended.
- ANN latency at 10⁹ vectors has **not** been measured.

---

## 8. EXPLORATORY (post-test): not confirmatory

**A4b + L4 score fusion** (`reports/exploratory_fusion.md`).
- *Why we tried it.* The test showed L4 stronger on BLiPS, PPIPS and P3/P4, and FINAL stronger on TOUGH-M1 D.
- *Protocol.* The fused score is w·z(FINAL) + (1−w)·z(L4). The protocol was declared before any fused score existed,
  w = 0.5 was chosen on dev, and the test was looked at once.
- *Results* (Δ fused − FINAL, ROC):
  - TOUGH-M1-test D: −0.007 <!-- src: results/exploratory/fusion/test_deltas.parquet#delta[set=tough_m1_test,comparison=FUSED − FINAL,metric=auc,mode=D] --> [−0.038, +0.009];
  - TOUGH-M1-test L: +0.026;
  - BLiPS-test L / D: +0.030 / +0.029, CIs > 0;
  - ProSPECCTs P3 / P4: +0.062 / +0.064;
  - Vertex: +0.025 [−0.011, +0.056];
  - PPIPS MRR: +0.059 [+0.008, +0.108].
- *Cost.* 8.9 ms per pocket with a GPU (55 ms on CPU) and 3,072 B per pocket.
- *Reading.* The gains sit on the sets that motivated the analysis. Fusion does not help the cleanest endpoint
  (TOUGH-M1 D).
- *Decision.* FINAL is unchanged. The pre-registered replication on fresh data (§4.11, R2) found no fusion gain
  (+0.010, p 0.34), so the exploratory gains here were selection effects or set-specific.

**PPI-R: ligand-grounded PPI retrieval (train+val only; `reports/exploratory_ppi.md`).** 1,806 PPI-modulator
pockets (67 homology groups) vs 1,272 non-PPI ligand pockets matched on volume and buriedness; queries rank pockets of
other homology groups. FINAL AUC 0.552 [0.495, 0.590], P@10 0.52 vs chance 0.55; B1 0.493; ESM-2 P@10 0.74 (cause
unclear: no shared Pfam or ligand cluster). **Negative:** the fingerprint does not recognise "PPI-modulator
pocket-ness" across families. <!-- src: reports/exploratory_ppi.md -->

**AFDB dimer interface-pocket atlas (demo).** All 15,161 AFDB dimers in 347 s (43.7 dimers/s; ~60 CPU cores + 2 GPUs),
127,824 pockets of which 32,473 are interface pockets (f_min ≥ 0.25), 0 errors. Interface pockets are no closer to
known PPI-modulator pockets than to ordinary ligand pockets (16 above a strict threshold, below the 1 % null); 150
clusters of ≥ 10 under a stricter post-hoc rule, 45 cross-family. <!-- src: reports/exploratory_ppi.md -->

**API and tooling changes after the test** (D23; `reports/tooling.md`). None of them changes an evaluated number,
because the frozen tag holds the evaluated code.
- `describe(..., locate="burrow")` now locates D sites exactly as the evaluation did. The old rule differed on
  4/765 + 2/523 dev sites. A regression test reproduces the stored evaluation vectors to ≤ 1.1e-7.
- New `describe_all` and the `pocketcompare` CLI, covered by 10 tests; the full suite passes (122 tests).
- Human AFDB v6 release with the final head: 116,246 fingerprints and FAISS indices.
  - Its top-10 neighbours overlap only 20 % with the N1 demo's.
  - The demo's family sanity checks (kinase recovery) were not re-run with the final head.

---

## 9. Process and integrity (brief)

**Sealing (D2).**
- Every benchmark pair/label table was moved to `data/sealed/` (chmod 000, sha256-listed) before any method existed.
- Only `final_eval.py` reads them. It requires FINAL_EVAL=1, a committed FREEZE.json and a clean worktree at the
  frozen commit, and it logs every read.

**Pre-registration.**
- DESIGN v2 came from two review rounds. PREREG.md consolidated all amendments before any model fit.
- Addendum A1 (L4 candidate) and Addendum A2 (final method; N1 and L4 descriptive) were added before test use.
- C1-D was added after a dev finding (D11). It made the claim family larger, not easier.

**Split audit failure and rebuild (D15/D18).**
- The independent audit failed before any model fit. MMseqs2 had run without `-a`, and Foldseek was not exhaustive,
  so 16 test pockets had BURROW homologues; there were smaller leaks elsewhere.
- The graph was rebuilt and all splits re-derived under unchanged rules: 254 TOUGH-M1 pockets moved; BLiPS-test was
  unchanged.
- The re-audit passed, and all dev numbers were re-run. <!-- src: reports/audit_splits.md, data/splits/SPLITS.md -->

**Deviations.**
- **DEV1.** A reviewer read the TOUGH-M1 pair table 2 min before sealing and computed B0 (0.577) on all pairs. No
  method was tuned.
- **DEV2.** The largest BLiPS within-dataset component is 10.6 %, against a 10 % gate. We did not re-split.
- **DEV3.** The first final run aborted on a stale sealed-file hash for PPIPS (the rebuild had rewritten the file). The
  hash list was corrected from the creation log, the method was re-frozen with identical code and the identical
  evaluation was re-run. No test number was viewed in between.
- **DEV4.** 66 TOUGH-M1-test pockets are homologous to PPIPS-train chains. The audit covered the primary training
  sets but not PPIPS. Excluding them does not change Δ (§4.2).
- **DEV5.** P6 ≡ P6.2 after cofactor stripping, so C2 double-weights P6.
- **DEV6.** final_eval skipped FINAL's paired C5 Δ (method name contains `|`) and omitted the blind test and the
  PPIPS BURROW strata; all three computed post hoc with the frozen functions (§4.10).
- The C5 bug (§4.6) is a further, post-hoc-discovered gap.

**Re-freezes (D21).**
- Two pre-test re-freezes fixed infrastructure: the parent mount was read-only, and a stale FREEZE.json caused a
  nested worktree.
- One more re-freeze (DEV3) happened after the aborted run.
- Method and evaluation code were identical across all freezes.

**The D19 tie-break.** All A4b heads store 384 dims, so the declared "simplest" criteria did not separate them.
- The agent fell back to grid order, which is not a declared rule, and that picked n1_base.
- The PI substituted "fewest parameters", which picks n1_linear. The PI did this after seeing the table, in which
  n1_linear scored higher (0.737 vs 0.717, both within one SE).
- The choice is defensible, but it was not blind.

**Independent verification.**
- A separate agent wrote its own code and did not import `final_eval`/`evaluate`.
- It reproduced every headline to ≤ 1e-8 and found no computational error or test leakage.
- It also surfaced the Holm fragility, DEV4, P6 ≡ P6.2 and the ligand-size imprint. <!-- src: reports/verification_final.md -->

---

## 10. Limitations

1. **Power.** The TOUGH-M1-test has 102–112 units, one of them giant, and its MDE is ≈ 0.12–0.13. Only C1-D is
   robust. The C1a/C1b rejections depend on Monte-Carlo luck.
2. **Ligand-sharing labels.** They are a proxy for pocket similarity, and L-mode labels and pockets carry ligand
   size (§4.4). D-mode is still oracle-assisted, because the ligand picks the pocket.
3. **Detection.** D-mode misses 14 % of TOUGH-M1 and 34 % of BLiPS positive pairs, and blind recall on AF models
   was 0.615 (val). The fingerprint inherits BURROW's recall.
4. **No significant gain on ProSPECCTs (C2).** FINAL is weaker than B1 on BLiPS unseen chemotypes, and weaker than
   L4 on several reported sets.
5. **Learning over N1 is not proven.** No paired test was run, and the gains are 0.01–0.04 on most sets.
6. **PPI.** There is no ligand-grounded, fold-independent PPI test. PPIPS measures interolog transfer, where sequence
   wins. Most PPIPS-test complexes are BURROW-homologous.
7. **AF robustness for FINAL is unpaired** (C5 bug). The blind test was run only on val, with N1.
8. **Not literature-comparable.** 76 % of TOUGH-M1 is excluded, and our pockets are BURROW grid points.
9. **The fixed-size sph8 site** describes only the centre of large or elongated pockets. Cofactors, metals and waters
   are stripped (FINGERPRINTS.md §5).
10. **Inherited data.** ESM-2 (B4) was pretrained on UniRef, which contains test sequences. Transferred BLiPS-test
    ligands clash with the protein in 29 % of holo and 55 % of AF sites. <!-- src: reports/blips_ppips_prep.md -->

---

## 11. Follow-ups and remaining ideas (prioritised)

1. **Replace L-mode benchmarks with ligand-free site definitions.**
   - Re-score published methods (DeeplyTough, PocketVec, ProFSA, G-LoSA) on detected or fpocket pockets of the same
     pairs.
   - Always report a size-only baseline and size-stratified AUC.
   - Release our TOUGH-M1 D-mode pairs as a benchmark variant.
2. **Improve detection and early precision for blind search** (§4.10: 30 % of sites undetected; hit@100 0.078):
   site-level merging of BURROW sub-pockets, multi-pocket (set-to-set) scoring, re-ranking the FAISS top-k with L4 or
   an alignment step.
3. **Larger cross-family training data.**
   - Train A4b/L4 on PDB-wide BioLiP sites under the same leakage rules, auditing every training source (DEV4).
   - Use graded ligand-similarity targets to help unseen chemotypes.
   - Pre-register a fresh held-out set before any claim.
4. **Do not ship L4 / fusion as default.** On fresh data (§4.11) neither beats FINAL; L4 remains a research lead
   (decoy sensitivity on ProSPECCTs P3/P4). Re-validate any variant on new
   held-out data.
5. **PPI pockets need PPI-specific training signal.** The exploratory PPI-R test (§8) is negative; train with
   interface-pocket positives grounded in modulator data (across families where they exist) and evaluate PPI-R on a
   held-out split.
6. **Cofactor-aware pockets.**
   - Keep cofactors and metals as typed points (BURROW currently strips them).
   - Re-test the D6.2 condition.
   - Add pLDDT-aware down-weighting: AF retrieval lost ~0.17 top-1 at pLDDT 70–90 on dev.
7. **ANN at AFDB scale.**
   - Measure OPQ-IVF-PQ with an HNSW coarse quantiser at 10⁸–10⁹ vectors.
   - Use per-shard CSLS radii against hubness.
   - Use a set-max over BURROW sub-pockets as the deployment locator.
8. **Integration with ADock re-ranking.** Use the fingerprint as a tier-1 prefilter, then dock the top-k. A2 failed
   as a tier-1 descriptor, but re-ranking a shortlist was never tested. A3 pseudocentre alignment is the other
   tier-2 candidate.
9. **Power for TOUGH-M1.** Pre-register a homology-group unit and a looser cross-dataset exclusion (TM ≥ 0.7 doubles
   the test set) for a separately sealed re-evaluation.

---

## 12. Deliverables and reproduction

**Where the work lives.**
- Everything is on git branch **`pocket-compare`**, as local commits only; there is no remote. The PI commits and
  pushes.
- The freeze is tag `freeze-v1`, with FREEZE.json recording commit e5a6f35.
- ProSPECCTs data must never be redistributed (DATA.md).

**Main deliverables.**
- `src/pocketcompare/` (library, API and CLI) and `configs/final_method.yaml` plus `results/models/a4b/n1_linear/`.
  The method and weights are sha256-pinned in FREEZE.json.
- `results/final/` (test results, sealed-read log) and `reports/verification_final.md`.
- `docs/FINGERPRINTS.md` (handover note for BURROW/ADock).
- `data/processed/release/human_afdb_v6/` (116,246 fingerprints + FAISS indices).

**Reproduction.**
- README.md lists the install steps and every pipeline step, from benchmark download to `final_eval.py`.
- Every result file has a `.prov.json` sidecar with the commit, inputs, seeds and evaluate.py hash.
- `python scripts/check_report.py REPORT.md` re-checks the tagged numbers in this report.
