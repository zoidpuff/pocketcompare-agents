# Round 1 review — data, labels, splits, leakage (reviewer: data/leakage)

Scope: DESIGN.md v0 §2 (data), §2.6 (receptor-model leakage) and how §3–4 use the data. I checked feasibility on
disk with read-only commands: MMseqs2/Foldseek from `pocket_detect/tools/bin`, and BURROW's
`train/work/final_all_obs.fasta` (24,737 train+dev input chains). The scripts were throw-away scratch files and
are not in the repo, so re-derive the numbers below with committed scripts before relying on them.

## Measured facts that change the design
1. **TOUGH-M1 leaks into BURROW.** 2,387 of 7,524 TOUGH-M1 proteins (32 %) hit BURROW train/dev chains under
   BURROW's own rule (E < 1e-3, id ≥ 0.3, qcov|tcov ≥ 0.5 or aln ≥ 80); 1,329 of them are ≥ 90 % identical.
   That makes D-mode (learned detection) and the `point_score` arm on these proteins a violation of the brief,
   not just a stratum.
2. **BLiPS-test as drafted is BURROW training data.** §2.3 builds all BLiPS splits from BURROW
   `train/dev`, so BLiPS-test sites are sites BURROW's detector was fitted on.
3. **The §2.2 TOUGH-M1 split is infeasible.** With MMseqs 30 %/cov 0.8 merged with Foldseek TM ≥ 0.5 (max of
   q/t normalisation), one component holds 5,161 of 7,524 proteins (69 %). A 30/70 split then puts every
   common fold in test. With BURROW's rule plus TM ≥ 0.5 on **both** normalisations (min), the largest component
   is 4.5 % (1,421 components), which splits cleanly.
4. **The PPIPS split as drafted is infeasible.** Linking complexes through shared or homologous chains
   (sequence only, E ≤ 1e-3, cov ≥ 0.5) gives a giant component of 6,798 of 15,161 complexes (45 %; 61 % of
   heterodimers). Homodimers do not percolate (largest component 3.7 %). Outside the giant component there are
   2,507 homo and 312 hetero cross-species interologs at < 30 % identity.
5. **A clean, ready-made test source exists.** BURROW Track C `data/processed/af/` holds 10,341 LIGYSIS human
   sites on 3,465 proteins, with the holo representative chain, the AFDB v6 model, transferred ligands, pLDDT
   and AF-vs-holo RMSD. It is in BURROW's frozen test union, so by construction it shares no protein with
   BURROW train (30 % rule). 3,201 TOUGH-M1 proteins are homologous to it, and the TOUGH-M1 proteins homologous
   to it or to BURROW train together number 5,356, two almost disjoint groups.
6. **Additives dominate the BURROW sites.** The most frequent non-ion CCDs on BURROW sites include CLA (439
   sites), HEC, C8E (detergent), PO4, SO4, GOL, AZI, MPG, Y01, PGW, BU3 and OXY. BioLiP's own filter is not
   enough. 606 pooled sites carry ≥ 3 distinct CCDs.
7. **ADock is more than stock Vina.** `v2_fitted` has 18 weights fitted on the docking team's splits. The
   AF/template-first mode retrieves PDB templates (the test holo itself can be retrieved), and `adock_rerank`
   is a fitted model.

## MUST
- **M1. One global homology graph and one split assignment for every dataset.** Nodes are proteins from
  TOUGH-M1, BLiPS, af_set, PPIPS chains, ProSPECCTs and Vertex. Edges are BURROW's sequence rule (reuse
  `pocketdetect.datasets.leakage.apply_rule` verbatim, not "cov 0.8") or Foldseek TM ≥ 0.5 on both
  normalisations. Gate on component sizes (largest ≤ 10 %) and commit them before freezing. Reading
  ProSPECCTs/Vertex **sequences and structures for leakage control only** (no labels, no descriptors) is
  allowed; write that exception into §2.2.
- **M2. TOUGH-M1 split aligned with BURROW.** Components that contain any BURROW-train/dev homologue go to
  TOUGH-M1-dev (≈ 32 %, close to the planned 30 %). The rest go to test, which then needs no BURROW stratum.
  Because dev is family-related to BLiPS-train, use TOUGH-dev only to select non-learned arms; select A4/A5
  on BLiPS-val and PPIPS-val. Seal TOUGH-M1-test in `final_eval.py` like ProSPECCTs, including the shipped
  APoc/G-LoSA/SiteEngine scores.
- **M3. Rebuild BLiPS from three sources.** Train from BURROW train, val from BURROW dev (already filtered at
  30 % against train), and **test from the Track C af_set** (holo representative chain, non-ion LIGYSIS sites).
  Then drop train/val proteins with a Foldseek (min) TM ≥ 0.5 hit to any test partition, and report how many
  were removed.
