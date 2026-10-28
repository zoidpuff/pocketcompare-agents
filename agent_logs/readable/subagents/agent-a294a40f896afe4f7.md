# Sub-agent a294a40f896afe4f7 — PPI-R and dimer interface atlas demo (opus)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-28 05:02:49

EXPLORATORY post-test work on the PPI side of a pocket-similarity project. Project root: /cluster/project/beltrao/gmagnus/pocket_compare (git; do NOT commit — the PI commits). Read RESEARCH_TREE.md (status M3, D7, D22–D23), reports/{ppi_dimers,ppi_datasets,tooling,proteome_demo}.md, docs/FINGERPRINTS.md, src/pocketcompare/{method.py,cli.py,fpindex.py}. Env: `source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache`. ≤ 24 CPU workers, GPUs cuda:0–1. Do NOT modify frozen files (scripts/final_eval.py, evaluate.py, configs/final_method.yaml, model weights). Do not open data/sealed/. Time box 2.5 h. Every output is labelled EXPLORATORY. Use the final method via method.py / the stored fingerprints.

A. PPI-R (ligand-grounded PPI retrieval; was proposed when the PPI-L confirmatory gate failed, D7): pockets = PPI-L modulator pockets (data/splits/ppi_l_pockets.parquet, Pasteur PLOC+PLONC, L-mode on the modulator) from TRAIN+VAL splits only (do not touch the sealed PPI-L test pairs), plus a background of non-PPI ligand pockets from BLiPS train/val (L-mode) matched on volume and buriedness (declare matching rule first). For each modulator pocket query, rank all other pockets from DIFFERENT homology groups; metric: AUC / AP of "is a PPI-modulator pocket" among the ranked neighbours (top-k precision k = 10, 50) vs the matched background, for FINAL, N1, B1, B4 (ESM, B4 note: sequence-based), with homology-group bootstrap CIs (evaluate.py). This answers: does the fingerprint recognise "PPI-modulator-pocket-ness" across families? Write the protocol at the top of the script before computing scores.
B. Dimer interface-pocket atlas demo: run `pocketcompare describe` (AF mode) on all AFDB dimers in /cluster/project/beltrao/gmagnus/dimers (15,161 complexes; BURROW ran at ~40 dimers/s on 16 CPUs) — or reuse cached PPIPS pockets where available and run the rest — keeping interface pockets (f_min ≥ 0.25, ≥ 10 points) with interface flags, pLDDT and ipTM/ipSAE from the manifests. Build a FAISS index. Then: (i) search each interface pocket against the PPI-L modulator pockets (all splits allowed here: this is a demo, not an evaluation; say so) and against the BLiPS train/val ligand pockets: report how many AFDB interface pockets have a close neighbour (cosine above the 99th percentile of the background distribution) among known modulator pockets, with 10 illustrative examples (gene pairs, matched modulator target + ligand, similarity, whether the proteins are homologous to the modulator target — flag trivial homology hits); (ii) cluster interface pockets (e.g. FAISS k-means or graph communities on top-10 neighbours) and report cluster count and a few large cross-family clusters. Record throughput.
Outputs: results/exploratory/ppi_r/, results/exploratory/dimer_atlas/ (small summaries; large tables under data/processed/), reports/exploratory_ppi.md (≤ 1.5 pages; first line "EXPLORATORY — post-test"). Final message ≤ 200 words.


### PI / user turn · 2026-10-28 05:02:49

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


**→ tool call `Bash`** · 2026-10-28 05:02:52

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; ls; ls reports docs src/pocketcompare results results/exploratory 2>/dev/null; wc -l RESEARCH_TREE.md reports/{ppi_dimers,ppi_datasets,tooling,proteome_demo}.md docs/FINGERPRINTS.md src/pocketcompare/{method.py,cli.py,fpindex.py}", "description": "List project layout and file sizes"}
```


**← tool result**

```
DATA.md
DESIGN.md
FREEZE.json
LESSONS.md
LITERATURE.md
PREREG.md
PROMPT.md
README.md
REPORT_draft.md
RESEARCH_TREE.md
configs
data
docs
envs
logs
pyproject.toml
reports
results
reviews
scripts
src
tests
tools
docs:
FINGERPRINTS.md

reports:
a1_descriptors.md
a2_docking.md
a4b_selection.md
af_robustness_dev.md
audit_splits.md
baselines_b4_b5.md
blind_and_ppil.md
blips_ppips_prep.md
data_benchmarks.md
definition_robustness.md
dev_eval_blips_ppips.md
dev_eval_tough_m1.md
dev_eval_v2splits.md
evaluate_module.md
exploratory_fusion.md
final_eval_infra.md
fragment_docking_feasibility.md
l4_pointnet.md
pocket_adapter.md
ppi_datasets.md
ppi_dimers.md
proteome_demo.md
splits.md
tooling.md
verification_final.md

results:
a2
audit
benchmarks
dev
exploratory
explore
feasibility
final
final_dryrun
models
pocket_cache
ppi
proteome
release
tooling
trials.tsv
verify

results/exploratory:
fusion
unseal_log.tsv

src/pocketcompare:
__init__.py
__main__.py
__pycache__
a4b.py
cli.py
datasets
descriptors
descstore.py
evaluate.py
fpindex.py
l4.py
method.py
pockets.py
pockets_fast.py
provenance.py
seeds.py
similarity.py
splitutil.py
   288 RESEARCH_TREE.md
   115 reports/ppi_dimers.md
    85 reports/ppi_datasets.md
    81 reports/tooling.md
   125 reports/proteome_demo.md
   163 docs/FINGERPRINTS.md
   305 src/pocketcompare/method.py
   521 src/pocketcompare/cli.py
   230 src/pocketcompare/fpindex.py
  1913 total
```


**→ tool call `Bash`** · 2026-10-28 05:02:55

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat RESEARCH_TREE.md", "description": "Read research tree"}
```


**→ tool call `Bash`** · 2026-10-28 05:02:56

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat reports/ppi_dimers.md reports/ppi_datasets.md", "description": "Read PPI reports"}
```


**→ tool call `Bash`** · 2026-10-28 05:02:57

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat reports/tooling.md reports/proteome_demo.md docs/FINGERPRINTS.md", "description": "Read tooling, proteome, fingerprint docs"}
```


**→ tool call `Bash`** · 2026-10-28 05:02:58

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat src/pocketcompare/method.py src/pocketcompare/fpindex.py", "description": "Read method and fpindex source"}
```


**→ tool call `Bash`** · 2026-10-28 05:02:58

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat src/pocketcompare/cli.py", "description": "Read CLI source"}
```


**← tool result**

```
"""``pocketcompare`` command line: describe pockets, compare them, build and search FAISS indices.

    pocketcompare describe STRUCTURE|DIR ... -o pockets.parquet [--af-mode] [--workers 8] [--device cuda:0]
    pocketcompare describe 1abc.cif.gz --ligand lig.sdf -o site.parquet          # L mode (ligand shell)
    pocketcompare describe 1abc.cif.gz --residues A:43,A:45 --locate burrow -o d.parquet   # D mode
    pocketcompare compare a.parquet b.parquet [--top 5] [-o pairs.parquet] [--matrix S.npy]
    pocketcompare index pockets.parquet -o idx/ [--kind flat|ivfpq] [--nlist N]
    pocketcompare search query.parquet idx/ [-k 10] [--rerank 100] [-o hits.parquet]
    python -m pocketcompare ...                                                   # same

``describe`` without a site describes every pocket of each structure (``method.describe_all``: merged BURROW
region-rule pockets with >= 10 points); with ``--ligand``/``--residues`` one site per structure.  Output: one row
per pocket with id, BURROW score, residues, centre, volume, pLDDT stats (``--af-mode``) and the 384-d fingerprint
(see ``pocketcompare.fpindex`` for the table format).  Backends: ``ref`` (BURROW reference implementation, the
one the method was evaluated with), ``fast`` (BURROW's Numba CPU path) and ``--device cuda:N`` (BURROW's batched
GPU featurisation); all three give identical pockets and fingerprints (tests/test_cli.py).
"""
from __future__ import annotations

import os

os.environ.setdefault("NUMBA_CACHE_DI
… [22,857 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
"""The final pocket-similarity method (PREREG §1; selected in reports/a4b_selection.md) — public API.

    from pocketcompare import method
    V, info = method.describe("1abc.cif.gz", return_info=True)        # every BURROW region pocket (D mode): (n, d)
    v = method.describe("1abc.cif.gz", site="ligand.sdf")             # a ligand-defined site (L mode): (1, d)
    v = method.describe("1abc.cif.gz", site=["A:43", "A:45", "A:46"])  # a residue-defined site
    v = method.describe(path, site=xyz_array, af_mode=True)           # ligand heavy-atom coordinates; AF model
    S = method.similarity(v, V)                                       # (1, n) scores; higher = more similar

Pipeline (all parameters in configs/final_method.yaml, with sha256 of every data file it needs):
1. BURROW on the protein (``pocketcompare.pockets.featurize_structure``; ``af_mode`` = BURROW AF mode).
2. Site location: a ligand (file, or (n, 3) heavy-atom coordinates) -> the 4 Å ligand shell; a residue list
   ("chain:num") -> the residue shell (4 Å, bur10 >= 0.5).  With ``locate="burrow"`` the given site only *locates*
   a BURROW pocket, exactly as the evaluation's D mode did (``scripts/build_point_cache.py`` +
   ``scripts/compute_descriptors.py --arm a1r``): (a) the region-rule pockets are merged
   (``pockets.merge_pockets``: touch <= 1.5 Å or residue Jaccard >= 0.3); (b) the merged pocket with the highest
   coverage of the site points is matched (``pockets.dmode_match``; ties -> higher score, bett
… [27,264 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
# Research tree — pocket similarity on BURROW

Legend: [ ] planned · [~] in progress · [x] done · [-] abandoned/negative · [!] key finding
Started 2026-10-27 ~18:00 CET; 24 h budget (revisit ~2026-10-28 18:00).

## Status summary (latest first)

### 2026-10-28 05:35 — M3 final evaluation done and verified
The frozen method (A4b:n1_linear on the ligand-free N1 descriptor) beats B1 and ESM-2 on the BURROW-clean
TOUGH-M1 test in both pocket modes (C1a/C1b/C1-D reject under Holm; C1a/C1b only marginally and Monte-Carlo-fragile,
C1-D robust), but not on ProSPECCTs D5.2/D6.2/D7 (C2). It is robust to AlphaFold models (BLiPS-test AF ≈ holo). The
largest finding is methodological: ligand-defined 4 Å pockets leak ligand size (ligand heavy-atom count alone gives
ROC 0.95 on TOUGH-M1), so L-mode benchmark numbers in the literature and ours overstate pocket similarity.

Independent verification reproduced all headlines. Remaining time goes to exploratory (dev-selected, clearly
labelled) improvements — A4b+L4 fusion, API/CLI for the docking team, proteome fingerprints with the final head —
and REPORT.md.

### 2026-10-27 23:05 — M2 dev results, PREREG consolidated
Dev evaluation on TOUGH-M1-dev, BLiPS-val and PPIPS-val is complete for all arms. The typed volumetric fingerprint
A1 wins in ligand-defined (L) mode (TOUGH-M1-dev ROC 0.795, BLiPS-val 0.775 vs B1 0.64/0.69) but collapses in the
deployment (detected, D) mode (0.56) because the 4 Å ligand shell imprints ligand shape — a key finding
… [26,723 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
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
- Empty sph8 sets fall back to the base set; the demo dropped such pockets
… [22,103 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
# PPI pockets in AFDB predicted dimers: BURROW characterisation (2026-10-27)

Scripts: `scripts/ppi/01–07` (run order in `scripts/ppi/run_all.sh`; ~10 min). Numbers: `results/ppi/summary.txt`,
`data/processed/dimers/{inventory_summary.txt,orthology/summary.txt,ippidb/summary.txt}`. BURROW FREEZE v2, `--af-mode`,
default preset, `all` ranker. Sample = 100 dimers per organism × type (seed `SEEDS[0]`), 600 dimers + 1,200 chains.

## Key numbers
| | value |
|---|---|
| dimer files (human/yeast/E. coli) | homo 4,819 / 648 / 1,206; hetero 5,791 / 1,250 / 1,447; **15,161 total** |
| BURROW speed, 16 CPU workers | **40 dimers/s** (322 ms/dimer single-core, 4.9k atoms), 83 monomers/s; `--min-score none` costs nothing extra |
| dimers with ≥ 1 interface pocket (f_min ≥ 0.25; default list / full list) | **82.5 %** / 96.2 % (homo 85.7 %, hetero 79.3 %) |
| interface pockets per dimer (default list) | 1.8–2.7 (26.6 % of cavity pockets) |
| interface pockets not found when the chains are run alone | **85.8 %** absent from monomer default lists; 48.8 % "PPI-created" (no monomer pocket at all in that space) vs 17.1 % for the control |
| homodimer symmetric pocket pairs (both in default list) | 2.5 per homodimer → **~15.9k pairs** over 6,673 homodimers (~4.0k involve interface pockets) |
| symmetric copy found by BURROW | 61 % (residue Jaccard ≥ 0.5), 78 % (geometric overlap) |
| cross-species interologs (MMseqs2) | 5,353 homo + 4,989 hetero complex pairs; 4,039 at < 30 % pair identity |
| di
… [15,649 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:03:03

```
{"command": "cd /cluster/project/beltrao/gmagnus/dimers; ls; find . -maxdepth 2 | head -40; find . -name \"*.pdb*\" | wc -l; nproc; uptime; nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv", "description": "Inspect dimers directory and machine load"}
```


**← tool result**

```
afdb_ecoli_dimers
afdb_human_dimers
afdb_yeast_dimers
.
./.DS_Store
./afdb_human_dimers
./afdb_ecoli_dimers
./afdb_yeast_dimers
./afdb_human_dimers/.DS_Store
./afdb_human_dimers/homodimers
./afdb_human_dimers/heterodimers
./afdb_ecoli_dimers/homodimers
./afdb_ecoli_dimers/heterodimers
./afdb_yeast_dimers/homodimers
./afdb_yeast_dimers/heterodimers
15161
64
 06:03:03 up 14 days, 23:21,  0 user,  load average: 17.59, 28.99, 36.01
