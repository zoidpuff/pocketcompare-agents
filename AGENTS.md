# How the agents worked

This file describes the agent team that produced `pocketcompare`: who the agents were, how work was delegated,
how the project unfolded, and what went right and wrong. It is written by the lead ("PI") agent from the project
record. Per-agent numbers are in [AGENT_ROSTER.md](AGENT_ROSTER.md) (generated from the transcripts). The full
transcripts are in [agent_logs/](agent_logs/). A broader account of the science and the process is the research
briefing, [pocketcompare/docs/BRIEFING.md](pocketcompare/docs/BRIEFING.md) (§10 covers the process).

## 1. Setup

- **One human prompt.** A scientist wrote [PROMPT.md](PROMPT.md): the goal (a fast, fold-independent pocket-similarity
  method on top of the BURROW pocket finder, usable at AlphaFold-database scale and for protein–protein-interface
  pockets), process rules (literature review, independent design review, leakage-free splits with a held-out test,
  pre-specified metrics, independent verification, a research tree, a lessons file, runtime next to accuracy) and
  one idea offered as a "human prior" (fragment-docking fingerprints). Budget: 24 hours.
- **No human input during the research.** Between the prompt (27 Oct, 18:00 CET) and the end of the research (28 Oct,
  ≈ 08:30) the human did not intervene. Afterwards the human asked follow-up questions (which baselines were used, how
  the fingerprint works, AFDB cost, which pockets are kept) and requested the briefing and the two repositories; those
  exchanges are at the end of the PI transcript.
- **Software and hardware.** One Claude Code session (Claude Agent SDK) running Claude Opus 5.5 as the PI, inside a
  Singularity container on one node of ETH Zurich's Euler cluster: 64 CPU cores, 4 × RTX 4090, ≈ 190 GB RAM, a
  500 GB storage cap, read-only mounts of the sibling projects (BURROW, the docking engine ADock), network access.
  Permission prompts were switched off; the container was the sandbox.
- **Git.** The PI committed to a local repository throughout (89 commits on branch `pocket-compare`, 27 Oct 18:29 →
  28 Oct 11:08; this repository keeps that history). Sub-agents were told not to commit; the PI committed their work
  after reviewing their report. There was no push credential.

## 2. The agent hierarchy

```
human ── PROMPT.md
  └─ PI agent (Claude Opus 5.5): plans, delegates, reviews, decides, commits, keeps RESEARCH_TREE.md / LESSONS.md
       ├─ 45 sub-agents launched with the Agent tool (37 Opus, 8 Sonnet), each in the background with a written brief
       │    └─ 3 nested sub-agents launched by the literature agent (catalogue of methods, benchmarks, PPI/leakage)
       └─ 14 re-briefs (SendMessage) to running or finished sub-agents
```

