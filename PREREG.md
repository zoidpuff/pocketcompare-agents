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

## 2. Confirmatory claims (Holm family, one-sided α = 0.05, paired vertex bootstrap B = 2,000, H0: Δ ≤ 0)
| id | set | mode | comparison | unit |
|---|---|---|---|---|
| C1a | TOUGH-M1-test (BURROW-clean, 1,014 pockets) | L | final − B1, ROC-AUC | component(ligand cluster ∪ homology group) |
| C1b | TOUGH-M1-test | L | final − B4 | same |
| C1-D | TOUGH-M1-test | D (common set, match = coverage ≥ 0.3 or precision ≥ 0.5) | final − B1 | same |
| C2 | ProSPECCTs D5.2 + D6.2 + D7, self-pairs removed | L | macro Δ(final − B1), independent bootstrap per subset | homology group |
SESOI 0.03 reported with the lower CI bound; test MDE (dev-derived) ≈ 0.13 for C1 — power is limited. C3 (PPI-L) is
exploratory (gate failed, D7).

## 3. Reported (not in the Holm family)
TOUGH-M1-test: AP, cluster-balanced AUC, 2-D size-stratified AUC (5 × 20), pAUC; B0, B0m, B0' (global Foldseek TM),
B5 (EPoCS), B5-T (shipped APoc / G-LoSA / SiteEngine, all columns). TOUGH-M1 "full minus dev" (non-learned arms only,
L-mode; literature-comparable). ProSPECCTs all 10 subsets (with/without self-pairs; L; D on BURROW-clean subset).
Vertex (L). BLiPS-test (L, D; AF-model pockets for C5: Δ holo vs AF with CI; strata by holo release date ≥ 2018-05-01
and pLDDT band). PPIPS-test P-ortho (top-1/top-3/MRR) and P-sym percentile. PPI-L test (exploratory). Runtime per
pocket (BURROW + descriptor) and per pair; proteome demo throughput; bytes/pocket; PQ recall@10.

## 4. Fixed rules
Metrics only via evaluate.py at sha256 f22d02967c08d706d8a6081865a8ba40f491340e87e205826e32f8206f65707b. Size strata
5 × 20 quantile bins (5 × 5 if < 500 positives). Missing pockets: common set primary + worst-case bound + miss rates.
Final evaluation runs from a git worktree at the frozen commit via scripts/final_eval.py with FINAL_EVAL=1 and
FREEZE.json; only the PI unseals; an agent that did not produce the numbers re-derives every headline.

## Addendum A1 (2026-10-27 23:20, before any model fit or test use)
One additional learned candidate is declared for the §1 selection: **L4 = point-cloud network** (EGNN/PointNet-style,
≤ 6 pre-declared configs in configs/a4_grid.yaml) on the sph8 site points with BURROW analytic point features,
trained under the same data rules as A4b (BLiPS-train v2 + PPIPS-train + L↔D same-site positives), seeds SEEDS[:3]
ensemble, time box 3 h. Same objective, one-SE rule (L4 counts as "learned", more complex than A4b) and guards. No
other candidates will be added.

## Addendum A2 (2026-10-28 02:55, before any test use)
Final method (PREREG §1, decision D19): **A4b:n1_linear, raw cosine** (linear projection of N1 = A1(sph8)+env(sph8),
3-seed ensemble, 384 stored dims). Descriptive (non-claim) arms added to the final evaluation: N1 raw (non-learned
parent) and L4:egnn_small|CSLS (best dev candidate, more complex). They are not in the Holm family.
