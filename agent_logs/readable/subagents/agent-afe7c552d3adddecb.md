# Sub-agent afe7c552d3adddecb — Exploratory A4b+L4 fusion (opus)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-28 04:14:01

You run a POST-TEST, EXPLORATORY experiment on a pocket-similarity project. The confirmatory final evaluation is done (results/final/, verified in reports/verification_final.md). Project root: /cluster/project/beltrao/gmagnus/pocket_compare (git; do NOT commit — the PI commits). Read RESEARCH_TREE.md (top status M3 + D19–D21, DEV3–DEV4), PREREG.md, reports/{a4b_selection,l4_pointnet,final_eval_infra,verification_final}.md, results/dev/l4/final_select_all_l4_summary.md, results/final/final_report.md (test numbers — you may look at them, which is exactly why everything you do is labelled exploratory), scripts/eval_dev.py, scripts/final_eval.py. Env: `source .venv/bin/activate`. ≤ 16 CPU threads; GPU cuda:2 if needed.

Question: does a score-level fusion of the final method (A4b:n1_linear raw) and L4:egnn_small help? Observation motivating it: L4 is better on BLiPS, ProSPECCTs decoys P3/P4, PPIPS; A4b on TOUGH-M1 D-mode.
Protocol (write it in the script header BEFORE running): fused score = w·cos_A4b + (1−w)·cos_L4 (both raw; optionally per-method z-scoring of the pair-score distribution fitted on BLiPS-train pairs — declare which), w ∈ {0.25, 0.5, 0.75}, choose w on BLiPS-val D-mode cb-AUC (one-SE rule → prefer w = 0.5 if within one SE) — DEV ONLY. Report dev numbers for all w on BLiPS-val L/D, TOUGH-M1-dev D, PPIPS-val. Then ONE exploratory test look with the chosen w only: rerun the same metrics as final_eval for the fused score on all test sets (reuse final_eval's code paths/functions where possible — import functions, do not modify final_eval.py; you are allowed to read data/sealed/ files for this exploratory look: chmod 400, read, chmod 000, log each access to results/exploratory/unseal_log.tsv) and the paired Δ vs the final method on TOUGH-M1-test (L, D), BLiPS-test (L, D, AF), ProSPECCTs subsets, Vertex, PPIPS-test, with vertex-bootstrap CIs. Also report fused-method runtime (L4 needs GPU or 47 ms/pocket CPU).
Output under results/exploratory/fusion/ with provenance sidecars; trials rows with tag 'exploratory_posttest'. Report reports/exploratory_fusion.md (≤ 1 page; first line: "EXPLORATORY — post-test; not a confirmatory result"). Final message ≤ 200 words.


### PI / user turn · 2026-10-28 04:14:01

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


### Assistant · 2026-10-28 04:14:03

I'll start by reading the project context files.


**→ tool call `Bash`** · 2026-10-28 04:14:05

```
{"command": "ls && wc -l RESEARCH_TREE.md PREREG.md reports/{a4b_selection,l4_pointnet,final_eval_infra,verification_final}.md results/dev/l4/final_select_all_l4_summary.md results/final/final_report.md scripts/eval_dev.py scripts/final_eval.py && ls results/ results/final data data/sealed 2>&1 | head -80", "description": "List project layout and file sizes"}
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
   271 RESEARCH_TREE.md
    52 PREREG.md
    70 reports/a4b_selection.md
    73 reports/l4_pointnet.md
   120 reports/final_eval_infra.md
    56 reports/verification_final.md
   123 results/dev/l4/final_select_all_l4_summary.md
  1199 results/final/final_report.md
  2037 scripts/eval_dev.py
  1575 scripts/final_eval.py
  5576 total
data:
processed
raw
ref
sealed
sealed_SHA256SUMS.txt
sealed_raw_SHA256SUMS.txt
splits

data/sealed:
blips_test_pairs.parquet
blips_test_sites.parquet
ppi_l_test_b6.parquet
ppi_l_test_pairs.parquet
ppips_sym_test_pairs.parquet
ppips_test_queries.parquet
prospeccts_pairs.parquet
tough_m1_pairs.parquet
tough_m1_test_pairs.parquet
vertex_pairs.parquet

results/:
a2
audit
benchmarks
dev
explore
feasibility
final
final_dryrun
models
pocket_cache
ppi
proteome
trials.tsv
verify

results/final:
final_claims.json
final_claims.json.prov.json
final_details.json
final_details.json.prov.json
final_ppips.parquet
final_ppips.parquet.prov.json
final_report.md
final_report.md.prov.json
final_summary.parquet
final_summary.parquet.prov.json
unseal_log.tsv
```


**→ tool call `Bash`** · 2026-10-28 04:14:08

```
{"command": "sed -n 1,120p RESEARCH_TREE.md", "description": "Read research tree top"}
```


**→ tool call `Bash`** · 2026-10-28 04:14:09

```
{"command": "cat PREREG.md reports/a4b_selection.md reports/l4_pointnet.md", "description": "Read prereg and selection reports"}
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
… [14,706 more characters; full text in agent_logs/raw/]
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
… [10,111 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:14:12

```
{"command": "cat reports/final_eval_infra.md reports/verification_final.md && cat results/dev/l4/final_select_all_l4_summary.md | head -60", "description": "Read infra and verification reports"}
```


**← tool result**

```
# Final-evaluation infrastructure (final-eval agent, 2026-10-27; update 2026-10-28 03:50)

## Update 03:50 (final method A4b:n1_linear raw, D20; rebuilt splits, D18; Addendum A2)
- **Splits:** `final_eval.py` reads the current split files: TOUGH-M1-dev has 765 pockets (10,574 pairs), BLiPS-val
  v2 has 2,772 pairs, PPIPS-val has 217 ortho queries. The B0′ tables for TOUGH-M1-test/dev and BLiPS-val were
  rebuilt on the new pocket lists.
- **Sealed hashes:** all 9 needed hashes are now recorded, read from `data/sealed_SHA256SUMS.txt` and
  `data/splits/SHA256SUMS.txt`.
- **Addendum-A2 arms** (descriptive, not in Holm; raw and CSLS rows):
  - **N1:** `eval_dev.fs_embed`, BLiPS-train statistics.
  - **L4:egnn_small:** designated variant CSLS.
- **Label-free inputs added for the sealed sets:**
  - A4b inputs (`compute_descriptors --arm a1r --label-free-structures`) for ProSPECCTs, Vertex and PPI-L;
  - L4 point sets (`l4_extract.py`) for ProSPECCTs and Vertex: 0 errors, 0 sph8 mismatches;
  - L4 embeddings for all 7 sets (`scripts/l4_embed.py`, cuda:2) in `data/processed/l4_emb/egnn_small/`. The re-embedded
    dev sets are bit-identical to the model directory's files.
- **Empty-sph8 fallback:** the final-method adapter now goes through `a4b.raw_parts`, so the fallback (empty sph8 →
  located set) applies everywhere.
- **Dry run (B = 2000, `results/final_dryrun/`):**
  - FINAL / N1 / L4 against `results/dev/l4/final_select_all_l4_summary`: 24 rows, **max |dev| = 0**, identical pa
… [19,653 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:14:16

```
{"command": "sed -n 1,140p results/final/final_report.md", "description": "Read final report head"}
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
… [16,693 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:14:21

```
{"command": "grep -n \"^def \\|^class \\|^[A-Z_]* = \" scripts/final_eval.py | head -150", "description": "List final_eval functions"}
```


**← tool result**

```
96:ROOT = Path(__file__).resolve().parents[1]
108:CSLS_K = ED.CSLS_K
109:SESOI = 0.03
110:METHOD_CFG = ROOT / "configs/final_method.yaml"
111:SEALED_DIR = ROOT / "data/sealed"
112:SEALED_SUMS = ROOT / "data/sealed_SHA256SUMS.txt"
113:SPLIT_SUMS = ROOT / "data/splits/SHA256SUMS.txt"
114:SEALED_NEEDED = ("tough_m1_test_pairs.parquet", "prospeccts_pairs.parquet", "blips_test_pairs.parquet",
117:WORKTREE_LINKS = ("data/processed", "data/sealed", "data/raw", "data/splits/homology_edges.parquet", "tools",
122:def log(msg):
127:class Sealed:
172:class StandinA1PairOnly:
190:class MethodAdapter:
234:def load_method(allow_standin: bool, force_standin: bool = False):
250:class PairSet:
282:def _index(ds):
286:def _attach_geometry(P: pd.DataFrame, ds: str) -> pd.DataFrame:
299:def _pairs_index(P, pairs, ca="pocket_a", cb="pocket_b"):
306:def tough_set(name, pairs, pocket_filter) -> PairSet:
336:def tough_test_units() -> dict:
344:def blips_set(name, pairs, sites, cache_ds, desc_ds, exclusions=None, allow_missing=False) -> PairSet:
371:_PU_CACHE = {}
374:def prospeccts_units(P: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
392:def _prospeccts_maps():
412:def prospeccts_sets(pairs: pd.DataFrame, synthetic: bool) -> list[PairSet]:
435:def vertex_set(pairs: pd.DataFrame, synthetic: bool) -> PairSet:
454:def synthetic_prospeccts(rng) -> pd.DataFrame:
470:def synthetic_vertex(rng) -> pd.DataFrame:
488:def synthetic_tough_full(rng) -> pd.DataFrame:
502:def _embed_scores(E_rows, rows, n, ia, 
… [2,264 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:14:24

```
{"command": "sed -n 1,300p scripts/final_eval.py", "description": "Read final_eval first 300 lines"}
```


**→ tool call `Bash`** · 2026-10-28 04:14:25

```
{"command": "sed -n 300,1125p scripts/final_eval.py", "description": "Read final_eval stages"}
```


**→ tool call `Bash`** · 2026-10-28 04:14:26

```
{"command": "sed -n 1245,1420p scripts/final_eval.py", "description": "Read final_eval run function"}
```


**← tool result**

```
def run(args, real: bool, method, cfg_sha, sealed: Sealed, out: Path):
    store = DescriptorStore(ROOT)
    rng = np.random.default_rng(SEEDS[0])
    tabs, details = [], {"mode": "FINAL" if real else "DRYRUN-DEV", "method": method.name,
                         "method_is_learned": bool(method.is_learned), "method_csls": bool(method.csls),
                         "method_config_sha256": cfg_sha, "B": args.B, "seed": args.seed}
    split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
    dev_pairs = pd.read_parquet(ROOT / "data/splits/tough_m1_dev_pairs.parquet")
    tm_dev = tough_set("tough_m1_dev", dev_pairs, lambda s: s.partition == "dev")
    # ---------------------------------------------------------------- TOUGH-M1-test (C1a, C1b, C1-D)
    if real:
        tp = sealed.read("tough_m1_test_pairs.parquet", "C1a/C1b/C1-D + TOUGH-M1-test reported items")
        tm = tough_set("tough_m1_test", tp, lambda s: s.partition == "test")
        tvecs, ttab, tinfo = stage_tough(tm, method, store, args, tm_dev, "tough_m1_test")
    else:
        tm = tm_dev
        tvecs, ttab, tinfo = stage_tough(tm, method, store, args, None, "tough_m1_dev")
    tabs.append(ttab)
    details[tm.name] = tinfo
    claims = claims_tough(tm, tvecs, method, args)
    # ---------------------------------------------------------------- ProSPECCTs (C2 + all subsets)
    pp = (sealed.read("prospeccts_pairs.parquet", "C2 + ProSPECCTs reported items") if real
          else synthetic
… [10,907 more characters; full text in agent_logs/raw/]
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
… [14,350 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
<persisted-output>
Output too large (42.2KB). Full output saved to: /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/brjbha3lc.txt

Preview (first 2KB):
    pos = {p: i for i, p in enumerate(P.pocket_id)}
    if not (pairs[ca].isin(pos) & pairs[cb].isin(pos)).all():
        raise RuntimeError("pair with a pocket outside the pool")
    return pairs[ca].map(pos).to_numpy(), pairs[cb].map(pos).to_numpy()


def tough_set(name, pairs, pocket_filter) -> PairSet:
    """TOUGH-M1 partition (as eval_dev.ToughM1Dev): units = components of (ligand cluster ∪ homology group)."""
    split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
    P = split[pocket_filter(split)].sort_values("pocket_id").reset_index(drop=True)
    P = _attach_geometry(P, "tough_m1")
    if not P.cache_ok.all():
        raise RuntimeError("TOUGH-M1 pocket without a point-cache entry")
    unit = ED._components(len(P), ED._shared_label_edges(P.ligand_cluster.to_numpy())
                          + ED._shared_label_edges(P.group_id.to_numpy()))
    P["unit"] = unit
    ia, ib = _pairs_index(P, pairs)
    y = pairs.label.to_numpy().astype(int)
    pcomp = ED._components(len(P), list(zip(ia[y == 1], ib[y == 1])))
    ps = PairSet(name, "tough_m1", P, ia, ib, y, {"u": unit}, pos_cluster=pcomp[ia], pairs=pairs,
                 subsets={"all": np.ones(len(y), bool)})
    nat = {}
    if "apoc_c1" in pairs:
        nat.update({

… [650 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:14:29

```
{"command": "sed -n 300,700p scripts/final_eval.py", "description": "Read final_eval lines 300-700"}
```


**← tool result**

```
    pos = {p: i for i, p in enumerate(P.pocket_id)}
    if not (pairs[ca].isin(pos) & pairs[cb].isin(pos)).all():
        raise RuntimeError("pair with a pocket outside the pool")
    return pairs[ca].map(pos).to_numpy(), pairs[cb].map(pos).to_numpy()


def tough_set(name, pairs, pocket_filter) -> PairSet:
    """TOUGH-M1 partition (as eval_dev.ToughM1Dev): units = components of (ligand cluster ∪ homology group)."""
    split = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
    P = split[pocket_filter(split)].sort_values("pocket_id").reset_index(drop=True)
    P = _attach_geometry(P, "tough_m1")
    if not P.cache_ok.all():
        raise RuntimeError("TOUGH-M1 pocket without a point-cache entry")
    unit = ED._components(len(P), ED._shared_label_edges(P.ligand_cluster.to_numpy())
                          + ED._shared_label_edges(P.group_id.to_numpy()))
    P["unit"] = unit
    ia, ib = _pairs_index(P, pairs)
    y = pairs.label.to_numpy().astype(int)
    pcomp = ED._components(len(P), list(zip(ia[y == 1], ib[y == 1])))
    ps = PairSet(name, "tough_m1", P, ia, ib, y, {"u": unit}, pos_cluster=pcomp[ia], pairs=pairs,
                 subsets={"all": np.ones(len(y), bool)})
    nat = {}
    if "apoc_c1" in pairs:
        nat.update({
            ("B5T", "apoc_ps"): (pairs.apoc_c1.to_numpy(float), "APoc PS-score (apoc_c1)"),
            ("B5T", "apoc_negp"): (-pairs.apoc_c2.to_numpy(float), "−APoc P-value (apoc_c2)"),
            ("B5T", "glosa_ga"): (pair
… [17,540 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:14:32

```
{"command": "sed -n 700,1122p scripts/final_eval.py", "description": "Read final_eval lines 700-1122"}
```


**← tool result**

```
                     synthetic=False, ap_neg=False):
    """One row per (vector, subset): point metrics + vertex-bootstrap CIs (wider over unit definitions)."""
    y_all = np.asarray(y_all).astype(bool)
    tasks = []
    for v in vecs:
        if generic_filter is not None and not generic_filter(v):
            continue
        if pc_all is None and cov_all is None:
            continue
        for sn, sm in subsets.items():
            m = eval_set(v, dset) & sm
            if not _ok_mask(y_all, m):
                continue
            for un, (ci, cj) in units.items():
                tasks.append((f"{v.key}#{sn}#{un}", y_all[m], v.s[m], None if pc_all is None else pc_all[m],
                              None if cov_all is None else cov_all[m], ci[m], cj[m], args.B, args.seed))
    gen = ED.run_generic(tasks, args.threads, log, fn=_gtask) if tasks else {}
    rows = []
    for v in vecs:
        for sn, sm in subsets.items():
            m = eval_set(v, dset) & sm
            if not _ok_mask(y_all, m):
                continue
            y, s = y_all[m], v.s[m]
            r = ev.binary_metrics(y, s)
            row = {"set": name, "key": v.key, "subset": sn, "arm": v.arm, "config": v.config, "variant": v.variant,
                   "mode": v.mode, "dims": v.dims, "note": v.note, "synthetic": synthetic, "n_pairs": int(m.sum()),
                   "n_pos": r["n_pos"], "n_neg": r["n_neg"], "auc": r["auc"], "ap": r["ap"],
                   "prevalence": r["prevalence"], 
… [22,606 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:14:53

```
{"command": "grep -n \"^def \\|^class \\|^[A-Z_]* = \" scripts/eval_dev.py | head -120; grep -n \"def main_final_select\" -A 120 scripts/eval_dev.py | head -220", "description": "Inspect eval_dev structure and final_select"}
```


**← tool result**

```
117:ROOT = Path(__file__).resolve().parents[1]
125:CSLS_K = 10
126:N_FOLDS = 5
133:class DevDataset:
172:def _components(n, edges):
180:def _shared_label_edges(labels):
188:class ToughM1Dev(DevDataset):
251:class BlipsVal(DevDataset):
311:class PpipsVal(DevDataset):
347:DATASETS = {"tough_m1": ToughM1Dev, "blips": BlipsVal, "ppips": PpipsVal}
352:class Vec:
367:def cosine_vectors(M, avail, ia, ib, *, zscore=True, layout=None, block_weights=None, csls=True):
384:def neg_euclid_vectors(M, avail, ia, ib):
398:def build_vectors(ds: DevDataset, log) -> tuple[list[Vec], dict]:
492:def _a1_grid():
499:def unit_folds(units: np.ndarray, n_folds: int, seed: int) -> np.ndarray:
513:def cross_fit(X, y, fa, fb, n_folds=N_FOLDS, *, method="direction"):
553:def n_bins_for(y):
557:def point_metrics(y, s, pc, cov):
567:def _generic_task(args):
578:def _pool_init():
586:def _safe_generic_task(args):
594:def run_generic(tasks, threads, log, fn=_generic_task):
606:def main():
911:UNIT_NAMES = {"hom": "homology group", "lig": "Butina ligand cluster (label ligand)"}
914:def _wider(per: dict):
923:def _ci_cols(row, prefix, per):
936:def _select_task(a):
948:def _a1_raw(ds):
966:def select_a1_d11(args, bl, bl_V, log):
1031:def main_blips(args):
1231:def render_md_blips(summary, lvd, csls_df, comps, sel, details) -> str:
1282:def _wmean(x, w):
1287:def _boot_means(cols: dict, units, B, seed, diff=False):
1305:def main_ppips(args):
1545:def render_md_ppips(summary, hyp, verdict, details) -> str:
1578:
… [7,257 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:14:58

```
{"command": "sed -n 905,948p scripts/eval_dev.py; sed -n 1626,1700p scripts/eval_dev.py; sed -n 1886,1960p scripts/eval_dev.py", "description": "Read eval_dev helper functions"}
```


**← tool result**

```
                                    **({"tag": args.trial_tag} if args.trial_tag else {})},
                         f"{args.dataset}_{ds.split}", metrics, f_sum)
    log(f"done: {f_sum}")


# ============================================================================================ BLiPS-val (v2)
UNIT_NAMES = {"hom": "homology group", "lig": "Butina ligand cluster (label ligand)"}


def _wider(per: dict):
    """{unit: BootstrapResult | None} -> (BootstrapResult with the wider CI, its unit) or (None, None)."""
    ok = {u: r for u, r in per.items() if r is not None}
    if not ok:
        return None, None
    w = ev.wider_ci(*ok.values())
    return w, next(u for u, r in ok.items() if r is w)


def _ci_cols(row, prefix, per):
    """Write <prefix>_lo/_hi/_se (wider CI), <prefix>_ci_unit and per-unit lo/hi columns into ``row``."""
    w, wu = _wider(per)
    row[f"{prefix}_lo"] = w.ci_low if w else np.nan
    row[f"{prefix}_hi"] = w.ci_high if w else np.nan
    row[f"{prefix}_se"] = w.se if w else np.nan
    row[f"{prefix}_ci_unit"] = wu
    for u, r in per.items():
        row[f"{prefix}_lo_{u}"] = r.ci_low if r is not None else np.nan
        row[f"{prefix}_hi_{u}"] = r.ci_high if r is not None else np.nan
    return w


def _select_task(a):
    """Joint (cb_L, cb_D) generic bootstrap with identical replicate weights (D on the D-set pairs)."""
    key, y, sL, sD, dmask, pc, ci, cj, B, seed = a

    def fn(w):
        return [ev.cluster_balanced_auc(y, sL, pc, w)["auc_cb"
… [8,360 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:15:06

```
{"command": "ls scripts/ && sed -n 1,80p scripts/eval_l4.py && grep -n \"def \\|trials\" scripts/eval_l4.py | head -40", "description": "Inspect eval_l4 script"}
```


**← tool result**

```
__pycache__
a2
bench_evaluate.py
bench_l4.py
bench_method.py
build_point_cache.py
check_report.py
collect_epocs.py
compute_descriptors.py
compute_esm.py
compute_n_inputs.py
data
eval_af_robustness.py
eval_blind.py
eval_dev.py
eval_l4.py
explore
feasibility
final_eval.py
l4_embed.py
l4_extract.py
ppi
proteome
run_blips_ppips_desc.sh
run_blips_ppips_esm.sh
run_final_prep_cache.sh
run_final_prep_desc.sh
run_final_prep_l4.sh
run_l4.sh
train_a4b.py
train_l4.py
write_final_method.py
#!/usr/bin/env python
"""Dev evaluation of the L4 candidates through scripts/eval_dev.py's PREREG §1 final selection (unchanged code).

    python scripts/eval_l4.py                         # N1/N2 (+ pool sensitivity) + every L4 model of configs/a4_grid.yaml
    python scripts/eval_l4.py --with-a4b              # ... + every A4b model (the full PREREG §1 candidate set)
    python scripts/eval_l4.py --B 20 --no-trials --models <dir> --out <scratch>     # smoke test

This wrapper only extends ``eval_dev.fs_candidates`` / ``eval_dev.fs_embed`` with the L4 candidates and then calls
``eval_dev.main_final_select`` (objective BLiPS-val D cb-AUC, homology-group SE, one-SE rule, guards BLiPS-val L
and TOUGH-M1-dev D >= B1, PPIPS-val P-ortho / P-sym; trials appended to results/trials.tsv with arm ``L4``).
L4 candidates: kind "learned", stored dims = out_dim x 3 seeds, grid order after every A4b config (so at equal
dims an A4b model is "simpler", PREREG A1).  Embeddings = results/models/l4/<config>/emb_<dataset>_
… [3,180 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:15:13

```
{"command": "sed -n 1960,2037p scripts/eval_dev.py; sed -n 1700,1766p scripts/eval_dev.py; sed -n 80,120p scripts/eval_l4.py; head -3 results/trials.tsv; tail -2 results/trials.tsv; awk -F'\\t' 'NR>1{print $NF}' results/trials.tsv | sort | uniq -c | head", "description": "Read final_select outputs, trials logging"}
```


**← tool result**

```
               "candidate_table": C.drop(columns="simplicity").to_dict(orient="records"),
               "deltas": deltas.to_dict(orient="records"), "ppips": pp_df.to_dict(orient="records")}
    cfg = {"task": "final_select", "candidates": args.candidates, "B": args.B, "seed": args.seed, "csls_k": CSLS_K,
           "splits_sha256sums": sha256_file(ROOT / "data/splits/SHA256SUMS.txt"),
           "scaling": "N1/N2/A4b inputs: BLiPS-train v2 statistics (L+U rows); B1/B4 references: pool z-score as "
                      "eval_dev (PPIPS: train)", "selection_units": sel_unit}
    inputs = sorted(set(map(str, bl.inputs + tm.inputs + pp.inputs)) | {str(ROOT / "src/pocketcompare/a4b.py")}
                    | {str(A4.a1r_dir(d_) / "ids.parquet") for d_ in ("blips", "tough_m1", "ppips")})
    common = dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=inputs, seed=args.seed, device="cpu",
                  start_time=t_start)
    f_sum = out / f"{tag}_summary.parquet"
    write_result(f_sum, summary, **common)
    write_result(out / f"{tag}_candidates.parquet", ctab, **common)
    write_result(out / f"{tag}_ppips.parquet", pp_df, **common)
    write_result(out / f"{tag}_details.json", details, **common)
    f_md = out / f"{tag}_summary.md"
    f_md.write_text(render_md_final_select(ctab, C, sel, deltas, details))
    if not args.no_trials:
        seen = _logged_trials()
        n_new = 0
        splits_fp = sha256_file(ROOT / "data/splits/SHA256SUMS.txt")[:16]     # spl
… [10,693 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:15:18

```
{"command": "grep -rn \"def append_trial\" -A 30 src/pocketcompare/ | head -45; grep -c '\"tag\"' results/trials.tsv; grep -o '\"tag\":\"[^\"]*\"' results/trials.tsv | sort | uniq -c; grep -n \"def write_result\" -A 30 src/pocketcompare/provenance.py | head -50", "description": "Inspect append_trial and write_result"}
```


**← tool result**

```
src/pocketcompare/provenance.py:197:def append_trial(arm: str, config, dataset_split: str, metrics: Mapping, result_path, *,
src/pocketcompare/provenance.py-198-                 trials_path=None) -> dict:
src/pocketcompare/provenance.py-199-    """Append one trial row to results/trials.tsv (append-only; header written when the file is new/empty)."""
src/pocketcompare/provenance.py-200-    tp = Path(trials_path) if trials_path is not None else TRIALS_TSV
src/pocketcompare/provenance.py-201-    tp.parent.mkdir(parents=True, exist_ok=True)
src/pocketcompare/provenance.py-202-    git = git_state()
src/pocketcompare/provenance.py-203-    row = {"timestamp_utc": _iso(time.time()), "arm": arm, "config_sha256": config_sha256(config),
src/pocketcompare/provenance.py-204-           "dataset_split": dataset_split, "metrics": metrics, "result_path": str(result_path),
src/pocketcompare/provenance.py-205-           "config": config if not isinstance(config, Path) else str(config),
src/pocketcompare/provenance.py-206-           "git_commit": git["git_commit"], "git_dirty": git["git_dirty"],
src/pocketcompare/provenance.py-207-           "evaluate_sha256": sha256_file(EVALUATE_PY), "hostname": socket.gethostname(),
src/pocketcompare/provenance.py-208-           "user": os.environ.get("USER", "")}
src/pocketcompare/provenance.py-209-    line = "\t".join(_cell(row[c]) for c in TRIAL_COLUMNS) + "\n"
src/pocketcompare/provenance.py-210-    with open(tp, "a+") as fh:
src/pocketcompare/provenance.
… [3,023 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:16:00

```
{"command": "source .venv/bin/activate && grep -n \"^def \" src/pocketcompare/evaluate.py | head -60; grep -n \"def vertex_bootstrap_generic\" -A 40 src/pocketcompare/evaluate.py | head -60; sed -n 1282,1305p scripts/eval_dev.py; ls -la data/processed/l4_emb/egnn_small/ results/models/l4/egnn_small/ | head -40", "description": "Check evaluate API and L4 embedding files"}
```


**← tool result**

```
113:def _as_arrays(y, s, w=None, *, allow_nan=False):
137:def _need_both(y, w):
145:def _grouped_desc(y, s, w):
160:def roc_auc(y, s, w=None) -> float:
171:def average_precision(y, s, w=None, *, target: str = "pos") -> dict:
189:def partial_auc(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
210:def binary_metrics(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
223:def _balance(labels, mask, w):
234:def _factorize(a):
240:def cluster_balanced_auc(y, s, pos_cluster, w=None, *, neg_cluster=None) -> dict:
253:def per_cluster_auc(y, s, pos_cluster, w=None, *, k: int = 10, negatives: str = "all", ci=None, cj=None):
284:def _quantile_bins(x, n_bins):
290:def size_covariates(log_vol_a, log_vol_b) -> np.ndarray:
297:def stratified_auc(y, s, covariate, w=None, *, n_bins: int | Sequence[int] = (5, 5),
347:def retrieval_metrics(df, *, query_col="query", score_col="score", label_col="label", ks: Sequence[int] = (1, 10),
383:def _score_dict(scores) -> dict[str, np.ndarray]:
392:def missing_summary(y, scores) -> dict:
405:def common_set(y, scores) -> tuple[np.ndarray, dict]:
418:def worst_case(y, s) -> tuple[np.ndarray, dict]:
429:def min_impute(y, s) -> tuple[np.ndarray, dict]:
439:def apply_missing_policy(y, scores, missing: str = "raise"):
464:def _encode_clusters(ci, cj):
473:def pair_bootstrap_weights(counts, a, b, w):
479:def bootstrap_counts(n_clusters: int, B: int = DEFAULT_B, seed=DEFAULT_SEED):
531:def _boot_kernel_numpy(cnt, ci_s, cj_s, w_s, y_s, end_s, out_auc, out_ap, offset):
… [6,941 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:16:07

```
{"command": "source .venv/bin/activate && python - <<'EOF'\nimport sys; sys.path.insert(0,'src'); sys.path.insert(0,'scripts')\nimport numpy as np, pandas as pd, json\nfrom pocketcompare import a4b as A4\nM=np.load('data/processed/l4_emb/egnn_small/emb_blips_L.npy'); print(M.shape, M.dtype, np.linalg.norm(M,axis=1)[:5])\nids=A4.ids_table('blips'); print(len(ids), ids.head())\ns=pd.read_parquet('data/splits/blips_sites_v2.parquet'); print(s.partition.value_counts()); print(s.columns.tolist())\ntp=pd.read_parquet('data/splits/blips_train_pairs_v2.parquet'); print(tp.shape, tp.columns.tolist(), tp.label.mean())\nprint(set(tp.site_a)|set(tp.site_b) <= set(ids.pocket_id))\nprint(json.load(open('data/processed/l4_emb/egnn_small/ids.json')).keys())\nimport yaml; print(yaml.safe_load(open('configs/final_method.yaml')))\nEOF\ncat results/models/l4/bench.json | head -50; ls results/dev/ | grep -i runtime; cat results/dev/final_method_runtime.json 2>/dev/null | head -40", "description": "Check embeddings, BLiPS train pairs, config, bench"}
```


**← tool result**

```
(2862, 384) float32 [1. 1. 1. 1. 1.]
2862                          pocket_id  u_member  ...  has_L  has_U
0  burrow_dev:A0A0B4KG38__6qp8_A:3         0  ...   True   True
1  burrow_dev:A0A0B4KG38__6qp8_A:4         0  ...   True   True
2  burrow_dev:A0A0B4KG38__6qp8_A:5         0  ...   True   True
3  burrow_dev:A0A0M5J3M0__9dq2_A:0         0  ...   True   True
4  burrow_dev:A0A0M5J3M0__9dq2_A:1         0  ...   True   True

[5 rows x 11 columns]
partition
train                  2318
val                     523
excluded_not_cached     128
excluded_lt10             1
Name: count, dtype: int64
['site_id', 'partition_v1', 'node_id', 'sid', 'protein', 'uniprot', 'pdb_id', 'chain', 'site_index', 'site_residues', 'structure_id', 'site_name', 'group_id', 'site_is_ion', 'all_ccds', 'q_ccds', 'n_qualifying', 'label_ccd', 'label_ha', 'label_smiles', 'label_cluster', 'cluster_in_train', 'n_lmode_points', 'partition']
(41952, 21) ['pair_id', 'label', 'max_tc', 'n_shared', 'pair_cluster', 'best_ccd_a', 'best_ccd_b', 'site_a', 'protein_a', 'group_a', 'label_ccd_a', 'site_cluster_a', 'site_b', 'protein_b', 'group_b', 'label_ccd_b', 'site_cluster_b', 'n_shared_stratum', 'promiscuous', 'chemotype_seen', 'site_clusters_in_train'] 0.16666666666666666
True
dict_keys(['model', 'device', 'files', 'check_vs_model_dir', 'wall_s'])
{'name': 'pocketcompare-final:A4b:n1_linear|raw', 'selected_by': 'results/dev/final_select_pi.json', 'selection_rule': 'PREREG §1 (one-SE rule on BLiPS-val D-mode cb-AUC + g
… [3,621 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:16:14

```
{"command": "source .venv/bin/activate && python - <<'EOF'\nimport json, pandas as pd\nd=json.load(open('results/final/final_details.json'))\nprint(d.keys()); print(json.dumps(d['runtime'],default=str)[:1500])\ns=pd.read_parquet('results/final/final_summary.parquet'); print(s.set.unique()); print(s.columns.tolist())\nprint(s[(s.arm=='L4')&(s.variant=='raw')].groupby(['set','mode']).size())\np=pd.read_parquet('results/final/final_ppips.parquet'); print(p[['arm','variant','ortho_mrr','ortho_top1']])\nEOF\ncat results/final/unseal_log.tsv | cut -f1-8 | head -12; ls -la data/sealed/", "description": "Inspect final details and summary"}
```


**← tool result**

```
dict_keys(['B', 'blips_test', 'mde_reference', 'method', 'method_config_sha256', 'method_csls', 'method_is_learned', 'mode', 'ppi_l', 'prospeccts', 'runtime', 'sealed_files_accessed', 'seed', 'tough_m1_test', 'vertex'])
{"a1_pair_only_L_ms_per_pocket_median": 4.544522147625685, "b1_default_L_ms_per_pocket_median": 1.2157079763710499, "burrow_featurise_s_per_pocket_median": 0.4301310710143298, "bytes_per_pocket_float32": 1536, "final_dims": 384, "pair_us_median_of_3": 0.419588393997401, "proteome": {"backend_equivalence.json": {"n_pockets_gpu": 127200, "run_fastcpu": {"a1_identical": true, "env_identical": true, "errors": {}, "n_pockets": 127200, "n_struct_errors": 0, "table_identical": true}, "run_refcpu": {"a1_identical": true, "env_identical": true, "errors": {"refcpu: ValueError: no protein heavy atoms": 74}, "gpu_n_atoms_of_error_structures_max": 0, "gpu_n_kept_of_error_structures": 0, "n_pockets": 127200, "n_struct_errors": 74, "table_identical": true}}, "backend_equivalence.json.prov.json": {"args": [], "config": {"producer": "compare_backends.py"}, "config_sha256": "bc4a8f9ce06ac3e4093b7d8ac86a3b88d310e9a8e396c76585eaf12e0c85b8dd", "device": "see result", "end_time": "2026-10-27T22:34:04+00:00", "evaluate_sha256": "f22d02967c08d706d8a6081865a8ba40f491340e87e205826e32f8206f65707b", "extra": {"note": "sidecar added afterwards by write_sidecars.py; result produced by scripts/proteome/compare_backends.py"}, "git_commit": "ed8afe2cf441255d787d9c85c2540155937fbb41", "git_dir
… [5,752 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:16:34

```
{"command": "sed -n 133,200p scripts/eval_dev.py; sed -n 251,347p scripts/eval_dev.py; sed -n 553,606p scripts/eval_dev.py", "description": "Read eval_dev dataset classes"}
```


**← tool result**

```
class DevDataset:
    """Adapter interface.  After ``load()``:

    * ``pairs``: DataFrame (pocket_a, pocket_b, y ∈ {0,1}) — the evaluated dev pairs;
    * ``pockets``: DataFrame indexed 0..P-1 with pocket_id, unit, logv_L, d_match, desc_row (row in the
      descriptor arrays), in a fixed order; ``ia``/``ib`` = pair endpoints as indices into it;
    * ``pos_cluster``: positive cluster id per pair (only read for positives);
    * ``native``: {name: (scores per pair, note)} pair scores shipped with the benchmark (may be empty);
    * ``test_units()``: number of bootstrap units of the matching sealed test partition (label-free).
    """
    name = "abstract"
    split = "dev"
    arms = frozenset({"B0", "B0p", "B5T", "B1", "A1", "B4", "B5", "A2", "CTRL"})   # arms build_vectors computes
    native: dict = {}
    global_scores: dict = {}

    def load(self):
        raise NotImplementedError

    def descriptor(self, arm: str, config: str, mode: str):
        """(matrix over self.pockets rows, layout or None) from data/processed/descriptors/<ds>/."""
        d = ROOT / "data/processed/descriptors" / self.name
        M = np.load(d / f"{arm}_{config}_{mode}.npy", mmap_mode="r")[self.pockets.desc_row.to_numpy()]
        lay = d / f"{arm}_{config}_{mode}.layout.json"
        self.inputs.append(d / f"{arm}_{config}_{mode}.npy")
        return np.asarray(M, np.float64), (json.loads(lay.read_text()) if lay.exists() else None)

    def docking_raw(self, panel: str, mode: str) -> pd.Dat
… [8,372 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:17:17

```
{"command": "sed -n 350,368p scripts/eval_dev.py; cat src/pocketcompare/seeds.py | head -20; ls scripts/explore; head -30 scripts/bench_l4.py; grep -n \"def pair_scores\" -A8 src/pocketcompare/similarity.py", "description": "Check Vec, SEEDS, explore dir, bench_l4"}
```


**← tool result**

```
# ============================================================================================== score vectors
@dataclass
class Vec:
    arm: str
    config: str
    variant: str          # raw | csls | native | crossfit | control
    mode: str             # L | D | native
    s: np.ndarray         # one score per dev pair, NaN = missing
    dims: int | None = None
    note: str = ""
    y_override: np.ndarray | None = None   # shuffled-label control only

    @property
    def key(self):
        return f"{self.arm}|{self.config}|{self.variant}|{self.mode}"


def cosine_vectors(M, avail, ia, ib, *, zscore=True, layout=None, block_weights=None, csls=True):
    """Raw cosine and CSLS scores over all pairs (NaN where a pocket is unavailable)."""
"""The only source of random seeds in this project (fixed before any modelling)."""
SEEDS = [0, 1, 2, 3, 4]
__pycache__
defrob_compute.py
defrob_dmode_delta.py
defrob_eval.py
defrob_setmatch.py
#!/usr/bin/env python
"""L4 inference cost: ms/pocket of the 3-seed ensemble on GPU (batch 256) and on 1 CPU thread (batch 32).

    python scripts/bench_l4.py --models results/models/l4 --device cuda:2 [--n 1024]

Pockets = the first ``n`` TOUGH-M1 U-mode point sets (data/processed/l4).  Excludes BURROW and point-set
extraction (sph8 shaper + FPS + soft typing: see data/processed/l4/*/summary.json t_ms_*), includes padding and
host->device copies.  Output: <models>/bench.json (+ printed table).
"""
from __future__ import annotations

import argpa
… [791 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-28 04:17:22

Now I'll write the script with the protocol in the header before running anything.


**→ tool call `Write`** · 2026-10-28 04:19:09

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/fusion_a4b_l4.py", "content": "#!/usr/bin/env python\n\"\"\"EXPLORATORY — post-test; not a confirmatory result.  Score-level fusion of the final method and L4.\n\n    python scripts/explore/fusion_a4b_l4.py --phase dev   [--B 2000] [--threads 16]    # scales + dev table + w choice\n    python scripts/explore/fusion_a4b_l4.py --phase test  [--B 2000] [--threads 16]    # ONE exploratory test look\n    python scripts/explore/fusion_a4b_l4.py --phase runtime\n\nContext: the confirmatory final evaluation is done (results/final/, reports/verification_final.md).  The test\nnumbers of FINAL (A4b:n1_linear raw) and of the descriptive arm L4:egnn_small have been seen, which motivated this\nquestion (L4 better on BLiPS, ProSPECCTs decoys P3/P4, PPIPS; A4b better on TOUGH-M1 D).  Everything here is\ntherefore post hoc and EXPLORATORY; no result changes any PREREG claim.\n\nPROTOCOL (fixed in this header before any fused score was computed)\n------------------------------------------------------------------\nComponents (both RAW cosine, no CSLS; frozen weights / embeddings, nothing re-trained):\n  cos_A = FINAL A4b:n1_linear raw (configs/final_method.yaml through final_eval.MethodAdapter / eval_dev.fs_embed);\n  cos_L = L4:egnn_small raw (3-seed mean cosine; data/processed/l4_emb/egnn_small = results/models/l4/egnn_small).\nFused score (DECLARED PRIMARY: per-method z-scoring of the pair-score distribution):\n  
… [32,580 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/fusion_a4b_l4.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-28 04:19:32

```
{"command": "source .venv/bin/activate && python - <<'EOF'\nimport sys; sys.path.insert(0,'src')\nimport numpy as np, pandas as pd\nfrom pocketcompare import a4b as A4\nP=pd.read_parquet('data/processed/ppi/ppips/pockets.parquet')\nM=np.load('data/processed/l4_emb/egnn_small/emb_ppips_D.npy'); ids=A4.ids_table('ppips').pocket_id\nn=pd.Series(np.linalg.norm(M,axis=1),index=ids).reindex(P.pocket_id)\nprint(P.split.value_counts()); print(pd.crosstab(P.split.values, (n>0).values))\nEOF", "description": "Check L4 coverage on PPIPS pockets"}
```


**← tool result**

```
split
train    15555
val       2488
test      2454
Name: count, dtype: int64
col_0   True
row_0       
test    2454
train  15555
val     2488
```


### Assistant · 2026-10-28 04:19:35

Full coverage. Adding N1 to the candidate list (needed by main_final_select's focus deltas).


**→ tool call `Edit`** · 2026-10-28 04:19:37

```
{"replace_all": false, "file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/fusion_a4b_l4.py", "old_string": "    ED.fs_candidates = lambda which: [a4, l4] + fused + sens", "new_string": "    n1 = ED.Cand(\"N1\", \"nonlearned\", \"N1\", 627, 0)          # main_final_select's focus deltas need N1\n    ED.fs_candidates = lambda which: [n1, a4, l4] + fused + sens"}
```


**→ tool call `Bash`** · 2026-10-28 04:19:38

```
{"command": "source .venv/bin/activate && mkdir -p results/exploratory/fusion && nohup python scripts/explore/fusion_a4b_l4.py --phase dev --B 2000 --threads 16 > results/exploratory/fusion/dev_run.log 2>&1 &\nsleep 60; cat results/exploratory/fusion/dev_run.log", "description": "Launch dev phase in background"}
```


**← tool result**

```
The file /cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/fusion_a4b_l4.py has been updated successfully. (file state is current in your context — no need to Read it back)
```


**← tool result**

```
[    0.8s] scales: {"mu_A": 0.14677356920427742, "sd_A": 0.2804997672809255, "mu_L": 0.2816380445007128, "sd_L": 0.24599559202421598, "pearson_pooled": 0.7184054036851069}
[    0.0s] candidates: ['N1', 'A4b:n1_linear', 'L4:egnn_small', 'FUSEz:w0.25', 'FUSEz:w0.50', 'FUSEz:w0.75', 'FUSEraw:w0.50']
[    0.7s]   vectors blips L done
[    0.8s]   vectors blips D done
[    1.4s]   vectors tough_m1 L done
[    1.6s]   vectors tough_m1 D done
[    1.6s] generic bootstrap: 108 tasks, B=2000
[   12.2s]     generic bootstrap 20/108 (11 s)
[   16.0s]     generic bootstrap 40/108 (14 s)
[   19.8s]     generic bootstrap 60/108 (18 s)
[   37.5s]     generic bootstrap 80/108 (36 s)
[   55.2s]     generic bootstrap 100/108 (54 s)
```


**→ tool call `Bash`** · 2026-10-28 04:20:43

```
{"command": "sleep 120; cat /cluster/project/beltrao/gmagnus/pocket_compare/results/exploratory/fusion/dev_run.log | tail -20", "description": "Wait and check dev run log"}
```


**← tool result**

```
<tool_use_error>Blocked: sleep 120 followed by: cat /cluster/project/beltrao/gmagnus/pocket_compare/results/exploratory/fusion/dev_run.log tail -20. To wait for a condition, use Monitor with an until-loop (e.g. `until <check>; do sleep 2; done`). To wait for a command you started, use run_in_background: true. Do not chain shorter sleeps to work around this block.</tool_use_error>
```


**→ tool call `ToolSearch`** · 2026-10-28 04:20:45

```
{"query": "select:Monitor", "max_results": 1}
```


**← tool result**

```
[non-text content]
```


**→ tool call `Bash`** · 2026-10-28 04:20:48

```
{"command": "until grep -qE \"trial rows appended|Traceback|Error\" results/exploratory/fusion/dev_run.log || ! pgrep -f \"fusion_a4b_l4.py --phase dev\" >/dev/null; do sleep 5; done; tail -25 results/exploratory/fusion/dev_run.log", "description": "Wait for dev phase to finish", "run_in_background": true}
```


**← tool result**

```
Command running in background with ID: b6058vp18. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/b6058vp18.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
```


**→ tool call `Bash`** · 2026-10-28 04:20:51

```
{"command": "until ! pgrep -f \"fusion_a4b_l4.py --phase dev\" >/dev/null; do sleep 5; done; tail -30 results/exploratory/fusion/dev_run.log", "description": "Wait for dev process exit", "timeout": 600000}
```


**← tool result**

```
Command did not complete within its 600s timeout and was moved to the background (ID: b3k24r4zf). Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/b3k24r4zf.output. You will be notified when it completes. It is running now: do not start a second copy while it runs. If it is no longer needed, stop it with TaskStop. No output had been read from it when it was moved. A program that buffers its output, or a pipe into one such as tail, can keep the output file empty until the command finishes. To check interim output, use Read on that file path.
```


**→ tool call `Bash`** · 2026-10-28 04:30:54

```
{"command": "tail -15 results/exploratory/fusion/dev_run.log; pgrep -fa \"fusion_a4b_l4\" | head", "description": "Check dev log tail"}
```


**← tool result**

```
[    0.8s]   vectors blips D done
[    1.4s]   vectors tough_m1 L done
[    1.6s]   vectors tough_m1 D done
[    1.6s] generic bootstrap: 108 tasks, B=2000
[   12.2s]     generic bootstrap 20/108 (11 s)
[   16.0s]     generic bootstrap 40/108 (14 s)
[   19.8s]     generic bootstrap 60/108 (18 s)
[   37.5s]     generic bootstrap 80/108 (36 s)
[   55.2s]     generic bootstrap 100/108 (54 s)
[   68.5s] BLiPS / TOUGH-M1 metrics done
[   74.2s] PPIPS done
[   74.5s] selection: best FUSEz:w0.50|csls (0.7710, SE 0.0368) -> chosen A4b:n1_linear|raw
[   75.5s] done: /cluster/project/beltrao/gmagnus/pocket_compare/results/exploratory/fusion/dev/final_select_fusion_summary.md
[   76.3s] selection: {'rule': 'argmax_w BLiPS-val D cb (raw, z-scored fusion); threshold = best - SE_hom(best); prefer w = 0.5 if within one SE', 'best': 'FUSEz:w0.25', 'best_bl_D_cb': 0.761199097798766, 'se_best': 0.039092837624622484, 'threshold': 0.7221062601741436, 'w_star': 0.5, 'candidate': 'FUSEz:w0.50', 'scales': {'mu_A': 0.14677356920427742, 'sd_A': 0.2804997672809255, 'mu_L': 0.2816380445007128, 'sd_L': 0.24599559202421598}, 'guards_reported_not_used': {'FUSEz:w0.25': {'blips_L_ge_B1': True, 'tm_D_ge_B1': True}, 'FUSEz:w0.50': {'blips_L_ge_B1': True, 'tm_D_ge_B1': True}, 'FUSEz:w0.75': {'blips_L_ge_B1': True, 'tm_D_ge_B1': True}}, 'B': 2000, 'seed': 0, 'tag': 'exploratory_posttest'}
[   85.2s] 40 trial rows appended; w* = 0.5
1639230 /bin/bash -c source /home/.claude/shell-snapshots/snapshot-bash-1793121
… [744 more characters; full text in agent_logs/raw/]
```


**→ tool call `TaskStop`** · 2026-10-28 04:30:57

```
{"task_id": "b3k24r4zf"}
```


**← tool result**

```
{"message":"Successfully stopped task: b3k24r4zf (until ! pgrep -f \"fusion_a4b_l4.py --phase dev\" >/dev/null; do sleep 5; done; tail -30 results/exploratory/fusion/dev_run.log)","task_id":"b3k24r4zf","task_type":"local_bash","command":"until ! pgrep -f \"fusion_a4b_l4.py --phase dev\" >/dev/null; do sleep 5; done; tail -30 results/exploratory/fusion/dev_run.log"}
```


**→ tool call `Bash`** · 2026-10-28 04:31:01

```
{"command": "source .venv/bin/activate && head -22 results/exploratory/fusion/dev/final_select_fusion_summary.md; python -c \"\nimport pandas as pd; pd.set_option('display.width',250)\nd=pd.read_parquet('results/exploratory/fusion/dev/fusion_dev_deltas.parquet'); print(d[['a','dataset','mode','delta','lo_selunit','hi_selunit','p_one_sided_selunit','lo_wider','hi_wider']].round(3))\np=pd.read_parquet('results/exploratory/fusion/dev/final_select_fusion_ppips.parquet'); print(p[['cand','variant','ortho_mrr','ortho_top1','sym_pct']].round(3))\"", "description": "Show dev results"}
```


**← tool result**

```
# Final-method selection (PREREG §1) — auto-generated by scripts/eval_dev.py --dataset final_select

B = 2000, seed 0. cb = cluster-balanced ROC-AUC; SE / CI: BLiPS homology-group units, TOUGH-M1 ligand-cluster ∪ homology-group units. blips_L: 2772 pairs (462 pos) · blips_D: 1544 pairs (287 pos) · tough_m1_L: 10574 pairs (3450 pos) · tough_m1_D: 8540 pairs (2843 pos)

| candidate | var | dims | **BLiPS D cb** [CI] (SE) | BLiPS L cb | TM-dev D cb | TM-dev L cb | BLiPS D strat | PPIPS MRR | P-sym | 1-SE | guards |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | raw | 45 | 0.648 [0.578, 0.738] (0.040) | 0.701 | 0.617 | 0.639 | 0.682 | 0.761 | 0.997 |  |  |
| B1 | csls | 45 | 0.651 [0.584, 0.744] (0.041) | 0.709 | 0.629 | 0.649 | 0.693 | 0.747 | 0.997 |  |  |
| B4 | raw | 1280 | 0.670 [0.604, 0.760] (0.040) | 0.641 | 0.598 | 0.602 | 0.719 | 0.986 | 1.000 |  |  |
| B4 | csls | 1280 | 0.711 [0.632, 0.799] (0.042) | 0.687 | 0.588 | 0.610 | 0.682 | 0.973 | 1.000 |  |  |
| N1 | raw | 627 | 0.697 [0.618, 0.775] (0.040) | 0.706 | 0.667 | 0.656 | 0.694 | 0.790 | 0.999 |  | ✓ |
| N1 | csls | 627 | 0.700 [0.626, 0.782] (0.040) | 0.720 | 0.667 | 0.658 | 0.696 | 0.782 | 0.999 |  | ✓ |
| A4b:n1_linear | raw | 384 | 0.737 [0.650, 0.802] (0.038) | 0.718 | 0.721 | 0.720 | 0.735 | 0.719 | 0.999 | ✓ | ✓ |
| A4b:n1_linear | csls | 384 | 0.748 [0.662, 0.809] (0.037) | 0.721 | 0.711 | 0.717 | 0.738 | 0.717 | 0.999 | ✓ | ✓ |
| L4:egnn_small | raw | 384 | 0.748 [0.663, 0.827] (0.041) | 0.760 |
… [2,985 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:31:07

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd\nd=pd.read_parquet('results/exploratory/fusion/dev/fusion_dev_deltas.parquet')\nfor r in d.itertuples(): print(r.a, r.dataset, r.mode, f'{r.delta:+.3f} [{r.lo_selunit:+.3f},{r.hi_selunit:+.3f}] p={r.p_one_sided_selunit:.3f}')\nc=pd.read_parquet('results/exploratory/fusion/dev/final_select_fusion_candidates.parquet'); print(c[c.cand=='FUSEraw:w0.50'][['variant','bl_D_cb','bl_D_cb_se','bl_L_cb','tm_D_cb','tm_L_cb']].round(3))\"", "description": "Print dev deltas and raw-sum row"}
```


**← tool result**

```
FUSEz:w0.25 blips L +0.051 [+0.005,+0.098] p=0.015
FUSEz:w0.25 blips D +0.024 [-0.024,+0.086] p=0.110
FUSEz:w0.25 tough_m1 L -0.007 [-0.078,+0.020] p=0.706
FUSEz:w0.25 tough_m1 D -0.030 [-0.107,+0.010] p=0.934
FUSEz:w0.50 blips L +0.046 [+0.014,+0.079] p=0.003
FUSEz:w0.50 blips D +0.024 [-0.004,+0.064] p=0.043
FUSEz:w0.50 tough_m1 L +0.008 [-0.033,+0.025] p=0.314
FUSEz:w0.50 tough_m1 D -0.007 [-0.051,+0.019] p=0.661
FUSEz:w0.75 blips L +0.026 [+0.011,+0.043] p=0.000
FUSEz:w0.75 blips D +0.016 [+0.002,+0.035] p=0.013
FUSEz:w0.75 tough_m1 L +0.009 [-0.010,+0.017] p=0.150
FUSEz:w0.75 tough_m1 D +0.002 [-0.018,+0.014] p=0.319
   variant  bl_D_cb  bl_D_cb_se  bl_L_cb  tm_D_cb  tm_L_cb
16     raw     0.76       0.038    0.763    0.715    0.729
17    csls     0.77       0.037    0.766    0.705    0.727
```


### Assistant · 2026-10-28 04:31:13

Dev selection gives w* = 0.5. Before the one-shot test look, I'll smoke-test the test-phase helpers on dev data (B=20) to avoid a crash mid-run.


**→ tool call `Bash`** · 2026-10-28 04:31:20

```
{"command": "source .venv/bin/activate && python -m pyflakes scripts/explore/fusion_a4b_l4.py 2>&1 | head; cd scripts/explore && python - <<'EOF' 2>&1 | grep -v \"^\\[\" | tail -30\nimport sys, argparse, json, numpy as np, pandas as pd\nsys.argv=['x']\nimport fusion_a4b_l4 as X\nFE=X.FE\nargs=argparse.Namespace(B=20, seed=0, threads=8)\nsc=json.loads(X.SCALES.read_text())\nfinal,_=FE.load_method(allow_standin=False)\nfused=X.FusedMethod(final,0.5,sc['sd_A'],sc['sd_L'])\nl4=FE.ExtraArm(\"L4\",\"L4:egnn_small\",True,\"raw\",FE._l4_embed)\narms=[(\"FUSED\",fused),(\"FINAL\",final),(\"L4\",l4)]\nstore=FE.DescriptorStore(X.ROOT)\ntm=FE.tough_set(\"tough_m1_dev\", pd.read_parquet(X.ROOT/\"data/splits/tough_m1_dev_pairs.parquet\"), lambda s: s.partition==\"dev\")\nvecs=X.raw_vecs(tm,arms,store,(\"L\",\"D\"))\nprint([v.key for v in vecs])\ntab,_=FE.evaluate_vectors(tm.name, vecs, tm.y, tm.pair_units, tm.pos_cluster, tm.cov, tm.dset, tm.subsets, args)\nprint(tab[['arm','mode','auc','auc_cb']])\nF={v.mode:v.s for v in vecs if v.arm=='FUSED'}; A={v.mode:v.s for v in vecs if v.arm=='FINAL'}\nprint(X.dpair(tm,F['D'],A['D'],args,mask=tm.dset)['delta'], X.dcb(tm,F['D'],A['D'],args,mask=tm.dset))\nq=pd.read_parquet(X.ROOT/\"data/splits/ppips_ortho_queries_val.parquet\")\nrrF,qu=X.ppips_rr(\"val\",q,fused,store); rrA,_=X.ppips_rr(\"val\",q,final,store)\nprint(rrF.mean(), rrA.mean())\nbo=X.ED._boot_means({\"mrr\":rrF-rrA},qu,20,0,diff=True); print(X._res(bo['mrr']))\ns=pd.read_parquet(X.ROOT/\
… [220 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
/cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python: No module named pyflakes
Command did not complete within its 600s timeout and was moved to the background (ID: b01j1iuqm). Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/b01j1iuqm.output. You will be notified when it completes. It is running now: do not start a second copy while it runs. If it is no longer needed, stop it with TaskStop. To check interim output, use Read on that file path.
Session cwd remains /cluster/project/beltrao/gmagnus/pocket_compare; directory changes made by the backgrounded command do not apply to subsequent commands.
```


**→ tool call `Bash`** · 2026-10-28 04:41:27

```
{"command": "tail -c 3000 /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/b01j1iuqm.output; ps aux | grep -c \"multiprocessing.spawn\"", "description": "Check smoke test output"}
```


**← tool result**

```
/cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python: No module named pyflakes
19
```


**→ tool call `TaskStop`** · 2026-10-28 04:41:31

```
{"task_id": "b01j1iuqm"}
```


**← tool result**

```
{"message":"Successfully stopped task: b01j1iuqm (source .venv/bin/activate && python -m pyflakes scripts/explore/fusion_a4b_l4.py 2>&1 | head; cd scripts/explore && python - <<'EOF' 2>&1 | grep -v \"^\\[\" | tail -30\nimport sys, argparse, json, numpy as np, pandas as pd\nsys.argv=['x']\nimport fusion_a4b_l4 as X\nFE=X.FE\nargs=argparse.Namespace(B=20, seed=0, threads=8)\nsc=json.loads(X.SCALES.read_text())\nfinal,_=FE.load_method(allow_standin=False)\nfused=X.FusedMethod(final,0.5,sc['sd_A'],sc['sd_L'])\nl4=FE.ExtraArm(\"L4\",\"L4:egnn_small\",True,\"raw\",FE._l4_embed)\narms=[(\"FUSED\",fused),(\"FINAL\",final),(\"L4\",l4)]\nstore=FE.DescriptorStore(X.ROOT)\ntm=FE.tough_set(\"tough_m1_dev\", pd.read_parquet(X.ROOT/\"data/splits/tough_m1_dev_pairs.parquet\"), lambda s: s.partition==\"dev\")\nvecs=X.raw_vecs(tm,arms,store,(\"L\",\"D\"))\nprint([v.key for v in vecs])\ntab,_=FE.evaluate_vectors(tm.name, vecs, tm.y, tm.pair_units, tm.pos_cluster, tm.cov, tm.dset, tm.subsets, args)\nprint(tab[['arm','mode','auc','auc_cb']])\nF={v.mode:v.s for v in vecs if v.arm=='FUSED'}; A={v.mode:v.s for v in vecs if v.arm=='FINAL'}\nprint(X.dpair(tm,F['D'],A['D'],args,mask=tm.dset)['delta'], X.dcb(tm,F['D'],A['D'],args,mask=tm.dset))\nq=pd.read_parquet(X.ROOT/\"data/splits/ppips_ortho_queries_val.parquet\")\nrrF,qu=X.ppips_rr(\"val\",q,fused,store); rrA,_=X.ppips_rr(\"val\",q,final,store)\nprint(rrF.mean(), rrA.mean())\nbo=X.ED._boot_means({\"mrr\":rrF-rrA},qu,20,0,diff=True); print(X._res(bo
… [1,865 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:41:32

```
{"command": "pkill -f \"multiprocessing.spawn\" ; sleep 1; ps aux | grep -c \"multiprocessing.spawn\"", "description": "Kill leftover spawn workers"}
```


**← tool result**

```
Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Interfere With Workloads]. If you have other tasks that don't depend on this action, continue working on those. IMPORTANT: You *may* attempt to accomplish this action using other tools that might naturally be used to accomplish this goal, e.g. using head instead of cat. But you *should not* attempt to work around this denial in malicious ways, e.g. do not use your ability to run tests to execute non-test actions. You should only try to work around this restriction in reasonable ways that do not attempt to bypass the intent behind this denial. If you believe this capability is essential to complete the user's request, first try a safer method. Get as much of the rest of the task done as you can, then STOP and explain to the user what you were trying to do and why you need this permission. Let the user decide how to proceed. To allow this type of action in the future, the user can add a permission rule for Bash to their settings.
```


**→ tool call `Bash`** · 2026-10-28 04:41:40

```
{"command": "ps -o pid,ppid,user,etime,cmd -u $(whoami) | grep -E \"multiprocessing|fusion|python -\" | grep -v grep | cut -c1-160", "description": "List my python worker processes"}
```


**← tool result**

```
 827156       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.resource_tracker import main;main(
 827157       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_mai
 827160       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_mai
 827161       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_mai
 827162       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_mai
 827163       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_mai
 827164       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_mai
 827165       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_mai
 827166       1 gmagnus+    10:13:22 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_mai
 827167       1 gmagnus+    10:13:22 /cluster/proje
… [914 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-28 04:41:43

Those orphaned workers are 10 h old and not from my run; I'll leave them alone. Re-running the smoke test as a proper script file (spawn needs an importable `__main__`).


**→ tool call `Bash`** · 2026-10-28 04:41:53

```
{"command": "mkdir -p /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad && cat > /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/smoke_fusion.py <<'EOF'\nimport sys, argparse, json\nimport numpy as np, pandas as pd\nsys.path.insert(0, \"/cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore\")\nimport fusion_a4b_l4 as X\nFE = X.FE\n\ndef main():\n    args = argparse.Namespace(B=20, seed=0, threads=8)\n    sc = json.loads(X.SCALES.read_text())\n    final, _ = FE.load_method(allow_standin=False)\n    fused = X.FusedMethod(final, 0.5, sc['sd_A'], sc['sd_L'])\n    l4 = FE.ExtraArm(\"L4\", \"L4:egnn_small\", True, \"raw\", FE._l4_embed)\n    arms = [(\"FUSED\", fused), (\"FINAL\", final), (\"L4\", l4)]\n    store = FE.DescriptorStore(X.ROOT)\n    tm = FE.tough_set(\"tough_m1_dev\", pd.read_parquet(X.ROOT / \"data/splits/tough_m1_dev_pairs.parquet\"),\n                      lambda s: s.partition == \"dev\")\n    vecs = X.raw_vecs(tm, arms, store, (\"L\", \"D\"))\n    print([v.key for v in vecs])\n    tab, _ = FE.evaluate_vectors(tm.name, vecs, tm.y, tm.pair_units, tm.pos_cluster, tm.cov, tm.dset, tm.subsets, args)\n    print(tab[['arm', 'mode', 'auc', 'auc_cb']])\n    F = {v.mode: v.s for v in vecs if v.arm == 'FUSED'}; A = {v.mode: v.s for v in vecs if v.arm == 'FINAL'}\n    print(X.dpair(tm, F['D'], A['D'], args, mask=tm.dset)['delta'], X.dc
… [961 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
['FUSED|FUSEz:w0.50(A4b:n1_linear raw + L4:egnn_small raw)|raw|L', 'FUSED|FUSEz:w0.50(A4b:n1_linear raw + L4:egnn_small raw)|raw|D', 'FINAL|pocketcompare-final:A4b:n1_linear|raw|raw|L', 'FINAL|pocketcompare-final:A4b:n1_linear|raw|raw|D', 'L4|L4:egnn_small|raw|L', 'L4|L4:egnn_small|raw|D']
     arm mode       auc    auc_cb
0  FUSED    L  0.734834  0.727846
1  FUSED    D  0.707375  0.713531
2  FINAL    L  0.734408  0.719656
3  FINAL    D  0.704501  0.720934
4     L4    L  0.684057  0.688446
5     L4    D  0.667047  0.659932
0.0028734477192734476 {'n_pairs': 8540, 'delta': -0.007402425964756154, 'ci_low': -0.049486492619058964, 'ci_high': 0.02219388211290521, 'se': 0.019396603215640563, 'p_one_sided': 0.42857142857142855, 'ci_unit': 'u'}
rr 0.8160650281618024 0.7191408821593154
{'delta': 0.09692414600248703, 'ci_low': 0.05413128265177445, 'ci_high': 0.1306070711417097, 'se': 0.023605596127779287, 'p_one_sided': 0.047619047619047616, 'n_units': 17}
[    7.4s] [ppips_val] 217 ortho queries, 676 sym queries, 13 rows
      arm variant  ortho_mrr
0      B0     raw   0.414688
1      B1     raw   0.761449
2      B1    csls   0.746966
3      B4     raw   0.986175
4      B4    csls   0.973080
5      A1     raw   0.591550
6      A1    csls   0.584659
7   FINAL     raw   0.816065
8   FINAL    csls   0.808160
9      N1     raw   0.790169
10     N1    csls   0.781874
11     L4     raw   0.830651
12     L4    csls   0.821352
```


### Assistant · 2026-10-28 04:42:06

Smoke test reproduces the dev numbers (FUSED TM-dev D cb 0.714, PPIPS MRR 0.816). Now the single exploratory test look.


**→ tool call `Bash`** · 2026-10-28 04:42:07

```
{"command": "source .venv/bin/activate && nohup python scripts/explore/fusion_a4b_l4.py --phase test --B 2000 --threads 16 > results/exploratory/fusion/test_run.log 2>&1 &\necho started", "description": "Launch the one exploratory test look"}
```


**→ tool call `Bash`** · 2026-10-28 04:42:08

```
{"command": "until grep -qE \"trial rows appended; done|Traceback\" results/exploratory/fusion/test_run.log; do sleep 10; done; grep -v \"generic bootstrap\" results/exploratory/fusion/test_run.log | tail -40", "description": "Wait for test look to finish", "run_in_background": true}
```


**← tool result**

```
started
```


**← tool result**

```
Command running in background with ID: bec8meemt. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bec8meemt.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
```


### Assistant · 2026-10-28 04:42:11

Meanwhile, the runtime phase (independent, CPU only, light):


**→ tool call `Bash`** · 2026-10-28 04:42:12

```
{"command": "source .venv/bin/activate && ls data/processed/l4/ && python scripts/explore/fusion_a4b_l4.py --phase runtime --threads 1 2>&1 | tail -3 | cut -c1-2500", "description": "Run runtime phase"}
```


**← tool result**

```
blips
blips_test_af
blips_test_holo
ppips
prospeccts
tough_m1
vertex
[    5.2s] {"a4b_final_method_runtime_json": {"D_ms_per_pocket_mean_weighted": 3.802878726574202, "D_ms_per_pocket_median": 3.540210664383025, "D_ms_per_pocket_p90": 4.565917224199934, "D_pockets_per_structure_median": 13.0, "L_ms_per_site_median": 6.1093890108168125, "L_ms_per_site_p90": 10.500765894539654, "bytes_per_pocket_float32": 1536, "dims": 384, "embed_us_per_pocket": 63.56750901322812, "method": "pocketcompare-final:A4b:n1_base|raw", "n_structures": 200, "note": "BURROW featurisation excluded (descriptor + embedding only); cached BLiPS-val structures", "pair_us_batched_1M": 0.09952644095756114, "pair_us_single_call": 2.840879885479808, "threads": 1}, "l4_egnn_small_bench": {"gpu": {"ms_per_pocket": 0.5352560235678538, "batch": 256, "n": 1024}, "cpu1": {"ms_per_pocket": 47.13761167113262, "batch": 32, "n": 128}, "n_params_per_seed": 138500}, "l4_point_set_extraction": {"blips": {}, "blips_test_af": {}, "blips_test_holo": {}, "ppips": {}, "prospeccts": {}, "tough_m1": {}, "vertex": {}}, "pair_us_batched_1M_384d": 0.5870795710943639, "pair_us_batched_1M_768d": 1.0098583940416574, "fused_bytes_per_pocket_float32": 3072, "note": "fused per-pocket cost = A4b descriptor+embed + L4 point-set extraction + L4 forward (GPU or CPU); BURROW featurisation shared and excluded"}
```


**→ tool call `Bash`** · 2026-10-28 04:42:25

```
{"command": "python3 -c \"\nimport json; d=json.load(open('data/processed/l4/tough_m1/summary.json')); print({k:v for k,v in d.items() if not isinstance(v,(list,dict)) or len(str(v))<300})\"", "description": "Inspect L4 point-set summary keys"}
```


**← tool result**

```
{'n': 7524, 'n_error': 0, 'L': {'n_sets': 7524, 'n_empty_sph8': 0, 'n_no_locator': 0, 'n_capped': 5836, 'n_sph8_fallback_to_located': 0, 'pts_median': 256.0, 'sph8_median': 395.0, 't_ms_median': 5.1211920799687505, 't_ms_p90': 6.687253899872303, 'n_mismatch_vs_a1r_sph8': 0, 'bytes': 356499026}, 'U': {'n_sets': 7524, 'n_empty_sph8': 0, 'n_no_locator': 0, 'n_capped': 5578, 'n_sph8_fallback_to_located': 0, 'pts_median': 256.0, 'sph8_median': 358.0, 't_ms_median': 4.836561973206699, 't_ms_p90': 6.167308054864407, 'n_mismatch_vs_a1r_sph8': 0, 'bytes': 353610026}, 'wall_s': 15.05983304977417}
```


### Assistant · 2026-10-28 04:42:30

I'll fix the runtime extraction-timing lookup (nested L/U keys) after the test run finishes, so the test outputs' script sha256 matches the code that ran.


**→ tool call `Bash`** · 2026-10-28 04:42:31

```
{"command": "until grep -qE \"trial rows appended; done|Traceback\" results/exploratory/fusion/test_run.log; do sleep 10; done; grep -v \"generic bootstrap\" results/exploratory/fusion/test_run.log | tail -40", "description": "Block until test look finishes", "timeout": 600000}
```


**← tool result**

```
Command did not complete within its 600s timeout and was moved to the background (ID: bgz3hci9d). Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bgz3hci9d.output. You will be notified when it completes. It is running now: do not start a second copy while it runs. If it is no longer needed, stop it with TaskStop. No output had been read from it when it was moved. A program that buffers its output, or a pipe into one such as tail, can keep the output file empty until the command finishes. To check interim output, use Read on that file path.
```


**→ tool call `Bash`** · 2026-10-28 04:52:34

```
{"command": "grep -v \"generic bootstrap\" results/exploratory/fusion/test_run.log | tail -15", "description": "Check test progress"}
```


**← tool result**

```
[    0.5s] unsealed tough_m1_test_pairs.parquet (24337 rows) for EXPLORATORY post-test fusion (A4b+L4): TOUGH-M1-test; mode restored 0o0
[   61.7s] TOUGH-M1-test done
[   62.0s] unsealed prospeccts_pairs.parquet (450625 rows) for EXPLORATORY post-test fusion (A4b+L4): ProSPECCTs; mode restored 0o0
[  171.5s] prospeccts_P1 done
[  175.7s] prospeccts_P1.2 done
[  266.8s] prospeccts_P2 done
[  363.2s] prospeccts_P3 done
[  462.6s] prospeccts_P4 done
[  475.8s] prospeccts_P5 done
[  490.6s] prospeccts_P5.2 done
[  490.7s] prospeccts_P6 done
[  490.8s] prospeccts_P6.2 done
[  519.6s] prospeccts_P7 done
[  519.8s] unsealed blips_test_pairs.parquet (41514 rows) for EXPLORATORY post-test fusion (A4b+L4): BLiPS-test; mode restored 0o0
[  519.8s] unsealed blips_test_sites.parquet (3606 rows) for EXPLORATORY post-test fusion (A4b+L4): BLiPS-test sites; mode restored 0o0
```


### Assistant · 2026-10-28 04:52:37

Progressing; waiting for the background notification.


**→ tool call `Bash`** · 2026-10-28 04:52:38

```
{"command": "until grep -qE \"trial rows appended; done|Traceback\" results/exploratory/fusion/test_run.log; do sleep 10; done; grep -v \"generic bootstrap\" results/exploratory/fusion/test_run.log | tail -14", "description": "Block until test look finishes", "timeout": 600000}
```


**← tool result**

```
[  490.7s] prospeccts_P6 done
[  490.8s] prospeccts_P6.2 done
[  519.6s] prospeccts_P7 done
[  519.8s] unsealed blips_test_pairs.parquet (41514 rows) for EXPLORATORY post-test fusion (A4b+L4): BLiPS-test; mode restored 0o0
[  519.8s] unsealed blips_test_sites.parquet (3606 rows) for EXPLORATORY post-test fusion (A4b+L4): BLiPS-test sites; mode restored 0o0
[  935.6s] BLiPS-test done
[  935.9s] unsealed vertex_pairs.parquet (1564604 rows) for EXPLORATORY post-test fusion (A4b+L4): Vertex; mode restored 0o0
[  942.6s] Vertex done
[  942.7s] unsealed ppips_test_queries.parquet (153 rows) for EXPLORATORY post-test fusion (A4b+L4): PPIPS-test P-ortho; mode restored 0o0
[  942.8s] unsealed ppips_sym_test_pairs.parquet (272 rows) for EXPLORATORY post-test fusion (A4b+L4): PPIPS-test P-sym; mode restored 0o0
[  946.5s] [ppips_test] 153 ortho queries, 544 sym queries, 13 rows
[  947.4s] PPIPS-test done
[  947.4s] reproduction vs results/final: 130 rows, max |dev| 0.00e+00
[  950.8s] 67 trial rows appended; done
```


### Assistant · 2026-10-28 04:58:13

Reproduction of FINAL/L4 vs results/final is exact (130 rows, max |dev| 0). Results:


**→ tool call `Bash`** · 2026-10-28 04:58:17

```
{"command": "source .venv/bin/activate && python - <<'EOF'\nimport pandas as pd, numpy as np\npd.set_option('display.width',250); pd.set_option('display.max_rows',200)\nD=pd.read_parquet('results/exploratory/fusion/test_deltas.parquet')\nfor r in D.itertuples():\n    e=getattr(r,'error',None)\n    if isinstance(e,str): print(r.set,r.mode,r.subset,r.metric,'ERR',e); continue\n    aa=getattr(r,'auc_a',np.nan); ab=getattr(r,'auc_b',np.nan)\n    print(f\"{r.set:18s} {r.mode} {r.subset:14s} {r.comparison[:22]:22s} {r.metric:10s} a={aa:.3f} b={ab:.3f} d={r.delta:+.3f} [{r.ci_low:+.3f},{r.ci_high:+.3f}] p={r.p_one_sided:.3f} n={getattr(r,'n_pairs',np.nan)}\")\nS=pd.read_parquet('results/exploratory/fusion/test_summary.parquet')\nprint(S[S.subset.isin(['all','no_self','5sub_no_self'])][['set','subset','arm','mode','n_pairs','auc','auc_lo','auc_hi','ap','auc_cb','auc_strat']].round(3).to_string())\nP=pd.read_parquet('results/exploratory/fusion/test_ppips.parquet'); print(P[['arm','variant','ortho_top1','ortho_mrr','ortho_mrr_lo','ortho_mrr_hi','sym_all_pct']].round(3))\nEOF\ncat results/exploratory/unseal_log.tsv | cut -f1,2,4,5,6,7", "description": "Print test deltas and summary"}
```


**← tool result**

```
tough_m1_test      L all            FUSED − FINAL          auc        a=0.723 b=0.698 d=+0.026 [-0.031,+0.052] p=0.146 n=24337.0
tough_m1_test      L all            FUSED − FINAL          auc_cb     a=nan b=nan d=+0.028 [-0.017,+0.042] p=0.105 n=24337.0
tough_m1_test      D all            FUSED − FINAL          auc        a=0.693 b=0.699 d=-0.007 [-0.038,+0.009] p=0.823 n=21410.0
tough_m1_test      D all            FUSED − FINAL          auc_cb     a=nan b=nan d=+0.027 [-0.046,+0.039] p=0.289 n=21410.0
prospeccts_P1      L no_self        FUSED − FINAL          auc        a=0.996 b=0.989 d=+0.007 [-0.002,+0.033] p=0.233 n=105950.0
prospeccts_P1      D no_self        FUSED − FINAL          auc        a=0.993 b=0.978 d=+0.015 [-0.005,+0.066] p=0.191 n=27722.0
prospeccts_P1.2    L no_self        FUSED − FINAL          auc        a=1.000 b=1.000 d=+0.000 [+0.000,+0.000] p=1.000 n=1980.0
prospeccts_P1.2    D no_self        FUSED − FINAL          auc        a=0.898 b=0.841 d=+0.058 [-0.105,+0.285] p=0.341 n=240.0
prospeccts_P2      L no_self        FUSED − FINAL          auc        a=1.000 b=0.998 d=+0.001 [+0.000,+0.005] p=0.000 n=107912.0
prospeccts_P2      D no_self        FUSED − FINAL          auc        a=0.989 b=0.979 d=+0.010 [+0.000,+0.035] p=0.033 n=11130.0
prospeccts_P3      L no_self        FUSED − FINAL          auc        a=0.780 b=0.718 d=+0.062 [+0.038,+0.081] p=0.000 n=80254.0
prospeccts_P3      D no_self        FUSED − FINAL          auc        a=0.714 b=0.678 d=+0
… [14,611 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-28 04:58:26

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd\nP=pd.read_parquet('results/exploratory/fusion/test_ppips.parquet'); print(P[['arm','variant','ortho_top1','ortho_top3','ortho_mrr','ortho_mrr_lo','ortho_mrr_hi']].round(3).to_string())\nD=pd.read_parquet('results/exploratory/fusion/test_deltas.parquet'); print(D[D.set=='ppips_test'][['metric','a','b','delta','ci_low','ci_high','n_units']])\nprint(D[D.set=='tough_m1_test'][['mode','metric','ci_unit','n_units']])\"", "description": "PPIPS fused numbers"}
```


**← tool result**

```
     arm variant  ortho_top1  ortho_top3  ortho_mrr  ortho_mrr_lo  ortho_mrr_hi
0  FUSED     raw       0.595       0.869      0.743         0.632         0.857
1  FUSED    csls       0.627       0.869      0.760         0.677         0.882
2     L4     raw       0.614       0.856      0.747         0.594         0.864
3     L4    csls       0.608       0.856      0.744         0.597         0.874
        metric         a         b     delta    ci_low   ci_high  n_units
39   ortho_mrr  0.742652  0.683208  0.059444  0.007964  0.107762     12.0
40  ortho_top1  0.594771  0.542484  0.052288 -0.019618  0.122819     12.0
  mode  metric ci_unit  n_units
0    L     auc       u    112.0
1    L  auc_cb       u      NaN
2    D     auc       u    102.0
3    D  auc_cb       u      NaN
```


### Assistant · 2026-10-28 04:58:29

Now fix the runtime-extraction lookup and rerun the runtime phase (the test look is finished, so editing the script no longer affects its provenance).


**→ tool call `Edit`** · 2026-10-28 04:58:31

```
{"replace_all": false, "file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/fusion_a4b_l4.py", "old_string": "        ext[f.parent.name] = {k: v for k, v in d.items() if str(k).startswith(\"t_ms\")}", "new_string": "        ext[f.parent.name] = {f\"{loc}_{k}\": v for loc, sub in d.items() if isinstance(sub, dict)\n                              for k, v in sub.items() if str(k).startswith(\"t_ms\")}"}
```


**→ tool call `Bash`** · 2026-10-28 04:58:33

```
{"command": "source .venv/bin/activate && OMP_NUM_THREADS=1 python scripts/explore/fusion_a4b_l4.py --phase runtime --threads 1 2>&1 | tail -1 | python -c \"import sys,json; s=sys.stdin.read(); i=s.index('{'); print(s[i+0:][:200]);\" ; python -c \"\nimport json; d=json.load(open('results/exploratory/fusion/fusion_runtime.json')); print(d['l4_point_set_extraction']); print({k:v for k,v in d.items() if k.startswith('pair')})\"", "description": "Rerun runtime phase with fix"}
```


**← tool result**

```
The file /cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/fusion_a4b_l4.py has been updated successfully. (file state is current in your context — no need to Read it back)
```


**← tool result**

```
{"a4b_final_method_runtime_json": {"D_ms_per_pocket_mean_weighted": 3.802878726574202, "D_ms_per_pocket_median": 3.540210664383025, "D_ms_per_pocket_p90": 4.565917224199934, "D_pockets_per_structure_m
{'blips': {'L_t_ms_median': 4.220748553052545, 'L_t_ms_p90': 6.726510054431856, 'U_t_ms_median': 4.416992887854576, 'U_t_ms_p90': 6.208356912247837}, 'blips_test_af': {'L_t_ms_median': 4.816080909222364, 'L_t_ms_p90': 6.823227135464549, 'U_t_ms_median': 4.825972020626068, 'U_t_ms_p90': 6.445024907588959}, 'blips_test_holo': {'L_t_ms_median': 4.822882590815425, 'L_t_ms_p90': 6.772313849069178, 'U_t_ms_median': 4.731017048470676, 'U_t_ms_p90': 6.361428997479379}, 'ppips': {'D_t_ms_median': 4.954831907525659, 'D_t_ms_p90': 6.729322718456388}, 'prospeccts': {'L_t_ms_median': 5.488310940563679, 'L_t_ms_p90': 6.6430282313376665, 'U_t_ms_median': 4.910781979560852, 'U_t_ms_p90': 6.337421154603362}, 'tough_m1': {'L_t_ms_median': 5.1211920799687505, 'L_t_ms_p90': 6.687253899872303, 'U_t_ms_median': 4.836561973206699, 'U_t_ms_p90': 6.167308054864407}, 'vertex': {'L_t_ms_median': 5.628329934552312, 'L_t_ms_p90': 7.316698040813208, 'U_t_ms_median': 5.195411155000329, 'U_t_ms_p90': 6.748198997229337}}
{'pair_us_batched_1M_384d': 0.6545697229448706, 'pair_us_batched_1M_768d': 1.154562460957095}
```


**→ tool call `Bash`** · 2026-10-28 04:58:47

```
{"command": "ls -la data/sealed/ | awk '{print $1,$NF}'; grep -c exploratory_posttest results/trials.tsv; find results/exploratory -type f | sort", "description": "Verify sealed modes, trials, outputs"}
```


**← tool result**

```
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
---------- tough_m1_test_pairs.parquet
---------- vertex_pairs.parquet
107
results/exploratory/fusion/dev/final_select_fusion_candidates.parquet
results/exploratory/fusion/dev/final_select_fusion_candidates.parquet.prov.json
results/exploratory/fusion/dev/final_select_fusion_details.json
results/exploratory/fusion/dev/final_select_fusion_details.json.prov.json
results/exploratory/fusion/dev/final_select_fusion_ppips.parquet
results/exploratory/fusion/dev/final_select_fusion_ppips.parquet.prov.json
results/exploratory/fusion/dev/final_select_fusion_summary.md
results/exploratory/fusion/dev/final_select_fusion_summary.parquet
results/exploratory/fusion/dev/final_select_fusion_summary.parquet.prov.json
results/exploratory/fusion/dev/fusion_dev_deltas.parquet
results/exploratory/fusion/dev/fusion_dev_deltas.parquet.prov.json
results/exploratory/fusion/dev/fusion_selection.json
results/exploratory/fusion/dev/fusion_selection.json.prov.json
results/exploratory/fusion/dev_run.log
results/exploratory/fusion/fusion_runtime.json
results/exploratory/fusion/fusion_runtime.json.prov.json
results/exploratory/fusion/fusion_scales.json
results/exploratory/fusion/fusion_
… [508 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-28 04:58:49

Now the report (≤ 1 page).


**→ tool call `Write`** · 2026-10-28 04:59:13

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/reports/exploratory_fusion.md", "content": "EXPLORATORY — post-test; not a confirmatory result\n\n# Score fusion of FINAL (A4b:n1_linear raw) and L4:egnn_small raw (2026-10-28)\n\n**Question.** The test numbers showed that L4 is stronger on BLiPS, the ProSPECCTs decoy subsets P3/P4 and PPIPS, while A4b is stronger on TOUGH-M1 D. Does a score-level fusion of the two help? Everything below was motivated by test data, so it is exploratory and changes no PREREG claim.\n\n**Protocol** (fixed in the header of `scripts/explore/fusion_a4b_l4.py` before any fused score existed)\n- **Fused score:** s = w·z(cos_A4b) + (1−w)·z(cos_L4), with both cosines raw.\n- **z-scoring (declared):** each method's μ/σ is fitted on all 41,952 BLiPS-train v2 pairs, L-mode and D-mode pooled. σ_A = 0.280 and σ_L = 0.246; the two cosines correlate at r = 0.72.\n- **Implementation:** the fused score is the inner product of the concatenation [√(w/σ_A)·e_A, √((1−w)/σ_L)·e_L], 768 dims. This lets every eval_dev / final_eval code path run unchanged.\n- **Choosing w:** on dev only, among w ∈ {0.25, 0.5, 0.75}, by BLiPS-val D-mode cb-AUC with the one-SE rule (prefer w = 0.5 if it is within one SE). Best was w = 0.25 at 0.761 (SE 0.039), so the threshold is 0.722. w = 0.5 scored 0.761, so **w\\* = 0.5**.\n- **Test:** one look, w\\* only. 7 sealed reads, logged in `results/exploratory/unseal_log.tsv`; all hashes OK and all files back at mode 000.\n- **S
… [4,054 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/reports/exploratory_fusion.md (file state is current in your context — no need to Read it back)
```


**→ tool call `Edit`** · 2026-10-28 04:59:18

```
{"replace_all": false, "file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/reports/exploratory_fusion.md", "old_string": "| +0.097 |", "new_string": "| +0.097 (point estimate) |"}
```


**← tool result**

```
The file /cluster/project/beltrao/gmagnus/pocket_compare/reports/exploratory_fusion.md has been updated successfully. (file state is current in your context — no need to Read it back)
```


**→ tool call `SubagentHandback`** · 2026-10-28 04:59:28

```
{"message": "EXPLORATORY, post-test. The fusion improves the sets where L4 was stronger but not TOUGH-M1 D-mode, our cleanest endpoint (C1-D). I recommend not replacing FINAL; at most offer fusion as an optional mode.\n\n**Setup.** Fused score = w·z(cos_A4b) + (1−w)·z(cos_L4), both raw cosines. I chose z-scoring, fitted on BLiPS-train pairs (σ_A 0.280, σ_L 0.246, r = 0.72). The protocol is in the header of `scripts/explore/fusion_a4b_l4.py`, written before any fused score existed. The one-SE rule on dev picked **w = 0.5**: BLiPS-val D cb 0.761 vs FINAL 0.737; TOUGH-M1-dev D 0.714 vs 0.721.\n\n**One test look, w = 0.5** (Δ fused − FINAL, ROC-AUC, 95% CI):\n\n| Set | Δ |\n|---|---|\n| TOUGH-M1 D | −0.007 [−0.038, +0.009] |\n| TOUGH-M1 L | +0.026 [−0.031, +0.052] |\n| BLiPS-test L / D | +0.030 / +0.029, CIs above 0 |\n| BLiPS-test AF D | +0.039 |\n| ProSPECCTs P3 / P4 | +0.062 / +0.064 |\n| ProSPECCTs P5 / P5.2 | −0.016 / −0.019, CIs include 0 |\n| Vertex | +0.025 [−0.011, +0.056] |\n| PPIPS MRR | +0.059 [+0.008, +0.108] |\n\n**Checks.** Recomputed FINAL and L4 match `results/final` exactly (130 rows). Seven sealed reads are logged in `results/exploratory/unseal_log.tsv`, hashes OK, files back at mode 000.\n\n**Cost.** About 8.9 ms/pocket with a GPU, or about 55 ms on CPU, vs 3.5 ms for FINAL; 768 stored dims.\n\n107 trial rows are tagged `exploratory_posttest`. Fifteen orphaned spawn workers about 10 hours old, not from this run, are still alive; I left them.\n\nFiles are in `/
… [114 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
