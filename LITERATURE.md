# LITERATURE.md — binding-pocket similarity: methods, benchmarks, numbers, pitfalls

Scope: prior art for a **fast, sequence- and fold-independent pocket similarity method** built on BURROW
(`/cluster/project/beltrao/gmagnus/pocket_detect`), intended for AFDB-scale search (~200 M structures),
off-target / repurposing, function annotation, and **pockets at protein–protein interfaces** (we hold AFDB
predicted homo/heterodimers). Companion docking engine: ADock, Vina-family GPU, ~0.1–0.2 s per ligand–pocket.

**Verification convention.** Every number is tagged with where it was read.
- **[P]** read by me directly in the primary full text (PDF/PMC/BioC) during this review, on 2026-10-27.
- **[S]** secondary — quoted by another paper (source named), not read in the originating paper.
- **[U]** unverified: I could not open a primary source. Treat as a lead, not a fact.
URLs marked "(200)" were checked with `curl -sIL` on 2026-10-27 and returned HTTP 200 from this container.
**Nothing here is invented.** Where I could not confirm something the brief asked for, it says so explicitly
(see §9).

---

## 1. Taxonomy of pocket representations and comparison schemes

Five families, ordered by what they cost per comparison. The runtime column is the single most useful axis for
us: at AFDB scale, an O(n²) alignment at 10 ms/pair is 10⁹ core-seconds for 10⁵ pockets; a fixed-length vector
with cosine distance is a BLAS call.

### 1.1 Alignment-based (geometric / graph / clique / hashing)

Explicitly put two pockets in correspondence; return an alignment + score. Most accurate on hard pairs,
slowest, and generally not indexable.

| Method | Representation | Matching | DOI |
|---|---|---|---|
| Cavbase | pseudocentres on cavity surface | Bron–Kerbosch clique | 10.1016/S0022-2836(02)00811-2 |
| SiteEngine | physicochemical pseudocentres + surface patches | geometric hashing of triangles, then surface scoring | 10.1016/j.jmb.2004.04.012; server 10.1093/nar/gki482 |
| **I2I-SiteEngine** | *both halves of a PPI interface* | simultaneous alignment of two interface sides | 10.1007/978-3-540-30219-3_17 |
| SiteAlign | cavity projected on an 80-triangle sphere, residue-property fingerprint per triangle | rotational search over sphere orientations | 10.1002/prot.21858 |
| ProBiS | protein-surface graph | maximum clique local structural alignment | 10.1093/bioinformatics/btq100 |
| APoc | pocket-lining residues | iterative DP + assignment problem (order-independent); PS-score | 10.1093/bioinformatics/btt024 |
| G-LoSA | local structure fragments | iterative maximum clique + fragment superposition; GA-score | 10.1021/ci4003602 |
| IsoMIF | grid molecular interaction fields, 6 probes | clique matching of MIF nodes | 10.1021/acs.jcim.5b00333 |
| Grim | interaction-pseudoatom graph (needs bound ligand) | clique matching | 10.1021/ci300566n |
| SMAP | Cα geometric potential | order-independent profile–profile alignment | 10.1073/pnas.0704422105 |
| VolSite/Shaper | pharmacophore-annotated cavity grid points | shape (Gaussian) alignment | 10.1021/ci300184x |
| SiteHopper | surface patches, shape + colour | superposition | 10.1186/1758-2946-6-S1-P57 |
| ProCare | pharmacophore-annotated point cloud | point-cloud registration (computer vision, ICP refinement) | 10.1021/acs.jmedchem.0c00422 |
| FLAPP | pocket atoms | compiled clique matching | 10.1021/acs.jcim.2c00967 |
| SiteContext | per-atom spherical histograms | Sinkhorn-approximated Earth Mover's Distance (optimal transport) | 10.1016/j.jmb.2026.169791 |
| PDBspheres | >2 M ligand-centred PDB "spheres" | LGA structural alignment + all-atom scoring | 10.1093/nargab/lqac078 |
| eMatchSite | residue features | order-independent alignment | 10.1371/journal.pcbi.1003829 |
| iAlign / IS-score | **PPI interface contacts** (<4.5 Å heavy-atom across chains) | iTM-score + side-chain contact similarity | 10.1093/bioinformatics/btq404 |

**Runtime, from ProSPECCTs Table 6** [P] (Ehrt et al. 2018, read verbatim from the PMC BioC text). One core,
dataset 5 = 100 Kahraman structures, 10,000 all-vs-all comparisons. Columns: preparation (s, all 100
structures) / comparison (s) / **average per comparison (s)**. Numbers in brackets in the paper denote
successfully prepared structures or actual comparisons when a tool failed on some inputs.

| Method | basis | prep [s] | compare [s] | **s / comparison** |
|---|---|---|---|---|
| PocketMatch | distance lists | 28.97* | 0.28 | **0.000028** |
| KRIPO | fingerprint | 446.50 | 0.92 | **0.000092** |
| RAPMAD | histogram | 71.42 | 2.36 (8,281) | **0.000285** |
| FuzCav | fingerprint | 399.88 (96) | 5.59 (9,216) | **0.000607** |
| FuzCav (PDB) | fingerprint | 236.73 (96) | 5.64 (9,216) | 0.000612 |
| TM-align | matrix | 25.72* | 65.96 | **0.006596** |
| Shaper (PDB) | grid points | 181.16 (96) | 364.42 (9,216) | 0.039542 |
| Shaper | grid points | 384.21 (96) | 367.21 (9,216) | 0.039845 |
| VolSite/Shaper | grid points | 537.00 (76) | 248.77 (5,776) | 0.043070 |
| ProBiS | graph | 6.95 | 479.32 | **0.047932** |
| VolSite/Shaper (PDB) | grid points | 259.54 (57) | 162.26 (3,249) | 0.049942 |
| TIFP | fingerprint | 228.30 (77) | 550.88 (5,929) | 0.092913 |
| Grim | graph | 220.17 (95) | 2,104.99 (9,025) | 0.233240 |
| IsoMIF | graph | 752.83 | 2,561.44 | **0.256144** |
| SiteHopper | 3D points | 154.01 | 3,828.61 | 0.382861 |
| Cavbase | graph | 67.89 (100) | 21,823.71 (8,281) | **2.635396** |
| SMAP | graph | 1.69 | 42,346.74 | 4.234674 |
| SiteEngine | 3D points | 328.81 | 81,193.54 | **8.119354** |
| SiteAlign | fingerprint (sphere) | 28.97* | 286,326.41 | **28.632641** |

\* exemplary preparation times for tools that require user-defined cavities.
The paper's own framing [P]: one query against all of sc-PDB (9,283 entries) takes **0.28 s with PocketMatch
and about three days with SiteAlign**; for all-vs-all, **RAPMAD is ~9,200× faster than Cavbase**. Note
SiteAlign is listed as "fingerprint" but its cost comes from the rotational search — it is effectively an
alignment method, and it is the top-ranked method on ProSPECCTs (§3). **Accuracy and speed are anti-correlated
in this table**; closing that gap is our opening.

Other published runtimes: APoc ≈ 37 ms/pair (73 s for 2,000 comparisons, excluding input prep) vs SiteEngine
8,983 s for the same 2,000 [S, APoc paper]. FLAPP 12.5 ms/pair on one core, ~1 ms on 12 cores [S, abstract].
SiteMine ~3 min against a 10,000-pocket database ⇒ ~55 comparisons/s [S, developer page]. G-LoSA was *omitted*
from DeeplyTough's Vertex evaluation because it would have taken "hundreds of days on a single processor" [P].

### 1.2 Alignment-free fingerprints, histograms, sketches

Fixed-length (or set-valued) descriptors compared by Tanimoto/cosine/Euclidean. Microseconds per comparison,
indexable. This is the family BURROW's 76 descriptors + 84 per-point features naturally belong to.

- **PocketMatch** (10.1186/1471-2105-9-543): 90 sorted lists of pairwise distances between residue-type-labelled
  points. 28 µs/comparison [P, ProSPECCTs Table 6].
- **FuzCav** (10.1021/ci900349y): 4,833-integer count vector of pharmacophoric Cα triplets. 0.6 ms [P].
- **RAPMAD** (10.1021/ci5005898): distance histograms from Cavbase pseudocentres to reference points; linear
  time. 285 µs [P]. Depends on Cavbase (commercial) for the pseudocentres.
- **KRIPO** (10.1021/ci3000776): **subpocket** three-point pharmacophore fingerprints derived from *bound ligand
  fragments*; modified Tanimoto. 92 µs [P]. Requires a holo structure — a hard blocker for AFDB.
- **TIFP** (10.1021/ci300566n): 210-integer interaction-triplet fingerprint; also ligand-dependent.
- **PoSSuM** (10.1093/nar/gkr1130; v2.0 10.1093/nar/gku1144; v3 10.1021/acs.jcim.3c01405): random-projection
  bit sketches + multiple sorting (SketchSort) for **all-pairs search at database scale**. The canonical
  LSH precedent for exactly our problem.
- **3D Zernike** (Kihara lab): Pocket-Surfer 10.1002/prot.22715, Patch-Surfer 10.1186/1471-2105-13-S2-S7;
  rotation-invariant moment descriptors, seconds-to-minutes database searches [S]. 3D-AF-Surfer
  (10.1038/s42003-022-03261-8) applies Zernike at AlphaFold scale but on **whole structures**, not pockets.
- **KiSSim** (10.1021/acs.jcim.2c00050): uses the fixed 85-residue KLIFS kinase pocket, so no alignment is
  needed at all. Kinase-only; conda-forge, MIT.