- **Sub-agents were general-purpose Claude Code agents** with the same tools as the PI (shell, files, web), started in
  the background. They knew only their brief: a self-contained instruction of median ≈ 3,100 characters (up to 5,900)
  naming the goal, the files to read first, the rules (e.g. "never open `data/sealed/`", "do not commit", "≤ 16 CPU
  threads, GPU cuda:1 only"), the outputs, and a word limit for the final report.
- **Model choice.** Opus for building, analysis, review and writing; Sonnet for cheaper, well-specified tasks (the
  agent-failure-modes review, the ESM-2/EPoCS baselines, the AlphaFold-robustness and blind-test scripts, the three
  milestone retrospectives, the reproduction script).
- **Hand-backs.** Each sub-agent ended with a short report (typically ≤ 250 words) delivered to the PI. The PI read
  reports, not raw logs, to keep its own context small, and opened files only when a decision needed it.
- **Re-briefs** were used to relay design-review changes to builders already running, to give "go" signals after an
  audit gate, to request fixes (the split rebuild after the failed audit), and to ask the auditor and verifier for
  extra checks. Agents that keep their context made these cheap.
- **Parallelism.** Up to seven sub-agents ran at once. GPUs and CPU budgets were assigned per brief
  (e.g. "cuda:0 and cuda:2 only, ≤ 8 CPU workers").

### Roles (48 sub-agents)

| role | agents (roster #) | what they did |
|---|---|---|
| literature and data scouting | 1 (+1.1–1.3), 2, 3, 4 | literature review with provenance tags; download and check public benchmarks; docking feasibility and cost; characterise PPI pockets in AFDB dimers |
| design reviewers | 5–10, 12 | round 1: external PI, statistics, data/leakage, algorithms/compute, AI-agent failure modes, domain (FBDD/PPI); round 2: combined panel |
| builders | 11, 13–18, 20 | pocket adapter, evaluation module, homology graph and splits, PPI datasets, typed fingerprint and baselines, ESM-2/EPoCS baselines, docking descriptors, caches |
| development evaluators and explorers | 19, 22, 23, 29, 30 | dev evaluation of all arms; pocket-definition robustness; validation evaluation; AlphaFold robustness; blind-search test |
| model builders and selection | 26, 28 | learned metric heads (A4b) and final selection; graph neural network (L4) |
| independent checkers | 21, 32 | split audit (re-briefed twice: re-audit, temporal set); verifier of the final and temporal results |
| infrastructure | 24, 27, 41 | proteome-scale demo; final-evaluation machinery with dry run; reproduction script |
| milestone retrospectives | 25, 35, 42 | fresh agents asked "what should we stop doing?" and "what worked well?" and proposed pruned LESSONS |
| post-test work | 33, 34, 37, 38, 39, 40 | exploratory fusion; API/CLI and human-proteome release; exploratory PPI tests; completion of missing reported items; temporal replication set and its evaluation script |
| writers | 31, 36, 45, 44 | report draft, final report, briefing text, briefing figures |
| release | 43 | standalone `pocketcompare` repository |

## 3. How the work went

The timeline figure is [pocketcompare/docs/figures/fig9_process.png](pocketcompare/docs/figures/fig9_process.png);
the decision log is [RESEARCH_TREE.md](RESEARCH_TREE.md) (decisions D0–D26, deviations DEV1–DEV7, dated).

| phase (CET) | what happened |
|---|---|
| 18:00–19:05 kickoff | PI saved the prompt, inspected mounts, built the environment; four parallel scouts (literature, benchmarks, docking feasibility, PPI pockets) |
| 19:05–20:10 design | DESIGN v0 → six independent reviewers → v1 → review panel → v2; benchmark labels sealed (19:12); one reviewer had read TOUGH-M1 labels two minutes earlier and disclosed it (DEV1) |
| 19:20–21:30 build | seven builders in parallel: evaluation module (frozen, 41 tests), homology graph and splits, PPI sets, descriptors, baselines, docking profiles |
| 21:30–03:40 development | fragment docking fails its pre-registered gate; the ligand-size imprint of ligand-defined pockets is found and a detected-pocket claim added; the split audit fails (MMseqs2 without exact alignments) and all splits are rebuilt before any model fit; learned heads and a graph network are trained; final method selected and frozen (03:40) |
| 03:40–05:35 test | sealed test sets opened once by the frozen evaluation (one abort on a stale checksum, re-run); independent verification reproduces every headline |
| 05:35–08:30 post-test | exploratory work, report, completion of three missing pre-registered items (one evaluation bug), and a pre-registered temporal replication on PDB entries released after all training data; stop decision (D26) |
| after 08:30 | follow-up requests from the human: AFDB cost benchmarks, briefing, figures, repositories |

## 4. Cost

- **Session cost record** (Claude Code's cost tracker, covering 27 Oct 18:01 to ≈ 28 Oct 09:18, i.e. the research and
  the first follow-ups, PI and sub-agents together): **≈ $327**: Opus 5.5 $286, Opus 5 $35, Sonnet 5.5 $5,
  Haiku 5.5 $2 (144 web searches). The raw record is the `cost-state` line in
  `agent_logs/raw/main_session_PI.jsonl.gz`. Later work (briefing, repositories) is not included.
- **Sub-agents** (from their completion reports): 9.2 M tokens in total (median ≈ 210 k per agent; the largest, the
  split builder, ≈ 500 k), 27.6 h of summed agent wall time over ≈ 16 h of elapsed time.
- **Compute.** The heaviest jobs were docking (≈ 75 GPU-min), feature caches and descriptors (minutes each), the
  proteome demo (3 min on 2 GPUs) and homology searches (the exhaustive Foldseek rebuild ≈ 1 h).

## 5. What the record shows about agent behaviour

Observed, with the evidence in RESEARCH_TREE.md, LESSONS.md, `reviews/` and the transcripts:

- **Safeguards had to be mechanical.** The round-1 reviewer of agent failure modes judged the first design
  "honour-system" and asked for technical sealing, a freeze file, provenance sidecars, a metric module written first
  and an independent verifier. Each of these later caught something (see the briefing, §10).
- **Agents disclosed their own slips**, often unprompted: a reviewer reading labels before sealing (DEV1), a split
  script reading a sealed file three times while debugging, an agent running a GPU test it was not asked to, agents
  exceeding CPU budgets (two used ≈ 46–60 cores against a budget of 22–24).
- **Errors were ordinary and were caught by other agents**, rarely by their producer: a missing `-a` flag in MMseqs2
  (audit), an invented "grid order" tie-break (PI), a string-split bug that silently skipped a pre-registered
  comparison (report writer), an incomplete leakage check (verifier), a stale checksum list (the freeze guard).
- **Independent agents disagreed productively.** Review rounds changed the split design, the statistics and the
  claims; the auditor failed the splits; the verifier found that two claims were Monte-Carlo-fragile; retrospectives
  stopped work on failed paths and capped post-test exploration.
- **Fresh agents were good critics.** The three retrospectives, each run by a new agent that had not done the work,
  produced the most direct process corrections ("stop trying to rescue the Holm margin", "stop post-test work that
  cannot change a decision").
- **The PI's own decisions were not always blind.** The tie-break between learned heads (D19) was made after seeing
  the table; it is recorded as such. The PI also added post-test exploratory analyses that, in the end, could not
  change a decision until a fresh held-out set was built.
- **Harness quirks shaped the work.** Sub-agents could not write some Markdown files at the repository root (the PI
  saved their text); background agents sometimes notified twice; `--help` on argument-less scripts executed them;
  an overwritten `LD_LIBRARY_PATH` silently moved a GPU job to CPU.
- **The research tree worked as memory.** The PI kept decisions, times and status summaries in RESEARCH_TREE.md, so
  that the state of the project could be recovered from one file rather than from the conversation.

## 6. Reading the transcripts

- `agent_logs/readable/main_session_PI.md`: the PI's side, in order (its messages complete; tool inputs and outputs
  truncated to 1,500 characters).
- `agent_logs/readable/subagents/agent-<id>.md`: each sub-agent from its brief to its final report. The roster links
  each row to its file.
- `agent_logs/raw/`: the full records as gzipped JSONL (one JSON object per line; `type` = user / assistant /
  attachment / queue-operation / cost-state), sub-agent `meta.json` files (description, model, parent) and the large
  tool outputs the harness stored separately (`tool-results/`).
- Timestamps in the raw files are UTC (CET = UTC + 1).
- Export and redaction: `scripts/meta/export_transcripts.py`; counts in `agent_logs/EXPORT.json`.
