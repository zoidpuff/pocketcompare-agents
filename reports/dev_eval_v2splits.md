# Dev re-evaluation on the rebuilt splits (D15/D18): old vs new (eval agent, 2026-10-28)

I re-ran `scripts/eval_dev.py --dataset {tough_m1,blips,ppips} --out-suffix _v2splits --trial-tag splits_v2` with B = 2000, seed 0 and 16 threads. Wall time: 196 s, 267 s and 23 s.
- **Code:** unchanged, except two new CLI flags (`--out-suffix`, `--trial-tag`) and one fix (below).
- **Outputs:** `results/dev/{tough_m1_dev,blips_val,ppips_val}_v2splits_*` with `.prov.json`. The old files are kept.
- **Trials:** 137 + 88 + 25 rows appended to `results/trials.tsv` with config `tag = splits_v2`.
- Not touched: `data/sealed/`, `configs/final_method.yaml`, `results/models/`.

**Fix needed for PPIPS.** The docking tables `data/processed/docking/ppips/*.parquet` carry a `split` column written before the rebuild. It agrees with the new membership for only 67 % of pockets. The A2 reference set (train) and the evaluated pool (val) are therefore now taken from the rebuilt `pockets.parquet` / `ppips_complex_splits`, not from the docking tables. The old run was unaffected, because its membership matched.

## Old vs new (raw cosine; ROC / cb-AUC / size-stratified AUC unless stated)
| set | quantity | old splits | new splits |
|---|---|---|---|
| TM1-dev | pockets / pairs (pos) / units (largest) | 731 / 9,829 (3,366) / 146 (438) | 765 / 10,574 (3,450) / 152 (478) |
| TM1-dev | A1 pair_only L | 0.795 / 0.798 / 0.732 | 0.779 / 0.794 / 0.705 |
| TM1-dev | A1 default L | 0.788 / 0.794 / 0.732 | 0.775 / 0.792 / 0.707 |
| TM1-dev | SiteEngine c1 / B1 / A2 frag-IFP+CSLS / B4 / B5 (ROC, L) | 0.680 / 0.643 / 0.632 / 0.601 / 0.599 | 0.672 / 0.635 / 0.621 / 0.595 / 0.568 |
| TM1-dev | B0 / B0m stratified (diagnostic: 0.5 ± 0.03) | 0.520 / 0.489 | 0.535 / 0.491 |
| TM1-dev | B0 / B0m ROC (size shortcut) | 0.780 / 0.857 | 0.782 / 0.861 |
| TM1-dev | controls: random / shuffled labels (ROC) | 0.506 / 0.499 | 0.498 / 0.493 |
| TM1-dev | D mode ROC: B1 / B4 / A1 pair_only | 0.615 / 0.600 / 0.560 | 0.607 / 0.588 / 0.549 |
| TM1-dev | **A2 gate** Δ strat, A1 + A2 frag (raw) [CI] | −0.010 [−0.027, +0.007] **FAIL** | −0.009 [−0.066, +0.023] **FAIL** |
| TM1-dev | A2 gate, lead-like / both panels / frag CSLS | −0.015 / −0.015 / −0.005, all FAIL | −0.032 / −0.035 / +0.002, all FAIL |
| TM1-dev | **L→D on the same pairs**, A1 pair_only | 0.808 → 0.560, Δ −0.249 [−0.366, −0.217] | 0.793 → 0.549, Δ −0.244 [−0.328, −0.186] |
| TM1-dev | L→D, B1 / B4 | −0.061 / −0.024 | −0.059 / −0.030 |
| TM1-dev | CSLS − raw Δ AUC: A2 frag-IFP L / A1 L / A1 D / B4 L | +0.040* / −0.002 / +0.006 / −0.061 | +0.044* / +0.018 / +0.012 / −0.022 |
| TM1-dev | A1 selection, old rule (TM1-L cb, one SE): best / chosen | no_bur / **pair_only** | no_bur (SE 0.023) / **usr_only** (84 d) |
| TM1-dev | dev Δ AUC A1 chosen − B1; projected test MDE; test units (largest) | +0.152, MDE 0.127; 141 (710) | usr_only +0.097, MDE 0.211; pair_only (CSLS) +0.138, MDE 0.118; 133 (787) |
| BLiPS-val | sites / pairs (pos) / hom / lig units / pos clusters | 511 / 3,378 (563) / 256 / 187 / 48 | 523 / 2,772 (462) / 252 / 193 / 52 |
| BLiPS-val | D-set pairs (pos); D miss rate pos / neg | 1,858 (313); 0.44 / 0.45 | 1,544 (287); 0.38 / 0.46 |
| BLiPS-val | L: A1 default / B1 / B4 / B0 | .775/.713/.742 · .687/.641/.674 · .679/.686/.676 · .659/.646/.511 | .741/.738/.710 · .696/.701/.690 · .655/.641/.654 · .646/.646/.535 |
| BLiPS-val | D: A1 default / B1 / B4 | .555/.561/.548 · .676/.641/.671 · .698/.655/.699 | .602/.605/.596 · .682/.648/.682 · .717/.670/.719 |
| BLiPS-val | B0m stratified | 0.481 | 0.482 |
| BLiPS-val | Δ A1 default − B1, L: AUC; strat | +0.087 [+0.033, +0.136]; +0.069 [+0.004, +0.123] | **+0.045 [−0.005, +0.098]; +0.020 [−0.038, +0.084]** |
| BLiPS-val | Δ A1 default − B4, D: AUC | −0.144 [−0.262, −0.029] | −0.115 [−0.201, −0.004] |
| BLiPS-val | Δ A1 default − B1, D: AUC | −0.121 [−0.229, −0.001] | −0.080 [−0.166, +0.015] |
| BLiPS-val | **L→D on the same pairs**: A1 default / B1 / B4 | −0.267 [−0.353, −0.175] / −0.046 / −0.000 | −0.161 [−0.245, −0.082] / −0.041 / +0.013 |
| BLiPS-val | CSLS − raw Δ AUC: A1 L / A1 D / B1 L / B4 D | +0.001 / +0.001 / +0.004 / −0.044 (all n.s.) | +0.004 / +0.000 / +0.000 / −0.036 (all n.s.) |
| BLiPS-val | no_promiscuous, L strat: A1 default / B1 / B4 | 0.745 / 0.696 / 0.720 | 0.696 / 0.642 / 0.624 |
| D11 | best (mean of 4 cb, SE) → **chosen** | no_hellinger (0.657, 0.021) → **pair_only** (0.652) | no_hellinger (0.673, 0.018) → **untyped** (37 d, 0.656; threshold 0.6545) |
| D11 | configs within one SE | 12 | 14 (adds untyped, default_bw) |
| PPIPS-val | P-ortho queries (pockets) / units; chance MRR | 95 (69) / 13; 0.352 | 217 (138) / 17; 0.305 |
| PPIPS-val | P-ortho MRR: B4 / B1 / A1 default / A1 chosen | 0.942 / 0.764 / 0.633 / 0.563 (pair_only) | 0.986 / 0.761 / 0.644 / 0.530 (untyped) |
| PPIPS-val | P-ortho MRR: A2 IFP frag / lead; rank frag / lead | 0.619 / 0.544; 0.482 / 0.486 | 0.571 / 0.613; 0.435 / 0.498 |
| PPIPS-val | P-sym percentile: B1 / A1 default / A2 frag-IFP / B0 | 0.998 / 0.944 / 0.980 / 0.768 | 0.997 / 0.954 / 0.981 / 0.751 |
| PPIPS-val | **sub-hypothesis**: Δ MRR (frag − lead), raw, rank / LE-resid / IFP | −0.004 / +0.045 / +0.074; Holm p .50/.28/.25 | −0.063 / −0.005 / −0.042; Holm p 1/1/1 |
| PPIPS-val | same, shallowest bur16 tertile, IFP | +0.133 [−0.065, +0.317] | −0.024 [−0.116, +0.163] |
| PPIPS-val | **verdict** | NOT SUPPORTED | NOT SUPPORTED |

