# SPLITS — homology graph, TOUGH-M1 dev/test, BLiPS train/val/test (built 2026-10-27, data agent)

Rebuild everything: `bash scripts/data/run_splits.sh` (≈ 25 min, 24 threads; seed `SEEDS[0]` = 0).
Checksums: `SHA256SUMS.txt` (sealed files: hash recorded at write time). Verification: `scripts/data/verify_splits.py`
(66 checks, 0 failures; log `logs/verify_splits.log`). Splits are read-only once committed.

## Rules (DESIGN §2.1 + design round 2)
- **Edge** = `pocketdetect.datasets.leakage.apply_rule` verbatim (MMseqs2 -s 7.5, E < 1e-3, fident ≥ 0.30,
  qcov or tcov ≥ 0.5 or alnlen ≥ 80) **or** Foldseek min(qTM, tTM) ≥ 0.5 (either search direction). Identical
  sequences are always linked (shared `sid`).
- **Groups** = connected components of each dataset's own graph. **Exclusion across datasets** uses DIRECT edges only.
- Sealed test sets: ProSPECCTs, Vertex, BLiPS-test (= all af_set proteins), PPI-L-test (`ppi_split == test`),
  TOUGH-M1-test (for BLiPS).

## Homology graph
| | value |
|---|---|
| nodes (chains) | 65,326: dimers 30,322 · Vertex 9,146 · TOUGH-M1 7,524 · BURROW train 6,475 / dev 579 / assembly partners 2,634 · af_set 3,473 · ProSPECCTs 3,041 · PPI-L 2,132 |
| unique sequences / Foldseek reps (≥ 20 aa) | 35,628 / 35,575 |
| edges (sid pairs) | 2,706,174: MMseqs2 rule 1,020,281; Foldseek 2,483,810; Foldseek-only 1,685,893 |
| largest within-dataset component (gate ≤ 10 %) | TOUGH-M1 385 = 5.1 % ✓ · ProSPECCTs 6.6 % ✓ · BLiPS (train+dev+af) 9.6 % ✓ · **Vertex 25.3 % ✗** · **dimers 24.3 % ✗** |
| global component (information only) | 32,498 / 65,326 = 49.8 % |
Vertex and dimers are not split here (Vertex is a fixed sealed test; PPIPS is split by the PPI agent). If they need
splitting, the gate fails → DataSAIL-style cluster-based splitting is the proposed fix.

## TOUGH-M1 (dev = BURROW-homologous, test = BURROW-clean, excluded = touches BURROW AND a sealed set)
| partition | pockets | groups | ligand clusters | pos pairs | neg pairs |
|---|---|---|---|---|---|
| dev | 731 | 483 | 276 | 3,366 | 6,463 |
| test (sealed pairs) | 1,014 | 530 | 302 | 10,064 | 13,221 |
| excluded | 5,779 | 464 | 1,088 | (317,384) | (299,818) |
411,610 cross-partition pairs dropped. Excluded pockets touching ProSPECCTs 4,595 · af_set 3,947 · Vertex 1,589 ·
PPI-L-test 212 (overlapping). Ligand cluster = Butina(Tc ≥ 0.6) on ECFP4 of the shipped ligand SDF.
Dev/test pair tables carry the shipped APoc (2 numeric columns), G-LoSA (1) and SiteEngine (3) scores in file order
(`apoc_c1…`; semantics as in the OSF files); 100 % of pairs matched.

## BLiPS
| | train | val | test (sealed) |
|---|---|---|---|
| sites / proteins / groups | 2,699 / 1,772 / 1,189 | 163 / 99 / 92 | 3,606 / 2,304 / 860 |
| largest group (proteins) | 28 (1.6 %) | 2 (2.0 %) | **577 (25.0 %)** |
| positives (n_shared 1 / ≥ 2) | 8,000 (7,822 / 178) | 335 (331 / 4) | 6,895 (6,623 / 272) |
| negatives | 40,000 | 1,675 | 34,475 |
| positive ligand clusters; max share | 176; 3.8 % | 15; **58.8 %** | 229; 4.4 % |
| positives with a top-20 promiscuous CCD | 3,082 | 314 | 2,068 |
| chemotype seen / unseen (positives) | — | 335 / 0 | 6,267 / 628 |
| site clusters unseen in train | — | 25 | 1,474 |
Site funnel (train / val / test sites): all 13,640 / 1,221 / 10,341 → ≥ 1 qualifying ligand 5,768 / 491 / 4,280 (ion-only
5,014 / 416 / 4,026; additive 1,873 / 197 / 1,491; < 10 HA 966 / 117 / 346) → after test-homology removal 3,197 / 178 /
4,280 → ≤ 3 sites/protein 2,699 / 163 / 3,606. Train/val proteins removed for direct edges to a test set: train
1,700 / 3,472 (ProSPECCTs 1,444, af_set 863, Vertex 266, PPI-L-test 31, TOUGH-M1-test 0); val 147 / 299; plus 53 val
proteins dropped for sharing a component with train. Positive cap per Butina ligand cluster = 300 (meets ≤ 10 % in
train/test; impossible in val with 15 clusters). Negatives = 5× positives, uniform, seeded. Top-20 CCDs (train):
HEC BGC HEM GLC ADP ATP GAL AMP FRU ANP COA SAM SAH GTP NAD XYP GDP AGS C2E IHP.

