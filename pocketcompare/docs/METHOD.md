# Method: every step and parameter

Frozen method `pocketcompare-final:A4b:n1_linear|raw` (`configs/final_method.yaml`). The values below are those of
the shipped configuration and code; nothing here is tunable without changing the fingerprint. Research names in
brackets (A1, env/"A1r", N1, A4b, sph8, L/D mode) are the names used in the evaluation reports.

```
structure (PDB / mmCIF; AlphaFold model; multi-chain complex)
 │ 1. BURROW on the protein only (ligands, waters, ions, cofactors stripped)               0.1–0.4 s
 ▼
 2. located point set: merged BURROW pocket │ 4 Å ligand shell │ residue shell │ BURROW pocket at a site
 ▼
 3. sph8 site: buried points (bur10 ≥ 0.5) within 8 Å of the vol·bur16⁴-weighted centroid      < 0.5 ms
 ▼
 4./5. N1 = A1 typed volumetric fingerprint (514) ⊕ env protein-environment block (113)       ~3.5 ms
 ▼
 6./7. z-score (fixed statistics), clip ±5 → 3 linear heads 627→128, L2 each → concat / √3      64 µs
 ▼
 8. 384-d unit vector; score = inner product (= mean per-seed cosine)
```

## 1. BURROW featurisation (`pockets.featurize_structure`, `pockets_fast`)

- BURROW 1.0.0 (`burrow-pockets`, import `pocketdetect`), preset `default`, ranker `all`, model
  `models/burrow/burrow_all_default_s0.json` (sha256 `f33963e7…`; pinned and verified on load).
- Input view: protein heavy atoms of the first model (`chains=` restricts chains); ligands, waters, ions, nucleic
  acids, cofactors and hydrogens are removed before BURROW runs. Stripped hetero atoms are kept only to resolve
  ligand-defined sites.
- `af_mode=True` (`--af-mode`): BURROW AF mode (pLDDT read from the B-factor column; low-confidence residues pruned;
  soft occlusion). Use it for every AlphaFold model.
- Grid: 1 Å spacing in BURROW's canonical (PCA) frame. Points kept: every featurised point, i.e. dense LIGSITE
  survivors (`vol` = 1 voxel), coarse sub-lattice points standing for the exposed shell (subsample 3 → `vol` = 27
  voxels) and metal candidates (`vol` = 0). Volumes are `Σ vol × 1 Å³`.
- 84 analytic per-point features (buriedness `bur6/10/16` = fraction of 30 rays of length 6/10/16 Å that hit the
  protein, `burbb16`, depth, escape, nearest-atom distance, first-hit chemistry, residue-group counts and atom
  composition within 4/8/12 Å, metal-candidate flag, …). BURROW's learned point score is **not** used.
