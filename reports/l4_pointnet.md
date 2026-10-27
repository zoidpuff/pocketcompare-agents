# L4 point-cloud pocket encoder (PREREG Addendum A1) — STATUS: built, waiting for the go (no real fit yet)

## Numbers (label-free / synthetic only, 2026-10-27 23:55)
- **Point sets** (`scripts/l4_extract.py`, 16 workers, about 1 min in total, 0 errors, 2.3 GB in `data/processed/l4/`):
  - BLiPS train+val: 2,862 sites, L/U. One L site has an empty sph8 set; N1 lacks the same site.
  - BLiPS-test holo: 3,606 sites, L/U. BLiPS-test AF: 3,603 sites, L/U.
  - TOUGH-M1: 7,524 pockets, L/U. PPIPS: 20,497 pockets, D.
  - **The sph8 set sizes match the N1 (a1r) sph8 sets exactly** (0 mismatches in every set).
  - Median sph8 size is 270–395 points. 52–78 % of the sets are capped at 256.
  - Extraction (shaper + FPS + soft typing) takes 4.3–5.3 ms/pocket median on 1 thread.
- **Invariance** (`tests/test_l4.py`, 5/5 pass): random rotations, reflections and translations up to 20 Å change the
  embedding by < 1e-4 (float64), with and without coordinate updates. Point order and padding/batch composition
  leave it unchanged (< 1e-6). FPS is deterministic.
- **Inference cost** (egnn_base, 3-seed ensemble, 616 k params/seed; point sets precomputed):
  - GPU (RTX 4090, batch 256, bf16): **0.90 ms/pocket**.
  - 1 CPU thread (batch 32, fp32): **150 ms/pocket**, about 50 ms per seed. This is ~30× N1's 5 ms descriptor.
- **Synthetic smoke tests:** all 6 configs train end-to-end on random clouds with permuted labels; ES ≈ 0.50 as
  expected. Training memory is 20.4 GiB at 512 pockets/step for hidden 128.
  - Timing: about 15 s/epoch (50 steps + ES), so the full grid takes about 1 h on cuda:2 + cuda:3.
  - The eval wrapper ran end-to-end (B = 20, `--no-trials`, scratch output).
  - Disclosure: this smoke test printed BLiPS-val metrics for the noise-trained model (D cb 0.67). Nothing was selected or tuned on them.

## Inputs
- **Site:** sph8 of the N1 locators: L = the ligand shell; U = the best-covering BURROW sub-pocket (`u_member` of the
  a1r ids); PPIPS D = the merged region pocket.
- **Sampling:** capped at 256 points by deterministic vol-weighted FPS. The start point is the one nearest the
  weighted centroid; the score is d_min · w^(1/3).
- **vol weight:** voxels of every sph8 point assigned to the nearest sample (Σ = sph8 volume).
- **Point features (93 per point):**
  - The 84 BURROW analytic features: bur6/10/16, burbb6/10/16, depth, hit_{apolar,polar,charged,aromatic}, escape,
    psp, nearest, metal_cand, n_coord28, coord_spread, n_all{4,8,10,12}, n4_* (19), f8_* (21), f12_* (21) and
    prot_frac. Count-like features are log1p-transformed. All are z-scored on BLiPS-train L+U points.
  - 8 soft VolSite channels: A1 soft typing for hyd, aro, don, acc, da, pos, neg, plus metal.
  - log(vol weight).
  - No `point_score` and no learned BURROW output.

## Model / grid (`configs/a4_grid.yaml`, sha256 71884154…, declared before any real fit)
- **Architecture:** a kNN EGNN (k = 16, recomputed per layer; RBF(d) edges; bounded equivariant coordinate updates).
  It feeds vol-weighted attention pooling and a vol-weighted mean, then an MLP to a 128-d L2-normalised vector.
- **Configs:** egnn_base (4 × 128), egnn_small (3 × 64), egnn_n1cat (+ N1 vector before the head), egnn_inv (no
  coordinate updates), egnn_nce (InfoNCE only) and egnn_noppi (no PPIPS positives).
- **Training rules = A4b:** `train_a4b.Data` is reused unchanged (same pairs, L↔D/PPIPS positives, masking and 10 %
  ES hold-out). Augmentation is a random rotation plus 15 % point dropout. Seeds SEEDS[:3]; the ensemble score is
  the mean cosine.
- **Evaluation:** `scripts/eval_l4.py` adds the L4 candidates to `eval_dev.main_final_select`, whose code is unchanged.
  The L4 candidates rank after every A4b config at equal dims.

## Pending (after "splits final + audit passed")
`L4_AUDIT_PASSED=1 nohup bash scripts/run_l4.sh > logs/l4_run.log 2>&1 &` runs four steps:
1. Re-extract the point sets (site membership may change).
2. Train 6 configs × 3 seeds.
3. Benchmark.
4. Run the PREREG §1 evaluation with trials logged.

Weights go to `results/models/l4/<config>/seed*.pt`, with sha256 in `config.json`.