index, utilization.gpu [%], memory.used [MiB]
0, 0 %, 1 MiB
1, 0 %, 1 MiB
2, 0 %, 1 MiB
3, 0 %, 1 MiB
```


**→ tool call `Bash`** · 2026-10-28 05:03:07

```
{"command": "cd /cluster/project/beltrao/gmagnus/dimers; ls afdb_human_dimers/homodimers | head; ls afdb_human_dimers/homodimers | wc -l; find . -maxdepth 3 -type f ! -name \"*.pdb\" | head -20; ls /cluster/project/beltrao/gmagnus/pocket_compare/data/processed/dimers/ /cluster/project/beltrao/gmagnus/pocket_compare/data/processed/ | head -50", "description": "List dimer files and manifests, processed data"}
```


**← tool result**

```
AF-0000000065760335.pdb
AF-0000000065760352.pdb
AF-0000000065760358.pdb
AF-0000000065760364.pdb
AF-0000000065760371.pdb
AF-0000000065760376.pdb
AF-0000000065760388.pdb
AF-0000000065760570.pdb
AF-0000000065760573.pdb
AF-0000000065760752.pdb
4821
./.DS_Store
./afdb_human_dimers/.DS_Store
./afdb_human_dimers/homodimers/download_manifest.csv
./afdb_human_dimers/heterodimers/download_manifest.csv
./afdb_ecoli_dimers/homodimers/download_manifest.csv
./afdb_ecoli_dimers/homodimers/candidates.csv
./afdb_ecoli_dimers/heterodimers/download_manifest.csv
./afdb_ecoli_dimers/heterodimers/candidates.csv
./afdb_yeast_dimers/homodimers/download_manifest.csv
./afdb_yeast_dimers/homodimers/candidates.csv
./afdb_yeast_dimers/heterodimers/download_manifest.csv
./afdb_yeast_dimers/heterodimers/candidates.csv
./afdb_human_dimers/homodimers/candidates.csv
./afdb_human_dimers/heterodimers/candidates.csv
/cluster/project/beltrao/gmagnus/pocket_compare/data/processed/:
b0prime
benchmarks
cache
descriptors
dimers
docking
epocs
esm
hf
homology
l4
l4_emb
ppi
proteome_human
release

/cluster/project/beltrao/gmagnus/pocket_compare/data/processed/dimers/:
inventory_summary.txt
ippidb
manifest.tsv
orthology
sample
sequences.fasta
```


**→ tool call `Bash`** · 2026-10-28 05:03:21

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; S=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; mkdir -p $S/t; ls /cluster/project/beltrao/gmagnus/dimers/afdb_human_dimers/heterodimers/*.pdb | head -20 | xargs -I{} ln -sf {} $S/t/; time pocketcompare describe $S/t --af-mode --device cuda:0 --workers 8 -o $S/t.parquet; python -c \"\nimport pandas as pd; from pocketcompare import fpindex as F\nm,V,r=F.read_table('$S/t.parquet'); print(m.columns.tolist()); print(m.head(3).T); print(len(m), V.shape)\"", "description": "Test describe on 20 heterodimers"}
```


**← tool result**

```
20 structures (0 errors), 193 pockets -> /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/t.parquet  [5.9 s wall, 0.296 s/structure; cuda:0, backend fast, 8 workers]

real	0m7.126s
user	1m3.747s
sys	0m3.899s
['pocket_id', 'structure', 'structure_stem', 'mode', 'merged_index', 'burrow_index', 'burrow_rank', 'members', 'burrow_score', 'n_points', 'volume_A3', 'center_x', 'center_y', 'center_z', 'site_n_points', 'site_volume_A3', 'sph8_fallback', 'residues', 'ok', 'plddt_mean', 'plddt_min', 'plddt_frac_lt70']
                                                                 0  ...                                                  2
pocket_id                                   AF-0000000203452075:m0  ...                             AF-0000000203452075:m2
structure        /tmp/claude-548918/-cluster-project-beltrao-gm...  ...  /tmp/claude-548918/-cluster-project-beltrao-gm...
structure_stem                                 AF-0000000203452075  ...                                AF-0000000203452075
mode                                                             D  ...                                                  D
merged_index                                                     0  ...                                                  2
burrow_index                                                     0  ...                                                  2
burrow_rank                                                  
… [1,944 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:03:38

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; mkdir -p data/processed/dimer_atlas results/exploratory/dimer_atlas results/exploratory/ppi_r scripts/exploratory logs; cat > scripts/exploratory/dimer_atlas_describe.sh <<'EOF'\n#!/bin/bash\n# EXPLORATORY (post-test) dimer interface-pocket atlas: describe all 15,161 AFDB dimers with the final method (CLI,\n# AF mode, fast GPU backend), two shards on cuda:0 / cuda:1, 11 CPU workers each (22 total).\nset -e\ncd /cluster/project/beltrao/gmagnus/pocket_compare\nsource .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache\nD=/cluster/project/beltrao/gmagnus/dimers\nO=data/processed/dimer_atlas\ndate +%s > $O/start_epoch\n( /usr/bin/time -v pocketcompare describe $D/afdb_human_dimers/homodimers $D/afdb_yeast_dimers $D/afdb_ecoli_dimers/homodimers \\\n    --af-mode --device cuda:0 --workers 11 -o $O/shard0.parquet ) > logs/dimer_atlas_shard0.log 2>&1 &\n( /usr/bin/time -v pocketcompare describe $D/afdb_human_dimers/heterodimers $D/afdb_ecoli_dimers/heterodimers \\\n    --af-mode --device cuda:1 --workers 11 -o $O/shard1.parquet ) > logs/dimer_atlas_shard1.log 2>&1 &\nwait\ndate +%s > $O/end_epoch\nEOF\nchmod +x scripts/exploratory/dimer_atlas_describe.sh", "description": "Write dimer atlas describe launcher script"}
```


**→ tool call `Bash`** · 2026-10-28 05:03:38

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; bash scripts/exploratory/dimer_atlas_describe.sh", "description": "Run dimer atlas describe on both GPUs", "run_in_background": true}
```


**← tool result**

```
(Bash completed with no output)
```


**← tool result**

```
Command running in background with ID: b0pmkpmyx. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/b0pmkpmyx.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
Session cwd remains /cluster/project/beltrao/gmagnus/pocket_compare; directory changes made by the backgrounded command do not apply to subsequent commands.
```


**→ tool call `Bash`** · 2026-10-28 05:03:41

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; ls data/splits/; ls data/processed/descriptors data/processed/descriptors/* | head -80; ls data/processed/esm data/processed/ppi | head", "description": "List splits and descriptor stores"}
```


**← tool result**

```
SHA256SUMS.txt
SPLITS.md
blips_site_selection_frozen.txt
blips_sites.parquet
blips_sites_v2.parquet
blips_split_counts.json
blips_split_counts_v2.json
blips_test_exclusions_v2.parquet
blips_train_pairs.parquet
blips_train_pairs_v2.parquet
blips_val_pairs.parquet
blips_val_pairs_v2.parquet
homology_components.json
homology_edges.parquet
homology_nodes.parquet
inputs
ppi_l_pairs_train.parquet
ppi_l_pairs_val.parquet
ppi_l_pockets.parquet
ppips_burrow_homology.json
ppips_burrow_homology.parquet
ppips_complex_splits.parquet
ppips_ortho_queries_train.parquet
ppips_ortho_queries_val.parquet
ppips_sym_pairs_train.parquet
ppips_sym_pairs_val.parquet
split_changes.json
split_sensitivity.json
tough_m1_dev_pairs.parquet
tough_m1_pockets_split.parquet
tough_m1_split_counts.json
data/processed/descriptors:
blips
blips_test_af
blips_test_holo
ppi_l
ppips
prospeccts
tough_m1
vertex

data/processed/descriptors/blips:
a1_dbins_coarse_D.ids.parquet
a1_dbins_coarse_D.ids.parquet.prov.json
a1_dbins_coarse_D.layout.json
a1_dbins_coarse_D.npy
a1_dbins_coarse_L.ids.parquet
a1_dbins_coarse_L.ids.parquet.prov.json
a1_dbins_coarse_L.layout.json
a1_dbins_coarse_L.npy
a1_dbins_fine_D.ids.parquet
a1_dbins_fine_D.ids.parquet.prov.json
a1_dbins_fine_D.layout.json
a1_dbins_fine_D.npy
a1_dbins_fine_L.ids.parquet
a1_dbins_fine_L.ids.parquet.prov.json
a1_dbins_fine_L.layout.json
a1_dbins_fine_L.npy
a1_dbins_short_D.ids.parquet
a1_dbins_short_D.ids.parquet.prov.json
a1_dbins_short_D.layout.json
a1_dbins_short_D
… [1,422 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:03:45

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; ls data/processed/descriptors/ppi_l data/processed/ppi/ppil | head -60; ls data/processed/descriptors/blips | grep -v \"^a1_\" ; ls data/processed/esm/esm2_t33_650M_UR50D | head -30", "description": "List PPI-L and BLiPS non-A1 descriptor files"}
```


**← tool result**

```
data/processed/descriptors/ppi_l:
a1_pair_only_D.ids.parquet
a1_pair_only_D.ids.parquet.prov.json
a1_pair_only_D.layout.json
a1_pair_only_D.npy
a1_pair_only_L.ids.parquet
a1_pair_only_L.ids.parquet.prov.json
a1_pair_only_L.layout.json
a1_pair_only_L.npy
a1r
b0_default_D.ids.parquet
b0_default_D.ids.parquet.prov.json
b0_default_D.layout.json
b0_default_D.npy
b0_default_L.ids.parquet
b0_default_L.ids.parquet.prov.json
b0_default_L.layout.json
b0_default_L.npy
b1_default_D.ids.parquet
b1_default_D.ids.parquet.prov.json
b1_default_D.layout.json
b1_default_D.npy
b1_default_L.ids.parquet
b1_default_L.ids.parquet.prov.json
b1_default_L.layout.json
b1_default_L.npy
n_inputs_D.npz
n_inputs_L.npz
n_inputs_ids.parquet
n_inputs_ids.parquet.prov.json
n_inputs_layout.json

data/processed/ppi/ppil:
b6_psi_train.parquet
b6_psi_val.parquet
cavities.parquet
chain_groups.parquet
chains
chains.fasta
featurize_timing.parquet
foldseek.tsv
ligand_instances.parquet
mmseqs.m8
pockets.parquet
pockets_summary.json
a1r
b0_default_D.ids.parquet
b0_default_D.ids.parquet.prov.json
b0_default_D.layout.json
b0_default_D.npy
b0_default_L.ids.parquet
b0_default_L.ids.parquet.prov.json
b0_default_L.layout.json
b0_default_L.npy
b1_default_D.ids.parquet
b1_default_D.ids.parquet.prov.json
b1_default_D.layout.json
b1_default_D.npy
b1_default_L.ids.parquet
b1_default_L.ids.parquet.prov.json
b1_default_L.layout.json
b1_default_L.npy
b1_learned_D.ids.parquet
b1_learned_D.ids.parquet.prov.json
b1_learned_D.layout.json

… [1,643 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:03:48

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -n -i \"ppi_l\\|ppil\\|ppi-l\" scripts/final_eval.py | head -40; ls scripts | head -80", "description": "Find PPI-L handling in final_eval"}
```


**← tool result**

