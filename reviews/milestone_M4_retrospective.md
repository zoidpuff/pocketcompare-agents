# Milestone M4 retrospective (fresh-eyes, final, 2026-10-28 ~08:30, ~14 h in)

Basis: PROMPT, RESEARCH_TREE (D22-D25, DEV5-7, P6/P7), LESSONS, M2/M3 retrospectives, REPORT s1/s9, git log. No raw or sealed data opened.

## 1. What should we stop doing?

1. **Stop shipping a frozen evaluator that was never tested on every pre-registered output.** DEV6: final_eval silently skipped C5 (method name contains "|"), the blind test and PPIPS strata; the report writer found it, not a check. Add a "every PREREG item produced a non-empty row" assertion to the dry run.
2. **Stop post-test work that cannot change a decision.** The fusion, PPI-R and atlas (exploratory) cost ~3 commits and a REPORT section; R2 then showed fusion +0.010 (p 0.34) does not replicate. Spend such time on verification or writing instead, or skip.
3. **Stop letting scripts raise on expected edge cases after unsealing.** DEV7: pdbt_pairs unsealed, run aborted on the 9 excluded sites. Dry-run on dev must include the exclusion path.
4. **Stop leaving leakage boundary calls until the audit.** D25: 9 sites at TM 0.50-0.56 and 51 near-identical non-featurised chains, found only at the PDB-T audit. Fix the leakage rule (including partner/non-featurised chains) in the PREREG, not afterwards.
5. **Stop one-off tie-breaks by the PI after seeing the table** (D19). It happened to be vindicated (R3), but was not blind; declare a total order before looking.
6. **Stop writing history in the report.** s9 retells DEV1-7, D19, re-freezes; keep a deviations table and link.

## 2. What worked well (since M3)

- **A fresh temporal set (PREREG2) with a feasibility gate, hashed before any score, frozen artefacts only.** R1 replicated (D 0.752 vs 0.671, +0.081, Holm p 0.003) and it settled the Holm-fragile L-mode claims and the fusion question without reopening the old test.
- **Independent audit + verifier again**: PDB-T audit found the boundary sites before scoring; verification confirmed R1-R3.
- **Disclosure over repair:** DEV5-7 and post-hoc items were computed with frozen functions, labelled, and not used to change the headline.
- **Number-tagged report with `check_report.py`** (143 tags) caught the DEV6 gaps and keeps numbers traceable.
- **Retrospective-driven stops were obeyed:** headline = D-mode, no test-set re-selection, fusion capped and labelled, simple head kept.

## 3. Final LESSONS.md (12 rules, project-independent)

1. Seal label tables technically (move, chmod 000, hash) at creation, in the script that writes them, updating the hash list in the same step. (DEV1 reviewer read labels pre-seal; DEV3 stale hash aborted the final run.)
2. Pre-register gates, claim family, selection and tie-break rules (a total order) in one hashed file before scores; amend only before test use. (D7/D10 gates ended paths; D6/D8/D9/D11 amendments and the D19 non-rule cost review time.)
3. Run size/trivial-feature baselines and size-stratified metrics first; report the deployment-realistic definition as primary. (B0 0.78 vs 0.489 stratified; ligand size alone ROC 0.95; D-mode headline.)
4. Freeze and unit-test the metric code on synthetic known answers and stamp its hash in outputs. (41 tests; exposed the 0.539 strata shortcut.)
5. Leakage work is done only after an independent re-implementation covering every training source, with exact identities and exhaustive search near thresholds. (D15: 16 test pockets leaked; DEV4 PPIPS-train missed; D25 boundary sites.)
6. Cap dev exploration with a trial budget, log every variant, and discount gains inside the CI/MDE. (36 variants, best +0.024 [-0.039, +0.043]; fusion +0.010 failed to replicate.)
7. Stop a path at its failed gate and do not scale compute behind it. (A2 failed D10 yet ~28k dockings ran.)
8. Prefer shipped prior-art scores to bespoke baselines. (EPoCS 0.599 ~ ESM 0.601 after 38 GPU-min; TOUGH-M1 ships three.)
9. Have a different agent verify headline numbers with its own code path and report what it finds. (1e-8 match plus DEV4, P6=P6.2, Holm fragility, PDB-T audit.)
10. Dry-run the full freeze-to-final path, incl. every pre-registered output and exclusion branch, before unsealing; keep post-freeze code out of the frozen tree. (D21 re-freezes; DEV6 skipped outputs; DEV7 abort.)
11. Keep a fresh temporal/prospective holdout in reserve to settle borderline or post-hoc claims, pre-registered and gated. (PDB-T: R1 replicated, R2/R3 clarified; Holm p 0.0495 claims stayed borderline.)
12. Operations: detach long jobs with log/marker/PID, never `pkill -f`, give scripts an argparse guard, do not `git add` dirs agents are editing, and tag every report number to a checked source. (Silent CPU run; --help re-ran splits; check_report.py caught gaps.)
