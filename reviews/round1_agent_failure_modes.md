# Round 1 review: AI-agent failure modes (DESIGN v0)

Verdict: the design states the right principles (§2 sealing, §5 controls, §7) but most are honour-system. A single PI + sub-agents
on one POSIX filesystem will, over 22 h, drift unless the rules are made mechanical. Below, ranked changes. Evidence from
pocket_detect LESSONS (items 2,3,7,9,10,13,15) is cited as PD#.

## MUST

M1. **Real sealing, not a flag.** `FINAL_EVAL=1` is an env var any agent can set. Instead: (a) at split time, move the sealed
raw files (ProSPECCTs, Vertex, TOUGH-M1-test labels, BLiPS/PPIPS-test label tables) to `data/sealed/` owned by a separate
directory with `chmod -R a-rwx` (or tar + `chmod 000`) and store only sha256 + counts in DATA.md; (b) keep *structures* (needed
for caching) separate from *labels*: caches for sealed sets may be built, label/pair files are the sealed part; (c) `final_eval.py`
requires a freeze file `FREEZE.json` (git commit hash, config hash, model-weights sha256, list of arms) whose commit is an
ancestor of HEAD and refuses if the working tree is dirty; the PI alone does the `chmod` unseal, logged in the tree with `date`.
(d) Agent briefs say: never open `data/sealed/`, never `ls` it for contents. (e) Add a detector: `scripts/audit_sealed.py` greps
all agent logs/scripts/notebooks/results for sealed filenames/label column names and checks `stat` atime on sealed files; run
before freeze. A ProSPECCTs test also includes the D1 structure smoke test: restrict to a 5-file copy made at split time.
Note: TOUGH-M1 dev/test is not sealed the same way (70% test); treat the 70% test pairs as sealed too (separate file, chmod).

M2. **Provenance sidecar on every result file.** All results written through one helper `pocketcompare.provenance.write_result(path,
df, meta)` that emits `<path>.prov.json`: git commit + dirty flag (refuse to write if dirty for anything under `results/final/`),
script path + argv, config hash, input file sha256s, seed, split id, metric-code version, node/GPU, wall time, row counts.
Reports may only cite numbers from a `results/` file with a sidecar. Add `scripts/make_report_numbers.py` that generates a
`reports/numbers.json`/LaTeX-style table from sidecar'd files; REPORT.md and tree notes include numbers by key (`{{C1.auc}}`) and
a CI-style check `scripts/check_report.py` regex-extracts every number with >=2 decimals from REPORT.md/RESEARCH_TREE.md and
fails if it is not in numbers.json (or on an explicit whitelist for literature values with citation). This is the direct detector
for "number not produced by a committed script".

M3. **One frozen metric/eval module, with tests, before any model.** `pocketcompare/eval.py` (AUC, AP, cluster bootstrap, missing-
pocket rule) is written first, unit-tested against sklearn on toy data and against a published number (a known TOUGH-M1/ProSPECCTs
baseline would touch sealed data; instead reproduce on TOUGH-M1-dev one published classical method or, at minimum, an
independently re-implemented AUC by a second agent; PD8). Its sha256 goes into every sidecar; a change after the first
result forces re-run of all numbers (enforced by hash mismatch in check_report). Missing-pocket policy implemented once inside it;
a test confirms count of pairs in == pairs scored + reported failures (no silent drop).

M4. **Pre-register selection and list policy in a committed `PREREG.md` before first test run** (PD10): primary metric, D-mode vs
L-mode for C1 (state which one is the headline: currently ambiguous), number of arms/configs tried, fusion rule, tie-breaking,
what counts as "A2 go" (gate in §3 uses TOUGH-M1-dev, fine). Any arm evaluated on dev is logged in an append-only
`results/trials.tsv` (arm, config hash, split, metric, time) so the number of looks is countable and a multiplicity statement
can be made. Dev reuse: TOUGH-M1-dev and BLiPS-val are used for gating, selection, and fusion fitting; cap this by fusion
fitted on BLiPS-val only and selection via CV on train, as in PD13; disclose any test-informed steering.

M5. **Independent verifier is a different agent AND different code path, with a fixed checklist.** §5's last line is right; make it
operational: for each headline (C1-C4), a fresh agent given only the sidecar, the frozen scripts and the raw data (not the producer's
summary or the hypothesis) re-computes the metric from predictions via its own implementation, and confirms: pair counts,
no train/test overlap (re-derive the cluster split with its own MMseqs2 call; PD9), negative-control AUC, size-baseline. The
verifier writes `reviews/verify_<claim>.md` with PASS/FAIL, and the PI may not cite a claim without it. For the split/leakage
audit (largest risk, §2.3 removal list) require this *before* any model is fit, not at the end.

## SHOULD

