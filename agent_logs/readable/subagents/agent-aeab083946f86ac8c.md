# Sub-agent aeab083946f86ac8c — Blind deployment test + PPI-L descriptors (sonnet)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-27 22:57:15

Two small tasks for a pocket-similarity project. Project root: /cluster/project/beltrao/gmagnus/pocket_compare (git; do NOT commit — the PI commits). Read PREREG.md §3, DESIGN.md §2.7 (blind deployment test), RESEARCH_TREE.md (top + D13–D17), reports/{final_eval_infra,af_robustness_dev,blips_ppips_prep,ppi_datasets}.md, src/pocketcompare/{method.py,pockets.py,descriptors/a1r.py,evaluate.py,provenance.py}, scripts/{final_eval.py,eval_af_robustness.py,compute_n_inputs.py}. Env: `source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache`. ≤ 12 CPU workers; no GPU. NEVER open data/sealed/.

Task 1 — blind deployment test script `scripts/eval_blind.py` (DESIGN §2.7): on a site set with AF models (BLiPS-val v2 for the dry run; BLiPS-test at final eval behind FINAL_EVAL=1), take ALL BURROW region-rule detected pockets (merged, ≥ 10 points, no single-point metal candidates) of every AF model WITHOUT ligand guidance, describe them with the final method (configs/final_method.yaml via method.py), and for each true site (located only to define the ground truth: the detected pocket matching the site by the D-mode rule, coverage ≥ 0.3 or precision ≥ 0.5) query the full pool of detected pockets from ALL OTHER proteins; report: fraction of sites whose matched pocket exists (detection recall), and for ligand-sharing positive partners (from the pair labels: val pairs for dry run) the rank of the partner's matched pocket among all pool pockets (hit@1/10/100, MRR, and AUC of partner vs all non-partner pool pockets), with homology-group bootstrap CIs via evaluate.py. Compare the final method vs B1 (and B4 if available). Run the dry run on BLiPS-val v2 and write results to results/dev/blind_val/ + trials rows (arm "blind_dev"). Make the test path exist but refuse without FINAL_EVAL=1; do not run it.
Task 2 — compute final-method descriptors (N1 inputs; via scripts/compute_n_inputs.py or the descriptor adapters) for the PPI-L pockets (data/splits/ppi_l_pockets.parquet; caches from the PPI agent — see reports/ppi_datasets.md) so that the exploratory PPI-L evaluation can run at final eval; also make sure scripts/final_eval.py can find them (read its PPI-L section; if it needs a small adapter, add it and run its tests tests/test_final_eval.py).
Write reports/blind_and_ppil.md (≤ 1 page, numbers first). Final message ≤ 200 words.


### PI / user turn · 2026-10-27 22:57:15

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


**→ tool call `Bash`** · 2026-10-27 22:57:17

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; ls; ls scripts src/pocketcompare src/pocketcompare/descriptors reports configs results results/dev data/splits | head -150; wc -l PREREG.md DESIGN.md RESEARCH_TREE.md reports/{final_eval_infra,af_robustness_dev,blips_ppips_prep,ppi_datasets}.md src/pocketcompare/{method,pockets,evaluate,provenance}.py scripts/{final_eval,eval_af_robustness,compute_n_inputs}.py"}
```


**← tool result**

```
DATA.md
DESIGN.md
LESSONS.md
LITERATURE.md
PREREG.md
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
configs:
a1_grid.yaml
a4_grid.yaml
a4b_grid.yaml
final_method.yaml

data/splits:
SHA256SUMS.txt
SPLITS.md
blips_sites.parquet
blips_sites_v2.parquet
blips_split_counts.json
blips_split_counts_v2.json
blips_test_exclusions_v2.parquet
blips_train_pairs.parquet
blips_train_pairs_v2.parquet
blips_val_pairs.parquet
blips_val_pairs_v2.parquet
homology_components.json
homology_edges.parquet
homology_nodes.parquet
inputs
ppi_l_pairs_train.parquet
ppi_l_pairs_val.parquet
ppi_l_pockets.parquet
ppips_complex_splits.parquet
ppips_ortho_queries_train.parquet
ppips_ortho_queries_val.parquet
ppips_sym_pairs_train.parquet
ppips_sym_pairs_val.parquet
split_sensitivity.json
tough_m1_dev_pairs.parquet
tough_m1_pockets_split.parquet
tough_m1_split_counts.json

reports:
a1_descriptors.md
a2_docking.md
af_robustness_dev.md
audit_splits.md
baselines_b4_b5.md
blips_ppips_prep.md
data_benchmarks.md
definition_robustness.md
dev_eval_blips_ppips.md
dev_eval_tough_m1.md
evaluate_module.md
final_eval_infra.md
fragment_docking_feasibility.md
l4_pointnet.md
pocket_adapter.md
ppi_datasets.md
ppi_dimers.md
proteome_demo.md
splits.md

results:
a2
audit
benchmarks
dev
explore
feasibility
final_dryrun
models
pocket_cache
ppi
proteome
trials.tsv

results/dev:
af_robustness_train
af_robustness_val
blips_val_details.json
blips_val_details.json.pr
… [2,076 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:57:20

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat PREREG.md; sed -n 1,60p RESEARCH_TREE.md; grep -n \"D1[3-7]\" RESEARCH_TREE.md | head; grep -n \"2.7\" DESIGN.md"}
```


**→ tool call `Bash`** · 2026-10-27 22:57:20

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; cat reports/final_eval_infra.md reports/af_robustness_dev.md reports/ppi_datasets.md configs/final_method.yaml"}
```


**← tool result**

```
# Final-evaluation infrastructure (final-eval agent, 2026-10-27)

No file in `data/sealed/` and no chmod-000 file under `data/raw/` was opened, copied or chmod-ed; every check below
ran on dev data or on label-free tables. Nothing is committed.

## 1. Label-free preparation of the sealed external sets
- **PDB mirror:** 183 of the 201 previously missing Vertex entries are now present. 18 remain missing, all
  obsolete (`results/benchmarks/vertex_site_map_summary.json`).
- **`build_benchmarks.py` was not run.** It re-parses the raw label lists: the ProSPECCTs `*.csv` files and the
  Vertex `protein_pairs.tsv`, which are chmod 000. The pocket table was refreshed by
  `scripts/data/vertex_site_map.py` instead. That script reads only the pocket table and the mmCIF files; the old
  table is kept as `vertex_pockets.pre_sitemap.parquet`.
- **Vertex `site_index` → ligand instance**
  - The adapter's old guess, "k-th copy of the HET", is wrong. In all 184 multi-site entries the site indices run
    across *different* HET codes (e.g. 1kvl: 1, 2, 3 = THN, KCP, CLS). In 480 single-site pockets, k is larger than
    the number of HET copies.
  - The ACS paper and the SI description are blocked (HTTP 403). The only public re-implementation is DeeplyTough
    (`ligand_extract.py`; ignore list vendored in `data/ref/`). It defines site k as the k-th HETATM residue with
    ≥ 3 atoms that is not on its ignore list.
  - This rule reproduces the given HET at position k for 85 % of the k > 1 pocke
… [16,597 more characters; full text in agent_logs/raw/]
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
… [8,812 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:57:22

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 105,135p DESIGN.md; cat reports/blips_ppips_prep.md; cat src/pocketcompare/method.py; cat scripts/compute_n_inputs.py"}
```


**← tool result**

```
- Positives: sites in different homology groups sharing a ligand with ECFP4 Tc ≥ 0.7; stratified by number of
  shared ligands (1 vs ≥ 2). Negatives: different-group sites with max Tc < 0.3. Pairs capped per ligand
  cluster (Butina 0.6; ≤ 300 positives per cluster) and per protein (≤ 3 sites); results also reported
  without the top-20 promiscuous CCDs. **No subsampling to size-match:** size is handled by size-stratified
  AUC (§4); diagnostic B0m (§4).
- AUC also reported for seen vs unseen ligand chemotypes (ligand cluster present in train or not).
- BLiPS is primarily a training/selection resource; BLiPS-test is reported (secondary), C5 uses it. The
  AF-vs-holo pipeline is developed on val first (pocket_detect `af_train` dev sites) and stratified by holo
  release date (≥ 2018-05-01) and site pLDDT band.

### 2.7 Blind deployment test (secondary)
BLiPS-test proteins, AF models, BURROW region-rule pockets without any ligand guidance: for each true site, rank
all detected pockets of all other test proteins; report hit rates for the partner sites. Plus a human-proteome
FAISS demo (§6).

### 2.8 Leakage of models used to prepare receptors
- BURROW: tier-1 features are BURROW's **analytic** point features only (no `point_score`, no ranker scores);
  learned features are an ablation. D-mode/blind tests use BURROW detection and are evaluated on BURROW-clean
  data (TOUGH-M1-test, BLiPS-test = af_set). 
- ADock: **stock Vina** weights only (no fitted weights, no template mode, n
… [24,173 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:57:25

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -n -i \"ppi_l\\|ppil\\|ppi-l\" scripts/final_eval.py | head -60; ls data/processed/cache/points data/processed/descriptors; ls data/processed/descriptors/ppi_l 2>/dev/null; ls data/processed/descriptors/blips_val* data/processed/descriptors/blips 2>/dev/null | head -30; grep -n \"^def \\|^class \" src/pocketcompare/evaluate.py | head -80"}
```


