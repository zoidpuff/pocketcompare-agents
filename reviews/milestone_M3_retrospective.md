# Milestone M3 retrospective (fresh-eyes review, 2026-10-28 ~05:15, ~11.5 h in, 6-10 h left)

Basis: PROMPT, RESEARCH_TREE (M3, D15-D21, DEV1-4), LESSONS, M2 retrospective, git log (80 commits), verification_final.md, report headers. No raw data or sealed files opened.

## 1. What should we stop doing?

1. **Stop using the test set as information.** It is now spent. Any change to the method, head, claims or strata after seeing results/final is post-hoc. A4b+L4 fusion, the CLI and the proteome fingerprints are "exploratory, dev-selected": select on BLiPS-val/PPIPS-val only, never re-run TOUGH-M1-test to compare variants, and keep the frozen A4b:n1_linear as the headline in REPORT.md.
2. **Stop trying to rescue the Holm margin.** C1a/C1b pass at p 0.0165/0.0185 against a 0.0167 threshold. The verifier's B = 20k gives 0.0164/0.0171, and 30-50 % of B = 2000 reruns would fail. Do not re-bootstrap until it passes or change the family. Report "borderline, MC-fragile" and lead with C1-D (p 0.006-0.0095, robust).
3. **Stop leading with L-mode numbers.** Ligand heavy-atom count alone gives ROC 0.95 on TOUGH-M1, and B0 is 0.80 on test (0.56 in D-mode). Headline = D-mode (C1-D, Vertex, BLiPS-test); L-mode only as secondary with the imprint caveat. Also stop quoting ProSPECCTs 0.99 as strength (near-ceiling, C2 not significant).
4. **Stop counting P6.2 as an independent condition.** P6 and P6.2 are identical by construction (BURROW strips HETATM, pockets.py:252), so the C2 macro Δ effectively double-weights P6. D-mode on P6 has 4 usable pairs. Disclose it as DEV5; do not re-run it.
5. **Stop open-ended L4/fusion work.** L4 was a pre-declared "last candidate" and its gain on BLiPS-val D (0.756, SE 0.040) is inside the one-SE rule. Give fusion one capped slot (about 1 h, ≤ 6 configs, logged in trials.tsv). If it does not beat the n1_linear threshold on val, drop it and write.
6. **Stop one-fix-at-a-time freeze/hash firefighting.** DEV2-DEV4 and four freeze re-commits (afdae23, 5c5555a, f706931, 809d2ad) each came from a single-source-of-truth gap (sealed hash list, worktree path, stale FREEZE.json). From now on, no further changes to code under the frozen tag except bug fixes with disclosure. New exploratory code goes into a separate directory/namespace so freeze.json hashes stay valid.
7. **Stop discovering leakage after the fact.** DEV4 (66 test pockets homologous to PPIPS-train chains, found by the verifier at 05:30) shows the audit covered the primary training sets and not every training source. Report the with/without sensitivity (C1a Δ +0.135 without) in REPORT.md. Any new training for exploratory heads must reuse the same audit across all sources.
8. **Stop writing narrative in three places.** Tree bullets, reports/*.md and PREREG repeat each other, and D13-D21 are hard to scan. For REPORT.md, build one results table from verification_final.md and results/final/ and link reports; do not retell the history. Do not add a lesson per incident (13-15 are one-off operational fixes).

## 2. What worked well (since M2)

- **M2 stop-list was acted on.** A2 stopped at its gate, the baseline set froze, and the audit became a blocking gate. It then failed (D15: 16 test pockets leaked past a 30 % score-based rule) and was fixed by an mmseqs `-a` plus exhaustive Foldseek rebuild before any model fit.
- **Pre-declared selection rules, one-SE threshold, trials log.** The D19 tie-break was caught as a non-rule and corrected before L4; D20 picked the simpler n1_linear over L4. This made the final choice defensible.
- **Freeze → worktree → hash guard → dry run with max dev 0.** The hash guard caught the stale sealed list (DEV3) rather than silently scoring the wrong data.
- **Independent verifier with its own code path** (no import of final_eval/evaluate): every headline reproduced to ≤ 1e-8 and, beyond that, it found DEV4, the P6≡P6.2 identity, the Holm fragility and the ligand-size shortcut (0.95). This is the highest-value step of the project.
- **Methodological finding turned into a deliverable.** The ligand-shell imprint was caught at M2 by label-free L-vs-D checks, carried through to final claims (C1-D), and quantified by the verifier.
- **Robustness and deployment evidence kept separate:** AF-vs-holo (BLiPS-test AF ≈ holo), Vertex 0.822, PPIPS P-ortho MRR 0.683, human proteome demo with timing.

## 3. Proposed pruned LESSONS.md (12 rules; merges the current 15)

1. Seal label/pair tables technically (move, chmod 000, sha256) at creation by the script that writes them, and update the recorded hash list in the same step. (DEV1: reviewer read labels 2 min before sealing; DEV3: stale hash aborted the first final run; the guard itself worked.)
2. Pre-register gates and the claim family in one hashed file before computing scores; amend only before test use. (D7/D10 gates ended paths cleanly; D6/D8/D9/D11 piecemeal amendments cost review time.)
3. Run size-only baselines and size-stratified AUC first, and report the deployment (detected, ligand-free) definition as primary. (B0 0.78 vs stratified 0.489; A1 0.808 -> 0.560 in D-mode; ligand heavy-atom count alone gives ROC 0.95.)
4. Freeze and unit-test the metric module on synthetic data with known answers; stamp its hash in every output. (evaluate.py, 41 tests; it exposed the 5x5 strata shortcut 0.539.)
5. Data/split/leakage work is "done" only after an independent re-implementation, run before fitting and covering every training source. (verify_splits 97 checks; global graph percolated at 49.8 %; DEV4 missed PPIPS-train.)
6. Use exact alignment identities (mmseqs `-a`) and exhaustive structure search near thresholds. (Score-based identity leaked 16 test pockets past 30 %, D15.)
7. Cap dev exploration with a declared trial budget and tie-break rule, log every variant, and discount gains whose CI includes zero given the test MDE. (36 variants, best +0.024 [-0.039, +0.043]; D19 "grid order" was not a rule.)
8. Stop a path at a failed gate; do not scale compute behind it. (A2 failed D10 yet ~28k dockings ran.)
9. Prefer shipped prior-art scores to bespoke baselines. (B5 EPoCS 0.599 ~ B4 0.601 after ~38 GPU-min; TOUGH-M1 ships APoc/G-LoSA/SiteEngine.)
10. Always have a different agent verify headline numbers with its own code path, and report what it finds (fragile p-values, identical conditions, shortcuts). (verification_final: 1e-8 match plus DEV4, P6=P6.2, Holm margin.)
11. Dry-run the full freeze -> worktree -> preflight path before the freeze, and keep post-freeze code changes out of the frozen tree. (Read-only parent mount and stale FREEZE.json forced D21 re-freezes; four re-freeze commits.)
12. Operations: detach jobs > 5 min with log, marker and PID; never `pkill -f`; append to LD_LIBRARY_PATH; give no-arg scripts an argparse guard (`--help` executes them); do not `git add` dirs agents are editing. (Silent CPU ESM run; --help re-ran split scripts; in-progress pockets.py swept into a commit.)