- **BSSF** (10.1186/1471-2105-11-47): fingerprint + Z-score; ~1 min per query against 188,959 sites [S].

### 1.3 Learned embeddings (vector-search compatible)

- **DeeplyTough** (10.1021/acs.jcim.9b00554): voxelised pocket → 3D *steerable* (SE(3)) CNN → descriptor,
  Euclidean distance. Trained on TOUGH-M1. Still the reference learned baseline (§3).
- **BindSiteS-CNN** (10.1021/acs.jcim.2c00832): graph **spherical CNN** (DeepSphere) on SURFNET-derived pocket
  surfaces with shape/charge/hydrophobicity/pseudocentre feature maps; rotation invariance by training-time
  random rotations. (This is the "spherical-CNN pocket classification" of the brief.)
- **Site2Vec** (10.1088/2632-2153/abad88): frame-invariant autoencoder embedding; self-reported 3–5 sites/s
  descriptor generation [S].
- **ProFSA** (ICLR 2024, arXiv:2310.07229): cuts >5 M pseudo pocket–fragment complexes out of PDB proteins and
  contrastively aligns a pocket encoder to a molecule encoder. Best published pocket-matching numbers (§3).
- **EPoCS** (10.1093/bioinformatics/btaf284): mean-pooled **ESM-2 3B** residue embeddings over Voronoi-defined
  pocket residues, Euclidean distance. Training-free. Rank correlation **0.677 with APoc** on a random
  3,500-pocket PDB set, with only 0.14 % of APoc-near pairs called far [P]. Apache-2.0, `tugceoruc/epocs`.
- **PocketScope** (bioRxiv 10.64898/2026.08.30.748136): training-free, frozen **ESM-C 600M**, **late-interaction
  MaxSim** (no pooling, no ANN). Claims **rank 1 of 23 methods by mean rank on ProSPECCTs** and reports
  **153,805 cavities over 37,682 AlphaFold human proteins** [P, abstract only; full numbers not read].
- **ErePOC** (10.1038/s41467-026-69663-y): ESM-2 + contrastive learning on **326,416 pocket–ligand pairs from
  BioLiP2**, trained with a KL loss that *aligns the distribution of pocket cosine similarity to the
  distribution of ligand Tanimoto similarity*; 256-d embedding. Pearson **0.96** between ligand Tanimoto and
  pocket cosine on 500 random BioLiP2 pockets [P]. Applied to 23,391 human AFDB models with Fpocket.
- **MaSIF** (10.1038/s41592-019-0666-6) and **dMaSIF** (10.1109/CVPR46437.2021.01502): geodesic/point-cloud
  surface fingerprints. MaSIF-ligand classifies cofactor classes; MaSIF-search is the PPI-complementarity
  variant — the most relevant learned surface method for interfaces.
- **GraphSite** (10.3390/biom12081053) is a 14-class **classifier**, not a pairwise similarity tool.
  **PocketAnchor** (10.1016/j.cels.2023.05.005) targets site detection and affinity, not similarity.
- **DrugCLIP** (NeurIPS 2023; genome-wide application Science 2026, 10.1126/science.ads9530), **LigUnity**
  (10.1016/j.patter.2025.101371), **BindCLIP** (arXiv:2602.15236), **Simpatico**
  (10.1101/2025.06.08.658499), **OneProt** (10.1371/journal.pcbi.1013679): pocket–ligand co-embeddings. They
  give a pocket a position in *ligand space*, which is the learned analogue of a docking profile. Simpatico
  notably abandons the single pooled vector for **per-atom** embeddings.

**Nobody has published a FAISS/ANN pocket-vs-pocket all-vs-all at AFDB scale.** Every method in this subsection
produces cosine/Euclidean-comparable vectors and could be indexed; none reports doing it. PocketScope
explicitly declines ANN ("exhaustive … without … approximate nearest-neighbor search").

### 1.4 Motif / active-site search at AFDB scale (not pocket similarity, but the scaling precedent)

- **Folddisco** (preprint 10.1101/2025.07.06.663357; Nat Biotechnol 2026): residue-pair geometric hashing into
  30-bit keys (both residue identities, binned Cα–Cα and Cβ–Cβ distances, binned sin/cos of three angles) in an
  **inverted index** with rarity-weighted scoring. Indexed **53 M AFDB50 structures into 1.45 TB in <24 h**;
  per-query pre-filter **~13 s** on AFDB50 [S]. GPL-3.0, bioconda, prebuilt AFDB50/PDB indices.
  **The strongest existing AFDB-scale precedent and the architecture to imitate.** Limitation: needs
  user-specified motif residues.
- **pyScoMotif** (10.1093/bioadv/vbad158): residue-pair index, PyPI `pyscomotif` 0.9.50.
- **ActSeek** (10.1093/bioinformatics/btaf424): three key residues + neighbours, distance pre-screen, SVD
  superposition, optional pyKVFinder cavity comparison; "10,000 proteins in 2–10 min" per 24-CPU node [S].
- **Foldseek** (10.1038/s41587-023-01773-0, GPL-3, bioconda) and **MMseqs2** (10.1038/nbt.3988, MIT, bioconda)
  are the fold/sequence baselines our method must beat — a pocket method that only recapitulates Foldseek has
  no reason to exist.

### 1.5 Ligand- and docking-profile descriptors

Covered in detail in §4. Representation = a vector of responses to a fixed probe/ligand panel; comparison =
cosine/rank correlation (microseconds). Descriptor *generation* is the expensive step, which is precisely
where our GPU docking engine changes the economics.

---

## 2. Benchmarks and datasets

### 2.1 ProSPECCTs — the field standard (Ehrt, Brinkjost & Koch 2018, 10.1371/journal.pcbi.1006483)

**Correction to the brief: there is no D8/D9/D10.** The "ten" sets are D1, D1.2, D2, D3, D4, D5, D5.2, D6,
D6.2, D7. DeeplyTough and most later papers label them P1…P7. Also, **D3 is the physicochemical decoy set and
D4 the shape+physicochemical decoy set** (the brief had these reversed). Table below is **verbatim from
ProSPECCTs Table 2** [P]; "active/inactive" = similar/dissimilar pairs in the authors' wording.

| Set | Goal | active / inactive pairs |
|---|---|---|
| **D1** structures with identical sequences | sensitivity to **binding-site definition** (same site, chemically different ligands → different site definitions); 12 groups of identical-sequence structures | 13,430 / 92,846 |
| **D1.2** identical sequences + similar ligands | impact of **ligand diversity** on the comparison | 241 / 1,784 |
| **D2** NMR structures | sensitivity to **binding-site flexibility**; 17 structural ensembles of diverse proteins | 7,729 / 100,512 |
| **D3** decoy set 1 | discriminate sites differing by residue substitutions that change **physicochemistry** | 13,430 / 67,150 (full); 13,430 / 13,430 (five-variant subset) |
| **D4** decoy set 2 | substitutions changing **physicochemistry *and* shape** | 13,430 / 67,150 (full); 13,430 / 13,430 |
| **D5** Kahraman w/o phosphate | classify proteins binding **identical ligands/cofactors** | 920 / 5,480 |
| **D5.2** Kahraman, original | as D5, phosphate sites included | 1,320 / 8,680 |
| **D6 / D6.2** Barelier (6.2 includes cofactors) | **distant relationships**: unrelated proteins, identical ligand, similar local environment | 19 / 43 |
| **D7** successful applications | **recovery of literature-reported site similarities** among diverse proteins; 49 query structures against an sc-PDB cull | 115 / 56,284 |

- Download: DOI `10.17877/DE290M-2` (200) → TU Dortmund Dataverse. Licence: **"Custom Dataset Terms"** (a
  data-use agreement, *not* CC); the article itself is CC-BY-4.0. ~450 MB total; `decoy.tar.gz` is 312 MB [S].
- Pitfalls: **D1–D4 are near-trivial for global-fold methods** (TM-align scores 1.00/1.00/1.00 on D1/D1.2/D2,
  §3) — they measure robustness, not discovery. **D6/D6.2 have 62 pairs total**, so AUCs are extremely noisy
  and most tools do poorly; PocketVec omitted them. Different papers define the pocket differently (DeeplyTough
  uses complete residues within 8 Å of any ligand atom [P]; BindSiteS-CNN uses 6 Å [P]) — **pocket definition
  materially changes the AUC**, so a results table is only comparable within a definition.
- AF / PPI suitability: all structures are experimental (X-ray + NMR); **no AF version exists**. Essentially no
  PPI content. D2 is the only conformational-robustness test, and it is NMR ensembles, not apo/holo.

### 2.2 Other pair / label benchmarks