**← tool result**

```
64:  PPI-L test (exploratory): run iff its descriptors exist, else recorded as skipped.
1217:    # ---------------------------------------------------------------- PPI-L (exploratory)
1218:    if store.available("ppi_l", "b1_default_L"):
1219:        details["ppi_l"] = "descriptors present but the PPI-L stage is not implemented in this version"
1221:        details["ppi_l"] = "skipped: no PPI-L descriptors (data/processed/descriptors/ppi_l); exploratory per D7"
data/processed/cache/points:
blips
blips_af_dev
blips_test_af
blips_test_holo
ppi_l
ppips
prospeccts
tough_m1
vertex

data/processed/descriptors:
blips
blips_test_af
blips_test_holo
ppips
prospeccts
tough_m1
vertex
data/processed/descriptors/blips:
a1_dbins_coarse_D.ids.parquet
a1_dbins_coarse_D.ids.parquet.prov.json
a1_dbins_coarse_D.layout.json
a1_dbins_coarse_D.npy
a1_dbins_coarse_L.ids.parquet
a1_dbins_coarse_L.ids.parquet.prov.json
a1_dbins_coarse_L.layout.json
a1_dbins_coarse_L.npy
a1_dbins_fine_D.ids.parquet
a1_dbins_fine_D.ids.parquet.prov.json
a1_dbins_fine_D.layout.json
a1_dbins_fine_D.npy
a1_dbins_fine_L.ids.parquet
a1_dbins_fine_L.ids.parquet.prov.json
a1_dbins_fine_L.layout.json
a1_dbins_fine_L.npy
a1_dbins_short_D.ids.parquet
a1_dbins_short_D.ids.parquet.prov.json
a1_dbins_short_D.layout.json
a1_dbins_short_D.npy
a1_dbins_short_L.ids.parquet
a1_dbins_short_L.ids.parquet.prov.json
a1_dbins_short_L.layout.json
a1_dbins_short_L.npy
a1_default_D.ids.parquet
a1_default_D.ids.parquet.prov.json
a1_default_D.layo
… [2,598 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:57:30

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 1,140p scripts/eval_af_robustness.py; ls data/processed/cache/points/blips_af_dev | head -5; python3 - <<'E'\nimport pandas as pd\nfor f in [\"data/processed/cache/points/blips_af_dev/index.parquet\",\"data/processed/cache/points/ppi_l/index.parquet\",\"data/splits/ppi_l_pockets.parquet\",\"data/splits/blips_val_pairs_v2.parquet\",\"data/splits/blips_sites_v2.parquet\"]:\n    d=pd.read_parquet(f); print(f,d.shape); print(d.dtypes.to_string()[:1800]); print(d.iloc[0].to_dict() if 'index' in f else '')\nE"}
```


**← tool result**

```
Exit code 1
#!/usr/bin/env python
"""AlphaFold-vs-holo robustness evaluation (claim C5, REPORTED not confirmatory; PREREG §3, DESIGN §2.6).

    python scripts/eval_af_robustness.py --set val              # BLiPS-val v2 sites with an AF model (dev)
    python scripts/eval_af_robustness.py --set train --max-sites 600   # sample of BLiPS-train sites (if val is small)
    FINAL_EVAL=1 python scripts/eval_af_robustness.py --set test --pairs <BLiPS-test pairs parquet>   # PI / final_eval

The script is dataset-agnostic: an *adapter* returns ``(sites, pairs)``.

sites (one row per site that has BOTH a holo-chain pocket and an AF-model pocket of the same site)
    site_id, group_id (homology group = bootstrap unit), role ('val' | 'partner' | 'test' | 'train'),
    holo_cache, holo_structure, holo_chains, holo_lig   (holo Featurized npz [built if missing]; ligand heavy-atom xyz)
    af_cache,   af_structure,   af_lig                   (AF-mode Featurized npz; transferred ligand xyz)
    af_plddt (site mean pLDDT), release_date (holo, first PDB release), site_cluster (label-ligand cluster, optional)
pairs (ligand-sharing labels; optional)
    site_a, site_b, label, pair_cluster, group_a, group_b, site_cluster_a, site_cluster_b

What is computed (fixed before the first run; mode L = ligand shell of the (transferred) ligand, mode D = the
BURROW region-rule pocket that best covers the ligand shell [AF mode on the AF model], matched iff coverage >= 0.3 or
precision >= 0.5; unmatched / <10
… [6,179 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:57:33

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; sed -n 140,420p scripts/eval_af_robustness.py"}
```


**← tool result**

```
    el = np.concatenate([a["lig_elements"][ptr[k]:ptr[k + 1]] for k in sel])
    xyz = xyz[np.asarray([str(e).strip().upper() not in ("H", "D") for e in el])]
    return xyz.astype(np.float64), flag


def adapter_blips_dev(partition: str, max_sites: int | None, seed: int):
    """BLiPS v2 sites of ``partition`` ('val' | 'train') whose BURROW entry has an AF model in pocket_detect's
    af_train (matched by entry id = UniProt__pdb_chain of the BURROW train/dev pools; the AF model is keyed by the
    UniProt accession).  Partner sites (the other end of a labelled pair) are added with role 'partner' if they have
    AF models too, so that val-vs-train pairs are usable."""
    sys.path.insert(0, str(AFT_IO))
    from build_af_train_io import load_af_entry, read_af_manifest   # noqa: E402  (read-only)
    S = pd.read_parquet(SPLITS / "blips_sites_v2.parquet")
    S["src"] = S.site_id.str.split(":").str[0]
    S["entry"] = S.site_id.str.split(":").str[1]
    S["sidx"] = S.site_id.str.split(":").str[2].astype(int)
    man = {"burrow_dev": read_af_manifest("dev"), "burrow_train": read_af_manifest("train")}
    man = {k: v.set_index("entry_id") for k, v in man.items()}
    P = pd.read_parquet(BENCH / "blips_pockets.parquet").set_index("pocket_id")
    HI = pd.read_parquet(CACHE / "blips/index.parquet").set_index("pocket_id")
    pairs = pd.read_parquet(SPLITS / f"blips_{partition}_pairs_v2.parquet")
    S = S[S.partition.isin({"val", "train"})].copy()
    S = S[S.apply(lambda r: r.ent
… [13,132 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:57:51

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; sed -n 420,644p scripts/eval_af_robustness.py; sed -n 464,530p src/pocketcompare/evaluate.py; sed -n 579,700p src/pocketcompare/evaluate.py"}
```


**← tool result**

```
    cand = np.ones_like(S, bool)
    if same_group_excl:
        cand &= ~same
    diag = np.diag(S)
    gt = ((S > diag[:, None]) & cand).sum(1)
    tie = ((S == diag[:, None]) & cand).sum(1) - 1               # excl. the true candidate itself
    rank = 1 + gt + tie
    q = query_mask[pidx]
    if q.sum() < 2:
        return {"n_queries": int(q.sum()), "n_pool": n}
    out = {"n_queries": int(q.sum()), "n_pool": n, "n_groups": int(pd.Series(grp[q]).nunique()),
           "top1": float((rank[q] <= 1).mean()), "top3": float((rank[q] <= 3).mean()),
           "mrr": float((1.0 / rank[q]).mean()), "median_rank": float(np.median(rank[q]))}
    if q.sum() >= 5:
        for k, v in (("top1", (rank <= 1)), ("top3", (rank <= 3)), ("mrr", 1.0 / rank)):
            lo, hi = group_boot(v[q].astype(float), grp[q], B, seed)
            out[f"{k}_lo"], out[f"{k}_hi"] = lo, hi
    # AUC same-site (positives, one per query) vs other-site (negatives) similarity over the query rows
    qi = np.flatnonzero(q)
    I, J = np.meshgrid(qi, np.arange(n), indexing="ij")
    I, J = I.ravel(), J.ravel()
    keep = cand[I, J]
    if max_neg is not None and len(qi) * n > max_neg:
        r = rng.random(len(I))
        keep &= (I == J) | (r < max_neg / (len(qi) * n))
    I, J = I[keep], J[keep]
    y = (I == J).astype(int)
    s = S[I, J]
    out["auc"] = ev.roc_auc(y, s)
    if q.sum() >= 5:
        try:
            r = ev.vertex_bootstrap(y, s, grp[I], grp[J], B=B, seed=seed)["auc"]
            out["au
… [19,568 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:57:58

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; grep -n \"def \\|^[A-Z_]* = \" src/pocketcompare/pockets.py | head -90; grep -n \"metal\\|merged\\|MIN_POINTS\" scripts/ppi/2*.py src/pocketcompare/pockets.py | head -30; ls scripts/ppi; grep -rn \"def append_trial\" -A25 src/pocketcompare/provenance.py | head -50; head -3 results/trials.tsv | cut -c1-600"}
```


