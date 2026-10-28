
# REPORT (draft) — fast, fold-independent pocket similarity on BURROW

Status: draft written 2026-10-28 ~03:30 CET, after method freeze decision D20 and the re-audit PASS, **before** the
final held-out evaluation. Every number below is a development (dev/val) number unless it sits in a
`[[...]]` placeholder. Sources are noted as `<!-- src: ... -->` after number-bearing sentences; keyed tags
(`path#key`) are machine-checkable by `scripts/check_report.py`.

---

## 1. Summary

**What we built.** `pocketcompare` describes every BURROW pocket of a structure (PDB or AlphaFold model, monomer
or dimer) with a 384-dimensional unit vector and scores two pockets by cosine. The vector does not use sequence
or fold. The final method, **A4b:n1_linear (raw cosine)**, works in four steps:

1. A ligand-free "sph8" site shaper takes the buried BURROW grid points within 8 Å of the pocket's
 buriedness-weighted centroid.
2. On that point set we compute a typed volumetric fingerprint (A1, 514 d) and a protein-environment block
 (env, 113 d). Together these form N1 (627 d).
3. A linear projection to 128 d is trained contrastively on BioLiP ligand-sharing pairs (BLiPS-train), AlphaFold
 dimer pocket pairs (PPIPS-train) and same-site ligand-defined ↔ detected pairs.
4. Three seeds are concatenated into the 384-d vector.

Cost after BURROW is ≈ 3.5 ms per pocket on one CPU thread and ≈ 0.1 µs per pair in batched search, and the
vectors go straight into FAISS. <!-- src: results/dev/final_method_runtime.json (measured for the sibling A4b:n1_base; same input pipeline) -->

**Dev results (rebuilt splits, cluster-balanced ROC-AUC).**
- **Deployment (detected-pocket, D) mode.** The final method scores 0.737 <!-- src: results/dev/l4/final_select_all_l4_summary.parquet#auc_cb[cand=A4b:n1_linear,variant=raw,dataset=blips,mode=D] --> on BLiPS-val and 0.721 <!-- src: results/dev/l4/final_select_all_l4_summary.parquet#auc_cb[cand=A4b:n1_linear,variant=raw,dataset=tough_m1,mode=D] --> on TOUGH-M1-dev.
- BURROW's own descriptor (B1) scores 0.648 <!-- src: results/dev/l4/final_select_all_l4_summary.parquet#auc_cb[cand=B1,variant=raw,dataset=blips,mode=D] --> and 0.617 on the same sets.
- An ESM-2 lining-residue embedding (B4) scores 0.670 and 0.598. <!-- src: results/dev/l4/final_select_all_l4_summary.md -->
- **Ligand-defined (L) mode.** The final method is roughly level with B1 on BLiPS-val (0.718 vs 0.701) and above it
on TOUGH-M1-dev (0.720 vs 0.639). <!-- src: results/dev/l4/final_select_all_l4_summary.md -->
- **How sure we are.** Paired bootstrap CIs against B1 include zero for the sibling head n1_base on BLiPS-val
(+0.069 [−0.029, +0.132]). No paired CI has been computed for n1_linear itself. Dev power is limited, so these
are directions, not established gains. <!-- src: results/dev/l4/final_select_all_l4_summary.md -->

**Key findings.**
1. **The ligand imprint.** Pockets cut as a 4 Å shell around the bound ligand carry the ligand's shape and size.
 On TOUGH-M1-dev the best handcrafted fingerprint (A1) scores ROC-AUC 0.793 on ligand-defined pockets and 0.549
 on BURROW-detected pockets of the same sites, a drop of −0.244 [−0.328, −0.186]. B1 loses only 0.06 and B4 only
 0.03. The drop replicates on BLiPS-val: −0.161 [−0.245, −0.082]. <!-- src: reports/dev_eval_v2splits.md -->
 Benchmarks whose positives are ligand-defined therefore reward pocket-definition artefacts. Ligand-free site
 shaping removes most of the definition sensitivity: same-site L↔D agreement is 0.996. <!-- src: reports/definition_robustness.md -->
2. **Size is a strong shortcut.** Pocket volume alone (B0) gives ROC-AUC 0.782 on TOUGH-M1-dev, and a size
 logistic gives 0.861, above every similarity method we ran. Size-stratified AUC removes this (B0m 0.491). <!-- src: reports/dev_eval_v2splits.md -->
3. **Fragment docking as a descriptor (the human prior) failed its pre-registered gate.** Adding the fragment
 block to A1 changed size-stratified AUC by −0.009 [−0.066, +0.023]. The sub-hypothesis that fragments beat
 lead-like molecules on shallow PPI pockets was not supported. <!-- src: reports/dev_eval_v2splits.md -->
4. **Scale.** On the human AlphaFold proteome (23,586 models → 116,246 pockets), BURROW plus the ligand-free
 descriptor ran at 132.8 <!-- src: results/proteome/summary.json#runs.run_gpu.structures_per_s --> structures/s
 on 2 GPUs and 22 CPU workers. Exact FAISS all-vs-all top-50 took 0.51 <!-- src: results/proteome/index_search.json#exact.all_vs_all_wall_s --> s.
 The extrapolated cost for 200 M AFDB structures is ≈ 7,150 CPU-core-h + 223 GPU-h. <!-- src: reports/proteome_demo.md -->

