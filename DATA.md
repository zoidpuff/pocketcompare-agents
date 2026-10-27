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
| iPPI-DB cavity summary (feasibility only) | https://ippidb.pasteur.fr/api/summary/ | live API 2026-10-27; partial (10/117 pages, server 503s) | per-page JSON in data/raw/ippidb/pages/ (no combined file yet) | see ippidb.pasteur.fr (unstated in API) | scripts/ppi/07_ippidb_feasibility.py | used only for overlap counts in reports/ppi_dimers.md |

## Tools (binaries)
| tool | source | version (commit) | sha256 (archive) | license |
|---|---|---|---|---|
| MMseqs2 | github.com/soedinglab/MMseqs2 releases/latest mmseqs-linux-avx2.tar.gz (2026-10-27) | 8cc5ce367b5638c4306c2d7cfc652dd099a4643f | bd9b0234da5949ad528d5b5f9ea4cda9c1e23dce14b46c0791d4d919a76e61ce | MIT |
| Foldseek | mmseqs.com/foldseek/foldseek-linux-avx2.tar.gz (2026-10-27) | 463739e0014a1549a527de589102cde98f802f37 | f886374e29ebbf03849cd9c4c8929be00904856dd271627d8c3043607e2af95a | GPL-3.0 |