**← tool result**

```
38:ADAPTER_VERSION = "pockets-v1"
39:REGION_RULE = "c16_0.005"          # == pocketdetect.burrow.cli.REGION_RULE (checked at featurisation)
40:WATER = 2                          # pocketdetect.structure kind codes: 0 protein, 1 ligand, 2 water, 3 other polymer
43:L_CUTOFF = 4.0                     # point <= 4 Å of a ligand heavy atom
44:LINING_CUTOFF = 4.0                # residue heavy atom <= 4 Å of an L-mode point
45:RES_CUTOFF = 4.0                   # residue-list mode: point <= 4 Å of a listed residue's heavy atom
46:RES_BUR_MIN = 0.5                  # ... and bur10 >= 0.5
47:MERGE_TOUCH = 1.5                  # merge detected pockets with any point pair <= 1.5 Å
48:MERGE_JACCARD = 0.3                # ... or residue Jaccard >= 0.3
49:COVER_DIST = 1.5                   # L point covered if <= 1.5 Å of a detected pocket point
50:MIN_COVERAGE = 0.3                 # below -> "missed"
55:def _git_state(repo: str) -> dict:
56:    def run(*a):
66:def _sha256(path: str) -> str:
75:def _load_model(path: str):
80:def pocketdetect_root() -> Path:
85:def model_path(ranker: str = "all", preset: str = "default") -> Path:
91:_STR = lambda a, w: np.asarray(a).astype(f"U{w}")  # noqa: E731
130:    def spacing(self) -> float:
134:    def n_pockets(self) -> int:
137:    def feature(self, name: str) -> np.ndarray:
140:    def pocket_idx(self, i: int) -> np.ndarray:
144:    def pocket_residue_set(self, i: int) -> frozenset:
148:    def volume(self, idx) -> float:
152:    def point_tree(
… [8,930 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:58:01

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; sed -n 55,80p scripts/ppi/22_ppips_build.py; sed -n 394,470p src/pocketcompare/pockets.py; sed -n 668,690p src/pocketcompare/pockets.py; ls scripts/ppi/../; ls data/processed/benchmarks | head -30; grep -n \"B4\\|b4\" reports/baselines_b4_b5.md | head -8; ls data/processed/descriptors/blips | grep -v \"a1_\" "}
```


**← tool result**

```
MIN_MAPPED = 0.5
MAX_IDENT = 0.30


def pocket_rows(key: str) -> list:
    from pocketcompare import pockets as pk
    fs = pk.Featurized.load(CACHE / f"{key}.npz")
    rows = []
    for k, mp in enumerate(pk.merge_pockets(fs, "region")):
        if len(mp.idx) < MIN_POINTS:
            continue
        res = sorted(mp.residues, key=lambda r: (r.split(":")[0], int(r.split(":")[1])))
        na = sum(r.startswith("A:") for r in res)
        nb = len(res) - na
        fmin = min(na, nb) / max(len(res), 1)
        rows.append({"pocket_id": f"{key}:m{k}", "complex": key, "merged_index": k,
                     "members": np.asarray(mp.members, np.int32), "n_points": int(len(mp.idx)),
                     "n_points_dense": int((fs.vol[mp.idx] == 1).sum()), "volume_A3": mp.volume_A3,
                     "score": mp.score, "residues": " ".join(res), "n_res": len(res), "f_min": fmin,
                     "is_interface": fmin >= IFACE_FMIN})
    return rows


def rset(s: str) -> frozenset:
    return frozenset(s.split()) if s else frozenset()



def merge_pockets(fs: Featurized, which: str = "region", touch: float = MERGE_TOUCH,
                  jaccard: float = MERGE_JACCARD) -> list:
    """Merge touching detected pockets: connected components of the graph whose edges join pockets with any
    point pair <= ``touch`` Å or residue Jaccard >= ``jaccard``.  ``which``: ``region`` | ``v2`` | ``full``.
    Returned in order of their best member's rank."""
    sel = {"region": fs.pk_in_r
… [6,754 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:58:11

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; grep -n \"d_precision\\|d_coverage\\|d_members\" scripts/build_point_cache.py | head; python - <<'E'\nimport pandas as pd\nv=pd.read_parquet(\"data/splits/blips_val_pairs_v2.parquet\"); print(v.columns.tolist(), len(v), v.label.sum())\ns=pd.read_parquet(\"data/splits/blips_sites_v2.parquet\"); print(s.columns.tolist()); print(s.partition.value_counts())\np=pd.read_parquet(\"data/splits/ppi_l_pockets.parquet\"); print(p.columns.tolist(), len(p)); \ni=pd.read_parquet(\"data/processed/cache/points/ppi_l/index.parquet\"); print(i.columns.tolist(), len(i), i.status.value_counts().to_dict())\nE"}
```


**← tool result**

```
Exit code 1
148:                    row.update(d_members=np.asarray(p.members if p else [], np.int32),
152:                               d_precision=pk.coverage(fs, p.idx, lp.idx) if p else 0.0)
177:        "dmode_region_coverage_p50": float(ok.d_coverage.median()) if len(ok) else None,
179:        "dmode_region_missed_but_precision_ge_0.5": float((ok.d_missed & (ok.d_precision >= 0.5)).mean())
181:        "dmode_region_precision_p50": float(ok.d_precision.median()) if len(ok) else None,
['pair_id', 'label', 'max_tc', 'n_shared', 'pair_cluster', 'best_ccd_a', 'best_ccd_b', 'site_a', 'protein_a', 'group_a', 'label_ccd_a', 'site_cluster_a', 'site_b', 'protein_b', 'group_b', 'label_ccd_b', 'site_cluster_b', 'n_shared_stratum', 'promiscuous', 'chemotype_seen', 'site_clusters_in_train'] 3378 563
['site_id', 'partition_v1', 'node_id', 'sid', 'protein', 'uniprot', 'pdb_id', 'chain', 'site_index', 'site_residues', 'structure_id', 'site_name', 'group_id', 'site_is_ion', 'all_ccds', 'q_ccds', 'n_qualifying', 'label_ccd', 'label_ha', 'label_smiles', 'label_cluster', 'cluster_in_train', 'n_lmode_points', 'partition']
partition
train            2350
val               511
excluded_lt10       1
Name: count, dtype: int64
['pocket_id', 'pdb', 'chain', 'uniprot', 'lig', 'resnum', 'labels', 'cavities', 'n_cavities', 'cavity_volume', 'pfam_accession', 'pfam_name', 'cath', 'label', 'smiles', 'heavy_atoms', 'ligand_file', 'inchikey', 'structure_path', 'in_pdb_mirror', 'ligand_cluster', 'mol_id', 
… [2,112 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:58:16

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; ls data/processed/cache/points/ppi_l | head; ls data/processed/cache/points/ppi_l | wc -l; ls data/processed/cache/points/ppips | head -3; ls data/processed/cache/points/blips | head -3; python - <<'E'\nimport pandas as pd\nfor f in [\"data/processed/cache/points/blips/index.parquet\",\"data/processed/cache/points/ppips/index.parquet\"]:\n    try:\n        i=pd.read_parquet(f); print(f,i.columns.tolist(), len(i))\n    except Exception as e: print(f,e)\nE\nsed -n 1,40p scripts/ppi/11_ppil_pockets.py; grep -n \"index\\|cache_file\\|lmode\" scripts/ppi/11_ppil_pockets.py | head -30; sed -n 1195,1230p scripts/final_eval.py; grep -n \"def available\\|class .*Store\" -A12 scripts/final_eval.py | head -60"}
```


**← tool result**

```
1a28_A.npz
1a9u_A.npz
1ap8_A.npz
1axb_A.npz
1b8y_A.npz
1bav_A.npz
1bgq_A.npz
1bl4_A.npz
1bl6_A.npz
1bm6_A.npz
4003
AF-0000000065760570.npz
AF-0000000065760573.npz
AF-0000000065761128.npz
A0A023I7E1__5xc2_A.npz
A0A023UGN9__6zjs_A.npz
A0A023X3C8__7lq4_A.npz
data/processed/cache/points/blips/index.parquet ['pocket_id', 'structure_key', 'cache_file', 'status', 'failure_reason', 'n_points_structure', 'n_full', 'n_region', 'n_merged_region', 'definition', 'lmode_idx', 'n_points', 'n_points_dense', 'volume_A3', 'n_lining_res', 'lining_residues', 'n_ligand_atoms', 'ligand_protein_min_dist', 'n_missing_residues', 'alt_definition', 'alt_idx', 'alt_n_points', 'alt_volume_A3', 'alt_jaccard', 'alt_n_missing_residues', 'alt_chain_remapped', 'd_coverage', 'd_missed', 'd_members', 'd_n_points', 'd_volume_A3', 'd_score', 'd_rank_in_merged', 'd_precision', 'dfull_coverage', 'dfull_missed'] 2862
data/processed/cache/points/ppips/index.parquet data/processed/cache/points/ppips/index.parquet
#!/usr/bin/env python
"""PPI-L step 2: pocket table in our format + BURROW point cache via the pocket adapter (L-mode on the ligand).

Input : data/processed/ppi/ppil/ligand_instances.parquet (10_).
Structure = local PDB mirror mmCIF, chain = the ligand-bound chain only (the pocketome's PL systems are single
chains; the partner is absent).  Featurised once per (pdb, chain) with pockets.featurize_structure (holo
mode, default preset, `all` ranker).
L-mode (DESIGN §2.2): BURROW points <= 4 Å of the modulator's 
… [4,864 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:58:23

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'E'\nimport pandas as pd\nP=pd.read_parquet(\"data/processed/ppi/ppil/pockets.parquet\"); print(P.columns.tolist(), len(P)); print(P.status.value_counts().to_dict())\nfor f in [\"ppi_l_pairs_val\",\"ppi_l_pairs_train\"]:\n    d=pd.read_parquet(f\"data/splits/{f}.parquet\"); print(f,d.columns.tolist(),len(d)); print(d.head(2).T)\nE\ngrep -n \"ppi_l\" -r scripts/*.py reports/*.md src | grep -v \"^scripts/final_eval.py:12\" | head -20; grep -n \"^class\\|^def \" scripts/final_eval.py | head -80"}
```


