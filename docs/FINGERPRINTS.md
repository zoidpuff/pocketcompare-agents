# Pocket fingerprints: handover note (BURROW / ADock)

This note covers fingerprints from `pocketcompare-final:A4b:n1_linear|raw` (`configs/final_method.yaml`, frozen).
The method and its evaluation are in `REPORT.md` and `results/final/final_report.md`.
Numbers below come from `results/tooling/describe_runtime.json` and `results/release/human_afdb_v6.json`.

## 1. What a fingerprint is

**One pocket → one 384-d float32 unit vector.** Two pockets are compared by their inner product, which ranges
from −1 to 1; higher means more similar. The fingerprint uses no sequence, no fold and no ligand. It does not
change under rigid motions of the structure. The same input always gives the same vector.

**How the vector is built.** BURROW runs on the protein, with ligands, waters, ions and cofactors removed.
1. **Pocket.** In deployment, a pocket is a *merged* BURROW region-rule pocket: sub-pockets that touch within
   1.5 Å or share ≥ 30 % of their residues are merged, and merged pockets with < 10 grid points are dropped.
2. **Site (sph8).** The described site is every buried grid point (bur10 ≥ 0.5) within 8 Å of the pocket's
   buriedness-weighted centre.
3. **Descriptors.** Two descriptors are computed on that site:
   - A1 (514 d): the typed void, i.e. point-type × buriedness histograms and pair distances;
   - env (113 d): the protein side, i.e. lining chemistry and residue-group composition from BURROW's per-point
     features.
4. **Embedding.**
   - Each block is z-scored with fixed BLiPS-train statistics and clipped at ±5.
   - Three linear heads (627 → 128, one per training seed) each produce a unit vector.
   - The three vectors are concatenated and divided by √3. The inner product is therefore the mean cosine of the
     three heads.

**The stored vector is already the complete embedding.** Do not z-score or normalise it again.
**A zero vector means "not describable"** (no buried points). The `ok` column marks it, and the index skips it.

**What to expect from a score** (human AFDB release, 116 k pockets):

| quantity | value |
|---|---|
| random pairs, different proteins: median / p99 / p99.9 | 0.11 / 0.62 / 0.77 |
| nearest neighbour of a pocket: p10 / median / p90 | 0.75 / 0.82 / 0.91 |

A score is only a ranking signal and has no calibrated meaning. On held-out TOUGH-M1 the ROC-AUC for
"binds the same ligand class" is 0.70 (`results/final/final_report.md`).

## 2. Computing fingerprints

```bash
source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache
pocketcompare describe models/ --af-mode --workers 22 -o pockets.parquet                     # CPU
pocketcompare describe models/ --af-mode --device cuda:0 --workers 22 -o pockets.parquet     # BURROW on GPU
pocketcompare describe holo.cif.gz --ligand lig.sdf -o site.parquet                          # a known site
pocketcompare describe holo.cif.gz --residues A:43,A:45,A:46 --locate burrow -o site.parquet
```

- **Use `--af-mode` for AlphaFold models.** It turns on BURROW's pLDDT pruning and fills the `plddt_*` columns.
- **Output table.** It has one row per pocket:
  - `pocket_id` (`<file stem>:m<k>`), `burrow_rank`, `burrow_score`, `members` (BURROW ranks);
  - `residues` (author numbering of the input file), `center_{x,y,z}` (Å, input frame; the sph8 centre);
  - `volume_A3`, `site_volume_A3`, `plddt_{mean,min,frac_lt70}` over the lining residues;
  - `ok` and `fingerprint`.
  - A sidecar `<out>.structures.parquet` gives status and timing per structure.
- **Python:**
  - `pocketcompare.method.describe_all(path, af_mode=True)` gives every pocket of a structure;
  - `method.describe(path, site=...)` gives one site;
  - `pocketcompare.fpindex.read_table(parquet)` returns (metadata, vectors, method record).
- **Backends.** `--backend ref` (default), `--backend fast` and `--device cuda:N` give **identical** fingerprints:
  max |Δ| = 0 on 2,000 AF models.

**Runtime** (AFDB human models, 5.7 pockets per model; shared 128-core node with 2 × RTX 4090):

| | ref CPU | fast CPU (Numba) | GPU (1 × RTX 4090) |
|---|---|---|---|
| one structure, 1 core: median / mean | 0.42 / 0.58 s | 0.21 / 0.30 s | 0.13 / 0.21 s |
| 22 worker processes: structures/s | 34 | 55 | 56 |

- **Descriptor and embedding** cost ≈ 40 ms per structure (≈ 7 ms per pocket). The rest is parsing and BURROW.
- **The GPU path is CPU-bound** at 22 workers: the GPU is busy only about 10 ms per structure. Adding CPU
  workers, or running one `describe` per GPU on separate shards, scales it further.
- **One-off costs.** Imports take about 1 s per process. The first Numba compilation ever takes about 15 s and
  is cached in `NUMBA_CACHE_DIR`.

## 3. Comparing and searching

```bash
pocketcompare compare site.parquet pockets.parquet --top 5 -o pairs.tsv --matrix S.npy      # or two structures
pocketcompare index pockets.parquet -o idx/ --kind ivfpq      # OPQ64 + IVF + PQ64; or --kind flat (exact)
pocketcompare search site.parquet idx/ -k 10 --rerank 100 -o hits.parquet [--exclude-self]
```

