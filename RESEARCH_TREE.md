# Research tree — pocket similarity on BURROW

Legend: [ ] planned · [~] in progress · [x] done · [-] abandoned/negative · [!] key finding
Started 2026-10-27 ~18:00 CET; 24 h budget (revisit ~2026-10-28 18:00).

## Status summary (latest first)

### 2026-10-27 23:05 — M2 dev results, PREREG consolidated
Dev evaluation on TOUGH-M1-dev, BLiPS-val and PPIPS-val is complete for all arms. The typed volumetric fingerprint
A1 wins in ligand-defined (L) mode (TOUGH-M1-dev ROC 0.795, BLiPS-val 0.775 vs B1 0.64/0.69) but collapses in the
deployment (detected, D) mode (0.56) because the 4 Å ligand shell imprints ligand shape — a key finding that also
inflates many literature numbers. A ligand-free site shaper (sph8) + protein-environment block fixes the
definition sensitivity (L↔D agreement 0.996; TOUGH-M1-dev D 0.672 vs A1 0.541). Fragment docking (A2) failed its
gate; the PPI fragment sub-hypothesis was not supported; PPI-L failed its feasibility gate (C3 exploratory).

All amendments are consolidated in PREREG.md (selection on BLiPS-val D-mode, Holm {C1a, C1b, C1-D, C2}). Running:
split audit (gates any model fit), A4b learned metric + final selection, final-eval infrastructure, proteome
FAISS demo. Next: audit → A4b fit → freeze (target ≤ 10:00) → final eval → independent verification → REPORT.

### 2026-10-27 19:55 — M1 design v1 + build launched
Literature, benchmarks, feasibility and PPI characterisation done; DESIGN v1 after six round-1 reviews. Key
findings so far: TOUGH-M1 is the only large fold-independent benchmark (TM-score AUC 0.51); 32 % of TOUGH-M1 is
homologous to BURROW training, so TOUGH-M1 dev = BURROW-homologous groups and test = BURROW-clean rest;
fragment docking is cheap (0.8 ms/fragment×pocket) but tracks pocket size (ρ −0.74), so it is gated.
Seven agents are building in parallel: evaluation module, splits, PPI datasets, A1/B0/B1, B4/B5, A2 docking.
No method has been evaluated yet. One protocol deviation (DEV1: TOUGH-M1 labels read by a reviewer before
sealing; B0 only). Next: round-2 review, commit splits, evaluate arms on dev.

### 2026-10-27 18:15 — M0 kickoff
Scaffold, venv (BURROW importable via read-only .pth on ../pocket_detect/src), PROMPT.md saved. BURROW
export smoke test passes (1a28: top pocket 0.626, 312 pts). Phase 1 launched in parallel: literature review,
public benchmark acquisition, fragment-docking feasibility (ADock), PPI/dimer pocket characterization.

Nothing modelled yet. No held-out data touched. Next: LITERATURE.md → DESIGN.md → ≤3 review rounds.

## Decisions
- D20 (02:55) L4 trained: best L4:egnn_small|CSLS BLiPS-val D 0.756 (SE 0.040) → one-SE threshold 0.716; A4b
  n1_linear raw (0.737) is within it and simpler → **final method = A4b:n1_linear raw** (configs/final_method.yaml from
  results/dev/final_select_pi.json). PREREG addendum A2 (sha256 4454979ed1efe50d04837e21bff49454154e0b6dfd13a709667ab7fd4e305e25): N1 raw and L4 reported descriptively at final eval.
- D19 (01:20) A4b tie-break: the agent picked n1_base by "grid order" (not a declared rule). PREREG says "simplest"
  (non-learned < learned; fewer stored dims; no CSLS); all A4b heads store 384 dims, so the natural next criterion is
  fewest parameters → **A4b:n1_linear raw** (0.737 ≥ threshold 0.715). Provisional final method pending L4 (Addendum A1).