**← tool result**

```
['pocket_id', 'pdb', 'chain', 'uniprot', 'lig', 'resnum', 'labels', 'cavities', 'n_cavities', 'cavity_volume', 'pfam_accession', 'pfam_name', 'cath', 'label', 'smiles', 'heavy_atoms', 'ligand_file', 'inchikey', 'structure_path', 'in_pdb_mirror', 'ligand_cluster', 'mol_id', 'key', 'structure_key', 'status', 'failure_reason', 'definition', 'lmode_idx', 'n_points', 'n_points_dense', 'volume_A3', 'n_lining_res', 'lining_residues', 'n_ligand_atoms_struct', 'ligand_protein_min_dist', 'd_coverage', 'd_missed', 'd_members', 'd_precision', 'pocket_def_type', 'pocket_def', 'ligand_resname', 'cache_file'] 4421
{'ok': 4375, 'failed': 46}
ppi_l_pairs_val ['pocket_a', 'pocket_b', 'label', 'ecfp4_tc', 'group_a', 'group_b', 'ligand_cluster_a', 'ligand_cluster_b', 'volume_a', 'volume_b', 'label_a', 'label_b'] 70501
                               0               1
pocket_a          1jvj:A:IM2:300  1jvj:A:IM2:300
pocket_b          1kzk:A:JE2:701  1nmk:A:SFM:166
label                          0               0
ecfp4_tc                0.127451        0.102362
group_a                   1axb_A          1axb_A
group_b                   1kzk_A          1nmk_A
ligand_cluster_a          1545.0          1545.0
ligand_cluster_b          1543.0           101.0
volume_a                   487.0           487.0
volume_b                  1255.0          1164.0
label_a                     PLOC            PLOC
label_b                     PLOC            PLOC
ppi_l_pairs_train ['pocket_a', 'pocket_b', 'label', '
… [3,776 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:58:27

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; sed -n 100,170p scripts/final_eval.py; sed -n 190,305p scripts/final_eval.py; sed -n 343,372p scripts/final_eval.py; sed -n 501,565p scripts/final_eval.py; sed -n 636,730p scripts/final_eval.py; sed -n 825,850p scripts/final_eval.py; sed -n 1105,1135p scripts/final_eval.py"}
```


**← tool result**

```
import eval_dev as ED  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.descstore import DescriptorStore  # noqa: E402
from pocketcompare.provenance import git_state, sha256_file, write_result  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402
from pocketcompare.similarity import ZScorer, csls_r, embed, pair_scores  # noqa: E402

PREREG_EVALUATE_SHA256 = "f22d02967c08d706d8a6081865a8ba40f491340e87e205826e32f8206f65707b"
CSLS_K = ED.CSLS_K
SESOI = 0.03
METHOD_CFG = ROOT / "configs/final_method.yaml"
SEALED_DIR = ROOT / "data/sealed"
SEALED_SUMS = ROOT / "data/sealed_SHA256SUMS.txt"
SPLIT_SUMS = ROOT / "data/splits/SHA256SUMS.txt"
SEALED_NEEDED = ("tough_m1_test_pairs.parquet", "prospeccts_pairs.parquet", "blips_test_pairs.parquet",
                 "blips_test_sites.parquet", "vertex_pairs.parquet", "tough_m1_pairs.parquet",
                 "ppips_test_queries.parquet", "ppips_sym_test_pairs.parquet")
WORKTREE_LINKS = ("data/processed", "data/sealed", "data/raw", "data/splits/homology_edges.parquet", "tools",
                  "results/dev", "results/proteome", "results/models")
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


# ============================================================================================ sealed access
class Sealed:
    """Temporary unsealing of data/sealed/<name> with sha256 check and an append-only access log."""

    def __init__(self, log_path:
… [20,219 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:58:33

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; grep -n \"ppi_l\\|ppil\" scripts/build_point_cache.py scripts/compute_descriptors.py src/pocketcompare/descstore.py | head -20; sed -n 100,170p scripts/build_point_cache.py; sed -n 1,80p src/pocketcompare/descstore.py"}
```


**← tool result**

```
scripts/compute_descriptors.py:22:  tough_m1, blips, blips_test_holo, blips_test_af, ppi_l   point-cache index.parquet as written by build_point_cache.py
            fs = None
    if fs is None:
        try:
            fs = pk.featurize_structure(_abs(task["structure_path"]), chains=task["chains"], af_mode=task["af_mode"],
                                        preset=task["preset"], ranker=task["ranker"], key=key)
            ts = time.perf_counter()
            tim["bytes"] = fs.save(out)
            tim["save_s"] = time.perf_counter() - ts
            tim.update(fs.meta["timings"])
        except Exception as e:  # noqa: BLE001
            tim.update(status="failed", error=f"featurize: {type(e).__name__}: {e}")
            tim["total_s"] = time.perf_counter() - t0
            rows = [{"pocket_id": r["pocket_id"], "structure_key": key, "status": "failed",
                     "failure_reason": tim["error"]} for r in task["rows"]]
            return rows, tim
    tim.update(n_atoms=int(len(fs.atom_xyz)), n_points=int(len(fs.points)), n_full=int(fs.n_pockets),
               n_region=int(fs.pk_in_region.sum()))
    ti = time.perf_counter()
    merged = {w: pk.merge_pockets(fs, w) for w in ("region", "full")}
    rows = []
    for r in task["rows"]:
        row = {"pocket_id": r["pocket_id"], "structure_key": key, "cache_file": _rel(out),
               "status": "ok", "failure_reason": None, "n_points_structure": int(len(fs.points)),
               "n_full": int(fs.n_pocket
… [6,658 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:58:47

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; sed -n 1,60p scripts/compute_descriptors.py; sed -n 565,576p scripts/final_eval.py; sed -n 850,893p scripts/final_eval.py; cat scripts/run_final_prep_desc.sh | head -30; grep -n \"def load_light\" -A15 scripts/compute_descriptors.py"}
```


**← tool result**

```
#!/usr/bin/env python
"""Compute tier-1 pocket descriptors for every pocket of a cached dataset (label-free).

    python scripts/compute_descriptors.py --dataset tough_m1 --arm a1 --config all --mode both --workers 12
    python scripts/compute_descriptors.py --dataset tough_m1 --arm b1 --config all --mode both
    python scripts/compute_descriptors.py --dataset tough_m1 --arm b0 --mode both

Inputs : data/processed/cache/points/<dataset>/{index.parquet,<key>.npz} (pocketcompare.pockets point cache).
Outputs: data/processed/descriptors/<dataset>/<arm>_<config>_<mode>.npy        (n, d) float32, NaN rows = failed
         .../<arm>_<config>_<mode>.ids.parquet (+ .prov.json sidecar)          row order of the .npy
         .../<arm>_<config>_<mode>.layout.json                                 block layout / column names
L-mode: every pocket of the index.  D-mode: every pocket with a matched merged BURROW pocket (``d_members``
non-empty); ``d_coverage``, ``d_precision``, ``d_missed`` and ``d_match`` (coverage >= 0.3 or precision >= 0.5,
DESIGN §2.2) are carried in the ids table so callers apply the DESIGN rule themselves.
Per-pocket descriptor time (``time_ms``: pocket assembly + typing + descriptor, one thread, excluding npz I/O)
is recorded per row.

--label-free-structures is required for prospeccts / vertex (sealed external sets): only their label-free point
cache is read (DESIGN D2).

Dataset adapters (index -> rows; the TOUGH-M1 path is unchanged):
  tough_m1, blips, blips_t
… [7,210 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 22:58:51

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; grep -n \"index\\b\\|index\\.\\|index\\[\" scripts/compute_descriptors.py | head -30; grep -n \"def volume\" -A4 src/pocketcompare/pockets.py"}
```


**← tool result**

