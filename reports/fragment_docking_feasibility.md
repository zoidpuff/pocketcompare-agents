# Fragment-docking pocket fingerprints: feasibility and cost (ADock on BURROW pockets)

2026-10-27. Node eu-g6-048: 4x RTX 4090, 64 CPUs. The node was shared, with a 1-min load of about 25 throughout, so CPU timings are conservative.
ADock source: `/cluster/work/.../autoresearch_docking/src/adock`, read-only, used unmodified. The sha256 of the sorted `src/adock/*.py` files plus `config/adock.json` hashes to `667cb8d14c0f7bd9`. The ADock repo has no reachable git dir.
This is a feasibility study on 27 pockets, so all signal numbers are anecdotal.

## Numbers first

**Throughput.** The panel is 64 fragments × 27 BURROW pockets (9 PDB entries). Each figure is the median of 3 seeds. Wall time includes receptor typing, grid build and search. Ligand prep is done once per panel (0.17 s for 64 fragments).

| preset (search budget) | GPU ms/pair, 1 proc | CPU ms/pair, 1 thread | seed r (dz) | redock RMSD BEN / OHT |
|---|---|---|---|---|
| `v2_default` (ADock stock) | 7.0 (per-pocket batch) | – | 0.999 | – |
| `v2_fast` (ADock stock) | 4.4 per-pocket, 3.7 multi-pocket | – | 0.994 | 0.4 / 1.1 Å |
| `v2_fast_nn` (exact polish without neighbour lists) | 1.76 | 347 | – | – |
| **`frag_lite_np`** (32 chains × 64 MC steps, no polish) | **0.82** | **57** | **0.980** (min 0.90) | 0.3 / 1.1–1.2 Å |
| `frag_xlite_np` (16 × 32) | 0.69 | 20 | 0.94 (min 0.69) | 0.3 / 1.1–1.4 Å |
| `frag_scan` (rigid Stage A + 20 BFGS, no MC) | 0.65 | 9 | 0.76 (min 0.40) | fails in 1 of 3 seeds |

- **Node throughput, `frag_lite_np`:** 4 GPUs × 4 processes give **9,500 pairs/s** in the timed part, i.e. 2,400/GPU or 0.42 ms per pair per GPU (`results/feasibility/concurrency.txt`). With 1 process per GPU it is 4,900 pairs/s.
- **Cost per 64-fragment fingerprint:** about 6.7 ms of node time, or about 150 pockets/s per node.
- **Extrapolation, `frag_lite_np`, 64 fragments:**
  - **(a) 10k pockets** = 0.64 M pairs. That is 67 s on one node, 9 min on one GPU with one process, or about 10 CPU-h on CPU only (roughly 10 min on 64 cores, assuming linear scaling, not measured).
  - **(b) 200 M AFDB × 5 pockets** = 6.4e10 pairs. That is about 1,870 node-hours, i.e. **≈78 node-days (≈7,500 GPU-h)**. 128 fragments, PocketVec-sized, doubles this to about 156 node-days. CPU only it would be about 1.0 M CPU-h. With stock `v2_fast` it is about 5× more. Storing the fingerprints at fp16 needs 128 GB.

**Signal.** These numbers use `frag_lite_np` with seed-averaged vectors. "dz" means: subtract each fragment's mean over pockets, then z-score each pocket's vector.
- **Raw score vectors carry no pocket identity.** Pockets correlate with each other at a median r of 0.82 (90th percentile 0.94).
- **Seed reproducibility is high.** Per-pocket r between seeds is 0.995 raw and 0.98 after dz.
- **Size confounding is strong.** The mean fragment score per pocket tracks BURROW volume (Spearman −0.74), point count (−0.83) and bur16 (−0.50).
  - Pocket means explain 57% of the score-matrix variance and fragment means 17%; fragment means track heavy-atom count (ρ −0.81). Only 27% is pocket × fragment interaction.
  - After dz, PC1 still carries 43% of the variance. It tracks pocket volume (ρ −0.66) and apolar first-hit fraction (−0.69), and its fragment loadings track fragment size (ρ 0.81).
  - Pair similarity after dz still correlates with volume similarity (ρ 0.34).

**Pair similarities.** The table gives Pearson r after dz, with the rank of the partner among the 26 other pockets. Rows marked † are near-identical structures of the same protein, the case that "same site in two PDB entries" asks about.

