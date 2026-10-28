# pocketcompare-agents

The complete record of an experiment in agentic science: one human prompt, one lead AI agent and 48 sub-agents
built, tested and documented a protein binding-pocket similarity method in about 16 hours, without human input
during the research.

The method itself is published separately as [`pocketcompare`](https://github.com/zoidpuff/pocketcompare) (also
included here under [pocketcompare/](pocketcompare/)). This repository holds everything else: the prompt, the
agents' plans and decisions, design reviews, pre-registrations, audits, verifications, retrospectives, every result
file, the full development git history, and the transcripts of every agent.

**Start here**

1. [pocketcompare/docs/BRIEFING.md](pocketcompare/docs/BRIEFING.md): the research briefing, written for a broad
   audience, covering both the science and the agentic process, with figures.
2. [AGENTS.md](AGENTS.md): how the agent team was organised, how the work went, what it cost, and what the record shows
   about agent behaviour. [AGENT_ROSTER.md](AGENT_ROSTER.md) lists all 48 sub-agents with model, cost and a link to
   each transcript.
3. [PROMPT.md](PROMPT.md): the only human input to the research, verbatim.
4. [RESEARCH_TREE.md](RESEARCH_TREE.md): the PI agent's running record (status summaries, decisions D0–D26 and
   protocol deviations DEV1–DEV7, with times).
5. [agent_logs/readable/main_session_PI.md](agent_logs/readable/main_session_PI.md): the PI's transcript, in order.

## What is where

| path | content |
|---|---|
| `PROMPT.md` | the human brief (fixed goal, process rules, one "human prior" idea) |
| `RESEARCH_TREE.md` | research tree: status summaries per milestone, decisions, deviations |
| `LITERATURE.md` | literature review (methods, benchmarks, published numbers, provenance tags) |
| `DESIGN.md` | the design (v0 → v1 → v2) with change logs from the review rounds |
| `PREREG.md`, `PREREG2.md`, `FREEZE.json` | pre-registered claims and rules; the frozen method (commit, config and weight hashes); the temporal replication plan |
| `REPORT.md`, `REPORT_draft.md` | the final technical report (numbers tagged to source files) and its pre-test draft |
| `LESSONS.md` | process rules the agents distilled, pruned at each milestone |
| `DATA.md` | every dataset and tool: source, version, checksum, licence |
| `reviews/` | design reviews (round 1: six reviewers; round 2: panel) and milestone retrospectives (M2, M3, M4) |
| `reports/` | one report per delegated task (data, methods, evaluations, audit, verification, exploratory work, cost) |
| `results/` | result tables with provenance sidecars (`.prov.json`), trial log (`results/trials.tsv`), final and temporal test results, verification outputs |
| `data/splits/` | train/validation/test split tables and the homology graph summaries (test labels are not included) |
| `src/`, `scripts/`, `tests/`, `configs/` | the research code as it was developed (`src/pocketcompare/`), including evaluation, splits, descriptors, models, final evaluation |
| `docs/` | `FINGERPRINTS.md` (hand-over note), `AFDB_COST.md` (cost of running on the whole AlphaFold DB) |
| `pocketcompare/` | the standalone method repository with its own history (git subtree of github.com/zoidpuff/pocketcompare) |
| `agent_logs/` | transcripts of the PI and all sub-agents: `readable/` (Markdown) and `raw/` (gzipped JSONL, sub-agent metadata, stored tool outputs); `EXPORT.json` = redaction counts |
| `AGENTS.md`, `AGENT_ROSTER.md`, `agent_roster.csv` | the agent team, the process, and per-agent statistics |
| `scripts/meta/` | export of the transcripts (`export_transcripts.py`) and the roster builder (`build_agent_roster.py`) |
| `RESEARCH_README.md` | the research repository's own README (install, usage, reproduction of the research code) |

## The git history

Git was used throughout. `git log --reverse` replays the project from the first scaffold commit (27 Oct 2026, 18:29
CET) to the end of the work: the research history (branch `pocket-compare` of the original repository) followed by
the method repository's history merged in under `pocketcompare/`. The tag `freeze-v1` marks the frozen method that
was evaluated once on the sealed test sets. All research commits were made by the PI agent (sub-agents were told not
to commit; the agent that built the standalone method repository made its first commit). Only a few late commits carry
a `Co-Authored-By: Claude` trailer; the research commits do not, although all of them were written by agents. For this
publication the author and committer of every commit were set to `zoidpuff <zoidpuff@gmail.com>`; content, messages
and dates are unchanged, so commit hashes differ from the original repository.

## What is not included, and why

- **Large or regenerable data** (≈ 95 GB): raw downloads, point caches, descriptors, docking tables, model
  embeddings. They were git-ignored during development; `DATA.md` and the scripts say how to regenerate them.
- **Sealed test labels** (`data/sealed/`) and the raw benchmark pair lists. TOUGH-M1, Vertex and the Pasteur PPI
  set can be downloaded from their sources (DATA.md). ProSPECCTs may not be redistributed.
- **The sibling projects** (the BURROW pocket finder and the ADock docking engine), which were read-only
  dependencies.
- **Transcript redactions** (counts in `agent_logs/EXPORT.json`): the session owner's institutional e-mail address
  was replaced with the public one, account and organisation identifiers were removed, and ProSPECCTs pair-label rows
  that agents printed while building loaders were replaced with a placeholder. Harness bookkeeping records that
  duplicate the conversation or carry account data (API request records, session-bridge records) were dropped. The
  PI transcript is a snapshot taken when this repository was assembled; its last exchanges concern building this
  repository.

## Licence

Code and documentation: MIT (see `pocketcompare/LICENSE`). Data products derived from public datasets keep the
licences listed in `DATA.md`.