**Main caveats.** The headline TOUGH-M1 test set is small after leakage control. Its minimum detectable effect is
≈ 0.12–0.13 AUC, so the confirmatory claims are underpowered by design. <!-- src: reports/dev_eval_v2splits.md -->
Learning over the non-learned parent N1 is not demonstrated: n1_base − N1 is +0.020 [−0.060, +0.088] on BLiPS-val
D. The learned heads lower PPI ortholog-transfer retrieval (PPIPS MRR 0.719 vs N1's 0.790). <!-- src: results/dev/l4/final_select_all_l4_summary.md -->

> **[[TEST RESULTS — filled after final evaluation]]**
> C1a / C1b / C1-D / C2: Δ, 95 % CI, Holm p — headline sentence.
> BLiPS-test L/D, ProSPECCTs, Vertex, PPIPS-test, C5 (AF vs holo) headline sentence.
> Independent re-derivation of every headline: [[verifier, date, result]].

---

## 2. Problem, scope, benchmarks

**Task.** Score whether two binding pockets are similar, meaning they bind the same or similar ligands, without
using sequence or fold. Pockets come from BURROW, our pocket finder. The method has to run at AFDB scale
(≈ 200 M structures × ~5 pockets), work on AlphaFold models, and handle pockets created at protein–protein
interfaces. Intended uses are off-target and repurposing search, functional annotation, and evolutionary
comparison. The brief asked for a fast, versatile tool.

**"Fold-independent" in this report** means three things together:
- the method takes no sequence or fold input (B4 does, and is kept only as a baseline);
- the primary benchmark's positives and negatives are both structurally unrelated. TOUGH-M1 imposes TM-score
< 0.4 on both classes, so global TM-score scores 0.51 in the original paper <!-- src: LITERATURE.md §3.2 --> and our Foldseek B0′ scores 0.508 on dev; <!-- src: reports/dev_eval_tough_m1.md -->
- no test protein, or homologue of one, appears in training or in BURROW's training data. Homology is MMseqs2
≥ 30 % identity under BURROW's rule, or Foldseek TM ≥ 0.5 in both directions.

Ligand sharing is a proxy for pocket similarity, so promiscuous ligands and cofactors are reported separately.

**Pocket definitions.**
- **L-mode:** BURROW points within 4 Å of the benchmark ligand. This is the literature convention.
- **D-mode:** the BURROW-detected pocket that best covers the site. It counts as a match if coverage ≥ 0.3 or
precision ≥ 0.5. Choosing the pocket uses the ligand, so D-mode is an oracle-assisted proxy for deployment.
- **Blind test (§7):** no ligand guidance at all.

**Benchmarks and why.**

| set | role | size (dev / val / test) | notes |
|---|---|---|---|
| TOUGH-M1, BURROW-clean split | C1a/C1b (L), C1-D (D) | dev 765 pockets (3,450 pos / 7,124 neg pairs) · test 1,045 pockets (10,160 / 14,177), sealed | dev = groups homologous to BURROW training; test = BURROW-clean rest <!-- src: data/splits/SPLITS.md --> |
| ProSPECCTs D5.2 + D6.2 + D7 (self-pairs removed) | C2 (L) | sealed external | the subsets that test fold-independent similarity; P7 has 49 self-pairs among 115 actives <!-- src: reports/data_benchmarks.md --> |
| Vertex | reported (L) | 6,149 / 6,218 pockets cached; sealed | site rule fixed to DeeplyTough's public rule (D17) <!-- src: reports/final_eval_infra.md --> |
| BLiPS (our BioLiP ligand-sharing pairs) | training, selection, reported test, C5 | train v2 2,318 sites (6,992 pos) · val v2 523 sites (462 pos, 52 ligand clusters) · test 3,606 sites (6,919 pos), sealed | test = BURROW's held-out af_set, so BURROW-clean, and each site has an AF model <!-- src: data/splits/SPLITS.md --> |
| PPIPS (AFDB predicted dimers) | PPI training, reported | 1,991 complexes; P-ortho val 217 queries in 17 units | P-sym = symmetric copy in homodimers (sanity check); P-ortho = cross-species interolog counterpart among the partner complex's pockets <!-- src: reports/ppi_datasets.md, reports/dev_eval_v2splits.md --> |
| PPI-L (Pasteur PPI pocketome) | planned C3 → exploratory | 2,236 modulator pockets | gate failed (below) <!-- src: reports/ppi_datasets.md --> |

**Consequences of the TOUGH-M1 BURROW-clean split.**
- 32 % of TOUGH-M1 proteins are homologous to BURROW training data. <!-- src: RESEARCH_TREE.md D4 -->
Their groups form dev. Groups that touch both BURROW and a sealed set were excluded: 5,779 / 7,524 pockets
(77 %) under the original graph and 5,714 (76 %) after the D15 rebuild. <!-- src: reports/splits.md, data/splits/SPLITS.md -->
- The test set is therefore ~1 k pockets, not 7.5 k. Its units (connected components of ligand cluster ∪ homology
group) include one giant unit: 787 of 1,045 pockets in 133 units. <!-- src: reports/dev_eval_v2splits.md -->
- The projected test MDE for Δ(final − B1) is ≈ 0.13 under the original split (0.127) and ≈ 0.12 after the rebuild.
That is about four times the 0.03 smallest effect of interest. The unit definition was kept as pre-registered (D12). <!-- src: results/dev/tough_m1_dev_details.json, reports/dev_eval_v2splits.md -->
- Results are **not comparable** to published full-TOUGH-M1 numbers: zero-shot APoc 0.65, SiteEngine 0.66,
G-LoSA 0.69, ProFSA 0.82; DeeplyTough 0.91–0.93 when trained on TOUGH-M1. <!-- src: LITERATURE.md §3.2 -->
For context we report a secondary "TOUGH-M1 full minus dev" evaluation for non-learned arms only (D8).
- A looser structural rule would have enlarged test: TM ≥ 0.7 gives 2,228 test pockets. The rule was not changed
after counts were seen. <!-- src: data/splits/SPLITS.md -->

**PPI-L gate failure (D7).** The ligand-grounded PPI test needed ≥ 50 test positives spanning ≥ 10 homology groups
and ≥ 5 ligand clusters. The whole set has only 175 cross-group positive pairs, and the test split has 3 pairs in
2 groups and 1 cluster. PPI-modulator chemistry is target-specific: 4,312 positive pairs fall within one UniProt
entry, against 175 across groups. <!-- src: reports/ppi_datasets.md --> C3 became exploratory before any score
was computed. PPI performance therefore rests on PPIPS. P-ortho is an interolog transfer task in which sequence
embeddings excel, so it does **not** test fold independence.

---

## 3. The method

```
structure (PDB / AF model / dimer)
 │  BURROW featurisation (analytic point features only; no learned point_score)       ~0.1–0.4 s/structure
 ▼
sites:  D-mode = each BURROW region-rule pocket     │  L-mode = 4 Å ligand shell (or residue shell)
 ▼
sph8 shaper: buried points (bur10 ≥ 0.5) within 8 Å of the vol·bur16⁴-weighted centroid      0.2–0.5 ms
 ▼
A1 typed volumetric fingerprint (514 d)  ⊕  env protein-environment block (113 d)  = N1 (627 d)   ~4.7 ms
 ▼
per-part z-score (BLiPS-train stats), clip ±5 → 3 linear heads (627→128, seeds 0–2), L2 → concat/√3   64 µs
 ▼
384-d unit vector → cosine (= mean seed cosine) → FAISS IndexFlatIP / OPQ-IVF-PQ           0.1 µs/pair batched
```
<!-- src: configs/final_method.yaml, reports/a4b_selection.md, reports/a1_descriptors.md, results/dev/final_method_runtime.json -->

**Site shaper (sph8).** BURROW's detected sub-pockets are compact cores. The ligand shell, by contrast, follows the
ligand. sph8 replaces both with the same object: every buried solvent-grid point within 8 Å of a
buriedness⁴-weighted centroid. If that set is empty (one fully exposed site in all our data), the located set is
used. The shaper makes the description almost independent of how the site was found. Label-free retrieval of a
site's D descriptor from its L descriptor reaches AUC 0.996, against 0.765 for A1 on the raw definitions. <!-- src: reports/definition_robustness.md -->

**A1, the typed volumetric fingerprint.** Points are weighted by volume and resampled to a pocket-anchored 2 Å
lattice. Each point gets a soft VolSite-like type from protein atoms within 4.5 Å: hydrophobic, aromatic, donor,
acceptor, donor/acceptor, positive, negative, plus a metal channel. The fingerprint has five blocks:
- type × buriedness-tertile histograms (27);
- Gaussian-binned pairwise distance distributions for 28 type pairs (392, 2–20 Å);
- USR-like shape moments with soft extreme points (84);
- global buriedness and shape scalars (10);
- log volume (1).

Hellinger is applied to the histogram and pair blocks. The descriptor is exactly rigid-motion invariant (relative
error ≤ 1.3e-7), point-order free and deterministic. <!-- src: reports/a1_descriptors.md -->

**env.** env holds 113 protein-side features: volume- and buriedness⁴-weighted means of BURROW's first-hit
chemistry, neighbour-residue-group and 8/12 Å composition features, plus a first-hit chemistry × buriedness
histogram. It costs 0.15–0.3 ms. Almost no part of it depends on the exact point set (agreement 0.997). <!-- src: reports/definition_robustness.md, reports/a4b_selection.md -->

**Linear head (A4b:n1_linear).**
- *Inputs:* N1, z-scored per part with BLiPS-train v2 statistics (L + D rows) and clipped to ±5.
- *Architecture:* one linear map 627 → 128 per seed (dropout 0.2), seeds SEEDS[:3]. The stored vector is the
concatenation of the three L2-normalised outputs divided by √3, so the inner product equals the mean seed cosine.
- *Training data:*
- 6,992 BLiPS-train ligand-sharing positives;
- 1,602 L↔D same-site positives, which teach invariance to pocket definition;
- 3,177 PPIPS-train P-sym/P-ortho positives.
- *Loss:* InfoNCE with masked in-batch negatives, plus BCE on balanced labelled pairs.
- *Early stopping:* on 10 % of BLiPS-train homology groups; best epochs were 3, 4 and 5.
- *Data rules:* nothing from TOUGH-M1, BLiPS-val, PPIPS-val or any test set was used in training. Twelve configs
were pre-declared in `configs/a4b_grid.yaml` before any fit. Training all 12 × 3 seeds took 2 min. <!-- src: configs/final_method.yaml, reports/a4b_selection.md -->

CSLS hub correction is implemented (k = 10, background = the searched database) but **not** used by the final
method (raw variant).

**How it plugs into BURROW.**
- `pocketcompare.pockets.featurize_structure` runs BURROW's reference pipeline once on the protein-only view.
- `pocketcompare.pockets_fast` is a byte-identical fast CPU/GPU backend used for the proteome. <!-- src: reports/proteome_demo.md -->
- Only BURROW's analytic point features are used. BURROW's learned scores play no role in the descriptor, so its
training set matters only for which pockets are detected. This is why D-mode claims are evaluated on
BURROW-clean data.

**API** (`src/pocketcompare/method.py`; config and weights verified by sha256 on load):
- `describe(structure, site=None|ligand file|xyz|residue list, af_mode=…, locate="shell"|"burrow")` returns an
(n, 384) array: one row per BURROW pocket when `site=None`, otherwise one row for the given site.
- `similarity(a, b)` returns the inner product.

There is no command-line wrapper yet; README.md shows the Python usage. Six tests cover the API:
- it reproduces the evaluated vectors in L and D mode;
- similarity under rigid motion stays > 0.995;
- repeated calls are bit-identical;
- self-similarity is 1 and the maximum;
- a tampered weight file is rejected. <!-- src: reports/a4b_selection.md -->

**Search.** The vectors are unit-norm, so `faiss.IndexFlatIP` gives exact cosine search. The PQ settings below were
measured on the proteome demo's 627-d N1 vectors, not the final 384-d head (§6).

---

## 4. Development results (dev/val only)

All numbers in this section use the **rebuilt splits** (D15/D18) unless marked "old splits". Earlier numbers are
provisional and are mentioned only where they drove a decision.

### 4.1 Final-selection table (PREREG §1)

Metric: cluster-balanced ROC-AUC (cb). SE from the homology-group vertex bootstrap, B = 2,000. The objective is
BLiPS-val D cb. Columns are BLiPS-val D (1,544 pairs / 287 pos), BLiPS-val L (2,772 / 462), TOUGH-M1-dev D
(8,540 / 2,843) and TOUGH-M1-dev L (10,574 / 3,450). <!-- src: results/dev/l4/final_select_all_l4_summary.md -->

| candidate | dims | BLiPS D cb (SE) | BLiPS L cb | TM-dev D cb | TM-dev L cb | PPIPS P-ortho MRR | P-sym pct |
|---|---|---|---|---|---|---|---|
| B1 BURROW descriptors (raw) | 45 | 0.648 (0.040) | 0.701 | 0.617 | 0.639 | 0.761 | 0.997 |
| B4 ESM-2 raw / CSLS | 1280 | 0.670 / 0.711 | 0.641 / 0.687 | 0.598 / 0.588 | 0.602 / 0.610 | 0.986 / 0.973 | 1.000 |
| N1 = A1(sph8)+env(sph8), non-learned | 627 | 0.697 (0.040) | 0.706 | 0.667 | 0.656 | 0.790 | 0.999 |
| N2 = N1 + A1(located sub-pocket) | 1141 | 0.704 (0.039) | 0.738 | 0.646 | 0.719 | 0.803 | 0.997 |
| A4b:n1_base (MLP) raw | 384 | 0.717 (0.038) | 0.702 | 0.687 | 0.695 | 0.694 | 0.999 |
| **A4b:n1_linear raw (final)** | 384 | **0.737** (0.038) | 0.718 | 0.721 | 0.720 | 0.719 | 0.999 |
| A4b:n2_linear CSLS (best A4b) | 384 | 0.751 (0.036) | 0.755 | 0.702 | 0.754 | 0.755 | 0.999 |
| L4:egnn_small CSLS (best overall) | 384 | 0.756 (0.040) | 0.765 | 0.661 | 0.694 | 0.821 | 1.000 |
<!-- src: results/dev/l4/final_select_all_l4_summary.md, results/dev/l4/final_select_all_l4_ppips.parquet -->

Other rows for the final method:
- 95 % CIs: BLiPS-val D [0.650, 0.802]; TOUGH-M1-dev D [0.674, 0.804].
- Plain pair ROC-AUC: BLiPS-val D 0.741, TOUGH-M1-dev L 0.734.
- Size-stratified AUC: BLiPS-val D 0.735, TOUGH-M1-dev L 0.727. <!-- src: results/dev/l4/final_select_all_l4_summary.parquet -->

**Paired comparisons available.** These come from the selection run's paired bootstrap. They cover n1_base, N1 and
L4. No paired Δ was computed for n1_linear, so its gaps to B1 are point differences only.
- N1 − B1, TOUGH-M1-dev D: +0.050 [+0.010, +0.125].
- n1_base − B1: BLiPS-val D +0.069 [−0.029, +0.132]; TOUGH-M1-dev D +0.070 [−0.012, +0.128].
- n1_base − N1, BLiPS-val D: +0.020 [−0.060, +0.088].
- L4 − B1, BLiPS-val D: +0.108 [+0.018, +0.181].
- L4 − N1: BLiPS-val D +0.059 [−0.006, +0.130]; TOUGH-M1-dev D −0.006 [−0.089, +0.068]. <!-- src: results/dev/l4/final_select_all_l4_summary.md -->

Reading:
- Every ligand-free candidate beats B1 and B4 in D-mode on both sets, but most individual CIs include 0.
- L4 is best in-distribution (BLiPS, PPIPS) but does not transfer to TOUGH-M1-dev D.
- The learned linear head beats the non-learned N1 by 0.04 (point estimates) on BLiPS-val D and by 0.054 on
TOUGH-M1-dev D. That second gap is on a set never used for training or selection. It costs 0.07 in PPIPS MRR.

### 4.2 Arms on TOUGH-M1-dev, L-mode (rebuilt splits)

765 pockets, 10,574 pairs (3,450 pos), 152 units (largest 478). <!-- src: reports/dev_eval_v2splits.md -->

| arm | ROC-AUC | cb-AUC | size-strat. AUC |
|---|---|---|---|
| B0 size, −\|Δ log V\| | 0.782 | — | 0.535 |
| B0m size logistic (diagnostic) | 0.861 | — | 0.491 |
| A1 pair_only (old dev pick) | 0.779 | 0.794 | 0.705 |
| A1 default | 0.775 | 0.792 | 0.707 |
| B5-T SiteEngine (shipped column c1) | 0.672 | — | — |
| B1 | 0.635 | 0.639 | — |
| A2 fragments IFP + CSLS | 0.621 | — | — |
| B4 ESM-2 (z-scored) | 0.595 | — | — |
| B5 EPoCS (run locally) | 0.568 | — | — |
| controls: random vectors / shuffled labels | 0.498 / 0.493 | — | — |
<!-- src: reports/dev_eval_v2splits.md, results/dev/l4/final_select_all_l4_summary.md -->

On the old splits, the shipped APoc PS-score scored 0.600 and G-LoSA 0.646. The global TM-score (B0′) scored 0.508,
as TOUGH-M1's construction intends. <!-- src: reports/dev_eval_tough_m1.md -->

### 4.3 The ligand-imprint finding (L vs D)

This is the central and most generalisable finding. On the **same pairs**, switching from ligand-defined to
detected pockets gives:

| set | A1 pair_only/default L → D (Δ [CI]) | B1 Δ | B4 Δ |
|---|---|---|---|
| TOUGH-M1-dev | 0.793 → 0.549, −0.244 [−0.328, −0.186] | −0.059 | −0.030 |
| BLiPS-val | −0.161 [−0.245, −0.082] | −0.041 | +0.013 |
<!-- src: reports/dev_eval_v2splits.md -->

The first-run numbers were similar: −0.249 on TOUGH-M1-dev and −0.268 on BLiPS-val. <!-- src: reports/dev_eval_tough_m1.md, reports/dev_eval_blips_ppips.md -->

**Mechanism.** A 4 Å shell around the crystal ligand has the ligand's volume and internal distance distribution.
On benchmarks whose positives are defined by shared ligands, a shape-sensitive descriptor of that shell partly
recognises the ligand rather than the pocket.

**Label-free evidence.** Before any labels were used, the same site described in L and D mode was retrieved with
AUC 0.70 by A1 and 0.94 by B1. <!-- src: reports/a1_descriptors.md -->

**What fixes it.** Ligand-free site shapers trade L-mode performance for D-mode performance. With sph8, A1+env has
L↔D agreement 0.996, TOUGH-M1-dev D cb 0.672 against 0.541 for A1 (old splits), and Δ vs A1 in D-mode of +0.131
[+0.056, +0.185]. <!-- src: reports/definition_robustness.md -->

**What it caps.** Ligand-free sites cap L-mode cb at 0.62–0.66 on TOUGH-M1-dev, while the 4 Å shell reaches 0.80
and size alone reaches 0.766. <!-- src: reports/definition_robustness.md -->

**Consequences.**
- (i) We amended the protocol before any test use (D11). We added C1-D (TOUGH-M1-test in D-mode) to the Holm
family and moved final selection to the D-mode objective (D14).
- (ii) Published L-mode numbers on ligand-defined benchmarks probably include a definition component.
- We measured this only for our own arms. The shipped APoc / G-LoSA / SiteEngine scores use their own pocket
  definitions and cannot be re-run in D-mode here.
- (iii) For deployment on AFDB, where there is no ligand, L-mode accuracy is the wrong selection target.

### 4.4 Size shortcut

Pair ROC-AUC on TOUGH-M1-dev is dominated by size: B0 0.782 and B0m 0.861. A1's pair AUC of 0.779 is below the
pure-size logistic. <!-- src: reports/dev_eval_v2splits.md -->
- On BLiPS-val L, B0 scores 0.646 ROC and 0.535 stratified. <!-- src: reports/dev_eval_v2splits.md -->
- Fragment docking scores track pocket volume (Spearman −0.74 in the 27-pocket feasibility study). <!-- src: reports/fragment_docking_feasibility.md -->
- We therefore report a 2-D size-stratified AUC: 5 mean-log-volume quantiles × 20 |Δ log-volume| quantiles. 5 × 5
strata still left a 0.539 shortcut in simulation; 5 × 20 left 0.507 (D6). The B0m diagnostic (0.5 ± 0.03) passes
on every set. <!-- src: reports/evaluate_module.md, reports/dev_eval_v2splits.md -->

### 4.5 Selection procedure and candidates

**Rule (PREREG §1).**
- Objective: BLiPS-val v2 D-mode cb-AUC.
- One-SE rule: among candidates within one SE of the best, take the simplest. Non-learned is simpler than learned,
then fewer stored dims, then no CSLS.
- Guards: BLiPS-val L cb ≥ B1, and TOUGH-M1-dev D cb ≥ B1.
- Candidates were declared in advance:
- N1 and N2 (non-learned), each raw and with CSLS;
- 12 A4b heads × 2 inputs;
- 6 L4 point-cloud configs (Addendum A1, D16).

**Outcome.**
- The best candidate was L4:egnn_small CSLS at 0.756 (SE 0.040), which sets the threshold at 0.716.
- N1 (0.697) and N2 (0.704) fall below the threshold, so the rule moves to learned candidates.
- 28 learned rows fall within one SE, and all A4b and L4 rows store 384 dims. L4 counts as more complex than A4b.
- Both guards hold for n1_linear: 0.718 ≥ 0.701 and 0.721 ≥ 0.617. <!-- src: results/dev/l4/final_select_all_l4_details.json, results/dev/l4/final_select_all_l4_summary.md -->

The tie-break between A4b heads is disclosed in §8 (D19). Descriptive arms at final evaluation (Addendum A2) are
N1 raw (the non-learned parent) and L4:egnn_small CSLS.

**Candidates in one line each.**
- **N1:** robust, non-learned, best PPIPS among ligand-free arms.
- **N2:** adds the located-pocket A1 view. It is better in L, worse in D.
- **A4b:** the learned projection. Small, uncertain gain over N1; loses PPIPS MRR.
- **L4:** EGNN on ≤ 256 sph8 points with BURROW point features. Best on BLiPS and PPIPS, worse on TOUGH-M1-dev D,
and 47 ms/pocket on CPU. <!-- src: reports/l4_pointnet.md -->

**Earlier provisional numbers that drove decisions (old splits).**
- **A1 vs B1 on BLiPS-val L.** A1's advantage looked significant: +0.087 [+0.033, +0.136]. On the rebuilt splits
it is +0.045 [−0.005, +0.098]. The L-mode A1 > B1 result now rests on TOUGH-M1-dev, which carries the imprint. <!-- src: reports/dev_eval_v2splits.md -->
- **D13.** The hybrid N2 (mean(L,D) 0.691) and the ligand-free N1 were carried forward on the strength of the old
TOUGH-M1-dev definition-robustness screen (36 variants; best Δ +0.024 [−0.039, +0.043]). <!-- src: reports/definition_robustness.md -->

---

## 4b. Test-set results

> **[[TEST RESULTS — filled after final evaluation]]** — `scripts/final_eval.py` (FINAL_EVAL=1, worktree at the
> FREEZE commit), B = 2,000, evaluate.py sha256 f22d0296…; final = A4b:n1_linear raw; B1/B4 with the same CSLS
> treatment as the final method (none).

**Confirmatory (Holm family, one-sided α = 0.05, H0: Δ ≤ 0; SESOI 0.03):**

| claim | set / mode | comparison | final AUC | ref AUC | Δ [95 % CI] | p (one-sided) | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|
| C1a | TOUGH-M1-test, L | final − B1 | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] |
| C1b | TOUGH-M1-test, L | final − B4 | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] |
| C1-D | TOUGH-M1-test, D (common set) | final − B1 | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] |
| C2 | ProSPECCTs D5.2+D6.2+D7, L, no self-pairs | macro final − B1 | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] |