- **M4. Sealed sets and D-mode.** ProSPECCTs and Vertex cannot be re-split. Their headline is L-mode with
  analytic features. D-mode or `point_score` numbers are headlined only on the BURROW-clean subset (pairs where
  both proteins have no rule hit), with the full set as secondary. This applies to C2 too.
- **M5. PPIPS split.** Put the giant component in train. Split the remaining 2,165 components into
  train/val/test (suggest 60/20/20 so test has a few hundred complex pairs), and say that test is mostly
  homodimers. Exclude the 260 dimer proteins found in BURROW train/dev from val/test. Recompute the components
  after the Foldseek merge.
- **M6. Ligand-level leakage.** Define ligand clusters as ECFP4 Butina at 0.7 (the same threshold as the
  positive label). On BLiPS-test and TOUGH-M1-test, report AUC for "chemotype seen in A4 training positives"
  vs "unseen" pairs, plus macro-AUC over ligand clusters. Do not use Bemis–Murcko scaffolds: cofactors and
  sugars do not have meaningful ones.
- **M7. Additive list.** Start from BioLiP's exclusion list plus the PLINDER artefact list. Add detergents and
  lipids (C8E, LDA, BOG, LMT, MPG, PGW, Y01), buffer ions (PO4, SO4), cryo-agents (GOL, EDO, BU3, PEG*), ACT,
  AZI, OXY and covalent glycans. Require ≥ 8 heavy atoms for Tanimoto labels, and below that use exact CCD only.
  Cap pairs at ≤ 3 sites per protein, and cap per ligand cluster (e.g. ≤ 300 positive pairs) so that CLA/HEC
  in photosystems cannot dominate.
- **M8. Size matching in 2-D, with a gate.** Match negatives on (mean log-volume bin × |Δ log-volume| bin),
  not on the ratio alone. Accept the set only if B0 has AUC in 0.5 ± 0.03 on BLiPS-val; otherwise re-sample.
  Do the same for PPIPS, adding f_min and bur16 bins.
- **M9. Robustness sets built on val first.** Build AF-vs-holo on af_set proteins in BLiPS-**val** (and
  TOUGH-dev) during development, and run the test-protein version only in final eval. Stratify by holo release
  date ≥ 2018-05-01 (after the AF2 training cutoff, so AF has not memorised that holo) and by site pLDDT band.
- **M10. ADock configuration.** Use stock Vina weights, `frag_lite_np`, a plain receptor, and no template
  mode or reranker. Record the config hash. Document that Vina's 6 weights were themselves fit on PDBbind-2007:
  this is a declared, negligible-capacity exposure, not "leakage-free".

## SHOULD
- **S1. Fold criterion for positives.** Use TM normalised by the *shorter* chain < 0.5, or a crop of 15 Å
  around the site, instead of global TM. Global TM < 0.5 lets the same kinase or Rossmann domain inside
  different multidomain proteins count as "cross-fold".
- **S2. Hold out ligand clusters.** Remove ~20 % of ligand clusters (frequency-stratified, seeded) from
  BLiPS-train positives entirely, so that the unseen-chemotype stratum in M6 has power.
- **S3. Interolog positives.** Require complex-level conservation: US-align multimer TM ≥ 0.5 with consistent
  chain mapping, and ≥ 50 % of interface residues aligned. Define correspondence at site level (mapped
  residues), score by best-over-overlapping pockets, and add hard negatives: non-corresponding interface
  pockets of the same interolog pair. Use homology only for negatives, because no Pfam is on disk.
- **S4. AF-template stratum for PPIPS-test.** Flag pairs where both chains hit a single PDB entry at ≥ 30 %,
  using the docking team's PDB SEQRES MMseqs DB. In those pairs both models may copy the same template.
- **S5. Pooled multi-ligand sites.** Label each site with its dominant (largest, non-additive) ligand cluster,
  or exclude sites with > 3 clusters.
- **S6. Vertex structures.** Freeze the site-index → HET-instance rule and the missing or obsolete-entry
  policy now (structures only). Freeze the splits only after the PDB mirror sync has finished, and record the
  snapshot.

## COULD
- **C1. EPoCS stratum.** Add an EPoCS-style pocket-level similarity between BLiPS-test and BLiPS-train pockets
  as a stratum. EPoCS shows that 30 % sequence splits are easy.
- **C2. Drop P-lig.** Replace the iPPI-DB P-lig tier with BURROW's 400-assembly dimer set. It is in BURROW's
  test union and has real interface ligands.
- **C3. D-mode augmentations in A4.** D-mode pockets on BLiPS-train are optimistic, because BURROW was trained
  on those sites. Draw the D-mode augmentations for A4 from af_set-val instead, where available.

Feasibility: the global MMseqs2 run on ~40k sequences takes minutes. Foldseek all-vs-all on 7.5k TOUGH-M1
structures took a few minutes on 48 threads, so ~40k structures fit in under 1 h. BLiPS test reuses Track C
tables. All of this fits within the 21:30 freeze slot plus about 1.5 h.
