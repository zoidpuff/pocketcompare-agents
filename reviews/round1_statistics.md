# Review R1 — statistics (benchmark design, metrics, inference) of DESIGN.md v0

**Disclosure.** Between 19:08 and 19:10 I read `tough_m1_pairs.parquet`, before it was sealed at 19:12. I computed the
structure of the label graph and one size proxy: B0 using `n_pocket_residues`, which gave AUC 0.577 on all pairs. I
fitted or tuned no method. Scratch scripts: `/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/t{1,2}.py`.
I did not touch the sealed tables afterwards.

**TOUGH-M1 facts that drive everything below.**
- The positives form 1,269 ligand clusters (connected components of the positive graph). The top cluster holds
  **47 %** of positive pairs, the top 5 hold 81 % and the top 10 hold 91 %.
- Negatives involve only **1,266 pockets, exactly one representative per ligand cluster**. Each representative
  takes part in about 880 negative pairs. 78 % of these representatives come from clusters that have no positives.
- AUC standard error by resampling unit, on a simulated 70 % partition: pair bootstrap 0.0008, pocket-vertex
  bootstrap 0.009, ligand-cluster-vertex bootstrap **0.016**. A pair-level or naive CI is 10–20× too narrow.

## MUST

**M1. Resampling unit (§4).** Pairs are dyadic, so use a **vertex bootstrap**: resample units with replacement and
give each pair the weight c_i·c_j from the resample counts of its two units. Pairs whose units were not drawn drop
out.
- TOUGH-M1: the unit is the **ligand cluster**, merged with the protein cluster wherever the two overlap.
- BLiPS and PPIPS: the unit is the protein (fold/orthogroup) cluster. Also run the bootstrap with the ligand
  chemotype as unit and report the **wider** of the two CIs.
- Use B = 2,000 and percentile CIs. Every arm uses the same resamples (paired).
- Cost: under 1 h of code. The simulation showed that protein-cluster resampling alone understates the CI.

**M2. Define C1 precisely and check it is detectable.** "Exceeds by ≥ 0.03" is ambiguous. Testing H0: Δ ≤ 0.03
needs a true Δ of about 0.06–0.08 to reach 80 % power, given a plausible SE(Δ) of 0.01–0.02. Change C1 as follows:
- Test **H0: Δ ≤ 0** with a one-sided ligand-cluster bootstrap, α = 0.05.
- Keep 0.03 as the pre-declared smallest effect of interest. Call the gain "meaningful" only if the point estimate
  is ≥ 0.03, and report the lower bound of the 95 % CI.
- Before sealing the test, write down the minimum detectable effect, (1.645 + 0.84)·SE(Δ), where SE(Δ) is the
  ligand-cluster bootstrap SE of B0 vs B1 on **dev**.

**M3. Pair-weighted TOUGH-M1 AUC mostly measures the 1–5 largest ligand clusters.** Keep pair-weighted ROC-AUC as
the primary metric, for comparability. Next to it, always report:
- a **cluster-balanced AUC**: weight each positive by 1/(positive pairs in its ligand cluster), with negatives
  uniform;
- per-cluster AUC for the top 10 clusters;
- a **pocket-marginal baseline** B0m = g(a) + g(b), where g is any per-pocket score (e.g. a logistic model on
  size/buriedness fitted on dev). Negatives come from a special pocket population (the cluster representatives), so
  an AUC that "pair-free" features can reach is a shortcut, not similarity.

Cost: minutes.

**M4. TOUGH-M1 dev/test split (§2.2).** A 30/70 split keeps about 8 % (dev) and 51 % (test) of pairs and discards
41 %. In a simulation it gave dev = 85k pairs (43k positive / 43k negative), but the negatives came from only
**about 350 representative pockets**. Class balance holds in expectation. The ligand-cluster mix does not, because
one cluster holds 47 % of positives. Changes:
- **(a)** Assign protein clusters stratified by dominant ligand cluster (DataSAIL or a greedy method).
- **(b)** Before splitting, check the Foldseek TM ≥ 0.5 single-linkage merge for a giant component. Rossmann-fold
  chaining is likely. If the largest component is more than 15 % of proteins, use DataSAIL's ILP instead of
  connected components.
- **(c)** Commit the realised pairs, prevalence, number of negative pockets and ligand-cluster shares per partition
  to DATA.md before any modelling.
- Consider 40/60. Dev is where every gate is decided, and 350 negative pockets is thin.

