# Cost of running pocketcompare on the whole AFDB (estimate, 2026-10-28)

> Copied from the research repository (`docs/AFDB_COST.md`, 2026-10-28). File paths below (`results/...`,
> `scripts/tooling/...`, `data/processed/...`) refer to that repository and are not part of this package.

Everything below is extrapolated from measurements on this node (64 CPU cores allocated, 4× RTX 4090, shared with
other users), using the frozen method (BURROW default preset, AF mode → describe_all → 384-d fingerprint).
Raw logs/JSON: `results/tooling/afdb_cost/`, `results/tooling/bench_*.json`, `results/proteome/summary.json`,
`results/release/human_afdb_v6.json`. Benchmark script: `scripts/tooling/bench_afdb_proteome.py`.
Assumptions: 200 M structures (scale linearly for 214 M), AFDB dominated by bacterial/TrEMBL entries of ~300–350 aa
(E. coli / Salmonella / Pseudomonas samples: mean 307–331 aa), 4.6–4.8 pockets per structure (measured).

## 1. Measured throughput
| configuration | structures/s | notes |
|---|---|---|
| 1 shard: 1 GPU + 15 workers, thread caps, quieter node | 149 | 4,000 E. coli models in 26.9 s; GPU ~50 % busy, 1.5 GB VRAM |
| **full node: 4 shards × (1 GPU + 15 workers), thread caps** | **380** | 16,000 models (E. coli, Salmonella, Pseudomonas, yeast) in 42 s; 0 errors; 1,760 pockets/s |
| full node, CPU only (4 × 15 workers, fast Numba backend) | 234 | same 16,000 models in 68 s |
| human proteome demo (2 GPUs + 22 workers, no thread caps) | 133 | 23,586 models; CPU ms/structure: read 33 · BURROW 77 · descriptor 35, + 4.8 GPU-ms |
Per-thread caps (`OMP_NUM_THREADS=NUMBA_NUM_THREADS=1`) matter: without them one shard topped out at 76–95/s.
Peak memory: ~1 GB per worker (15–16 GB per 15-worker shard; 62 GB for the full node).

## 2. Cost per structure and per stage
| stage | GPU path | CPU-only path | 200 M structures |
|---|---|---|---|
| read + gunzip mmCIF (~70 KB) | ~20–33 core-ms | same | ~1,100–1,800 core-h |
| BURROW detection + point features | ~77 core-ms + ~5 GPU-ms | ~246 core-ms | GPU path ~4,300 core-h + ~280 GPU-h; CPU ~13,700 core-h |
| sph8 + N1 descriptor (6.4 ms/pocket × 4.7) | ~30–35 core-ms | same | ~1,700–1,900 core-h |
| A4b linear head (627 → 384) | < 0.1 ms | same | negligible |
| **total (measured end to end on the full node)** | **≈ 0.16 core-s + ≈ 5–10 GPU-ms** | **≈ 0.27 core-s** | **≈ 8,800 core-h + ~300–550 GPU-h**, or **≈ 15,000 core-h** CPU-only |
On our node alone: 200 M / 380 s⁻¹ ≈ **6.1 days** (GPU) or 200 M / 234 s⁻¹ ≈ **9.9 days** (CPU only).

## 3. Indexing and search (pockets ≈ 0.95 × 10⁹)
| item | cost | basis |
|---|---|---|
| fingerprints fp16 / fp32 | 0.73 TB / 1.46 TB | 768 / 1,536 B per pocket |
| OPQ + IVF-PQ index (64-B codes + ids) | ≈ 0.09 TB, fits in ~128 GB RAM | measured 94 B/pocket |
| metadata (residues, centre, scores) | ≈ 0.1 TB | 109 B/pocket |
| index build (train on ~10 M sample, add 10⁹) | ~1–3 h on 1 GPU (not measured at this scale) | — |
| one query, exact brute force | ~60 s/thread on CPU; fp16 matrix does not fit 4×24 GB VRAM | 7.3 ms per 116 k (measured) |
| one query, IVF-PQ + fp16 re-rank | ~10–30 ms/thread (estimate) | scanned-code scaling from the 116 k measurement |
| **exact all-vs-all top-k** | **≈ 7,600 GPU-h** (4090) | 3.3 × 10¹⁰ pairs/s measured |
| approximate all-vs-all (IVF-PQ) | ~5,000 core-h CPU; GPU likely 10–30× less (not measured) | estimate |
Fingerprinting is embarrassingly parallel; the all-vs-all graph is the only step that does not shrink with more CPUs.

## 4. Data movement
- Input: ~200 M × ~70 KB ≈ **14 TB** of mmCIF.gz (mean 63 KB E. coli, 97 KB yeast, 126 KB human). Only 49 proteomes
  + Swiss-Prot are on local disk; the rest must be streamed (e.g. the public AFDB Google Cloud bucket), in shards
  that are deleted after processing (project storage cap 500 GB).
- Sustained read at 24 h: ≈ 2,300–2,800 structures/s × 70 KB ≈ **160–200 MB/s** (≈ 1.5 Gbit/s).
- Output: ≈ 1.4 TB (fp32 parquet as written now) or ≈ 0.8 TB (fp16 + metadata) + 0.09 TB index → exceeds the 500 GB
  cap; keep the PQ index + metadata on project storage and the fp16 vectors on scratch/object storage.

