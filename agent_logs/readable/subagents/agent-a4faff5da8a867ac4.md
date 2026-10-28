# Sub-agent a4faff5da8a867ac4 — Review R1: external PI (opus)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-27 18:08:46

You are an external, senior PI in computational structural biology / cheminformatics reviewing a research design. Be candid and specific. Project root: /cluster/project/beltrao/gmagnus/pocket_compare. Read PROMPT.md (the fixed project brief — goal and parts are fixed; ideas in it are human priors, not a plan), DESIGN.md (draft v0, under review), and skim LITERATURE.md §3, §4, §7 and reports/{data_benchmarks,fragment_docking_feasibility,ppi_dimers}.md. The pocket finder is described in /cluster/project/beltrao/gmagnus/pocket_detect/FOR_FURTHER_DEVELOPMENT.md.

Your remit: overall scientific strategy. Is this the right set of bets for a 24-hour project (about 22 h remain) whose goal is the best possible fast, versatile, fold-independent pocket-similarity tool that also works for PPI pockets? What is missing, what is over-scoped, what should be cut or reprioritised, are the claims well posed, is the PPI part credible, is the novelty real? Propose CONCRETE changes that stay within the project's scope (each change: what to change in DESIGN.md, why, expected effect, cost), or state that none are needed. Rank changes by importance (must / should / could). Keep it ≤ 1.5 pages.

Write your review to /cluster/project/beltrao/gmagnus/pocket_compare/reviews/round1_pi.md. Do not edit DESIGN.md. Do not commit. Your final message: the ranked list of changes (≤ 250 words).


### PI / user turn · 2026-10-27 18:08:46

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


**→ tool call `Bash`** · 2026-10-27 18:08:50

```
{"command": "ls -la && ls reviews reports 2>/dev/null; wc -l PROMPT.md DESIGN.md LITERATURE.md reports/*.md /cluster/project/beltrao/gmagnus/pocket_detect/FOR_FURTHER_DEVELOPMENT.md", "description": "List project files and sizes"}
```


**→ tool call `Read`** · 2026-10-27 18:08:51

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/PROMPT.md"}
```


**→ tool call `Read`** · 2026-10-27 18:08:51

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/DESIGN.md"}
```


**← tool result**

