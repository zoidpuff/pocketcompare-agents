# AFDB-scale demo: the human proteome, all-vs-all (2026-10-27)

**Input.** AFDB v6 human proteome tarball, read by byte offset and never extracted: 23,586 models, 20,550 UniProt
entries (sha256 `1de6f3d7…`, 47,172 members; DATA.md).

**Pipeline.**
- BURROW AF mode, full list, region rule.
- Merged pockets with ≥ 10 points. This also drops 2.1 single-point metal candidates per model.
- Ligand-free tier-1 descriptor: **A1(sph8) + env(sph8)**, 627 d (sph8 around the merged pocket's bur16⁴ centroid,
  the `@sph8` row of definition_robustness.md). Vectors are stored raw; the A4b head is not applied.
- Index vectors: z-scored with **TOUGH-M1-dev (731) + BLiPS-train v2 (2,350)** D-mode pockets (no test set), each
  block L2-normalised, 1:1 block cosine.

## 1. Throughput (full proteome, same node, shared: load 52–67 on 64 cores)
| backend (all: identical outputs) | wall | structures/s | pockets/s | CPU ms/structure: read · BURROW · descriptors |
|---|---|---|---|---|
| **fast GPU**, 2 × RTX 4090 + 22 CPU workers | 177.6 s | **132.8** <!-- src: results/proteome/summary.json#runs.run_gpu.structures_per_s --> | **716** <!-- src: results/proteome/summary.json#runs.run_gpu.pockets_per_s --> | 33 · 77 · 35 (+ 4.8 GPU-ms) |
| fast CPU (Numba), 22 workers | 337.3 s | 69.9 <!-- src: results/proteome/summary.json#runs.run_fastcpu.structures_per_s --> | 377 | 32 · 246 · 34 |
| reference featuriser (our adapter), 22 workers | 679.6 s | 34.7 <!-- src: results/proteome/summary.json#runs.run_refcpu.structures_per_s --> | 187 | 22 · 572 · 35 |

- **The GPU run is CPU-bound.** Worker utilisation is 87 %, and the GPU is busy only 56 of 174 s per device.
  - CPU time splits: BURROW parse/prep/formation/ranking 54 %, descriptors 24 % (**6.4 ms/pocket**), and tar
    read + gunzip 23 %.
  - More CPU workers per GPU is the next lever.
- **Backends agree byte for byte.** Pocket tables and raw descriptors are identical across all three backends for
  all 127,200 pockets (`backend_equivalence.json`).
  - On 20 models, points, features, scores and pocket lists are identical too (`fast_equivalence.json`,
    `tests/test_pockets_fast.py`).
  - The reference path raises on 74 models that AF-mode pruning empties completely. The fast path returns 0 pockets
    for them.
- **Pockets.**
  - Per model: 18.1 region pockets → 17.6 merged → **5.39 kept**. 7.8 % of models have no pocket.
  - Size: median 53 points / 73 Å³ (p90 261); sph8 site 376 Å³.
  - Lining pLDDT: median 88.8; 5.6 % of pockets are below 70.
