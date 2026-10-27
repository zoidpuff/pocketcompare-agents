# Milestone M2 retrospective (fresh-eyes review, 2026-10-27 ~22:30, ~4.5 h in, ~19 h left)

Basis: PROMPT, RESEARCH_TREE, LESSONS, git log (30 commits), reports/ and reviews/ headers. No raw data, logs or sealed files opened.

## 1. What should we stop doing?

1. **Stop investing in A2 (docking descriptor) beyond the pre-registered PPI sub-test.** The gate failed (D10: fusion stratified dAUC -0.010; every variant negative), yet 7,524 L + 6,068 D TOUGH-M1 dockings and 20,497 PPIPS dockings were run, plus a 27-pocket feasibility study. This is the PI's headline idea, so a clean negative is worth reporting. It is not worth another GPU-hour or agent-hour, and it should not re-enter fusion.
2. **Stop adding external baselines and env hacks.** B5/EPoCS cost ~38 min GPU plus a pymol/micromamba env and an LD_LIBRARY_PATH silent-CPU incident, and landed at 0.599 vs B4 0.601 (dev). B5-T (APoc/G-LoSA/SiteEngine) ships with TOUGH-M1 for free and is the more useful comparator. Freeze the baseline set.
3. **Stop open-ended exploration on TOUGH-M1-dev.** Definition robustness logged 36 variants on 731 pockets; the best hybrid gains +0.024 with CI [-0.039, +0.043], and D-mode vs B1 is +0.052 [-0.004, +0.134]. Test MDE is ~0.13 (D12) while dev delta was +0.152. This is a forking-paths risk: further dev picking will mostly select noise, and D13 already picks from the 36. Freeze the tier-1 candidate list at D13 and spend the time on A4b, the audit and the test-protocol dry run.
4. **Stop amending the protocol piecemeal.** In 4 h we have D6, D8 (+ secondary eval), D9, D11 (new claim C1-D, new Holm family) and C3 downgraded. Each was dated and made before test use, which is fine, but the claim family has changed twice and each change was triggered by dev results. Rule from here: one consolidated "PRE-REGISTRATION v3" file with a hash, written before A4b is fit; after that, no claim, metric, split or strata edits (only bug fixes with a disclosed note).
5. **Stop treating "required before" items as soft.** The independent split audit is still [~] although DESIGN says it must finish before the first model fit (A4b). Likewise open: Vertex 188 structures missing, loader chain-"A" bug (3,191 files), A1 provenance re-run from a clean tree. These are the things that cause an unreliable or protocol-violating final number. Close them before any A4b training; make `final_eval`/train scripts refuse to run without the audit marker.
6. **Stop launching agents before the guard rails exist** (DEV1: a reviewer opened labels 2 min before sealing). Sealing is now technical (chmod 000), good, but the same class of risk remains for new sealed tables (PPIPS test, BLiPS test): any new label file must be sealed at creation by the script that writes it, not afterwards.
7. **Stop reporting only mean(L,D)-style selection objectives that reward the known artefact.** D13 itself admits mean(L,D) still rewards the L-mode ligand imprint. Report D-mode, ligand-free results as the primary deployment number everywhere, L-mode as secondary.
8. **Process overhead that is not paying off:** a 14 KB tree whose Decisions block mixes status and rationale (D13 text is already hard to scan); reports duplicate tree bullets. Keep the top summary + decisions short and link the reports. Do not add a 3rd review round; the two done caught real issues (percolation, augmentation leakage, vacuous strata) and a third is low yield.

## 2. What worked well (keep)

- **Technical sealing + hashes + an honestly disclosed deviation (DEV1).** Costs minutes, makes the final test defensible.
- **Pre-registered gates recorded before scores.** A2 gate (D10) and PPI-L gate (D7, recorded before any similarity was computed) each ended a path in one run without argument.
- **Size baselines first (B0, B0m, stratified AUC).** B0 alone ROC 0.78, B0m 0.857 but 0.489 stratified; this reframed every later number and exposed the fragment-size confounder (rho -0.74).
- **Label-free diagnostics before label use** (same-site L vs D agreement: A1 0.70 vs B1 0.94). This found the ligand-imprint problem (A1 0.808 -> 0.560 in D-mode) without touching test and drove the best decision of the project (D11).
- **evaluate.py written and frozen first, on synthetic data with known answers (41 tests, hash in every sidecar)**, and sample-size/power computed (D12) before the test.
- **Independent verification by a different code path** (verify_splits 66 -> 97 checks; MMseqs + Foldseek graph; per-dataset components after round 2 showed the global graph percolates at 49.8 %).
- **Parallel agents with a report-per-agent and a trial log (`results/trials.tsv`, 137 + 36 rows).** Tree + reports let the PI stay lean.
- **Leakage-first split design:** found 32 % of TOUGH-M1 homologous to BURROW training before any modelling.

## 3. Proposed pruned LESSONS.md (10 rules)

1. Seal label/pair tables technically (move + chmod 000, sha256) at creation, before any agent or reviewer launches. (DEV1: reviewer read TOUGH-M1 labels 2 min before sealing.)
2. Record gates and the claim family in a hashed pre-registration before computing scores; amend only before any test use, once, in one consolidated file. (D10, D7 gates stopped work cleanly; D6/D8/D9/D11 amendments cost review time.)
3. Run size-only baselines and size-stratified AUC first on any pocket-pair benchmark. (B0 ROC 0.78 vs B0m stratified 0.489; fragment score vs volume rho -0.74.)
4. Evaluate in the deployment pocket definition (detected, ligand-free) beside the ligand-defined one, and use label-free L-vs-D agreement as a pre-check. (A1 0.808 -> 0.560; agreement 0.70 vs B1 0.94.)
5. Freeze the metric module first and test it on synthetic data with known answers; stamp its hash in every output. (evaluate.py, 41 tests, hash in sidecars.)
6. "Done" for data, split or leakage work needs an independent re-implementation, and it must finish before anything is fitted on it. (verify_splits 97 checks; global graph percolated at 49.8 %; audit still open at M2.)
7. Cap dev exploration: log every variant, fix a trial budget, and discount gains whose CI includes zero given test MDE. (36 variants, best +0.024 [-0.039, +0.043]; MDE ~0.13.)
8. Stop a path when its gate fails; do not scale compute behind a failed gate. (A2: negative on dev, yet ~28k dockings were still run.)
9. Reproduce a published number or use shipped prior-art scores before building a new baseline; avoid costly bespoke baselines with no marginal information. (B5 0.599 ~ B4 0.601 after ~38 min GPU + env hacks; TOUGH-M1 ships APoc/G-LoSA/SiteEngine.)
10. Run jobs > 5 min detached with log + marker and PID; never `pkill -f`; append to LD_LIBRARY_PATH, never overwrite; check mounts and caps first. (Overwritten LD_LIBRARY_PATH silently ran EPoCS on CPU; /rsyncPDB not mounted, D1.)
