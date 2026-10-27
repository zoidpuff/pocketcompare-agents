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
- D2 (19:12) Technical sealing: all benchmark pair/label tables moved to `data/sealed/` (chmod 000, sha256 in
  `data/sealed_SHA256SUMS.txt`). Raw label lists under data/raw/ are sealed by protocol (agents told not to read
  them). Before sealing, the data agent only counted pairs (no analysis). TOUGH-M1 dev pairs will be extracted by
  a split script that writes dev pairs only. Point featurisation of structures (label-free) is allowed for all sets.
- D1 (18:25) Mount check: `/cluster/work/beltrao/shared/rsyncPDB` (referenced by pocket_detect manifests) is NOT
  mounted; use `/cluster/scratch/jjaenes/pdb/<mid2>/<id>.cif.gz`. BioLiP2 snapshot 2025-11-12 is readable at
  pocket_detect/data/raw/biolip2/current (read-only) — candidate source for a ligand-labelled pair set.
- D0 (18:10) Repo on branch `pocket-compare`; identity gmagnusson (same as pocket_detect). pocket_detect is a
  read-only mount, so it is imported via a .pth path, not installed. Seeds fixed: `pocketcompare.seeds.SEEDS = [0..4]`.

## Tree
- [~] P1 Literature review → LITERATURE.md
- [x] P1 Public benchmark acquisition → DATA.md, reports/data_benchmarks.md, tests/test_datasets.py (4 pass)
  - [x] ProSPECCTs 10 subsets (6,093 pockets; counts exact). Click-through licence, NO redistribution → never commit
  - [x] TOUGH-M1 7,524 pockets, 505,116 pos / 556,810 neg (exact); residue numbering renumbered vs PDB
  - [x] Vertex 6,218 pockets (+1 pos vs DeeplyTough's parser bug; kept as-is); labels are per protein pair
  - [x] TOUGH-C1 (classification), KLIFS metadata (14,917 structures); LIGYSIS/PoSSuM recorded, not fetched
  - [ ] Re-run scripts/data/build_benchmarks.py once PDB mirror sync completes (188/6,029 Vertex structures missing)
  - pitfalls: ProSPECCTs self-pairs counted as actives (P7: 49/115); TOUGH-M1 ∩ TOUGH-C1 = 2,611 PDB IDs
- [x] P1 Fragment-docking feasibility (ADock throughput, fragment library) — reports/fragment_docking_feasibility.md
  - [x] ADock runs from our .venv + /tmp/adock/overlay (cupy etc.; scripts/feasibility/setup_adock_overlay.sh)
  - [x] `frag_lite_np` preset: 0.82 ms/fragment×pocket GPU; node ≈150 pockets/s @64 frags; AFDB×5 ≈ 78 node-days
  - [x] Seed reproducibility r ≥ 0.98; same-site pairs r ≈ 0.8 (n=2, anecdotal)
  - [!] Size confounder: mean frag score vs volume Spearman −0.74; pocket mean = 57 % of variance → must normalise
        and must beat a volume-only baseline (n=27 pockets, anecdotal)
  - [-] Probe-atom energy maps on BURROW points and rigid GPU scan: poor signal / no faster (prototype only)
- [~] P1 PPI / dimer pocket characterization (BURROW on AFDB dimers)
- [~] P2 DESIGN.md draft v0 (19:15) + review round 1 (PI, stats, data, algorithms, agent-failure, domain)
  - [x] R1 agent-failure-modes review → reviews/round1_agent_failure_modes.md (sealing, eval-first, provenance)
- [~] P3 Pocket adapter (L/D-mode) + point-feature cache on TOUGH-M1 (label-free)
- [ ] P3 Implement + evaluate candidate representations
- [ ] P4 Final held-out evaluation, REPORT.md
