# Independent split/leakage audit (2026-10-27 23:05, audit agent)

**Method.** The audit used its own code path: gemmi extraction, then all-vs-all MMseqs2 `easy-search` and exhaustive Foldseek with exact TM-score. It did not use the data agent's sequences, hits or `verify_splits.py`, and it did not open `data/sealed/`.
- Code is in `results/audit/scripts/a1–a4`.
- Numbers are in `results/audit/{mmseqs_checks,foldseek_checks,partition_impact,checks_4_5}.json`.
- Example pairs are in `results/audit/*_examples.tsv`.

**Rule.** An edge is either:
- an MMseqs2 hit (`-s 7.5`, E < 1e‑3) with identity ≥ 0.30 and (qcov or tcov ≥ 0.5, or alnlen ≥ 80), as in `apply_rule`; or
- a Foldseek hit with min(qTM, tTM) ≥ 0.5.

## Verdict: FAIL (small but real leaks). Main cause: a bug in the MMseqs2 call

**Bug.** `scripts/data/build_homology_graph.py:367` runs `mmseqs search` **without `-a`**. Without backtraces, `convertalis` reports `fident` and `alnlen` as estimates from the score (nident = 0), not as counted identities. Near the 30 % cut-off these estimates are systematically too low.
- Example: 2qiaA vs 6uec_A gives 0.266 without `-a` and 0.327 with it. 2qo3A vs FASN (P49327) gives 0.269 vs 0.317.
- Reproduced in `results/audit/mmdemo/`.
- Over the 24.1 k shared sequences, exact identities give **831,838 rule edges, against 705,700 in their graph**. 176 k edges appear only in this audit and 50 k only in theirs.

**Second, smaller cause.** Their Foldseek search was non-exhaustive (`--max-seqs 2000`) and used approximate TM-scores, so it missed some small helical folds. Example: TOUGH-M1-test 1ecmA vs BURROW 3ret_B has TM 0.80/0.80 (chorismate-mutase fold), and their raw Foldseek file has no hit for this pair.

| # | Check | Result | Counts (rule-hit pairs → affected units) |
|---|---|---|---|
| 1 | Extraction | PASS | 34,320 chains: TM-dev 731, TM-test 1,014, BURROW train+dev 7,054, ProSPECCTs 3,041, Vertex 8,910 (9 non-protein HET chains), af_set 3,473 models (+45 fragmented, sequence only), BLiPS train 1,772 / val 99 proteins, PPIPS 2,944/536/502 chains, PPI-L-test 374. Lengths match their nodes for every discrepant pair checked. |
| 2a | MMseqs2 TM-test vs BURROW | **FAIL** | 16 pairs (8 with max-cov ≥ 0.5; 2 with both cov ≥ 0.5) → 15 test pockets. Identity 0.30–0.40, for example 1kapA–7usl_C 0.40/122 aa, 4e8cA–5ifp_A 0.31/330 aa (E 4e‑37), 2qiaA–6uec_A 0.33. |
| 2b | TM-dev vs sealed sets | **FAIL** | ProSPECCTs 5 (e.g. 1id8A–3kp0C, 5fliC–1h1iC). af_set 4 (2qo3A–P49327 FASN 0.32 over 845 aa). Vertex 0, PPI-L-test 0. Total 7 dev pockets in 7 groups, which should have been *excluded*. Also 3nmxB is 96.6 % identical to APC (P25054), one of the 45 fragmented af_set proteins that are missing from their graph (not in BLiPS-test sites). |
| 2c | TM-dev vs TM-test | **FAIL** | 2 pairs (4xg0A–5dmhA 0.34; 2pyhB–3sucA 0.31), which break the dev/test component separation. |
| 2d | BLiPS train/val vs sealed sets | **FAIL** (train) / PASS (v1 val) | v1 train: af_set 2, ProSPECCTs 8, TM-test 7, Vertex 0, PPI-L 0. v1 val: 0. BLiPS-v2 (D9) train vs val: **7 pairs**, so the component rule is violated. |
| 2e | PPIPS train vs val/test; val vs test | PASS | 0 / 0. No identical sequences anywhere. |
| 2f | Near misses (identity 25–30 %, cov ≥ 0.5, no rule hit) | info | TM-test vs BURROW: 31 chains, median best identity 0.269 (IQR 0.261–0.277). BLiPS-train vs af_set: 29 chains (median 0.272). All other pairs ≤ 18 chains. |
| 3 | Foldseek, both directions ≥ 0.5 | **FAIL** (minor) | TM-test vs BURROW: 11 pairs / 6 pockets (1,061 pairs above 0.5 in one direction only). TM-dev vs ProSPECCTs, Vertex, af_set and PPI-L: 0 (289 / 2,317 / 581 / 111 one-direction). TM-dev vs TM-test: 2 (3remA–1ecmA 0.78/0.83). BLiPS-train vs af_set 4, vs TM-test 3, vs PPI-L-test 3. BLiPS-v2 train vs val 4. PPIPS train vs val/test: 2 pairs, 1 complex (AF-…66231028 vs …66233041; TM 0.50–0.56, E 4e‑17). Most structural misses have TM 0.50–0.60. |
| 4 | Identical PDB IDs / sequences | PASS (info) | Identical sequences across partitions: 0 in every comparison. Shared PDB entries always involve different chains or proteins: TM dev/test 1 (4xru C/D); TM-test vs BURROW 3 (2yep, 3it6, 4pht); TM-test vs ProSPECCTs 40 (allowed); BLiPS-train vs af_set holo entries 5. Shared UniProt between BLiPS train/val and af_set: 0. PPIPS UniProt overlap between splits: 0, and vs BURROW: 0. |
| 5 | Ligand overlap (info) | info | TOUGH-M1: 73 % of test pockets have a dev ligand with ECFP4 Tc ≥ 0.6 (54 % have an identical fingerprint). 52 of the 70 positive-capable test ligand clusters also occur in dev. BLiPS: 47 % (v1) / 46 % (v2) of test sites carry a CCD that is a qualifying CCD in train. |

