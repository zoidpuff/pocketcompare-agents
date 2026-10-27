# A2 — docking-profile pocket descriptor on TOUGH-M1 (2026-10-27)

Scripts `scripts/a2/{build_panels,prep_pockets,dock_tough_m1,run_dock.sh,aggregate,analyze_repro,build_descriptors}`;
descriptor `src/pocketcompare/descriptors/a2.py` (7 unit tests, `tests/test_a2_descriptor.py`).
Node eu-g6-048, **cuda:0 + cuda:2 only, 4 processes per GPU, 2 CPU threads each**. ADock read-only, unmodified,
overlay env per `scripts/feasibility/setup_adock_overlay.sh`. No label or pair file was opened.

## Protocol (as DESIGN §3 A2)
Stock Vina weights, rigid receptor, preset `frag_lite_np`, **fixed 12 Å cubic box** centred on the
volume-weighted centroid of the L-mode BURROW points (D-mode: the matched merged region-rule pocket), so box
volume is not a pocket-size proxy. Both panels are docked in one batch per pocket → identical receptor prep,
grid and compute. Best pose per molecule; **pose-in-pocket** = pose centroid ≤ 2 Å from a pocket point.
Stored per pocket × molecule: score, inter, LE = score/heavy atoms, in-pocket flag and centroid distance,
best-pose contact counts (H-bond donor matched, H-bond acceptor matched, apolar, aromatic, charged) and
buried fraction → `data/processed/docking/tough_m1/{fragments,leadlike}{,_dmode}.parquet` (+ `.prov.json`).

## Panels (full provenance, licences and sha256 in DATA.md "Docking panels")
128 **fragments** from the public-domain NCI Open Database (release 4), Ro3-like filter (8–17 HA, MW ≤ 300,
≤ 3 rot. bonds, ≥ 1 ring, PAINS-free), stratified 6 pharmacophore classes × 3 HA bins (24/80/24 for 8–9 /
10–14 / 15–17), MaxMin within stratum, seed 0. 128 **lead-like** (MW 200–450, ≤ 6 rot. bonds) MaxMin-picked
from PocketVec's published 1,000-molecule lead-like pool (MIT); 16/128 coincide with PocketVec's own 128.
Both protonated at pH 7.4 (dimorphite-dl 2.1.0), ETKDGv3+MMFF 3D. **Honest caveat:** no vendor fragment
library (Enamine/Maybridge/DSi-Poised) was redistributable or reachable (ZINC is proxy-blocked/captcha-gated),
so the fragment panel is a fragment-*like* subset of a general public collection, not a designed library.

## Reproducibility (3 seeds × 100 pockets, SEEDS[0..2]; `results/a2/repro.json`)
| per-pocket Pearson r between seeds | fragments | lead-like |
|---|---|---|
| score vector (128) | mean **0.988**, median 0.994, p05 0.962, 98 % of pockets ≥ 0.95 | mean **0.972**, median 0.979, p05 0.930, 78 % ≥ 0.95 |
| rank vector / LE vector | 0.987 / 0.988 | 0.963 / 0.983 |
| pose-interaction block (768) | 0.962 | 0.956 |
| top-pose RMSD across seeds | median 0.16 Å, 78 % ≤ 2 Å, p90 4.3 Å | median 0.74 Å, 74 % ≤ 2 Å, p90 5.9 Å |

Mean and median r ≥ 0.95 for both panels, so the production run used **one seed, SEEDS[0]**, per DESIGN.
Individual poses do flip for ~¼ of molecules (review item: pose control), but the *aggregated* contact block is
stable (r ≈ 0.96). If A2 passes the gate, switch the IFP block to Boltzmann-weighted contacts over the top-3
poses (already produced by `n_out=3`) and/or a 3-seed mean for the lead-like panel.

## Production runs, timing, failures
| | L-mode | D-mode |
|---|---|---|
| pockets × molecules | 7,524 × 256 | 6,068 × 256 (1,456 pockets unmatched, `d_missed`) |
| wall (8 procs, 2 GPUs) | **19.0 min** (1,140 s) | 15.0 min (902 s) |
| per pocket, both panels | 0.303 GPU-s (1.18 ms/pair/GPU) | 0.297 GPU-s |
| per pocket, one panel (idle GPU, 1 proc) | fragments 0.135 s, lead-like 0.306 s | — |
| implied full-node throughput (4 GPUs, 16 procs) | **13 pockets/s** both panels; ≈ 43/s fragments-only, ≈ 19/s lead-like-only | — |
| failures | **0** docking, 0/256 ligand-prep, receptor-annotation coordinate match 100 % | 0 |
| pose in pocket | 99.6 % / 99.5 % (frag/lead) | 95.1 % / 95.5 % |
| positive (repulsive) scores | 0.75 % / 4.8 % | 1.1 % / 8.2 % |

AFDB extrapolation (measured, not run): ~0.09 GPU-s per pocket per 128-molecule fragment panel → 10⁹ pockets ≈
2.6 × 10⁴ GPU-h ≈ 270 node-days; A2 is a tier-2 / reference-set arm, not an all-of-AFDB descriptor.
**Disk:** 135 MB docking parquets (+8 MB 3-seed repro with poses), 57 MB descriptors, 0.8 MB panels,
201 MB NCI source archive (git-ignored) — 0.39 GB total.

## Descriptor (`pocketcompare.descriptors.a2`)
`A2Config`/`A2Descriptor` with an explicit **fit/transform** API. `fit(raw, pocket_meta, reference_pocket_ids)`
**raises if no reference set is given** — there is no fit-on-all-pockets default, so nothing can leak at
evaluation. Blocks: (a) `rank` — PocketVec-style rank vector, ties `method='max'`, non-binders binned to
N+1 (score above the panel's 90th-percentile score on the reference set), N+2 (pose out of pocket) and
N+3 (missing); (b) `le_resid` — LE residualised per molecule on log volume + mean buriedness (OLS fitted on the
reference set) then per-molecule z-scored; (c) `ifp` — contact counts per heavy atom + buried fraction,
z-scored per (molecule, type), flattened (128 × 6). 1,024 floats = 4 kB/pocket/panel (tier-2 only).
Fitted objects and all-pocket descriptors in `results/a2/` (reference = deterministic 2,000-pocket sample;
**the evaluator must refit on the split's own reference set**).

Label-free size diagnostics (`results/a2/descriptor_diagnostics_*.json`), Spearman of PC1 with log volume /
of pair cosine with |Δlog volume|: L-mode fragments — raw dz 0.23/−0.27, rank −0.40/−0.33, le_resid 0.40/−0.17,
ifp **0.16/−0.09**; lead-like is worse throughout (raw dz 0.54/−0.42, rank 0.61/−0.38, le_resid 0.67/−0.43,
ifp 0.35/−0.12). D-mode is much cleaner (ifp 0.01/−0.03). **Honest finding:** the per-molecule linear
residualisation on log V + buriedness does *not* remove the size axis from the LE block (PC1 still 64 %/88 % of
variance and ρ 0.40/0.67 with log volume); the pose-interaction block is the least size-confounded of the
three, and fragments are consistently less size-confounded than lead-like molecules, which is the direction the
pre-registered PPI sub-hypothesis predicts. The gate itself (size-stratified AUC vs B0/A1 and the published
Vina 0.55) is for the evaluation agent — no labels were touched here.