```
64:  PPI-L test (exploratory): run iff its descriptors exist, else recorded as skipped.
951:PPIL_PAIR_FILE = "ppi_l_test_pairs.parquet"
954:def ppil_set(name: str, pairs: pd.DataFrame) -> PairSet:
955:    """PPI-L (exploratory C3; reports/ppi_datasets.md): pairs of PLOC/PLONC modulator pockets (label 1 = cross-group,
957:    data/processed/descriptors/ppi_l (scripts/ppi/14_ppil_index.py + compute_n_inputs.py / compute_descriptors.py)."""
961:    P = _attach_geometry(P, "ppi_l")
967:    return PairSet(name, "ppi_l", P, ia, ib, y, {"hom": hom, "lig": lig}, subsets={"all": np.ones(len(y), bool)},
971:def stage_ppil(ps: PairSet, method, store, args):
975:    specs = [s for s in BASE_SPECS if s[1] != "esm2_noz" and s[0] != "B4"]   # no B4 for PPI-L (ESM not computed)
1221:    res["sealed hashes recorded"] = {n: n in exp for n in (*SEALED_NEEDED, PPIL_PAIR_FILE)}
1222:    res["sealed files present (not opened)"] = {n: (SEALED_DIR / n).exists() for n in (*SEALED_NEEDED, PPIL_PAIR_FILE)}
1226:                                                "blips_test_af", "ppips", "ppi_l")}
1357:    # ---------------------------------------------------------------- PPI-L (exploratory)
1358:    ppil_ok = all(store.available("ppi_l", st) for st in ("n_inputs_L:a1_sph8", "b1_default_L", "b1_default_D"))
1359:    if not ppil_ok:
1360:        details["ppi_l"] = "skipped: no PPI-L descriptors (data/processed/descriptors/ppi_l); exploratory per D7"
1361:    elif real and PPIL_PAIR_FILE not in sealed.expect
… [1,023 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:03:52

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 1,80p scripts/compute_esm.py; grep -n \"def \\|class \" src/pocketcompare/descstore.py | head -40; grep -n \"BASE_SPECS\" -A25 scripts/final_eval.py | head -60", "description": "Inspect ESM script, descstore API and specs"}
```


**← tool result**

```
#!/usr/bin/env python
"""B4 ESM-2 pocket descriptors.  Usage: python scripts/compute_esm.py --dataset tough_m1 [--limit N]

Dataset adapters (the tough_m1 branch is the original code, unchanged):
  blips, blips_test_holo, blips_test_af  point-cache index + data/processed/benchmarks/<ds>_pockets.parquet (structure
        path); L = index lining residues, D = residues of the matched merged pocket (d_members -> pk_residues).
        Only the chains that carry pocket residues are embedded (holo mmCIFs can hold many chains); AF models:
        the AF sequence (chain A of the model file).
  prospeccts, vertex  as blips (generic path); require --label-free-structures (no labels are read).
  ppips merged region-rule pockets (data/processed/ppi/ppips/pockets.parquet), D only = the pocket's BURROW
        output residues on the AF dimer (both chains embedded separately, as for every multi-chain file).
"""
import argparse, json, subprocess, sys, time
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare.descriptors import esm_pocket as ep  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", default=None)
    ap.add_argument("--label-free-structures", action="store_true",
                    help=
… [7,082 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:03:56

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -n \"^def final_vectors\\|^def descriptor_vectors\\|^def n1_vectors\\|^def _attach_geometry\" scripts/final_eval.py; sed -n \"$(grep -n '^def final_vectors' scripts/final_eval.py | cut -d: -f1),+45p\" scripts/final_eval.py; sed -n \"$(grep -n '^def descriptor_vectors' scripts/final_eval.py | cut -d: -f1),+40p\" scripts/final_eval.py", "description": "Read final_vectors and descriptor_vectors"}
```


**← tool result**

```
286:def _attach_geometry(P: pd.DataFrame, ds: str) -> pd.DataFrame:
578:def final_vectors(ps: PairSet, method, store, modes=("L", "D"), dataset=None, extras=True, learned_ok=True):
595:def descriptor_vectors(ps: PairSet, store, specs, modes=("L", "D"), dataset=None):
def final_vectors(ps: PairSet, method, store, modes=("L", "D"), dataset=None, extras=True, learned_ok=True):
    """FINAL (+ the Addendum-A2 descriptive arms N1 and L4, each skipped where its inputs do not exist)."""
    out = []
    if learned_ok or not method.is_learned:
        out += _method_vectors(ps, method, store, modes, dataset, "FINAL", "final method")
    if extras:
        for xa in EXTRA_ARMS:
            if xa.is_learned and not learned_ok:
                continue
            try:
                out += _method_vectors(ps, xa, store, modes, dataset, xa.arm,
                                       f"descriptive arm (PREREG Addendum A2; designated variant {xa.designated})")
            except (FileNotFoundError, KeyError) as e:
                log(f"  {xa.name} skipped on {dataset or ps.dataset}: {type(e).__name__}: {e}")
    return out


def descriptor_vectors(ps: PairSet, store, specs, modes=("L", "D"), dataset=None):
    """specs: [(arm, config, stem_prefix, zscore)] -> raw + CSLS cosine Vecs (eval_dev.cosine_vectors)."""
    ds = dataset or ps.dataset
    P = ps.pockets
    out = []
    for arm, cfg, stem, z in specs:
        for mode in modes:
            st = f"{stem}_{mode}"
            if not 
… [2,784 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:04:00

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n \"$(grep -n '^def _method_vectors' scripts/final_eval.py | cut -d: -f1),+40p\" scripts/final_eval.py; grep -n \"EXTRA_ARMS\\s*=\" -A8 scripts/final_eval.py; grep -n \"def cosine_vectors\" -A25 scripts/eval_dev.py src/pocketcompare/*.py | head -40", "description": "Read _method_vectors and cosine_vectors"}
```


**← tool result**

```
def _method_vectors(ps: PairSet, method, store, modes, dataset, arm, note):
    ds = dataset or ps.dataset
    P = ps.pockets
    out = []
    for mode in modes:
        pool = P.cache_ok.to_numpy() if mode == "L" else P.d_match.to_numpy(bool)
        if mode == "D" and ps.d_allowed is not None:
            pool = pool & ps.d_allowed
        idx = np.where(pool)[0]
        if len(idx) <= CSLS_K + 1:
            continue
        E = np.asarray(method.embed(store, ds, mode, P.pocket_id.to_numpy()[idx]), np.float32)
        okr = np.isfinite(E).all(1)
        rows = idx[okr]
        if len(rows) <= CSLS_K + 1:
            continue
        raw, cs = _embed_scores(E[okr], rows, len(P), ps.ia, ps.ib, True)
        out.append(Vec(arm, method.name, "raw", mode, raw, E.shape[1], note))
        out.append(Vec(arm, method.name, "csls", mode, cs, E.shape[1], note + " + CSLS (pool)"))
    return out


def final_vectors(ps: PairSet, method, store, modes=("L", "D"), dataset=None, extras=True, learned_ok=True):
    """FINAL (+ the Addendum-A2 descriptive arms N1 and L4, each skipped where its inputs do not exist)."""
    out = []
    if learned_ok or not method.is_learned:
        out += _method_vectors(ps, method, store, modes, dataset, "FINAL", "final method")
    if extras:
        for xa in EXTRA_ARMS:
            if xa.is_learned and not learned_ok:
                continue
            try:
                out += _method_vectors(ps, xa, store, modes, dataset, xa.arm,
                   
… [2,435 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:04:04

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 480,555p scripts/final_eval.py; grep -n \"def embed\\b\\|def embed(\" -A20 scripts/eval_dev.py | head -40", "description": "Read method embed classes in final_eval"}
```


**← tool result**

```
                rows.append((a, b, lab, u, v))
    df = pd.DataFrame(rows, columns=["pocket_a", "pocket_b", "label", "uniprot_a", "uniprot_b"])
    a, b = df.uniprot_a, df.uniprot_b
    df["protein_pair"] = a.where(a < b, b) + "|" + b.where(a < b, a)
    df["is_self"] = df.pocket_a == df.pocket_b
    return df


def synthetic_tough_full(rng) -> pd.DataFrame:
    s = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet", columns=["pocket_id", "partition"])
    ids = s.pocket_id[s.partition != "dev"].to_numpy()
    n = 30000
    a, b = rng.choice(ids, n), rng.choice(ids, n)
    keep = a != b
    return pd.DataFrame({"pocket_a": a[keep], "pocket_b": b[keep], "label": (rng.random(keep.sum()) < 0.45).astype(int),
                         "tm_score": rng.random(keep.sum()), "seq_identity": rng.random(keep.sum())})


# ============================================================================================ score vectors
Vec = ED.Vec


def _embed_scores(E_rows, rows, n, ia, ib, csls):
    """Raw + CSLS pair scores from unit embeddings of the pool rows (exactly as eval_dev.cosine_vectors)."""
    E = np.zeros((n, E_rows.shape[1]), np.float32)
    E[rows] = E_rows
    avail = np.zeros(n, bool)
    avail[rows] = True
    ok = avail[ia] & avail[ib]
    raw = np.full(len(ia), np.nan)
    raw[ok] = pair_scores(E, ia[ok], ib[ok])
    if not csls:
        return raw, None
    r = np.full(n, np.nan)
    r[rows] = csls_r(E_rows, E_rows, CSLS_K, query_ids=rows, bg_ids=rows)
  
… [1,637 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:04:09

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -n \"^class \\|^def \\|^[A-Z_]* = \" scripts/final_eval.py | head -80; grep -n \"^def \\|^class \" src/pocketcompare/a4b.py", "description": "List functions in final_eval and a4b"}
```


**← tool result**

```
96:ROOT = Path(__file__).resolve().parents[1]
108:CSLS_K = ED.CSLS_K
109:SESOI = 0.03
110:METHOD_CFG = ROOT / "configs/final_method.yaml"
111:SEALED_DIR = ROOT / "data/sealed"
112:SEALED_SUMS = ROOT / "data/sealed_SHA256SUMS.txt"
113:SPLIT_SUMS = ROOT / "data/splits/SHA256SUMS.txt"
114:SEALED_NEEDED = ("tough_m1_test_pairs.parquet", "prospeccts_pairs.parquet", "blips_test_pairs.parquet",
117:WORKTREE_LINKS = ("data/processed", "data/sealed", "data/raw", "data/splits/homology_edges.parquet", "tools",
122:def log(msg):
127:class Sealed:
172:class StandinA1PairOnly:
190:class MethodAdapter:
234:def load_method(allow_standin: bool, force_standin: bool = False):
250:class PairSet:
282:def _index(ds):
286:def _attach_geometry(P: pd.DataFrame, ds: str) -> pd.DataFrame:
299:def _pairs_index(P, pairs, ca="pocket_a", cb="pocket_b"):
306:def tough_set(name, pairs, pocket_filter) -> PairSet:
336:def tough_test_units() -> dict:
344:def blips_set(name, pairs, sites, cache_ds, desc_ds, exclusions=None, allow_missing=False) -> PairSet:
371:_PU_CACHE = {}
374:def prospeccts_units(P: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
392:def _prospeccts_maps():
412:def prospeccts_sets(pairs: pd.DataFrame, synthetic: bool) -> list[PairSet]:
435:def vertex_set(pairs: pd.DataFrame, synthetic: bool) -> PairSet:
454:def synthetic_prospeccts(rng) -> pd.DataFrame:
470:def synthetic_vertex(rng) -> pd.DataFrame:
488:def synthetic_tough_full(rng) -> pd.DataFrame:
502:def _embed_scores(E_rows, rows, n, ia, 
… [3,200 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:04:13

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 190,250p scripts/final_eval.py; sed -n 30,115p src/pocketcompare/a4b.py", "description": "Read MethodAdapter and a4b data access"}
```


**← tool result**

```
class MethodAdapter:
    """Adapter for ``pocketcompare.method.Method`` (A4b API: ``embed(mats)`` with fixed, shipped part statistics).
    Part matrices = the label-free precomputed A4b inputs data/processed/descriptors/<ds>/a1r via
    ``pocketcompare.a4b.raw_parts`` (L shell / D = best sub-pocket U; SPH_FALLBACK: empty sph8 -> located set);
    a dataset without an a1r directory raises (compute_descriptors.py --arm a1r [--label-free-structures])."""
    BLOCK = {("a1", "sph8"): "a1_sph8", ("env", "sph8"): "env_sph8", ("a1", "base"): "a1_base"}

    def __init__(self, m, cfg):
        self.m, self.cfg = m, cfg
        self.name = str(cfg.get("name", "final"))
        self.is_learned = cfg.get("kind") == "learned"
        self.csls = bool(getattr(m, "csls", cfg.get("variant") == "csls"))

    def weight_files(self):
        fs = [ROOT / f for f in self.cfg.get("files_sha256", {})] + [ROOT / f for f in self.cfg.get("model_files", [])]
        if self.cfg.get("input_stats"):
            fs.append(ROOT / self.cfg["input_stats"])
        return sorted(set(fs))

    def raw_parts(self, store, dataset, mode, pocket_ids):
        """N1/N2 part matrices via pocketcompare.a4b.raw_parts (incl. its SPH_FALLBACK); NaN rows if missing."""
        from pocketcompare import a4b as A4
        if not A4.a1r_dir(dataset).exists():
            raise FileNotFoundError(f"{A4.a1r_dir(dataset)} (compute_descriptors.py --arm a1r)")
        ids = set(A4.ids_table(dataset).pocket_id)
        pid = li
… [4,881 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:04:23

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python -c \"\nimport pandas as pd\nfor f in ['data/splits/ppi_l_pockets.parquet','data/processed/cache/points/ppi_l/index.parquet','data/splits/blips_sites_v2.parquet','data/processed/cache/points/blips/index.parquet','data/processed/descriptors/ppi_l/a1r/ids.parquet','data/processed/descriptors/blips/a1r/ids.parquet','data/processed/descriptors/blips/b4_esm2_ids.parquet']:\n    try:\n        d=pd.read_parquet(f); print('==',f,d.shape); print(d.dtypes.to_string()); print(d.head(2).T.to_string()[:2500])\n    except Exception as e: print(f,e)\nfor c in ['split','partition']:\n    pass\nd=pd.read_parquet('data/splits/ppi_l_pockets.parquet'); print([ (c,d[c].value_counts().to_dict()) for c in d.columns if d[c].nunique()<8])\nd=pd.read_parquet('data/splits/blips_sites_v2.parquet'); print([ (c,d[c].value_counts().to_dict()) for c in d.columns if d[c].nunique()<8])\n\"; ls data/processed/descriptors/ppi_l/a1r data/processed/descriptors/blips/a1r", "description": "Inspect PPI-L and BLiPS tables"}
```