| Dataset | Positive / negative means | Size | Access (status) | Licence | Pitfalls | AF? PPI? |
|---|---|---|---|---|---|---|
| **TOUGH-M1** (10.1186/s12859-018-2109-2 — *BMC Bioinformatics*, not Sci Rep) | **+**: both pockets in one ligand cluster (SUBSET Tc 0.7) **and** global TM-score < 0.4; **−**: representatives of different ligand clusters, TM-score < 0.4. Pockets are **Fpocket 2.0 predictions** kept only if MCC ≥ 0.4 vs true binding residues | 7,524 structures; **505,116 positive / 556,810 negative** pairs [P] | https://osf.io/6ngbs/ (200) | OSF states none; article CC0 waiver language [S] | **Label noise**: positives are a *ligand-similarity proxy*; BindSiteS-CNN states false pos/neg "may indicate questionable ground-truth labels … shared binding … may be attributed to promiscuity of the molecule rather than pocket similarity" [P]. Family redundancy ⇒ must split by structure/UniProt. Pockets are predicted, not ligand-defined | single chains, no PPI. Protocol transfers to AF models; **no AF re-run published** |
| **TOUGH-C1** (10.1371/journal.pcbi.1006718) | pocket **class** labels (nucleotide / heme / steroid / control), not pairs | 1,553 nucleotide, 596 heme, 69 steroid, 1,946 control [P, BindSiteS-CNN Table 1] | https://osf.io/enz69/ (200) [S] | none stated | class-level, pairs must be derived; steroid class tiny (69) | no PPI |
| **Vertex** (10.1021/acs.jcim.6b00118) | **protein-level**: + = the two proteins share ≥1 active ligand in ChEMBL; − = share none | 6,598 positive / 379 negative protein pairs from 6,029 structures; expands to **1,461,668 / 102,935 pocket comparisons** [P, DeeplyTough] | original SI paywalled; DeeplyTough preprocessed copy Zenodo 3687317 (CC-BY-4.0) [S] | original not stated | ~17:1 imbalance; protein-level labels mean the compared pocket may not be the one binding the shared ligand | no PPI |
| **Kahraman** (10.1016/j.jmb.2007.01.086) | + = same ligand type; 100 proteins, 9 ligand types | 100 structures (80 without PO₄) | via ProSPECCTs D5/D5.2 | — | "an easy benchmark since the chosen ligands may be distinguished solely by their sizes" [P, DeeplyTough citing Hoffmann 2010]; cofactor-dominated | no PPI |
| **Barelier** (10.1021/acschembio.5b00683) | 62 pairs of fold-unrelated proteins binding the same ligand; class A (19) = similar local environment = positives | 59 ligands, 116 complexes | via ProSPECCTs D6/D6.2 | NIH author manuscript, none stated | tiny; the only true "distant relationship" set, and therefore the one that matters most to us and is hardest to measure | includes 4odj as a symmetric dimer [S] |
| **sc-PDB** (10.1093/nar/gku928) | curated druggable sites; source of ProSPECCTs D1/D2/D7 | 2017 release: 16,034 entries / 4,782 proteins / 6,326 ligands [S] | bioinfo-pharma.u-strasbg.fr/scPDB/ — **no response from this container (000)** | not stated | registration-gated historically | no PPI |
| **PLINDER** (10.1101/2024.07.17.603955) | protein–ligand systems with **leakage-aware splits** built from 14 similarity metrics including **pocket structural similarity and interaction fingerprints**; each system linked to an **apo structure and an AF2 prediction** | >400k systems (449,383 in the workshop paper) [S] | https://www.plinder.sh (200) | Apache-2.0 for PLINDER-curated data; BindingDB parts CC-BY-4.0, ChEMBL parts CC-BY-SA-4.0 [S] | preprint only; releases move (2024-04/v1 vs 2026-09) | **best source of holo/apo/AF triplets.** Sister resource **PINDER** (10.1101/2024.07.17.603980, https://www.pinder.sh 200) is the PPI analogue |
| **LIGYSIS** (10.1186/s13321-024-00923-z; server 10.1093/nar/gkaf411) | biologically relevant ligand sites pooled across **PISA biological assemblies**, ligands clustered by interaction fingerprint | ~30,000 proteins; human subset 3,448 segments / 8,244 sites / 65,116 ligands [S] | https://www.compbio.dundee.ac.uk/ligysis/ (200); Zenodo 10.5281/zenodo.13121414 | CC-BY-4.0 (Zenodo); code MIT | an internal count inconsistency in Table 2 (2,275 vs 2,775) [S] | **built on biological assemblies ⇒ contains interface sites.** BURROW's ranker was already trained LIGYSIS-style — watch for leakage |
| **PoSSuM** v3 (10.1021/acs.jcim.3c01405) | precomputed *similar site pairs* found by sketch search | ~10 M known+putative sites, **191 M precomputed similar pairs**; PoSSuMAF covers 23,391 human AFDB v2 models (pLDDT<70 filtered) [S] | https://possum.cbrc.pj.aist.go.jp/PoSSuM/ (200) | data not stated; article CC BY-NC-ND | "silver" labels produced by one method ⇒ circular if used as ground truth | **has an AF arm** and an antibody–antigen interface arm (PoSSuMAg) |
| **KLIFS** (10.1093/nar/gkaa895) | kinase structures with a fixed 85-residue pocket | — | https://klifs.net (200) | not stated; paper CC BY | within-family only | hard negatives for a fine-grained test |
| **AFDB** (10.1093/nar/gkad1011) | — | >214 M predictions | https://alphafold.ebi.ac.uk/download (200) | **CC-BY-4.0** | — | EMBL news (not peer-reviewed) reports 1.7 M high-confidence homodimers added 2026-03 and ~80k high-confidence heterodimers 2026-05 [U] |
| **PPI pocket dataset** (Moine-Franel et al., 10.1038/s41597-024-03233-z) | VolSite pockets at/near PPI interfaces, classed **PLOC** (orthosteric competitive), **PLONC** (orthosteric non-competitive), **PLA** (allosteric) | **>23,000 pockets, 3,700 proteins, >500 organisms, ~3,500 ligands, >1,700 families** [P] | Zenodo 10.5281/zenodo.10805580 (API 200) | **CC-BY-4.0** | pockets are VolSite predictions with PPI-tuned parameters; classification of allosteric effects is "a foundational step", authors' words [P] | **the single most relevant PPI-pocket resource.** See §5 |
| **iPPI-DB** | PPI inhibitors, curated | — | https://ippidb.pasteur.fr (200) | — | ligand-centric | PPI |
| **2P2Idb / TIMBAL / PIFACE** | — | — | **2p2idb.marseille.inserm.fr: no response (000)** from here; TIMBAL and PIFACE also unreachable [S] | — | appear partly dead | PPI |

### 2.3 Leakage-control resources (methodology, not similarity labels)

- **LP-PDBBind** (arXiv:2308.09639; J Phys Chem B 2026, 10.1021/acs.jpcb.5c08598): re-split of PDBbind with max
  protein sequence similarity 0.5, max ligand similarity 0.99, **plus an interaction-fingerprint filter** so
  that pairs with low sequence/ligand similarity but high *interaction* similarity are also removed [S]. Repo
  `THGLab/LP-PDBBind`; licence is UC Regents educational/non-profit only.
- **PDBbind CleanSplit / GEMS** (Graber et al., 10.1038/s42256-025-01124-5): filters on **combined TM-score,
  ligand Tanimoto and binding-conformation similarity**, deliberately keeping activity cliffs. **Retraining
  top models on CleanSplit caused substantial performance drops** [S] — read as direct evidence the original
  scores were leakage-driven. Zenodo 10.5281/zenodo.14260170; code `camlab-ethz/GEMS` (MIT).
- **DataSAIL** (10.1038/s41467-025-58606-8): leakage-minimising splitting as clustering + ILP, including
  two-dimensional (drug × target) splits. **MIT, `pip install datasail` (PyPI 1.4.0 confirmed)**. This is the
  tool for our pair splits.
- **HonestAffinity** (arXiv 2606.03422) [U, subagent-reported, I did not open it]: leak-aware affinity
  evaluation; reports pocket-marker and ESM-2 features *hurting* on strict leak-proof tiers. Affinity, not
  similarity.

### 2.4 Items I could not identify

- **GenomeScreenDB**: not found in Crossref or in the DrugCLIP Science 2026 paper text; the name appears only
  in one press article [S]. **Treat as non-existent under that name**; the DrugCLIP genome-wide screen hosts
  results at a project site instead.
- **"PocketSimBench", "PSB", "ApoHoloBench"**: no such benchmarks found.
- **ECIFP, Siteomix, SiteMatcher, ACP4, LEN-Seek, GTA-5, DMPPS, PSIM, "MetalSiteHunter"**: not found as named
  methods. Nearest real equivalents: ECIF/PLEC/SPLIF for interaction fingerprints; **MetalS2/MetalS3** for
  metal-site alignment and search (Valasatava et al., PMID 24699831), and **Master of Metals** for AF-model
  zinc sites. **"FUSED"** was not found as a pocket tool; the closest idea is fused Gromov–Wasserstein protein
  comparison (GWProt), which has no pocket benchmark.
- **SiteContext** *does* exist (10.1016/j.jmb.2026.169791) and is, as far as I can tell, the only published
  **optimal-transport** pocket comparer (Sinkhorn EMD on spherical atom histograms). Web server only.
- **POEM** exists (10.1021/acs.jcim.4c00601) but is a *subpocket-registration + generative linking* hit-finding
  pipeline (applied to the LRRK2 WD40 domain), not a general similarity measure.

---

## 3. Published numbers we must beat

### 3.1 ProSPECCTs (ROC AUC)

**Source and caveat.** The ProSPECCTs paper itself puts its per-method AUCs in supplementary tables S14–S32,
which I could not retrieve. The table below is **verbatim from DeeplyTough's Table 2** (bioRxiv v1,
10.1101/600304, read directly [P]), which states it is "directly reusing their published results" for the 21
baselines. Column labels are the paper's P-numbering (P1 = D1, …). Blank = not reported.

