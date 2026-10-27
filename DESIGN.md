# DESIGN — fast, fold-independent pocket similarity on BURROW (draft v0, 2026-10-27 19:15)

Status: DRAFT for review round 1. Inputs: PROMPT.md, LITERATURE.md, reports/{data_benchmarks,
fragment_docking_feasibility,ppi_dimers}.md, pocket_detect/FOR_FURTHER_DEVELOPMENT.md.

## 0. Goal and claims

Build **a versatile, fast tool that scores the similarity of two binding pockets independent of sequence and
fold**, built on BURROW pockets, usable at AFDB scale (≈200 M structures × ~5–15 pockets), on PDB and AlphaFold
models, and on pockets created by protein–protein interfaces (PPIs).

Deliverables:
1. `pocketcompare` package: pocket → descriptor(s); (pocket, pocket) → similarity; batch/ANN search CLI.
2. An evaluation on public benchmarks (zero-shot) and on our own leakage-controlled benchmarks (including a new
   PPI-pocket benchmark), with runtime reported next to every accuracy number.
3. REPORT.md with test results, limitations, follow-ups.

Pre-registered primary claim (C1): our final method's ROC-AUC on the **TOUGH-M1 test partition** (§2.2) exceeds
our pre-specified internal baseline B1 (BURROW size-free descriptor cosine, §3) by ≥ 0.03, paired cluster
bootstrap, one-sided α = 0.05. Secondary claims (Holm-corrected together): C2 ProSPECCTs D5+D5.2+D6+D6.2+D7
macro-AUC > B1; C3 PPI-test AUC > B1; C4 runtime: descriptor ≤ 1 s/pocket and comparison ≤ 10 µs/pair on CPU
for the tier-1 descriptor. Published numbers (zero-shot classical TOUGH-M1 0.64–0.69, ProFSA zero-shot 0.82)
are context, not paired comparisons (different pocket definitions).

## 1. Architecture (two tiers; tiers are hypotheses to be tested, not commitments)

- **Tier 1 (index tier):** fixed-length vector per pocket, cosine/learned metric, FAISS-indexable;
  goal ≤ 1 s/pocket including BURROW, µs/pair. Must cover all of AFDB.
- **Tier 2 (re-rank tier):** richer, slower comparison applied to the top-k of tier 1 (alignment of typed point
  clouds and/or docking profiles). Budget ≤ ~0.1 s/pair or ≤ 30 s/pocket precomputation.
- Final score = tier-1 score, or a calibrated fusion of tier-1 and tier-2 where tier 2 is available.

## 2. Data and splits (fixed before any modelling)

All splits are written to `data/splits/` with sha256 recorded in DATA.md and committed before any model is fit.
Held-out sets are only read by `scripts/final_eval.py`, which refuses to run unless `FINAL_EVAL=1` and the
method config is frozen (hash recorded in RESEARCH_TREE.md).

### 2.1 Pocket definitions (an explicit adapter, used identically for all methods we run)
- **L-mode (ligand-defined):** BURROW grid points (default preset, full protein, all ligands/waters stripped) within
  4 Å of any ligand heavy atom given by the benchmark, plus their 4 Å lining residues. Where a benchmark only
  gives residues, points ≤ 4 Å of those residues' atoms that are also buried (bur10 ≥ 0.5) — documented per set.
- **D-mode (detected):** BURROW `--output-rule region` pockets on the ligand-free structure; touching
  sub-pockets merged (point sets within 1.5 Å, or residue Jaccard ≥ 0.3); the benchmark site is represented by
  the detected pocket with the highest point-coverage of the L-mode pocket (coverage ≥ 0.3, else "missed" →
  pair scored with the minimum similarity, counted, never dropped).
- L-mode is the comparability mode; D-mode is the deployment mode and is reported for every headline number.

