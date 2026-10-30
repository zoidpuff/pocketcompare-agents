# pocketcompare over the AlphaFold DB on Euler

This folder runs the frozen `pocketcompare` method (BURROW AF mode → merged pockets → 384-d fingerprint) over the
AlphaFold database on ETH's Euler cluster. It uses 4 GPU nodes (64 cores, 4 × RTX 4090 each) and works in three
tiers ordered by organism priority. Everything is resumable. Nodes share state through the file system, one SLURM
array task per node.

Tier 3 (all of AFDB beyond the local data) is read by default from the **Foldcomp** database `afdb_uniprot_v4`.
That is all ~214 M AFDB v4 models in 1.1 TB, downloaded once to scratch, so the GPU jobs need no network. The
Google Cloud bucket of original v4 files remains available as `TIER3_SOURCE=gcs`, but anonymous downloads from it
were denied on 2026-10-28.

| file | what it does |
|---|---|
| `config.sh` | every path and knob (all can be overridden from the environment) |
| `setup_env.sh` | builds the venv with uv-managed CPython 3.12 (idempotent), warms Numba, self-tests on CPU and GPU |
| `fetch_foldcomp.py`, `fetch_foldcomp.sbatch` | CPU job: downloads the Foldcomp database, UniProt taxids and NCBI taxonomy (resumable) |
| `species_order.tsv` | tier-1 proteome order with a short rationale for each |
| `make_worklist.py` | writes `OUT_ROOT/worklist.parquet` (+ `.tsv`, `worklist.json`), `skip_accessions.txt` and, for Foldcomp, `fc_entries_<db>.parquet` |
| `worker.py` | one per node: claims units, extracts / decompresses / downloads them, describes them on 4 GPUs, filters, writes outputs |
| `describe_server.py` | the persistent per-GPU `pocketcompare describe` used by the worker (same code path) |
| `afdb.sbatch`, `submit.sh` | the array job (`--array=0-3`, one node per task) and a checked submission wrapper |
| `afdb_cpu.sbatch` | the same job on CPU-only nodes (64 cores, no GPU), submitted with `submit.sh --cpu-nodes N` |
| `status.py` | progress per tier, throughput, ETA, failures |
| `build_index.py` | FAISS OPQ + IVF-PQ index (chunked; up to ~10⁹ pockets) or an exact flat index |
| `smoke_test.sh`, `make_tiny_foldcomp.py`, `mock_gcs_server.py` | end-to-end test on a tiny work list: a real 300-entry Foldcomp DB for tier 3, plus a mock GCS bucket (~2 min) |
| `test_worklist_compat.sh` | regression test: tier-1/2 work list byte-identical to commit 24d1c8f; adding tier 3 keeps tier-1/2 rows |
| `POCKETOME.md` | data guide for analysing the output (formats, loading, scores, pitfalls); copied to `$OUT_ROOT` |
| `download_metadata.json` | AFDB v6 per-archive structure counts (EBI FTP, fetched 2026-10-28) |

## Step by step (on the Euler host)