`similarity(a, b) = a · b`. The vectors work directly with FAISS `IndexFlatIP`.

**Search on the human release** (116,246 pockets):

| index | storage per pocket | 1 query, 1 CPU thread | recall@10 vs exact |
|---|---|---|---|
| exact flat | 1,536 B | 7.3 ms | 1 |
| OPQ64 + IVF1024 + PQ64, nprobe 64 | 94 B | 0.63 ms | 0.886 |
| same + exact re-rank of the top-100 (fp16 vectors) | 94 + 768 B | 0.78 ms | **0.987** |

- **GPU all-vs-all:** the exact top-50 for all 116 k pockets takes 0.4 s on one GPU.
- **AFDB scale** (≈ 1 × 10⁹ pockets):
  - fp16 vectors need ≈ 0.8 TB, and PQ codes plus ids ≈ 0.1 TB;
  - nlist must grow to 2¹⁶–2²⁰. Latency at that scale has **not** been measured.

## 4. Release: human AFDB v6

**Location:** `data/processed/release/human_afdb_v6/`.
- **`fingerprints.parquet`:** 116,246 pockets in 19,084 UniProt entries. Residues use UniProt numbering, with
  fragments mapped.
- **Indices:** `index_flat/` and `index_opq_ivfpq/`.
- **Details:** see its `README.md`.

## 5. Known limitations

- **The site description is ligand-free and fixed-size (sph8).**
  - The described site is always the buried grid points within 8 Å of the pocket's buried centre. It is not the
    pocket's full shape, and not a ligand's shape.
  - Large or elongated pockets, such as long channels or multi-site clefts, are described only around their
    centre.
  - Two sites < 8 Å apart share most of their description.
  - A ligand's size is deliberately not encoded.
  - For a known sub-site, pass `--ligand` or `--residues`.
- **L mode and D mode differ.**
  - An L-mode vector is located by a ligand's 4 Å shell (`--ligand`).
  - A D-mode vector is located by a BURROW pocket. This covers `describe_all` and `--locate burrow`.
  - Both are described by sph8, but around different centres. The L and D vectors of the same site have median
    cosine 0.87 on BLiPS-val and 0.86 on TOUGH-M1-dev. The 10th percentile is 0.54–0.65, which is about the 99th
    percentile of random pairs.
  - Compare like with like where possible. Database pockets are always D mode; query with `--locate burrow` if
    you start from a ligand.
  - `--locate burrow` reproduces the evaluated D vectors exactly (`tests/test_method_eval_consistency.py`).
  - D mode inherits BURROW's detection recall. In the blind AF dry run (BLiPS-val), 61 % of known ligand sites
    had a matching pocket (`reports/blind_and_ppil.md`).
- **Blind retrieval is weak.** Retrieving a ligand-sharing partner among all AF pockets had hit@10 ≈ 0.16 when
  both sites were detected (BLiPS-val dry run).
  - That run used the predecessor N1 descriptor. It has not been re-measured with the final head.
  - Use the fingerprint to rank or prefilter candidates for docking, not to decide.
- **PPI pockets.**
  - An interface pocket exists only if the complex is passed in, as a multi-chain file. AFDB monomers have none.
  - On PPIPS-test, ortholog interface retrieval reaches MRR 0.68 (N1: 0.65). A sequence baseline (ESM-2)
    reaches 0.95, because orthologous interfaces are sequence-homologous.
  - The head was selected on ligand sites; PPI pockets were only part of its training data. On PPIPS-val the
    head lowered MRR relative to N1 (0.72 vs 0.79).
- **Cofactors, ions and waters are stripped.**
  - BURROW featurises the apo protein, so a heme, NAD, Fe–S or metal site is described as the empty cavity
    including the cofactor volume.
  - A cofactor-dependent ligand site is therefore not distinguished from its apo form. A holo PDB pocket and the
    AF model of the same protein can differ there.
  - Docking with the cofactor needs it added back.
  - Metal-binding positions appear only as BURROW metal-candidate points. Merged pockets < 10 points, e.g.
    isolated metal sites, are dropped.
- **AlphaFold specifics.**
  - pLDDT pruning (`--af-mode`) removes low-confidence regions before BURROW.
  - Pockets with lining mean pLDDT < 70 are less reliable. They are 5.6 % of the release, and 33 % of pockets
    have at least one lining residue below 70. Filter on `plddt_mean` / `plddt_min`.
  - The z-statistics come from holo PDB pockets.
- **Hubness.** In the release's top-10 graph, in-degree skewness is 1.62 and the maximum in-degree is 93.
  - Hubs are pockets that are close to many others: their median mean-top-10 similarity r is 0.92, against 0.78
    overall.
  - CSLS with database radii (`index_flat/csls_r_db.npy`, `s − (r_a + r_b)/2`) cuts skewness to 0.55 and keeps
    73 % of the raw top-10.
  - The method's score stays raw, because CSLS did not improve the held-out TOUGH-M1 evaluation.
- **Unit differences from the evaluation.** `describe_all` describes the *merged* pocket; the evaluation's D mode
  described the best sub-pocket at a known site. The two units have the same sph8 centre whenever the merged
  pocket has a single member. `unit="member"` gives sub-pockets.
- **One proteome pocket is missing.** The proteome pipeline dropped the one pocket whose sph8 set was empty. The
  API describes such a pocket by its own points instead.