- **Fragments.** All 3,251 fragment models are processed and mapped to UniProt numbering via the DBREF offset.
  - They are de-duplicated greedily by score: a pocket is dropped if its residue Jaccard is ≥ 0.5 with a kept
    pocket from another fragment (pocket_detect's rule).
  - This removes 10,954 duplicates, leaving **116,246 indexed pockets**
    in 19,084 proteins.

## 2. Index and search (FAISS 1.14.1, faiss-gpu-cu12)
- **Exact (GpuIndexFlatIP, 1 GPU).** All-vs-all top-50 for all 116,246 pockets takes **0.51 s** <!-- src: results/proteome/index_search.json#exact.all_vs_all_wall_s -->
  (4.4 µs/pocket batched, 2.7 × 10¹⁰ pairs/s).
  - Single query: 0.58 ms on GPU, 13.1 ms on CPU (1 thread).
  - Storage: 2,508 B/pocket (float32).
  - Median cosine of hit 1 / 10 / 50: 0.80 / 0.75 / 0.70.
- **IVF-PQ** (627 → 640 d zero-pad, nlist 1,024, PQ64 × 8 bit = 64-byte codes; trained on 100k).
  - Scored on 10k random queries, self excluded, against exact top-10.

| index | B/pocket (with ids) | nprobe | recall@10 | top-1 agree | recall@10 after exact re-rank of PQ top-100 | 1-query latency (1 thread) |
|---|---|---|---|---|---|---|
| IVF-PQ64 | 100 | 16 / 64 | 0.62 / 0.63 | 0.48 / 0.49 | 0.92 / 0.99 | 0.31 / 0.64 ms |
| **OPQ64 + IVF-PQ64** | 114 | 16 / 64 | **0.81** <!-- src: results/proteome/index_search.json#ivfpq.OPQ64_640,IVF1024,PQ64.sweep.16.recall_at_10 --> / 0.85 | 0.73 / 0.76 | 0.92 / **0.995** <!-- src: results/proteome/index_search.json#ivfpq.OPQ64_640,IVF1024,PQ64.sweep.64.recall_at_10_rerank_top100 --> | 0.54 / 0.86 ms |

64-byte codes alone lose too much: recall@10 is at most 0.85. PQ shortlist + exact re-rank (the vectors kept on disk
as fp16) gives ≥ 0.99 at < 1 ms.

## 3. Sanity checks (label-free)
**(a) Perturbed copies of 20 random models.** Each pocket is queried against all 116,246 pockets; we report the rank of
its original.
- *detected*: the copy is re-run through BURROW, and its pockets are matched to originals by residue Jaccard ≥ 0.5.
- *fixed centre*: the original centre is moved by the same rigid motion and described in the copy's points.

| copy | detected: matched / copy pockets | detected: rank 1 (top-10) | fixed centre: rank 1 (top-10), median cos |
|---|---|---|---|
| rotation + 10 Å translation | 104 / 111 | 97 % (100 %) | **100 %** <!-- src: results/proteome/sanity_jitter.json#per_condition.rot|fixed_centre.rank1 --> (100 %), 1.000 |
| + 0.5 Å RMS per-atom noise | 59 / 110 | 80 % (92 %) | 94 % (98 %), 0.93 |
| + 1.0 Å RMS per-atom noise | 43 / 104 | 53 % (67 %) | **83 %** (89 %), 0.88 |

- The descriptor is rigid-motion invariant up to PDB rounding.
- Under 1 Å noise, BURROW's **detection** changes first: only 41 % of copy pockets keep a Jaccard ≥ 0.5 counterpart.
  A described site still finds itself at rank 1 in 83 % of cases.

**(b) Known family (descriptive; KLIFS human kinases plus pocket_detect's known BioLiP sites, local files).**
- Queries: 196 kinase pockets at a known small-molecule site.
- Their top-10 hits outside the query's own UniProt entry are **75 % kinase pockets** (size-matched random
  expectation 4.6 %, 16×) and 30 % kinase-site pockets (expectation 0.26 %).
- Kinase hits are in the same KLIFS group 47 % of the time (expectation 12 %).
- With CSLS: 68 % kinase hits, 53 % same group.
- All 5,168 kinase pockets: 15 % kinase hits (3.3×).
- Non-kinase ligand-site pockets: 3.4 % kinase hits (0.8×).
- Kinase domains are homologous, so this shows the index recovers a known site family. It is **not** evidence of
  fold-independent similarity.

**(c) Hubness of the top-10 graph** (in-degree N₁₀; self excluded):

| ranking | skewness | max | p99 | in-degree 0 | top-1 % share |
|---|---|---|---|---|---|
| raw cosine | 1.82 <!-- src: results/proteome/index_search.json#hubness.raw.skewness --> | 109 | 41 | 4.5 % | 5.0 % |
| CSLS, r from the proteome (k = 10) | **0.62** <!-- src: results/proteome/index_search.json#hubness.csls_db.skewness --> | 37 | 22 | 0.1 % | 2.4 % |
| CSLS, r from the DESIGN reference pool | 1.55 | 104 | 33 | 1.1 % | 3.9 % |

- Hubness is moderate. The hubs are large buried sites: median sph8 volume 482 vs 376 Å³, and r_db 0.88 vs 0.77.
- CSLS with database-local radii removes most of the hubness while keeping 68 % of the raw top-10.
- The reference-pool radii (holo PDB pockets) barely help on AF pockets.
- Only 3.1 % of top-1 hits come from the same protein.

## 4. Extrapolation to 200 M structures (EXTRAPOLATED, not run)
Basis: the measured per-model cost of non-fragment human models, 4.75 pockets/model, and linear scaling.

| quantity | value |
|---|---|
| Pockets | ≈ 0.95 × 10⁹ |
| Build | ≈ 7,150 CPU-core-h (BURROW 3,570, descriptors 1,620, I/O 1,950) + 223 GPU-h <!-- src: results/proteome/summary.json#extrapolation_200M.gpu_hours -->; 15.5 days on one node like this, ~4 h on 100 |
| Storage | raw float32 2.4 TB, fp16 1.2 TB, OPQ-IVF-PQ64 index 0.11 TB, metadata 0.10 TB |
| Exact all-vs-all | ≈ 9,400 GPU-h (N²) |
| Exact single query (CPU) | ≈ 110 s |

- Human models are longer than the AFDB average, so the build cost is probably an overestimate.
- ANN latency at 10⁹ vectors is **not measured**. It needs nlist ≈ 2¹⁶–2²⁰ with an HNSW coarse quantiser.

## Caveats
- The z-statistics come from holo PDB pockets and are applied to AF pockets.
- The pocket unit is the merged region-rule pocket centred by sph8. definition_robustness.md recommends the
  set-max over sub-pockets for deployment; that is not done here.
- The 1 Å-noise test mixes descriptor and detection noise; the *fixed centre* arm separates them.
- Timings are from a shared node and are pessimistic.

**Files.**
- Scripts (`scripts/proteome/`): `index_tar.py`, `run_proteome.py`, `run_stage1.sh`, `run_cpu_backends.sh`,
  `ref_stats.py`, `index_search.py`, `sanity_{jitter,family}.py`, `compare_backends.py`,
  `check_fast_equivalence.py`, `summarize.py`, `write_sidecars.py`.
- Library: `src/pocketcompare/pockets_fast.py`.
- Results: `results/proteome/*.json` (+ `.prov.json`).
- Data: `data/processed/proteome_human/` (1.6 GB).