```bash
cd /cluster/project/beltrao/gmagnus/pocket_compare/release/pocketcompare
bash afdb/setup_env.sh                       # once (~2 min); re-run on a GPU node to also run the GPU self-test
source afdb/config.sh                        # OUT_ROOT=/cluster/scratch/gmagnusson/pocketcompare_afdb by default
mkdir -p $OUT_ROOT/logs
# optional: reuse the tar indices built while testing (saves ~10 min of make_worklist.py)
cp -r /cluster/project/beltrao/gmagnus/pocket_compare/release/afdb_smoke/worklist_full/tar_index $OUT_ROOT/
# 1. tier-3 inputs into $FOLDCOMP_DIR (= $OUT_ROOT/foldcomp), CPU only, resumable. Files already there with the
#    server's size (e.g. fetched by curl) are reused; idmapping_selected.tab.gz is used as found. Then it builds
#    uniprot_taxid.parquet (~3 min), downloads + parses UniProt 2021_04 (151 GB, ~15 min + ~75 min) and the taxdump.
sbatch afdb/fetch_foldcomp.sbatch            # FETCH_ARGS="--dbs afdb_uniprot_v4 afdb_rep_v4" adds TIER_REPS input
# 2. the work list (a few min for all 3 tiers; DuckDB needs ~50 GB RAM for tier 3). Run it with the default
#    tier-1/2 options: an existing work list is replaced only if every finished unit keeps its definition
#    (tier-1/2 rows are reproduced exactly; tier-3 unit_ids follow them)
srun --cpus-per-task=16 --mem-per-cpu=8G --time=2:00:00 -A es_biol \
     $ENV_DIR/bin/python afdb/make_worklist.py           # --tiers 1,2 works before the fetch job has finished
srun --gpus=rtx_4090:2 --cpus-per-task=32 --mem-per-cpu=3G --time=1:00:00 -A es_biol -p es_biol \
     bash afdb/smoke_test.sh                 # optional, ~2 min; writes into release/afdb_smoke/smoke
# 3. the GPU job: 4 nodes
bash afdb/submit.sh --tiers 1                # tier 1 first (~10 min on 4 nodes), then:
bash afdb/submit.sh --tiers 2                # Swiss-Prot (~5 min), then:
bash afdb/submit.sh                          # everything that is left (tier 3, ~1.7 days)
bash afdb/submit.sh --nodes 0 --cpu-nodes 4  # optional: 4 CPU-only nodes on the same work list, alongside the GPUs
$ENV_DIR/bin/python afdb/status.py           # monitor; logs: $OUT_ROOT/logs/pocketcompare-afdb_<job>_<task>.out
$ENV_DIR/bin/python afdb/build_index.py --tiers 1 --kind flat -o $OUT_ROOT/index/tier1_flat
$ENV_DIR/bin/python afdb/build_index.py --tiers 1,2,3 --kind ivfpq -o $OUT_ROOT/index/all_ivfpq --threads 32
$ENV_DIR/bin/pocketcompare search my_site.parquet $OUT_ROOT/index/tier1_flat -k 20 -o hits.tsv
```

You can also submit all tiers at once (`bash afdb/submit.sh`): units are claimed in work-list order, so tier 1
finishes first anyway. What `submit.sh` checks before submitting:
- that the environment and the work list exist;
- for Foldcomp units in scope, that the database file is complete: its size must equal the end of the last
  index entry;
- only with `TIER3_SOURCE=gcs`, that one GCS object can be downloaded (`SKIP_GCS_CHECK=1` overrides).

It sends `--tiers` and `--retry-failed` on to the workers, and anything after `--` goes to `sbatch`. `DRY=1`
prints the command without submitting.

**Run `index` / `build_index.py` / `status.py` with the same `OUT_ROOT` as the run** (source `config.sh`, or
pass `--out-root`).

**Analysing the results:** [POCKETOME.md](POCKETOME.md) is the data guide for analysis agents (formats, loading,
what the scores mean, pitfalls). `submit.sh` copies it to `$OUT_ROOT/POCKETOME.md`.

## Check on the host before submitting

1. **Scratch quota and purge.** Run `lquota`. Euler personal scratch allows 2.5 TB and 1,000,000 files and
   **deletes files older than 15 days** (docs.hpc.ethz.ch/hardware/storage, read 2026-10-28). Peak use is about
   1.8 TB: the 1.1 TB Foldcomp database, the 0.66 TB of outputs, and a 151 GB UniProt 2021_04 tarball that
   exists during the fetch job only.
   - **Start the tier-3 run within about 10 days of the fetch.** The run takes ~2 days, and the database is
     purged 15 days after download. `fetch_foldcomp.py` re-downloads a deleted file, and resumes a partial one.
   - Copy finished tiers to permanent storage. Keep `worklist.parquet`, `skip_accessions.txt`, `tar_index/`,
     `fc_entries_*.parquet` and `fc_taxa_*.parquet` elsewhere too (≈ 2 GB together).
   - The outputs do not fit a 500 GB project share; use `/cluster/work/beltrao` or LTS for tier 3.
