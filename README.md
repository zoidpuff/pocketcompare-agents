# pocketcompare

**Fast, ligand-free fingerprints for protein binding pockets.** `pocketcompare` turns every pocket of a protein
structure (a PDB entry, an AlphaFold model or a predicted complex) into a 384-dimensional unit vector. Two pockets
are compared with one dot product, so a pocket can be searched against millions of others with
[FAISS](https://github.com/facebookresearch/faiss). The fingerprint uses neither sequence nor fold. It describes the
cavity and the protein environment around it, and it does not depend on which ligand (if any) is bound.

Pockets come from [BURROW](https://github.com/zoidpuff/burrow) **[set the final URL]**, a fast pocket detector that
also runs on AlphaFold models. Each pocket is described by a typed volumetric fingerprint of its buried core (A1:
pharmacophore-typed cavity histograms, pair-distance distributions and shape moments) plus a block of
protein-environment features (env). A small linear head trained contrastively maps this 627-d descriptor to the
final 384-d vector. Describing a pocket takes a few milliseconds once BURROW has run (0.1–0.4 s per structure). The
method is frozen: the code here reproduces the evaluated fingerprints exactly (see [Reproducibility](#reproducibility)).

- [Install](#install) · [Quickstart](#quickstart) · [What a fingerprint is](#what-a-fingerprint-is) ·
  [Runtime](#runtime) · [Validated performance](#validated-performance) · [Limitations](#limitations) ·
  [Retraining the head](#retraining-the-head) · [Citing](#citing) · [Acknowledgements and references](#acknowledgements-and-references)
- Technical description with every parameter: [docs/METHOD.md](docs/METHOD.md). Result tables:
  [docs/RESULTS.md](docs/RESULTS.md). Cost of running it on the whole AlphaFold DB: [docs/AFDB_COST.md](docs/AFDB_COST.md).

## Install

Requirements: Python ≥ 3.11 (tested with 3.12.3), Linux or macOS. Dependencies are pinned to the versions the method
was developed and evaluated with (numpy 2.5.4, scipy 1.18.1, pandas 3.1.0, pyarrow 26.0.0, pyyaml 6.0.3; BURROW pins
numba 0.68.0, gemmi 0.7.5, lightgbm 4.7.0).

BURROW (`burrow-pockets`, import name `pocketdetect`, MIT) is not on PyPI, so install it first:

```bash
uv venv --python 3.12 && source .venv/bin/activate          # or: python -m venv .venv
uv pip install "git+https://github.com/zoidpuff/burrow"     # [set the final URL]; or a local clone: uv pip install /path/to/burrow
uv pip install "pocketcompare[search] @ git+https://github.com/[set the final URL]/pocketcompare"
# from a clone of this repository instead:
#   uv pip install -e ".[search,test]"   &&   pytest
```

(`pip install ...` works the same way.) Extras: `search` = FAISS (`faiss-cpu`) for `pocketcompare index` / `search`;
`gpu` = PyTorch + Triton for BURROW's GPU featurisation (`--device cuda:0`); `train` = PyTorch for
`scripts/train_head.py`; `test` = pytest.

The frozen method files (`configs/final_method.yaml`, `models/`) are installed with the package and verified by
sha256 every time the method is loaded. The BURROW model the method was evaluated with
(`models/burrow/burrow_all_default_s0.json`, from BURROW 1.0.0, MIT) is shipped here as well, so the fingerprint does
not depend on where BURROW keeps its models.

## Quickstart

The example structures are in [`examples/`](examples/): the progesterone receptor ligand-binding domain crystal
structure 1A28 (chain A, ligand removed) with its progesterone ligand as a separate file, and the AlphaFold models of
the progesterone receptor (P06401) and of carbonic anhydrase 2 (P00918). The full walk-throughs are
`bash examples/quickstart.sh` and `python examples/quickstart.py` (about 5 s after the one-off Numba compilation).

### Command line

```bash
# a ligand-defined site of a crystal structure (one fingerprint)
pocketcompare describe examples/pdb/1a28_A.pdb --ligand examples/pdb/1a28_STR.pdb -o site.parquet
# every pocket of an AlphaFold model (--af-mode: BURROW's pLDDT-aware mode; use it for all AlphaFold models)
pocketcompare describe examples/afdb/AF-P06401-F1-model_v6.cif.gz --af-mode -o pr_af.parquet
# compare (top-3 targets per query; --matrix S.npy writes the full matrix)
pocketcompare compare site.parquet pr_af.parquet --top 3
#    query_id  rank                target_id  score
# 1a28_A:site     1 AF-P06401-F1-model_v6:m2 0.9863     <- the steroid pocket of the AlphaFold model
# 1a28_A:site     2 AF-P06401-F1-model_v6:m5 0.2835
# a folder of structures -> one table; then a FAISS index and a search
pocketcompare describe examples/afdb/ --af-mode --workers 8 -o afdb.parquet     # --device cuda:0 for BURROW on a GPU
pocketcompare index afdb.parquet -o afdb_index/                  # exact; --kind ivfpq for OPQ + IVF-PQ (millions)
pocketcompare search site.parquet afdb_index/ -k 10 -o hits.tsv
```

Other site definitions: `--residues A:718,A:721,A:725` (residue list), and `--locate burrow` to describe the BURROW
pocket at the given ligand/residues instead of the ligand/residue shell (this is how database pockets are described,
so it compares like with like). `--n1` also stores the raw 627-d descriptor (for [retraining](#retraining-the-head)).
`compare` and `search` also accept a structure file instead of a table.

`describe` writes one row per pocket: `pocket_id` (`<file stem>:m<k>`), `burrow_rank`, `burrow_score`, `members`
(BURROW sub-pocket ranks), `residues` (author numbering), `center_{x,y,z}` (the described site's centre, Å),
`volume_A3`, `site_volume_A3`, `plddt_{mean,min,frac_lt70}` over the lining residues (with `--af-mode`), `ok`, and
the 384-d `fingerprint`; `<out>.structures.parquet` has the status and timings of every structure. Read a table with
`pocketcompare.fpindex.read_table(path)` → (metadata DataFrame, (n, 384) float32 array, method record).

### Python

```python
from pocketcompare import method

site = method.describe("examples/pdb/1a28_A.pdb", site="examples/pdb/1a28_STR.pdb")    # (1, 384)
#   site= also accepts (n, 3) ligand heavy-atom coordinates or a residue list ["A:718", "A:725", ...];
#   locate="burrow" describes the BURROW pocket at the site
V, info = method.describe_all("examples/afdb/AF-P06401-F1-model_v6.cif.gz", af_mode=True)  # (7, 384) + table
S = method.similarity(site, V)         # (1, 7) cosines (= inner products); higher = more similar
print(info.assign(score=S[0]).sort_values("score", ascending=False)[["burrow_rank", "score", "residues"]].head(3))

import faiss                            # pip install pocketcompare[search]
index = faiss.IndexFlatIP(384)          # unit vectors: inner product = cosine; no further normalisation
index.add(V[info.ok.to_numpy()])
D, I = index.search(site, 5)
```

`describe` / `describe_all` accept a file path (PDB/mmCIF, `.gz` allowed), a loaded BURROW `Structure` or a
pre-computed `pockets.Featurized`; `chains=[...]` restricts the chains (complexes are passed as ordinary multi-chain
files). The first call in a process imports BURROW and compiles its Numba kernels (~15 s the first time ever; cached).

## What a fingerprint is

- **One pocket → one 384-d float32 unit vector.** The score of two pockets is their inner product (−1 to 1; higher =
  more similar). The vectors work directly with FAISS `IndexFlatIP` and IVF-PQ indices; do not z-score or
  re-normalise them. A zero vector means "not describable" (no buried grid points; `ok = False`).
- **Which pockets.** `describe_all` (and `pocketcompare describe` without a site) describes BURROW's region-rule
  pockets after merging touching sub-pockets (any points ≤ 1.5 Å apart or ≥ 30 % shared residues), keeping merged
  pockets with ≥ 10 grid points, with no score cutoff (store `burrow_score` and filter at search time if needed).
- **What is described.** Not the whole pocket and not a ligand's shape: the *sph8 site*, i.e. all buried BURROW grid
  points (buriedness bur10 ≥ 0.5) within 8 Å of the pocket's buriedness-weighted centre. This makes ligand-defined and
  detected pockets comparable and removes the ligand-size imprint (see [Validated performance](#validated-performance)).
- **How.** sph8 site → A1 typed volumetric fingerprint (514 d) + env block (113 d) = N1 (627 d) → per-part z-score
  with fixed statistics, clip ±5 → three linear heads 627 → 128 (training seeds 0, 1, 2), each L2-normalised →
  concatenated and divided by √3. The inner product is therefore the mean cosine of the three heads.
- **Properties.** Invariant to rotations/translations of the input (BURROW works in a canonical frame), deterministic,
  independent of atom/point order; BURROW's reference, fast-CPU and GPU backends give identical fingerprints.
- **What to expect from a score** (116 k human AlphaFold pockets): random pairs of different proteins have median
  0.11, 99th percentile 0.62, 99.9th 0.77; a pocket's nearest neighbour has median 0.82. Scores are a ranking signal,
  not a calibrated probability.

## Runtime

Measured with the frozen method on AlphaFold models (BURROW default preset, AF mode). Per-structure latency and the
human proteome run were measured on a shared node with RTX 4090 GPUs; full-node throughput on a 64-core node with
4 × RTX 4090 (shared with other users). Sources: research `REPORT.md` §7, `docs/FINGERPRINTS.md`,
[docs/AFDB_COST.md](docs/AFDB_COST.md).

| item | value |
|---|---|
| one structure end to end, 1 core (human AFDB, 5.7 pockets/model) | median 0.42 s (`--backend ref`), 0.21 s (`--backend fast`), 0.13 s (`--device cuda:0`) |
| descriptor + embedding per pocket, after BURROW | median 3.5 ms (ligand-defined site 6.1 ms); the head itself 64 µs |
| throughput, one 64-core node | 380 structures/s with 4 GPUs (4 × 15 workers); 234 structures/s CPU only |
| human AFDB v6 (23,586 models → 116,246 pockets) | 178 s on 2 × RTX 4090 + 22 CPU workers |
| pair score | 0.1–0.7 µs batched against 10⁶ vectors |
| storage per pocket | 1,536 B float32; 768 B fp16; 94 B as OPQ64 + IVF-PQ64 code |
| search, 116 k pockets, 1 CPU thread | exact 7.3 ms/query; OPQ-IVF-PQ (nprobe 64) + exact re-rank of the top-100: 0.77 ms/query, recall@10 0.987 |
| whole AFDB (200 M structures, extrapolated) | ≈ 6 days on one such node; ≈ 8,800 CPU core-h + 300–550 GPU-h |

## Validated performance

The method was frozen before a single evaluation on held-out test sets (pre-registered claims, leakage-controlled
splits; homologues of test proteins excluded from training and from BURROW's training data). Full tables:
[docs/RESULTS.md](docs/RESULTS.md). "B1" = BURROW's own 45 size-free pocket descriptors, the natural baseline.

| test | pockets | pocketcompare | baseline | Δ [95 % CI] | verdict |
|---|---|---|---|---|---|
| TOUGH-M1-test (fold-unrelated pairs sharing a ligand class), BURROW-detected pockets | 21,410 pairs | ROC-AUC 0.699 | B1 0.546 | **+0.154** [+0.050, +0.289], Holm p 0.024 | confirmatory, robust |
| temporal replication: 987 ligand sites in PDB entries released after all training data, detected pockets | 6,171 pairs | ROC-AUC 0.752 | B1 0.671 | **+0.081** [+0.028, +0.132], Holm p 0.003 | replicated |
| TOUGH-M1-test, ligand-shell pockets | 24,337 pairs | 0.698 | B1 0.568 / ESM-2 0.568 | +0.129 / +0.130, Holm p 0.0495 | borderline, not robust to Monte-Carlo error |
| ProSPECCTs P5.2 + P6.2 + P7 (macro) | 66,312 pairs | 0.740 | B1 0.718 | +0.022 [−0.064, +0.113], p 0.27 | **not better** |
| BLiPS-test, AlphaFold models vs holo structures (detected pockets) | 3,606 sites | AF 0.723, holo 0.728 | — | paired holo − AF within ±0.03 | no AlphaFold penalty |

Caveats you should know before using the numbers:
- **Ligand-defined benchmarks leak ligand size.** A 4 Å ligand shell inherits the ligand's size, and positives in
  TOUGH-M1 share ligands of nearly the same size: the ligand heavy-atom count alone scores ROC-AUC 0.95 on
  TOUGH-M1-test and the shell volume alone 0.80, above every similarity method. Ligand-shell numbers (ours and
  published) therefore partly measure ligand size; we report detected-pocket and size-stratified results. On fresh
  data the gain over B1 is a detected-pocket gain (ligand-shell Δ only +0.014, CI includes 0).
- **ProSPECCTs: no significant gain**, and FINAL is weaker than BURROW's descriptors on BLiPS pairs with unseen
  ligand chemotypes (0.685 vs 0.770).
- **Protein–protein interface pockets: limited.** Interface-pocket retrieval across orthologues reaches MRR 0.68,
  where a sequence-embedding baseline (ESM-2) reaches 0.95; the fingerprint does not recognise "PPI-modulator
  pocket-ness" across families (exploratory test negative). There is no ligand-grounded PPI test.
- **Blind retrieval is hard.** Searching a ligand site's partner among all ~14 k pockets of 2,295 AlphaFold models:
  ROC-AUC 0.72 when both sites are detected, but hit@100 only 0.078; BURROW detected 70 % of the known sites. Use the fingerprint to rank and
  prefilter (e.g. for docking), not to decide.
- **Not comparable with published full-set numbers.** Leakage control removed 76 % of TOUGH-M1, and our pockets are
  BURROW grid points; against the published methods' shipped scores on our partition, pocketcompare is level with
  G-LoSA/SiteEngine on raw ROC-AUC and ahead after size stratification (no paired CI).

## Limitations

- **The described site is fixed-size (sph8).** Large or elongated pockets (channels, multi-site clefts) are described
  only around their buried centre; two sites < 8 Å apart share most of their description; a ligand's size is
  deliberately not encoded. For a known sub-site pass `--ligand` or `--residues`.
- **Ligand-shell (`--ligand`) and detected-pocket vectors differ.** They are described by sph8 around different
  centres (median cosine 0.87 for the same site; 10th percentile 0.54–0.65). Database pockets are detected pockets,
  so query with `--locate burrow` when you start from a ligand.
- **Detection is inherited from BURROW.** A pocket BURROW does not find has no fingerprint.
- **Cofactors, metals, waters and ligands are stripped** before BURROW runs: a heme or NAD site is described as the
  empty cavity, and isolated metal sites (< 10 grid points) are dropped.
- **AlphaFold models.** Use `--af-mode`. Pockets lined by low-confidence residues (`plddt_mean` < 70; 5.6 % of the
  human release) are less reliable; filter on the `plddt_*` columns.
- **Interface pockets** exist only if the complex is passed in as a multi-chain file.
- **Hubness.** Some pockets are close to many others (top-10 in-degree skewness 1.6 on the human proteome). CSLS
  (`s − (r_a + r_b)/2`, `pocketcompare.similarity.csls_r`) reduces it but did not improve accuracy, so the score is raw.
- **Training data.** The head was trained on BioLiP ligand-sharing pairs, same-site pairs and AlphaFold-dimer
  interface pairs (no test proteins); chemotypes outside its training data are a known weak spot.

## Retraining the head

The descriptor (N1) is fixed; the small head can be retrained on your own pairs, e.g. for a protein family or a
different notion of similarity:

```bash
pocketcompare describe my_structures/ --n1 -o pockets.parquet                       # N1 descriptors
python scripts/train_head.py --pockets pockets.parquet --pairs pairs.tsv --out my_head/ --device cuda:0
python -c "from pocketcompare.method import Method; m = Method('my_head/method.yaml')"   # then m.describe_all(...)
```

`pairs.tsv` has columns `pocket_a`, `pocket_b`, `label` (1/0) and optionally `group_a`, `group_b` (homology groups:
never used as negatives of each other; the early-stopping hold-out is whole groups) and `source` (positive sources
mixed with `--source-weights`). The script ports the published recipe (InfoNCE + BCE, 3 seeds, published
hyperparameters as defaults); its docstring documents the format, and `scripts/build_pair_table_example.py` writes a
tiny example from the example structures. The published head's training data is described in
[docs/METHOD.md](docs/METHOD.md#9-training-the-published-head).

## Reproducibility

- `pytest` runs 41 tests: a **golden test** (fingerprints of the example structures computed with the research code
  of the frozen method, `tests/data/golden.npz`, must be reproduced to ≤ 1e-6; this package reproduces them
  bit-identically), rigid-motion invariance, determinism, identity, the CLI, identical backends (GPU if available)
  and an end-to-end retraining smoke test (needs PyTorch).
- A human AFDB v6 release of 116,246 fingerprints was built with the research code. Re-describing 20 random models
  of it with this package (reference, fast-CPU and GPU backends) reproduced all 91 released pockets with
  max |Δ| = 1.1e-7.
- `configs/final_method.yaml` pins every model file by sha256 (`models/SHA256SUMS`); the method name
  `pocketcompare-final:A4b:n1_linear|raw` is stored in every fingerprint table, and tables of different methods are
  never mixed.

## Citing

If you use pocketcompare, please cite: **[citation to be added: authors, title, venue, year, DOI]** and BURROW
**[BURROW citation to be added]**. See [`CITATION.cff`](CITATION.cff).

## Acknowledgements and references

pocketcompare builds on ideas and tools from the following work. Identifiers are those of the project's literature
review (pocket methods, benchmarks) and of the Crossref/arXiv-checked reference list of the project briefing
(standard methods); the one entry marked † has no checked identifier yet.
- **BURROW** pocket detection (MIT): https://github.com/zoidpuff/burrow **[set the final URL]**. The pinned BURROW model
  and the example files 1a28_A.pdb and AF-P00918-F1-model_v6.cif.gz come from the BURROW release.
- **VolSite/Shaper** pharmacophoric cavity typing: Desaphy J et al. *J Chem Inf Model* (2012). doi:10.1021/ci300184x
- Alignment-free pocket fingerprints and distance histograms: **FuzCav**, Weill N, Rognan D. *J Chem Inf Model*
  (2010). doi:10.1021/ci900349y · **PocketMatch**, Yeturu K, Chandra N. *BMC Bioinformatics* 9:543 (2008).
  doi:10.1186/1471-2105-9-543 · **RAPMAD**, Krotzky T et al. *J Chem Inf Model* (2015). doi:10.1021/ci5005898 ·
  shape distributions, Osada R, Funkhouser T, Chazelle B, Dobkin D. *ACM Trans Graph* (2002) †
- **USR / USRCAT** moment descriptors: Ballester PJ, Richards WG. *J Comput Chem* 28:1711 (2007).
  doi:10.1002/jcc.20681 · Schreyer AM, Blundell T. *J Cheminform* 4:27 (2012). doi:10.1186/1758-2946-4-27
- Contrastive learning with **InfoNCE**: van den Oord A, Li Y, Vinyals O. Representation learning with contrastive
  predictive coding. arXiv:1807.03748 (2018)
- **FAISS** and quantisation: Johnson J, Douze M, Jégou H. Billion-scale similarity search with GPUs. *IEEE Trans Big
  Data* 7:535 (2021). doi:10.1109/TBDATA.2019.2921572 · Jégou H, Douze M, Schmid C. Product quantization for nearest
  neighbor search. *IEEE TPAMI* 33:117 (2011). doi:10.1109/TPAMI.2010.57 · Ge T, He K, Ke Q, Sun J. Optimized
  product quantization. *IEEE TPAMI* 36:744 (2014). doi:10.1109/TPAMI.2013.240 · **CSLS** hub correction:
  Conneau A, Lample G, Ranzato M, Denoyer L, Jégou H. Word translation without parallel data. ICLR 2018.
  arXiv:1710.04087
- Baselines: **ESM-2**, Lin Z et al. *Science* 379:1123 (2023). doi:10.1126/science.ade2574 · **EPoCS**, Oruç T et al.
  *Bioinformatics* (2025). doi:10.1093/bioinformatics/btaf284
- Training data and benchmarks: **BioLiP2**, Zhang C, Zhang X, Freddolino PL, Zhang Y. *Nucleic Acids Res* 52:D404
  (2024). doi:10.1093/nar/gkad630 · **TOUGH-M1**, Govindaraj RG, Brylinski M. *BMC Bioinformatics* 19:91 (2018).
  doi:10.1186/s12859-018-2109-2 · **ProSPECCTs**, Ehrt C, Brinkjost T, Koch O. *PLoS Comput Biol* 14:e1006483 (2018).
  doi:10.1371/journal.pcbi.1006483 · **AlphaFold DB**, Varadi M et al. *Nucleic Acids Res* (2024).
  doi:10.1093/nar/gkad1011

## License

Code and model files: MIT ([LICENSE](LICENSE)). Example data: 1A28 from the wwPDB (CC0 1.0); AlphaFold DB models
AF-P00918-F1 and AF-P06401-F1 (CC BY 4.0; AlphaFold DB, EMBL-EBI and Google DeepMind); see [examples/README.md](examples/README.md).
The shipped BURROW model is MIT (© 2026 BURROW authors; [models/burrow/NOTICE](models/burrow/NOTICE)).
