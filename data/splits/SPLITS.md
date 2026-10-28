# SPLITS — homology graph, TOUGH-M1 dev/test, BLiPS train/val/test, PPIPS (rebuilt 2026-10-28 after audit D15)

Rebuild everything: `bash scripts/data/run_splits.sh` (≈ 1.5 h, 24 threads; seed `SEEDS[0]` = 0). Checksums:
`SHA256SUMS.txt` (sealed files: hash recorded at write time). Verification: `scripts/data/verify_splits.py`
(101 checks, 0 failures; log `logs/verify_splits.log`). Units moved vs the pre-audit commit: `split_changes.json`.

## D15 rebuild (audit `reports/audit_splits.md` FAILED with small leaks) — what changed
- MMseqs2 `search -a`: exact `fident`/`alnlen` (the score-based estimate without backtraces was too low near 30 %).
  Rule edges 1.02 M → 1.21 M.
- Foldseek **exhaustive** all-vs-all (`--exhaustive-search 1`, `-e 10`, `-a`, no prefilter) on 26,819 structures
  (every non-dimer chain + the PPIPS dimer chains; the other 8,781 AFDB-dimer sequences, used by no split, keep
  sequence edges only). 57.3 M hits. TM rule: exact TM (`--exact-tmscore 1`) for all 1.98 M hits with approximate
  min-TM in [0.45, 0.60); approximate min-TM ≥ 0.60 accepted (exact is ~0.01 below approximate; validation: 20,000
  random such pairs, all exact ≥ 0.5, minimum 0.559). Edge iff min(qTM, tTM) ≥ 0.5 either direction.
- The 45 af_set proteins without a single AFDB model are now sequence-only nodes (UniProt sequence).
- All audit example edges are present (1ecmA–3ret_B TM 0.83; 2qiaA–6uec_A id 0.327; 2qo3A–FASN 0.316;
  4xg0A–5dmhA 0.341; 3remA–1ecmA 0.81; 3nmxB–APC 0.966).
- BLiPS builder bug fixed: the ≤ 3 sites/protein tie-break used one permutation over ALL sites, so train/val changes
  re-drew TEST sites. Now: the committed first-build selection is frozen (`blips_site_selection_frozen.txt`), new
  proteins use a per-site stable key, and each partition has its own pair generator `default_rng([SEEDS[0], k])`.
  BLiPS-test sites are identical to before (caches/descriptors valid); test pairs were re-sampled (sealed, unopened).
- BLiPS v2 (D9): 128 re-admitted v1 train/val sites are not in the BLiPS point cache (not extended here) →
  `excluded_not_cached` (extend the cache and rerun `make_blips_resplit_v2.py` to include them). The component
  guard now requires only that no pooled component spans two v1 groups (1 v1 group falls into 2 pooled pieces;
  it stays one unit).
- PPIPS (`scripts/ppi/21_ppips_homology.py`): Foldseek exhaustive with exact TM over EVERY chain model of every
  complex (3,982 models; the audit leak was between two AF models of the same UniProt pair); 22 re-run unchanged.

**Units moved vs the pre-audit commit** (`split_changes.json`):
| split | moved / total | transitions |
|---|---|---|
| TOUGH-M1 pockets | 254 / 7,524 | dev→test 16, test→dev 17, dev→excl 20, excl→dev 53, test→excl 58, excl→test 90 |
| BLiPS v1 sites (proteins) | 148 (110) | removed→train 119 (84), removed→val 9 (7), train→removed 17 (17), val→removed 3 (2); test 0 |
| BLiPS v2 sites | 972 / 2,970 | train→val 421, val→train 403 (new candidate k = 5 under the unchanged D9 rule), new not-cached 128, out of pool 20 |
| PPIPS complexes | 681 / 1,991 | train↔val/test reshuffle (PPIPS groups 321 → 326 re-permute the 60/20/20 rule) |
The D9 and PPIPS rules permute components, so any change of the component set redraws the assignment; a
minimal-move variant (keep previous assignments, move only components with a new cross-split edge) would move ~1
PPIPS complex and only the affected v2 groups — not applied (rules unchanged as instructed); PI decision.

## Rules (DESIGN §2.1 + design round 2)
- **Edge** = `pocketdetect.datasets.leakage.apply_rule` verbatim on exact MMseqs2 alignments (-s 7.5, -a, E < 1e-3,
  fident ≥ 0.30, qcov or tcov ≥ 0.5 or alnlen ≥ 80) **or** exhaustive Foldseek min(qTM, tTM) ≥ 0.5 (exact TM in the
  uncertain band). Identical sequences are always linked (shared `sid`).
- **Groups** = connected components of each dataset's own graph. **Exclusion across datasets** uses DIRECT edges only.
- Sealed test sets: ProSPECCTs, Vertex, BLiPS-test (= all af_set proteins), PPI-L-test (`ppi_split == test`),
  TOUGH-M1-test (for BLiPS).

