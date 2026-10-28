#!/usr/bin/env python
"""PREREG2 temporal replication (PDB-T): the single evaluation script (claims R1-R3 + reported items).

    python scripts/eval_pdbt.py --dryrun-dev [--B 2000] [--threads 12]     # identical code path on BLiPS-val v2
    python scripts/eval_pdbt.py --prepare [--device cuda:2]                # label-free: L4 embeddings of PDB-T
    FINAL_EVAL=1 python scripts/eval_pdbt.py --check-only                  # every guard, no sealed file opened
    FINAL_EVAL=1 python scripts/eval_pdbt.py [--device cuda:2]             # THE real run (one look)

Nothing is trained, tuned or selected here.  All arms are the frozen artefacts, evaluated with the frozen functions of
scripts/final_eval.py (imported, never modified; hash-checked against FREEZE.json together with evaluate.py,
configs/final_method.yaml, the A4b weights and PREREG.md):
  FINAL   pocketcompare-final:A4b:n1_linear raw (final_eval.load_method -> MethodAdapter; N1 inputs from
          data/processed/descriptors/<ds>/a1r via pocketcompare.a4b.raw_parts)
  N1      raw (final_eval EXTRA_ARMS, BLiPS-train part statistics)
  L4      L4:egnn_small, designated variant CSLS (k = 10, background = evaluated pool); raw also reported.
          Embeddings data/processed/l4_emb/egnn_small/emb_<ds>_{L,U}.npy; for PDB-T they are computed here (--prepare,
          or at the start of the real run, before unsealing) from the build's label-free point sets
          data/processed/l4/<ds>/ with scripts/train_l4.load_models / ensemble_embed (= scripts/l4_embed.py).
  FUSION  the declared rule of scripts/explore/fusion_a4b_l4.py, reused exactly (its FusedMethod class): w = 0.5,
          s = w z(cos_FINAL) + (1 - w) z(cos_L4), both raw, z fitted on BLiPS-train v2 pairs
          (results/exploratory/fusion/fusion_scales.json); raw inner product, no CSLS.
  B1      default descriptor, pool z-scored cosine, raw (FINAL is raw -> B1 raw, as final_eval C1-D)
  B0      -|delta log V| (L-mode volume; D-mode matched-pocket volume)
Claims (Holm over {R1, R2, R3}, one-sided alpha 0.05; ROC-AUC; final_eval.paired = evaluate.paired_bootstrap,
vertex bootstrap B = 2000, seed SEEDS[0], units = PDB-T homology components; D mode = both sites D-matched by the
frozen rule coverage >= 0.3 or precision >= 0.5; common set of the two compared arms, as final_eval C1-D):
  R1  FINAL[raw] - B1[raw]          R2  FUSION[raw] - FINAL[raw]          R3  L4[csls] - FINAL[raw]
Reported (no multiplicity): the same three deltas in L mode, R3 with L4 raw, and per arm / mode (final_eval.
evaluate_vectors): ROC-AUC, AP, McClish pAUC, cluster-balanced AUC (positive clusters = the pair's ligand Butina
cluster), size-stratified AUC (5 x 20, 5 x 5 if < 500 positives), vertex-bootstrap CIs, missing / worst case; B0.

Guards of the real run (refuse otherwise): FINAL_EVAL=1; frozen files == FREEZE.json, evaluate.py == the PREREG
constant, PREREG2.md == its D24 hash, L4 weights / fusion scales / fusion script == the hashes recorded below;
scripts/eval_pdbt.py committed and unmodified; results/pdbt/gate.json present and parseable (PASS -> confirmatory;
FAIL -> DESCRIPTIVE mode: no p-values, no Holm, no claims, stated in every output); the sealed pair file has a
recorded sha256 in data/sealed_SHA256SUMS.txt; results/pdbt/claims.json absent (one look; --rerun overrides and is
recorded).  The sealed file is read through final_eval.Sealed: chmod 400 -> sha256 check -> read into memory ->
chmod 000 (finally), one row per access in results/pdbt/unseal_log.tsv.  Sealed contents are never written to disk.
Outputs: results/pdbt/{claims.json, summary.parquet, report.md} (+ .prov.json sidecars); dry run -> results/pdbt_dryrun/
(+ reproduction_check.json: FINAL / N1 / L4 / B1 vs results/dev/l4/final_select_all_l4_summary.parquet, FUSION vs
results/exploratory/fusion/dev/final_select_fusion_summary.parquet, and the recomputed L4 embeddings vs the stored).

Expected PDB-T inputs (written by scripts/data/build_pdbt.py; the first matching column name is used, recorded):
  data/splits/pdbt_sites.parquet   site id (site_id | pocket_id); homology component (hom_component |
                                   homology_component | component | group_id); optional bool `excluded`
  data/sealed/pdbt_pairs.parquet   (site_a, site_b | pocket_a, pocket_b), label (1 / 0), positive ligand cluster
                                   (pair_cluster | ligand_cluster | butina_cluster)
  label-free caches of dataset `pdbt`: data/processed/cache/points/pdbt/index.parquet, descriptors/pdbt/a1r/,
  descriptors/pdbt/b1_default_{L,D}.npy (+ .ids.parquet), data/processed/l4/pdbt/ (point sets)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import eval_dev as ED  # noqa: E402
import final_eval as FE  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.descstore import DescriptorStore  # noqa: E402
from pocketcompare.provenance import git_state, sha256_file, write_result  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402

_spec = importlib.util.spec_from_file_location("fusion_a4b_l4", ROOT / "scripts/explore/fusion_a4b_l4.py")
FU = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FU)

T0 = time.time()
PREREG2_SHA256 = "20c3e6c5ac5c573fd63d381276e0476d4a85f865b65396b590bad7cc13e3e686"   # RESEARCH_TREE D24
FROZEN2 = {   # artefacts PREREG2 names that are not in FREEZE.json (hashes recorded when this script was written)
    "results/models/l4/egnn_small/config.json": "6284809bae4a352a7e5258e5d773edd48e9161b40d1c1b9f9388f260fb93bdc7",
    "results/models/l4/egnn_small/point_scaler.json": "a8d14b49df6c462ffb1c683c7b18ae94cf04f6e52a0da9fa9004c4b96e7a1751",
    "results/models/l4/egnn_small/n1_stats.json": "845d5671dc3ef8184330ebcd788c70b9a078280cf7ea57a623facbba8a86a95d",
    "results/models/l4/egnn_small/seed0.pt": "863b3130ea1d55e0d3c33200e3c5a87ac0771aedfa4635bfb23c265c9f436a5f",
    "results/models/l4/egnn_small/seed1.pt": "8ad15367a5752a9816a7606b59275e6b02c6ed6b6857baeba059031ca8923284",
    "results/models/l4/egnn_small/seed2.pt": "d353d6d35dd5c345ba0d0058e78ee89254f8202ec1f8c2bb531a5a2cf87d8537",
    "results/exploratory/fusion/fusion_scales.json": "cf64b3c8f2fc2200efc0d88030ba38caa08b66238f0b86353165ead4f865c53e",
    "results/exploratory/fusion/dev/fusion_selection.json":
        "e8736fd83f6b126fbbf9fbc530375937619406038bfc2264b49855b56b3cce85",
    "scripts/explore/fusion_a4b_l4.py": "f3f03923c53e3b5134f69850172d0e2473105d9c5303a32522147201962f64a7",
}
W_FUSION = 0.5                                   # PREREG2: "w 0.5 z-score rule exactly as declared"
L4_DIR = ROOT / "results/models/l4/egnn_small"
L4_EMB = ROOT / "data/processed/l4_emb" / FE.L4_MODEL
PDBT_DS = "pdbt"
PDBT_SITES = ROOT / "data/splits/pdbt_sites.parquet"
PDBT_PAIRS = "pdbt_pairs.parquet"                # under data/sealed/
GATE = ROOT / "results/pdbt/gate.json"
OUT_REAL = ROOT / "results/pdbt"
OUT_DRY = ROOT / "results/pdbt_dryrun"
DRY_SITES = ROOT / "data/splits/blips_sites_v2.parquet"
DRY_PAIRS = ROOT / "data/splits/blips_val_pairs_v2.parquet"
REF_SEL = ROOT / "results/dev/l4/final_select_all_l4_summary.parquet"
REF_FUS = ROOT / "results/exploratory/fusion/dev/final_select_fusion_summary.parquet"
SITE_COLS = ("site_id", "pocket_id")
UNIT_COLS = ("hom_component", "homology_component", "component", "group_id")
PAIR_COLS = (("site_a", "site_b"), ("pocket_a", "pocket_b"))
CLUSTER_COLS = ("pair_cluster", "ligand_cluster", "butina_cluster")
CLAIMS = (("R1", "FINAL", "raw", "B1", "raw"), ("R2", "FUSION", "raw", "FINAL", "raw"),
          ("R3", "L4", "csls", "FINAL", "raw"))


def log(msg):
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


# ============================================================================================ guards
def check_frozen() -> dict:
    """Frozen files == FREEZE.json (+ evaluate.py == PREREG constant), PREREG2 == D24 hash, FROZEN2 hashes."""
    fr = json.loads((ROOT / "FREEZE.json").read_text())
    checks = {"scripts/final_eval.py": fr["final_eval_sha256"], "src/pocketcompare/evaluate.py": fr["evaluate_sha256"],
              fr["method_config"]: fr["method_config_sha256"], "PREREG.md": fr["prereg_sha256"], **fr["weights"],
              "PREREG2.md": PREREG2_SHA256, **FROZEN2}
    bad = {p: (sha256_file(ROOT / p), h) for p, h in checks.items() if sha256_file(ROOT / p) != h}
    if fr["evaluate_sha256"] != FE.PREREG_EVALUATE_SHA256 or ev.module_sha256() != FE.PREREG_EVALUATE_SHA256:
        bad["evaluate.py vs PREREG §4 constant"] = (ev.module_sha256(), FE.PREREG_EVALUATE_SHA256)
    if bad:
        raise SystemExit(f"frozen file(s) differ from their recorded hashes: {bad}")
    log(f"frozen files match ({len(checks)} files; FREEZE commit {fr['commit'][:10]}, PREREG2 {PREREG2_SHA256[:10]})")
    return {"freeze_commit": fr["commit"], "files_checked": checks}


def script_committed() -> dict:
    rel = "scripts/eval_pdbt.py"
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True).returncode == 0
    clean = tracked and subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT).returncode == 0
    return {"tracked": tracked, "unmodified_vs_HEAD": clean, "sha256": sha256_file(Path(__file__))}


def read_gate() -> dict:
    """results/pdbt/gate.json (written by the build before any score) -> {'verdict': PASS|FAIL, ...}."""
    if not GATE.exists():
        raise SystemExit(f"{GATE} missing: the PREREG2 gate must be recorded before any score")
    g = json.loads(GATE.read_text())
    verdict = None
    for k in ("gate", "verdict", "status", "result", "decision", "outcome"):
        x = g.get(k)
        if isinstance(x, dict):
            x = next((x[k2] for k2 in ("verdict", "status", "result") if isinstance(x.get(k2), str)), None)
        if isinstance(x, str) and x.strip().upper() in ("PASS", "FAIL"):
            verdict = x.strip().upper()
            break
    if verdict is None:
        for k in ("pass", "passed", "gate_pass", "gate_passed"):
            if isinstance(g.get(k), bool):
                verdict = "PASS" if g[k] else "FAIL"
                break
    if verdict is None:
        raise SystemExit(f"{GATE}: no PASS / FAIL verdict found (keys {sorted(g)})")
    return {"verdict": verdict, "file": str(GATE), "sha256": sha256_file(GATE),
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(GATE.stat().st_mtime)), "content": g}


def _pick(df: pd.DataFrame, names, what, required=True):
    for n in names:
        if (isinstance(n, tuple) and all(c in df for c in n)) or (not isinstance(n, tuple) and n in df):
            return n
    if required:
        raise SystemExit(f"no {what} column (tried {names}; have {list(df.columns)})")
    return None


def input_preflight(ds: str, need_l4_points: bool) -> dict:
    """Label-free inputs of dataset ``ds``; raises with the missing files."""
    from pocketcompare import a4b as A4
    a1r = A4.a1r_dir(ds)
    need = [ROOT / f"data/processed/cache/points/{ds}/index.parquet", a1r / "ids.parquet"]
    need += [a1r / f"{loc}_{sh}.npz" for loc in ("L", "U") for sh in ("sph8", "base")]
    need += [ROOT / f"data/processed/descriptors/{ds}/b1_default_{m}{suf}" for m in ("L", "D")
             for suf in (".npy", ".ids.parquet")]
    if need_l4_points:
        need += [ROOT / f"data/processed/l4/{ds}/{f}" for f in ("ids.parquet", "L.npz", "U.npz")]
    miss = [str(p.relative_to(ROOT)) for p in need if not p.exists()]
    if miss:
        raise SystemExit(f"missing label-free inputs for dataset {ds!r}: {miss}")
    return {str(p.relative_to(ROOT)): sha256_file(p) for p in need if p.suffix != ".npz"}


# ============================================================================================ L4 embeddings
_L4M: dict = {}


def l4_forward(ds, loc, ids, device):
    """scripts/l4_embed.py's computation (train_l4.load_models / ensemble_embed) for ``ids`` of dataset ``ds``."""
    import torch
    import train_l4 as T
    torch.set_num_threads(min(12, int(os.environ.get("POCKETCOMPARE_THREADS", "12"))))
    if device.startswith("cuda") and not torch.cuda.is_available():
        log(f"  {device} unavailable -> cpu")
        device = "cpu"
    if device not in _L4M:
        _L4M[device] = T.load_models(L4_DIR, device)
    models, cfg, sc, n1s = _L4M[device]
    E, av = T.ensemble_embed(models, cfg, sc, n1s, ds, loc, list(ids), device)
    return E, av, device


