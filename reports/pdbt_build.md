# PDB-T build (PREREG2): temporal held-out pocket-pair set (2026-10-28, 06:40–07:35)

**Gate: PASS.** The set has 1,353 positive pairs spanning 186 homology groups and 38 ligand clusters (rule: ≥ 300 / ≥ 30 / ≥ 10). It is recorded in `results/pdbt/gate.json`, which was written before the seal.

The pairs are sealed in `data/sealed/pdbt_pairs.parquet` (mode 000) with sha256 `b4bf2909f44a819f4a1fd5160a23e30b2fbbc7695082aaeb460b7899d1f70c60`. The hash was appended to `data/sealed_SHA256SUMS.txt` in the same step, and `data/sealed` was restored to r-x. No similarity score or method output was computed.

## Funnel
| step | count |
|---|---|
| mirror entries (all have a revision history; 45 k older-format files needed a full parse, not just the header) | 261,139 |
| first revision released > 2025-11-12 (range 2025-11-19 … 2026-10-21) | 16,533 |
| X-ray or EM | 16,271 |
| resolution ≤ 3.0 Å | **11,585** (X-ray 8,337 · EM 3,248) |
| non-polymer, non-water ligand instances | 190,182 → ion 109,418 · additive 53,440 · < 10 HA 2,808 · no CCD SMILES 325 · covalent 1,928 · < 10 observed HA 696 · no protein chain ≥ 50 aa 204 · no contact ≤ 4 Å 864 → **qualifying 20,499** (3,367 CCDs, 2,327 Butina clusters) |
| physical sites (on primary chain) → one per (chain, ligand cluster) | 17,696 → 14,528 (5,596 entries, 13,036 chains) |
| ≥ 2 contacting residues | 14,244 |
| after leakage removal (below) | 4,156 |
| one per (entry, protein, cluster) → ≤ 3 per protein (BLiPS rule) | 1,910 → **996 sites** · 545 proteins · 882 entries · **317 groups** (largest 12 proteins = 2.2 %) |
| < 10 L-mode points | 0 excluded |

**Pairs** (`make_blips_split.make_pairs`, unchanged; seed `SEEDS[0]`):
- Positives: 1,353 (17,972 before capping). The per-cluster cap is 135, giving a maximum cluster share of 9.98 %; no positive has ≥ 2 shared ligands.
- Negatives: 6,765 (5×), drawn from 431,003 eligible.
- 682 positives touch a top-20 promiscuous CCD. In 1,127 / 1,353 positives (83 %), a best-matching CCD also occurs in BLiPS-train. **The proteins are new, but most chemotypes are not.**

## Leakage (direct edge = MMseqs2 `-a` + BURROW `apply_rule`, or exhaustive Foldseek min-TM ≥ 0.5 with exact TM in [0.45, 0.60); searches run both directions)
- **Training sids:** 10,943, of which 10,922 have a structure. By source: BLiPS v2 train/val 1,851 · BURROW representatives 7,053 · BURROW assembly partners 1,870 · PPIPS train/val 1,655 (1,740 complexes) · TOUGH-M1-dev 765.
- **Removed:**
  - 9,082 / 13,036 chains, i.e. 4,284 / 5,939 unique sequences and 9,845 sites.
  - By rule: a sequence edge for 5,955 chains; a Foldseek edge only for 3,127.
  - Chains with an edge to each source (overlapping): BURROW rep 8,239 · partner 3,476 · PPIPS 3,219 · BLiPS v2 2,065 · TOUGH-dev 594.
- **Freshness:** 208 further chains had an exact sequence in a test set and were removed (TOUGH-M1-test 109, Vertex 103, ProSPECCTs 45, af_set 2; overlapping).
  - 1,486 chains share a UniProt accession with BLiPS-test (af_set). These are only **flagged** (`test_uniprot_af_set` in `data/processed/pdbt/chain_homology.parquet`), not removed, because their sequences are not exact matches.
- **PDB-T groups:** connected components of the all-vs-all graph over the 1,622 kept sequences, using the same edge rule. There are 319 components, 317 of which have sites.

## Caches (label-free, 22 workers, ~1 min total)
- **Point cache:** 996 / 996 sites succeeded, on 960 structures in 37 s. L-mode median is 387 points (642 Å³).
- **D-mode:** 883 / 996 sites match (88.7 %); the region-rule miss rate is 31 %.
- **Descriptors:** a1r (L/U × sph8/base), N1/N2 inputs (`n_inputs_{L,D}`), `b1_default_{L,D}`, `b0_default_{L,D}` and a1 pair_only/default each ran on 996 sites with 0 errors.
- **L4 point sets:** `data/processed/l4/pdbt` has L and U for all 996 sites, with 0 empty sets and 0 mismatches against a1r.

## Definitions not fixed by PREREG2
All of these were set before any pair existed.
1. **Ligand qualification:** the ligand has no `struct_conn covale` link and at least 10 observed heavy atoms.
2. **Chain assignment:** each ligand instance goes to its primary chain, which is featurised alone, as in BLiPS. A site needs at least 2 contacting residues (BioLiP's rule).
3. **Physical sites:** instances within 4 Å of each other form one site. `q_ccds` is the set of their CCDs, and the L-mode site is the union of their atoms.
4. **Proteins:** a protein is its UniProt accession(s), or its sequence when no accession is available. Homo-oligomer copies of the same site within one entry count once.
5. **Partner chains:** BURROW assembly partners count as training data (conservative).

## Order and provenance
- **Order:** the label-free point cache was built before the pairs, so the < 10-point exclusion (DESIGN §2.6) could be applied before pairing, as for BLiPS v2.
- **Ligand identities:** after sealing, CCD and cluster columns were stripped from every unsealed intermediate. `data/splits/pdbt_sites.parquet` has no labels and contains `site_id`, `hom_component` and `excluded`.
- **Files:**
  - Scripts: `scripts/data/{run_pdbt.sh, pdbt_enumerate.py, build_pdbt.py, pdbt_homology.py}`.
  - Code change: `build_point_cache.py` now accepts `pdbt`.
  - Logs: `logs/pdbt_*.log`.
  - Counts: `data/processed/pdbt/*.json`, `results/pdbt/{gate,build_counts}.json`.
  - The CCD is in `data/raw/ccd/` (sha256 in `DATA.md`).