## Homology graph
| | value |
|---|---|
| nodes (chains) | 65,437: dimers 30,322 · Vertex 9,212 · TOUGH-M1 7,524 · BURROW train 6,475 / dev 579 / assembly partners 2,634 · af_set 3,518 (45 sequence-only) · ProSPECCTs 3,041 · PPI-L 2,132 |
| unique sequences / Foldseek structures | 35,695 / 26,819 |
| edges (sid pairs) | 2,819,816: MMseqs2 rule 1,209,243; Foldseek 2,492,135; Foldseek-only 1,610,573 |
| largest within-dataset component (gate ≤ 10 %) | TOUGH-M1 280 = 3.7 % ✓ · ProSPECCTs 6.6 % ✓ · **BLiPS (train+dev+af) 10.6 % ✗ (marginal)** · **Vertex 25.3 % ✗** · **dimers 18.9 % ✗** |
| global component (information only) | 29,430 / 65,437 = 45.0 % |
Vertex and dimers are not split here (Vertex is a fixed sealed test; PPIPS uses its own groups). The BLiPS gate is
on the pooled train+dev+af graph; BLiPS partitions are source-defined and their own largest groups are 1.3 % (train),
1.9 % (val), 25.8 % (test). DataSAIL-style splitting is the proposed fix if any of these must be split further.

## TOUGH-M1 (dev = BURROW-homologous, test = BURROW-clean, excluded = touches BURROW AND a sealed set)
| partition | pockets | groups | ligand clusters | pos pairs | neg pairs |
|---|---|---|---|---|---|
| dev | 765 | 505 | 291 | 3,450 | 7,124 |
| test (sealed pairs) | 1,045 | 536 | 315 | 10,160 | 14,177 |
| excluded | 5,714 | 481 | 1,065 | (316,427) | (291,107) |
419,481 cross-partition pairs dropped. Excluded pockets touching ProSPECCTs 4,520 · af_set 3,890 · Vertex 1,542 ·
PPI-L-test 209 (overlapping). Ligand cluster = Butina(Tc ≥ 0.6) on ECFP4 of the shipped ligand SDF.
Dev/test pair tables carry the shipped APoc (2 numeric columns), G-LoSA (1) and SiteEngine (3) scores in file order
(`apoc_c1…`; semantics as in the OSF files); 100 % of pairs matched. (The sealed pair file was read by
`make_tough_m1_split.py` again for this rebuild; counts only were printed; all sealed/raw files back to mode 000.)

## BLiPS (v1)
| | train | val | test (sealed) |
|---|---|---|---|
| sites / proteins / groups | 2,801 / 1,839 / 1,226 | 169 / 104 / 97 | 3,606 / 2,304 / 849 |
| largest group (proteins) | 24 (1.3 %) | 2 (1.9 %) | **595 (25.8 %)** |
| positives (n_shared 1 / ≥ 2) | 8,256 (8,089 / 167) | 343 (339 / 4) | 6,919 (6,637 / 282) |
| negatives | 41,280 | 1,715 | 34,595 |
| positive ligand clusters; max share | 189; 3.6 % | 16; **57.4 %** | 227; 4.3 % |
| positives with a top-20 promiscuous CCD | 3,121 | 319 | 1,828 |
| chemotype seen / unseen (positives) | — | 343 / 0 | 6,288 / 631 |
| site clusters unseen in train | — | 25 | 1,472 |
Site funnel (train / val / test sites): all 13,640 / 1,221 / 10,341 → ≥ 1 qualifying ligand 5,768 / 491 / 4,280 (ion-only
5,014 / 416 / 4,026; additive 1,873 / 197 / 1,491; < 10 HA 966 / 117 / 346) → after test-homology removal 3,304 / 184 /
4,280 → ≤ 3 sites/protein 2,801 / 169 / 3,606. Train/val proteins removed for direct edges to a test set: train
1,633 / 3,472 (ProSPECCTs 1,392, af_set 790, Vertex 237, PPI-L-test 29, TOUGH-M1-test 0); val 145 / 299; plus 50 val
proteins dropped for sharing a component with train. Positive cap per Butina ligand cluster = 300 (meets ≤ 10 % in
train/test; impossible in val with 16 clusters). Negatives = 5× positives, uniform, seeded. Top-20 CCDs (train):
HEC BGC HEM GLC ADP ATP GAL AMP FRU SAM ANP COA SAH GTP NAD XYP RAM GDP AGS C2E (v2 keeps its own frozen v1 list).

## Sensitivity to the Foldseek threshold (counts only; `split_sensitivity.json`)
| edge rule | TOUGH-M1 dev / test / excluded | BURROW train+dev proteins removed (of 7,054) |
|---|---|---|
| seq ∨ TM ≥ 0.5 (adopted) | 765 / 1,045 / 5,714 | 2,511 |
| seq ∨ TM ≥ 0.6 | 1,092 / 1,519 / 4,913 | 1,884 |
| seq ∨ TM ≥ 0.7 | 1,260 / 2,228 / 4,036 | 1,238 |
| seq ∨ TM ≥ 0.8 | 1,371 / 2,823 / 3,330 | 758 |
| seq only | 1,429 / 3,115 / 2,980 | 568 |