```
8:Inputs : data/processed/cache/points/<dataset>/{index.parquet,<key>.npz} (pocketcompare.pockets point cache).
12:L-mode: every pocket of the index.  D-mode: every pocket with a matched merged BURROW pocket (``d_members``
21:Dataset adapters (index -> rows; the TOUGH-M1 path is unchanged):
22:  tough_m1, blips, blips_test_holo, blips_test_af, ppi_l   point-cache index.parquet as written by build_point_cache.py
154:    idx = load_index(_DATASET)
169:    return PPIPS_POCKETS if dataset == "ppips" else ROOT / "data/processed/cache/points" / dataset / "index.parquet"
172:def load_index(dataset: str) -> pd.DataFrame:
238:def main_a1r(a, index, out_dir, t_start):
243:    rows = index[["pocket_id", "cache_file", "lmode_idx", "d_members"]].to_dict("records")
259:    m = index.set_index("pocket_id").loc[ids.pocket_id]
328:    index = load_index(a.dataset)
329:    index = index[index.status == "ok"].reset_index(drop=True)
331:        index = index.iloc[:a.limit]
333:        return main_a1r(a, index, out_dir, t_start)
342:    rows = index[cols].to_dict("records")
356:    meta = index.set_index("pocket_id")
411:                ids.to_parquet(ids_path, index=False)
148:    def volume(self, idx) -> float:
149-        """Å^3 of a point-index set (respects the coarse sub-lattice weights)."""
150-        return float(self.vol[np.asarray(idx, np.int64)].sum(dtype=np.float64) * self.spacing ** 3)
151-
152-    def point_tree(self) -> cKDTree:
```


### Assistant · 2026-10-27 22:58:53

Write the index builder.


**→ tool call `bash`** · 2026-10-27 22:58:53

```
{"command": "echo"}
```


**← tool result**

```
<tool_use_error>Error: No such tool available: bash. Tool names are case-sensitive: call Bash instead.</tool_use_error>
```


**→ tool call `Write`** · 2026-10-27 22:59:02

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/ppi/14_ppil_index.py", "content": "#!/usr/bin/env python\n\"\"\"PPI-L step 3: point-cache index.parquet for data/processed/cache/points/ppi_l (adapter, label-free).\n\n11_ppil_pockets.py wrote the pocket table (data/processed/ppi/ppil/pockets.parquet, with lmode_idx / d_members /\nd_coverage / d_precision per pocket) and the per-chain point caches, but not the build_point_cache.py-style\nindex.parquet that compute_descriptors.py, compute_n_inputs.py and scripts/final_eval.py read.  This script writes it\n(no re-featurisation, no labels beyond what the table already holds): the table rows with status == 'ok', plus\nd_n_points / d_volume_A3 / d_score of the matched merged pocket (union of the d_members; pocket points from the cache).\n\n    python scripts/ppi/14_ppil_index.py --workers 12\n\"\"\"\nfrom __future__ import annotations\n\nimport os\n\nfor _v in (\"NUMBA_NUM_THREADS\", \"OMP_NUM_THREADS\", \"OPENBLAS_NUM_THREADS\", \"MKL_NUM_THREADS\"):\n    os.environ[_v] = \"1\"\nos.environ.setdefault(\"NUMBA_CACHE_DIR\", \"/tmp/numba_cache\")\n\nimport argparse  # noqa: E402\nimport sys  # noqa: E402\nimport time  # noqa: E402\nfrom multiprocessing import get_context  # noqa: E402\nfrom pathlib import Path  # noqa: E402\n\nimport numpy as np  # noqa: E402\nimport pandas as pd  # noqa: E402\n\nROOT = Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT / \"src\"))\nsys.path.insert(0, str(ROOT / \"sc
… [2,193 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/ppi/14_ppil_index.py (file state is current in your context — no need to Read it back)
```


**→ tool call `Bash`** · 2026-10-27 22:59:06

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; python scripts/ppi/14_ppil_index.py --workers 12 2>&1 | tail -5 && (python scripts/compute_n_inputs.py --dataset ppi_l --workers 12 2>&1 | tail -15)", "timeout": 1800000}
```


**← tool result**

```
wrote /cluster/project/beltrao/gmagnus/pocket_compare/data/processed/cache/points/ppi_l/index.parquet (4375 pockets, 4375 with a D pocket) in 17s
   "t_a1_sph8_ms": 5.4509860929101706,
   "t_env_ms": 0.17134984955191612
  }
 },
 "D": {
  "n_ok_sph8": 4375,
  "t_ms_median": {
   "t_shape_ms": 0.18056994304060936,
   "t_a1_base_ms": 2.0885381381958723,
   "t_a1_sph8_ms": 4.675035830587149,
   "t_env_ms": 0.16043893992900848
  }
 }
} 
done 4375 pockets in 12s
```


### Assistant · 2026-10-27 22:59:39

Now B1 / A1 pair_only / B0 baselines for PPI-L.


**→ tool call `Bash`** · 2026-10-27 22:59:41

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; for spec in \"a1 pair_only\" \"b1 default\" ; do set -- $spec; python scripts/compute_descriptors.py --dataset ppi_l --arm $1 --config $2 --mode both --workers 12 2>&1 | tail -2; done; python scripts/compute_descriptors.py --dataset ppi_l --arm b0 --mode both 2>&1 | tail -2; ls data/processed/descriptors/ppi_l; grep -n \"a1_pair_only\\|pair_only\" scripts/final_eval.py | head -3; ls data/processed/descriptors/blips | grep pair_only | head -3", "timeout": 1800000}
```


**← tool result**

```
  wrote a1_pair_only_D: (4375, 392), failed 0, median 1.83 ms/pocket (p90 11.75)
[compute_descriptors] done in 9s
  wrote b1_default_D: (4375, 45), failed 0, median 0.85 ms/pocket (p90 1.33)
[compute_descriptors] done in 6s
  wrote b0_default_D: (4375, 1), failed 0, median 0.00 ms/pocket (p90 0.00)
[compute_descriptors] done in 5s
a1_pair_only_D.ids.parquet
a1_pair_only_D.ids.parquet.prov.json
a1_pair_only_D.layout.json
a1_pair_only_D.npy
a1_pair_only_L.ids.parquet
a1_pair_only_L.ids.parquet.prov.json
a1_pair_only_L.layout.json
a1_pair_only_L.npy
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
n_inputs_D.npz
n_inputs_L.npz
n_inputs_ids.parquet
n_inputs_ids.parquet.prov.json
n_inputs_layout.json
35:Until A4b delivers ``pocketcompare.method``, ``--dryrun-dev`` uses the stand-in ``A1 pair_only`` (z-score on the
50:    B5-T shipped APoc / G-LoSA / SiteEngine columns, A1 pair_only, random control; raw and CSLS) with ROC-AUC, AP
173:    """Stand-in final method (dry run only): A1 pair_only, z-scored on the pool, cosine, no CSLS."""
a1_pair_only_D.ids.parquet
a1_pair_only_D.ids.parquet.prov.json
a1_pair_only_D.layout.json
```


**→ tool call `Bash`** · 2026-10-27 23:00:13

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; grep -n \"ppi_l\" data/sealed_SHA256SUMS.txt data/splits/SHA256SUMS.txt; grep -n \"SEALED_NEEDED\" scripts/final_eval.py; sed -n 1,35p tests/test_final_eval.py; sed -n 641,645p scripts/final_eval.py; grep -n \"class Vec\" -A12 scripts/final_eval.py; grep -n \"\\-\\-dryrun-dev\\|add_argument\" scripts/final_eval.py | head -30"}
```


**← tool result**

