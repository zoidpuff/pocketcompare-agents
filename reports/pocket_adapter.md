# Pocket adapter + TOUGH-M1 point cache (DESIGN §2.1) — 2026-10-27

**TOUGH-M1, all 7,524 pockets / 7,524 structures:** 100 % success (0 failures). Wall time 113 s on 32 CPU workers
(66 structures/s); per structure median 0.42 s, p90 0.75 s, max 3.0 s (featurise 0.28 s, npz write 0.08 s).
Disk: 6.4 GB (npz median 0.82 MB). Points per structure: median 4,984 (max 25,506).
**L-mode** (ligand file, 4 Å): median 352 points (p90 658, min 16) = 542 Å³ (p90 1,091), 28 lining residues.
**D-mode** (merged region-rule pockets): miss rate (coverage < 0.3) **19.4 %**; median coverage 0.51; full list
17.5 %. 13.9 % of all pockets are "missed" but located: the matched pocket lies inside the site (precision ≥ 0.5)
and is just smaller than the 4 Å ligand shell. Only **5.5 %** are missed and not located. The matched pocket is
BURROW's best merged pocket in 68 % of cases.

## What was built
- `src/pocketcompare/pockets.py`
  - `featurize_structure(path|Structure, chains, af_mode, preset, ranker)` runs the BURROW reference pipeline
    once on the protein-only view (ligands, waters, ions and H removed).
  - It keeps **all** featurised solvent-shell points: dense points (`vol`=1), coarse sub-lattice points
    (`vol`=27) and metal candidates (`vol`=0, `is_metal`), with the 84 analytic features.
  - `point_score` (learned) is stored separately and is for ablations only (§2.6).
  - It also stores the protein atom table, the stripped hetero atoms (used for ligand-residue definitions),
    BURROW's full pocket list (≤ 50) with CSR memberships, scores, residues, 76 descriptors, and
    `pk_in_region`/`pk_in_v2` flags. Volumes are always Σ`vol`·spacing³.
  - `lmode_from_ligand` / `lmode_from_residues` (bur10 ≥ 0.5), `merge_pockets` (≤ 1.5 Å or residue Jaccard ≥ 0.3),
    `dmode_match` and `coverage`. `resolve_pocket` applies the precedence: shipped ligand file, then ligand
    residue in the file, then residue list. Every threshold is a parameter.
- `scripts/build_point_cache.py --dataset tough_m1 --workers 32` (resumable, spawn pool, 1 thread/worker) writes:
  - `data/processed/cache/points/<ds>/{<key>.npz, index.parquet, timing.parquet, summary.json}`;
  - the marker `logs/build_point_cache_<ds>.done`;
  - a committed copy of the summary in `results/pocket_cache/tough_m1_summary.json`.
- The index has one row per pocket:
  - L-mode point indices, n points, dense points, Å³ and lining residues; `definition` (TOUGH-M1: `ligand_file:sdf`);
  - the residue-list alternative (`alt_*`: indices, size, Jaccard, chain remap);
  - D-mode members, coverage, `missed`, precision, rank, n/Å³, plus full-list coverage;
  - ligand–protein distance, and status/failure reason.
- Provenance stored in each npz `meta`:
  - pocket_detect commit `73cb2759…` (src clean);
  - model `results/dev/freeze_v2/models/burrow_all_default_s0.json` and its sha256;
  - feature/formation config and the structure sha256.
- Sealed sets: `prospeccts` and `vertex` are refused unless `FINAL_EVAL=1`. They were not run, and no pair or
  label file was opened.

## Verification (`tests/test_pockets.py`, 9 tests, 6 s)
- **Equivalence:** points, features and pocket sets equal `pocket_representations` for the region, v2 and full lists.
- **Invariance:** an in-memory rotation + translation gives the same points (≤ 1e-5 Å). Scores and canonical
  coordinates are identical, and features are equal except < 1 % of points, where an atom sits exactly on a
  4/8/12 Å count boundary. A rotated PDB file (rounded to 1e-3 Å) gives ≥ 99.5 % matched points, < 1 % changed
  feature values and a median difference of 0.
- **L-mode, 1a28 + crystal progesterone (STR):** 307 points / 305 Å³, contains Gln725/Arg766/Asn719.
- **D-mode:** coverage 0.99 by BURROW's top pocket. Merged pockets partition the region list. Negative control:
  points > 25 Å from the ligand have coverage 0.
- **Determinism:**
  - a repeat run gives byte-identical npz files;
  - a 300-structure driver re-run with `--overwrite` gives 0 mismatching index cells and 0 array/meta mismatches;
  - the SDF and PDB ligand files agree exactly (300 checked).

## Issues and caveats for the PI
1. **Benchmark-table bug:** the `pocket_def` column of `tough_m1_pockets.parquet` hardcodes `A:`.
   - The structure files keep the original chain letter (3,191 / 7,524 are not `A`).
   - The adapter remaps the chain for single-chain files and records `alt_chain_remapped`. After the remap, no
     residues are missing.
   - Fix it in `datasets/tough_m1.py` (owner: data agent).
2. **The D-mode coverage ≥ 0.3 rule penalises size mismatch.**
   - BURROW pockets are compact cores (sub-pockets of ~6 Å). L-mode is the whole 4 Å ligand shell.
   - Suggestion: report `d_precision` alongside, or define "missed" as coverage < 0.3 **and** precision < 0.5
     (5.5 %). This is a DESIGN decision, so the current spec is unchanged.
3. **L-mode definitions differ in size.** The residue-list alternative (fpocket residues + bur10 ≥ 0.5) is about
   2× larger than the ligand pocket (median 672 vs 352 points) and has a median Jaccard of only 0.39 with it.
   Ligand-defined pockets are used throughout.
4. **Ligand contacts.** 20 ligands sit < 1 Å from protein atoms (covalent adducts or clashes) and 621 sit < 2 Å.
   They are kept and flagged by `ligand_protein_min_dist`.
5. **Vertex `ligand_het_site` is unverified.** Its `site_index` is mapped to the k-th HET instance; this must be
   checked before the final evaluation. ProSPECCTs `LIG:chain:resnum` is implemented but has not been run.