- Pockets: BURROW's full output list (`min_score = None`, ≤ 50 after NMS); the method uses its region-rule subset
  (`c16_0.005`, BURROW's `--output-rule region`).
- The reference (`--backend ref`, default), Numba CPU (`--backend fast`) and GPU (`--device cuda:N`) backends give
  identical points, pockets and fingerprints.

## 2. Located point set

| call | located set |
|---|---|
| `describe_all(structure)` (deployment; CLI without a site) | BURROW region-rule pockets merged into connected components (edge: any two points ≤ 1.5 Å apart, or residue Jaccard ≥ 0.3); merged pockets with < 10 points dropped (removes single-point metal candidates). Located set = union of the members. Rows in order of the best member's BURROW rank. `unit="member"`: every region sub-pocket instead. |
| `describe(structure, site=ligand)` (L mode, `locate="shell"`) | grid points ≤ 4.0 Å of any ligand heavy atom (`.sdf`/`.mol` V2000 atom block, `.pdb` ATOM/HETATM, or an (n, 3) array) |
| `describe(structure, site=["A:43", …])` | grid points ≤ 4.0 Å of a heavy atom of the listed residues **and** bur10 ≥ 0.5 (single-chain files: a missing chain id is remapped to the only chain) |
| `locate="burrow"` (D mode, as in the evaluation) | (a) region pockets merged as above; (b) the merged pocket with the highest coverage of the site points (a site point is covered if ≤ 1.5 Å of a pocket point; ties → higher score, better rank); (c) its single member with the highest coverage (ties → better rank) |
| `locate="burrow_flat"` | step (c) over all region pockets, without (a)–(b) |
| `describe(structure)` (no site) | every region-rule sub-pocket separately |

## 3. Site shaper sph8 (`pockets.shape_site(…, "sph8")`)

1. Centre = centroid of the located set weighted by `vol × bur16⁴` (falls back to `vol`-weighted, then plain
   centroid if the weights vanish).
2. Described set = **all** grid points of the structure (not only the located set) within 8.0 Å of the centre with
   bur10 ≥ 0.5.
3. If that set is empty (a fully solvent-exposed site), the located set itself is described (`sph8_fallback`).

The located set therefore only *locates* the site; ligand-shell and detected-pocket sites differ only in their
centre, not in how their extent is cut. This removed the ligand-size imprint of ligand-shell pockets.

## 4. A1 typed volumetric fingerprint, 514 d (`descriptors/a1.py`, configuration hash `8f4f566dbad665ba`)

1. **Atom typing** (VolSite-like): every protein heavy atom gets one of null / hydrophobic / aromatic / donor /
   acceptor / donor-acceptor / positive / negative from a residue × atom-name table (e.g. Ser OG donor-acceptor,
   Lys NZ positive, Asp OD1/OD2 negative, backbone N donor and O acceptor, Pro N and Gly CA null; unknown residues
   fall back to the element: C/S/Se hydrophobic, N donor, O acceptor).
2. **Point typing**, soft: weights `exp(−(d − d_min)/τ)` over the atoms within radius 4.5 Å (τ = 0.5 Å, at most 32
   atoms), times a cosine taper of width 0.5 Å that brings each atom's weight, and the whole point via `d_min`, to 0
   at 4.5 Å (continuous in the coordinates). Metal-candidate points form an 8th channel `met` with weight 1 voxel.
3. **Resampling** in BURROW's canonical frame: coarse points are splatted into their 3³ voxels (dense voxels win
   duplicates), voxels pooled into 2 Å cells anchored at the site's bounding-box corner; cell weight = voxel count,
   cell position/attributes = voxel means.
4. **Blocks** (cell-weighted):
   - `hist` (27): volume fraction per channel (shape + 8 types) × 3 bur16 bins (edges 0.5833, 0.85);
   - `pair` (392): typed pair-distance distributions for the 28 unordered pairs of channels {shape, hyd, aro, don,
     acc, pos, neg} (`don`/`acc` absorb half of `da`), 14 Gaussian-soft-assigned bins on 2–20 Å (σ = 1 Å; first
     and last bins open-ended), normalised by `W² − Σw²`;
   - `usr` (84): USRCAT-like moments: for 7 channels × 4 reference points (centroid, bur16⁴-weighted centroid,
     soft-farthest point from the centroid, soft-farthest from that point; soft-argmax T = 0.5 Å) the weighted
     mean, standard deviation and signed cube root of the third central moment of distances (Å);
   - `glob` (10): volume-weighted means of bur6, bur10, bur16, burbb16, depth, escape, nearest; √(λ₂/λ₁), √(λ₃/λ₁)
     of the cell covariance; R_g / V^⅓;
   - `size` (1): log volume (Å³).
5. **Hellinger**: square root of the `hist` and `pair` blocks.

## 5. env protein-environment block, 113 d (`descriptors/env.py`, version a1r-v1)

On the same sph8 point set (weights = `vol`, metal candidates 1 voxel), from BURROW's analytic point features:
- `env_mean` (49): weighted means of first-hit chemistry fractions (apolar, polar, charged, aromatic), residue-group
  counts within 4 Å (7 groups) and atom/residue-group composition fractions within 8 Å and 12 Å (C, N, O, S,
  aromatic, hydrophobic side-chain C, donor, acceptor, backbone, side chain, positive, negative + 7 residue groups);