Realised test units and MDE: [[ ]]. D-mode miss rates and worst-case bound for C1-D: [[ ]].

**Reported (not in the Holm family):**

| item | final | N1 (descr.) | L4 (descr.) | B1 | B4 | B0 / B0m | other |
|---|---|---|---|---|---|---|---|
| TOUGH-M1-test: AP, cb-AUC, size-strat. AUC, pAUC (L; D) | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | B0′, B5, B5-T APoc/G-LoSA/SiteEngine [[ ]] |
| TOUGH-M1 full minus dev (non-learned only, L) | — | [[ ]] | — | [[ ]] | — | [[ ]] | published context: §2 |
| ProSPECCTs all 10 subsets (± self-pairs; L; D on BURROW-clean) | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | LITERATURE §3.1 |
| Vertex (L) | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | |
| BLiPS-test L / D (seen vs unseen chemotype; no promiscuous) | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | |
| PPIPS-test P-ortho top-1/top-3/MRR; P-sym (by BURROW-homology flag) | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | [[ ]] | |
| PPI-L test (exploratory, 3 positive pairs) | [[ ]] | | | [[ ]] | | | |
| Blind deployment (BLiPS-test AF models) | [[ ]] | | | [[ ]] | | [[ ]] | detection recall [[ ]] |