```
114:SEALED_NEEDED = ("tough_m1_test_pairs.parquet", "prospeccts_pairs.parquet", "blips_test_pairs.parquet",
1361:        nohash = [n for n in SEALED_NEEDED if n not in Sealed(Path("/dev/null"), False).expected]
"""scripts/final_eval.py guards (synthetic files only; never touches data/sealed/)."""
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fe():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("final_eval", ROOT / "scripts/final_eval.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["final_eval"] = m
    spec.loader.exec_module(m)
    return m


def _sealed(tmp_path, fe, monkeypatch, corrupt=False):
    d = tmp_path / "sealed"
    d.mkdir()
    f = d / "x_pairs.parquet"
    pd.DataFrame({"a": [1, 2, 3]}).to_parquet(f)
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    sums = tmp_path / "sums.txt"
    sums.write_text(f"{'0' * 64 if corrupt else h}  data/sealed/x_pairs.parquet\n")
    os.chmod(f, 0)
    monkeypatch.setattr(fe, "SEALED_DIR", d)
    monkeypatch.setattr(fe, "SEALED_SUMS", sums)
    return f
def evaluate_vectors(name, vecs, y_all, units, pc_all, cov_all, dset, subsets, args, *, generic_filter=None,
                     synthetic=False, ap_neg=False):
    """One row per (vector, subset): point metrics + vertex-bootstrap CIs (wider over unit defin
… [1,039 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 23:00:27

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python - <<'E'\np=\"scripts/final_eval.py\"\ns=open(p).read()\nnew_stage='''\nPPIL_PAIR_FILE = \"ppi_l_test_pairs.parquet\"\n\n\ndef ppil_set(name: str, pairs: pd.DataFrame) -> PairSet:\n    \"\"\"PPI-L (exploratory C3; reports/ppi_datasets.md): pairs of PLOC/PLONC modulator pockets (label 1 = cross-group,\n    ECFP4 Tc >= 0.5; 0 = Tc < 0.3).  Units: homology group ('hom') and ligand Butina cluster ('lig').  Descriptors:\n    data/processed/descriptors/ppi_l (scripts/ppi/14_ppil_index.py + compute_n_inputs.py / compute_descriptors.py).\"\"\"\n    a = pairs[[\"pocket_a\", \"group_a\", \"ligand_cluster_a\"]].set_axis([\"pocket_id\", \"group\", \"lig\"], axis=1)\n    b = pairs[[\"pocket_b\", \"group_b\", \"ligand_cluster_b\"]].set_axis([\"pocket_id\", \"group\", \"lig\"], axis=1)\n    P = pd.concat([a, b]).drop_duplicates(\"pocket_id\").sort_values(\"pocket_id\").reset_index(drop=True)\n    P = _attach_geometry(P, \"ppi_l\")\n    hom = pd.factorize(P.group)[0]\n    lig = pd.factorize(P.lig.astype(\"string\").fillna(P.pocket_id))[0]\n    P[\"unit\"] = hom\n    ia, ib = _pairs_index(P, pairs)\n    y = pairs.label.to_numpy().astype(int)\n    return PairSet(name, \"ppi_l\", P, ia, ib, y, {\"hom\": hom, \"lig\": lig}, subsets={\"all\": np.ones(len(y), bool)},\n                   pairs=pairs)\n\n\ndef stage_ppil(ps: PairSet, method, store, args):\n    log(f\"[{ps.name}] {len(ps.pockets)} pocket
… [2,424 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
64:  PPI-L test (exploratory): run iff its descriptors exist, else recorded as skipped.
```


**→ tool call `Bash`** · 2026-10-27 23:00:34

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; SP=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; cat > $SP/t_ppil.py <<'E'\nimport sys, types, importlib.util, pandas as pd, numpy as np\nsys.path.insert(0,\"/cluster/project/beltrao/gmagnus/pocket_compare/scripts\")\nspec=importlib.util.spec_from_file_location(\"final_eval\",\"/cluster/project/beltrao/gmagnus/pocket_compare/scripts/final_eval.py\")\nfe=importlib.util.module_from_spec(spec); sys.modules[\"final_eval\"]=fe; spec.loader.exec_module(fe)\nfrom pocketcompare.descstore import DescriptorStore\nR=fe.ROOT\nm,_=fe.load_method(False)\ntr=pd.read_parquet(R/\"data/splits/ppi_l_pairs_train.parquet\")\npos=tr[tr.label==1]; neg=tr[tr.label==0].sample(60000,random_state=0)\nps=fe.ppil_set(\"ppi_l_train_smoke\",pd.concat([pos,neg]).reset_index(drop=True))\nargs=types.SimpleNamespace(B=100,seed=1,threads=8)\ntab,info=fe.stage_ppil(ps,m,DescriptorStore(R),args)\nprint(info)\nprint(tab[[\"key\",\"mode\",\"n_pairs\",\"n_pos\",\"auc\",\"auc_lo\",\"auc_hi\"]].to_string())\nE\npython $SP/t_ppil.py 2>&1 | tail -30", "timeout": 900000}
```


**← tool result**

```
Command did not complete within its 600s timeout and was moved to the background (ID: bu3bn57k3). Output is being written to: /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bu3bn57k3.output. You will be notified when it completes. It is running now: do not start a second copy while it runs. If it is no longer needed, stop it with TaskStop. No output had been read from it when it was moved. A program that buffers its output, or a pipe into one such as tail, can keep the output file empty until the command finishes. To check interim output, use Read on that file path.
Session cwd remains /cluster/project/beltrao/gmagnus/pocket_compare; directory changes made by the backgrounded command do not apply to subsequent commands.
```


**→ tool call `Write`** · 2026-10-27 23:11:50

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/scripts/eval_blind.py", "content": "#!/usr/bin/env python\n\"\"\"Blind deployment test (DESIGN §2.7; secondary, reported).  No ligand guidance anywhere in the query/pool.\n\n    python scripts/eval_blind.py --set val                                   # dry run: BLiPS-val v2 sites with an AF model\n    FINAL_EVAL=1 python scripts/eval_blind.py --set test --pairs <blips_test_pairs>   # PI / final_eval only (NOT run here)\n\nSet  = the sites of the chosen partition that have an AF model (adapter of scripts/eval_af_robustness.py: val ->\n       BLiPS-val v2 sites with a pocket_detect af_train model; test -> BLiPS-test af_set, exclusions v2).  The AF models\n       of the set are the \"proteins\"; the labelled ligand-sharing pairs (val pairs v2 / the sealed test pairs, supplied\n       by the PI: this script never opens data/sealed) restricted to pairs whose two sites are both in the set.\nPool = ALL BURROW region-rule pockets of every AF model (AF mode, no ligand): merged (pockets.merge_pockets 'region'),\n       >= 10 points (drops the single-point metal candidates).  Every pool pocket is described with the final method\n       (configs/final_method.yaml via pocketcompare.method.raw_parts/embed: base = the merged pocket, sph8 shaper) and\n       with B1 (default, z-scored on the pool; label-free) and B0 (size) for reference.  B4 needs ESM-2 on a GPU and is\n       not computed here (documented gap).\nTruth (the ONLY 
… [18,111 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 23:11:51

```
{"command": "cat /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bu3bn57k3.output | tail -30"}
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/scripts/eval_blind.py (file state is current in your context — no need to Read it back)
```


**← tool result**

```
(Bash completed with no output)
```


**→ tool call `Bash`** · 2026-10-27 23:11:56

```
{"command": "ps aux | grep -c \"t_ppil\" ; ps aux | grep t_ppil | head -3 | cut -c1-150; uptime"}
```


**← tool result**

```
5
gmagnus+ 1040378  0.0  0.0   4464  3396 ?        Ss   00:00   0:00 /bin/bash -c source /home/.claude/shell-snapshots/snapshot-bash-1793121823956-muadw
gmagnus+ 1040382  4.0  0.1 9522468 758036 ?      Sl   00:00   0:27 python /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-
gmagnus+ 1271229  0.0  0.0   4464  3368 ?        Ss   00:11   0:00 /bin/bash -c source /home/.claude/shell-snapshots/snapshot-bash-1793121823956-muadw
 00:11:57 up 14 days, 17:30,  0 user,  load average: 151.00, 136.57, 100.70
```


**→ tool call `Bash`** · 2026-10-27 23:12:01

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; nohup python scripts/eval_blind.py --set val --B 2000 --workers 12 > /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/blind.log 2>&1 &\nsleep 90; cat /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/blind.log", "timeout": 200000}
```


**← tool result**

```
[1]+  Done                    nohup python scripts/eval_blind.py --set val --B 2000 --workers 12 > /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/blind.log 2>&1
[00:12:04] blips_val_v2_af_blind: 239 sites, 158 AF models, 698 pairs (93 positive)
[00:12:09] described 158 AF models in 5s, 0 errors
[00:12:09] pool: 817 pockets from 157 models; 147/239 sites detected
[00:12:18] done in 16s; results in /cluster/project/beltrao/gmagnus/pocket_compare/results/dev/blind_val
```


