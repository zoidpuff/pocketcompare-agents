# PREREG2 — temporal replication on fresh held-out data (2026-10-28 06:45, before the set exists)

Motivation: the PREREG test sets are spent; the post-test fusion of FINAL and L4 (reports/exploratory_fusion.md)
and the C1/C1-D result need replication on data nobody has looked at. No method is retrained or changed: all arms
are the frozen artefacts (FINAL = configs/final_method.yaml at tag freeze-v1; L4:egnn_small CSLS and N1 as frozen in
results/models/; fusion = w 0.5 z-score rule exactly as declared in scripts/explore/fusion_a4b_l4.py; B1; B0).

## Set: PDB-T (temporal)
- PDB entries in the local mirror (/cluster/scratch/jjaenes/pdb) with initial release date > 2025-11-12 (after the
  BioLiP2 snapshot behind every training set and after BURROW's training data). X-ray or EM ≤ 3.0 Å.
- Sites: non-polymer ligands with ≥ 10 heavy atoms, excluding the committed additive list (data/ref/additives.txt),
  ions, and covalently linked / polymer-like ligands; one site per ligand cluster per chain; protein chain ≥ 50 aa.
- Pairs: positives = sites in different homology groups sharing a ligand with ECFP4 Tc ≥ 0.7; negatives = different
  groups, max Tc < 0.3, 5× positives, seeded (SEEDS[0]); caps as BLiPS (≤ 3 sites/protein, ≤ 300 positives per
  Butina cluster).
- Leakage: any protein with a direct edge (MMseqs2 -a rule or exhaustive Foldseek TM ≥ 0.5 both directions) to any
  training source (BLiPS-train/val v2, PPIPS-train/val, BURROW train/dev, TOUGH-M1-dev, the A4b/L4 training data)
  is removed. Splits inside PDB-T: homology components (for bootstrap units only).
- Pair labels are sealed at creation (chmod 000, sha256 recorded in data/sealed_SHA256SUMS.txt by the build script).
- **Gate** (recorded before any score): ≥ 300 positive pairs spanning ≥ 30 homology groups and ≥ 10 ligand clusters;
  otherwise PDB-T is reported descriptively only, with no claims.

## Claims (Holm family, one-sided α = 0.05, vertex bootstrap B = 2,000, units = homology components, D-mode primary)
| id | comparison | mode |
|---|---|---|
| R1 | FINAL − B1, ROC-AUC | D (common set) |
| R2 | FUSION − FINAL, ROC-AUC | D (common set) |
| R3 | L4 − FINAL, ROC-AUC | D (common set) |
Reported: the same in L-mode; size-stratified AUC (5 × 20); B0; cluster-balanced AUC. Runtime unchanged.
Evaluation by a single script `scripts/eval_pdbt.py` that reuses the frozen functions; an independent agent verifies.