| pair | docking (`frag_lite_np`) | BURROW size-free descriptors (39) | probe maps (§4) |
|---|---|---|---|
| CDK2 ATP site, 1HCK (ATP) / 1AQ1 (staurosporine) † | **0.81 (rank 3)** | 0.03 (12) | −0.28 (15) |
| trypsin S1, 3PTB holo / 2PTN apo † | 0.76 (1) | 0.98 (1) | 0.99 (1) |
| trypsin Ca site, 3PTB / 2PTN † | 0.61 (2) | 0.88 (1) | −0.09 (13) |
| ATP site CDK2 / PKA (same fold) | 0.75 (5) | 0.06 (10) | −0.72 (22) |
| ATP site PKA / HSP90 (other fold) | 0.62 (8) | 0.74 (4) | 0.45 (11) |
| heme myoglobin / P450cam (other fold) | 0.47 (10) | 0.03 (12) | −0.41 (22) |
| *different:* CDK2 ATP vs Mb heme | 0.69 (9) ✗ | −0.61 (26) | −0.24 (14) |
| *different:* CDK2 ATP vs trypsin S1 / Mb heme vs S1 / ER vs S1 | −0.26 / −0.22 / −0.38 | 0.33 / −0.54 / −0.03 | −0.65 / −0.30 / −0.19 |
| all 351 pairs: median (90th pct) | 0.12 (0.70) | −0.04 (0.56) | −0.04 (0.78) |
| same-site partner ranks (6 queries) | [3, 6, 1, 1, 2, 2] | [12, 13, 1, 1, 1, 1] | [15, 15, 1, 1, 13, 12] |

- Docking separates the polar or charged S1 pocket clearly from the large apolar pockets.
- The kinase ATP site and the heme cavity look alike to docking (r 0.69), which is the size and hydrophobicity axis again.
- Docking is better than the descriptors on the CDK2 pair, whose pockets have different shapes (72 vs 199 Å³) because of the different bound ligands. It is worse on the Ca site.
- n = 3 pairs: this is anecdotal, not a benchmark.

**Positive control** (`results/feasibility/redock_control.txt`): re-docking the crystal ligands with our receptor prep and the BURROW box gives top-pose RMSD of 0.3 Å for benzamidine in 3PTB and 1.1–1.4 Å for 4-hydroxytamoxifen in 3ERT, with every preset except `frag_scan`.

## 1. Running ADock from our container (cheapest route)
- **The sibling's own env is not usable.** `conda_envs/dock` is a dangling symlink to `/tmp/adock/envs/dock`, which was node-local on another node. The repo is read-only (`test -w` gives not writable).
- **A full conda build is not needed.** CUDA ≥ 12.8 matters only for sm_120 (Blackwell). The RTX 4090 is sm_89 and runs with our `.venv` (torch 2.6+cu124, NVRTC 12.4 wheel). The driver is 580.178, CUDA 13.0.
- **What was missing:** only `cupy-cuda12x`, `fastrlock`, `meeko` and `cuda-pathfinder`. They go into an overlay in /tmp: 291 MB, under 10 s, nothing to persist.
- **Commands** (`scripts/feasibility/setup_adock_overlay.sh`):
  ```
  source .venv/bin/activate
  uv pip install --target /tmp/adock/overlay --no-deps cupy-cuda12x==14.2.0 fastrlock==0.8.4 meeko==0.8.0 cuda-pathfinder==1.8.4
  export NUMBA_CACHE_DIR=/tmp/numba_cache CUPY_CACHE_DIR=/tmp/adock/cupy_cache
  export PYTHONPATH=/tmp/adock/overlay:/cluster/work/beltrao/buhmanju/agentic_ai/workspaces/hackathon/autoresearch_docking/src
  ```
- **CPU engine:** ADock's own `cpukernel` compiles with the system g++ into `/tmp/adock/cpukernel`. It worked unchanged.

## 2. Setup, batching, bottlenecks
- **Fragments** (`make_fragments.py`):
  - Source: RDKit-bundled `Data/NCI/first_5K.smi`, the first 5,000 compounds of the NCI/DTP open set. NCI data are public domain; RDKit is BSD-3.
  - Filters (Ro3-like): neutral, MW 100–250, 7–18 heavy atoms, at least 1 ring, at most 3 rotatable bonds, PAINS-free. 1,378 compounds pass.
  - Selection: MaxMin pick of 64 on Morgan fingerprints, seed 0; ETKDG/MMFF 3D.
  - The PI should add this to DATA.md.
- **Pockets** (`make_pockets.py`):
  - Entries: 1HCK, 1AQ1, 1ATP, 3PTB, 2PTN, 1A6M, 2CPP, 3ERT, 1BYQ, from the local mirror. One chain each, polymer only, so heme, ions and waters are removed.
  - BURROW `pocket_representations(ranker="all", preset="default")`.
  - Pockets kept: the top-3 per entry plus the native-site pocket, chosen by best residue Jaccard against residues within 4 Å of the ligand.
  - Box: the extent of the pocket points ± 3 Å, at least 12 Å per side. Tiny pockets (1–3 points) therefore dock into their surroundings.
