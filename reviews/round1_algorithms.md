# Review round 1 — algorithms, scaling and compute (DESIGN.md v0)

Reviewer: algorithms/HPC agent, 2026-10-27. Read: PROMPT.md, DESIGN.md v0, LITERATURE.md §1/§3/§4/§7,
reports/fragment_docking_feasibility.md, pocket_detect/FOR_FURTHER_DEVELOPMENT.md §2–§5, results/feasibility/*.
Verdict: the arm set is sound. Two-tier design, A2 as a gated tier-2 arm, and the B0/B1 baselines are right.
Four things need fixing before implementation: A1 has a grid-sampling artefact, A3 has a reflection bug and
no plan for meeting its cost target, A4 is too large for the time left, and no arm handles hub pockets.

## Arm-by-arm

**A1 (typed 2-point histograms): keep as the main tier-1 bet, with these specifications.**
- *Sampling artefact.* BURROW thins exposed points to a 3 Å sub-lattice, each carrying `vol` = 27 voxels.
  Unweighted pair histograms then mix two lattices. The 1–3 Å bins end up encoding "how much of the pocket is
  buried" rather than shape, and shallow PPI pockets suffer most. Fix: weight every point by `vol`, resample to a
  uniform 2 Å lattice (or drop bins below 3 Å), and run a unit test showing that a thinned copy and a dense copy
  give the same fingerprint.
- *Typing.* Use soft channels, not argmax. Hard types from `hit_*` fractions are almost all "apolar".
  Precedent: VolSite types each cavity point by its nearest protein atom within 4 Å (hydrophobic, aromatic,
  donor, acceptor, donor/acceptor, cation, anion, null). Do the same with a KD-tree on `load_protein` atoms, or
  derive weights from `n4_{donor,acceptor,positive,negative,aromatic,hydrophobic_sc_C,coord}`. That gives K ≈ 7
  channels plus a shape channel (all points). The weighted histogram is
  H_ab(r) = Σ_ij w_ia·w_jb·g(d_ij − r).
- *Binning.* Use 12–16 Gaussian-smoothed bins (σ ≈ 1 Å) from 2 to 20 Å, with the last bin open. That gives
  28 type pairs × 14 bins ≈ 400 dims, plus 7 types × 4 `bur16` bins. Apply a Hellinger (√) transform and per-dim
  z-scoring on dev, then cosine. The √ step is free and usually beats raw-count cosine.
- *Cheap add-on to test inside A1: typed USR/USRCAT.* Take the first three moments of each channel's distances
  to 4 reference points (centroid, the most buried point, and the two extreme points), ≈ 84 dims. It is a proven
  fast ligand-shape analogue and captures layout that pair histograms blur.
- *Not worth the time:* persistent homology (gudhi is not installed, there is no evidence of benefit, and
  mouth/enclosure is already in `escape`/`psp`). Spherical-harmonic or Zernike invariants need a stable centre,
  which D-mode pockets lack. Full 3-point (FuzCav) hashing on 100–400 points gives 10⁶–10⁷ triplets per pocket and
  thousands of sparse dims, and FuzCav itself is mediocre on P5–P7. Revisit it only on ≤ 40 pseudocentres (see A3).
- *Overfitting guard.* Pre-register the A1 grid (≤ 20 configs) before tuning on TOUGH-M1-dev.

**A2 (docking profiles): keep it gated. Specify how size is removed and where poses must lie.**
- PC1 still carries 43 % of the variance after dz. So pre-register one normalisation:
  1. score per heavy atom^0.3 (ligand efficiency);
  2. per fragment, the residual of a regression on (log n_pts, mean bur16, apolar fraction), fitted on
     dev-background pockets;
  3. rank (PocketVec style).
  Variant (a) uses only steps 1 and 3; variant (b) uses steps 1–3.
- *In-pocket constraint.* The ±4 Å box lets fragments dock outside shallow pockets; the feasibility report saw
  this on tiny pockets. A pose counts only if ≥ 50 % of its heavy atoms lie within 2 Å of a pocket point.
  Otherwise the fragment goes to the non-binder bin. This is decisive for PPI pockets.
- *Pose profile (c).* Reuse ADock's XS receptor typing for contacts (no new typing code). Use the best pose
  only. Represent it as a 64 × 6 matrix compressed to ≤ 128 dims by PCA fitted on train.
- *Cost check.* Gating on TOUGH-M1-dev is about 2.2k pockets × 128 fragments × 2 panels, i.e. minutes. At AFDB
  scale it remains tier-2 or reference-set only (78 node-days for 64 fragments).

**A3 (Gaussian shape+colour alignment): keep, but time-box to 3 h.**
- *Evidence.* It is the closest analogue to Shaper/VolSite (middling on ProSPECCTs: P5 0.65, P6.2 0.65–0.76) and
  to SiteHopper (Vertex 0.887, P5.2 0.81). It is also the only arm that returns a correspondence, which helps
  explain hits.
- *Must fix: rotations.* "8 sign flips" of the PCA axes include 4 improper rotations (reflections), and pockets
  are chiral. Use the 4 proper flips × the 24 cube rotations about the PCA frame, or ≥ 30 quasi-uniform SO(3)
  starts. Optimise rigid quaternion + translation with Adam/L-BFGS for 30–50 steps, batched in torch.
- *Cost.* Full clouds of 300 × 300 points × 30 starts × 50 steps take about 1–10 ms per pair, which misses the
  1 ms target. Reduce each pocket first to 32–48 weighted pseudocentres (k-means on the typed, vol-weighted
  points, one Gaussian per centre with summed weight). The estimate is then about 20–100 µs per pair batched on
  one 4090. TOUGH-M1-test (≈ 0.5 M within-partition pairs) takes minutes. Pseudocentres are also the only way
  to store tier-2 inputs at AFDB scale: about 450 B per pocket versus about 4 KB for raw points (5.6 TB at
  1.4 B pockets, over the cap).
- *Scores.* Report both Tanimoto and Tversky overlap (overlap / min self-overlap). Tversky handles D-mode
  over-segmentation and sub-pocket matches.
- *OT / fused Gromov–Wasserstein.* Not worth it here: O(n³) per iteration at n ≈ 300, 10–100 ms per pair on CPU
  with POT, and new GPU engineering. ICP adds nothing over gradient-based Gaussian overlap.

**A4 (learned embedding): reorder.** Make A4b the must-do: an MLP or metric head on A1 + B1 descriptors,
128-d output, trained in minutes. Full point networks are a stretch goal, only if A1–A3 are done by about 04:00.
Reasons:
- ligand-sharing labels are noisy (PocketVec: AUROC 0.58 for one shared ligand);
- a few thousand fold-disjoint BLiPS positives give high variance;
- 5 seeds × an EGNN plus debugging will not fit the 03:00–10:00 slot together with A3, fusion, robustness and
  the AFDB demo.

If the full network is built:
- use an invariant distance-based GNN (SchNet/EGNN-lite: 4 layers, 64 hidden) on ≤ 256 vol-weighted points
  with the analytic features. Equivariant outputs are unnecessary for a pooled invariant vector.
- Add plentiful *robustness positives* that cost no labels: same site holo/apo/AF from pocket_detect
  `apo_train`/`af_train`, homodimer copies, and L-mode vs D-mode.
- Use a soft target (pocket cosine regressed onto ligand Tanimoto, ErePOC-style) instead of binary InfoNCE only.

A model trained on TOUGH-M1-dev is a legitimate *trained* arm (DeeplyTough: 0.74 with 1,395 structures), as
long as it is reported apart from the zero-shot claims.

**A5 (fusion):** Fine. Fit on BLiPS-val + PPIPS-val, check on TOUGH-M1-dev, and keep ≤ 5 inputs.

## Indexing and AFDB-scale compute (to state in §6)

- **BURROW dominates tier-1 cost.** 200 M structures at about 400–550 structures/s per node (default preset,
  3–4 GPUs) is about 4–6 node-days. A1 or a small GNN adds ≤ 10 %; A1 histograms are an O(n²) einsum taking
  1–20 ms per pocket on CPU.
- **Index sizes at 1.4 B pockets.** A 128-d fp16 flat index needs 256 B per pocket (360 GB). IVF-PQ32 (OPQ,
  IVF 2¹⁶) needs about 40 B per pocket with ids (≈ 56 GB). That fits sharded across 4 × 24 GB GPUs, so the full
  AFDB kNN graph is a measurable multi-hour job, not a fantasy.
- **Demo.** Human proteome, ≈ 0.25–0.35 M pockets. Exact all-vs-all as a torch fp16 matmul with top-k takes
  minutes on one GPU, so FAISS is not needed (and is not installed). Use `faiss-cpu`/`faiss-gpu-cu12` from pip only to measure
  PQ recall@10 against exact and the ΔAUC from PQ-approximated scores on TOUGH-M1-dev. Report bytes per pocket.
- **Not affordable at AFDB scale:**
  - ESM embeddings: about 2,800 GPU-h.
  - A2: 78 node-days.
  - A3 all-vs-all rerank: top-100 × 1.4 B ≈ 2,000 GPU-h.
  All three are per-query tier-2 only.

## Ranked changes

**Must**
1. A1: weight points by vol and resample to a uniform lattice. Use soft VolSite-style typing, Hellinger plus
   z-score, and a pre-registered grid of ≤ 20 configs.
2. A3: use proper rotations only. Reduce pockets to pseudocentres. Score with Tanimoto + Tversky. Time-box 3 h.
3. Add hubness correction to every arm: CSLS, or a per-query z-score against each pocket's mean similarity to
   its k = 50 background neighbours. The feasibility report's kinase–haem confusion is a hub effect. It costs one
   line, helps pooled-pair ROC-AUC and retrieval, and gives AFDB hits a threshold.
4. A4: make A4b the default and the full GNN a stretch goal. Add robustness positives.

**Should**
5. A2: use the ligand-efficiency + covariate-residual normalisation and the in-pocket pose filter.
6. A1 variant: typed USRCAT.
7. Baseline/fusion input: pooled ESM-2 embedding of the lining residues (EPoCS-style, training-free). Stratify by
   homology, because it carries sequence signal.
8. §6: add the index-size and compute table above, and measure PQ recall on the demo.

**Could**
9. Multi-vector "late interaction": sub-pocket vectors scored by MaxSim, for split sites and PPI.
10. A docking-derived pharmacophore cloud (pooled fragment pose atoms) compared with the A3 machinery.

**Drop:** FGW/OT, persistent homology, full-point 3-point hashing.
