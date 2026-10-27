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
  per column. The headline is 5 × 5 strata: quintiles of the pair's mean log-volume × quintiles of |Δ log-volume|,
  with edges from the evaluated pairs. Strata are weighted by their positive weight (Janes & Pepe). Strata
  that lack a class are dropped, and the dropped strata, dropped pairs and lost positive weight are all
  returned. The weightings `min` and `equal` remain available as options.
- **Retrieval:** the rank of the best true hit, with ties broken pessimistically (so a constant scorer gets no
  credit). Gives top-k and MRR. Queries without a hit and NaN scores are counted.
- **Vertex bootstrap:** draw K units with replacement. A pair inside one unit u gets weight w·c_u; a pair across
  units u and v gets w·c_u·c_v (DESIGN v2). Replicates with no positive or no negative weight are counted as
  degenerate and excluded. CIs are percentile intervals; the paired version uses identical replicates for
  both methods; the one-sided p-value is (1 + #{Δ_b ≤ 0}) / (B_valid + 1). The default seed is SEEDS[0], drawn
  in fixed chunks, so results do not depend on the thread count.
- **Helpers:**
  - `macro_paired_bootstrap` (C2): each subset is bootstrapped independently with seed `[seed, k]`, and the
    per-subset values are averaged replicate by replicate.
  - `wider_ci`: for two unit definitions of the same quantity, returns the wider CI.
  - `holm`.
  - `mde` = (z₀.₉₅ + z₀.₈₀)·SE, and `mde_scaled`, which multiplies the dev SE by √(n_dev / n_test) units.
- **Missing scores:** the low-level metrics raise an error on NaN. The policies `common` (the default for paired
  comparisons), `worst` (positive → −inf, negative → +inf) and `min` (deployment) always return counts, including
  per-label miss rates.
- **Provenance:** `<file>.prov.json` records:
  - the git commit and a dirty flag (untracked files are counted separately);
  - the script and its sha256, the args, and the config with its sha256 (canonical JSON, or the file's bytes);
  - the inputs' sha256, or size + mtime_ns for files over 1 GiB;
  - the sha256 of evaluate.py and of the result file;
  - the seed, device, host, start/end time (the process start by default) and wall seconds.

  It refuses to write to `results/final/` from a dirty tree. `trials.tsv` is append-only and protected by a
  flock; a row with a foreign header is refused.
- **check_report:** each number is tagged `<!-- src: path#key -->`; the key is a JSON dotted path or
  `col[filter=val]`. A number matches if it equals the stored value rounded to the decimals shown (a `%` suffix
  is handled). The check fails on a missing sidecar, a result file whose sha256 no longer matches its sidecar,
  or a stale evaluate.py hash. Untagged numbers with ≥ 2 decimals produce a warning (`--fail-untagged` makes
  them errors).

## Timings (eu-g6-048, CPU, numba)
- **1 M pairs × B = 2000, K = 1,300 units:**
  - one method (AUC + AP): **1.7 s** on 16 threads, against about 21 s on 1 thread (extrapolated from B = 200);
  - paired comparison of two methods: **3.1 s** on 16 threads.
- **Test suites:** both together take about 4 s (41 tests); the `slow` coverage test takes 0.7 s.

## Test results: 41/41 pass
- AUC, AP and McClish pAUC equal sklearn to 1e-12 (weighted, with heavy ties, 20 random sets). The hand
  example gives AUC 7.5/9 and AP 29/36.
- Perfect, reversed and all-tied scores give AUC 1, 0 and 0.5.
- Integer weights give the same result as duplicated rows, for every metric.
- The fast bootstrap equals the generic Python path and a manual check of the within-unit weights. The numpy
  fallback equals numba. 1 thread equals 4 threads.
- A method paired with itself gives Δ = 0 and p = 1.
- The degenerate-replicate count matches the exact expectation.
- The worst-case bound ≤ the common-set value for AUC and AP, and min-imputation rewards failures on negatives.
- Holm matches a hand example. Retrieval hand example passes, including the tie modes.

**Coverage** (400 simulated clustered datasets with within-unit positives; target 95 %):

| Bootstrap | 60 units | 20 units |
|---|---|---|
| vertex (c_u for within-unit pairs) | **96.0 %** | **94.3 %** |
| c_u² variant | 98.8 % (over-covers) | not run |
| naive pair bootstrap | 59.5 % | 64.8 % |

**Size shortcut — finding for the PI.** In the simulated size confound, B0 = −|Δ log V| has a pair AUC of 0.74.
The 5 × 5 strata bring it down to 0.539, which removes about 84 % of the shortcut but is **outside the ±0.03
acceptance band**. With 5 × 20 bins it is 0.507. An absolute-size scorer (log V_a + log V_b) stays at 0.536
under 5 × 5. The residual comes from size variation within a quintile. If the B0 / B0m check fails on dev,
refine the |Δ| bins; the test asserts both of these facts.