### 2.2 Public benchmarks (zero-shot external tests)
| set | role | split |
|---|---|---|
| TOUGH-M1 (7,524 pockets; 505k/557k pairs) | primary | split by **protein clusters** (MMseqs2 30 % id, cov 0.8, then merged with Foldseek TM ≥ 0.5 components) into **dev 30 % / test 70 %** (seed SEEDS[0]); only within-partition pairs used; cross-partition pairs discarded |
| ProSPECCTs D1–D7 (10 subsets) | secondary, **sealed test** | none: never read before final eval (except a 5-pocket parser smoke test on D1 structure files, no labels) |
| Vertex (6,218 pockets) | secondary, **sealed test** | none |
| Kahraman / Barelier | inside ProSPECCTs D5/D6 | sealed |

Self-pairs in ProSPECCTs are kept as in the original protocol and additionally reported without them.

### 2.3 Own benchmark BLiPS (BioLiP2 ligand-sharing pocket pairs) — train / val / test
Source: BURROW's leakage-controlled LIGYSIS-style sites (pocket_detect `data/processed/{train,dev}`, 6,475 + 579
chains, sites with CCD codes) and BioLiP2 2025-11-12 for additional chains if needed.
- Pocket = LIGYSIS site (pooled ligands); ligand identity = set of CCD codes at the site.
- Exclusions: ions/metals-only sites, common additives/crystallisation agents (curated list committed as data),
  sites with < 10 BURROW points.
- **Positive pair:** two sites in proteins of different 30 % clusters **and** different Foldseek fold clusters
  (TM < 0.5) that share a ligand of ECFP4 Tanimoto ≥ 0.7 (main) — sensitivity at identical CCD only.
- **Negative pair:** different-fold sites whose ligands have max Tanimoto < 0.3, **size-matched to the positives**
  (pocket-volume ratio distribution matched by stratified sampling) — so volume alone cannot solve the set.
  A second, unmatched negative set is reported as well.
- Ligand-class balance: cap pairs per ligand chemotype (Bemis–Murcko scaffold cluster) so ATP/NAD/haem do not
  dominate; report per-class AUC.
- **Split:** protein clusters (30 % id + Foldseek TM ≥ 0.5 merge) → train 70 / val 15 / test 15 (seed
  SEEDS[0]); a pair belongs to a split only if both proteins do.
- **Leakage removal:** any BLiPS-train/val protein with ≥ 30 % identity (MMseqs2, E ≤ 1e-3, cov ≥ 0.5) or Foldseek
  TM ≥ 0.5 to any protein of the test partitions (TOUGH-M1-test, ProSPECCTs, Vertex, BLiPS-test, PPI-test) is
  removed from train/val.

### 2.4 PPI benchmark (PPIPS) from the AFDB dimers (new; train / val / test)
15,161 AFDB complexes (human/yeast/E. coli; homo + hetero), pLDDT in B-factor. Interface pocket = BURROW
cavity pocket (≥ 10 points) with minority-chain residue share f_min ≥ 0.25.
- **Positives (graded tasks):**
  - P-sym (sanity, easy): the two symmetry copies of a single-chain pocket in a homodimer (~15.9k pairs) and the
    same interface pocket in two models of the same complex if available. Reported but not a headline.
  - P-ortho (headline): the same interface pocket in **cross-species interologs** (human/yeast/E. coli complex
    pairs from MMseqs2 orthology; 4,039 at < 30 % pair identity). Correspondence by structural alignment of the
    complex (US-align/Foldseek multimer) → residue mapping → pocket overlap ≥ 0.5. Positive only if interface
    pockets correspond; restrict the headline to pairs at < 30 % sequence identity per chain.
  - P-lig (if feasible): PDB complexes with small-molecule PPI inhibitors (iPPI-DB / 2P2I / TIMBAL) vs AFDB
    interface pockets of the same target pair — reported as an exploratory retrieval test.
- **Negatives:** interface pockets from unrelated complexes (no shared Pfam/orthogroup, Foldseek TM < 0.5),
  size-matched to positives.
- Split by **complex orthogroup cluster** (all members of an interolog family stay together) into train/val/test
  70/15/15 before modelling.

### 2.5 Robustness sets
- AF vs holo vs apo: same site in a PDB holo structure and its AFDB model (and apo PDB where available). Built for
  BLiPS-test proteins and TOUGH-M1-test proteins (AF models via the local AFDB or the AFDB API); metric = rank of
  the true partner among all pockets of the other structure + ΔAUC (holo/holo vs holo/AF).