## 5. What it takes to finish in 24 h
Required rate: 200 M / 86,400 s = 2,315 structures/s; with ~20 % margin (stragglers, I/O, long proteins) ≈ 2,800/s.
| option | hardware | expected time |
|---|---|---|
| A. 8 nodes like ours (GPU path) | 8 × (64 cores, 4 GPUs, ≥ 128 GB RAM) = 512 cores, 32 GPUs, ~1 TB RAM | ≈ 18 h |
| B. 2 large GPU nodes | 2 × (≥ 256 cores, 8 GPUs ≥ 8 GB VRAM, 512 GB–1 TB RAM) | ≈ 16–20 h (assumes linear scaling to 256 cores; not measured) |
| C. CPU only | ≈ 700–800 cores (11–12 × 64-core nodes), ≥ 1 GB RAM/core | ≈ 20–24 h |
| D. our single node | 64 cores, 4 × 4090 | ≈ 6 days |
Rules of thumb: ~450–500 busy CPU cores is the real requirement; GPUs are lightly used (≈ 1.5 GB VRAM, ~50 % busy per
shard), so 1 modest GPU per ~16 cores is enough and VRAM size does not matter; RAM ≈ 1–2 GB per worker (2 GB if
the 2,700-aa fragment models are included). No single standard node does it in 24 h.
An exact all-vs-all similarity graph is a separate, much larger job (≈ 7,600 GPU-h); an approximate kNN graph or a
query service on the IVF-PQ index is the realistic deliverable.

## 6. Caveats
- Shared node: single-shard rates varied 76–149/s with background load and thread settings; full-node numbers are
  from one 42 s run per configuration. Re-measure on the target cluster with ~100 k structures before booking.
- AFDB length distribution assumed from bacterial/yeast proteomes; long eukaryotic proteins cost somewhat more.
- BURROW's `--preset fast` would cut detection cost further but changes the pockets; the method was not validated
  with it.

## 7. Which pockets are fingerprinted, and score cutoffs (added 2026-10-28)
`describe_all` fingerprints every merged BURROW region-rule pocket with ≥ 10 points, with **no score cutoff**.
Human run: 43 BURROW candidates → 18.1 region pockets → 17.6 merged → **5.39 kept** per model (12 per model are < 10
points: surface tiles and single-point metal candidates). Median BURROW score of kept pockets 0.05; 28 % ≥ 0.1.
Effect of a score cutoff on true ligand sites (dev data: 1,299 BLiPS val+train sites on 843 AF models, blind
setting; `results/tooling/site_score_recall.json`, `scripts/tooling/site_score_recall.py`):
| min BURROW score | detected true sites kept | pockets kept | pockets / model |
|---|---|---|---|
| none (current) | 100 % (65 % of all sites detected) | 100 % | 5.3 |
| 0.03 | 99.2 % | 78 % | 4.2 |
| 0.05 | 93.7 % | 56 % | 3.0 |
| 0.1 | 84.8 % | 37 % | 2.0 |
| 0.3 | 61.8 % | 17 % | 0.9 |
These are known small-molecule sites; interface (PPI) pockets score lower in BURROW (only 9.9 % ≥ 0.3 vs 17 % for
single-chain pockets, reports/ppi_dimers.md), so cutoffs remove them disproportionately. Recommendation: keep all,
store the score, and use a cutoff (e.g. 0.03) only as a search-time filter or index tier.

## 8. Storing BURROW's pockets (beyond the fingerprints)
| what | per pocket | 0.95 × 10⁹ pockets | note |
|---|---|---|---|
| pocket table (ranks, score, centre, residues, volumes, pLDDT) | 116 B (parquet, measured) | **≈ 0.11 TB** | enough for docking boxes (centre + volume) |
| pocket grid points, xyz only (mean 97 points; 1 Å lattice → int16 or fp16) | ≈ 0.6 KB (≈ 0.25 KB zstd) | ≈ 0.25–0.6 TB | merged pocket; the sph8 site (mean 257 points) ×2.6 |
| pocket grid points + 84 point features (fp16) | ≈ 16 KB | ≈ 15 TB | not worth it: recomputing is ~0.16 CPU-s/structure |
| BURROW full point cache (all grid points of the structure) | — | ≈ 100–160 TB (0.5–0.8 MB/structure) | infeasible; recompute on demand |

## 9. Staggered roll-out on our node (≈ 380 structures/s, GPU path)
| tier | structures | node time | pockets | fp16 + table |
|---|---|---|---|---|
| human (done: data/processed/release/human_afdb_v6) | 23.6 k | ≈ 1 min (measured 3 min on half the node) | 116 k | ≈ 0.1 GB |
| all 48 local model-organism / global-health proteomes | ≈ 0.5–0.7 M (84.6 GB of tarballs) | ≈ 25–30 min | ≈ 3 M | ≈ 3 GB |
| Swiss-Prot (local, 68.6 GB) | ≈ 0.55 M | ≈ 25 min | ≈ 2.6 M | ≈ 2.3 GB |
| AFDB Foldseek cluster representatives | ≈ 2.3 M | ≈ 1.7 h | ≈ 11 M | ≈ 10 GB |
| AFDB50 (UniRef50-level representatives) | ≈ 50 M | ≈ 1.5 days | ≈ 0.24 B | ≈ 0.2 TB |
| full AFDB | ≈ 200–214 M | ≈ 6–6.5 days | ≈ 0.95–1.0 B | ≈ 0.85 TB |
Cluster-representative counts are from the AFDB/Foldseek publications (approximate); only the first three tiers
are on local disk.
