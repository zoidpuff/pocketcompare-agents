# DESIGN — fast, fold-independent pocket similarity on BURROW (v2, 2026-10-27 20:10)

History: v0 (19:15) → review round 1 (reviews/round1_{pi,statistics,data,algorithms,domain,agent_failure_modes}.md)
→ v1 (19:35) → review round 2 (reviews/round2_panel.md) → v2 (this). Change logs in §10 and §11. Inputs: PROMPT.md, LITERATURE.md, reports/*.md.

## 0. Goal, deliverables, claims

Build **a versatile, fast tool that scores the similarity of two binding pockets independent of sequence and
fold**, on BURROW pockets, usable at AFDB scale (≈ 200 M structures × 5–15 pockets), for PDB and AlphaFold
models, and for pockets created at protein–protein interfaces (PPIs).

Deliverables: (1) the `pocketcompare` package and CLI (pocket → descriptor; pair → score; batch/ANN search);
(2) evaluation on public benchmarks and on our own leakage-controlled sets, runtime next to every accuracy;
(3) REPORT.md.

**Pre-registered confirmatory claims** (one Holm family; one-sided α = 0.05; paired vertex bootstrap, §4):
- **C1a** TOUGH-M1-test (L-mode): ROC-AUC(final) − ROC-AUC(B1) > 0. **C1b** same vs B4 (ESM-2 pocket embedding).
  Smallest effect of interest 0.03: reported with its lower CI bound; the minimum detectable effect is
  computed on dev and recorded before unsealing.
- **C2** ProSPECCTs D5.2 + D6.2 + D7 (self-pairs removed), macro ROC-AUC(final) − macro ROC-AUC(B1) > 0.
- **C3** PPI ligand-grounded test (§2.5 PPI-L): ROC-AUC(final) − ROC-AUC(B1) > 0 — only if the PPI-L gate
  (§2.5) passes; otherwise C3 is exploratory and the Holm family is {C1a, C1b, C2}.
- **C1-D** (amendment D11, before any test evaluation) TOUGH-M1-test, D-mode, common-set ROC-AUC(final) −
  ROC-AUC(B1) > 0. Holm family = {C1a, C1b, C1-D, C2} (C3 exploratory, D7).
Reported, not in the Holm family: runtime (C4: tier-1 descriptor ≤ 1 s/pocket incl. BURROW and ≤ 10 µs/pair
CPU); AF robustness (C5: BLiPS-test ROC-AUC with AF-model pockets vs holo pockets, Δ with CI); all other
benchmarks and arms. Published numbers are context only (different pocket definitions); we additionally run
one external method ourselves (B5) and use the per-pair APoc / G-LoSA / SiteEngine scores shipped with
TOUGH-M1 (B5-T) so that comparisons to prior art are paired. B0' (global TM-score) is reported next to C1.
The claim-bearing final method takes **no B4 input**; a fusion including B4 is descriptive only. B1 and B4
receive the same CSLS treatment as the final method.

## 1. Architecture

- **Tier 1 (index):** fixed-length vector, cosine (optionally a learned linear/MLP head), FAISS-indexable;
  ≤ 1 s/pocket incl. BURROW; ≤ 10 µs/pair; ≤ 512 B/pocket stored (PQ target ~64 B).
- **Tier 2 (re-rank, optional):** slower comparison on the tier-1 top-k (docking profile and/or alignment).
- **Hub correction:** every arm is evaluated raw and with CSLS-style local scaling (score − ½(mean top-k
  neighbour score of each pocket in a background set)), k = 10, background = the train/dev pocket pool.

## 2. Data, splits, leakage (all fixed and committed before any model is fit)

### 2.1 One homology graph for everything
Nodes = every protein chain in TOUGH-M1, ProSPECCTs, Vertex, BLiPS sources (BURROW train/dev, BURROW af_set),
PPI sets, and BURROW's training chains. Edges: MMseqs2 ≥ 30 % identity, E ≤ 1e-3, coverage ≥ 0.5 (BURROW's rule)
**or** Foldseek TM ≥ 0.5 in **both** directions (single-direction merge produced a 69 % giant component).
Edges use `pocketdetect.datasets.leakage.apply_rule` verbatim (BURROW's sequence rule) OR Foldseek TM ≥ 0.5 in
both directions. **Splits within a dataset assign connected components of that dataset's own graph; exclusion
across datasets uses direct edges** (a train/dev item is removed if it has an edge to any test item) — a single
global component graph over ~60k chains would percolate. Gate: largest within-dataset component ≤ 10 %, else
DataSAIL. ProSPECCTs/Vertex sequences are read for leakage control only. An independent agent re-derives the
splits and checks overlaps before the first model fit; realised counts are committed (test: counts only).

### 2.2 Pocket definitions (one adapter, `src/pocketcompare/pockets.py`, used by every method we run)
- **L-mode:** BURROW grid points (ligands/waters/hetero stripped) within 4 Å of the benchmark ligand heavy atoms
  (or, where only residues are given, within 4 Å of those residues' atoms with bur10 ≥ 0.5). Headline mode for
  public benchmarks (comparability with the literature).
- **D-mode:** BURROW `--output-rule region` pockets, touching sub-pockets merged; the site is represented by the
  merged detected pocket of maximal coverage of the L-mode pocket; it is a match if coverage ≥ 0.3 **or**
  precision ≥ 0.5 (detected points within 1.5 Å of L-mode points; BURROW pockets are often smaller than the 4 Å
  ligand shell — 13.9 % of TOUGH-M1 sites), else "missed" (5.5 % on TOUGH-M1 under this rule). Because the choice
  uses the ligand, D-mode is an oracle-assisted deployment proxy; the **blind** deployment test is §2.7.
- D-mode numbers on public sets are reported only on the BURROW-clean subset (§2.3).

### 2.3 TOUGH-M1 (primary public benchmark)
- **Dev = homology groups that contain any BURROW-train/dev homologue (~32 % of proteins); test = all other
  groups (BURROW-clean).** Within-partition pairs only. Test pair labels (and B0 scores, see DEV1) stay sealed.
- Groups with direct edges to BURROW train/dev **and** to any sealed test set (ProSPECCTs, Vertex, BLiPS-test,
  PPI-L-test) are excluded from both TOUGH-M1 partitions; their number is reported. (TOUGH-M1 shares 355 PDB IDs
  with ProSPECCTs.)
- The shipped APoc / G-LoSA / SiteEngine pair scores are attached to dev and (sealed) test pairs (B5-T).
- Report: realised counts, ligand-cluster composition per partition.

### 2.4 ProSPECCTs (D1–D7) and Vertex — sealed external tests
Read only by `scripts/final_eval.py`. Headline L-mode; self-pairs reported with and without. Vertex site rules
frozen after the PDB mirror sync completes.

### 2.5 PPI sets
- **PPI-L (ligand-grounded, test for C3):** the Pasteur PPI pocketome (Moine-Franel et al., Sci Data 2024;
  Zenodo 10.5281/zenodo.10805580; CC-BY-4.0; 23k VolSite cavities at PDB PPI interfaces with orthosteric /
  allosteric / ligand-free labels and iPPI-DB ligands). **Only cavities with a PDB HET modulator are used**
  (L-mode on that ligand). Positives = pockets binding the same or similar (ECFP4 Tc ≥ 0.5, ≥ 12 heavy atoms)
  modulators in different homology groups; negatives = ligand-bound pairs with Tc < 0.3 in different groups.
  Split by homology component 60/20/20. **Gate** (recorded before any score is computed): test positives ≥ 50
  pairs spanning ≥ 10 homology groups and ≥ 5 ligand clusters; else C3 is exploratory.
  Their 109-descriptor PSI (precomputed pair distances) is baseline B6 on PPI-L.
- **PPIPS (AFDB dimers; transfer task, not a headline of fold independence):**
  - P-sym (sanity): rank percentile of a pocket's symmetry copy among its scores against all other pockets of
    its split (expected ≥ 0.9).
  - P-ortho retrieval: for each cross-species interolog complex pair (< 30 % identity per chain), the query
    interface pocket must retrieve its residue-mapped counterpart (mapping through both chain alignments,
    pocket overlap ≥ 0.5) **among all pockets of the partner complex** (so the decoys share the fold). Metrics:
    top-1 / MRR. Compared against B0', B4 and Foldseek-local baselines.
  - Split by homology group: the giant group (45 % of complexes; hubs SKP1/CUL3/histones) goes to train; the
    rest 60/20/20; the 260 BURROW-train proteins are kept out of val/test.

### 2.6 BLiPS (BioLiP ligand-sharing pairs; training + a clean test)
- **Train** from BURROW train sites, **val** from BURROW dev sites, **test** from BURROW's held-out af_set (10,341
  human LIGYSIS sites on 3,465 proteins with holo chain + AFDB v6 model) — the test is BURROW-clean by
  construction and comes with AF models (→ C5). Homology groups from §2.1; train/val groups homologous to any
  test set are removed.
- Exclusions: ion/metal-only sites; additives/detergents/lipids/buffers (curated list committed as data:
  GOL, EDO, PEG family, SO4, PO4, CL, ACT, DMS, MPD, CLA, C8E, LDA, BOG, OLC, etc.); label ligands < 10 heavy
  atoms; sites with < 10 BURROW points. One label ligand per site (largest qualifying).
- Positives: sites in different homology groups sharing a ligand with ECFP4 Tc ≥ 0.7; stratified by number of
  shared ligands (1 vs ≥ 2). Negatives: different-group sites with max Tc < 0.3. Pairs capped per ligand
  cluster (Butina 0.6; ≤ 300 positives per cluster) and per protein (≤ 3 sites); results also reported
  without the top-20 promiscuous CCDs. **No subsampling to size-match:** size is handled by size-stratified
  AUC (§4); diagnostic B0m (§4).
- AUC also reported for seen vs unseen ligand chemotypes (ligand cluster present in train or not).
- BLiPS is primarily a training/selection resource; BLiPS-test is reported (secondary), C5 uses it. The
  AF-vs-holo pipeline is developed on val first (pocket_detect `af_train` dev sites) and stratified by holo
  release date (≥ 2018-05-01) and site pLDDT band.

### 2.7 Blind deployment test (secondary)
BLiPS-test proteins, AF models, BURROW region-rule pockets without any ligand guidance: for each true site, rank
all detected pockets of all other test proteins; report hit rates for the partner sites. Plus a human-proteome
FAISS demo (§6).

### 2.8 Leakage of models used to prepare receptors
- BURROW: tier-1 features are BURROW's **analytic** point features only (no `point_score`, no ranker scores);
  learned features are an ablation. D-mode/blind tests use BURROW detection and are evaluated on BURROW-clean
  data (TOUGH-M1-test, BLiPS-test = af_set). 
- ADock: **stock Vina** weights only (no fitted weights, no template mode, no reranker); Vina's weights were fit
  on PDBbind-era data (disclosed limitation).
- ESM-2 (B4) was pretrained on UniRef (which includes test sequences) without labels; disclosed.

## 3. Methods

**Baselines.** B0 size only (−|log vol ratio|) and size-stratified variants; B0' MMseqs2 identity and Foldseek
TM (global); B1 BURROW size-free descriptor cosine (z-scored on dev); **B4 ESM-2 (650M) mean of lining-residue
embeddings, cosine** (EPoCS-style; strong, not sequence-independent); **B5 one external method run locally**
(EPoCS if it installs in ≤ 1 h, else PocketVec precomputed descriptors on overlapping ProSPECCTs pockets, else
APoc); B6 PSI on PPI-L; published numbers (LITERATURE.md §3) as context.

**A1 — typed volumetric fingerprint (main tier-1 bet).**
- Points: L/D-mode pocket points, **weighted by `vol`** and resampled to a uniform 2 Å lattice (removes the
  thinning artefact from BURROW's coarse exposed sub-lattice).
- Typing: soft VolSite-style typing by nearest protein atoms within 4.5 Å: hydrophobic, aromatic, donor,
  acceptor, donor/acceptor, positive, negative, metal; plus a "shape" (all points) channel and a buriedness
  tertile.
- Blocks: (i) type × buriedness histograms; (ii) pairwise-distance distributions per type pair, 12–16
  Gaussian-smoothed bins on 2–20 Å; (iii) typed USRCAT-like shape moments; (iv) global scalars (log volume
  kept separate and down-weighted). Square-root (Hellinger) transform, z-score (train statistics), cosine.
- ≤ 20 configurations pre-registered in `configs/a1_grid.yaml`. Selection score = mean cluster-balanced AUC over
  TOUGH-M1-dev and BLiPS-val; one-SE rule on that mean.

**A4b — learned metric on A1 (+B1) (main tier-1 bet #2).** MLP projection to 64–128 d, trained on BLiPS-train
(+PPIPS-train, + augmentation pairs: same site L-mode vs D-mode, holo vs AF / apo from pocket_detect
`af_train`/`apo_train` sites in BLiPS-train groups, homodimer symmetric copies) with a graded ligand-similarity
contrastive loss (ErePOC-style KL to ligand Tc). **A4b and A5 are selected on BLiPS-val (+PPIPS-val) only;
TOUGH-M1-dev selects non-learned arms only** (TOUGH-M1-dev is BURROW-family-related to BLiPS-train). Seeds SEEDS[:3]; the reported model is the seed-mean ensemble, never a picked seed.

**A2 — docking-profile descriptor (human prior; gated).**
- ADock `frag_lite_np`, stock Vina, rigid receptor, **fixed 12 Å cubic box** at the pocket centre (box volume
  must not proxy pocket size). Poses accepted only if the centroid lies within 2 Å of a pocket point; otherwise
  "non-binder".
- Panel: **128 fragments** from a recognised public fragment library, stratified by pharmacophore class ×
  heavy-atom bin (10–14 HA core); and, as the pre-registered comparison, **128 lead-like** molecules (MW
  200–450) at matched compute. Sources/licences in DATA.md. Seed reproducibility (score r and top-pose RMSD
  across 3 seeds) is checked first for each panel.
- Descriptors: (a) PocketVec-style rank vector, non-binder = score above the panel's 90th-percentile score;
  (b) ligand-efficiency-normalised scores, residualised on log volume and buriedness, per-fragment z-scored on
  the background pool; (c) **pose interaction profile** (novel): per fragment, contact-type counts of the best
  pose (H-bond donor/acceptor matched, apolar, aromatic, charged), buried fraction.
- **Gate (TOUGH-M1-dev, size-stratified AUC):** A2 must add ≥ 0.01 to A1 in a cross-fitted fusion (lower CI
  bound > 0); the gain over A1 + B4 is reported descriptively. Fails → reported negative, not developed further.
- PPI sub-hypothesis (pre-registered): fragments beat lead-like on shallow interface pockets (PPIPS P-ortho
  and PPI-L-val).

**A3 — alignment (stretch, 3 h time box).** Weighted pseudocentres (32–48 per pocket, typed), Gaussian
overlap maximisation on GPU; initialisation from 4 proper PCA flips × 24 cube rotations (no reflections);
Tanimoto and Tversky. Only if A1/A4b are done by 03:00.

**A4 — point network (stretch).** Only if A4b saturates and time allows.

**A5 — fusion.** Logistic regression on val scores (cross-fitted); hub correction applied before fusion.

## 4. Evaluation and statistics

- Metrics: ROC-AUC (field standard), PR-AUC with prevalence and AP lift, partial AUC (FPR ≤ 0.1);
  **cluster-balanced AUC** (each ligand cluster / homology group weighted equally) next to pair AUC; per-cluster
  AUC for the 10 largest clusters; retrieval: top-1/top-10/MRR.
- Size control: **2-D size-stratified AUC** — strata = quintiles of the pair's mean L-mode log-volume ×
  **20 quantile bins** of |Δ log-volume| (amendment D6: 5 × 5 left a residual size shortcut of 0.539 in
  simulation, 5 × 20 gave 0.507; sets with < 500 positives use 5 × 5) (edges from the evaluated partition);
  per-stratum AUC weighted by n positives;
  strata lacking a class dropped and counted. Diagnostic B0m (logistic on log v_a + log v_b and |Δ|, fit on dev)
  must give stratified AUC 0.5 ± 0.03.
  Pocket-marginal shortcut baseline (score = f(pocket a) + f(pocket b), e.g. per-pocket mean similarity).
- Uncertainty: **vertex (two-way) bootstrap** — resample units; pair weight = c_u if both pockets are in unit u,
  else c_u · c_v. TOUGH-M1 unit = connected component of (ligand cluster ∪ homology group), ligand cluster =
  component of the positive-pair graph. BLiPS/PPI: run with homology-group units and with Butina ligand-cluster
  units; report the wider CI. C2: independent bootstrap per subset (unit = homology group), macro Δ per replicate
  index. B = 2,000; paired for differences. MDE from dev scaled to test by √(n_units_dev / n_units_test).
- Failures/misses: primary comparison on the common pair set where all compared arms have scores; plus
  worst-case bound (misses scored adversarially) and miss rates by label. Never silently dropped.
- Selection: every arm/config evaluated on dev is appended to `results/trials.tsv` (append-only). Final config =
  the simplest within one SE of the best dev score (pre-declared). One frozen config goes to test.
- Seeds: SEEDS = [0..4]; learned arms use SEEDS[:3] and report the ensemble.
- Cut order if behind at 03:00: A3/A4 → proteome demo → §2.7 blind test → P-ortho. Inputs to C1–C3 are never cut.

## 5. Verification and controls
- `src/pocketcompare/evaluate.py` written and unit-tested **first** (toy pairs with known AUC/AP; bootstrap
  coverage on simulated data; miss handling). Frozen; its hash goes into every result sidecar.
- Toy/geometry tests: identity → max; rotation/translation/point-order invariance; type-permuted copy scores
  lower; a uniformly scaled pocket is not rewarded by size-free blocks.
- Positive controls: same site in two PDB entries of one protein; homodimer P-sym copies. Negative controls:
  shuffled labels ≈ 0.5; random descriptors ≈ 0.5; B0.
- Provenance: every result file gets a `.prov.json` sidecar (git commit, script, args, config hash, input
  hashes, evaluate.py hash, seed, device, wall time) written by `pocketcompare.provenance`. REPORT numbers come
  only from sidecar'd files; `scripts/check_report.py` checks this.
- An agent that did not produce a result verifies it (different code path where feasible) before REPORT use.

## 6. Compute and storage
- BURROW: default preset ≈ 0.1 s/structure-core; 40 dimers/s on 16 CPUs.
- ADock fragments: ≈ 150 pockets/s/node at 64 fragments → ~75 pockets/s at 128.
- Storage target ≤ 150 GB (cap 500 GB); report bytes/pocket (float32 128 d = 512 B; PQ-64 ≈ 64 B) and FAISS
  recall@10 of PQ vs exact on the human-proteome demo (23.6k AF models, BURROW pockets, all-vs-all).
- AFDB-scale numbers are extrapolated from measured throughput, not run.
- Resource leases: GPUs assigned per agent (cuda:k) in the agent brief; ≤ 32 CPU workers per agent; timing runs
  for C4 on an otherwise idle node slot, median of ≥ 3 warm runs.

## 7. Process safeguards
- Sealed labels in `data/sealed/` (chmod 000; sha256 committed). `scripts/final_eval.py` needs `FINAL_EVAL=1`, a
  clean tree and a committed `FREEZE.json` (commit, config hash, weights hash); final eval runs from a git
  worktree at the frozen commit. Only the PI unseals.
- Agents work in their own files/directories; only the PI edits DESIGN/RESEARCH_TREE/LESSONS/REPORT; splits are
  read-only once committed. Long jobs detached, logged, with completion markers; kill only stored PIDs.
- Time boxes: PPI-L + PPIPS build 3 h; A2 gate 3 h; A3 3 h.

## 8. Timeline (start 18:00; now 19:35)
- by 21:30: design v2 (round 2), evaluate.py + provenance, homology graph + all splits committed; point caches.
- 21:30–03:00: B0–B5, A1 grid, A2 gate, PPI builds, A4b.
- 03:00–09:00: fusion, hub correction, robustness, stretch arms, proteome demo.
- 09:00–11:00: freeze + verification; 11:00–13:00 final eval + independent re-check; 13:00–17:00 REPORT.

## 9. Open questions (after round 2)
- PPI-L feasibility is decided by its gate (§2.5), recorded before any score.
- TOUGH-M1-dev (BURROW-homologous groups) may differ in composition from test; its ligand-cluster composition is
  reported next to test counts.

## 10. Changes vs v0 (from round 1)
Scope cut (A3, A4 → stretch; A4b promoted) [PI M1, algorithms 4]. Added B4 ESM-2 and B5 external baseline
[PI M2, domain 6, algorithms 7]. Claims: C1 vs B1 and B4, Δ > 0 with 0.03 SESOI, C4 out of Holm, C5 added, C2
without self-pairs [PI M3, stats 2]. PPI: interolog task → within-complex-pair retrieval (fold-honest); new
ligand-grounded PPI-L from Pasteur pocketome; PSI baseline [PI M4, domain 1/5]. Splits: one homology graph,
bidirectional Foldseek edges; TOUGH-M1 dev = BURROW-homologous groups (32 % of TOUGH-M1 leaks into BURROW);
BLiPS test = BURROW af_set; PPIPS giant group to train [data 1–5]. BLiPS labels: additives list, ≥ 10 HA,
shared-ligand-count strata, seen/unseen chemotypes, stratified AUC instead of subsampled size matching [data
6–8, domain 4/11, stats]. Statistics: vertex bootstrap by ligand cluster, cluster-balanced AUC, misses on common
set + worst case, one-SE selection, trials.tsv [stats 1,3,5,6]. A1: vol weighting + 2 Å resampling, soft typing,
Hellinger, ≤ 20 configs [algorithms 1, 6]. A2: fixed 12 Å box, 128-fragment stratified panel vs 128 lead-like,
LE normalisation, non-binder criterion, pose-in-pocket check, gate vs published Vina 0.55 [domain 2/3/7/8/9,
algorithms 5]. A3: proper rotations only, pseudocentres [algorithms 2]. CSLS hub correction [algorithms 3].
Safeguards: sealing, FREEZE.json, provenance sidecars, evaluate.py first, worktree final eval [agent-failure].
Not adopted: Govindaraj–Brylinski 1,515-drug replication (cost; replaced by the dev gate against their published
Vina number); 40/60 TOUGH-M1 split (superseded by the BURROW-homology split).

## 11. Changes vs v1 (from round 2, reviews/round2_panel.md)
Adopted MUST 1 (TOUGH-M1 doubly-homologous groups excluded from both partitions), 2 (within-dataset components +
direct-edge cross-dataset exclusion, ≤ 10 % gate), 3 (A4b augmentations from af_train/apo_train; A4b/A5 selected
on BLiPS-val only), 4 (2-D size strata + B0m diagnostic), 5 (bootstrap weights, units, C2 bootstrap), 6 (PPI-L
ligand-bound only + gate), 7 (raw label lists chmod 000, done 20:05). SHOULD 8–12 and COULD 13–16 adopted.
Added B5-T (TOUGH-M1 shipped APoc/G-LoSA/SiteEngine pair scores) as paired prior-art comparators.
