# Public pocket-similarity benchmarks: acquisition report (2026-10-27)

Fetch scripts: `scripts/data/fetch_{prospeccts,tough_m1,vertex,tough_c1,klifs}.py`. They are idempotent, check sha256 (and md5 where the host publishes one) and write `data/raw/<name>/MANIFEST.json`. Loaders are in `src/pocketcompare/datasets/`. Rebuild with `scripts/data/build_benchmarks.py`, then summarise with `scripts/data/check_benchmarks.py`, which writes `results/benchmarks/benchmark_counts.json`. Output tables: `data/processed/benchmarks/<name>_{pairs,pockets}.parquet`. Tests: `tests/test_datasets.py` (4 pass). Licences and checksums are in DATA.md.

## Counts vs. papers
| set | pockets | pos | neg | paper pos/neg | match |
|---|---|---|---|---|---|
| ProSPECCTs P1 identical | 326 | 13,430 | 92,846 | 13,430/92,846 | yes |
| P1.2 similar ligands | 45 | 241 | 1,784 | 241/1,784 | yes |
| P2 NMR | 329 | 7,729 | 100,512 | 7,729/100,512 | yes |
| P3 decoy physchem (all; n_sub=5) | 1,956; 652 | 13,430 | 67,150; 13,430 | 13,430/67,150; 13,430/13,430 | yes |
| P4 decoy shape (all; n_sub=5) | 1,956; 652 | 13,430 | 67,150; 13,430 | same as P3 | yes |
| P5 Kahraman w/o phosphate; P5.2 full | 80; 100 | 920; 1,320 | 5,480; 8,680 | 920/5,480; 1,320/8,680 | yes |
| P6 Barelier; P6.2 with cofactors | 115 | 19 | 43 | 19/43 | yes |
| P7 review | 1,151 | 115 | 56,284 | 115/56,284 | yes |
| TOUGH-M1 | 7,524 | 505,116 | 556,810 | 505,116/556,810 | yes |
| Vertex, pocket pairs | 6,218 (6,029 PDB) | 1,461,669 | 102,935 | 1,461,668/102,935 (DeeplyTough) | **pos off by 1** |
| Vertex, protein pairs | 490 UniProt | 6,598 | 379 | 6,598/379 | yes |
| TOUGH-C1 (classes, no pairs) | 1,553 nuc / 596 heme / 69 ster / 1,946 ctrl | – | – | same | yes |

The Vertex +1 is explained by DeeplyTough's parser (`if i > 1`), which skips the header **and the first data row**. The raw file has 1,461,669 positives; the table was not altered. KLIFS: 14,917 structures (7,382 PDB, 371 kinases), metadata only; 112 of them have pocket strings that are not 85 characters long.

## Failures / not obtained
- The original ProSPECCTs URL returns 404. The same form is still served on the `www.ewit.ccb…` host. The download needs a license click-through, which the fetch script accepts. **The license forbids redistribution**, so the raw ProSPECCTs files must never be committed. Also, `README.txt` is returned with the HTML page appended.
- pubs.acs.org returns 403 to scripts. The Vertex SI was taken from ACS's own figshare mirror instead.
- LIGYSIS is distributed only as Python pickles, which are unsafe to load. It is a site-prediction set, so it was not fetched.
- PoSSuM has no bulk download. Not fetched.
- KLIFS residue numbers were not fetched; they need about 15k per-structure API calls.

## Pitfalls
- **ProSPECCTs pair lists** are ordered all-vs-all lists that include the diagonal. Self-pairs count as actives: 326 in P1, and **49 of the 115 P7 actives**, leaving only 66 literature pairs. Evaluate both with and without `is_self`.
- **Ligand in pocket files.** Every ProSPECCTs PDB contains exactly one `LIG` residue (that is the pocket definition), so it must be stripped before any descriptor is computed. TOUGH ligands are in separate files. Barelier P6 files keep DNA as HETATM; P6.2 keeps cofactors (NAP, HEM…).
- **Decoys.** The CSV is shared by P3 and P4. Decoy names encode `<group><n_substitutions><idx><chain>`; this was verified against residue diffs. `decoy/decoy_structures/` is an undocumented third decoy set (all 1,630 decoys differ from the rational ones). DeeplyTough loads it as P3, and its code expects `decoy_structures5.csv` and `kahraman_structures80.csv`, which are not in the current archives.
- **P5** (phosphate removed) is derived by us: LIG = 1 P + 4 O, giving 20 sites. It reproduces the paper's 920/5,480 exactly.
- **TOUGH-M1.** Structures are renumbered from 1 and set to chain A, so pocket residue lists do **not** use PDB numbering. The pocket is the fpocket pocket chosen by best overlap with the ligand; 316 have MCC < 0.5. Pairs appear in one orientation only. The OSF file `TOUGH-M1_dataset.info` actually describes TOUGH-M2.
- **Vertex.** Labels are defined at UniProt-pair level, and the benchmark scores each protein pair by the max over its pocket pairs. 139,762 pocket pairs appear in both orientations. Pocket = PDB + site index + HET code, and the specific ligand instance is not given: 627 site indices exceed the number of HET copies in the mirror, and 29 HET codes are absent.
- **The local PDB mirror was being synced (rsync, alphabetical) while this work ran.** At 18:55 the 75 directories `xx`…`zz` were empty; by 19:05 only 26 were. Missing PDB IDs at the 18:55 snapshot: ProSPECCTs 66, TOUGH-M1 353, Vertex 205, TOUGH-C1 181, KLIFS 310. Most were in the empty directories; 6–43 per set are probably obsolete entries (e.g. 1qla, 3ake). ProSPECCTs and TOUGH ship their own structures, so this only matters for Vertex (188 of 6,029 still missing at 19:05). **Re-run `build_benchmarks.py` + `check_benchmarks.py` after the sync finishes** to refresh `in_pdb_mirror` and `structure_path`. Obsolete IDs need RCSB/PDBe obsolete archives.
- **Cross-benchmark PDB overlap (leakage risk):** TOUGH-M1∩TOUGH-C1 2,611; Vertex∩KLIFS 1,675; ProSPECCTs∩TOUGH-M1 355; ProSPECCTs∩Vertex 320.

## Disk
ProSPECCTs 2.4 GB, TOUGH-M1 4.4 GB, TOUGH-C1 0.96 GB, Vertex 0.19 GB, KLIFS 10 MB, parquet tables 26 MB. **Total about 8 GB.** The DeeplyTough Vertex copy (12 GB extracted) was deleted after inspection.
