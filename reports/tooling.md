# Tooling: consistent API, `pocketcompare` CLI, human AFDB release (2026-10-28)

Frozen files are untouched: `final_eval.py`, `evaluate.py`, `results/final/`, `configs/final_method.yaml` and the
weights. Nothing is committed.

## 1. API consistency (`src/pocketcompare/method.py`)
**`describe(..., site, locate="burrow")` now matches the evaluation's D locator.**
- The rule: the region pockets are merged; the merged pocket that covers the site best is matched; then that
  pocket's member that covers the site best is described.
- The old rule, the best member over all region pockets, is kept as `locate="burrow_flat"`. It chose a different
  member for 4/765 TOUGH-M1-dev and 2/523 BLiPS-val sites.
- **Regression test:** `tests/test_method_eval_consistency.py`.
  - It runs BURROW from the structure file for 20 TOUGH-M1-dev and 20 BLiPS-val pockets. The set includes every
    pocket where the old and new rules differ.
  - `describe` reproduces the evaluated embeddings with max |Δ| ≤ 1.1e-7 in both L and D mode.
  - With `burrow_flat`, the differing pockets fail (|Δ| up to 0.20).

**New: `method.describe_all(structure)`.**
- It describes merged region-rule pockets with ≥ 10 points; base = the merged pocket, then sph8. This is exactly the
  unit of the proteome demo and the blind test (tested against `eval_blind`'s rule).
- `unit="member"` gives every sub-pocket, which equals `describe(site=None)` (unchanged).
- Empty sph8 sets fall back to the base set; the demo dropped such pockets, which affected 1 pocket in the proteome.

## 2. CLI (`pocketcompare` console script; `python -m pocketcompare`; `src/pocketcompare/{cli,fpindex}.py`)
**Subcommands:**
- `describe`: files or directories → parquet with id, BURROW rank and score, residues, centre, volumes, pLDDT
  stats and the 384-d fingerprint, plus a per-structure status/timing sidecar. Options: `--af-mode`,
  `--ligand`/`--residues` with `--locate`, `--workers`, `--device cuda:N`, `--backend ref|fast`.
- `compare`: files or structures → top pairs and the full matrix.
- `index`: flat, or OPQ + IVF-PQ plus fp16 vectors for re-ranking. Vectors are stored as is: they are unit-norm,
  and the score is the inner product.
- `search`: top-k with exact re-ranking.

**Tests:** `tests/test_cli.py`, 10 tests on the BURROW examples, all passing. They show:
- the CLI output equals the API output;
- the ref, fast-CPU and GPU backends give identical results;
- L/D site modes, zero-pocket and bad-file handling work;
- `compare` returns the inner products;
- flat search is exact, and IVF-PQ with re-ranking reaches recall@10 > 0.95 on a synthetic 1.2k set.

Fully AF-pruned models now give 0 pockets on the ref backend instead of an error, as on the fast backend.

**Runtime** (`scripts/tooling/bench_describe.py` → `results/tooling/describe_runtime.json`): 2,000 random AFDB human
models with 5.7 pockets each, run end to end through the CLI on a shared node.

| | ref CPU | fast CPU | GPU (RTX 4090) |
|---|---|---|---|
| per structure, 1 core: median / mean | 0.42 / 0.58 s | 0.21 / 0.30 s | 0.13 / 0.21 s |
| throughput, 22 workers | 34 /s | 55 /s | 56 /s (CPU-bound; GPU 10 ms/structure) |

- Description plus embedding costs ≈ 40 ms per structure; start-up is ≈ 1 s.
- Fingerprints are identical across backends (max |Δ| = 0).

## 3. Human-proteome release (`scripts/proteome/release_final_head.py` → `results/release/human_afdb_v6.json`)
- **Build:** the frozen n1_linear head was applied to the stored N1 descriptors; BURROW was not re-run. The output
  is `data/processed/release/human_afdb_v6/`: 116,246 pockets, `fingerprints.parquet` (1.5 kB/pocket),
  `index_flat/`, `index_opq_ivfpq/` (94 B/pocket + 768 B fp16), `README.md` and `SHA256SUMS`.
- **Cross-check:** `describe_all` re-run from 40 model files reproduces all 209 released vectors to 1.2e-7.
- **PQ vs exact recall@10** (10k queries):

  | nprobe | PQ alone | + re-rank of the top-100 | latency (1 thread) |
  |---|---|---|---|
  | 16 | 0.815 | 0.876 | |
  | 32 | 0.866 | 0.952 | |
  | 64 (default) | 0.886 | **0.987** | 0.77 ms |
  | exact flat | | | 7.3 ms |

- **Hubness of the top-10 graph:** raw skewness 1.62 (maximum 93; N1 demo: 1.82 / 109); with CSLS (database radii)
  0.55 (37).
- **The new neighbours differ from the N1 demo's:** top-10 overlap is only 0.20. The demo's family sanity checks
  were not re-run for the final head.

## 4. Docs
- `docs/FINGERPRINTS.md`: the handover note for ADock/BURROW. It covers what the fingerprint is, how to compute,
  compare and search, runtime, storage, score scale, and limitations: sph8, L vs D, PPI, cofactors, AF/pLDDT, hubness.
- `README.md` has new CLI, `describe_all`/locator, release and reproduce sections.

## Caveats
- Throughput comes from a shared node: load average 23 → 80 during the run.
- The GPU path runs one device per process, so for two GPUs, shard the input.
- Blind-retrieval numbers quoted in the note are from the N1 dry run and were not re-measured with the final head.