```
1	/goal You are the PI of a computational structural biology project and work autonomously. You lead a team of agents (Opus 5.5 or Sonnet 5.5, as you see fit). You delegate, review, integrate and decide; you keep the research record. The goal is the best possible outcome, not the fastest completion. Make decisions yourself, document why, and keep going.
2	Context. Parallel teams are building a pocket finder and a docking predictor. This component supplies pocket fingerprints for similarity search and for docking ligands against pockets across the AlphaFold Protein Structure Database (~200M structures).
3	
4	Docking: /cluster/work/beltrao/buhmanju/agentic_ai/workspaces/hackathon/autoresearch_docking
5	Pocket finder: /cluster/project/beltrao/gmagnus/pocket_detect
6	(FOR_FURTHER_DEVELOPMENT.md in pocket_detect might be useful)
7	Task. Design a method that scores the similarity of two protein binding pockets independent of sequence or fold, built on top of our existing fast pocket predictor. The intended use could go towards drug off-target prediction, drug repurposing, evolutionary comparison and or function annotation, but for this project we mostly want a versatile fast tool.
8	Treat pocket representation and comparison as an open design question. Look at literature and try to explore novel ideas. One idea that we find interesting is to use docking of a set of molecule fragments into a pocket as pocket descriptor (Fragment Based Drug Design). But please go down various paths a
… [5,339 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
total 168
drwxr-sr-x 14 gmagnusson nogroup           4096 Oct 27 19:07 .
drwxr-xr-x  5 gmagnusson gmagnusson-group   100 Oct 27 17:59 ..
drwxr-sr-x  8 gmagnusson nogroup           4096 Oct 27 19:07 .git
-rw-r--r--  1 gmagnusson nogroup             84 Oct 27 18:25 .gitignore
drwxr-xr-x  3 gmagnusson nogroup           4096 Oct 27 18:56 .pytest_cache
drwxr-sr-x  5 gmagnusson nogroup           4096 Oct 27 18:26 .venv
-rw-r--r--  1 gmagnusson nogroup           3468 Oct 27 18:59 DATA.md
-rw-r--r--  1 gmagnusson nogroup          15204 Oct 27 19:07 DESIGN.md
-rw-r--r--  1 gmagnusson nogroup            579 Oct 27 18:27 LESSONS.md
-rw-r--r--  1 gmagnusson nogroup          66135 Oct 27 19:05 LITERATURE.md
-rw-r--r--  1 gmagnusson nogroup           6740 Oct 27 18:24 PROMPT.md
-rw-r--r--  1 gmagnusson nogroup           3059 Oct 27 19:00 RESEARCH_TREE.md
drwxr-sr-x  4 gmagnusson nogroup           4096 Oct 27 18:25 data
drwxr-sr-x  2 gmagnusson nogroup           4096 Oct 27 18:25 docs
drwxr-sr-x  2 gmagnusson nogroup           4096 Oct 27 18:58 logs
-rw-r--r--  1 gmagnusson nogroup            280 Oct 27 18:25 pyproject.toml
drwxr-sr-x  2 gmagnusson nogroup           4096 Oct 27 18:59 reports
drwxr-sr-x  5 gmagnusson nogroup           4096 Oct 27 18:52 results
drwxr-sr-x  2 gmagnusson nogroup           4096 Oct 27 18:25 reviews
drwxr-sr-x  5 gmagnusson nogroup           4096 Oct 27 18:31 scripts
drwxr-sr-x  4 gmagnusson nogroup           4096 Oct 27 18:25 src
drwxr-sr-x  3 gmagnusson nogroup
… [377 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
1	# DESIGN — fast, fold-independent pocket similarity on BURROW (draft v0, 2026-10-27 19:15)
2	
3	Status: DRAFT for review round 1. Inputs: PROMPT.md, LITERATURE.md, reports/{data_benchmarks,
4	fragment_docking_feasibility,ppi_dimers}.md, pocket_detect/FOR_FURTHER_DEVELOPMENT.md.
5	
6	## 0. Goal and claims
7	
8	Build **a versatile, fast tool that scores the similarity of two binding pockets independent of sequence and
9	fold**, built on BURROW pockets, usable at AFDB scale (≈200 M structures × ~5–15 pockets), on PDB and AlphaFold
10	models, and on pockets created by protein–protein interfaces (PPIs).
11	
12	Deliverables:
13	1. `pocketcompare` package: pocket → descriptor(s); (pocket, pocket) → similarity; batch/ANN search CLI.
14	2. An evaluation on public benchmarks (zero-shot) and on our own leakage-controlled benchmarks (including a new
15	   PPI-pocket benchmark), with runtime reported next to every accuracy number.
16	3. REPORT.md with test results, limitations, follow-ups.
17	
18	Pre-registered primary claim (C1): our final method's ROC-AUC on the **TOUGH-M1 test partition** (§2.2) exceeds
19	our pre-specified internal baseline B1 (BURROW size-free descriptor cosine, §3) by ≥ 0.03, paired cluster
20	bootstrap, one-sided α = 0.05. Secondary claims (Holm-corrected together): C2 ProSPECCTs D5+D5.2+D6+D6.2+D7
21	macro-AUC > B1; C3 PPI-test AUC > B1; C4 runtime: descriptor ≤ 1 s/pocket and comparison ≤ 10 µs/pair on CPU
22	for the tier-1 descriptor. Published numbers (zero-s
… [14,228 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 18:08:55

```
{"command": "grep -n '^#' LITERATURE.md | head -60; cat reports/data_benchmarks.md", "description": "Show literature headings and data report"}
```


**→ tool call `Bash`** · 2026-10-27 18:08:55

```
{"command": "cat reports/fragment_docking_feasibility.md reports/ppi_dimers.md", "description": "Read docking and PPI reports"}
```


**→ tool call `Read`** · 2026-10-27 18:08:55

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_detect/FOR_FURTHER_DEVELOPMENT.md"}
```