- D18 (00:50) Accept rebuilt splits as drawn (rules unchanged, deterministic; no model fit yet). DEV2: BLiPS
  largest within-dataset component 10.6 % > 10 % gate (narrow); not re-split with DataSAIL (would redraw again, ~1 h);
  mitigated by cluster-balanced metrics and homology-group bootstrap. All dev numbers before 00:50 are provisional
  (old splits) and are re-run on the new splits. Fits (A4b, L4) proceed in parallel with the re-audit; freezing
  requires a re-audit PASS.
- D17 (23:50) Vertex site k = k-th qualifying HETATM residue (DeeplyTough public rule; matches listed ligand 85 % for
  k > 1 vs 36 % for the old guess); 510 fall back to first copy (flagged), 43 unresolved → missing policy. B0' =
  global Foldseek TM (Spearman 0.31 with TOUGH-M1's shipped TM list) — descriptive only. PPI-L (exploratory) needs
  N1 descriptors before final eval (cut-order item).
- D16 (23:20) PREREG addendum A1 (sha256 now a0d6ec8bbee31b76d1040f5e2afbe1e4d5f44f4ae4d76c25fd0242ea25c5cf45): one last candidate L4 (point-cloud network on sph8 points), ≤ 6
  configs, 3 h box; no further candidates. Reason: GPUs idle, learned geometric models are the main literature
  alternative (DeeplyTough/ProFSA) and must be tested for a "best method" claim.
- D15 (23:05) Audit failed before any model fit (gate worked). Rebuild graph with mmseqs -a + exhaustive Foldseek,
  re-derive all splits with unchanged rules; re-audit; re-run dev evaluations on the new splits (dev numbers so far
  are provisional, expected shifts small: ~2 % of units move). PPIPS val/test: most complexes have a BURROW-train
  homologue (BURROW prepares their pockets) → PPIPS-test reported stratified by BURROW homology; membership unchanged.
- D14 (22:45) Milestone M2 retrospective (reviews/milestone_M2_retrospective.md) adopted: LESSONS pruned to 11 rules;
  all amendments consolidated in PREREG.md (sha256 d3598a048cb397729a533948656591ea449ed64eb49b9c00fc0a10b27309d840). Selection objective = BLiPS-val D-mode cluster-balanced
  AUC with one-SE rule (deployment definition), guards on L-mode and TOUGH-M1-dev D-mode; Holm {C1a, C1b, C1-D, C2}.
  No further open-ended exploration on TOUGH-M1-dev; no more bespoke baselines; A2 stops after the PPI sub-test.
- D13 (22:25) Tier-1 candidates for A4b: hybrid A1(sub-pocket)+A1(sph8)+env(sph8) (1,141-d) trained with L↔D
  augmentation; selection on BLiPS-val mean(L,D) per DESIGN. The ligand-free non-learned A1(sph8)+env(sph8) is kept
  as the robust non-learned fallback (best D-mode, L↔D agreement 0.996). Rationale: mean(L,D) still rewards the
  L-mode imprint; the learned metric with L↔D augmentation is the principled way to trade it off.
- D10 (21:45) **A2 gate FAILED** on TOUGH-M1-dev (fusion A1+A2 vs A1, stratified ΔAUC −0.010 [−0.027, +0.007];
  every A2 variant/fusion negative). Per DESIGN, A2 is a negative result and is not developed further for tier 1.
  The pre-registered PPI sub-hypothesis (fragments vs lead-like on PPIPS) is still run (docking already queued).
- D11 (21:45) **L-mode ligand imprint.** A1's L-mode advantage collapses in D-mode (0.808 → 0.560 on the same pairs;
  B1 −0.06, B4 −0.02). 4 Å ligand-shell pockets encode ligand shape, and TOUGH-M1 positives are ligand-defined, so
  an L-mode win partly measures the pocket definition. Amendment (before any test evaluation): add claim **C1-D**
  (TOUGH-M1-test, D-mode, common-set ROC-AUC final − B1 > 0; TOUGH-M1-test is BURROW-clean so D-mode is allowed)
  to the Holm family {C1a, C1b, C1-D, C2}; selection objective for all further development = mean cluster-balanced
  AUC over L-mode and D-mode (TOUGH-M1-dev; BLiPS-val when available). Development now targets definition
  robustness (D-mode pocket core extraction, robust descriptor blocks, L/D-augmented learned metric).
