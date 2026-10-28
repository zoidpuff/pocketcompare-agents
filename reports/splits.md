# Homology graph and splits (data agent, 2026-10-27 21:40)

> **Superseded counts (2026-10-28, D15):** the graph and all splits were rebuilt after the audit (MMseqs2 `-a`, exhaustive Foldseek with exact TM). Current numbers, moved units and the PPIPS BURROW-homology flag are in `data/splits/SPLITS.md`; the numbers below are the pre-audit version.

Full tables are in `data/splits/SPLITS.md`. Rebuild with `scripts/data/run_splits.sh` (~25 min on 24 threads).
`verify_splits.py` runs 66 independent checks and all pass.

## Numbers
- **Graph:**
  - 65,326 chains and 35,628 unique sequences.
  - 2.71 M edges: 1.02 M from MMseqs2 under BURROW's rule and 2.48 M from Foldseek TM ≥ 0.5 in both directions. 1.69 M edges are Foldseek-only.
  - Largest within-dataset component: TOUGH-M1 5.1 %, ProSPECCTs 6.6 %, BLiPS 9.6 % (all pass the gate). **Vertex 25 % and dimers 24 % fail the gate.** The global component is 49.8 %, which confirms the round-2 change to per-dataset components.
- **TOUGH-M1:**
  - dev: 731 pockets, 3,366 positive / 6,463 negative pairs, 276 ligand clusters.
  - test: 1,014 pockets, 10,064 positive / 13,221 negative pairs, 302 ligand clusters.
  - **excluded: 5,779 pockets (77 %).** Of these, 4,595 touch ProSPECCTs, 3,947 af_set, 1,589 Vertex and 212 PPI-L-test.
  - 411,610 cross-partition pairs were dropped.
  - Dev and test pairs carry the shipped APoc, G-LoSA and SiteEngine scores; 100 % of pairs matched.
- **BLiPS** (train / val / test):
  - sites: 2,699 / 163 / 3,606
  - proteins: 1,772 / 99 / 2,304
  - positive pairs: 8,000 / 335 / 6,895
  - negative pairs: 40,000 / 1,675 / 34,475
  - test positives, seen vs unseen chemotype: 6,267 vs 628
  - 1,700 of 3,472 train proteins were removed for direct edges to test sets.

## Problems for the PI
1. **The exclusion rule removes most of TOUGH-M1.** Structural edges are dense, so 79 % of TOUGH-M1 chains touch BURROW directly and most of those also touch a sealed set. C1 then rests on 1,014 test pockets (23 k pairs instead of 1.06 M). The threshold sensitivity (counts only) is below. A stricter structural rule for *cross-dataset exclusion* (for example TM ≥ 0.7) would roughly double test; the choice is a design decision.

   | edge rule | dev / test / excluded pockets | BURROW train+dev removed |
   |---|---|---|
   | TM ≥ 0.5 (adopted) | 731 / 1,014 / 5,779 | 2,637 |
   | TM ≥ 0.6 | 1,105 / 1,608 / 4,811 | 1,869 |
   | TM ≥ 0.7 | 1,290 / 2,370 / 3,864 | 1,222 |
   | TM ≥ 0.8 | 1,439 / 3,146 / 2,939 | 734 |
   | sequence edges only | 1,543 / 3,589 / 2,392 | 536 |

2. **BLiPS-val is weak.** It has 99 proteins and 335 positives in 15 ligand clusters, and one sugar cluster holds 59 % of the positives. The ≤ 10 % cluster share cannot be reached. Selecting on BLiPS-val will be noisy.
3. **The largest BLiPS-test homology group is 25 % of test proteins.** The positive/negative rule ("different groups") still works, but cluster-balanced bootstraps will be dominated by that group. DataSAIL is proposed if test has to be split further.
4. **The sealed TOUGH-M1 file was read twice by `make_tough_m1_split.py`.** The first run used a graph with a node-mapping bug; the rerun produced the same partition. Only counts were printed. All sealed and raw files are back to mode 000, and this is checked.

## Decisions not dictated by DESIGN
- **Nodes:**
  - BURROW assembly-partner chains count as BURROW (this affects 253 excluded and 2 dev pockets).
  - ProSPECCTs decoys were skipped.
  - Vertex chains are the ones carrying the HET instances. 18 Vertex entries are obsolete and have no node.
  - BURROW's test union was not added.
- **Edges:** sequences are the residues observed in the structure. Foldseek used model 1 and chains ≥ 20 aa, with `-s 7.5`, `--max-seqs 2000` and exhaustive search off.
- **TOUGH-M1 groups:**
  - Membership is decided at group level: a group is "touching" if any member touches.
  - Ligand clusters come from ECFP4 of the shipped SDF with Butina at Tc ≥ 0.6. I read "Butina(0.6)" as a similarity cutoff.
- **BLiPS sites and ligands:**
  - The positive/negative label uses the maximum Tc over each site's full set of qualifying ligands. The label ligand (the largest qualifying one) only defines the site's cluster.
  - Test ligands are af_ligands rows with status = ok, which is at most 5 per site.
  - ECFP4 ignores chirality, so sugars such as GLC and GAL collide.
  - The additives list keeps free fatty acids, cofactors and free sugars. It excludes N-glycan sugars (NAG, MAN, BMA, FUC, SIA), lipids/sterols, pigments (including phycobilins) and detergents.
  - The "< 10 BURROW points" exclusion is **not applied**, because it needs the point cache.
- **BLiPS caps and sampling:**
  - When a val protein shares a component with train, the val protein is dropped.
  - The ≤ 3 sites per protein keep distinct label clusters first.
  - The cluster cap is the largest value ≤ 300 that meets the 10 % share, with a minimum of 25.
  - Negatives are sampled uniformly at 5× the positives.
  - Promiscuous CCDs are the top 20 by number of train sites.
- **Score columns:** the shipped scores are kept as `<tool>_c1…` in file order. I did not inspect their meaning.
- **File size:** `homology_edges.parquet` is 18.6 MB (zstd). The PI decides whether to commit it.
