# BLiPS + PPIPS preparation: D9 re-split, point caches, label-free descriptors (2026-10-27 22:20)

## Numbers
- **D9 re-split**:
  - **train v2**: 2,350 sites / 1,526 proteins / 1,024 groups; 7,186 positive / 35,930 negative pairs; 144 positive ligand clusters, max share 4.2 %.
  - **val v2**: 511 sites / 344 proteins / 256 groups; **563 positive / 2,815 negative pairs; 48 positive clusters, max share 9.95 %** (v1 val: 163 sites, 15 clusters, max share 59 %).
  - Val holds 17.9 % of sites and 256 of 1,280 components. All 20 candidates were feasible (val 17.9–23.4 % of sites, 37–48 clusters); the rule chose k = 6.
  - Val seen / unseen chemotype: 550 / 13 positives.
  - `verify_splits.py`: 97 PASS, 0 FAIL, including 31 new v2 checks (no component shared between train and val, no test-homologous protein, labels recomputed).
- **< 10 BURROW-point exclusion**: v1 train 1 site, v1 val 0 (applied before the v2 pairs were built); test 3 / 3,606 (holo pocket). 13 AF pockets are flagged (`af_lt10`, 3 of them empty).

**Point caches** (24 workers; `scripts/build_point_cache.py`):

| dataset | sites ok | structures | wall | s/structure p50 | disk | L-mode points / Å³ p50 | D missed (cov < 0.3) / no match* |
|---|---|---|---|---|---|---|---|
| `blips` (train+val) | 2,862 / 2,862 | 1,871 | 50 s | 0.47 | 1.9 GB | 214 / 635 | 44.9 % / 24.7 % |
| `blips_test_holo` | 3,606 / 3,606 | 2,768 | 69 s | 0.48 | 3.0 GB | 315 / 662 | 40.4 % / 21.3 % |
| `blips_test_af` (af_mode) | 3,603 / 3,606 | 2,304 | 76 s | 0.60 | 3.7 GB | 294 / 600 | 43.1 % / 23.3 % |

\*"No match" = coverage < 0.3 and precision < 0.5. TOUGH-M1 is 19.4 % / 5.5 %, so BLiPS sites are much harder for D-mode, which matters for the D11 objective. AF failures: 3 empty L-mode pockets. Across sites, holo and AF L-mode sizes correlate at r = 0.87.

**Descriptors** (0 failed rows):
- A1 ×16, B1 ×2 and B0 in L and D mode for the three BLiPS caches; D only for PPIPS (20,497 merged pockets).
- Wall time: A1 70–120 s per dataset on 23 workers. Disk 1.0 GB.
- A1 default per-pocket time, median / p90: L 7.3 / 17.5 ms (BLiPS), 9.1 / 22.2 ms (holo); D on PPIPS 2.3 / 5.1 ms.
- Every A1 config has an L-mode median ≤ 11.3 ms (no_resample; p90 90 ms), so all 16 configs were computed. The PPIPS `no_resample` D-mode maximum is 7.2 s for one giant pocket.

**B4 ESM-2** (cuda:1; 0 errors):

| dataset | pockets with L / D | new sequences | wall |
|---|---|---|---|
| BLiPS | 2,862 / 2,862 | 1,682 | 175 s |
| holo | 3,606 / 3,606 | 2,505 | 362 s |
| AF | 3,602 / 3,603 | 2,273 | 109 s |
| PPIPS | D 20,497 | 1,661 | 78 s |

- The one missing AF L vector is the 2-point pocket.
- The ESM cache grew from 5.5 to 14 GB.

## Definitions and decisions (not dictated by DESIGN)
1. **The re-split pool is v1 train + val minus the < 10-point sites.** The exclusion was applied before pairing, so the v2 pair caps are computed on eligible sites only. The 53 v1-val proteins dropped for sharing a component with train were not restored. The top-20 promiscuous list is kept from v1. `chemotype_seen` is recomputed against v2 train; the sealed test flag still refers to v1 train.
2. **L-mode ligands**: the union of all instances whose CCD is in the site's qualifying set (`q_ccds`, which defines the labels), not just `label_ccd`. For train/val, the label-ligand-only alternative is stored as `alt_*` (median Jaccard 1.0).
3. **Test holo chain**:
   - 2,632 sites use the LIGYSIS representative chain.
   - 761 sites have no representative chain and use the source chain of their first qualifying instance.
   - 213 sites use that source chain as a fallback, because every instance re-transferred onto the representative chain had RMSD > 2 Å.
   - Ligands are re-transferred with Track C's `transfer_instance` (site-Cα Kabsch, ≤ 2 Å).
4. **Test AF ligands**: transferred instances with RMSD ≤ 2 Å. For 303 sites, the lowest-RMSD instance is used instead (`lig_fallback`).
5. **Clashes in test ligands.** In test, 29 % of holo sites and 55 % of AF sites have a ligand atom < 2 Å from protein (train/val: 1 site), because Track C transfer has no clash filter. L-mode only counts solvent points, but these sites are flagged via `ligand_protein_min_dist`.
6. **Sealed file reads.** `blips_test_sites.parquet` was opened 3 times (columns: site_id, protein, structure_id, site_name, pdb_id, chain, q_ccds; the first run crashed and the second added the fallback) and was 000 again after each read. `blips_test_pairs` was never opened. Test tables and caches carry no CCD codes.
7. **PPIPS pockets** are the PPI agent's merged region-rule pockets (≥ 10 points), D mode only; ESM uses their BURROW residues.
