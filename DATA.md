# DATA — every dataset used (source, version, checksum, license)

Raw data lives in `data/raw/` (git-ignored); fetch scripts in `scripts/data/`. Restricted data is never committed.

| dataset | source URL | version / date fetched | sha256 (archive) | license | fetch script | notes |
|---|---|---|---|---|---|---|
| AFDB (local copy) | /cluster/work/beltrao/shared/alphafold/v6 | v6 | n/a (mount) | CC-BY-4.0 | — | proteome tarballs |
| PDB (local copy) | /cluster/scratch/jjaenes/pdb | mirror | n/a (mount) | CC0 | — | mmCIF.gz, 2-char dirs |
| AFDB predicted dimers | /cluster/project/beltrao/gmagnus/dimers | AFDB complexes v1 | per-file in manifests | CC-BY-4.0 | — | human/yeast/ecoli homo+hetero |
