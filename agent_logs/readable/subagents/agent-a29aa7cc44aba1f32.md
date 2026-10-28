# Sub-agent a29aa7cc44aba1f32 — Dev evaluation of all arms TOUGH-M1 (opus)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-27 20:35:43

You run the first development evaluation of all pocket-similarity arms on TOUGH-M1-dev. Project root: /cluster/project/beltrao/gmagnus/pocket_compare (git; do NOT commit — the PI commits). Read DESIGN.md (v2: §0 claims, §3 arms, §4 statistics — note amendment D6: size strata = 5 quintiles of mean log-volume × 20 quantile bins of |Δ log-volume|), RESEARCH_TREE.md decisions D6–D9, reports/{evaluate_module,a1_descriptors,a2_docking,baselines_b4_b5,splits,pocket_adapter}.md, data/splits/SPLITS.md. Env: `source .venv/bin/activate`. ≤ 16 CPU threads; no GPU needed. NEVER open data/sealed/ or anything chmod 000.

Inputs: dev pairs data/splits/tough_m1_dev_pairs.parquet (labels + shipped APoc/G-LoSA/SiteEngine scores — find their semantics in the OSF/TOUGH-M1 docs or the data agent's scripts; a higher-is-more-similar orientation must be verified on a tiny subset or from documentation, and if a column's meaning is unclear, report all columns rather than choosing post hoc); pocket metadata data/splits/tough_m1_pockets_split.parquet (groups, ligand clusters); point index data/processed/cache/points/tough_m1/index.parquet (L-mode volume, D-mode match fields); descriptors in data/processed/descriptors/tough_m1/ (A1 16 configs L/D, B0, B1 configs, B4 esm2 L/D, B5 epocs L); docking raw tables in data/processed/docking/tough_m1/ with src/pocketcompare/descriptors/a2.py (rank / le_resid / ifp; fit only on the dev pocket set, label-free); similarity helpers in src/pocketcompare/similarity.py; metrics ONLY via the frozen src/pocketcompare/evaluate.py (do not modify it); provenance via src/pocketcompare/provenance.py (write_result + append_trial to results/trials.tsv for EVERY arm/config/variant evaluated).

Build `scripts/eval_dev.py` (reusable for BLiPS-val/PPIPS-val later: dataset adapters for pairs, units, covariates) and run it on TOUGH-M1-dev:
- Units for the vertex bootstrap: connected components of (ligand cluster ∪ homology group) over dev pockets. Covariate: L-mode log volume. B = 2000, seed SEEDS[0].
- For each arm and variant: pair ROC-AUC (+95 % CI), AP (+prevalence, lift), pAUC(FPR ≤ 0.1), cluster-balanced AUC, 2-D size-stratified AUC (n_bins (5,20)), and for L-mode and D-mode (D-mode: common set of pairs where both pockets have a D-match per DESIGN rule coverage ≥ 0.3 OR precision ≥ 0.5, plus worst-case bound and miss rates by label).
- Arms: B0 (−|Δ log vol|), B0m (logistic on log v_a + log v_b and |Δ|, cross-fitted over unit folds on dev — diagnostic; must give stratified AUC 0.5 ± 0.03), B1 (each config), B4, B5 (−Euclidean), B5-T shipped scores, A1 all 16 configs, A2 {fragments, lead-like} × {rank, le_resid, ifp}, each raw cosine (z-scored on dev pockets, label-free) and with CSLS (k = 10, background = all dev pockets).
- A2 gate (DESIGN §3): cross-fitted fusion (logistic regression on z-scored similarities, folds = unit-grouped 5-fold on dev, seed SEEDS[0]) of A1(best config by the one-SE rule on cluster-balanced AUC) + A2 vs A1 alone, metric = size-stratified AUC; report Δ with paired bootstrap CI (the bootstrap must use the cross-fitted out-of-fold scores). Also descriptive: fusion A1 + B1, A1 + B1 + A2, A1 + A2 + B4.
- A1 selection: one-SE rule on cluster-balanced AUC on TOUGH-M1-dev (BLiPS-val will be added later; note this). Report the chosen config.
- Minimum detectable effect for C1 from the dev bootstrap SE of the paired Δ(best non-learned arm − B1), scaled to test by sqrt(n_units_dev / n_units_test) (test has 530 homology groups / 302 ligand clusters → compute n_units_test from data/splits/tough_m1_pockets_split.parquet partition labels WITHOUT opening test pairs).
- Sanity/negative controls: shuffled-label AUC ≈ 0.5; random-vector descriptor ≈ 0.5.
Output: results/dev/tough_m1_dev_summary.{parquet,md} (+ .prov.json), per-arm rows in results/trials.tsv, a figure is optional. Write reports/dev_eval_tough_m1.md (≤ 1.5 pages, numbers first: a table of all arms with ROC / AP / cluster-balanced / stratified AUC and CIs; L vs D; CSLS effect; A2 gate verdict; chosen A1 config; MDE; anything surprising). Do not tune anything beyond the pre-registered grid; if you think something else should be tried, list it as a suggestion. Final message ≤ 250 words.


### PI / user turn · 2026-10-27 20:35:43

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


### Assistant · 2026-10-27 20:35:45

I'll start by reading the design documents and reports.


**→ tool call `Bash`** · 2026-10-27 20:35:46

```
{"command": "ls && wc -l DESIGN.md RESEARCH_TREE.md reports/*.md data/splits/SPLITS.md && ls src/pocketcompare src/pocketcompare/descriptors scripts results results/* | head -80", "description": "List project structure and doc sizes"}
```


**← tool result**

```
DATA.md
DESIGN.md
LESSONS.md
LITERATURE.md
PROMPT.md
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
   263 DESIGN.md
   115 RESEARCH_TREE.md
   128 reports/a1_descriptors.md
    75 reports/a2_docking.md
    17 reports/baselines_b4_b5.md
    41 reports/data_benchmarks.md
    83 reports/evaluate_module.md
   121 reports/fragment_docking_feasibility.md
    71 reports/pocket_adapter.md
    85 reports/ppi_datasets.md
   115 reports/ppi_dimers.md
    63 reports/splits.md
    71 data/splits/SPLITS.md
  1248 total
results:
a2
benchmarks
feasibility
pocket_cache
ppi

results/a2:
a2_fragments_descriptors.npz
a2_fragments_dmode_descriptors.npz
a2_leadlike_descriptors.npz
a2_leadlike_dmode_descriptors.npz
descriptor_diagnostics_D_dmode.json
descriptor_diagnostics_L.json
fragments_dmode_ref.npz
fragments_ref.npz
leadlike_dmode_ref.npz
leadlike_ref.npz
reference_pockets.txt
repro.json
run_summary_L.json
run_summary_dmode_D.json

results/benchmarks:
benchmark_counts.json

results/feasibility:
concurrency.txt
fragments.sdf
pocket_points.npz
pockets.tsv
pockets_burrow_descriptors.tsv
probe_fingerprints.tsv
receptors
redock_control.txt
scores_gpu_frag_lite_multi2048.tsv
scores_gpu_frag_lite_multi512.tsv
scores_gpu_frag_lite_nn_multi.tsv
scores_gpu_frag_lite_np_multi.tsv
scores_gpu_frag_lite_pp.tsv
scores_gpu_frag_scan_multi.tsv
scores_gpu_frag_xlite_multi2048.tsv
scores_gpu_frag_xlite_multi512.tsv
scores_gpu_frag_xlite_np_multi.tsv
s
… [583 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:35:50

```
{"command": "cat DESIGN.md", "description": "Read DESIGN.md"}
```


**→ tool call `Bash`** · 2026-10-27 20:35:50

```
{"command": "cat RESEARCH_TREE.md", "description": "Read RESEARCH_TREE.md"}
```


**← tool result**

```
# DESIGN — fast, fold-independent pocket similarity on BURROW (v2, 2026-10-27 20:10)

