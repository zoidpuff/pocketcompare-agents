# Sub-agent a3fdf5a2c159749c4 — Pocket-definition robustness exploration (opus)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-27 21:04:39

You are a research scientist on a fast, fold-independent pocket-similarity project built on BURROW pockets. Project root: /cluster/project/beltrao/gmagnus/pocket_compare (git; do NOT commit — the PI commits). Read first: RESEARCH_TREE.md (top status + decisions D10–D12), reports/dev_eval_tough_m1.md and results/dev/tough_m1_dev_summary.md (the dev results), reports/{a1_descriptors,pocket_adapter}.md, DESIGN.md §2.2 and §3 A1, src/pocketcompare/{pockets.py,similarity.py,descriptors/a1.py,descriptors/baselines.py}, scripts/eval_dev.py. Env: `source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache`. ≤ 16 CPU threads; no GPU. NEVER open data/sealed/. Use the frozen src/pocketcompare/evaluate.py for every metric and append EVERY variant you evaluate to results/trials.tsv via provenance.append_trial (this is our multiple-testing record — log failures too). Time box: 2.5 hours.

Problem (D11): on TOUGH-M1-dev the typed volumetric fingerprint A1 scores ROC 0.80 in L-mode (pocket = BURROW grid points within 4 Å of the ligand) but collapses to 0.56 in D-mode (pocket = BURROW-detected merged pocket best covering the site) — the L-mode shell imprints the ligand's shape, and TOUGH-M1 positives are ligand-defined. In deployment (AFDB scale) there is no ligand: D-mode is what matters. B1 (BURROW size-free descriptor) and B4 (ESM-2) are more robust (D-mode ≈ 0.58–0.60) but weak. Goal: find a pocket definition + descriptor combination that maximises the mean cluster-balanced AUC over L-mode and D-mode on TOUGH-M1-dev (the amended selection objective), with size-stratified AUC as the guard (size shortcuts do not count).

Explore (prioritise cheap, principled variants; ≤ ~40 logged variants total):
1. Ligand-free site definitions that apply identically to both modes, so L and D differ only in how the site is located: e.g. (a) "residue mode": lining residues (≤ 4 Å of ligand in L; of the detected pocket in D) → all buried solvent-shell points (bur10 ≥ τ) within 4 Å of those residues' atoms; (b) "core mode": within the located region keep the most buried points (top-q by bur16/burbb16 or depth) or points within R Å of the buriedness-weighted centroid (R ∈ {6, 8, 10}); (c) for D-mode: unmerged best-coverage region pocket vs merged; BURROW sub-pockets with set-to-set best-match scoring (max or soft-max over sub-pocket pair similarities).
2. Which A1 blocks are definition-robust (type × buriedness histograms, pair-distance distributions, typed moments, scalars)? Measure the label-free same-site agreement (L-mode vs D-mode descriptor of the same site: retrieval AUC of the true partner among all dev pockets) per block and per definition — a label-free robustness objective — and the labelled dev AUCs.
3. A1 "environment" variants that describe the protein side rather than the void: e.g. per-point first-hit chemistry fractions and residue-group composition at 8/12 Å (already in BURROW point features: hit_*, f8_*, f12_*, n4_rg_*) aggregated as histograms weighted by buriedness — likely more robust to the exact point set than pair distances.
4. Concatenations/weighted blocks of the above with B1 (both are cheap) — but only a handful, and report the size-stratified AUC.
Keep each variant's per-pocket cost and dimension. Put new code in src/pocketcompare/descriptors/ (e.g. a1r.py) and src/pocketcompare/pockets.py extensions with tests for invariances; scripts in scripts/explore/. Compute descriptors for all 7,524 TOUGH-M1 pockets (label-free) but evaluate ONLY on TOUGH-M1-dev pairs (data/splits/tough_m1_dev_pairs.parquet).
Deliver reports/definition_robustness.md (≤ 1.5 pages, numbers first: table of variants with L / D / mean cluster-balanced AUC, stratified AUC, L↔D agreement, ms/pocket, dims; the recommended configuration(s) for the next stage — the learned metric A4b will be trained on top; honest about what did not work). Final message ≤ 250 words.


### PI / user turn · 2026-10-27 21:04:39

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


### Assistant · 2026-10-27 21:04:41

I'll start by reading the project status and key files.


