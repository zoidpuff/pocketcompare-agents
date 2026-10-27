# PPI datasets: PPI-L (Pasteur pocketome) and PPIPS (AFDB dimers), 2026-10-27

Scripts: `scripts/ppi/10–13` (PPI-L), `20–22` (PPIPS), driver `scripts/ppi/run_ppi_datasets.sh`, fetch
`scripts/data/fetch_ppi_pocketome.py`. Counts: `results/ppi/{ppil_inventory,ppil_gate,ppips_counts,ppil_b6_check}.json`.
Sealed (chmod 000, r-x dir restored): `ppi_l_test_pairs` (sha256 8a10795f…), `ppi_l_test_b6` (6abb5137…),
`ppips_test_queries` (7346812b…), `ppips_sym_test_pairs` (e7915969…). No similarity score was computed before the C3 gate was recorded.

## Verdict: C3 fails its gate and must be downgraded to exploratory
| PPI-L primary (PLOC+PLONC) | train | val | test | all groups, no split |
|---|---|---|---|---|
| pockets (homology groups) | 1,278 (49) | 528 (18) | 430 (26) | 2,236 (93) |
| cross-group positives (Tc ≥ 0.5) | 34 | 0 | **3** (2 groups, 1 cluster) | **175** (38 groups, 37 clusters) |
| negatives (Tc < 0.3) | 663,250 | 70,501 | 70,310 | 2.25 M |

- The PI gate (≥ 50 test positives, ≥ 10 groups, ≥ 5 ligand clusters) fails. So does the DESIGN v1 gate (≥ 100).
- It fails for any split, because the whole set holds only 175 cross-group positives.
- Adding PLA does not rescue it: 406 positives in total, 15 in test.
- PPI-modulator chemistry is target-specific. At Tc ≥ 0.5 there are 4,312 positive pairs within the same UniProt, 225 within the same group but a different UniProt, and 175 across groups. At Tc ≥ 0.7 only 18 cross-group pairs remain.
- The cross-group positives that do exist are mostly bromodomain/BRD4 vs p38α (31 + 28 pairs), i.e. small fragment-like or promiscuous inhibitors.
- Proposed alternative, **PPI-R** (ligand-grounded PPI-site retrieval):
  - Query = a PLOC/PLONC modulator pocket (test: 430 pockets, 26 groups).
  - Relevant = PPI-modulator pockets of other homology groups in the same split.
  - Decoys = non-PPI ligand-bound pockets from BLiPS-test / TOUGH-M1-test, with no direct homology edge to any PPI-L chain, matched to the PPI pockets on volume and buriedness (all ligand-bound, so "has a ligand" cannot be a shortcut).
  - Metric: AUC / enrichment@k, with B0 (size), B1 and B6.
  - It tests whether PPI-site character transfers across folds, not chemotype sharing. Risk: a shape-only shortcut (flat interface pockets), which the size and buriedness matching plus B0 must expose.
  - Not built. The decoy pool needs the global graph's direct edges to PPI-L chains, and PPI-L is not yet a node set there.

## PPI-L inventory (Moine-Franel 2024; 11.1 GB, md5 checked; 1.0 GB extracted)
- **Labels** (per liganded VolSite cavity):
  - PLOC = orthosteric competitive (modulator in the PPI interface pocket, competes with the partner): 2,325 cavities;
  - PLONC = orthosteric non-competitive: 817;
  - PLA = allosteric: 1,830;
  - HD = ligand-free heterodimer interface cavities: 18,266 in 4,770 PDB entries (excluded, PI round 2).
- **Ligand instances:**
  - 4,424 in total (PLOC 1,929 / PLA 1,734 / PLONC 761), on 4,005 PDB entries, 285 UniProt and 141 Pfam families (1,454 instances without Pfam);
  - 3,358 CCD ids and 3,317 distinct molecules in 1,564 Butina(0.6) chemotypes;
  - 30 % of instances are kinase / bromodomain / trypsin.