History: v0 (19:15) → review round 1 (reviews/round1_{pi,statistics,data,algorithms,domain,agent_failure_modes}.md)
→ v1 (19:35) → review round 2 (reviews/round2_panel.md) → v2 (this). Change logs in §10 and §11. Inputs: PROMPT.md, LITERATURE.md, reports/*.md.

## 0. Goal, deliverables, claims

Build **a versatile, fast tool that scores the similarity of two binding pockets independent of sequence and
fold**, on BURROW pockets, usable at AFDB scale (≈ 200 M structures × 5–15 pockets), for PDB and AlphaFold
models, and for pockets created at protein–protein interfaces (PPIs).

Deliverables: (1) the `pocketcompare` package and CLI (pocket → descriptor; pair → score; batch/ANN search);
(2) evaluation on public benchmarks and on our own leakage-controlled sets, runtime next to every accuracy;
(3) REPORT.md.

**Pre-registered confirmatory claims** (one Holm family; one-sided α = 0.05; paired vertex bootstrap, §4):
- **C1a** TOUGH-M1-test (L-mode): ROC-AUC(final) − ROC-AUC(B1) > 0. **C1b** same vs B4 (ESM-2 pocket embedding).
  Smallest effect of interest 0.03: reported with its lower CI bound; the minimum detectable effect is
  computed on dev and recorded before unsealing.
- **C2** ProSPECCTs D5.2 + D6.2 + D7 (self-pairs removed), macro ROC-AUC(final) − macro ROC-AUC(B1) > 0.
- **C3** PPI ligand-grounded test (§2.5 PPI-L): ROC-AUC(final) − ROC-AUC(B1) > 0 — only if the PPI-L gate
  (§2.5) passes
… [19,504 more characters; full text in agent_logs/raw/]
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
- D8 (21:00) Keep 
… [9,027 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:35:54

```
{"command": "cat reports/evaluate_module.md reports/a1_descriptors.md", "description": "Read evaluate and A1 reports"}
```


**→ tool call `Bash`** · 2026-10-27 20:35:54

```
{"command": "cat reports/a2_docking.md reports/baselines_b4_b5.md reports/splits.md reports/pocket_adapter.md data/splits/SPLITS.md", "description": "Read A2, baselines, splits, adapter reports"}
```


**← tool result**

```
# evaluate.py, provenance and check_report (evaluation engineer, 2026-10-27)

Files: `src/pocketcompare/evaluate.py` (sha256 f22d0296…, the frozen metric module; the full definitions are in its
docstring), `src/pocketcompare/provenance.py`, `scripts/check_report.py`, `scripts/bench_evaluate.py`, and
`tests/test_evaluate.py` + `tests/test_provenance.py` (with `tests/conftest.py`, which adds a `slow` marker).
All of this was built on synthetic data only. I opened no sealed or pair files.

## Definitions chosen
- **AUC / AP / pAUC:** every metric takes pair weights, and a tied pair counts as ½. AP is the step-function sum,
  equal to sklearn's; it is returned with the prevalence and the lift (AP / prevalence). `target="neg"` computes
  AP with the negatives as the target class (for Vertex). For pAUC (FPR ≤ 0.1) the **McClish-standardised value
  is the headline** (equal to sklearn `max_fpr`; 0.5 = chance) and the raw area is also returned.
- **Cluster-balanced AUC:** each positive gets weight w / W⁺(its positive cluster) and the negatives stay
  uniform. This equals the plain mean of the per-cluster AUCs, each computed against all negatives (tested).
  `neg_cluster` can optionally balance the negatives the same way. A per-cluster AUC table for the top k
  clusters is available, with negatives = all or = only those involving the cluster.
- **Size-stratified AUC (DESIGN v2):** the API is generic: an (n × k) covariate array plus the number of bins
  per column. The headline is 5 × 
… [12,481 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
# A2 — docking-profile pocket descriptor on TOUGH-M1 (2026-10-27)

Scripts `scripts/a2/{build_panels,prep_pockets,dock_tough_m1,run_dock.sh,aggregate,analyze_repro,build_descriptors}`;
descriptor `src/pocketcompare/descriptors/a2.py` (7 unit tests, `tests/test_a2_descriptor.py`).
Node eu-g6-048, **cuda:0 + cuda:2 only, 4 processes per GPU, 2 CPU threads each**. ADock read-only, unmodified,
overlay env per `scripts/feasibility/setup_adock_overlay.sh`. No label or pair file was opened.

## Protocol (as DESIGN §3 A2)
Stock Vina weights, rigid receptor, preset `frag_lite_np`, **fixed 12 Å cubic box** centred on the
volume-weighted centroid of the L-mode BURROW points (D-mode: the matched merged region-rule pocket), so box
volume is not a pocket-size proxy. Both panels are docked in one batch per pocket → identical receptor prep,
grid and compute. Best pose per molecule; **pose-in-pocket** = pose centroid ≤ 2 Å from a pocket point.
Stored per pocket × molecule: score, inter, LE = score/heavy atoms, in-pocket flag and centroid distance,
best-pose contact counts (H-bond donor matched, H-bond acceptor matched, apolar, aromatic, charged) and
buried fraction → `data/processed/docking/tough_m1/{fragments,leadlike}{,_dmode}.parquet` (+ `.prov.json`).

## Panels (full provenance, licences and sha256 in DATA.md "Docking panels")
128 **fragments** from the public-domain NCI Open Database (release 4), Ro3-like filter (8–17 HA, MW ≤ 300,
≤ 3 rot. bonds, ≥ 1 ring, PAINS-free), stratified 6 pha
… [23,426 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:35:58

```
{"command": "ls src/pocketcompare src/pocketcompare/descriptors && wc -l src/pocketcompare/*.py src/pocketcompare/descriptors/*.py && sed -n 1,200p src/pocketcompare/evaluate.py", "description": "List package and read evaluate.py head"}
```


**← tool result**

```
src/pocketcompare:
__init__.py
__pycache__
datasets
descriptors
evaluate.py
pockets.py
provenance.py
seeds.py
similarity.py
splitutil.py

src/pocketcompare/descriptors:
__init__.py
__pycache__
a1.py
a2.py
baselines.py
esm_pocket.py
     1 src/pocketcompare/__init__.py
   810 src/pocketcompare/evaluate.py
   575 src/pocketcompare/pockets.py
   225 src/pocketcompare/provenance.py
     2 src/pocketcompare/seeds.py
   142 src/pocketcompare/similarity.py
   137 src/pocketcompare/splitutil.py
     0 src/pocketcompare/descriptors/__init__.py
   507 src/pocketcompare/descriptors/a1.py
   303 src/pocketcompare/descriptors/a2.py
    85 src/pocketcompare/descriptors/baselines.py
   120 src/pocketcompare/descriptors/esm_pocket.py
  2907 total
"""The single frozen evaluation module of pocketcompare (DESIGN §4, §5).

Every number in a report is computed by a function in this file; its sha256 is recorded in every result sidecar
(``pocketcompare.provenance``).  Changing this file after the first result invalidates all results.

Conventions
-----------
* ``y`` is a binary label per pair (1 = positive, "similar"), ``s`` a real score (higher = more similar), ``w`` an
  optional non-negative pair weight (default 1).  All metrics are *weighted* metrics: a pair with weight 2 counts
  exactly like two copies of that pair.
* Ties count one half (Mann-Whitney convention), i.e. the ROC curve runs diagonally through a block of tied scores.
* **Missing scores** (method failures) are ``NaN``.  The low-le
… [10,881 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:36:01

```
{"command": "grep -n \"^def \\|^class \\|^    def \" src/pocketcompare/evaluate.py && sed -n '/^def stratified_auc/,/^def retrieval/p' src/pocketcompare/evaluate.py | head -120", "description": "List evaluate.py functions and stratified_auc"}
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
492:    def _boot_kernel(cnt, ci_s, cj_s, w_s, y_s, end_s, out_auc, out_ap, offset):  
… [3,957 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:36:05

```
{"command": "sed -n 200,300p src/pocketcompare/evaluate.py && sed -n 380,810p src/pocketcompare/evaluate.py", "description": "Read rest of evaluate.py"}
```


**← tool result**

```
    if stop >= len(fpr):
        raw = float(np.trapezoid(tpr, fpr))
    else:
        t_at = np.interp(max_fpr, fpr[stop - 1:stop + 1], tpr[stop - 1:stop + 1])
        raw = float(np.trapezoid(np.append(tpr[:stop], t_at), np.append(fpr[:stop], max_fpr)))
    a_min, a_max = 0.5 * max_fpr ** 2, max_fpr
    mcclish = 0.5 * (1 + (raw - a_min) / (a_max - a_min))
    return {"pauc_mcclish": mcclish, "pauc_raw": raw, "max_fpr": max_fpr}


def binary_metrics(y, s, w=None, *, max_fpr: float = 0.1) -> dict:
    """ROC-AUC, AP (+prevalence, lift), pAUC (McClish + raw) and counts for one score vector (no NaN)."""
    y, s, w = _as_arrays(y, s, w)
    out = {"n": int(len(y)), "n_pos": int(y.sum()), "n_neg": int((~y).sum()),
           "w_pos": float(w[y].sum()), "w_neg": float(w[~y].sum()), "auc": roc_auc(y, s, w)}
    ap = average_precision(y, s, w)
    out.update(ap=ap["ap"], prevalence=ap["prevalence"], ap_lift=ap["ap_lift"])
    pa = partial_auc(y, s, w, max_fpr=max_fpr)
    out.update(pauc_mcclish=pa["pauc_mcclish"], pauc_raw=pa["pauc_raw"], max_fpr=max_fpr)
    return out


# ---------------------------------------------------------------------------------------- cluster-aware metrics
def _balance(labels, mask, w):
    """Return w with entries in ``mask`` rescaled so that each label group sums to 1 (others unchanged)."""
    out = w.copy()
    lab = np.asarray(labels)[mask]
    codes, uniq = _factorize(lab)
    tot = np.bincount(codes, weights=w[mask], minlength=len(uniq))
    sub 
… [24,061 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:36:13

```
{"command": "cat src/pocketcompare/provenance.py src/pocketcompare/similarity.py src/pocketcompare/seeds.py", "description": "Read provenance and similarity modules"}
```


**← tool result**

```
"""Provenance sidecars and the append-only trials log (DESIGN §4, §5; reviews/round1_agent_failure_modes.md M2, M4).

``write_result(path, obj, ...)`` writes a result file (format from the extension: .parquet, .json, .tsv, .csv)
and next to it ``<path>.prov.json`` with:

* git commit of the project + ``git_dirty`` (tracked files modified; untracked files are not counted, their number
  is recorded as ``git_untracked``).  Writing under ``results/final/`` from a dirty tree is refused.
* script path + sha256, args, config (inline if JSON-serialisable) + config sha256 (canonical JSON with sorted
  keys for a dict; raw bytes for a file path), seed, device, hostname, start/end time (UTC ISO), wall seconds.
* inputs: for each input file sha256 + size; **files larger than 1 GiB are fingerprinted by size + mtime_ns
  only** (``"method": "size_mtime"``) because hashing them would cost minutes per result.
* sha256 of ``pocketcompare/evaluate.py`` (the frozen metric module) and of the result file itself.

``start_time`` defaults to the start time of the current process (Linux /proc), so wall seconds cover the whole
script run; pass ``start_time=time.time()`` captured earlier to time a section instead.

``append_trial(arm, config, dataset_split, metrics, result_path)`` appends one row to ``results/trials.tsv``
(created with a header if missing; never rewritten; an exclusive ``flock`` serialises concurrent writers).
"""
from __future__ import annotations

import datetime as _dt
import fcnt
… [14,612 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:36:16

```
{"command": "cat src/pocketcompare/descriptors/a2.py src/pocketcompare/descriptors/baselines.py", "description": "Read A2 descriptor and baselines code"}
```


**← tool result**

```
"""A2 — docking-profile pocket descriptor (DESIGN §3 "A2").

Turns the raw per-pocket x per-molecule docking table written by ``scripts/a2/dock_tough_m1.py`` into three
descriptor blocks:

(a) ``rank``      PocketVec-style rank vector over the panel (most negative score = rank 1), with explicit
                  **non-binder bins**: a molecule is a non-binder if its score is above the panel's
                  ``nonbinder_quantile`` score (default: the 90th percentile of the panel's scores on the
                  reference set) or if its best pose left the pocket (pose centroid > 2 A from any pocket
                  point, flag ``in_pocket``).  Non-binders are binned, after the N binder ranks, to
                  N+1 (score bin), N+2 (out-of-pocket bin) and N+3 (missing / docking failure), as PocketVec
                  bins its non-binders to 129/130/131.
(b) ``le_resid``  ligand efficiency (score / heavy atoms) **residualised on log pocket volume and mean
                  buriedness** (per molecule: OLS LE ~ 1 + log V + buriedness) and then z-scored per molecule.
(c) ``ifp``       pose interaction profile: per molecule x contact type (H-bond donor matched, H-bond acceptor
                  matched, apolar, aromatic, charged, buried fraction) of the best pose, counts divided by the
                  molecule's heavy-atom count, z-scored per (molecule, type) and flattened.

**All fitted statistics — the non-binder threshold, the LE regression coefficients, and every z-sco
… [17,858 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 20:36:19

Now the data files.


**→ tool call `Bash`** · 2026-10-27 20:36:21

```
{"command": "source .venv/bin/activate && ls -la data/processed/descriptors/tough_m1/ | head -100 && ls -la data/processed/docking/tough_m1/ && ls data/splits/ && python -c \"\nimport pandas as pd\nfor f in ['data/splits/tough_m1_dev_pairs.parquet','data/splits/tough_m1_pockets_split.parquet','data/processed/cache/points/tough_m1/index.parquet']:\n    d=pd.read_parquet(f); print(f, d.shape); print(d.dtypes.to_string()); print(d.head(3).T.to_string()[:3000])\n\"", "description": "Inspect descriptor files and key parquet tables"}
```


**← tool result**

```
total 525452
drwxr-sr-x 2 gmagnusson nogroup    16384 Oct 27 20:12 .
drwxr-sr-x 3 gmagnusson nogroup     4096 Oct 27 19:27 ..
-rw-r--r-- 1 gmagnusson nogroup   435030 Oct 27 19:49 a1_dbins_coarse_D.ids.parquet
-rw-r--r-- 1 gmagnusson nogroup     3502 Oct 27 19:49 a1_dbins_coarse_D.ids.parquet.prov.json
-rw-r--r-- 1 gmagnusson nogroup     8753 Oct 27 19:49 a1_dbins_coarse_D.layout.json
-rw-r--r-- 1 gmagnusson nogroup 12098720 Oct 27 19:49 a1_dbins_coarse_D.npy
-rw-r--r-- 1 gmagnusson nogroup   326254 Oct 27 19:49 a1_dbins_coarse_L.ids.parquet
-rw-r--r-- 1 gmagnusson nogroup     3500 Oct 27 19:49 a1_dbins_coarse_L.ids.parquet.prov.json
-rw-r--r-- 1 gmagnusson nogroup     8753 Oct 27 19:49 a1_dbins_coarse_L.layout.json
-rw-r--r-- 1 gmagnusson nogroup 12098720 Oct 27 19:49 a1_dbins_coarse_L.npy
-rw-r--r-- 1 gmagnusson nogroup   435152 Oct 27 19:49 a1_dbins_fine_D.ids.parquet
-rw-r--r-- 1 gmagnusson nogroup     3491 Oct 27 19:49 a1_dbins_fine_D.ids.parquet.prov.json
-rw-r--r-- 1 gmagnusson nogroup    12461 Oct 27 19:49 a1_dbins_fine_D.layout.json
-rw-r--r-- 1 gmagnusson nogroup 17154848 Oct 27 19:49 a1_dbins_fine_D.npy
-rw-r--r-- 1 gmagnusson nogroup   326370 Oct 27 19:49 a1_dbins_fine_L.ids.parquet
-rw-r--r-- 1 gmagnusson nogroup     3493 Oct 27 19:49 a1_dbins_fine_L.ids.parquet.prov.json
-rw-r--r-- 1 gmagnusson nogroup    12461 Oct 27 19:49 a1_dbins_fine_L.layout.json
-rw-r--r-- 1 gmagnusson nogroup 17154848 Oct 27 19:49 a1_dbins_fine_L.npy
-rw-r--r-- 1 gmagnusson nogroup   4351
… [15,488 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:36:33

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd, numpy as np\np=pd.read_parquet('data/splits/tough_m1_dev_pairs.parquet')\nprint(p.subset.value_counts(), p.source_label.value_counts(), p.is_self.sum())\nprint(pd.crosstab(p.label, p.ligand_cluster_a==p.ligand_cluster_b))\nprint(pd.crosstab(p.label, p.group_a==p.group_b))\nprint(p.describe().T.to_string())\nprint(p.isna().sum().to_string())\nfor c in ['apoc_c1','apoc_c2','glosa_c1','siteengine_c1','siteengine_c2','siteengine_c3','tm_score','seq_identity']:\n    from sklearn.metrics import roc_auc_score\n    m=p[c].notna()\n    print(c, m.sum(), roc_auc_score(p.label[m], p[c][m]))\ns=pd.read_parquet('data/splits/tough_m1_pockets_split.parquet')\nprint(s.partition.value_counts())\ndev=s[s.partition=='dev']; print(dev.group_id.nunique(), dev.ligand_cluster.nunique(), dev.ligand_fp_ok.value_counts())\nallp=set(p.pocket_a)|set(p.pocket_b); print(len(allp), len(allp-set(dev.pocket_id)), len(set(dev.pocket_id)-allp))\n\"", "description": "Explore dev pairs table structure"}
```


**← tool result**

```
subset
TOUGH-M1    9829
Name: count, dtype: int64 source_label
negative    6463
positive    3366
Name: count, dtype: int64 0
col_0  False  True 
label              
0       6463      0
1        992   2374
col_0  False
label       
0       6463
1       3366
                count         mean          std           min          25%          50%          75%          max
label          9829.0     0.342456     0.474555  0.000000e+00     0.000000     0.000000     1.000000     1.000000
seq_identity   9829.0     0.202586     0.034108  5.400000e-02     0.181000     0.202000     0.223000     0.383000
tm_score       9829.0     0.326015     0.039535  1.840400e-01     0.298020     0.326970     0.356220     0.399980
ligand_tc      9829.0     0.370799     0.392062  0.000000e+00     0.072165     0.125000     0.826087     1.000000
apoc_c1        9829.0     0.307912     0.043315 -2.612500e-01     0.284320     0.308620     0.331770     0.673690
apoc_c2        9829.0     0.514976     0.302995  7.193000e-07     0.253600     0.497800     0.779600     1.000000
glosa_c1       9829.0     0.384989     0.073613  0.000000e+00     0.358957     0.394027     0.426564     0.676239
siteengine_c1  9829.0    27.283040     6.144215  0.000000e+00    23.000000    27.000000    31.000000    63.000000
siteengine_c2  9829.0  3432.939465  1004.185033  0.000000e+00  2705.000000  3390.000000  4067.000000  8069.000000
siteengine_c3  9829.0    47.158612     6.910997 -4.300000e+01    44.000000    47.000000    51.000000   
… [886 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:36:42

```
{"command": "grep -rln -i \"apoc\\|siteengine\\|glosa\\|g-losa\" --include=*.py --include=*.md --include=*.txt --include=*.json . 2>/dev/null | grep -v \"^./.venv\\|^./data/sealed\" | head -30; ls data/raw 2>/dev/null; ls -la data/raw/* 2>/dev/null | head -40", "description": "Find docs about shipped APoc/G-LoSA/SiteEngine scores"}
```


**← tool result**

```
DATA.md
PROMPT.md
RESEARCH_TREE.md
LITERATURE.md
DESIGN.md
scripts/data/fetch_tough_m1.py
scripts/data/make_tough_m1_split.py
scripts/data/verify_splits.py
data/sealed_raw_SHA256SUMS.txt
data/splits/tough_m1_split_counts.json
data/splits/SPLITS.md
reviews/round1_domain.md
reports/baselines_b4_b5.md
reviews/round1_statistics.md
reports/splits.md
reviews/round1_data.md
ippidb
klifs
panel_sources
ppi_pocketome
prospeccts
tough_c1
tough_m1
vertex
data/raw/ippidb:
total 12
drwxr-sr-x  3 gmagnusson nogroup 4096 Oct 27 19:10 .
drwxr-sr-x 10 gmagnusson nogroup 4096 Oct 27 19:34 ..
drwxr-sr-x  2 gmagnusson nogroup 4096 Oct 27 19:18 pages

data/raw/klifs:
total 20
drwxr-sr-x  3 gmagnusson nogroup 4096 Oct 27 18:51 .
drwxr-sr-x 10 gmagnusson nogroup 4096 Oct 27 19:34 ..
-rw-r--r--  1 gmagnusson nogroup 5275 Oct 27 18:51 MANIFEST.json
drwxr-sr-x  2 gmagnusson nogroup 4096 Oct 27 18:51 downloads

data/raw/panel_sources:
total 202764
drwxr-sr-x  3 gmagnusson nogroup      4096 Oct 27 19:36 .
drwxr-sr-x 10 gmagnusson nogroup      4096 Oct 27 19:34 ..
-rw-r--r--  1 gmagnusson nogroup     45072 Oct 27 19:32 LLM.smi
-rw-r--r--  1 gmagnusson nogroup 206737123 Oct 27 19:32 NCI-Open_2012-05-01.sdf.gz
-rw-r--r--  1 gmagnusson nogroup      1061 Oct 27 19:32 PocketVec_LICENSE.txt
-rw-r--r--  1 gmagnusson nogroup      6152 Oct 27 19:32 TOP_128_rDock_LLM.smi
drwxr-sr-x  2 gmagnusson nogroup      4096 Oct 27 19:37 pools

data/raw/ppi_pocketome:
total 24
drwxr-sr-x  5 gmagnusson nogroup 4096 Oct 27 19:33
… [623 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:36:48

```
{"command": "grep -n -i -B2 -A8 \"apoc\\|siteengine\\|glosa\\|g-losa\" DATA.md scripts/data/fetch_tough_m1.py scripts/data/make_tough_m1_split.py LITERATURE.md reviews/round1_domain.md reviews/round1_data.md | head -150; ls -la data/raw/tough_m1 data/raw/tough_m1/* | head -40", "description": "Grep docs/scripts for shipped score semantics"}
```


**← tool result**

```
DATA.md-9-| AFDB predicted dimers | /cluster/project/beltrao/gmagnus/dimers | AFDB complexes v1 | per-file in manifests | CC-BY-4.0 | — | human/yeast/ecoli homo+hetero |
DATA.md-10-| ProSPECCTs (Ehrt et al. 2018) | http://www.ewit.ccb.tu-dortmund.de/ag-koch/prospeccts/ (POST form; old www.ccb… URL is 404) | 2026-10-27 (files dated 2018) | 7 tarballs, full sha256 in data/raw/prospeccts/MANIFEST.json; e.g. decoy.tar.gz 0f7d1221c9b95d97…, review_structures.tar.gz aa2fae208212c949… | TU Dortmund terms of use (license_en.pdf): free, internal use only, **no redistribution**, cite paper — never commit raw or per-structure derived files | scripts/data/fetch_prospeccts.py | 10 subsets P1–P7; counts match paper Table 2 exactly |
DATA.md:11:| TOUGH-M1 (Govindaraj & Brylinski 2018) | Dataverse doi:10.7910/DVN/L7H7JJ (TOUGH-M1_dataset.tar.gz) + OSF https://osf.io/6ngbs/ (lists, baseline scores) | Dataverse v3 (2017-06-26); fetched 2026-10-27 | TOUGH-M1_dataset.tar.gz d9c7a872ea3d4860… (md5 matches Dataverse); lists/scores sha256 = OSF API values, in MANIFEST.json | tarball CC0 1.0 (Dataverse); OSF lists: unstated | scripts/data/fetch_tough_m1.py | 7524 pockets, 505,116 pos / 556,810 neg — match paper; APoc/G-LoSA/SiteEngine scores fetched as baselines |
DATA.md-12-| Vertex set (Chen et al. 2016) | ACS SI ci6b00118_si_002.zip via figshare doi:10.1021/acs.jcim.6b00118.s002 (https://ndownloader.figshare.com/files/5922126) | figshare v1 (2016-08-25); fetched 2026-10-27 | 37cb4a392b953a9c… (md
… [18,262 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:36:54

```
{"command": "cat data/raw/tough_m1/downloads/TOUGH-M1_dataset.info; sed -n 100,175p scripts/data/make_tough_m1_split.py", "description": "Read TOUGH-M1 dataset.info and split script parsing"}
```


**← tool result**

```
Dataset
-------

**TOUGH-M2** comprises experimental target structures with binding pockets identified by [*e*FindSite 1.3][1]. The following files are included:

### Lists

**`TOUGH-M2_target.list`**

A list of 5874 targets

**`TOUGH-M2_pocket.list`**

A list of pockets identified by [*e*FindSite 1.3][1]

* 1st column is the PDB-ID of target protein
* 2nd column is the index of the best pocket
* 3rd column is the accuracy of the best pocket (Matthews correlation coefficient over binding residues)

**`TOUGH-M2_positive.list`**

A list of 308822 positive pairs. These proteins bind chemically similar ligands despite having dissimilar global sequences and structures.

* The first two columns are the PDB-IDs of target proteins
* 3rd column is the sequence identity between the targets
* 4th column is the structure similarity ([TM-score][2] by [Fr-TM-align][3])
* 5th column is the chemical similarity of bound ligands (Tanimoto coefficient by [kcombu][4])

**`TOUGH-M2_negative.list`**

A list of 359410 negative pairs. These proteins have dissimilar global sequences and structures and bind chemically dissimilar ligands.

* The first two columns are the PDB-IDs of target proteins
* 3rd column is the sequence identity between the targets
* 4th column is the structure similarity ([TM-score][2] by [Fr-TM-align][3])
* 5th column is the chemical similarity of bound ligands (Tanimoto coefficient by [kcombu][4])

### Data

**`TOUGH-M2_dataset.tar.gz`**

A tarball containing the following fil
… [6,794 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:37:27

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd, numpy as np\nfrom scipy.sparse import coo_matrix\nfrom scipy.sparse.csgraph import connected_components\np=pd.read_parquet('data/splits/tough_m1_dev_pairs.parquet')\ns=pd.read_parquet('data/splits/tough_m1_pockets_split.parquet'); dev=s[s.partition=='dev'].reset_index(drop=True)\nidx={k:i for i,k in enumerate(dev.pocket_id)}; n=len(dev)\ndef comp(edges):\n    a,b=zip(*edges) if edges else ([],[])\n    g=coo_matrix((np.ones(len(a)),(a,b)),shape=(n,n)); return connected_components(g,directed=False)[1]\npos=p[p.label==1]\nc_pos=comp([(idx[a],idx[b]) for a,b in zip(pos.pocket_a,pos.pocket_b)])\n# positive graph comps among pockets in positives\npp=set(pos.pocket_a)|set(pos.pocket_b)\ncp=pd.Series(c_pos[[idx[x] for x in pp]]).value_counts(); print('pos-graph comps', len(cp), cp.head(10).tolist())\npc=pd.Series(c_pos[[idx[a] for a in pos.pocket_a]]).value_counts(); print('positives per pos-comp', (pc/pc.sum()).head(5).round(3).tolist())\n# butina-cluster positives share\nbc=pos.ligand_cluster_a.where(pos.ligand_cluster_a==pos.ligand_cluster_b,'X').value_counts(); print('butina share', (bc/bc.sum()).head(8).round(3).to_dict())\n# units: ligand cluster U group\ne=[]\nfor col in ['ligand_cluster','group_id']:\n    for _,g in dev.groupby(col):\n        ii=[idx[x] for x in g.pocket_id]; e+= [(ii[0],j) for j in ii[1:]]\ne+=[(i,i) for i in range(n)]\nu=comp(e); uc=pd.Series(u).value_counts(); print('units', len(u
… [924 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
pos-graph comps 76 [47, 47, 24, 24, 23, 19, 19, 16, 14, 14]
positives per pos-comp [0.249, 0.244, 0.067, 0.064, 0.05]
butina share {'X': 0.295, 'tm1lig:0000': 0.281, 'tm1lig:0002': 0.219, 'tm1lig:0021': 0.039, 'tm1lig:0009': 0.034, 'tm1lig:0010': 0.028, 'tm1lig:0042': 0.018, 'tm1lig:0041': 0.012}
units 146 [438, 29, 14, 13, 9, 7, 7, 6, 6, 5]
pairs within unit 0.32129412961644116 pos within 0.8538324420677362
units incl pos graph 99 [556, 14, 9, 6, 6]
test units 141 [710, 38, 13, 12, 12] 530 302
```


**→ tool call `Bash`** · 2026-10-27 20:37:46

```
{"command": "source .venv/bin/activate && ls data/processed/descriptors/tough_m1/ | sed 's/_[LD]\\..*//; s/_[LD]$//' | sort | uniq -c; ls data/processed/descriptors/tough_m1/ | grep -v \"^a1_\"; python -c \"\nimport pandas as pd, numpy as np, json\nd='data/processed/descriptors/tough_m1/'\nfor f in ['a1_default_L','a1_default_D','b1_default_D','b0_L','b0_D']:\n    try:\n        x=pd.read_parquet(d+f+'.ids.parquet'); print(f, x.shape, list(x.columns)); print(x.head(2).to_string())\n        print(np.load(d+f+'.npy').shape)\n    except Exception as e: print(f, e)\nx=pd.read_parquet(d+'b4_esm2_ids.parquet'); print(x.shape, x.columns.tolist()); print(x.head(2))\nx=pd.read_parquet(d+'b5_epocs_ids.parquet'); print(x.shape, x.columns.tolist()); print(x.head(2))\nprint(json.load(open(d+'a1_default_L.layout.json')).keys() if isinstance(json.load(open(d+'a1_default_L.layout.json')),dict) else json.load(open(d+'a1_default_L.layout.json'))[:3])\n\"", "description": "Inspect descriptor id tables and shapes"}
```


**← tool result**

```
      8 a1_dbins_coarse
      8 a1_dbins_fine
      8 a1_dbins_short
      8 a1_default
      8 a1_glob_only
      8 a1_hard_typing
      8 a1_hist_only
      8 a1_no_bur
      8 a1_no_hellinger
      8 a1_no_resample
      8 a1_no_usr
      8 a1_pair_only
      8 a1_radius_4
      8 a1_resample_3A
      8 a1_untyped
      8 a1_usr_only
      8 b0_default
      8 b1_default
      8 b1_learned
      2 b4_esm2
      1 b4_esm2_ids.parquet
      1 b4_esm2_provenance.json
      1 b5_epocs.npy
      1 b5_epocs_ids.parquet
      1 b5_epocs_provenance.json
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
b1_learned_L.layout.json
b1_learned_L.npy
b4_esm2_D.npy
b4_esm2_L.npy
b4_esm2_ids.parquet
b4_esm2_provenance.json
b5_epocs.npy
b5_epocs_ids.parquet
b5_epocs_provenance.json
a1_default_L (7524, 11) ['row', 'pocket_id', 'structure_key', 'mode', 'status', 'error', 'n_points', 'volume_A3', 'n_cells', 'time_ms', 'io_ms']
   row       pocket_id structure_key mode status error  n
