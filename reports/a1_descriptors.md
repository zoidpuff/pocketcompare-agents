# A1 typed volumetric fingerprint, B0/B1 baselines and the scoring helpers (2026-10-27)

**Code:** `src/pocketcompare/descriptors/{a1,baselines}.py`, `src/pocketcompare/similarity.py`, `configs/a1_grid.yaml`
(16 configs), `scripts/compute_descriptors.py`, `tests/test_descriptors.py` (17 tests, 12 s). **Outputs (git-ignored):**
`data/processed/descriptors/tough_m1/<arm>_<config>_<L|D>.{npy,ids.parquet,ids.parquet.prov.json,layout.json}`.
These cover A1 ×16, B1 ×2 and B0, each in L and D mode: 7,524 pockets per mode, 0 failures, 196 s on 12 workers, 440 MB.
D-mode rows are all pockets with a matched merged BURROW pocket. The ids table carries `d_coverage`, `d_precision`,
`d_missed` and `d_match` (cov ≥ 0.3 or prec ≥ 0.5; 94.5 %), so the caller applies the DESIGN rule.

## Design as implemented (default config, 514 dims)
- **Inputs:** the point cache alone. Protein atoms, names, elements and residue names are cached, so no structure is
  re-read. Analytic point features only; `point_score` is never used.
- **Typing:** each heavy atom gets a VolSite-like type from a residue/atom table (hyd, aro, don, acc, don/acc, pos,
  neg, null; unknown residues fall back to the element).
  - Points are soft-typed by the atoms within 4.5 Å with weights exp(−(d−d_min)/0.5 Å).
  - A cosine taper over the last 0.5 Å makes the type continuous at the cutoff.
  - The metal channel comes from BURROW metal-candidate points (weight 1 voxel); ions are stripped.
- **Resampling:** vol-weighted, done in BURROW's canonical frame X, where its grid lives.
  - Each coarse point is splatted into its 27 voxels; dense voxels win duplicates.
  - Voxels are pooled into 2 Å cells anchored at the pocket's integer bounding-box corner. Cell borders never touch a
    grid point, so there are no round-off flips.
  - Median 125 cells per L pocket (p90 228).
- **Blocks:**
  - *hist* (27): shape + 8 types × bur16 tertiles. Edges are 0.5833/0.85, half-way on bur16's 1/30 grid, fixed
    label-free from 400 pockets.
  - *pair* (392): 28 unordered pairs of {shape, hyd, aro, don+½da, acc+½da, pos, neg} × 14 bins on 2–20 Å, σ = 1.
    Gaussian soft-assignment is normalised over bins, so the end bins are open. The block is normalised by
    W² − Σw² and excludes self pairs.
  - *usr* (84): 7 channels × 4 references × (mean, sd, cube-root skew). The references are the centroid, the
    bur⁴-weighted centroid, a soft-farthest point and a soft-farthest-from-that point. Soft-argmax (T = 0.5 Å) keeps
    them continuous and independent of point order.
  - *glob* (10): vol-weighted means of bur6/10/16, burbb16, depth, escape and nearest; two PCA ratios; R_g/V^⅓.
  - *size* (1): log Å³.
  - Hellinger (√) is applied to *hist* and *pair*.
- **Scoring (`similarity.py`):**
  - `ZScorer.fit(D, ids, ref_ids)`; dimensions that are constant on the reference set map to 0; optional clip.
  - `embed` returns unit rows, either plain cosine or block-weighted cosine (= Σ w_b cos_b / Σ w_b; FAISS-IP
    compatible).
  - `csls_r` gives the top-k mean with self-exclusion; `csls_pair_scores` = s − ½(r_i + r_j).
- **Pair-scoring speed (1 thread):** 0.73 µs/pair at d = 514 and 0.09 µs/pair at d = 45, with 5 M pairs chunked;
  CSLS adds < 0.1 µs/pair.

**B1 (45 dims)** is the 76 `pocket_features` descriptors minus five excluded groups. B1-`learned` (50 dims) adds back
the five size-free learned score summaries (`score_mean/max/top10/top30/q50`).

| excluded group | descriptors |
|---|---|
| extensive (size) | n_pts, vol, sqrt_vol, sat_vol, geo_strength, metal_n, pca1–3, extent, n_res |
| protein context | n_atoms_prot, log_atoms, n_chains, prot_frac (ρ = −0.92 with log protein atoms), f8_wcn (ρ = +0.85) |
| candidate context | level, is_sub, is_score_src, score_rank, score_rel |
| bur24 duplicates of bur16 | bur24_mean, bur24_q90, bur24_q10 |
| learned | all `score_*` |

