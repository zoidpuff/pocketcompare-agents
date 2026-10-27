# PPI pockets in AFDB predicted dimers: BURROW characterisation (2026-10-27)

Scripts: `scripts/ppi/01–07` (run order in `scripts/ppi/run_all.sh`; ~10 min). Numbers: `results/ppi/summary.txt`,
`data/processed/dimers/{inventory_summary.txt,orthology/summary.txt,ippidb/summary.txt}`. BURROW FREEZE v2, `--af-mode`,
default preset, `all` ranker. Sample = 100 dimers per organism × type (seed `SEEDS[0]`), 600 dimers + 1,200 chains.

## Key numbers
| | value |
|---|---|
| dimer files (human/yeast/E. coli) | homo 4,819 / 648 / 1,206; hetero 5,791 / 1,250 / 1,447; **15,161 total** |
| BURROW speed, 16 CPU workers | **40 dimers/s** (322 ms/dimer single-core, 4.9k atoms), 83 monomers/s; `--min-score none` costs nothing extra |
| dimers with ≥ 1 interface pocket (f_min ≥ 0.25; default list / full list) | **82.5 %** / 96.2 % (homo 85.7 %, hetero 79.3 %) |
| interface pockets per dimer (default list) | 1.8–2.7 (26.6 % of cavity pockets) |
| interface pockets not found when the chains are run alone | **85.8 %** absent from monomer default lists; 48.8 % "PPI-created" (no monomer pocket at all in that space) vs 17.1 % for the control |
| homodimer symmetric pocket pairs (both in default list) | 2.5 per homodimer → **~15.9k pairs** over 6,673 homodimers (~4.0k involve interface pockets) |
| symmetric copy found by BURROW | 61 % (residue Jaccard ≥ 0.5), 78 % (geometric overlap) |
| cross-species interologs (MMseqs2) | 5,353 homo + 4,989 hetero complex pairs; 4,039 at < 30 % pair identity |
| disk | 506 MB (`data/processed/dimers/`), of which 280 MB extracted monomer PDBs |

## 1. Inventory
- Files are PDB with **2 chains, always `A` and `B`**, numbering contiguous from 1 (UniProt numbering). The **B-factor is per-residue pLDDT** (constant within every residue, range 1–99). pLDDT is present.
- The manifests list human entries twice (`downloaded` + `present` rows). That gives 9,638 / 11,582 rows, but there are 4,819 / 5,791 unique files. 87 entries failed to download. Every file is in `candidates.csv`.
- `DBREF` is a placeholder (`XXXX`) in 14 % of files. Use the manifest accessions.
- The minimum ipSAE is 0.600 and the minimum pDockQ2 is 0.230 across all files, which suggests these were the selection cut-offs. ipTM goes down to 0.06, and 8.6 % of human homodimers have ipTM < 0.5.
- Median size 615–770 residues per complex (max 2,749). Median interface 52–106 residues (heavy atom ≤ 5 Å).
- Median interface pLDDT 87–94. The human complexes contain much disorder: 13–16 % of residues have pLDDT < 50 (95th percentile 47–54 %). In *E. coli* this is 1–3 %.
- Heterodimers are hub-rich. Human SKP1 appears in 62 heterodimers, ELOC in 59, CUL3 in 48 and histones H4/H2A in 47/40.

## 2. BURROW on the sample
**Output lists.** The default (v2) list has 12 pockets per dimer (IQR 8–18). With `--min-score none` the list hits the 50-pocket cap in almost every dimer. 40 % of default pockets and 63 % of full-list pockets have fewer than 10 points: 750 metal-candidate singletons and 2,436 one-point surface tiles. These are excluded below. That leaves 7 [4–11] default and 18 [14–21] full cavity pockets per dimer.

**Interface definition.**
- f_min = share of lining residues on the minority chain.
- Interface if f_min ≥ 0.25, i.e. ≥ 3–4 residues of a typical 14-residue pocket. "Touching" if 0 < f_min < 0.25.
- Justification: 91 % [76–99] of an interface pocket's points have heavy atoms of *both* chains within the 6 Å shell, against 54 % for "touching" pockets.
- The f_min histogram is not cleanly bimodal, so the sensitivity is reported. Dimers with an interface pocket: 89.5 / 82.5 / 61.2 % at T = 0.10 / 0.25 / 0.40.