… [13,240 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:37:54

```
{"command": "cat configs/a1_grid.yaml; ls configs; python3 -c \"\nimport json;l=json.load(open('data/processed/descriptors/tough_m1/a1_default_L.layout.json'));print([(b['name'],b['start'],b['stop']) for b in l])\nfor c in ['hist_only','glob_only','untyped','usr_only']:\n  l=json.load(open(f'data/processed/descriptors/tough_m1/a1_{c}_L.layout.json'));print(c,[(b['name'],b['start'],b['stop']) for b in l])\n\"; grep -n \"score_weights\\|block_weights\" -r src scripts | head", "description": "Read A1 grid config and layouts"}
```


**← tool result**

```
# A1 typed volumetric fingerprint — pre-registered configuration grid (DESIGN §3 "A1", <= 20 configs).
# Written 2026-10-27 before any label was available. Each entry overrides
# pocketcompare.descriptors.a1.DEFAULT_CONFIG recursively (see a1.make_config); `resample: null` disables
# resampling. Selection (DESIGN §4): mean cluster-balanced AUC over TOUGH-M1-dev and BLiPS-val; the simplest
# config within one SE of the best wins. "Simplest" = fewest vector dimensions; ties go to the earlier entry.
# Scoring of every config: z-score on the reference (train/dev) pool, then cosine; block-weighted cosine with
# DEFAULT_CONFIG.score_weights (hist/pair/usr/glob 1, size 0.25) is evaluated as a scoring variant of `default` only.
version: a1-grid-v1
configs:
  default: {}                       # soft typing 4.5 Å, 2 Å lattice, bur16 tertiles, 14 bins 2-20 Å σ 1, all blocks, Hellinger
  # --- each block alone
  hist_only:  {blocks: [hist]}
  pair_only:  {blocks: [pair]}
  usr_only:   {blocks: [usr]}       # typed USRCAT-like moments alone
  glob_only:  {blocks: [glob]}
  # --- transforms / typing / sampling
  no_hellinger: {hellinger: false}
  hard_typing:  {typing: {mode: hard}}            # VolSite argmax: type of the nearest atom within 4.5 Å
  radius_4:     {typing: {radius: 4.0}}           # VolSite's original 4 Å typing radius (soft)
  no_resample:  {resample: null}                  # raw BURROW points weighted by vol (1 dense, 27 coarse)
  resample_3A:  {resample: {spacing: 3.0}}
… [1,984 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:38:09

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd, numpy as np\ng=pd.read_parquet('data/processed/docking/tough_m1/pocket_geom.parquet'); print(g.shape, g.columns.tolist()); print(g.head(2).T)\nfor f in ['fragments','leadlike_dmode']:\n    r=pd.read_parquet(f'data/processed/docking/tough_m1/{f}.parquet'); print(f, r.shape, r.columns.tolist(), r.pocket_id.nunique(), r.mol_id.nunique(), r.seed.unique() if 'seed' in r else None, r.panel.unique()); print(r.head(2).T)\ns=pd.read_parquet('data/splits/tough_m1_pockets_split.parquet'); dev=set(s.pocket_id[s.partition=='dev'])\nr=pd.read_parquet('data/processed/docking/tough_m1/fragments_dmode.parquet'); print('dev with D dock', len(dev & set(r.pocket_id)))\nix=pd.read_parquet('data/processed/cache/points/tough_m1/index.parquet'); ixd=ix[ix.pocket_id.isin(dev)]\ndm=(ixd.d_coverage>=0.3)|(ixd.d_precision>=0.5); print('dev dmatch', dm.sum(), 'cov>=.3', (ixd.d_coverage>=0.3).sum(), 'd_missed false', (~ixd.d_missed).sum())\nprint('dmatch but no dock', (dm & ~ixd.pocket_id.isin(set(r.pocket_id))).sum())\nprint(ixd.status.value_counts())\n\"; ls data/processed/docking/tough_m1/raw_L | head", "description": "Inspect A2 docking raw tables and D-mode coverage"}
```


**← tool result**

```
(7524, 15) ['pocket_id', 'volume_L', 'volume_D', 'bur16_L', 'bur16_D', 'n_points_L', 'n_points_D', 'cx', 'cy', 'cz', 'dx', 'dy', 'dz', 'receptor', 'd_matched']
                                                            0                                                  1
pocket_id                                      tough_m1:11asA                                     tough_m1:13pkD
volume_L                                                154.0                                              454.0
volume_D                                                 76.0                                              963.0
bur16_L                                              0.968831                                           0.839648
bur16_D                                              0.974123                                           0.855729
n_points_L                                                155                                                429
n_points_D                                                 77                                                889
cx                                                  26.839748                                          -3.787205
cy                                                   17.47168                                          87.349434
cz                                                   8.881777                                         118.531487
dx                                                  28.266813                                    
… [2,935 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:39:44

```
{"command": "source .venv/bin/activate && git status --short | head -20; git log --oneline | head -5; ls results/trials.tsv results/dev 2>&1; sed -n 1,40p scripts/check_report.py; python -c \"\nimport pandas as pd\np=pd.read_parquet('data/splits/tough_m1_dev_pairs.parquet')\nc=['apoc_c1','apoc_c2','glosa_c1','siteengine_c1','siteengine_c2','siteengine_c3','tm_score']\nprint(p[c].corr(method='spearman').round(2).to_string())\nprint((p[c]==0).sum().to_string())\n\"; nproc", "description": "Check git state, check_report format, label-free score correlations"}
```


**← tool result**

```
 M scripts/a2/dock_tough_m1.py
 M scripts/a2/run_dock.sh
?? results/audit/
?? scripts/a2/prep_pockets_ppips.py
8ee839b tree: P3/P4 plan
373856f Homology graph + TOUGH-M1/BLiPS splits; D8/D9
2ad6d9d A2 docking profiles on TOUGH-M1 (fragments + lead-like)
95ce9f3 B4 ESM-2 + B5 EPoCS baselines on TOUGH-M1
d77ef60 PPI datasets (PPIPS built; PPI-L gate failed -> C3 exploratory)
ls: cannot access 'results/trials.tsv': No such file or directory
ls: cannot access 'results/dev': No such file or directory
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
* Match rul
… [1,866 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:40:10

```
{"command": "source .venv/bin/activate && OMP_NUM_THREADS=1 python -c \"\nimport numpy as np, time\nfrom pocketcompare import evaluate as ev\nrng=np.random.default_rng(0); n=9829\ny=rng.random(n)<0.34; s=rng.normal(size=n)+0.3*y; cov=rng.normal(size=(n,2)); pc=rng.integers(0,76,n)\nci=rng.integers(0,146,n); cj=rng.integers(0,146,n)\ndef fn(w):\n    return [ev.cluster_balanced_auc(y,s,pc,w)['auc_cb'], ev.stratified_auc(y,s,cov,w,n_bins=(5,20))['auc_strat']]\nt=time.time(); r=ev.vertex_bootstrap_generic(fn,ci,cj,B=50); print((time.time()-t)/50*2000,'s per 2000')\n\"\n", "description": "Benchmark generic bootstrap speed"}
```


**← tool result**

```
21.671056747436523 s per 2000
```


**→ tool call `Bash`** · 2026-10-27 20:40:21

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd, numpy as np, glob\nd='data/processed/descriptors/tough_m1/'\nref=pd.read_parquet(d+'a1_default_L.ids.parquet').pocket_id.tolist()\nfor f in sorted(glob.glob(d+'*.ids.parquet'))+[d+'b4_esm2_ids.parquet',d+'b5_epocs_ids.parquet']:\n    x=pd.read_parquet(f); same=x.pocket_id.tolist()==ref\n    st=x.status.value_counts().to_dict() if 'status' in x else ''\n    rowok=(x['row'].values==np.arange(len(x))).all() if 'row' in x else ''\n    print(f.split('/')[-1], same, st, rowok, x.get('d_match',pd.Series()).sum() if 'd_match' in x else '')\nx=pd.read_parquet(d+'b5_epocs_ids.parquet'); print(x.has_epocs.all())\nx=pd.read_parquet(d+'b4_esm2_ids.parquet'); print(x[['L_found','L_missing','D_has','D_missed','D_found','D_missing']].describe().T)\nprint(np.isnan(np.load(d+'b1_default_L.npy')).sum(), np.isnan(np.load(d+'a1_default_D.npy')).sum())\nix=pd.read_parquet('data/processed/cache/points/tough_m1/index.parquet'); print(ix.pocket_id.tolist()==ref)\na=pd.read_parquet(d+'a1_default_D.ids.parquet'); print(((a.d_coverage>=0.3)|(a.d_precision>=0.5)).equals(a.d_match), (a.d_coverage.values==ix.d_coverage.values).all())\nprint(a[~a.d_match].status.value_counts(), np.abs(np.load(d+'a1_default_D.npy')[~a.d_match.values]).sum())\nb0=np.load(d+'b0_default_L.npy'); print(b0[:3].ravel(), np.log(ix.volume_A3.values[:3]))\n\"\n", "description": "Verify descriptor row alignment and D-match fields"}
```


**← tool result**

```
a1_dbins_coarse_D.ids.parquet True {'ok': 7524} True 7112
a1_dbins_coarse_L.ids.parquet True {'ok': 7524} True 
a1_dbins_fine_D.ids.parquet True {'ok': 7524} True 7112
a1_dbins_fine_L.ids.parquet True {'ok': 7524} True 
a1_dbins_short_D.ids.parquet True {'ok': 7524} True 7112
a1_dbins_short_L.ids.parquet True {'ok': 7524} True 
a1_default_D.ids.parquet True {'ok': 7524} True 7112
a1_default_L.ids.parquet True {'ok': 7524} True 
a1_glob_only_D.ids.parquet True {'ok': 7524} True 7112
a1_glob_only_L.ids.parquet True {'ok': 7524} True 
a1_hard_typing_D.ids.parquet True {'ok': 7524} True 7112
a1_hard_typing_L.ids.parquet True {'ok': 7524} True 
a1_hist_only_D.ids.parquet True {'ok': 7524} True 7112
a1_hist_only_L.ids.parquet True {'ok': 7524} True 
a1_no_bur_D.ids.parquet True {'ok': 7524} True 7112
a1_no_bur_L.ids.parquet True {'ok': 7524} True 
a1_no_hellinger_D.ids.parquet True {'ok': 7524} True 7112
a1_no_hellinger_L.ids.parquet True {'ok': 7524} True 
a1_no_resample_D.ids.parquet True {'ok': 7524} True 7112
a1_no_resample_L.ids.parquet True {'ok': 7524} True 
a1_no_usr_D.ids.parquet True {'ok': 7524} True 7112
a1_no_usr_L.ids.parquet True {'ok': 7524} True 
a1_pair_only_D.ids.parquet True {'ok': 7524} True 7112
a1_pair_only_L.ids.parquet True {'ok': 7524} True 
a1_radius_4_D.ids.parquet True {'ok': 7524} True 7112
a1_radius_4_L.ids.parquet True {'ok': 7524} True 
a1_resample_3A_D.ids.parquet True {'ok': 7524} True 7112
a1_resample_3A_L.ids.parquet True {'ok': 7524} True 
a1_u
… [1,057 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:41:03

```
{"command": "grep -n \"score_weights\" -A3 src/pocketcompare/descriptors/a1.py | head; grep -n \"def make_config\\|def load_grid\\|yaml\" src/pocketcompare/descriptors/a1.py | head; source .venv/bin/activate; python -c \"import sklearn, threadpoolctl, yaml; print(sklearn.__version__)\"", "description": "Check A1 score weights and available libs"}
```


**← tool result**

```
129:    "score_weights": {"hist": 1.0, "pair": 1.0, "usr": 1.0, "glob": 1.0, "size": 0.25},
130-}
131-BLOCK_ORDER = ("hist", "pair", "usr", "glob", "size")
132-
6:Pipeline (every step is a parameter of the config dict, see ``DEFAULT_CONFIG`` and configs/a1_grid.yaml):
144:def make_config(overrides: dict | None = None) -> dict:
1.9.1
```


### Assistant · 2026-10-27 20:42:10

Now I have enough context. Let me write the evaluation script.


**→ tool call `Write`** · 2026-10-27 20:44:38

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/eval_dev.py", "content": "#!/usr/bin/env python\n\"\"\"Development evaluation of every pocket-similarity arm on a dev split (DESIGN v2 §3, §4; amendment D6).\n\n    python scripts/eval_dev.py --dataset tough_m1            # TOUGH-M1-dev, B = 2000, seed SEEDS[0]\n    python scripts/eval_dev.py --dataset tough_m1 --B 50 --out <scratch> --no-trials     # smoke test\n\nReusable for BLiPS-val / PPIPS-val: everything dataset-specific lives in a ``DevDataset`` adapter (pairs + labels,\npocket table with bootstrap units, L-mode log volume, D-mode match flag, positive clusters, descriptor / docking\nlocations, natively shipped pair scores).  Only ``ToughM1Dev`` is implemented; ``BlipsVal`` documents what the\nBLiPS adapter must provide.\n\nAll metrics come from the frozen ``pocketcompare.evaluate``; result files get provenance sidecars and every\nevaluated arm / config / variant / mode is appended to ``results/trials.tsv`` (unless ``--no-trials``).\n\nAnalysis choices fixed in this file BEFORE the first run (not tuned afterwards)\n------------------------------------------------------------------------------\n* Units (vertex bootstrap): connected components of (ligand cluster ∪ homology group) over the partition's pockets.\n  Positive cluster for the cluster-balanced AUC: connected component of the positive-pair graph (DESIGN §4).\n* Size strata: covariate = L-mode log volume of both pockets (``evaluate.size_covari
… [43,750 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/eval_dev.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-27 20:56:35

```
{"command": "source .venv/bin/activate && timeout 3000 python scripts/eval_dev.py --dataset tough_m1 --B 50 --out /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/smoke --no-trials 2>&1 | tail -40", "description": "Smoke test eval_dev.py with B=50 to scratch", "timeout": 3100000}
```


**← tool result**

```
[    0.4s] 731 pockets, 9829 pairs (3366 pos); 146 units (largest 438 pockets), 126 units in pairs; D-set 7866 pairs
[    0.4s]   b1 default done
[    0.5s]   b1 learned done
[    0.6s]   a1 default done
[    0.6s]   a1 hist_only done
[    0.7s]   a1 pair_only done
[    0.7s]   a1 usr_only done
[    0.7s]   a1 glob_only done
[    0.9s]   a1 no_hellinger done
[    1.0s]   a1 hard_typing done
[    1.1s]   a1 radius_4 done
[    1.1s]   a1 no_resample done
[    1.2s]   a1 resample_3A done
[    1.3s]   a1 dbins_coarse done
[    1.3s]   a1 dbins_fine done
[    1.4s]   a1 dbins_short done
[    1.5s]   a1 no_bur done
[    1.5s]   a1 untyped done
[    1.6s]   a1 no_usr done
[    1.7s]   B4 done
[    1.9s]   B5 done
[    2.3s]   A2 fragments L done
[    2.7s]   A2 leadlike L done
[    2.9s]   A2 fragments D done
[    3.3s]   A2 leadlike D done
[    6.1s] 122 score vectors built
[    6.1s] generic bootstrap (cluster-balanced + stratified AUC) for 122 vectors, B=50
[    7.8s]     generic bootstrap 20/122 (2 s)
[    8.2s]     generic bootstrap 40/122 (2 s)
[    8.6s]     generic bootstrap 60/122 (3 s)
[    9.1s]     generic bootstrap 80/122 (3 s)
[    9.7s]     generic bootstrap 100/122 (4 s)
[   10.1s]     generic bootstrap 120/122 (4 s)
[   10.5s] A1 selection: best no_bur cb=0.8000 SE=0.0323 -> chosen pair_only
[   11.3s] generic bootstrap for 15 fusion/control vectors
[   12.8s] fast-path bootstrap (AUC, AP) and table
[   18.3s] A2 gate (primary): Δ strat = -0.0027 [-0.0196, 0.0134] -
… [173 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 20:57:03

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/smoke && source /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/activate && python -c \"\nimport pandas as pd; pd.set_option('display.width',250)\ns=pd.read_parquet('tough_m1_dev_summary.parquet')\nprint(s[['arm','config','variant','mode','n_pairs','n_pos','auc','ap','auc_cb','auc_strat','strat_n_strata_dropped','strat_frac_pos_dropped']].round(3).to_string())\n\"; python -c \"\nimport json; d=json.load(open('tough_m1_dev_details.json')); print(json.dumps(d['units'],indent=0)); print(d['pos_clusters'], d['d_mode']); print(json.dumps(d['build']['folds'])[:1500]); print(d['build']['b0m'])\"", "description": "Inspect smoke-test summary"}
```


**← tool result**

```
        arm                         config        variant    mode  n_pairs  n_pos    auc     ap  auc_cb  auc_strat  strat_n_strata_dropped  strat_frac_pos_dropped
0        B0                        default            raw       L     9829   3366  0.780  0.574   0.766      0.520                      20                     0.0
1        B0                        default            raw       D     7866   2825  0.530  0.378   0.484      0.523                      21                     0.0
2       B0p                       tm_score         native  native     9829   3366  0.508  0.344   0.539      0.493                      20                     0.0
3       B0p                   seq_identity         native  native     9829   3366  0.525  0.359   0.518      0.530                      20                     0.0
4       B5T                        apoc_ps         native  native     9829   3366  0.600  0.420   0.506      0.582                      20                     0.0
5       B5T                      apoc_negp         native  native     9829   3366  0.585  0.414   0.527      0.571                      20                     0.0
6       B5T                       glosa_ga         native  native     9829   3366  0.646  0.465   0.577      0.611                      20                     0.0
7       B5T                  siteengine_c1         native  native     9829   3366  0.680  0.435   0.675      0.672                      20                     0.0
8       B5T                  site
… [23,680 more characters; full text in agent_logs/raw/]
```


<details><summary>thinking · 2026-10-27 20:57:41</summary>

The smoke test reveals that between-fold intercept shifts are distorting pooled cross-fitted scores (e.g., AUC drops from 0.80 raw to 0.43 cross-fitted). I'll fix cross-fitting to use globally comparable, intercept-free unit-norm features while preserving the original implementation as a diagnostic reference.



</details>


**→ tool call `Edit`** · 2026-10-27 20:57:51

```
{"replace_all": false, "file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/eval_dev.py", "old_string": "def cross_fit(X, y, fa, fb, n_folds=N_FOLDS):\n    \"\"\"Out-of-fold logistic-regression decision values; fully unit-disjoint (see module docstring).\"\"\"\n    from sklearn.linear_model import LogisticRegression\n    from sklearn.pipeline import make_pipeline\n    from sklearn.preprocessing import StandardScaler\n\n    oof = np.full(len(y), np.nan)\n    info, coefs = [], []\n    for k in range(n_folds):\n        for l in range(k, n_folds):\n            test = ((fa == k) & (fb == l)) | ((fa == l) & (fb == k))\n            if not test.any():\n                continue\n            train = ~np.isin(fa, [k, l]) & ~np.isin(fb, [k, l])\n            m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))\n            m.fit(X[train], y[train])\n            oof[test] = m.decision_function(X[test])\n            coefs.append(m[-1].coef_.ravel().tolist())\n            info.append({\"folds\": [k, l], \"n_test\": int(test.sum()), \"n_train\": int(train.sum()),\n                         \"n_train_pos\": int(y[train].sum())})\n    assert np.isfinite(oof).all()\n    return oof, {\"fits\": info, \"coef_mean\": np.mean(coefs, 0).tolist(), \"coef_min\": np.min(coefs, 0).tolist(),\n                 \"coef_max\": np.max(coefs, 0).tolist()}", "new_string": "def cross_fit(X, y, fa, fb, n_folds=N_FOLDS, *, method=\"direction\"):\n    \"\"\"Out-of-fold logisti
… [2,136 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
The file /cluster/project/beltrao/gmagnus/pocket_compare/scripts/eval_dev.py has been updated successfully. (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-27 20:58:03

```
{"command": "python3 - <<'EOF'\np='scripts/eval_dev.py'; s=open(p).read()\nold=\"\"\"  (L2, C = 1).  Scores are out-of-fold decision values; bootstraps use those fixed OOF scores.\"\"\"\nnew=\"\"\"  (L2, C = 1) on features z-scored once over all evaluated pairs (label-free).  OOF score = x · β/‖β‖ without\n  intercept.  DEVIATION (found in a B = 50 smoke run, before the B = 2000 run): the first implementation\n  (per-fold scaler + decision_function with intercept) pooled scores whose fold-set intercepts differ because the\n  training-set prevalence ranges 5–44 % (one unit holds 60 % of the dev pockets); it gave B0m stratified AUC 0.24\n  and a cross-fitted A1-alone AUC of 0.43 vs 0.80 raw.  Its point metrics are kept in the details file\n  (\"crossfit_decision_diagnostic\").  Bootstraps use the fixed OOF scores.\"\"\"\nassert old in s; s=s.replace(old,new)\nold=\"\"\"    meta[\"fusion\"] = fus_info\"\"\"\nnew=\"\"\"    meta[\"fusion\"] = fus_info\n    diag = {}\n    for name, X in ((\"B0m\", Xb0), (\"A1|raw\", np.column_stack(fusions[\"A1|raw\"])),\n                    (\"A1+A2frag|raw\", np.column_stack(fusions[\"A1+A2frag|raw\"]))):\n        o, _ = cross_fit(X, y_all.astype(int), fa, fb, method=\"decision\")\n        diag[name] = point_metrics(y_all, o, pc_all, cov_all)\n    meta[\"crossfit_decision_diagnostic\"] = diag\"\"\"\nassert old in s; s=s.replace(old,new)\nopen(p,'w').write(s)\nEOF\nsource .venv/bin/activate && timeout 3000 python scripts/eval_dev.py --dataset toug
… [909 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
[    7.8s] A1 selection: best no_bur cb=0.8000 SE=0.0323 -> chosen pair_only
[    8.6s] generic bootstrap for 15 fusion/control vectors
[   10.3s] fast-path bootstrap (AUC, AP) and table
[   14.9s] A2 gate (primary): Δ strat = -0.0097 [-0.0281, 0.0097] -> FAIL
[   16.5s] done: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/smoke/tough_m1_dev_summary.parquet
        arm                         config        variant    auc     ap  auc_cb  auc_strat
120    CTRL                      random128        control  0.506  0.346   0.488      0.499
121     B0m              logit_sum_absdiff       crossfit  0.857  0.704   0.881      0.489
122  FUSION               A1[A1=pair_only]   crossfit_raw  0.795  0.635   0.798      0.732
123  FUSION        A1+A2frag[A1=pair_only]   crossfit_raw  0.789  0.613   0.796      0.722
124  FUSION        A1+A2lead[A1=pair_only]   crossfit_raw  0.786  0.593   0.796      0.718
125  FUSION        A1+A2both[A1=pair_only]   crossfit_raw  0.785  0.592   0.794      0.718
126  FUSION            A1+B1[A1=pair_only]   crossfit_raw  0.787  0.594   0.797      0.716
127  FUSION     A1+B1+A2frag[A1=pair_only]   crossfit_raw  0.784  0.588   0.795      0.713
128  FUSION     A1+A2frag+B4[A1=pair_only]   crossfit_raw  0.791  0.616   0.804      0.728
129  FUSION               A1[A1=pair_only]  crossfit_csls  0.793  0.624   0.795      0.724
130  FUSION        A1+A2frag[A1=pair_only]  crossfit_csls  0.789  0.610
… [777 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 20:58:29

Cross-fitting now behaves: B0m stratified AUC 0.489 (within 0.5 ± 0.03), and cross-fitted A1-alone reproduces raw A1. Launching the full B = 2000 run (writes results/dev and appends to trials.tsv).


**→ tool call `Bash`** · 2026-10-27 20:58:29

```
{"command": "source .venv/bin/activate && mkdir -p logs && nohup python scripts/eval_dev.py --dataset tough_m1 > logs/eval_dev_tough_m1.log 2>&1 &\necho $! > logs/eval_dev_tough_m1.pid; cat logs/eval_dev_tough_m1.pid", "description": "Launch full dev evaluation in background"}
```


**← tool result**

```
932211
```


**→ tool call `ToolSearch`** · 2026-10-27 20:58:33

```
{"query": "select:Monitor", "max_results": 1}
```


**← tool result**

```
[non-text content]
```


**→ tool call `Bash`** · 2026-10-27 20:58:36

```
{"command": "until ! kill -0 $(cat logs/eval_dev_tough_m1.pid) 2>/dev/null; do sleep 5; done; tail -8 logs/eval_dev_tough_m1.log", "description": "Wait for the full evaluation run to finish", "run_in_background": true}
```


**← tool result**

```
Command running in background with ID: bcxyfcsvc. Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bcxyfcsvc.output. You will be notified when it completes — do not poll that file or sleep while waiting. Read the file only if the user asks for progress, or if you need a line it prints before you can go on, such as a server's ready line or port.
```


### Assistant · 2026-10-27 20:58:38

I'll wait for the run to finish.


**→ tool call `Bash`** · 2026-10-27 20:58:40

```
{"command": "until ! kill -0 $(cat logs/eval_dev_tough_m1.pid) 2>/dev/null; do sleep 5; done; tail -8 logs/eval_dev_tough_m1.log", "description": "Block until evaluation finishes, then show log tail", "timeout": 1800000}
```


**← tool result**

```
[   89.1s]     generic bootstrap 80/122 (85 s)
[  112.0s]     generic bootstrap 100/122 (108 s)
[  125.6s]     generic bootstrap 120/122 (122 s)
[  132.0s] A1 selection: best no_bur cb=0.8000 SE=0.0289 -> chosen pair_only
[  132.7s] generic bootstrap for 15 fusion/control vectors
[  154.3s] fast-path bootstrap (AUC, AP) and table
[  163.1s] A2 gate (primary): Δ strat = -0.0097 [-0.0273, 0.0072] -> FAIL
[  173.8s] done: /cluster/project/beltrao/gmagnus/pocket_compare/results/dev/tough_m1_dev_summary.parquet
```


**→ tool call `Bash`** · 2026-10-27 21:01:31

```
{"command": "source .venv/bin/activate && wc -l results/trials.tsv && ls results/dev && python -c \"\nimport pandas as pd, json; pd.set_option('display.width',300)\ns=pd.read_parquet('results/dev/tough_m1_dev_summary.parquet')\nc=['arm','config','variant','mode','n_pairs','auc','auc_lo','auc_hi','ap','ap_lift','pauc_mcclish','auc_cb','auc_cb_lo','auc_cb_hi','auc_strat','auc_strat_lo','auc_strat_hi']\nprint(s[~s.arm.isin(['A1'])|s.config.isin(['pair_only','default','no_bur'])][c+['auc_worst_all','miss_rate_pos_all','miss_rate_neg_all']].round(3).to_string())\nd=json.load(open('results/dev/tough_m1_dev_details.json'))\nprint(json.dumps(d['selection'],indent=0)[:2500]); print(json.dumps(d['mde'],indent=0)[:4000]); print(d['units'], d['build']['crossfit_decision_diagnostic']['B0m']['auc_strat'])\n\"", "description": "Inspect final summary, selection, MDE"}
```


**← tool result**

```
138 results/trials.tsv
tough_m1_dev_details.json
tough_m1_dev_details.json.prov.json
tough_m1_dev_replicates.parquet
tough_m1_dev_replicates.parquet.prov.json
tough_m1_dev_summary.md
tough_m1_dev_summary.md.prov.json
tough_m1_dev_summary.parquet
tough_m1_dev_summary.parquet.prov.json
        arm                         config        variant    mode  n_pairs    auc  auc_lo  auc_hi     ap  ap_lift  pauc_mcclish  auc_cb  auc_cb_lo  auc_cb_hi  auc_strat  auc_strat_lo  auc_strat_hi  auc_worst_all  miss_rate_pos_all  miss_rate_neg_all
0        B0                        default            raw       L     9829  0.780   0.696   0.844  0.574    1.678         0.552   0.766      0.729      0.833      0.520         0.457         0.573            NaN                NaN                NaN
1        B0                        default            raw       D     7866  0.530   0.422   0.574  0.378    1.051         0.501   0.484      0.426      0.572      0.523         0.357         0.576          0.347              0.161              0.220
2       B0p                       tm_score         native  native     9829  0.508   0.455   0.593  0.344    1.005         0.500   0.539      0.422      0.585      0.493         0.439         0.640            NaN                NaN                NaN
3       B0p                   seq_identity         native  native     9829  0.525   0.481   0.551  0.359    1.048         0.502   0.518      0.474      0.557      0.530         0.420         0.560            NaN    
… [24,179 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 21:01:41

```
{"command": "sed -n '/## A1 selection/,$p' results/dev/tough_m1_dev_summary.md; head -2 results/trials.tsv | cut -c1-400", "description": "Read gate, CSLS, L-vs-D and MDE sections"}
```


**← tool result**

```
## A1 selection
best no_bur (cb 0.8000, SE 0.0289); within one SE: default, pair_only, no_hellinger, hard_typing, radius_4, no_resample, resample_3A, dbins_coarse, dbins_fine, no_bur, no_usr; **chosen pair_only**.

## A2 gate and fusions (Δ size-stratified AUC vs cross-fitted A1 alone)

| fusion | inputs | Δ strat [CI] | Δ AUC [CI] | gate |
|---|---|---|---|---|
| A1+A2frag | raw | -0.0097 [-0.0273, +0.0072] | -0.0066 [-0.0108, -0.0010] | FAIL |
| A1+A2lead | raw | -0.0145 [-0.0263, +0.0097] | -0.0086 [-0.0151, +0.0025] | FAIL |
| A1+A2both | raw | -0.0145 [-0.0440, +0.0037] | -0.0105 [-0.0213, -0.0003] | FAIL |
| A1+B1 | raw | -0.0162 [-0.0195, +0.0054] | -0.0083 [-0.0112, +0.0014] |  |
| A1+B1+A2frag | raw | -0.0195 [-0.0272, +0.0049] | -0.0115 [-0.0153, -0.0000] |  |
| A1+A2frag+B4 | raw | -0.0041 [-0.0357, +0.0126] | -0.0037 [-0.0162, +0.0058] |  |
| A1+A2frag | csls | -0.0045 [-0.0374, +0.0139] | -0.0041 [-0.0161, -0.0004] | FAIL |
| A1+A2lead | csls | -0.0187 [-0.0303, +0.0021] | -0.0137 [-0.0217, +0.0034] | FAIL |
| A1+A2both | csls | -0.0184 [-0.0394, +0.0117] | -0.0151 [-0.0254, +0.0046] | FAIL |
| A1+B1 | csls | -0.0139 [-0.0169, +0.0080] | -0.0068 [-0.0094, +0.0026] |  |
| A1+B1+A2frag | csls | -0.0128 [-0.0365, +0.0180] | -0.0068 [-0.0140, +0.0044] |  |
| A1+A2frag+B4 | csls | -0.0088 [-0.0437, +0.0162] | -0.0082 [-0.0235, -0.0025] |  |

## CSLS − raw (paired)

| arm | config | mode | Δ AUC [CI] | Δ cb [CI] | Δ strat [CI] |
|---|---|---|---|---|---|
| B1 | default
… [11,856 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 21:02:00

Key results are in. Let me generate the report table programmatically from the summary (avoids transcription errors), then write the report.


**→ tool call `Bash`** · 2026-10-27 21:02:11

```
{"command": "source .venv/bin/activate && python -c \"\nimport pandas as pd\ns=pd.read_parquet('results/dev/tough_m1_dev_summary.parquet').set_index('key')\nrows=[('B0|default|raw|L','B0 size −|Δlog V|'),('B0m|logit_sum_absdiff|crossfit|L','B0m size logistic (cf)'),\n('B0p|tm_score|native|native','B0′ global TM-score'),('B1|default|raw|L','B1 BURROW desc.'),('B1|default|csls|L','B1 CSLS'),\n('B4|esm2|raw|L','B4 ESM-2 (z)'),('B4|esm2_noz|raw|L','B4 ESM-2 (raw cos)'),('B5|epocs|raw|L','B5 EPoCS'),\n('B5T|apoc_ps|native|native','B5-T APoc PS'),('B5T|apoc_negp|native|native','B5-T APoc −P'),('B5T|glosa_ga|native|native','B5-T G-LoSA GA'),\n('B5T|siteengine_c1|native|native','B5-T SiteEngine c1*'),('B5T|siteengine_c2|native|native','B5-T SiteEngine c2*'),('B5T|siteengine_c3|native|native','B5-T SiteEngine c3*'),\n('A1|pair_only|raw|L','**A1 pair_only (chosen)**'),('A1|pair_only|csls|L','A1 pair_only CSLS'),('A1|no_bur|raw|L','A1 no_bur (best cb)'),('A1|default|raw|L','A1 default'),\n('A1|hist_only|raw|L','A1 hist_only'),('A1|untyped|raw|L','A1 untyped'),\n('A2|fragments_rank|raw|L','A2 frag rank'),('A2|fragments_le_resid|raw|L','A2 frag LE-resid'),('A2|fragments_ifp|raw|L','A2 frag IFP'),('A2|fragments_ifp|csls|L','A2 frag IFP CSLS'),\n('A2|leadlike_rank|raw|L','A2 lead rank'),('A2|leadlike_le_resid|raw|L','A2 lead LE-resid'),('A2|leadlike_ifp|raw|L','A2 lead IFP'),\n('FUSION|A1+A2frag[A1=pair_only]|crossfit_raw|L','Fusion A1+A2frag (cf)'),('FUSION|A1+B1[A1=pair_only]|crossfit_raw
… [947 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
| arm (L-mode, 9,829 pairs) | ROC-AUC [95 % CI] | AP (lift) | pAUC₀.₁ | cluster-bal. AUC [CI] | size-strat. AUC [CI] |
|---|---|---|---|---|---|
| B0 size −|Δlog V| | 0.780 [0.696, 0.844] | 0.574 (1.68) | 0.552 | 0.766 [0.729, 0.833] | 0.520 [0.457, 0.573] |
| B0m size logistic (cf) | 0.857 [0.824, 0.959] | 0.704 (2.06) | 0.625 | 0.881 [0.849, 0.930] | 0.489 [0.420, 0.709] |
| B0′ global TM-score | 0.508 [0.455, 0.593] | 0.344 (1.01) | 0.500 | 0.539 [0.422, 0.585] | 0.493 [0.439, 0.640] |
| B1 BURROW desc. | 0.643 [0.549, 0.664] | 0.465 (1.36) | 0.531 | 0.632 [0.584, 0.701] | 0.630 [0.461, 0.659] |
| B1 CSLS | 0.645 [0.553, 0.667] | 0.468 (1.37) | 0.533 | 0.640 [0.594, 0.710] | 0.628 [0.462, 0.658] |
| B4 ESM-2 (z) | 0.601 [0.514, 0.625] | 0.431 (1.26) | 0.522 | 0.624 [0.558, 0.680] | 0.600 [0.483, 0.632] |
| B4 ESM-2 (raw cos) | 0.575 [0.480, 0.624] | 0.404 (1.18) | 0.516 | 0.572 [0.483, 0.634] | 0.575 [0.497, 0.670] |
| B5 EPoCS | 0.599 [0.429, 0.642] | 0.429 (1.25) | 0.524 | 0.552 [0.466, 0.610] | 0.592 [0.384, 0.640] |
| B5-T APoc PS | 0.600 [0.441, 0.630] | 0.420 (1.23) | 0.517 | 0.506 [0.469, 0.609] | 0.582 [0.358, 0.619] |
| B5-T APoc −P | 0.585 [0.450, 0.616] | 0.414 (1.21) | 0.516 | 0.527 [0.465, 0.597] | 0.571 [0.404, 0.607] |
| B5-T G-LoSA GA | 0.646 [0.432, 0.693] | 0.465 (1.36) | 0.531 | 0.577 [0.478, 0.636] | 0.611 [0.318, 0.667] |
| B5-T SiteEngine c1* | 0.680 [0.624, 0.781] | 0.435 (1.27) | 0.500 | 0.675 [0.603, 0.725] | 0.672 [0.493, 0.705] |
| B5-T SiteEngin
… [2,366 more characters; full text in agent_logs/raw/]
```


**→ tool call `Write`** · 2026-10-27 21:03:01

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/reports/dev_eval_tough_m1.md", "content": "# Dev evaluation of all arms on TOUGH-M1-dev (eval agent, 2026-10-27)\n\n`scripts/eval_dev.py --dataset tough_m1` (B = 2000, seed 0, 16 threads, 174 s). Results: `results/dev/tough_m1_dev_summary.{parquet,md}`,\n`tough_m1_dev_details.json` (selection, gate, MDE, folds), `tough_m1_dev_replicates.parquet`, all with `.prov.json`; 137 rows\nappended to `results/trials.tsv`. Dev = 731 pockets, 9,829 pairs (3,366 pos, prevalence 0.342). Full table (137 rows,\nincl. all 16 A1 configs in L and D mode) in the summary md. Not committed.\n\n## Main table (L-mode unless noted; CIs = 95 % vertex bootstrap, units = ligand cluster ∪ homology group)\n\n| arm | ROC-AUC [CI] | AP (lift) | pAUC₀.₁ | cluster-bal. AUC [CI] | size-strat. AUC [CI] |\n|---|---|---|---|---|---|\n| B0 size, −abs(Δ log V) | 0.780 [0.696, 0.844] | 0.574 (1.68) | 0.552 | 0.766 [0.729, 0.833] | 0.520 [0.457, 0.573] |\n| B0m size logistic (cross-fitted) | 0.857 [0.824, 0.959] | 0.704 (2.06) | 0.625 | 0.881 [0.849, 0.930] | **0.489** [0.420, 0.709] |\n| B0′ global TM-score | 0.508 [0.455, 0.593] | 0.344 (1.01) | 0.500 | 0.539 [0.422, 0.585] | 0.493 [0.439, 0.640] |\n| B1 BURROW descriptors | 0.643 [0.549, 0.664] | 0.465 (1.36) | 0.531 | 0.632 [0.584, 0.701] | 0.630 [0.461, 0.659] |\n| B4 ESM-2, z-scored cosine | 0.601 [0.514, 0.625] | 0.431 (1.26) | 0.522 | 0.624 [0.558, 0.680] | 0.600 [0.483, 0.632] |\n| B4 ESM-2, raw 
… [8,411 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/reports/dev_eval_tough_m1.md (file state is current in your context — no need to Read it back)
```


### Assistant · 2026-10-27 21:03:06

Let me fix the two src tags so they check the right numbers, then run check_report.


**→ tool call `Bash`** · 2026-10-27 21:03:10

```
{"command": "source .venv/bin/activate && python3 - <<'EOF'\np='reports/dev_eval_tough_m1.md'; s=open(p).read()\ns=s.replace(\"\"\"Δ size-stratified AUC = −0.0097 [−0.027, +0.007]\n   <!-- src: results/dev/tough_m1_dev_details.json#gate.A1+A2frag|raw.delta_strat_vs_cf_A1.estimate -->;\"\"\",\n\"\"\"Δ size-stratified AUC = −0.0097 <!-- src: results/dev/tough_m1_dev_details.json#gate.A1+A2frag|raw.delta_strat_vs_cf_A1.estimate -->\n   [−0.027, +0.007];\"\"\")\ns=s.replace(\"\"\"**MDE on test of 0.127**\n   <!-- src: results/dev/tough_m1_dev_details.json#comparisons -->.\"\"\",\n\"\"\"**MDE on test of 0.127** <!-- src: results/dev/tough_m1_dev_details.json#mde.comparisons.chosen_A1_raw:A1|pair_only|raw - B1|default|raw|L.mde_test.mde -->.\"\"\")\nopen(p,'w').write(s)\nEOF\npython scripts/check_report.py --help 2>&1 | head -5; python scripts/check_report.py reports/dev_eval_tough_m1.md 2>&1 | grep -v \"^WARN\\|untagged\" | tail -8", "description": "Fix src tags and run check_report"}
```


**← tool result**

```
usage: check_report.py [-h] [--root ROOT] [--allow-stale-eval]
                       [--fail-untagged]
                       markdown [markdown ...]

Check that numbers in a markdown report match their sidecar'd result files (DESIGN §5).
check_report: 2 tagged numbers OK, 0 errors
```


**→ tool call `Bash`** · 2026-10-27 21:03:15

```
{"command": "git status --short src/ && sha256sum src/pocketcompare/evaluate.py | cut -c1-8 && wc -l reports/dev_eval_tough_m1.md", "description": "Confirm evaluate.py untouched"}
```


**← tool result**

```
 M src/pocketcompare/pockets.py
?? src/pocketcompare/datasets/blips.py
f22d0296
104 reports/dev_eval_tough_m1.md
```


**→ tool call `SubagentHandback`** · 2026-10-27 21:03:27

```
{"message": "The evaluation ran on TOUGH-M1-dev (B=2000, seed 0; 137 rows appended to results/trials.tsv; nothing committed). The A2 gate fails, and A1's L-mode lead over B1 is mostly a ligand imprint.\n\n**Results** (ROC / size-stratified AUC, L-mode)\n\n| Arm | ROC | Stratified |\n|---|---|---|\n| **A1 pair_only (chosen)** | 0.795 | 0.732 |\n| SiteEngine c1 (shipped score) | 0.680 | 0.672 |\n| B1 | 0.643 | 0.630 |\n| B4 | 0.601 | 0.600 |\n| B5 | 0.599 | 0.592 |\n| A2 fragment IFP + CSLS | 0.632 | 0.625 |\n| Controls (random / shuffled) | 0.506 / 0.499 | |\n\n- **A1 config:** 11 of 16 configs fall within one SE (best no_bur, cb 0.800); the one-SE rule picks pair_only (392 dims). BLiPS-val is not in the selection yet.\n- **A2 gate: FAIL.** Δ stratified AUC = −0.010 [−0.027, +0.007]. Every A2 fusion is negative, raw or CSLS.\n- **Size shortcut:** B0 alone gives 0.78 and B0m 0.857. The B0m diagnostic passes (stratified 0.489).\n- **L vs D (biggest risk):** on the same 7,866 pairs A1 drops 0.808 → 0.560, while B1 loses 0.06 and B4 0.02. In D-mode, B1 and B4 beat A1. L-mode pockets are ligand shells, so a C1a win would partly reflect pocket definition.\n- **MDE:** the units have a giant component (dev 438/731 pockets; test 710/1,014 pockets, 141 units). Dev Δ(A1−B1) = +0.152, SE 0.050, so the test MDE is 0.127 — four times the 0.03 SESOI.\n- **CSLS:** small effect, only clearly positive for A2-IFP.\n\n**Disclosures**\n- In a B=50 smoke run, the cross-fitting pooled fold intercept
… [508 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