## Sensitivity to the Foldseek threshold (counts only; `split_sensitivity.json`)
| edge rule | TOUGH-M1 dev / test / excluded | BURROW train+dev proteins removed (of 7,054) |
|---|---|---|
| seq ∨ TM ≥ 0.5 (adopted) | 731 / 1,014 / 5,779 | 2,637 |
| seq ∨ TM ≥ 0.6 | 1,105 / 1,608 / 4,811 | 1,869 |
| seq ∨ TM ≥ 0.7 | 1,290 / 2,370 / 3,864 | 1,222 |
| seq ∨ TM ≥ 0.8 | 1,439 / 3,146 / 2,939 | 734 |
| seq only | 1,543 / 3,589 / 2,392 | 536 |

## Files
`homology_nodes.parquet` (node_id, dataset, uniprot, pdb_id, chain, pocket_ids, sid, seq_len, group_dataset, group_id,
global_component, …) · `homology_edges.parquet` (sid_a, sid_b, seq_edge, fident, alnlen, qcov, tcov, evalue, fs_edge,
tm_min, fs_alntm; 18.6 MB) · `homology_components.json` · `tough_m1_pockets_split.parquet` · `tough_m1_dev_pairs.parquet`
· `tough_m1_split_counts.json` · `blips_sites.parquet` (test rows without ligand columns) · `blips_{train,val}_pairs.parquet`
· `blips_split_counts.json` · `split_sensitivity.json`. Sealed (mode 000): `data/sealed/tough_m1_test_pairs.parquet`,
`data/sealed/blips_test_{pairs,sites}.parquet`. Not committed: `data/processed/homology/` (sequences, raw hits).

## D9 re-split (BLiPS train/val v2; `scripts/data/make_blips_resplit_v2.py`, built 2026-10-27 22:00)
Rule (script header, written before the first run): pool = v1 train + val sites (2,862; test-homology removal and
≤ 3 sites/protein kept, the 53 dropped v1-val proteins not restored) minus DESIGN §2.6 "< 10 BURROW points" (L-mode,
point cache `blips`); units = v1 group ids (re-checked = components of the pooled graph); 20 candidates, seed_k =
`SeedSequence(SEEDS[0]).generate_state(20)[k]`, val = first round(20 %) of permuted components; feasible = val
15–25 % of sites; choose max distinct positive pair ligand clusters in val, ties → lowest k. Pairs rebuilt with
`make_blips_split.make_pairs` unchanged (rng `SEEDS[0]`, train then val; cross-split pairs dropped); ligand
clusters reproduce v1 exactly; top-20 promiscuous list = v1 list; seen/unseen recomputed against v2 train.

| | train v2 | val v2 |
|---|---|---|
| sites / proteins / groups | 2,350 / 1,526 / 1,024 | 511 / 344 / 256 |
| from v1 train / v1 val | 2,215 / 135 | 483 / 28 |
| largest group (proteins) | 28 | 9 |
| positives (n_shared 1 / ≥ 2) | 7,186 (7,015 / 171) | 563 (553 / 10) |
| negatives | 35,930 | 2,815 |
| positive ligand clusters; max share; cap | 144; 4.2 %; 300 | **48; 9.95 %**; 56 |
| positives with a top-20 promiscuous CCD | 3,147 | 252 |
| chemotype seen / unseen (positives) | — | 550 / 13 |
Excluded (< 10 L-mode points): 1 site (v1 train); 0 without a pocket. Candidates: 20/20 feasible (val 17.9–23.4 % of
sites), 37–48 val positive clusters; chosen k = 6 (seed 574372308; val 17.9 % of sites, 256 / 1,280 components).
`verify_splits.py`: 31 new v2 checks (no component shared train↔val, no test-homologous protein, labels recomputed),
all pass. Files: `blips_sites_v2.parquet` (partition train | val | excluded_lt10; `partition_v1`, `n_lmode_points`),
`blips_{train,val}_pairs_v2.parquet`, `blips_split_counts_v2.json`.

**BLiPS-test exclusion** (`scripts/data/blips_test_exclusions.py` → `blips_test_exclusions_v2.parquet`, ids and point
counts only): 3 / 3,606 sites have < 10 holo-chain L-mode points → excluded; 13 AF-model pockets have < 10 points
(3 empty), flagged `af_lt10`. Filter the sealed test pairs by site id at final evaluation (they were not opened).
The sealed test pairs' `chemotype_seen` flag refers to v1 train; recompute against v2 train at final evaluation.