---

## 5. Negative and null results

**A2, fragment-docking profiles: gate failed (D10).**
- *Protocol:* ADock with stock Vina weights, a fixed 12 Å box, and 128 NCI fragment-like molecules plus 128
lead-like molecules on every TOUGH-M1 pocket (7,524 L + 6,068 D, 0 failures). Seed reproducibility r was 0.988
for fragments and 0.972 for lead-like. <!-- src: reports/a2_docking.md -->
- *Pre-registered gate:* the A1 + A2 fragment fusion must add ≥ 0.01 size-stratified AUC to A1 with lower CI > 0.
- Result: −0.0097 <!-- src: results/dev/tough_m1_dev_details.json#gate.A1+A2frag|raw.delta_strat_vs_cf_A1.estimate --> [−0.027, +0.007] on the old splits, and −0.009 [−0.066, +0.023] on the rebuilt splits.
- Every variant was ≤ +0.002: lead-like, both panels, CSLS inputs, and fusion with B1 or B4. <!-- src: reports/dev_eval_v2splits.md -->
- *Standalone:* the fragment-IFP block with CSLS (ROC 0.621) is on par with B1 but adds nothing to A1. Published
TOUGH-M1 context: a Vina docking profile scored 0.55 and rDock 0.67. <!-- src: reports/dev_eval_v2splits.md, LITERATURE.md §3.2 -->
- *Why:*
- docking scores are dominated by pocket size and hydrophobicity; pocket means explain 57 % of the score-matrix
  variance <!-- src: reports/fragment_docking_feasibility.md -->;
