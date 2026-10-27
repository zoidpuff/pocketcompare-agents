# Research tree — pocket similarity on BURROW

Legend: [ ] planned · [~] in progress · [x] done · [-] abandoned/negative · [!] key finding
Started 2026-10-27 ~18:00 CET; 24 h budget (revisit ~2026-10-28 18:00).

## Status summary (latest first)

### 2026-10-27 18:15 — M0 kickoff
Scaffold, venv (BURROW importable via read-only .pth on ../pocket_detect/src), PROMPT.md saved. BURROW
export smoke test passes (1a28: top pocket 0.626, 312 pts). Phase 1 launched in parallel: literature review,
public benchmark acquisition, fragment-docking feasibility (ADock), PPI/dimer pocket characterization.

Nothing modelled yet. No held-out data touched. Next: LITERATURE.md → DESIGN.md → ≤3 review rounds.

## Decisions
- D0 (18:10) Repo on branch `pocket-compare`; identity gmagnusson (same as pocket_detect). pocket_detect is a
  read-only mount, so it is imported via a .pth path, not installed. Seeds fixed: `pocketcompare.seeds.SEEDS = [0..4]`.

## Tree
- [~] P1 Literature review → LITERATURE.md
- [~] P1 Public benchmark acquisition (ProSPECCTs, TOUGH-M1, Vertex, Kahraman, ...) → DATA.md
- [~] P1 Fragment-docking feasibility (ADock throughput, fragment library)
- [~] P1 PPI / dimer pocket characterization (BURROW on AFDB dimers)
- [ ] P2 DESIGN.md draft + review rounds (≤3)
- [ ] P3 Implement + evaluate candidate representations
- [ ] P4 Final held-out evaluation, REPORT.md