- Pocket-definition sensitivity: L-mode vs D-mode vs perturbed L-mode (3 Å / 5 Å cut-offs).

### 2.6 Leakage of models used to prepare pockets
- BURROW's point and pocket models were trained on BioLiP2 chains leakage-filtered against BURROW's own test
  union, **not** against TOUGH-M1/ProSPECCTs/Vertex. Therefore: tier-1 descriptors use only BURROW's
  **analytic** point features by default (buriedness, depth, first-hit chemistry, composition); the learned
  `point_score` is an ablation arm only. D-mode uses BURROW detection (learned) — we report D-mode results
  stratified by homology of the test protein to BURROW's training set (MMseqs2 30 %).
- ADock: use the **stock Vina** scoring function (not the 18-weight fitted variant, which was fit on PDBbind-like
  data) for all docking descriptors.

## 3. Methods (arms). Each arm is scored on TOUGH-M1-dev, BLiPS-val and PPIPS-val.

**Baselines (must-beat):**
- B0 size only: −|log vol_a − log vol_b|. B0' sequence identity (MMseqs2) and global TM-score (Foldseek/US-align).
- B1 BURROW size-free descriptor (fractions/means of the 76 descriptors), z-scored with dev statistics, cosine.
- B2 APoc (bioconda) if installable in ≤ 1 h; else quote published numbers.
- B3 published numbers (LITERATURE.md §3) — context only.

**A1 — Typed point-cloud fingerprint (tier-1 candidate, alignment-free).** Assign each pocket point a
pharmacophore/environment type from BURROW's analytic features (e.g. apolar, aromatic, donor-, acceptor-,
positive-, negative-lined, metal; plus buriedness bin). Fingerprint = concatenation of (i) type × buriedness
histograms, (ii) pairwise-distance histograms for each type pair (2-point "shape–pharmacophore" distributions,
FuzCav/PocketMatch-like, but on volume points), (iii) a few global shape moments. Normalise by point count
(size-free); compare by cosine and by a per-block weighted cosine.

**A2 — Docking-profile fingerprint (tier-2 candidate; human prior).** ADock `frag_lite_np`, stock Vina, rigid
receptor, box from pocket points + 4 Å.
- Panels (pre-registered head-to-head at matched size N = 64 and 128): **fragments** (MW 100–250, diverse) vs
  **lead-like** (MW 200–450). Sources and licences recorded in DATA.md.
- Descriptor variants: (a) PocketVec-style per-pocket rank vector with non-binder bins, cosine; (b) per-fragment
  score z-scored against a reference pocket background (removes the per-fragment mean) and then per-pocket
  centred (removes the size component), cosine; (c) **pose interaction profile** (novel): for each fragment's
  best pose, counts of contact types (H-bond donor/acceptor matched, apolar, aromatic, charged) and buried
  fraction → per-fragment-per-type matrix, flattened.
- Go/no-go gate: on TOUGH-M1-dev (≤ 2,000 pockets), A2 must reach ROC-AUC ≥ B0 + 0.05 and add ≥ 0.01 to A1 in a
  val-fitted fusion; otherwise A2 is reported as negative and not developed further.

**A3 — Alignment-based typed point-cloud comparison (tier-2 candidate).** Superpose two pockets by maximising
the overlap of type-matched Gaussian point densities (shape+colour à la ROCS, on BURROW points), initialised from
principal axes (8 sign flips) + a few random rotations, refined by gradient/ICP on GPU in batch. Score = colour +
shape Tanimoto. Target ≤ 1 ms/pair on GPU batch.

**A4 — Learned pocket embedding (tier-1 candidate).** Small equivariant/point network (e.g. EGNN or PointNet++
on ≤ 512 pocket points with analytic features) trained contrastively on BLiPS-train positives/negatives +
PPIPS-train, with augmentations that mimic deployment noise (D-mode vs L-mode definitions, AF vs holo where
available, point subsampling, rotations). Variant A4b: a learned metric (MLP projection) on top of the A1 vector
(cheaper, less overfitting risk). Selection on BLiPS-val/PPIPS-val/TOUGH-M1-dev only. 5 seeds (SEEDS).