S1. **Silent-fallback guards.** Every pipeline stage logs `n_in, n_ok, n_fallback, n_failed` to the sidecar; the run fails
(non-zero exit) if fallback/failure rate > 2% unless a flag `--allow-fail-rate` is passed and recorded. Explicit things to
guard: BURROW learned-vs-analytic features (assert feature-set name in the cache header; learned `point_score` must not be in
tier-1 vectors), ADock stock Vina weights (assert weight hash), D-mode "missed" pockets, CPU fallback when GPU unavailable
(record device), docking failure -> min similarity. Cache keys include code hash + feature-set name so stale caches are not reused.

S2. **Hand-off protocol.** Each sub-agent gets a brief with: goal, input files + sha256, output path *inside its own directory*
(`work/<agent>/`), forbidden paths (sealed, other agents' dirs, `src/` core modules unless assigned), and a required final
message (<=15 lines: what was produced, files, commit-ready paths, counts, deviations, open doubts). Agents never edit shared files
(DESIGN, RESEARCH_TREE, LESSONS, `src/eval.py`, splits) - they write `work/<agent>/NOTE.md` and the PI merges. Shared code goes in
`src/` only through the PI after a test passes. Splits and `data/splits/*` are made read-only (`chmod a-w`) after freezing, with
hash check in `tests/`. Per-agent file lists logged (PD6) so resume after a pause works.

S3. **Concurrency on shared hardware.** One `scripts/gpu_lease.sh`/`flock`-based lock per GPU (`/tmp/gpu{0..3}.lock`) and a
documented allocation: e.g. GPU0 docking (A2), GPU1 A3, GPU2-3 A4 training; CPU budget file (BURROW caching <=32 workers, rest 
<=24, 8 reserved for PI/interactive); set `OMP_NUM_THREADS`, `CUDA_VISIBLE_DEVICES` per job. Memory cap is ~79 GB effective not
192 (PD1): size caches accordingly. Runtime measurements (C4) must be done on an otherwise idle node via a dedicated timing
script with the load recorded (`nvidia-smi`, `uptime`) in the sidecar, else the runtime claim is not valid. Kill only stored PIDs.

S4. **Context-lean PI.** PI reads only `NOTE.md`/verification files and the top-of-tree status; logs stay in `logs/`. Tree
updates are one line per node with a result key into numbers.json, not pasted numbers. Every 3 h: 10-line "state of the run"
checkpoint at the tree top (current arm table with dev metrics, open risks, next 3 actions) so a context reset resumes from it.
Commit at each hand-off, timestamps from `date` (PD3). Only PI commits (PD2).

S5. **Confirmation-bias controls.** The agent proposing an arm must not be its verifier or its negative-control author. Mandatory
red-team agent before freeze: tries to break each headline (size, ligand-class composition, protein-family shortcuts,
self-pairs, duplicated PDB entries of the same protein across pairs). Negative controls are specified *before* results: shuffled
labels, size-only, sequence/fold-only (B0'), random type permutation, and "pocket-shuffled within cluster". Report C1 also
under the unfavorable pocket mode and all arms tried (from trials.tsv), not only the winner.

S6. **Compute/time boxes.** Each arm gets a wall-clock and GPU-hour budget and a kill criterion in the tree at launch (PD14);
A4 training capped (e.g. 2 GPU-h per seed, 5 seeds); PPIPS construction (§2.4 interolog + US-align) is the riskiest
build: time-box 3 h, fall back to P-sym + P-ortho by sequence-orthology only and say so. Disk: a `du` check in the 3-hourly
checkpoint; delete caches only via script, never `rm -rf` globs.

## COULD

C1. Append-only `results/ledger.jsonl` hash-chained (each line includes hash of the previous) so deletions or edits of earlier
results are detectable; cheap and a good audit trail for 22 h.
C2. Read-only git worktree (`git worktree add`) for final_eval at the frozen commit (PD15); test branch-boundary exactness on
fixed thresholds (pLDDT, 4 Å cut-offs).
C3. A second agent independently re-implements the L-mode adapter (§2.1) on 50 pockets and compares point sets (IoU >= 0.95):
all downstream numbers depend on it and "pocket definition used identically" is a hidden degree of freedom.
C4. Seeds: single `seeds.py` imported everywhere; a grep-test fails if `random_state=`/`np.random.seed(` literals appear in src/scripts.

## Specific gaps in DESIGN v0
- §2.2: "5-pocket parser smoke test on D1" is a label-free read, fine, but implement it on a pre-made 5-file copy.
- §2 sealing says "sealed sets read only by final_eval.py" but TOUGH-M1-test (70%) is also needed to stay sealed for C1; state it.
- §7 lists principles only; fold M1-M5 and S1-S5 into it as mechanisms, with owner (PI vs verifier).
- C1 threshold (+0.03) and tests are fine; add that trials.tsv count is reported next to it.
