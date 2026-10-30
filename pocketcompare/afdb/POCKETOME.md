# The AFDB pocketome: a guide for analysis agents

Read this before analysing the pocketome. It says what the data are, how to load them without running out of
memory, what the numbers mean, what the method can and cannot tell you, and which mistakes are easy to make.
Everything here applies to the output of `afdb/worker.py` (directory `$OUT_ROOT`, by default
`/cluster/scratch/gmagnusson/pocketcompare_afdb`). If a number below matters for your conclusion, check it
against the files rather than trusting this document.

## 1. What the pocketome is

- **Pockets.** Every AlphaFold DB model was run through BURROW, a fast pocket detector (AF mode: residues with
  pLDDT < 50 are pruned first). A *pocket* is one merged BURROW region pocket: a set of cavity grid points
  (1 Å grid) plus the protein residues lining it.
- **Fingerprints.** Each kept pocket has a 384-number unit vector computed by `pocketcompare` (frozen method,
  `A4b:n1_linear`). The vector describes the buried core of the site (all buried grid points within 8 Å of the
  pocket's buriedness-weighted centre, "sph8"): typed cavity histograms, pairwise-distance distributions, shape
  moments and the chemistry of the lining residues, projected by a learned linear map. No sequence, fold or
  ligand information goes in.
- **Similarity** of two pockets = dot product of their fingerprints (= cosine, range −1 to 1; a pocket with itself
  = 1). It was trained and tested to rank pockets that bind similar ligands in *unrelated* proteins above other
  pairs. It is not a structural alignment and does not tell you which residues correspond.
- **Monomers only.** The AFDB contains single-chain models, so protein–protein-interface pockets are absent.
  No ligands, cofactors, metals or waters are present in AF models.

## 2. Coverage and how the run was ordered

| tier | content | structures | expected kept pockets |
|---|---|---|---|
| 1 | 46 AFDB v6 reference proteomes (human, yeast, E. coli, mouse, rat, fly, worm, zebrafish, Arabidopsis, fission yeast, Dictyostelium, then a spread of pathogens and model species; `species_order.tsv`) | 555,846 | ≈ 2.3 M |
| 2 | Swiss-Prot v6, minus accessions already in tier 1 | 436,886 | ≈ 1.8 M |
| 3 | the rest of AFDB: AFDB **v4** models decompressed from the Foldcomp database `afdb_uniprot_v4` (`source = foldcomp:afdb_uniprot_v4`), in "tree round-robin" order | 213.7 M | ≈ 0.8 B |

- **Each accession appears in one tier only**: tiers 2 and 3 skip accessions processed earlier
  (`skip_accessions.txt`).
- **Tier 3 is not the original model files.** Foldcomp stores torsion angles, not coordinates; the decompressed
  model differs slightly from the AFDB file and so do its pockets (§6, pitfall 10). Columns `source` and
  `model_version` tell you which kind of model a row comes from. (The pipeline can also read tier 3 from the
  Google Cloud bucket of original v4 files, `source = gcs_v4_tar`, but that was not the default.)
- **Tier-3 taxa.** Foldcomp entries carry no taxonomy. `taxid` comes from the current UniProt idmapping, else from
  UniProt 2021_04 (the release AFDB v4 was built from; many v4 accessions have since been removed from UniProt),
  else from the other entries of the same AFDB source tar. Entries with none of these have `taxid = 0` and
  organism "unmapped accession" and sit in an "unclassified" group of the round-robin; `worklist.json` reports
  how many (`afdb_uniprot_v4_unmapped_taxid`).
- **Tier 3 order.** Taxa are interleaved over superkingdom → phylum → class → order → family → genus, so that the
  first units cover the tree of life broadly (the first 1,000 units span ≈ 216 phyla). If the run stopped early,
  the data are a broad but **incomplete** sample: never treat "no pocket found" as "the organism has no such
  pocket" without checking which units finished.
- **Check completeness first.** `python afdb/status.py --out-root $OUT_ROOT` reports done / failed / pending units
  per tier. `state/done/<unit_id>.json` exists only for finished units; `state/failed/` lists failures.

## 3. Files

```
$OUT_ROOT/
  pockets/tier<T>/<unit_id:06d>.parquet       one row per kept pocket (metadata + fingerprint)
  structures/tier<T>/<unit_id:06d>.parquet    one row per structure (including structures with no kept pocket)
  state/done/<unit_id>.json                   per-unit counts (pockets dropped per filter, errors, timing)
  worklist.parquet                            the work units: tier, source tar(s) or Foldcomp database, taxid,
                                              organism, lineage
  fc_entries_afdb_uniprot_v4.parquet          tier-3 entries per unit (offset/length in the Foldcomp DB, accession,
                                              taxid); fc_taxa_*.parquet: taxid -> name + lineage
  skip_accessions.txt                         accession -> first tier it occurs in
  ncbi/                                       NCBI new_taxdump used for lineages (rankedlineage.dmp)
  index/                                      FAISS indices, if build_index.py was run
```

### Pocket table (`pockets/tier*/…parquet`)

| column | type | meaning |
|---|---|---|
| `pocket_id` | str | `AF-<accession>-F<fragment>-model_v<version>:m<i>`; unique |
| `unit_id`, `tier` | int | work unit and tier |
| `accession` | str | UniProt accession |
| `fragment` | int16 | AFDB fragment number (1 for almost all; > 1 only for long human proteins split into fragments) |
| `model_version` | int8 | 6 (tiers 1–2), 4 (tier 3; 3 for 11 GCS tars if tier 3 came from GCS) |
| `taxid`, `organism` | int32, str | NCBI taxon id and organism name. Tiers 1–2: from the model file. Tier 3: UniProt idmapping → UniProt 2021_04 → source tar; 0 = unknown ("unmapped accession") |
| `source` | str | where the model came from: `afdb_v6_tar` (tier 1), `afdb_swissprot_v6_tar` (tier 2), `foldcomp:afdb_uniprot_v4` (tier 3; `foldcomp:afdb_rep_v4` with TIER_REPS=1), `gcs_v4_tar` (tier 3 from GCS) |
| `merged_index`, `burrow_index`, `burrow_rank`, `members` | | BURROW bookkeeping: merged-pocket index in the model, index/rank of its best member pocket, member ranks |
| `burrow_score` | float | BURROW's pocket score (0–1, probability-like, comparable across proteins; ≥ 0.03 here) |
| `n_points`, `volume_A3` | int, float | size of the detected pocket (grid points; Å³) |
| `site_n_points`, `site_volume_A3` | int, float | size of the sph8 site that the fingerprint describes |
| `sph8_fallback` | bool | true if the sph8 set was empty and the whole pocket was described instead (rare) |
| `center_x/y/z` | float | pocket centre in the model's coordinate frame (only meaningful within one model) |
| `residues` | str | lining residues, space-separated `chain:resnum`, e.g. `A:53 A:79 A:82` (chain is always A) |
| `plddt_mean`, `plddt_min`, `plddt_frac_lt70` | float | pLDDT of the lining residues (mean ≥ 70 here) |
| `fingerprint` | `fixed_size_list<halffloat>[384]` | float16 copy of the unit-norm fingerprint (768 B; max error 6 × 10⁻⁵ vs float32) |

The Parquet schema metadata carries the method record (`pocketcompare`, incl. config hash and model weight hashes)
and the unit's filter settings (`pocketcompare_afdb`). **Only compare fingerprints made by the same method
record.**

Residue numbering: for fragment 1 the numbers are UniProt positions. For fragments > 1, check the offset in the
model file's `_struct_ref_seq` before mapping to UniProt (AFDB long-protein fragments are overlapping windows).

### Structure table (`structures/tier*/…parquet`)

`structure_stem`, `accession`, `fragment`, `model_version`, `taxid`, `organism`, `source` (as in the pocket
table), `source_file` (tar or Foldcomp database name), `n_res`, `plddt_mean`, `plddt_frac_lt70`, `plddt_frac_lt50`
(tiers 1–2: from the mmCIF `_ma_qa_metric_local`; tier 3: from the CA B-factors of the decompressed PDB, ±0.03), `n_pockets_all` (before filters), `n_pockets_kept`, `status`
(`ok` / `error` / `missing`), `error`, timings. Use it for denominators ("pockets per protein", "fraction of
proteins with a pocket") and to exclude failed structures.

## 4. Loading without running out of memory

Sizes: a fingerprint is 768 B, metadata ≈ 100–250 B per pocket. Tiers 1–2 (≈ 4 M pockets, ≈ 3–4 GB) fit in
memory. **Tier 3 (≈ 0.8 B pockets, ≈ 0.6 TB of fingerprints) does not**: work with column projections, filters,
per-file streaming, or a FAISS index.

```python
import sys, pyarrow.compute as pc, numpy as np
sys.path.insert(0, "<repo>/afdb")
from afdb_common import open_pockets, fill_source

pockets = open_pockets(OUT_ROOT)              # all tiers; schema unified across files (see the note on `source`)
meta = fill_source(pockets.to_table(columns=["pocket_id", "tier", "accession", "taxid", "burrow_score", "source"],
                                    filter=pc.field("tier") <= 2)).to_pandas()     # metadata only: cheap

t = pockets.to_table(columns=["pocket_id", "fingerprint"], filter=pc.field("taxid") == 9606)
V = np.asarray(t["fingerprint"].combine_chunks().flatten()).reshape(-1, 384).astype(np.float32)
S = V @ V[:5].T                                                         # similarities to 5 query pockets
```

`pocketcompare.fpindex.read_table(path)` returns `(metadata DataFrame, float32 vectors, method record)` for one file. DuckDB also reads the files
directly (`SELECT … FROM read_parquet('pockets/*/*.parquet', union_by_name = true)`) and is convenient for metadata
aggregation.

**The `source` column is missing from the first tier-1/2 files.** Tiers 1 and 2 were run with an earlier version
of the pipeline (commit 24d1c8f), whose pocket and structure tables have no `source` column. Tier 3 files always
have it. Derive it from the tier: tier 1 → `afdb_v6_tar`, tier 2 → `afdb_swissprot_v6_tar`; these are the only
sources those tiers have.
- `afdb_common.fill_source(table_or_df)` does that.
- `afdb_common.open_pockets(OUT_ROOT[, "structures"])` opens all files with a unified schema, so the column
  reads as null instead of disappearing.
- A plain `pyarrow.dataset.dataset(...)` takes the schema of the first file (a tier-1 file) and silently drops
  `source` everywhere. In DuckDB use `union_by_name = true` and `coalesce(source, …)`.

`build_index.py` derives `source` in `meta.parquet` the same way.

**Search.** For anything larger than a few million pockets use an index:
`python afdb/build_index.py --tiers 1,2 --kind flat -o $OUT_ROOT/index/t12_flat` (exact) or `--kind ivfpq`
(compressed, built in chunks; ≈ 72–94 B per pocket in RAM; recall@10 ≈ 0.89 alone, ≈ 0.99 with exact re-ranking
of the top 100 on the human set). Query with `pocketcompare search queries.parquet <index_dir> -k 50 -o hits.tsv`.
New query pockets: `pocketcompare describe <model.cif.gz> --af-mode -o q.parquet` (or `--ligand` / `--residues`
for a known site).

## 5. What the similarity scores mean

- **Typical values** (human AFDB, final method): median cosine of a pocket's 1st / 10th / 50th nearest neighbour
  0.82 / 0.76 / 0.72. Scores are relative: there is **no validated cutoff** that means "binds the same ligand".
  Prefer ranks, per-query z-scores, or comparison with a background (e.g. random pocket pairs of matched size).
- **Validated performance** (held-out tests, pre-registered):
  - Unrelated proteins, detected pockets (TOUGH-M1): ROC-AUC 0.70 vs 0.55 for BURROW's own descriptors.
  - Proteins released after all training data: 0.75 vs 0.67.
  - AlphaFold models score the same as crystal structures.
- **Weak spots**:
  - Proteome-wide blind search has low early precision: a true ligand-sharing partner reaches the top 100 of
    ≈ 14,000 candidate pockets only ≈ 8 % of the time.
  - Ligand chemotypes absent from training are handled worse.
  - No gain on the ProSPECCTs benchmark.
  - Pockets that bind protein–protein-interaction modulators are not recognised across families.
- **Hubs.** Some pockets are near neighbours of very many others. CSLS rescaling (subtract the mean similarity of
  each pocket's k nearest neighbours) reduced hubness skew from 1.62 to 0.55 on the human set. Use it when
  building similarity graphs, but not for retrieval benchmarks, where it lowered accuracy.

## 6. Pitfalls for evolutionary and comparative analyses

1. **Homology dominates nearest-neighbour lists.** Homologous proteins have near-identical pockets, so most top
   hits of a pocket are in its own protein family. In a demo with the precursor descriptor, 75 % of the
   non-self top-10 hits of kinase ATP-site pockets were kinase pockets. To study convergence across unrelated
   proteins, remove homologous pairs explicitly: run MMseqs2 or Foldseek on the candidate protein pairs, and
   treat "same family" and "different family" separately.
2. **Taxonomic sampling is uneven.** The AFDB over-represents bacteria and some well-sequenced clades. Many tier-3
   taxa contribute a single protein, and part of tier 3 is unclassified or metagenomic. Normalise per taxon,
   subsample evenly across clades, or weight by inverse clade size.
3. **Model versions differ.** Tiers 1–2 are v6 models, tier 3 v4 (Foldcomp-decompressed). The same accession
   never appears twice, but version and source are covariates when comparing, for example, human (v6) with other
   primates (v4).
4. **Filters shape what is present.** Pockets with BURROW score < 0.03 or mean lining pLDDT < 70 were dropped,
   and AF mode prunes pLDDT < 50 regions before detection. Disordered, flexible and low-confidence proteins,
   shallow surface pockets and the cores of predicted interfaces are therefore under-represented.
   `n_pockets_all` versus `n_pockets_kept` shows the effect per structure.
5. **Detection is incomplete.** On validation data BURROW found about 70 % of known ligand sites in AF models.
   Absence of a pocket is weak evidence of absence of a binding site.
6. **One site can be several pockets.** BURROW may split a large site (e.g. cofactor plus substrate) into two or
   three merged pockets. The sph8 site is a fixed 8 Å sphere, so it describes only the central part of large or
   elongated pockets. Group pockets of one protein by residue overlap (Jaccard ≥ 0.3–0.5) when you need sites
   rather than pockets.
7. **Fragments duplicate sites.** Long human proteins appear as several overlapping fragments, each with its own
   pockets. Deduplicate per accession by residue overlap after converting fragment numbering to UniProt
   positions.
8. **Size still matters.** The method was trained and selected to resist the pocket-size shortcut, but size and
   similarity are not independent. Report a size-only baseline (similarity of `site_volume_A3`) or stratify by
   size when claiming that two groups of pockets differ.
9. **Pocket scores are for ranking.** `burrow_score` is comparable across proteins but is not a calibrated
   probability of ligand binding.
10. **Tier 3 = Foldcomp-decompressed models.** Measured on 300 local v6 models (compress → decompress →
    describe):
    - Heavy-atom RMSD to the original: median 0.12 Å (atoms matched by residue and name; worst atoms 0.8–1.9 Å).
      pLDDT survives to ±0.03.
    - Pockets: 1,404 → 1,380 (kept after filters: 1,097 → 1,080). Only 60 % of the original pockets have a
      counterpart with residue Jaccard ≥ 0.5.
    - Matched fingerprints: cosine median 0.95 (5th percentile 0.76). For 75 % of the original pockets, the
      nearest Foldcomp pocket from the same protein in a 300-protein pool is its counterpart.

    So the Foldcomp perturbation is small next to cross-protein differences, but **do not compare pockets of the
    same protein across sources** (a stored tier-3 row against a pocket re-described from the original v4 or a
    v6 model of that protein) and expect identity. For close
    inspection of a tier-3 pocket, re-describe the original model, `https://alphafold.ebi.ac.uk/files/AF-<acc>-F1-model_v4.cif`
    (`pocketcompare describe … --af-mode`), and match pockets by residue overlap rather than by `pocket_id`.

## 7. Analyses the data support well

- **Pocket families.** Build a k-nearest-neighbour graph (FAISS, k ≈ 20–50, optionally CSLS), cluster it (e.g.
  Leiden), then annotate each cluster with its taxa (join `taxid` to `ncbi/rankedlineage.dmp`) and protein
  families.
- **Phylogenetic profiles of pocket types.** For each pocket cluster, record the presence or absence per clade.
  Compare with the profile of the host protein family to separate inherited from convergent pockets.
- **Conservation of a known site across species.** Describe the site in one protein (`pocketcompare describe
  --ligand` or `--residues`), search the index, and restrict hits to orthologues (from an external orthology
  table) or to unrelated proteins (convergence).
- **Off-target and repurposing hypotheses.** Rank pockets in other proteomes by similarity to a drug's known
  pocket; treat hits as hypotheses for docking or experiments, since early precision is low (§5).

## 8. Provenance

- Method: `pocketcompare` (github.com/zoidpuff/pocketcompare); frozen model and config hashes are in each file's
  schema metadata. The pipeline is in `afdb/` (README there). The research record, including how the method was
  validated, is in github.com/zoidpuff/pocketcompare-agents.
- Recompute any pocket's fingerprint with `pocketcompare describe <model> --af-mode` from the same AFDB model
  file. For tier 3 the "same model file" is the Foldcomp-decompressed PDB (`foldcomp.decompress` of the entry in
  `afdb_uniprot_v4`), which reproduces the stored fingerprint; the original v4 mmCIF gives a slightly different one. Fingerprints are deterministic: CPU and GPU backends give identical results, and the stored float16 copy
  differs by ≤ 6 × 10⁻⁵.
- Data: AlphaFold DB (CC BY 4.0; cite Varadi et al. and Jumper et al.); tier 3 through Foldcomp (Kim, Mirdita,
  Steinegger, *Bioinformatics* 39:btad153, 2023); UniProt for tier-3 taxids; NCBI Taxonomy for lineages.
- Scratch storage is purged after 15 days on Euler: if `$OUT_ROOT` is on scratch, check that the files you need
  still exist and copy them to permanent storage.