**Where interface pockets rank.**
- Top-1 pocket is an interface pocket in 20 % of dimers; top-3 in 43 %.
- The rate is flat across ipTM tertiles (81.5 / 82.0 / 84.0 %).
- By organism and type, between 72 % (*E. coli* hetero) and 87 % (yeast homo) of dimers have one.

**Interface vs single-chain pockets** (default list, median [IQR]):
| | score | volume Å³ | lining res | bur16 | burbb16 | escape |
|---|---|---|---|---|---|---|
| interface | 0.08 [0.05–0.16] | 98 [54–180] | 14 | 0.86 | 0.71 | 0.13 |
| single-chain | 0.09 [0.05–0.22] | 91 [51–150] | 13 | 0.84 | 0.70 | 0.15 |

Interface pockets are about as buried as single-chain pockets, but BURROW rarely gives them high confidence:

| score | ≥ 0.3 | ≥ 0.5 |
|---|---|---|
| interface | 9.9 % | 2.8 % |
| single-chain | 17.1 % | 7.1 % |

The ranker was trained on ligand sites, which are mostly single-chain. pLDDT is the same for both classes (91.6).

**Monomer comparison** (each chain cut from the dimer file, so coordinates are identical). Coverage = share of dimer-pocket points that have a monomer-pocket point within 2 Å.

The control is single-chain pockets ≥ 12 Å from the partner (n = 1,170). Only 72.7 % are recovered (best coverage ≥ 0.5), and 17.1 % have no monomer pocket at all. Recovery depends on score: 67 / 81 / 88 % for scores ≤ 0.1, 0.1–0.3 and > 0.3. **BURROW's segmentation depends on context**: protein-size and within-protein rank features, NMS, and the grid frame all change when a chain is run alone.

Score-stratified, interface pockets versus the control:

| score | interface "created" | control "created" | interface recovered | control recovered |
|---|---|---|---|---|
| ≤ 0.1 | 54 % | 23 % | 20 % | 67 % |
| 0.1–0.3 | 48 % | 8 % | 25 % | 81 % |
| > 0.3 | 21 % | 4 % | 42 % | 88 % |

- In total, 48.8 % of interface pockets are PPI-created, 27.5 % partial and 23.7 % pre-existing (homo 47.5 %, hetero 50.4 % created).
- 85.8 % are absent from the monomer *default* output.
- 57 % of dimers have at least one PPI-created interface pocket.
- Pre-existing interface pockets score higher in the dimer (0.10) than their monomer counterparts (0.04), and are more buried (bur16 0.93 vs 0.84 for created).

## 3. Homodimer symmetry
- **The chains are nearly symmetric.** CA RMSD between chains A and B is 0.10 Å (median), but 14.7 % are > 2 Å.
- **On-axis pockets.** 19.9 % of interface pockets lie on the 2-fold axis (J(S, swap S) ≥ 0.5), i.e. 0.51 per homodimer. Off-axis pockets: 2,657.
- **Symmetric copy found.** Same residue numbers on the other chain, Jaccard ≥ 0.5:
  - default list 56 %, full list 61 %, and 83 % at J ≥ 0.3;
  - by score: 57 / 62 / 71 % (≤ 0.1 / 0.1–0.3 / > 0.3);
  - interface pockets only: 54 %.
- **Geometric check.** Points are mapped by the A↔B superposition. 73.8 % have a single other pocket covering ≥ 50 % of the mapped points, and 12.9 % have no pocket at the copy site. Most misses are **different segmentation of the same site** (e.g. J 0.43, coverage 0.9), not a missing site.
- **Mutual pairs.** 748 pairs have both copies in the default list (1,318 in the full list), in 293/300 homodimers. 171 involve interface pockets. Pairs have Δscore 0.017 [0.007–0.034], J 0.75 and geometric coverage 0.97.