**M5. Missing-pocket policy (§2.1, §4).** Giving misses the minimum similarity is **not neutral**. Every missed
negative counts as a correct rejection, so an arm that fails more often on negatives gains AUC. Changes:
- **(i)** Run all paired arm comparisons and C1 on the **common pair set**, where every compared arm returns a score.
- **(ii)** Report the min-imputed number as the deployment figure.
- **(iii)** Report the worst-case bound: missed positives get the minimum and missed negatives the maximum.
- **(iv)** Report the miss rate by label and by arm.

Cost: trivial.

**M6. Selection on dev and the gates (§3).** Dev will see dozens of configurations: A1 blocks, A2 panels × 3
variants, A3, A4 × 5 seeds and fusions. Dev SE is about 0.02–0.03, so the best dev AUC is biased upwards. Changes:
- **(a)** Pre-declare one selection rule: the best dev cluster-bootstrap mean over {TOUGH-dev, BLiPS-val,
  PPIPS-val}, with a **one-SE rule** that prefers the faster or simpler arm. Log how many configurations were
  evaluated.
- **(b)** Exactly **one** frozen configuration goes into the C1–C3 tests. Other arms may appear on test only as
  descriptive results.
- **(c)** The A2 gate "≥ B0 + 0.05" must use the **size-stratified AUC** (see S1). Docking scores correlate with
  volume (ρ = −0.74).
- **(d)** "+0.01 in fusion" is below dev noise and is in-sample if the fusion is fitted on the same data. Replace it
  with 2-fold cross-fitting over ligand clusters and the criterion "one-sided 90 % lower bound of the gain > 0".
- **(e)** For A4, report the mean ± SD over the 5 seeds, or ensemble them. Never pick the best seed on dev.

## SHOULD

**S1. Size-matched negatives (§2.3, §2.4).** Matching on the volume ratio changes the estimand to an AUC
conditional on size ratio. It still leaves absolute size usable: positives are enriched for large
nucleotide/cofactor pockets. Instead of subsampling:
- keep all negatives and compute a **covariate-stratified AUC** (Janes & Pepe 2008), with strata of
  (mean log vol × |Δ log vol|) weighted by the positives in each stratum;
- define volume in L-mode, fixed;
- use B0 as the diagnostic: on this estimand it must be about 0.5, otherwise the stratification is too coarse;
- keep the unmatched AUC as a secondary figure.

**S2. ROC vs PR.** Prevalence ranges from 0.2 % (ProSPECCTs D7) through 48 % (TOUGH-M1) to 93 % positives (Vertex).
- AP is nearly redundant on TOUGH-M1.
- On Vertex, AP for positives is trivially high, so report AP with *negatives* as the target class.
- AP is not comparable across partitions that differ in prevalence. Always print the prevalence and AP/prevalence.
- For a search tool used at prevalence ≪ 1 %, add an early-retrieval metric: McClish-standardised partial AUC at
  FPR ≤ 1 %, and per-query recall@k / MAP.

**S3. C2 definition.** A macro-average over D5, D5.2, D6, D6.2 and D7 double-counts: D5 and D5.2 share proteins,
and D6 and D6.2 are the same 62 pairs. It also weights D6 (SE ≈ 0.08) like D7. Changes:
- Define C2 on {D5.2, D6.2, D7} with **self-pairs excluded** from the claim. 49 of the 115 D7 actives are
  self-pairs, which any method scores at maximum.
- Report every subset with CIs.
- Treat D6/D6.2 as descriptive only.

**S4. Fair comparison to published numbers.** Published TOUGH-M1 AUCs use all pairs with fpocket pockets. Ours use
51 % of pairs with BURROW pockets. Changes:
- Also run the frozen method in "published-protocol mode": the shipped fpocket pocket residues and all pairs. Label
  it dev-contaminated.
- Anchor with one re-run published method (APoc, B2, or PocketMatch) in both modes, and quote Δ(ours − anchor).
- Compare only to zero-shot numbers (0.64–0.69, ProFSA 0.82), never to 0.91–0.94.

**S5. Multiple testing.** C4 (runtime) is a threshold check, not an inferential test, so take it out of the Holm
family. Before sealing, estimate the number of independent PPIPS-test orthogroups. If there are fewer than about
100, declare C3 exploratory.

## COULD

- **C-a.** In addition, report DeLong-style intervals with a two-way (pocket × pocket) U-statistic variance, as a
  check on the bootstrap.
- **C-b.** Store the per-pair test scores of every arm, so any later analysis needs no re-run on sealed data.

No other changes are needed. The confounder baselines, the sealed-set gating and the Holm correction are sound.