- per-molecule residualisation on log volume did not remove the size axis. <!-- src: reports/a2_docking.md -->
- *Cost:* 0.30 GPU-s per pocket for both panels, about 13 pockets/s per 4-GPU node. That is two to three orders of
magnitude above the tier-1 descriptor. <!-- src: reports/a2_docking.md -->

**PPI fragment sub-hypothesis: not supported.** The pre-registered prediction was that fragments beat lead-like
molecules on shallow interface pockets (PPIPS P-ortho MRR).
- First run, old splits, 95 queries, 13 units: Δ MRR rank −0.004, LE-resid +0.045, IFP +0.074, Holm p 0.50 / 0.28 / 0.25.
- Rebuilt splits, 217 queries: Δ −0.063 / −0.005 / −0.042, Holm p = 1.
- Shallowest tertile, IFP: +0.133 [−0.065, +0.317] (old) → −0.024 [−0.116, +0.163] (new). <!-- src: reports/dev_eval_blips_ppips.md, reports/dev_eval_v2splits.md -->

The early positive trend was noise. There was one label-free observation in the predicted direction: lead-like
LE drops on interface pockets while fragment LE does not. It did not turn into retrieval signal. <!-- src: reports/a2_docking.md -->

**CSLS hub correction is negligible for accuracy.**
- The only CI-excluding effect is on A2-IFP: +0.044 [+0.017, +0.069] on TOUGH-M1-dev.
- A1 and B1 change by |Δ| ≤ 0.02, not significant. B4 gets worse (−0.022 TOUGH-M1, −0.036 BLiPS D). <!-- src: reports/dev_eval_v2splits.md -->
- At proteome scale, CSLS with database-local radii does reduce hubness: top-10 in-degree skewness falls from
1.82 <!-- src: results/proteome/index_search.json#hubness.raw.skewness --> to 0.62. <!-- src: results/proteome/index_search.json#hubness.csls_db.skewness -->
It is kept as an option for search, not for scoring.