**→ tool call `Bash`** · 2026-10-27 23:13:37

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; cat results/dev/blind_val/details.json; python - <<'E'\nimport pandas as pd\npd.set_option(\"display.width\",200)\nR=pd.read_csv(\"results/dev/blind_val/metrics.csv\")\nR[\"v\"]=R.estimate.round(3).astype(str)+\" [\"+R.ci_low.round(3).astype(str)+\",\"+R.ci_high.round(3).astype(str)+\"]\"\nfor (v,c),g in R.groupby([\"variant\",\"conditional\"]):\n    print(v,c, g.n_pairs.iloc[0]); print(g.pivot(index=\"arm\",columns=\"metric\",values=\"v\").to_string())\nE\ntail -2 results/trials.tsv | cut -c1-200"}
```


**← tool result**

```
{
 "n_sites": 239,
 "n_models": 157,
 "n_pool_pockets": 817,
 "pockets_per_model_median": 4.0,
 "n_sites_detected": 147,
 "n_pairs_pos": 93,
 "n_directed_pos": 186,
 "n_directed_both_detected": 84,
 "median_candidates": 810.0,
 "b4": "not computed (ESM-2 needs a GPU)",
 "n_model_errors": 0
}all False 186
metric                      auc                  hit1                 hit10                hit100                   mrr
arm                                                                                                                    
B0          0.473 [0.411,0.532]         0.0 [0.0,0.0]     0.016 [0.0,0.078]     0.032 [0.0,0.107]   0.006 [0.001,0.022]
B1           0.566 [0.469,0.68]     0.005 [0.0,0.034]       0.048 [0.0,0.2]     0.188 [0.047,0.4]   0.024 [0.002,0.084]
final       0.561 [0.461,0.674]     0.016 [0.0,0.059]      0.07 [0.0,0.192]     0.199 [0.048,0.4]   0.032 [0.003,0.087]
final-B1  -0.006 [-0.056,0.037]  0.011 [-0.027,0.057]  0.022 [-0.051,0.118]  0.011 [-0.071,0.119]  0.008 [-0.043,0.067]
all True 84
metric                      auc                  hit1                 hit10               hit100                   mrr
arm                                                                                                                   
B0          0.439 [0.306,0.567]         0.0 [0.0,0.0]     0.036 [0.0,0.152]    0.071 [0.0,0.206]   0.013 [0.002,0.041]
B1          0.647 [0.412,0.827]      0.012 [0.0,0.07]     0.107 [0.0,0.354]  0.417 [0.132,0.691]   0.053 
… [2,314 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 23:13:43

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; python scripts/eval_blind.py --set test --pairs x 2>&1 | tail -2; echo rc=$?; python scripts/eval_blind.py --set test 2>&1 | tail -1; cat /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bu3bn57k3.output | tail; ls results/dev/blind_val"}
```


**← tool result**

```
refusing: --set test needs FINAL_EVAL=1 (PI / final_eval wrapper only)
rc=0
refusing: --set test needs FINAL_EVAL=1 (PI / final_eval wrapper only)
details.json
metrics.csv
metrics.parquet
metrics.parquet.prov.json
pairs.parquet
pairs.parquet.prov.json
pockets.parquet
pockets.parquet.prov.json
```


**→ tool call `Bash`** · 2026-10-27 23:13:51

```
{"command": "sleep 240; ps aux | grep t_ppil.py | grep -v grep | awk '{print $3,$4,$10}'; cat /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bu3bn57k3.output | tail", "timeout": 300000}
```


**← tool result**

```
<tool_use_error>Blocked: sleep 240 followed by: ps aux grep t_ppil.py grep -v grep awk '{print $3,$4,$10}' cat /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bu3bn57k3.output tail. To wait for a condition, use Monitor with an until-loop (e.g. `until <check>; do sleep 2; done`). To wait for a command you started, use run_in_background: true. Do not chain shorter sleeps to work around this block.</tool_use_error>
```


**→ tool call `Bash`** · 2026-10-27 23:13:55

```
{"command": "ps aux | grep t_ppil.py | grep -v grep | awk '{print $3,$4,$10}'; py-spy --version 2>/dev/null; cat /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bu3bn57k3.output | tail"}
```


**← tool result**

```
0.0 0.0 0:00
3.5 0.1 0:28
```


**→ tool call `Bash`** · 2026-10-27 23:14:00

```
{"command": "pid=$(pgrep -f \"python .*t_ppil.py\" | head -1); echo $pid; cat /proc/$pid/wchan; echo; ls /proc/$pid/task | wc -l; for t in $(ls /proc/$pid/task | head -5); do cat /proc/$pid/task/$t/stat | awk '{print $3,$14,$15}'; done; ls -l /proc/$pid/fd | tail -5; pgrep -P $pid | head"}
```


**← tool result**

```
1040378
do_wait
1
S 0 0
total 0
lrwx------ 1 gmagnusson gmagnusson-group 64 Oct 28 00:01 0 -> socket:[156402477]
l-wx------ 1 gmagnusson gmagnusson-group 64 Oct 28 00:01 1 -> /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bu3bn57k3.output
l-wx------ 1 gmagnusson gmagnusson-group 64 Oct 28 00:01 2 -> /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tasks/bu3bn57k3.output
1040382
1040383
```


**→ tool call `Bash`** · 2026-10-27 23:14:03

```
{"command": "pid=1040382; ps -o pid,pcpu,etime,time,nlwp -p $pid,1040383; ls /proc/$pid/task | wc -l; pgrep -P $pid | head -3"}
```


**← tool result**

```
    PID %CPU     ELAPSED     TIME NLWP
1040382  3.5       13:28 00:00:28  177
1040383  0.0       13:28 00:00:00    1
177
1040560
1316143
1316145
```


**→ tool call `Bash`** · 2026-10-27 23:14:07

```
{"command": "ps -o pid,ppid,pcpu,etime,time,nlwp,cmd --ppid 1040382 | cut -c1-160; uptime; nproc"}
```


**← tool result**

```
    PID    PPID %CPU     ELAPSED     TIME NLWP CMD
1040560 1040382  0.0       13:30 00:00:00    1 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.resource_tracker import 
1317577 1040382  287       00:02 00:00:06  173 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main;
1317590 1040382  616       00:02 00:00:13  169 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main;
1317591 1040382  466       00:02 00:00:09  168 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main;
1317719 1040382  283       00:01 00:00:05  174 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main;
1317862 1040382  454       00:01 00:00:07  173 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main;
1317961 1040382  395       00:01 00:00:04  142 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main;
1318025 1040382  311       00:01 00:00:03  128 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main;
1318494 1040382  772       00:00 00:00:03   65 /cluster/project/beltrao/gmagnus/pocket_compare/.venv/bin/python -c from multiprocessing.spawn import spawn_main;

… [78 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 23:14:14

```
{"command": "pkill -f t_ppil.py; sleep 2; cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache; SP=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; sed -i 's/sample(60000/sample(4000/; s/B=100,seed=1,threads=8/B=30,seed=1,threads=4/' $SP/t_ppil.py; export NUMBA_NUM_THREADS=4 POCKETCOMPARE_THREADS=4; timeout 580 python $SP/t_ppil.py 2>&1 | tail -30", "timeout": 600000}
```


**← tool result**

```
Exit code 144
```


**→ tool call `Bash`** · 2026-10-27 23:14:19

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache NUMBA_NUM_THREADS=4 POCKETCOMPARE_THREADS=4; SP=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; nohup python -u $SP/t_ppil.py > $SP/ppil.log 2>&1 &\necho started"}
```


**→ tool call `Monitor`** · 2026-10-27 23:14:21

```
{"command": "until grep -q \"auc\" /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/ppil.log || grep -q Traceback /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/ppil.log; do sleep 5; done; tail -30 /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/ppil.log", "description": "wait for PPI-L smoke test", "timeout_ms": 900000, "persistent": "false"}
```


**← tool result**

```
started
```


**← tool result**

```
Monitor started (task b8xfudo43, expires in 15m unless the source ends first; you get one notice at expiry — re-arm if you still need the watch). You will be notified on each event. Keep working — do not poll or sleep. Events may arrive while you are waiting for the user — an event is not their reply.
```


### Assistant · 2026-10-27 23:14:24

Meanwhile, write the report skeleton after results; wait for the monitor.


**→ tool call `Monitor`** · 2026-10-27 23:14:25

```
{"command": "sleep 1; echo", "description": "noop", "timeout_ms": 5000, "persistent": "false"}
```


**← tool result**

```
Monitor started (task bicqy19gg, expires in 5s unless the source ends first; you get one notice at expiry — re-arm if you still need the watch). You will be notified on each event. Keep working — do not poll or sleep. Events may arrive while you are waiting for the user — an event is not their reply.
```


**→ tool call `Bash`** · 2026-10-27 23:14:28

```
{"command": "cat /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/ppil.log | tail"}
```


**← tool result**

```
            if __name__ == '__main__':
                freeze_support()
                ...

        The "freeze_support()" line can be omitted if the program
        is not going to be frozen to produce an executable.

        To fix this issue, refer to the "Safe importing of main module"
        section in https://docs.python.org/3/library/multiprocessing.html
```


**→ tool call `Bash`** · 2026-10-27 23:14:33

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; pkill -f t_ppil.py; export NUMBA_CACHE_DIR=/tmp/numba_cache NUMBA_NUM_THREADS=4 POCKETCOMPARE_THREADS=4; SP=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; python - <<E\ns=open(\"$SP/t_ppil.py\").read()\nhead,body=s.split(\"R=fe.ROOT\",1)\nbody=\"R=fe.ROOT\"+body\nbody=\"\\n\".join(\"    \"+l for l in body.splitlines())\nopen(\"$SP/t_ppil.py\",\"w\").write(head+\"def main():\\n\"+body+\"\\n\\nif __name__=='__main__':\\n    main()\\n\")\nE\ntimeout 550 python -u $SP/t_ppil.py 2>&1 | tail -30", "timeout": 600000}
```


**← tool result**

```
Exit code 144
```


**→ tool call `Bash`** · 2026-10-27 23:14:38

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache NUMBA_NUM_THREADS=4 POCKETCOMPARE_THREADS=4; SP=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; tail -5 $SP/t_ppil.py; timeout 550 python -u $SP/t_ppil.py 2>&1 | tail -30", "timeout": 600000}
```


**← tool result**

```
Exit code 143
ps=fe.ppil_set("ppi_l_train_smoke",pd.concat([pos,neg]).reset_index(drop=True))
args=types.SimpleNamespace(B=100,seed=1,threads=8)
tab,info=fe.stage_ppil(ps,m,DescriptorStore(R),args)
print(info)
print(tab[["key","mode","n_pairs","n_pos","auc","auc_lo","auc_hi"]].to_string())
Terminated
```


**→ tool call `Bash`** · 2026-10-27 23:23:56

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache NUMBA_NUM_THREADS=4 POCKETCOMPARE_THREADS=4; SP=/tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad; cat > $SP/t_ppil.py <<'E'\nimport sys, types, importlib.util, pandas as pd, numpy as np\nsys.path.insert(0,\"/cluster/project/beltrao/gmagnus/pocket_compare/scripts\")\ndef main():\n    spec=importlib.util.spec_from_file_location(\"final_eval\",\"/cluster/project/beltrao/gmagnus/pocket_compare/scripts/final_eval.py\")\n    fe=importlib.util.module_from_spec(spec); sys.modules[\"final_eval\"]=fe; spec.loader.exec_module(fe)\n    from pocketcompare.descstore import DescriptorStore\n    R=fe.ROOT\n    m,_=fe.load_method(False)\n    tr=pd.read_parquet(R/\"data/splits/ppi_l_pairs_train.parquet\")\n    pos=tr[tr.label==1]; neg=tr[tr.label==0].sample(20000,random_state=0)\n    ps=fe.ppil_set(\"ppi_l_train_smoke\",pd.concat([pos,neg]).reset_index(drop=True))\n    args=types.SimpleNamespace(B=50,seed=1,threads=4)\n    tab,info=fe.stage_ppil(ps,m,DescriptorStore(R),args)\n    print(info)\n    print(tab[[\"key\",\"mode\",\"n_pairs\",\"n_pos\",\"auc\",\"auc_lo\",\"auc_hi\"]].to_string())\nif __name__==\"__main__\":\n    main()\nE\ntimeout 550 python -u $SP/t_ppil.py 2>&1 | tail -30", "timeout": 600000}
```


**← tool result**

```
[    0.5s] [ppi_l_train_smoke] 1278 pockets, 20034 pairs (34 pos); D-set 17961
[    2.9s]     generic bootstrap 20/28 (2 s)
{'n_pairs': 20034, 'n_pos': 34, 'n_pockets': 1278, 'n_d_set': 17961, 'arms': ['A1|pair_only|csls|D', 'A1|pair_only|csls|L', 'A1|pair_only|raw|D', 'A1|pair_only|raw|L', 'B0|default|raw|D', 'B0|default|raw|L', 'B1|default|csls|D', 'B1|default|csls|L', 'B1|default|raw|D', 'B1|default|raw|L', 'FINAL|pocketcompare-final:N1|raw|csls|D', 'FINAL|pocketcompare-final:N1|raw|csls|L', 'FINAL|pocketcompare-final:N1|raw|raw|D', 'FINAL|pocketcompare-final:N1|raw|raw|L']}
                                        key mode  n_pairs  n_pos       auc    auc_lo    auc_hi
0    FINAL|pocketcompare-final:N1|raw|raw|L    L    20034     34  0.591184  0.298967  0.796362
1   FINAL|pocketcompare-final:N1|raw|csls|L    L    20034     34  0.745579  0.418051  0.899193
2    FINAL|pocketcompare-final:N1|raw|raw|D    D    17961     23  0.578379  0.349900  0.915453
3   FINAL|pocketcompare-final:N1|raw|csls|D    D    17961     23  0.756015  0.458318  0.956756
4                          B0|default|raw|L    L    20034     34  0.547615  0.320998  0.752498
5                          B0|default|raw|D    D    17961     23  0.500164  0.142752  0.829374
6                          B1|default|raw|L    L    20034     34  0.730313  0.418539  0.880670
7                         B1|default|csls|L    L    20034     34  0.763762  0.461639  0.922110
8                          B1|default|raw|D    D    17961   
… [509 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 23:24:06

```
{"command": "cd /cluster/project/beltrao/gmagnus/pocket_compare; source .venv/bin/activate; export NUMBA_CACHE_DIR=/tmp/numba_cache NUMBA_NUM_THREADS=4; python -m pytest tests/test_final_eval.py -q 2>&1 | tail -5; python - <<'E'\nimport sys,importlib.util,types,pandas as pd\nsys.path.insert(0,\"scripts\")\nspec=importlib.util.spec_from_file_location(\"final_eval\",\"scripts/final_eval.py\"); fe=importlib.util.module_from_spec(spec); sys.modules[\"final_eval\"]=fe; spec.loader.exec_module(fe)\nv=pd.read_parquet(\"data/splits/ppi_l_pairs_val.parquet\"); ps=fe.ppil_set(\"ppi_l_val\",v)\nprint(len(ps.pockets), ps.pockets.cache_ok.mean(), ps.y.sum())\nprint(fe.stage_ppil(ps,None,None,None))\nE", "timeout": 600000}
```


**← tool result**

```
....                                                                     [100%]
4 passed in 0.81s
528 1.0 0
[    0.1s] [ppi_l_val] 528 pockets, 70501 pairs (0 pos); D-set 58195
(None, {'n_pairs': 70501, 'n_pos': 0, 'note': 'too few positives to evaluate'})
```


**→ tool call `Write`** · 2026-10-27 23:24:24

```
{"file_path": "/cluster/project/beltrao/gmagnus/pocket_compare/reports/blind_and_ppil.md", "content": "# Blind deployment test (dry run on BLiPS-val v2) and PPI-L final-eval inputs (2026-10-28)\n\nNothing committed; `data/sealed/` not opened. Test paths exist and refuse without `FINAL_EVAL=1`; not run.\n\n## 1. Blind test, BLiPS-val v2 dry run (`scripts/eval_blind.py --set val`, B = 2,000, 16 s)\nSet: 239 val sites with an AF model, 157 AF models, pool = **817** BURROW region-rule merged pockets (>= 10 points; median 4 per model). 93 positive val pairs = 186 directed queries. Median candidates per query 810 (chance hit@100 ~ 12 %). 95 % CIs: vertex bootstrap over homology groups.\n\n**Detection recall** (site -> detected pocket by the D rule, ligand used only for this): **0.615 [0.551, 0.683]** of all 239 sites; 0.667 [0.561, 0.776] for sites in positive pairs. Both ends detected for 84 of 186 directed pairs (45 %).\n\nPartner retrieval, both sites detected (n = 84 directed pairs), candidates = pockets of all other proteins, other positives filtered:\n\n| arm | hit@1 | hit@10 | hit@100 | MRR | AUC |\n|---|---|---|---|---|---|\n| final (N1) | 0.036 [0.00, 0.15] | 0.155 [0.00, 0.39] | 0.440 [0.13, 0.71] | 0.071 [0.01, 0.20] | 0.634 [0.41, 0.82] |\n| B1 | 0.012 [0.00, 0.07] | 0.107 [0.00, 0.35] | 0.417 [0.13, 0.69] | 0.053 [0.01, 0.15] | 0.647 [0.41, 0.83] |\n| B0 (size) | 0.000 | 0.036 | 0.071 | 0.013 | 0.439 [0.31, 0.57] |\n| final - B1 | +0.024 [-0.06, +0.15] | +0.048 [-0.10,
… [2,600 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
File created successfully at: /cluster/project/beltrao/gmagnus/pocket_compare/reports/blind_and_ppil.md (file state is current in your context — no need to Read it back)
```


**→ tool call `SubagentHandback`** · 2026-10-27 23:24:31

```
{"message": "Both tasks are done and nothing is committed. The test paths refuse without FINAL_EVAL=1 and were not run, and data/sealed/ was not opened. The report is reports/blind_and_ppil.md.\n\n**Task 1 (BLiPS-val v2 dry run, scripts/eval_blind.py)**\n- The set is 239 sites on 157 AF models. The pool is 817 merged BURROW pockets of at least 10 points. Results are in results/dev/blind_val/, with trials arm blind_dev.\n- Detection recall is 0.615 [0.551, 0.683]. Both sites of a pair were detected for 84 of 186 directed pairs.\n- Partner retrieval for those 84 pairs, final vs B1:\n\n| metric | final | B1 |\n|---|---|---|\n| hit@1 | 0.036 | 0.012 |\n| hit@10 | 0.155 | 0.107 |\n| hit@100 | 0.44 | 0.417 |\n| MRR | 0.071 | 0.053 |\n| AUC | 0.634 | 0.647 |\n\n- Final beats the size baseline (B0 AUC 0.44) but is not distinguishable from B1: every final−B1 CI includes 0. Power is low at about 42 unique pairs.\n- B4 is not included (it needs the GPU).\n\n**Task 2 (PPI-L inputs)**\n- PPI-L point-cache index, N1/N2 inputs, and A1 pair_only/B1/B0 descriptors now exist.\n- I added a PPI-L evaluation stage to scripts/final_eval.py (it was previously \"not implemented\"). tests/test_final_eval.py passes (4 tests). The new stage was only smoke-tested on a train-pair subsample.\n- PI action: add the sha256 of ppi_l_test_pairs.parquet (starts 8a10795f) to data/sealed_SHA256SUMS.txt, otherwise PPI-L is recorded as skipped at final eval."}
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