- **Primary eligible set: 2,236 pockets.** Excluded:
  - 46 L-mode failures (modified residues and covalent adducts);
  - 153 unparsable SDFs;
  - 335 with < 12 heavy atoms;
  - 187 partial SDFs (fewer than 0.8 × the heavy atoms of the HET residue);
  - 228 cofactors, additives or detergents (SAM/SAH, nucleotides, CoA esters, BNG/MA4…);
  - PLA, which is not an interface pocket.
- **Pocket table and point cache:**
  - pocket table `data/splits/ppi_l_pockets.parquet`; point cache `data/processed/cache/points/ppi_l/` (4,003 chains, 3.0 GB, 128 s on 13 workers);
  - structure = PDB mirror, ligand chain only;
  - L-mode on the HET residue (4,370), SDF fallback (5);
  - median 339 points / 581 Å³ / 25 lining residues;
  - D-mode miss 19.7 % (11.8 % of all pockets are missed by coverage but precision ≥ 0.5).
- **Homology:**
  - dataset's own graph over 4,003 chains: `leakage.apply_rule` OR Foldseek min(qTM, tTM) ≥ 0.5;
  - 157 groups; largest 969 chains (325 bromodomain pockets);
  - greedy 60/20/20 split by pocket count (seed 0).
- **B6:**
  - PSI pair distances are not in the archive. The API serves only a kNN list (~78 neighbours per cavity, no filter), so it cannot cover negatives.
  - Re-implemented as Euclidean distance on the 108 z-scored descriptors. Against 300 API records: r = 0.959, median ratio 0.999.

## PPIPS (AFDB dimers, BURROW AF mode, region rule; 1,991 complexes, 5.2 GB cache, 0 failures, ~1.1 s/dimer)
| | train | val | test |
|---|---|---|---|
| complexes (groups) | 1,472 (119) | 268 (34) | 251 (34) |
| pockets / interface pockets | 15,593 / 3,756 | 2,472 / 580 | 2,432 / 667 |
| P-sym pairs (interface) | 2,088 (425) | 366 (72) | 440 (83) |
| P-ortho queries (complex pairs; hetero/homo) | 1,088 (878; 432/656) | 95 (79; 62/33) | 229 (195; 148/81) |

- **Complexes** = the 4,039 cross-species interolog pairs at < 30 % identity, from `data/processed/dimers/orthology`.
- **Pockets** = merged region-rule pockets with ≥ 10 points; interface if f_min ≥ 0.25. Median 9 pockets and 2 interface pockets per complex.
- **P-sym:**
  - mutual-best residue-swap Jaccard ≥ 0.5 in homodimers;
  - 694 on-axis pockets excluded;
  - metric (PI round 2): percentile of the copy among the query's scores against all pockets of its split.
- **P-ortho:**
  - residues are mapped through the MMseqs2 chain alignments (homodimers: best chain orientation);
  - query = interface pocket with ≥ 50 % of residues mapped;
  - counterpart = partner-complex pocket with Jaccard ≥ 0.5 against the mapped set, computed over its alignable residues;
  - candidates = all pockets of the partner complex (median 10–11; median 1 positive);
  - median pair identity 0.27.
  - **Low yield:** of 20,693 interface-pocket × partner instances, 84.6 % map well, but only 1,412 have a Jaccard ≥ 0.5 counterpart (median best J 0.17). An overlap coefficient ≥ 0.5 would yield 8,905; that column is stored as `positives_overlap`.
- **Splits:**
  - dataset's own protein graph (1,893 proteins, 321 groups);
  - complexes are joined if they share a protein group or form an interolog pair;
  - largest component (113 complexes; hubs are rare in this subset) → train;
  - the 79 complexes containing a BURROW train/dev UniProt → train, with their components;
  - the rest greedy 60/20/20.
