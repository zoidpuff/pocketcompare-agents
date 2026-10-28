# Sub-agent a6125af1ffd03e22b — Independent verification of final results (opus)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-28 03:56:19

You are the independent verifier of a final held-out evaluation. You did not produce these results; your job is to re-derive them by a DIFFERENT code path and find any error. Project root: /cluster/project/beltrao/gmagnus/pocket_compare (git; do NOT commit; write only under results/verify/ and reports/verification_final.md). Read: PREREG.md (binding claims C1a, C1b, C1-D, C2, Holm), FREEZE.json, results/final/final_report.md and final_claims.json (the numbers to check), RESEARCH_TREE.md (D18–D21, DEV3), configs/final_method.yaml, data/splits/SPLITS.md. Env: `source .venv/bin/activate`. ≤ 16 CPU threads; GPU cuda:0 if you need it.

The final evaluation is complete, so you ARE now authorised to read the sealed test files in data/sealed/ (chmod 400 to read, restore chmod 000 immediately after each read; log each access with time + file in results/verify/unseal_log.tsv). Do not modify them.

Independent re-derivation (do NOT import scripts/final_eval.py or src/pocketcompare/evaluate.py for the metric; use sklearn.metrics.roc_auc_score and your own bootstrap code; you may use the stored descriptor files / method API to obtain scores, but independently re-compute the final method's pair scores from the stored per-pocket embeddings: check that cosine of the 3-seed 128-d embeddings averaged = what final_eval used):
1. C1a/C1b: TOUGH-M1-test pairs (data/sealed/tough_m1_test_pairs.parquet), L-mode: ROC-AUC of final method, B1, B4; Δ final−B1 and final−B4. Your own vertex bootstrap with units = connected components of (ligand cluster ∪ homology group) over test pockets (re-derive the units yourself from data/splits/tough_m1_pockets_split.parquet), pair weight c_u (same unit) or c_u·c_v, B = 2000; one-sided p. Compare to final_claims.json (point estimates must match to ~1e-6; p-values/CIs within Monte-Carlo error).
2. C1-D: same in D-mode on the common set (both pockets D-matched: coverage ≥ 0.3 or precision ≥ 0.5) — re-derive the common set yourself from the point-cache index.
3. C2: ProSPECCTs D5.2, D6.2, D7 without self-pairs (data/sealed/prospeccts_pairs.parquet; identify subsets and self-pairs yourself), macro Δ(final − B1) with independent per-subset bootstrap (homology-group units).
4. Holm correction over the four claims.
5. Sanity checks: ProSPECCTs D1 / D1.2 / D2 AUCs of the final method should be high (identical/NMR structures); shuffled-label AUC ≈ 0.5; the B0 size baseline on TOUGH-M1-test; counts of pairs/pockets per set vs SPLITS.md; check no TOUGH-M1-test pocket appears in TOUGH-M1-dev or in BLiPS-train sites (by PDB id + chain) and that the A4b model's training data (results/models/a4b/n1_linear/config.json and scripts/train_a4b.py) contained no test-set items.
6. Spot-check 3 reported items from final_report.md of your choice (e.g. Vertex AUC, BLiPS-test AUC, PPIPS-test MRR) by recomputation.
Write reports/verification_final.md (≤ 1 page): for each check PASS/FAIL with both numbers; any discrepancy explained. Final message ≤ 200 words.


### PI / user turn · 2026-10-28 03:56:19

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


**→ tool call `Bash`** · 2026-10-28 03:56:23

```
{"command": "ls && cat PREREG.md | head -300 && cat FREEZE.json && ls results/final data/sealed data/splits results/verify 2>&1", "description": "Read prereg, freeze, list dirs"}
```


**← tool result**

```
Exit code 2
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
- A4b trains on BLiPS-train v2 (+ PPIPS-train P-sym/P-ortho pairs, + L↔D same-site augmentation); never 
… [5,578 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:56:26

```
{"command": "cat results/final/final_report.md && cat results/final/final_claims.json && cat results/final/unseal_log.tsv && cat configs/final_method.yaml && ls -la data/sealed", "description": "Read final report and claims"}
```


**→ tool call `Bash`** · 2026-10-28 03:56:27

```
{"command": "cat data/splits/SPLITS.md; grep -n -A30 \"^## D18\\|^### D18\\|D19\\|D20\\|D21\\|DEV3\" RESEARCH_TREE.md | head -200", "description": "Read splits and research tree"}
```


**← tool result**

```
# SPLITS — homology graph, TOUGH-M1 dev/test, BLiPS train/val/test, PPIPS (rebuilt 2026-10-28 after audit D15)

Rebuild everything: `bash scripts/data/run_splits.sh` (≈ 1.5 h, 24 threads; seed `SEEDS[0]` = 0). Checksums:
`SHA256SUMS.txt` (sealed files: hash recorded at write time). Verification: `scripts/data/verify_splits.py`
(101 checks, 0 failures; log `logs/verify_splits.log`). Units moved vs the pre-audit commit: `split_changes.json`.

## D15 rebuild (audit `reports/audit_splits.md` FAILED with small leaks) — what changed
- MMseqs2 `search -a`: exact `fident`/`alnlen` (the score-based estimate without backtraces was too low near 30 %).
  Rule edges 1.02 M → 1.21 M.
- Foldseek **exhaustive** all-vs-all (`--exhaustive-search 1`, `-e 10`, `-a`, no prefilter) on 26,819 structures
  (every non-dimer chain + the PPIPS dimer chains; the other 8,781 AFDB-dimer sequences, used by no split, keep
  sequence edges only). 57.3 M hits. TM rule: exact TM (`--exact-tmscore 1`) for all 1.98 M hits with approximate
  min-TM in [0.45, 0.60); approximate min-TM ≥ 0.60 accepted (exact is ~0.01 below approximate; validation: 20,000
  random such pairs, all exact ≥ 0.5, minimum 0.559). Edge iff min(qTM, tTM) ≥ 0.5 either direction.
- The 45 af_set proteins without a single AFDB model are now sequence-only nodes (UniProt sequence).
- All audit example edges are present (1ecmA–3ret_B TM 0.83; 2qiaA–6uec_A id 0.327; 2qo3A–FASN 0.316;
  4xg0A–5dmhA 0.341; 3remA–1ecmA 0.81; 3nmxB–APC 0.966).
- BLiP
… [15,954 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
<persisted-output>
Output too large (166.6KB). Full output saved to: /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/befu0d08a.txt

Preview (first 2KB):
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
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | raw | L | 24337 (10160) | 0.698 [0.669, 0.855] | 0.600 (1.44) | 0.554 | 0.
… [613 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:56:32

```
{"command": "F=/home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/befu0d08a.txt; grep -n \"^## \\|^### \" $F | head -50; wc -l $F", "description": "Outline of final report"}
```


**← tool result**

```
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
1502 /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/befu0d08a.txt
```


**→ tool call `Bash`** · 2026-10-28 03:56:36

```
{"command": "F=/home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/befu0d08a.txt; sed -n 14,70p $F | cut -c1-260; sed -n 856,870p $F | cut -c1-260; sed -n 1052,1120p $F | cut -c1-260", "description": "Show key report sections"}
```


**← tool result**

```
## tough_m1_test

| subset | arm | config | variant | mode | n (pos) | ROC-AUC [CI] | AP (lift) | pAUC | cb-AUC [CI] | strat [CI] | worst |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | raw | L | 24337 (10160) | 0.698 [0.669, 0.855] | 0.600 (1.44) | 0.554 | 0.665 [0.639, 0.788] | 0.719 [0.689, 0.889] | — |
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | csls | L | 24337 (10160) | 0.641 [0.614, 0.842] | 0.523 (1.25) | 0.521 | 0.658 [0.616, 0.770] | 0.684 [0.652, 0.877] | — |
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | raw | D | 21410 (8702) | 0.699 [0.650, 0.861] | 0.587 (1.44) | 0.552 | 0.650 [0.625, 0.810] | 0.717 [0.650, 0.888] | 0.537 |
| all | FINAL | pocketcompare-final:A4b:n1_linear|raw | csls | D | 21410 (8702) | 0.638 [0.608, 0.837] | 0.508 (1.25) | 0.521 | 0.631 [0.601, 0.780] | 0.669 [0.604, 0.857] | 0.490 |
| all | N1 | N1 | raw | L | 24337 (10160) | 0.692 [0.670, 0.845] | 0.616 (1.48) | 0.569 | 0.627 [0.609, 0.803] | 0.675 [0.650, 0.856] | — |
| all | N1 | N1 | csls | L | 24337 (10160) | 0.632 [0.618, 0.825] | 0.528 (1.26) | 0.527 | 0.607 [0.579, 0.775] | 0.645 [0.628, 0.838] | — |
| all | N1 | N1 | raw | D | 21410 (8702) | 0.655 [0.605, 0.805] | 0.569 (1.40) | 0.555 | 0.615 [0.579, 0.785] | 0.641 [0.574, 0.833] | 0.503 |
| all | N1 | N1 | csls | D | 21410 (8702) | 0.608 [0.588, 0.778] | 0.495 (1.22) | 0.521 | 0.591 [0.556, 0.765] | 0.615 [0.577, 0.817] | 0.467 |
| all | L4 | L4:egnn_s
… [14,620 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:56:43

```
{"command": "python3 -c \"\nimport json;d=json.load(open('results/final/final_claims.json'));print(json.dumps(d,indent=1)[:6000])\"; wc -l scripts/final_eval.py src/pocketcompare/evaluate.py", "description": "Show final claims json"}
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
  "ci_low": 0.011542478647091473,
  "ci_unit": "u",
  "comparison": "FINAL[raw] \u2212 B4 esm2 (z)[raw]",
  "delta": 0.129513
… [3,529 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:56:50

```
{"command": "sed -n 1,200p scripts/final_eval.py", "description": "Read final_eval.py head"}
```


**← tool result**

```
#!/usr/bin/env python
"""Final (confirmatory) evaluation — PREREG.md §2 claims and §3 reported items, with the §4 rules.

Real run (PI only):
    FINAL_EVAL=1 python scripts/final_eval.py                      # reads the committed FREEZE.json
Dry run on dev data (identical code path; sealed files are never touched):
    python scripts/final_eval.py --dryrun-dev [--B 2000] [--threads 16]
Write a FREEZE.json template for the current HEAD (PI reviews + commits it):
    python scripts/final_eval.py --write-freeze
Preflight of the real run (all FREEZE / worktree / hash checks, exits before any sealed file is opened):
    FINAL_EVAL=1 python scripts/final_eval.py --check-only

Guards of the real run
----------------------
* ``FINAL_EVAL=1`` is required; FREEZE.json must be committed and unmodified; the main tree must be clean (tracked
  files).  FREEZE.json = {commit, method_config, method_config_sha256, weights: {path: sha256}, evaluate_sha256,
  prereg_sha256, final_eval_sha256}.  Any mismatch -> refuse.
* The evaluation runs from a git worktree at FREEZE.commit (created next to the repo; git-ignored data
  directories are symlinked into it) and re-checks every hash there: evaluate.py must equal FREEZE and the PREREG §4
  constant f22d0296…; PREREG.md, configs/final_method.yaml, model weights and this script must equal FREEZE.
* Sealed files (data/sealed/, chmod 000) are opened one at a time: chmod 400 -> sha256 check against
  data/sealed_SHA256SUMS.txt -> read into memory -> ch
… [10,131 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:56:54

```
{"command": "sed -n 200,520p scripts/final_eval.py", "description": "Read final_eval.py continued"}
```


**← tool result**

```
        self.is_learned = cfg.get("kind") == "learned"
        self.csls = bool(getattr(m, "csls", cfg.get("variant") == "csls"))

    def weight_files(self):
        fs = [ROOT / f for f in self.cfg.get("files_sha256", {})] + [ROOT / f for f in self.cfg.get("model_files", [])]
        if self.cfg.get("input_stats"):
            fs.append(ROOT / self.cfg["input_stats"])
        return sorted(set(fs))

    def raw_parts(self, store, dataset, mode, pocket_ids):
        """N1/N2 part matrices via pocketcompare.a4b.raw_parts (incl. its SPH_FALLBACK); NaN rows if missing."""
        from pocketcompare import a4b as A4
        if not A4.a1r_dir(dataset).exists():
            raise FileNotFoundError(f"{A4.a1r_dir(dataset)} (compute_descriptors.py --arm a1r)")
        ids = set(A4.ids_table(dataset).pocket_id)
        pid = list(pocket_ids)
        have = np.array([p in ids for p in pid])
        out = [np.full((len(pid), 514 if src == "a1" else 113), np.nan) for src, _ in self.m.parts]
        if have.any():
            got = A4.raw_parts(dataset, mode, [p for p, h in zip(pid, have) if h], self.m.inp)
            for k in range(len(out)):
                out[k][have] = got[k]
        return out

    def embed(self, store, dataset, mode, pocket_ids):
        mats = self.raw_parts(store, dataset, mode, pocket_ids)
        E = np.asarray(self.m.embed(mats), np.float32)
        ok = np.ones(len(E), bool)
        for M in mats:
            ok &= np.isfinite(M).any(1)
        E[~ok] = np.
… [14,211 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:57:01

```
{"command": "cat configs/final_method.yaml; ls src/pocketcompare; wc -l src/pocketcompare/method.py src/pocketcompare/a4b.py; cat results/models/a4b/n1_linear/config.json | head -80", "description": "Inspect method config and model config"}
```


**← tool result**

```
# Final method (generated by scripts/write_final_method.py; do not edit by hand)
name: pocketcompare-final:A4b:n1_linear|raw
selected_by: results/dev/final_select_pi.json
selection_rule: PREREG §1 (one-SE rule on BLiPS-val D-mode cb-AUC + guards)
kind: learned
candidate: A4b:n1_linear
variant: raw
input: N1
dims: 384
csls_k: 10
csls_background: 'the searched database (evaluation: the evaluated split''s pocket
  pool)'
parts:
- src: a1
  shaper: sph8
- src: env
  shaper: sph8
site:
  L_cutoff_A: 4.0
  residue_cutoff_A: 4.0
  residue_bur_min: 0.5
  D_pockets: BURROW region-rule output (pk_in_region), each sub-pocket separately
  D_locator_with_site: best-covering region pocket (pockets.best_member, cover 1.5
    Å)
  shaper_sph8:
    radius_A: 8.0
    centroid: vol * bur16^4-weighted
    bur_feature: bur10
    bur_min: 0.5
    empty_fallback: located (base) set
a1:
  version: a1-v1
  overrides: {}
  config_hash: 8f4f566dbad665ba
env:
  version: a1r-v1
  dims: 113
scaling: per part z-score, BLiPS-train v2 sites (L + D rows), constant dims -> 0;
  A4b input clipped to +-5
input_stats: results/models/a4b/n1_linear/input_stats.json
model_files:
- results/models/a4b/n1_linear/seed0.npz
- results/models/a4b/n1_linear/seed1.npz
- results/models/a4b/n1_linear/seed2.npz
files_sha256:
  results/models/a4b/n1_linear/input_stats.json: 845d5671dc3ef8184330ebcd788c70b9a078280cf7ea57a623facbba8a86a95d
  results/models/a4b/n1_linear/seed0.npz: d455b1fca0f49bf39a57efc768cc12e70792ff5e9b2c6fb5f8
… [2,522 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:57:05

```
{"command": "cat src/pocketcompare/method.py; sed -n 1,211p src/pocketcompare/a4b.py", "description": "Read method.py and a4b.py"}
```


**← tool result**

```
"""The final pocket-similarity method (PREREG §1; selected in reports/a4b_selection.md) — public API.

    from pocketcompare import method
    V, info = method.describe("1abc.cif.gz", return_info=True)        # every BURROW region pocket (D mode): (n, d)
    v = method.describe("1abc.cif.gz", site="ligand.sdf")             # a ligand-defined site (L mode): (1, d)
    v = method.describe("1abc.cif.gz", site=["A:43", "A:45", "A:46"])  # a residue-defined site
    v = method.describe(path, site=xyz_array, af_mode=True)           # ligand heavy-atom coordinates; AF model
    S = method.similarity(v, V)                                       # (1, n) scores; higher = more similar

Pipeline (all parameters in configs/final_method.yaml, with sha256 of every data file it needs):
1. BURROW on the protein (``pocketcompare.pockets.featurize_structure``; ``af_mode`` = BURROW AF mode).
2. Site location: ``site=None`` -> each BURROW pocket of the region-rule output (``pockets="region"``; "v2" or
   "full" also accepted) is a site; a ligand (file, or (n, 3) heavy-atom coordinates) -> the 4 Å ligand shell;
   a residue list ("chain:num") -> the residue shell (4 Å, bur10 >= 0.5).  ``locate="burrow"`` replaces a given
   site by the single region-rule BURROW pocket that best covers it (the evaluation's D-mode locator).
3. Description: ``base`` = the located points, ``sph8`` = buried points (bur10 >= 0.5) within 8 Å of the
   bur16^4-weighted centroid of ``base`` (``base`` itself if that set is
… [18,595 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:57:12

```
{"command": "grep -n \"def \\|B1\\|B4\\|esm2\\|b1_default\\|matrix(\" scripts/final_eval.py | sed -n 1,200p | grep -v \"^.*#.*$\" | head -120", "description": "Find score computation in final_eval"}
```


**← tool result**

```
41:  C1a  TOUGH-M1-test L: ROC-AUC(final) − ROC-AUC(B1); units = components of (ligand cluster ∪ homology group).
42:  C1b  same vs B4 (ESM-2 lining-residue mean, z-scored cosine).  B1/B4 get the final method's CSLS treatment.
43:  C1-D TOUGH-M1-test D (both pockets matched: coverage ≥ 0.3 or precision ≥ 0.5; common set of final and B1).
44:  C2   ProSPECCTs P5.2 + P6.2 + P7, self-pairs removed, L: macro Δ(final − B1), independent bootstrap per subset
49:    B0' Foldseek global TM (data/processed/b0prime) and the TOUGH-M1 list TM / identity, B1, B4 (z, raw), B5 EPoCS,
52:    AUC (10 largest positive clusters) for final and B1; D-mode worst-case bound and miss rates.
60:    CI = wider of homology-group / ligand-cluster units.  C5: final (and B1, B4) on holo vs AF-model pockets, paired
73:over the real label-free pocket tables (numbers ≈ 0.5, flagged ``synthetic``).  The dev numbers of B1 / A1 in
122:def log(msg):
130:    def __init__(self, log_path: Path, enabled: bool):
142:    def read(self, name: str, purpose: str) -> pd.DataFrame:
178:    def weight_files(self):
181:    def embed(self, store, dataset, mode, pocket_ids):
182:        M = store.matrix(dataset, f"a1_pair_only_{mode}", pocket_ids)
197:    def __init__(self, m, cfg):
203:    def weight_files(self):
209:    def raw_parts(self, store, dataset, mode, pocket_ids):
224:    def embed(self, store, dataset, mode, pocket_ids):
234:def load_method(allow_standin: bool, force_standin: bool = False):
266:    def pair_units(s
… [5,095 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:57:16

```
{"command": "sed -n 556,700p scripts/final_eval.py; sed -n 760,870p scripts/final_eval.py; sed -n 1,80p src/pocketcompare/descstore.py", "description": "Read vectors, paired and descstore"}
```


**← tool result**

```
def _method_vectors(ps: PairSet, method, store, modes, dataset, arm, note):
    ds = dataset or ps.dataset
    P = ps.pockets
    out = []
    for mode in modes:
        pool = P.cache_ok.to_numpy() if mode == "L" else P.d_match.to_numpy(bool)
        if mode == "D" and ps.d_allowed is not None:
            pool = pool & ps.d_allowed
        idx = np.where(pool)[0]
        if len(idx) <= CSLS_K + 1:
            continue
        E = np.asarray(method.embed(store, ds, mode, P.pocket_id.to_numpy()[idx]), np.float32)
        okr = np.isfinite(E).all(1)
        rows = idx[okr]
        if len(rows) <= CSLS_K + 1:
            continue
        raw, cs = _embed_scores(E[okr], rows, len(P), ps.ia, ps.ib, True)
        out.append(Vec(arm, method.name, "raw", mode, raw, E.shape[1], note))
        out.append(Vec(arm, method.name, "csls", mode, cs, E.shape[1], note + " + CSLS (pool)"))
    return out


def final_vectors(ps: PairSet, method, store, modes=("L", "D"), dataset=None, extras=True, learned_ok=True):
    """FINAL (+ the Addendum-A2 descriptive arms N1 and L4, each skipped where its inputs do not exist)."""
    out = []
    if learned_ok or not method.is_learned:
        out += _method_vectors(ps, method, store, modes, dataset, "FINAL", "final method")
    if extras:
        for xa in EXTRA_ARMS:
            if xa.is_learned and not learned_ok:
                continue
            try:
                out += _method_vectors(ps, xa, store, modes, dataset, xa.arm,
                   
… [14,470 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:57:22

```
{"command": "grep -n \"def cosine_vectors\" -A30 scripts/eval_dev.py; grep -n \"np.save\\|to_parquet\\|embeddings\" scripts/final_eval.py | head; ls -la results/final/; ls data/processed/descriptors/tough_m1/ | head -50", "description": "Check cosine_vectors and stored outputs"}
```


**← tool result**

```
367:def cosine_vectors(M, avail, ia, ib, *, zscore=True, layout=None, block_weights=None, csls=True):
368-    """Raw cosine and CSLS scores over all pairs (NaN where a pocket is unavailable)."""
369-    rows = np.where(avail)[0]
370-    zs = ZScorer.fit(M[rows]) if zscore else None
371-    Er = embed(M[rows], zs, layout, block_weights)
372-    E = np.zeros((len(M), Er.shape[1]), np.float32)
373-    E[rows] = Er
374-    ok = avail[ia] & avail[ib]
375-    raw = np.full(len(ia), np.nan)
376-    raw[ok] = pair_scores(E, ia[ok], ib[ok])
377-    if not csls:
378-        return raw, None
379-    r = np.full(len(M), np.nan)
380-    r[rows] = csls_r(Er, Er, CSLS_K, query_ids=rows, bg_ids=rows)
381-    return raw, raw - 0.5 * (r[ia] + r[ib])
382-
383-
384-def neg_euclid_vectors(M, avail, ia, ib):
385-    rows = np.where(avail)[0]
386-    X = M[rows]
387-    sq = (X ** 2).sum(1)
388-    S = -np.sqrt(np.clip(sq[:, None] + sq[None, :] - 2 * X @ X.T, 0, None))
389-    np.fill_diagonal(S, -np.inf)
390-    r = np.full(len(M), np.nan)
391-    r[rows] = np.sort(S, axis=1)[:, -CSLS_K:].mean(1)
392-    ok = avail[ia] & avail[ib]
393-    raw = np.full(len(ia), np.nan)
394-    raw[ok] = -np.linalg.norm(M[ia[ok]] - M[ib[ok]], axis=1)
395-    return raw, raw - 0.5 * (r[ia] + r[ib])
396-
397-
503:    """Raw + CSLS pair scores from unit embeddings of the pool rows (exactly as eval_dev.cosine_vectors)."""
540:    """L4:egnn_small ensemble embeddings (scripts/l4_embed.py; rows = pocketcompare.a4b.ids_ta
… [2,531 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:57:28

```
{"command": "cat results/final/unseal_log.tsv | cut -f1,2,4,5,6,7,8; ls data/processed/descriptors/tough_m1/ | grep -v \"a1_\" ; ls data/processed/descriptors/tough_m1/defrob; ls data/processed/cache/points/tough_m1/ | head; python3 -c \"\nimport numpy as np; z=np.load('results/models/a4b/n1_linear/seed0.npz'); print({k:z[k].shape for k in z.files})\"", "description": "Unseal log and descriptor listing"}
```


**← tool result**

```
Exit code 1
time	file	sha256_ok	mode_before	mode_after	rows	purpose
2026-10-28T04:23:49+0100	data/sealed/tough_m1_test_pairs.parquet	True	0o0	0o0	24337	C1a/C1b/C1-D + TOUGH-M1-test reported items
2026-10-28T04:25:02+0100	data/sealed/prospeccts_pairs.parquet	True	0o0	0o0	450625	C2 + ProSPECCTs reported items
2026-10-28T04:41:16+0100	data/sealed/blips_test_pairs.parquet	True	0o0	0o0	41514	BLiPS-test reported items + C5
2026-10-28T04:41:16+0100	data/sealed/blips_test_sites.parquet	True	0o0	0o0	3606	BLiPS-test site groups / label clusters
2026-10-28T04:53:57+0100	data/sealed/vertex_pairs.parquet	True	0o0	0o0	1564604	Vertex reported items
2026-10-28T04:54:40+0100	data/sealed/tough_m1_pairs.parquet	True	0o0	0o0	1061926	TOUGH-M1 full-minus-dev (literature-comparable, D8)
2026-10-28T04:55:29+0100	data/sealed/ppips_test_queries.parquet	True	0o0	0o0	153	PPIPS-test P-ortho
2026-10-28T04:55:29+0100	data/sealed/ppips_sym_test_pairs.parquet	True	0o0	0o0	272	PPIPS-test P-sym
2026-10-28T04:55:33+0100	data/sealed/ppi_l_test_pairs.parquet	True	0o0	0o0	70313	PPI-L test (exploratory C3)
b0_default_D.ids.parquet
b0_default_D.ids.parquet.prov.json
b0_default_D.layout.json
b0_default_D.npy
b0_default_L.ids.parquet
b0_default_L.ids.parquet.prov.json
b0_default_L.layout.json
b0_default_L.npy
b1_default_D.ids.parquet
b1_default_D.ids.parquet.prov.json
b1_default_D.layout.json
b1_default_D.npy
b1_default_L.ids.parquet
b1_default_L.ids.parquet.prov.json
b1_default_L.layout.json
b1_default_L.npy
b1_learn
… [931 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:57:35

```
{"command": "source .venv/bin/activate && mkdir -p results/verify && python -c \"\nimport numpy as np, pandas as pd, json\nz=np.load('results/models/a4b/n1_linear/seed0.npz'); print({k:z[k].shape for k in z.files})\ns=json.load(open('results/models/a4b/n1_linear/input_stats.json')); print(s.keys(), [len(m) for m in s['mean']], s['parts'])\nsp=pd.read_parquet('data/splits/tough_m1_pockets_split.parquet'); print(sp.head()); print(sp.columns.tolist()); print(sp.partition.value_counts())\nix=pd.read_parquet('data/processed/cache/points/tough_m1/index.parquet'); print(ix.columns.tolist()); print(ix.head(3).T)\nids=pd.read_parquet('data/processed/descriptors/tough_m1/defrob/ids.parquet'); print(ids.head(), len(ids))\nd=np.load('data/processed/descriptors/tough_m1/defrob/L_sph8.npz'); print({k:d[k].shape for k in d.files})\n\"; ls -la data/sealed", "description": "Inspect data structures"}
```


**← tool result**

```
{'w2': (128, 627), 'b2': (128,)}
dict_keys(['inp', 'parts', 'mean', 'std', 'n_ref']) [514, 113] [{'src': 'a1', 'shaper': 'sph8'}, {'src': 'env', 'shaper': 'sph8'}]
        pocket_id         node_id  ... ligand_cluster  ligand_fp_ok
0  tough_m1:11asA  tough_m1:11asA  ...    tm1lig:0093          True
1  tough_m1:13pkD  tough_m1:13pkD  ...    tm1lig:0000          True
2  tough_m1:154lA  tough_m1:154lA  ...    tm1lig:0030          True
3  tough_m1:1a05B  tough_m1:1a05B  ...    tm1lig:0213          True
4  tough_m1:1a0iA  tough_m1:1a0iA  ...    tm1lig:0000          True

[5 rows x 14 columns]
['pocket_id', 'node_id', 'sid', 'group_id', 'partition', 'touch_burrow', 'touch_burrow_rep', 'touch_prospeccts', 'touch_vertex', 'touch_af_set', 'touch_ppi_l_test', 'touch_sealed', 'ligand_cluster', 'ligand_fp_ok']
partition
excluded    5714
test        1045
dev          765
Name: count, dtype: int64
['pocket_id', 'structure_key', 'cache_file', 'status', 'failure_reason', 'n_points_structure', 'n_full', 'n_region', 'n_merged_region', 'definition', 'lmode_idx', 'n_points', 'n_points_dense', 'volume_A3', 'n_lining_res', 'lining_residues', 'n_ligand_atoms', 'ligand_protein_min_dist', 'n_missing_residues', 'alt_definition', 'alt_idx', 'alt_n_points', 'alt_volume_A3', 'alt_jaccard', 'alt_n_missing_residues', 'alt_chain_remapped', 'd_coverage', 'd_missed', 'd_members', 'd_n_points', 'd_volume_A3', 'd_score', 'd_rank_in_merged', 'd_precision', 'dfull_coverage', 'dfull_missed']
                      
… [6,327 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:57:49

```
{"command": "sed -n 1,200p src/pocketcompare/similarity.py | grep -v \"^\\s*$\" | head -150", "description": "Read similarity.py"}
```


**← tool result**

```
"""Tier-1 scoring helpers: z-scoring on a reference set, (block-weighted) cosine, CSLS hub correction, batched
pair scoring (DESIGN §1, §3).
    zs = ZScorer.fit(D, ids, ref_ids)                  # statistics from the caller's train/dev pocket ids only
    E = embed(D, zs)                                   # unit rows: E[i] @ E[j] = cosine of z-scored vectors
    E = embed(D, zs, layout=lay, block_weights={...})  # unit rows: E[i] @ E[j] = sum_b w_b cos_b / sum_b w_b
    s = pair_scores(E, i, j)                           # millions of pairs, chunked, float32
    r = csls_r(E, E[bg], k=10, query_ids=ids, bg_ids=ids[bg])     # mean top-k background similarity
    s_c = csls_pair_scores(E, i, j, r)                 # s - (r_i + r_j) / 2   (DESIGN §1)
Every embedding is a plain unit vector, so all scores are inner products (FAISS IndexFlatIP-compatible).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
EPS_STD = 1e-8
@dataclass
class ZScorer:
    mean: np.ndarray
    std: np.ndarray            # 0 marks a constant dimension in the reference set (mapped to 0)
    n_ref: int
    clip: float | None = None
    @classmethod
    def fit(cls, D, ids=None, ref_ids=None, clip: float | None = None) -> "ZScorer":
        """Statistics over the rows of ``D`` whose id is in ``ref_ids`` (all rows if ``ref_ids`` is None).
        Non-finite values are ignored in the statistics."""
        D = np.asarray(D, np.float64)
        if ref_ids is not None:
   
… [4,694 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-28 03:58:09

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/vlib.py", "content": "\"\"\"Independent verifier helpers (do NOT import scripts/final_eval.py or pocketcompare.evaluate).\"\"\"\nimport getpass\nimport hashlib\nimport os\nimport socket\nimport time\nfrom pathlib import Path\n\nimport numpy as np\nimport pandas as pd\nfrom scipy.sparse import coo_matrix\nfrom scipy.sparse.csgraph import connected_components\nfrom sklearn.metrics import roc_auc_score\n\nROOT = Path(\"/cluster/project/beltrao/gmagnus/pocket_compare\")\nLOG = ROOT / \"results/verify/unseal_log.tsv\"\n\n\ndef read_sealed(name, purpose):\n    p = ROOT / \"data/sealed\" / name\n    before = oct(os.stat(p).st_mode & 0o777)\n    t = time.strftime(\"%Y-%m-%dT%H:%M:%S%z\")\n    os.chmod(p, 0o400)\n    try:\n        h = hashlib.sha256(p.read_bytes()).hexdigest()\n        df = pd.read_parquet(p)\n    finally:\n        os.chmod(p, 0)\n    after = oct(os.stat(p).st_mode & 0o777)\n    new = not LOG.exists()\n    with open(LOG, \"a\") as fh:\n        if new:\n            fh.write(\"time\\tfile\\tsha256\\tmode_before\\tmode_after\\trows\\tpurpose\\tuser\\thost\\tpid\\n\")\n        fh.write(f\"{t}\\tdata/sealed/{name}\\t{h}\\t{before}\\t{after}\\t{len(df)}\\t{purpose}\\t{getpass.getuser()}\\t\"\n                 f\"{socket.gethostname()}\\t{os.getpid()}\\n\")\n    return df, h\n\n\ndef components_from_labels(*label_arrays):\n    \"\"\"Connected components of pockets linked when they share any label (
… [2,820 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/results/verify/vlib.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 03:58:18

```
{"command": "ls data/raw/ | head; ls data/raw/* -d | head -30; find data/raw -maxdepth 3 -iname \"*tough*\" | head", "description": "Locate raw TOUGH-M1 data"}
```


**← tool result**

```
ippidb
klifs
panel_sources
ppi_pocketome
prospeccts
tough_c1
tough_m1
vertex
data/raw/ippidb
data/raw/klifs
data/raw/panel_sources
data/raw/ppi_pocketome
data/raw/prospeccts
data/raw/tough_c1
data/raw/tough_m1
data/raw/vertex
data/raw/tough_m1
data/raw/tough_c1
data/raw/tough_m1/downloads/APoc-TOUGH-M1_positive.score
data/raw/tough_m1/downloads/TOUGH-M1_positive.list
data/raw/tough_m1/downloads/TOUGH-M1_pocket.list
data/raw/tough_m1/downloads/TOUGH-M1_negative.list
data/raw/tough_m1/downloads/TOUGH-M1_dataset.tar.gz
data/raw/tough_m1/downloads/TOUGH-M1_target.list
data/raw/tough_m1/downloads/TOUGH-M1_dataset.info
data/raw/tough_m1/downloads/APoc-TOUGH-M1_negative.score
```


**→ tool call `Bash`** · 2026-10-28 03:58:23

```
{"command": "ls -la data/raw/tough_m1/ data/raw/tough_m1/*/ | head -30; head -3 data/raw/tough_m1/downloads/TOUGH-M1_pocket.list data/raw/tough_m1/downloads/TOUGH-M1_target.list; cat data/raw/tough_m1/downloads/TOUGH-M1_dataset.info | head -30", "description": "Inspect raw TOUGH-M1 files"}
```


**← tool result**

```
data/raw/tough_m1/:
total 24
drwxr-sr-x  4 gmagnusson nogroup 4096 Oct 27 18:36 .
drwxr-sr-x 10 gmagnusson nogroup 4096 Oct 27 19:34 ..
-rw-r--r--  1 gmagnusson nogroup 4250 Oct 27 18:41 MANIFEST.json
drwxr-sr-x  2 gmagnusson nogroup 4096 Oct 27 18:41 downloads
drwxr-sr-x  3 gmagnusson nogroup 4096 Oct 27 18:38 extracted

data/raw/tough_m1/downloads/:
total 921032
drwxr-sr-x 2 gmagnusson nogroup      4096 Oct 27 18:41 .
drwxr-sr-x 4 gmagnusson nogroup      4096 Oct 27 18:36 ..
---------- 1 gmagnusson nogroup  17819817 Oct 27 18:41 APoc-TOUGH-M1_negative.score
---------- 1 gmagnusson nogroup  16163785 Oct 27 18:41 APoc-TOUGH-M1_positive.score
---------- 1 gmagnusson nogroup  11693010 Oct 27 18:41 G-LoSA-TOUGH-M1_negative.score
---------- 1 gmagnusson nogroup  10607436 Oct 27 18:41 G-LoSA-TOUGH-M1_positive.score
---------- 1 gmagnusson nogroup  13920250 Oct 27 18:41 SiteEngine-TOUGH-M1_negative.score
---------- 1 gmagnusson nogroup  12627900 Oct 27 18:41 SiteEngine-TOUGH-M1_positive.score
-rw-r--r-- 1 gmagnusson nogroup      4035 Oct 27 18:41 TOUGH-M1_dataset.info
-rw-r--r-- 1 gmagnusson nogroup 819163520 Oct 27 18:36 TOUGH-M1_dataset.tar.gz
---------- 1 gmagnusson nogroup  19488350 Oct 27 18:35 TOUGH-M1_negative.list
-rw-r--r-- 1 gmagnusson nogroup    127908 Oct 27 18:35 TOUGH-M1_pocket.list
---------- 1 gmagnusson nogroup  17679060 Oct 27 18:35 TOUGH-M1_positive.list
-rw-r--r-- 1 gmagnusson nogroup     45144 Oct 27 18:41 TOUGH-M1_target.list

data/raw/tough_m1/extracted/:
tot
… [1,388 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:58:27

```
{"command": "ls data/raw/tough_m1/extracted/*/ | head; d=$(ls -d data/raw/tough_m1/extracted/*/); ls $d | head -3; ls $d/$(ls $d | head -1) ; sed -n 30,80p data/raw/tough_m1/downloads/TOUGH-M1_dataset.info", "description": "Inspect extracted TOUGH-M1 structure"}
```


**← tool result**

```
11asA
13pkD
154lA
1a05B
1a0iA
1a0jC
1a3gB
1a4eD
1a4iB
1a4mD
11asA
13pkD
154lA
11asA.fpocket
11asA.pdb
11asA.pdbqt
11asA00.lpc
11asA00.pdb
11asA00.pdbqt
11asA00.sdf

A list of 359410 negative pairs. These proteins have dissimilar global sequences and structures and bind chemically dissimilar ligands.

* The first two columns are the PDB-IDs of target proteins
* 3rd column is the sequence identity between the targets
* 4th column is the structure similarity ([TM-score][2] by [Fr-TM-align][3])
* 5th column is the chemical similarity of bound ligands (Tanimoto coefficient by [kcombu][4])

### Data

**`TOUGH-M2_dataset.tar.gz`**

A tarball containing the following files ([11asA][5] as an example):

* target structure in PDB format (`11asA.pdb`)
* target structure in PDBQT format (`11asA.pdbqt`)
* bound ligand in PDB format (`11asA00.pdb`)
* bound ligand in PDBQT format (`11asA00.pdbqt`)
* bound ligand in SDF format (`11asA00.sdf`)
* protein-ligand contacts by [LPC][6] (`11asA.lpc`)
* sequence profile by [PROFILpro 1.1][7] (`11asA.profile`)
* secondary structure by [PSIPRED 4.0][8] (`11asA.ss2`)
* pockets by [*e*FindSite][1] (`11asA-efindsite.pockets.dat`)
* template-target structure alignments by [*e*FindSite][1] (`11asA-efindsite.alignments.dat`)
* ligands bound to templates extracted by [*e*FindSite][1] (`11asA-efindsite.ligands.sdf`)

Results
-------

Output files generated for the TOUGH-M2 dataset by several binding site alignment algorithms are available to facilitate compara
… [610 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:58:33

```
{"command": "d=data/raw/tough_m1/extracted/$(ls data/raw/tough_m1/extracted/)/11asA; ls -la $d; ls $d/11asA.fpocket 2>/dev/null | head; file $d/*; head -5 $d/11asA00.lpc; grep -rn \"residue_list\\|alt_definition\" scripts/*.py scripts/*/*.py src -l | head", "description": "Inspect pocket definition files"}
```


**← tool result**

```
total 1068
drwxr-sr-x    2 gmagnusson nogroup   4096 May 29  2017 .
drwxr-sr-x 7526 gmagnusson nogroup 581632 May 29  2017 ..
-rw-r--r--    1 gmagnusson nogroup  35818 Oct  3  2016 11asA.fpocket
-rw-r--r--    1 gmagnusson nogroup 171394 Aug 24  2016 11asA.pdb
-rw-r--r--    1 gmagnusson nogroup 250268 Oct  3  2016 11asA.pdbqt
-rw-r--r--    1 gmagnusson nogroup  13978 Oct  3  2016 11asA00.lpc
-rw-r--r--    1 gmagnusson nogroup    495 Aug 24  2016 11asA00.pdb
-rw-r--r--    1 gmagnusson nogroup   1488 Oct  3  2016 11asA00.pdbqt
-rw-r--r--    1 gmagnusson nogroup   2391 Aug 24  2016 11asA00.sdf
data/raw/tough_m1/extracted/TOUGH-M1_dataset/11asA/11asA.fpocket
/bin/bash: line 1: file: command not found
Contacts of ligand LIG   1A in  PDB entry 0.00

Ligand-Protein Contacts (LPC) are derived
with the LPC software (Sobolev V., Sorokine A.,
Prilusky J., Abola E.E., Edelman M., (1999)
scripts/build_point_cache.py
scripts/ppi/14_ppil_index.py
src/pocketcompare/pockets.py
src/pocketcompare/datasets/tough_m1.py
src/pocketcompare/datasets/tough_c1.py
```


**→ tool call `Bash`** · 2026-10-28 03:58:38

```
{"command": "head -30 data/raw/tough_m1/extracted/TOUGH-M1_dataset/11asA/11asA.fpocket; grep -n \"residue_list\\|fpocket\\|pocket.list\" src/pocketcompare/datasets/tough_m1.py | head -20", "description": "Look at fpocket file and loader"}
```


**← tool result**

```
Pocket 1 :
	Score : 			48.846
	Druggability Score : 		0.129
	Number of Alpha Spheres : 	282
	Total SASA : 			1008.520
	Polar SASA : 			623.287
	Apolar SASA : 			385.233
	Volume : 			2073.218
	Mean local hydrophobic density : 18.203
	Mean alpha sphere radius :	3.888
	Mean alp. sph. solvent access :  0.505
	Apolar alpha sphere proportion : 0.209
	Hydrophobicity score:		7.067
	Volume score: 			 3.489
	Polarity score:			 28
	Charge score :			 -2
	Proportion of polar atoms: 	52.206
	Alpha sphere density : 		9.598
	Cent. of mass - Alpha Sphere max dist: 23.097
	Flexibility : 			 0.000

Pocket 2 :
	Score : 			20.735
	Druggability Score : 		0.045
	Number of Alpha Spheres : 	71
	Total SASA : 			322.774
	Polar SASA : 			164.575
	Apolar SASA : 			158.199
	Volume : 			752.563
	Mean local hydrophobic density : 19.429
5:  downloads/TOUGH-M1_pocket.list               "id best_pocket_index MCC"
8:  extracted/TOUGH-M1_dataset/<id>/<id>.fpocket fpocket 2.0 output; 'POCKET n r1 r2 ...'
11:Pocket definition used by the benchmark: the fpocket 2.0 pocket with index
51:def _fpocket_residues(path: Path) -> dict[int, list[str]]:
72:    pl = pd.read_csv(DL / "TOUGH-M1_pocket.list", sep=r"\s+", header=None,
77:        prot, lig, fp = d / f"{r.name}.pdb", d / f"{r.name}00.pdb", d / f"{r.name}.fpocket"
78:        res = _fpocket_residues(fp) if fp.exists() else {}
86:            "pocket_def_type": "residue_list",
92:            "fpocket_index": int(r.pocket_index), "pocket_mcc": float(r.pocket_mcc),
94:  
… [40 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:58:44

```
{"command": "sed -n 1,110p src/pocketcompare/datasets/tough_m1.py; grep -n \"POCKET\" data/raw/tough_m1/extracted/TOUGH-M1_dataset/11asA/11asA.fpocket | head -3", "description": "Read TOUGH-M1 loader"}
```


**← tool result**

```
"""TOUGH-M1 loader (Govindaraj & Brylinski 2018, BMC Bioinformatics 19:91).

Raw layout (scripts/data/fetch_tough_m1.py):
  downloads/TOUGH-M1_{positive,negative}.list  "idA idB seqid TMscore ligandTc"
  downloads/TOUGH-M1_pocket.list               "id best_pocket_index MCC"
  extracted/TOUGH-M1_dataset/<id>/<id>.pdb     single chain, renumbered from 1, chain 'A'
  extracted/TOUGH-M1_dataset/<id>/<id>00.pdb   bound ligand (resname LIG)
  extracted/TOUGH-M1_dataset/<id>/<id>.fpocket fpocket 2.0 output; 'POCKET n r1 r2 ...'
                                               lines list residue numbers of pocket n

Pocket definition used by the benchmark: the fpocket 2.0 pocket with index
`best_pocket_index` (the one best overlapping the ligand-binding residues;
MCC given). We record its residue list (numbering of the TOUGH-M1 .pdb file,
NOT of the original PDB entry) and the ligand file.
Labels: positive.list -> 1, negative.list -> 0 (as distributed).

Chain letters: the structure files are renumbered from 1 but keep the ORIGINAL chain letter (3,191 of
7,524 are not 'A'); `pocket_def` therefore uses the chain read from the structure file (it hard-coded
'A:' before 2026-10-27).

Sealing: the pair lists and the shipped baseline score files are sealed (chmod 000; TOUGH-M1 pair labels
live in data/sealed/). `build()` writes the POCKET table only and never reads the pair lists; the pair
table is built once by `build_pairs()` (only the PI / sealed workflow may call it) and the dev/test pa
… [3,806 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 03:58:53

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd; s=pd.read_parquet('results/final/final_summary.parquet'); print(s.columns.tolist()); print(s.set.unique() if 'set' in s else s.iloc[:,0].unique()); print(s.head(3).T)\ni=pd.read_parquet('data/processed/descriptors/tough_m1/b4_esm2_ids.parquet'); print(i.head(), len(i))\n\"", "description": "Inspect summary parquet"}
```


**← tool result**

```
['set', 'key', 'subset', 'arm', 'config', 'variant', 'mode', 'dims', 'note', 'synthetic', 'n_pairs', 'n_pos', 'n_neg', 'auc', 'ap', 'prevalence', 'ap_lift', 'pauc_mcclish', 'pauc_raw', 'B', 'seed', 'auc_cb', 'auc_strat', 'strat_n_bins', 'strat_n_strata_dropped', 'strat_frac_pos_dropped', 'n_units_u', 'auc_lo', 'auc_hi', 'auc_se', 'auc_ci_unit', 'auc_lo_u', 'auc_hi_u', 'ap_lo', 'ap_hi', 'ap_se', 'ap_ci_unit', 'ap_lo_u', 'ap_hi_u', 'auc_cb_lo', 'auc_cb_hi', 'auc_cb_se', 'auc_cb_ci_unit', 'auc_cb_lo_u', 'auc_cb_hi_u', 'auc_strat_lo', 'auc_strat_hi', 'auc_strat_se', 'auc_strat_ci_unit', 'auc_strat_lo_u', 'auc_strat_hi_u', 'n_missing_in_ref_pos', 'n_missing_in_ref_neg', 'auc_worst_all', 'ap_worst_all', 'miss_rate_pos_all', 'miss_rate_neg_all', 'n_units_hom', 'auc_lo_hom', 'auc_hi_hom', 'ap_lo_hom', 'ap_hi_hom', 'auc_strat_lo_hom', 'auc_strat_hi_hom', 'n_units_lig', 'auc_lo_lig', 'auc_hi_lig', 'ap_lo_lig', 'ap_hi_lig', 'auc_cb_lo_hom', 'auc_cb_hi_hom', 'auc_cb_lo_lig', 'auc_cb_hi_lig', 'auc_strat_lo_lig', 'auc_strat_hi_lig', 'ap_neg_target']
<ArrowStringArray>
[          'tough_m1_test',           'prospeccts_P1',
         'prospeccts_P1.2',           'prospeccts_P2',
           'prospeccts_P3',           'prospeccts_P4',
           'prospeccts_P5',         'prospeccts_P5.2',
           'prospeccts_P6',         'prospeccts_P6.2',
           'prospeccts_P7',              'blips_test',
           'blips_test_af',                  'vertex',
 'tough_m1_full_minus_dev']
Length: 15, dtyp
… [1,989 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-28 03:58:56

Now the TOUGH-M1 verification script.


**→ tool call `Write`** · 2026-10-28 03:59:35

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_tough.py", "content": "\"\"\"Independent re-derivation of C1a / C1b / C1-D, B0 (+ shipped-pocket size variants), shuffled control.\"\"\"\nimport json\nimport os\nimport re\nimport sys\n\nos.environ.setdefault(\"OMP_NUM_THREADS\", \"16\")\nimport numpy as np\nimport pandas as pd\nfrom sklearn.metrics import roc_auc_score\n\nsys.path.insert(0, \"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify\")\nfrom vlib import ROOT, boot_paired, components_from_labels, l2n, pair_cos, read_sealed, zcos_embed  # noqa\n\nOUT = ROOT / \"results/verify\"\nres = {}\n\npairs, h = read_sealed(\"tough_m1_test_pairs.parquet\", \"verify C1a/C1b/C1-D/B0 (independent verifier)\")\nres[\"pairs_sha256\"] = h\nres[\"pair_columns\"] = list(pairs.columns)\nsplit = pd.read_parquet(ROOT / \"data/splits/tough_m1_pockets_split.parquet\")\nP = split[split.partition == \"test\"].sort_values(\"pocket_id\").reset_index(drop=True)\npos = {p: i for i, p in enumerate(P.pocket_id)}\nassert pairs.pocket_a.isin(pos).all() and pairs.pocket_b.isin(pos).all()\nia, ib = pairs.pocket_a.map(pos).to_numpy(), pairs.pocket_b.map(pos).to_numpy()\ny = pairs.label.to_numpy().astype(int)\nres[\"n_pool_pockets\"] = len(P)\nres[\"n_pockets_in_pairs\"] = int(len(set(ia) | set(ib)))\nres[\"n_pairs\"], res[\"n_pos\"], res[\"n_neg\"] = len(y), int(y.sum()), int((1 - y).sum())\nres[\"n_self_pairs\"] = int((ia == ib).sum())\nres[\"n_dup_pairs\"] = in
… [9,455 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_tough.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 03:59:39

```
{"command": "source .venv/bin/activate && time python results/verify/v_tough.py > results/verify/v_tough.log 2>&1; tail -5 results/verify/v_tough.log; ls -la data/sealed/tough_m1_test_pairs.parquet", "description": "Run TOUGH-M1 verification", "timeout": 1200000}
```


**← tool result**

```
real	1m28.515s
user	0m51.948s
sys	0m1.001s
   "n_degenerate": 0,
   "n_pairs": 21410
  }
 }
}
---------- 1 gmagnusson nogroup 997652 Oct 28 01:27 data/sealed/tough_m1_test_pairs.parquet
```


**→ tool call `Bash`** · 2026-10-28 04:01:11

```
{"command": "cat results/verify/v_tough.log | head -230", "description": "Show TOUGH results"}
```


**← tool result**

```
{
 "pairs_sha256": "17973ec019b5e7a511d47e4c0327c777768d102d39753773c6d1f9ebe7a0cda2",
 "pair_columns": [
  "pair_id",
  "pocket_a",
  "pocket_b",
  "label",
  "subset",
  "source_label",
  "is_self",
  "seq_identity",
  "tm_score",
  "ligand_tc",
  "apoc_c1",
  "apoc_c2",
  "glosa_c1",
  "siteengine_c1",
  "siteengine_c2",
  "siteengine_c3",
  "ligand_cluster_a",
  "ligand_cluster_b",
  "group_a",
  "group_b"
 ],
 "n_pool_pockets": 1045,
 "n_pockets_in_pairs": 922,
 "n_pairs": 24337,
 "n_pos": 10160,
 "n_neg": 14177,
 "n_self_pairs": 0,
 "n_dup_pairs": 0,
 "n_units_pool": 133,
 "n_units_in_pairs": 112,
 "cache_ok_all": true,
 "n_dmatch_pockets": 940,
 "n_D_common_pairs": 21410,
 "n_D_common_pos": 8702,
 "final_L_max_abs_diff_own_vs_api": 1.7937610163887285e-07,
 "final_L_api_dims": 384,
 "final_D_max_abs_diff_own_vs_api": 1.973519901943277e-07,
 "final_D_api_dims": 384,
 "b0": {
  "B0_L_volume(4A ligand shell)": {
   "n": 24337,
   "auc": 0.7964581786291315
  },
  "B0_L_volume_reported": 0.7964581786291315,
  "B0_D_volume(common D set)": {
   "n": 21410,
   "auc": 0.5554574590828834
  },
  "B0_D_reported": 0.5554574590828834,
  "B0_D_volume(all pairs, D-volume even if unmatched)": {
   "n": 24337,
   "auc": 0.5330067026607919
  },
  "B0_L_volume_on_D_common_set": {
   "n": 21410,
   "auc": 0.8042545791194713
  },
  "B0_alt_residue_list_points_volume": {
   "n": 24337,
   "auc": 0.5314904464311997
  },
  "B0_L_n_lining_residues": {
   "n": 24337,
   "auc": 0.6152510248661607

… [3,501 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:01:29

```
{"command": "cat >> results/verify/v_tough.py <<'EOF'\n\n# save pair-level arrays (scratchpad only) for the Monte-Carlo-error study\nSCR = os.environ.get(\"VERIFY_SCRATCH\")\nif SCR:\n    np.savez(os.path.join(SCR, \"tough_scores.npz\"), y=y, ua=ua, ub=ub, dset=dset,\n             **{k: v for k, v in scores.items()})\nEOF\nsource .venv/bin/activate && VERIFY_SCRATCH=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad python results/verify/v_tough.py > results/verify/v_tough.log 2>&1; tail -3 results/verify/v_tough.log; cat results/verify/unseal_log.tsv", "description": "Re-run TOUGH script saving scores to scratchpad", "timeout": 1200000}
```


**← tool result**

```
  }
 }
}
time	file	sha256	mode_before	mode_after	rows	purpose	user	host	pid
2026-10-28T04:59:42+0100	data/sealed/tough_m1_test_pairs.parquet	17973ec019b5e7a511d47e4c0327c777768d102d39753773c6d1f9ebe7a0cda2	0o0	0o0	24337	verify C1a/C1b/C1-D/B0 (independent verifier)	gmagnusson	eu-g6-048	1632392
2026-10-28T05:01:32+0100	data/sealed/tough_m1_test_pairs.parquet	17973ec019b5e7a511d47e4c0327c777768d102d39753773c6d1f9ebe7a0cda2	0o0	0o0	24337	verify C1a/C1b/C1-D/B0 (independent verifier)	gmagnusson	eu-g6-048	1632661
```


**→ tool call `Bash`** · 2026-10-28 04:02:27

```
{"command": "cat > results/verify/v_tough_mc.py <<'EOF'\n\"\"\"Monte-Carlo error of the C1 bootstrap p-values: B = 20,000 with an independent seed (verifier code).\"\"\"\nimport json, sys\nimport numpy as np\nsys.path.insert(0, \"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify\")\nfrom vlib import boot_paired\ncid = sys.argv[1]; scr = sys.argv[2]\nz = np.load(f\"{scr}/tough_scores.npz\")\na, b, D = {\"C1a\": (\"FINAL_L\", \"B1_L\", False), \"C1b\": (\"FINAL_L\", \"B4_L\", False), \"C1-D\": (\"FINAL_D\", \"B1_D\", True)}[cid]\nsa, sb, y = z[a], z[b], z[\"y\"]\nm = np.isfinite(sa) & np.isfinite(sb) & (z[\"dset\"] if D else True)\nr = boot_paired(y[m], sa[m], sb[m], z[\"ua\"][m], z[\"ub\"][m], B=20000, seed=777)\nbt = r.pop(\"boot\")\nr[\"p_by_2000_block\"] = [float((1 + (bt[i:i+2000] <= 0).sum()) / 2001) for i in range(0, 20000, 2000)]\njson.dump(r, open(f\"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_tough_mc_{cid}.json\", \"w\"), indent=1)\nprint(cid, r)\nEOF\nsource .venv/bin/activate; S=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; for c in C1a C1b C1-D; do OMP_NUM_THREADS=2 nohup python results/verify/v_tough_mc.py $c $S > results/verify/v_tough_mc_$c.log 2>&1 & done; echo started", "description": "Launch B=20000 bootstrap MC study"}
```


**← tool result**

```
started
```


**→ tool call `Bash`** · 2026-10-28 04:02:32

```
{"command": "grep -n \"2.1\" LITERATURE.md | head; awk '/^#+ *2\\.1/{f=1} /^#+ *2\\.2/{f=0} f' LITERATURE.md | head -60; ls data/raw/prospeccts; ls data/raw/prospeccts/* | head -40", "description": "Read ProSPECCTs literature and raw layout"}
```


**← tool result**

```
40:| SMAP | Cα geometric potential | order-independent profile–profile alignment | 10.1073/pnas.0704422105 |
50:**Runtime, from ProSPECCTs Table 6** [P] (Ehrt et al. 2018, read verbatim from the PMC BioC text). One core,
59:| RAPMAD | histogram | 71.42 | 2.36 (8,281) | **0.000285** |
68:| TIFP | fingerprint | 228.30 (77) | 550.88 (5,929) | 0.092913 |
69:| Grim | graph | 220.17 (95) | 2,104.99 (9,025) | 0.233240 |
72:| Cavbase | graph | 67.89 (100) | 21,823.71 (8,281) | **2.635396** |
105:- **3D Zernike** (Kihara lab): Pocket-Surfer 10.1002/prot.22715, Patch-Surfer 10.1186/1471-2105-13-S2-S7;
107:  (10.1038/s42003-022-03261-8) applies Zernike at AlphaFold scale but on **whole structures**, not pockets.
121:- **ProFSA** (ICLR 2024, arXiv:2310.07229): cuts >5 M pseudo pocket–fragment complexes out of PDB proteins and
139:  (10.1016/j.patter.2025.101371), **BindCLIP** (arXiv:2602.15236), **Simpatico**
### 2.1 ProSPECCTs — the field standard (Ehrt, Brinkjost & Koch 2018, 10.1371/journal.pcbi.1006483)

**Correction to the brief: there is no D8/D9/D10.** The "ten" sets are D1, D1.2, D2, D3, D4, D5, D5.2, D6,
D6.2, D7. DeeplyTough and most later papers label them P1…P7. Also, **D3 is the physicochemical decoy set and
D4 the shape+physicochemical decoy set** (the brief had these reversed). Table below is **verbatim from
ProSPECCTs Table 2** [P]; "active/inactive" = similar/dissimilar pairs in the authors' wording.

| Set | Goal | active / inactive pairs |
|---|---|---|
| **D1** struct
… [2,737 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:02:37

```
{"command": "cat data/raw/prospeccts/downloads/README.txt | head -80; ls data/raw/prospeccts/extracted/barelier_structures; ls data/raw/prospeccts/extracted/barelier_structures/* | head -30", "description": "Inspect barelier raw folder"}
```


**← tool result**

```
PROSPECCT 

(Protein Site Pairs for the Evaluation of Cavity Comparison ToolS)


The pdb-files of the protein-ligand complexes for the individual datasets are included in the compressed folders. All pairwise comparisons and their class (active, i.e. similar, and inactive, i.e. dissimilar) are given in the accompanying csv-files.
- data set 1: identical_structures.tar.gz
- data set 1.2: identical_structures_similar_ligands.tar.gz
- data set 2: NMR_structures.tar.gz
- data set 3: decoy_rational_structures.tar.gz
- data set 4: decoy_shape_structures.tar.gz
- data set 5: kahraman_structures.tar.gz -> data set of Kahraman and co-workers
- data set 6: barelier_structures.tar.gz -> data set of Barelier and co-workers (cofactors are omitted in those structures)
- data set 6.2: barelier_structures_cofactors.tar.gz -> data set of Barelier and co-workers (cofactors included)
- data set 7: review_structures.tar.gz
<html lang=de>
<head>
<title>ProSPECCTs</title>
<meta name="robots" content="index, nofollow">
<meta name="description" content="Download ProSPECCTs - Benchmark sets for the optimization and evaluation of binding site comparison methodologies">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="HandheldFriendly" content="True">
<meta http-equiv="cleartype" content="on">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

<style>
html,body,div,span,object,iframe,h1,h2,h3,h4,h5,h6,p,blockquote,pre,abbr,address,cite,code,del,dfn,em,im
… [3,910 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:02:45

```
{"command": "source .venv/bin/activate && ls data/raw/prospeccts/extracted/barelier_structures/barelier_structures_cofactors | head -5; ls data/raw/prospeccts/extracted/barelier_structures/barelier_structures | wc -l; ls data/raw/prospeccts/extracted/barelier_structures/barelier_structures_cofactors | wc -l; head -5 data/raw/prospeccts/extracted/barelier_structures/barelier_structures.csv; wc -l data/raw/prospeccts/extracted/barelier_structures/barelier_structures.csv; python -c \"\nimport pandas as pd; t=pd.read_parquet('data/processed/benchmarks/prospeccts_pockets.parquet'); print(t.columns.tolist())\nb=t[t.subset.fillna('').str.contains('P6')]; print(len(b)); print(b.subset.value_counts()); print(b.head(3).T)\n\"", "description": "Compare barelier structure folders and pocket table"}
```


**← tool result**

```
1b66.pdb
1br6.pdb
1diy.pdb
1dx6.pdb
1e2s.pdb
115
115
head: cannot open 'data/raw/prospeccts/extracted/barelier_structures/barelier_structures.csv' for reading: Permission denied
wc: data/raw/prospeccts/extracted/barelier_structures/barelier_structures.csv: Permission denied
['pocket_id', 'dataset', 'source_dir', 'name', 'pdb_id', 'chain', 'structure_path', 'pocket_def_type', 'pocket_def', 'pocket_file', 'ligand_file', 'ligand_resname', 'n_lig_residues', 'n_lig_atoms', 'is_phosphate_site', 'is_decoy', 'decoy_nsub', 'n_models', 'protein_chains', 'in_pdb_mirror', 'file_missing', 'subset']
230
subset
P6      115
P6.2    115
Name: count, dtype: int64
                                                                4712  ...                                               4714
pocket_id                        prospeccts:barelier_structures/1b66  ...                prospeccts:barelier_structures/1diy
dataset                                                   prospeccts  ...                                         prospeccts
source_dir                   barelier_structures/barelier_structures  ...            barelier_structures/barelier_structures
name                                                            1b66  ...                                               1diy
pdb_id                                                          1b66  ...                                               1diy
chain                                                              A  ...                       
… [2,051 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:02:56

```
{"command": "B=data/raw/prospeccts/extracted/barelier_structures; nd=0; for f in $(ls $B/barelier_structures); do cmp -s $B/barelier_structures/$f $B/barelier_structures_cofactors/$f || nd=$((nd+1)); done; echo \"differing files: $nd / 115\"; f=1b66.pdb; grep HETATM $B/barelier_structures/$f | awk '{print $4}' | sort | uniq -c; echo ---; grep HETATM $B/barelier_structures_cofactors/$f | awk '{print $4}' | sort | uniq -c; for f in $(ls $B/barelier_structures | head -115); do a=$(grep -c HETATM $B/barelier_structures/$f); b=$(grep -c HETATM $B/barelier_structures_cofactors/$f); [ \"$a\" != \"$b\" ] && echo \"$f $a $b\"; done | head -40", "description": "Diff barelier structures with/without cofactors"}
```


**← tool result**

```
differing files: 74 / 115
      1 HETATM
     17 LIG
      2 OCCUPANCY
      2 RES
---
     17 LIG
1b66.pdb 22 17
1diy.pdb 24 22
1dx6.pdb 21 34
1e2s.pdb 17 15
1e6q.pdb 15 14
1he5.pdb 20 66
1lcb.pdb 37 57
1m9n.pdb 25 22
1mxh.pdb 30 77
1nok.pdb 15 14
1oq5.pdb 28 26
1ow4.pdb 23 21
1oxr.pdb 14 13
1pa9.pdb 16 15
1pb9.pdb 8 7
1qhy.pdb 22 20
1rf7.pdb 31 29
1s2c.pdb 20 68
1s4m.pdb 19 18
1sep.pdb 17 65
1tx0.pdb 23 33
1w7h.pdb 16 15
1xql.pdb 32 7
1z9y.pdb 25 21
2b50.pdb 23 20
2fbz.pdb 19 60
2fu7.pdb 20 14
2fxl.pdb 20 11
2gqs.pdb 28 25
2hkk.pdb 16 13
2nuv.pdb 22 19
2o63.pdb 23 28
2ph9.pdb 22 21
2q6h.pdb 25 22
2qre.pdb 23 22
2rh1.pdb 24 22
2uxu.pdb 21 20
2uy4.pdb 14 13
2vyv.pdb 73 54
2wd9.pdb 18 15
```


**→ tool call `Bash`** · 2026-10-28 04:03:07

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd, numpy as np\nt=pd.read_parquet('data/processed/benchmarks/prospeccts_pockets.parquet')\na=t[t.subset=='P6'].set_index('name'); b=t[t.subset=='P6.2'].set_index('name')\nprint(b.source_dir.unique(), a.source_dir.unique())\nprint((a.structure_path==b.structure_path.reindex(a.index)).sum(), 'same structure path')\nprint(b.structure_path.iloc[0], a.structure_path.iloc[0])\nix=pd.read_parquet('data/processed/cache/points/prospeccts/index.parquet').set_index('pocket_id')\nia=ix.reindex(a.pocket_id); ib=ix.reindex(b.loc[a.index].pocket_id)\nfor c in ['status','n_points_structure','n_points','volume_A3','d_coverage','d_precision','d_volume_A3']:\n    x,y=ia[c].to_numpy(),ib[c].to_numpy(); print(c, (pd.Series(x).astype(str).values==pd.Series(y).astype(str).values).mean())\nprint(ia.status.value_counts())\nd='data/processed/descriptors/prospeccts/'\nimport os; print([f for f in os.listdir(d) if 'b1_default_L' in f or 'a1r' in f])\nids=pd.read_parquet(d+'b1_default_L.ids.parquet').pocket_id; M=np.load(d+'b1_default_L.npy'); r=pd.Series(range(len(ids)),index=ids)\nx=M[r.reindex(a.pocket_id).dropna().astype(int)]; y=M[r.reindex(b.loc[a.index].pocket_id).dropna().astype(int)]; print('b1 L identical rows', np.isclose(x,y,equal_nan=True).all(1).mean(), x.shape)\n\"\n", "description": "Compare P6 vs P6.2 pockets in cache"}
```


**← tool result**

```
<ArrowStringArray>
['barelier_structures/barelier_structures_cofactors']
Length: 1, dtype: str <ArrowStringArray>
['barelier_structures/barelier_structures']
Length: 1, dtype: str
0 same structure path
data/raw/prospeccts/extracted/barelier_structures/barelier_structures_cofactors/1b66.pdb data/raw/prospeccts/extracted/barelier_structures/barelier_structures/1b66.pdb
status 1.0
n_points_structure 1.0
n_points 1.0
volume_A3 1.0
d_coverage 1.0
d_precision 1.0
d_volume_A3 1.0
status
ok    115
Name: count, dtype: int64
['b1_default_L.layout.json', 'b1_default_L.npy', 'b1_default_L.ids.parquet', 'b1_default_L.ids.parquet.prov.json', 'a1r']
b1 L identical rows 1.0 (115, 45)
```


**→ tool call `Bash`** · 2026-10-28 04:03:13

```
{"command": "grep -n -i \"hetatm\\|het\\b\\|hetero\\|cofactor\\|is_protein\\|polymer\" src/pocketcompare/pockets.py scripts/build_point_cache.py | head -30", "description": "Check HETATM handling in featurisation"}
```


**← tool result**

```
scripts/build_point_cache.py:20:    (pocket id, structure path, ligand residue / HET site; written by the label-free pocket builders) and the
src/pocketcompare/pockets.py:40:WATER = 2                          # pocketdetect.structure kind codes: 0 protein, 1 ligand, 2 water, 3 other polymer
src/pocketcompare/pockets.py:252:    # stripped non-protein heavy atoms (ligands, ions, cofactors); kept only to resolve ligand-defined pockets
src/pocketcompare/pockets.py:256:    het = dict(het_xyz=het_xyz, het_element=_STR(np.char.upper(s.element[nonprot].astype(str)), 3),
src/pocketcompare/pockets.py:306:        res_ids=_STR(P.residue_ids, 16), res_names=_res_names(P), **het,
src/pocketcompare/pockets.py:474:    .pdb: ATOM/HETATM records, element from columns 77-78 or the atom name)."""
src/pocketcompare/pockets.py:488:            if line.startswith(("ATOM  ", "HETATM")):
src/pocketcompare/pockets.py:559:        # Vertex: "HET:<code>;site_index:<k>"; instance k (1-based) of the residues named <code> in
src/pocketcompare/pockets.py:561:        het = str(row["pocket_def"]).split(";")[0].split(":")[1]
src/pocketcompare/pockets.py:566:            # enumeration; fallback first HET copy) -- see ``site_rule``
src/pocketcompare/pockets.py:574:                raise ValueError(f"site_index {k} not among {len(inst)} {het} instances")
src/pocketcompare/pockets.py:577:        m = (fs.het_resname == het) & (fs.het_res == f"{ch}:{seqid.strip()}")
src/pocketcompare/pockets.py:579:            raise Val
… [66 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:03:39

```
{"command": "cat >> results/verify/vlib.py <<'EOF'\n\n\n# ------------------------------------------------------------------ final method, own numpy re-implementation\nimport json as _json\n\n\ndef _desc_dir(ds):\n    d = ROOT / \"data/processed/descriptors\"\n    return d / \"tough_m1/defrob\" if ds == \"tough_m1\" else d / ds / \"a1r\"\n\n\ndef final_seed_embeddings(ds, loc, pocket_ids):\n    \"\"\"Per-seed 128-d unit embeddings (list of 3 arrays) + availability, from stored part descriptors.\"\"\"\n    stats = _json.load(open(ROOT / \"results/models/a4b/n1_linear/input_stats.json\"))\n    heads = [dict(np.load(ROOT / f\"results/models/a4b/n1_linear/seed{s}.npz\")) for s in (0, 1, 2)]\n    ids = pd.read_parquet(_desc_dir(ds) / \"ids.parquet\")\n    r = pd.Series(np.arange(len(ids)), index=ids.pocket_id).reindex(list(pocket_ids)).to_numpy()\n    have = ~pd.isna(r)\n    ri = np.where(have, r, 0).astype(int)\n    sph = np.load(_desc_dir(ds) / f\"{loc}_sph8.npz\")\n    base = np.load(_desc_dir(ds) / f\"{loc}_base.npz\")\n    mats = []\n    for src in (\"a1\", \"env\"):\n        M = sph[src][ri].astype(np.float64)\n        Bm = base[src][ri].astype(np.float64)\n        fb = ~np.isfinite(M).any(1) & np.isfinite(Bm).any(1)\n        M[fb] = Bm[fb]\n        M[~have] = np.nan\n        mats.append(M)\n    Z = []\n    for k, M in enumerate(mats):\n        mu, sd = np.asarray(stats[\"mean\"][k]), np.asarray(stats[\"std\"][k])\n        z = np.zeros_like(M)\n        g = sd > 0\n        z[
… [2,100 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
ok
data/processed/descriptors/prospeccts/:
a1_default_D.ids.parquet
a1_default_D.ids.parquet.prov.json
a1_default_D.layout.json
a1_default_D.npy
a1_default_L.ids.parquet
a1_default_L.ids.parquet.prov.json
a1_default_L.layout.json
a1_default_L.npy
a1_pair_only_D.ids.parquet
a1_pair_only_D.ids.parquet.prov.json
a1_pair_only_D.layout.json
a1_pair_only_D.npy
a1_pair_only_L.ids.parquet
a1_pair_only_L.ids.parquet.prov.json
a1_pair_only_L.layout.json
a1_pair_only_L.npy
a1r
b0_default_D.ids.parquet
b0_default_D.ids.parquet.prov.json
b0_default_D.layout.json
b0_default_D.npy
b0_default_L.ids.parquet
b0_default_L.ids.parquet.prov.json
b0_default_L.layout.json
b0_default_L.npy
b1_default_D.ids.parquet
b1_default_D.ids.parquet.prov.json
b1_default_D.layout.json
b1_default_D.npy
b1_default_L.ids.parquet
b1_default_L.ids.parquet.prov.json
b1_default_L.layout.json
b1_default_L.npy
b1_learned_D.ids.parquet
b1_learned_D.ids.parquet.prov.json
b1_learned_D.layout.json
b1_learned_D.npy
b1_learned_L.ids.parquet
b1_learned_L.ids.parquet.prov.json
```


**→ tool call `Bash`** · 2026-10-28 04:03:45

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd\nt=pd.read_parquet('data/processed/benchmarks/prospeccts_pockets.parquet')\nprint(t.groupby(['source_dir']).agg(n=('pocket_id','size'), sub=('subset', lambda s: s.unique()[:5].tolist()), ex=('pocket_id','first')).to_string())\nn=pd.read_parquet('data/splits/homology_nodes.parquet'); p=n[n.dataset=='prospeccts']; print(p[['pdb_id','chain','pocket_ids','sid','group_id']].head())\n\"", "description": "Map prospeccts source dirs to subsets"}
```


**← tool result**

```
                                                                              n              sub                                                     ex
source_dir                                                                                                                                             
NMR_structures/NMR_structures                                               329             [P2]                        prospeccts:NMR_structures/cz00A
barelier_structures/barelier_structures                                     115             [P6]                    prospeccts:barelier_structures/1b66
barelier_structures/barelier_structures_cofactors                           115           [P6.2]          prospeccts:barelier_structures_cofactors/1b66
decoy/decoy_rational_structures                                            1956             [P3]             prospeccts:decoy_rational_structures/1a42A
decoy/decoy_shape_structures                                               1956             [P4]                prospeccts:decoy_shape_structures/1a42A
identical_structures/identical_structures                                   326             [P1]                  prospeccts:identical_structures/1a42A
identical_structures_similar_ligands/identical_structures_similar_ligands    45           [P1.2]  prospeccts:identical_structures_similar_ligands/1bk0A
kahraman_structures/kahraman_structures                                     100  [P5,P5.2, P5.2]                   prospeccts:kahram
… [645 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-28 04:04:23

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_prospeccts.py", "content": "\"\"\"Independent C2 re-derivation + ProSPECCTs sanity (D1/D1.2/D2) + P6 vs P6.2 investigation.\"\"\"\nimport json\nimport os\nimport sys\n\nimport numpy as np\nimport pandas as pd\nfrom sklearn.metrics import roc_auc_score\n\nsys.path.insert(0, \"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify\")\nfrom vlib import ROOT, final_scores, desc_matrix, pair_cos, read_sealed, unit_weights, zcos_embed  # noqa\n\nres = {}\npairs, h = read_sealed(\"prospeccts_pairs.parquet\", \"verify C2 + ProSPECCTs sanity + P6/P6.2 (independent verifier)\")\nres[\"sha256\"] = h\nres[\"columns\"] = list(pairs.columns)\ntab = pd.read_parquet(ROOT / \"data/processed/benchmarks/prospeccts_pockets.parquet\").set_index(\"pocket_id\")\n\n# --- own subset identification from the pocket source directory (+ phosphate flag for D5 vs D5.2)\nDIR2SUB = {\"identical_structures\": \"P1\", \"identical_structures_similar_ligands\": \"P1.2\", \"NMR_structures\": \"P2\",\n           \"decoy_rational_structures\": \"P3\", \"decoy_shape_structures\": \"P4\", \"kahraman_structures\": \"P5.2\",\n           \"barelier_structures\": \"P6\", \"barelier_structures_cofactors\": \"P6.2\", \"review_structures\": \"P7\"}\nda = pairs.pocket_a.str.split(\":\").str[1].str.split(\"/\").str[0]\ndb = pairs.pocket_b.str.split(\":\").str[1].str.split(\"/\").str[0]\nres[\"pairs_with_mixed_dirs_by_reported_subset\"] = p
… [7,846 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_prospeccts.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 04:04:28

```
{"command": "source .venv/bin/activate && time OMP_NUM_THREADS=8 python results/verify/v_prospeccts.py > results/verify/v_prospeccts.log 2>&1; tail -5 results/verify/v_prospeccts.log; ls -la data/sealed/prospeccts_pairs.parquet; cat results/verify/v_tough_mc_*.log", "description": "Run ProSPECCTs verification", "timeout": 2400000}
```


**← tool result**

```
real	0m42.891s
user	0m51.985s
sys	0m1.342s
  "se": 0.040832582682033325,
  "p": 0.24862431215607803,
  "n_valid": 1998
 }
}
---------- 1 gmagnusson nogroup 2614190 Oct 27 18:55 data/sealed/prospeccts_pairs.parquet
C1-D {'auc_a': 0.699485353422565, 'auc_b': 0.5458167406694592, 'delta': 0.15366861275310584, 'ci_low': 0.054144465401967524, 'ci_high': 0.28405567171939494, 'lower95': 0.09138840421879522, 'se': 0.05091400563834216, 'p': 0.008449577521123944, 'n_units': 102, 'n_degenerate': 0, 'p_by_2000_block': [0.0074962518740629685, 0.010494752623688156, 0.008995502248875561, 0.010494752623688156, 0.009495252373813094, 0.006496751624187906, 0.0074962518740629685, 0.008995502248875561, 0.0074962518740629685, 0.011494252873563218]}
C1a {'auc_a': 0.697590120462388, 'auc_b': 0.5683575037531678, 'delta': 0.12923261670922015, 'ci_low': 0.012848513998013508, 'ci_high': 0.20364208597453418, 'lower95': 0.04089373235827337, 'se': 0.04075001526305188, 'p': 0.01639918004099795, 'n_units': 112, 'n_degenerate': 0, 'p_by_2000_block': [0.013493253373313344, 0.015492253873063468, 0.019490254872563718, 0.01199400299850075, 0.021989005497251374, 0.019490254872563718, 0.012993503248375811, 0.014492753623188406, 0.017991004497751123, 0.020989505247376312]}
C1b {'auc_a': 0.697590120462388, 'auc_b': 0.5680769742385221, 'delta': 0.1295131462238659, 'ci_low': 0.013184902016655457, 'ci_high': 0.2559320121685512, 'lower95': 0.04685691556256889, 'se': 0.05072283132783713, 'p': 0.017149142542872857, 'n_units
… [262 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:05:25

```
{"command": "source .venv/bin/activate && python -c \"\nimport json; r=json.load(open('results/verify/v_prospeccts.json'))\nfor k in ['columns','pairs_with_mixed_dirs_by_reported_subset','reported_subset_counts','crosstab_reported_vs_own','self_counts','is_self_equals_same_id','P6_vs_P62','c2_per_subset','C2']: print(k, json.dumps(r[k]))\nfor s,d in r['subsets'].items(): print(s, json.dumps(d))\n\"", "description": "Show ProSPECCTs results"}
```


**← tool result**

```
columns ["pair_id", "pocket_a", "pocket_b", "label", "subset", "source_label", "is_self", "decoy_nsub"]
pairs_with_mixed_dirs_by_reported_subset {}
reported_subset_counts {"P2": 108241, "P1": 106276, "P3": 80580, "P4": 80580, "P7": 56399, "P5.2": 10000, "P5": 6400, "P1.2": 2025, "P6": 62, "P6.2": 62}
crosstab_reported_vs_own {"P1": {"P1": 106276}, "P1.2": {"P1.2": 2025}, "P2": {"P2": 108241}, "P3": {"P3": 80580}, "P4": {"P4": 80580}, "P5": {"P5.2": 6400}, "P5.2": {"P5.2": 10000}, "P6": {"P6": 62}, "P6.2": {"P6.2": 62}, "P7": {"P7": 56399}}
self_counts {"P1": {"is_self_col": 326, "same_pocket_id": 326, "same_pdb_chain": 326}, "P1.2": {"is_self_col": 45, "same_pocket_id": 45, "same_pdb_chain": 45}, "P2": {"is_self_col": 329, "same_pocket_id": 329, "same_pdb_chain": 7729}, "P3": {"is_self_col": 326, "same_pocket_id": 326, "same_pdb_chain": 1956}, "P4": {"is_self_col": 326, "same_pocket_id": 326, "same_pdb_chain": 1955}, "P5": {"is_self_col": 80, "same_pocket_id": 80, "same_pdb_chain": 80}, "P5.2": {"is_self_col": 100, "same_pocket_id": 100, "same_pdb_chain": 100}, "P6": {"is_self_col": 0, "same_pocket_id": 0, "same_pdb_chain": 0}, "P6.2": {"is_self_col": 0, "same_pocket_id": 0, "same_pdb_chain": 0}, "P7": {"is_self_col": 49, "same_pocket_id": 49, "same_pdb_chain": 49}}
is_self_equals_same_id true
P6_vs_P62 {"n_P6": 62, "n_P62": 62, "identical_pairs_and_labels": true, "n_pos": 19}
c2_per_subset {"P5.2": {"delta": 0.046796479564856, "n_pairs": 9900, "n_units": 91, "auc_final": 0.7
… [11,090 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:05:39

```
{"command": "grep -n \"read_parquet\\|parquet\\|partition\\|split\\|val\\b\\|test\\|holdout\" scripts/train_a4b.py | head -60; sha256sum scripts/train_a4b.py src/pocketcompare/a4b.py", "description": "Inspect A4b training data sources"}
```


**← tool result**

```
6:    python scripts/train_a4b.py --synthetic --config n1_base --device cpu   # code smoke test on random data only
8:Training data (never TOUGH-M1, BLiPS-val, PPIPS-val or any test set):
9:* BLiPS-train v2 labelled site pairs (data/splits/blips_train_pairs_v2.parquet; label, max_tc);
75:        sites = pd.read_parquet(A4.SITES_V2)
76:        tr = sites[sites.partition == "train"].sort_values("site_id").reset_index(drop=True)
86:        pk = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
87:        cs = pd.read_parquet(ROOT / "data/splits/ppips_complex_splits.parquet")
88:        pt = pk[pk.split == "train"].reset_index(drop=True)
93:        if synthetic:     # code smoke test: random inputs, never real descriptors
112:        pairs = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
135:        sym = pd.read_parquet(ROOT / "data/splits/ppips_sym_pairs_train.parquet")
136:        orth = pd.read_parquet(ROOT / "data/splits/ppips_ortho_queries_train.parquet")
140:        self.n = {"sites": Nb, "sites_holdout": int(self.hold.sum()), "groups_holdout": len(hold),
222:    model.eval()
285:    model.eval()
330:    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
335:    ap.add_argument("--synthetic", action="store_true", help="random inputs (code smoke test; no real fit)")
337:    ap.add_argument("--max-epochs", type=int, default=None, help="override (smoke tests only)")
340:        raise SystemExit("refusing to fit on real data: 
… [320 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:05:43

```
{"command": "sed -n 70,140p scripts/train_a4b.py", "description": "Read training data loader"}
```


**← tool result**

```
    2Nb.. PPIPS-train pockets.  Entities (masking): BLiPS site s -> s; PPIPS pocket p -> Nb + p."""

    def __init__(self, inp: str, synthetic: bool = False):
        self.inp = inp
        rng = np.random.default_rng(SEEDS[0])
        sites = pd.read_parquet(A4.SITES_V2)
        tr = sites[sites.partition == "train"].sort_values("site_id").reset_index(drop=True)
        self.site_ids = tr.site_id.tolist()
        Nb = len(tr)
        self.Nb = Nb
        ids = A4.ids_table("blips").set_index("pocket_id").loc[self.site_ids]
        self.dmatch = ids.d_match.to_numpy(bool)
        # ---- inputs
        self.scaler = A4.blips_train_scaler(inp)
        XL = A4.head_input(A4.raw_parts("blips", "L", self.site_ids, inp), self.scaler)
        XD = A4.head_input(A4.raw_parts("blips", "D", self.site_ids, inp), self.scaler)
        pk = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
        cs = pd.read_parquet(ROOT / "data/splits/ppips_complex_splits.parquet")
        pt = pk[pk.split == "train"].reset_index(drop=True)
        Xp = A4.head_input(A4.raw_parts("ppips", "D", pt.pocket_id.tolist(), inp), self.scaler)
        Np = len(pt)
        self.Np = Np
        X = np.concatenate([XL, XD, Xp]).astype(np.float32)
        if synthetic:     # code smoke test: random inputs, never real descriptors
            X = rng.normal(size=X.shape).astype(np.float32)
        self.X = X
        # ---- groups (global ints) per entity
        grp_b = pd.factorize(tr.group_id)[0]
 
… [2,294 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:05:54

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd\ns=pd.read_parquet('data/splits/blips_sites_v2.parquet'); print(s.columns.tolist()); print(s.head(2).T)\nn=pd.read_parquet('data/splits/homology_nodes.parquet'); print(n.columns.tolist()); print(n.dataset.value_counts())\np=pd.read_parquet('data/processed/ppi/ppips/pockets.parquet'); print(p.columns.tolist()); print(p.head(2).T)\nc=pd.read_parquet('data/splits/ppips_complex_splits.parquet'); print(c.columns.tolist()); print(c.head(2))\n\"", "description": "Inspect BLiPS sites, nodes, PPIPS tables"}
```


**← tool result**

```
['site_id', 'partition_v1', 'node_id', 'sid', 'protein', 'uniprot', 'pdb_id', 'chain', 'site_index', 'site_residues', 'structure_id', 'site_name', 'group_id', 'site_is_ion', 'all_ccds', 'q_ccds', 'n_qualifying', 'label_ccd', 'label_ha', 'label_smiles', 'label_cluster', 'cluster_in_train', 'n_lmode_points', 'partition']
                                                                  0                                                  1
site_id                             burrow_dev:A0A0B4KG38__6qp8_A:3                    burrow_dev:A0A0B4KG38__6qp8_A:4
partition_v1                                                    val                                                val
node_id                               burrow_dev:A0A0B4KG38__6qp8_A                      burrow_dev:A0A0B4KG38__6qp8_A
sid                                                         s027597                                            s027597
protein                                          A0A0B4KG38__6qp8_A                                 A0A0B4KG38__6qp8_A
uniprot                                                  A0A0B4KG38                                         A0A0B4KG38
pdb_id                                                         6qp8                                               6qp8
chain                                                             A                                                  A
site_index                                                        3                                         
… [4,383 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:06:01

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd\nn=pd.read_parquet('data/splits/homology_nodes.parquet'); d=n[n.dataset=='dimers']; print(d[['node_id','uniprot','pdb_id','chain','fs_key','sid']].head(3).to_string()); print(n[n.dataset=='tough_m1'][['node_id','pdb_id','chain','sid','group_id']].head(3).to_string())\nc=pd.read_parquet('data/splits/ppips_complex_splits.parquet'); print(c.complex.head().tolist())\nprint(d.node_id.str.contains('0000000065760570').sum())\n\"", "description": "Map PPIPS complexes to homology nodes"}
```


**← tool result**

```
                            node_id uniprot pdb_id chain  fs_key      sid
35041  dimers:AF-0000000065760335_A  P31946    NaN     A   16888  s025689
35042  dimers:AF-0000000065760335_B  P31946    NaN     B   16889  s025689
35043  dimers:AF-0000000065760352_A  P62258    NaN     A   16890  s013500
          node_id pdb_id chain      sid         group_id
0  tough_m1:11asA   11as     A  s001983  tough_m1:g00027
1  tough_m1:13pkD   13pk     D  s003727  tough_m1:g00166
2  tough_m1:154lA   154l     A  s030684  tough_m1:g00425
['AF-0000000065760570', 'AF-0000000065760573', 'AF-0000000065761128', 'AF-0000000065762644', 'AF-0000000065763136']
2
```


**→ tool call `Write`** · 2026-10-28 04:06:22

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_leak.py", "content": "\"\"\"Leakage checks for TOUGH-M1-test vs TOUGH-M1-dev, BLiPS-train v2 and the A4b training data (verifier).\"\"\"\nimport json\nimport sys\n\nimport numpy as np\nimport pandas as pd\n\nsys.path.insert(0, \"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify\")\nfrom vlib import ROOT  # noqa\n\nr = {}\nsplit = pd.read_parquet(ROOT / \"data/splits/tough_m1_pockets_split.parquet\")\nnodes = pd.read_parquet(ROOT / \"data/splits/homology_nodes.parquet\")\ntm = nodes[nodes.dataset == \"tough_m1\"].set_index(\"node_id\")\nsplit = split.join(tm[[\"pdb_id\", \"chain\"]], on=\"node_id\")\ntest, dev = split[split.partition == \"test\"], split[split.partition == \"dev\"]\nkey = lambda d: set(zip(d.pdb_id.str.lower(), d.chain))  # noqa\nr[\"test_dev_pocket_id_overlap\"] = len(set(test.pocket_id) & set(dev.pocket_id))\nr[\"test_dev_pdbchain_overlap\"] = len(key(test) & key(dev))\nr[\"test_dev_pdb_overlap\"] = len(set(test.pdb_id) & set(dev.pdb_id))\nr[\"test_dev_sid_overlap\"] = len(set(test.sid) & set(dev.sid))\nr[\"test_dev_group_overlap\"] = len(set(test.group_id) & set(dev.group_id))\n\nbl = pd.read_parquet(ROOT / \"data/splits/blips_sites_v2.parquet\")\nbtr = bl[bl.partition == \"train\"]\nr[\"blips_train_sites\"] = len(btr)\nr[\"test_blipstrain_pdbchain_overlap\"] = len(key(test) & set(zip(btr.pdb_id.str.lower(), btr.chain)))\nr[\"test_blipstrain_pdb_overlap\"] = len(set(
… [3,481 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_leak.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 04:06:25

```
{"command": "source .venv/bin/activate && ls data/processed/descriptors/blips/a1r/ | head; python results/verify/v_leak.py 2>&1 | tail -50", "description": "Run leakage checks", "timeout": 600000}
```


**← tool result**

```
L_base.npz
L_sph8.npz
U_base.npz
U_sph8.npz
a1_layout.json
env_layout.json
ids.parquet
ids.parquet.prov.json
summary.json
{
 "test_dev_pocket_id_overlap": 0,
 "test_dev_pdbchain_overlap": 0,
 "test_dev_pdb_overlap": 1,
 "test_dev_sid_overlap": 0,
 "test_dev_group_overlap": 0,
 "blips_train_sites": 2318,
 "test_blipstrain_pdbchain_overlap": 0,
 "test_blipstrain_pdb_overlap": 2,
 "test_blipstrain_sid_overlap": 0,
 "test_blipsall_v2_pdbchain_overlap": 0,
 "blips_train_pairs_sites_all_train": true,
 "ppips_train_pockets": 15555,
 "ppips_train_pocket_split_consistent": true,
 "ppips_train_pairs_in_train_pockets": true,
 "ppips_train_complexes_mapped_to_nodes": 2966,
 "direct_edges_test_to_blips_train": 0,
 "direct_edges_test_to_ppips_train": 565,
 "direct_edges_test_to_dev": 0,
 "test_sealed_flags": {
  "touch_burrow": 0,
  "touch_sealed": 728
 },
 "input_stats_n_ref_a1": [
  4636,
  4636
 ],
 "input_stats_n_ref_env": [
  4636,
  4636
 ],
 "input_stats_mean_max_abs_diff_refit_on_blips_train": [
  0.0,
  0.0
 ]
}
```


**→ tool call `Write`** · 2026-10-28 04:06:48

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_ppips_sens.py", "content": "\"\"\"Sensitivity: C1a/C1b on TOUGH-M1-test pairs whose pockets have no direct homology edge to PPIPS-train chains\n(A4b training data).  Verifier code.\"\"\"\nimport json\nimport sys\n\nimport numpy as np\nimport pandas as pd\nfrom sklearn.metrics import roc_auc_score\n\nsys.path.insert(0, \"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify\")\nfrom vlib import ROOT, boot_paired, components_from_labels, desc_matrix, final_scores, pair_cos, read_sealed, zcos_embed  # noqa\n\npairs, _ = read_sealed(\"tough_m1_test_pairs.parquet\", \"verify: sensitivity to PPIPS-train homology (verifier)\")\nsplit = pd.read_parquet(ROOT / \"data/splits/tough_m1_pockets_split.parquet\")\nP = split[split.partition == \"test\"].sort_values(\"pocket_id\").reset_index(drop=True)\npos = {p: i for i, p in enumerate(P.pocket_id)}\nia, ib = pairs.pocket_a.map(pos).to_numpy(), pairs.pocket_b.map(pos).to_numpy()\ny = pairs.label.astype(int).to_numpy()\nunit = components_from_labels(P.ligand_cluster.to_numpy(), P.group_id.to_numpy())\n\nnodes = pd.read_parquet(ROOT / \"data/splits/homology_nodes.parquet\")\npk = pd.read_parquet(ROOT / \"data/processed/ppi/ppips/pockets.parquet\")\ndim = nodes[nodes.dataset == \"dimers\"]\ndim = dim.assign(cx=dim.node_id.str.split(\":\").str[1].str.rsplit(\"_\", n=1).str[0])\nS = set(dim.sid[dim.cx.isin(set(pk.complex[pk.split == \"train\"]))])\nedges = p
… [1,349 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_ppips_sens.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 04:06:52

```
{"command": "source .venv/bin/activate && python results/verify/v_ppips_sens.py 2>&1 | tail -40", "description": "Run PPIPS-homology sensitivity", "timeout": 900000}
```


**← tool result**

```
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
  "se": 0.04171108463238371,
  "p": 0.004997501249375313,
  "n_units": 110,
  "n_degenerate": 0
 },
 "C1b_clean": {
  "auc_a": 0.699159015694157,
  "auc_b": 0.5670033921049689,
  "delta": 0.1321556235891881,
  "ci_low": -0.002307135080382655,
  "ci_high": 0.2738904146763063,
  "lower95": 0.04083667639792488,
  "se": 0.059557015705546466,
  "p": 0.026486756621689155,
  "n_units": 110,
  "n_degenerate": 0
 },
 "final_auc_pairs_touching_ppips_homologues": 0.6915074390629946
}
```


**→ tool call `Bash`** · 2026-10-28 04:07:28

```
{"command": "grep -n \"blips_set(\\|vertex_set(\\|exclusions\\|stage_vertex\" scripts/final_eval.py | head; sed -n 883,908p scripts/final_eval.py; sed -n 1290,1330p scripts/final_eval.py", "description": "Find BLiPS/Vertex details in final_eval"}
```


**← tool result**

```
59:  BLiPS-test (L, D; exclusions blips_test_exclusions_v2; chemotype_seen recomputed vs BLiPS-train v2): as BLiPS-val;
344:def blips_set(name, pairs, sites, cache_ds, desc_ds, exclusions=None, allow_missing=False) -> PairSet:
347:    if exclusions is not None:
348:        S = S[~S.site_id.isin(exclusions)].reset_index(drop=True)
435:def vertex_set(pairs: pd.DataFrame, synthetic: bool) -> PairSet:
883:def stage_vertex(ps: PairSet, method, store, args):
1281:        exc = pd.read_parquet(ROOT / "data/splits/blips_test_exclusions_v2.parquet")
1286:        bl = blips_set("blips_test", bp, bs, "blips_test_holo", "blips_test_holo",
1287:                       exclusions=set(exc.site_id[exc.excluded]))
1288:        af = blips_set("blips_test", bp, bs, "blips_test_af", "blips_test_af", exclusions=set(exc.site_id[exc.excluded]),
def stage_vertex(ps: PairSet, method, store, args):
    log(f"[vertex] {len(ps.pockets)} pockets, {len(ps.y)} pocket pairs")
    vecs = final_vectors(ps, method, store, modes=("L",)) + b0_vectors(ps)[:1] \
        + descriptor_vectors(ps, store, BASE_SPECS, modes=("L",))
    fsv, fsi = b0p_foldseek(ps, "vertex")
    vecs += fsv
    pr = ps.pairs.protein_pair.to_numpy()
    codes, uniq = pd.factorize(pr)
    lab = pd.Series(ps.y).groupby(codes).agg(["min", "max"])
    y = lab["max"].to_numpy()
    n_conf = int((lab["min"] != lab["max"]).sum())
    unit = ps.pockets.unit.to_numpy()
    first = pd.Series(np.arange(len(codes))).groupby(codes).first().to_numpy()
 
… [3,739 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:07:34

```
{"command": "sed -n 982,1084p scripts/final_eval.py", "description": "Read PPIPS stage"}
```


**← tool result**

```
def stage_ppips(split: str, ortho: pd.DataFrame, sym: pd.DataFrame, method, store, args):
    """P-ortho / P-sym exactly as eval_dev.main_ppips, for the given split (z-score on PPIPS-train)."""
    P = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
    cs = pd.read_parquet(ROOT / "data/splits/ppips_complex_splits.parquet")
    P = P[["pocket_id", "complex", "is_interface", "split", "volume_A3"]].copy()
    P["group"] = P.complex.map(dict(zip(cs.complex, cs.group)))
    P["logv"] = np.log(np.clip(P.volume_A3.to_numpy(float), 1.0, None))
    pid = {p: i for i, p in enumerate(P.pocket_id)}
    tr = (P.split == "train").to_numpy()
    ev_ = (P.split == split).to_numpy()
    eval_idx = np.where(ev_)[0]
    ref = tr | ev_
    members = P.groupby("complex").indices
    n_eval = len(eval_idx)
    Q = ortho.reset_index(drop=True)
    oq, oc, ol = [], [], []
    for k, r in enumerate(Q.itertuples()):
        cand = members[r.partner_complex]
        posset = set(r.positives)
        oq += [k] * len(cand)
        oc += list(cand)
        ol += [P.pocket_id.iat[c] in posset for c in cand]
    oq, oc, ol = np.asarray(oq), np.asarray(oc), np.asarray(ol)
    q_pk = Q["query"].map(pid).to_numpy()
    o_i = q_pk[oq]
    q_unit = Q.query_complex.map(dict(zip(P.complex, P.group))).to_numpy()
    S_ = sym.reset_index(drop=True)
    a_i, b_i = S_.pocket_a.map(pid).to_numpy(), S_.pocket_b.map(pid).to_numpy()
    sq, sh = np.concatenate([a_i, b_i]), np.concatenate([b_i, a_i])
  
… [4,028 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-28 04:08:05

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_spot.py", "content": "\"\"\"Spot checks: Vertex FINAL-L AUC, BLiPS-test FINAL-L AUC, PPIPS-test FINAL P-ortho MRR, TOUGH-M1 full-minus-dev\nB0 (+ shipped fpocket / ligand-size variants).  Verifier code.\"\"\"\nimport json\nimport re\nimport sys\n\nimport numpy as np\nimport pandas as pd\nfrom sklearn.metrics import roc_auc_score\n\nsys.path.insert(0, \"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify\")\nfrom vlib import ROOT, final_scores, final_seed_embeddings, read_sealed  # noqa\n\nsumm = pd.read_parquet(ROOT / \"results/final/final_summary.parquet\")\nFIN = \"pocketcompare-final:A4b:n1_linear|raw\"\n\n\ndef rep(set_, arm=\"FINAL\", cfg=FIN, var=\"raw\", mode=\"L\", sub=\"all\", col=\"auc\"):\n    r = summ[(summ.set == set_) & (summ.arm == arm) & (summ.config == cfg) & (summ.variant == var)\n             & (summ[\"mode\"] == mode) & (summ.subset == sub)]\n    return [float(r[col].iloc[0]), int(r.n_pairs.iloc[0])] if len(r) else None\n\n\ndef okmask(ds, pid):\n    ix = pd.read_parquet(ROOT / f\"data/processed/cache/points/{ds}/index.parquet\").set_index(\"pocket_id\").reindex(pid)\n    return (ix.status == \"ok\").to_numpy(), ix\n\n\nout = {}\n# ------------------------------------------------------------------ Vertex\nvp, _ = read_sealed(\"vertex_pairs.parquet\", \"verify spot check Vertex AUC (verifier)\")\npid = sorted(set(vp.pocket_a) | set(vp.pocket_b))\npos = {p: i for i, p 
… [5,678 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_spot.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 04:08:10

```
{"command": "source .venv/bin/activate && ls data/processed/descriptors/ | tr '\\n' ' '; ls data/processed/descriptors/ppips/a1r data/processed/descriptors/vertex/a1r data/processed/descriptors/blips_test_holo/a1r 2>&1 | head -30", "description": "Check descriptor dirs exist"}
```


**← tool result**

```
blips blips_test_af blips_test_holo ppi_l ppips prospeccts tough_m1 vertex data/processed/descriptors/blips_test_holo/a1r:
L_base.npz
L_sph8.npz
U_base.npz
U_sph8.npz
a1_layout.json
env_layout.json
ids.parquet
ids.parquet.prov.json
summary.json

data/processed/descriptors/ppips/a1r:
D_base.npz
D_sph8.npz
a1_layout.json
env_layout.json
ids.parquet
ids.parquet.prov.json
summary.json

data/processed/descriptors/vertex/a1r:
L_base.npz
L_sph8.npz
U_base.npz
U_sph8.npz
a1_layout.json
env_layout.json
ids.parquet
ids.parquet.prov.json
summary.json
```


**→ tool call `Bash`** · 2026-10-28 04:08:14

```
{"command": "source .venv/bin/activate && time OMP_NUM_THREADS=16 python results/verify/v_spot.py > results/verify/v_spot.log 2>&1; tail -60 results/verify/v_spot.log; ls -la data/sealed | awk '{print $1, $NF}'", "description": "Run spot checks", "timeout": 2400000}
```


**← tool result**

```
real	3m28.421s
user	0m17.259s
sys	0m4.343s
  "label_conflicts": 0,
  "auc_final_L": 0.821921817611433,
  "reported": [
   0.8219218176114329,
   6931
  ]
 },
 "blips_test": {
  "n_sites": 3603,
  "n_excluded": 3,
  "n_pairs": 41438,
  "n_pos": 6905,
  "auc_final_L": 0.7258432588266326,
  "reported": [
   0.7258432441485254,
   41438
  ]
 },
 "ppips_test": {
  "n_queries": 153,
  "mrr_final_raw": 0.6832078778157209,
  "mrr_ties_pessimistic": 0.6832078778157209,
  "top1": 0.5424836601307189,
  "reported_mrr": 0.6832078778157209,
  "reported_top1": 0.5424836601307189
 },
 "tough_full_minus_dev_B0": {
  "n_pairs": 866483,
  "n_pos": 430846,
  "L_shell_volume": [
   0.8152563710265798,
   866483
  ],
  "D_volume": [
   0.5432913486768524,
   794332
  ],
  "residue_list_points_volume": [
   0.5932266508487494,
   866483
  ],
  "fpocket_volume_shipped": [
   0.5553063908945859,
   866483
  ],
  "fpocket_n_residues_shipped": [
   0.580223272288536,
   866483
  ],
  "ligand_heavy_atoms": [
   0.9564879259413177,
   866483
  ],
  "reported_B0_L": [
   0.8152563710265799,
   866483
  ],
  "tm_score_auc": 0.5199714007207781
 }
}
total 25524
dr-x--S--- .
drwxr-sr-x ..
---------- blips_test_pairs.parquet
---------- blips_test_sites.parquet
---------- ppi_l_test_b6.parquet
---------- ppi_l_test_pairs.parquet
---------- ppips_sym_test_pairs.parquet
---------- ppips_test_queries.parquet
---------- prospeccts_pairs.parquet
---------- tough_m1_pairs.parquet
---------- tough_m1_test_pairs.parque
… [33 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:11:54

```
{"command": "source .venv/bin/activate && cut -f2,3 results/verify/unseal_log.tsv | sort -u; grep -E \"tough_m1_test|prospeccts_pairs|vertex|blips_test|ppips_test_q|tough_m1_pairs\" data/sealed_SHA256SUMS.txt data/splits/SHA256SUMS.txt; python - <<'EOF'\nimport json\ndef holm(ps):\n    ids=sorted(ps,key=ps.get); m=len(ids); adj={}; run=0\n    for k,i in enumerate(ids):\n        run=max(run,min(1,(m-k)*ps[i])); adj[i]=run\n    return adj\nV='/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/'\nt=json.load(open(V+'v_tough.json'))['claims']; p=json.load(open(V+'v_prospeccts.json'))['C2']\nmc={c:json.load(open(V+f'v_tough_mc_{c}.json'))['p'] for c in ['C1a','C1b','C1-D']}\nrep=json.load(open('results/final/final_claims.json'))\nout={}\nfor nm,ps in [('reported',{c:rep[c]['p_one_sided'] for c in rep}),('verifier_B2000',{**{c:t[c]['p'] for c in t},'C2':p['p']}),('verifier_B20000_C1',{**mc,'C2':p['p']})]:\n    a=holm(ps); out[nm]={c:{'p':ps[c],'p_holm':a[c],'reject':a[c]<=0.05} for c in ps}\njson.dump(out,open(V+'v_holm.json','w'),indent=1); print(json.dumps(out,indent=1))\nEOF", "description": "Check hashes and compute Holm"}
```


**← tool result**

```
data/sealed/blips_test_pairs.parquet	a10773a548b66a250054f3e5c0ee107af3b55b83cda1aa7bfe4e6ea3bd8916b9
data/sealed/blips_test_sites.parquet	4059e7c80e6172fc473ccde065345d6edcbf6cde39bf155a30eb216423794d32
data/sealed/ppips_test_queries.parquet	85989dcc06b0bce9fe51d720e05b02ddc42f71aa2be7e477b73944f6e8070e41
data/sealed/prospeccts_pairs.parquet	25b92e1254af89498e3499810e689be65dfa8e8dc947d933e1b533765b3e5c57
data/sealed/tough_m1_pairs.parquet	740fe939cec3c67bc9fbe6e412123ef452f4054b23a0a0586fd44086adc1b875
data/sealed/tough_m1_test_pairs.parquet	17973ec019b5e7a511d47e4c0327c777768d102d39753773c6d1f9ebe7a0cda2
data/sealed/vertex_pairs.parquet	abbc5e934a530ad358360e97e2234a32272ecd88fb0dfe80ab4495d7ba402e75
file	sha256
data/sealed_SHA256SUMS.txt:25b92e1254af89498e3499810e689be65dfa8e8dc947d933e1b533765b3e5c57  data/sealed/prospeccts_pairs.parquet
data/sealed_SHA256SUMS.txt:740fe939cec3c67bc9fbe6e412123ef452f4054b23a0a0586fd44086adc1b875  data/sealed/tough_m1_pairs.parquet
data/sealed_SHA256SUMS.txt:abbc5e934a530ad358360e97e2234a32272ecd88fb0dfe80ab4495d7ba402e75  data/sealed/vertex_pairs.parquet
data/sealed_SHA256SUMS.txt:85989dcc06b0bce9fe51d720e05b02ddc42f71aa2be7e477b73944f6e8070e41  data/sealed/ppips_test_queries.parquet
data/splits/SHA256SUMS.txt:5aab4a5b196ef94285f664138386b2235110f6a3e858ab47c4135eb846d26a2d  data/splits/blips_test_exclusions_v2.parquet
data/splits/SHA256SUMS.txt:17973ec019b5e7a511d47e4c0327c777768d102d39753773c6d1f9ebe7a0cda2  data/sealed/tough_m1_test_pa
… [1,522 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:12:15

```
{"command": "tail -n +2 results/verify/unseal_log.tsv | cut -f1,2,4,5 ; ls reports/ | head", "description": "Show verifier unseal log"}
```


**← tool result**

```
2026-10-28T04:59:42+0100	data/sealed/tough_m1_test_pairs.parquet	0o0	0o0
2026-10-28T05:01:32+0100	data/sealed/tough_m1_test_pairs.parquet	0o0	0o0
2026-10-28T05:04:31+0100	data/sealed/prospeccts_pairs.parquet	0o0	0o0
2026-10-28T05:06:55+0100	data/sealed/tough_m1_test_pairs.parquet	0o0	0o0
2026-10-28T05:08:17+0100	data/sealed/vertex_pairs.parquet	0o0	0o0
2026-10-28T05:08:22+0100	data/sealed/blips_test_pairs.parquet	0o0	0o0
2026-10-28T05:08:22+0100	data/sealed/blips_test_sites.parquet	0o0	0o0
2026-10-28T05:08:22+0100	data/sealed/ppips_test_queries.parquet	0o0	0o0
2026-10-28T05:08:23+0100	data/sealed/tough_m1_pairs.parquet	0o0	0o0
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
```


**→ tool call `Write`** · 2026-10-28 04:12:47

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/reports/verification_final.md", "content": "# Verification of the final held-out evaluation (independent verifier, 2026-10-28)\n\nHow I checked: I wrote my own code in `results/verify/` (`vlib.py`, `v_tough.py`, `v_tough_mc.py`, `v_prospeccts.py`, `v_leak.py`, `v_ppips_sens.py`, `v_spot.py`; outputs in `*.json`). It does not import `final_eval.py` or `evaluate.py`. AUCs come from `sklearn.roc_auc_score`, and the vertex bootstrap is my own (multinomial unit counts, pair weight c_u or c_u·c_v, B = 2000, different seeds). I re-derived the units, the D common set, the ProSPECCTs subsets and self-pairs, and the homology groups myself.\n\nThe final-method scores were recomputed from the stored part descriptors and the seed weights (z → clip ±5 → linear → L2, mean of the three 128-d seed cosines). They match the method API that final_eval used: max |Δscore| = 1.8e-7 (L) and 2.0e-7 (D).\n\nSealed files: 9 reads, each logged in `results/verify/unseal_log.tsv`. Every sha256 matched the recorded hash, and every file was back at mode 000 after its read.\n\n| # | check | reported | verifier | verdict |\n|---|---|---|---|---|\n| 1 | C1a AUC final / B1; Δ | 0.697590 / 0.568358; +0.12923 | 0.697590 / 0.568358; +0.12923 | **PASS** |\n| | C1a CI; p | [+0.015, +0.208]; 0.0165 | [+0.023, +0.206]; 0.0145 (B = 20k: [+0.013, +0.204]; 0.0164) | PASS (within MC error) |\n| | C1b B4 AUC; Δ; p | 0.568077; +0.12951; 0.0185 | 0.568077; +0.129
… [5,116 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/reports/verification_final.md (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 04:12:52

```
{"command": "rm -f /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/tough_scores.npz; ls -la /cluster/project/beltrao/gmagnus/pocket_compare/data/sealed | awk '{print $1}' | sort | uniq -c", "description": "Remove scratch scores; confirm seals"}
```


**← tool result**

```
     10 ----------
      1 dr-x--S---
      1 drwxr-sr-x
      1 total
```


**→ tool call `SubagentHandback`** · 2026-10-28 04:13:01

```
{"message": "All checks pass. Every headline number reproduces by an independent code path to ≤1e-8, or exactly at the float32 precision final_eval used. I found no computational error and no test leakage.\n\n- **C1a, C1b, C1-D:** the Δ values match (+0.1292, +0.1295, +0.1537). p-values and CIs agree within Monte-Carlo error.\n- **C2:** macro Δ matches (+0.0223), p = 0.25.\n- **Spot checks:** Vertex, BLiPS-test and PPIPS-test MRR match exactly.\n- **Embeddings:** my numpy re-implementation (mean of the three 128-d seed cosines) agrees with the method API to 2e-7.\n\n**Holm is fragile.** With B=20,000, p is 0.0164 for C1a and 0.0171 for C1b, against a 0.0167 threshold. About 30–50% of independent B=2000 runs would not reject C1a/C1b. The pre-registered seed-0 run does reject. C1-D is robust.\n\n**PI check (a), P6 ≡ P6.2:** the source ships one pair list for both, and the loader picks the right structure folders. They come out identical because BURROW strips all non-protein atoms (cofactors included), so the D6.2 cofactor condition is never tested. The D-mode results rest on only 4 pairs (2 positive), so those AUCs mean nothing.\n\n**PI check (b), B0:** 0.796 on test and 0.815 on full-minus-dev are confirmed. Using the benchmark's own fpocket pockets gives 0.48–0.59, and D-mode gives about 0.55. Ligand heavy-atom count alone gives 0.95, so this is a ligand-size imprint of our 4 Å ligand-shell L-mode, not a property of TOUGH-M1 pockets.\n\n**Minor:** 66 test pockets have homolog
… [315 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```


### PI / user turn · 2026-10-28 06:55:36

The coordinator sent a message while you were working:
PI: one more independent verification, please (≤ 40 min). A pre-registered temporal replication (PREREG2.md) was evaluated by scripts/eval_pdbt.py → results/pdbt/{claims.json,report.md,summary.parquet}. Re-derive R1 (FINAL − B1), R2 (FUSION − FINAL; fusion = 0.5·z(cos FINAL) + 0.5·z(cos L4), z fitted on BLiPS-train pairs, rule in scripts/explore/fusion_a4b_l4.py), R3 (L4 CSLS − FINAL) on the D-mode common set with your own code (sklearn AUC + your own vertex bootstrap, units = hom_component in data/splits/pdbt_sites.parquet, excluding sites with excluded == True, and dropping pairs that involve them), Holm over the three. You may read data/sealed/pdbt_pairs.parquet (chmod 400 → read → chmod 000; log to results/verify/unseal_log.tsv; sha256 must equal the line in data/sealed_SHA256SUMS.txt). Also check: the 9 excluded sites are exactly those listed in RESEARCH_TREE D25; no PDB-T site id appears in any training table; point estimates match to ~1e-6. Append a "PDB-T verification" section to reports/verification_final.md. Final message ≤ 120 words.

Address this before completing your current task.


**→ tool call `Bash`** · 2026-10-28 06:55:48

```
{"command": "cat PREREG2.md | head -120; cat results/pdbt/claims.json | head -150; grep -n \"D25\" -A25 RESEARCH_TREE.md | head -60", "description": "Read PREREG2, PDB-T claims, D25"}
```


**← tool result**

```
# PREREG2 — temporal replication on fresh held-out data (2026-10-28 06:45, before the set exists)

Motivation: the PREREG test sets are spent; the post-test fusion of FINAL and L4 (reports/exploratory_fusion.md)
and the C1/C1-D result need replication on data nobody has looked at. No method is retrained or changed: all arms
are the frozen artefacts (FINAL = configs/final_method.yaml at tag freeze-v1; L4:egnn_small CSLS and N1 as frozen in
results/models/; fusion = w 0.5 z-score rule exactly as declared in scripts/explore/fusion_a4b_l4.py; B1; B0).

## Set: PDB-T (temporal)
- PDB entries in the local mirror (/cluster/scratch/jjaenes/pdb) with initial release date > 2025-11-12 (after the
  BioLiP2 snapshot behind every training set and after BURROW's training data). X-ray or EM ≤ 3.0 Å.
- Sites: non-polymer ligands with ≥ 10 heavy atoms, excluding the committed additive list (data/ref/additives.txt),
  ions, and covalently linked / polymer-like ligands; one site per ligand cluster per chain; protein chain ≥ 50 aa.
- Pairs: positives = sites in different homology groups sharing a ligand with ECFP4 Tc ≥ 0.7; negatives = different
  groups, max Tc < 0.3, 5× positives, seeded (SEEDS[0]); caps as BLiPS (≤ 3 sites/protein, ≤ 300 positives per
  Butina cluster).
- Leakage: any protein with a direct edge (MMseqs2 -a rule or exhaustive Foldseek TM ≥ 0.5 both directions) to any
  training source (BLiPS-train/val v2, PPIPS-train/val, BURROW train/dev, TOUGH-M1-dev, the A4b/L4 training dat
… [13,207 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 06:55:55

```
{"command": "sed -n 285,295p RESEARCH_TREE.md; grep -n \"pdbt:\" RESEARCH_TREE.md | head; source .venv/bin/activate; python -c \"\nimport pandas as pd; s=pd.read_parquet('data/splits/pdbt_sites.parquet'); print(s.columns.tolist()); print(len(s)); print(s.excluded.value_counts()); print([c for c in s.columns if 'excl' in c]); \nfor c in [c for c in s.columns if 'excl' in c]: print(c, s[c].value_counts(dropna=False).to_dict())\nprint(s[s.excluded].T.head(40))\n\"; grep pdbt data/sealed_SHA256SUMS.txt; ls -la data/sealed/pdbt_pairs.parquet; ls results/pdbt", "description": "Inspect PDB-T sites and exclusions"}
```


**← tool result**

```
- [x] P7 Temporal replication PDB-T (PREREG2) — results/pdbt/report.md (987 sites, D set 6,171 pairs / 1,060 pos)
  - [!] R1 FINAL − B1 (D): 0.752 vs 0.671, Δ +0.081 [+0.028, +0.132], Holm p 0.003 — REPLICATES
  - [-] R2 FUSION − FINAL: +0.010 [−0.010, +0.032], Holm p 0.34 — exploratory fusion gain does not replicate
  - [-] R3 L4 − FINAL: −0.022 [−0.061, +0.018] — L4 not better; one-SE choice of the linear head vindicated
  - [x] L-mode FINAL 0.774 vs B1 0.760 (Δ +0.014, CI incl. 0); size-strat D 0.752
  - [x] gate PASS: 996 sites, 545 proteins, 317 homology groups; 1,353 pos / 6,765 neg; 38 ligand clusters
  - [x] leakage: 9,082/13,036 chains removed (edge to any training source); 208 exact-sequence test overlaps removed
  - [x] eval_pdbt.py dry run on BLiPS-val reproduces dev exactly
  - [x] independent PDB-T audit PASS with boundary caveat (reports/audit_splits.md "PDB-T audit"): 0 sequence edges;
        9 sites (8 chains) at min-TM 0.50–0.56 vs training chains → excluded before any score (D25)
- [x] P6 REPORT.md written (143 tagged numbers checked)
['site_id', 'pdb_id', 'chain', 'entity_id', 'protein', 'uniprot', 'sid', 'group_id', 'release_date', 'resolution', 'methods', 'structure_path', 'n_lig_atoms', 'n_lig_instances', 'n_contact_res', 'max_chains_contact', 'n_lmode_points', 'excluded_lt10', 'hom_component', 'excluded', 'excluded_audit_tm_boundary']
996
excluded
False    987
True       9
Name: count, dtype: int64
['excluded_lt10', 'excluded', 'excluded_audit_tm_boun
… [3,149 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 06:56:01

```
{"command": "grep -n \"PDB-T audit\" -A60 reports/audit_splits.md | grep -n -i \"boundary\\|pdbt:\\|0\\.5[0-6]\\|chain\\|[0-9][a-z0-9]\\{3\\}_[A-Z]\" | head -40; source .venv/bin/activate; python -c \"\nimport pandas as pd; s=pd.read_parquet('data/splits/pdbt_sites.parquet'); print(s[s.excluded][['site_id','pdb_id','chain','hom_component']].to_string())\"", "description": "Find audit list of boundary sites"}
```


**← tool result**

```
4:68-- **PDB-T:** 960 chains (829 unique sequences) behind the 996 non-excluded sites in `pdbt_sites.parquet`.
6:70-  - BLiPS v2 train+val proteins (1,851 chains);
7:71-  - PPIPS train+val, both chains of each complex (3,480 model chains);
10:74-  - BURROW assembly partners (2,478 chains; the chain IDs come from `homology_nodes` `burrow_partner`, but I extracted the sequences and structures myself);
11:75-  - as a conservative superset, every other protein chain of the BURROW entries (20,262).
17:81-| Sequence edge (BURROW rule) to BLiPS-v2 / PPIPS / BURROW rep / partners / TOUGH-M1-dev | **PASS** | 0 PDB-T chains, and 0 identical sequences. Near misses at 25–30 % identity: 68 chains. |
18:82-| Sequence edge to *other* chains of BURROW entries (not featurised, not assembly partners; info) | info | 51 chains, 44 proteins, 79 sites. Example: 9uz0_A / 21ok_A vs 3rlf_E at 99.7 % identity; 9tb0_C vs 3mmp_A at 98.6 %. These are only training data if non-assembly chains of BURROW entries count as training. PREREG2 and the builder count only representatives and partners. |
19:83-| Foldseek min-TM ≥ 0.5 to frozen-model training chains | **FAIL (boundary)** | 8 pairs, 7 chains, 9 sites, 6 proteins, 6 PDB-T groups. BURROW rep 6: 9kmd_H / 9lo8_O / 9l3u_A (MSP1) vs 8bv3 at TM 0.51–0.53; 9qmf_C–5zsx_A at 0.50; 32qr_A–4kg0_A at 0.50; 9woj_C–3csv_A at 0.53. BLiPS-v2/BURROW rep 1: 9lqe_B–6zm9_A at 0.555/0.570. PPIPS 1: 9s30_A–AF-…65792505_B at 0.50/0.55. All have min-TM 0.500–0.557 and fident
… [1,219 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 06:56:07

```
{"command": "wc -l scripts/eval_pdbt.py scripts/explore/fusion_a4b_l4.py; grep -n \"def \\|fusion\\|FUSE\\|z(\\|mu_A\\|scales\\|l4\\|L4\\|d_match\\|dmatch\\|pool\\|csls\\|excluded\" scripts/eval_pdbt.py | head -80", "description": "Outline eval_pdbt.py"}
```


**← tool result**

```
  586 scripts/eval_pdbt.py
  561 scripts/explore/fusion_a4b_l4.py
 1147 total
5:    python scripts/eval_pdbt.py --prepare [--device cuda:2]                # label-free: L4 embeddings of PDB-T
15:  L4      L4:egnn_small, designated variant CSLS (k = 10, background = evaluated pool); raw also reported.
16:          Embeddings data/processed/l4_emb/egnn_small/emb_<ds>_{L,U}.npy; for PDB-T they are computed here (--prepare,
18:          data/processed/l4/<ds>/ with scripts/train_l4.load_models / ensemble_embed (= scripts/l4_embed.py).
19:  FUSION  the declared rule of scripts/explore/fusion_a4b_l4.py, reused exactly (its FusedMethod class): w = 0.5,
20:          s = w z(cos_FINAL) + (1 - w) z(cos_L4), both raw, z fitted on BLiPS-train v2 pairs
21:          (results/exploratory/fusion/fusion_scales.json); raw inner product, no CSLS.
22:  B1      default descriptor, pool z-scored cosine, raw (FINAL is raw -> B1 raw, as final_eval C1-D)
27:  R1  FINAL[raw] - B1[raw]          R2  FUSION[raw] - FINAL[raw]          R3  L4[csls] - FINAL[raw]
28:Reported (no multiplicity): the same three deltas in L mode, R3 with L4 raw, and per arm / mode (final_eval.
33:constant, PREREG2.md == its D24 hash, L4 weights / fusion scales / fusion script == the hashes recorded below;
40:(+ reproduction_check.json: FINAL / N1 / L4 / B1 vs results/dev/l4/final_select_all_l4_summary.parquet, FUSION vs
41:results/exploratory/fusion/dev/final_select_fusion_summary.parquet, and the recomputed L4 embeddings vs the
… [5,326 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 06:56:11

```
{"command": "sed -n 253,330p scripts/eval_pdbt.py; grep -n \"class FusedMethod\" -A45 scripts/explore/fusion_a4b_l4.py; sed -n 520,556p scripts/final_eval.py; cat results/exploratory/fusion/fusion_scales.json | head -30", "description": "Read set build, fusion class and L4 embed"}
```


**← tool result**

```
def load_sites(path: Path, partition: str | None) -> tuple[pd.DataFrame, dict]:
    S = pd.read_parquet(path)
    if partition is not None:
        S = S[S.partition == partition]
    info = {"file": str(path), "n_rows": int(len(S))}
    if "excluded" in S and S["excluded"].dtype == bool:
        info["n_excluded_flag"] = int(S["excluded"].sum())
        S = S[~S["excluded"]]
    sid, unit = _pick(S, SITE_COLS, "site id"), _pick(S, UNIT_COLS, "homology component")
    info.update(site_col=sid, unit_col=unit)
    S = S.rename(columns={sid: "site_id"}).assign(_unit=S[unit].to_numpy())
    if S.site_id.duplicated().any():
        raise SystemExit(f"{path}: duplicated site ids")
    return S.sort_values("site_id").reset_index(drop=True), info


def build_set(name: str, ds: str, sites: pd.DataFrame, pairs: pd.DataFrame) -> tuple[FE.PairSet, dict]:
    """final_eval.PairSet over the whole site pool (= z-score / CSLS background), units = homology components."""
    ca, cb = _pick(pairs, PAIR_COLS, "pair site")
    pcl = _pick(pairs, CLUSTER_COLS, "positive ligand cluster", required=False)
    # D25: sites flagged `excluded` (audit boundary) leave the pool; their pairs are dropped and counted (no scores yet)
    keep = pairs[ca].isin(sites.site_id) & pairs[cb].isin(sites.site_id)
    n_drop, n_drop_pos = int((~keep).sum()), int(pairs.label[~keep].sum())
    pairs = pairs[keep].reset_index(drop=True)
    P = FE._attach_geometry(pd.DataFrame({"pocket_id": sites.site_id.to_numpy(), "uni
… [7,268 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 06:56:16

```
{"command": "grep -n \"def fuse\" -A15 scripts/explore/fusion_a4b_l4.py; grep -n \"fusion_scales\\|def fit_scales\\|mu_A\\|sd_A\" scripts/explore/fusion_a4b_l4.py | head -20; ls data/processed/l4_emb/egnn_small/ | grep pdbt; ls data/processed/descriptors/pdbt/ data/processed/descriptors/pdbt/a1r; ls data/processed/cache/points/ | grep pdbt", "description": "Read fuse rule and PDB-T inputs"}
```


**← tool result**

```
117:def fuse(EA, EL, w, sdA, sdL):
118-    """Concatenated embedding whose inner product = w cosA / sdA + (1 - w) cosL / sdL."""
119-    return np.concatenate([np.sqrt(w / sdA) * EA, np.sqrt((1 - w) / sdL) * EL], axis=1).astype(np.float32)
120-
121-
122-# ============================================================================================ scales
123-def fit_scales(args):
124-    """mu / sd of raw pair cosines of FINAL and L4 over BLiPS-train v2 pairs (L + D-matched D pooled)."""
125-    if SCALES.exists():
126-        log(f"{SCALES} exists -> reused (fixed once)")
127-        return json.loads(SCALES.read_text())
128-    tp = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
129-    sites = sorted(set(tp.site_a) | set(tp.site_b))
130-    P = FE._attach_geometry(pd.DataFrame({"pocket_id": sites}), "blips")
131-    pos = {p: i for i, p in enumerate(P.pocket_id)}
132-    ia, ib = tp.site_a.map(pos).to_numpy(), tp.site_b.map(pos).to_numpy()
19:  s_w = w * (cos_A - mu_A) / sd_A + (1 - w) * (cos_L - mu_L) / sd_L,   w in {0.25, 0.50, 0.75}
24:  inner product of the concatenated embedding [sqrt(w/sd_A) e_A, sqrt((1-w)/sd_L) e_L] (768 stored dims), so every
75:SCALES = OUT / "fusion_scales.json"
123:def fit_scales(args):
142:        out["per_mode"][mode] = {"n_pairs": int(ok.sum()), "mu_A": sA.mean(), "sd_A": sA.std(), "mu_L": sL.mean(),
146:    out.update(mu_A=float(sA.mean()), sd_A=float(sA.std()), mu_L=float(sL.mean()), sd_L=float(sL.std()),
150:    log(f"s
… [1,570 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 06:56:26

```
{"command": "grep -n \"read_parquet\\|SITES_V2\\|split ==\\|partition ==\" scripts/train_l4.py | head; ls data/splits/ | grep -v \"^blips\\|^ppips\\|^tough\" ; cat results/pdbt/unseal_log.tsv | cut -f1,2,3,7", "description": "Check L4 training sources and pdbt unseal log"}
```


**← tool result**

```
70:        _STORES[k] = (L4.PointStore(PTS / dataset / f"{loc}.npz"), pd.read_parquet(PTS / dataset / "ids.parquet"))
230:    pk = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
231:    ppt = pk[pk.split == "train"].reset_index(drop=True).pocket_id.tolist()
SHA256SUMS.txt
SPLITS.md
homology_components.json
homology_edges.parquet
homology_nodes.parquet
inputs
pdbt_sites.parquet
ppi_l_pairs_train.parquet
ppi_l_pairs_val.parquet
ppi_l_pockets.parquet
split_changes.json
split_sensitivity.json
time	file	sha256	rows
2026-10-28T07:53:46+0100	data/sealed/pdbt_pairs.parquet	b4bf2909f44a819f4a1fd5160a23e30b2fbbc7695082aaeb460b7899d1f70c60	8118
2026-10-28T07:54:35+0100	data/sealed/pdbt_pairs.parquet	b4bf2909f44a819f4a1fd5160a23e30b2fbbc7695082aaeb460b7899d1f70c60	8118
```


**→ tool call `Bash`** · 2026-10-28 06:56:30

```
{"command": "sed -n 215,245p scripts/train_l4.py", "description": "Read L4 training data section"}
```


**← tool result**

```
    model.load_state_dict(best_state)
    model.eval()
    mem = torch.cuda.max_memory_allocated(device) / 2 ** 30 if str(device).startswith("cuda") else 0.0
    log(f"  seed {seed}: best epoch {best_ep} ES {best:.4f}; {len(hist)} epochs, {time.time() - t0:.0f} s, "
        f"peak GPU mem {mem:.1f} GiB")
    return model, {"seed": seed, "best_epoch": best_ep, "best_es": best, "epochs_run": len(hist), "history": hist,
                   "wall_s": time.time() - t0, "peak_gpu_gib": mem}


def build_training(cfg, synthetic, device, log):
    import torch
    import train_a4b
    data = train_a4b.Data("N1", synthetic=synthetic)
    sc = point_scaler()
    rng = np.random.default_rng(SEEDS[0])
    pk = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
    ppt = pk[pk.split == "train"].reset_index(drop=True).pocket_id.tolist()
    if len(ppt) != data.Np:
        raise RuntimeError("PPIPS-train pocket order differs from train_a4b.Data")
    parts = [gather("blips", "L", data.site_ids, sc, synthetic, rng),
             gather("blips", "U", data.site_ids, sc, synthetic, rng),
             gather("ppips", "D", ppt, sc, synthetic, rng)]
    X, H, M = (np.concatenate([p[k] for p in parts]) for k in range(3))
    av = np.concatenate([p[3] for p in parts])
    T = {"X": torch.from_numpy(X).to(device), "H": torch.from_numpy(H).to(device), "M": torch.from_numpy(M).to(device),
         "N1": torch.from_numpy(np.nan_to_num(data.X)).to(device) if cfg["concat_n1"] else None}
    
… [239 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-28 06:56:33

Now the PDB-T verification script.


**→ tool call `Write`** · 2026-10-28 06:57:05

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_pdbt.py", "content": "\"\"\"Independent re-derivation of PREREG2 R1 / R2 / R3 on PDB-T (D-mode common set) + exclusion / training-table checks.\"\"\"\nimport hashlib\nimport json\nimport sys\n\nimport numpy as np\nimport pandas as pd\nfrom sklearn.metrics import roc_auc_score\n\nsys.path.insert(0, \"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify\")\nfrom vlib import ROOT, boot_paired, desc_matrix, final_seed_embeddings, pair_cos, read_sealed, zcos_embed  # noqa\n\nr = {}\nexp = [l.split()[0] for l in (ROOT / \"data/sealed_SHA256SUMS.txt\").read_text().splitlines()\n       if l.strip().endswith(\"data/sealed/pdbt_pairs.parquet\")]\npairs, h = read_sealed(\"pdbt_pairs.parquet\", \"verify PREREG2 R1/R2/R3 (independent verifier)\")\nr[\"sha256\"], r[\"sha256_expected\"], r[\"sha256_ok\"] = h, exp, h in exp\nr[\"pair_columns\"] = list(pairs.columns)\nca, cb = (\"site_a\", \"site_b\") if \"site_a\" in pairs else (\"pocket_a\", \"pocket_b\")\n\nS = pd.read_parquet(ROOT / \"data/splits/pdbt_sites.parquet\")\nr[\"n_sites_file\"], r[\"n_excluded\"] = len(S), int(S.excluded.sum())\nD25 = {\"pdbt:32qr_A:0\", \"pdbt:9kmd_H:0\", \"pdbt:9l3u_A:0\", \"pdbt:9lo8_O:0\", \"pdbt:9lqe_B:0\", \"pdbt:9qmf_C:0\",\n       \"pdbt:9s30_A:0\", \"pdbt:9s30_A:1\", \"pdbt:9woj_C:0\"}   # chains named in audit_splits.md \"PDB-T audit\" (D25)\nexc = set(S.site_id[S.excluded])\nr[\"excluded_equals_audit_list\"] = e
… [7,240 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_pdbt.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 07:03:57

```
{"command": "source .venv/bin/activate && ls data/processed/l4_emb/egnn_small/ | grep blips; time OMP_NUM_THREADS=16 python results/verify/v_pdbt.py > results/verify/v_pdbt.log 2>&1; cat results/verify/v_pdbt.log | head -200; ls -la data/sealed/pdbt_pairs.parquet", "description": "Run PDB-T verification", "timeout": 1800000}
```


**← tool result**

```
emb_blips_L.npy
emb_blips_U.npy
emb_blips_test_af_L.npy
emb_blips_test_af_U.npy
emb_blips_test_holo_L.npy
emb_blips_test_holo_U.npy

real	0m21.016s
user	0m26.939s
sys	0m0.572s
{
 "sha256": "b4bf2909f44a819f4a1fd5160a23e30b2fbbc7695082aaeb460b7899d1f70c60",
 "sha256_expected": [
  "b4bf2909f44a819f4a1fd5160a23e30b2fbbc7695082aaeb460b7899d1f70c60"
 ],
 "sha256_ok": true,
 "pair_columns": [
  "pair_id",
  "label",
  "max_tc",
  "n_shared",
  "pair_cluster",
  "best_ccd_a",
  "best_ccd_b",
  "site_a",
  "protein_a",
  "group_a",
  "label_ccd_a",
  "site_cluster_a",
  "site_b",
  "protein_b",
  "group_b",
  "label_ccd_b",
  "site_cluster_b",
  "n_shared_stratum",
  "promiscuous",
  "ccd_in_blips_train"
 ],
 "n_sites_file": 996,
 "n_excluded": 9,
 "excluded_equals_audit_list": true,
 "excluded_flag_equals_audit_tm_boundary": true,
 "n_pairs_file": 8118,
 "n_pairs_dropped": 141,
 "n_pos_dropped": 33,
 "pairs_with_unknown_site": 0,
 "n_sites_pool": 987,
 "n_dmatch": 874,
 "n_pairs": 7977,
 "n_pos": 1320,
 "n_pairs_D": 6171,
 "n_pos_D": 1060,
 "l4_norm_range": [
  0.999999923471524,
  1.0000000618975469
 ],
 "fusion_scales_refit": {
  "mu_A": 0.1467735697947879,
  "sd_A": 0.2804997675637712,
  "mu_L": 0.2816380444594207,
  "sd_L": 0.2459955919965482,
  "n": 65858
 },
 "fusion_scales_max_abs_diff": 5.905104738523903e-10,
 "claims": {
  "R1": {
   "auc_a": 0.7519170638246032,
   "auc_b": 0.6713708501456348,
   "delta": 0.08054621367896841,
   "ci_low": 0.02525435297938874,
   "ci_high":
… [2,654 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 07:04:35

```
{"command": "cat >> reports/verification_final.md <<'EOF'\n\n## PDB-T verification (PREREG2: R1 / R2 / R3, D-mode common set)\n\nHow I checked: `results/verify/v_pdbt.py` → `v_pdbt.json`, my own code with sklearn AUC and my own vertex bootstrap (B = 2000, seed 31337). Units = `hom_component` of `pdbt_sites.parquet`. The sealed pairs were read once, the sha256 equals the `data/sealed_SHA256SUMS.txt` line (b4bf2909…), and the file is back at mode 000 (logged).\n\n- **Pool:** 996 sites, minus 9 excluded = 987.\n- **Pairs:** 141 of the 8,118 pairs (33 positive) involve excluded sites and were dropped.\n- **D common set:** 874 sites are D-matched, giving 6,171 pairs / 1,060 positives / 289 units. This matches the report.\n- **FINAL:** recomputed with my own numpy head on `descriptors/pdbt/a1r` U parts.\n- **L4:** taken from the stored `emb_pdbt_U.npy` (unit-norm), with CSLS k = 10 over the D-matched pool. The EGNN forward pass was not re-run.\n- **FUSION:** I refit the z-scales on the BLiPS-train v2 pairs (L plus D-matched D, n = 65,858). They agree with `fusion_scales.json` to 6e-10.\n\n| claim | reported AUC a / b; Δ [CI]; p → Holm | verifier | verdict |\n|---|---|---|---|\n| R1 FINAL − B1 | 0.751917 / 0.671371; +0.0805 [+0.028, +0.132]; 0.0010 → 0.003 | identical (diff 0); +0.0805 [+0.025, +0.130]; 0.0030 → 0.009 | **PASS** (rejects) |\n| R2 FUSION − FINAL | 0.762324 / 0.751917; +0.0104 [−0.010, +0.032]; 0.171 → 0.343 | 0.762324 (diff 1.8e-7, float32 vs float64); +0.0104 [−0.01
… [1,246 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
2026-10-28T05:08:22+0100	data/sealed/ppips_test_queries.parquet	0o0	0o0
2026-10-28T05:08:23+0100	data/sealed/tough_m1_pairs.parquet	0o0	0o0
2026-10-28T08:04:00+0100	data/sealed/pdbt_pairs.parquet	0o0	0o0
```


**→ tool call `SubagentHandback`** · 2026-10-28 07:04:41

```
{"message": "The PDB-T check passes: my own code reproduces R1, R2 and R3 on the D-mode common set (6,171 pairs, 1,060 positive, 289 units).\n\n- **R1 FINAL − B1:** point estimates identical, Δ +0.0805. My p is 0.003 (reported 0.001); Holm rejects, so it replicates.\n- **R2 FUSION − FINAL:** Δ +0.0104, AUC within 1.8e-7 of reported. My p is 0.15 (reported 0.17); not supported.\n- **R3 L4 CSLS − FINAL:** Δ −0.0224, identical; not supported.\n\nHolm decisions are the same under both sets of p-values, with wide margins. My refit of the fusion z-scales on BLiPS-train pairs matches the stored ones to 6e-10.\n\nThe 9 excluded sites are exactly the audit's D25 boundary list. No PDB-T site id, PDB chain or sequence appears in any training table. The sealed file's sha256 matched; read logged, back at mode 000.\n\nNot re-run: L4 uses the stored embeddings. Text slip: the audit says \"7 chains\" but lists 8.\n\nSection appended to `reports/verification_final.md`."}
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