\* 95 % CI excludes 0 (old [+0.005, +0.060]; new [+0.017, +0.069]).

## Did any conclusion change?
- **A2 gate:** unchanged, FAIL. Every A2 fusion Δ remains ≤ +0.002 with a CI that includes 0.
- **Ligand imprint (D11):** unchanged in direction and significance.
  - TOUGH-M1: A1 loses 0.244 from L to D, versus 0.06 / 0.03 for B1 / B4.
  - BLiPS: the drop is smaller than before (−0.161 vs −0.267) but its CI still excludes 0.
  - In D mode, B4 > B1 > A1 on both sets.
  - A1 − B4 in D mode stays negative on BLiPS: −0.115 [−0.201, −0.004].
- **CSLS:** unchanged. The only reliable gain is A2-IFP on TOUGH-M1 (+0.04); everything else is n.s.
- **Rankings:** the orderings are unchanged.
  - TOUGH-M1 L: A1 > SiteEngine > B1 > A2-IFP > B4 > B5.
  - BLiPS L: A1 > B1 > B4.
  - D mode (both sets): B4 ≥ B1 > A1.
  - PPIPS: B4 > B1 > A1 default > A2.
  - Exception: the PPIPS IFP panel order flips (lead-like now ahead).
- **Changed 1: the BLiPS L-mode advantage of A1 over B1 is no longer significant.** Δ AUC is +0.045 [−0.005, +0.098] and Δ stratified +0.020 [−0.038, +0.084]; before, both CIs excluded 0. The A1 > B1 L-mode result now rests on TOUGH-M1-dev alone. There it is still large, but that set carries the ligand imprint.
- **Changed 2: the A1 config choice is unstable.**
  - The D11 rule now picks **untyped** (37 d), which clears the threshold by only 0.0015. The old TOUGH-only rule picks usr_only.
  - The cause is the fewest-dims tie-break among 12–14 near-equivalent configs: their means span 0.656–0.673, which is less than one SE.
  - untyped is worse on PPIPS (MRR 0.530 vs 0.644 for default) and on BLiPS n_shared ≥ 2 (strat 0.50 vs 0.73, 9 positives).
  - This affects only the A1-as-arm reporting. The final method is selected separately under D14/PREREG by the A4b agent.
- **Changed 3: the sub-hypothesis point estimates reversed.** The positive Δs (fragments > lead-like) did not replicate on the larger val set (217 queries); all three blocks are now negative. The verdict stays **NOT SUPPORTED**, and the earlier positive trend should be treated as noise.
- **Power:** TOUGH-M1-test units fall 141 → 133, and the giant unit grows to 787 of 1,045 test pockets. The C1 MDE for the old chosen config (pair_only, CSLS vs B1) is ≈ 0.12.