def ensure_l4(ds: str, device: str) -> dict:
    """emb_<ds>_{L,U}.npy: computed (label-free, all ids_table rows) if absent; sha256 + sidecar either way."""
    from pocketcompare import a4b as A4
    info = {}
    for loc in ("L", "U"):
        f = L4_EMB / f"emb_{ds}_{loc}.npy"
        side = f.with_name(f.name + ".prov.json")
        if not f.exists():
            ids = A4.ids_table(ds).pocket_id.tolist()
            t0 = time.time()
            E, av, dev_used = l4_forward(ds, loc, ids, device)
            L4_EMB.mkdir(parents=True, exist_ok=True)
            np.save(f, E)
            side.write_text(json.dumps({
                "result": str(f), "result_sha256": sha256_file(f), "n": int(len(E)), "n_available": int(av.sum()),
                "model_dir": str(L4_DIR), "model_files_sha256": {k: v for k, v in FROZEN2.items() if "/l4/" in k},
                "device": dev_used, "wall_s": round(time.time() - t0, 1), "script": str(Path(__file__)),
                "script_sha256": sha256_file(Path(__file__)), "computation": "train_l4.ensemble_embed (as l4_embed.py)",
                **git_state()}, indent=1, default=str) + "\n")
            log(f"  L4 embedded {ds} {loc}: {E.shape}, available {int(av.sum())} ({time.time() - t0:.0f} s)")
        sha = sha256_file(f)
        if side.exists():
            rec = json.loads(side.read_text()).get("result_sha256")
            if rec and rec != sha:
                raise SystemExit(f"{f}: sha256 {sha} != its sidecar {rec}")
        info[f.name] = sha
    return info


