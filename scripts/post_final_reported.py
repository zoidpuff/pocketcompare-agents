#!/usr/bin/env python
"""Post-hoc completion of three PRE-REGISTERED REPORTED (non-confirmatory) items that the final evaluation
(scripts/final_eval.py at freeze commit e5a6f357, run 2026-10-28 04:23) failed to deliver (RESEARCH_TREE DEV6).

    FINAL_EVAL=1 python scripts/post_final_reported.py c5      [--threads 24]   # item 1: paired holo − AF Δ (C5)
    FINAL_EVAL=1 python scripts/post_final_reported.py ppips   [--threads 8]    # item 3: PPIPS-test × BURROW flag
    FINAL_EVAL=1 python scripts/post_final_reported.py blind                    # item 2: blind test, BLiPS-test AF
    FINAL_EVAL=1 python scripts/post_final_reported.py afrob                    # item 1 (suppl.): eval_af_robustness
    FINAL_EVAL=1 python scripts/post_final_reported.py summary                  # tables from the files above
Outputs: results/final_post/ (provenance sidecars); sealed-file access log results/final_post/unseal_log.tsv.

Nothing here is tuned or selected: the frozen FINAL method (configs/final_method.yaml, A4b:n1_linear raw) and the
references of final_eval (N1 raw, L4:egnn_small [designated CSLS; raw also shown], B1, B4) are evaluated with the
frozen functions of scripts/final_eval.py, imported (not copied).  The frozen files (final_eval.py, evaluate.py,
configs/final_method.yaml, model weights) are hash-checked against FREEZE.json before anything is unsealed and are
not modified.  Sealed files are read through final_eval.Sealed (chmod 400 -> sha256 check against
data/sealed_SHA256SUMS.txt / data/splits/SHA256SUMS.txt -> read into memory -> chmod 000; one log row per access),
serialised across concurrent sub-commands with a file lock.  Sealed contents are never written to disk.

THE BUG (item 1) -- final_eval.stage_blips, C5 arm filter:
    for key in [k for k in Vh if k.split("|")[0] in ("FINAL", "B1", "B4") and k.split("|")[2] == "raw"
                and k.split("|")[1] in (method.name, "default", "esm2")]:
Vec keys are "<arm>|<config>|<variant>|<mode>", but the final method's config is its name
"pocketcompare-final:A4b:n1_linear|raw", which itself contains "|".  FINAL's keys are therefore
"FINAL|pocketcompare-final:A4b:n1_linear|raw|raw|L", so split("|")[1] == "pocketcompare-final:A4b:n1_linear"
!= method.name and FINAL was silently dropped (only B1 and B4 got paired C5 values).
THE FIX (local, here): select vectors by their Vec attributes (v.arm, v.config, v.variant, v.mode) instead of
parsing the key string.  Everything else of the C5 block (strata, D-mode common set, paired(), units, B, seed) is
the frozen code path; B1 / B4 are recomputed and compared with results/final/final_details.json (max deviation
reported) to show the path is identical.  N1 raw and L4 (csls = designated, raw) are added for reference, as the
pre-registered final_eval docstring lists "final (and B1, B4)" and Addendum A2 adds N1 / L4 as descriptive arms.

Item 2 (blind deployment test): scripts/eval_blind.py --set test, as designed, in-process (so the sealed pairs never
touch the disk): eval_af_robustness.adapter_blips_test is wrapped to return the unsealed pairs filtered exactly as
its own code does (pairs with both sites in the adapter's site list; label -> int).  Arms as designed: final, B1, B0.
B4 is not run (needs ESM-2 on every pool pocket; the script has no B4 arm; "if cheap" -> not cheap).
Item 1 supplement: scripts/eval_af_robustness.py --set test (same in-process wrapper, --max-neg 3000000 as its
report prescribes).  Its "delta" is holo/holo vs mixed holo/AF scores on its own L/D sets; the PREREG C5 number is
the final_eval one (holo/holo vs AF/AF on the final_eval pair sets) computed by the c5 sub-command.
Item 3 (PPIPS-test by BURROW-homology flag, data/splits/ppips_burrow_homology.parquet, flag burrow_rep_edge as
SPLITS.md prescribes; burrow_any_edge secondary): final_eval.stage_ppips is called on the query / sym-pair subsets.
Per-query values in stage_ppips depend only on the query and the fixed candidate / background pools (all test-split
pockets), so the subset calls return exactly the stratified values; the unstratified call is checked against
results/final/final_ppips.parquet.  P-ortho is stratified by the QUERY complex's flag (partner flag tabulated),
P-sym by the complex's flag.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/final_post"
LOCK = OUT / ".unseal.lock"
SENTINEL = "<in-memory: data/sealed/blips_test_pairs.parquet via post_final_reported.py>"
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


# ============================================================================================ guards / sealed
def check_frozen():
    """Refuse unless the frozen files equal FREEZE.json (they are imported, never modified)."""
    sys.path.insert(0, str(ROOT / "src"))
    from pocketcompare.provenance import sha256_file
    fr = json.loads((ROOT / "FREEZE.json").read_text())
    checks = {"scripts/final_eval.py": fr["final_eval_sha256"], "src/pocketcompare/evaluate.py": fr["evaluate_sha256"],
              fr["method_config"]: fr["method_config_sha256"], "PREREG.md": fr["prereg_sha256"], **fr["weights"]}
    bad = {p: (sha256_file(ROOT / p), h) for p, h in checks.items() if sha256_file(ROOT / p) != h}
    if bad:
        raise SystemExit(f"frozen file(s) differ from FREEZE.json: {bad}")
    log(f"frozen files match FREEZE.json ({len(checks)} files, commit {fr['commit']})")
    return {"freeze_commit": fr["commit"], "frozen_files_checked": checks}


@contextmanager
def _lock():
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def unseal(name, purpose):
    import final_eval as FE
    s = FE.Sealed(OUT / "unseal_log.tsv", enabled=True)
    with _lock():
        return s.read(name, "post-hoc pre-registered reported item (final_eval omission, DEV6): " + purpose)


def _common(args, cfg, inputs=(), start=None):
    return dict(script=__file__, args=sys.argv[1:], config=cfg, inputs=[str(p) for p in inputs], seed=args.seed,
                device="cpu", start_time=start or T0)


def _setup_fe(args):
    sys.path.insert(0, str(ROOT / "scripts"))
    os.environ["POCKETCOMPARE_THREADS"] = str(args.threads)
    import final_eval as FE
    return FE


# ============================================================================================ item 1: C5
def cmd_c5(args, frz):
    FE = _setup_fe(args)
    import numpy as np
    import pandas as pd
    from pocketcompare import evaluate as ev
    from pocketcompare.descstore import DescriptorStore
    from pocketcompare.provenance import write_result
    method, cfg_sha = FE.load_method(False)
    store = DescriptorStore(ROOT)
    # ---- identical to final_eval.run (real branch), BLiPS block
    rd = pd.read_parquet(ROOT / "data/processed/benchmarks/blips_holo_release_dates.parquet")
    bp = unseal("blips_test_pairs.parquet", "C5 paired holo-AF delta (FINAL, N1, L4; B1/B4 reproduction)")
    bs = unseal("blips_test_sites.parquet", "C5: BLiPS-test site groups / label clusters")
    exc = pd.read_parquet(ROOT / "data/splits/blips_test_exclusions_v2.parquet")
    trp = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
    seen = set(trp.pair_cluster[trp.label == 1])
    bp = bp.copy()
    bp["chemotype_seen"] = np.where(bp.label == 1, bp.pair_cluster.isin(seen), None)
    bl = FE.blips_set("blips_test", bp, bs, "blips_test_holo", "blips_test_holo",
                      exclusions=set(exc.site_id[exc.excluded]))
    af = FE.blips_set("blips_test", bp, bs, "blips_test_af", "blips_test_af",
                      exclusions=set(exc.site_id[exc.excluded]), allow_missing=True)
    afp = pd.read_parquet(ROOT / "data/processed/benchmarks/blips_test_af_pockets.parquet",
                          columns=["pocket_id", "site_plddt_mean"]).set_index("pocket_id").site_plddt_mean
    rdt = rd[rd.dataset == "blips_test_holo"].set_index("pocket_id").release_date
    # ---- identical to final_eval.stage_blips (vectors used by C5; B0 / B0' are not part of C5)
    ps = bl
    specs = [s for s in FE.BASE_SPECS if s[1] != "esm2_noz"]
    vecs = FE.final_vectors(ps, method, store) + FE.descriptor_vectors(ps, store, specs)
    avecs = FE.final_vectors(af, method, store, dataset=af.dataset) + FE.descriptor_vectors(af, store, specs,
                                                                                           dataset=af.dataset)
    Va, Vh = FE.V(avecs), FE.V(vecs)
    d = rdt.reindex(ps.pockets.pocket_id).to_numpy()
    post = d >= np.datetime64("2018-05-01")
    pa, pb = post[ps.ia], post[ps.ib]
    rel = np.where(pa & pb, "post", np.where(~pa & ~pb, "pre", "mixed"))
    pl = afp.reindex(ps.pockets.pocket_id).to_numpy(float)
    pmin = np.fmin(pl[ps.ia], pl[ps.ib])
    band = np.where(pmin >= 90, "ge90", np.where(pmin >= 70, "70_90", np.where(np.isfinite(pmin), "lt70", "na")))
    strata = {"all": np.ones(len(ps.y), bool),
              **{f"release_{k}": rel == k for k in ("post", "pre", "mixed")},
              **{f"plddt_{k}": band == k for k in ("ge90", "70_90", "lt70")}}
    # ---- THE FIX: select by Vec attributes, not by splitting the key on "|"
    wanted = {("FINAL", method.name, "raw"), ("N1", "N1", "raw"), ("L4", f"L4:{FE.L4_MODEL}", "csls"),
              ("L4", f"L4:{FE.L4_MODEL}", "raw"), ("B1", "default", "raw"), ("B4", "esm2", "raw")}
    c5, rows = {}, []
    for key, v in Vh.items():
        if (v.arm, v.config, v.variant) not in wanted or key not in Va:
            continue
        for sn, sm in strata.items():
            if not FE._ok_mask(ps.y.astype(bool), sm & np.isfinite(Vh[key].s) & np.isfinite(Va[key].s)):
                continue
            dm = ps.dset & af.dset if v.mode == "D" else None
            mask = sm if dm is None else (sm & dm)
            try:
                r = FE.paired(ps.y, Vh[key].s, Va[key].s, ps.pair_units, args, mask=mask)
            except ValueError as e:
                r = {"error": str(e)}
            c5[f"{key}#{sn}"] = r
            rows.append({"key": key, "arm": v.arm, "config": v.config, "variant": v.variant, "mode": v.mode,
                         "stratum": sn, **r})
            log(f"  C5 {key} {sn}: " + (f"Δ {r['delta']:+.4f} [{r['ci_low']:+.4f}, {r['ci_high']:+.4f}] "
                                         f"n {r['n_pairs']} pos {r['n_pos']}" if "delta" in r else str(r)))
    T = pd.DataFrame(rows)
    # ---- reproduction 1: B1 / B4 paired C5 entries vs results/final/final_details.json
    ref = json.loads((ROOT / "results/final/final_details.json").read_text())["blips_test"]["c5_holo_minus_af"]
    devs, n_cmp, missing = [], 0, []
    for k, rv in ref.items():
        mine = c5.get(k)
        if mine is None:
            missing.append(k)
            continue
        for f, x in rv.items():
            if isinstance(x, (int, float)) and not isinstance(x, bool) and isinstance(mine.get(f), (int, float)):
                n_cmp += 1
                if np.isfinite(x) or np.isfinite(mine[f]):
                    devs.append(abs(float(x) - float(mine[f])) if np.isfinite(x) and np.isfinite(mine[f]) else np.inf)
            elif x != mine.get(f):
                devs.append(np.inf)
    rep = {"c5_entries_in_final_details": len(ref), "entries_recomputed": len(ref) - len(missing),
           "missing": missing, "n_numeric_fields_compared": n_cmp,
           "max_abs_deviation": float(max(devs)) if devs else 0.0}
    # ---- reproduction 2: unpaired ROC-AUC (subset all) of every C5 vector vs results/final/final_summary.parquet
    S = pd.read_parquet(ROOT / "results/final/final_summary.parquet")
    S = S[S.subset == "all"]
    udev = []
    for setname, VV, P_ in (("blips_test", Vh, ps), ("blips_test_af", Va, af)):
        for key, v in VV.items():
            if (v.arm, v.config, v.variant) not in wanted:
                continue
            m = FE.eval_set(v, P_.dset)
            a = ev.binary_metrics(P_.y.astype(bool)[m], v.s[m])["auc"]
            r = S[(S.set == setname) & (S.key == key)]
            udev.append({"set": setname, "key": key, "auc": a, "auc_final_eval": float(r.auc.iloc[0]) if len(r)
                         else np.nan, "n_pairs": int(m.sum()), "n_pairs_final_eval": int(r.n_pairs.iloc[0])
                         if len(r) else -1})
    U = pd.DataFrame(udev)
    U["abs_dev"] = (U.auc - U.auc_final_eval).abs()
    rep["unpaired_auc_vs_final_summary"] = {"n_rows": int(len(U)), "max_abs_deviation": float(U.abs_dev.max()),
                                            "n_pairs_all_equal": bool((U.n_pairs == U.n_pairs_final_eval).all())}
    log(f"reproduction: B1/B4 C5 {rep['entries_recomputed']}/{len(ref)} entries, max |dev| "
        f"{rep['max_abs_deviation']:.3g}; unpaired AUC {len(U)} rows, max |dev| {U.abs_dev.max():.3g}")
    cfg = {"item": "C5 paired holo − AF ΔROC-AUC (PREREG §3; final_eval.stage_blips with the key-parsing fix)",
           "method": method.name, "method_config_sha256": cfg_sha, "B": args.B, "seed": args.seed,
           "arms": sorted("|".join(w) for w in wanted), **frz}
    inputs = sorted({str(p) for p in store.inputs})
    write_result(OUT / "c5_holo_minus_af.parquet", T, **_common(args, cfg, inputs))
    write_result(OUT / "c5_unpaired_auc_check.parquet", U, **_common(args, cfg, inputs))
    write_result(OUT / "c5_details.json", {"c5_holo_minus_af": c5, "reproduction": rep,
                                           "n_pairs_holo": int(len(ps.y)), "n_pos_holo": int(ps.y.sum())},
                 **_common(args, cfg, inputs))
    return 0


# ============================================================================================ item 3: PPIPS strata
def cmd_ppips(args, frz):
    FE = _setup_fe(args)
    import numpy as np
    import pandas as pd
    from pocketcompare.descstore import DescriptorStore
    from pocketcompare.provenance import write_result
    method, cfg_sha = FE.load_method(False)
    store = DescriptorStore(ROOT)
    q = unseal("ppips_test_queries.parquet", "PPIPS-test P-ortho stratified by BURROW-homology flag")
    s = unseal("ppips_sym_test_pairs.parquet", "PPIPS-test P-sym stratified by BURROW-homology flag")
    flag = pd.read_parquet(ROOT / "data/splits/ppips_burrow_homology.parquet").set_index("complex")
    full = FE.stage_ppips("test", q, s, method, store, args)
    ref = pd.read_parquet(ROOT / "results/final/final_ppips.parquet").set_index("key")
    num = [c for c in full.columns if c in ref.columns and pd.api.types.is_numeric_dtype(full[c])]
    f2 = full.set_index("key")
    dev = float(np.nanmax(np.abs(f2[num].to_numpy(float) - ref.loc[f2.index, num].to_numpy(float))))
    log(f"reproduction vs results/final/final_ppips.parquet: {len(f2)} rows, max |dev| {dev:.3g}")
    tabs = [full.assign(flag="all", stratum="all")]
    counts = {}
    for fl in ("burrow_rep_edge", "burrow_any_edge"):
        qf = q.query_complex.map(flag[fl]).to_numpy(bool)
        pf = q.partner_complex.map(flag[fl]).to_numpy(bool)
        sf = s.complex.map(flag[fl]).to_numpy(bool)
        counts[fl] = {"ortho_queries_query_flagged": int(qf.sum()), "ortho_queries_query_clean": int((~qf).sum()),
                      "ortho_queries_partner_flagged": int(pf.sum()),
                      "ortho_queries_both_clean": int((~qf & ~pf).sum()),
                      "sym_pairs_flagged": int(sf.sum()), "sym_pairs_clean": int((~sf).sum()),
                      "test_complexes_flagged": int(flag[flag.split == "test"][fl].sum()),
                      "test_complexes": int((flag.split == "test").sum())}
        for val, name in ((True, "edge"), (False, "no_edge")):
            t = FE.stage_ppips("test", q[qf == val], s[sf == val], method, store, args)
            tabs.append(t.assign(flag=fl, stratum=name))
        t = FE.stage_ppips("test", q[~qf & ~pf], s[~sf], method, store, args)   # stricter: query AND partner clean
        tabs.append(t.assign(flag=fl, stratum="no_edge_query_and_partner"))
    T = pd.concat(tabs, ignore_index=True)
    cfg = {"item": "PPIPS-test P-ortho / P-sym stratified by BURROW-homology flag (PREREG §3 via D15/SPLITS.md)",
           "method": method.name, "method_config_sha256": cfg_sha, "B": args.B, "seed": args.seed,
           "flags": "data/splits/ppips_burrow_homology.parquet (primary burrow_rep_edge; secondary burrow_any_edge)",
           "ortho_stratified_by": "query complex flag", "sym_stratified_by": "complex flag", **frz}
    inputs = sorted({str(p) for p in store.inputs} | {str(ROOT / "data/splits/ppips_burrow_homology.parquet")})
    write_result(OUT / "ppips_burrow_strata.parquet", T, **_common(args, cfg, inputs))
    write_result(OUT / "ppips_burrow_strata.json", {"reproduction_max_abs_deviation": dev,
                                                    "reproduction_rows": int(len(f2)), "counts": counts},
                 **_common(args, cfg, inputs))
    return 0


# ============================================================================================ items 2 / 1-suppl
def _patch_adapter(purpose):
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "src"))
    bp = unseal("blips_test_pairs.parquet", purpose)
    import eval_af_robustness as AR
    orig = AR.adapter_blips_test

    def adapter_blips_test(pairs_path):
        """In-memory replacement of the pairs_path read (same filter as the original adapter)."""
        assert pairs_path == SENTINEL
        sites, _ = orig(None)
        ok = set(sites.site_id)
        pairs = bp[bp.site_a.isin(ok) & bp.site_b.isin(ok)].copy()
        pairs["label"] = pairs["label"].astype(int)
        return sites, pairs

    AR.adapter_blips_test = adapter_blips_test
    return AR


def cmd_blind(args, frz):
    _patch_adapter("blind deployment test on BLiPS-test AF models (eval_blind.py --set test)")
    import eval_blind as EB
    out = OUT / "blind_test"
    argv = ["--set", "test", "--pairs", SENTINEL, "--B", str(args.B), "--workers", str(args.workers),
            "--seed", str(args.seed), "--out", str(out)]
    log(f"eval_blind.main({argv})")
    return EB.main(argv)


def cmd_afrob(args, frz):
    AR = _patch_adapter("C5 supplement: eval_af_robustness.py --set test (retrieval + HH/HA/AA, strata)")
    out = OUT / "af_robustness_test"
    argv = ["--set", "test", "--pairs", SENTINEL, "--B", str(args.B), "--workers", str(args.workers),
            "--seed", str(args.seed), "--max-neg", "3000000", "--out", str(out)]
    log(f"eval_af_robustness.main({argv})")
    return AR.main(argv)


def cmd_summary(args, frz):
    """Headline tables (read from the result files above; no sealed access) -> final_post_summary.{json,md}."""
    import pandas as pd
    from pocketcompare.provenance import write_result
    f = lambda x: f"{x:+.3f}" if pd.notna(x) else "—"     # noqa: E731
    g = lambda x: f"{x:.3f}" if pd.notna(x) else "—"      # noqa: E731
    md, js = ["# Post-hoc pre-registered reported items (final_eval omissions, DEV6)", ""], {}
    C = pd.read_parquet(OUT / "c5_holo_minus_af.parquet")
    C = C[[(a, v) in {("FINAL", "raw"), ("N1", "raw"), ("L4", "csls"), ("B1", "raw"), ("B4", "raw")}
           for a, v in zip(C.arm, C.variant)]]
    md += ["## 1. C5 paired holo − AF ΔROC-AUC, BLiPS-test (wider CI of hom / lig units, B = 2000)", "",
           "| arm | mode | stratum | pairs (pos) | holo | AF | Δ [95 % CI] |", "|---|---|---|---|---|---|---|"]
    for r in C.itertuples():
        md.append(f"| {r.arm} {r.variant} | {r.mode} | {r.stratum} | {r.n_pairs} ({r.n_pos}) | {g(r.auc_a)} | "
                  f"{g(r.auc_b)} | {f(r.delta)} [{f(r.ci_low)}, {f(r.ci_high)}] |")
    js["c5"] = C.drop(columns=[c for c in C.columns if c == "error"]).to_dict("records")
    rep = json.loads((OUT / "c5_details.json").read_text())["reproduction"]
    js["c5_reproduction"] = rep
    md += ["", f"B1/B4 reproduction vs final_details.json: {rep['entries_recomputed']}/"
           f"{rep['c5_entries_in_final_details']} entries, max |dev| = {rep['max_abs_deviation']:.3g}; unpaired AUCs "
           f"vs final_summary: max |dev| = {rep['unpaired_auc_vs_final_summary']['max_abs_deviation']:.3g}.", ""]
    bd = OUT / "blind_test/metrics.parquet"
    if bd.exists():
        B = pd.read_parquet(bd)
        md += ["## 2. Blind deployment test, BLiPS-test AF models (variant all)", "",
               "| set | arm | hit@1 | hit@10 | hit@100 | MRR | AUC [95 % CI] |", "|---|---|---|---|---|---|---|"]
        for cond in (True, False):
            for arm in ("final", "B1", "B0", "final-B1"):
                s = B[(B.variant == "all") & (B.conditional == cond) & (B.arm == arm)].set_index("metric")
                if len(s):
                    md.append(f"| {'both detected' if cond else 'unconditional'} (n={int(s.n_pairs.iloc[0])}) | "
                              f"{arm} | " + " | ".join(g(s.estimate[m]) for m in ("hit1", "hit10", "hit100", "mrr"))
                              + f" | {g(s.estimate['auc'])} [{g(s.ci_low['auc'])}, {g(s.ci_high['auc'])}] |")
        dr = B[B.variant == "detection"]
        md += ["", "Detection recall: " + "; ".join(f"{r.arm} {r.estimate:.3f} [{r.ci_low:.3f}, {r.ci_high:.3f}]"
                                                    for r in dr.itertuples()), ""]
        js["blind"] = B.to_dict("records")
    P = pd.read_parquet(OUT / "ppips_burrow_strata.parquet")
    P = P[pd.Series([(a, v) in {("FINAL", "raw"), ("N1", "raw"), ("L4", "csls"), ("B1", "raw"), ("B4", "raw")}
                     for a, v in zip(P.arm, P.variant)], index=P.index) & P.stratum.isin(["all", "edge", "no_edge"])]
    md += ["## 3. PPIPS-test by BURROW-homology flag (query complex for P-ortho; complex for P-sym)", "",
           "| flag | stratum | arm | P-ortho n (units) | top-1 | top-3 | MRR [95 % CI] | P-sym n | pct |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in P.itertuples():
        md.append(f"| {r.flag} | {r.stratum} | {r.arm} {r.variant} | {r.ortho_n_queries} ({r.ortho_n_units}) | "
                  f"{g(r.ortho_top1)} | {g(r.ortho_top3)} | {g(r.ortho_mrr)} [{g(r.ortho_mrr_lo)}, "
                  f"{g(r.ortho_mrr_hi)}] | {r.sym_n_queries} | {g(r.sym_all_pct)} |")
    js["ppips"] = P.to_dict("records")
    js["ppips_meta"] = json.loads((OUT / "ppips_burrow_strata.json").read_text())
    cfg = {"item": "summary of post-hoc pre-registered reported items", **frz}
    ins = [OUT / n for n in ("c5_holo_minus_af.parquet", "c5_details.json", "ppips_burrow_strata.parquet",
                             "ppips_burrow_strata.json", "blind_test/metrics.parquet") if (OUT / n).exists()]
    write_result(OUT / "final_post_summary.json", js, **_common(args, cfg, ins))
    from pocketcompare.provenance import git_state, sha256_file
    mdp = OUT / "final_post_summary.md"
    mdp.write_text("\n".join(md) + "\n")
    prov = {"result": str(mdp), "result_sha256": sha256_file(mdp), **git_state(), "script": str(Path(__file__)),
            "script_sha256": sha256_file(__file__), "args": sys.argv[1:], "config": cfg,
            "derived_from": [str(p) for p in ins]}
    (OUT / "final_post_summary.md.prov.json").write_text(json.dumps(prov, indent=2, default=str) + "\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("cmd", choices=["c5", "ppips", "blind", "afrob", "summary"])
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=24)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    # CPU budget: pin the main process's numba / BLAS pools before numpy / numba are imported (final_eval and the
    # eval_* modules are imported later as non-__main__ modules and would otherwise get one thread per core).
    nt = str(args.threads if args.cmd in ("c5", "ppips") else args.workers)
    for v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "POCKETCOMPARE_THREADS"):
        os.environ[v] = nt
    if os.environ.get("FINAL_EVAL") != "1":
        raise SystemExit("refusing: needs FINAL_EVAL=1 (sealed test data; pre-registered reported items only)")
    sys.path.insert(0, str(ROOT / "src"))
    from pocketcompare.seeds import SEEDS
    if args.seed != SEEDS[0] or args.B != 2000:
        raise SystemExit("B / seed are fixed to final_eval's (2000, SEEDS[0])")
    frz = check_frozen()
    return {"c5": cmd_c5, "ppips": cmd_ppips, "blind": cmd_blind, "afrob": cmd_afrob,
            "summary": cmd_summary}[args.cmd](args, frz) or 0


if __name__ == "__main__":
    sys.exit(main())
