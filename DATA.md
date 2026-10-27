# DATA — every dataset used (source, version, checksum, license)

Raw data lives in `data/raw/` (git-ignored); fetch scripts in `scripts/data/`. Restricted data is never committed.

| dataset | source URL | version / date fetched | sha256 (archive) | license | fetch script | notes |
|---|---|---|---|---|---|---|
| AFDB (local copy) | /cluster/work/beltrao/shared/alphafold/v6 | v6 | n/a (mount) | CC-BY-4.0 | — | proteome tarballs |
| PDB (local copy) | /cluster/scratch/jjaenes/pdb | mirror | n/a (mount) | CC0 | — | mmCIF.gz, 2-char dirs |
| AFDB predicted dimers | /cluster/project/beltrao/gmagnus/dimers | AFDB complexes v1 | per-file in manifests | CC-BY-4.0 | — | human/yeast/ecoli homo+hetero |
| ProSPECCTs (Ehrt et al. 2018) | http://www.ewit.ccb.tu-dortmund.de/ag-koch/prospeccts/ (POST form; old www.ccb… URL is 404) | 2026-10-27 (files dated 2018) | 7 tarballs, full sha256 in data/raw/prospeccts/MANIFEST.json; e.g. decoy.tar.gz 0f7d1221c9b95d97…, review_structures.tar.gz aa2fae208212c949… | TU Dortmund terms of use (license_en.pdf): free, internal use only, **no redistribution**, cite paper — never commit raw or per-structure derived files | scripts/data/fetch_prospeccts.py | 10 subsets P1–P7; counts match paper Table 2 exactly |
| TOUGH-M1 (Govindaraj & Brylinski 2018) | Dataverse doi:10.7910/DVN/L7H7JJ (TOUGH-M1_dataset.tar.gz) + OSF https://osf.io/6ngbs/ (lists, baseline scores) | Dataverse v3 (2017-06-26); fetched 2026-10-27 | TOUGH-M1_dataset.tar.gz d9c7a872ea3d4860… (md5 matches Dataverse); lists/scores sha256 = OSF API values, in MANIFEST.json | tarball CC0 1.0 (Dataverse); OSF lists: unstated | scripts/data/fetch_tough_m1.py | 7524 pockets, 505,116 pos / 556,810 neg — match paper; APoc/G-LoSA/SiteEngine scores fetched as baselines |
| Vertex set (Chen et al. 2016) | ACS SI ci6b00118_si_002.zip via figshare doi:10.1021/acs.jcim.6b00118.s002 (https://ndownloader.figshare.com/files/5922126) | figshare v1 (2016-08-25); fetched 2026-10-27 | 37cb4a392b953a9c… (md5 ff40a156… matches figshare) | CC BY-NC 4.0 (figshare) | scripts/data/fetch_vertex.py | pair list only; structures from local PDB mirror (5,841/6,029 present on 2026-10-27 19:05, while the mirror was still syncing). DeeplyTough dt_vertex.zip (Zenodo 3687317, CC-BY-4.0, sha256 51b94a49…) inspected then deleted (no pair list) |
| TOUGH-C1 (Pu et al. 2019, DeepDrug3D) | OSF https://osf.io/enz69/ | fetched 2026-10-27 | per-file sha256 = OSF API values, in data/raw/tough_c1/MANIFEST.json | unstated (no OSF license) | scripts/data/fetch_tough_c1.py | classification set (nucleotide/heme/steroid/control), no pairs; pockets table only |
| KLIFS metadata | https://klifs.net/api (kinase_information, structures_list) | live API snapshot 2026-10-27 | kinase_information.json e9718d7342f8a50b…, structures_list.json 92f4aa708ed6642e… | unstated (none found on klifs.net; cite Kanev et al. 2021) | scripts/data/fetch_klifs.py | 14,917 structures / 7,382 PDB / 371 kinases; 85-residue pocket strings only, no residue numbers |
| LIGYSIS (Utgés & Barton) | Zenodo 10.5281/zenodo.14645504 | not fetched | — | CC-BY-4.0 | — | site-prediction reference set, no similarity pairs; distributed only as Python pickles (unsafe to unpickle untrusted data) |
| PoSSuM (Ito et al.) | https://possum.cbrc.pj.aist.go.jp/PoSSuM/ | not fetched (site release Jul-2022) | — | unstated | — | no bulk download found; per-query result downloads only |
| Pasteur PPI pocketome (Moine-Franel et al., Sci Data 2024) | Zenodo 10.5281/zenodo.10805580 (CDPPILBP.tar.gz + README + 2 TMAP html) | Zenodo record as of 2026-10-27 (data dated 2023-03-17, "part8") | CDPPILBP.tar.gz 985ab8d34ddceeeb… (11.09 GB; md5 a2ee28e5… matches Zenodo); all in data/raw/ppi_pocketome/MANIFEST.json | CC-BY-4.0 | scripts/data/fetch_ppi_pocketome.py | selective extraction (1.0 GB: CSVs, ligand SDF/mol2, labelled cavity mol2, ligand-contact lists; no structures, PDB mirror used); 4,972 liganded PL cavities (PLOC/PLONC/PLA), 18,266 HD cavities; PSI pair distances NOT in the archive (API kNN list only) -> B6 re-implemented from the 108 descriptors; 300 API distance records kept in api/distance_sample.json for the check |
| iPPI-DB cavity summary (feasibility only) | https://ippidb.pasteur.fr/api/summary/ | live API 2026-10-27; partial (10/117 pages, server 503s) | per-page JSON in data/raw/ippidb/pages/ (no combined file yet) | see ippidb.pasteur.fr (unstated in API) | scripts/ppi/07_ippidb_feasibility.py | used only for overlap counts in reports/ppi_dimers.md |

## Tools (binaries)
| tool | source | version (commit) | sha256 (archive) | license |
|---|---|---|---|---|
| MMseqs2 | github.com/soedinglab/MMseqs2 releases/latest mmseqs-linux-avx2.tar.gz (2026-10-27) | 8cc5ce367b5638c4306c2d7cfc652dd099a4643f | bd9b0234da5949ad528d5b5f9ea4cda9c1e23dce14b46c0791d4d919a76e61ce | MIT |
| Foldseek | mmseqs.com/foldseek/foldseek-linux-avx2.tar.gz (2026-10-27) | 463739e0014a1549a527de589102cde98f802f37 | f886374e29ebbf03849cd9c4c8929be00904856dd271627d8c3043607e2af95a | GPL-3.0 |

## External baselines
| tool | source | version (commit) | licence | sha256 | notes |
|---|---|---|---|---|---|
| EPoCS (B5) | github.com/tugceoruc/epocs (cloned 2026-10-27 to `envs/epocs_src`) | bc9e15c89ef2078d8559b0f34a4d35bde40a44bb (2025-08-11) | Apache-2.0 | n/a (git) | separate venv `envs/epocs` (py3.10, torch 2.6+cu124, fair-esm 2.0.0, biopandas 0.5.2, pymol-open-source 3.2.0a0 from PyPI; libX11/GL from conda-forge via micromamba in `envs/x11`, appended to LD_LIBRARY_PATH — do NOT overwrite LD_LIBRARY_PATH, the cluster's CUDA libs live there). `tmap` (clustering/plot only) is not usable (PyPI `tmap` lacks `layout_from_edge_list`); we skip clustering and only use the pocket embeddings (`pocket_embeddings/*.pkl`). Run with `-sr false`, `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` (torch 2.6 default weights_only breaks fair-esm checkpoint loading; checkpoint is the official Meta file). |
| ESM-2 3B weights (for EPoCS) | https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t36_3B_UR50D.pt | esm2_t36_3B_UR50D | MIT (ESM) | 7de8b4082ba15891959ab368b77ce3886697af1efb16d3c9e9e7b0c5d3f07500 | `envs/esm_weights/` (5.7 GB); contact-regression file sha256 4da500eab246481dc9c8c95bc7b1d02f2803d761c380b0e95186d4a07d0fc84e |
| ESM-2 650M (B4) | HuggingFace `facebook/esm2_t33_650M_UR50D` via transformers | HF cache `data/processed/hf` | MIT | (HF snapshot, see cache) | fp16 forward |

## Docking panels (A2)
Raw sources in `data/raw/panel_sources/` (git-ignored); prepared panels in `data/ref/panels/`
(`<panel>_v1.{smi,csv,sdf}` + `panels_manifest.json`, ~0.8 MB, committable under the licences below).
Built by `scripts/a2/build_panels.py` (`--stage pool` then `--stage pick`), deterministic (`SEEDS[0]`).
Protonation: **dimorphite-dl 2.1.0**, pH 7.4 (`ph_min=ph_max=7.4, precision=0.0`, single dominant microstate),
which is what ADock/meeko expects (explicit H, formal charges on the input mol).
3D: RDKit ETKDGv3 (`randomSeed=SEEDS[0]`) + MMFF94 (UFF fallback), explicit H.

| dataset | source URL | version / date fetched | sha256 (archive) | license | fetch/build script | notes |
|---|---|---|---|---|---|---|
| NCI Open Database, release 4 (fragment pool) | https://cactus.nci.nih.gov/download/nci/NCI-Open_2012-05-01.sdf.gz | release 2012-05-01, fetched 2026-10-27 | 64394fc0e07e49b0cfdbd79f4481d7b304662c8792df28f1a87a0f7e0279f45b | **public domain** (NCI/DTP Open Chemical Repository; NCI/CADD processing). Freely redistributable. | `scripts/a2/build_panels.py` | 265,242 records → 47,663 after the Ro3-like fragment filter |
| PocketVec lead-like set `LLM.smi` (lead-like pool) | https://raw.githubusercontent.com/sbnb-irb/PocketVec/HEAD/data/libs/SMILES/LLM.smi | repo HEAD 2026-10-27 | 326a30bf1093d7a0c08cb8e1054e1d64a87b1195dd4c52c25047ea86dd147777 | **MIT** (`sbnb-irb/PocketVec`, LICENSE sha256 59c12b29a575d2c7…) | `scripts/a2/build_panels.py` | the published 1,000 lead-like molecules (MOE, MW 200–450) from which PocketVec drew its 128-molecule panel; 840 pass MW 200–450 + ≤ 6 rotatable bonds |
| PocketVec published 128 (`TOP_128_rDock_LLM.smi`, reference only) | …/data/libs/SMILES/TOP_128_rDock_LLM.smi | repo HEAD 2026-10-27 | 66c2aa6aab8c9851a641fc0bf181ee412daac6ecff5bc0505bb345896bb53c5b | MIT | — | kept only to measure the overlap with our MaxMin pick (16/128) |
| **A2 fragment panel** `data/ref/panels/fragments_v1.*` | derived | built 2026-10-27, seed 0 | sdf b5d94fa27a03315a…, csv 88650ce117a65cfe…, smi e75a3336fc424567… | public domain (NCI) | `scripts/a2/build_panels.py --stage pick` | 128 fragments; filters: neutral-source largest fragment, elements CHNOFPSClBrI, 8–17 heavy atoms, MW ≤ 300, ≥ 1 ring, ≤ 3 rotatable bonds, HBD ≤ 3, HBA ≤ 6, cLogP ≤ 3.5, PAINS-free. Stratified 6 pharmacophore classes (apolar/aromatic, donor-rich, acceptor-rich, mixed, cationic, anionic) × 3 heavy-atom bins (8–9: 24, 10–14: 80, 15–17: 24), MaxMin (Morgan r2/2048) within stratum |
| **A2 lead-like panel** `data/ref/panels/leadlike_v1.*` | derived | built 2026-10-27, seed 0 | sdf c466c31947179779…, csv 471bee472560ed86…, smi 612f8108f6789f96… | MIT (PocketVec) | `scripts/a2/build_panels.py --stage pick` | 128 lead-like molecules, MW 200–450, ≤ 6 rotatable bonds, MaxMin over the 840-molecule pool |

**Licence honesty.** The fragment panel is *not* a vendor fragment library. Enamine / Life Chemicals /
Maybridge / DSi-Poised sets either carry no redistribution grant or are behind a click-through; ZINC's
`files.docking.org` is blocked by the cluster proxy and `zinc.docking.org` subsets are captcha-gated from here.
We therefore used the public-domain NCI Open Database and applied a Rule-of-3-like fragment filter ourselves;
this is a fragment-*like* subset of a general screening collection, not a designed fragment library, and that
difference should be stated in any comparison with published fragment-screening results.