2. **Internet** is needed only by `fetch_foldcomp.sbatch`: S3, UniProt FTP and NCBI FTP, through `module load
   eth_proxy`. The GPU job reads tier 3 from scratch (and from GCS only with `TIER3_SOURCE=gcs`).
3. **Lustre striping.** `fetch_foldcomp.sbatch` runs `lfs setstripe -c 8` on `$FOLDCOMP_DIR`, so the 1.1 TB file
   is spread over 8 storage targets. Tier-3 workers do random 4-kB reads from it. On local NVMe these ran at
   1,100 entries/s per node; Lustre was not measured here. Watch `extract_s` in the done markers.
4. **GCS (only if `TIER3_SOURCE=gcs`).** On 2026-10-28 listing the bucket worked anonymously, but every object
   download returned HTTP 403. Test with
   `curl -sI https://storage.googleapis.com/public-datasets-deepmind-alphafold-v4/proteomes/proteome-tax_id-100-0_v4.tar`.
   If downloads are still denied, use `GCS_AUTH_CMD='gcloud auth print-access-token'` (plus
   `GCS_USER_PROJECT=<billing project>` if the bucket is requester-pays), or a mirror (`GCS_BASE_URL`).
5. The node type and account in `afdb.sbatch` (`es_biol`, `rtx_4090:4`, `--tmp=200G`) come from your template.
   The job asks for 7 days. `--signal=B:USR1@900` lets the workers stop claiming 15 min before the time limit.
   `fetch_foldcomp.sbatch` uses `-A es_biol` with the default partition.

## Tier design

Units are processed in work-list order: tier 1, then tier 2, then tier 3. Within a tier they run in the order
below. Every unit is a member range of one local tar, a pack of Foldcomp taxon chunks, or a pack of GCS tars.

| tier | content | structures | units | ETA, 4 nodes × 380/s |
|---|---|---|---|---|
| 1 | the 46 local AFDB v6 proteomes (`species_order.tsv`) | 555,846 | 162 | ≈ 6 min (+ start-up) |
| 2 | local Swiss-Prot v6 minus the 113,236 models whose accession is in tier 1 | 436,886 | 110 | ≈ 5 min |
| 3 | Foldcomp `afdb_uniprot_v4` minus tier 1–2 accessions, tree round-robin order | 213,731,905 | 81,431 | ≈ 39 h |

Tiers 1–2 counts come from `download_metadata.json` and the local tar indices.

**Tier 3 from Foldcomp** (`TIER3_SOURCE=foldcomp`, the default):
- **Entries.** `afdb_uniprot_v4` has 214,683,829 entries (AFDB v4, UniProt 2021_04). 951,924 of them have an
  accession already in tiers 1–2 and are dropped when the work list is built.
- **Taxids.** Foldcomp entries carry no taxonomy. `taxid` comes from, in this order:
  1. the current UniProt idmapping (column 13 of `idmapping_selected.tab.gz`; 150 M accessions);
  2. UniProt **2021_04**, parsed from its AC/OX lines, for the accessions removed from UniProt since then;
  3. the other entries of the same source tar, for accessions in neither. Column 3 of the `.lookup` numbers the
     1,015,797 GCS proteome tars the database was built from, one taxon per tar. Mapped entries agree with
     their tar's majority taxid in 99.93 % of cases.

  Measured before step 2 was added: 74.6 M entries were mapped by the current idmapping, 38.0 M were filled
  from their tar, and **101.2 M (47 %) stayed unmapped**. Step 2 is meant to close that gap. `worklist.json`
  reports the final split (`afdb_uniprot_v4_taxid_idmapping`, `_taxid_from_2021_04`, `_taxid_from_tar`,
  `_unmapped_taxid`). Entries left without a taxid get `taxid` 0 and the "unclassified" group.