**Combined impact (sequence OR structure edges)**
- **TOUGH-M1-test:** 16 / 1,014 pockets (15 groups, 23 pockets) touch BURROW and belong in dev or excluded.
- **TOUGH-M1-dev:** 7 / 731 pockets touch a sealed set. 3 pockets have edges to test.
- **BLiPS-v1 train:** 19 / 1,772 proteins have edges to sealed sets.
- **BLiPS-v2:** 9 train proteins link to val.
- **PPIPS:** 1 complex.

Small as these numbers are, they break a hard requirement. **Fix:** rerun `build_homology_graph.py` with `-a` on the MMseqs2 search and exhaustive Foldseek (or `--max-seqs` ≥ 10 k), then re-derive the splits. The changes are about 2 % of units, so headline counts barely change.

**Warning outside the rule.** PPIPS is not BURROW-clean, but DESIGN only requires UniProt exclusion. 191 / 251 test and 179 / 268 val complexes contain a chain with a sequence or TM ≥ 0.5 edge to BURROW train/dev chains. BURROW detects the PPIPS pockets, so PROMPT's "model used to prepare receptors" clause applies. Disclose this, or restrict PPIPS claims.

## Re-audit after the D15 rebuild (2026-10-28 03:30, commit 1ce80fb; same independent code path)

**Method.** All steps were re-run on the new partition files: gemmi extraction, MMseqs2 `easy-search` all-vs-all over 24,618 unique sequences, and exhaustive Foldseek with exact TM for every query→target block. Scripts are unchanged except that the PPIPS-vs-BURROW Foldseek block was dropped. The first-audit outputs are kept in `results/audit/v1/`. `data/sealed/` was not opened.

**Partition sizes.** TOUGH-M1 765 / 1,045 / 5,714 (dev / test / excluded) and BLiPS v1 1,839 / 104 proteins both match SPLITS.md. Excluded pockets are not checked here; they are used in no evaluation.

| Check | Result | Counts (rule-hit pairs) |
|---|---|---|
| 2 MMseqs2: TM-test vs BURROW; TM-dev vs ProSPECCTs/Vertex/af_set/PPI-L-test; TM-dev vs TM-test | **PASS** | 0 / 0 / 0 / 0 / 0 / 0. Near misses (25–30 %): 32 test chains, median 0.267. |
| 2 MMseqs2: BLiPS v1 train and val vs af_set/ProSPECCTs/Vertex/TM-test/PPI-L-test; v1 train vs val | **PASS** | All 0. |
| 2 MMseqs2: BLiPS-v2 train vs val | PASS (1 boundary case) | 1 pair, 5odq_G–9gz4_A: identity 0.329, alnlen exactly 80, cov 0.12/0.16, E 8.1e‑4. The reverse direction has alnlen 68, so this is not a meaningful homology. |
| 2 MMseqs2: PPIPS train vs val/test; val vs test | **PASS** | 0 / 0. |
| 3 Foldseek, TM ≥ 0.5 both directions: TM-test vs BURROW; TM-dev vs the 4 sealed sets; TM-dev vs TM-test; BLiPS val vs sealed sets; BLiPS v1 train vs val; PPIPS train vs val/test; PPIPS val vs test | **PASS** | All 0. One-direction-only counts (info): 1,219 / 354, 2,357, 601, 112 / 92 / … |
| 3 Foldseek: BLiPS train vs ProSPECCTs; BLiPS-v2 train vs val | PASS (boundary) | 8 pairs from 3 train proteins (6hur_A, 2i10_B, 3a4m_A; min-TM 0.502–0.518). 1 v2 pair, 7uq2_A–8g0e_4 (0.556/0.596, E 3.5, 80 aa). Their exact TM for the same sid pairs is 0.41–0.497 (2i10–2gby: approximate 0.44, so never re-scored). These are alignment-variance disagreements at the threshold, not clear homologues. Being conservative would mean dropping 3 of 1,839 train proteins and 1 v2 protein. |
| 4 Identical sequences / PDB IDs | **PASS** | Identical sequences across partitions: 0 everywhere. Shared PDB entries always have different chains and proteins: TM dev/test 1 (4xru); TM-test vs BURROW 3; BLiPS-v2 train vs val 26; BLiPS train vs af_set holo entries 5. UniProt overlap: 0 (BLiPS vs af_set, PPIPS between splits, PPIPS vs BURROW). |
| Previous six examples | **gone** | 1kapA, 2qiaA, 1ecmA: test → dev. 2qo3A, 3nmxB: dev → excluded. 4xg0A–5dmhA and 3remA–1ecmA now all in dev. PPIPS AF-…66231028 and …66233041 are both in train, in the same group. |
| Info | — | PPIPS val/test with a BURROW sequence edge: 37 / 25 complexes (theirs: 37 / 24). TOUGH-M1: 73 % of test pockets have a dev ligand with Tc ≥ 0.6; 57 of 77 positive-capable test clusters occur in dev. BLiPS-v2: 46 % of test sites carry a train qualifying CCD. |

**Verdict: PASS.** No leak beyond threshold-level alignment variance (1 sequence pair, 4 structural pairs at min-TM ≤ 0.56). The PPIPS–BURROW homology warning still applies; it is now handled by the `burrow_rep_edge` stratification flag.