| Method | P1 | P1.2 | P2 | P3 | P4 | P5 | P5.2 | P6 | P6.2 | P7 |
|---|---|---|---|---|---|---|---|---|---|---|
| Cavbase | 0.98 | 0.91 | 0.87 | 0.65 | 0.64 | 0.60 | 0.57 | 0.55 | 0.55 | 0.82 |
| FuzCav | 0.94 | 0.99 | 0.99 | 0.69 | 0.58 | 0.55 | 0.54 | 0.67 | 0.73 | 0.77 |
| FuzCav (PDB) | 0.94 | 0.99 | 0.98 | 0.69 | 0.58 | 0.56 | 0.54 | 0.65 | 0.72 | 0.77 |
| Grim | 0.69 | 0.97 | 0.92 | 0.55 | 0.56 | 0.69 | 0.61 | 0.45 | 0.65 | 0.70 |
| Grim (PDB) | 0.62 | 0.83 | 0.85 | 0.57 | 0.56 | 0.61 | 0.58 | 0.45 | 0.50 | 0.64 |
| IsoMIF | 0.77 | 0.97 | 0.70 | 0.59 | 0.59 | **0.75** | **0.81** | 0.62 | 0.62 | 0.87 |
| KRIPO | 0.91 | 1.00 | 0.96 | 0.60 | 0.61 | **0.76** | 0.77 | **0.73** | **0.74** | 0.85 |
| PocketMatch | 0.82 | 0.98 | 0.96 | 0.59 | 0.57 | 0.66 | 0.60 | 0.51 | 0.51 | 0.82 |
| ProBiS | 1.00 | 1.00 | 1.00 | 0.47 | 0.46 | 0.54 | 0.55 | 0.50 | 0.50 | 0.85 |
| RAPMAD | 0.85 | 0.83 | 0.82 | 0.61 | 0.63 | 0.55 | 0.52 | 0.60 | 0.60 | 0.74 |
| Shaper | 0.96 | 0.93 | 0.93 | 0.71 | **0.76** | 0.65 | 0.65 | 0.54 | 0.65 | 0.75 |
| Shaper (PDB) | 0.96 | 0.93 | 0.93 | 0.71 | 0.76 | 0.66 | 0.64 | 0.54 | 0.65 | 0.75 |
| VolSite/Shaper | 0.93 | 0.99 | 0.78 | 0.68 | 0.76 | 0.56 | 0.58 | 0.71 | **0.76** | 0.77 |
| VolSite/Shaper (PDB) | 0.94 | 1.00 | 0.76 | 0.68 | 0.76 | 0.57 | 0.56 | 0.50 | 0.57 | 0.72 |
| **SiteAlign** | 0.97 | 1.00 | 1.00 | **0.85** | **0.80** | 0.59 | 0.57 | 0.44 | 0.56 | **0.87** |
| SiteEngine | 0.96 | 1.00 | 1.00 | 0.82 | 0.79 | 0.64 | 0.57 | 0.55 | 0.55 | 0.86 |
| SiteHopper | 0.98 | 0.94 | 1.00 | 0.75 | 0.75 | 0.72 | **0.81** | 0.56 | 0.54 | 0.77 |
| SMAP | 1.00 | 1.00 | 1.00 | 0.76 | 0.65 | 0.62 | 0.54 | 0.68 | 0.68 | 0.86 |
| TIFP | 0.66 | 0.90 | 0.91 | 0.66 | 0.66 | 0.71 | 0.63 | 0.55 | 0.60 | 0.71 |
| TIFP (PDB) | 0.55 | 0.74 | 0.78 | 0.56 | 0.57 | 0.54 | 0.53 | 0.56 | 0.61 | 0.66 |
| TM-align | 1.00 | 1.00 | 1.00 | 0.49 | 0.49 | 0.66 | 0.62 | 0.59 | 0.59 | **0.88** |
| **DeeplyTough** (bioRxiv v1) | 0.96 | 0.97 | 0.93 | 0.72 | 0.72 | 0.66 | 0.61 | 0.59 | 0.59 | 0.80 |
| *(DeeplyTough rank among all)* | 7–10 | 12–14 | 11–13 | 5 | 8 | 6–9 | 8–9 | 8–9 | 13–14 | 8–9 |

Added from other primary sources (different pocket definitions and protocols — **not strictly comparable**):

| Method | P1 | P1.2 | P2 | P3 | P4 | P5 | P5.2 | P6 | P6.2 | P7 | source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **PocketVec** (128 lead-like, rDock) | 0.97 | 1.00 | 0.96 | 0.67 | 0.72 | 0.64 | 0.62 | — | — | 0.87 | [P] Nat Commun 2024 text |
| **BindSiteS-CNN** (6 Å ligand pockets) | 0.94 | 0.98 | 0.83 | **0.91** | 0.79 | 0.64 | 0.66 | 0.62 | 0.61 | 0.78 | [P] JCIM 2022 text |

Notes that matter:
- **PocketVec is "the second-best ranked strategy in terms of the weighted average among datasets (0.89)" and
  "surpasses the median and the average performance in all ProSPECCTs datasets, apart from P3"; the top-scoring
  method is SiteAlign** [P, verbatim]. PocketVec omitted P6/P6.2.
- BindSiteS-CNN reports **1st on P3 and 2nd on P4** of all tools [P] — a learned surface method can be made
  *sensitive* to mutations, which is exactly where PocketVec and DeeplyTough are weak.
- **The global-fold baselines TM-align, ProBiS and SMAP score 1.00/1.00/1.00 on P1/P1.2/P2 and collapse on
  P3/P4 (TM-align 0.49/0.49)**. Any headline claim on P1/P1.2/P2 alone is meaningless for a fold-independent
  method; **P5, P6, P6.2 and P7 are the sets that test what we actually claim**, and they are where *every*
  method is mediocre (best P6.2 = 0.76, best P5 = 0.76).
- Published **PR-AUC on ProSPECCTs is essentially absent**. DeeplyTough reports **average precision 0.44 on P7**
  [P] — the only PR-style number I found. Given D7's 115 : 56,284 imbalance and D1's 13,430 : 92,846, **AUC-PR
  is the more honest metric and we should report it even though nobody else does** (and also report AUC-ROC for
  comparability).

### 3.2 TOUGH-M1, APoc set, Kahraman, Vertex (ROC AUC)

| Method | TOUGH-M1 | APoc set | Kahraman (w/o PO₄) | Vertex | Source |
|---|---|---|---|---|---|
| global sequence identity (DP) | 0.55 | — | — | — | [P] TOUGH-M1 Table 1 |
| global TM-score (Fr-TM-align) | **0.51** | 0.75 | — | — | [P] TOUGH-M1 |
| APoc | 0.65 | 0.82 | — | — | [P] TOUGH-M1 Table 1 |
| SiteEngine | 0.66 | 0.60 | 0.64 | — | [P] TOUGH-M1 Table 1; Kahraman from ProFSA Table 2 [P] |
| G-LoSA | 0.69 | 0.77 | — | — | [P] TOUGH-M1 Table 1 |
| **AutoDock Vina docking profile** | **0.55** | — | — | — | [P] TOUGH-M1 Table 1 |
| **rDock docking profile** | **0.67** | — | — | — | [P] TOUGH-M1 Table 1 |
| APoc + Vina / APoc + rDock | 0.67 / 0.70 | — | — | — | [P] |
| SiteEngine + Vina / + rDock | 0.66 / 0.76 | — | — | — | [P] |
| G-LoSA + Vina / **G-LoSA + rDock** | 0.66 / **0.77** | — | — | — | [P] — best in that paper |
| PocketMatch | 0.611 (DT split) / 0.644 | — | 0.66 | 0.604 | [P] DeeplyTough; [P] BindSiteS-CNN; [P] ProFSA |
| TM-align | 0.65 | — | 0.66 | — | [P] ProFSA Table 2 |
| IsoMIF | — | — | 0.75 | — | [P] ProFSA Table 2 |
| SiteHopper | — | — | — | **0.887** | [P] DeeplyTough (provided by Chen et al.) |
| **DeeplyTough** | **0.933 ± 0.004** (bioRxiv, UniProt-fold split) ; **0.91 ± 0.003** (as re-run/quoted by BindSiteS-CNN) ; 0.91 (ProFSA table) | — | 0.67 | 0.818 (bioRxiv) / 0.830 [U] | [P] all three |
| DeeplyTough trained on a 1,395-structure subset | **0.740** | — | — | 0.709 | [P] DeeplyTough |
| **BindSiteS-CNN** | **0.86 ± 0.003** (Fpocket pockets) / **0.89 ± 0.002** (6 Å ligand pockets) | — | — | — | [P] JCIM 2022 |
| Uni-Mol (zero-shot / fine-tuned) | 0.76 / 0.79 | — | 0.66 / 0.71 | — | [P] ProFSA Table 2 |
| CoSP | — | — | 0.62 | — | [P] ProFSA Table 2 |
| **ProFSA (zero-shot / fine-tuned)** | **0.82 / 0.94** | — | **0.80 / 0.85** | — | [P] ProFSA Table 2 |

Reading of this table:
1. **TM-score AUC on TOUGH-M1 is 0.51** [P] — the benchmark is genuinely fold-independent by construction
   (TM-score < 0.4 imposed on both classes). That is why it is the right primary benchmark for our claim, and
   why the APoc set (TM-score AUC 0.75, because the TM-score cut was applied only to controls [P]) is not.
2. **The 0.91–0.94 figures are fine-tuned-on-TOUGH-M1 numbers.** Zero-shot, the best published is ProFSA 0.82;
   un-trained classical methods sit at 0.64–0.69. Our fair comparison point depends on whether we train on
   TOUGH-M1 at all. **Report both arms.**
3. A plain Vina docking profile scores **0.55** — barely above chance — while rDock scores **0.67** [P]. The
   docking protocol and ligand set, not "docking" as an idea, carry the signal (§4).