- **Batching:** both "many fragments per pocket" and "many pockets per GPU call" work.
  - `dock_panel.py --layout multi` puts all (pocket, fragment) pairs into one ADock `Problem`, with one grid per pocket and `rec_idx` per pair.
  - The gain is small (4.4 → 3.7 ms with `v2_fast`) because GPU kernels are not the bottleneck.
- **Where the time goes** (cProfile): Python per-ligand loops inside ADock.
  - `mckernel.receptor_neighbours`, the exact-polish neighbour lists, is about 55% of `v2_fast` search time and about 78% for `frag_xlite`. Dropping it (`_nn`) or the polish (`_np`) gives 2–4×.
  - Next are the per-ligand `stage_a_kernel` lattice and nearest-grid lookup, which could be computed once per pocket.
  - Running 4 processes per GPU hides part of this (×1.95 over 1 process per GPU).
  - Vectorising both loops in ADock is the sibling team's call. I estimate a further 2–5×, but did not measure it.
- **CPU:** the grid build costs about 0.36 s per pocket on 1 thread; with 64 fragments that is about 5.6 ms per pair, so CPU-only runs should batch many fragments per pocket. 16 OpenMP threads give a 12× wall-time speed-up on the loaded node.

## 3. Signal check: details
See the tables above; the full output is in `results/feasibility/signal_report.txt` (`analyze_signal.py`).
- **Seeds:** the median |Δscore| between seeds is 0.01 kcal/mol (95th percentile 0.2). `v2_default` and `v2_fast` are essentially deterministic: raw r is 0.999–1.000.
- **Normalisation is not optional.** Without it every pocket looks like every other.
- **dz is not enough on its own.** Its first axis is still "big apolar pocket likes big fragments". A real method would need:
  - a size-matched fragment panel (e.g. 10–14 heavy atoms), or per-heavy-atom (ligand-efficiency) scores;
  - an explicit size covariate or regression;
  - evaluation against a size-only baseline (volume and buriedness) on a real benchmark (ProSPECCTs, TOUGH-M1).

## 4. Alternatives (prototyped)
- **(i) Probe maps on BURROW points** (`pseudo_probe.py`):
  - Method: Vina energy of 10 XS probe atoms at each pocket point, relaxed over ±0.75 Å, summarised by quantiles and the fraction of favourable points (40 features).
  - Cost: 141 ms per pocket on 1 CPU thread with unoptimised numpy, about 25× cheaper than the 64-fragment dock on CPU. A GPU or grid version would take a few milliseconds.
  - Signal: poor (partner ranks 15/15/1/1/13/12). Single-atom probes on the solvent-shell points are dominated by repulsion and by how close the points sit to the protein. Not recommended as is.
- **(ii) Rigid-body GPU scan** (`frag_scan`): no faster than `frag_lite_np` (overhead-bound), but noisier (seed r 0.76) and it fails redocking in 1 of 3 seeds. Not worth it.
- **(iii) BURROW size-free descriptors:** free, and as good on the near-identical pairs. Worse on the CDK2 pair with the ligand-induced shape change.

## Recommendation
1. Fragment docking is technically easy (overlay env in 10 s) and cheap below about 10 M pockets (10k pockets is about 1 node-minute).
2. At full AFDB scale (≈1e9 pockets) it costs about 80 node-days for 64 fragments, so it does not fit a 24 h budget. It would need the ADock loop vectorisation, or use only for re-ranking candidates found by a cheaper descriptor.
3. Its signal is reproducible but dominated by pocket size and hydrophobicity. It earns a place only if, on a real benchmark, it beats BURROW descriptors plus a size baseline.
4. Next step: run `frag_lite_np` with a size-matched panel of about 64–128 fragments on a ProSPECCTs or TOUGH-M1 subset (a few thousand pockets is about one node-minute). Report it alongside a volume-only and a BURROW-descriptor baseline before investing further.

## Files
- Scripts, in `scripts/feasibility/`:
  - `setup_adock_overlay.sh`, `make_fragments.py`, `make_pockets.py`, `dock_panel.py` (presets, layouts, timing)
  - `analyze_signal.py`, `pseudo_probe.py`, `redock_control.py`
- Outputs, in `results/feasibility/`:
  - `timing.tsv` (concurrent rows lost to the write race; see `concurrency.txt`)
  - `scores_*.tsv`, `signal_report.txt`, `pockets.tsv`, `pockets_burrow_descriptors.tsv`, `pocket_points.npz`
  - `probe_fingerprints.tsv`, `fragments.sdf`, `receptors/`
- Run all commands from the project root with the environment from §1.
