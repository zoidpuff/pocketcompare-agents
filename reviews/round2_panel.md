# Review round 2 — panel (PI · statistics · data/leakage) on DESIGN v1

**Verdict.** v1 adopts most round-1 MUSTs correctly: sealing with FREEZE.json, provenance, evaluate.py written first, B4/B5,
fold-honest P-ortho, H0: Δ ≤ 0 with a 0.03 smallest effect of interest, cluster-balanced AUC, the common-set miss policy,
the A1/A3 fixes and CSLS. The two rejections (no Brylinski replication, no 40/60 split) give adequate reasons.

We found three misadoptions, two new leakage holes and three underspecified statistical procedures. All fixes below are text
changes or cheap checks. Nothing here adds scope.

## MUST
1. **TOUGH-M1 groups homologous to both BURROW train/dev and a sealed test (§2.3, internal contradiction).**
   - v1 sends these groups to test. Test is then no longer BURROW-clean.
   - It also leaks A4b's training data into C1: BLiPS-train is BURROW train sites.
   - Text: *"Groups homologous to BURROW train/dev **and** to any sealed test set (ProSPECCTs, Vertex, BLiPS-test,
     PPI-L-test) are excluded from both TOUGH-M1 partitions; their number is reported."*
2. **The global connected-component graph (§2.1) will percolate.**
   - It spans about 60k chains: BURROW 24.7k, dimers 11.8k, Vertex, af_set and others. The 4.5 % largest component
     was measured on TOUGH-M1 alone, and v1 dropped the data reviewer's gate.
   - Text: *"Splits within a dataset assign connected components. Exclusion across datasets uses direct edges: a
     train/dev item is removed if it has an edge to any test item. Edge = `pocketdetect.datasets.leakage.apply_rule`
     verbatim OR Foldseek TM ≥ 0.5 in both directions. Gate: largest within-dataset component ≤ 10 %, else DataSAIL."*
3. **A4b has two problems.**
   - (a) *Leak.* The augmentation "holo vs AF from af_set-val" has no source: all of af_set is BLiPS-test. Replace it
     with pocket_detect `af_train`/`apo_train` sites that lie in BLiPS-train groups.
   - (b) *Misadoption of data M2.* "Selection on BLiPS-val/TOUGH-M1-dev" should read *"A4b and A5 are selected on BLiPS-val
     (+PPIPS-val) only. TOUGH-M1-dev selects non-learned arms only."* TOUGH-dev is BURROW-family-related to BLiPS-train,
     so using it favours the learned arms.
4. **Size-stratified AUC (§4) is one-dimensional, and its B0 check is vacuous.**
   - B0 = −|Δ log vol| is the stratification variable itself, so it gives ≈ 0.5 by construction.
   - Absolute size stays exploitable, because positives are enriched for large pockets. Both stats S1 and data M8
     asked for 2-D strata.
   - Text: *"Strata = quintiles of mean L-mode log-volume × quintiles of |Δ log-volume| (edges taken from the evaluated
     partition). Per-stratum AUC is weighted by the number of positives. Strata lacking a class are dropped and counted.
     Diagnostic: B0m (logistic on log v_a + log v_b and |Δ|, fit on dev) must give a stratified AUC of 0.5 ± 0.03."*
5. **The vertex bootstrap is ambiguous for within-unit pairs.** All TOUGH-M1 positives are within one ligand cluster.
   - Text: *"Pair weight = c_u if both pockets are in unit u, else c_u·c_v. TOUGH-M1 unit = component of (ligand
     cluster ∪ homology group), with ligand cluster = component of the positive graph [stats M1]. BLiPS/PPI: run with
     homology-group units and with ligand-cluster (Butina) units, and report the wider CI. C2: an independent bootstrap
     per subset, unit = homology group, with the macro Δ computed per replicate index."*
6. **C3 on Pasteur PPI-L is not well defined.**
   - Ligand-free cavities have no L-mode pocket.
   - Negatives that involve ligand-free pockets make "has a ligand" a per-pocket shortcut.
   - "< 100 positives" counts pairs, not independent units. Most modulator families (Bcl-2/Mcl-1, MDM2/MDMX, BET,
     14-3-3) fall inside one homology group, so expect a downgrade.
   - Text: *"PPI-L uses only cavities with a PDB HET modulator (L-mode). Negatives = ligand-bound pairs with Tc < 0.3.
     Gate, recorded before any score: test positives ≥ 50 pairs spanning ≥ 10 homology groups and ≥ 5 ligand clusters.
     Otherwise C3 is exploratory and the Holm family is {C1a, C1b, C2}."*
7. **Seal the raw label lists mechanically.** Run `chmod 000` on the pair/label files of ProSPECCTs, Vertex and TOUGH-M1
   under `data/raw/` and leave the structures readable. DEV1 shows that sealing "by protocol" fails. This takes 2 minutes.

## SHOULD
8. **B4 as the C1b comparator is sensible.** The TOUGH-M1 test is homology-split, and ESM pretraining uses no labels.
   - Add: *"The claim-bearing final method takes no B4 input. A fusion that includes B4 is descriptive only. B1 and B4
     receive the same CSLS treatment as the final method."*
   - Replace the garbled §2.8 ESM sentence with: *"ESM-2 was pretrained on UniRef (which includes test sequences) without
     labels; disclosed."*
9. **Multi-set selection rule (§3 A1).** Text: *"Score = mean cluster-balanced AUC over TOUGH-M1-dev and BLiPS-val; apply
   the one-SE rule to that mean."*
   - A2 gate: drop "> 0.55". It is a different protocol, and B0 already scores 0.577 (DEV1).
   - Keep "adds to A1"; report the gain over A1 + B4 as descriptive.
10. **C5 / data M9 (not adopted, no reason given).**
    - Develop the AF-vs-holo pipeline on val first: pocket_detect `af_train` or BLiPS-val proteins.
    - Stratify by holo release date (≥ 2018-05-01) and by site pLDDT band.
11. **Split audit before the first fit.** An independent agent re-derives the splits and checks overlap before any model
    is fit (agent M5). The split script writes test counts and composition once (counts only).
12. **Cut order if behind at 03:00:** A3/A4 → proteome demo → §2.7 blind test → P-ortho. C1–C3 inputs are never cut.

## COULD
13. Scale the minimum detectable effect from dev to test by √(n_units_dev / n_units_test).
14. Define P-sym "≥ 0.9 percentile" as: rank of the copy among the query's scores against all other pockets of its split.
15. BLiPS: state the caps (≤ 3 sites/protein, ≤ 300 positives per ligand cluster). Report results with and without the
    top-20 promiscuous CCDs.
16. Report B0' (TM) as a descriptive comparator next to C1. PI M3b was dropped without a reason.