---

## 4. Docking-profile descriptors — what PocketVec actually did, and what it means for the fragment idea

**PocketVec** — Comajuncosa-Creus, Jorba, Barril & Aloy, *Nat Commun* 15 (2024), **10.1038/s41467-024-52146-3**
(note: no author named "Balboa"; the brief's attribution is wrong). Code:
https://gitlabsbnb.irbbarcelona.org/acomajuncosa/pocketvec (200) and a GitHub mirror **`sbnb-irb/PocketVec`,
MIT, last push 2026-10-05** (200, checked via the GitHub API).

All of the following is [P], read in the PMC full text:

- **Ligand set.** 650k lead-like molecules → clustering → 1,000 representative lead-like molecules (LLM, MOE
  v2019.01, MW 200–450) → **the 128 most diverse by Shannon entropy of their rankings across pockets**.
- **Fragments were tested and lost.** A **667-compound Glide diverse fragment set (MW 50–200)** was benchmarked
  head-to-head. Verbatim reasons: LLM "showed a superior discriminative power with respect to the size of the
  pocket and, overall, provided higher ranking diversity among all ProSPECCTs pockets"; "LLM occupied a larger
  fraction of the binding sites than fragments"; and "rigid docking might have removed the noise created by
  similar rankings of the same ligand in different conformations". Even restricted to 128 compounds each,
  "the use of rDock and LLM (128) was still the best strategy according to the ProSPECCTs datasets."
- **Docking.** rDock, **rigid**, default parameters, 12 Å site box, 25 runs; score = minimum `SCORE.INTER`.
  SMINA flexible docking was the alternative and was worse.
- **Descriptor.** Scores → **ranks** (ties by `rankdata(method='max')`), non-binders (positive scores) binned to
  ranks 129/130/131. Length 128. Compared by **cosine distance**; the paper's similarity threshold is 0.17.
- **How many ligands are enough:** "the use of ~**100–200 molecules** was often sufficient to get competitive
  performances in most datasets."
- **Runtime:** "On average, the generation of a PocketVec descriptor for a protein pocket takes **1 h** on an
  Intel Xeon Gold 6138 CPU." Comparison itself is a cosine.
- **Results:** ProSPECCTs as in §3.1; **weighted average 0.89, second best overall, behind SiteAlign**.
- **Robustness (their own analysis, most relevant to AFDB):** holo-vs-holo descriptors of the same pocket are
  cleanly separable from random pairs (**LIG-LIG AUROC 0.90**); holo vs apo-PDB detected pockets **LIG-PD 0.77**,
  **PD-PD 0.80**; **holo vs AF2 LIG-AF2 0.82** — i.e. *descriptors from holo structures are more similar to AF2
  descriptors than to apo-PDB descriptors*; across **MD frames 0.78**.
- **Ligand-sharing validation:** pockets sharing a single PDB ligand are only marginally closer (**AUROC 0.58**);
  sharing **≥3 ligands gives AUROC 0.75**; with predicted (lead-like) actives instead, **0.87**. ProSPECCTs
  P5/P5.2 (identical cofactor) give only 0.64/0.62 — **"two binding sites having identical … crystallized
  ligands are not necessarily similar"** (their words).
- **Chemoproteomics check:** against Offensperger et al. (*Science* 2024, 10.1126/science.adk5864) fragment
  screening, after filtering to 301 fragments × 525 proteins, there was **no enrichment of shared compounds at
  PocketVec distance ≤0.17** — "expected due to the smaller nature of the fragments (translating in lower
  specificity)" — but **~8× and ~30× enrichment for ≥3 shared compounds at ≤0.10 and ≤0.05**.
- **Proteome scale:** >32k pockets in human PDB + AF2 models, **>1.2 billion pairwise comparisons**, yielding
  millions of similar pairs in domains of low sequence and structure similarity [S for the exact pair counts].

**The older lineage.** Affinity fingerprinting — Kauvar et al., *Chem Biol* 2 (1995) 107–118,
10.1016/1074-5521(95)90283-X — is the experimental ancestor: characterise a protein by its measured affinities
against a small reference compound panel. Fukunishi's "docking score index" / protein–compound affinity matrix
work is the in-silico ancestor [U for its specific results]. Probe-based (non-docking) relatives: **FTMap/FTSite**
(16 probes; E-FTMap 119) consensus hot spots; **Fragment Hotspot Maps** (CSD-derived propensities);
**SILCS FragMaps** (explicit-solvent MD, hours–days per protein); **GRID/MIF** methods (IsoMIF: 6 probes);
**FragFEATURE** (10.1371/journal.pcbi.1003589) predicts preferred fragments from a knowledge base *without
docking at all*.

### What this means for our fragment-docking idea

1. **The cost argument is overwhelming and is the main reason to do this.** PocketVec's 1 h/pocket is the
   reason the idea has not scaled. At ADock's 0.1–0.2 s/ligand-pocket, 128 ligands is **~13–26 s/pocket**
   (~150–280× faster), and 1,000 ligands is ~2–3 min. Even at 20 s/pocket, 10⁶ pockets is ~5,600 GPU-hours —
   still far too much for all of AFDB, so a **two-tier design (cheap descriptor everywhere, docking profile on
   a shortlist or on a reference set) is mandatory**, not optional. Budget this explicitly in DESIGN.md.
2. **Our human prior (fragments) is the arm PocketVec tested and rejected.** We should not assume it; we should
   run the comparison ourselves, because our situation differs in two ways that could flip it: (a) fragments
   are plausibly better for **shallow/flat PPI-interface pockets** where a lead-like molecule cannot be
   accommodated at all and every score saturates; (b) we can afford *many more* fragments, and fragments'
   weakness was partly low per-ligand information, which more probes can offset. Pre-register this as a
   head-to-head: fragments vs lead-like, at matched descriptor length and matched compute.
3. **Rank-transform, do not use raw scores.** Raw docking scores track pocket volume and scoring-function
   scale. PocketVec's rank vector + explicit non-binder bins + cosine is the normalisation that made it work.
4. **Use the pose, not just the score.** PocketVec throws away the pose. Its blind spots are exactly
   P3/P4 (mutation decoys: 0.67/0.72) and P5 (cofactor classes: 0.64) — properties a **docked-pose interaction
   fingerprint** (per-fragment contact types, buried fraction, H-bond/apolar/aromatic counts) would see and a
   scalar score cannot. ADock gives poses for free. **No published pocket descriptor uses pose/IFP profiles at
   scale** — this is the most defensible novel component available to us.
5. **Validate against the known failure mode.** Plain Vina profiles score **0.55 on TOUGH-M1** [P]. Before
   building anything on ADock scores, reproduce the Govindaraj & Brylinski indirect experiment (1,515 FDA drugs
   from DrugBank, SUBSET Tc 0.95, Spearman ρ between rank vectors [P]) with ADock and check we land near rDock's
   0.67 rather than Vina's 0.55. That is a cheap, decisive go/no-go.
6. **Docking profiles are conformation-tolerant**, which is their best property for AFDB: P2 (NMR) 0.96, MD
   frames 0.78, holo-vs-AF2 0.82 [P]. Weigh this against their insensitivity to point mutations.

---

## 5. Pockets at protein–protein interfaces

**What exists.**
- **The resource to use: Moine-Franel et al., *Sci Data* 2024, 10.1038/s41597-024-03233-z** (Institut Pasteur).
  >23,000 **VolSite** pockets over 3,700 proteins and ~3,500 ligands, >1,700 families, CC-BY-4.0 on Zenodo
  (10.5281/zenodo.10805580). Crucially [P]: **VolSite parameters were re-tuned for PPI pockets** because "pockets
  within PPIs typically exhibit distinct properties, such as shallowness"; for heterodimers, pockets are
  detected **with the partner protein treated as the ligand**; pockets are classified **PLOC / PLONC / PLA**
  (orthosteric competitive, orthosteric non-competitive, allosteric) by their relation to the interface. They
  also define a **pocket similarity index (PSI)** from **109 pocket descriptors** (89 VolSite + 10 Kuenemann-style
  composites + 10 geometric) after dropping near-constant ones. **That is architecturally the same thing as
  BURROW's 76 descriptors + cosine** — so this is both a ready-made benchmark *and* a direct baseline for our
  cheapest tier.
- Interface *geometry* comparison (not pockets): **iAlign/IS-score** (10.1093/bioinformatics/btq404; 90 %
  coverage at 0.05 errors/query on 1,517 dimers [S]), **I2I-SiteEngine** (PMID 15980484), **PIFACE** (22,604
  unique interface structures [S]; the URL did not respond from here), **MaSIF-search/MaSIF-site**, **PInet**.
- Ligand/chemistry databases: **iPPI-DB** (200), **2P2Idb** (unreachable from here), **TIMBAL** (unreachable).

**How interface pockets differ** (all [S] — read in secondary sources, not the originals):
- 2P2I interfaces are **more hydrophobic, with fewer charged residues**, and have **smaller accessible surface
  areas** than general PPI interfaces (Bourgeas et al. 2010, 10.1371/journal.pone.0009598).
- PPI inhibitors pay in **molecular weight, hydrophobicity and aromaticity** relative to enzyme inhibitors.
- The "flat and featureless" picture is **contested**: Jubb, Blundell & Ascher 2015
  (10.1016/j.pbiomolbio.2015.01.009) argue druggability comes from **small pockets and single-residue
  sub-pockets** exploited in combination; a PDB-wide analysis (*Brief Bioinform* 2022, bbac165) finds interfaces
  **more concave than the narrative implies**, with small druggable pockets inside even large flat interfaces.