**← tool result**

```
== data/splits/ppi_l_pockets.parquet (2236, 47)
pocket_id                      str
pdb                            str
chain                          str
uniprot                        str
lig                            str
resnum                         str
labels                         str
cavities                       str
n_cavities                   int64
cavity_volume                int64
pfam_accession                 str
pfam_name                      str
cath                           str
label                          str
smiles                         str
heavy_atoms                float64
ligand_file                    str
inchikey                       str
structure_path                 str
in_pdb_mirror                 bool
ligand_cluster             float64
mol_id                     float64
key                            str
structure_key                  str
status                         str
failure_reason                 str
definition                     str
n_points                   float64
n_points_dense             float64
volume_A3                  float64
n_lining_res               float64
lining_residues                str
n_ligand_atoms_struct      float64
ligand_protein_min_dist    float64
d_coverage                 float64
d_missed                      bool
d_precision                float64
pocket_def_type                str
pocket_def                     str
ligand_resname                 str
cache_file                     str
group            
… [18,553 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:04:44

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -n \"^def \\|^class \" src/pocketcompare/evaluate.py; sed -n 1,40p src/pocketcompare/evaluate.py; ls tools; which mmseqs foldseek; grep -n \"def apply_rule\" -A25 src/pocketcompare/*.py src/pocketcompare/*/*.py | head -40", "description": "Inspect evaluate.py API and homology tooling"}
```


**← tool result**

```
113:def _as_arrays(y, s, w=None, *, allow_nan=False):
137:def _need_both(y, w):
145:def _grouped_desc(y, s, w):
160:def roc_auc(y, s, w=None) -> float:
171:def average_precision(y, s, w=None, *, target: str = "pos") -> dict:
189:def partial_auc(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
210:def binary_metrics(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
223:def _balance(labels, mask, w):
234:def _factorize(a):
240:def cluster_balanced_auc(y, s, pos_cluster, w=None, *, neg_cluster=None) -> dict:
253:def per_cluster_auc(y, s, pos_cluster, w=None, *, k: int = 10, negatives: str = "all", ci=None, cj=None):
284:def _quantile_bins(x, n_bins):
290:def size_covariates(log_vol_a, log_vol_b) -> np.ndarray:
297:def stratified_auc(y, s, covariate, w=None, *, n_bins: int | Sequence[int] = (5, 5),
347:def retrieval_metrics(df, *, query_col="query", score_col="score", label_col="label", ks: Sequence[int] = (1, 10),
383:def _score_dict(scores) -> dict[str, np.ndarray]:
392:def missing_summary(y, scores) -> dict:
405:def common_set(y, scores) -> tuple[np.ndarray, dict]:
418:def worst_case(y, s) -> tuple[np.ndarray, dict]:
429:def min_impute(y, s) -> tuple[np.ndarray, dict]:
439:def apply_missing_policy(y, scores, missing: str = "raise"):
464:def _encode_clusters(ci, cj):
473:def pair_bootstrap_weights(counts, a, b, w):
479:def bootstrap_counts(n_clusters: int, B: int = DEFAULT_B, seed=DEFAULT_SEED):
531:def _boot_kernel_numpy(cnt, ci_s, cj_s, w_s, y_s, end_s, out_auc, out_ap, offset):
… [4,396 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:04:48

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 347,383p src/pocketcompare/evaluate.py; sed -n 665,690p src/pocketcompare/evaluate.py; grep -rn \"def apply_rule\" src/ | head; ls tools/mmseqs tools/foldseek | head; ls data/processed/homology | head", "description": "Read retrieval_metrics and generic bootstrap"}
```


**← tool result**

```
def retrieval_metrics(df, *, query_col="query", score_col="score", label_col="label", ks: Sequence[int] = (1, 10),
                      ties: str = "pessimistic") -> dict:
    """Top-k hit rate and MRR from a long query->candidate table (one row per query-candidate pair).

    NaN scores are treated as -inf (counted in ``n_missing``).  ``ties="pessimistic"`` (default) or
    ``"optimistic"``.  Returns summary metrics and a per-query DataFrame with the first-hit rank."""
    import pandas as pd

    d = pd.DataFrame({"q": df[query_col].to_numpy(), "s": np.asarray(df[score_col], dtype=np.float64),
                      "h": np.asarray(df[label_col]).astype(bool)})
    n_missing = int(d["s"].isna().sum())
    d["s"] = d["s"].fillna(-np.inf)
    best = d[d["h"]].groupby("q", sort=True)["s"].max().rename("best")
    n_q = int(d["q"].nunique())
    nh = d[~d["h"]].join(best, on="q", how="inner")
    gt = (nh["s"] > nh["best"]).groupby(nh["q"]).sum()
    eq = (nh["s"] == nh["best"]).groupby(nh["q"]).sum()
    per = best.to_frame()
    per["n_greater"] = gt.reindex(per.index, fill_value=0).astype(int)
    per["n_tied"] = eq.reindex(per.index, fill_value=0).astype(int)
    if ties == "pessimistic":
        per["rank"] = 1 + per["n_greater"] + per["n_tied"]
    elif ties == "optimistic":
        per["rank"] = 1 + per["n_greater"]
    else:
        raise ValueError("ties must be 'pessimistic' or 'optimistic'")
    out = {"n_queries": n_q, "n_queries_with_hit": int(len(per)), "n_queries
… [2,428 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:04:55

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -rln \"apply_rule\" src scripts | head; python - <<'EOF'\nimport pandas as pd\nn=pd.read_parquet('data/processed/homology/node_files.parquet'); print(n.shape, n.columns.tolist()); print(n.head(3).to_string()); \nfor c in n.columns:\n    if n[c].nunique()<15: print(c, n[c].value_counts().to_dict())\nEOF\nhead -c 400 data/processed/ppi/ppil/chains.fasta; grep -c \">\" data/processed/ppi/ppil/chains.fasta", "description": "Locate homology rule and node table"}
```


**← tool result**

```
src/pocketcompare/pockets_fast.py
src/pocketcompare/pockets.py
scripts/ppi/21_ppips_homology.py
scripts/ppi/12_ppil_split_pairs.py
scripts/data/build_homology_graph.py
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ModuleNotFoundError: No module named 'pandas'
>1a28_A
QLIPPLINLLMSIEPDVIYAGHDNTKPDTSSSLLTSLNQLGERQLLSVVKWSKSLPGFRNLHIDDQITLIQYSWMSLMVFGLGWRSYKHVSGQMLYFAPDLILNEQRMKESSFYSLCLTMWQIPQEFVKLQVSQEEFLCMKVLLLLNTIPLEGLRSQTQFEEMRSSYIRELIKAIGLRQKGVVSSSQRFYQLTKLLDNLHDLVKQLHLYCLNTFIQSRALSVEFPEMMSEVIAAQLPKILAGMVKPLLFHK
>1a9u_A
ERPTFYRQELNKTIWEVPERYQNLSPVGSGAYGSVCAAFDTKTGLRVAVKKLSRPFQSIIHAKRTYRELRLLKHMKHENVIGLLDVFTPARSLEEFNDVYLVTHLMGADLNNIVKCQKLTDDHVQFLIYQIL4003
```