**← tool result**

```
1	# For further development: building a pocket-comparison method on BURROW
2	
3	This note is for the agent that will build a method to compare pockets (a similarity measure over pocket
4	descriptors or representations) on top of BURROW. It says what exists, where it is, how to get every pocket
5	representation from code, and what we learned that matters for comparison. Every command and code block was
6	run on 2026-10-27 from the root of the main repository with `.venv` active; outputs quoted below are real.
7	
8	## 1. Orientation
9	
10	**What BURROW is.** BURROW finds and ranks ligand-binding pockets in protein structures (PDB/mmCIF;
11	experimental structures, AlphaFold models, multi-chain assemblies).
12	- It fills the solvent shell around the protein with grid points ("volume elements", 1 Å grid in the default preset).
13	- It describes each point by ray-cast buriedness, through a full-atom grid and a backbone-only grid, plus first-hit chemistry and neighbourhood composition.
14	- A small LightGBM model scores the points. Candidate pockets are assembled at several buriedness and score levels.
15	- A second LightGBM model ranks the pockets. It was trained on a leakage-controlled, LIGYSIS-style BioLiP2 set.
16	- There are no neural networks. CPU (Numba) and GPU (PyTorch/Triton) give byte-identical output.
17	- `--af-mode` uses pLDDT to prune low-confidence regions.
18	
19	**Where things live.**
20	| place | what |
21	|---|---|
22	| this repository (`/cluster/project/beltrao
… [23,039 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
# Fragment-docking pocket fingerprints: feasibility and cost (ADock on BURROW pockets)

2026-10-27. Node eu-g6-048: 4x RTX 4090, 64 CPUs. The node was shared, with a 1-min load of about 25 throughout, so CPU timings are conservative.
ADock source: `/cluster/work/.../autoresearch_docking/src/adock`, read-only, used unmodified. The sha256 of the sorted `src/adock/*.py` files plus `config/adock.json` hashes to `667cb8d14c0f7bd9`. The ADock repo has no reachable git dir.
This is a feasibility study on 27 pockets, so all signal numbers are anecdotal.

## Numbers first

**Throughput.** The panel is 64 fragments × 27 BURROW pockets (9 PDB entries). Each figure is the median of 3 seeds. Wall time includes receptor typing, grid build and search. Ligand prep is done once per panel (0.17 s for 64 fragments).

| preset (search budget) | GPU ms/pair, 1 proc | CPU ms/pair, 1 thread | seed r (dz) | redock RMSD BEN / OHT |
|---|---|---|---|---|
| `v2_default` (ADock stock) | 7.0 (per-pocket batch) | – | 0.999 | – |
| `v2_fast` (ADock stock) | 4.4 per-pocket, 3.7 multi-pocket | – | 0.994 | 0.4 / 1.1 Å |
| `v2_fast_nn` (exact polish without neighbour lists) | 1.76 | 347 | – | – |
| **`frag_lite_np`** (32 chains × 64 MC steps, no polish) | **0.82** | **57** | **0.980** (min 0.90) | 0.3 / 1.1–1.2 Å |
| `frag_xlite_np` (16 × 32) | 0.69 | 20 | 0.94 (min 0.69) | 0.3 / 1.1–1.4 Å |
| `frag_scan` (rigid Stage A + 20 BFGS, no MC) | 0.65 | 9 | 0.76 (min 0.40) | fails in 1 of 3 seeds |

- **Node throughp
… [20,644 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
1:# LITERATURE.md — binding-pocket similarity: methods, benchmarks, numbers, pitfalls
18:## 1. Taxonomy of pocket representations and comparison schemes
24:### 1.1 Alignment-based (geometric / graph / clique / hashing)
89:### 1.2 Alignment-free fingerprints, histograms, sketches
112:### 1.3 Learned embeddings (vector-search compatible)
148:### 1.4 Motif / active-site search at AFDB scale (not pocket similarity, but the scaling precedent)
163:### 1.5 Ligand- and docking-profile descriptors
171:## 2. Benchmarks and datasets
173:### 2.1 ProSPECCTs — the field standard (Ehrt, Brinkjost & Koch 2018, 10.1371/journal.pcbi.1006483)
202:### 2.2 Other pair / label benchmarks
221:### 2.3 Leakage-control resources (methodology, not similarity labels)
238:### 2.4 Items I could not identify
256:## 3. Published numbers we must beat
258:### 3.1 ProSPECCTs (ROC AUC)
313:### 3.2 TOUGH-M1, APoc set, Kahraman, Vertex (ROC AUC)
350:## 4. Docking-profile descriptors — what PocketVec actually did, and what it means for the fragment idea
400:### What this means for our fragment-docking idea
429:## 5. Pockets at protein–protein interfaces
478:## 6. Data leakage and robustness
480:### 6.1 Leakage in the pocket-similarity literature specifically
513:### 6.2 AlphaFold vs apo vs holo
541:## 7. Implications for our design — 10 opinionated recommendations
622:## 8. References
713:## 9. Explicitly unverified / open
# Public pocket-similarity benchmarks: acquisition report (2026-10-27)

Fetch scripts: `scrip
… [5,421 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 18:08:58

```
{"command": "sed -n 256,430p LITERATURE.md", "description": "Read literature sections 3 and 4"}
```


**→ tool call `Bash`** · 2026-10-27 18:08:59

```
{"command": "sed -n 541,622p LITERATURE.md; cat RESEARCH_TREE.md LESSONS.md; ls reviews", "description": "Read literature section 7 and tree"}
```


**← tool result**

```
## 3. Published numbers we must beat

### 3.1 ProSPECCTs (ROC AUC)

**Source and caveat.** The ProSPECCTs paper itself puts its per-method AUCs in supplementary tables S14–S32,
which I could not retrieve. The table below is **verbatim from DeeplyTough's Table 2** (bioRxiv v1,
10.1101/600304, read directly [P]), which states it is "directly reusing their published results" for the 21
baselines. Column labels are the paper's P-numbering (P1 = D1, …). Blank = not reported.

| Method | P1 | P1.2 | P2 | P3 | P4 | P5 | P5.2 | P6 | P6.2 | P7 |
|---|---|---|---|---|---|---|---|---|---|---|
| Cavbase | 0.98 | 0.91 | 0.87 | 0.65 | 0.64 | 0.60 | 0.57 | 0.55 | 0.55 | 0.82 |
| FuzCav | 0.94 | 0.99 | 0.99 | 0.69 | 0.58 | 0.55 | 0.54 | 0.67 | 0.73 | 0.77 |
| FuzCav (PDB) | 0.94 | 0.99 | 0.98 | 0.69 | 0.58 | 0.56 | 0.54 | 0.65 | 0.72 | 0.77 |
| Grim | 0.69 | 0.97 | 0.92 | 0.55 | 0.56 | 0.69 | 0.61 | 0.45 | 0.65 | 0.70 |
| Grim (PDB) | 0.62 | 0.83 | 0.85 | 0.57 | 0.56 | 0.61 | 0.58 | 0.45 | 0.50 | 0.64 |
| IsoMIF | 0.77 | 0.97 | 0.70 | 0.59 | 0.59 | **0.75** | **0.81** | 0.62 | 0.62 | 0.87 |
| KRIPO | 0.91 | 1.00 | 0.96 | 0.60 | 0.61 | **0.76** | 0.77 | **0.73** | **0.74** | 0.85 |
| PocketMatch | 0.82 | 0.98 | 0.96 | 0.59 | 0.57 | 0.66 | 0.60 | 0.51 | 0.51 | 0.82 |
| ProBiS | 1.00 | 1.00 | 1.00 | 0.47 | 0.46 | 0.54 | 0.55 | 0.50 | 0.50 | 0.85 |
| RAPMAD | 0.85 | 0.83 | 0.82 | 0.61 | 0.63 | 0.55 | 0.52 | 0.60 | 0.60 | 0.74 |
| Shaper | 0.96 | 0.93 | 0.93 | 0.71 | **0.76** | 0.65 | 0.65 | 0.54
… [12,500 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
## 7. Implications for our design — 10 opinionated recommendations

1. **Primary benchmark: TOUGH-M1. Secondary: ProSPECCTs D5/D5.2, D6/D6.2, D7 and the Vertex set.** TOUGH-M1 is
   the only large set where the fold baseline is dead (TM-score AUC 0.51 [P]), so it directly tests the
   fold-independence claim. ProSPECCTs D1/D1.2/D2/D3/D4 are **robustness diagnostics, not headline results** —
   TM-align scores 1.00 on the first three. Report all ten anyway (the field does) but set our pre-registered
   endpoints on TOUGH-M1 + D5/D6/D7 + Vertex, and **report AUC-PR alongside AUC-ROC**: the class balance swings
   from 17 positives per negative (Vertex) to 1 positive per 489 negatives (ProSPECCTs D7), and ROC-AUC hides
   both extremes. Accept that TOUGH-M1 has a label-noise ceiling and say so.
2. **Report zero-shot and trained numbers separately, and never compare across them.** Published 0.91–0.94 on
   TOUGH-M1 are fine-tuned-on-TOUGH-M1; zero-shot state of the art is ProFSA 0.82 and classical methods are
   0.64–0.69 [P]. If our method is untrained (a real advantage of a docking/descriptor profile), the honest
   comparison set is the zero-shot column — where beating 0.82 is a genuine result.
3. **Build the split with DataSAIL and the leakage check with EPoCS.** DataSAIL is MIT and `pip`-installable
   (PyPI 1.4.0, confirmed); it handles two-dimensional pair splits, which is exactly our setting. EPoCS
   (Apache-2.0, `tugceoruc/epocs`) showed that 30 %-identity splits are am
… [9,780 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 18:09:06

```
{"command": "sed -n 429,540p LITERATURE.md; sed -n 112,170p LITERATURE.md", "description": "Read PPI and learned-embedding literature sections"}
```


**← tool result**

```
## 5. Pockets at protein–protein interfaces

**What exists.**
- **The resource to use: Moine-Franel et al., *Sci Data* 2024, 10.1038/s41597-024-03233-z** (Institut Pasteur).
  >23,000 **VolSite** pockets over 3,700 proteins and ~3,500 ligands, >1,700 families, CC-BY-4.0 on Zenodo
  (10.5281/zenodo.10805580). Crucially [P]: **VolSite parameters were re-tuned for PPI pockets** because "pockets
  within PPIs typically exhibit distinct properties, such as shallowness"; for heterodimers, pockets are
  detected **with the partner protein treated as the ligand**; pockets are classified **PLOC / PLONC / PLA**
  (orthosteric competitive, orthosteric non-competitive, allosteric) by their relation to the interface. They
  also define a **pocket similarity index (PSI)** from **109 pocket descriptors** (89 VolSite + 10 Kuenemann-style
  composites + 10 geometric) after dropping near-constant ones. **That is architecturally the same thing as
  BURROW's 76 descriptors + cosine** — so this is both a ready-made benchmark *and* a direct baseline for our
  cheapest tier.
- Interface *geometry* comparison (not pockets): **iAlign/IS-score** (10.1093/bioinformatics/btq404; 90 %
  coverage at 0.05 errors/query on 1,517 dimers [S]), **I2I-SiteEngine** (PMID 15980484), **PIFACE** (22,604
  unique interface structures [S]; the URL did not respond from here), **MaSIF-search/MaSIF-site**, **PInet**.
- Ligand/chemistry databases: **iPPI-DB** (200), **2P2Idb** (unreachable from here), **TIMBAL** (unreacha
… [12,873 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-27 18:11:12

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/reviews/round1_pi.md", "content": "# Review round 1 — external PI (overall scientific strategy) — DESIGN.md v0\n\n**Verdict.** The evaluation discipline is strong: sealed tests, a fold-dead primary benchmark, a size-matched negative set and a missing-pocket policy. The method portfolio is too large for ~22 h, though, and the claims are anchored to a weak internal baseline. It is also missing the arm most likely to beat everything here cheaply: a pooled protein-language-model (PLM) embedding over the pocket residues. The PPI part as written tests homology recovery, not fold-independent similarity. Novelty is real in three places only: the pose-interaction docking profile, a leakage-controlled PPI-pocket benchmark, and AF-model robustness plus an AFDB-scale ANN index. A1 is FuzCav/PocketMatch on volume points, A3 is essentially SiteHopper (ROCS on pockets) and A4 is DeeplyTough-like. Say so in DESIGN.md.\n\n## Changes, ranked\n\n### MUST\n\n**M1. Cut scope to a critical path (§3, §8).** A1 and A4b (the learned metric on A1) are the main tier-1 bets. A2 is the tier-2 bet, gated. Demote A3 and full A4 (EGNN) to *could*: start them only if A1, A2 and A4b are scored on dev by 03:00. Run fragments vs lead-like at one size (N = 128), not two. Re-check the lead-like docking preset: `frag_lite_np` was only validated on fragments, so measure seed r on 20 lead-likes first. Drop \"two models of the same complex\" from PPIPS, b
… [4,868 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/reviews/round1_pi.md (file state is current in your context — no need to Read it back)
```


**→ tool call `SubagentHandback`** · 2026-10-27 18:11:23

```
{"message": "I wrote the round-1 strategy review to /cluster/project/beltrao/gmagnus/pocket_compare/reviews/round1_pi.md. DESIGN.md is untouched and nothing is committed. Ranked changes:\n\n**MUST**\n- **M1 Cut scope.** Main bets are A1, A4b (learned metric on A1) and A2 (gated). Demote A3 (≈ SiteHopper) and full A4 (EGNN) to \"could\", unless dev is done by 03:00. Run fragments vs lead-like at N = 128 only. Check that the lead-like docking preset gives reproducible scores before using it. Saves about 6–8 agent-hours.\n- **M2 Add a PLM-pocket arm (B4).** Mean-pool ESM-2 embeddings over BURROW pocket residues (EPoCS-style), as a must-beat baseline and a fusion input. It is the most likely off-the-shelf method to beat us. About 1–2 GPU-h.\n- **M3 Fix the claims.** Say which pocket mode C1 uses. C1 must beat B4 and the TM-score baseline, not only our weak B1. Add C5 for AF robustness. Make the margin test explicit (H0: Δ ≤ 0.03).\n- **M4 Make the PPI task fold-honest.** Interolog positives against random negatives are solved by global fold. The headline should be ranking the corresponding pocket within an interolog complex pair, scored as best-over-overlapping pockets at site level. Call the result \"transfer\", not fold-independent PPI similarity.\n- **M5 Extend leakage rules.** Apply them to anything fit on TOUGH-M1-dev (it shares 355 PDB IDs with ProSPECCTs). Report the largest cluster component in the split.\n\n**SHOULD**\n- **S1** Add the Pasteur PPI-pocket set (CC-BY) as a
… [601 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