- **Flexibility is essential**: Kozakov et al. *PNAS* 2011 (10.1073/pnas.1101835108) — druggable interface sites
  are **clusters of hot spots with concave topology** that require **low-energy side-chain motion** to
  accommodate drug-sized ligands. Eyrisch & Helms 2007 found **transient** pockets absent from the apo crystal
  in BCL-XL, IL-2 and MDM2.
- **Molecular glues**: a GlueFinder-style preprint mines the PDB for **interface-adjacent pockets** as glue
  nucleation sites [S] — the closest analogue to what we would do on AFDB dimers, and it is PDB-only.

**The gap, stated plainly.** *There is no published benchmark for comparing pockets **at** interfaces.*
ProSPECCTs, TOUGH-M1, Kahraman, Barelier and Vertex are monomeric/classical. iAlign and PIFACE benchmark
interface *geometry*, not interface *pockets*. The Pasteur PPI dataset is the only labelled interface-pocket
collection, and it was built for descriptor analysis, not as a similarity benchmark. **Building one (positives
= PLOC pockets of homologous PPI families, symmetric copies in our dimer set, PDB holo interface pockets
matched to their AFDB-dimer counterparts; negatives = unrelated interface pockets, chemotype-balanced) is
itself a contribution**, and BURROW's existing 400-assembly dimer benchmark with grouped symmetric copies is a
head start.

**Caveats for AFDB dimers.** AF-Multimer reliability degrades for **small interfaces** [S], which is precisely
where ligandable interface pockets live. An interface-confidence filter (ipTM/PAE, interface pLDDT) is
mandatory. BURROW's own note already records that interface sites in assemblies are *at par* with P2Rank, not
better, so detection quality — not just comparison — limits us here.

---

## 6. Data leakage and robustness

### 6.1 Leakage in the pocket-similarity literature specifically

- **DeeplyTough's split changed between preprint and journal.** The repo changelog (23.02.2020) records moving
  "away … from UniProt-based splitting … to sequence-based clustering approach whereby protein structures
  sharing more than 30% sequence identity are always allocated to the same testing/training set" [P, README].
  The widely quoted **0.933 on TOUGH-M1 is the bioRxiv (UniProt-fold) number**; the JCIM-era number quoted by
  others is **0.91**. Cite the right one.
- **The cross-benchmark controls are partial by design.** For Vertex and ProSPECCTs, DeeplyTough trains on *all*
  of TOUGH-M1 and only removes structures whose UniProt accession appears in the evaluation set (plus 220 PDB
  IDs with no accession), leaving 6,979 / 6,369 structures respectively [P]. That is a UniProt-identity filter,
  **not** a homology filter — homologues below the accession level are not removed. **ProFSA states it follows
  DeeplyTough's splitting practice** [P] and reports no additional overlap analysis. So the 0.91–0.94 TOUGH-M1
  and 0.80–0.85 Kahraman numbers should be read as *upper bounds*.
- **BindSiteS-CNN is explicit that it did not control overlap**: "There were 7117 unique UniProt codes in
  TOUGH-M1 and 67 in the kinase set, with 30 overlaps between the two sets. As we were comparing against
  previously published results using the ProSPECCTs dataset … we did not remove the overlaps to allow for this
  comparison" [P, verbatim]. It *did* remove TOUGH-M1 proteins occurring in ProSPECCTs before training [P].
- **EPoCS demonstrates the failure of sequence-identity splits for pocket models** [P]: using their pocket
  metric to build progressively harder splits, test AUC falls from ~0.92 (random) to **0.81** on the hardest
  tree-based split, and a **30 % sequence-identity split "ranks among the easier splits"**. They also exhibit
  concrete PoseBusters/PDBbind overlaps that survived chronological *and* sequence-based splitting. **This is
  the most directly applicable leakage result for us, and EPoCS is Apache-2.0 and installable** — we can use
  its metric to *define* our splits, not just to benchmark.
- **Label noise is the other half of the problem.** TOUGH-M1 positives are ligand-similarity proxies, and
  BindSiteS-CNN's own reading is that false positives/negatives "may indicate questionable ground-truth labels
  … shared binding … attributed to the promiscuity of the molecule rather than … pocket similarity"; negatives
  are weak because "the lack of a structural/experimental conformation of binding does not mean that binding
  related ligands is unfeasible" [P]. **An AUC ceiling well below 1.0 is baked into TOUGH-M1.**
- Broader affinity-model leakage (context, [S]): Volkov et al. 2022 (*J Med Chem* 65:7946) — memorisation
  dominates; DUD-E analogue bias (Chen et al. 2019); a LIT-PCBA audit naming DrugCLIP among methods whose
  enrichment it attributes largely to leakage (arXiv:2507.21404, single-group preprint, no rebuttal found [U]);
  LP-PDBBind; CleanSplit (retrained top models drop substantially).

### 6.2 AlphaFold vs apo vs holo

- **PocketVec, the only pocket-*similarity* measurement** [P]: descriptor agreement LIG-LIG 0.90, LIG-PD 0.77,
  PD-PD 0.80, **LIG-AF2 0.82** — AF2-derived descriptors are *closer to holo than apo-PDB descriptors are*.
  But the bigger loss is upstream in **detection**: predicted-vs-reference pocket agreement ~59 % on PDB vs
  ~49 % on AF2, and descriptor score correlation ~0.88 (PDB) vs 0.62 (AF2) [S, from the preprint]. **Most of
  the AF degradation is pocket-definition disagreement, not descriptor instability** — which puts the burden on
  BURROW's pocket output, and argues for comparison schemes that are robust to the pocket boundary (soft
  masks / overlapping sub-pockets / residue-set matching rather than a hard point set).
- **Docking on AF models is clearly worse** [S]: Karelina, Noh & Dror (*eLife* 2023, 10.7554/eLife.89386) — AF2
  GPCR pockets are far more accurate than homology models (median 1.3 Å vs 3.3 Å) **yet docking into them was
  not better**; Scardino et al. (*iScience* 2023, 10.1016/j.isci.2022.105920) — AF models consistently
  underperformed matched PDB structures in high-throughput docking, with enrichment factors of zero on several
  targets; Holcomb et al. (*Protein Sci* 2023;32:e4530) — AF2 backbones are right but finer details prevent
  direct use as docking targets. **This is a direct risk to a docking-profile descriptor on AFDB** and must be
  measured, not assumed: the question for us is not pose accuracy but whether the *rank vector* is stable
  between holo and AF2 for the same site. PocketVec's 0.82 says it is largely stable; our own apo/AF pairs
  (`data/processed/{af_train,apo_train}` in pocket_detect) let us check this directly and cheaply.
- **Whether AF2 is apo-like or holo-like is unsettled** [U/contested]; BURROW's own LITERATURE.md already
  records that AF models of well-studied proteins are often holo-like and that pLDDT does not separate binders
  from non-binders. Do not build an argument on either claim.
- **Nobody has re-run ProSPECCTs or TOUGH-M1 on AlphaFold models.** Both subagent searches and my own found
  nothing. Given that everybody now searches AFDB, **an AF-model version of ProSPECCTs D1/D2/D7 (map each PDB
  entry to its UniProt AF model, re-detect pockets, recompute AUC) is a cheap, high-value experiment and a
  publishable artefact in its own right.**

---

## 7. Implications for our design — 10 opinionated recommendations

1. **Primary benchmark: TOUGH-M1. Secondary: ProSPECCTs D5/D5.2, D6/D6.2, D7 and the Vertex set.** TOUGH-M1 is
   the only large set where the fold baseline is dead (TM-score AUC 0.51 [P]), so it directly tests the
   fold-independence claim. ProSPECCTs D1/D1.2/D2/D3/D4 are **robustness diagnostics, not headline results** —
   TM-align scores 1.00 on the first three. Report all ten anyway (the field does) but set our pre-registered
   endpoints on TOUGH-M1 + D5/D6/D7 + Vertex, and **report AUC-PR alongside AUC-ROC**: the class balance swings
   from 17 positives per negative (Vertex) to 1 positive per 489 negatives (ProSPECCTs D7), and ROC-AUC hides
   both extremes. Accept that TOUGH-M1 has a label-noise ceiling and say so.
2. **Report zero-shot and trained numbers separately, and never compare across them.** Published 0.91–0.94 on
   TOUGH-M1 are fine-tuned-on-TOUGH-M1; zero-shot state of the art is ProFSA 0.82 and classical methods are
   0.64–0.69 [P]. If our method is untrained (a real advantage of a docking/descriptor profile), the honest
   comparison set is the zero-shot column — where beating 0.82 is a genuine result.
3. **Build the split with DataSAIL and the leakage check with EPoCS.** DataSAIL is MIT and `pip`-installable
   (PyPI 1.4.0, confirmed); it handles two-dimensional pair splits, which is exactly our setting. EPoCS
   (Apache-2.0, `tugceoruc/epocs`) showed that 30 %-identity splits are among the *easiest* [P] — so use a
   pocket-similarity-based split as the hard tier and report a **split progression** (random → cluster →
   pocket-tree), not a single number. Reuse pocket_detect's `data/manifests/test_union.tsv` exclusion lists so
   nothing leaks against BURROW's own test sets.