## 4. Proposed PPI-pocket similarity benchmark (not built)
Positives and negatives should be defined at the **site** level: residues mapped by symmetry, alignment or superposition. Methods should be scored with best-over-overlapping-pockets, because BURROW splits the same site differently 20–40 % of the time.

- **(a) Symmetric copies: invariance tier (easy).**
  - ~15.9k pairs (~4.0k interface) plus 0.5 on-axis pockets per homodimer.
  - The sequence is identical, so this tier tests robustness to segmentation and AF asymmetry, not generalisation.
  - Report it separately, and include the 15 % of homodimers with chain RMSD > 2 Å as "hard" copies.
- **(b) Cross-species interologs: main tier.** Feasible with the local MMseqs2 (18-8cc5c): 11,804 proteins, all-vs-all, E ≤ 1e-3, coverage ≥ 0.5.
  - Homodimer pairs: human–yeast 2,426, human–*E. coli* 2,228, yeast–*E. coli* 699.
  - Heterodimer pairs: 4,736, 188 and 65.
  - Median weaker-chain identity 0.25–0.47; 4,039 pairs are < 30 %.
  - Positive = interface pockets whose lining residues map through both chain alignments (mapped Jaccard ≥ 0.5). The interface itself must also be conserved (≥ 50 % of interface residues aligned, or a complex US-align check).
  - Stratify by pair identity (< 30 / 30–50 / > 50 %).
  - OMA's REST API is reachable and can separate orthologues from paralogues. The eggNOG API was unreachable. MMseqs2 alone suffices for feasibility.
- **(c) PDB PPI-inhibitor sites: external validation, small.**
  - iPPI-DB is reachable via REST (`/api/summary`, `/api/ligand`, `/api/pdb`; counts at query time: 23,238 cavities, 8,774 PDB entries, 4,424 ligand records, 5,549 proteins). The full summary pull was rate-limited (HTTP 503); 2,000 of the 23,238 cavities came through (resumable script, `--partial` summary). In that slice, 26 of 311 iPPI-DB protein pairs (8 %) are also AFDB dimers, e.g. CDK2–cyclin E, Ku70/80 and eIF4E–4E-BP1, so PDB-vs-AF comparisons of the same interface are possible for a few hundred complexes.
  - 2P2I-DB: the host resolves but does not respond. TIMBAL: no DNS (defunct).
  - Most PPI inhibitors bind a groove on one partner (single-chain "interface" pockets). True PPI-created ligand sites (molecular glues, 14-3-3 stabilisers) are rare. BURROW's own dimer benchmark (`pocket_detect/data/processed/dimer`, 400 PDB assemblies with homo/hetero-interface ligand sites, symmetric copies grouped) is a ready source of them.
- **(d) Negatives.**
  - Interface pockets from complexes with no homologous chain, matched in size and buriedness so that volume cannot solve the task.
  - Hard negatives: other pockets in the same complex, and non-equivalent interface pockets in interolog pairs.
- **Leakage.**
  - Paralogous complexes are abundant within each organism: 20.5k human homo and 83.3k human hetero homologous complex pairs (18.4k share a protein); 27.4k in *E. coli* hetero.
  - Split by connected components of complexes linked by any homologous chain (MMseqs2 or Foldseek), *before* modelling, with the test set held out.
  - Hub proteins (SKP1, CUL3, histones, 14-3-3) must stay in one split.
  - 1,671 dimer proteins are in BURROW's test union and 260 in its train/dev set; keep that in mind when BURROW scores are used as features.
  - AFDB complexes may be templated on PDB complexes, so tier (c) is not independent of the AF models.

**Recommendation.** Use (b) as the PPI test bed: cross-species interolog interface sites at < 50 % identity, split by complex-homology components. Use (a) as an invariance and sanity tier, and (c) plus BURROW's dimer set as a small external check with real ligands.

Running BURROW on all 15,161 dimers and their 30k chains takes ~15 min on 16 CPUs. Stream the monomer chains from the dimer files instead of writing them out (~7 GB of PDB text otherwise).