def l4_recheck(ds, device) -> dict:
    """Dry run: recompute ensure_l4's embedding (all ids_table rows, as for PDB-T) and compare with the stored file."""
    from pocketcompare import a4b as A4
    ids = A4.ids_table(ds).pocket_id.tolist()
    out = {}
    for loc in ("L", "U"):
        E, av, dev_used = l4_forward(ds, loc, ids, device)
        S = np.load(L4_EMB / f"emb_{ds}_{loc}.npy")
        out[loc] = {"n": int(len(ids)), "device": dev_used, "shape_equal": E.shape == S.shape,
                    "max_abs_dev": float(np.abs(E - S).max()) if E.shape == S.shape else None}
    return out


# ============================================================================================ pair set
def load_sites(path: Path, partition: str | None) -> tuple[pd.DataFrame, dict]:
    S = pd.read_parquet(path)
    if partition is not None:
        S = S[S.partition == partition]
    info = {"file": str(path), "n_rows": int(len(S))}
    if "excluded" in S and S["excluded"].dtype == bool:
        info["n_excluded_flag"] = int(S["excluded"].sum())
        S = S[~S["excluded"]]
    sid, unit = _pick(S, SITE_COLS, "site id"), _pick(S, UNIT_COLS, "homology component")
    info.update(site_col=sid, unit_col=unit)
    S = S.rename(columns={sid: "site_id"}).assign(_unit=S[unit].to_numpy())
    if S.site_id.duplicated().any():
        raise SystemExit(f"{path}: duplicated site ids")
    return S.sort_values("site_id").reset_index(drop=True), info