- **Order.** Each taxon is split into chunks of ≤ `UNIT_STRUCTURES` entries (accession order). The chunks are
  ordered by the tree round-robin below. Consecutive chunks are then packed into units of ≤ 4,000 entries (at
  most 2,000 chunks).
- **Entry lists.** The entry list of each unit is in `fc_entries_afdb_uniprot_v4.parquet` (1.9 GB): one file,
  row groups of 100 k rows, sorted by unit, so a worker reads 1–2 row groups per unit.
- **`TIER_REPS=1`** (off by default) runs the 2.3 M Foldseek cluster representatives (`afdb_rep_v4`, fetch it with
  `FETCH_ARGS="--dbs afdb_uniprot_v4 afdb_rep_v4"`) first, as the first units of tier 3, with
  `source = foldcomp:afdb_rep_v4`. The rest of tier 3 then skips those accessions. Tier numbers therefore stay
  1–3, instead of adding a separate "tier 2b".
  - Tested at work-list level: 2,263,724 representatives in 810 units, then the remaining 211.5 M entries; the
    tier-3 total is unchanged.
  - The worker reads representatives through the same code path as `afdb_uniprot_v4`, but it was not run on
    `afdb_rep_v4` data here.

**Tier 3 = Foldcomp-decompressed v4 models.** Foldcomp stores torsion angles, so the decompressed model differs
slightly from the AFDB file. Measured on 300 local v6 models (compress → decompress → describe):

| measure | value |
|---|---|
| heavy-atom RMSD (atoms matched by residue + name) | median 0.12 Å; worst atoms 0.8–1.9 Å |
| pLDDT (kept in the B-factors) | within ±0.03 |
| pockets, all → kept | 1,404 → 1,380, and 1,097 → 1,080 |
| original pockets with a counterpart of residue Jaccard ≥ 0.5 | 60 % |
| cosine of matched fingerprints | median 0.95 (5th percentile 0.76) |
| nearest Foldcomp pocket from the same protein, in a 300-protein pool | 75 % |

Do not compare pockets of the same protein across sources. For close inspection, re-describe the original from
`https://alphafold.ebi.ac.uk/files/AF-<acc>-F1-model_v4.cif` (POCKETOME.md §6).

**Tier 3 from GCS** (`TIER3_SOURCE=gcs`): every (taxid, shard) tar of the bucket not covered by tiers 1–2.
- **Listing.** The full listing (11 min) has 2,031,605 objects. That is 1,015,808 (taxid, shard) tars over
  1,007,292 taxa and 25.95 TB, keeping the highest model version per tar (all v4, except 11 v3-only tars).
- **Size estimate.** About 214.0 M models, estimated at 120.9 kB/model.
- **Units.** Most tars are tiny (median 60 kB, one model), so consecutive tars are packed into 48,341 units of
  about 4,000 models.
- **Per-member work.** The worker streams the tars and skips `.pdb.gz` members and tier 1–2 accessions.
- This path was tested only against a local mock of the bucket (the smoke test), because real downloads were
  denied.

**Tier 1 order** (full table with taxids, counts and rationale in `species_order.tsv`): first the classic
experimental organisms, HUMAN, YEAST, ECOLI, MOUSE, RAT, DROME, CAEEL, DANRE, ARATH, SCHPO, DICDI. Then a spread
over the tree of life and global health: METJA (the only archaeon), PLAF7, TRYB2, MYCTU, STAA8, CAMJE, ORYSJ,
CANAL, SCHMA, BRUMA, NEIG1, PSEAE, LEIIN, AJECG, STRR6, HELPY, HAEIN, SOYBN, MAIZE, TRYCC, SPOS1, 9NOCA1, MYCLE,
SALTY, KLEPH, SHIDS, STRER, ONCVO, TRITR, WUCBA, DRAME, PARBA, 9EURO1, 9EURO2, 9PEZI1. The local directory has
46 proteome tars, exactly these 46, with no extras and none missing.

