# Post-hoc completion of three pre-registered reported items (2026-10-28)

Each item is a **pre-registered reported item, computed post hoc after a bug or omission in final_eval
(disclosed, DEV6)**. None is in the Holm family, and nothing was tuned.
- **Arms:** frozen FINAL (A4b:n1_linear raw), with N1, L4 CSLS, B1 and B4 as references.
- **Code and outputs:** `scripts/post_final_reported.py` → `results/final_post/` (provenance sidecars; tables in
  `final_post_summary.md`).

## 1. C5: paired holo − AF ΔROC-AUC on BLiPS-test (B = 2,000; wider of the hom/lig unit CIs)
| arm | L Δ [95 % CI] (41,379 pairs / 6,896 pos) | D Δ [95 % CI] (19,818 / 3,823, common D set) |
|---|---|---|
| **FINAL** | −0.004 [−0.020, +0.010] | +0.004 [−0.016, +0.028] |
| N1 / L4 CSLS | +0.005 [−0.009, +0.017] / +0.002 [−0.017, +0.023] | −0.004 [−0.025, +0.018] / −0.014 [−0.035, +0.007] |
| B1 / B4 (reproduced) | +0.010 [−0.007, +0.024] / +0.013 [+0.005, +0.020] | −0.013 [−0.043, +0.016] / +0.012 [−0.006, +0.031] |

- **FINAL strata, L / D:**
  - Both holo structures released ≥ 2018-05-01: −0.002 [−0.034, +0.027] / −0.010 [−0.053, +0.031].
  - Both released earlier: −0.012 / +0.011.
  - Pair-minimum site pLDDT ≥ 90: −0.009 [−0.024, +0.008] / +0.005.
  - pLDDT 70–90: +0.006 / +0.007 [−0.030, +0.059].
  - pLDDT < 70: only 43 / 2 positives, uninformative.
- **No AF penalty for FINAL.** Every CI includes 0, and both all-pairs CIs lie within the ±0.03 SESOI.
- **Reproduction:** B1/B4 match `final_details.json` exactly (28/28 entries, 364 fields, **max |dev| = 0**). The
  unpaired AUCs of all 24 vectors equal `final_summary.parquet`.
- **Bug and fix:**
  - **Bug:** final_eval picked the C5 arms with `key.split("|")[1] == method.name`, but the name
    `pocketcompare-final:A4b:n1_linear|raw` contains "|", so FINAL was silently dropped.
  - **Fix:** the new script selects arms by the `Vec` attributes. It imports the frozen functions and hash-checks
    them against FREEZE.json.
- **Supplement (`eval_af_robustness.py --set test`, as designed; its own L/D sets):**
  - FINAL holo/holo − AF/AF: L −0.004 [−0.020, +0.010], D +0.016 [−0.006, +0.038].
  - Same-site holo → AF top-1: FINAL L 0.503 / D 0.350; B1 0.644 / 0.244.
  - FINAL L top-1 falls at pLDDT 70–90 (0.299 vs 0.573 at ≥ 90). Before and after 2018 it is equal (0.514 / 0.488).
  - Its holo/holo − mixed holo/AF Δ is negative for every arm, size included (FINAL −0.020, B0 −0.023). That is
    a score-averaging artefact.

## 2. Blind deployment test on BLiPS-test AF models (`eval_blind.py --set test`, as designed)
- **Set:** 3,600 sites on 2,295 AF models. The pool holds 13,876 merged BURROW pockets, so a query has a median of
  13,859 candidates (chance hit@100 ≈ 0.7 %).
- **Detection:** recall 0.700 [0.676, 0.723]. Both ends were found for 8,048 of 13,792 directed positive pairs.

| both detected (n = 8,048) | hit@10 | hit@100 | MRR | AUC [95 % CI] |
|---|---|---|---|---|
| **FINAL** | 0.016 | 0.078 | 0.009 | 0.719 [0.684, 0.761] |
| B1 / B0 size | 0.012 / 0.002 | 0.059 / 0.019 | 0.007 / 0.001 | 0.688 [0.660, 0.723] / 0.583 |
| FINAL − B1 | +0.003 | +0.019 [0.000, +0.040] | +0.002 | +0.031 [−0.001, +0.057] |

- **Unconditional** (a missed detection counts as a miss): FINAL AUC 0.628, B1 0.610; Δ +0.018 [−0.001, +0.036].
- **FINAL vs B1:** FINAL is ahead, but the gain is borderline. Early retrieval is very low and detection drops 30 %
  of sites.
- **Run details:**
  - **B4 not run:** it needs ESM-2 on 13.9 k pockets, and the script has no B4 arm.
  - **No adapter fixes were needed.** The only wrapper passes the unsealed pairs in memory.
  - **Not comparable with the val dry run,** which used `final` = N1.

## 3. PPIPS-test by BURROW-homology flag (`burrow_rep_edge`; P-ortho by query complex, P-sym by complex)
**Strata.** 136 of 251 test complexes have an edge. P-ortho: 70 queries in 6 units with an edge, 83 in 6
without; every clean query also has a clean partner. P-sym: 352 / 192 queries.

| arm | P-ortho MRR, edge | MRR, no edge | P-sym pct, edge / no edge |
|---|---|---|---|
| **FINAL** | 0.683 [0.518, 0.830] | 0.683 [0.648, 0.883] | 0.998 / 0.998 |
| N1 | 0.707 | 0.603 | 0.998 / 0.997 |
| L4 CSLS | 0.722 | 0.762 | 1.000 / 1.000 |
| B1 | 0.648 | 0.611 | 0.997 / 0.990 |
| B4 ESM-2 | 0.936 | 0.970 | 1.000 / 1.000 |

- **FINAL's ortholog transfer is not inflated by BURROW-homologous complexes.** B4 dominates both strata, and the
  CIs are rough with 6 units per stratum.
- **Secondary flag** `burrow_any_edge`: FINAL 0.681 / 0.687.
- **Reproduction:** the unstratified call equals `final_ppips.parquet` (max |dev| 0).

## Disclosures
- **Sealed reads:** 8, all sha256-OK and restored to mode 000 (`results/final_post/unseal_log.tsv`).
- **Two killed runs:** the first blind and afrob launches used about 46 cores for about 2 min, which breaks the
  24-core budget. I killed them before they wrote output and re-ran them with thread caps.
- **Trial rows:** the designed rows (arms `blind`, `C5`) were appended to `results/trials.tsv`.
- **Frozen files** are unchanged. Nothing is committed.