def build_set(name: str, ds: str, sites: pd.DataFrame, pairs: pd.DataFrame) -> tuple[FE.PairSet, dict]:
    """final_eval.PairSet over the whole site pool (= z-score / CSLS background), units = homology components."""
    ca, cb = _pick(pairs, PAIR_COLS, "pair site")
    pcl = _pick(pairs, CLUSTER_COLS, "positive ligand cluster", required=False)
    # D25: sites flagged `excluded` (audit boundary) leave the pool; their pairs are dropped and counted (no scores yet)
    keep = pairs[ca].isin(sites.site_id) & pairs[cb].isin(sites.site_id)
    n_drop, n_drop_pos = int((~keep).sum()), int(pairs.label[~keep].sum())
    pairs = pairs[keep].reset_index(drop=True)
    P = FE._attach_geometry(pd.DataFrame({"pocket_id": sites.site_id.to_numpy(), "unit_label": sites._unit.to_numpy()}),
                            ds)
    unit = pd.factorize(P.unit_label)[0]
    P["unit"] = unit
    ia, ib = FE._pairs_index(P, pairs, ca, cb)
    y = pairs.label.to_numpy().astype(int)
    log(f"[{name}] dropped {n_drop} pairs ({n_drop_pos} positive) involving excluded sites")
    if not set(np.unique(y)) <= {0, 1}:
        raise SystemExit("labels must be 0 / 1")
    ps = FE.PairSet(name, ds, P, ia, ib, y, {"hom": unit}, pos_cluster=None if pcl is None else pairs[pcl].to_numpy(),
                    subsets={"all": np.ones(len(y), bool)}, pairs=pairs)
    d = ps.dset
    pu = np.unique(np.concatenate([unit[ia[y == 1]], unit[ib[y == 1]]])) if y.any() else []
    info = {"pair_cols": [ca, cb], "pos_cluster_col": pcl, "n_sites_pool": int(len(P)),
            "n_sites_cache_ok": int(P.cache_ok.sum()), "n_sites_d_match": int(P.d_match.sum()),
            "n_units_pool": int(unit.max() + 1), "n_pairs": int(len(y)), "n_pos": int(y.sum()),
            "n_neg": int((y == 0).sum()), "n_units_in_positive_pairs": int(len(pu)),
            "n_pos_clusters": None if pcl is None else int(pd.Series(ps.pos_cluster[y == 1]).nunique()),
            "n_pairs_D": int(d.sum()), "n_pos_D": int(y[d].sum()),
            "strat_bins_L": "x".join(map(str, ED.n_bins_for(y))), "strat_bins_D": "x".join(map(str, ED.n_bins_for(y[d])))}
    return ps, info