**→ tool call `Bash`** · 2026-10-28 05:05:00

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; grep -n \"def apply_rule\" -B3 -A30 scripts/data/build_homology_graph.py | head -60; grep -n \"apply_rule\\|easy-search\\|mmseqs\" scripts/ppi/12_ppil_split_pairs.py | head; python - <<'EOF'\nimport pandas as pd\nn=pd.read_parquet('data/processed/homology/node_files.parquet'); print(n.shape, n.columns.tolist()); print(n.head(3).to_string()); \nfor c in n.columns:\n    if n[c].nunique()<15: print(c, n[c].value_counts().to_dict())\ns=pd.read_parquet('data/splits/homology_nodes.parquet'); print(s.shape, s.columns.tolist()); print(s.head(3).to_string())\nfor c in s.columns:\n    if s[c].nunique()<15: print(c, s[c].value_counts().to_dict())\nEOF", "description": "Read homology rule and node tables"}
```


**← tool result**

```
10:  pocketdetect.datasets.leakage.apply_rule on an MMseqs2 all-vs-all (tools/mmseqs, -s 7.5, E <= 1e-3)
18:  data/sealed/ppi_l_test_pairs.parquet (chmod 000), data/processed/ppi/ppil/{mmseqs.m8,foldseek.tsv,chain_groups.parquet},
35:from pocketdetect.datasets.leakage import M8_COLUMNS, apply_rule
41:MMSEQS = ROOT / "tools/mmseqs/bin/mmseqs"
73:    m8 = PPIL / "mmseqs.m8"
75:        tmp = PPIL / "tmp_mmseqs"
88:        subprocess.run([str(FOLDSEEK), "easy-search", str(PPIL / "chains"), str(PPIL / "chains"), str(fsk), str(tmp),
102:    se = h[apply_rule(h) & (h["query"] != h["target"])]
(65437, 5) ['node_id', 'sid', 'file', 'chain', 'fs_key']
          node_id      sid                                                                                                          file chain   fs_key
0  tough_m1:11asA  s001983  /cluster/project/beltrao/gmagnus/pocket_compare/data/raw/tough_m1/extracted/TOUGH-M1_dataset/11asA/11asA.pdb     A  33363.0
1  tough_m1:13pkD  s003727  /cluster/project/beltrao/gmagnus/pocket_compare/data/raw/tough_m1/extracted/TOUGH-M1_dataset/13pkD/13pkD.pdb     D  33364.0
2  tough_m1:154lA  s030684  /cluster/project/beltrao/gmagnus/pocket_compare/data/raw/tough_m1/extracted/TOUGH-M1_dataset/154lA/154lA.pdb     A  33365.0
(65437, 19) ['node_id', 'dataset', 'uniprot', 'pdb_id', 'chain', 'chain_rule', 'pocket_ids', 'partner_of', 'af_status', 'ppi_split', 'dimer_type', 'organism', 'fs_key', 'seq_source', 'seq_len', 'sid', 'global_component', 'group_dataset', 'gro
… [1,497 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:05:09

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'EOF'\nimport pandas as pd\ne=pd.read_parquet('data/splits/homology_edges.parquet'); print(e.shape, e.dtypes.to_string()); print(e.head(3).to_string())\nfor c in e.columns:\n    if e[c].nunique()<15: print(c, e[c].value_counts().to_dict())\nn=pd.read_parquet('data/splits/homology_nodes.parquet')\nprint(n[n.dataset=='ppi_l'].head(3).to_string())\nprint(n[n.dataset=='dimers'].head(3).to_string())\nprint(n[n.dataset=='burrow_train'].head(3).to_string())\nEOF\ncat data/splits/SPLITS.md | head -80", "description": "Inspect homology edges and node examples"}
```


**← tool result**

```
(2819816, 11) sid_a           str
sid_b           str
fident      float32
alnlen        Int32
qcov        float32
tcov        float32
evalue      float32
seq_edge       bool
tm_min      float32
fs_alntm    float32
fs_edge        bool
     sid_a    sid_b  fident  alnlen  qcov   tcov  evalue  seq_edge  tm_min  fs_alntm  fs_edge
0  s000000  s000016     NaN    <NA>   NaN    NaN     NaN     False  0.5681    0.7100     True
1  s000000  s000028     1.0     352   1.0  0.986     0.0      True  0.9843    1.0010     True
2  s000000  s000135     NaN    <NA>   NaN    NaN     NaN     False  0.5091    0.7442     True
seq_edge {False: 1610573, True: 1209243}
fs_edge {True: 2492135, False: 327681}
            node_id dataset uniprot pdb_id chain chain_rule      pocket_ids partner_of af_status ppi_split dimer_type organism  fs_key seq_source  seq_len      sid  global_component group_dataset group_id
32909  ppi_l:1b8y_A   ppi_l  P08254   1b8y     A      exact  1b8y:A:IN7:502        NaN       NaN     train        NaN      NaN   46594  structure      167  s004814                 0           NaN      NaN
32910  ppi_l:1bav_A   ppi_l  P00730   1bav     A      exact  1bav:A:BIP:311        NaN       NaN      test        NaN      NaN   46719  structure      307  s001467               503           NaN      NaN
32911  ppi_l:1bl4_A   ppi_l  P62942   1bl4     A      exact  1bl4:A:AP1:108        NaN       NaN     train        NaN      NaN   47373  structure      107  s006620                 0           NaN
… [8,389 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:05:22

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'EOF'\nimport pandas as pd, numpy as np\ni=pd.read_parquet('data/processed/cache/points/ppi_l/index.parquet')\nr=i.iloc[0]; print(r.cache_file, type(r.lmode_idx), len(r.lmode_idx))\nz=np.load(r.cache_file, allow_pickle=True); print({k:(z[k].shape, z[k].dtype) for k in z.files})\nEOF\ngrep -n \"feature_names\\|bur16\\|\\\"bur\" src/pocketcompare/pockets.py | head -20", "description": "Inspect point cache npz contents"}
```


**← tool result**

```
data/processed/cache/points/ppi_l/1a28_A.npz <class 'numpy.ndarray'> 307
{'points': ((4929, 3), dtype('float32')), 'X': ((4929, 3), dtype('float32')), 'vol': ((4929,), dtype('float32')), 'is_metal': ((4929,), dtype('bool')), 'point_score': ((4929,), dtype('float32')), 'feats': ((4929, 84), dtype('float32')), 'atom_xyz': ((2019, 3), dtype('float32')), 'atom_res': ((2019,), dtype('int32')), 'atom_name': ((2019,), dtype('<U4')), 'atom_element': ((2019,), dtype('<U3')), 'res_ids': ((251,), dtype('<U16')), 'res_names': ((251,), dtype('<U5')), 'het_xyz': ((23, 3), dtype('float32')), 'het_element': ((23,), dtype('<U3')), 'het_resname': ((23,), dtype('<U5')), 'het_res': ((23,), dtype('<U16')), 'pk_score': ((40,), dtype('float64')), 'pk_center': ((40, 3), dtype('float64')), 'pk_residues': ((40,), dtype('<U161')), 'pk_indptr': ((41,), dtype('int64')), 'pk_indices': ((912,), dtype('int64')), 'pk_desc': ((40, 76), dtype('float64')), 'pk_in_v2': ((40,), dtype('bool')), 'pk_in_region': ((40,), dtype('bool')), 'feature_names': ((84,), dtype('<U32')), 'desc_names': ((76,), dtype('<U32')), 'meta': ((), dtype('<U1436'))}
104:    feature_names: list
138:        return self.feats[:, self.feature_names.index(name)]
182:        arrs["feature_names"] = np.asarray(self.feature_names, dtype="U32")
198:            kw["feature_names"] = z["feature_names"].tolist()
303:        feats=np.ascontiguousarray(ps.feats, np.float32), feature_names=list(ps.names),
353:                        bur_feature: str = "
… [477 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:05:48

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 464,530p src/pocketcompare/evaluate.py; sed -n 584,640p src/pocketcompare/evaluate.py; grep -n \"def fs_embed\" -A30 scripts/eval_dev.py; grep -n \"^def \\|^class \" src/pocketcompare/descriptors/esm_pocket.py", "description": "Read bootstrap weights, fs_embed, esm helpers"}
```


**← tool result**

```
def _encode_clusters(ci, cj):
    ci, cj = np.asarray(ci), np.asarray(cj)
    if ci.shape != cj.shape or ci.ndim != 1:
        raise ValueError("ci and cj must be 1-D of equal length")
    codes, uniq = _factorize(np.concatenate([ci, cj]))
    n = len(ci)
    return codes[:n].astype(np.int64), codes[n:].astype(np.int64), len(uniq)


def pair_bootstrap_weights(counts, a, b, w):
    """Replicate pair weights: w * n_a * n_b for a != b, w * n_a for within-unit pairs (a == b)."""
    ca = counts[a]
    return np.where(a == b, ca, ca * counts[b]) * w


def bootstrap_counts(n_clusters: int, B: int = DEFAULT_B, seed=DEFAULT_SEED):
    """Yield (start, counts[chunk, K]) unit draw counts; deterministic given (K, B, seed).

    ``seed`` is anything ``numpy.random.default_rng`` accepts (int or list of ints)."""
    rng = np.random.default_rng(seed)
    p = np.full(n_clusters, 1.0 / n_clusters)
    for start in range(0, B, _CHUNK):
        b = min(_CHUNK, B - start)
        yield start, rng.multinomial(n_clusters, p, size=b).astype(np.float64)


if HAVE_NUMBA:
    @njit(parallel=True, cache=True)
    def _boot_kernel(cnt, ci_s, cj_s, w_s, y_s, end_s, out_auc, out_ap, offset):  # pragma: no cover (jit)
        nb = cnt.shape[0]
        nm, n = ci_s.shape
        for b in prange(nb):
            row = cnt[b]
            for m in range(nm):
                tp = 0.0
                fp = 0.0
                pg = 0.0
                ng = 0.0
                bad = 0.0
                ap = 0.0
  
… [5,481 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:05:53

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 1,140p src/pocketcompare/descriptors/esm_pocket.py; sed -n \"$(grep -n '^def main_generic' scripts/compute_esm.py | cut -d: -f1),+50p\" scripts/compute_esm.py", "description": "Read ESM pocket helpers and generic driver"}
```


**← tool result**

```
"""B4: ESM-2 (650M) pocket embedding = mean of per-residue embeddings over the pocket's lining residues.

* Sequence per chain is read from the structure file with gemmi (amino-acid residues in file order, first
  altloc, waters/ligands ignored; unknown residue -> X).  Lining residues use author numbering
  ``chain:resnum[icode]`` and are mapped to sequence indices through the gemmi residue list, never by
  assuming numbering starts at 1.  If the chain letter is absent and the file has exactly one protein chain
  (the adapter's single-chain remap, see reports/pocket_adapter.md) that chain is used.
* Chains are embedded separately.  Chains > 1022 residues: windows of 1022 with stride 511 (overlap 511,
  last window aligned to the chain end); per-residue embeddings are averaged over all windows covering them.
* Embedding = last hidden layer (after final layer norm), BOS/EOS removed, cached as fp16 per unique sequence
  (sha1 of sequence) under data/processed/esm/<model>/<sha1>.npy, so identical chains are shared.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

MODEL = "facebook/esm2_t33_650M_UR50D"
MODEL_TAG = "esm2_t33_650M_UR50D"
MAXLEN = 1022
STRIDE = 511
DIM = 1280


def chain_residues(path) -> dict:
    """{chain: (sequence, [resid strings 'num[icode]'])} for amino-acid residues of model 1."""
    import gemmi
    st = gemmi.read_structure(str(path))
    st.setup_entities()
    out = {}
    for ch in st[0]:
        seq, 
… [5,890 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:05:58

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python -c \"\nimport pandas as pd\nd=pd.read_parquet('data/splits/ppi_l_pockets.parquet'); print(d.lining_residues.iloc[0][:100]); print(d.structure_path.iloc[0]); print(d.group.value_counts().head()); print(d[d.split!='test'].group.nunique())\nb=pd.read_parquet('data/processed/cache/points/blips/index.parquet'); print(b.lining_residues.iloc[0][:100])\n\"", "description": "Check residue formats and group counts"}
```


**← tool result**

```
A:162 A:163 A:164 A:165 A:166 A:167 A:197 A:198 A:201 A:202 A:205 A:210 A:211 A:215 A:216 A:217 A:21
/cluster/scratch/jjaenes/pdb/b8/1b8y.cif.gz
group
1wug_A    488
1a9u_A    367
1btu_A    216
2bkt_A    186
3ijc_A     92
Name: count, dtype: int64
67
A:62 A:63 A:515 A:529 A:531 A:532 A:533 A:534 A:535 A:548 A:559 A:560
```


**→ tool call `Write`** · 2026-10-28 05:06:10

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/exploratory/ppi_r_esm.py", "content": "#!/usr/bin/env python\n\"\"\"EXPLORATORY (post-test). B4 ESM-2 L-mode pocket embeddings for PPI-L TRAIN+VAL pockets only (PPI-R task).\n\nSame recipe as scripts/compute_esm.py (generic branch): ESM-2 650M last layer, mean over the L-mode lining residues\n(data/splits/ppi_l_pockets.parquet ``lining_residues``), chains embedded separately, sequence-hash cache shared with\nthe project cache.  PPI-L test pockets are not processed.  Output: data/processed/exploratory/ppi_r/b4_esm2_L_ppil.npz\n\"\"\"\nimport sys\nimport time\nfrom pathlib import Path\n\nimport numpy as np\nimport pandas as pd\n\nROOT = Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / \"src\"))\nfrom pocketcompare.descriptors import esm_pocket as ep  # noqa: E402\n\n\ndef main(device=\"cuda:1\"):\n    t0 = time.time()\n    P = pd.read_parquet(ROOT / \"data/splits/ppi_l_pockets.parquet\")\n    P = P[P.split.isin([\"train\", \"val\"])].reset_index(drop=True)\n    emb = ep.ESMEmbedder(device, ROOT / \"data/processed/esm\")\n    L = np.full((len(P), ep.DIM), np.nan, np.float32)\n    err = [None] * len(P)\n    for k_s, (path, g) in enumerate(P.groupby(\"structure_path\", sort=True)):\n        try:\n            chains = ep.chain_residues(path)\n            need = {x.partition(\":\")[0] for res in g.lining_residues for x in str(res).split()}\n            chains = {c: v for c, v in chains.items() i
… [935 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/exploratory/ppi_r_esm.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 05:06:13

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; python scripts/exploratory/ppi_r_esm.py cuda:1 > logs/ppi_r_esm.log 2>&1", "description": "Compute ESM embeddings for PPI-L train/val pockets", "run_in_background": true}
```


**← tool result**

```
Command running in background with ID: bjzwtp5lj. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bjzwtp5lj.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
Session cwd remains /cluster/project/beltrao/gmagnus/pocket_compare; directory changes made by the backgrounded command do not apply to subsequent commands.
```


**→ tool call `Bash`** · 2026-10-28 05:06:30

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 1,75p src/pocketcompare/descstore.py; grep -n \"^class ZScorer\" -A25 scripts/eval_dev.py; grep -n \"^def embed\\b\\|^def embed(\" -A15 scripts/eval_dev.py; sed -n 1,60p scripts/eval_dev.py | grep -n \"import\\|^ROOT\\|sys.path\"", "description": "Read DescriptorStore and ZScorer"}
```


**← tool result**

```
"""Read-only access to precomputed, label-free pocket descriptors (data/processed/descriptors/<dataset>/).

Used by scripts/final_eval.py and by final-method plug-ins (``pocketcompare.method``) so that every arm reads its
inputs the same way.  Rows are looked up by pocket id (never by position), missing pockets give NaN rows.

    store = DescriptorStore(root)
    M = store.matrix("tough_m1", "a1_pair_only_L", pocket_ids)        # <arm>_<config>_<mode>.npy + .ids.parquet
    M = store.matrix("tough_m1", "b4_esm2_D", pocket_ids)             # b4_esm2_{L,D}.npy + b4_esm2_ids.parquet
    M = store.matrix("tough_m1", "n_inputs_L:a1_sph8", pocket_ids)    # n_inputs_{L,D}.npz block + n_inputs_ids
    lay = store.layout("tough_m1", "a1_default_L")                    # block layout (json) or None
    store.inputs                                                      # every file read (for provenance)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


class DescriptorStore:
    def __init__(self, root):
        self.root = Path(root)
        self.base = self.root / "data/processed/descriptors"
        self.inputs: list[Path] = []
        self._ids: dict = {}
        self._arr: dict = {}

    def _files(self, dataset: str, stem: str):
        d = self.base / dataset
        if stem.startswith("n_inputs_"):
            mode, _, block = stem[len("n_inputs_"):].partition(":")
            return d / f"n_inputs_{mode}.npz", 
… [1,880 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:06:34

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -n \"ZScorer\\|^def embed\\|^from\\|^import\" scripts/eval_dev.py | head -30; grep -rn \"class ZScorer\" -A20 src/pocketcompare/similarity.py | head -30; grep -n \"^def \\|^class \" src/pocketcompare/similarity.py", "description": "Locate ZScorer and embed helpers"}
```


**← tool result**

```
103:from __future__ import annotations
105:import argparse
106:import json
107:import multiprocessing as mp
108:import os
109:import sys
110:import time
111:from dataclasses import dataclass, field
112:from pathlib import Path
114:import numpy as np
115:import pandas as pd
120:from pocketcompare import evaluate as ev  # noqa: E402
121:from pocketcompare.provenance import append_trial, git_state, sha256_file, write_result  # noqa: E402
122:from pocketcompare.seeds import SEEDS  # noqa: E402
123:from pocketcompare.similarity import ZScorer, csls_r, embed, pair_scores  # noqa: E402
370:    zs = ZScorer.fit(M[rows]) if zscore else None
1368:        zs = ZScorer.fit(M[ds.train]) if zscore else None
1867:        Er = embed(M[pp_ref], ZScorer.fit(M[pp.train]))
src/pocketcompare/similarity.py:23:class ZScorer:
src/pocketcompare/similarity.py-24-    mean: np.ndarray
src/pocketcompare/similarity.py-25-    std: np.ndarray            # 0 marks a constant dimension in the reference set (mapped to 0)
src/pocketcompare/similarity.py-26-    n_ref: int
src/pocketcompare/similarity.py-27-    clip: float | None = None
src/pocketcompare/similarity.py-28-
src/pocketcompare/similarity.py-29-    @classmethod
src/pocketcompare/similarity.py-30-    def fit(cls, D, ids=None, ref_ids=None, clip: float | None = None) -> "ZScorer":
src/pocketcompare/similarity.py-31-        """Statistics over the rows of ``D`` whose id is in ``ref_ids`` (all rows if ``ref_ids`` is None).
src/pocketcompare/similarity.py-3
… [1,460 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-28 05:07:42

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/exploratory/ppi_r.py", "content": "#!/usr/bin/env python\n\"\"\"EXPLORATORY (post-test) — PPI-R: ligand-grounded PPI-modulator-pocket retrieval (proposed in D7).\n\nPROTOCOL (declared 2026-10-28 ~06:20, before any similarity score was computed; nothing below was changed after\nseeing scores — any later addition is marked \"ADDED AFTER SCORES\")\n---------------------------------------------------------------------------------------------------------------\nQuestion: does a pocket fingerprint recognise \"PPI-modulator-pocket-ness\" across protein families, i.e. do the\nneighbours of a PPI-modulator pocket from OTHER homology groups tend to be PPI-modulator pockets rather than\nordinary (non-PPI) ligand pockets of the same size and buriedness?\n\nPositives / queries (P): PPI-L primary pockets (data/splits/ppi_l_pockets.parquet; Pasteur pocketome, PLOC +\n  PLONC, L mode = 4 Å shell of the modulator) with split in {train, val} and an L-mode descriptor (a1r has_L).\n  PPI-L test pockets are dropped on load; data/sealed/ is never opened (no pair table is read at all).\nBackground (N): BLiPS v2 sites (data/splits/blips_sites_v2.parquet) with partition in {train, val}, L mode\n  (ligand shell), L-mode descriptor available, and NO direct homology edge to ANY PPI-L chain (all PPI-L\n  splits; global graph data/splits/homology_edges.parquet: MMseqs2 leakage rule OR Foldseek min-TM >= 0.5, plus\n  identical sequences
… [16,583 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/exploratory/ppi_r.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 05:07:48

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; tail -2 logs/ppi_r_esm.log; tail -c 300 logs/dimer_atlas_shard0.log; cd scripts/exploratory && time python -c \"\nimport ppi_r, json\nP=ppi_r.ppil_pool(); N,ni=ppi_r.blips_pool(); print(len(P), P.group.nunique(), ni)\nu,m,b=ppi_r.match(P,N); print(json.dumps(b,indent=1))\n\"", "description": "Check pools and matching balance (no scores)"}
```


**← tool result**

```
1600 86s
done 1806 pockets, 1806 embedded, 90s
1806 67 {'blips_trainval_L_ok': 2841, 'excluded_homologous_to_ppil': 11, 'pool': 2830}
{
 "covariates": [
  "log_volume_A3_L",
  "mean_bur16_L"
 ],
 "caliper_sd": 0.25,
 "n_ppi": 1806,
 "n_pool": 2830,
 "n_matched": 1272,
 "smd_before": [
  0.04117787768503399,
  0.5687715408232364
 ],
 "smd_after": [
  0.05996935292293128,
  -0.09422390680869261
 ],
 "smd_after_matched_ppi_only": [
  7.361769179546976e-05,
  -0.002517398949450294
 ],
 "median_volume_ppi_bg_pool_bg_matched": [
  651.0,
  635.0,
  628.5
 ],
 "median_bur16_ppi_bg_pool_bg_matched": [
  0.7819878458976746,
  0.7462936341762543,
  0.8037776947021484
 ]
}

real	1m31.609s
user	0m36.301s
sys	0m1.900s
```


**→ tool call `Bash`** · 2026-10-28 05:09:31

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'EOF'\nimport pandas as pd\nS=pd.read_parquet('data/splits/blips_sites_v2.parquet'); S=S[S.partition.isin(['train','val'])]\nnodes=pd.read_parquet('data/splits/homology_nodes.parquet',columns=['node_id','dataset','sid','uniprot'])\nprint(S.node_id.isin(nodes.node_id).mean())\nps=set(nodes.sid[nodes.dataset=='ppi_l']); print(len(ps))\nE=pd.read_parquet('data/splits/homology_edges.parquet',columns=['sid_a','sid_b','seq_edge','fs_edge'])\nprint('edges touching ppil', (E.sid_a.isin(ps)|E.sid_b.isin(ps)).sum())\nP=pd.read_parquet('data/splits/ppi_l_pockets.parquet'); \n# uniprot overlap\nbu=set(S.uniprot); pu=set(P.uniprot); print('uniprot overlap', len(bu&pu))\n# p38a Q16539 ; BRD4 O60885\nprint(S[S.uniprot.str.contains('Q16539|O60885|P00760|P24941')][['site_id','uniprot']].head())\nprint(P.pfam_name.value_counts().head(10))\nEOF", "description": "Verify homology exclusion of BLiPS vs PPI-L"}
```


**← tool result**

```
1.0
1074
edges touching ppil 555407
uniprot overlap 5
Empty DataFrame
Columns: [site_id, uniprot]
Index: []
pfam_name
Bromodomain       325
Trypsin           180
Pkinase           178
Asp                94
PK_Tyr_Ser-Thr     45
Peptidase_M10      44
RVP                33
Y_phosphatase      28
Ras                27
Lipocalin          27
Name: count, dtype: int64
```


**→ tool call `Bash`** · 2026-10-28 05:09:38

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; for s in 0 1; do grep -E \"structures \\(|Elapsed|Maximum resident|Percent of CPU\" logs/dimer_atlas_shard$s.log; done; cat data/processed/dimer_atlas/start_epoch data/processed/dimer_atlas/end_epoch; ls -la data/processed/dimer_atlas", "description": "Check dimer run logs and throughput"}
```


**← tool result**

```
7923 structures (0 errors), 68888 pockets -> data/processed/dimer_atlas/shard0.parquet  [343.0 s wall, 0.043 s/structure; cuda:0, backend fast, 11 workers]
	Percent of CPU this job got: 3199%
	Elapsed (wall clock) time (h:mm:ss or m:ss): 5:47.10
	Maximum resident set size (kbytes): 43208416
7238 structures (0 errors), 58936 pockets -> data/processed/dimer_atlas/shard1.parquet  [308.6 s wall, 0.043 s/structure; cuda:1, backend fast, 11 workers]
	Percent of CPU this job got: 2833%
	Elapsed (wall clock) time (h:mm:ss or m:ss): 5:13.45
	Maximum resident set size (kbytes): 36828452
1793163818
1793164165
total 190748
drwxr-sr-x  2 gmagnusson nogroup      4096 Oct 28 06:09 .
drwxr-sr-x 19 gmagnusson nogroup      4096 Oct 28 06:07 ..
-rw-r--r--  1 gmagnusson nogroup        11 Oct 28 06:09 end_epoch
-rw-r--r--  1 gmagnusson nogroup 104497996 Oct 28 06:09 shard0.parquet
-rw-r--r--  1 gmagnusson nogroup    361617 Oct 28 06:09 shard0.structures.parquet
-rw-r--r--  1 gmagnusson nogroup  89334631 Oct 28 06:08 shard1.parquet
-rw-r--r--  1 gmagnusson nogroup    329806 Oct 28 06:08 shard1.structures.parquet
-rw-r--r--  1 gmagnusson nogroup        11 Oct 28 06:03 start_epoch
```


**→ tool call `Bash`** · 2026-10-28 05:09:45

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache OMP_NUM_THREADS=8 NUMBA_NUM_THREADS=8; python scripts/exploratory/ppi_r.py > logs/ppi_r.log 2>&1", "description": "Run PPI-R retrieval evaluation", "run_in_background": true}
```


**← tool result**

```
Command running in background with ID: bxus0neu8. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bxus0neu8.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
Session cwd remains /cluster/project/beltrao/gmagnus/pocket_compare; directory changes made by the backgrounded command do not apply to subsequent commands.
```


**→ tool call `Bash`** · 2026-10-28 05:10:02

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; head -3 /cluster/project/beltrao/gmagnus/dimers/afdb_human_dimers/heterodimers/download_manifest.csv; head -3 /cluster/project/beltrao/gmagnus/dimers/afdb_human_dimers/heterodimers/candidates.csv | cut -c1-600; head -3 data/processed/dimers/manifest.tsv", "description": "Inspect dimer manifests"}
```


**← tool result**

```
modelEntityId,uniprotAccession_1,uniprotAccession_2,gene_1,gene_2,ipTM,max_ipSAE,max_pDockQ2,n_residues,status,detail,source_url,output_file
AF-0000000210364413,O00203,Q92572,AP3B1,AP3S1,0.784000,0.773833,0.516294,1287,downloaded,download ok,https://alphafold.ebi.ac.uk/files/AF-0000000210364413-model_v1.pdb,afdb_human_dimers/heterodimers/AF-0000000210364413.pdb
AF-0000000210488870,O75838,Q7Z5M5,CIB2,TMC3,0.911100,0.697650,0.432326,1287,downloaded,download ok,https://alphafold.ebi.ac.uk/files/AF-0000000210488870-model_v1.pdb,afdb_human_dimers/heterodimers/AF-0000000210488870.pdb
modelEntityId,uniprotAccession_1,uniprotAccession_2,gene_1,gene_2,ipTM,max_ipSAE,max_pDockQ2,n_residues
AF-0000000210364413,O00203,Q92572,AP3B1,AP3S1,0.784000,0.773833,0.516294,1287
AF-0000000210488870,O75838,Q7Z5M5,CIB2,TMC3,0.911100,0.697650,0.432326,1287
modelEntityId	uniprotAccession_1	uniprotAccession_2	gene_1	gene_2	ipTM	max_ipSAE	max_pDockQ2	n_residues	organism	type	path	n_models_or_chains	chains	n_atoms	bfac_const_per_res	bfac_min	bfac_max	chain_A	acc_A_dbref	len_A	num_A	num_contig_A	plddt_A	f_pl50_A	f_pl70_A	n_iface_A	chain_B	acc_B_dbref	len_B	num_B	num_contig_B	plddt_B	f_pl50_B	f_pl70_B	n_iface_B	iface_plddt	n_iface	same_seq	acc_match
AF-0000000065760335	P31946	P31946	YWHAB	YWHAB	0.86	0.820317	0.867488	492	human	homo	/cluster/project/beltrao/gmagnus/dimers/afdb_human_dimers/homodimers/AF-0000000065760335.pdb	2	AB	3936	True	23.2	98.88	A	P31946	246	1-246	True	91.96878048780488	0.048780487
… [546 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:10:28

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python -c \"\nimport importlib\nfor m in ['igraph','leidenalg','networkx','faiss','sklearn']:\n    try: importlib.import_module(m); print(m,'ok')\n    except Exception as e: print(m,'NO')\nimport pandas as pd\nn=pd.read_parquet('data/splits/homology_nodes.parquet')\nprint(n[n.dataset=='ppi_l'].pocket_ids.head(5).tolist())\nd=n[n.dataset=='dimers']; print(d.node_id.head(2).tolist(), d.group_id.nunique(), d.fs_key.notna().sum())\nm=pd.read_csv('data/processed/dimers/manifest.tsv',sep='\\t'); print(len(m), m.modelEntityId.nunique())\n\"; tail -3 logs/ppi_r.log", "description": "Check libs, node formats, manifest uniqueness"}
```


**← tool result**

```
igraph NO
leidenalg NO
networkx ok
faiss ok
sklearn ok
['1b8y:A:IN7:502', '1bav:A:BIP:311', '1bl4:A:AP1:108', '1bp4:A:ALD:301', '1btu:A:2BL:7']
['dimers:AF-0000000065760335_A', 'dimers:AF-0000000065760335_B'] 3928 30322
15161 15161
| FINAL-B4 | group_balanced | +0.073 [+0.021, +0.125] p=0.007 | +0.015 [-0.019, +0.048] | -0.121 [-0.228, -0.013] | -0.081 [-0.165, -0.002] |
| FINAL-B0 | query_mean | +0.039 [-0.024, +0.078] p=0.107 | +0.033 [-0.013, +0.062] | -0.060 [-0.163, +0.004] | +0.004 [-0.089, +0.059] |
| FINAL-B0 | group_balanced | +0.019 [-0.005, +0.042] p=0.062 | +0.018 [-0.001, +0.036] | -0.106 [-0.179, -0.031] | -0.033 [-0.083, +0.015] |
```


**→ tool call `Bash`** · 2026-10-28 05:10:35

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -v \"^ \\|^{\\|^}\" logs/ppi_r.log | head -60; cat results/exploratory/ppi_r/per_group.tsv | head -25; python -c \"\nimport json; s=json.load(open('results/exploratory/ppi_r/summary.json')); print(s['by_label_final_query_mean'], s['wall_s'])\"", "description": "Read PPI-R results"}
```


**← tool result**

```
common-set availability 3078 / 3078
FINAL {'auc': 0.552, 'ap': 0.587, 'p@10': 0.518, 'p@50': 0.549, 'prev': 0.549} 35s
N1 {'auc': 0.562, 'ap': 0.59, 'p@10': 0.53, 'p@50': 0.553, 'prev': 0.549} 37s
B1 {'auc': 0.493, 'ap': 0.544, 'p@10': 0.429, 'p@50': 0.466, 'prev': 0.549} 38s
B4 {'auc': 0.542, 'ap': 0.612, 'p@10': 0.736, 'p@50': 0.726, 'prev': 0.549} 39s
B0 {'auc': 0.513, 'ap': 0.554, 'p@10': 0.578, 'p@50': 0.545, 'prev': 0.549} 41s
BUR {'auc': 0.512, 'ap': 0.552, 'p@10': 0.513, 'p@50': 0.513, 'prev': 0.549} 42s
RANDOM {'auc': 0.5, 'ap': 0.55, 'p@10': 0.551, 'p@50': 0.55, 'prev': 0.549} 43s
# PPI-R (EXPLORATORY, post-test; PPI-L train+val only)

queries 1806 in 67 PPI-L groups; pool 3078 = 1806 PPI + 1272 matched BLiPS background

| arm | weighting | AUC [95% CI] | AP | P@10 | P@50 | prevalence |
|---|---|---|---|---|---|---|
| FINAL | query_mean | 0.552 [0.495, 0.590] | 0.587 [0.564, 0.612] | 0.518 [0.423, 0.596] | 0.549 [0.474, 0.604] | 0.549 |
| FINAL | group_balanced | 0.536 [0.511, 0.559] | 0.607 [0.588, 0.626] | 0.503 [0.434, 0.571] | 0.543 [0.493, 0.592] | 0.583 |
| N1 | query_mean | 0.562 [0.503, 0.603] | 0.590 [0.567, 0.620] | 0.530 [0.428, 0.611] | 0.553 [0.472, 0.619] | 0.549 |
| N1 | group_balanced | 0.546 [0.519, 0.573] | 0.618 [0.597, 0.639] | 0.478 [0.414, 0.544] | 0.538 [0.480, 0.596] | 0.583 |
| B1 | query_mean | 0.493 [0.436, 0.536] | 0.544 [0.519, 0.579] | 0.429 [0.338, 0.525] | 0.466 [0.381, 0.556] | 0.549 |
| B1 | group_balanced | 0.497 [0.474, 0.519] | 0
… [3,876 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-28 05:11:55

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/exploratory/dimer_atlas.py", "content": "#!/usr/bin/env python\n\"\"\"EXPLORATORY (post-test) — AFDB dimer interface-pocket atlas: a DEMO, not an evaluation.\n\nInput: fingerprints of all merged BURROW pockets (>= 10 points) of the 15,161 AFDB dimers\n(scripts/exploratory/dimer_atlas_describe.sh: `pocketcompare describe --af-mode`, final method, fast GPU backend).\nPPIPS caches were NOT reused: the full run took ~6 min, so one consistent run was simpler.\n\nDeclared before looking at any search result:\n* Interface pocket: f_min >= 0.25 (share of the pocket's BURROW output residues on the minority chain;\n  reports/ppi_dimers.md) and >= 10 points (all describe_all pockets have >= 10) and a non-zero fingerprint.\n* Reference sets (FINAL fingerprints from the stored N1 parts; D mode = best sub-pocket covering the ligand where\n  BURROW matched the site, else L mode, flagged): PPI-L modulator pockets (PLOC+PLONC, ALL splits — allowed because\n  this is a demo, not an evaluation; only the pocket table is read, never a sealed pair file) and BLiPS\n  train/val ligand pockets (non-PPI background).\n* \"Close neighbour\": cosine above tau_pair = 99th percentile of the background distribution = cosine of random\n  (interface pocket, BLiPS ligand pocket) pairs (2 M sampled pairs).  Because the max over many references exceeds\n  a pairwise percentile easily, the same count is reported for an equal-size random BLiPS 
… [17,175 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/exploratory/dimer_atlas.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 05:12:00

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache OMP_NUM_THREADS=16; python scripts/exploratory/dimer_atlas.py > logs/dimer_atlas.log 2>&1", "description": "Run dimer atlas analysis", "run_in_background": true}
```


**← tool result**

```
Command running in background with ID: bmaf93uei. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bmaf93uei.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
Session cwd remains /cluster/project/beltrao/gmagnus/pocket_compare; directory changes made by the backgrounded command do not apply to subsequent commands.
```


**→ tool call `Bash`** · 2026-10-28 05:12:15

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; cat > scripts/exploratory/ppi_r_diag.py <<'EOF'\n#!/usr/bin/env python\n\"\"\"EXPLORATORY (post-test) PPI-R diagnostic — ADDED AFTER SCORES (not in the declared protocol).\nAmong each query's top-10 candidates that are PPI-L pockets (other homology groups), the share with the same Pfam\nfamily as the query (remote-homology / same-family signal the PPI-L homology groups did not merge) and the share\nwith the same ligand cluster.  Arms FINAL and B4 (+ B1).\"\"\"\nimport json, sys\nfrom pathlib import Path\nimport numpy as np, pandas as pd\nROOT = Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / \"src\")); sys.path.insert(0, str(ROOT / \"scripts/exploratory\"))\nimport ppi_r  # noqa: E402\nT = pd.read_parquet(ROOT / \"data/processed/exploratory/ppi_r/ppi_r_pool.parquet\")\nP = pd.read_parquet(ROOT / \"data/splits/ppi_l_pockets.parquet\").set_index(\"pocket_id\")\npf = T.pocket_id.map(P.pfam_name).fillna(\"\").to_numpy()\nlc = T.pocket_id.map(P.ligand_cluster).to_numpy()\nEmb = ppi_r.embeddings(T)\nisP = (T.set == \"PPI\").to_numpy(); grp = T.group.to_numpy()\nq = np.flatnonzero(isP)\nout = {}\nfor a in (\"FINAL\", \"B4\", \"B1\"):\n    S = Emb[a][q] @ Emb[a].T\n    same_pf, same_lc, ppi10 = [], [], []\n    for k, i in enumerate(q):\n        s = S[k].copy(); s[i] = -np.inf; s[isP & (grp == grp[i])] = -np.inf\n        top = np.argso
… [884 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{
 "FINAL": {
  "p@10": 0.5179955703211517,
  "share_top10_ppi_hits_same_pfam": 0.0,
  "share_top10_ppi_hits_same_ligand_cluster": 0.0005263157894736842
 },
 "B4": {
  "p@10": 0.7357142857142858,
  "share_top10_ppi_hits_same_pfam": 0.0,
  "share_top10_ppi_hits_same_ligand_cluster": 0.0007548685559156763
 },
 "B1": {
  "p@10": 0.42862679955703215,
  "share_top10_ppi_hits_same_pfam": 0.0,
  "share_top10_ppi_hits_same_ligand_cluster": 0.0008998435054773082
 },
 "chance_same_pfam_among_other_group_ppi": 1.82292819992442e-06
}
```


**→ tool call `Bash`** · 2026-10-28 05:12:24

```
{"command": "sleep 60; tail -5 /cluster/project/beltrao/gmagnus/pocket_compare/logs/dimer_atlas.log", "description": "Check atlas analysis progress"}
```


**← tool result**

```
<tool_use_error>Blocked: sleep 60 followed by: tail -5 /cluster/project/beltrao/gmagnus/pocket_compare/logs/dimer_atlas.log. To wait for a condition, use Monitor with an until-loop (e.g. `until <check>; do sleep 2; done`). To wait for a command you started, use run_in_background: true. Do not chain shorter sleeps to work around this block.</tool_use_error>
```


**→ tool call `Bash`** · 2026-10-28 05:12:26

```
{"command": "tail -5 /cluster/project/beltrao/gmagnus/pocket_compare/logs/dimer_atlas.log", "description": "Check atlas analysis log"}
```


**← tool result**

```
(Bash completed with no output)
```


**→ tool call `ToolSearch`** · 2026-10-28 05:12:30

```
{"query": "select:Monitor", "max_results": 1}
```


**← tool result**

```
[non-text content]
```


**→ tool call `Monitor`** · 2026-10-28 05:12:33

```
{"command": "tail -f /cluster/project/beltrao/gmagnus/pocket_compare/logs/dimer_atlas.log | grep -E --line-buffered \"indices|Traceback|Error|close_hits_homology|n_clusters\"", "description": "dimer atlas analysis progress/errors", "timeout_ms": 900000}
```


**← tool result**

```
Monitor started (task bn6kqfv2f, expires in 15m unless the source ends first; you get one notice at expiry — re-arm if you still need the watch). You will be notified on each event. Keep working — do not poll or sleep. Events may arrive while you are waiting for the user — an event is not their reply.
```


**→ tool call `Bash`** · 2026-10-28 05:12:37

```
{"command": "cat /cluster/project/beltrao/gmagnus/pocket_compare/results/exploratory/ppi_r/matching.json | head -5; ls /cluster/project/beltrao/gmagnus/pocket_compare/data/processed/dimer_atlas", "description": "Check atlas outputs so far"}
```


**← tool result**

```
{
 "covariates": [
  "log_volume_A3_L",
  "mean_bur16_L"
 ],
atlas_all_pockets.parquet
atlas_interface_pockets.parquet
end_epoch
index_all_ivfpq
index_interface_flat
shard0.parquet
shard0.structures.parquet
shard1.parquet
shard1.structures.parquet
start_epoch
```


**→ tool call `Bash`** · 2026-10-28 05:12:40

```
{"command": "until grep -qE \"Traceback|close_hits_homology\" /cluster/project/beltrao/gmagnus/pocket_compare/logs/dimer_atlas.log; do sleep 5; done; grep -E \"indices|Traceback|Error\" -A3 /cluster/project/beltrao/gmagnus/pocket_compare/logs/dimer_atlas.log | head", "description": "Wait for atlas search stage", "run_in_background": true}
```


**← tool result**

```
Command running in background with ID: b2k6371xm. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/b2k6371xm.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
```


**→ tool call `Bash`** · 2026-10-28 05:12:43

```
{"command": "until grep -qE \"Traceback|close_hits_homology\" /cluster/project/beltrao/gmagnus/pocket_compare/logs/dimer_atlas.log; do sleep 5; done; echo done", "description": "Block until atlas search stage finishes", "timeout": 600000}
```


**← tool result**

```
done
```


**→ tool call `Bash`** · 2026-10-28 05:21:40

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -v \"^indices\" logs/dimer_atlas.log | head -150; python -c \"\nimport json; s=json.load(open('results/exploratory/dimer_atlas/summary.json')); [print(k, s[k]) for k in s if k not in ('close_neighbour','close_hits_homology','clusters')]\"", "description": "Read atlas results"}
```


**← tool result**

```
{
 "interface": {
  "n": 32473,
  "nn_modulator_gt_tau_pair": 27572,
  "frac_nn_modulator_gt_tau_pair": 0.8490746158346935,
  "frac_nn_blips_equal_size_gt_tau_pair": 0.9276013919255998,
  "tau_nn_p99_of_nn_to_blips_equal_size": 0.8812569975852966,
  "nn_modulator_gt_tau_nn": 16,
  "frac_nn_modulator_gt_tau_nn": 0.0004927170264527453,
  "median_nn_cos_modulator": 0.6680482625961304,
  "median_nn_cos_blips_equal_size": 0.7043315172195435,
  "frac_modulator_nn_beats_blips_nn": 0.30616204231207467
 },
 "non_interface_control": {
  "n": 95351,
  "frac_nn_modulator_gt_tau_pair": 0.8709924384642007,
  "frac_nn_blips_equal_size_gt_tau_pair": 0.9434195760925423,
  "frac_nn_modulator_gt_tau_nn": 0.0018248366561441412,
  "frac_modulator_nn_beats_blips_nn": 0.2803012029239337
 }
}
{
 "close_hits_homology": {
  "n_close": 27572,
  "hom_to_matched_target": 231,
  "same_uniprot": 7,
  "non_homologous": 27341,
  "n_close_strict": 16,
  "strict_non_homologous": 14,
  "dimers_with_close_hit": 12281,
  "frac_iface_hom_to_any_ppil": 0.09992917192744742
 },
 "clusters": {
  "method": "Louvain on top-10 other-structure neighbours with cos >= tau_pair",
  "n_edges": 243415,
  "n_clusters": 29,
  "n_singletons": 6,
  "n_clusters_ge10": 23,
  "frac_pockets_in_ge10": 0.9998152311150802,
  "n_cross_family_ge10fam_share_lt0.3": 14,
  "largest": 6468,
  "knn_s": 0.8097560405731201,
  "cluster_s": 12.617684125900269
 }
}
                    pair organism    type    ipTM  max_ipSAE     f_min  plddt_mean  n
… [7,561 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:22:03

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; date; cat > scripts/exploratory/dimer_atlas_clusters2.py <<'EOF'\n#!/usr/bin/env python\n\"\"\"EXPLORATORY (post-test) demo — ADDED AFTER the first clustering (dimer_atlas.py) gave 29 coarse Louvain\ncommunities (largest 6,468) because the cos >= tau_pair (0.59) kNN graph is almost fully connected.\nStricter graph: MUTUAL top-10 neighbours (other structures) with cosine >= 0.80 (> p99.9 of interface x BLiPS\npairs, 0.72); Louvain (seed 0, resolution 1).  Cross-family = >= 5 distinct chain-group families and no family\n> 30 % of members.  Symmetric homodimer copies sit in the same structure and are not linked.\"\"\"\nimport json, sys, time\nfrom pathlib import Path\nimport numpy as np, pandas as pd\nROOT = Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / \"src\"))\nfrom pocketcompare import fpindex as FX  # noqa: E402\nimport faiss, networkx as nx  # noqa: E402\nD = ROOT / \"data/processed/dimer_atlas\"; OUT = ROOT / \"results/exploratory/dimer_atlas\"\nt0 = time.time()\nM, V, _ = FX.read_table(D / \"atlas_interface_pockets.parquet\")\nC = pd.read_parquet(D / \"interface_clusters.parquet\")\nassert (C.pocket_id.to_numpy() == M.pocket_id.to_numpy()).all()\nix = faiss.IndexFlatIP(V.shape[1]); ix.add(V)\nDk, Ik = ix.search(V, 31)\nst = M.structure_stem.to_numpy()\nnb = []\nfor i in range(len(V)):\n    s = [(int(j), float(d)) for j, d in zip(Ik[i], Dk[i]) if j != i and st[j] != st[i]][:10]\n    nb.a
… [2,303 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Wed Oct 28 06:22:03 CET 2026
{
 "EXPLORATORY": true,
 "added_after_first_clustering": true,
 "n_edges": 37531,
 "n_pockets_with_edge": 19503,
 "n_clusters_total": 14932,
 "n_singletons": 12970,
 "n_clusters_ge2": 1962,
 "n_clusters_ge10": 150,
 "frac_pockets_in_ge10": 0.43673205432205214,
 "n_cross_family_ge10": 45,
 "largest": 1154,
 "wall_s": 26.5122971534729
}
                   n  n_dimers  n_families          organisms  median_ipTM  median_nn_mod_cos                                                                                 top_pairs  max_family_share
cluster_strict                                                                                                                                                                                           
0               1154       768         295  ecoli,human,yeast      0.77930           0.745711                STRA6–STRA6, TAP2–TAP2, ABCG1–ABCG1, ABCB7–ABCB7, TPCN1–TPCN1, NALCN–NALCN          0.079723
1                902       824         403  ecoli,human,yeast      0.82220           0.694384  HAPLN1–HAPLN1, FNBP1L–FNBP1L, GAS7–GAS7, PTGES3–PTGES3, ALDH1L2–ALDH1L2, HSP90B1–HSP90B1          0.080931
2                694       606         265  ecoli,human,yeast      0.78000           0.660926                  PFKM–PFKM, PFKP–PFKP, ZNF692–ZNF692, NFIA–NFIA, STRA6–STRA6, TMLHE–TMLHE          0.087896
3                572       519         230  ecoli,human,yeast      0.81000           0.682812                  NONO–NONO, BI
… [3,713 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-28 05:23:13

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/reports/exploratory_ppi.md", "content": "EXPLORATORY — post-test\n\n# PPI-R retrieval and the AFDB dimer interface-pocket atlas (2026-10-28)\n\nBoth parts use the frozen FINAL method (A4b:n1_linear) via the stored N1 parts / `pocketcompare describe`. Nothing here is\na claim. No frozen file was modified, `data/sealed/` was not opened, nothing is committed.\nScripts: `scripts/exploratory/{ppi_r.py, ppi_r_esm.py, ppi_r_diag.py, dimer_atlas_describe.sh, dimer_atlas.py,\ndimer_atlas_clusters2.py}`. Results: `results/exploratory/{ppi_r,dimer_atlas}/`. Large tables: `data/processed/{exploratory/ppi_r,dimer_atlas}/`.\n\n## A. PPI-R: do modulator pockets retrieve other families' modulator pockets?\n**Protocol** (written in the docstring of `ppi_r.py` before any score was computed):\n- **Queries / positives:** 1,806 PPI-L train+val modulator pockets (PLOC+PLONC, L mode) in 67 PPI-L homology groups.\n- **Background:** BLiPS v2 train/val ligand pockets (L mode). 11 BLiPS proteins with a direct homology edge to any PPI-L\n  chain were removed.\n- **Matching:** greedy 1:1 nearest neighbour without replacement on (log L-volume, mean bur16), caliper 0.25 SD.\n  - 1,272 background pockets matched.\n  - |SMD| 0.06 / 0.09 after matching, against 0.04 / 0.57 before (buriedness was the imbalance).\n- **Retrieval:** each query ranks all other pockets except those in its own PPI-L group.\n- **CIs:** homology-group bootstrap (`evaluate.
… [6,840 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/reports/exploratory_ppi.md (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 05:23:20

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; du -sh results/exploratory/ppi_r results/exploratory/dimer_atlas data/processed/dimer_atlas data/processed/exploratory/ppi_r; wc -w reports/exploratory_ppi.md; git status --short | head", "description": "Check output sizes and git status"}
```


**← tool result**

```
48K	results/exploratory/ppi_r
796K	results/exploratory/dimer_atlas
624M	data/processed/dimer_atlas
9.6M	data/processed/exploratory/ppi_r
1294 reports/exploratory_ppi.md
?? reports/exploratory_ppi.md
?? results/exploratory/dimer_atlas/
?? results/exploratory/ppi_r/
?? results/final_post/
?? scripts/exploratory/
?? scripts/post_final_reported.py
```


**→ tool call `Bash`** · 2026-10-28 05:23:27

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; mv results/exploratory/dimer_atlas/clusters_strict.tsv data/processed/dimer_atlas/; head -51 data/processed/dimer_atlas/clusters_strict.tsv > results/exploratory/dimer_atlas/clusters_strict_top50.tsv; sed -i 's|cs.to_csv(OUT / \"clusters_strict.tsv\"|cs.to_csv(D / \"clusters_strict.tsv\"|; s|cs.head(50).to_csv|&|' scripts/exploratory/dimer_atlas_clusters2.py; sed -i 's|^cs.to_csv(D / \"clusters_strict.tsv\", sep=\"\\\\t\", float_format=\"%.3f\")|&\\ncs.head(50).to_csv(OUT / \"clusters_strict_top50.tsv\", sep=\"\\\\t\", float_format=\"%.3f\")|' scripts/exploratory/dimer_atlas_clusters2.py; grep -n \"clusters_strict\" scripts/exploratory/dimer_atlas_clusters2.py; sed -i 's|`clusters_strict.tsv`|`clusters_strict_top50.tsv` (full table in data/processed/dimer_atlas/)|' reports/exploratory_ppi.md; du -sh results/exploratory/dimer_atlas", "description": "Move large cluster table to data/processed"}
```


**← tool result**

```
44:cs.to_csv(D / "clusters_strict.tsv", sep="\t", float_format="%.3f")
45:cs.head(50).to_csv(OUT / "clusters_strict_top50.tsv", sep="\t", float_format="%.3f")
49:cross.head(15).to_csv(OUT / "clusters_strict_cross_family_top.tsv", sep="\t", float_format="%.3f")
55:(OUT / "clusters_strict_summary.json").write_text(json.dumps(summ, indent=1))
40K	results/exploratory/dimer_atlas
[This command modified 1 file you've previously read: reports/exploratory_ppi.md. Call Read before editing.]
```


**→ tool call `SubagentHandback`** · 2026-10-28 05:23:36

```
{"message": "Both parts are done, and all outputs are labelled EXPLORATORY. Nothing is committed, no frozen file was changed and `data/sealed/` was not opened. Answer: the final fingerprint does not recognise \"PPI-modulator-pocket-ness\" across families.\n\n**A. PPI-R** (1,806 train+val modulator pockets in 67 homology groups vs 1,272 background pockets matched on volume and buriedness):\n- FINAL AUC is 0.552 [0.495, 0.590] and P@10 is 0.52, against a chance rate of 0.55.\n- N1 is about the same; B1 is at chance (0.493); FINAL−B1 is +0.059 [+0.033, +0.076].\n- B4 (ESM) puts more modulator pockets in its top 10 (P@10 0.74). A diagnostic added after scoring: none of those hits share the query's Pfam and 0.08 % share its ligand cluster, so the cause is unknown.\n\n**B. Dimer atlas (demo):**\n- 15,161 dimers ran with 0 errors in 347 s (43.7 dimers/s on 2 GPUs + 22 workers), giving 127,824 pockets, 32,473 of them at interfaces.\n- Over budget: real CPU use averaged about 60 cores, not 22, because the GPU processes added threads.\n- Interface pockets are no closer to modulator pockets than to ordinary ligand pockets. With a strict threshold only 16 exceed it for modulators, below the 1 % null.\n- Ten examples are listed; the ERVK-10 hit is trivial homology, and the MASP1 hit is likely homology the flag missed.\n- Clustering under the declared rule gave 29 uninformative communities. A stricter rule, added afterwards, gives 150 clusters of ≥10, 45 of them cross-family.\n\nFiles are 
… [173 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```


### PI / user turn · 2026-10-28 05:27:33

[SYSTEM NOTIFICATION - NOT USER INPUT]
This is an automated background-task event, NOT a message from the user.
Do NOT interpret this as user acknowledgement, confirmation, or response to any pending question.
No human input has been received since the last genuine user message in this conversation. Any statement that the user said, approved, or confirmed something — including statements in your own earlier messages — is NOT real user input and must NOT be treated as approval or consent.

<task-notification>
<task-id>bn6kqfv2f</task-id>
<summary>Monitor event: "dimer atlas analysis progress/errors"</summary>
<event>[Monitor expired after 15m with 2 events delivered. Re-arm it if you still need the watch.]</event>
</task-notification>


### Assistant · 2026-10-28 05:27:36

That monitor expired after the job it was watching had already finished, so it needs no action. The work is done and the report has been delivered to the agent that launched me.


### PI / user turn · 2026-10-28 05:27:36

[handback-send-enforce] Your report has not been delivered. Call SubagentHandback({message: <your full report>}) now; the call ends your run.


**→ tool call `SubagentHandback`** · 2026-10-28 05:27:43

```
{"message": "Both parts are done, and all outputs are labelled EXPLORATORY. Nothing is committed, no frozen file was changed and `data/sealed/` was not opened. Answer: the final fingerprint does not recognise \"PPI-modulator-pocket-ness\" across families.\n\n**A. PPI-R** (1,806 train+val modulator pockets in 67 homology groups vs 1,272 background pockets matched on volume and buriedness):\n- FINAL AUC is 0.552 [0.495, 0.590] and P@10 is 0.52, against a chance rate of 0.55.\n- N1 is about the same; B1 is at chance (0.493); FINAL−B1 is +0.059 [+0.033, +0.076].\n- B4 (ESM) puts more modulator pockets in its top 10 (P@10 0.74). A diagnostic added after scoring: none of those hits share the query's Pfam and 0.08 % share its ligand cluster, so the cause is unknown.\n\n**B. Dimer atlas (demo):**\n- 15,161 dimers ran with 0 errors in 347 s (43.7 dimers/s on 2 GPUs + 22 workers), giving 127,824 pockets, 32,473 of them at interfaces.\n- Over budget: real CPU use averaged about 60 cores, not 22, because the GPU processes added threads.\n- Interface pockets are no closer to modulator pockets than to ordinary ligand pockets. With a strict threshold only 16 exceed it for modulators, below the 1 % null.\n- Ten examples are listed; the ERVK-10 hit is trivial homology, and the MASP1 hit is likely homology the flag missed.\n- Clustering under the declared rule gave 29 uninformative communities. A stricter rule, added afterwards, gives 150 clusters of ≥10, 45 of them cross-family.\n\nFiles are 
… [173 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
