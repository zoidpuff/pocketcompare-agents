# pocketcompare over the AlphaFold DB on Euler

This folder runs the frozen `pocketcompare` method (BURROW AF mode → merged pockets → 384-d fingerprint) over the
AlphaFold database on ETH's Euler cluster. It uses 4 GPU nodes (64 cores, 4 × RTX 4090 each) and works in three
tiers ordered by organism priority. Everything is resumable. Nodes share state through the file system, one SLURM
array task per node.

| file | what it does |
|---|---|
| `config.sh` | every path and knob (all can be overridden from the environment) |
| `setup_env.sh` | builds the venv with uv-managed CPython 3.12 (idempotent), warms Numba, self-tests on CPU and GPU |
| `species_order.tsv` | tier-1 proteome order with a short rationale for each |
| `make_worklist.py` | writes `OUT_ROOT/worklist.parquet` (+ `.tsv`, `worklist.json`) and `OUT_ROOT/skip_accessions.txt` |
| `worker.py` | one per node: claims units, extracts or downloads them, describes them on 4 GPUs, filters, writes outputs |
| `describe_server.py` | the persistent per-GPU `pocketcompare describe` used by the worker (same code path) |
| `afdb.sbatch`, `submit.sh` | the array job (`--array=0-3`, one node per task) and a checked submission wrapper |
| `status.py` | progress per tier, throughput, ETA, failures |
| `build_index.py` | FAISS OPQ + IVF-PQ index (chunked; up to ~10⁹ pockets) or an exact flat index |
| `smoke_test.sh`, `mock_gcs_server.py` | end-to-end test on a tiny work list (about 1 min, +1–2 min without cached tar indices / taxonomy) |
| `download_metadata.json` | AFDB v6 per-archive structure counts (EBI FTP, fetched 2026-10-28) |

## Step by step (on the Euler host)

```bash
cd /cluster/project/beltrao/gmagnus/pocket_compare/release/pocketcompare
bash afdb/setup_env.sh                       # once (~2 min); re-run on a GPU node to also run the GPU self-test
source afdb/config.sh                        # OUT_ROOT=/cluster/scratch/gmagnusson/pocketcompare_afdb by default
# optional: reuse the tar indices and GCS listing built while testing (saves ~20 min)
mkdir -p $OUT_ROOT && cp -r /cluster/project/beltrao/gmagnus/pocket_compare/release/afdb_smoke/worklist_full/{tar_index,gcs_listing.tsv.gz,gcs_listing.json} $OUT_ROOT/
$ENV_DIR/bin/python afdb/make_worklist.py    # tiers 1-3: ~10 min tar indexing + ~11 min GCS listing (both cached)
#   --tiers 1,2 for local data only; --gcs-max-pages 20 for a quick partial tier 3
srun --gpus=rtx_4090:2 --cpus-per-task=32 --mem-per-cpu=3G --time=1:00:00 -A es_biol -p es_biol \
     bash afdb/smoke_test.sh                 # optional, ~1-3 min; writes into release/afdb_smoke/smoke
bash afdb/submit.sh --tiers 1                # tier 1 first (~10 min on 4 nodes), then:
bash afdb/submit.sh --tiers 2                # Swiss-Prot (~5 min), then (after GCS access is sorted out, see below):
bash afdb/submit.sh                          # everything that is left (tier 3, ~1.7 days)
$ENV_DIR/bin/python afdb/status.py           # monitor; logs: $OUT_ROOT/logs/pocketcompare-afdb_<job>_<task>.out
$ENV_DIR/bin/python afdb/build_index.py --tiers 1 --kind flat -o $OUT_ROOT/index/tier1_flat
$ENV_DIR/bin/python afdb/build_index.py --tiers 1,2,3 --kind ivfpq -o $OUT_ROOT/index/all_ivfpq --threads 32
$ENV_DIR/bin/pocketcompare search my_site.parquet $OUT_ROOT/index/tier1_flat -k 20 -o hits.tsv
```

You can also submit all tiers at once (`bash afdb/submit.sh`): units are claimed in work-list order, so tier 1
finishes first anyway. `submit.sh` checks that the environment and the work list exist. When GCS units are in
scope it also test-downloads one GCS object and refuses to submit if that fails (`SKIP_GCS_CHECK=1` overrides).
It sends `--tiers` and `--retry-failed` on to the workers, and anything after `--` goes to `sbatch`.
`DRY=1` prints the command without submitting.