## PPIPS — BURROW homology flag (stratification only; membership NOT changed)
`ppips_burrow_homology.parquet` (`scripts/data/ppips_burrow_flags.py`): per complex, a direct edge (MMseqs2 rule, or
exhaustive Foldseek exact min-TM ≥ 0.5 over every chain model) to a BURROW train/dev representative chain
(`burrow_rep_edge`, split into `_seq_edge`/`_fs_edge`), to an assembly-partner chain (`burrow_partner_edge`), or either
(`burrow_any_edge`). Report PPIPS val/test stratified by `burrow_rep_edge`.
| split | complexes | burrow_rep_edge (seq / fs) | burrow_partner_edge | burrow_any_edge |
|---|---|---|---|---|
| train | 1,483 | 1,076 (351 / 1,046) | 410 | 1,121 |
| val | 257 | **125** (37 / 115) | 6 | 129 |
| test | 251 | **136** (24 / 135) | 75 | 159 |
Cross-check: on the pre-rebuild PPIPS membership this rule reproduces the audit's structural counts (test 185 / 185,
val 176 / 177; the one difference has E = 9.96 at the cut-off); the lower counts above reflect the new membership.

## Files
`homology_nodes.parquet` (node_id, dataset, uniprot, pdb_id, chain, pocket_ids, sid, seq_len, group_dataset, group_id,
global_component, …) · `homology_edges.parquet` (sid_a, sid_b, seq_edge, fident, alnlen, qcov, tcov, evalue, fs_edge,
tm_min, fs_alntm; 19.8 MB, git-ignored) · `homology_components.json` · `tough_m1_pockets_split.parquet` · `tough_m1_dev_pairs.parquet`
· `tough_m1_split_counts.json` · `blips_sites.parquet` (test rows without ligand columns) · `blips_{train,val}_pairs.parquet`
· `blips_split_counts.json` · `blips_site_selection_frozen.txt` · `split_sensitivity.json` · `split_changes.json` ·
`ppips_burrow_homology.{parquet,json}`. Sealed (mode 000): `data/sealed/tough_m1_test_pairs.parquet`,
`data/sealed/blips_test_{pairs,sites}.parquet`. Not committed: `data/processed/homology/` (sequences, raw hits).

## D9 re-split (BLiPS train/val v2; `scripts/data/make_blips_resplit_v2.py`, built 2026-10-27 22:00, rebuilt D15)
Rule (script header, written before the first run): pool = v1 train + val sites (D15: 2,970; test-homology removal and
≤ 3 sites/protein kept, the 50 dropped v1-val proteins not restored) minus DESIGN §2.6 "< 10 BURROW points" (L-mode,
point cache `blips`); units = v1 group ids (re-checked: no pooled component spans two groups); 20 candidates, seed_k =
`SeedSequence(SEEDS[0]).generate_state(20)[k]`, val = first round(20 %) of permuted components; feasible = val
15–25 % of sites; choose max distinct positive pair ligand clusters in val, ties → lowest k. Pairs rebuilt with
`make_blips_split.make_pairs` unchanged (rng `SEEDS[0]`, train then val; cross-split pairs dropped); ligand
clusters reproduce v1 exactly; top-20 promiscuous list = v1 list; seen/unseen recomputed against v2 train.

| | train v2 | val v2 |
|---|---|---|
| sites / proteins / groups | 2,318 / 1,501 / 1,009 | 523 / 350 / 252 |
| from v1 train / v1 val | 2,185 / 133 | 496 / 27 |
| largest group (proteins) | 21 | 9 |
| positives (n_shared 1 / ≥ 2) | 6,992 (6,836 / 156) | 462 (453 / 9) |
| negatives | 34,960 | 2,310 |
| positive ligand clusters; max share; cap | 139; 4.3 %; 300 | **52; 9.96 %**; 46 |
| positives with a top-20 promiscuous CCD | 2,987 | 254 |
| chemotype seen / unseen (positives) | — | 441 / 21 |
D15 rebuild: excluded (< 10 L-mode points) 1 site; not in the point cache 128 (`excluded_not_cached`); 0 without a
pocket. Candidates: 20/20 feasible (val 17.5–21.7 % of sites), 36–52 val positive clusters; chosen k = 5 (val 18.4 %
of sites, 252 / 1,261 components). Files: `blips_sites_v2.parquet` (partition train | val | excluded_lt10 |
excluded_not_cached; `partition_v1`, `n_lmode_points`), `blips_{train,val}_pairs_v2.parquet`, `blips_split_counts_v2.json`.

**BLiPS-test exclusion** (`scripts/data/blips_test_exclusions.py` → `blips_test_exclusions_v2.parquet`, ids and point
counts only): 3 / 3,606 sites have < 10 holo-chain L-mode points → excluded; 13 AF-model pockets have < 10 points
(3 empty), flagged `af_lt10`. Filter the sealed test pairs by site id at final evaluation (they were not opened).
The sealed test pairs' `chemotype_seen` flag refers to v1 train; recompute against v2 train at final evaluation.