**→ tool call `Bash`** · 2026-10-27 21:04:43

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; head -c 9000 RESEARCH_TREE.md; echo ----; ls; ls reports results results/dev scripts scripts/* src/pocketcompare src/pocketcompare/descriptors tests data data/* 2>/dev/null | grep -v sealed | head -150", "description": "Read research tree and list project layout"}
```


**← tool result**

```
# Research tree — pocket similarity on BURROW

Legend: [ ] planned · [~] in progress · [x] done · [-] abandoned/negative · [!] key finding
Started 2026-10-27 ~18:00 CET; 24 h budget (revisit ~2026-10-28 18:00).

## Status summary (latest first)

### 2026-10-27 19:55 — M1 design v1 + build launched
Literature, benchmarks, feasibility and PPI characterisation done; DESIGN v1 after six round-1 reviews. Key
findings so far: TOUGH-M1 is the only large fold-independent benchmark (TM-score AUC 0.51); 32 % of TOUGH-M1 is
homologous to BURROW training, so TOUGH-M1 dev = BURROW-homologous groups and test = BURROW-clean rest;
fragment docking is cheap (0.8 ms/fragment×pocket) but tracks pocket size (ρ −0.74), so it is gated.
Seven agents are building in parallel: evaluation module, splits, PPI datasets, A1/B0/B1, B4/B5, A2 docking.
No method has been evaluated yet. One protocol deviation (DEV1: TOUGH-M1 labels read by a reviewer before
sealing; B0 only). Next: round-2 review, commit splits, evaluate arms on dev.

### 2026-10-27 18:15 — M0 kickoff
Scaffold, venv (BURROW importable via read-only .pth on ../pocket_detect/src), PROMPT.md saved. BURROW
export smoke test passes (1a28: top pocket 0.626, 312 pts). Phase 1 launched in parallel: literature review,
public benchmark acquisition, fragment-docking feasibility (ADock), PPI/dimer pocket characterization.

Nothing modelled yet. No held-out data touched. Next: LITERATURE.md → DESIGN.md → ≤3 review rounds.

## Decisions
- D10 (21:45) **A2
… [10,014 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:04:48

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat reports/dev_eval_tough_m1.md results/dev/tough_m1_dev_summary.md; ", "description": "Read dev eval reports"}
```


**→ tool call `Bash`** · 2026-10-27 21:04:48

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat reports/a1_descriptors.md reports/pocket_adapter.md", "description": "Read A1 and pocket adapter reports"}
```


**← tool result**

```
# A1 typed volumetric fingerprint, B0/B1 baselines and the scoring helpers (2026-10-27)

**Code:** `src/pocketcompare/descriptors/{a1,baselines}.py`, `src/pocketcompare/similarity.py`, `configs/a1_grid.yaml`
(16 configs), `scripts/compute_descriptors.py`, `tests/test_descriptors.py` (17 tests, 12 s). **Outputs (git-ignored):**
`data/processed/descriptors/tough_m1/<arm>_<config>_<L|D>.{npy,ids.parquet,ids.parquet.prov.json,layout.json}`.
These cover A1 ×16, B1 ×2 and B0, each in L and D mode: 7,524 pockets per mode, 0 failures, 196 s on 12 workers, 440 MB.
D-mode rows are all pockets with a matched merged BURROW pocket. The ids table carries `d_coverage`, `d_precision`,
`d_missed` and `d_match` (cov ≥ 0.3 or prec ≥ 0.5; 94.5 %), so the caller applies the DESIGN rule.

## Design as implemented (default config, 514 dims)
- **Inputs:** the point cache alone. Protein atoms, names, elements and residue names are cached, so no structure is
  re-read. Analytic point features only; `point_score` is never used.
- **Typing:** each heavy atom gets a VolSite-like type from a residue/atom table (hyd, aro, don, acc, don/acc, pos,
  neg, null; unknown residues fall back to the element).
  - Points are soft-typed by the atoms within 4.5 Å with weights exp(−(d−d_min)/0.5 Å).
  - A cosine taper over the last 0.5 Å makes the type continuous at the cutoff.
  - The metal channel comes from BURROW metal-candidate points (weight 1 voxel); ions are stripped.
- **Resampling:** vol-weighted, done in BU
… [11,815 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
<persisted-output>
Output too large (41.3KB). Full output saved to: /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/brr6wfdvp.txt

Preview (first 2KB):
# Dev evaluation of all arms on TOUGH-M1-dev (eval agent, 2026-10-27)

`scripts/eval_dev.py --dataset tough_m1` (B = 2000, seed 0, 16 threads, 174 s). Results: `results/dev/tough_m1_dev_summary.{parquet,md}`,
`tough_m1_dev_details.json` (selection, gate, MDE, folds), `tough_m1_dev_replicates.parquet`, all with `.prov.json`; 137 rows
appended to `results/trials.tsv`. Dev = 731 pockets, 9,829 pairs (3,366 pos, prevalence 0.342). Full table (137 rows,
incl. all 16 A1 configs in L and D mode) in the summary md. Not committed.

## Main table (L-mode unless noted; CIs = 95 % vertex bootstrap, units = ligand cluster ∪ homology group)

| arm | ROC-AUC [CI] | AP (lift) | pAUC₀.₁ | cluster-bal. AUC [CI] | size-strat. AUC [CI] |
|---|---|---|---|---|---|
| B0 size, −abs(Δ log V) | 0.780 [0.696, 0.844] | 0.574 (1.68) | 0.552 | 0.766 [0.729, 0.833] | 0.520 [0.457, 0.573] |
| B0m size logistic (cross-fitted) | 0.857 [0.824, 0.959] | 0.704 (2.06) | 0.625 | 0.881 [0.849, 0.930] | **0.489** [0.420, 0.709] |
| B0′ global TM-score | 0.508 [0.455, 0.593] | 0.344 (1.01) | 0.500 | 0.539 [0.422, 0.585] | 0.493 [0.439, 0.640] |
| B1 BURROW descriptors | 0.643 [0.549, 0.664] | 0.465 (1.36) | 0.531 | 0.632 [0.584, 0.701] | 0.630 [0.461, 0.659] |
| B4 ESM-2, z-scored cosine | 0.601
… [692 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:04:51

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 1,400p /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/brr6wfdvp.txt | head -120", "description": "Read dev eval report body"}
```


**← tool result**

```
# Dev evaluation of all arms on TOUGH-M1-dev (eval agent, 2026-10-27)

`scripts/eval_dev.py --dataset tough_m1` (B = 2000, seed 0, 16 threads, 174 s). Results: `results/dev/tough_m1_dev_summary.{parquet,md}`,
`tough_m1_dev_details.json` (selection, gate, MDE, folds), `tough_m1_dev_replicates.parquet`, all with `.prov.json`; 137 rows
appended to `results/trials.tsv`. Dev = 731 pockets, 9,829 pairs (3,366 pos, prevalence 0.342). Full table (137 rows,
incl. all 16 A1 configs in L and D mode) in the summary md. Not committed.

## Main table (L-mode unless noted; CIs = 95 % vertex bootstrap, units = ligand cluster ∪ homology group)

| arm | ROC-AUC [CI] | AP (lift) | pAUC₀.₁ | cluster-bal. AUC [CI] | size-strat. AUC [CI] |
|---|---|---|---|---|---|
| B0 size, −abs(Δ log V) | 0.780 [0.696, 0.844] | 0.574 (1.68) | 0.552 | 0.766 [0.729, 0.833] | 0.520 [0.457, 0.573] |
| B0m size logistic (cross-fitted) | 0.857 [0.824, 0.959] | 0.704 (2.06) | 0.625 | 0.881 [0.849, 0.930] | **0.489** [0.420, 0.709] |
| B0′ global TM-score | 0.508 [0.455, 0.593] | 0.344 (1.01) | 0.500 | 0.539 [0.422, 0.585] | 0.493 [0.439, 0.640] |
| B1 BURROW descriptors | 0.643 [0.549, 0.664] | 0.465 (1.36) | 0.531 | 0.632 [0.584, 0.701] | 0.630 [0.461, 0.659] |
| B4 ESM-2, z-scored cosine | 0.601 [0.514, 0.625] | 0.431 (1.26) | 0.522 | 0.624 [0.558, 0.680] | 0.600 [0.483, 0.632] |
| B4 ESM-2, raw cosine | 0.575 [0.480, 0.624] | 0.404 (1.18) | 0.516 | 0.572 [0.483, 0.634] | 0.575 [0.497, 0.670] |
| B5 EPoCS (−Euclidea
… [10,094 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:04:55

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -E \"^\\| (A1|B1|B4|B0) \" results/dev/tough_m1_dev_summary.md | head -60", "description": "Show A1/B1/B4 rows of the dev summary"}
```


**← tool result**

```
| B0 | default | raw | L | 9829 | 0.780 [0.696, 0.844] | 0.574 (1.68) | 0.552 | 0.766 [0.729, 0.833] | 0.520 [0.457, 0.573] | — |
| B0 | default | raw | D | 7866 | 0.530 [0.422, 0.574] | 0.378 (1.05) | 0.501 | 0.484 [0.426, 0.572] | 0.523 [0.357, 0.576] | 0.347 |
| B1 | default | raw | L | 9829 | 0.643 [0.549, 0.664] | 0.465 (1.36) | 0.531 | 0.632 [0.584, 0.701] | 0.630 [0.461, 0.659] | — |
| B1 | default | csls | L | 9829 | 0.645 [0.553, 0.667] | 0.468 (1.37) | 0.533 | 0.640 [0.594, 0.710] | 0.628 [0.462, 0.658] | — |
| B1 | default | raw | D | 7866 | 0.615 [0.527, 0.633] | 0.455 (1.27) | 0.525 | 0.620 [0.549, 0.679] | 0.614 [0.443, 0.641] | 0.402 |
| B1 | default | csls | D | 7866 | 0.619 [0.537, 0.641] | 0.456 (1.27) | 0.525 | 0.630 [0.560, 0.692] | 0.615 [0.470, 0.653] | 0.405 |
| B1 | learned | raw | L | 9829 | 0.647 [0.543, 0.667] | 0.472 (1.38) | 0.534 | 0.628 [0.579, 0.695] | 0.631 [0.442, 0.659] | — |
| B1 | learned | csls | L | 9829 | 0.649 [0.546, 0.671] | 0.474 (1.38) | 0.536 | 0.635 [0.586, 0.701] | 0.631 [0.446, 0.661] | — |
| B1 | learned | raw | D | 7866 | 0.625 [0.524, 0.642] | 0.466 (1.30) | 0.530 | 0.618 [0.551, 0.674] | 0.621 [0.435, 0.648] | 0.409 |
| B1 | learned | csls | D | 7866 | 0.631 [0.535, 0.651] | 0.468 (1.30) | 0.529 | 0.630 [0.560, 0.691] | 0.623 [0.456, 0.656] | 0.413 |
| A1 | default | raw | L | 9829 | 0.788 [0.760, 0.876] | 0.625 (1.82) | 0.590 | 0.794 [0.766, 0.872] | 0.732 [0.597, 0.789] | — |
| A1 | default | csls | L | 9829 | 0.781 [0.75
… [6,582 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:05:00

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; wc -l scripts/eval_dev.py src/pocketcompare/*.py src/pocketcompare/descriptors/*.py; sed -n 1,200p scripts/eval_dev.py", "description": "Read eval_dev.py first part"}
```


**← tool result**

```
   790 scripts/eval_dev.py
     1 src/pocketcompare/__init__.py
   810 src/pocketcompare/evaluate.py
   587 src/pocketcompare/pockets.py
   225 src/pocketcompare/provenance.py
     2 src/pocketcompare/seeds.py
   142 src/pocketcompare/similarity.py
   137 src/pocketcompare/splitutil.py
     0 src/pocketcompare/descriptors/__init__.py
   507 src/pocketcompare/descriptors/a1.py
   303 src/pocketcompare/descriptors/a2.py
    85 src/pocketcompare/descriptors/baselines.py
   120 src/pocketcompare/descriptors/esm_pocket.py
  3709 total
#!/usr/bin/env python
"""Development evaluation of every pocket-similarity arm on a dev split (DESIGN v2 §3, §4; amendment D6).

    python scripts/eval_dev.py --dataset tough_m1            # TOUGH-M1-dev, B = 2000, seed SEEDS[0]
    python scripts/eval_dev.py --dataset tough_m1 --B 50 --out <scratch> --no-trials     # smoke test

Reusable for BLiPS-val / PPIPS-val: everything dataset-specific lives in a ``DevDataset`` adapter (pairs + labels,
pocket table with bootstrap units, L-mode log volume, D-mode match flag, positive clusters, descriptor / docking
locations, natively shipped pair scores).  Only ``ToughM1Dev`` is implemented; ``BlipsVal`` documents what the
BLiPS adapter must provide.

All metrics come from the frozen ``pocketcompare.evaluate``; result files get provenance sidecars and every
evaluated arm / config / variant / mode is appended to ``results/trials.tsv`` (unless ``--no-trials``).

Analysis choices fixed in this file BEFORE the fir
… [11,097 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:05:05

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 200,480p scripts/eval_dev.py", "description": "Read eval_dev.py middle"}
```


**→ tool call `Bash`** · 2026-10-27 21:05:06

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -n \"^def \\|^class \" src/pocketcompare/evaluate.py src/pocketcompare/provenance.py src/pocketcompare/similarity.py src/pocketcompare/pockets.py src/pocketcompare/descriptors/a1.py src/pocketcompare/descriptors/baselines.py; head -5 results/trials.tsv; wc -l results/trials.tsv", "description": "List functions in key modules and trials header"}
```


**← tool result**

```
    split = "val"

    def load(self):
        raise NotImplementedError("BLiPS-val adapter: descriptors and the D9 re-split are not available yet")


DATASETS = {"tough_m1": ToughM1Dev, "blips": BlipsVal}


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
    rows = np.where(avail)[0]
    zs = ZScorer.fit(M[rows]) if zscore else None
    Er = embed(M[rows], zs, layout, block_weights)
    E = np.zeros((len(M), Er.shape[1]), np.float32)
    E[rows] = Er
    ok = avail[ia] & avail[ib]
    raw = np.full(len(ia), np.nan)
    raw[ok] = pair_scores(E, ia[ok], ib[ok])
    if not csls:
        return raw, None
    r = np.full(len(M), np.nan)
    r[rows] = csls_r(Er, Er, CSLS_K, query_ids=rows, bg_ids=rows)
    return raw, raw - 0.5 * (r[ia] + r[ib])


def neg_euclid_vectors(M, avail, ia, ib):

… [11,527 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
src/pocketcompare/evaluate.py:113:def _as_arrays(y, s, w=None, *, allow_nan=False):
src/pocketcompare/evaluate.py:137:def _need_both(y, w):
src/pocketcompare/evaluate.py:145:def _grouped_desc(y, s, w):
src/pocketcompare/evaluate.py:160:def roc_auc(y, s, w=None) -> float:
src/pocketcompare/evaluate.py:171:def average_precision(y, s, w=None, *, target: str = "pos") -> dict:
src/pocketcompare/evaluate.py:189:def partial_auc(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
src/pocketcompare/evaluate.py:210:def binary_metrics(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
src/pocketcompare/evaluate.py:223:def _balance(labels, mask, w):
src/pocketcompare/evaluate.py:234:def _factorize(a):
src/pocketcompare/evaluate.py:240:def cluster_balanced_auc(y, s, pos_cluster, w=None, *, neg_cluster=None) -> dict:
src/pocketcompare/evaluate.py:253:def per_cluster_auc(y, s, pos_cluster, w=None, *, k: int = 10, negatives: str = "all", ci=None, cj=None):
src/pocketcompare/evaluate.py:284:def _quantile_bins(x, n_bins):
src/pocketcompare/evaluate.py:290:def size_covariates(log_vol_a, log_vol_b) -> np.ndarray:
src/pocketcompare/evaluate.py:297:def stratified_auc(y, s, covariate, w=None, *, n_bins: int | Sequence[int] = (5, 5),
src/pocketcompare/evaluate.py:347:def retrieval_metrics(df, *, query_col="query", score_col="score", label_col="label", ks: Sequence[int] = (1, 10),
src/pocketcompare/evaluate.py:383:def _score_dict(scores) -> dict[str, np.ndarray]:
src/pocketcompare/evaluate.py:392:def missin
… [11,981 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:05:10

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 480,640p scripts/eval_dev.py; sed -n 190,225p src/pocketcompare/provenance.py", "description": "Read eval main and append_trial"}
```


**← tool result**

```
        f"(largest {unit_sizes.max()} pockets), {len(units_in_pairs)} units in pairs; D-set {dset.sum()} pairs")

    vecs, meta = build_vectors(ds, log)
    # B0m diagnostic: cross-fitted logistic on (log va + log vb, |Δ log v|)
    ufold = unit_folds(P.unit.to_numpy(), N_FOLDS, args.seed)
    fa, fb = ufold[ds.ia], ufold[ds.ib]
    lv = P.logv_L.to_numpy()
    Xb0 = np.column_stack([lv[ds.ia] + lv[ds.ib], np.abs(lv[ds.ia] - lv[ds.ib])])
    oof, b0m_info = cross_fit(Xb0, y_all.astype(int), fa, fb)
    vecs.append(Vec("B0m", "logit_sum_absdiff", "crossfit", "L", oof, 2, "diagnostic; must be 0.5 ± 0.03 stratified"))
    meta["b0m"] = b0m_info
    meta["folds"] = {"pockets_per_fold": np.bincount(ufold, minlength=N_FOLDS).tolist(),
                     "pairs_per_foldset": None}
    for v in vecs:  # L-mode / native vectors must be complete
        if v.mode != "D" and np.isnan(v.s).any():
            raise RuntimeError(f"{v.key}: {int(np.isnan(v.s).sum())} NaN scores in a complete mode")
    log(f"{len(vecs)} score vectors built")

    # ------------------------------------------------------------------ evaluation records
    def eval_sets(v: Vec):
        """Primary evaluation mask (pairs) for a vector."""
        if v.mode == "D":
            return dset & ~np.isnan(v.s)
        return np.ones(len(y_all), bool)

    def generic_args(key, v: Vec, mask, y=None):
        y = (y_all if y is None else y)[mask]
        return (key, y, v.s[mask], pc_all[mask], cov_all[mask], ci_all
… [9,560 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:05:15

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 1,60p src/pocketcompare/pockets.py; sed -n 95,215p src/pocketcompare/pockets.py", "description": "Read pockets.py header and Featurized"}
```


**→ tool call `Bash`** · 2026-10-27 21:05:15

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 317,587p src/pocketcompare/pockets.py", "description": "Read pocket definition functions"}
```


**← tool result**

```
def _res_names(P) -> np.ndarray:
    out = np.empty(len(P.residue_ids), dtype="U5")
    out[P.res_index] = P.res_name
    return out


# --------------------------------------------------------------------------- L-mode
@dataclass
class LPocket:
    idx: np.ndarray           # point indices into Featurized.points (sorted)
    residues: list            # lining residues (<= lining cutoff of the points)
    volume_A3: float
    definition: str           # "ligand" | "residues"
    info: dict = field(default_factory=dict)

    @property
    def n_points(self) -> int:
        return len(self.idx)


def lmode_from_ligand(fs: Featurized, ligand_xyz, cutoff: float = L_CUTOFF,
                      lining_cutoff: float = LINING_CUTOFF) -> LPocket:
    """Points within ``cutoff`` Å of any ligand heavy atom (caller passes heavy atoms only)."""
    L = np.asarray(ligand_xyz, np.float64).reshape(-1, 3)
    if len(L) == 0:
        raise ValueError("no ligand heavy atoms")
    hits = cKDTree(L).query_ball_point(fs.points.astype(np.float64), cutoff, return_length=True)
    idx = np.flatnonzero(hits > 0)
    dmin, _ = fs.atom_tree().query(L, k=1)
    info = {"n_ligand_atoms": int(len(L)), "ligand_protein_min_dist": float(dmin.min()),
            "ligand_protein_median_dist": float(np.median(dmin))}
    return LPocket(idx=idx, residues=fs.residues_near(idx, lining_cutoff), volume_A3=fs.volume(idx),
                   definition="ligand", info=info)


def lmode_from_residues(fs: Featurized, re
… [12,664 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
"""Pocket adapter (DESIGN §2.1): the single source of BURROW points, point features and pocket definitions
for every method in this project.

    fs = featurize_structure(path)                       # all BURROW solvent-shell points + features + pockets
    lp = lmode_from_ligand(fs, ligand_heavy_xyz)          # L-mode: points <= 4 Å of the ligand
    lp = lmode_from_residues(fs, ["A:43", ...])           # L-mode from a residue list (+ bur10 >= 0.5)
    dm = dmode_match(fs, lp.idx)                          # D-mode: merged region-rule pocket covering lp
    fs.save(path) / Featurized.load(path)                 # per-structure cache (compressed npz)

Points.  ``featurize_structure`` runs the BURROW reference pipeline (``pocketdetect.burrow``) once on the
protein-only view of the structure (ligands, waters, ions, nucleic acids and hydrogens stripped by
``protein_from_structure``) and keeps EVERY featurised point, not only pocket points: the dense LIGSITE
survivors (``vol`` = 1 grid voxel), the coarse sub-lattice points that stand for the exposed shell
(``vol`` = subsample^3 = 27 voxels in the ``default`` preset) and the metal candidates (``vol`` = 0).
Volumes are therefore always ``sum(vol[idx]) * spacing**3`` Å^3, never point counts.

Pockets.  One run yields BURROW's full output list (``min_score=None``, <= 50 pockets after NMS); the
``--output-rule region`` list and the default (v2) list are post-filters of it (flags ``pk_in_region``,
``pk_in_v2``), exactly as ``pocketdetect
… [7,285 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 21:05:18

Now the A1 descriptor and compute_descriptors script.


**→ tool call `Bash`** · 2026-10-27 21:05:20

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 1,212p src/pocketcompare/descriptors/a1.py", "description": "Read a1.py first half"}
```


**→ tool call `Bash`** · 2026-10-27 21:05:20

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 212,507p src/pocketcompare/descriptors/a1.py", "description": "Read a1.py second half"}
```


**→ tool call `Bash`** · 2026-10-27 21:05:21

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat src/pocketcompare/descriptors/baselines.py; cat scripts/compute_descriptors.py", "description": "Read baselines.py and compute_descriptors.py"}
```


**← tool result**

```
# ----------------------------------------------------------------------------------------------- steps
def _taper(d, radius, width):
    """1 for d <= radius - width, cosine down to 0 at radius, 0 beyond (inf -> 0)."""
    if width <= 0:
        return (d <= radius).astype(np.float64)
    x = np.clip((d - (radius - width)) / width, 0.0, 1.0)
    out = 0.5 * (1.0 + np.cos(np.pi * x))
    out[~np.isfinite(d)] = 0.0
    return out


def type_points(xyz, atom_xyz, atom_type, cfg_typing: dict) -> np.ndarray:
    """(n, 7) atom-derived type vectors (channels hyd..neg; the metal channel is added by the caller)."""
    n = len(xyz)
    out = np.zeros((n, 7), np.float64)
    if n == 0 or atom_xyz is None or len(atom_xyz) == 0:
        return out
    R = float(cfg_typing["radius"])
    k = int(min(cfg_typing.get("k_max", 32), len(atom_xyz)))
    d, j = cKDTree(atom_xyz).query(xyz, k=k, distance_upper_bound=R)
    d = d.reshape(n, k)
    j = j.reshape(n, k)
    valid = np.isfinite(d)
    jj = np.where(valid, j, 0)
    codes = np.asarray(atom_type, np.int64)[jj]                       # (n, k)
    onehot = np.zeros((n, k, len(ATOM_TYPES)), np.float64)
    np.put_along_axis(onehot, codes[..., None], 1.0, axis=2)
    onehot[~valid] = 0.0
    if cfg_typing["mode"] == "hard":
        t = onehot[:, 0, 1:]                                          # nearest atom (k sorted by distance)
        return np.where(valid[:, :1], t, 0.0)
    dmin = np.where(valid[:, 0], d[:, 0], np.inf)
    tau = float
… [11,446 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
"""A1 — typed volumetric pocket fingerprint (DESIGN §3 "A1"; reviews/round1_algorithms.md).

    pin = pocket_input(fs, idx)                       # from a pocketcompare.pockets.Featurized + point indices
    vec, layout = a1_descriptor(pin, cfg)             # float32 vector + block layout (list of Block)

Pipeline (every step is a parameter of the config dict, see ``DEFAULT_CONFIG`` and configs/a1_grid.yaml):

1. **Typing** (input frame).  Every protein heavy atom gets one VolSite-like pharmacophore type from a
   residue/atom-name table (``atom_type_codes``): hydrophobic, aromatic, donor, acceptor, donor/acceptor,
   positive, negative, or null (carbons bonded to N/O, Gly CA, Pro N ...).  A pocket point is typed by the atoms
   within ``radius`` (4.5 Å): *soft* = weights exp(-(d - d_min)/tau) over the atoms in range, times a cosine
   taper that brings the weight of an atom (and of the whole point, via d_min) to 0 at ``radius`` so the
   descriptor is continuous in the coordinates; *hard* = one-hot type of the nearest atom (VolSite).  BURROW
   metal-candidate points (vol = 0, protein-only view, so no ions) form the "metal" channel with weight
   ``metal_weight`` voxels.
2. **Resampling** (BURROW canonical frame ``X``, in which BURROW's 1 Å grid is defined, so the lattice is
   invariant to rigid motions of the input).  Each coarse sub-lattice point (vol = s^3, s = 3 in the default
   preset) is splatted into its s^3 grid voxels (they inherit its type/buriedness), duplicate
… [10,386 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
"""Baselines B0 (size only) and B1 (BURROW size-free pocket descriptor) — DESIGN §3 "Baselines".

B0: ``b0_descriptor`` = [log pocket volume (Å^3)]; similarity = -|log V_a - log V_b| (``b0_pair_scores``).

B1: the 76 BURROW pocket descriptors computed with ``pocketdetect.burrow.model.pocket_features`` on the pocket
point set (L- or D-mode), restricted to the size-free, context-free columns below; scored by cosine on
z-scored vectors (``pocketcompare.similarity``).  Exclusion rule (fixed before any label is seen):

* size by construction (extensive: counts, sums, absolute extents): n_pts, vol, sqrt_vol, sat_vol,
  geo_strength (volume-weighted sum of bur10/16/24), metal_n, pca1, pca2, pca3, extent, n_res
* protein context (whole-protein properties, not the pocket): n_atoms_prot, log_atoms, prot_frac
  (Spearman rho with log protein atoms = -0.92 on 500 TOUGH-M1 L-mode pockets), f8_wcn (rho = +0.85),
  n_chains
* candidate-generation context (constant / meaningless for an externally defined pocket): level, is_sub,
  is_score_src, score_rank, score_rel
* exact duplicates in the default preset (bur24 = longest ray = bur16): bur24_mean, bur24_q90, bur24_q10
* learned (DESIGN §2.8; ablation variant ``learned`` only): score_sum, score_sqrt, score_mean, score_max,
  score_top10, score_top30, score_q50 (score_sum and score_sqrt are also size-mixed and never used)

Intensive descriptors that merely correlate with size (e.g. bur*_mean, rho ~ -0.6 with log volume: bigger
pockets are more
… [17,352 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:05:25

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python -c \"\nimport pandas as pd, numpy as np, json\nix=pd.read_parquet('data/processed/cache/points/tough_m1/index.parquet'); print(ix.columns.tolist()); print(ix.iloc[0])\nz=np.load(ix.cache_file.iloc[0] if ix.cache_file.iloc[0].startswith('/') else ix.cache_file.iloc[0])\nprint(z['feature_names'].tolist())\nprint(z['desc_names'].tolist())\n\"; grep -n \"2.2\\|^## \\|^### \" DESIGN.md | head -60", "description": "Inspect index columns and feature names"}
```


**← tool result**

```
['pocket_id', 'structure_key', 'cache_file', 'status', 'failure_reason', 'n_points_structure', 'n_full', 'n_region', 'n_merged_region', 'definition', 'lmode_idx', 'n_points', 'n_points_dense', 'volume_A3', 'n_lining_res', 'lining_residues', 'n_ligand_atoms', 'ligand_protein_min_dist', 'n_missing_residues', 'alt_definition', 'alt_idx', 'alt_n_points', 'alt_volume_A3', 'alt_jaccard', 'alt_n_missing_residues', 'alt_chain_remapped', 'd_coverage', 'd_missed', 'd_members', 'd_n_points', 'd_volume_A3', 'd_score', 'd_rank_in_merged', 'd_precision', 'dfull_coverage', 'dfull_missed']
pocket_id                                                     tough_m1:11asA
structure_key                                                          11asA
cache_file                    data/processed/cache/points/tough_m1/11asA.npz
status                                                                    ok
failure_reason                                                          None
n_points_structure                                                      5686
n_full                                                                    50
n_region                                                                  13
n_merged_region                                                           13
definition                                                   ligand_file:sdf
lmode_idx                  [1926, 1927, 1930, 1931, 1942, 1943, 1949, 195...
n_points                                                                
… [5,343 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:05:30

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 54,64p DESIGN.md; sed -n 128,178p DESIGN.md; nproc; free -g | head -2", "description": "Read DESIGN pocket defs and methods"}
```


**← tool result**

```
### 2.2 Pocket definitions (one adapter, `src/pocketcompare/pockets.py`, used by every method we run)
- **L-mode:** BURROW grid points (ligands/waters/hetero stripped) within 4 Å of the benchmark ligand heavy atoms
  (or, where only residues are given, within 4 Å of those residues' atoms with bur10 ≥ 0.5). Headline mode for
  public benchmarks (comparability with the literature).
- **D-mode:** BURROW `--output-rule region` pockets, touching sub-pockets merged; the site is represented by the
  merged detected pocket of maximal coverage of the L-mode pocket; it is a match if coverage ≥ 0.3 **or**
  precision ≥ 0.5 (detected points within 1.5 Å of L-mode points; BURROW pockets are often smaller than the 4 Å
  ligand shell — 13.9 % of TOUGH-M1 sites), else "missed" (5.5 % on TOUGH-M1 under this rule). Because the choice
  uses the ligand, D-mode is an oracle-assisted deployment proxy; the **blind** deployment test is §2.7.
- D-mode numbers on public sets are reported only on the BURROW-clean subset (§2.3).

## 3. Methods

**Baselines.** B0 size only (−|log vol ratio|) and size-stratified variants; B0' MMseqs2 identity and Foldseek
TM (global); B1 BURROW size-free descriptor cosine (z-scored on dev); **B4 ESM-2 (650M) mean of lining-residue
embeddings, cosine** (EPoCS-style; strong, not sequence-independent); **B5 one external method run locally**
(EPoCS if it installs in ≤ 1 h, else PocketVec precomputed descriptors on overlapping ProSPECCTs pockets, else
APoc); B6 PSI on PPI-L; 
… [3,642 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:06:03

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python -c \"\nimport pandas as pd, numpy as np\nix=pd.read_parquet('data/processed/cache/points/tough_m1/index.parquet')\nz=np.load(ix.cache_file.iloc[5]); F=z['feats']; fn=z['feature_names'].tolist(); idx=ix.lmode_idx.iloc[5]\nnp.set_printoptions(precision=3,suppress=True)\nfor i,n in enumerate(fn): print(n, F[idx,i].min(), F[idx,i].mean(), F[idx,i].max(), '| all', F[:,i].mean())\nprint(z['pk_in_region'].sum(), ix.d_members.iloc[5], ix.n_merged_region.describe())\n\" 2>&1 | head -100; grep -rn \"hit_apolar\\|f8_rg\\|n4_rg\" ../pocket_detect/src/pocketdetect/burrow/*.py | head -20", "description": "Inspect point feature ranges"}
```


**← tool result**

```
bur6 0.36666667 0.71849155 0.96666664 | all 0.49654013
bur10 0.6333333 0.8187348 1.0 | all 0.5636099
bur16 0.7 0.84184915 1.0 | all 0.5882992
burbb6 0.2 0.58369833 0.96666664 | all 0.35104692
burbb10 0.43333334 0.7124088 1.0 | all 0.4513604
burbb16 0.56666666 0.7744526 1.0 | all 0.49791738
depth 2.4 5.8051095 8.9 | all 8.852944
hit_apolar 0.16666667 0.38686132 0.6 | all 0.2687045
hit_polar 0.2 0.37518248 0.6666667 | all 0.21669467
hit_charged 0.0 0.029683702 0.2 | all 0.040734526
hit_aromatic 0.0 0.050121654 0.23333333 | all 0.062165495
escape -1.1920929e-07 0.15815082 0.3 | all 0.41170081
psp 1.0 4.1167884 7.0 | all 2.039973
nearest 2.547961 3.1661196 4.7107935 | all 3.5462792
metal_cand 0.0 0.0 0.0 | all 0.0057104467
n_coord28 0.0 0.13138686 2.0 | all 0.10883439
coord_spread 0.0 0.0035773416 0.49009532 | all 0.0044787517
n_all4 0.0 5.2846713 14.0 | all 4.139402
n_all8 42.0 77.70803 108.0 | all 49.72993
n_all10 98.0 154.78102 212.0 | all 95.77058
n_all12 188.0 264.0146 345.0 | all 157.41417
n4_C 0.0 2.5255475 7.0 | all 2.4568357
n4_N 0.0 0.91240877 3.0 | all 0.6610682
n4_O 0.0 1.7299271 7.0 | all 0.9654014
n4_S 0.0 0.11678832 2.0 | all 0.05609674
n4_aromatic 0.0 0.124087594 3.0 | all 0.46187437
n4_hydrophobic_sc_C 0.0 0.5182482 3.0 | all 1.1084985
n4_donor 0.0 1.4014598 4.0 | all 0.8918374
n4_acceptor 0.0 1.7737226 7.0 | all 1.0268726
n4_backbone 0.0 3.7080293 12.0 | all 1.860598
n4_sidechain 0.0 1.5766424 6.0 | all 2.278804
n4_positive 0.0 0.0 0.0 | all 0.12227074
n4_negati
… [3,516 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:06:52

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; ls tests; sed -n 1,80p tests/test_descriptors.py; grep -n \"def test\\|fixture\" tests/test_descriptors.py tests/test_pockets.py | head -40", "description": "Look at existing tests for fixtures"}
```


**← tool result**

```
__pycache__
conftest.py
test_a2_descriptor.py
test_datasets.py
test_descriptors.py
test_esm_pocket.py
test_evaluate.py
test_pockets.py
test_provenance.py
"""A1 descriptor, baselines and similarity helpers (DESIGN §3 A1, §5 toy/geometry tests).

Real-structure tests use BURROW's example 1a28_A.pdb + the crystal progesterone (PDB mirror 1a28, STR chain A),
as tests/test_pockets.py does; cache-based tests use the TOUGH-M1 point cache when present."""
import dataclasses
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
from scipy.spatial.transform import Rotation  # noqa: E402

from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import baselines as BL  # noqa: E402
from pocketcompare import similarity as SIM  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
EX = PD / "release/burrow/examples/1a28_A.pdb"
MIRROR_1A28 = Path("/cluster/scratch/jjaenes/pdb/a2/1a28.cif.gz")
CACHE = ROOT / "data/processed/cache/points/tough_m1"
need_struct = pytest.mark.skipif(not (EX.exists() and MIRROR_1A28.exists()), reason="1a28 inputs not mounted")
need_cache = pytest.mark.skipif(not (CACHE / "index.parquet").exists(), reason="TOUGH-M1 point cache missing")


def rel(a, b):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    return np.linalg.norm(a - b) / max(np.lin
… [4,018 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:06:56

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 186,232p tests/test_descriptors.py; sed -n 1,45p tests/test_pockets.py; sed -n 72,90p tests/test_pockets.py", "description": "Read real-structure test fixtures"}
```


**← tool result**

```
@pytest.fixture(scope="module")
def real():
    pk = pytest.importorskip("pocketcompare.pockets")
    from pocketdetect.structure import load_structure
    fs = pk.featurize_structure(EX)
    s = load_structure(str(MIRROR_1A28))
    m = (s.res_name == "STR") & (s.chain == "A") & ~s.is_hydrogen
    lig = s.coords[m].astype(np.float64)
    R, t = Rotation.random(random_state=3).as_matrix(), np.array([12.0, -30.0, 7.5])
    s0 = load_structure(str(EX))
    g = pk.featurize_structure(dataclasses.replace(s0, coords=(s0.coords.astype(np.float64) @ R.T + t)
                                                   .astype(s0.coords.dtype)))
    lp_a = pk.lmode_from_ligand(fs, lig)
    lp_b = pk.lmode_from_ligand(g, lig @ R.T + t)
    return fs, g, lp_a.idx, lp_b.idx


@need_struct
@pytest.mark.parametrize("name", ["default", "hard_typing", "no_resample", "resample_3A"])
def test_rotation_translation_invariance(real, name):
    import yaml
    fs, g, ia, ib = real
    assert len(ia) == len(ib) > 100
    cfg = A1.make_config(yaml.safe_load((ROOT / "configs/a1_grid.yaml").read_text())["configs"][name])
    va, _ = A1.a1_descriptor(A1.pocket_input(fs, ia), cfg)
    vb, _ = A1.a1_descriptor(A1.pocket_input(g, ib), cfg)
    assert rel(va, vb) < 1e-4, rel(va, vb)
    b1a, _ = BL.b1_descriptor(fs, ia)
    b1b, _ = BL.b1_descriptor(g, ib)
    assert rel(b1a, b1b) < 1e-4


@need_struct
def test_point_order_invariance_and_determinism(real):
    fs, _, ia, _ = real
    cfg = A1.make_config()
    v1, _
… [3,198 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 21:07:23

Now I'll write the pocket-definition extensions.


**→ tool call `Bash`** · 2026-10-27 21:07:44

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat >> src/pocketcompare/pockets.py <<'EOF'\n\n\n# --------------------------------------------------------------------------- ligand-free site shapers (D11)\n# A \"locator\" gives a point set S (L-mode: the ligand shell; D-mode: the matched detected pocket).  A \"shaper\"\n# turns S into the site actually described, using S only to *locate* the site, so that L- and D-mode differ only\n# in where the site is, not in how its extent is cut.  Duck-typed: ``fs`` needs points, vol, feats,\n# feature_names, atom_xyz, atom_res (a Featurized or the light namespace of scripts/compute_descriptors.py).\nSITE_BUR_FEATURE = \"bur10\"\nSITE_BUR_MIN = 0.5\n\n\ndef _feat(fs, name):\n    return np.asarray(fs.feats[:, list(fs.feature_names).index(name)], np.float64)\n\n\ndef buried_centroid(fs, idx, feature: str = \"bur16\", power: float = 4.0) -> np.ndarray:\n    \"\"\"Centroid of ``idx`` weighted by vol * feature^power (input frame).  Falls back to the vol-weighted centroid\n    (then the plain centroid) if the weights vanish.\"\"\"\n    idx = np.asarray(idx, np.int64)\n    if len(idx) == 0:\n        raise ValueError(\"empty point set\")\n    P = np.asarray(fs.points[idx], np.float64)\n    v = np.asarray(fs.vol[idx], np.float64)\n    for w in (v * np.clip(_feat(fs, feature)[idx], 0, None) ** power, v, np.ones(len(idx))):\n        if w.sum() > 0:\n            return (w[:, None] * P).sum(0) / w.sum()\n    return P.mean(0)\n\n\nde
… [4,401 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
(Bash completed with no output)
```


**→ tool call `Write`** · 2026-10-27 21:08:03

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/src/pocketcompare/descriptors/a1r.py", "content": "\"\"\"A1r — definition-robust descriptor blocks (D11 exploration; reports/definition_robustness.md).\n\nThe A1 fingerprint describes the *void* (typed volume, pair distances); its L-mode advantage is largely an imprint\nof the ligand shape.  The ``env`` block describes the *protein side* of the site from BURROW's analytic per-point\nenvironment features, which are smoothed over 4–12 Å and therefore change little when the exact point set\nchanges:\n\n* ``env_mean``  (49): vol-weighted means of first-hit chemistry fractions (hit_apolar/polar/charged/aromatic),\n  residue-group counts within 4 Å (n4_rg_*), and atom/residue-group composition fractions within 8 and 12 Å\n  (f8_*, f12_*: C N O S aromatic hydrophobic-sc donor acceptor backbone sidechain positive negative + 7 residue\n  groups; the size/context-like wcn/coord columns are left out).\n* ``env_bur``   (49): the same features weighted by vol * bur16^4 (the buried core dominates).\n* ``env_hist``  (15): first-hit chemistry x bur16 tertile volume fractions (12) + tertile volume fractions (3),\n  the protein-side analogue of A1's type x buriedness histogram (same fixed tertile edges as A1).\n\nAll blocks are intensive (size-free), invariant to rigid motions (features are) and to point order.  Only analytic\npoint features are used (no ``point_score``, DESIGN §2.8).\n\"\"\"\nfrom __future__ import annotations\n\n
… [2,374 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:08:08

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; mkdir -p scripts/explore; python -c \"\nimport sys,time; sys.path.insert(0,'scripts'); sys.path.insert(0,'src')\nfrom compute_descriptors import load_light\nimport pandas as pd, numpy as np\nfrom pocketcompare import pockets as pk\nfrom pocketcompare.descriptors import a1r, a1 as A1, baselines as BL\nix=pd.read_parquet('data/processed/cache/points/tough_m1/index.parquet')\nfor k in [0,5,100,2000]:\n  r=ix.iloc[k]; fs=load_light(r.cache_file); fs.pk_indices; L=np.asarray(r.lmode_idx)\n  mem=list(r.d_members); D=np.unique(np.concatenate([fs.pk_indices[fs.pk_indptr[m]:fs.pk_indptr[m+1]] for m in mem]))\n  bm,c=pk.best_member(fs,L,mem); U=fs.pk_indices[fs.pk_indptr[bm]:fs.pk_indptr[bm+1]]\n  out=[]\n  for nm,S in [('L',L),('D',D),('U',U)]:\n    for sh in pk.SHAPERS:\n      t=time.perf_counter(); I=pk.shape_site(fs,S,sh); t1=time.perf_counter()-t\n      out.append(f'{nm}-{sh}:{len(I)}/{fs.vol[I].sum():.0f}')\n  print(r.pocket_id, len(mem), bm, round(c,2), ' '.join(out))\n  e=a1r.env_descriptor(fs,L); print(e.shape, np.isfinite(e).all())\n\"\n", "description": "Smoke-test shapers and env descriptor"}
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/src/pocketcompare/descriptors/a1r.py (file state is current in your context — no need to Read it back)
```


**← tool result**

```
tough_m1:11asA 1 0 0.68 L-base:155/154 L-res:588/579 L-sph6:266/265 L-sph8:415/413 L-sph10:605/623 L-core8:155/154 D-base:77/76 D-res:420/413 D-sph6:188/187 D-sph8:317/314 D-sph10:492/485 D-core8:77/76 U-base:77/76 U-res:420/413 U-sph6:188/187 U-sph8:317/314 U-sph10:492/485 U-core8:77/76
(113,) True
tough_m1:1a0jC 1 1 0.81 L-base:137/163 L-res:398/629 L-sph6:162/214 L-sph8:232/413 L-sph10:326/559 L-core8:137/163 D-base:91/117 D-res:349/528 D-sph6:146/172 D-sph8:213/342 D-sph10:321/554 D-core8:91/117 U-base:91/117 U-res:349/528 U-sph6:146/172 U-sph8:213/342 U-sph10:321/554 U-core8:91/117
(113,) True
tough_m1:1bsvA 3 2 0.78 L-base:742/950 L-res:1340/1725 L-sph6:332/358 L-sph8:580/736 L-sph10:856/1140 L-core8:510/614 D-base:905/1191 D-res:1712/2327 D-sph6:337/415 D-sph8:607/789 D-sph10:882/1244 D-core8:480/636 U-base:585/741 U-res:1222/1734 U-sph6:313/417 U-sph8:547/807 U-sph10:795/1107 U-core8:478/582
(113,) True
tough_m1:2ewsA 1 3 0.22 L-base:518/672 L-res:942/1560 L-sph6:188/188 L-sph8:376/401 L-sph10:606/786 L-core8:343/342 D-base:103/233 D-res:349/607 D-sph6:169/377 D-sph8:282/568 D-sph10:459/899 D-core8:103/233 U-base:103/233 U-res:349/607 U-sph6:169/377 U-sph8:282/568 U-sph10:459/899 U-core8:103/233
(113,) True
```


### Assistant · 2026-10-27 21:08:18

Now the compute script.


**→ tool call `Write`** · 2026-10-27 21:08:43

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/defrob_compute.py", "content": "#!/usr/bin/env python\n\"\"\"Definition-robustness exploration (D11): descriptors of every TOUGH-M1 pocket under ligand-free site shapers.\n\n    python scripts/explore/defrob_compute.py --workers 16          # all 7,524 pockets, label-free\n\nLocators (where the site is):  L = L-mode ligand shell (index ``lmode_idx``);  D = matched merged BURROW pocket\n(``d_members`` union, as in the dev evaluation);  U = the single member of the matched merged pocket with maximal\ncoverage of the L-mode points (unmerged D-mode; same oracle use of the ligand as D).\nShapers (what is described; ``pocketcompare.pockets.shape_site``): base, res, sph6, sph8, sph10, core8.\nDescriptors per (locator, shaper): A1 default (514 dims; blocks sliced at evaluation), B1 (45), env (113,\n``pocketcompare.descriptors.a1r``).  Per-pocket times (ms, one thread, excl. npz I/O) are stored per descriptor\nand for the shaper.\n\nOutput: data/processed/descriptors/tough_m1/defrob/<loc>_<shaper>.npz (a1, b1, env, vol_A3, n_points,\nt_shape, t_a1, t_b1, t_env; rows = index order) + ids.parquet (pocket_id, has_D, U member, U coverage).\n\"\"\"\nfrom __future__ import annotations\n\nimport os\n\nfor _v in (\"OMP_NUM_THREADS\", \"OPENBLAS_NUM_THREADS\", \"MKL_NUM_THREADS\", \"NUMEXPR_NUM_THREADS\"):\n    os.environ[_v] = \"1\"\nos.environ.setdefault(\"NUMBA_CACHE_DIR\", \"/tmp/numba_cache\")\n\nimport argpars
… [5,782 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:08:44

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; time python scripts/explore/defrob_compute.py --workers 16 --limit 64 --chunk 4 && python -c \"\nimport json; d=json.load(open('data/processed/descriptors/tough_m1/defrob/summary.json')); print(d['wall_s'])\nfor k,v in d['sets'].items(): print(k, {a:round(b,1) for a,b in v.items()})\"", "description": "Smoke-run compute on 64 pockets"}
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/defrob_compute.py (file state is current in your context — no need to Read it back)
```


**← tool result**

```
  1/16  2s
  2/16  2s
  3/16  2s
  4/16  2s
  5/16  2s
  6/16  2s
  7/16  2s
  8/16  2s
  9/16  2s
  10/16  2s
  11/16  2s
  12/16  2s
  13/16  2s
  14/16  2s
  15/16  2s
  16/16  2s
done 64 pockets in 2s

real	0m3.115s
user	0m19.669s
sys	0m4.241s
2.3555517196655273
L_base {'n_ok': 64, 'vol_median': 551.5, 't_shape_median_ms': 0.0, 't_a1_median_ms': 6.8, 't_b1_median_ms': 1.4, 't_env_median_ms': 0.2, 't_shape_p90_ms': 0.0, 't_a1_p90_ms': 13.8}
L_res {'n_ok': 64, 'vol_median': 1028.0, 't_shape_median_ms': 1.5, 't_a1_median_ms': 31.3, 't_b1_median_ms': 1.7, 't_env_median_ms': 0.2, 't_shape_p90_ms': 2.1, 't_a1_p90_ms': 47.2}
L_sph6 {'n_ok': 64, 'vol_median': 302.0, 't_shape_median_ms': 0.2, 't_a1_median_ms': 3.5, 't_b1_median_ms': 1.1, 't_env_median_ms': 0.1, 't_shape_p90_ms': 0.3, 't_a1_p90_ms': 4.7}
L_sph8 {'n_ok': 64, 'vol_median': 470.0, 't_shape_median_ms': 0.2, 't_a1_median_ms': 5.3, 't_b1_median_ms': 1.2, 't_env_median_ms': 0.2, 't_shape_p90_ms': 0.3, 't_a1_p90_ms': 8.6}
L_sph10 {'n_ok': 64, 'vol_median': 663.0, 't_shape_median_ms': 0.2, 't_a1_median_ms': 8.6, 't_b1_median_ms': 1.3, 't_env_median_ms': 0.2, 't_shape_p90_ms': 0.3, 't_a1_p90_ms': 15.5}
L_core8 {'n_ok': 64, 'vol_median': 429.5, 't_shape_median_ms': 0.1, 't_a1_median_ms': 4.7, 't_b1_median_ms': 1.0, 't_env_median_ms': 0.1, 't_shape_p90_ms': 0.1, 't_a1_p90_ms': 7.4}
D_base {'n_ok': 64, 'vol_median': 128.0, 't_shape_median_ms': 0.0, 't_a1_median_ms': 2.1, 't_b1_median_ms': 1.0, 't_env_median_ms': 0.1, 't_shape_p
… [2,020 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 21:08:51

Fast. Launching the full run in the background while I write the evaluation script.


**→ tool call `Bash`** · 2026-10-27 21:08:52

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; mkdir -p logs; python scripts/explore/defrob_compute.py --workers 16 > logs/defrob_compute.log 2>&1", "description": "Compute all descriptors for 7,524 pockets", "run_in_background": true}
```


**← tool result**

```
Command running in background with ID: bh7qhvgly. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bh7qhvgly.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
Session cwd remains /cluster/project/beltrao/gmagnus/pocket_compare; directory changes made by the backgrounded command do not apply to subsequent commands.
```


**→ tool call `Bash`** · 2026-10-27 21:09:05

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 240,252p src/pocketcompare/evaluate.py; sed -n 290,346p src/pocketcompare/evaluate.py; sed -n 584,690p src/pocketcompare/evaluate.py", "description": "Read evaluate bootstrap and stratified APIs"}
```


**← tool result**

```
def cluster_balanced_auc(y, s, pos_cluster, w=None, *, neg_cluster=None) -> dict:
    """Cluster-balanced ROC-AUC: each positive cluster has equal total weight (see module docstring).

    ``pos_cluster``: cluster id per pair (only read for positives).  ``neg_cluster``: optional group id per pair,
    read for negatives; if given, each negative group also gets equal total weight."""
    y, s, w = _as_arrays(y, s, w)
    wb, n_pc = _balance(pos_cluster, y, w)
    n_nc = None
    if neg_cluster is not None:
        wb, n_nc = _balance(neg_cluster, ~y, wb)
    return {"auc_cb": roc_auc(y, s, wb), "n_pos_clusters": n_pc, "n_neg_groups": n_nc}


def size_covariates(log_vol_a, log_vol_b) -> np.ndarray:
    """Headline stratification covariates (n x 2): mean log-volume of the pair and |delta log-volume|."""
    a = np.asarray(log_vol_a, dtype=np.float64)
    b = np.asarray(log_vol_b, dtype=np.float64)
    return np.column_stack([0.5 * (a + b), np.abs(a - b)])


def stratified_auc(y, s, covariate, w=None, *, n_bins: int | Sequence[int] = (5, 5),
                   weighting: str = "pos") -> dict:
    """Covariate-stratified ROC-AUC (see module docstring).

    ``covariate``: (n,) or (n, k); ``n_bins``: int (same for every column) or one int per column.  Default:
    5 x 5 strata on :func:`size_covariates`, weights proportional to stratum positive weight.  Returns the
    stratified AUC, the per-stratum table and counts of dropped strata / pairs / positive weight."""
    y, s, w = _as
… [7,984 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 21:09:27

While that runs, the evaluation script.


**→ tool call `Write`** · 2026-10-27 21:10:23

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/defrob_eval.py", "content": "#!/usr/bin/env python\n\"\"\"Definition-robustness exploration (D11): label-free L<->D agreement screen and labelled TOUGH-M1-dev evaluation.\n\n    python scripts/explore/defrob_eval.py screen                      # label-free only (no labels opened)\n    python scripts/explore/defrob_eval.py eval --variants v1,v2 ...   # labelled dev evaluation + trials.tsv rows\n\nInputs: data/processed/descriptors/tough_m1/defrob/*.npz (scripts/explore/defrob_compute.py).  Pairs, units,\npositive clusters, size covariates and the D-set exactly as scripts/eval_dev.py (imported, not copied).\n\nFixed before the labelled run:\n* a variant = list of parts (source a1|b1|env, block subset, L-mode set, D-mode set, weight).  One part -> cosine of\n  the z-scored vector (as eval_dev).  Several parts -> each part z-scored and L2-normalised separately, weighted\n  block cosine sum_b w_b cos_b / sum_b w_b (= FAISS-IP compatible concatenation).\n* z-scoring: per mode, on the dev pockets available in that mode (label-free), as eval_dev.\n* L-mode metrics on all dev pairs; D-mode on the D-set (both pockets D-matched: coverage >= 0.3 or precision >= 0.5,\n  the merged-pocket rule, also used for the unmerged locator U).  Objective = mean of the two cluster-balanced AUCs;\n  guard = size-stratified AUC (L-mode log-volume covariates, (5, 20) bins) per mode.\n* Joint vertex bootstrap (units = ligand cl
… [14,002 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:10:24

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 20,60p src/pocketcompare/similarity.py; cat logs/defrob_compute.log | tail -3", "description": "Check ZScorer API and compute progress"}
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/defrob_eval.py (file state is current in your context — no need to Read it back)
```


**← tool result**

```
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
            if ids is None:
                raise ValueError("ids are needed to select ref_ids")
            m = np.isin(np.asarray(ids), np.asarray(ref_ids))
            if not m.any():
                raise ValueError("no reference rows")
            D = D[m]
        mean = np.nanmean(D, 0)
        std = np.nanstd(D, 0)
        std = np.where(std > EPS_STD * np.maximum(1.0, np.abs(mean)), std, 0.0)
        return cls(mean=mean, std=std, n_ref=int(len(D)), clip=clip)

    def transform(self, D) -> np.ndarray:
        D = np.asarray(D, np.float64)
        ok = self.std > 0
        Z = np.zeros_like(D)
        Z[:, ok] = (D[:, ok] - self.mean[ok]) / self.std[ok]
        Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
        if self.clip is not None:
            np.clip(Z, -self.clip, self.clip, out=Z)
        return Z


def l2_normalise(Z) -> np.ndarray:
    Z = np.asarray(Z, np.float64)
    n = np.linalg.norm(Z, axis=1, keepdims=True)
    return np.w
… [90 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:10:47

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; python - <<'EOF'\nimport re\np='scripts/explore/defrob_eval.py'; s=open(p).read()\ns=s.replace(\"\"\"        zs = ZScorer.fit(M[fit_rows])\n        Z = zs.transform(M) if hasattr(zs, \"transform\") else (M - zs.mean) / zs.scale\n        Z = np.nan_to_num(Z)\n\"\"\",\"\"\"        Z = ZScorer.fit(M[fit_rows]).transform(M)\n\"\"\")\nopen(p,'w').write(s)\nEOF\ncat > tests/test_a1r.py <<'EOF'\n\"\"\"Ligand-free site shapers (pockets.shape_site & co.) and the A1r env block: invariances (D11 exploration).\n\nUses BURROW's example 1a28_A.pdb + crystal progesterone as tests/test_pockets.py; a rigidly moved in-memory copy\nmust give the same site (shapers) and the same descriptor (env, A1 on the shaped site).\"\"\"\nimport dataclasses\nimport os\nfrom pathlib import Path\n\nimport numpy as np\nimport pytest\n\nos.environ.setdefault(\"NUMBA_CACHE_DIR\", \"/tmp/numba_cache\")\nfrom scipy.spatial import cKDTree  # noqa: E402\nfrom scipy.spatial.transform import Rotation  # noqa: E402\n\npk = pytest.importorskip(\"pocketcompare.pockets\")\nfrom pocketcompare.descriptors import a1 as A1  # noqa: E402\nfrom pocketcompare.descriptors import a1r  # noqa: E402\n\nPD = Path(\"/cluster/project/beltrao/gmagnus/pocket_detect\")\nEX = PD / \"release/burrow/examples/1a28_A.pdb\"\nMIRROR_1A28 = Path(\"/cluster/scratch/jjaenes/pdb/a2/1a28.cif.gz\")\nneed = pytest.mark.skipif(not (EX.exists() and MIRROR_1A28.exists()), reason=\"1a28 inputs
… [3,640 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
  752/941  108s
  799/941  113s
```


**→ tool call `Bash`** · 2026-10-27 21:10:51

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; timeout 600 python -m pytest -q tests/test_a1r.py 2>&1 | tail -8", "description": "Run new invariance tests"}
```


**← tool result**

```
..........                                                               [100%]
10 passed in 4.97s
```


**→ tool call `Bash`** · 2026-10-27 21:11:01

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; tail -2 logs/defrob_compute.log; ls data/processed/descriptors/tough_m1/defrob/ | head; ", "description": "Check compute completion"}
```


**← tool result**

```
  846/941  118s
  893/941  125s
D_base.npz
D_core8.npz
D_res.npz
D_sph10.npz
D_sph6.npz
D_sph8.npz
L_base.npz
L_core8.npz
L_res.npz
L_sph10.npz
```


**→ tool call `Bash`** · 2026-10-27 21:11:05

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sleep 45; tail -2 logs/defrob_compute.log", "description": "Wait briefly for compute to finish"}
```


**← tool result**

```
  940/941  132s
done 7524 pockets in 134s
```


### Assistant · 2026-10-27 21:11:53

Compute done (134 s for 7,524 pockets × 18 sets). Running the label-free screen.


**→ tool call `Bash`** · 2026-10-27 21:11:54

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; python -c \"\nimport json; d=json.load(open('data/processed/descriptors/tough_m1/defrob/summary.json')); print(d['n'], d['wall_s'])\nfor k,v in d['sets'].items(): print(k, {a:round(b,1) for a,b in v.items()})\"; python scripts/explore/defrob_eval.py screen 2>&1 | tail -30", "description": "Run label-free L-D agreement screen"}
```


**← tool result**

```
7524 133.70198011398315
L_base {'n_ok': 7524, 'vol_median': 542.0, 't_shape_median_ms': 0.0, 't_a1_median_ms': 6.9, 't_b1_median_ms': 1.9, 't_env_median_ms': 0.2, 't_shape_p90_ms': 0.0, 't_a1_p90_ms': 17.2}
L_res {'n_ok': 7524, 'vol_median': 1056.5, 't_shape_median_ms': 1.6, 't_a1_median_ms': 29.4, 't_b1_median_ms': 2.3, 't_env_median_ms': 0.3, 't_shape_p90_ms': 2.6, 't_a1_p90_ms': 76.2}
L_sph6 {'n_ok': 7524, 'vol_median': 305.0, 't_shape_median_ms': 0.2, 't_a1_median_ms': 3.8, 't_b1_median_ms': 1.5, 't_env_median_ms': 0.2, 't_shape_p90_ms': 0.4, 't_a1_p90_ms': 5.3}
L_sph8 {'n_ok': 7524, 'vol_median': 486.0, 't_shape_median_ms': 0.2, 't_a1_median_ms': 6.2, 't_b1_median_ms': 1.7, 't_env_median_ms': 0.2, 't_shape_p90_ms': 0.4, 't_a1_p90_ms': 10.1}
L_sph10 {'n_ok': 7524, 'vol_median': 694.0, 't_shape_median_ms': 0.2, 't_a1_median_ms': 10.3, 't_b1_median_ms': 2.0, 't_env_median_ms': 0.2, 't_shape_p90_ms': 0.4, 't_a1_p90_ms': 18.5}
L_core8 {'n_ok': 7524, 'vol_median': 448.0, 't_shape_median_ms': 0.1, 't_a1_median_ms': 5.3, 't_b1_median_ms': 1.6, 't_env_median_ms': 0.2, 't_shape_p90_ms': 0.2, 't_a1_p90_ms': 8.3}
D_base {'n_ok': 7434, 'vol_median': 146.0, 't_shape_median_ms': 0.0, 't_a1_median_ms': 2.7, 't_b1_median_ms': 1.6, 't_env_median_ms': 0.1, 't_shape_p90_ms': 0.0, 't_a1_p90_ms': 15.9}
D_res {'n_ok': 7461, 'vol_median': 733.0, 't_shape_median_ms': 1.4, 't_a1_median_ms': 16.2, 't_b1_median_ms': 2.2, 't_env_median_ms': 0.3, 't_shape_p90_ms': 2.8, 't_a1_p90_ms': 122.4}
D_sph6 {'
… [4,835 more characters; full text in agent_logs/raw/]
```


<details><summary>thinking · 2026-10-27 21:12:21</summary>

Found a clear pattern: sphere/residue shapers and env/B1 blocks match much better across L↔D than the void blocks do under the base definition, with U ≥ D holding everywhere. Moving on to labelled batch 1, covering the definition sweep and blocks.



</details>


**→ tool call `Bash`** · 2026-10-27 21:12:22

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; V=\"a1pair@base,a1@base,b1@base,env@base,a1@baseU,a1@resU,a1@sph6U,a1@sph8U,a1@sph10U,a1@core8U,a1pair@sph8U,a1hist@sph8U,b1@baseU,b1@resU,b1@sph8U,env@baseU,env@resU,env@sph8U,env@sph10U\"; time python scripts/explore/defrob_eval.py eval --tag batch1 --variants $V 2>&1 | tail -25", "description": "Labelled dev evaluation, batch 1 (19 variants)", "timeout": 1200000}
```


**← tool result**

```
bootstrap 19 variants in 66s
     variant  dims  cb_L  cb_D  cb_mean  cb_mean_lo  cb_mean_hi  d_cb_mean_vs_ref  d_cb_mean_vs_ref_lo  d_cb_mean_vs_ref_hi  strat_L  strat_D  agree_auc   ms_L   ms_D
 a1pair@base   392 0.798 0.522    0.660       0.637       0.738             0.000                0.000                0.000    0.732    0.558      0.765  6.504  2.395
     a1@base   514 0.794 0.528    0.661       0.638       0.741             0.001               -0.004                0.010    0.732    0.553      0.777  6.504  2.395
     b1@base    45 0.632 0.599    0.616       0.566       0.676            -0.045               -0.111               -0.025    0.630    0.611      0.951  1.827  1.504
    env@base   113 0.661 0.603    0.632       0.592       0.695            -0.028               -0.096               -0.007    0.650    0.627      0.977  0.183  0.132
    a1@baseU   514 0.794 0.540    0.667       0.645       0.734             0.007               -0.033                0.026    0.732    0.584      0.804  6.504  2.178
     a1@resU   514 0.657 0.580    0.619       0.579       0.673            -0.041               -0.105               -0.021    0.666    0.624      0.937 23.228 13.173
    a1@sph6U   514 0.642 0.635    0.639       0.600       0.715            -0.021               -0.075                0.008    0.666    0.630      0.944  3.722  3.460
    a1@sph8U   514 0.626 0.642    0.634       0.601       0.728            -0.026               -0.074                0.024    0.655   
… [1,912 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 21:13:47

L-mode numbers reproduce the dev summary exactly, but D-mode is ~0.02 lower for all three reference arms. Checking why before going on.


**→ tool call `Bash`** · 2026-10-27 21:13:50

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python -c \"\nimport pandas as pd, numpy as np\nd='data/processed/descriptors/tough_m1/'\niL=pd.read_parquet(d+'a1_default_L.ids.parquet'); iD=pd.read_parquet(d+'a1_default_D.ids.parquet')\nprint(len(iL),len(iD), (iL.pocket_id.values[:len(iD)]==iD.pocket_id.values).mean())\nids=pd.read_parquet(d+'defrob/ids.parquet'); print((ids.pocket_id.values==iL.pocket_id.values).mean())\nB=np.load(d+'b1_default_D.npy'); z=np.load(d+'defrob/D_base.npz')['b1']\npos=pd.Series(np.arange(len(iD)),index=iD.pocket_id)\nr=pos.loc[ids.pocket_id[ids.has_D]].values\nprint(np.nanmax(np.abs(B[r]-z[ids.has_D.values])))\n# eval_dev style indexing\nprint(np.nanmax(np.abs(B[np.arange(len(iD))]-z[:len(iD)])))\n\"\n", "description": "Check D-mode row alignment in eval_dev"}
```


**← tool result**

```
7524 7524 1.0
1.0
0.0
0.0
```


**→ tool call `Bash`** · 2026-10-27 21:14:02

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; python - <<'EOF' 2>&1 | grep -v Warn\nimport sys; sys.path[:0]=['scripts','scripts/explore','src']\nimport numpy as np, pandas as pd\nimport eval_dev as E, defrob_eval as R\nfrom pocketcompare import evaluate as ev\nds,rows=R.setup(); P=ds.pockets; dm=P.d_match.to_numpy(); dset=dm[ds.ia]&dm[ds.ib]; y=ds.pairs.y.to_numpy().astype(bool)\nM,_=ds.descriptor('b1','default','D')\nraw,_=E.cosine_vectors(M,dm,ds.ia,ds.ib,csls=False)\nm=dset&~np.isnan(raw); print('evaldev-style', m.sum(), ev.cluster_balanced_auc(y[m],raw[m],ds.pos_cluster[m])['auc_cb'])\ns,ok,_=R.mode_scores(R.variant_parts('b1@base'),'D',ds,rows,dm)\nprint('mine', np.isnan(s[dset]).sum(), ev.cluster_balanced_auc(y[dset],s[dset],ds.pos_cluster[dset])['auc_cb'])\nprint(np.nanmax(np.abs(s[m]-raw[m])))\nMd=R.part_matrix(R.variant_parts('b1@base')[0],'D',rows)\nprint(np.nanmax(np.abs(Md-M)), np.isnan(M[dm]).sum(), np.isnan(Md[dm]).sum())\nEOF", "description": "Compare eval_dev D scoring with mine for B1"}
```


**← tool result**

```
evaldev-style 7866 0.6197170094113911
Traceback (most recent call last):
  File "<stdin>", line 10, in <module>
  File "/cluster/project/beltrao/gmagnus/pocket_compare/src/pocketcompare/evaluate.py", line 245, in cluster_balanced_auc
    y, s, w = _as_arrays(y, s, w)
              ^^^^^^^^^^^^^^^^^^^
  File "/cluster/project/beltrao/gmagnus/pocket_compare/src/pocketcompare/evaluate.py", line 124, in _as_arrays
    raise ValueError(f"{int(np.isnan(s).sum())} NaN scores: choose a missing-score policy "
ValueError: 31 NaN scores: choose a missing-score policy (common_set / worst_case / min_impute) instead of dropping silently
```


<details><summary>thinking · 2026-10-27 21:14:11</summary>

Found the discrepancy: eval_dev treats partial-NaN rows as 0 after z-scoring, while I had dropped them entirely. I'll align with eval_dev's rule, treating "available" as any non-empty set.



</details>


**→ tool call `Bash`** · 2026-10-27 21:14:12

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'EOF'\np='scripts/explore/defrob_eval.py'; s=open(p).read()\nn=s.count(\"ok &= np.isfinite(M).all(1)\")\ns=s.replace(\"ok &= np.isfinite(M).all(1)\",\"ok &= np.isfinite(M).any(1)   # partial NaN -> 0 after z-scoring (as eval_dev)\")\nopen(p,'w').write(s); print(n)\nEOF\npython -c \"\nimport numpy as np\nfor f in ['D_base','L_base','D_sph8','U_sph8','L_sph8']:\n  z=np.load('data/processed/descriptors/tough_m1/defrob/'+f+'.npz')\n  for k in ['a1','b1','env']:\n    M=z[k]; print(f,k,'partial-nan rows',int((np.isnan(M).any(1)&~np.isnan(M).all(1)).sum()), 'all-nan',int(np.isnan(M).all(1).sum()))\n\"", "description": "Fix availability rule and count partial-NaN rows"}
```


**← tool result**

```
2
D_base a1 partial-nan rows 0 all-nan 90
D_base b1 partial-nan rows 0 all-nan 90
D_base env partial-nan rows 0 all-nan 90
L_base a1 partial-nan rows 0 all-nan 0
L_base b1 partial-nan rows 0 all-nan 0
L_base env partial-nan rows 0 all-nan 0
D_sph8 a1 partial-nan rows 0 all-nan 0
D_sph8 b1 partial-nan rows 0 all-nan 0
D_sph8 env partial-nan rows 0 all-nan 0
U_sph8 a1 partial-nan rows 0 all-nan 0
U_sph8 b1 partial-nan rows 0 all-nan 0
U_sph8 env partial-nan rows 0 all-nan 0
L_sph8 a1 partial-nan rows 0 all-nan 0
L_sph8 b1 partial-nan rows 0 all-nan 0
L_sph8 env partial-nan rows 0 all-nan 0
```


**→ tool call `Bash`** · 2026-10-27 21:14:22

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; python - <<'EOF' 2>&1 | grep -v Warn\nimport sys; sys.path[:0]=['scripts','scripts/explore','src']\nimport numpy as np, pandas as pd\nimport eval_dev as E, defrob_eval as R\nds,rows=R.setup(); P=ds.pockets; dm=P.d_match.to_numpy()\nM,_=ds.descriptor('b1','default','D')\nMd=R.part_matrix(R.variant_parts('b1@base')[0],'D',rows)\nbad=dm & np.isnan(Md).all(1); print(bad.sum(), np.isnan(M[bad]).all(1).sum())\nix=pd.read_parquet('data/processed/cache/points/tough_m1/index.parquet').set_index('pocket_id')\nprint(ix.loc[P.pocket_id[bad], ['d_members','d_coverage','d_precision','d_n_points']].head())\nids=pd.read_parquet('data/processed/descriptors/tough_m1/defrob/ids.parquet').set_index('pocket_id'); print(ids.loc[P.pocket_id[bad]].head())\nEOF", "description": "Debug NaN D rows for matched pockets"}
```


**← tool result**

```
6 0
               d_members  d_coverage  d_precision  d_n_points
pocket_id                                                    
tough_m1:2a6cB       [1]    0.026316          1.0           1
tough_m1:2i22C       [2]    0.035088          1.0           1
tough_m1:2jdmC       [0]    0.009709          1.0           1
tough_m1:2xwqA       [0]    0.010417          1.0           1
tough_m1:3h7qA       [0]    0.025641          1.0           1
                has_D  u_member  u_coverage
pocket_id                                  
tough_m1:2a6cB   True         1    0.026316
tough_m1:2i22C   True         2    0.035088
tough_m1:2jdmC   True         0    0.009709
tough_m1:2xwqA   True         0    0.010417
tough_m1:3h7qA   True         0    0.025641
```


<details><summary>thinking · 2026-10-27 21:14:33</summary>

Six dev pockets matched to a metal-candidate point got skipped in my compute even though eval_dev assigns them a descriptor. I'll fix this by applying metal_weight 1 in env and computing whenever the set is non-empty, then rerun.



</details>


**→ tool call `Bash`** · 2026-10-27 21:14:37

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; python - <<'EOF'\np='src/pocketcompare/descriptors/a1r.py'; s=open(p).read()\ns=s.replace('''    \"\"\"(113,) float32 env vector of point indices ``idx`` of a Featurized-like object (feats, feature_names, vol,\n    is_metal).  Metal candidates (vol 0) carry no weight.\"\"\"''','''    \"\"\"(113,) float32 env vector of point indices ``idx`` of a Featurized-like object (feats, feature_names, vol,\n    is_metal).  Metal candidates (vol 0) get weight 1 voxel (as A1's ``metal_weight``).\"\"\"''')\ns=s.replace('''    w = np.asarray(fs.vol[idx], np.float64)\n    W = w.sum()''','''    w = np.where(np.asarray(fs.is_metal[idx], bool), 1.0, np.asarray(fs.vol[idx], np.float64))\n    W = w.sum()''')\nopen(p,'w').write(s)\np='scripts/explore/defrob_compute.py'; s=open(p).read()\ns=s.replace(\"if len(I) == 0 or fs.vol[I].sum() <= 0:\",\"if len(I) == 0:\")\nopen(p,'w').write(s)\nEOF\ngrep -n \"is_metal\\|len(I) == 0\" src/pocketcompare/descriptors/a1r.py scripts/explore/defrob_compute.py; python scripts/explore/defrob_compute.py --workers 16 > logs/defrob_compute.log 2>&1; tail -1 logs/defrob_compute.log; python -m pytest -q tests/test_a1r.py 2>&1 | tail -1", "description": "Fix metal-only pockets, recompute, retest", "timeout": 600000}
```


**← tool result**

```
scripts/explore/defrob_compute.py:74:                if len(I) == 0:
src/pocketcompare/descriptors/a1r.py:47:    is_metal).  Metal candidates (vol 0) get weight 1 voxel (as A1's ``metal_weight``)."""
src/pocketcompare/descriptors/a1r.py:52:    w = np.where(np.asarray(fs.is_metal[idx], bool), 1.0, np.asarray(fs.vol[idx], np.float64))
done 7524 pockets in 106s
10 passed in 3.46s
```


**→ tool call `Bash`** · 2026-10-27 21:16:33

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; python scripts/explore/defrob_eval.py screen > logs/defrob_screen.log 2>&1; tail -14 logs/defrob_screen.log; V=\"a1pair@base,a1@base,b1@base,env@base,a1@baseU,a1@resU,a1@sph6U,a1@sph8U,a1@sph10U,a1@core8U,a1pair@sph8U,a1hist@sph8U,b1@baseU,b1@resU,b1@sph8U,env@baseU,env@resU,env@sph8U,env@sph10U\"; python scripts/explore/defrob_eval.py eval --tag batch1fix --variants $V 2>&1 | tail -21", "description": "Re-run screen and batch 1 after the fix", "timeout": 1200000}
```


**← tool result**

```
desc       a1  a1glob  a1hist  a1nosize  a1pair  a1usr     b1    env  envbur  envhist  envmean
def                                                                                           
base    0.777   0.649   0.835     0.778   0.765  0.653  0.949  0.976   0.985    0.763    0.963
baseU   0.804   0.686   0.867     0.804   0.790  0.677  0.962  0.982   0.988    0.794    0.970
core8   0.804   0.693   0.879     0.805   0.797  0.673  0.958  0.979   0.982    0.812    0.973
core8U  0.816   0.705   0.883     0.817   0.809  0.671  0.967  0.985   0.987    0.816    0.979
res     0.931   0.836   0.974     0.931   0.925  0.780  0.994  0.997   0.998    0.952    0.993
resU    0.937   0.845   0.983     0.937   0.930  0.796  0.996  0.998   0.998    0.962    0.996
sph10   0.976   0.915   0.984     0.976   0.971  0.870  0.993  0.996   0.996    0.971    0.994
sph10U  0.981   0.925   0.990     0.981   0.976  0.885  0.998  0.999   0.999    0.978    0.998
sph6    0.932   0.850   0.952     0.932   0.916  0.832  0.975  0.987   0.987    0.922    0.985
sph6U   0.944   0.861   0.962     0.944   0.929  0.842  0.985  0.994   0.994    0.930    0.992
sph8    0.956   0.888   0.972     0.956   0.946  0.849  0.986  0.991   0.993    0.952    0.990
sph8U   0.966   0.895   0.979     0.966   0.957  0.857  0.995  0.997   0.998    0.956    0.996
bootstrap 19 variants in 63s
     variant  dims  cb_L  cb_D  cb_mean  cb_mean_lo  cb_mean_hi  d_cb_mean_vs_ref  d_cb_mean_vs_ref_lo  d_cb_mean_vs_ref_hi  strat_L  strat_D
… [3,198 more characters; full text in agent_logs/raw/]
```


<details><summary>thinking · 2026-10-27 21:18:10</summary>

The dev summary matches exactly (A1 0.798/0.541, B1 0.632/0.620), confirming the robust definitions boost D-mode and the stratified guard at the cost of the L-mode imprint; batch1 trial rows remain superseded in trials.tsv. Next I'll run batch 2 to test combinations and env block/centre checks.



</details>


**→ tool call `Bash`** · 2026-10-27 21:18:11

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; V=\"a1pair@base+env@sph8U,a1@baseU+env@sph8U,a1@sph8U+env@sph8U,a1@sph6U+env@sph8U,env@sph8U+b1@sph8U,a1@sph8U+env@sph8U+b1@sph8U,a1@baseU+env@sph8U+b1@sph8U,a1@core8U+env@sph8U,env@sph8,envbur@sph8U,envmean@sph8U,env@sph6U\"; python scripts/explore/defrob_eval.py eval --tag batch2 --skip-ref-trial --variants $V 2>&1 | tail -14", "description": "Labelled dev evaluation, batch 2 (12 variants)", "timeout": 1200000}
```


**← tool result**

```
                    variant  dims  cb_L  cb_D  cb_mean  cb_mean_lo  cb_mean_hi  d_cb_mean_vs_ref  d_cb_mean_vs_ref_lo  d_cb_mean_vs_ref_hi  strat_L  strat_D  agree_auc  ms_L  ms_D
                a1pair@base   392 0.798 0.541    0.670       0.646       0.742             0.000                0.000                0.000    0.732    0.564      0.765 5.670 2.100
      a1pair@base+env@sph8U   505 0.762 0.616    0.689       0.653       0.751             0.019               -0.030                0.033    0.732    0.631      0.970 6.092 2.467
         a1@baseU+env@sph8U   627 0.756 0.631    0.693       0.649       0.750             0.024               -0.039                0.043    0.729    0.650      0.982 6.092 2.331
         a1@sph8U+env@sph8U   627 0.648 0.672    0.660       0.612       0.726            -0.010               -0.083                0.018    0.681    0.669      0.996 5.205 4.904
         a1@sph6U+env@sph8U   627 0.655 0.669    0.662       0.609       0.721            -0.008               -0.081                0.014    0.687    0.665      0.992 3.790 3.518
         env@sph8U+b1@sph8U   158 0.642 0.659    0.650       0.597       0.704            -0.019               -0.109                0.007    0.664    0.658      0.997 1.535 1.501
a1@sph8U+env@sph8U+b1@sph8U   672 0.648 0.671    0.659       0.615       0.723            -0.011               -0.083                0.015    0.674    0.665      0.997 6.433 6.118
a1@baseU+env@sph8U+b1@sph8U   672 0.719 0.650    0.684      
… [1,019 more characters; full text in agent_logs/raw/]
```


<details><summary>thinking · 2026-10-27 21:19:13</summary>

The fully robust setup edges out on D-mode and L↔D agreement, while the hybrid wins on mean cb but retains the ligand-imprinted void. I'll run a final cross-mode batch scoring the L-defined query against the D-defined target to mimic real deployment and settle the trade-off.



</details>


**→ tool call `Bash`** · 2026-10-27 21:19:28

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'EOF'\np='scripts/explore/defrob_eval.py'; s=open(p).read()\n# cross-mode scores\ns=s.replace('''def agreement(parts, rows, dm):''','''def cross_scores(parts, ds, rows, dm):\n    \"\"\"Cross-mode pair score 0.5 * (cos(L_a, D_b) + cos(D_a, L_b)); parts z-scored on the union of the L rows and\n    the D rows of the dev pockets (as ``agreement``).  NaN unless both pockets are D-matched.\"\"\"\n    mL = [part_matrix(p, \"L\", rows) for p in parts]\n    mD = [part_matrix(p, \"D\", rows) for p in parts]\n    ok = dm.copy()\n    for M in mL + mD:\n        ok &= np.isfinite(M).any(1)\n    n = len(rows)\n    fit = np.concatenate([np.flatnonzero(ok), n + np.flatnonzero(ok)])\n    E = embed_parts([np.concatenate([a, b]) for a, b in zip(mL, mD)], [p[\"w\"] for p in parts], fit)\n    EL, ED = E[:n], E[n:]\n    s = np.full(len(ds.ia), np.nan)\n    m = ok[ds.ia] & ok[ds.ib]\n    a, b = ds.ia[m], ds.ib[m]\n    s[m] = 0.5 * ((EL[a] * ED[b]).sum(1) + (ED[a] * EL[b]).sum(1))\n    return s\n\n\ndef agreement(parts, rows, dm):''')\ns=s.replace('''    key, y, sL, sD, rL, rD, dset, pc, cov, ci, cj, B, seed = a''','''    key, y, sL, sD, rL, rD, dset, pc, cov, ci, cj, B, seed, sX = a''')\ns=s.replace('''        return [cbL, cbD, 0.5 * (cbL + cbD), stL, stD, 0.5 * (stL + stD), 0.5 * (cbL + cbD) - 0.5 * (r[0] + r[1]),\n                0.5 * (stL + stD) - 0.5 * (r[2] + r[3])]\n\n    names = [\"cb_L\", 
… [3,547 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
140:def cross_scores(parts, ds, rows, dm):
226:    key, y, sL, sD, rL, rD, dset, pc, cov, ci, cj, B, seed, sX = a
241:        if sX is not None:
242:            out += [ev.cluster_balanced_auc(y[dset], sX[dset], pc[dset], w[dset])["auc_cb"],
243:                    ev.stratified_auc(y[dset], sX[dset], cov[dset], w[dset], n_bins=nb_D)["auc_strat"]]
247:    if sX is not None:
288:        sX = None
289:        if args.cross:
290:            sX = cross_scores(parts, ds, rows, dm)
291:            sX = np.where(dset, np.nan_to_num(sX, nan=np.nanmin(sX[dset])), np.nan)
293:                sX)
301:    for v, (sL, sD, dim, parts, sX) in S.items():
324:            for mode in (("L", "D", "X") if args.cross else ("L", "D")):
327:                                                 "pairset": "D-set, cross-mode 0.5*(cos(L_a,D_b)+cos(D_a,L_b))",
361:    e.add_argument("--cross", action="store_true", help="also cross-mode (L query vs D target) metrics on the D-set")
```


**→ tool call `Bash`** · 2026-10-27 21:19:39

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'EOF'\np='scripts/explore/defrob_eval.py'; s=open(p).read()\ns=s.replace('''        rec = {\"variant\": v, \"dims\": dim, \"strat_mean_pt\": None,''','''        rec = {\"variant\": v, \"dims\": dim,''')\ns=s.replace('''            for mode in ((\"L\", \"D\", \"X\") if args.cross else (\"L\", \"D\")):''','''            for mode in ((\"L\", \"D\", \"X\") if args.cross else (\"L\", \"D\")):\n                if mode != \"X\" and r[\"variant\"] in logged:\n                    continue           # L/D already logged in an earlier batch (identical numbers); log X only''')\ns=s.replace('''    if not args.no_trials:\n        for r in recs:''','''    logged = set(args.logged.split(\",\")) if args.logged else set()\n    if not args.no_trials:\n        for r in recs:''')\ns=s.replace('''    e.add_argument(\"--cross\", action=\"store_true\",''','''    e.add_argument(\"--logged\", default=\"\", help=\"variants whose L/D rows were logged earlier (log X rows only)\")\n    e.add_argument(\"--cross\", action=\"store_true\",''')\nopen(p,'w').write(s)\nEOF\nexport NUMBA_CACHE_DIR=/tmp/numba_cache\nOLD=\"a1@base,b1@base,env@sph8U,b1@sph8U,a1@baseU+env@sph8U,a1@sph8U+env@sph8U,a1@core8U+env@sph8U\"\nNEW=\"a1@sph8U+env@sph8U*2,a1@baseU*0.5+env@sph8U,a1@baseU+a1@sph8U+env@sph8U,a1@sph8+env@sph8\"\npython scripts/explore/defrob_eval.py eval --tag final_cross --cross --logged \"a1pair@base,$OLD\" --v
… [112 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
bootstrap 12 variants in 40s
                    variant  dims  cb_L  cb_D  cb_mean  cb_mean_lo  cb_mean_hi  d_cb_mean_vs_ref  d_cb_mean_vs_ref_lo  d_cb_mean_vs_ref_hi  strat_L  strat_D  agree_auc   ms_L  ms_D  cb_X  strat_X
                a1pair@base   392 0.798 0.541    0.670       0.646       0.742             0.000                0.000                0.000    0.732    0.564      0.765  5.670 2.100 0.647    0.651
                    a1@base   514 0.794 0.549    0.672       0.648       0.747             0.002               -0.003                0.009    0.732    0.560      0.777  5.670 2.100 0.664    0.652
                    b1@base    45 0.632 0.620    0.626       0.578       0.679            -0.044               -0.114               -0.023    0.630    0.614      0.949  1.325 1.083 0.662    0.650
                  env@sph8U   113 0.637 0.655    0.646       0.580       0.694            -0.024               -0.121                0.001    0.669    0.664      0.997  0.332 0.323 0.660    0.681
                   b1@sph8U    45 0.637 0.654    0.646       0.606       0.704            -0.024               -0.097                0.006    0.650    0.646      0.995  1.380 1.342 0.662    0.666
         a1@baseU+env@sph8U   627 0.756 0.631    0.693       0.649       0.750             0.024               -0.039                0.043    0.729    0.650      0.982  6.092 2.331 0.726    0.706
         a1@sph8U+env@sph8U   627 0.648 0.672    0.660       0.612       0.726            -0.010   
… [1,076 more characters; full text in agent_logs/raw/]
```


<details><summary>thinking · 2026-10-27 21:20:42</summary>

The hybrid A1(base)+env(sph8) leads on the amended objective, stratified-mean, and cross-mode, while fully robust A1(sph8)+env(sph8) is best for D-only, though all Δ CIs include 0 given the giant unit. I'll use remaining time to check item 1c: set-to-set best-match over BURROW sub-pockets, eliminating the oracle choice of U.



</details>


**→ tool call `Bash`** · 2026-10-27 21:20:42

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python -c \"\nimport pandas as pd, numpy as np\nix=pd.read_parquet('data/processed/cache/points/tough_m1/index.parquet')\nsp=pd.read_parquet('data/splits/tough_m1_pockets_split.parquet'); dev=set(sp.pocket_id[sp.partition=='dev'])\nd=ix[ix.pocket_id.isin(dev)]; n=d.d_members.map(lambda m: 0 if m is None else len(m)); print(n.value_counts().sort_index())\n\"", "description": "Members per matched merged pocket on dev"}
```


**← tool result**

```
d_members
1     570
2     110
3      37
4       9
5       1
6       2
7       1
10      1
Name: count, dtype: int64
```


### Assistant · 2026-10-27 21:20:53

78 % of matched dev pockets have a single member, so set-matching can only change the other 22 %. It is cheap, so I'll test one variant.


**→ tool call `Write`** · 2026-10-27 21:21:21

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/defrob_setmatch.py", "content": "#!/usr/bin/env python\n\"\"\"D11 exploration, item 1c: set-to-set best-match over BURROW sub-pockets (no oracle choice of one member).\n\n    python scripts/explore/defrob_setmatch.py compute --workers 16     # label-free, all 7,524 pockets\n    python scripts/explore/defrob_setmatch.py eval                     # one labelled variant -> trials.tsv\n\nD-mode site of a pocket = the SET of members of its matched merged BURROW pocket, each described by\nA1 + env on the sph8 shaper around that member (as the 'sph8U' definition, but for every member).  D-mode pair\nscore = max over member pairs of the block cosine (A1 and env z-scored separately on the dev member rows, weights\n1:1).  L-mode = the single L_sph8 site (identical to variant a1@sph8U+env@sph8U).  Agreement: own D set among all\nmatched dev pockets' D sets scored by max_k cos(L_i, member_jk) on the union z-scoring.\n\"\"\"\nfrom __future__ import annotations\n\nimport os\n\nfor _v in (\"OMP_NUM_THREADS\", \"OPENBLAS_NUM_THREADS\", \"MKL_NUM_THREADS\"):\n    os.environ[_v] = \"1\"\nos.environ.setdefault(\"NUMBA_CACHE_DIR\", \"/tmp/numba_cache\")\n\nimport argparse  # noqa: E402\nimport sys  # noqa: E402\nimport time  # noqa: E402\nfrom multiprocessing import get_context  # noqa: E402\nfrom pathlib import Path  # noqa: E402\n\nimport numpy as np  # noqa: E402\nimport pandas as pd  # noqa: E402\n\nROOT = Path(__f
… [6,335 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:21:23

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; time python scripts/explore/defrob_setmatch.py compute --workers 16 && python scripts/explore/defrob_setmatch.py eval 2>&1 | grep -v \"_lo\\|_hi\" | tail -25", "description": "Compute and evaluate set-to-set sub-pocket matching", "timeout": 1800000}
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/explore/defrob_setmatch.py (file state is current in your context — no need to Read it back)
```


**← tool result**

```
11358 member sites

real	0m10.507s
user	2m16.061s
sys	0m9.024s
variant                   a1@sph8S+env@sph8S (set max)
dims                                               627
agree_auc                                     0.994743
n_member_sites                                     879
ms_member_median                               5.55289
auc_L                                         0.680743
auc_D                                         0.664335
cb_L                                          0.647536
cb_D                                          0.663335
cb_mean                                       0.655436
strat_L                                       0.680744
strat_D                                       0.666703
strat_mean                                    0.673724
d_cb_mean_vs_ref                             -0.014334
d_strat_mean_vs_ref                           0.025703
```


### Assistant · 2026-10-27 21:22:12

Set-max over sub-pockets (no oracle) gives D cb 0.663: between the oracle-chosen single member (0.672) and the merged-pocket centre (0.652). Now consolidating all results.


**→ tool call `Bash`** · 2026-10-27 21:22:15

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'EOF'\nimport pandas as pd, numpy as np\nd='results/explore/definition_robustness/'\ndfs=[pd.read_parquet(d+f'eval_{t}.parquet').assign(batch=t) for t in ['batch1fix','batch2','final_cross','setmatch']]\ndf=pd.concat(dfs).drop_duplicates('variant',keep='last')\ncols=['variant','dims','cb_L','cb_D','cb_mean','cb_mean_lo','cb_mean_hi','d_cb_mean_vs_ref','d_cb_mean_vs_ref_lo','d_cb_mean_vs_ref_hi','strat_L','strat_D','strat_mean','d_strat_mean_vs_ref','d_strat_mean_vs_ref_lo','d_strat_mean_vs_ref_hi','cb_X','strat_X','agree_auc','ms_L','ms_D']\npd.set_option('display.width',300); pd.set_option('display.max_columns',40)\nprint(df[cols].sort_values('cb_mean',ascending=False).round(3).to_string(index=False))\nprint(len(df))\nEOF\nwc -l results/trials.tsv; grep -c \"A1R-explore\" results/trials.tsv", "description": "Consolidate all evaluated variants"}
```


**← tool result**

```
                     variant  dims  cb_L  cb_D  cb_mean  cb_mean_lo  cb_mean_hi  d_cb_mean_vs_ref  d_cb_mean_vs_ref_lo  d_cb_mean_vs_ref_hi  strat_L  strat_D  strat_mean  d_strat_mean_vs_ref  d_strat_mean_vs_ref_lo  d_strat_mean_vs_ref_hi  cb_X  strat_X  agree_auc   ms_L   ms_D
          a1@baseU+env@sph8U   627 0.756 0.631    0.693       0.649       0.750             0.024               -0.039                0.043    0.729    0.650       0.690                0.042                  -0.090                   0.063 0.726    0.706      0.982  6.092  2.331
 a1@baseU+a1@sph8U+env@sph8U  1141 0.732 0.650    0.691       0.652       0.757             0.021               -0.035                0.044    0.717    0.658       0.688                0.040                  -0.083                   0.061 0.718    0.708      0.988 11.422  7.139
       a1pair@base+env@sph8U   505 0.762 0.616    0.689       0.653       0.751             0.019               -0.030                0.033    0.732    0.631       0.682                0.034                  -0.070                   0.051   NaN      NaN      0.970  6.092  2.467
 a1@baseU+env@sph8U+b1@sph8U   672 0.719 0.650    0.684       0.639       0.740             0.014               -0.055                0.036    0.706    0.657       0.681                0.033                  -0.123                   0.057   NaN      NaN      0.993  7.458  3.655
      a1@baseU*0.5+env@sph8U   627 0.719 0.646    0.682       0.630       0.733             0.013        
… [8,852 more characters; full text in agent_logs/raw/]
```


<details><summary>thinking · 2026-10-27 21:22:33</summary>

I've logged 36 distinct variants. Now I'll pull one more paired metric—the D-mode Δ for the finalists versus A1 and B1, plus the C1-D comparator—using the same replicates already recorded.



</details>


**→ tool call `Bash`** · 2026-10-27 21:22:46

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; cat > scripts/explore/defrob_dmode_delta.py <<'EOF'\n#!/usr/bin/env python\n\"\"\"Paired D-mode deltas (cb-AUC, stratified AUC; same vertex-bootstrap replicates, B = 1000) of the D11 finalists\nvs A1 pair_only (base) and vs B1 (base, the C1-D comparator).  Variants were already logged by defrob_eval.py; this\nadds the paired D-mode Δ only (one summary trials row).\"\"\"\nimport multiprocessing as mp\nimport sys\nfrom pathlib import Path\n\nimport numpy as np\nimport pandas as pd\n\nROOT = Path(__file__).resolve().parents[2]\nsys.path[:0] = [str(ROOT / \"src\"), str(ROOT / \"scripts\"), str(ROOT / \"scripts/explore\")]\nimport defrob_eval as R  # noqa: E402\nfrom eval_dev import n_bins_for  # noqa: E402\nfrom pocketcompare import evaluate as ev  # noqa: E402\nfrom pocketcompare.provenance import append_trial, write_result  # noqa: E402\nfrom pocketcompare.seeds import SEEDS  # noqa: E402\n\nFINAL = [\"a1@baseU+env@sph8U\", \"a1@sph8U+env@sph8U\", \"env@sph8U\", \"a1@baseU+a1@sph8U+env@sph8U\"]\nREFS = [\"a1pair@base\", \"b1@base\"]\n\n\ndef task(a):\n    v, y, s, refs, pc, cov, ci, cj = a\n    nb = n_bins_for(y)\n\n    def fn(w):\n        out = []\n        for r in refs:\n            out += [ev.cluster_balanced_auc(y, s, pc, w)[\"auc_cb\"] - ev.cluster_balanced_auc(y, r, pc, w)[\"auc_cb\"],\n                    ev.stratified_auc(y, s, cov, w, n_b
… [1,903 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
                    variant                     stat  estimate     lo    hi  p_one_sided
         a1@baseU+env@sph8U    d_cb_D_vs_a1pair@base     0.090  0.004 0.128        0.022
         a1@baseU+env@sph8U d_strat_D_vs_a1pair@base     0.086 -0.088 0.124        0.161
         a1@baseU+env@sph8U        d_cb_D_vs_b1@base     0.011 -0.077 0.087        0.229
         a1@baseU+env@sph8U     d_strat_D_vs_b1@base     0.036 -0.082 0.105        0.143
         a1@sph8U+env@sph8U    d_cb_D_vs_a1pair@base     0.131  0.056 0.185        0.003
         a1@sph8U+env@sph8U d_strat_D_vs_a1pair@base     0.105 -0.052 0.176        0.086
         a1@sph8U+env@sph8U        d_cb_D_vs_b1@base     0.052 -0.004 0.134        0.033
         a1@sph8U+env@sph8U     d_strat_D_vs_b1@base     0.055 -0.032 0.149        0.073
                  env@sph8U    d_cb_D_vs_a1pair@base     0.114  0.023 0.162        0.011
                  env@sph8U d_strat_D_vs_a1pair@base     0.100 -0.067 0.179        0.103
                  env@sph8U        d_cb_D_vs_b1@base     0.035 -0.030 0.102        0.084
                  env@sph8U     d_strat_D_vs_b1@base     0.050 -0.037 0.136        0.074
a1@baseU+a1@sph8U+env@sph8U    d_cb_D_vs_a1pair@base     0.109  0.028 0.156        0.005
a1@baseU+a1@sph8U+env@sph8U d_strat_D_vs_a1pair@base     0.094 -0.061 0.136        0.126
a1@baseU+a1@sph8U+env@sph8U        d_cb_D_vs_b1@base     0.030 -0.045 0.117        0.096
a1@baseU+a1@sph8U+env@sph8U     d_strat_D_vs_b1@base     0.044 -0.065 0.120 
… [12 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 21:23:20

Now the report. Checking whether the project has a report linter first.


**→ tool call `Bash`** · 2026-10-27 21:23:20

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 1,30p scripts/check_report.py", "description": "Read report checker header"}
```


**← tool result**

```
#!/usr/bin/env python
"""Check that numbers in a markdown report match their sidecar'd result files (DESIGN §5).

Tag convention: a number is followed (on the same line) by ``<!-- src: <path>#<key> -->``; the checked number is
the last number between the previous tag (or line start) and this tag, e.g.

    ROC-AUC 0.734 <!-- src: results/c1/auc.json#delta_auc.estimate --> (95 % CI ...)

* ``path`` is relative to ``--root`` (default: the project root).  The file must have a ``<path>.prov.json``
  sidecar (``pocketcompare.provenance``) whose ``result_sha256`` matches the file, and whose ``evaluate_sha256``
  matches the current ``src/pocketcompare/evaluate.py`` (``--allow-stale-eval`` downgrades this to a warning).
* ``key`` for .json: dotted path into the object (``a.b.0.c``; a literal top-level key containing dots wins).
  For .parquet/.tsv/.csv: ``column`` (the table must have exactly one row) or ``column[col=value,col2=value]``
  (the filter must select exactly one row).
* Match rule: the reported number equals the stored value rounded to the shown number of decimals
  (|reported - value| <= 0.5 * 10^-decimals + 1e-12).  A number with a ``%`` suffix matches if it equals 100 x the
  value (fractions) or the value itself (already a percentage).
* Untagged numbers with >= 2 decimals are listed as warnings (``--fail-untagged`` makes them errors).

Exit status 0 if every tag checks out, 1 otherwise (mismatch, missing file, missing/stale sidecar, bad key).
"""
from __future__ imp
… [117 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-27 21:24:24

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/reports/definition_robustness.md", "content": "# Definition robustness: ligand-free site shapers × robust blocks (D11) — 2026-10-27\n\nTOUGH-M1-dev (731 pockets; L: 9,829 pairs, D: 7,866 D-set pairs). Metrics come from the frozen `evaluate.py`.\nCIs are 95 % joint vertex bootstraps (B = 1000, seed 0, units = ligand cluster ∪ homology group). 36 distinct\nvariants were logged to `results/trials.tsv` (arm `A1R-explore`).\nNotation: `desc@def`.\n- `base` = L ligand shell / D merged BURROW pocket (as in the dev eval). `U` = D located by the single best-covering\n  sub-pocket instead of the merged pocket.\n- **sph8** = all buried points (bur10 ≥ 0.5) within 8 Å of the bur16⁴-weighted centroid of the located set.\n- res = residue shell; core8 = located set ∩ 8 Å.\n- env = new protein-side block (113 d): vol-weighted and bur16⁴-weighted means of `hit_*`, `n4_rg_*`, `f8_*`, `f12_*`\n  composition, plus a first-hit chemistry × buriedness-tertile histogram.\n- Multi-part variants use a 1:1 block cosine.\n- cross = labelled pairs scored L-query vs D-target. agree = label-free retrieval AUC of a site's own D descriptor\n  from its L descriptor among the 655 matched dev pockets.\n\n| variant | dims | cb L | cb D | **mean** | strat L | strat D | cross cb | agree | ms L / D |\n|---|---|---|---|---|---|---|---|---|---|\n| a1pair@base (ref = dev pick) | 392 | 0.798 | 0.541 | 0.670 | 0.732 | 0.564 | 0.647 | 0.765 | 5.7 / 2.1 |\n| a
… [6,088 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:24:25

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python scripts/check_report.py reports/definition_robustness.md 2>&1 | grep -v \"untagged\" | tail -8; wc -w reports/definition_robustness.md; grep -c \"A1R-explore\" results/trials.tsv; python -m pytest -q tests/test_a1r.py tests/test_pockets.py 2>&1 | tail -1", "description": "Check report tags, counts and tests", "timeout": 600000}
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/reports/definition_robustness.md (file state is current in your context — no need to Read it back)
```


**← tool result**

```
check_report: 2 tagged numbers OK, 0 errors
1285 reports/definition_robustness.md
123
19 passed in 6.17s
```


**→ tool call `SubagentHandback`** · 2026-10-27 21:24:53

```
{"message": "Ligand-free site shapers lift D-mode a lot, but the amended mean(L, D) objective still rewards the 4 Å ligand-shell imprint. So the best scorer on that objective is a hybrid, and its gain over the reference has a CI that includes 0. Full write-up: `reports/definition_robustness.md` (`check_report` OK).\n\n| variant | cb L | cb D | mean (Δ vs ref) | strat L / D | L↔D agree |\n|---|---|---|---|---|---|\n| A1 pair, base (reference) | 0.798 | 0.541 | 0.670 | 0.732 / 0.564 | 0.765 |\n| **A1 on the best single sub-pocket + env on sph8** (627 d) | 0.756 | 0.631 | **0.693** (+0.024 [−0.039, +0.043]) | 0.729 / 0.650 | 0.982 |\n| **A1 + env on sph8**, ligand-free (627 d) | 0.648 | **0.672** | 0.660 | 0.681 / 0.669 | 0.996 |\n\n- **Definitions:** sph8 = buried points within 8 Å of the pocket's buriedness-weighted centroid. env is a new 113-d protein-side block, 0.3 ms/pocket.\n- **D-mode gains are real:** in paired D-set comparisons, ligand-free vs A1 is +0.131 [+0.056, +0.185]. Vs B1 (the C1-D comparator) it is +0.052 [−0.004, +0.134], one-sided p = 0.033.\n- **Robust blocks:** env and B1 are the most definition-robust; A1 hist is robust but uninformative, and USR is the least robust.\n- **What did not work:** residue mode (slow, mean 0.619), sph10, core8, merged-pocket centres (−0.02 in D), env up-weighting, and adding B1.\n- **Sub-pocket matching:** set-to-set max over sub-pockets needs no ligand to pick one and costs only −0.009 in D.\n\n**Recommendation for A4b:** feed
… [698 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