# ============================================================================================ evaluation
def all_vectors(ps, method, fused, store) -> list:
    vecs = FE.final_vectors(ps, method, store)                                      # FINAL + N1 + L4 (raw, csls)
    vecs += FE._method_vectors(ps, fused, store, ("L", "D"), None, "FUSION",
                               f"declared fusion rule (scripts/explore/fusion_a4b_l4.py), w = {W_FUSION}")
    vecs += FE.descriptor_vectors(ps, store, [s for s in FE.BASE_SPECS if s[0] == "B1"])
    vecs += FE.b0_vectors(ps)
    have = {(v.arm, v.variant, v.mode) for v in vecs}
    need = {(a, var, m) for a in ("FINAL", "N1", "L4", "FUSION", "B1") for var in ("raw", "csls") for m in ("L", "D")}
    if need - have:
        raise SystemExit(f"arms missing on {ps.name}: {sorted(need - have)}")
    return vecs


def get(vecs, arm, variant, mode):
    (v,) = [v for v in vecs if v.arm == arm and v.variant == variant and v.mode == mode]   # by attribute (DEV6)
    return v


def deltas(ps, vecs, args, mode, specs):
    out = {}
    for cid, a, va, b, vb in specs:
        r = FE.paired(ps.y, get(vecs, a, va, mode).s, get(vecs, b, vb, mode).s, ps.pair_units, args,
                      mask=ps.dset if mode == "D" else None)
        out[cid] = {"set": ps.name, "mode": "D (both sites D-matched; common set)" if mode == "D" else "L (common set)",
                    "comparison": f"{a}[{va}] − {b}[{vb}]", "metric": "ROC-AUC", "units": "homology components",
                    **r}
    return out


def evaluate(ps, method, fused, store, args, confirmatory: bool) -> tuple[pd.DataFrame, dict]:
    vecs = all_vectors(ps, method, fused, store)
    log(f"[{ps.name}] {len(vecs)} score vectors; per-arm metrics + bootstrap (B = {args.B})")
    summary, _ = FE.evaluate_vectors(ps.name, vecs, ps.y, ps.pair_units, ps.pos_cluster, ps.cov, ps.dset,
                                     ps.subsets, args)
    res = {"claims": None, "reported_deltas": {}}
    prim = deltas(ps, vecs, args, "D", CLAIMS)
    rep = {f"{k}-L": v for k, v in deltas(ps, vecs, args, "L", CLAIMS).items()}
    raw3 = (("R3raw", "L4", "raw", "FINAL", "raw"),)
    rep.update({f"R3raw-{m}": v for m in ("D", "L") for v in deltas(ps, vecs, args, m, raw3).values()})
    # common set over all four claim arms (sensitivity: the claims use the pairwise common set, as final_eval C1-D)
    allf = ps.dset.copy()
    for a, va in (("FINAL", "raw"), ("B1", "raw"), ("FUSION", "raw"), ("L4", "csls")):
        allf &= np.isfinite(get(vecs, a, va, "D").s)
    for cid, a, va, b, vb in CLAIMS:
        r = FE.paired(ps.y, get(vecs, a, va, "D").s, get(vecs, b, vb, "D").s, ps.pair_units, args, mask=allf)
        rep[f"{cid}-D-allarm-common"] = {"set": ps.name, "mode": "D, common set of FINAL, B1, FUSION, L4",
                                        "comparison": f"{a}[{va}] − {b}[{vb}]", "metric": "ROC-AUC", **r}
    if confirmatory:
        ids = [c[0] for c in CLAIMS]
        h = ev.holm([prim[c]["p_one_sided"] for c in ids], alpha=0.05)
        for c, pa, rj in zip(ids, h["p_adjusted"], h["reject"]):
            prim[c].update(p_holm=float(pa), reject_h0_holm=bool(rj), alpha=0.05)
        res["claims"] = prim
    else:   # descriptive: estimates + CIs only
        strip = ("p_one_sided",)
        res["descriptive_D_deltas_no_claims"] = {k: {kk: vv for kk, vv in v.items() if kk not in strip}
                                                 for k, v in prim.items()}
        rep = {k: {kk: vv for kk, vv in v.items() if kk not in strip} for k, v in rep.items()}
    res["reported_deltas"] = rep
    return summary, res