**Run `index` / `build_index.py` / `status.py` with the same `OUT_ROOT` as the run** (source `config.sh`, or
pass `--out-root`).

## Check on the host before submitting

1. **GCS downloads (tier 3). They were denied here.** On 2026-10-28, listing the bucket worked anonymously
   (2,031,605 objects in 11 min). Every object download returned **HTTP 403** ("Anonymous caller does not have
   storage.objects.get access"), for tars and for single files, from this node through the ETH proxy. Test it
   from a login node:
   `curl -sI https://storage.googleapis.com/public-datasets-deepmind-alphafold-v4/proteomes/proteome-tax_id-100-0_v4.tar | head -1`.
   If it is still 403, use an authenticated Google account: `GCS_AUTH_CMD='gcloud auth print-access-token'`.
   If the bucket turns out to be requester-pays, also set `GCS_USER_PROJECT=<billing project>`, which costs
   egress for ~26 TB. Another option is a mirror (`GCS_BASE_URL`). Tiers 1 and 2 need no network.
2. **Internet from compute nodes.** `afdb.sbatch` runs `module load eth_proxy` when no proxy is set. Check that
   a compute node reaches `storage.googleapis.com`, for example with the curl above inside `srun`.
3. **Scratch quota.** Run `lquota`. Euler personal scratch allows 2.5 TB and 1,000,000 files. The full run
   writes about 0.65 TB in about 150 k files (see Storage).
4. **Scratch purge.** Euler **deletes scratch files older than 15 days** (docs.hpc.ethz.ch/hardware/storage,
   read 2026-10-28; check the current policy). This applies to the outputs **and** to the work list, skip list,
   tar indices and done markers. Copy every finished tier to permanent storage. Re-create the work list
   (`make_worklist.py` reuses its caches only while they exist) if a run is paused for more than about 10 days.
   Small files worth keeping elsewhere: `worklist.parquet`, `skip_accessions.txt`, `tar_index/`,
   `gcs_listing.tsv.gz` (≈ 60 MB together).
5. The node type and account in `afdb.sbatch` (`es_biol`, `rtx_4090:4`, `--tmp=200G`) come from your template.
   The job asks for 7 days. `--signal=B:USR1@900` lets the workers stop claiming 15 min before the time limit.

## Tier design

Units are processed in work-list order: tier 1, then tier 2, then tier 3. Within a tier they run in the order
below. Every unit is a member range of one local tar, or a pack of GCS tars.

| tier | content | structures | units | ETA, 4 nodes × 380/s |
|---|---|---|---|---|
| 1 | the 46 local AFDB v6 proteomes (`species_order.tsv`) | 555,846 | 162 | ≈ 6 min (+ start-up) |
| 2 | local Swiss-Prot v6 minus the 113,236 models whose accession is in tier 1 | 436,886 | 110 | ≈ 5 min |
| 3 | every other (taxid, shard) tar of the GCS v4 bucket, tree round-robin order | ≈ 214.0 M (estimated) | 48,341 | ≈ 39 h compute (see below) |

Counts come from `download_metadata.json` and the local tar indices (tiers 1–2) and from the full bucket listing
(tier 3). Tier 3 has 2,031,605 objects = 1,015,808 (taxid, shard) tars over 1,007,292 taxa (25.95 TB). For each
tar the highest model version is kept: all are v4 except 11 that exist only as v3. Its structure count is
estimated from tar bytes at 120.9 kB/model, calibrated as total v4 bytes / 214,684,311 AFDB v4 models. The
989,696 accessions of tiers 1–2 are subtracted. Most tars are tiny: the median is 60 kB, i.e. one model. Tier 3
therefore packs consecutive tars into units of about 4,000 estimated models (at most 2,000 tars per unit).
One unit per tar would mean about 1 M units and 3 M state/output files, which is over the scratch file quota.
Single tars hold up to 10,000 proteins and stay one unit each; the worker splits them into describe batches.

**Tier 1 order** (full table with taxids, counts and rationale in `species_order.tsv`): first the classic
experimental organisms, HUMAN, YEAST, ECOLI, MOUSE, RAT, DROME, CAEEL, DANRE, ARATH, SCHPO, DICDI. Then a spread
over the tree of life and global health: METJA (the only archaeon), PLAF7, TRYB2, MYCTU, STAA8, CAMJE, ORYSJ,
CANAL, SCHMA, BRUMA, NEIG1, PSEAE, LEIIN, AJECG, STRR6, HELPY, HAEIN, SOYBN, MAIZE, TRYCC, SPOS1, 9NOCA1, MYCLE,
SALTY, KLEPH, SHIDS, STRER, ONCVO, TRITR, WUCBA, DRAME, PARBA, 9EURO1, 9EURO2, 9PEZI1. The local directory has
46 proteome tars, exactly these 46, with no extras and none missing. The 48 archives in
`download_metadata.json` also include the two Swiss-Prot tars.

**Tier 3 order, tree round-robin.** NCBI `rankedlineage.dmp` (new_taxdump; merged taxids followed) gives each tar
a lineage, superkingdom → phylum → class → order → family → genus → taxon. At every level the child groups are
ordered by total size (descending) and interleaved one item at a time. The leaves of a taxon are its tars by size,
descending. The top level is Bacteria, Eukaryota, Archaea, Viruses (any non-cellular realm) and unclassified
(e.g. metagenomes). Early units therefore cover the tree broadly: the first 100 units (≈ 0.9 M structures) span
≈ 70 phyla, the first 1,000 (≈ 5.9 M) 216 phyla, the first 10,000 (≈ 47 M) 238. The packing keeps this order.
Accessions already in tiers 1–2 are skipped per member: `skip_accessions.txt` lists each accession with the first
tier it occurs in. GCS tars of tier-1 taxa (e.g. human, rice) are still downloaded, because they also hold
non-reference entries of those species.

## Pocket filters

`describe_all` emits every merged BURROW region-rule pocket with ≥ 10 grid points (the method default, applied
inside the method; not counted). The worker then keeps a pocket only if:

| rule (in this order) | default | dropped on the 16 k-structure bacterial test run |
|---|---|---|
| fingerprint describable (`ok`, non-zero) | — | 0 % |
| BURROW score ≥ `MIN_SCORE` | 0.03 | 19.5 % |
| mean pLDDT of the lining residues ≥ `MIN_PLDDT` | 70 | 1.6 % (human: 4.7 %) |

Rationale:
- On dev data a 0.03 score floor keeps 99.2 % of the detected true ligand sites and drops 22 % of the pockets
  (1,299 BLiPS sites on 843 AF models; `results/tooling/site_score_recall.json` in the research repository;
  `docs/AFDB_COST.md` §7).
- Pockets lined by residues with pLDDT < 70 are unreliable for evolutionary comparison.
- Protein–protein-interface pockets score lower in BURROW (only 9.9 % ≥ 0.3, vs 17 % for single-chain pockets).
  This is why the floor is low. A higher cutoff can still be applied at search time, or with
  `build_index.py --min-score`.

Each done marker records the count dropped by each rule (`dropped`: first rule that drops a pocket, plus
`any_*` counts per rule).

## Outputs

```
OUT_ROOT/worklist.parquet, worklist.tsv, worklist.json, skip_accessions.txt, tar_index/, gcs_listing.tsv.gz, ncbi/
OUT_ROOT/pockets/tier<T>/<unit_id:06d>.parquet      one row per kept pocket
OUT_ROOT/structures/tier<T>/<unit_id:06d>.parquet   one row per structure
OUT_ROOT/state/{claims,done,failed}/                claims (dirs), done / failed markers (JSON)
OUT_ROOT/logs/                                      SLURM logs, one per node
```

**Pocket table:**
- Metadata: `unit_id`, `tier`, `accession`, `fragment`, `model_version` (6 for local data, 4 or 3 for GCS),
  `taxid` (from the mmCIF, else the tar's), `organism`.
- The `pocketcompare describe` columns: `pocket_id` (`AF-<acc>-F<k>-model_v<v>:m<i>`), `merged_index`,
  `burrow_index`, `burrow_rank`, `members`, `burrow_score`, `n_points`, `volume_A3`, `center_{x,y,z}`,
  `site_n_points`, `site_volume_A3`, `sph8_fallback`, `residues` (author numbering = UniProt numbering of the
  fragment), `plddt_{mean,min,frac_lt70}`.
- `fingerprint`: `fixed_size_list<halffloat>[384]`, the float16 copy of the unit-norm float32 fingerprint
  (max |Δ| 6e-5 measured; 768 B).
- Schema metadata: `pocketcompare` (method record, `storage: float16`) and `pocketcompare_afdb` (unit, filters).

The files work directly with `pocketcompare.fpindex.read_table` (which returns float32), `pocketcompare search`
and `compare`. A 3-line loader without pocketcompare:

```python
import pyarrow.parquet as pq, numpy as np
t = pq.read_table("pockets/tier1/000000.parquet")
V = np.asarray(t["fingerprint"].combine_chunks().flatten()).reshape(-1, 384)   # float16; scores = V @ q
```

**Structure table:** `structure_stem`, `accession`, `fragment`, `model_version`, `taxid`, `organism`, `source`
(tar), `n_res` and `plddt_mean` / `plddt_frac_lt70` / `plddt_frac_lt50` (from `_ma_qa_metric_local`),
`n_pockets_all` / `n_pockets_kept`, `status` (`ok` / `error` / `missing`), `error`, and the describe timings
`parse_s`, `gpu_s`, `burrow_s`, `describe_s`, `total_s`.

**Done marker** (`state/done/<unit_id>.json`): structures (ok / error), pockets all / kept, `dropped` per rule,
extraction counts (members seen, non-model members, skipped earlier-tier accessions, duplicates, bytes, HTTP
retries), describe and wall seconds, structures/s, runner, host and SLURM ids, and a sample of errors.

## Expected times

- **Compute:** 4 nodes × ≈ 380 structures/s ≈ 1,520/s (`docs/AFDB_COST.md`: one node with 4 GPUs × 15 workers
  and thread caps, 16,000 bacterial/yeast models). Tier 1 ≈ 6 min, tier 2 ≈ 5 min, plus about 1 min start-up per
  node. Tier 3: 214 M / 1,520 s⁻¹ ≈ **39 h**.
- **Download:** tier 3 is 25.95 TB of tars (each model comes with its .pdb.gz, confidence and PAE JSON). At
  300–400 MB/s that takes 18–24 h. To keep the GPUs busy, the 4 nodes need ≈ 1,520 × 121 kB ≈ **185 MB/s**
  sustained (≈ 46 MB/s per node). Below that, tier 3 is **bandwidth-bound**: at 100 MB/s it takes ≈ 3 days. The
  first tier-3 units are dominated by tiny single-model tars, about one HTTPS request per structure; the worker
  fetches those 32 at a time per extraction thread (`GCS_FETCH_THREADS`). Tars > 16 MB are streamed.
  `status.py` and the done markers (`extract.bytes`, `wall_s`) show whether downloads keep up.
- **Measured here, on 2 GPUs + 2 × 14 workers (half a node), 15,991 bacterial models in 4 units:** 77 s with the
  persistent runner (≈ 208/s) vs 95 s with one `pocketcompare describe` subprocess per 4,000-model batch
  (≈ 168/s). Each `describe` call costs ≈ 12 s of start-up: pool spawn, imports, GPU initialisation. Local tar
  extraction reads ≈ 1,600 models/s per thread with large sequential reads, vs 370/s with one seek per member.
  Re-measure on the target nodes with tier 1, which is a ~10 min job.

## Storage

Measured on the test runs:
- Kept pockets per structure: 3.7 (16 k bacterial models), 2.1 (human), 2.7 (smoke mix). Before the filters:
  4.7, 2.4 and 3.4.
- 811 B per kept pocket on disk (fp16 fingerprint + metadata, zstd) and 54 B per structure.

| | structures | kept pockets (≈) | pocket files | index (IVF-PQ64) |
|---|---|---|---|---|
| tier 1 | 0.56 M | 1.2–2 M | ≈ 1–1.7 GB | — (use flat: ≤ 3 GB RAM) |
| tier 2 | 0.44 M | ≈ 1.5 M | ≈ 1.2 GB | — (flat) |
| tier 3 | 214 M | ≈ 0.8 B | ≈ 0.65 TB (+ 12 GB structure tables) | ≈ 75 GB RAM / file |

That is about 0.66 TB and about 146 k files (3 per unit) in total: it fits the 2.5 TB / 1 M-file scratch quota.
It does not fit a 500 GB project share, so keep tier 3 on `/cluster/work/beltrao` or LTS.
`build_index.py --save-vectors` adds 768 B/pocket of fp16 vectors for exact re-ranking (0.6 TB for tier 3).

## Index

`build_index.py` never loads all vectors:
- **IVF-PQ:** it draws a uniform training sample file by file (default max(64 × nlist, 100 k), at most 5 M
  vectors), trains `OPQ64_384,IVF{nlist},PQ64` (nlist ≈ 4√n, power of 2, ≤ 65,536), then adds the pocket files
  one at a time. `meta.parquet` (FAISS id → tier, unit_id, row, pocket_id, accession, taxid, score, pLDDT) is
  streamed out with a ParquetWriter.
- **Memory at 10⁹ pockets:** ≈ 72 B/pocket codes + ids (≈ 75 GB), 100 MB of centroids and ≤ 8 GB of training
  sample. This fits a 192 GB node. Training IVF65536 on ≈ 4 M vectors takes roughly 0.5–1 h on 32 threads (not
  measured at that scale). `--compact-ids` keeps only tier / unit_id / row in `meta.parquet`.
- **Flat:** `--kind flat` builds an exact `IndexFlatIP` (1.5 kB/pocket in RAM) for single tiers.

The directory format is that of `pocketcompare index`, so `pocketcompare search query.parquet <index dir>` works.
It re-ranks exactly when `vectors.f16.npy` exists.

## Resuming, failures, re-runs

- **Resume:** resubmit (`bash afdb/submit.sh [...]`). A unit with `state/done/<id>.json` is never redone. A claim
  is taken over when its SLURM job is no longer in `squeue`, or when it is older than `STALE_HOURS` (24 h). At
  the time limit, `USR1` makes the workers stop claiming. `TERM` releases unfinished claims immediately.
- **Failed units:** a unit whose download or describe call fails after all retries gets
  `state/failed/<id>.json` with the error. The retries are: 8 HTTP attempts with restart-and-skip, and one
  describe retry through the plain `pocketcompare describe` CLI. Structures that fail inside a unit (parse
  errors) are recorded with `status = error` and do not fail the unit. `status.py` lists failures. Re-run them
  with `bash afdb/submit.sh --retry-failed`, or interactively with
  `python afdb/worker.py --retry-failed --unit-ids 17,42`.
- **Redo a finished unit** (e.g. after changing filters): delete its done marker and its two output files, then
  resubmit.
- **Testing:** `worker.py --dry-run --max-units 20` lists what would be claimed. `--max-units`, `--tiers`,
  `--unit-ids`, `--devices cuda:0,cuda:1` and `--workers-per-shard` are useful interactively.

## How the worker works

Each node runs three kinds of threads:
- **Extraction (`EXTRACT_THREADS` = 4):** claims units with an atomic `mkdir state/claims/<id>` plus
  `claim.json` (host, pid, SLURM job/array ids, time). It writes each unit's `.cif.gz` members into node-local
  `$TMPDIR` batch directories of ≤ 4,000 models and computes per-structure pLDDT / taxid from the mmCIF
  (≈ 0.7 ms each). It skips non-model members and earlier-tier accessions.
- **GPU slots (one per GPU):** a slot takes the next batch. Up to 4 more batches wait in the queue, so
  extraction overlaps describing.
- **Finaliser:** filters, adds metadata and writes the two parquet files and the done marker. Every write goes
  to a temporary file and is renamed into place.

The default `--runner persistent` keeps one `describe_server.py` per GPU. It runs the same `pocketcompare.cli`
functions as `pocketcompare describe --af-mode --backend fast --device cuda:<g> --workers 15 --batch 16` and writes
the same files, but its GPU context and worker pool live across batches. `--runner cli` runs the literal
`pocketcompare describe` subprocess per batch. The smoke test runs both and checks the stored fingerprints of 5
structures against a direct `pocketcompare describe` with the reference CPU backend (max |Δ| 6e-5 after fp16).
Thread caps (`OMP/MKL/OPENBLAS/NUMBA/NUMEXPR_NUM_THREADS=1`) are set everywhere. `afdb.sbatch` copies the warm
Numba cache to `$TMPDIR`.