**B0** is log Å³, scored with `b0_pair_scores` as −|Δ|.

## Per-pocket time (1 thread, excludes npz I/O of 8.7 ms median)

| config | L median / p90 / p99 / max (ms) | D median / p90 / p99 / max (ms) |
|---|---|---|
| default | 6.3 / 14.7 / 35 / 69 | 2.5 / 14.3 / 66 / 537 |

- The ≤ 50 ms target is met for 99.8 % of L pockets and 98.5 % of D pockets. The D-mode tail is merged pockets of up to
  1,597 cells, where the pair block is O(n²).
- `no_resample` is slower: L median 26 ms, p90 100 ms.
- Atom typing costs 0.4 ms per structure.
- B1 takes 1.6 ms; B0 is negligible.

**Vector lengths:**

| config | dims |
|---|---|
| default, no_hellinger, hard_typing, radius_4, no_resample, resample_3A | 514 |
| hist_only | 27 |
| pair_only | 392 |
| usr_only | 84 |
| glob_only | 10 |
| dbins_coarse (10 bins, σ 1.5) | 402 |
| dbins_fine (16, σ 0.75) | 570 |
| dbins_short (12 bins, 2–14 Å) | 458 |
| no_bur | 495 |
| untyped (shape channel only) | 37 |
| no_usr | 430 |

## Tests (17/17 pass)
- **Rotation and translation:** 1a28 is re-featurised in memory, and the L-mode pocket is rebuilt from the rotated
  crystal ligand.
  - Relative error ≤ 1.3e-7 for all 16 configs (tests assert < 1e-4); B1: 7e-10.
- **Point order and determinism:** a permuted index gives < 1e-5 (default, raw and hard typing); repeat runs are
  byte-identical.
- **Identity and type permutation:** identity scores 1. A type-permuted copy (hyd↔neg, aro↔don, acc↔pos) scores
  < 0.9, both plain and block-weighted.
- **Known answer:** two points at r_k peak at bin k and match the exact Gaussian weights. Points at 60 Å fall in the
  last bin. A typed two-point pocket gives the expected per-pair histograms through the full pipeline.
- **Thinned vs dense:** a BURROW-style thinned copy (41 % of the volume in vol = 27 points) vs its dense copy.
  - Cosines after resampling: hist 0.9989, glob 0.99995, pair and usr identical.
  - Vol weighting alone already removes most of the artefact (pair relative difference 0.016 without resampling).
- **Uniform scaling:** a 1.5× pocket at the same density.
  - hist cosine 0.996, glob relative difference 0.024, and Δ size = log 1.5³.
  - pair and USR change by design, because they are in Å.
- Typing table spot checks, continuity at the cutoff, the metal channel on a cached pocket, B1 column counts, and
  z-score / block-cosine / CSLS checked against brute force.

## Deviations and notes
1. Two choices the DESIGN did not specify:
   - The lattice is anchored per pocket, which is what makes it exactly invariant.
   - USR uses soft-argmax extreme points instead of argmax, for continuity.
2. Grid size: 16 configs, not 20. Block weights (size 0.25) are a scoring-time option (`score_weights`), not a config.
3. Storage: the default is 514 floats (2 KB) per pocket, above the 512 B tier-1 budget. The plan reaches the budget
   only through the A4b projection or PQ.
4. **Label-free control (no labels used): the same site in L and D mode vs random pairs.** Z-scored on all L pockets;
   AUC of same-site vs random pairs:

   | arm | AUC | MRR |
   |---|---|---|
   | A1 default | 0.70 | 0.07 |
   | A1 hist_only | 0.79 | 0.09 |
   | A1 untyped | 0.55 | — |
   | B1 | 0.94 | 0.28 |

   - For A1 the AUC is 0.79 at coverage ≥ 0.7 and 0.54 at coverage < 0.4.
   - A1 encodes the specific sub-region, so it is more sensitive to how far the pocket extends than B1, whose f8_*
     features are smoothed over 8 Å.
   - This is a robustness signal, not accuracy, and nothing was tuned on it. It argues for the A4b fusion with B1 and
     for L-vs-D augmentation pairs.
5. **Provenance:** the descriptors were computed from an uncommitted working tree (`git_dirty`; the sidecars record
   the script sha256). Re-run after the commit (about 4 min) for clean sidecars.
   - Separately, `provenance.git_state` cuts the first character of the first dirty path ("cripts/…"), because
     `.strip()` runs before `ln[3:]`.