# ============================================================================================ report
def render_md(summary, res, meta) -> str:
    f = ED._f
    mode = meta["run_mode"]
    L = [f"# PDB-T temporal replication (PREREG2) — {mode}", ""]
    if meta.get("dryrun"):
        L += ["**DRY RUN on BLiPS-val v2** (identical code path; not PDB-T, no claim).", ""]
    if res["claims"] is None:
        L += [f"**DESCRIPTIVE MODE — gate verdict {meta['gate']['verdict']}: no claims are made (PREREG2 gate).** "
              "Deltas below are descriptive estimates with CIs; no p-values, no Holm.", ""]
    s = meta["set"]
    L += [f"Set `{meta['set_name']}` (cache dataset `{meta['dataset']}`): {s['n_sites_pool']} sites "
          f"({s['n_sites_d_match']} D-matched), {s['n_pairs']} pairs ({s['n_pos']} pos), D set {s['n_pairs_D']} pairs "
          f"({s['n_pos_D']} pos); {s['n_units_pool']} homology components (bootstrap units), "
          f"{s['n_units_in_positive_pairs']} in positive pairs; {s['n_pos_clusters']} positive ligand clusters. "
          f"B = {meta['B']}, seed {meta['seed']}. Gate: {meta['gate']['verdict']}.", ""]
    if res["claims"] is not None:
        L += ["## Claims (D mode, Holm over R1–R3, one-sided α 0.05)", "",
              "| claim | comparison | n (pos) | AUC a | AUC b | Δ [95 % CI] | lower 95 % | p | p Holm | reject |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for c, r in res["claims"].items():
            L.append(f"| {c} | {r['comparison']} | {r['n_pairs']} ({r['n_pos']}) | {r['auc_a']:.3f} | {r['auc_b']:.3f} | "
                     f"{r['delta']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] | {r['lower_one_sided_95']:+.3f} | "
                     f"{r['p_one_sided']:.4f} | {r['p_holm']:.4f} | {r['reject_h0_holm']} |")
    rows = dict(res.get("descriptive_D_deltas_no_claims") or {})
    rows.update(res["reported_deltas"])
    L += ["", "## Reported deltas (no multiplicity correction)", "",
          "| id | mode | comparison | n (pos) | AUC a | AUC b | Δ [95 % CI] |", "|---|---|---|---|---|---|---|"]
    for c, r in rows.items():
        L.append(f"| {c} | {r['mode']} | {r['comparison']} | {r['n_pairs']} ({r['n_pos']}) | {r['auc_a']:.3f} | "
                 f"{r['auc_b']:.3f} | {r['delta']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] |")
    L += ["", "## Arms", "", "| arm | variant | mode | n (pos) | ROC-AUC [CI] | AP (lift) | cb-AUC [CI] | "
          "size-strat [CI] (bins) | worst case |", "|---|---|---|---|---|---|---|---|---|"]
    for r in summary.itertuples():
        g = lambda k: getattr(r, k, np.nan)  # noqa: E731
        L.append(f"| {r.arm} | {r.variant} | {r.mode} | {r.n_pairs} ({r.n_pos}) | {f(r.auc)} [{f(g('auc_lo'))}, "
                 f"{f(g('auc_hi'))}] | {f(r.ap)} ({f(r.ap_lift, 2)}) | {f(g('auc_cb'))} [{f(g('auc_cb_lo'))}, "
                 f"{f(g('auc_cb_hi'))}] | {f(g('auc_strat'))} [{f(g('auc_strat_lo'))}, {f(g('auc_strat_hi'))}] "
                 f"({g('strat_n_bins')}) | {f(g('auc_worst_all'))} |")
    L += ["", f"FINAL = `{meta['method']}`; L4 designated variant CSLS; FUSION = `{meta['fusion']}`. "
          f"Sealed accesses: {meta.get('sealed_files_accessed', [])}."]
    if meta.get("reproduction"):
        rp = meta["reproduction"]
        L += ["", f"Dry-run reproduction: {rp['n_rows_compared']} rows, max |deviation| = {rp['max_abs_deviation']:.3g} "
              f"(n_pairs mismatches {rp['n_pairs_mismatch']}); L4 re-embedding max |Δ| "
              f"{json.dumps(rp.get('l4_recheck'))}."]
    return "\n".join(L) + "\n"


REPRO_MAP = [(REF_SEL, {"A4b:n1_linear": "FINAL", "N1": "N1", "L4:egnn_small": "L4", "B1": "B1"}),
             (REF_FUS, {"FUSEz:w0.50": "FUSION", "A4b:n1_linear": "FINAL", "L4:egnn_small": "L4", "B1": "B1"})]
REPRO_METRICS = {"auc": "auc", "ap": "ap", "auc_cb": "auc_cb", "auc_strat": "auc_strat",
                 "auc_cb_lo_hom": "auc_cb_lo_hom", "auc_cb_hi_hom": "auc_cb_hi_hom", "auc_cb_se_hom": "auc_cb_se",
                 "auc_strat_lo_hom": "auc_strat_lo_hom", "auc_strat_hi_hom": "auc_strat_hi_hom",
                 "auc_strat_se_hom": "auc_strat_se"}


def reproduction_check(summary) -> dict:
    out = {"rows": [], "max_abs_deviation": 0.0, "n_pairs_mismatch": 0}
    for f, cmap in REPRO_MAP:
        ref = pd.read_parquet(f)
        ref = ref[ref.dataset == "blips"]
        for cand, arm in cmap.items():
            for var in ("raw", "csls"):
                for mode in ("L", "D"):
                    a = summary[(summary.arm == arm) & (summary.variant == var) & (summary["mode"] == mode)]
                    b = ref[(ref.cand == cand) & (ref.variant == var) & (ref["mode"] == mode)]
                    if len(a) != 1 or len(b) != 1:
                        out["rows"].append({"ref": f.name, "cand": cand, "variant": var, "mode": mode,
                                            "error": f"rows mine {len(a)} ref {len(b)}"})
                        out["max_abs_deviation"] = float("inf")
                        continue
                    a, b = a.iloc[0], b.iloc[0]
                    d = {rm: abs(float(a[mm]) - float(b[rm])) for rm, mm in REPRO_METRICS.items()}
                    npm = int(a.n_pairs) != int(b.n_pairs)
                    out["rows"].append({"ref": f.name, "cand": cand, "arm": arm, "variant": var, "mode": mode,
                                        "n_pairs": int(a.n_pairs), "n_pairs_ref": int(b.n_pairs),
                                        "auc": float(a.auc), "auc_cb": float(a.auc_cb), "auc_cb_ref": float(b.auc_cb),
                                        "max_abs_dev": max(d.values()), "worst_metric": max(d, key=d.get)})
                    out["max_abs_deviation"] = max(out["max_abs_deviation"], max(d.values()))
                    out["n_pairs_mismatch"] += npm
    out["n_rows_compared"] = sum("error" not in r for r in out["rows"])
    out["metrics"] = list(REPRO_METRICS)
    return out


# ============================================================================================ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dryrun-dev", action="store_true", help="identical code path on BLiPS-val v2 (D mode primary)")
    ap.add_argument("--prepare", action="store_true", help="label-free: compute PDB-T L4 embeddings, check inputs")
    ap.add_argument("--check-only", action="store_true", help="real-run guards only; no sealed file is opened")
    ap.add_argument("--simulate-gate", choices=("PASS", "FAIL"), default="PASS", help="dry run only")
    ap.add_argument("--rerun", action="store_true", help="real run: allow a second look (recorded)")
    ap.add_argument("--no-l4-recheck", action="store_true", help="dry run: skip re-embedding the pool with L4")
    ap.add_argument("--B", type=int, default=ev.DEFAULT_B)
    ap.add_argument("--seed", type=int, default=SEEDS[0])
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--device", default="cuda:2")
    ap.add_argument("--out", default=None, help="dry run only")
    args = ap.parse_args()
    args.threads = min(args.threads, 12)
    os.environ["POCKETCOMPARE_THREADS"] = str(args.threads)
    dry = args.dryrun_dev
    frozen = check_frozen()
    if args.prepare:
        info = {"inputs": input_preflight(PDBT_DS, need_l4_points=True), "l4": ensure_l4(PDBT_DS, args.device)}
        log(f"prepare OK: {json.dumps(info['l4'])}")
        return 0

    # ------------------------------------------------------------------ guards
    if dry:
        if args.rerun or args.check_only:
            raise SystemExit("--rerun / --check-only belong to the real run")
        gate = {"verdict": args.simulate_gate, "file": None, "note": "dry run: simulated gate"}
        out = Path(args.out) if args.out else OUT_DRY
        if out.resolve() == OUT_REAL.resolve():
            raise SystemExit("the dry run never writes to results/pdbt/")
        name, ds = "blips_val_dryrun", "blips"
        inputs_ok = input_preflight(ds, need_l4_points=False)
        l4info = {f"emb_{ds}_{loc}.npy": sha256_file(L4_EMB / f"emb_{ds}_{loc}.npy") for loc in ("L", "U")}
        committed = script_committed()
    else:
        if os.environ.get("FINAL_EVAL") != "1":
            raise SystemExit("FINAL_EVAL=1 is required for the real PDB-T evaluation (use --dryrun-dev otherwise)")
        if args.out or args.simulate_gate != "PASS":
            raise SystemExit("--out / --simulate-gate are dry-run options")
        committed = script_committed()
        if not committed["unmodified_vs_HEAD"]:
            raise SystemExit("scripts/eval_pdbt.py must be committed and unmodified before the real run")
        gate = read_gate()
        out, name, ds = OUT_REAL, "pdbt", PDBT_DS
        if (out / "claims.json").exists() and not args.rerun:
            raise SystemExit(f"{out / 'claims.json'} exists: the PDB-T look has been taken (--rerun to override)")
        sealed_probe = FE.Sealed(Path("/dev/null"), enabled=False)
        if PDBT_PAIRS not in sealed_probe.expected:
            raise SystemExit(f"no recorded sha256 for data/sealed/{PDBT_PAIRS} in {FE.SEALED_SUMS.name}")
        if not PDBT_SITES.exists():
            raise SystemExit(f"{PDBT_SITES} missing")
        inputs_ok = input_preflight(ds, need_l4_points=not all((L4_EMB / f"emb_{ds}_{l}.npy").exists()
                                                                for l in ("L", "U")))
        if args.check_only:
            l4p = {f"emb_{ds}_{l}.npy": (L4_EMB / f"emb_{ds}_{l}.npy").exists() for l in ("L", "U")}
            log(f"preflight OK: gate {gate['verdict']}, sealed hash recorded, inputs present, L4 embeddings {l4p}; "
                "no sealed file was opened")
            return 0
        l4info = ensure_l4(ds, args.device)                       # label-free, before unsealing
    confirmatory = gate["verdict"] == "PASS"
    log(f"mode {'DRYRUN-DEV' if dry else 'PDB-T'}; gate {gate['verdict']} -> "
        f"{'confirmatory claims' if confirmatory else 'DESCRIPTIVE ONLY (no claims)'}")

    # ------------------------------------------------------------------ methods
    method, cfg_sha = FE.load_method(allow_standin=False)
    sel = json.loads(FU.SELECTION.read_text())
    sc = json.loads(FU.SCALES.read_text())
    if float(sel["w_star"]) != W_FUSION:
        raise SystemExit(f"fusion selection w* {sel['w_star']} != PREREG2 w {W_FUSION}")
    fused = FU.FusedMethod(method, W_FUSION, sc["sd_A"], sc["sd_L"])
    store = DescriptorStore(ROOT)

    # ------------------------------------------------------------------ set
    if dry:
        sites, sinfo = load_sites(DRY_SITES, "val")
        pairs = pd.read_parquet(DRY_PAIRS)
        sealed = FE.Sealed(out / "unseal_log.tsv", enabled=False)
    else:
        sites, sinfo = load_sites(PDBT_SITES, None)
        sealed = FE.Sealed(out / "unseal_log.tsv", enabled=True)
        pairs = sealed.read(PDBT_PAIRS, "PREREG2 PDB-T evaluation (R1-R3 + reported items), scripts/eval_pdbt.py")
    ps, info = build_set(name, ds, sites, pairs)
    info["sites"] = sinfo
    log(f"[{name}] {json.dumps({k: v for k, v in info.items() if k != 'sites'})}")

    # ------------------------------------------------------------------ evaluate
    summary, res = evaluate(ps, method, fused, store, args, confirmatory)
    run_mode = ("DRYRUN-DEV" if dry else "PDB-T") + (" confirmatory" if confirmatory else " DESCRIPTIVE (no claims)")
    meta = {"run_mode": run_mode, "dryrun": dry, "set_name": name, "dataset": ds, "set": info, "gate": gate,
            "B": args.B, "seed": args.seed, "method": method.name, "method_config_sha256": cfg_sha,
            "fusion": fused.name, "fusion_w": W_FUSION, "fusion_scales": {k: sc[k] for k in ("mu_A", "sd_A", "mu_L",
                                                                                              "sd_L")},
            "l4_embeddings_sha256": l4info, "inputs_sha256": inputs_ok, "frozen": frozen,
            "eval_pdbt": committed, "prereg2_sha256": PREREG2_SHA256, "evaluate_sha256": ev.module_sha256(),
            "sealed_files_accessed": sealed.accessed, "rerun": bool(args.rerun), "git": git_state()}
    if dry:
        rep = reproduction_check(summary)
        if not args.no_l4_recheck:
            rep["l4_recheck"] = l4_recheck(ds, args.device)
        meta["reproduction"] = rep
    claims_doc = {"label": "PREREG2 temporal replication (PDB-T)" + (" — DRY RUN on BLiPS-val v2" if dry else ""),
                  "run_mode": run_mode, "claims_made": res["claims"] is not None, **res, "meta": meta}
    cfg = {"task": "eval_pdbt", "run_mode": run_mode, "B": args.B, "seed": args.seed, "csls_k": FE.CSLS_K,
           "fusion_w": W_FUSION, "method": method.name, "prereg2_sha256": PREREG2_SHA256}
    inputs = sorted({str(p) for p in store.inputs} | {str(ROOT / "PREREG2.md"), str(FU.SCALES), str(FU.SELECTION),
                                                      str(FE.METHOD_CFG), str(DRY_SITES if dry else PDBT_SITES)}
                    | ({str(DRY_PAIRS)} if dry else {str(GATE)}))
    common = dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=inputs, seed=args.seed, device="cpu",
                  start_time=T0)
    if not dry:
        common["extra"] = {"sealed_pairs": f"<in-memory: data/sealed/{PDBT_PAIRS}>"}
    write_result(out / "summary.parquet", summary, **common)
    write_result(out / "claims.json", claims_doc, **common)
    md = out / "report.md"
    md.write_text(render_md(summary, res, meta))
    prov = {"result": str(md), "result_sha256": sha256_file(md), **git_state(), "script": str(Path(__file__)),
            "script_sha256": sha256_file(__file__), "args": sys.argv[1:], "config": cfg,
            "evaluate_sha256": ev.module_sha256(), "derived_from": [str(out / "summary.parquet"),
                                                                    str(out / "claims.json")]}
    (out / "report.md.prov.json").write_text(json.dumps(prov, indent=2, default=str) + "\n")
    if dry:
        write_result(out / "reproduction_check.json", meta["reproduction"], **common)
        log(f"reproduction: {meta['reproduction']['n_rows_compared']} rows, max |dev| "
            f"{meta['reproduction']['max_abs_deviation']:.3g}, n_pairs mismatches "
            f"{meta['reproduction']['n_pairs_mismatch']}; L4 recheck {meta['reproduction'].get('l4_recheck')}")
    if res["claims"] is not None:
        log("claims: " + "; ".join(f"{c} Δ {r['delta']:+.4f} [{r['ci_low']:+.4f}, {r['ci_high']:+.4f}] "
                                   f"p {r['p_one_sided']:.4f} Holm {r['p_holm']:.4f}" for c, r in res["claims"].items()))
    else:
        log("DESCRIPTIVE mode: no claims (gate FAIL)")
    log(f"done -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
