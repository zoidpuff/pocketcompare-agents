# PDB-T evaluation infrastructure (PREREG2) — `scripts/eval_pdbt.py`

**What it does.** Evaluates the frozen arms with the frozen `final_eval.py` functions. Those functions are imported, never modified, and hash-checked against FREEZE.json together with evaluate.py, PREREG.md and PREREG2.md. The L4 weights, fusion scales, w selection and fusion script are checked against hashes recorded in the script.
- **Arms:** FINAL (A4b:n1_linear raw), N1, L4:egnn_small (CSLS designated, raw too), FUSION (`fusion_a4b_l4.FusedMethod`, w = 0.5, BLiPS-train z-scales), B1 and B0.
- **Claims:** R1 FINAL−B1, R2 FUSION−FINAL and R3 L4[csls]−FINAL. Each is a ROC-AUC difference on the D-mode pairwise common set, tested with `final_eval.paired` (paired vertex bootstrap, B = 2000, seed 0, units = homology components), with Holm across R1–R3.
- **Reported:** the L-mode deltas, R3 with L4 raw, and an all-arm common-set sensitivity check. Per arm and mode: AUC, AP, cluster-balanced AUC, size-stratified AUC (5×20, or 5×5 below 500 positives), and missing / worst case.

**Guards (real run).**
- Requires `FINAL_EVAL=1`, and the script must be committed and unmodified.
- `results/pdbt/gate.json` must give PASS or FAIL. On FAIL the run is DESCRIPTIVE: no p-values, no Holm, no claims, and this is stated in every output.
- The sealed pairs must have a sha256 recorded in `data/sealed_SHA256SUMS.txt`. They are read via `final_eval.Sealed` (chmod 400 → sha256 → read → chmod 000), and each access is logged to `results/pdbt/unseal_log.tsv`.
- It refuses a second look unless `--rerun` is given.
- `--check-only` runs every guard without opening the sealed file. `--prepare` computes the PDB-T L4 embeddings (label-free) on cuda:2 over the full ids table, exactly as `l4_embed.py` does.
- Outputs: `results/pdbt/{claims.json, summary.parquet, report.md}`, each with a `.prov.json` sidecar.

**Expected build outputs.** The first matching column name is used and recorded.
- Sites: `site_id` or `pocket_id`, plus a homology component column (`hom_component` / `homology_component` / `component` / `group_id`), and an optional boolean `excluded`.
- Pairs: `site_a`/`site_b` or `pocket_a`/`pocket_b`, `label`, and a cluster column (`pair_cluster` / `ligand_cluster` / `butina_cluster`).
- Caches for dataset `pdbt`: the point-cache index, `a1r/`, `b1_default_{L,D}`, and `data/processed/l4/pdbt/`.
- Not yet verifiable: none of these exist yet.

**Dry run** (`--dryrun-dev`; BLiPS-val v2, 1544 D pairs and 287 positives; `results/pdbt_dryrun/`):
- **Reproduction:** FINAL, N1, L4, B1 and FUSION (raw and csls, L and D) were compared with `results/dev/l4/final_select_all_l4_summary` and `results/exploratory/fusion/dev/final_select_fusion_summary`. Over 32 rows, the maximum |deviation| is **0** across AUC, AP, cb-AUC, stratified AUC and their homology-unit CIs and SEs, with n_pairs identical.
- **L4 re-embedding:** recomputing the L4 embeddings (full table, GPU) against the stored ones gives max |Δ| = 0.
  - Embedding only a subset changes batching and gives about 1e-3.
  - CPU gives about 2e-3, which moves AUC by 2e-4.
  - So use the GPU; the device is recorded.
- **Dry-run claims (dev, not evidence):**
  - R1: +0.059 [−0.025, 0.127]
  - R2: +0.042 [−0.000, 0.075], Holm p 0.080
  - R3: +0.041 [−0.025, 0.107]
- The FAIL / descriptive path was also exercised (B = 200, scratch output).
