# AF-vs-holo robustness (C5, reported, dev only) — `scripts/eval_af_robustness.py`

Method = configs/final_method.yaml (N1 raw), refs B1, A1 pair_only, B0 (size). Bootstrap B = 2000, homology-group units (pairs: wider of group / ligand-cluster CI). Results: `results/dev/af_robustness_{val,train}/`, trials arm `C5_dev`.
**Sets.** **BLiPS-val v2: 239 of 511 val sites** have a holo pocket and an AF-model pocket in af_train (>= 150, so no train sample needed for the primary): 698 labelled pairs (89 pos). **BLiPS-train v2, supplementary (all 1,068 train sites with AF, 9,019 pairs / 1,628 pos), not val** — used only for power.
D-mode matched on both sides: 131/239 val (55 %), 653/1,068 train (61 %) (BLiPS D is hard, ~40-45 % missed even on holo); D metrics are on this common set.

## Same-site retrieval (holo query -> AF pockets of the set; top-1 [95 % CI] / MRR / AUC)
| set, mode | final | B1 | A1 pair | B0 (size) |
|---|---|---|---|---|
| **val L** (n=238) | 0.78 [0.72,0.83] / 0.84 / 0.986 | 0.88 [0.84,0.92] / 0.92 / 0.993 | 0.66 / 0.75 / 0.987 | 0.05 / 0.14 / 0.85 |
| **val D** (n=131) | **0.55** [0.46,0.64] / 0.69 / 0.962 | 0.41 [0.33,0.50] / 0.55 / 0.911 | 0.12 / 0.24 / 0.79 | 0.02 / 0.08 / 0.63 |
| train L (n=1068) | 0.70 [0.67,0.73] / 0.77 / 0.982 | 0.83 / 0.87 / 0.988 | 0.60 / 0.67 / 0.981 | 0.01 / 0.04 / 0.86 |
| train D (n=653) | 0.52 [0.48,0.56] / 0.62 / 0.961 | 0.38 / 0.49 / 0.918 | 0.15 / 0.22 / 0.77 | 0.01 / 0.03 / 0.62 |

Removing same-homology-group decoys raises D top-1 of final to 0.75 (val) / 0.63 (train): most "misses" are a homologous site of another protein.

## Ligand-sharing AUC, holo/holo vs holo/AF (final; delta = HH - HA, 95 % CI)
| set, mode | pairs (pos) | HH | HA | delta |
|---|---|---|---|---|
| val L | 687 (89) | 0.638 | 0.643 | -0.005 [-0.054, +0.041] |
| val D | 196 (34) | 0.615 | 0.612 | +0.003 [-0.077, +0.086] |
| train L | 9,019 (1,628) | 0.705 | 0.713 | -0.008 [-0.019, +0.003] |
| train D | 3,267 (650) | 0.680 | 0.692 | -0.012 [-0.034, +0.010] |

B1: delta -0.004 [-0.012,+0.003] (train L); A1 pair: -0.010 [-0.020,-0.001] (train L). AF/AF is lower in D (val 0.557, B1 0.542). All |delta| <= 0.012; no CI excludes the 0.03 SESOI on the harm side.

## Strata (final; retrieval top-1 / pair delta, train L unless stated)
- Holo release before / after 2018-05-01: top-1 0.72 / 0.68 (val 0.78 / 0.78; D val 0.58 / 0.50); delta both-pre -0.012, both-post +0.001, mixed -0.010. No leakage signature (post-2018 not worse by more than CI width).
- AF site pLDDT <70 / 70-90 / >=90: top-1 0.13 (n=8) / 0.56 / 0.73 (val 0.50 (n=2) / 0.63 / 0.81; D train 0.34 / 0.54); delta 70-90 train L -0.007 [-0.029,+0.015]. Retrieval degrades at pLDDT 70-90 (about -0.17 top-1); the pair-task delta does not. <70 has too few sites (2 val, 8 train).

## Caveats
- Both pockets use the SAME transferred ligand location, so L-mode retrieval is optimistic and D-mode partly reflects detection. 40 % of AF val sites have a transferred ligand atom < 2 Å from the model (no clash filter); only 1 site lost in L (min 10 points).
- Holo L/AF L point counts: log-size r = 0.92 (val). B1 beats final in L retrieval (site-specific details), final wins D (ligand-free sph8 shaper).
- Val pair power is low (CIs about +-0.05, D +-0.08); train numbers are not val-clean (A4b trains on train) but N1 is non-learned. Median pLDDT 95.6: AF-model sites are high quality.
- Release dates: mirror mmCIF first revision (prepared table, parser cross-checked on 600 entries, 0 mismatches).

## Final evaluation
`FINAL_EVAL=1 python scripts/eval_af_robustness.py --set test --pairs <blips_test_pairs>` reuses the cached holo/AF test caches (`blips_test_holo`, `blips_test_af`), exclusions v2, unsealed tables only (the script never opens data/sealed; the PI/final_eval supplies the pairs path). Not run on test. For test use `--max-neg 3000000`; trial arm `C5`.