**A5 — Fusion.** Logistic regression (or rank-average) over arm scores fitted on val only.

PPI specifics: all arms run unchanged on interface pockets; we additionally test (i) adding a "chain-origin"
channel (points lined by one vs two chains) and (ii) fragments vs lead-like specifically on PPIPS, where the
fragment prior is most plausible.

## 4. Evaluation

- Metrics per benchmark: ROC-AUC (field standard) **and** PR-AUC (average precision); for retrieval tasks
  (PPIPS, robustness) also per-query top-1 / top-10 hit rate and MAP.
- Uncertainty: 95 % CIs by **cluster bootstrap** over protein clusters (1,000 resamples, seed SEEDS[0]); paired
  bootstrap for differences between methods on the same pairs.
- Missing-pocket policy: if a method fails on a pocket (parse failure, no points, docking failure, D-mode miss),
  all its pairs get the method's minimum similarity; failure counts reported per set; never silently dropped.
- Confounder controls on every headline: B0 (size), B0' (sequence/fold), and **per-subset size-matched AUC**.
  Decompose gains by ligand class (nucleotide / cofactor / haem / sugar / other) and by metal vs non-metal sites.
- Runtime: per-pocket descriptor time (BURROW + descriptor), per-pair comparison time (CPU single thread; GPU
  batch), all on this node (64 CPU, 4× RTX 4090), warm, median of ≥ 3 runs; AFDB-scale extrapolation including
  storage per pocket (bytes) and ANN search cost.

## 5. Verification and controls (written before results)
- Toy tests with known answers: identical pocket → similarity 1 (or max); rigid rotation/translation invariance;
  point-order invariance; a pocket vs a randomly typed copy (permuted types) scores lower; a size-scaled pocket
  is not rewarded by size-free descriptors.
- Positive controls: ProSPECCTs-like identical-structure pairs inside the dev partition (same protein, two PDB
  entries) must score high; homodimer P-sym must score high.
- Negative controls: shuffled labels give AUC ≈ 0.5; random-vector descriptor ≈ 0.5; B0 size-only reported.
- Every result that enters REPORT.md is re-derived by an agent that did not produce it (verification report in
  `reviews/`).

## 6. Compute and storage budget
- BURROW default ≈ 0.1 s/structure-core; full TOUGH-M1 + BLiPS + PPIPS ≈ 30k structures ≈ minutes on 32 workers.
- ADock fragments: 150 pockets/s/node at 64 fragments → TOUGH-M1 (7.5k pockets) ≈ 1 min per panel.
- Storage: raw benchmarks 8 GB; caches of point features ≤ 50 GB; total target ≤ 150 GB (cap 500 GB).
- AFDB-scale demo (not full AFDB): one proteome (e.g. human 23.6k models) end-to-end all-vs-all with FAISS, to
  measure real throughput; full AFDB is extrapolated, not run.

## 7. Process (AI-agent failure modes)
- Test-set peeking: sealed sets read only by `final_eval.py`; any analysis on them before freeze is a protocol
  violation recorded in RESEARCH_TREE.md.
- Metric drift: metrics and the missing-pocket policy are fixed here; any change is a dated, justified amendment
  made before seeing affected test numbers.
- Silent data loss: every loader reports counts vs the expected counts (tests/test_datasets.py).
- Over-claiming: every headline has its confounder baselines next to it; claims use Holm correction.
- Agents run long jobs detached with logs and completion markers; results are summarised in `reports/`.

## 8. Timeline (24 h; start 18:00)
- 19:00–21:30 design + ≤ 3 review rounds; splits frozen and committed.
- 21:30–03:00 pocket adapter + caches (L/D mode) on all sets; A1, B0–B1; A2 go/no-go; PPIPS build.
- 03:00–10:00 A3, A4, fusion; robustness; AFDB-scale demo.
- 10:00–13:00 freeze; final eval on sealed sets; independent verification.
- 13:00–17:00 REPORT.md, lessons, cleanup.