- D12 (21:45) Power: unit = component of (ligand cluster ∪ homology group) has a giant component (test 710/1,014
  pockets in one unit, 141 units) → test MDE ≈ 0.13 for Δ(A1−B1); dev Δ = +0.152 (SE 0.050). Kept as
  pre-registered (not changed after seeing it); C1 power is limited and will be reported as such.
- D8 (21:00) Keep the pre-registered TOUGH-M1 rule: dev 731 pockets (3,366 pos / 6,463 neg), test 1,014 pockets
  (530 groups, 302 ligand clusters; 10,064 pos / 13,221 neg), 5,779 excluded (touch BURROW AND a sealed set).
  Reason: rules are not changed after seeing counts; test has enough independent units. ADDED (before any test
  evaluation): secondary literature-comparable evaluation "TOUGH-M1 full minus dev pockets" for NON-learned arms
  only (BURROW's learned models play no role in L-mode with analytic features); learned arms are not reported there.
- D9 (21:00) BLiPS-val (163 sites, 15 ligand clusters, one cluster = 59 % of positives) is too weak for selection →
  re-split pooled BLiPS train+val (non-test) by homology component 80/20 (seeded) before any model fit.
- D7 (20:50) **C3 gate failed** (recorded before any similarity score): PPI-L (Pasteur, 2,236 PLOC+PLONC modulator
  pockets, 93 homology groups) has only 175 cross-group positive pairs in total; test split has 3 pairs / 2
  groups / 1 ligand cluster. C3 → exploratory; Holm family = {C1a, C1b, C2}. PPI evaluation relies on PPIPS
  (P-ortho transfer retrieval, P-sym sanity) and an exploratory PPI-R retrieval task (modulator pockets retrieving
  other families' modulator pockets over matched non-PPI pockets) if time allows.
- D6 (20:25) Amend size strata to 5 (mean log-vol) × 20 (|Δ log-vol|) quantile bins (5 × 5 for sets with < 500
  positives). Evidence: simulation only (reports/evaluate_module.md: 5×5 → 0.539, 5×20 → 0.507 for a pure size
  scorer). No real data had been evaluated. evaluate.py frozen at this commit (hash goes into every sidecar).
- D5 (20:12) Design frozen at v2 after 2 review rounds; no round 3: round-2 changes were exact text, adopted
  verbatim, and all build agents were re-briefed (splits, PPI, eval). Raw label lists chmod 000 (sealed_raw_SHA256SUMS).
  TOUGH-M1 ships per-pair APoc/G-LoSA/SiteEngine scores → paired prior-art baselines B5-T.
- D3 (19:45) D-mode match = coverage ≥ 0.3 OR precision ≥ 0.5 (detected pocket inside the site counts).
- D4 (19:45) DESIGN v1 after round 1: TOUGH-M1 dev = BURROW-homologous groups (32 % of TOUGH-M1 is homologous
  to BURROW training — leakage rule), test = BURROW-clean rest; BLiPS test = BURROW af_set; PPI-L from the
  Pasteur pocketome; ESM-2 baseline B4; A1 + A4b main bets, A2 gated, A3/A4 stretch. See DESIGN §10.
- DEV1 (19:40, protocol deviation, disclosed by the agent) The statistics reviewer read
  data/processed/benchmarks/tough_m1_pairs.parquet at 19:08–19:10, i.e. before sealing (D2, 19:12), and computed
  label-graph structure (top ligand cluster = 47 % of positives; negatives from 1,266 pockets) and a size-only B0
  ROC-AUC = 0.577 on ALL TOUGH-M1 pairs (incl. the future test partition). No method was fitted or tuned.
  Impact: the B0 test number is known in advance; this is a baseline, not a method under selection, so the
  selection risk is negligible. The label-structure facts are used for split design (stratification) only.
  Rule added to LESSONS.md: seal labels BEFORE launching any agent that might open them.
- D2 (19:12) Technical sealing: all benchmark pair/label tables moved to `data/sealed/` (chmod 000, sha256 in
  `data/sealed_SHA256SUMS.txt`). Raw label lists under data/raw/ are sealed by protocol (agents told not to read
  them). Before sealing, the data agent only counted pairs (no analysis). TOUGH-M1 dev pairs will be extracted by
  a split script that writes dev pairs only. Point featurisation of structures (label-free) is allowed for all sets.
- D1 (18:25) Mount check: `/cluster/work/beltrao/shared/rsyncPDB` (referenced by pocket_detect manifests) is NOT
  mounted; use `/cluster/scratch/jjaenes/pdb/<mid2>/<id>.cif.gz`. BioLiP2 snapshot 2025-11-12 is readable at
  pocket_detect/data/raw/biolip2/current (read-only) — candidate source for a ligand-labelled pair set.
- D0 (18:10) Repo on branch `pocket-compare`; identity gmagnusson (same as pocket_detect). pocket_detect is a
  read-only mount, so it is imported via a .pth path, not installed. Seeds fixed: `pocketcompare.seeds.SEEDS = [0..4]`.

## Tree
- [~] P1 Literature review → LITERATURE.md
- [x] P1 Public benchmark acquisition → DATA.md, reports/data_benchmarks.md, tests/test_datasets.py (4 pass)
  - [x] ProSPECCTs 10 subsets (6,093 pockets; counts exact). Click-through licence, NO redistribution → never commit
  - [x] TOUGH-M1 7,524 pockets, 505,116 pos / 556,810 neg (exact); residue numbering renumbered vs PDB
  - [x] Vertex 6,218 pockets (+1 pos vs DeeplyTough's parser bug; kept as-is); labels are per protein pair
  - [x] TOUGH-C1 (classification), KLIFS metadata (14,917 structures); LIGYSIS/PoSSuM recorded, not fetched
  - [ ] Re-run scripts/data/build_benchmarks.py once PDB mirror sync completes (188/6,029 Vertex structures missing)
  - pitfalls: ProSPECCTs self-pairs counted as actives (P7: 49/115); TOUGH-M1 ∩ TOUGH-C1 = 2,611 PDB IDs
- [x] P1 Fragment-docking feasibility (ADock throughput, fragment library) — reports/fragment_docking_feasibility.md
  - [x] ADock runs from our .venv + /tmp/adock/overlay (cupy etc.; scripts/feasibility/setup_adock_overlay.sh)
  - [x] `frag_lite_np` preset: 0.82 ms/fragment×pocket GPU; node ≈150 pockets/s @64 frags; AFDB×5 ≈ 78 node-days
  - [x] Seed reproducibility r ≥ 0.98; same-site pairs r ≈ 0.8 (n=2, anecdotal)
  - [!] Size confounder: mean frag score vs volume Spearman −0.74; pocket mean = 57 % of variance → must normalise
        and must beat a volume-only baseline (n=27 pockets, anecdotal)
  - [-] Probe-atom energy maps on BURROW points and rigid GPU scan: poor signal / no faster (prototype only)
- [~] P1 PPI / dimer pocket characterization (BURROW on AFDB dimers)
- [~] P2 DESIGN.md draft v0 (19:15) + review round 1 (PI, stats, data, algorithms, agent-failure, domain)
  - [x] R1 PI, algorithms, domain, statistics reviews in reviews/round1_*.md
  - [x] R1 agent-failure-modes review → reviews/round1_agent_failure_modes.md (sealing, eval-first, provenance)
- [x] P3 Pocket adapter (L/D-mode) + point-feature cache on TOUGH-M1 (label-free) — reports/pocket_adapter.md
  - [x] 7,524/7,524 pockets, 113 s on 32 workers, 6.4 GB; deterministic; 9 tests pass
  - [x] L-mode median 352 pts / 542 Å3; residue-list pockets ~2× ligand-defined (Jaccard 0.39) → ligand file used
  - [x] D-mode miss 19.4 % (coverage rule) → 5.5 % with coverage ≥ 0.3 OR precision ≥ 0.5 (D3)
  - [ ] bug: tough_m1_pockets.parquet hardcodes chain `A:` (3,191 files differ); adapter maps it — fix loader
- [x] P2b Review round 2 (combined PI/stats/data panel) on DESIGN v1 → DESIGN v2 (20:10)
  - [!] Round 2 caught: global homology graph would percolate (→ within-dataset components + direct-edge
        exclusion); A4b augmentation source leaked into test; 1-D size strata vacuous; PPI-L ligand-free shortcut
- [~] P3 Build (parallel, 19:50): evaluate.py + provenance (eval agent); homology graph + splits (split agent);
      PPI-L (Pasteur pocketome) + PPIPS (PPI agent, 3 h box); A1 + B0/B1 descriptors (A1 agent);
      B4 ESM-2 + B5 external (baseline agent, cuda:1); A2 docking panels on TOUGH-M1 (A2 agent, cuda:0,2)
- [x] P3 evaluate.py + provenance + check_report (41 tests; 1M pairs × 2000 boot in 1.7 s) — reports/evaluate_module.md
- [x] P3 A1 descriptor (16 configs, default 514-d), B0, B1; similarity + CSLS — reports/a1_descriptors.md
  - [x] 6.3 ms/L-pocket, 0.73 µs/pair; invariance error ≤ 1.3e-7; 17 tests
  - [!] label-free check: same site L vs D mode: A1 AUC 0.70 vs B1 0.94 → A1 is sensitive to pocket definition
  - [~] re-run from committed tree for clean provenance (pid in logs/descriptors_tough_m1.pid)
- [x] P3 PPI datasets — reports/ppi_datasets.md
  - [-] PPI-L gate failed (175 cross-group positives in the whole set; shared modulators stay within families)
  - [x] PPIPS: 1,991 dimers; P-ortho queries 1,088 / 95 / 229; P-sym pairs 2,088 / 366 / 440 (train/val/test)
  - [x] B6 PSI re-implemented from 108 descriptors (r = 0.96 vs API sample)
- [x] P3 B4 ESM-2 pocket mean (L+D, 0.06 s/pocket) and B5 EPoCS (ESM-2 3B, L only, 0.3 s/pocket), all 7,524
      TOUGH-M1 pockets — reports/baselines_b4_b5.md
- [x] P3 A2 docking on TOUGH-M1 (128 NCI fragments + 128 lead-like, stock Vina, 12 Å box) — reports/a2_docking.md
  - [x] L 7,524 + D 6,068 pockets, 0 failures, 0.30 GPU-s/pocket/256 mols (≈13 pockets/s/node)
  - [x] seed r 0.988 (frag) / 0.972 (lead); ~¼ of best poses flip between seeds
  - [!] LE residualisation does not remove the size axis; IFP block least confounded (label-free observation)
- [x] P3 Homology graph + splits — reports/splits.md, data/splits/SPLITS.md (verify_splits 66/66)
  - [x] graph 65k chains; within-dataset largest comp: TOUGH 5.1 %, ProSPECCTs 6.6 %, BLiPS 9.6 %
  - [!] 77 % of TOUGH-M1 excluded by the leakage rule (touches BURROW AND a sealed set) → D8
  - [x] BLiPS train/val/test sites 2,699/163/3,606; val too weak → D9 re-split
- [x] P3 Dev evaluation of all arms on TOUGH-M1-dev — reports/dev_eval_tough_m1.md (137 trials)
  - [!] L-mode ROC / stratified: A1 pair_only 0.795/0.732 · SiteEngine 0.680/0.672 · B1 0.643/0.630 ·
        B4 0.601/0.600 · B5 0.599/0.592 · A2 frag-IFP+CSLS 0.632/0.625 · controls 0.50
  - [!] D-mode: A1 collapses (0.808 → 0.560 same pairs), B1/B4 robust → D11
  - [-] A2 gate failed (D10)
  - [!] size shortcut B0 ROC 0.78, B0m 0.857; B0m stratified 0.489 (diagnostic passes)
  - [x] CSLS: small effect (positive only for A2-IFP)
- [x] P3 BLiPS re-split (D9) + caches + descriptors — reports/blips_ppips_prep.md (verify_splits 97/97)
  - [x] BLiPS v2 train 2,350 sites (7,186 pos) / val 511 sites (563 pos, 48 ligand clusters, max share 9.95 %)
  - [x] test holo 3,606 / AF 3,603 caches; transferred test ligands clash (< 2 Å) in 29 % holo / 55 % AF sites (flagged)
  - [!] BLiPS D-mode coverage < 0.3 for ~45 % of sites (TOUGH-M1 19 %)
- [-] P3 Independent split audit — **FAILED** (reports/audit_splits.md): mmseqs search without -a underestimates
      identity near 30 %; non-exhaustive Foldseek missed edges → leaks: TOUGH-test↔BURROW 16 pockets, TOUGH-dev↔sealed 7,
      dev↔test 3, BLiPS-train↔sealed 19 proteins, BLiPS train↔val 9, PPIPS 1 complex → rebuild (D15)
- [x] P3 A2 docking on all 20,497 PPIPS pockets (both panels, 40 min, 0 failures); interface pose-in-pocket 82 %
- [x] P3 Definition robustness — reports/definition_robustness.md (36 variants logged)
  - [!] ligand-free site shaper "sph8" (buried points ≤ 8 Å of buriedness-weighted centroid) + env block (113-d
        protein-side composition, 0.3 ms): cb D 0.672 (A1 0.541), L 0.648, L↔D agreement 0.996
  - [x] hybrid A1(best sub-pocket) + A1(sph8) + env(sph8): mean(L,D) 0.693 (+0.024 [−0.039, +0.043] vs ref)
  - [x] D-mode ligand-free vs B1: +0.052 [−0.004, +0.134]
  - [-] residue mode (slow, 0.619), sph10, core8, merged-pocket centres, env up-weighting, +B1
- [x] P3 Dev eval BLiPS-val v2 + PPIPS-val — reports/dev_eval_blips_ppips.md
  - [!] BLiPS-val L: A1 pair_only 0.775 / strat 0.741 vs B1 0.687, B4 0.679; D: A1 0.555, B1 0.676, B4 0.698
  - [!] ligand imprint replicates (A1 L→D on same pairs −0.268 [−0.359, −0.175])
  - [x] PPIPS-val P-ortho MRR: B4 0.942 · B1 0.764 · A1 0.633 · B0 0.426 (interolog transfer; 13 units); P-sym ≥ 0.92 all
  - [-] PPI sub-hypothesis fragments > lead-like: not supported (IFP +0.074 MRR, Holm p ≥ 0.25; underpowered)
- [x] P3 Dev tables re-run on rebuilt splits — reports/dev_eval_v2splits.md (250 trials, tag splits_v2)
  - [x] unchanged: A2 gate FAIL (−0.009 [−0.066, +0.023]); ligand imprint (A1 L→D −0.244 TOUGH, −0.161 BLiPS);
        CSLS negligible; fragment sub-hypothesis not supported (reversed to −0.06/−0.005/−0.04 MRR)
  - [!] changed: A1−B1 on BLiPS L no longer significant (+0.045 [−0.005, +0.098]); A1 config choice unstable
        (12–14 configs within one SE)
- [x] P4 A4b learned metric — reports/a4b_selection.md, results/dev/final_select_all_summary.md (new splits)
  - [!] BLiPS-val D cb: B1 0.648 · B4 0.670 · N1 0.697 · N2 0.704 · A4b n1_linear 0.737 · n2_linear+CSLS 0.751 (best)
  - [x] n1_linear raw: BLiPS L 0.718, TOUGH-M1-dev D 0.721 (B1 0.617), PPIPS MRR 0.719 (N1 0.790, B1 0.761)
  - [!] learned heads lower PPIPS P-ortho MRR vs N1 (0.69–0.76 vs 0.79)
  - [x] N1/N2 inputs for BLiPS (train/val/test holo+AF), PPIPS, TOUGH-M1; 3.8–6.2 ms/pocket
  - [!] non-learned BLiPS-val D cb-AUC: N1 0.686 (SE 0.041), N2+CSLS 0.701, B1 0.641, B4 0.655; N1 passes guards
  - [x] a4b grid pre-declared (configs/a4b_grid.yaml, 12 configs); train script refuses without audit flag (after audit + BLiPS descriptors)
- [x] P4 Final-eval infrastructure — reports/final_eval_infra.md; dry run reproduces dev numbers (max dev 5.6e-16)
  - [x] ProSPECCTs 6,093/6,093 and Vertex 6,149/6,218 point caches + descriptors (label-free)
  - [x] Vertex site mapping fixed to DeeplyTough's public rule (D17); B0' global Foldseek TM tables
- [x] P4 Human-proteome FAISS demo — reports/proteome_demo.md
  - [!] 23,586 AF models → 116,246 pockets, 0 failures; fast GPU backend 133 structures/s (716 pockets/s) on
        2×4090 + 22 workers (CPU-bound); descriptor 6.4 ms/pocket; backends byte-identical
  - [x] FAISS exact GPU all-vs-all top-50 0.51 s; OPQ+IVF-PQ 64 B codes recall@10 0.81–0.85, +re-rank 0.995
  - [x] extrapolation 200 M structures: ≈0.95 B pockets, ≈7,150 CPU-core-h + 223 GPU-h; 0.11 TB PQ index
  - [x] sanity: rotation self-retrieval 100 %; 1 Å atom noise → re-described site self-rank-1 83 %; CSLS cuts hubness
        skew 1.82 → 0.62 (proteome radii)
- [x] P4 AF robustness (C5) on val — reports/af_robustness_dev.md (239 val sites with holo + AF)
  - [!] holo/holo vs holo/AF ligand-sharing ΔAUC (N1): val L −0.005 [−0.054, +0.041], train L −0.008 [−0.019, +0.003]
  - [x] same-site holo→AF retrieval: L top-1 0.78 (B1 0.88), D top-1 0.55 (B1 0.41); pLDDT 70–90 −0.17 top-1
- [x] P4 L4 point-cloud network — reports/l4_pointnet.md
  - [!] egnn_small+CSLS: BLiPS-val D 0.756, L 0.765, PPIPS MRR 0.821 (best), but TOUGH-M1-dev D 0.646–0.681 (< A4b 0.72)
  - [x] vs N1 on BLiPS-val D +0.059 [−0.006, +0.130]; vs B1 +0.108 [+0.018, +0.181]; 0.54 ms/pocket GPU, 47 ms CPU
- [x] P3 Split rebuild (mmseqs -a, exhaustive Foldseek) — verify_splits 101/101; seq edges 1.02 M → 1.21 M
  - [x] TOUGH-M1 dev 765 / test 1,045 / excluded 5,714 (254 pockets moved); BLiPS-test unchanged (0 moved)
  - [x] BLiPS v2 train/val redrawn (972 sites moved); PPIPS redrawn (681 complexes moved); 128 readmitted
        train/val sites not cached → excluded_not_cached
  - [x] **re-audit PASS** (reports/audit_splits.md "Re-audit"): 0 sequence-rule hits across all checked partitions;
        4 boundary structure pairs with approximate min-TM 0.50–0.56 have exact TM 0.41–0.497 (< rule) → kept
- [x] P4 Blind deployment test script + val dry run — reports/blind_and_ppil.md
  - [x] detection recall 0.615 on val AF models; partner retrieval (84 pairs) final hit@10 0.155 vs B1 0.107, AUC
        0.634 vs 0.647 — not distinguishable (low power); B0 0.44
  - [x] PPI-L N1 descriptors + final_eval stage (exploratory)
- [ ] P4 Exploratory PPI-R task (modulator pockets retrieving other families' modulator pockets) (TOUGH-M1-dev, BLiPS-val, PPI val)
- [ ] P5 Freeze, final held-out evaluation, verification, REPORT.md
