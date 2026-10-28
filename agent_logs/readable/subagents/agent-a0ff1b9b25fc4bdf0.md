# Sub-agent a0ff1b9b25fc4bdf0 — Write final REPORT.md (opus)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-28 05:00:19

You finalise REPORT.md for a 24-h autonomous research project (fast, fold-independent protein pocket similarity on BURROW, incl. PPI pockets). Project root: /cluster/project/beltrao/gmagnus/pocket_compare (git; do NOT commit — the PI commits). Start from REPORT_draft.md (dev parts written before the test; keep its structure, tighten it). Authoritative sources, read them: RESEARCH_TREE.md (status M3 + all decisions incl. D19–D23, DEV1–DEV5), PREREG.md, FREEZE.json, results/final/final_report.md + final_claims.json + final_summary.parquet (test results), reports/verification_final.md (independent verification + its qualifications: C1a/C1b Monte-Carlo-fragile; ligand heavy-atom count alone ROC 0.95 on TOUGH-M1 L-mode; B0 with TOUGH-M1's own fpocket pockets 0.48–0.59; P6 ≡ P6.2; DEV4 66 pockets, Δ unchanged without them), reports/exploratory_fusion.md (EXPLORATORY post-test), reports/tooling.md, docs/FINGERPRINTS.md, reports/proteome_demo.md, reviews/milestone_M3_retrospective.md (its "stop doing" points apply to how results are presented: lead with D-mode C1-D, call C1a/C1b borderline, do not lead with L-mode or with ProSPECCTs P1/P2 ceilings), LITERATURE.md §3 (published numbers — context only, different pocket definitions). Never open data/sealed/.

Requirements (PROMPT.md: breakdown of the approach, the best methods, test-set results, follow-ups, limitations, remaining ideas; runtime alongside accuracy):
- §1 Summary: bottom line in ≤ 12 lines: what the tool is; the confirmatory results (C1-D robust; C1a/C1b borderline and MC-fragile; C2 not supported); the size-stratified view; AF robustness; the ligand-imprint/size finding and what it means for the field's L-mode benchmarks; runtime/scale; negative results (fragment docking, PPI-L infeasible); the honest positioning vs published methods (paired B5-T on our TOUGH-M1-test partition: G-LoSA, SiteEngine, APoc shipped scores — raw and stratified AUC).
- A test-results section with compact tables: claims (Δ, CI, p, Holm, reject, robustness note); per-set ROC / size-stratified / cb-AUC for FINAL, N1, L4, B0, B1, B4, A1, B5/B5-T in L and D (TOUGH-M1-test, TOUGH-M1 full-minus-dev [non-learned only], BLiPS-test holo + AF, ProSPECCTs per subset (no self-pairs; L; note P6 ≡ P6.2 and D-mode P6 n = 4), Vertex, PPIPS-test P-ortho/P-sym, PPI-L (exploratory, 3 positives — say it is uninformative)); runtime table (per pocket, per pair, proteome throughput, storage, AFDB extrapolation).
- Clearly separate: confirmatory (pre-registered) vs reported vs EXPLORATORY post-test (fusion; API changes). 
- Process/integrity section: sealing, deviations DEV1–DEV5, audit failure + rebuild, re-freezes, tie-break D19, verification. Brief, no retelling of the full history.
- Limitations; follow-ups; remaining ideas (concrete, prioritised: e.g. replace L-mode benchmarks with ligand-free site definitions; larger cross-family training data; L4/fusion as optional mode; PPI-R task; cofactor-aware pockets; ANN at AFDB scale; integration with ADock re-ranking).
- Keep numbers traceable: `<!-- src: path -->` tags after number-bearing sentences (machine-checkable `path#key` where possible; run scripts/check_report.py REPORT.md and fix failures).
- What to push: the work is on git branch `pocket-compare` (commits only, no remote); say so in a short "Reproduce / deliverables" section pointing to README.md.
Write REPORT.md (≈ 3–5k words). If you cannot write .md files, return the full text in your final message between lines "=====BEGIN REPORT=====" and "=====END REPORT=====". Otherwise final message ≤ 150 words.


### PI / user turn · 2026-10-28 05:00:19

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


### Assistant · 2026-10-28 05:00:21

I'll start by surveying the sources.


**→ tool call `Bash`** · 2026-10-28 05:00:24

```
{"command": "ls && wc -w REPORT_draft.md RESEARCH_TREE.md PREREG.md FREEZE.json results/final/final_report.md results/final/final_claims.json reports/verification_final.md reports/exploratory_fusion.md reports/tooling.md docs/FINGERPRINTS.md reports/proteome_demo.md reviews/milestone_M3_retrospective.md LITERATURE.md README.md scripts/check_report.py; ls REPORT.md 2>/dev/null; git branch 2>/dev/null | head", "description": "List project and word counts of sources"}
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
  7331 REPORT_draft.md
  4072 RESEARCH_TREE.md
   639 PREREG.md
    35 FREEZE.json
 32820 results/final/final_report.md
   412 results/final/final_claims.json
  1134 reports/verification_final.md
   957 reports/exploratory_fusion.md
   758 reports/tooling.md
  1547 docs/FINGERPRINTS.md
  1351 reports/proteome_demo.md
  1074 reviews/milestone_M3_retrospective.md
  9383 LITERATURE.md
  1511 README.md
   877 scripts/check_report.py
 63901 total
* pocket-compare
```


**→ tool call `Bash`** · 2026-10-28 05:00:27

```
{"command": "cat REPORT_draft.md", "description": "Read the report draft"}
```


**→ tool call `Bash`** · 2026-10-28 05:00:27

```
{"command": "cat scripts/check_report.py", "description": "Read the report checker script"}
```


**← tool result**

```
#!/usr/bin/env python
"""Check that numbers in a markdown report match their sidecar'd result files (DESIGN §5).

Tag convention: a number is followed (on the same line) by ``<!-- src: <path>#<key> -->``; the checked number is
the last number between the previous tag (or line start) and this tag, e.g.

    ROC-AUC 0.734 <!-- src: results/c1/auc.json#delta_auc.estimate --> (95 % CI ...)

* ``path`` is relative to ``--root`` (default: the project root).  The file must have a ``<path>.prov.json``
  sidecar (``pocketcompare.provenance``) whose ``result_sha256`` matches the file, and whose ``evaluate_sha256``
  matches the current ``src/pocketcompare/evaluate.py`` (``--allow-stale-eval`` downgrades this to a warning).
* ``key`` for .json: dotted path into the object (``a.b.0.c``; a literal top-level key containing dots wins).
  For .parquet/.tsv/.csv: ``column`` (the table must have exactly one row) or ``column[col=value,col2=value]``
  (the filter must select exactly one row).
* Match rule: the reported number equals the stored value rounded to the shown number of decimals
  (|reported - value| <= 0.5 * 10^-decimals + 1e-12).  A number with a ``%`` suffix matches if it equals 100 x the
  value (fractions) or the value itself (already a percentage).
* Untagged numbers with >= 2 decimals are listed as warnings (``--fail-untagged`` makes them errors).

Exit status 0 if every tag checks out, 1 otherwise (mismatch, missing file, missing/stale sidecar, bad key).
"""
from __future__ imp
… [6,512 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
<persisted-output>
Output too large (47.2KB). Full output saved to: /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/boathz5ng.txt

Preview (first 2KB):
# REPORT (draft) — fast, fold-independent pocket similarity on BURROW

Status: draft written 2026-10-28 ~03:30 CET, after method freeze decision D20 and the re-audit PASS, **before** the
final held-out evaluation. Every number below is a development (dev/val) number unless it sits in a
`[[...]]` placeholder. Sources are noted as `<!-- src: ... -->` after number-bearing sentences; keyed tags
(`path#key`) are machine-checkable by `scripts/check_report.py`.

---

## 1. Summary

**What we built.** `pocketcompare` describes every BURROW pocket of a structure (PDB or AlphaFold model, monomer
or dimer) with a 384-dimensional unit vector and scores two pockets by cosine. The vector does not use sequence
or fold. The final method, **A4b:n1_linear (raw cosine)**, works in four steps:

1. A ligand-free "sph8" site shaper takes the buried BURROW grid points within 8 Å of the pocket's
 buriedness-weighted centroid.
2. On that point set we compute a typed volumetric fingerprint (A1, 514 d) and a protein-environment block
 (env, 113 d). Together these form N1 (627 d).
3. A linear projection to 128 d is trained contrastively on BioLiP ligand-sharing pairs (BLiPS-train), AlphaFold
 dimer pocket pairs (PPIPS-train) and same-site ligand-defined ↔ detected pairs.
4. Three se
… [748 more characters; full text in agent_logs/raw/]
```


**→ tool call `Read`** · 2026-10-28 05:00:30

```
{"file_path": "/home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/boathz5ng.txt"}
```


**← tool result**

```
1	
2	# REPORT (draft) — fast, fold-independent pocket similarity on BURROW
3	
4	Status: draft written 2026-10-28 ~03:30 CET, after method freeze decision D20 and the re-audit PASS, **before** the
5	final held-out evaluation. Every number below is a development (dev/val) number unless it sits in a
6	`[[...]]` placeholder. Sources are noted as `<!-- src: ... -->` after number-bearing sentences; keyed tags
7	(`path#key`) are machine-checkable by `scripts/check_report.py`.
8	
9	---
10	
11	## 1. Summary
12	
13	**What we built.** `pocketcompare` describes every BURROW pocket of a structure (PDB or AlphaFold model, monomer
14	or dimer) with a 384-dimensional unit vector and scores two pockets by cosine. The vector does not use sequence
15	or fold. The final method, **A4b:n1_linear (raw cosine)**, works in four steps:
16	
17	1. A ligand-free "sph8" site shaper takes the buried BURROW grid points within 8 Å of the pocket's
18	 buriedness-weighted centroid.
19	2. On that point set we compute a typed volumetric fingerprint (A1, 514 d) and a protein-environment block
20	 (env, 113 d). Together these form N1 (627 d).
21	3. A linear projection to 128 d is trained contrastively on BioLiP ligand-sharing pairs (BLiPS-train), AlphaFold
22	 dimer pocket pairs (PPIPS-train) and same-site ligand-defined ↔ detected pairs.
23	4. Three seeds are concatenated into the 384-d vector.
24	
25	Cost after BURROW is ≈ 3.5 ms per pocket on one CPU thread and ≈ 0.1 µs per pair in batched search, and the
26	ve
… [48,971 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:00:33

```
{"command": "cat RESEARCH_TREE.md", "description": "Read the research tree"}
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
… [26,668 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:00:37

```
{"command": "cat PREREG.md FREEZE.json; ls results/final/", "description": "Read PREREG, FREEZE and list final results"}
```


**← tool result**

```
# PREREG — consolidated pre-registration (2026-10-27 22:45, before any model fit and before any test use)

Supersedes the scattered amendments (D6, D8, D9, D11, D12) by stating the final protocol in one place. DESIGN.md v2
remains the rationale; where they differ, this file wins. Its sha256 is recorded in RESEARCH_TREE.md (D14).

## 1. Final method selection (dev only)
- Candidates: (N1) non-learned ligand-free A1(sph8)+env(sph8); (N2) hybrid A1(best sub-pocket)+A1(sph8)+env(sph8);
  (L*) A4b learned heads on the N2 input (and on N1 input), seed ensemble over SEEDS[:3]; each with and without CSLS
  (k = 10, background = the evaluated split's pocket pool). The final method takes no B4 input.
- **Objective = BLiPS-val v2, D-mode, cluster-balanced ROC-AUC** (deployment definition). SE from the
  homology-group vertex bootstrap (B = 2,000). **One-SE rule**: among candidates within one SE of the best, pick the
  simplest (non-learned < learned; then fewer dimensions; then no CSLS).
- Guards (must hold, else next candidate): BLiPS-val L-mode cluster-balanced AUC ≥ B1's; TOUGH-M1-dev D-mode
  cluster-balanced AUC ≥ B1's; PPIPS-val P-ortho MRR reported (no guard).
- A4b trains on BLiPS-train v2 (+ PPIPS-train P-sym/P-ortho pairs, + L↔D same-site augmentation); never on
  TOUGH-M1-dev, BLiPS-val, PPIPS-val or any test set. Selection of A4b hyper-parameters on BLiPS-val only, ≤ 12 configs.

## 2. Confirmatory claims (Holm family, one-sided α = 0.05, paired vertex bootstrap B = 2,000, H
… [4,225 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:00:41

```
{"command": "cat results/final/final_claims.json; echo; .venv/bin/python -c \"\nimport pandas as pd; pd.set_option('display.width',250); pd.set_option('display.max_columns',50); pd.set_option('display.max_rows',2000)\ndf=pd.read_parquet('results/final/final_summary.parquet'); print(df.columns.tolist()); print(df.shape)\nfor c in df.columns:\n    if df[c].dtype==object and df[c].nunique()<60: print(c, sorted(df[c].dropna().unique().tolist()))\n\" 2>&1 | head -80; ls .venv/bin/python", "description": "Read claims and summary parquet schema"}
```


**← tool result**

```
{
  "C1-D": {
    "auc_a": 0.6994853579439732,
    "auc_b": 0.5458167542336838,
    "ci_high": 0.28907130465909664,
    "ci_low": 0.049564020764859655,
    "ci_unit": "u",
    "comparison": "FINAL[raw] \u2212 B1 default[raw]",
    "delta": 0.15366860371028934,
    "lower_bound_ge_sesoi": true,
    "lower_one_sided_95": 0.08972627359225384,
    "mode": "D (both D-matched; common set)",
    "n_degenerate": 0,
    "n_pairs": 21410,
    "n_pairs_dropped_not_common": 0,
    "n_pos": 8702,
    "n_units": 102,
    "p_holm": 0.0239880059970015,
    "p_one_sided": 0.005997001499250375,
    "reject_h0_holm": true,
    "se": 0.05068308406330059,
    "sesoi": 0.03,
    "set": "tough_m1_test"
  },
  "C1a": {
    "auc_a": 0.6975901239336866,
    "auc_b": 0.5683575037531678,
    "ci_high": 0.20811569905044414,
    "ci_low": 0.014698880134181242,
    "ci_unit": "u",
    "comparison": "FINAL[raw] \u2212 B1 default[raw]",
    "delta": 0.12923262018051873,
    "lower_bound_ge_sesoi": true,
    "lower_one_sided_95": 0.04074532527467853,
    "mode": "L",
    "n_degenerate": 0,
    "n_pairs": 24337,
    "n_pairs_dropped_not_common": 0,
    "n_pos": 10160,
    "n_units": 112,
    "p_holm": 0.049475262368815595,
    "p_one_sided": 0.01649175412293853,
    "reject_h0_holm": true,
    "se": 0.04176068157712037,
    "sesoi": 0.03,
    "set": "tough_m1_test"
  },
  "C1b": {
    "auc_a": 0.6975901239336866,
    "auc_b": 0.5680769638246267,
    "ci_high": 0.2509764746042582,
    "ci_low": 0.01154247864709
… [5,348 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:00:45

```
{"command": ".venv/bin/python -c \"\nimport pandas as pd; pd.set_option('display.width',250); pd.set_option('display.max_columns',50); pd.set_option('display.max_rows',2000)\ndf=pd.read_parquet('results/final/final_summary.parquet')\nfor c in ['set','subset','arm','config','variant','mode','key']:\n    print(c, df[c].nunique(), sorted(map(str,df[c].dropna().unique().tolist()))[:80])\n\"", "description": "List unique values of summary key columns"}
```


**← tool result**

```
set 15 ['blips_test', 'blips_test_af', 'prospeccts_P1', 'prospeccts_P1.2', 'prospeccts_P2', 'prospeccts_P3', 'prospeccts_P4', 'prospeccts_P5', 'prospeccts_P5.2', 'prospeccts_P6', 'prospeccts_P6.2', 'prospeccts_P7', 'tough_m1_full_minus_dev', 'tough_m1_test', 'vertex']
subset 10 ['5sub_no_self', '5sub_with_self', 'all', 'chemotype_seen', 'chemotype_unseen', 'n_shared_1', 'n_shared_ge2', 'no_promiscuous', 'no_self', 'with_self']
arm 12 ['A1', 'B0', 'B0m', 'B0p', 'B1', 'B4', 'B5', 'B5T', 'CTRL', 'FINAL', 'L4', 'N1']
config 19 ['L4:egnn_small', 'N1', 'apoc_negp', 'apoc_ps', 'default', 'epocs', 'esm2', 'esm2_noz', 'foldseek_tm', 'glosa_ga', 'logit_sum_absdiff', 'pair_only', 'pocketcompare-final:A4b:n1_linear|raw', 'random128', 'seq_identity', 'siteengine_c1', 'siteengine_c2', 'siteengine_c3', 'tm_score']
variant 5 ['control', 'csls', 'devfit', 'native', 'raw']
mode 3 ['D', 'L', 'native']
key 44 ['A1|pair_only|csls|D', 'A1|pair_only|csls|L', 'A1|pair_only|raw|D', 'A1|pair_only|raw|L', 'B0m|logit_sum_absdiff|devfit|L', 'B0p|foldseek_tm|native|L', 'B0p|foldseek_tm|native|native', 'B0p|seq_identity|native|native', 'B0p|tm_score|native|native', 'B0|default|raw|D', 'B0|default|raw|L', 'B1|default|csls|D', 'B1|default|csls|L', 'B1|default|raw|D', 'B1|default|raw|L', 'B4|esm2_noz|csls|D', 'B4|esm2_noz|csls|L', 'B4|esm2_noz|raw|D', 'B4|esm2_noz|raw|L', 'B4|esm2|csls|D', 'B4|esm2|csls|L', 'B4|esm2|raw|D', 'B4|esm2|raw|L', 'B5T|apoc_negp|native|native', 'B5T|apoc_ps|native|native', 'B5T|glos
… [572 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:00:49

```
{"command": "grep -n '^#' results/final/final_report.md | head -100; wc -l results/final/final_report.md", "description": "Show headings of final report"}
```


**← tool result**

```
1:# Final evaluation — FINAL
5:## Claims (Holm over C1a, C1b, C1-D, C2; one-sided α 0.05)
14:## tough_m1_test
62:## prospeccts_P1
129:## prospeccts_P1.2
196:## prospeccts_P2
263:## prospeccts_P3
392:## prospeccts_P4
521:## prospeccts_P5
588:## prospeccts_P5.2
655:## prospeccts_P6
722:## prospeccts_P6.2
789:## prospeccts_P7
856:## blips_test
1023:## blips_test_af
1052:## vertex
1073:## tough_m1_full_minus_dev
1092:## PPIPS (ppips_test)
1110:## Runtime
1199 results/final/final_report.md
```


**→ tool call `Bash`** · 2026-10-28 05:00:52

```
{"command": "sed -n 1,61p results/final/final_report.md | cut -c1-400", "description": "Read claims and TOUGH-M1-test sections"}
```


**← tool result**

```
# Final evaluation — FINAL

Method `pocketcompare-final:A4b:n1_linear|raw` (learned: True, CSLS: False); B = 2000, seed 0.

## Claims (Holm over C1a, C1b, C1-D, C2; one-sided α 0.05)

| claim | set | comparison | n | AUC final | AUC ref | Δ [95 % CI] | lower 95 % | p | p Holm | reject | ≥ SESOI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1a | tough_m1_test | FINAL[raw] − B1 default[raw] | 24337 | 0.698 | 0.568 | +0.129 [+0.015, +0.208] | +0.041 | 0.0165 | 0.0495 | True | True |
| C1b | tough_m1_test | FINAL[raw] − B4 esm2 (z)[raw] | 24337 | 0.698 | 0.568 | +0.130 [+0.012, +0.251] | +0.035 | 0.0185 | 0.0495 | True | True |
| C1-D | tough_m1_test | FINAL[raw] − B1 default[raw] | 21410 | 0.699 | 0.546 | +0.154 [+0.050, +0.289] | +0.090 | 0.0060 | 0.0240 | True | True |
| C2 | ProSPECCTs P5.2 + P6.2 + P7 | macro FINAL[raw] − B1 default[raw] | 788 | 0.740 | 0.718 | +0.022 [-0.064, +0.113] | -0.046 | 0.2668 | 0.2668 | False | False |

## tough_m1_test

| subset | arm | config | variant | mode | n (pos) | ROC-AUC [CI] | AP (lift) | pAUC | cb-AUC [CI] | strat [CI] | worst |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | raw | L | 24337 (10160) | 0.698 [0.669, 0.855] | 0.600 (1.44) | 0.554 | 0.665 [0.639, 0.788] | 0.719 [0.689, 0.889] | — |
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | csls | L | 24337 (10160) | 0.641 [0.614, 0.842] | 0.523 (1.25) | 0.521 | 0.658 [0.616, 0.770] | 0.684 [0.652, 0.877] | — |
… [6,204 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:00:57

```
{"command": "sed -n 1023,1199p results/final/final_report.md | cut -c1-330", "description": "Read BLiPS-AF, Vertex, full-minus-dev, PPIPS, runtime sections"}
```


**← tool result**

```
## blips_test_af

| subset | arm | config | variant | mode | n (pos) | ROC-AUC [CI] | AP (lift) | pAUC | cb-AUC [CI] | strat [CI] | worst |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | raw | L | 41379 (6896) | 0.730 [0.702, 0.772] | 0.393 (2.36) | 0.594 | 0.664 [0.642, 0.724] | 0.722 [0.695, 0.762] | 0.728 |
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | csls | L | 41379 (6896) | 0.729 [0.705, 0.762] | 0.374 (2.24) | 0.585 | 0.687 [0.664, 0.734] | 0.721 [0.697, 0.754] | 0.727 |
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | raw | D | 24155 (4471) | 0.723 [0.695, 0.764] | 0.398 (2.15) | 0.584 | 0.683 [0.658, 0.744] | 0.716 [0.687, 0.757] | 0.267 |
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | csls | D | 24155 (4471) | 0.726 [0.700, 0.756] | 0.394 (2.13) | 0.582 | 0.700 [0.675, 0.748] | 0.720 [0.693, 0.749] | 0.268 |
| all | N1 | N1 | raw | L | 41379 (6896) | 0.698 [0.670, 0.734] | 0.356 (2.13) | 0.580 | 0.649 [0.626, 0.701] | 0.693 [0.665, 0.727] | 0.696 |
| all | N1 | N1 | csls | L | 41379 (6896) | 0.703 [0.679, 0.732] | 0.346 (2.07) | 0.575 | 0.664 [0.641, 0.710] | 0.698 [0.672, 0.723] | 0.701 |
| all | N1 | N1 | raw | D | 24155 (4471) | 0.687 [0.654, 0.728] | 0.361 (1.95) | 0.573 | 0.685 [0.654, 0.729] | 0.682 [0.648, 0.723] | 0.254 |
| all | N1 | N1 | csls | D | 24155 (4471) | 0.697 [0.665, 0.727] | 0.370 (2.00) | 0.574 | 0.697 [0.666, 0.736] | 0.693 [0.658, 0.721] | 0.257 |
| all | L4
… [11,202 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:03

```
{"command": ".venv/bin/python -c \"\nimport json\nd=json.load(open('results/final/final_details.json'))\ndef show(o,p='',depth=0):\n    if depth>3: return\n    if isinstance(o,dict):\n        for k,v in o.items():\n            if isinstance(v,(dict,list)): print(p+str(k), type(v).__name__, len(v)); show(v,p+'  ',depth+1)\n            else: print(p+str(k),'=',repr(v)[:100])\n    elif isinstance(o,list) and o and depth<2:\n        show(o[0],p+'  [0] ',depth+1)\nshow(d)\n\" | head -300", "description": "Show final_details.json structure"}
```


**← tool result**

```
B = 2000
blips_test dict 2
  b0p dict 2
    b0p_foldseek_missing = 0
    b0p_foldseek_pairs_without_hit_set_to_0 = 0
  c5_holo_minus_af dict 28
    B1|default|raw|D#all dict 14
      auc_a = 0.6452951513343211
      auc_b = 0.6583690201383067
      ci_high = 0.01585829039319939
      ci_low = -0.04331906924399647
      ci_unit = 'hom'
      delta = -0.013073868803985533
      lower_one_sided_95 = -0.03697490071020274
      n_degenerate = 0
      n_pairs = 19818
      n_pairs_dropped_not_common = 0
      n_pos = 3823
      n_units = 701
      p_one_sided = 0.809095452273863
      se = 0.015009220067123243
    B1|default|raw|D#plddt_70_90 dict 14
      auc_a = 0.6685954965331398
      auc_b = 0.6720729830338608
      ci_high = 0.03593834675733788
      ci_low = -0.05035009451416062
      ci_unit = 'hom'
      delta = -0.0034774865007209943
      lower_one_sided_95 = -0.0407482553398165
      n_degenerate = 0
      n_pairs = 7388
      n_pairs_dropped_not_common = 0
      n_pos = 976
      n_units = 692
      p_one_sided = 0.5717141429285357
      se = 0.021730770876206597
    B1|default|raw|D#plddt_ge90 dict 14
      auc_a = 0.6348947583993858
      auc_b = 0.650622301945702
      ci_high = 0.022309413362846704
      ci_low = -0.052413892553391545
      ci_unit = 'hom'
      delta = -0.015727543546316225
      lower_one_sided_95 = -0.04688447756452896
      n_degenerate = 0
      n_pairs = 12332
      n_pairs_dropped_not_common = 0
      n_pos = 2845
      n_units = 613
      p
… [8,047 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:08

```
{"command": ".venv/bin/python -c \"\nimport json\nd=json.load(open('results/final/final_details.json'))\nfor k,v in d.items():\n    print('==',k, list(v.keys())[:40] if isinstance(v,dict) else v)\nprint()\nc5=d['blips_test']['c5_holo_minus_af']\nfor k,v in c5.items():\n    if k.endswith('#all'): print(k, {x:round(v[x],4) for x in ['auc_a','auc_b','delta','ci_low','ci_high','p_one_sided']}, v['n_pos'])\n\"", "description": "List top-level keys and C5 overall deltas"}
```


**← tool result**

```
== B 2000
== blips_test ['b0p', 'c5_holo_minus_af']
== mde_reference dev-derived MDE ≈ 0.13 for C1 (results/dev/tough_m1_dev_details.json#mde)
== method pocketcompare-final:A4b:n1_linear|raw
== method_config_sha256 de21f35d0d92726197eaf1d9481dec9d714fff604e2b9e0cac587a141cf70e2b
== method_csls False
== method_is_learned True
== mode FINAL
== ppi_l ['dry_run_note', 'exploratory', 'n_pairs', 'n_pos', 'note']
== prospeccts ['prospeccts_P1', 'prospeccts_P1.2', 'prospeccts_P2', 'prospeccts_P3', 'prospeccts_P4', 'prospeccts_P5', 'prospeccts_P5.2', 'prospeccts_P6', 'prospeccts_P6.2', 'prospeccts_P7']
== runtime ['a1_pair_only_L_ms_per_pocket_median', 'b1_default_L_ms_per_pocket_median', 'burrow_featurise_s_per_pocket_median', 'bytes_per_pocket_float32', 'final_dims', 'pair_us_median_of_3', 'proteome']
== sealed_files_accessed ['tough_m1_test_pairs.parquet', 'prospeccts_pairs.parquet', 'blips_test_pairs.parquet', 'blips_test_sites.parquet', 'vertex_pairs.parquet', 'tough_m1_pairs.parquet', 'ppips_test_queries.parquet', 'ppips_sym_test_pairs.parquet', 'ppi_l_test_pairs.parquet']
== seed 0
== tough_m1_test ['b0p', 'per_cluster_auc']
== vertex ['b0p_foldseek_missing', 'b0p_foldseek_pairs_without_hit_set_to_0', 'n_label_conflicts', 'n_pocket_pairs', 'n_pos', 'n_protein_pairs']

B1|default|raw|D#all {'auc_a': 0.6453, 'auc_b': 0.6584, 'delta': -0.0131, 'ci_low': -0.0433, 'ci_high': 0.0159, 'p_one_sided': 0.8091} 3823
B1|default|raw|L#all {'auc_a': 0.7368, 'auc_b': 0.7267, 'delta': 0.0101, 
… [333 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:13

```
{"command": ".venv/bin/python -c \"\nimport json\nd=json.load(open('results/final/final_details.json'))\nc5=d['blips_test']['c5_holo_minus_af']\nprint(list(c5.keys()))\nfor k,v in c5.items():\n    if k.startswith('FINAL') or k.startswith('N1'): print(k, {x:round(v[x],4) for x in ['auc_a','auc_b','delta','ci_low','ci_high','p_one_sided']}, v['n_pos'], v['ci_unit'])\nprint(json.dumps(d['ppi_l'],indent=1)[:2000])\nr=d['runtime']; print({k:v for k,v in r.items() if k!='proteome'})\nprint(d['tough_m1_test'].keys()); print(json.dumps(d['tough_m1_test']['b0p'])[:500])\nprint(json.dumps(d['vertex'])[:500])\n\"", "description": "Show C5 keys, PPI-L and runtime details"}
```


**← tool result**

```
['B1|default|raw|D#all', 'B1|default|raw|D#plddt_70_90', 'B1|default|raw|D#plddt_ge90', 'B1|default|raw|D#plddt_lt70', 'B1|default|raw|D#release_mixed', 'B1|default|raw|D#release_post', 'B1|default|raw|D#release_pre', 'B1|default|raw|L#all', 'B1|default|raw|L#plddt_70_90', 'B1|default|raw|L#plddt_ge90', 'B1|default|raw|L#plddt_lt70', 'B1|default|raw|L#release_mixed', 'B1|default|raw|L#release_post', 'B1|default|raw|L#release_pre', 'B4|esm2|raw|D#all', 'B4|esm2|raw|D#plddt_70_90', 'B4|esm2|raw|D#plddt_ge90', 'B4|esm2|raw|D#plddt_lt70', 'B4|esm2|raw|D#release_mixed', 'B4|esm2|raw|D#release_post', 'B4|esm2|raw|D#release_pre', 'B4|esm2|raw|L#all', 'B4|esm2|raw|L#plddt_70_90', 'B4|esm2|raw|L#plddt_ge90', 'B4|esm2|raw|L#plddt_lt70', 'B4|esm2|raw|L#release_mixed', 'B4|esm2|raw|L#release_post', 'B4|esm2|raw|L#release_pre']
{
 "dry_run_note": null,
 "exploratory": true,
 "n_pairs": 70313,
 "n_pos": 3,
 "note": "too few positives to evaluate"
}
{'a1_pair_only_L_ms_per_pocket_median': 4.544522147625685, 'b1_default_L_ms_per_pocket_median': 1.2157079763710499, 'burrow_featurise_s_per_pocket_median': 0.4301310710143298, 'bytes_per_pocket_float32': 1536, 'final_dims': 384, 'pair_us_median_of_3': 0.419588393997401}
dict_keys(['b0p', 'per_cluster_auc'])
{"b0p_foldseek_missing": 0, "b0p_foldseek_pairs_without_hit_set_to_0": 0}
{"b0p_foldseek_missing": 22545, "b0p_foldseek_pairs_without_hit_set_to_0": 2065, "n_label_conflicts": 0, "n_pocket_pairs": 1564604, "n_pos": 6598, "n_protein_pairs": 69
… [3 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:17

```
{"command": "cat reports/verification_final.md", "description": "Read independent verification report"}
```


**← tool result**

```
# Verification of the final held-out evaluation (independent verifier, 2026-10-28)

How I checked: I wrote my own code in `results/verify/` (`vlib.py`, `v_tough.py`, `v_tough_mc.py`, `v_prospeccts.py`, `v_leak.py`, `v_ppips_sens.py`, `v_spot.py`; outputs in `*.json`). It does not import `final_eval.py` or `evaluate.py`. AUCs come from `sklearn.roc_auc_score`, and the vertex bootstrap is my own (multinomial unit counts, pair weight c_u or c_u·c_v, B = 2000, different seeds). I re-derived the units, the D common set, the ProSPECCTs subsets and self-pairs, and the homology groups myself.

The final-method scores were recomputed from the stored part descriptors and the seed weights (z → clip ±5 → linear → L2, mean of the three 128-d seed cosines). They match the method API that final_eval used: max |Δscore| = 1.8e-7 (L) and 2.0e-7 (D).

Sealed files: 9 reads, each logged in `results/verify/unseal_log.tsv`. Every sha256 matched the recorded hash, and every file was back at mode 000 after its read.

| # | check | reported | verifier | verdict |
|---|---|---|---|---|
| 1 | C1a AUC final / B1; Δ | 0.697590 / 0.568358; +0.12923 | 0.697590 / 0.568358; +0.12923 | **PASS** |
| | C1a CI; p | [+0.015, +0.208]; 0.0165 | [+0.023, +0.206]; 0.0145 (B = 20k: [+0.013, +0.204]; 0.0164) | PASS (within MC error) |
| | C1b B4 AUC; Δ; p | 0.568077; +0.12951; 0.0185 | 0.568077; +0.12951; 0.0195 (20k: 0.0171) | **PASS** |
| 2 | C1-D common set (pairs / pos / units) | 21,410 / 8,702 / 102 | 21,410 / 8,7
… [4,946 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:21

```
{"command": "cat reviews/milestone_M3_retrospective.md", "description": "Read M3 retrospective"}
```


**→ tool call `Bash`** · 2026-10-28 05:01:22

```
{"command": "cat reports/exploratory_fusion.md reports/tooling.md", "description": "Read fusion and tooling reports"}
```


**→ tool call `Bash`** · 2026-10-28 05:01:23

```
{"command": "cat docs/FINGERPRINTS.md reports/proteome_demo.md", "description": "Read fingerprints doc and proteome demo report"}
```


**← tool result**

```
EXPLORATORY — post-test; not a confirmatory result

# Score fusion of FINAL (A4b:n1_linear raw) and L4:egnn_small raw (2026-10-28)

**Question.** The test numbers showed that L4 is stronger on BLiPS, the ProSPECCTs decoy subsets P3/P4 and PPIPS, while A4b is stronger on TOUGH-M1 D. Does a score-level fusion of the two help? Everything below was motivated by test data, so it is exploratory and changes no PREREG claim.

**Protocol** (fixed in the header of `scripts/explore/fusion_a4b_l4.py` before any fused score existed)
- **Fused score:** s = w·z(cos_A4b) + (1−w)·z(cos_L4), with both cosines raw.
- **z-scoring (declared):** each method's μ/σ is fitted on all 41,952 BLiPS-train v2 pairs, L-mode and D-mode pooled. σ_A = 0.280 and σ_L = 0.246; the two cosines correlate at r = 0.72.
- **Implementation:** the fused score is the inner product of the concatenation [√(w/σ_A)·e_A, √((1−w)/σ_L)·e_L], 768 dims. This lets every eval_dev / final_eval code path run unchanged.
- **Choosing w:** on dev only, among w ∈ {0.25, 0.5, 0.75}, by BLiPS-val D-mode cb-AUC with the one-SE rule (prefer w = 0.5 if it is within one SE). Best was w = 0.25 at 0.761 (SE 0.039), so the threshold is 0.722. w = 0.5 scored 0.761, so **w\* = 0.5**.
- **Test:** one look, w\* only. 7 sealed reads, logged in `results/exploratory/unseal_log.tsv`; all hashes OK and all files back at mode 000.
- **Sanity check:** FINAL and L4 were recomputed on the same code path and match `results/final` exactly (130 rows, max |Δ| = 
… [8,891 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
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
   - Each block is z-scored with 
… [17,113 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
# Milestone M3 retrospective (fresh-eyes review, 2026-10-28 ~05:15, ~11.5 h in, 6-10 h left)

Basis: PROMPT, RESEARCH_TREE (M3, D15-D21, DEV1-4), LESSONS, M2 retrospective, git log (80 commits), verification_final.md, report headers. No raw data or sealed files opened.

## 1. What should we stop doing?

1. **Stop using the test set as information.** It is now spent. Any change to the method, head, claims or strata after seeing results/final is post-hoc. A4b+L4 fusion, the CLI and the proteome fingerprints are "exploratory, dev-selected": select on BLiPS-val/PPIPS-val only, never re-run TOUGH-M1-test to compare variants, and keep the frozen A4b:n1_linear as the headline in REPORT.md.
2. **Stop trying to rescue the Holm margin.** C1a/C1b pass at p 0.0165/0.0185 against a 0.0167 threshold. The verifier's B = 20k gives 0.0164/0.0171, and 30-50 % of B = 2000 reruns would fail. Do not re-bootstrap until it passes or change the family. Report "borderline, MC-fragile" and lead with C1-D (p 0.006-0.0095, robust).
3. **Stop leading with L-mode numbers.** Ligand heavy-atom count alone gives ROC 0.95 on TOUGH-M1, and B0 is 0.80 on test (0.56 in D-mode). Headline = D-mode (C1-D, Vertex, BLiPS-test); L-mode only as secondary with the imprint caveat. Also stop quoting ProSPECCTs 0.99 as strength (near-ceiling, C2 not significant).
4. **Stop counting P6.2 as an independent condition.** P6 and P6.2 are identical by construction (BURROW strips HETATM, pockets.py:252), so the C2 macro Δ effecti
… [5,449 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:26

```
{"command": "grep -n '^#' LITERATURE.md | head -40", "description": "Show LITERATURE headings"}
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
```


**→ tool call `Bash`** · 2026-10-28 05:01:29

```
{"command": "sed -n 256,349p LITERATURE.md", "description": "Read published numbers section"}
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
… [5,521 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:32

```
{"command": "cat README.md | head -150; git log --oneline | head -15; git status --short | head -30; git tag", "description": "Read README and git state"}
```


**← tool result**

```
# pocketcompare — fast, fold-independent pocket similarity on BURROW

`pocketcompare` turns every BURROW pocket of a protein structure (a PDB entry, an AlphaFold model or a predicted
dimer) into a 384-d unit vector. Two pockets are compared by cosine, and large collections are searched with FAISS.
The descriptor is ligand-free and uses neither sequence nor fold.

The final method is **A4b:n1_linear**: a linear, 3-seed contrastive projection of A1(sph8) + env(sph8). It is
configured in `configs/final_method.yaml`, and the config, weights and statistics are sha256-verified on load.
Cost is ≈ 3.5 ms per pocket after BURROW and ≈ 0.1 µs per pair in batched search.

See `REPORT.md` for the method, results and limitations. Test-set results are pending the final evaluation.

## Install

Requirements:
- Python ≥ 3.11 (tested with 3.12.3) and `uv`.
- BURROW (`pocketdetect`, from `../pocket_detect/src`). It is imported through a `.pth` file, not installed.

```bash
cd pocket_compare
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e .                      # pyproject declares no dependencies; install them explicitly:
uv pip install numpy scipy pandas pyarrow scikit-learn numba gemmi rdkit pyyaml networkx
uv pip install faiss-gpu-cu12            # or faiss-cpu
uv pip install torch                     # needed only to train A4b/L4 or run L4
uv pip install transformers              # needed only for the B4 ESM-2 baseline
echo "$(realpath ../pocket_detect/src)" > .venv
… [7,928 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:36

```
{"command": "sed -n 150,400p README.md; git status --short | head -30", "description": "Read README reproduce section and git status"}
```


**← tool result**

```
Run everything from the project root with `.venv` active and `NUMBA_CACHE_DIR` set. Long jobs should run detached
(see LESSONS.md). Sealed test labels live in `data/sealed/` (chmod 000) and are read only by
`scripts/final_eval.py`.

1. **Public benchmarks**
 - `python scripts/data/fetch_{prospeccts,tough_m1,vertex,tough_c1,klifs}.py`
 - `python scripts/data/build_benchmarks.py`
 - `python scripts/data/check_benchmarks.py`
2. **PPI data**
 - `bash scripts/ppi/run_all.sh` (dimer characterisation)
 - `bash scripts/ppi/run_ppi_datasets.sh` (PPI-L + PPIPS; seals their test files)
3. **BLiPS sites**
 - `python scripts/data/prep_blips_pockets.py --part trainval`
 - `python scripts/data/prep_blips_pockets.py --part test`
4. **BURROW point caches (label-free)**
 - `python scripts/build_point_cache.py --dataset {tough_m1,blips,blips_test_holo,blips_test_af} --workers 32`
 - `bash scripts/run_final_prep_cache.sh` (ProSPECCTs/Vertex with `--label-free-structures`)
5. **Homology graph and all splits** (~1.5 h): `bash scripts/data/run_splits.sh`
 - This runs `build_homology_graph.py`, `make_tough_m1_split.py`, `make_blips_split.py`,
   `blips_test_exclusions.py`, `make_blips_resplit_v2.py`, `scripts/ppi/21_ppips_homology.py`,
   `scripts/ppi/22_ppips_build.py`, `ppips_burrow_flags.py`, `verify_splits.py` and `split_sensitivity.py`.
6. **Descriptors**
 - `python scripts/compute_descriptors.py --dataset tough_m1 --arm {a1,b1} --config all --mode both --workers 12`
   and `--arm b0 --mode bot
… [2,729 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:41

```
{"command": "ls results/ results/dev | head -80; ls results/tooling results/release results/exploratory results/exploratory/fusion results/verify 2>/dev/null; find results -newer results/final/final_claims.json -name '*.json' -not -name '*.prov.json' | head -50", "description": "List results directories and post-test files"}
```


**← tool result**

```
results/:
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

results/dev:
af_robustness_train
af_robustness_val
blind_val
blips_val_details.json
blips_val_details.json.prov.json
blips_val_replicates.parquet
blips_val_replicates.parquet.prov.json
blips_val_summary.md
blips_val_summary.md.prov.json
blips_val_summary.parquet
blips_val_summary.parquet.prov.json
blips_val_v2splits_details.json
blips_val_v2splits_details.json.prov.json
blips_val_v2splits_replicates.parquet
blips_val_v2splits_replicates.parquet.prov.json
blips_val_v2splits_summary.md
blips_val_v2splits_summary.md.prov.json
blips_val_v2splits_summary.parquet
blips_val_v2splits_summary.parquet.prov.json
final_method_runtime.json
final_method_runtime.json.prov.json
final_select_all_candidates.parquet
final_select_all_candidates.parquet.prov.json
final_select_all_details.json
final_select_all_details.json.prov.json
final_select_all_ppips.parquet
final_select_all_ppips.parquet.prov.json
final_select_all_summary.md
final_select_all_summary.parquet
final_select_all_summary.parquet.prov.json
final_select_nonlearned_candidates.parquet
final_select_nonlearned_candidates.parquet.prov.json
final_select_nonlearned_details.json
final_select_nonlearned_details.json.prov.json
final_select_nonlearned_ppips.parquet
final_select_nonlearned_ppips.parquet.prov.json
final_select_nonlearned_summary.md
final_select_nonlearned_summary.parquet
final_s
… [2,231 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:01:50

```
{"command": "grep -n \"c5\" scripts/final_eval.py | head -20; .venv/bin/python -c \"\nimport json\nd=json.load(open('results/exploratory/fusion/test_details.json'))\nprint(d.keys())\ndef find(o,p=''):\n    if isinstance(o,dict):\n        for k,v in o.items():\n            if 'c5' in str(k).lower() or 'holo' in str(k).lower(): print(p+'/'+k, json.dumps(v)[:300] if not isinstance(v,dict) else list(v.keys())[:30])\n            find(v,p+'/'+k)\nfind(d)\n\"", "description": "Look for C5 FINAL results in code and fusion details"}
```


**← tool result**

```
916:    c5 = {}
942:                    c5[f"{key}#{sn}"] = paired(ps.y, Vh[key].s, Va[key].s, ps.pair_units, args, mask=mask)
944:                    c5[f"{key}#{sn}"] = {"error": str(e)}
948:    return tab, {"c5_holo_minus_af": c5, "b0p": fsi}
dict_keys(['B', 'label', 'method', 'reproduction_vs_results_final', 'scales', 'sealed_files_accessed', 'seed', 'selection', 'tag', 'w'])
```


**→ tool call `Bash`** · 2026-10-28 05:01:54

```
{"command": "sed -n 900,950p scripts/final_eval.py; .venv/bin/python -c \"\nimport pandas as pd\nd=pd.read_parquet('results/exploratory/fusion/test_deltas.parquet'); print(d.columns.tolist()); print(d.to_string()[:3000])\"", "description": "Inspect C5 code and fusion deltas table"}
```


**← tool result**

```
        pvecs.append(Vec(v.arm, v.config, v.variant, "L" if v.mode == "native" else v.mode, s, v.dims,
                         v.note + "; protein pair = max over pocket pairs"))
    tab, _ = evaluate_vectors("vertex", pvecs, y, {"hom": (ci, cj)}, None, None, np.zeros(len(y), bool),
                              {"all": np.ones(len(y), bool)}, args, synthetic=ps.synthetic, ap_neg=True)
    return tab, {"n_protein_pairs": int(len(y)), "n_pos": int(y.sum()), "n_label_conflicts": n_conf,
                 "n_pocket_pairs": int(len(ps.y)), **fsi}


def stage_blips(ps: PairSet, af: PairSet | None, method, store, args, rel_dates, plddt):
    log(f"[{ps.name}] {len(ps.pockets)} sites, {len(ps.y)} pairs ({ps.y.sum()} pos); D-set {ps.dset.sum()}")
    specs = [s for s in BASE_SPECS if s[1] != "esm2_noz"]
    vecs = final_vectors(ps, method, store) + b0_vectors(ps) + descriptor_vectors(ps, store, specs)
    fsv, fsi = b0p_foldseek(ps, "blips_test_holo" if ps.name.endswith("test") else "blips_val")
    vecs += fsv
    tab, gen = evaluate_vectors(ps.name, vecs, ps.y, ps.pair_units, ps.pos_cluster, ps.cov, ps.dset, ps.subsets,
                                args, synthetic=ps.synthetic)
    c5 = {}
    if af is not None:
        avecs = final_vectors(af, method, store, dataset=af.dataset) + descriptor_vectors(af, store, specs,
                                                                                         dataset=af.dataset)
        Va, Vh = V(avecs), V(vecs)
        # pair stra
… [5,035 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:02:15

```
{"command": ".venv/bin/python -c \"\nimport pandas as pd\npd.set_option('display.width',250); pd.set_option('display.max_rows',500)\ndf=pd.read_parquet('results/final/final_summary.parquet')\ncols=['set','subset','arm','config','variant','mode','n_pairs','n_pos','auc','auc_cb','auc_strat','ap','auc_worst_all','miss_rate_pos_all','miss_rate_neg_all']\nb=df[df.set=='blips_test']\nprint(b.subset.unique())\nprint(b[cols].to_string())\n\"", "description": "Print BLiPS-test summary rows"}
```


**← tool result**

```
<persisted-output>
Output too large (32.9KB). Full output saved to: /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/bpnb2g7ve.txt

Preview (first 2KB):
<ArrowStringArray>
['all', 'no_promiscuous', 'n_shared_1', 'n_shared_ge2', 'chemotype_seen', 'chemotype_unseen']
Length: 6, dtype: str
            set            subset    arm                                 config variant    mode  n_pairs  n_pos       auc    auc_cb  auc_strat        ap  auc_worst_all  miss_rate_pos_all  miss_rate_neg_all
787  blips_test               all  FINAL  pocketcompare-final:A4b:n1_linear|raw     raw       L    41438   6905  0.725843  0.676371   0.719532  0.386349            NaN                NaN                NaN
788  blips_test    no_promiscuous  FINAL  pocketcompare-final:A4b:n1_linear|raw     raw       L    28136   5077  0.721208  0.680197   0.713901  0.395991            NaN                NaN                NaN
789  blips_test        n_shared_1  FINAL  pocketcompare-final:A4b:n1_linear|raw     raw       L    41156   6623  0.725793  0.670927   0.719890  0.378545            NaN                NaN                NaN
790  blips_test      n_shared_ge2  FINAL  pocketcompare-final:A4b:n1_linear|raw     raw       L    34815    282  0.727029  0.741695   0.710785  0.028594            NaN                NaN                NaN
791  blips_test    chemotype_seen  FINAL  pocketcompare-final:A4b:n1_linear|raw     raw       L    39980   544
… [737 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:02:27

```
{"command": "mkdir -p /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad && cd /cluster/project/beltrao/gmagnus/pocket_compare && cat > /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/tab.py <<'EOF'\nimport pandas as pd, numpy as np\ndf=pd.read_parquet('results/final/final_summary.parquet')\narms=[('FINAL',None,'raw'),('N1','N1','raw'),('L4','L4:egnn_small','raw'),('L4','L4:egnn_small','csls'),('A1','pair_only','raw'),('B0','default','raw'),('B0m',None,None),('B1','default','raw'),('B4','esm2','raw'),('B5','epocs','raw'),\n ('B5T','apoc_ps','native'),('B5T','apoc_negp','native'),('B5T','glosa_ga','native'),('B5T','siteengine_c1','native'),('B0p','foldseek_tm','native'),('CTRL',None,None)]\ndef f(x): return '—' if pd.isna(x) else f'{x:.3f}'\nfor s in df.set.unique():\n    d=df[df.set==s]\n    sub='no_self' if s.startswith('prospeccts') else 'all'\n    d=d[d.subset==sub]\n    print('##',s,sub)\n    for a,c,v in arms:\n        r=d[d.arm==a]\n        if c: r=r[r.config==c]\n        if v: r=r[r.variant==v]\n        for m in ['L','D','native']:\n            rr=r[r['mode']==m]\n            if len(rr)==0: continue\n            assert len(rr)==1,(s,a,c,v,m,len(rr))\n            x=rr.iloc[0]\n            print(f'{a:5s} {str(c):14s} {str(v):6s} {m:6s} n={x.n_pairs:>7} pos={x.n_pos:>6} roc={f(x.auc)} cb={f(x.auc_cb)} strat={f(x.auc_strat)} ap={f(x.ap)} worst=
… [261 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
## tough_m1_test all
FINAL None           raw    L      n=  24337 pos= 10160 roc=0.698 cb=0.665 strat=0.719 ap=0.600 worst=— mpos=—
FINAL None           raw    D      n=  21410 pos=  8702 roc=0.699 cb=0.650 strat=0.717 ap=0.587 worst=0.537 mpos=0.144
N1    N1             raw    L      n=  24337 pos= 10160 roc=0.692 cb=0.627 strat=0.675 ap=0.616 worst=— mpos=—
N1    N1             raw    D      n=  21410 pos=  8702 roc=0.655 cb=0.615 strat=0.641 ap=0.569 worst=0.503 mpos=0.144
L4    L4:egnn_small  raw    L      n=  24337 pos= 10160 roc=0.701 cb=0.680 strat=0.726 ap=0.603 worst=— mpos=—
L4    L4:egnn_small  raw    D      n=  21410 pos=  8702 roc=0.642 cb=0.671 strat=0.668 ap=0.544 worst=0.493 mpos=0.144
L4    L4:egnn_small  csls   L      n=  24337 pos= 10160 roc=0.653 cb=0.688 strat=0.695 ap=0.540 worst=— mpos=—
L4    L4:egnn_small  csls   D      n=  21410 pos=  8702 roc=0.604 cb=0.668 strat=0.644 ap=0.492 worst=0.464 mpos=0.144
A1    pair_only      raw    L      n=  24337 pos= 10160 roc=0.709 cb=0.773 strat=0.642 ap=0.597 worst=— mpos=—
A1    pair_only      raw    D      n=  21410 pos=  8702 roc=0.500 cb=0.523 strat=0.520 ap=0.409 worst=0.384 mpos=0.144
B0    default        raw    L      n=  24337 pos= 10160 roc=0.796 cb=0.785 strat=0.504 ap=0.662 worst=— mpos=—
B0    default        raw    D      n=  21410 pos=  8702 roc=0.555 cb=0.541 strat=0.564 ap=0.447 worst=0.426 mpos=0.144
B0m   None           None   L      n=  24337 pos= 10160 roc=0.882 cb=0.868 strat=0.582 ap=0.787 wor
… [25,564 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:02:40

```
{"command": ".venv/bin/python - <<'EOF'\nimport json\nfor p in ['results/tooling/describe_runtime.json','results/release/human_afdb_v6.json','results/dev/final_method_runtime.json','results/exploratory/fusion/fusion_runtime.json','results/proteome/summary.json']:\n    d=json.load(open(p))\n    print('=====',p)\n    s=json.dumps(d,indent=1)\n    print(s[:3500])\nEOF", "description": "Show runtime/release JSON contents"}
```


**← tool result**

```
===== results/tooling/describe_runtime.json
{
 "cpu_count": 128,
 "device": "cuda:0",
 "equivalence_vs_ref": {
  "fast": {
   "max_abs_diff": 0.0,
   "same_pocket_ids": true
  },
  "gpu": {
   "max_abs_diff": 0.0,
   "same_pocket_ids": true
  }
 },
 "host": "eu-g6-048",
 "loadavg_end": [
  80.7685546875,
  45.0673828125,
  30.63037109375
 ],
 "loadavg_start": [
  22.91650390625,
  22.8935546875,
  22.34521484375
 ],
 "n": 2000,
 "n_latency": 50,
 "runs": {
  "latency_fast_cpu1": {
   "cli_wall_s": 15.4,
   "n_errors": 0,
   "n_pockets": 275,
   "n_structures": 50,
   "per_structure_total_s": {
    "mean": 0.30125090638175606,
    "median": 0.21062923897989094,
    "p90": 0.700640352885239
   },
   "pockets_per_s": 17.857142857142858,
   "process_wall_s": 16.14073787815869,
   "s_per_structure_wall": 0.308,
   "stage_mean_s": {
    "burrow_s": 0.2279287467058748,
    "describe_s": 0.037825048393569885,
    "parse_s": 0.03545036453288049
   },
   "startup_s": 0.7407378781586882,
   "structures_per_s": 3.2467532467532467
  },
  "latency_gpu_inprocess": {
   "cli_wall_s": 11.3,
   "n_errors": 0,
   "n_pockets": 275,
   "n_structures": 50,
   "per_structure_total_s": {
    "mean": 0.2096513532428071,
    "median": 0.12656536314170808,
    "p90": 0.28263460497837517
   },
   "pockets_per_s": 24.336283185840706,
   "process_wall_s": 12.427433445118368,
   "s_per_structure_wall": 0.226,
   "stage_mean_s": {
    "burrow_s": 0.06213299482129514,
    "describe_s": 0.040243355580605565,

… [12,227 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:02:48

```
{"command": ".venv/bin/python - <<'EOF'\nimport json\nd=json.load(open('results/release/human_afdb_v6.json'))\nprint(json.dumps(d['index_opq_ivfpq'],indent=1)[:2500])\nprint([k for k in d])\nEOF\nsha256sum src/pocketcompare/evaluate.py; for f in results/final/final_summary.parquet results/final/final_claims.json results/release/human_afdb_v6.json results/tooling/describe_runtime.json results/exploratory/fusion/test_deltas.parquet results/proteome/summary.json results/dev/final_method_runtime.json results/final/final_details.json results/verify/v_holm.json results/verify/v_leak.json; do echo $f; ls $f.prov.json >/dev/null 2>&1 && grep -o '\"evaluate_sha256\": \"[0-9a-f]\\{8\\}' $f.prov.json; done", "description": "Show release PQ stats and sidecar eval hashes"}
```


**← tool result**

```
Exit code 2
{
 "build_s": 550.8093426518608,
 "bytes": {
  "index.faiss": 10934059,
  "meta.parquet": 12209504,
  "vectors.f16.npy": 89277056
 },
 "code_bytes": 64,
 "default_nprobe": 64,
 "dims": 384,
 "factory": "OPQ64_384,IVF1024,PQ64",
 "faiss_version": "1.14.1",
 "index_bytes_per_pocket": 94.05965796672574,
 "kind": "ivfpq",
 "method": {
  "af_mode": true,
  "backend": "fast GPU (identical to ref)",
  "config": "configs/final_method.yaml",
  "config_sha256": "de21f35d0d92726197eaf1d9481dec9d714fff604e2b9e0cac587a141cf70e2b",
  "dims": 384,
  "method": "pocketcompare-final:A4b:n1_linear|raw",
  "metric": "inner_product",
  "residues": "UniProt numbering",
  "source": "AFDB v6 human proteome (UP000005640_9606_HUMAN_v6.tar), AF mode",
  "unit": "merged region-rule pockets >= 10 points (method.describe_all)"
 },
 "metric": "inner_product",
 "n": 116246,
 "n_dropped_zero": 0,
 "n_train": 100000,
 "nlist": 1024,
 "normalisation": "none applied: final-method fingerprints are unit-norm embeddings; score = inner product",
 "opq": true,
 "pq_bits": 8,
 "pq_m": 64,
 "seed": 0,
 "train_s": 547.3102720738389
}
['crosscheck_describe_all', 'embed', 'exact', 'faiss_version', 'files', 'hubness', 'index_flat', 'index_opq_ivfpq', 'method', 'neighbour_overlap_with_n1_demo_top10', 'opq_ivfpq_recall', 'random_pair_similarity', 'release_counts', 'same_protein_top1_frac', 'storage_bytes_per_pocket']
f22d02967c08d706d8a6081865a8ba40f491340e87e205826e32f8206f65707b  src/pocketcompare/evaluate.py

… [574 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:02:53

```
{"command": ".venv/bin/python - <<'EOF'\nimport json\nd=json.load(open('results/release/human_afdb_v6.json'))\nfor k in ['opq_ivfpq_recall','random_pair_similarity','release_counts','storage_bytes_per_pocket','same_protein_top1_frac','neighbour_overlap_with_n1_demo_top10','embed']:\n    print(k, json.dumps(d[k])[:1200])\nfor f in ['v_holm','v_leak','v_tough_mc_C1a']:\n    print(f, json.dumps(json.load(open(f'results/verify/{f}.json')))[:1500])\nEOF", "description": "Show release recall stats and verifier JSONs"}
```


**← tool result**

```
opq_ivfpq_recall {"n_queries": 10000, "self_excluded": true, "sweep": {"1": {"recall_at_10": 0.3022, "recall_at_10_rerank_top100": 0.30457, "single_query_1thread_pq": {"median_ms": 0.22489449474960566, "n": 200, "p90_ms": 0.228715012781322}, "single_query_1thread_rerank100": {"median_ms": 0.34808460623025894, "n": 200, "p90_ms": 0.35598911345005035}, "top1_agree": 0.3581, "top1_agree_rerank": 0.387}, "4": {"recall_at_10": 0.5883299999999999, "recall_at_10_rerank_top100": 0.6039199999999999, "single_query_1thread_pq": {"median_ms": 0.24412490893155336, "n": 200, "p90_ms": 0.2558841370046139}, "single_query_1thread_rerank100": {"median_ms": 0.37486955989152193, "n": 200, "p90_ms": 0.3926020348444581}, "top1_agree": 0.6135, "top1_agree_rerank": 0.6922}, "16": {"recall_at_10": 0.81511, "recall_at_10_rerank_top100": 0.87577, "single_query_1thread_pq": {"median_ms": 0.32223446760326624, "n": 200, "p90_ms": 0.3545180428773165}, "single_query_1thread_rerank100": {"median_ms": 0.45986450277268887, "n": 200, "p90_ms": 0.49308002926409245}, "top1_agree": 0.7825, "top1_agree_rerank": 0.9228}, "32": {"recall_at_10": 0.8658, "recall_at_10_rerank_top100": 0.9519400000000001, "single_query_1thread_pq": {"median_ms
random_pair_similarity {"different_proteins": true, "n_pairs": 1999399, "p1": -0.4191819429397583, "p10": -0.19269947707653046, "p50": 0.11479835212230682, "p90": 0.4074493646621704, "p99": 0.6209051012992859, "p99.9": 0.7655677199363708}
release_counts {"fingerprints_parquet_bytes
… [3,050 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:02:57

```
{"command": "head -40 RESEARCH_TREE.md; grep -n \"D2[4-9]\\|DEV6\" RESEARCH_TREE.md", "description": "Re-read top of updated research tree"}
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
… [1,478 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:03:01

```
{"command": "diff <(git show HEAD:RESEARCH_TREE.md) RESEARCH_TREE.md | head -40", "description": "Diff research tree against HEAD"}
```


**← tool result**

```
(Bash completed with no output)
```


**→ tool call `Bash`** · 2026-10-28 05:03:07

```
{"command": ".venv/bin/python -c \"\nimport pandas as pd\npd.set_option('display.width',250)\nd=pd.read_parquet('results/exploratory/fusion/test_deltas.parquet')\nprint(d.comparison.unique()); print(d.set.unique())\nx=d[d.comparison.str.contains('AF|holo',case=False)|d.set.str.contains('af')]\nprint(x[['set','comparison','metric','mode','subset','auc_a','auc_b','delta','ci_low','ci_high','n_pairs']].to_string())\n\"", "description": "Look for holo-vs-AF comparisons in fusion deltas"}
```


**← tool result**

```
<ArrowStringArray>
['FUSED − FINAL', 'FUSED holo − FUSED AF (C5 analogue)']
Length: 2, dtype: str
<ArrowStringArray>
['tough_m1_test', 'prospeccts_P1', 'prospeccts_P1.2', 'prospeccts_P2', 'prospeccts_P3', 'prospeccts_P4', 'prospeccts_P5', 'prospeccts_P5.2', 'prospeccts_P6', 'prospeccts_P6.2', 'prospeccts_P7', 'blips_test', 'blips_test_af', 'vertex', 'ppips_test']
Length: 15, dtype: str
              set                           comparison  metric mode subset     auc_a     auc_b     delta    ci_low   ci_high  n_pairs
30  blips_test_af                        FUSED − FINAL     auc    L    all  0.759717  0.730385  0.029333  0.016504  0.039499  41379.0
31  blips_test_af                        FUSED − FINAL  auc_cb    L    all       NaN       NaN  0.030850  0.008553  0.046263  41379.0
32     blips_test  FUSED holo − FUSED AF (C5 analogue)     auc    L    all  0.755892  0.759717 -0.003826 -0.020204  0.011786  41379.0
35  blips_test_af                        FUSED − FINAL     auc    D    all  0.762020  0.723226  0.038794  0.025028  0.053666  24155.0
36  blips_test_af                        FUSED − FINAL  auc_cb    D    all       NaN       NaN  0.033500  0.013043  0.050226  24155.0
37     blips_test  FUSED holo − FUSED AF (C5 analogue)     auc    D    all  0.761431  0.770374 -0.008943 -0.025807  0.011750  19818.0
```


**→ tool call `Bash`** · 2026-10-28 05:03:29

```
{"command": ".venv/bin/python -c \"\nimport pandas as pd\npd.set_option('display.width',250); pd.set_option('display.max_columns',40)\nd=pd.read_parquet('results/final/final_ppips.parquet'); print(d.columns.tolist()); print(d.shape)\nprint(d[[c for c in d.columns if c in ('arm','config','variant','stratum','subset','n_queries','top1','top3','mrr','psym_pct','n')] ].head(40).to_string())\n\"; cat results/verify/v_ppips_sens.json | head -c 1500", "description": "Inspect PPIPS final table and verifier sensitivity"}
```


**← tool result**

```
['set', 'key', 'arm', 'config', 'variant', 'mode', 'dims', 'ortho_n_queries', 'ortho_n_units', 'ortho_top1', 'ortho_top1_lo', 'ortho_top1_hi', 'ortho_top3', 'ortho_top3_lo', 'ortho_top3_hi', 'ortho_mrr', 'ortho_mrr_lo', 'ortho_mrr_hi', 'sym_all_pct', 'sym_all_pct_lo', 'sym_all_pct_hi', 'sym_n_queries']
(13, 22)
      arm                                 config variant
0      B0                                default     raw
1      B1                                default     raw
2      B1                                default    csls
3      B4                                   esm2     raw
4      B4                                   esm2    csls
5      A1                              pair_only     raw
6      A1                              pair_only    csls
7   FINAL  pocketcompare-final:A4b:n1_linear|raw     raw
8   FINAL  pocketcompare-final:A4b:n1_linear|raw    csls
9      N1                                     N1     raw
10     N1                                     N1    csls
11     L4                          L4:egnn_small     raw
12     L4                          L4:egnn_small    csls
{
 "n_test_pockets_with_edge_to_ppips_train": 66,
 "of_pockets_in_pairs": 53,
 "n_pockets_in_pairs": 922,
 "n_pairs_clean": 22159,
 "n_pos_clean": 9035,
 "C1a_clean": {
  "auc_a": 0.699159015694157,
  "auc_b": 0.5643168301267363,
  "delta": 0.13484218556742067,
  "ci_low": 0.05811456062550281,
  "ci_high": 0.24065609352026543,
  "lower95": 0.0866680795732437,
  "se": 0.04171108463238371
… [450 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:03:46

```
{"command": ".venv/bin/python scripts/check_report.py REPORT_draft.md 2>&1 | grep -v WARN | tail -20; .venv/bin/python scripts/check_report.py REPORT_draft.md 2>&1 | grep -c WARN", "description": "Run report checker on the draft"}
```


**← tool result**

```
check_report: 13 tagged numbers OK, 0 errors
333
```


**→ tool call `Bash`** · 2026-10-28 05:04:12

```
{"command": ".venv/bin/python -c \"\nimport pandas as pd\ndf=pd.read_parquet('results/final/final_summary.parquet')\nd=df[(df.set=='blips_test')&(df.variant.isin(['raw']))&(df.arm.isin(['FINAL','B1','B4','L4','N1','A1']))&((df.config!='esm2_noz'))]\nfor (a,m),g in d.groupby(['arm','mode']):\n    print(a,m,' '.join(f'{r.subset}:{r.auc:.3f}/{r.n_pos}' for r in g.itertuples()))\n\"", "description": "BLiPS-test subset AUCs per arm"}
```


**← tool result**

```
A1 D all:0.577/4571 no_promiscuous:0.571/3170 n_shared_1:0.575/4414 n_shared_ge2:0.622/157 chemotype_seen:0.578/3913 chemotype_unseen:0.572/658
A1 L all:0.750/6905 no_promiscuous:0.757/5077 n_shared_1:0.750/6623 n_shared_ge2:0.771/282 chemotype_seen:0.751/5447 chemotype_unseen:0.750/1458
B1 D all:0.648/4571 no_promiscuous:0.651/3170 n_shared_1:0.648/4414 n_shared_ge2:0.669/157 chemotype_seen:0.646/3913 chemotype_unseen:0.662/658
B1 L all:0.736/6905 no_promiscuous:0.737/5077 n_shared_1:0.734/6623 n_shared_ge2:0.799/282 chemotype_seen:0.727/5447 chemotype_unseen:0.770/1458
B4 D all:0.655/4571 no_promiscuous:0.670/3170 n_shared_1:0.656/4414 n_shared_ge2:0.638/157 chemotype_seen:0.647/3913 chemotype_unseen:0.700/658
B4 L all:0.679/6905 no_promiscuous:0.690/5077 n_shared_1:0.678/6623 n_shared_ge2:0.700/282 chemotype_seen:0.668/5447 chemotype_unseen:0.717/1458
FINAL D all:0.728/4571 no_promiscuous:0.719/3170 n_shared_1:0.727/4414 n_shared_ge2:0.749/157 chemotype_seen:0.733/3913 chemotype_unseen:0.696/658
FINAL L all:0.726/6905 no_promiscuous:0.721/5077 n_shared_1:0.726/6623 n_shared_ge2:0.727/282 chemotype_seen:0.737/5447 chemotype_unseen:0.685/1458
L4 D all:0.740/4571 no_promiscuous:0.734/3170 n_shared_1:0.738/4414 n_shared_ge2:0.773/157 chemotype_seen:0.746/3913 chemotype_unseen:0.703/658
L4 L all:0.738/6905 no_promiscuous:0.737/5077 n_shared_1:0.738/6623 n_shared_ge2:0.742/282 chemotype_seen:0.744/5447 chemotype_unseen:0.715/1458
N1 D all:0.683/4571 no_promiscuous:0.674/3170 n_s
… [239 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:05:20

```
{"command": "cat > /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/gen.py <<'EOF'\nimport pandas as pd, numpy as np\nP='results/final/final_summary.parquet'\ndf=pd.read_parquet(P)\ndef row(s,sub,arm,cfg,var,mode):\n    d=df[(df.set==s)&(df.subset==sub)&(df.arm==arm)&(df['mode']==mode)]\n    if cfg: d=d[d.config==cfg]\n    if var: d=d[d.variant==var]\n    if len(d)!=1: return None,None\n    filt=f'set={s},subset={sub},arm={arm}'+(f',config={cfg}' if cfg else '')+(f',variant={var}' if var else '')+f',mode={mode}'\n    return d.iloc[0],filt\ndef cell(s,sub,arm,cfg,var,mode,col,tag=True):\n    r,filt=row(s,sub,arm,cfg,var,mode)\n    if r is None or pd.isna(r[col]): return '—'\n    v=f'{r[col]:.3f}'\n    return v+(f' <!-- src: {P}#{col}[{filt}] -->' if tag else '')\n# TOUGH-M1-test table\nrows=[('**FINAL** (A4b:n1_linear)', 'FINAL',None,'raw'),('N1 (non-learned parent)','N1','N1','raw'),('L4 egnn_small, CSLS (declared arm)','L4','L4:egnn_small','csls'),('L4 egnn_small, raw','L4','L4:egnn_small','raw'),\n ('A1 pair_only (4 Å shell fingerprint)','A1','pair_only','raw'),('B1 BURROW descriptors','B1','default','raw'),('B4 ESM-2 (z)','B4','esm2','raw'),('B5 EPoCS','B5','epocs','raw'),('B0 size −\\\\|Δ log V\\\\|','B0','default','raw'),('B0m size logistic (diagnostic)','B0m','logit_sum_absdiff','devfit')]\nout=['| arm | L ROC | L cb | L strat | D ROC | D cb | D strat |','|---|---|---|---|---|---|---|']\nfor name,a,c,v in
… [6,050 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{'ortho_n_queries': 153, 'ortho_n_units': 12, 'sym_n_queries': 544}
| arm | ROC | cb | strat |
|---|---|---|---|
| N1 (non-learned parent of FINAL) | 0.756 | 0.670 | 0.737 |
| A1 pair_only | 0.744 | 0.817 | 0.680 |
| B1 | 0.627 | 0.676 | 0.609 |
| B4 ESM-2 (z) | 0.587 | 0.624 | 0.590 |
| B5 EPoCS | 0.727 | 0.549 | 0.714 |
| B0 size | 0.815 | 0.780 | 0.511 |
| B0′ TM-score shipped | 0.520 | 0.527 | 0.524 |
| B0′ sequence identity shipped | 0.560 | 0.512 | 0.548 |
| arm | holo L ROC / cb / strat | holo D ROC / cb / strat | AF L ROC | AF D ROC | holo L, unseen chemotype |
|---|---|---|---|---|---|
| **FINAL** | 0.726 / 0.676 / 0.720 | 0.728 / 0.712 / 0.722 | 0.730 | 0.723 | 0.685 |
| N1 | 0.702 / 0.676 / 0.697 | 0.683 / 0.702 / 0.677 | 0.698 | 0.687 | 0.683 |
| L4 CSLS (declared) | 0.740 / 0.693 / 0.735 | 0.744 / 0.726 / 0.740 | 0.739 | 0.753 | 0.730 |
| L4 raw | 0.738 / 0.665 / 0.733 | 0.740 / 0.699 / 0.735 | 0.741 | 0.752 | 0.715 |
| A1 pair_only | 0.750 / 0.693 / 0.732 | 0.577 / 0.622 / 0.574 | 0.749 | 0.556 | 0.750 |
| B1 | 0.736 / 0.717 / 0.727 | 0.648 / 0.665 / 0.642 | 0.727 | 0.658 | 0.770 |
| B4 ESM-2 (z) | 0.679 / 0.682 / 0.678 | 0.655 / 0.707 / 0.654 | 0.665 | 0.643 | 0.717 |
| B0 size | 0.605 / 0.612 / 0.502 | 0.568 / 0.569 / 0.565 | — | — | 0.576 |
| arm | P1 | P1.2 | P2 | P3 | P4 | P5 | P5.2 | P6 | P7 |
|---|---|---|---|---|---|---|---|---|---|
| **FINAL** | 0.989 | 1.000 | 0.998 | 0.718 | 0.707 | 0.717 | 0.709 | 0.622 | 0.890 |
| N1 | 0.991 | 1.000 | 0.994 | 0.707 
… [2,874 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 05:06:10

```
{"command": "git rev-parse --short freeze-v1 freeze-v1^{commit} 2>/dev/null; git log --oneline | wc -l; head -5 results/final/unseal_log.tsv; wc -l results/final/unseal_log.tsv; ls reports/ | head -60", "description": "Check freeze tag, commit count, unseal log, reports"}
```


**← tool result**

```
70
time	file	sha256	sha256_ok	mode_before	mode_after	rows	purpose	user	host	pid	git_commit
2026-10-28T04:23:49+0100	data/sealed/tough_m1_test_pairs.parquet	17973ec019b5e7a511d47e4c0327c777768d102d39753773c6d1f9ebe7a0cda2	True	0o0	0o0	24337	C1a/C1b/C1-D + TOUGH-M1-test reported items	gmagnusson	eu-g6-048	1610173	e5a6f357e5284bf588d764cbee8050d92b31c94c
2026-10-28T04:25:02+0100	data/sealed/prospeccts_pairs.parquet	25b92e1254af89498e3499810e689be65dfa8e8dc947d933e1b533765b3e5c57	True	0o0	0o0	450625	C2 + ProSPECCTs reported items	gmagnusson	eu-g6-048	1610173	e5a6f357e5284bf588d764cbee8050d92b31c94c
2026-10-28T04:41:16+0100	data/sealed/blips_test_pairs.parquet	a10773a548b66a250054f3e5c0ee107af3b55b83cda1aa7bfe4e6ea3bd8916b9	True	0o0	0o0	41514	BLiPS-test reported items + C5	gmagnusson	eu-g6-048	1610173	e5a6f357e5284bf588d764cbee8050d92b31c94c
2026-10-28T04:41:16+0100	data/sealed/blips_test_sites.parquet	4059e7c80e6172fc473ccde065345d6edcbf6cde39bf155a30eb216423794d32	True	0o0	0o0	3606	BLiPS-test site groups / label clusters	gmagnusson	eu-g6-048	1610173	e5a6f357e5284bf588d764cbee8050d92b31c94c
10 results/final/unseal_log.tsv
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
poc
… [104 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-28 05:09:01

```
{"file_path": "/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/REPORT.tmpl.md", "content": "# pocketcompare: fast, fold-independent pocket similarity on BURROW (final report)\n\nStatus: 2026-10-28. The method was frozen at commit e5a6f35 (`FREEZE.json`, tag `freeze-v1`) and evaluated once on\nthe sealed test sets (`results/final/`). An agent that did not produce the numbers re-derived every headline with its\nown code (`reports/verification_final.md`). This report replaces `REPORT_draft.md`, which was written before the test.\n\nThree kinds of result are kept apart. **Confirmatory** results are the four pre-registered Holm-family claims\n(PREREG §2). **Reported** results are pre-registered descriptive metrics (PREREG §3). **EXPLORATORY (post-test)**\nresults were motivated by test numbers and carry no evidential weight (§8). Numbers carry `<!-- src: ... -->` tags;\n`path#key` tags are checked by `python scripts/check_report.py REPORT.md`.\n\nArms: **FINAL** = A4b:n1_linear, raw cosine (the frozen method). **N1** = its non-learned input descriptor.\n**L4** = point-cloud EGNN (best dev candidate, more complex). **A1** = typed volumetric fingerprint on the raw site.\n**B0** = pocket size. **B1** = BURROW's own descriptors. **B4** = ESM-2 lining-residue embedding. **B5** = EPoCS.\n**B5-T** = the APoc / G-LoSA / SiteEngine scores shipped with TOUGH-M1. **B0′** = global fold similarity.\n**L-mode** = pocket cut as a
… [41,002 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
<tool_use_error>Subagents should return findings as text, not write report files. Include this content in your final response instead.</tool_use_error>
```


### Assistant · 2026-10-28 05:09:09

The harness blocks writing `.md` files, so I'll take the caller's fallback route. I'll write the draft to a scratch `.txt` so I can run the checker on it, then return the full text.


**→ tool call `Bash`** · 2026-10-28 05:09:10

```
{"command": "ls /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/", "description": "List scratchpad files"}
```


**← tool result**

```
1a28.parquet
1a28.structures.parquet
PMC10640396.xml
PMC12259003.xml
PMC12343037.xml
PMC2639437.xml
PMC2838872.xml
PMC3098077.xml
PMC3821077.xml
PMC3980086.xml
PMC4383952.xml
PMC4941214.xml
PMC9405584.xml
PMC9549786.xml
PMC9709917.xml
a4b_smoke
af.parquet
af.structures.parquet
af20
bench
bench.log
bench2000
bench_n200.log
bench_smoke.json
bench_smoke.json.prov.json
bench_synth
bl_smoke
blind.log
blips.md
blips_block.py
blips_smoke
burrow.fasta
cache
cc.py
ccd.py
chk.py
compare.md
compare.py
cr.py
d2.py
decoy_an.py
decoy_map.pkl
dl
dry20
dry20b
drystandin
dt
e.parquet
e.structures.parquet
esm_blips
esm_ppips
eval_dev_orig.py
eval_synth
fmd.md
fs.log
fs_block.py
fs_smoke
gen.py
k_faq.php.html
k_index.php.html
kin.json
l4_synth
l4_synth_all
locdiff.py
ninp
osf
pdfenv
pp_smoke
ppil.log
ppips.md
ppips_block.py
ppips_smoke
prosp.md
q1.txt
q2.txt
q3.txt
q4.txt
q5.txt
release.log
run_desc.sh
rzip.py
scripts
seq.py
smoke
smoke.py
smoke2.py
smoke_fusion.py
str.pdb
survey.py
synth_a.log
synth_b.log
synth_models
t
t.fa
t.parquet
t.structures.parquet
t1.py
t2.py
t3.py
t_ppil.py
t_vs_af.m8
tab.py
tagcheck.txt
tcc.py
tcc2.py
tm_after
tm_after.log
tm_before
tm_before.log
tmpf
tmpm
tmpm2
tmpm3
tough.fasta
tough.md
tough_vs_burrow.m8
tpdb
tt.m8
tt_seq.m8
urls.txt
vertex.md
vertex_code5.txt
```


**→ tool call `Write`** · 2026-10-28 05:09:15

```
{"file_path": "/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/report_tmpl.txt", "content": "PLACEHOLDER\n"}
```


**← tool result**

```
File created successfully at: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/report_tmpl.txt (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 05:09:34

```
{"command": "echo ok", "description": "No-op placeholder"}
```


**← tool result**

```
ok
```


**→ tool call `Write`** · 2026-10-28 05:11:45

```
{"file_path": "/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/report_tmpl.txt", "content": "# pocketcompare: fast, fold-independent pocket similarity on BURROW (final report)\n\nStatus: 2026-10-28. The method was frozen at commit e5a6f35 (`FREEZE.json`, tag `freeze-v1`) and evaluated once on\nthe sealed test sets (`results/final/`). An agent that did not produce the numbers re-derived every headline with its\nown code (`reports/verification_final.md`). This report replaces `REPORT_draft.md`, which was written before the test.\n\nThree kinds of result are kept apart. **Confirmatory** results are the four pre-registered Holm-family claims\n(PREREG §2). **Reported** results are pre-registered descriptive metrics (PREREG §3). **EXPLORATORY (post-test)**\nresults were motivated by test numbers and carry no evidential weight (§8). Numbers carry `<!-- src: ... -->` tags;\n`path#key` tags are checked by `python scripts/check_report.py REPORT.md`.\n\nArms: **FINAL** = A4b:n1_linear, raw cosine (the frozen method). **N1** = its non-learned input descriptor.\n**L4** = point-cloud EGNN (best dev candidate, more complex). **A1** = typed volumetric fingerprint on the raw site.\n**B0** = pocket size. **B1** = BURROW's own descriptors. **B4** = ESM-2 lining-residue embedding. **B5** = EPoCS.\n**B5-T** = the APoc / G-LoSA / SiteEngine scores shipped with TOUGH-M1. **B0′** = global fold similarity.\n**L-mode** = pocket cut as 
… [41,886 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
The file /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/report_tmpl.txt has been updated successfully. (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 05:11:57

```
{"command": "S=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; cd /cluster/project/beltrao/gmagnus/pocket_compare && .venv/bin/python - <<EOF\nS='$S'\nt=open(f'{S}/report_tmpl.txt').read()\npros=open(f'{S}/prosp.md').read().replace('| P6 | P7 |','| P6 (≡ P6.2) | P7 |')\nlines=pros.split('\\n')\nfor i,l in enumerate(lines):\n    if l.startswith('| FINAL, D mode') or l.startswith('| B1, D mode'):\n        c=l.split(' | '); \n        # columns: name, P1..P7 -> P6 is index 8 (1-based subsets 8th)\n        c[8]='n/a (4 pairs)'; lines[i]=' | '.join(c)\npros='\\n'.join(lines)\nrep={'{{TOUGH}}':open(f'{S}/tough.md').read().strip(),'{{FMD}}':open(f'{S}/fmd.md').read().strip(),'{{BLIPS}}':open(f'{S}/blips.md').read().strip(),\n '{{PROSP}}':pros.strip(),'{{VERTEX}}':open(f'{S}/vertex.md').read().strip(),'{{PPIPS}}':open(f'{S}/ppips.md').read().strip()}\nfor k,v in rep.items():\n    assert k in t; t=t.replace(k,v)\nopen(f'{S}/report_full.txt','w').write(t)\nEOF\ngrep -n \"P6 (≡\" $S/report_full.txt | head; grep -n \"n/a (4\" $S/report_full.txt; .venv/bin/python scripts/check_report.py $S/report_full.txt 2>&1 | grep -v '^WARN' ; .venv/bin/python scripts/check_report.py $S/report_full.txt 2>&1 | grep -c '^WARN'; wc -w $S/report_full.txt; sed 's/<!--[^>]*-->//g' $S/report_full.txt | wc -w", "description": "Assemble report and run the checker"}
```


**← tool result**

```
281:| arm | P1 | P1.2 | P2 | P3 | P4 | P5 | P5.2 | P6 (≡ P6.2) | P7 |
291:| FINAL, D mode | 0.978 | 0.841 | 0.979 | 0.678 | 0.655 | 0.647 | 0.621 | n/a (4 pairs) | 0.848 |
292:| B1, D mode | 0.846 | 0.745 | 0.934 | 0.598 | 0.604 | 0.502 | 0.472 | n/a (4 pairs) | 0.741 |
check_report: 143 tagged numbers OK, 0 errors
484
7394 /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/report_full.txt
6686
```


**→ tool call `Bash`** · 2026-10-28 05:12:05

```
{"command": "S=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; sed 's/<!--[^>]*-->//g' $S/report_full.txt | grep -v '^|' | grep -v '^```' | wc -w; awk '/^## /{if(s)print s, n; s=$0; n=0; next}{gsub(/<!--[^>]*-->/,\"\"); if($0!~/^\\|/) n+=NF}END{print s,n}' $S/report_full.txt", "description": "Count prose words per section"}
```


**← tool result**

```
4797
## 1. Summary 531
## 2. Problem, scope, benchmarks 243
## 3. The method (frozen: `configs/final_method.yaml`) 288
## 4. Test-set results (frozen method, single evaluation) 1530
## 5. Development: how the method was chosen (dev/val only, rebuilt splits) 267
## 6. Negative and null results 250
## 7. Runtime and scale 76
## 8. EXPLORATORY (post-test): not confirmatory 285
## 9. Process and integrity (brief) 466
## 10. Limitations 240
## 11. Follow-ups and remaining ideas (prioritised) 300
## 12. Deliverables and reproduction 127
```


**→ tool call `Bash`** · 2026-10-28 05:12:38

```
{"command": "S=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; cat > $S/summary_new.txt <<'EOF'\n## 1. Summary\n\n- **Tool.** `pocketcompare` maps every BURROW pocket (PDB entry, AF model or dimer) to a 384-d unit vector. The pipeline is: ligand-free sph8 site → cavity + lining descriptor (N1, 627 d) → frozen linear contrastive head (A4b:n1_linear). Scores are cosines, searched with FAISS; no sequence, fold or ligand input is used.\n- **C1-D (headline, robust).** On TOUGH-M1-test with detected pockets, FINAL scores ROC 0.699 <!-- src: results/final/final_claims.json#C1-D.auc_a --> against B1's 0.546 <!-- src: results/final/final_claims.json#C1-D.auc_b -->. Δ = +0.154 <!-- src: results/final/final_claims.json#C1-D.delta --> [+0.050 <!-- src: results/final/final_claims.json#C1-D.ci_low -->, +0.289 <!-- src: results/final/final_claims.json#C1-D.ci_high -->], Holm p 0.024 <!-- src: results/final/final_claims.json#C1-D.p_holm -->. The verifier reproduced it.\n- **C1a/C1b (borderline).** In L-mode, Δ is +0.129 <!-- src: results/final/final_claims.json#C1a.delta --> against B1 and +0.130 <!-- src: results/final/final_claims.json#C1b.delta --> against ESM-2, Holm p 0.0495 <!-- src: results/final/final_claims.json#C1a.p_holm -->. Both are Monte-Carlo-fragile: 30–50 % of independent B = 2,000 bootstraps would not reject. <!-- src: reports/verification_final.md -->\n- **C2 (not supported).** On ProSPECCTs P5.2/P6.2/P7, 
… [4,063 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
check_report: 143 tagged numbers OK, 0 errors
4691
414
```


**→ tool call `Bash`** · 2026-10-28 05:12:57

```
{"command": "S=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; cd /cluster/project/beltrao/gmagnus/pocket_compare && sed -i 's/^- \\*\\*The learned head adds over its input.\\*\\* FINAL beats/- **The learned head appears to add over its input.** FINAL beats/' $S/report_full.txt && grep -n \"appears to add\" $S/report_full.txt && .venv/bin/python scripts/check_report.py $S/report_full.txt 2>&1 | tail -1 && cp $S/report_full.txt $S/REPORT_final.txt && sha256sum $S/REPORT_final.txt && cat $S/REPORT_final.txt", "description": "Apply edit, re-check, and print the final report"}
```


**← tool result**

```
<persisted-output>
Output too large (55.4KB). Full output saved to: /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/bo2mbllx5.txt

Preview (first 2KB):
189:- **The learned head appears to add over its input.** FINAL beats its non-learned input N1 in D-mode (0.699 vs 0.655 ROC;
check_report: 143 tagged numbers OK, 0 errors
62db674ac4f99b40264de46f7a844734f87f1f213f2dbcbe3fef960bb33d6041  /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/REPORT_final.txt
# pocketcompare: fast, fold-independent pocket similarity on BURROW (final report)

Status: 2026-10-28. The method was frozen at commit e5a6f35 (`FREEZE.json`, tag `freeze-v1`) and evaluated once on
the sealed test sets (`results/final/`). An agent that did not produce the numbers re-derived every headline with its
own code (`reports/verification_final.md`). This report replaces `REPORT_draft.md`, which was written before the test.

Three kinds of result are kept apart. **Confirmatory** results are the four pre-registered Holm-family claims
(PREREG §2). **Reported** results are pre-registered descriptive metrics (PREREG §3). **EXPLORATORY (post-test)**
results were motivated by test numbers and carry no evidential weight (§8). Numbers carry `<!-- src: ... -->` tags;
`path#key` tags are checked by `python scripts/check_report.py REPORT.md`.

Arms: **FINAL** = A4b:n1_linear, raw cosine (the fro
… [554 more characters; full text in agent_logs/raw/]
```


**→ tool call `Read`** · 2026-10-28 05:13:03

```
{"file_path": "/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/REPORT_final.txt"}
```


**← tool result**

```
1	# pocketcompare: fast, fold-independent pocket similarity on BURROW (final report)
2	
3	Status: 2026-10-28. The method was frozen at commit e5a6f35 (`FREEZE.json`, tag `freeze-v1`) and evaluated once on
4	the sealed test sets (`results/final/`). An agent that did not produce the numbers re-derived every headline with its
5	own code (`reports/verification_final.md`). This report replaces `REPORT_draft.md`, which was written before the test.
6	
7	Three kinds of result are kept apart. **Confirmatory** results are the four pre-registered Holm-family claims
8	(PREREG §2). **Reported** results are pre-registered descriptive metrics (PREREG §3). **EXPLORATORY (post-test)**
9	results were motivated by test numbers and carry no evidential weight (§8). Numbers carry `<!-- src: ... -->` tags;
10	`path#key` tags are checked by `python scripts/check_report.py REPORT.md`.
11	
12	Arms: **FINAL** = A4b:n1_linear, raw cosine (the frozen method). **N1** = its non-learned input descriptor.
13	**L4** = point-cloud EGNN (best dev candidate, more complex). **A1** = typed volumetric fingerprint on the raw site.
14	**B0** = pocket size. **B1** = BURROW's own descriptors. **B4** = ESM-2 lining-residue embedding. **B5** = EPoCS.
15	**B5-T** = the APoc / G-LoSA / SiteEngine scores shipped with TOUGH-M1. **B0′** = global fold similarity.
16	**L-mode** = pocket cut as a 4 Å shell around the bound ligand. **D-mode** = the BURROW-detected pocket at the site.
17	
18	---
19	
20	## 1. Summary
21	
22	- **Too
… [48,132 more characters; full text in agent_logs/raw/]
```


**→ tool call `SubagentHandback`** · 2026-10-28 05:16:16

```
{"message": "I could not create REPORT.md: the harness blocks subagents from writing `.md` files. The finished report is at `/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/REPORT_final.txt` (sha256 62db674a…). Install it with `cp <that path> /cluster/project/beltrao/gmagnus/pocket_compare/REPORT.md`. `scripts/check_report.py` on that file gives 143 tagged numbers OK, 0 errors. Nothing was committed. The full text is also between the markers below. Prose is about 4.7k words, plus tables.\n\nThings I found while writing it that you should know about:\n1. **C5 paired holo − AF Δ is missing for FINAL.** In `final_eval.py`, `stage_blips` compares `key.split(\"|\")[1]` with the method name, and the name itself contains a `|`. FINAL was silently skipped; only B1 and B4 have the paired values. The report quotes FINAL's AF result unpaired and lists the gap as a follow-up.\n2. **Three pre-registered items were not delivered.** The blind deployment test on BLiPS-test, the PPIPS-test split by BURROW-homology flag, and the C5 Δ above. PPI-L has no score at all, because the test split has only 3 positives.\n3. **The size diagnostic fails on test.** The size-logistic baseline (B0m) still scores 0.582 after size stratification, outside the 0.5 ± 0.03 band it met on dev.\n4. **Weak spots for FINAL on test.** On BLiPS unseen chemotypes it scores 0.685 against B1's 0.770. On Vertex, global Foldseek TM scores 0.910, so that set 
… [56,815 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
