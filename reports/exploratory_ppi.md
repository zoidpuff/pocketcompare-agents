EXPLORATORY — post-test

# PPI-R retrieval and the AFDB dimer interface-pocket atlas (2026-10-28)

Both parts use the frozen FINAL method (A4b:n1_linear) via the stored N1 parts / `pocketcompare describe`. Nothing here is
a claim. No frozen file was modified, `data/sealed/` was not opened, nothing is committed.
Scripts: `scripts/exploratory/{ppi_r.py, ppi_r_esm.py, ppi_r_diag.py, dimer_atlas_describe.sh, dimer_atlas.py,
dimer_atlas_clusters2.py}`. Results: `results/exploratory/{ppi_r,dimer_atlas}/`. Large tables: `data/processed/{exploratory/ppi_r,dimer_atlas}/`.

## A. PPI-R: do modulator pockets retrieve other families' modulator pockets?
**Protocol** (written in the docstring of `ppi_r.py` before any score was computed):
- **Queries / positives:** 1,806 PPI-L train+val modulator pockets (PLOC+PLONC, L mode) in 67 PPI-L homology groups.
- **Background:** BLiPS v2 train/val ligand pockets (L mode). 11 BLiPS proteins with a direct homology edge to any PPI-L
  chain were removed.
- **Matching:** greedy 1:1 nearest neighbour without replacement on (log L-volume, mean bur16), caliper 0.25 SD.
  - 1,272 background pockets matched.
  - |SMD| 0.06 / 0.09 after matching, against 0.04 / 0.57 before (buriedness was the imbalance).
- **Retrieval:** each query ranks all other pockets except those in its own PPI-L group.
- **CIs:** homology-group bootstrap (`evaluate.vertex_bootstrap_generic`, B = 2000).

| arm (query mean) | AUC [95 % CI] | AP | P@10 | P@50 |
|---|---|---|---|---|
| FINAL | 0.552 [0.495, 0.590] | 0.587 | 0.518 [0.423, 0.596] | 0.549 |
| N1 | 0.562 [0.503, 0.603] | 0.590 | 0.530 | 0.553 |
| B1 | 0.493 [0.436, 0.536] | 0.544 | 0.429 | 0.466 |
| B4 (ESM-2, sequence) | 0.542 [0.465, 0.596] | 0.612 | **0.736** [0.619, 0.828] | 0.726 |
| B0 size / BUR buriedness / random | 0.513 / 0.512 / 0.500 | 0.55 | 0.58 / 0.51 / 0.55 | 0.55 |

Chance for P@k is the prevalence, 0.549 (0.583 group-balanced).

**Paired differences:**
- FINAL − B1: ΔAUC +0.059 [+0.033, +0.076].
- FINAL − N1: −0.010 [−0.018, +0.001].
- FINAL − B4: ΔAUC +0.010 [−0.038, +0.072], ΔP@10 −0.22 [−0.30, −0.15].
- Group-balanced: FINAL AUC 0.536 [0.511, 0.559]; B4 0.463.
- PLOC 0.549, PLONC 0.561.

**Answer: no useful recognition of "PPI-modulator-pocket-ness" across families.**
- FINAL ranks other families' modulator pockets only slightly above size- and buriedness-matched ligand pockets
  (AUC 0.55, CI touching 0.5).
- Its top 10 are not enriched: P@10 0.52 vs prevalence 0.55.
- It beats B1, but B1 is at chance.
- **B4 enriches the top ranks (P@10 0.74), and the source is unexplained.**
  - Diagnostic added after the scores (`diag_topk_family.json`): none of B4's top-10 PPI hits share the query's Pfam,
    and 0.08 % share its ligand cluster. So remote homology and chemotype do not explain it.
  - Possible causes are the lining-residue composition of PPI grooves, or a curation difference between the Pasteur
    and BioLiP sets.
- Caveats:
  - Effectively 67 query groups, dominated by bromodomain, p38/kinase and trypsin groups (`per_group.tsv`).
  - Positives and background come from different curation pipelines.

## B. AFDB dimer interface-pocket atlas (DEMO, not an evaluation)
**Run:**
- `pocketcompare describe --af-mode` on all 15,161 dimers: 0 errors, 127,824 merged pockets (median 7 per dimer).
- **Throughput:** 347 s wall = **43.7 dimers/s** (368 pockets/s). Two shards ran on cuda:0 and cuda:1, each with 11
  CPU workers. Median 0.35 CPU-s and 9.6 GPU-ms per dimer.
- **Over-budget note:** the two GPU main processes added threads, so average CPU use was about 60 cores, not 22.
  Thread caps (`OMP_NUM_THREADS`) should be set next time.
- **Interface pockets** (f_min ≥ 0.25, ≥ 10 points): 32,473, i.e. 25 % of pockets. 86 % of dimers have at least one
  (the earlier sample gave 82.5 %).
- **FAISS indices:**
  - exact flat over the interface pockets: 0.03 s to build;
  - OPQ64 + IVF1024 + PQ64 over all pockets: 92 B/pocket, 540 s to build (OPQ training on a loaded node).
  - Tables are in `data/processed/dimer_atlas/`.