4. **Baselines that are cheap to run locally (checked today).** Easy: **APoc** — bioconda `apoc` 1b16, licence
   "freely available to ALL users" (this is the obvious classical alignment baseline, ~37 ms/pair);
   **Foldseek** (GPL-3, bioconda) and **MMseqs2** (MIT, bioconda) as the must-beat fold/sequence baselines;
   **Folddisco** (GPL-3, bioconda, prebuilt AFDB50 index) as the scaling reference; **EPoCS** (Apache-2.0, pip
   from GitHub) as a strong, training-free embedding baseline; **ProFSA** (MIT) for a learned baseline;
   **PocketVec** (MIT mirror `sbnb-irb/PocketVec`, plus precomputed descriptors on their GitLab — fetch the
   precomputed descriptors rather than re-docking). Medium: **PocketMatch** (GitHub, *no licence*, last push
   2015), **KRIPO** (`kripodb` Apache-2.0 but Docker-only, not on PyPI, and **requires a bound ligand** so it
   cannot run on apo AF models), **G-LoSA** (http://compbio.lehigh.edu/GLoSA/ responds 200; licence unknown).
   Hard or impossible: **DeeplyTough** (repo licence "NOASSERTION", Python 3.6 + legacy HTMD, last push 2023 —
   budget a day or use Docker, and if it fails, quote published numbers instead); **IsoMIF** (no licence, last
   push 2016); **ProBiS** (insilab.org responds but `/probis/` 404s); **SiteAlign, Cavbase, SiteEngine,
   SiteHopper, VolSite/Shaper** (commercial, license-gated, or unobtainable binaries) — for all of these,
   **quote the published ProSPECCTs numbers in §3.1 rather than attempting to re-run them**. Do not spend days
   resurrecting dead tools.
5. **Design for two tiers from the start.** Tier 1: a fixed-length, physics/geometry descriptor from BURROW's
   existing 76 descriptors + point-cloud statistics, cosine/learned metric, **FAISS-indexable** — microseconds
   per pair, runnable on all of AFDB. Tier 2: a docking/pose profile (ADock, rank-transformed, with per-pose
   interaction features) on the top-k shortlist. This mirrors the only architecture anyone has shown to work at
   53 M structures (Folddisco's index + rescore), and it is the only way the docking idea survives contact with
   200 M structures. **Nobody has published a FAISS pocket-vs-pocket all-vs-all at AFDB scale** — shipping one
   is a contribution independent of which descriptor wins.
6. **Run the docking-profile go/no-go before committing.** Reproduce Govindaraj & Brylinski's indirect
   experiment with ADock (1,515 DrugBank FDA drugs, Spearman ρ of rank vectors, TOUGH-M1) and check we are near
   **rDock's 0.67**, not **Vina's 0.55** [P]. If ADock behaves like Vina, the fragment idea needs the pose
   features (point 7) to be viable at all.
7. **The novel bit worth betting on: pose/interaction-fingerprint profiles, not score profiles.** PocketVec
   discards the pose and loses exactly on P3/P4/P5 (mutation decoys and cofactor classes), where a contact-type
   profile should help; BindSiteS-CNN's P3 = 0.91 shows a shape/chemistry-sensitive representation can win
   there [P]. ADock gives poses for ~free. This is, as far as I can determine, **unpublished at scale**.
8. **Test fragments vs lead-like as a pre-registered experiment, and do not assume the human prior.** PocketVec
   tested 667 Glide fragments against 1,000 lead-like molecules and fragments lost on ProSPECCTs [P], and found
   **no enrichment for shared fragments at their standard threshold** in the Offensperger chemoproteomics data
   [P]. Our counter-hypothesis — fragments should be *better* for shallow PPI-interface pockets, where
   lead-like molecules cannot be accommodated and scores saturate — is testable and is where the fragment idea
   is most likely to pay off. Match descriptor length and compute between arms. ~100–200 probes is the
   saturation point [P], so pick that scale and spend the surplus compute on pose features instead of more
   ligands.
9. **For PPI pockets, use the Pasteur dataset and build the missing benchmark.** Download
   10.5281/zenodo.10805580 (CC-BY-4.0, ~11 GB — hand to the data agent), use the **PLOC/PLONC/PLA** labels, and
   treat their **109-descriptor PSI** as the baseline our descriptor tier must beat. Combine with BURROW's
   400-assembly dimer set (symmetric copies = free positives) and AFDB dimers filtered on interface confidence.
   Expect interface pockets to be **shallower and more hydrophobic**, which means BURROW's buriedness-derived
   features will be compressed at the low end — check feature-distribution shift between monomer and interface
   pockets *before* assuming a single metric transfers, and consider a separate calibration.
10. **Three engineering rules that come straight from the literature.** (a) **Pocket definition dominates
    measured accuracy** — DeeplyTough 8 Å vs BindSiteS-CNN 6 Å, and BindSiteS-CNN's own TOUGH-M1 AUC moves
    0.86 → 0.89 just by switching Fpocket pockets for 6 Å ligand pockets [P]; fix and document ours, and report
    sensitivity to it. (b) **Avoid ligand-dependent representations** (KRIPO, TIFP, Grim): they cannot run on
    apo AF models, which is our entire target domain. (c) **Normalise away size and protein context** —
    PocketVec's rank transform exists for this reason, Kahraman "ligands may be distinguished solely by their
    sizes" [P], and BURROW's own note warns that `vol`, `score_sum`, `n_all*` and `n_atoms_prot` mix pocket
    identity with protein size. Also fold in BURROW's warnings: merge touching sub-pockets before comparing,
    separate metal/ion pockets (they dominate nearest-neighbour lists), weight by pocket confidence, and match
    by residue/point-set overlap rather than centre distance.

**Bonus experiment, cheap and unclaimed:** re-run ProSPECCTs D1/D2/D7 (and a TOUGH-M1 subset) on AlphaFold
models of the same UniProt entries and publish the AUC drop. Nobody has done it; everybody needs it; we have
the AFDB locally and a fast pocket finder.

---

## 8. References

Benchmarks and data
- Ehrt C, Brinkjost T, Koch O. ProSPECCTs. *PLoS Comput Biol* 14:e1006483 (2018). 10.1371/journal.pcbi.1006483 · data DOI 10.17877/DE290M-2
- Govindaraj RG, Brylinski M. TOUGH-M1 / comparative assessment. *BMC Bioinformatics* 19:91 (2018). 10.1186/s12859-018-2109-2 · https://osf.io/6ngbs/
- Pu L et al. DeepDrug3D / TOUGH-C1. *PLoS Comput Biol* 15:e1006718 (2019). 10.1371/journal.pcbi.1006718 · https://osf.io/enz69/
- Chen YC et al. Vertex dataset. *J Chem Inf Model* 56:1734 (2016). 10.1021/acs.jcim.6b00118
- Kahraman A et al. *J Mol Biol* 368:283 (2007). 10.1016/j.jmb.2007.01.086
- Barelier S et al. *ACS Chem Biol* 10:2772 (2015). 10.1021/acschembio.5b00683
- Desaphy J et al. sc-PDB. *Nucleic Acids Res* (2015). 10.1093/nar/gku928
- Durairaj J et al. PLINDER. bioRxiv (2024). 10.1101/2024.07.17.603955 · PINDER 10.1101/2024.07.17.603980
- Utgés JS, Barton GJ. LIGYSIS. *J Cheminform* 16:126 (2024). 10.1186/s13321-024-00923-z · server 10.1093/nar/gkaf411
- Tsuchiya Y et al. PoSSuM v.3. *J Chem Inf Model* (2023). 10.1021/acs.jcim.3c01405 · v2.0 10.1093/nar/gku1144
- Kanev GK et al. KLIFS. *Nucleic Acids Res* (2021). 10.1093/nar/gkaa895
- Varadi M et al. AlphaFold DB. *Nucleic Acids Res* (2024). 10.1093/nar/gkad1011
- Moine-Franel A et al. PPI + ligand-pocket dataset. *Sci Data* 11:452 (2024). 10.1038/s41597-024-03233-z · Zenodo 10.5281/zenodo.10805580
- Li J et al. LP-PDBBind. arXiv:2308.09639 · *J Phys Chem B* (2026) 10.1021/acs.jpcb.5c08598
- Graber et al. PDBbind CleanSplit / GEMS. *Nat Mach Intell* (2025). 10.1038/s42256-025-01124-5
- Joeres R, Blumenthal DB, Kalinina OV. DataSAIL. *Nat Commun* 16:3337 (2025). 10.1038/s41467-025-58606-8
- Offensperger F et al. Large-scale chemoproteomics. *Science* 384:eadk5864 (2024). 10.1126/science.adk5864

Alignment-based methods
- Schmitt S, Kuhn D, Klebe G. Cavbase. *J Mol Biol* (2002). 10.1016/S0022-2836(02)00811-2
- Shulman-Peleg A, Nussinov R, Wolfson HJ. SiteEngine. *J Mol Biol* (2004). 10.1016/j.jmb.2004.04.012 · server 10.1093/nar/gki482 · I2I-SiteEngine 10.1007/978-3-540-30219-3_17
- Schalon C et al. SiteAlign. *Proteins* (2008). 10.1002/prot.21858
- Konc J, Janežič D. ProBiS. *Bioinformatics* (2010). 10.1093/bioinformatics/btq100 · ProBiS-Fold 10.1021/acs.jcim.2c00947
- Gao M, Skolnick J. APoc. *Bioinformatics* (2013). 10.1093/bioinformatics/btt024 · iAlign 10.1093/bioinformatics/btq404
- Lee HS, Im W. G-LoSA. *J Chem Inf Model* (2013). 10.1021/ci4003602 · 10.1002/pro.2890
- Chartier M, Najmanovich R. IsoMIF. *J Chem Inf Model* (2015). 10.1021/acs.jcim.5b00333 · IsoMIF Finder 10.1093/bioinformatics/btv616
- Desaphy J et al. VolSite/Shaper. *J Chem Inf Model* (2012). 10.1021/ci300184x · TIFP/Grim 10.1021/ci300566n
- Eguida M, Rognan D. ProCare. *J Med Chem* (2020). 10.1021/acs.jmedchem.0c00422 · POEM 10.1021/acs.jcim.4c00601
- Sankar S et al. FLAPP. *J Chem Inf Model* (2022). 10.1021/acs.jcim.2c00967
- Bhatti, Yu, Singh. SiteContext. *J Mol Biol* (2026). 10.1016/j.jmb.2026.169791
- Zemla A et al. PDBspheres. *NAR Genom Bioinform* (2022). 10.1093/nargab/lqac078
- Brylinski M. eMatchSite. *PLoS Comput Biol* (2014). 10.1371/journal.pcbi.1003829
- Xie L, Bourne PE. SMAP. *PNAS* (2008). 10.1073/pnas.0704422105

Alignment-free fingerprints
- Yeturu K, Chandra N. PocketMatch. *BMC Bioinformatics* 9:543 (2008). 10.1186/1471-2105-9-543
- Weill N, Rognan D. FuzCav. *J Chem Inf Model* (2010). 10.1021/ci900349y
- Krotzky T et al. RAPMAD. *J Chem Inf Model* (2015). 10.1021/ci5005898
- Wood DJ et al. KRIPO. *J Chem Inf Model* (2012). 10.1021/ci3000776
- Ito J et al. PoSSuM. *Nucleic Acids Res* (2012). 10.1093/nar/gkr1130
- Sydow D et al. KiSSim. *J Chem Inf Model* (2022). 10.1021/acs.jcim.2c00050
- Chikhi R et al. Pocket-Surfer. *Proteins* (2010). 10.1002/prot.22715 · Patch-Surfer 10.1186/1471-2105-13-S2-S7 · 3D-AF-Surfer 10.1038/s42003-022-03261-8
- Xiong B et al. BSSF. *BMC Bioinformatics* (2010). 10.1186/1471-2105-11-47
- Reim et al. SiteMine. *Arch Pharm* (2024). 10.1002/ardp.202300661

Learned embeddings
- Simonovsky M, Meyers J. DeeplyTough. *J Chem Inf Model* 60:2356 (2020). 10.1021/acs.jcim.9b00554 · preprint 10.1101/600304 · https://github.com/BenevolentAI/DeeplyTough
- Scott O, Gu J, Chan AWE. BindSiteS-CNN. *J Chem Inf Model* (2022). 10.1021/acs.jcim.2c00832
- Gao B et al. ProFSA. ICLR 2024. arXiv:2310.07229 · https://github.com/bowen-gao/ProFSA (MIT)
- Oruç T et al. EPoCS. *Bioinformatics* (2025). 10.1093/bioinformatics/btaf284 · https://github.com/tugceoruc/epocs (Apache-2.0)
- Mohan K, Bhargava Y. PocketScope. bioRxiv (2026). 10.64898/2026.08.30.748136
- Zhang et al. ErePOC. *Nat Commun* (2026). 10.1038/s41467-026-69663-y
- Bhadra A, Yeturu K. Site2Vec. *Mach Learn Sci Technol* (2020). 10.1088/2632-2153/abad88
- Gainza P et al. MaSIF. *Nat Methods* (2020). 10.1038/s41592-019-0666-6 · dMaSIF 10.1109/CVPR46437.2021.01502
- Gao et al. DrugCLIP. NeurIPS 2023 · genome-wide screen *Science* (2026) 10.1126/science.ads9530
- Feng et al. LigUnity. *Patterns* (2025). 10.1016/j.patter.2025.101371
- Gaiser et al. Simpatico. bioRxiv (2025). 10.1101/2025.06.08.658499
- Flöge K et al. OneProt. *PLoS Comput Biol* (2025). 10.1371/journal.pcbi.1013679
- Shi W et al. GraphSite. *Biomolecules* (2022). 10.3390/biom12081053
- Li et al. PocketAnchor. *Cell Systems* (2023). 10.1016/j.cels.2023.05.005

Docking/ligand profiles and probes
- Comajuncosa-Creus A, Jorba G, Barril X, Aloy P. PocketVec. *Nat Commun* 15 (2024). 10.1038/s41467-024-52146-3 · code https://gitlabsbnb.irbbarcelona.org/acomajuncosa/pocketvec · mirror https://github.com/sbnb-irb/PocketVec (MIT)
- Kauvar LM et al. Affinity fingerprinting. *Chem Biol* 2:107 (1995). 10.1016/1074-5521(95)90283-X
- Tang GW, Altman RB. FragFEATURE. *PLoS Comput Biol* (2014). 10.1371/journal.pcbi.1003589
- Salentin S et al. PLIP-based profiles. *Prog Biophys Mol Biol* (2014). 10.1016/j.pbiomolbio.2014.05.006 · PLIP 2021 10.1093/nar/gkab294
- Hekkelman ML et al. AlphaFill. *Nat Methods* (2022). 10.1038/s41592-022-01685-y

Scale, motifs, baselines
- Kim H et al. Folddisco. preprint 10.1101/2025.07.06.663357 (Nat Biotechnol 2026)
- Cia G et al. pyScoMotif. *Bioinform Adv* (2023). 10.1093/bioadv/vbad158
- Castillo & Ollila. ActSeek. *Bioinformatics* (2025). 10.1093/bioinformatics/btaf424
- van Kempen M et al. Foldseek. *Nat Biotechnol* (2023). 10.1038/s41587-023-01773-0
- Steinegger M, Söding J. MMseqs2. *Nat Biotechnol* (2017). 10.1038/nbt.3988

PPI and robustness
- Bourgeas R et al. 2P2I analysis. *PLoS ONE* (2010). 10.1371/journal.pone.0009598
- Jubb H, Blundell TL, Ascher DB. *Prog Biophys Mol Biol* (2015). 10.1016/j.pbiomolbio.2015.01.009
- Kozakov D et al. Hot spots at PPI interfaces. *PNAS* 108:13528 (2011). 10.1073/pnas.1101835108
- Cukuroglu E et al. PIFACE (2014)
- Karelina M, Noh JJ, Dror RO. *eLife* 12:e89386 (2023). 10.7554/eLife.89386
- Scardino V, Di Filippo JI, Cavasotto CN. *iScience* 26 (2023). 10.1016/j.isci.2022.105920
- Holcomb M et al. *Protein Sci* 32:e4530 (2023)
- Volkov M et al. *J Med Chem* 65:7946 (2022)
- Eguida M, Rognan D. Review of cavity comparison. *Int J Mol Sci* 23:12462 (2022). 10.3390/ijms232012462

---

## 9. Explicitly unverified / open

Things the brief asked for that I could **not** confirm from a primary source, or that are wrong as stated:

1. **GenomeScreenDB** — not found in Crossref, in the DrugCLIP *Science* 2026 paper, or in any indexed
   publication. Probably a press-article name. Do not cite.
2. **Siteomix, SiteMatcher, ACP4, LEN-Seek, GTA-5, DMPPS, ECIFP, FUSED, PSIM, "metal-binding-site ICP
   alignment"** — no matching methods found. Nearest real equivalents listed in §2.4. **SiteContext**, **POEM**
   and **EPoCS** *do* exist and are described above; the brief's descriptions of POEM and SiteContext were
   approximately right.
3. **ProSPECCTs D8/D9/D10 do not exist**; **D3/D4 are swapped** relative to the brief; **TOUGH-M1 is BMC
   Bioinformatics, not Sci Rep**; **PocketVec's first author is Comajuncosa-Creus, not Balboa**.
4. **ProSPECCTs per-method AUCs** are in supplementary tables I could not retrieve; §3.1 is taken verbatim from
   DeeplyTough's Table 2, which states it reuses those published results. If a number matters for the paper,
   re-derive it from the ProSPECCTs supplements before publishing.
5. **DeeplyTough's journal-version per-dataset ProSPECCTs AUCs** (post-split-change) were not retrieved; §3.1
   lists the bioRxiv v1 row. The TOUGH-M1 discrepancy (0.933 preprint vs 0.91 as quoted elsewhere) is real and
   documented in the repo changelog.
6. **PocketScope** was read only at abstract level (full text not retrieved); its "rank 1 of 23 on ProSPECCTs"
   is its own claim and is unreviewed.
7. **HonestAffinity** (arXiv 2606.03422), the **LIT-PCBA leakage audit** (arXiv:2507.21404), **PocketVec's
   kinase odds ratios (3.2 / 4.1)** and its exact 1.2-billion-pair proteome counts, **Folddisco's journal DOI**
   (inferred from a repo URL), the **EMBL AFDB dimer release numbers**, and most PPI-interface property claims
   in §5 are **[S] or [U]** — second-hand. Verify before any of them enters a manuscript.
8. **No AF-model version of ProSPECCTs or TOUGH-M1 exists** and **no PPI-interface pocket-similarity benchmark
   exists**, as far as two independent searches could establish. Both are opportunities; both are also
   "absence of evidence" claims — phrase them as "we found none" in writing.
9. **URLs unreachable from this container** (may be live elsewhere): sc-PDB (bioinfo-pharma.u-strasbg.fr),
   2p2idb.marseille.inserm.fr, TIMBAL, PIFACE, insilab.org/probis/, compbio.lehigh.edu/GLoSA/glosa.html (the
   parent directory responds 200).