- `env_bur` (49): the same, weighted by `vol × bur16⁴`;
- `env_hist` (15): first-hit chemistry × bur16 tertile volume fractions (12) + tertile volume fractions (3).

All env features are intensive (size-free).

## 6. Input scaling (`models/n1_linear/input_stats.json`)

N1 = [A1 | env] (627 d). Each part is z-scored with the mean and standard deviation of 4,636 reference rows (the
BLiPS-train sites, described both as ligand shells and as detected pockets; label-free). Dimensions with a
standard deviation ≤ 1e-8 · max(1, |mean|) in the reference map to 0; NaN → 0. The concatenated z-scores are
clipped to [−5, 5].

## 7. Projection head (`models/n1_linear/seed{0,1,2}.npz`)

Three linear heads (training seeds 0, 1, 2), each `z ↦ W z + b` with W ∈ ℝ^{128×627}, followed by L2 normalisation.
The fingerprint is the concatenation of the three unit vectors divided by √3 (384 d, unit norm). Inference is plain
numpy (`head.head_forward_np`); PyTorch is only needed for training.

## 8. Score and search

- `similarity(a, b) = a · b` = mean over the three heads of their cosines; −1 … 1.
- Optional CSLS hub correction (not the default; it did not improve held-out accuracy):
  `s − (r_a + r_b)/2`, with r = mean of the top-10 similarities to the database (`similarity.csls_r`).
- `pocketcompare index`: `IndexFlatIP` (exact) or `OPQ64_384,IVF{nlist},PQ64` (`--kind ivfpq`; nlist ≈ 4√n, power of
  two; nprobe 64) with fp16 copies of the vectors for an exact re-rank of the top-100 (`search --rerank 100`).

## 9. Training the published head

Research script `train_a4b.py`, configuration `n1_linear`; ported as `scripts/train_head.py` (the port is compact
and not bit-identical to the original run: the original drew each BLiPS endpoint at random in ligand-shell or
detected-pocket form, the port treats every form as its own pocket).

| item | value |
|---|---|
| positive sources (sampling weights) | BLiPS ligand-sharing pairs 0.5; same-site ligand-shell ↔ detected-pocket pairs 0.25; AlphaFold-dimer interface pocket pairs (PPIPS) 0.25 |
| data (`models/n1_linear/config.json`) | 2,318 BLiPS-train sites; 33,334 labelled training pairs (5,574 positive); 1,560 same-site pairs; 15,555 dimer pockets with 3,327 positive pairs (2,284 symmetric copies, 1,043 interologs) |
| never used | TOUGH-M1, BLiPS-val/test, PPIPS-val/test, ProSPECCTs, Vertex, PDB-T, or homologues of their proteins |
| loss | symmetric InfoNCE (τ = 0.1, 256 positive pairs per batch, in-batch negatives; logits of pairs that may be positive are masked: same pocket, same homology group, known positive) + 1.0 × BCE on 512 balanced labelled BLiPS pairs (logit = a · cos + b; a, b learnable, initialised 10, −5) |
| model | dropout 0.2 on the input → Linear 627 → 128 |
| optimisation | AdamW, lr 1e-3, weight decay 1e-4; 50 steps per epoch, ≤ 80 epochs |
| early stopping | 10 % of the BLiPS-train homology groups (247 sites, 98 groups, 8,618 pairs) held out; metric = mean of ligand-shell and detected-pocket ROC-AUC; patience 10; best epochs 3, 4, 5 |
| selection | among candidate descriptors and heads, by BLiPS-val detected-pocket cluster-balanced AUC with a one-SE rule (pre-registered) |

## 10. Properties checked by the tests

- Golden: fingerprints of the example structures computed with the research code are reproduced to ≤ 1e-6 (here:
  bit-identically).
- Rigid motions: the fingerprints of a rotated and translated copy of a structure must agree with cosine > 0.995
  (ligand site) / > 0.99 (every pocket); A1 alone must agree to a relative error < 1e-4 whenever the point set is
  identical (BURROW's float32 features can flip single boundary points).
- Determinism, point-order invariance, identity = maximum similarity, identical reference / fast / GPU backends.