**Tier 3 order, tree round-robin.** NCBI `rankedlineage.dmp` (new_taxdump; merged taxids followed) gives each
leaf a lineage: superkingdom → phylum → class → order → family → genus → taxon. A leaf is a Foldcomp taxon chunk,
or a GCS tar.
- At every level, the child groups are ordered by total size (descending) and interleaved one item at a time.
  The leaves of a taxon are ordered by size, descending.
- The top level is Bacteria, Eukaryota, Archaea, Viruses (any non-cellular realm) and unclassified. Unclassified
  includes metagenomes and the unmapped accessions (`taxid` 0).
- Early units therefore cover the tree broadly. Measured for Foldcomp before the 2021_04 taxids were added:
  - the first 100 units (0.34 M entries) span 66 phyla;
  - the first 1,000 units (3.1 M) span 135 phyla;
  - the first 10,000 units (28 M) span 140 phyla.

  More taxa resolve with the 2021_04 taxids. For GCS the counts were ≈ 70 / 216 / 238 phyla.
- Accessions of tiers 1–2 are listed in `skip_accessions.txt`, each with the first tier it occurs in.

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
OUT_ROOT/worklist.parquet, worklist.tsv, worklist.json, skip_accessions.txt, tar_index/, ncbi/
OUT_ROOT/fc_entries_<db>.parquet, fc_taxa_<db>.parquet          Foldcomp tier-3 entry lists and taxon names
OUT_ROOT/foldcomp/                                               $FOLDCOMP_DIR: databases + uniprot*_taxid.parquet
OUT_ROOT/pockets/tier<T>/<unit_id:06d>.parquet                   one row per kept pocket
OUT_ROOT/structures/tier<T>/<unit_id:06d>.parquet                one row per structure
OUT_ROOT/state/{claims,done,failed}/                             claims (dirs), done / failed markers (JSON)
OUT_ROOT/logs/                                                   SLURM logs, one per node
```

**Pocket table** (full schema in POCKETOME.md §3):
- Metadata: `unit_id`, `tier`, `accession`, `fragment`, `model_version` (6 for tiers 1–2, 4 for tier 3),
  `taxid`, `organism`, and `source` (`afdb_v6_tar` | `afdb_swissprot_v6_tar` | `foldcomp:afdb_uniprot_v4` |
  `foldcomp:afdb_rep_v4` | `gcs_v4_tar`).
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

**Structure table:** `structure_stem`, `accession`, `fragment`, `model_version`, `taxid`, `organism`, `source`,
`source_file` (tar or Foldcomp database), `n_res`, `plddt_mean` / `plddt_frac_lt70` / `plddt_frac_lt50`,
`n_pockets_all` / `n_pockets_kept`, `status` (`ok` / `error` / `missing`), `error`, and the describe timings
`parse_s`, `gpu_s`, `burrow_s`, `describe_s`, `total_s`. The pLDDT columns come from `_ma_qa_metric_local` for
mmCIF and from the CA B-factors for Foldcomp PDBs. An entry that cannot be decompressed has `status = error`.

**Done marker** (`state/done/<unit_id>.json`): structures (ok / error), pockets all / kept, `dropped` per rule,
extraction counts (members seen, non-model members, skipped earlier-tier accessions, duplicates, bytes, HTTP
retries, `extract_s`), describe and wall seconds, structures/s, runner, host and SLURM ids, and a sample of
errors.

## Expected times

- **Fetch job:** the Foldcomp database is 1.10 TB. At the measured ~190 MB/s (16 ranged streams from S3) that
  is ≈ 1.6 h. Files already present with the right size are reused.
  - The idmapping extraction (`gzip -dc | cut -f1,13`) gives 150 M accessions → 0.77 GB parquet in 2.3 min.
  - UniProt 2021_04 is 151 GB at ≈ 195 MB/s (13 min), plus ≈ 75 min of parsing (single gzip stream, measured
    at ≈ 34 MB/s of input).
- **Work list:** measured here with 12 threads, about 1.5–2 min and ≈ 30 GB peak RAM for all three tiers.
  Tier 3 alone: the 214.7 M index and lookup lines are read in 24 s, the whole build takes 65 s, peak RSS 31 GB.
  The output is 81,431 units and a 1.9 GB entries file.
- **Compute:** 4 nodes × ≈ 380 structures/s ≈ 1,520/s (`docs/AFDB_COST.md`: one node with 4 GPUs × 15 workers
  and thread caps). Tier 1 ≈ 6 min, tier 2 ≈ 5 min, plus about 1 min start-up per node. Tier 3:
  213.7 M / 1,520 s⁻¹ ≈ **39 h**.
- **Not bandwidth-bound any more.** Tier 3 reads ≈ 1.1 TB from scratch over 39 h (≈ 8 MB/s).
  - Decompression measured at 274 entries/s per process. `FC_PROCS = 4` processes give ≈ 1,100/s per node,
    against ≈ 380/s needed.
  - A decompressed PDB is ≈ 210 kB, so 4,000-entry batches take ≈ 0.85 GB each in `$TMPDIR`. With the prefetch
    queue that is ≈ 10 GB per node.
  - With `TIER3_SOURCE=gcs`, tier 3 would instead need ≈ 185 MB/s of downloads (25.95 TB) to keep up.
- **Persistent runner (measured on 2 GPUs + 2 × 14 workers, 15,991 bacterial models in 4 units):** 77 s
  (≈ 208/s), vs 95 s (≈ 168/s) with one `pocketcompare describe` subprocess per 4,000-model batch. Each
  `describe` call costs ≈ 12 s of start-up. Local tar extraction reads ≈ 1,600 models/s per thread.

## Storage

Measured on the test runs:
- Kept pockets per structure: 3.7 (16 k bacterial models), 2.1 (human), 2.7 (smoke mix).
- 811 B per kept pocket on disk (fp16 fingerprint + metadata, zstd) and 54 B per structure.

| | structures | kept pockets (≈) | pocket files | index (IVF-PQ64) |
|---|---|---|---|---|
| tier 1 | 0.56 M | 1.2–2 M | ≈ 1–1.7 GB | — (use flat: ≤ 3 GB RAM) |
| tier 2 | 0.44 M | ≈ 1.5 M | ≈ 1.2 GB | — (flat) |
| tier 3 | 214 M | ≈ 0.8 B | ≈ 0.65 TB (+ 12 GB structure tables) | ≈ 75 GB RAM / file |
| inputs | `$FOLDCOMP_DIR` | | 1.10 TB database + 15 GB index/lookup + ≈ 3 GB of taxid maps; `fc_entries` 1.9 GB | |

Outputs are ≈ 0.66 TB in ≈ 245 k files (3 per unit). With the Foldcomp inputs scratch holds ≈ 1.8 TB, under the
2.5 TB / 1 M-file quota. During the fetch job the 151 GB UniProt 2021_04 tarball also exists temporarily.
`build_index.py --save-vectors` adds 768 B/pocket of fp16 vectors for exact re-ranking (0.6 TB for tier 3).
Delete `$FOLDCOMP_DIR` once tier 3 is done if space is needed.

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
- **Adding or switching tier 3 later** (as done here: tiers 1–2 first with commit 24d1c8f, then Foldcomp):
  re-run `make_worklist.py` with the default tier-1/2 options. It reproduces the tier-1/2 rows exactly (tested
  by `test_worklist_compat.sh`) and refuses to replace a work list if a finished unit would change. It moves
  failed markers of replaced units to `state/superseded/` and keeps the old list as `worklist.<time>.parquet`.
  Tier-1/2 files from that first run have no `source` column (POCKETOME.md §4).
- **Redo a finished unit** (e.g. after changing filters): delete its done marker and its two output files, then
  resubmit.
- **Testing:** `worker.py --dry-run --max-units 20` lists what would be claimed. `--max-units`, `--tiers`,
  `--unit-ids`, `--devices cuda:0,cuda:1` and `--workers-per-shard` are useful interactively.

## How the worker works

Each node runs three kinds of threads, plus a small process pool for Foldcomp.

**Extraction (`EXTRACT_THREADS` = 4).**
- **Claims.** A thread claims a unit with an atomic `mkdir state/claims/<id>` plus `claim.json` (host, pid,
  SLURM job/array ids, time).
- **Batches.** It fills node-local `$TMPDIR` batch directories of ≤ 4,000 models.
- **Local tars.** `.cif.gz` members are read with large sequential reads. Per-structure pLDDT / taxid come from
  the mmCIF (≈ 0.7 ms each).
- **Foldcomp.** The thread reads the unit's entries from `fc_entries_<db>.parquet`, sorts them by offset and hands
  them in chunks of 64 to `FC_PROCS` processes. These `os.pread` each entry from `$FOLDCOMP_DIR/<db>`, run
  `foldcomp.decompress`, write `<AF-…-model_v4>.pdb` and compute the B-factor pLDDT stats. Processes are needed
  because decompression holds the GIL.
  - **The leak.** `foldcomp.decompress` (foldcomp 1.0.0) never frees its output, about 200 kB per entry. Without
    a limit the processes reached 20–50 GB each and were OOM-killed within ~3 h on 192 GB nodes.
    Each process is therefore replaced after `FC_MAX_TASKS` = 200 chunks (≈ 12,800 entries, ≈ 2.5 GB).
  - **The timeout.** `Pool.map` never returns if a process dies mid-task, which silently stalls the extraction
    thread. Each batch therefore waits at most `FC_TIMEOUT` = 900 s. After that the unit fails (re-run with
    `--retry-failed`) and the thread moves on.
- **GCS tars.** Streamed or fetched in parallel; `.pdb.gz` members and earlier-tier accessions are skipped.

**GPU slots (one per GPU).** A slot takes the next batch. Up to 4 more batches wait in the queue, so extraction
overlaps describing.

**CPU-only nodes (`afdb_cpu.sbatch`).**
- **Same work list.** Nodes share work only through `state/claims`, so CPU and GPU arrays can run at the same time
  and be submitted or cancelled independently.
- **Same output.** `CPU_SHARDS_PER_NODE` = 4 slots each run `pocketcompare describe --device cpu --backend fast`
  (the Numba backend) through `--runner cli`. It gives the same pockets and fingerprints as the GPU path, so the
  database does not depend on the node type.
- **Not the persistent runner.** `describe_server.py` always featurises with torch, which is not the benchmarked
  CPU path.
- **Speed.** Measured at 190–385 structures/s per 64-core node on Foldcomp input, depending on the CPU
  generation and node load. A 4-GPU node does ≈ 650/s.

**Finaliser.** Filters, adds metadata (incl. `source`) and writes the two parquet files and the done marker.
Every write goes to a temporary file and is renamed into place.

**Runners.**
- `--runner persistent` (default) keeps one `describe_server.py` per GPU. It runs the same `pocketcompare.cli`
  functions as `pocketcompare describe --af-mode --backend fast --device cuda:<g> --workers 15 --batch 16`
  and writes the same files, but its GPU context and worker pool live across batches.
- `--runner cli` runs the literal `pocketcompare describe` subprocess per batch.

The smoke test runs both runners. It checks the stored fingerprints of 5 structures (2 tier-1 models, 3
decompressed Foldcomp entries) against a direct `pocketcompare describe` with the reference CPU backend
(max |Δ| 6e-5 after fp16). Thread caps (`OMP/MKL/OPENBLAS/NUMBA/NUMEXPR_NUM_THREADS=1`) are set everywhere.
`afdb.sbatch` copies the warm Numba cache to `$TMPDIR`.