**A1 configuration choice is unstable.**
- 12–14 of the 17 A1 configs fall within one SE of the best; their objective means span 0.656–0.673.
- The fewest-dims tie-break therefore flipped between splits: pair_only (old) → untyped (37 d), and under the old
TOUGH-only rule → usr_only. <!-- src: reports/dev_eval_v2splits.md -->

The grid cannot buy definition robustness: every config except hist_only sits at 0.51–0.58 cb in D-mode. <!-- src: reports/dev_eval_blips_ppips.md -->
This is why development moved to site shaping (D11) rather than descriptor tuning.

**B5 EPoCS ≈ B4.** The external ESM-2 3B pocket method, installed and run locally, scored 0.599 against B4's 0.601
(old splits) and 0.568 against 0.595 (rebuilt). It took ~38 GPU-min plus environment work and added no
information over B4 (LESSONS 9). <!-- src: reports/baselines_b4_b5.md, reports/dev_eval_v2splits.md -->

**PPI-L infeasible** as a confirmatory test (§2). The proposed alternative, PPI-R (modulator pockets retrieving
other families' modulator pockets against size- and buriedness-matched ligand-bound decoys), was designed but not
built. <!-- src: reports/ppi_datasets.md -->

**Other dead ends (definition-robustness screen, old splits).** <!-- src: reports/definition_robustness.md -->
- Residue-shell sites: mean 0.619 and 3× slower.
- sph10: dilutes the site (A1 cb-D 0.606).
- core8: keeps the imprint (D 0.566).
- Up-weighting env or adding B1 to A1+env: Δ ≤ 0.003.
- Probe-atom energy maps and rigid GPU scans as docking surrogates: poor signal. <!-- src: reports/fragment_docking_feasibility.md -->

**Learned heads do not help PPI transfer.** Every A4b head lowers PPIPS P-ortho MRR relative to N1: 0.62–0.76
against 0.79. P-ortho at < 30 % identity strongly favours sequence context (B4 MRR 0.986). <!-- src: results/dev/l4/final_select_all_l4_summary.md -->

---

## 6. Runtime and scale

**Per-pocket and per-pair cost** (1 CPU thread unless stated; BURROW excluded unless stated):

| step | cost | source |
|---|---|---|
| BURROW featurisation, reference path (TOUGH-M1 crystal structures) | median 0.42 s/structure (featurise 0.28 s), 32 workers → 66 structures/s | reports/pocket_adapter.md |
| BURROW, fast GPU backend (human AF models) | 77 CPU-ms + 4.8 GPU-ms per structure | reports/proteome_demo.md |
| BURROW on AF dimers | 322 ms/dimer single-core; 40 dimers/s on 16 CPUs | reports/ppi_dimers.md |
| final descriptor + embedding, D pocket | median 3.5 ms (p90 4.6 ms); head forward 64 µs | results/dev/final_method_runtime.json (n1_base) |
| final descriptor + embedding, L site | median 6.1 ms (p90 10.5 ms) | same |
| pair score | 0.10 µs batched vs 1 M vectors; 2.8 µs single call | same |
| storage | 1,536 B/pocket (384 × float32) | same |
| L4 alternative | 0.54 ms GPU / 47 ms CPU per pocket (+4.3–5.3 ms point extraction) | reports/l4_pointnet.md |
| B4 ESM-2 650M | 0.06 s/pocket (GPU) | reports/baselines_b4_b5.md |
| B5 EPoCS (ESM-2 3B) | ~0.3 s/pocket (GPU) | reports/baselines_b4_b5.md |
| A2 docking, 2 × 128 molecules | 0.30 GPU-s/pocket | reports/a2_docking.md |

The runtime file was measured for A4b:n1_base. n1_linear shares the same input pipeline and has a smaller head, so
its cost is at most that. [[re-bench n1_linear with scripts/bench_method.py before the final report]].

C4 targets (reported, not confirmatory):
- ≤ 1 s/pocket including BURROW: met.
- ≤ 10 µs/pair: met.
- ≤ 512 B/pocket: **not met** with float32 (1,536 B). It requires PQ.

**Human-proteome demo** (AFDB v6, 23,586 models, read from the tarball; ligand-free **N1 raw** 627-d vectors, not
the final head). <!-- src: reports/proteome_demo.md -->
- *Throughput:* 116,246 pockets in 19,084 proteins in 177.6 s on 2 × RTX 4090 + 22 CPU workers: 132.8 structures/s,
716 <!-- src: results/proteome/summary.json#runs.run_gpu.pockets_per_s --> pockets/s.
- The run is CPU-bound (BURROW 54 % of CPU time, descriptors 24 % at 6.4 ms/pocket, I/O 23 %).
- The fast CPU and reference backends give byte-identical outputs at 69.9 and 34.7 structures/s.
- *Pockets:* 5.39 kept per model; 7.8 % of models have none.
- *Exact search:* FAISS GpuIndexFlatIP all-vs-all top-50 in 0.51 s (2.7 × 10¹⁰ pairs/s). A single query takes
0.58 ms on GPU and 13.1 ms on one CPU thread.
- *Compressed index:* OPQ64 + IVF1024 + PQ64 (64-byte codes) gives recall@10 0.81 <!-- src: results/proteome/index_search.json#ivfpq.OPQ64_640,IVF1024,PQ64.sweep.16.recall_at_10 -->
at nprobe 16 and 0.85 at nprobe 64. Re-ranking the PQ top-100 exactly gives 0.995 <!-- src: results/proteome/index_search.json#ivfpq.OPQ64_640,IVF1024,PQ64.sweep.64.recall_at_10_rerank_top100 -->
at < 1 ms/query. Codes alone lose too much; PQ shortlist + fp16 re-rank is the recommended deployment.
- *Sanity checks:*
- rotation + translation self-retrieval: 100 % rank 1 <!-- src: results/proteome/sanity_jitter.json#per_condition.rot|fixed_centre.rank1 -->;
- 1 Å RMS atom noise: 83 % rank 1 with a fixed site centre, 53 % when BURROW re-detects;
- 196 kinase-site queries: 75 % kinase pockets in the top-10 outside the query's own protein, against 4.6 %
  expected. Kinases are homologous, so this checks the index, not fold independence.
- *Extrapolation to 200 M structures (not run):*
- ≈ 0.95 × 10⁹ pockets;
- ≈ 7,150 CPU-core-h + 223 <!-- src: results/proteome/summary.json#extrapolation_200M.gpu_hours --> GPU-h to build, ~4 h on 100 such nodes;
- storage: OPQ-IVF-PQ64 index 0.11 TB, raw float32 2.4 TB, fp16 1.2 TB.
- ANN latency at 10⁹ vectors was not measured; it needs nlist ≈ 2¹⁶–2²⁰ and an HNSW coarse quantiser.
- Exact all-vs-all would take ≈ 9,400 GPU-h.
- For the final 384-d vectors, raw storage scales by 384/627. PQ recall has not been re-measured.

---

## 7. Robustness

**AlphaFold model vs holo structure (C5, dev).** <!-- src: reports/af_robustness_dev.md -->

Set-up: 239 BLiPS-val sites with both a holo and an AF-model pocket, plus 1,068 BLiPS-train sites for power. The
"final" arm here is **N1 raw**, the configured method when this ran, not A4b:n1_linear.

*Ligand-sharing AUC, holo/holo vs holo/AF (Δ = HH − HA):*

| set, mode | Δ [95 % CI] |
|---|---|
| val L | −0.005 [−0.054, +0.041] |
| val D | +0.003 [−0.077, +0.086] |
| train L | −0.008 [−0.019, +0.003] |
| train D | −0.012 [−0.034, +0.010] |

- Every |Δ| ≤ 0.012.
- Same-site holo → AF retrieval:
- L top-1 0.78 (B1 0.88). B1's site-specific features win when both sides use the same ligand location.
- D top-1 0.55 (B1 0.41).
- Strata:
- At AF site pLDDT 70–90, retrieval top-1 drops by about 0.17; the pair-task Δ does not.
- Holo structures released after 2018-05-01 show no leakage signature.
- Caveat: both sides use the same transferred ligand location, so L retrieval is optimistic.

[[C5 test: BLiPS-test holo vs AF Δ AUC with CI (final, N1, B1), strata by release date and pLDDT band]].

**Blind deployment dry run (BLiPS-val AF models, no ligand anywhere; N1 as "final").** <!-- src: reports/blind_and_ppil.md -->

Set-up: 157 models, 817 detected pockets.

- Detection recall is 0.615 [0.551, 0.683]. Only 45 % of directed positive pairs have both ends detected.
- Partner retrieval when both ends are detected (84 directed pairs, ~810 candidates each):

| arm | hit@10 | MRR | AUC |
|---|---|---|---|
| final (N1) | 0.155 | 0.071 | 0.634 |
| B1 | 0.107 | 0.053 | 0.647 |
| B0 (size) | 0.036 | — | 0.439 |
| final − B1 (AUC) | | | −0.013 [−0.12, +0.08] |

Detection recall is the main ceiling for blind use, and pair-level signal at this sample size cannot separate the
method from B1. [[blind test on BLiPS-test]].

**Invariance and determinism.** Rigid-motion error is ≤ 1.3e-7 for A1 and < 1e-4 for L4. API vectors are
bit-identical across calls. The three BURROW backends give byte-identical outputs on 127,200 pockets. <!-- src: reports/a1_descriptors.md, reports/l4_pointnet.md, reports/proteome_demo.md -->

---

## 8. Process and integrity

**Sealing (D2).**
- All benchmark pair and label tables were moved to `data/sealed/` (chmod 000, sha256 in
`data/sealed_SHA256SUMS.txt`) at 19:12, before any method existed.
- Final evaluation runs only through `scripts/final_eval.py`. It requires FINAL_EVAL=1, a committed FREEZE.json
and a clean worktree at the frozen commit. It re-hashes evaluate.py, PREREG, config and weights, and logs every
unseal. <!-- src: reports/final_eval_infra.md -->
- The split builder (`make_tough_m1_split.py`) read the sealed TOUGH-M1 file to derive partitions and printed counts
only. This happened in both the original and the rebuild runs. <!-- src: data/splits/SPLITS.md -->

**Deviations.**
- **DEV1.** A statistics reviewer read the TOUGH-M1 pair table 2 min before sealing. They computed label-graph
structure and a size-only B0 ROC-AUC (0.577) on *all* pairs, including the future test partition. No method was
fitted or tuned, and the B0 test number is known in advance. <!-- src: RESEARCH_TREE.md DEV1 -->
- **DEV2.** After the rebuild, the largest BLiPS within-dataset component is 10.6 % against the 10 % gate. We did not
re-split, because that would redraw splits again. This is mitigated by cluster-balanced metrics and the
homology-group bootstrap. <!-- src: RESEARCH_TREE.md D18, data/splits/SPLITS.md -->
- **Shipped-score orientations.** Before the shipped APoc/G-LoSA/SiteEngine score orientations were fixed, the eval
agent computed their label AUCs in an exploratory check. Orientations then came from documentation, and all
SiteEngine columns are reported as shipped. <!-- src: reports/dev_eval_tough_m1.md -->

**Audit failure and rebuild (D15, D18).**
- *What the audit found.* The independent split audit used its own extraction, all-vs-all MMseqs2 and exhaustive
Foldseek. It **failed**: the graph builder ran `mmseqs search` without `-a`, which underestimates identity near
30 %, and Foldseek was non-exhaustive. The resulting leaks were:
- 16 TOUGH-M1-test pockets with BURROW homologues;
- 7 dev pockets touching sealed sets;
- 3 dev ↔ test links;
- 19 BLiPS-train proteins touching sealed sets;
- 9 BLiPS train ↔ val links;
- 1 PPIPS complex. <!-- src: reports/audit_splits.md -->
- *The fix.* The audit ran before any model fit, so the gate worked as designed. The graph was rebuilt (exact
identities, exhaustive Foldseek with exact TM near the threshold) and all splits re-derived with unchanged rules.
- 254 TOUGH-M1 pockets moved.
- BLiPS-test sites were unchanged.
- BLiPS v2 train/val (972 sites) and PPIPS (681 complexes) were redrawn, because their rules permute components.
- `verify_splits.py` passes 101/101 checks. <!-- src: data/splits/SPLITS.md -->
- *Re-audit:* **PASS**, with 0 rule hits. One sequence pair and four structural pairs sit at the threshold, with
exact TM 0.41–0.497. <!-- src: reports/audit_splits.md -->
- *Dev re-run.* All dev tables were re-run on the new splits. Conclusions were unchanged, except that A1 − B1 on
BLiPS-val L lost significance and the A1 config choice proved unstable (§4.5, §5). <!-- src: reports/dev_eval_v2splits.md -->
- *Known residual (disclosed).* Most PPIPS val/test complexes have a BURROW-train homologue (val 125/257, test
136/251 by representative-chain edge), and BURROW prepares their pockets. PPIPS-test is reported stratified by
this flag. <!-- src: data/splits/SPLITS.md -->

**Pre-registration.**
- DESIGN v2 was frozen after two review rounds: six round-1 reviewers and a combined round-2 panel.
- PREREG.md consolidated all amendments at 22:45, before any model fit (D14).
- Addendum A1 (L4 candidate, D16) was added before any fit.
- Addendum A2 (final method; N1 and L4 as descriptive arms, D20) was added before any test use.
- All amendments that touch claims came before test use. C1-D was added because of a dev finding (D11); it makes
the claim family harder, not easier.
- evaluate.py was frozen at sha256 f22d0296… (41 tests), and its hash is in every result sidecar. <!-- src: PREREG.md, reports/evaluate_module.md -->

**The D19 tie-break, stated plainly.**
- *What the agent did.* The A4b agent applied PREREG's "simplest" rule. Every A4b head stores 384 dims, so the
declared criteria (non-learned < learned, fewer dims, no CSLS) did not separate them, and the agent fell back to
"grid order" (not a declared criterion), which picked n1_base (0.717).
- *What the PI did.* The PI replaced that fallback with "fewest parameters", reading "simplest" as model size. This
picks n1_linear (0.737). <!-- src: RESEARCH_TREE.md D19, reports/a4b_selection.md -->
- *Why this is not a blind choice.* The PI made the decision **after** seeing the candidate table, in which
n1_linear scored higher than n1_base on every dev column except PPIPS. The criterion is defensible: a linear map
is simpler than an MLP, and both candidates are within one SE. Even so, the choice between two near-equivalent
heads was made with their dev scores visible.
- *Expected effect.* Within-one-SE differences (0.02) are small next to the test MDE, so the effect on the test
claims should be minor. L4 (D20) did not change the choice.

**Independent verification so far.**
- the split audit and re-audit (separate code path);
- `verify_splits.py` (an independent re-implementation of the split rules);
- the final-eval dry run, which re-derived the dev tables from scratch with a max deviation of 5.6e-16 and ran
claim dry runs on dev (none Holm-significant) <!-- src: reports/final_eval_infra.md -->;
- unit tests for metrics, pockets, descriptors, method API, L4 and final eval.

[[Independent re-derivation of every test headline by an agent that did not produce it: who, what, result]].

---

## 9. Limitations

1. **Power.** The TOUGH-M1 test has 133 units, and one of them holds 787 of 1,045 pockets. The C1 MDE is ≈ 0.12–0.13,
 so a null C1 result is not evidence of no effect. Dev differences between top candidates are smaller than one
 SE, and most paired CIs against B1 include 0.
2. **Selection optimism.** The selection threshold came from a maximum over ~40 rows on a 462-positive validation
 set. The chosen head was the higher-scoring of two tied heads (D19).
3. **Learning is not shown to help.** The head over N1 adds +0.02 to +0.04 with CIs including 0 (n1_base), and it
 lowers PPIPS MRR.
4. **Not literature-comparable.** 76–77 % of TOUGH-M1 is excluded, and our pocket definitions are BURROW grid points.
 Published AUCs (§2) are context only.
5. **Labels are ligand sharing.** Ligand sharing is not pocket similarity. Promiscuous ligands and cofactors
 dominate some clusters, and unseen-chemotype subsets are tiny (BLiPS-val 21 positives). <!-- src: data/splits/SPLITS.md -->
6. **D-mode is oracle-assisted, and detection is the bottleneck.**
 - The ligand picks which pocket counts as the site.
 - Coverage misses run to 38–46 % of BLiPS pairs. <!-- src: reports/dev_eval_v2splits.md -->
 - Blind detection recall is 0.615.
 - The API locates D sites over all region pockets, while evaluation used the best member of the matched merged
   pocket. <!-- src: reports/final_eval_infra.md -->
7. **PPI.**
 - PPI-L failed its gate.
 - PPIPS P-ortho measures interolog transfer, where sequence wins, and its val/test complexes are mostly
   BURROW-homologous.
 - We have no ligand-grounded, fold-independent PPI test.
8. **AF robustness and blind numbers are for N1, not the final head.** The proteome demo also used N1, with z-scores
 from holo PDB pockets.
9. **Storage.** The 384-d float32 vector is 1.5 kB. 64-byte PQ codes alone give recall@10 ≤ 0.85.
10. **Inherited data issues.**
  - Stock Vina weights were fit on PDBbind-era data.
  - ESM-2 (B4) was pretrained on UniRef, which contains test sequences.
  - Transferred BLiPS-test ligands clash (< 2 Å) in 29 % of holo and 55 % of AF sites. <!-- src: reports/blips_ppips_prep.md -->
  - 128 BLiPS train/val sites were left out because they are not cached.

---

## 10. Follow-ups and remaining ideas

**Concrete follow-ups (in priority order).**
1. **Deployment locator.** Replace merged-pocket centring with the set-max over BURROW sub-pockets. This recovered
 the oracle locator to within −0.009 D on dev. <!-- src: reports/definition_robustness.md --> Measure blind recall
 on AFDB, and work with the pocket_detect team on recall for BLiPS-type sites.
2. **Re-measure the final vectors at scale.** Bench n1_linear runtime, then measure OPQ/IVF-PQ recall on the 384-d
 head vectors on the human proteome, with fp16 re-rank. Test an HNSW coarse quantiser at 10⁸–10⁹ vectors.
3. **Build PPI-R** (§5). It is the only ligand-grounded PPI test that the pocketome supports.
4. **Larger, cleaner training for L4/A4b.** Train on PDB-wide BioLiP sites under the same leakage rules, including
 the 128 uncached sites. L4 was best in-distribution and on PPIPS; the open question is whether more data fixes
 its TOUGH-M1-dev D transfer.
5. **A5 fusion (never run).** Try N1/A4b + L4, and a homology-aware search mode that fuses B4 for users who want
 ortholog transfer (B4 PPIPS MRR 0.986). Report it separately from the fold-independent claim.
6. **Power.** Pre-register a second unit definition (homology groups, MDE ≈ 0.065 on the old split <!-- src: reports/dev_eval_tough_m1.md -->)
 and a looser cross-dataset exclusion (TM ≥ 0.7 doubles test) for a future, separately sealed TOUGH-M1 evaluation.
7. **Disseminate the ligand-imprint check.** Re-score published methods (DeeplyTough, PocketVec, ProFSA) in
 ligand-defined vs detected definitions on the same pairs, and add L↔D agreement as a standard label-free pre-check.
8. **pLDDT-aware scoring.** Down-weight low-pLDDT lining. Retrieval loses ~0.17 top-1 at pLDDT 70–90.

**Remaining ideas, not pursued for lack of time or evidence.**
- A3 pseudocentre alignment as a tier-2 re-ranker on the FAISS top-k.
- A2 docking as a tier-2 re-ranker on small shortlists only. The gate failure was about tier-1 fusion; re-ranking
was not tested.
- Graded ligand-similarity losses with more chemotype diversity.
- PPIPS positives by overlap coefficient (8,905 instead of 1,412) to strengthen PPI training. <!-- src: reports/ppi_datasets.md -->
- Hubness-aware CSLS radii computed per database shard.