**(i) Search against known modulator pockets.**
- PPI-L includes all splits here: this is a demo, not an evaluation.
- References: 2,236 modulator pockets and 2,841 BLiPS train/val ligand pockets. Both use D mode where BURROW matched the
  site (93 % / 75 %), otherwise L mode.
- Background threshold τ = 99th percentile of interface × BLiPS pair cosines = **0.593**.
- **85 % of interface pockets (27,572) have a modulator neighbour above τ, but 93 % have one in an equal-size random
  BLiPS set.** The maximum over 2,236 references makes a pairwise p99 easy to exceed.
- **Stricter, NN-level threshold:** τ_NN = p99 of the nearest-BLiPS cosine = 0.881. Only **16 interface pockets
  (0.05 %)** exceed it for modulators. The null rate is 1 %, and non-interface pockets reach 0.18 %.
- The modulator NN beats the BLiPS NN for 31 % of interface pockets and 28 % of non-interface pockets.
- **So interface pockets are *not* closer to PPI-modulator pockets than to ordinary ligand pockets**, consistent with A.
- Of the 27,572 hits above τ, 231 are homologous to the matched modulator target and 7 are the same UniProt.

**Top examples** (best per gene pair and per target; `examples_top.tsv`, `examples_nonhomologous.tsv`):

| dimer (ipTM / ipSAE) | cos | modulator pocket (target, ligand, label) | homologous? |
|---|---|---|---|
| MYRFL–MYRFL (0.33 / 0.61) | 0.926 | 5xxg SETD (Q9H7B4) 8HR, PLOC | no (low ipTM) |
| ILM1–ILM1, yeast (0.64 / 0.61) | 0.914 | 4c52 (Q07817) X0D, PLOC | no |
| HMG2–HMG2, yeast (0.50 / 0.74) | 0.906 | 6ne5 MCL-1 (Q07820) KJP, PLOC | no |
| HSD17B11 homo (0.81 / 0.68) | 0.903 | 5csx B-Raf (P15056) 54J, PLONC | no |
| PXP1–PXP1, yeast (0.94 / 0.91) | 0.899 | 5y95 (Q62141) 8TL, PLOC | no |
| ERVK-10 homo (0.70 / 0.76) | 0.898 | 3ka2 HIV protease (P03369) 2NC | **yes: trivial** (retroviral protease) |
| OCA2–OCA2 (0.71 / 0.78) | 0.898 | 5x72 PDEδ (O43924) P69, PLOC | no |
| SEPTIN6–SEPTIN8 (0.65 / 0.61) | 0.887 | 4ca8 (Q10714) 3ES, PLOC | no |
| AP3M1–AP3B2 (0.94 / 0.86) | 0.879 | 4qp4 ERK2 (P28482) 36O, PLOC | no |
| MASP1–MASP1 (0.77 / 0.80) | 0.876 | 4jzi trypsin-like (Q9Y5Y6) N4C | flag says no, but **likely missed homology** (both trypsin fold) |

- **The homology flag is incomplete:** non-PPIPS dimer chains carry sequence edges only, with no Foldseek edges, so a
  "no" is not proof of non-homology.
- **Several cross-family top hits also have an equal or higher BLiPS NN** (e.g. PXP1 0.902, OCA2 0.905), so they are
  not modulator-specific.

**(ii) Clusters.**
- **Declared clustering** (Louvain on top-10 neighbours from other structures, with cos ≥ τ): 29 coarse communities
  (largest 6,468). The graph is nearly connected at τ = 0.59, so the clusters are uninformative.
- **Stricter rule, added after seeing the result:** mutual top-10 neighbours with cos ≥ 0.80.
  - 14,932 clusters: 12,970 singletons, 1,962 with ≥ 2 members, 150 with ≥ 10 members (44 % of pockets).
  - 45 of the large clusters are cross-family (≥ 5 chain-group families, none > 30 %).
- The largest are broad cross-family, cross-species groups:
  - #0 (1,154 pockets, 295 families): STRA6, TAP2, ABCG1, ABCB7, TPCN1, NALCN. These are mostly transmembrane
    transporter or channel dimers, with intramembrane interface cavities.
  - #1 (902, 403 families): HAPLN1, FNBP1L, GAS7, PTGES3, HSP90B1.
  - #2 (694, 265 families): PFKM/PFKP, ZNF692, NFIA.
  - `clusters_strict_top50.tsv` (full table in data/processed/dimer_atlas/)
- These groupings are geometric/chemical neighbourhoods, not validated functional classes.
- **Hubness:** large buried sites were hubs in the proteome demo, and that likely shapes these clusters too.

**Bottom line.**
- The FINAL fingerprint does not carry a transferable "PPI-modulator pocket" signal: PPI-R AUC 0.55, no P@10
  enrichment, and atlas interface pockets are no closer to modulator pockets than to ordinary ligand pockets.
- The atlas is cheap: 15 k complexes in 6 min, with a searchable index.
- Its modulator hits should be read as generic pocket-shape neighbours that need docking or expert triage, not as PPI
  druggability predictions.
