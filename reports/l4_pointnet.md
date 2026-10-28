# L4 point-cloud pocket encoder (PREREG Addendum A1): dev results on the D18 splits (2026-10-28 03:15)

## Numbers (B = 2,000; cb = cluster-balanced ROC-AUC; SE from homology-group units)
Source: `results/dev/l4/final_select_all_l4_summary.md`. All 6 L4 configs were run jointly with N1/N2 and the 12 A4b
configs through `eval_dev.main_final_select`, whose code is unchanged. 60 L4 trial rows were appended to
`results/trials.tsv`.

| candidate | BLiPS-val D cb (SE) | BLiPS-val L cb | TM-dev D cb | TM-dev L cb | PPIPS P-ortho MRR | GPU / 1-CPU ms per pocket* |
|---|---|---|---|---|---|---|
| B1 raw (guard) | 0.648 (0.040) | 0.701 | 0.617 | 0.639 | 0.761 | – |
| N1 raw | 0.697 (0.040) | 0.706 | 0.667 | 0.656 | 0.790 | – |
| A4b n1_base raw / n1_linear raw | 0.717 / 0.737 | 0.702 / 0.718 | 0.687 / 0.721 | 0.695 / 0.720 | 0.694 / 0.719 | – |
| A4b n2_linear CSLS | 0.751 (0.036) | 0.755 | 0.702 | 0.754 | 0.755 | – |
| **L4 egnn_small CSLS (best overall)** | **0.756** (0.040) | 0.765 | 0.661 | 0.694 | 0.821 | 0.54 / 47 |
| L4 egnn_small raw | 0.748 (0.041) | 0.760 | 0.660 | 0.688 | **0.831** | 0.54 / 47 |
| L4 egnn_noppi raw / CSLS | 0.750 / 0.754 | 0.751 / 0.747 | 0.681 / 0.669 | 0.709 / 0.703 | 0.707 / 0.709 | 0.90 / 146 |
| L4 egnn_inv raw / CSLS | 0.742 / 0.750 | 0.725 / 0.728 | 0.663 / 0.651 | 0.689 / 0.697 | 0.821 / 0.820 | 0.84 / 118 |
| L4 egnn_base raw / CSLS | 0.734 / 0.740 | 0.732 / 0.738 | 0.658 / 0.646 | 0.687 / 0.686 | 0.796 / 0.800 | 0.90 / 145 |
| L4 egnn_n1cat raw / CSLS | 0.728 / 0.731 | 0.734 / 0.741 | 0.672 / 0.660 | 0.710 / 0.705 | 0.783 / 0.790 | 0.92 / 145 |
| L4 egnn_nce raw / CSLS | 0.710 / 0.719 | 0.707 / 0.719 | 0.669 / 0.659 | 0.683 / 0.682 | 0.818 / 0.804 | 0.90 / 146 |

\*The ms figures cover the 3-seed ensemble on precomputed point sets, timed on 1,024 TOUGH-M1 pockets
(`results/models/l4/bench.json`). GPU = RTX 4090, batch 256, bf16. CPU = 1 thread, batch 32, fp32. Point-set
extraction adds 4.3–5.3 ms per pocket on 1 thread. For comparison, A4b takes 3.5 ms per pocket in total (CPU).

- **Selection (PREREG §1).**
  - The best candidate overall is L4 egnn_small with CSLS: 0.756, SE 0.040, which sets the threshold at 0.716.
  - Every L4 config except nce-raw is within one SE, and all of them pass both guards.
  - Under the one-SE rule L4 counts as more complex than A4b, so **the choice stays with A4b**. The script prints
    n1_base raw by grid order. Under D19's fewest-parameters tie-break it is n1_linear raw. L4 does not change the
    selection.
- **Paired Δ, L4 egnn_small CSLS minus the reference:**
  - vs N1: BLiPS-val D +0.059 [−0.006, +0.130] (p 0.03); BLiPS-val L +0.059 [+0.014, +0.130].
  - vs N1 on TM-dev D: −0.006 [−0.089, +0.068].
  - vs B1: BLiPS-val D +0.108 [+0.018, +0.181]; TM-dev D +0.045 [−0.023, +0.138].
- **Interpretation.** L4 is the strongest candidate on BLiPS (in-distribution) and on PPIPS MRR (0.83 vs A4b
  0.69–0.76). It does not transfer to TOUGH-M1-dev D: 0.646–0.681, against N1's 0.667 and A4b's 0.69–0.72. The
  BLiPS gain is within one SE and is a maximum over 12 L4 rows.
- **Training.** Early stopping picks epochs 1–11 (ES 0.75–0.82); a config takes 4–9 min for 3 seeds on cuda:2/3. As
  with A4b, the models fit quickly and the hold-out stops improving after a few epochs. Peak GPU memory is 21 GiB
  for hidden 128.

## What was built
- **Point sets** (`scripts/l4_extract.py` → `data/processed/l4/`, git-ignored, 2.3 GB, about 1 min).
  - Coverage: BLiPS train+val L/U, BLiPS-test holo and AF L/U, TOUGH-M1 L/U (7,524) and PPIPS D (20,497).
  - Site: the sph8 set of the N1 locators. Its size matches N1's sph8 sets exactly (0 mismatches).
  - Sampling: capped at 256 points by deterministic vol-weighted FPS.
  - Per point:
    - the 84 BURROW analytic features (bur*/burbb*, depth, hit_*, escape, psp, nearest, metal_cand, n_coord28,
      coord_spread, n_all*, n4_*, f8_*, f12_*, prot_frac), log1p/z-scored on BLiPS-train points;
    - 8 soft VolSite channels (A1 typing);
    - the log of the aggregated vol weight.
  - No `point_score` and no learned BURROW output.
- **Model** (`src/pocketcompare/l4.py`): a kNN EGNN (k = 16, RBF distance edges, equivariant coordinate updates),
  then vol-weighted attention plus mean pooling, then a 128-d L2-normalised embedding.
- **Invariance test** (`tests/test_l4.py`, 5/5 pass): random rotations, reflections and translations change the
  embedding by < 1e-4. Point order and padding have no effect. FPS is deterministic.
- **Grid** (`configs/a4_grid.yaml`, declared before any real fit): base (4 × 128), small (3 × 64), n1cat, inv (no
  coordinate updates), nce and noppi.
- **Training rules = A4b.** `train_a4b.Data` is reused unchanged. Augmentation is a random rotation plus 15 % point
  dropout. Seeds SEEDS[:3]; the score is the mean cosine.
- **Weights:** `results/models/l4/<config>/seed{0,1,2}.pt`, with sha256 of the weights, scalers, embeddings and point
  files in `config.json`. About 63 MB per config is `emb_*.npy` eval caches, which should not be committed.

## Deviations
1. **sph8 fallback mirrored after the first run.**
   - What: the eval stopped on one BLiPS-val site with an empty sph8 set.
   - Fix: as in `a4b.raw_parts`, that site's L set is now the located set.
   - Done: re-extracted, re-embedded (eval only; the site is not in BLiPS-train, so training was unaffected), then
     evaluated. No scores had been produced before the fix.
2. **Smoke test before the go.** The eval smoke test with a noise-trained model printed BLiPS-val metrics. Nothing
   was tuned on them.
3. **Typo fix.** A shell quoting typo in `run_l4.sh` was fixed before any fit.
