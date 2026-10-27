#!/usr/bin/env python
"""Analysis of BURROW pockets on the AFDB dimer sample (tasks 2 and 3).

Inputs (from 02-04): sample.tsv, export/{dimers,monomers}_{pockets,points}.parquet, cli/*/ (verification),
cli/timing.tsv. All paths under data/processed/dimers/sample/.

Definitions (all thresholds are module constants, sensitivity reported in the summary):
* Lists. FULL = --min-score none (<= 50 NMS'd pockets). DEFAULT = v2 output floor = ranks 1-3 plus score >= 0.03
  (re-derived from FULL and checked against the CLI default output).
* Interface pocket. f_min = (lining residues on the minority chain) / (all lining residues).
  INTERFACE if f_min >= F_MIN (0.25), "touching" if 0 < f_min < F_MIN, single-chain if f_min == 0.
  Cross-check: share of pocket points with heavy atoms of BOTH chains within 6 A (the BURROW shell radius).
* Monomer comparison. Each chain is run alone (same coordinates). Coverage of dimer pocket p by monomer pocket q
  = fraction of p's points with a q point within R_COV (2.0 A). best_cov = max over q of both chains (FULL lists);
  union_cov = coverage by the union of all monomer FULL-list points.
  PPI-created: union_cov < 0.2. Pre-existing: best_cov >= 0.5 (in monomer FULL; also reported for DEFAULT).
  Control: single-chain pockets whose residues are all >= 12 A from the other chain must be recovered.
* Homodimer symmetry. S = lining residue set (chain, resnum); swap(S) exchanges chains A/B.
  On-axis: interface pocket with Jaccard(S, swap(S)) >= J_SYM. Symmetric partner of p: pocket q != p in the same
  dimer maximising Jaccard(swap(S_p), S_q); found if >= J_SYM (0.5). Geometric check: q's points are mapped
  onto p's frame by the Kabsch transform that superposes chain B onto chain A (and A onto B); coverage reported.

Writes data/processed/dimers/sample/analysis/{pockets.tsv, dimers.tsv, sym_pairs.tsv} and
       results/ppi/summary.txt (all numbers quoted in reports/ppi_dimers.md).
Usage: python scripts/ppi/05_analyze.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / "data/processed/dimers/sample"
RES = ROOT / "results/ppi"
F_MIN = 0.25
R_COV = 2.0
J_SYM = 0.5
SHELL = 6.0
FAR = 12.0
FLOOR, KEEP_MIN = 0.03, 3
N_PTS_MIN = 10   # "cavity" pockets: drops metal-candidate singletons (vol 0) and 1-point surface tiles
SCORE_BINS = [0, 0.1, 0.3, 1.0]
OUT_LINES: list[str] = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    OUT_LINES.append(s)


def parse_res(s: str) -> list[tuple[str, int]]:
    out = []
    for t in str(s).split():
        c, r = t.split(":")
        r = "".join(ch for ch in r if ch.isdigit() or ch == "-")
        out.append((c, int(r)))
    return out


def read_atoms(path: str):
    ch, rid, name, xyz = [], [], [], []
    with open(path) as fh:
        for line in fh:
            if line.startswith("ATOM") and line[76:78].strip() != "H":
                ch.append(line[21])
                rid.append(int(line[22:26]))
                name.append(line[12:16].strip())
                xyz.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
            elif line.startswith("ENDMDL"):
                break
    return np.array(ch), np.array(rid), np.array(name), np.array(xyz)


def kabsch(P, Q):
    """R, t such that R @ P_i + t ~ Q_i."""
    pc, qc = P.mean(0), Q.mean(0)
    H = (P - pc).T @ (Q - qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    R = Vt.T @ D @ U.T
    return R, qc - R @ pc


def q(x, ps=(0.25, 0.5, 0.75), nd=2):
    x = pd.Series(x).dropna()
    if not len(x):
        return "n/a"
    v = x.quantile(list(ps)).to_numpy()
    return f"{v[1]:.{nd}f} [{v[0]:.{nd}f}-{v[2]:.{nd}f}]"


def pct(x):
    x = pd.Series(x).dropna()
    return f"{100 * x.mean():.1f}% ({int(x.sum())}/{len(x)})" if len(x) else "n/a"


def main() -> None:
    sample = pd.read_csv(S / "sample.tsv", sep="\t")
    dp = pd.read_parquet(S / "export/dimers_pockets.parquet")
    dpts = pd.read_parquet(S / "export/dimers_points.parquet")
    mp = pd.read_parquet(S / "export/monomers_pockets.parquet")
    mpts = pd.read_parquet(S / "export/monomers_points.parquet")
    dp["default"] = (dp["rank"] <= KEEP_MIN) | (dp.score >= FLOOR)
    mp["default"] = (mp["rank"] <= KEEP_MIN) | (mp.score >= FLOOR)

    # ---------- verification against CLI output ----------
    nbad = 0
    for cfg, sub in [("dimer_default", dp[dp["default"]]), ("dimer_full", dp), ("mono_default", mp[mp["default"]]),
                     ("mono_full", mp)]:
        bad = 0
        g = dict(tuple(sub.groupby("sid")))
        for f in sorted((S / "cli" / cfg).glob("*.csv")):
            if f.name.endswith(".points.csv") or f.name == "timing.csv":
                continue
            c = pd.read_csv(f)
            e = g.get(f.stem)
            ne = 0 if e is None else len(e)
            norm = lambda v: [" ".join(sorted(str(x).split())) for x in v]  # noqa: E731  (CLI sorts numerically)
            if len(c) != ne or (ne and (norm(c.residues.fillna("")) != norm(e.residues) or
                                        not np.allclose(c.score.to_numpy(), e.score.to_numpy(), atol=1e-5))):
                bad += 1
        nbad += bad
        say(f"[verify] export vs CLI {cfg}: structures differing = {bad}")

    # ---------- timing ----------
    t = pd.read_csv(S / "cli/timing.tsv", sep="\t")
    for r in t.itertuples():
        say(f"[timing] CLI {r.config}: {r.n_inputs} inputs in {r.wall_s:.1f} s wall ({r.n_inputs / r.wall_s:.1f}/s, "
            f"{r.device}, {r.workers} workers; includes process start-up)")
    for cfg in ["dimer_default", "dimer_full", "mono_default", "dimer_default_gpu"]:
        rows_ = [ln.split(",")[:5] for ln in (S / "cli" / cfg / "timing.csv").read_text().splitlines()[1:]]
        tc = pd.DataFrame(rows_, columns=["stem", "status", "n_atoms", "n_pockets", "total_ms"]).astype(
            {"n_atoms": float, "total_ms": float})
        say(f"[timing] CLI {cfg} per structure (worker-internal, incl. parse): median {tc.total_ms.median():.0f} ms, "
            f"p95 {tc.total_ms.quantile(.95):.0f} ms; atoms median {tc.n_atoms.median():.0f}")
    for w in ["dimers", "monomers"]:
        tt = pd.read_csv(S / f"export/{w}_timing.tsv", sep="\t")
        say(f"[timing] reference export (1 thread/process) {w}: median {tt.sec.median():.2f} s, p95 {tt.sec.quantile(.95):.2f} s")

    # ---------- per-dimer structure info ----------
    meta = sample.set_index("modelEntityId")
    struct = {}
    for sid, r in meta.iterrows():
        ch, rid, name, xyz = read_atoms(r.path)
        a, b = ch == r.chain_A, ch == r.chain_B
        ta, tb = cKDTree(xyz[a]), cKDTree(xyz[b])
        # per-residue min distance to the other chain
        da, _ = tb.query(xyz[a])
        db, _ = ta.query(xyz[b])
        dist = pd.concat([pd.Series(da).groupby(rid[a]).min().rename(lambda k: (r.chain_A, k)),
                          pd.Series(db).groupby(rid[b]).min().rename(lambda k: (r.chain_B, k))])
        info = {"ta": ta, "tb": tb, "dist": dist.to_dict(), "A": r.chain_A, "B": r.chain_B}
        if r.type == "homo":
            ca = name == "CA"
            ca_a = dict(zip(rid[a & ca], xyz[a & ca]))
            ca_b = dict(zip(rid[b & ca], xyz[b & ca]))
            common = sorted(set(ca_a) & set(ca_b))
            P, Q = np.array([ca_a[k] for k in common]), np.array([ca_b[k] for k in common])
            R_ab, t_ab = kabsch(P, Q)      # maps chain A frame onto chain B
            R_ba, t_ba = kabsch(Q, P)
            rmsd = float(np.sqrt(((P @ R_ab.T + t_ab - Q) ** 2).sum(1).mean()))
            info.update(R_ab=R_ab, t_ab=t_ab, R_ba=R_ba, t_ba=t_ba, rmsd=rmsd)
        struct[sid] = info

    # ---------- classify dimer pockets ----------
    pts_by = {k: g for k, g in dpts.groupby(["sid", "rank"])}
    mpts_by = {k: g for k, g in mpts.groupby(["sid", "rank"])}
    mdef = set(map(tuple, mp.loc[mp["default"], ["sid", "rank"]].to_numpy()))
    rows = []
    for r in dp.itertuples():
        info = struct[r.sid]
        res = parse_res(r.residues)
        nA = sum(c == info["A"] for c, _ in res)
        nB = sum(c == info["B"] for c, _ in res)
        n = max(nA + nB, 1)
        P = pts_by[(r.sid, r.rank)][["x", "y", "z"]].to_numpy()
        both = (np.isfinite(info["ta"].query(P, distance_upper_bound=SHELL)[0]) &
                np.isfinite(info["tb"].query(P, distance_upper_bound=SHELL)[0])).mean()
        mind = min((info["dist"].get(x, np.inf) for x in res), default=np.inf)
        rows.append(dict(sid=r.sid, rank=r.rank, nA=nA, nB=nB, f_min=min(nA, nB) / n, f_pts_both=float(both),
                         min_dist_other=float(mind), n_lining=nA + nB))
    cls = pd.DataFrame(rows)
    dp = dp.merge(cls, on=["sid", "rank"])
    dp = dp.merge(sample[["modelEntityId", "organism", "type", "ipTM", "max_ipSAE"]].rename(
        columns={"modelEntityId": "sid"}), on="sid")
    dp["cls"] = np.where(dp.f_min >= F_MIN, "interface", np.where(dp.f_min > 0, "touching", "single"))

    # ---------- monomer coverage ----------
    mono_trees = {}
    mgroups = dict(tuple(mpts.groupby("sid")))
    for msid, g in mgroups.items():
        mono_trees[msid] = (cKDTree(g[["x", "y", "z"]].to_numpy()), g["rank"].to_numpy())
    best_cov, best_cov_def, union_cov, best_score, best_rank = [], [], [], [], []
    for r in dp.itertuples():
        info = struct[r.sid]
        P = pts_by[(r.sid, r.rank)][["x", "y", "z"]].to_numpy()
        bc, bcd, bs, br = 0.0, 0.0, np.nan, np.nan
        hit_any = np.zeros(len(P), bool)
        for c in (info["A"], info["B"]):
            msid = f"{r.sid}_{c}"
            if mono_trees.get(msid) is None:
                continue
            tree, ranks = mono_trees[msid]
            lists = tree.query_ball_point(P, R_COV)
            hits = defaultdict(set)
            for i, L in enumerate(lists):
                if L:
                    hit_any[i] = True
                    for rk in set(ranks[L]):
                        hits[rk].add(i)
            for rk, s in hits.items():
                cv = len(s) / len(P)
                if cv > bc:
                    bc, bs, br = cv, float(mp.loc[(mp.sid == msid) & (mp["rank"] == rk), "score"].iloc[0]), rk
                if (msid, rk) in mdef and cv > bcd:
                    bcd = cv
        best_cov.append(bc)
        best_cov_def.append(bcd)
        union_cov.append(hit_any.mean())
        best_score.append(bs)
        best_rank.append(br)
    dp["best_cov"], dp["best_cov_def"], dp["union_cov"] = best_cov, best_cov_def, union_cov
    dp["mono_best_score"], dp["mono_best_rank"] = best_score, best_rank
    dp["mono_status"] = np.where(dp.union_cov < 0.2, "created", np.where(dp.best_cov >= 0.5, "pre-existing", "partial"))

    # ---------- homodimer symmetry ----------
    sym_rows = []
    dp["J_self"] = np.nan
    dp["partner_rank"] = np.nan
    dp["partner_J"] = np.nan
    dp["geo_best_cov"] = np.nan    # p's points mapped onto the other protomer: best coverage by one other pocket
    dp["geo_union_cov"] = np.nan   # ... and by the union of all other FULL-list pockets
    dp = dp.set_index(["sid", "rank"]).sort_index()
    for sid, g in dp[dp.type == "homo"].groupby(level=0):
        info = struct[sid]
        A, B = info["A"], info["B"]
        allp = dpts[dpts.sid == sid]
        tree_all, ranks_all = cKDTree(allp[["x", "y", "z"]].to_numpy()), allp["rank"].to_numpy()
        for rk in g.index.get_level_values(1):
            P = pts_by[(sid, rk)][["x", "y", "z"]].to_numpy()
            R, t = (info["R_ab"], info["t_ab"]) if dp.loc[(sid, rk), "nA"] >= dp.loc[(sid, rk), "nB"] else (info["R_ba"], info["t_ba"])
            hits = defaultdict(set)
            anyhit = np.zeros(len(P), bool)
            for i, L in enumerate(tree_all.query_ball_point(P @ R.T + t, R_COV)):
                for rr in set(ranks_all[L]) - {rk}:
                    hits[rr].add(i)
                    anyhit[i] = True
            dp.loc[(sid, rk), "geo_best_cov"] = max((len(v) for v in hits.values()), default=0) / len(P)
            dp.loc[(sid, rk), "geo_union_cov"] = anyhit.mean()
        sets = {rk: set(parse_res(rs)) for (_, rk), rs in g.residues.items()}
        sw = {rk: {(B if c == A else A, n) for c, n in s} for rk, s in sets.items()}
        for rk in sets:
            u = sets[rk] | sw[rk]
            dp.loc[(sid, rk), "J_self"] = len(sets[rk] & sw[rk]) / len(u) if u else 0
            bestJ, bestq = 0.0, None
            for rq in sets:
                if rq == rk:
                    continue
                uu = sw[rk] | sets[rq]
                J = len(sw[rk] & sets[rq]) / len(uu) if uu else 0
                if J > bestJ:
                    bestJ, bestq = J, rq
            dp.loc[(sid, rk), "partner_J"] = bestJ
            dp.loc[(sid, rk), "partner_rank"] = bestq if bestq is not None else np.nan
        # geometric check for mutual pairs
        for rk in sets:
            rq = dp.loc[(sid, rk), "partner_rank"]
            if np.isnan(rq) or dp.loc[(sid, rk), "partner_J"] < J_SYM:
                continue
            rq = int(rq)
            if rk >= rq or dp.loc[(sid, rq), "partner_rank"] != rk:
                continue
            P = pts_by[(sid, rk)][["x", "y", "z"]].to_numpy()
            Qp = pts_by[(sid, rq)][["x", "y", "z"]].to_numpy()
            # p's dominant chain decides the mapping direction: map Q (on the other chain) onto p's chain
            pA = dp.loc[(sid, rk), "nA"] >= dp.loc[(sid, rk), "nB"]
            R, t = (info["R_ba"], info["t_ba"]) if pA else (info["R_ab"], info["t_ab"])
            Qm = Qp @ R.T + t
            covpq = (cKDTree(Qm).query(P, distance_upper_bound=R_COV)[0] < np.inf).mean()
            sym_rows.append(dict(sid=sid, organism=dp.loc[(sid, rk), "organism"], rank_p=rk, rank_q=rq,
                                 J=dp.loc[(sid, rk), "partner_J"], cls_p=dp.loc[(sid, rk), "cls"],
                                 cls_q=dp.loc[(sid, rq), "cls"], score_p=dp.loc[(sid, rk), "score"],
                                 score_q=dp.loc[(sid, rq), "score"], def_p=dp.loc[(sid, rk), "default"],
                                 def_q=dp.loc[(sid, rq), "default"], npts_p=dp.loc[(sid, rk), "n_points"],
                                 npts_q=dp.loc[(sid, rq), "n_points"], geo_cov=covpq, chain_rmsd=info["rmsd"]))
    dp = dp.reset_index()
    sym = pd.DataFrame(sym_rows)
    out = S / "analysis"
    out.mkdir(exist_ok=True)
    keep_cols = ["sid", "rank", "organism", "type", "ipTM", "max_ipSAE", "score", "default", "cls", "nA", "nB", "f_min",
                 "f_pts_both", "min_dist_other", "n_lining", "n_points", "volume_A3", "bur10_mean", "bur16_mean",
                 "burbb16_mean", "depth_mean", "escape", "psp_mean", "plddt_mean", "best_cov", "best_cov_def",
                 "union_cov", "mono_best_score", "mono_best_rank", "mono_status", "J_self", "partner_rank",
                 "partner_J", "geo_best_cov", "geo_union_cov", "residues"]
    dp[keep_cols].to_csv(out / "pockets.tsv", sep="\t", index=False)
    sym.to_csv(out / "sym_pairs.tsv", sep="\t", index=False)
    report(dp, sym, sample, struct, mp)
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "summary.txt").write_text("\n".join(OUT_LINES) + "\n")


def report(dp, sym, sample, struct, mp):
    D0 = dp[dp["default"]]
    say(f"\n== Pocket counts: dimers {dp.sid.nunique()}, pockets FULL {len(dp)}, DEFAULT {len(D0)}; "
        f"per dimer DEFAULT {q(D0.groupby('sid').size())}, FULL {q(dp.groupby('sid').size())}")
    mD = mp[mp["default"]]
    say(f"monomer pockets per chain DEFAULT {q(mD.groupby('sid').size())}, FULL {q(mp.groupby('sid').size())}")
    say(f"DEFAULT pockets with n_points < {N_PTS_MIN} (excluded below as non-cavity): {pct(D0.n_points < N_PTS_MIN)}; "
        f"of which metal-candidate singletons (volume 0): {int((D0.volume_A3 == 0).sum())}; 1-point surface tiles: "
        f"{int(((D0.n_points == 1) & (D0.volume_A3 > 0)).sum())}")
    say(f"FULL pockets with n_points < {N_PTS_MIN}: {pct(dp.n_points < N_PTS_MIN)}")
    dp = dp[dp.n_points >= N_PTS_MIN]
    D = dp[dp["default"]]
    say(f"cavity pockets (n_points >= {N_PTS_MIN}) per dimer: DEFAULT {q(D.groupby('sid').size())}, FULL {q(dp.groupby('sid').size())}")

    say("\n== f_min distribution (DEFAULT pockets): share with f_min = 0: "
        f"{(D.f_min == 0).mean():.3f}; (0,0.1): {((D.f_min > 0) & (D.f_min < .1)).mean():.3f}; [0.1,0.25): "
        f"{((D.f_min >= .1) & (D.f_min < .25)).mean():.3f}; [0.25,0.4): {((D.f_min >= .25) & (D.f_min < .4)).mean():.3f}; "
        f">=0.4: {(D.f_min >= .4).mean():.3f}")
    hist = np.histogram(D.f_min[D.f_min > 0], bins=np.arange(0, 0.55, 0.05))[0]
    say(f"f_min histogram (f_min>0, bins of 0.05 from 0 to 0.5): {hist.tolist()}")
    for c in ["single", "touching", "interface"]:
        say(f"  f_pts_both (share of points with both chains <= 6 A) for {c:9s}: {q(D.f_pts_both[D.cls == c])}")

    say("\n== Fraction of dimers with >=1 interface pocket (f_min >= T)")
    for T in [0.10, 0.25, 0.40]:
        for lst, X in [("DEFAULT", D), ("FULL", dp), ("top-3", dp[dp["rank"] <= 3]), ("top-1", dp[dp["rank"] == 1])]:
            has = X.assign(i=X.f_min >= T).groupby("sid").i.any().reindex(sample.modelEntityId, fill_value=False)
            ty = sample.set_index("modelEntityId").type.reindex(has.index)
            say(f"  T={T:.2f} {lst:7s}: all {pct(has)} | homo {pct(has[ty == 'homo'])} | hetero {pct(has[ty == 'hetero'])}")
    has = D.assign(i=D.cls == "interface").groupby("sid").i.any().reindex(sample.modelEntityId, fill_value=False)
    sm = sample.set_index("modelEntityId")
    for (o, t), g in sm.groupby(["organism", "type"]):
        say(f"  DEFAULT T=0.25 {o:6s} {t:6s}: {pct(has[g.index])}; interface pockets/dimer {D[D.cls == 'interface'].groupby('sid').size().reindex(g.index, fill_value=0).mean():.2f}")
    ipt = pd.qcut(sm.ipTM, 3, labels=["low", "mid", "high"])
    for lev in ["low", "mid", "high"]:
        idx = ipt.index[ipt == lev]
        say(f"  ipTM tertile {lev} ({sm.ipTM[idx].min():.2f}-{sm.ipTM[idx].max():.2f}): {pct(has[idx])}")
    say(f"  share of DEFAULT pockets that are interface: {pct(D.cls == 'interface')}; touching {pct(D.cls == 'touching')}")
    best_if = D[D.cls == "interface"].groupby("sid")["rank"].min()
    say(f"  rank of best interface pocket (dimers having one): rank1 {pct(best_if == 1)}, <=3 {pct(best_if <= 3)}")

    say("\n== Interface vs single-chain pockets (DEFAULT list): median [IQR]")
    cols = ["score", "volume_A3", "n_lining", "bur10_mean", "bur16_mean", "burbb16_mean", "depth_mean", "escape",
            "psp_mean", "plddt_mean"]
    for c in cols:
        say(f"  {c:13s} interface {q(D.loc[D.cls == 'interface', c])} | single {q(D.loc[D.cls == 'single', c])} | "
            f"touching {q(D.loc[D.cls == 'touching', c])}")
    for thr in [0.1, 0.3, 0.5]:
        say(f"  score >= {thr}: interface {pct(D.loc[D.cls == 'interface', 'score'] >= thr)} | single {pct(D.loc[D.cls == 'single', 'score'] >= thr)}")
    for t_ in ["homo", "hetero"]:
        X = D[D.type == t_]
        say(f"  {t_}: score interface {q(X.score[X.cls == 'interface'])} vs single {q(X.score[X.cls == 'single'])}; "
            f"bur16 interface {q(X.bur16_mean[X.cls == 'interface'])} vs single {q(X.bur16_mean[X.cls == 'single'])}")

    say("\n== Monomer comparison (dimer pocket covered by monomer pockets; points within 2 A)")
    ctrl = D[(D.cls == "single") & (D.min_dist_other >= FAR)]
    say(f"  CONTROL single-chain pockets >= {FAR:.0f} A from partner (n={len(ctrl)}): best_cov (monomer FULL) "
        f"{q(ctrl.best_cov)}; recovered (best_cov>=0.5) {pct(ctrl.best_cov >= 0.5)}; in monomer DEFAULT "
        f"{pct(ctrl.best_cov_def >= 0.5)}; union_cov<0.2 {pct(ctrl.union_cov < 0.2)}")
    for name, X in [("interface DEFAULT", D[D.cls == "interface"]), ("touching DEFAULT", D[D.cls == "touching"]),
                    ("single near-interface (<12 A) DEFAULT", D[(D.cls == "single") & (D.min_dist_other < FAR)]),
                    ("interface FULL", dp[dp.cls == "interface"])]:
        say(f"  {name} (n={len(X)}): created(union_cov<0.2) {pct(X.mono_status == 'created')}; partial "
            f"{pct(X.mono_status == 'partial')}; pre-existing(best_cov>=0.5, mono FULL) {pct(X.mono_status == 'pre-existing')}; "
            f"absent from monomer DEFAULT (best_cov_def<0.5) {pct(X.best_cov_def < 0.5)}; union_cov {q(X.union_cov)}")
    say("  score-stratified (DEFAULT cavity pockets): created = union_cov<0.2, recovered = best_cov>=0.5")
    for lo, hi in zip(SCORE_BINS[:-1], SCORE_BINS[1:]):
        c_ = ctrl[(ctrl.score > lo) & (ctrl.score <= hi)]
        i_ = D[(D.cls == "interface") & (D.score > lo) & (D.score <= hi)]
        say(f"   score ({lo},{hi}]: CONTROL n={len(c_)} recovered {pct(c_.best_cov >= 0.5)} created {pct(c_.union_cov < 0.2)} | "
            f"INTERFACE n={len(i_)} recovered {pct(i_.best_cov >= 0.5)} created {pct(i_.union_cov < 0.2)}")
    I = D[D.cls == "interface"]
    for t_ in ["homo", "hetero"]:
        X = I[I.type == t_]
        say(f"  interface DEFAULT {t_} (n={len(X)}): created {pct(X.mono_status == 'created')}; absent from monomer DEFAULT {pct(X.best_cov_def < 0.5)}")
    pre = I[I.mono_status == "pre-existing"]
    say(f"  pre-existing interface pockets: dimer score {q(pre.score)} vs best monomer pocket score {q(pre.mono_best_score)}")
    for st in ["created", "partial", "pre-existing"]:
        X = I[I.mono_status == st]
        say(f"  interface {st:12s}: score {q(X.score)}, vol {q(X.volume_A3, nd=0)}, bur16 {q(X.bur16_mean)}, f_min {q(X.f_min)}")
    hasc = I[I.mono_status == "created"].groupby("sid").size().reindex(sample.modelEntityId, fill_value=0)
    say(f"  dimers with >=1 PPI-created interface pocket in DEFAULT list: {pct(hasc > 0)}")

    say("\n== Homodimer symmetry (same residue numbers on A and B)")
    H = dp[dp.type == "homo"]
    HD = H[H["default"]]
    rm = pd.Series({k: v["rmsd"] for k, v in struct.items() if "rmsd" in v})
    say(f"  chain A vs B CA RMSD after superposition: {q(rm)}; >2 A: {pct(rm > 2)}")
    for T in [0.3, 0.5, 0.7]:
        X = HD[HD.cls == "interface"]
        say(f"  on-axis (interface, J_self>={T}): {pct(X.J_self >= T)} of {len(X)} interface DEFAULT pockets")
    onax = HD[(HD.cls == "interface") & (HD.J_self >= J_SYM)]
    offax = HD[~((HD.cls == "interface") & (HD.J_self >= J_SYM))].copy()
    full_ranks = {(s, r): d for s, r, d in H[["sid", "rank", "default"]].itertuples(index=False)}
    offax["partner_in_full"] = offax.partner_J >= J_SYM
    offax["partner_in_def"] = [pj >= J_SYM and full_ranks.get((s, int(pr)) if pr == pr else None, False)
                               for s, pj, pr in offax[["sid", "partner_J", "partner_rank"]].itertuples(index=False)]
    say(f"  DEFAULT homodimer pockets {len(HD)}: on-axis interface {len(onax)}; off-axis {len(offax)}")
    for c in ["interface", "touching", "single"]:
        X = offax[offax.cls == c]
        say(f"   off-axis {c:9s} (n={len(X)}): symmetric copy in DEFAULT {pct(X.partner_in_def)}; in FULL {pct(X.partner_in_full)}; "
            f"partner J {q(X.partner_J)}")
    for lo, hi in zip(SCORE_BINS[:-1], SCORE_BINS[1:]):
        X = offax[(offax.score > lo) & (offax.score <= hi)]
        say(f"   off-axis score ({lo},{hi}] (n={len(X)}): copy in DEFAULT {pct(X.partner_in_def)}; FULL {pct(X.partner_in_full)}; "
            f"interface-only: FULL {pct(X[X.cls == 'interface'].partner_in_full)}")
    say(f"   geometric copy check (p's points mapped by the A<->B superposition; other FULL pockets): best single-pocket "
        f"coverage >= 0.5 {pct(offax.geo_best_cov >= 0.5)}; union coverage >= 0.5 {pct(offax.geo_union_cov >= 0.5)}; "
        f"union < 0.2 (copy site not a pocket at all) {pct(offax.geo_union_cov < 0.2)}")
    for c in ["interface", "single"]:
        X = offax[offax.cls == c]
        say(f"    {c}: geo best >= 0.5 {pct(X.geo_best_cov >= 0.5)}; geo union >= 0.5 {pct(X.geo_union_cov >= 0.5)}")
    X = offax
    say(f"   all off-axis: copy in DEFAULT {pct(X.partner_in_def)}; FULL {pct(X.partner_in_full)}; "
        f"with J>=0.3 in FULL {pct(X.partner_J >= 0.3)}")
    say(f"   top-3 off-axis pockets: copy in FULL {pct(X[X['rank'] <= 3].partner_in_full)}")
    sym = sym[(sym.npts_p >= N_PTS_MIN) & (sym.npts_q >= N_PTS_MIN)] if len(sym) else sym
    if len(sym):
        both_def = sym[sym.def_p & sym.def_q]
        say(f"  mutual symmetric pairs (J>=0.5, FULL lists): {len(sym)} in {sym.sid.nunique()} of {H.sid.nunique()} homodimers; "
            f"both in DEFAULT: {len(both_def)}")
        for c in ["interface", "touching", "single"]:
            Y = both_def[(both_def.cls_p == c) | (both_def.cls_q == c)]
            say(f"   DEFAULT pairs involving {c}: {len(Y)} ({Y.sid.nunique()} dimers)")
        say(f"   pair |score diff| {q((both_def.score_p - both_def.score_q).abs(), nd=3)}; geometric coverage after "
            f"superposition {q(both_def.geo_cov)}; J {q(both_def.J)}")
        rmd = sym.groupby("sid").chain_rmsd.first()
        say(f"   pairs per homodimer (DEFAULT both): {q(both_def.groupby('sid').size().reindex(H.sid.unique(), fill_value=0))}")
        # missed copies vs RMSD
        miss = offax.groupby("sid").partner_in_full.mean()
        say(f"   share of off-axis pockets with a copy, by chain RMSD: <=1 A {q(miss[rm.reindex(miss.index) <= 1])}; "
            f">1 A {q(miss[rm.reindex(miss.index) > 1])} (n={int((rm.reindex(miss.index) > 1).sum())} dimers)")
        # extrapolation
        allm = pd.read_csv(ROOT / "data/processed/dimers/manifest.tsv", sep="\t")
        nh = allm[allm.type == "homo"].groupby("organism").size()
        per = both_def.groupby("organism").size() / H.groupby("organism").sid.nunique()
        per_if = both_def[(both_def.cls_p == "interface") | (both_def.cls_q == "interface")].groupby("organism").size() / H.groupby("organism").sid.nunique()
        tot = (per * nh).sum()
        tot_if = (per_if.reindex(nh.index, fill_value=0) * nh).sum()
        say(f"   extrapolated symmetric DEFAULT pairs over all {nh.sum()} homodimers: {tot:.0f} (interface-involving {tot_if:.0f}); "
            f"per dimer by organism {per.round(2).to_dict()}; on-axis interface pockets/homodimer {len(onax) / H.sid.nunique():.2f}")


if __name__ == "__main__":
    main()
