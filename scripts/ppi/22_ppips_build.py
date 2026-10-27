#!/usr/bin/env python
"""PPIPS step 3: pocket table, P-sym pairs, P-ortho retrieval queries, homology-group splits (DESIGN §2.5).

Pockets  : BURROW --output-rule region pockets of each featurised dimer (20_), touching sub-pockets merged
           (pockets.merge_pockets(fs, 'region')); merged pockets with < MIN_POINTS points are dropped
           (metal-candidate singletons / one-point surface tiles; reports/ppi_dimers.md §2).
           f_min = share of BURROW output residues on the minority chain; interface if f_min >= 0.25.
P-sym    : homodimers.  Pocket S (not on the 2-fold axis: J(S, swap(S)) < 0.5) and pocket T with
           J(swap(S), T) >= 0.5, mutual best -> one unordered pair.  Metric (PI round 2): rank/percentile of the
           copy among the query's scores against all other pockets of its split.
P-ortho  : cross-species interolog complex pairs with pair identity < 0.30 (06_ interologs.tsv).  Chains are
           matched by the alignment orientation (homodimers: both orientations tried, best kept), residues
           are mapped through the MMseqs2 chain alignments (21_).  Query = interface pocket of complex X whose
           residues are >= 50 % mapped; counterpart(s) = pockets T of the partner complex X' with
           J_aligned(map(S), T) >= 0.5, where J is computed over T's alignable residues only.
           Candidates = all pockets of X'.  Both directions are queries.  Queries without a counterpart are kept
           in a diagnostics table, not as queries.
Splits   : complex graph = complexes sharing a protein homology group (21_) + every interolog pair used;
           connected components.  Largest component -> train; components containing a BURROW train/dev
           protein (UniProt in pocket_detect split_chains.tsv, split in train/dev) -> train; the rest
           60/20/20 (seed SEEDS[0]) by complex count.
Outputs  : data/processed/ppi/ppips/{pockets,sym_pairs_all,ortho_queries_all,ortho_diag}.parquet (large),
           data/splits/ppips_complex_splits.parquet, data/splits/ppips_{sym_pairs,ortho_queries}_{train,val}.parquet,
           data/sealed/ppips_test_queries.parquet + data/sealed/ppips_sym_test_pairs.parquet (chmod 000),
           results/ppi/ppips_counts.json (counts only).
Usage: python scripts/ppi/22_ppips_build.py --workers 16
"""
from __future__ import annotations

import os

for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
from collections import defaultdict  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/processed/cache/points/ppips"
OUT = ROOT / "data/processed/ppi/ppips"
SPL = ROOT / "data/splits"
SEALED = ROOT / "data/sealed"
BURROW_SPLIT = Path("/cluster/project/beltrao/gmagnus/pocket_detect/data/processed/train/split_chains.tsv")
MIN_POINTS = 10
IFACE_FMIN = 0.25
J_SYM = 0.5
J_ORTHO = 0.5
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


def jac(a, b) -> float:
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def aln_map(row) -> dict:
    """query residue number -> target residue number from MMseqs2 qaln/taln (1-based starts)."""
    m, qi, ti = {}, int(row.qstart), int(row.tstart)
    for a, b in zip(row.qaln, row.taln):
        if a != "-" and b != "-":
            m[qi] = ti
        if a != "-":
            qi += 1
        if b != "-":
            ti += 1
    return m


def write_sealed(frames: dict) -> None:
    """data/sealed is kept r-x by the PI: open it for writing only for the duration of the write; files 000."""
    import hashlib
    SEALED.mkdir(exist_ok=True)
    mode = SEALED.stat().st_mode & 0o7777
    os.chmod(SEALED, mode | 0o700)
    try:
        for name, df in frames.items():
            f = SEALED / name
            if f.exists():
                os.chmod(f, 0o600)
            df.to_parquet(f, index=False)
            print(f"[sealed] {name} sha256 {hashlib.sha256(f.read_bytes()).hexdigest()} rows {len(df)}", flush=True)
            os.chmod(f, 0o000)
    finally:
        os.chmod(SEALED, mode)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    from pocketcompare.seeds import SEEDS
    OUT.mkdir(parents=True, exist_ok=True)
    SPL.mkdir(parents=True, exist_ok=True)
    cx = pd.read_parquet(CACHE / "complexes.parquet")
    tm = pd.read_parquet(CACHE / "timing.parquet")
    ok = set(tm.key[tm.status == "ok"])
    cx = cx[cx.modelEntityId.isin(ok)].reset_index(drop=True)

    # ---------------------------------------------------------------- pockets
    pf = OUT / "pockets.parquet"
    if pf.exists():
        P = pd.read_parquet(pf)
    else:
        with ProcessPoolExecutor(a.workers, mp_context=get_context("spawn")) as ex:
            rows = [r for rs in ex.map(pocket_rows, cx.modelEntityId.tolist(), chunksize=8) for r in rs]
        P = pd.DataFrame(rows)
        P.to_parquet(pf, index=False)
    P["rs"] = P.residues.map(rset)
    by_cx = {k: g for k, g in P.groupby("complex")}
    ctype = dict(zip(cx.modelEntityId, cx.type))
    print(f"[ppips] pockets {len(P)} in {P.complex.nunique()} complexes; interface {int(P.is_interface.sum())}",
          flush=True)

    # ---------------------------------------------------------------- P-sym
    swap = lambda s: frozenset(("B" if r[0] == "A" else "A") + r[1:] for r in s)  # noqa: E731
    sym = []
    on_axis = 0
    for key, g in by_cx.items():
        if ctype[key] != "homo":
            continue
        ids, sets = g.pocket_id.tolist(), g.rs.tolist()
        best = {}
        for i, s in enumerate(sets):
            ss = swap(s)
            if jac(s, ss) >= J_SYM:
                on_axis += 1
                best[i] = None
                continue
            js = [(jac(ss, t), j) for j, t in enumerate(sets) if j != i]
            jb, jj = max(js) if js else (0.0, None)
            best[i] = (jj, jb) if jb >= J_SYM else None
        for i, b in best.items():
            if b and best.get(b[0]) and best[b[0]][0] == i and i < b[0]:
                sym.append({"complex": key, "pocket_a": ids[i], "pocket_b": ids[b[0]], "jaccard_swap": b[1],
                            "interface": bool(g.is_interface.iloc[i] or g.is_interface.iloc[b[0]])})
    S = pd.DataFrame(sym)
    print(f"[ppips] P-sym pairs {len(S)} ({int(S.interface.sum())} interface); on-axis pockets {on_axis}", flush=True)

    # ---------------------------------------------------------------- P-ortho
    il = pd.read_csv(ROOT / "data/processed/dimers/orthology/interologs.tsv", sep="\t")
    il = il[(il.org1 != il.org2) & (il.pair_ident < MAX_IDENT) & il.cx1.isin(ok) & il.cx2.isin(ok)]
    cols = ["query", "target", "fident", "alnlen", "qlen", "tlen", "qcov", "tcov", "evalue", "bits",
            "qstart", "qend", "tstart", "tend", "qaln", "taln"]
    H = pd.read_csv(OUT / "mmseqs_aln.tsv", sep="\t", names=cols)
    H = H.sort_values("bits", ascending=False).drop_duplicates(["query", "target"])
    hits = {(r.query, r.target): r for r in H.itertuples()}
    cache_map = {}

    def resmap(p, q):
        if (p, q) not in cache_map:
            if p == q:
                cache_map[(p, q)] = None          # identity
            else:
                r = hits.get((p, q))
                cache_map[(p, q)] = aln_map(r) if r is not None else {}
        return cache_map[(p, q)]

    acc = {r.modelEntityId: (r.uniprotAccession_1, r.uniprotAccession_2) for r in cx.itertuples()}

    def map_set(s, chain_map):
        """chain_map: {'A': ('B', p, q), ...} -> mapped residue set + n mapped."""
        out = set()
        n = 0
        for r in s:
            ch, num = r.split(":")
            tgt_ch, p, q = chain_map[ch]
            m = resmap(p, q)
            t = int(num) if m is None else m.get(int(num))
            if t is not None:
                out.add(f"{tgt_ch}:{t}")
                n += 1
        return frozenset(out), n

    queries, diag = [], []
    for r in il.itertuples():
        for X, Y in ((r.cx1, r.cx2), (r.cx2, r.cx1)):
            (p1, p2), (q1, q2) = acc[X], acc[Y]
            orients = [{"A": ("A", p1, q1), "B": ("B", p2, q2)}, {"A": ("B", p1, q2), "B": ("A", p2, q1)}]
            orients = [o for o in orients if all((o[c][1] == o[c][2]) or (o[c][1], o[c][2]) in hits for c in "AB")]
            if not orients:
                continue
            gx, gy = by_cx.get(X), by_cx.get(Y)
            if gx is None or gy is None:
                continue
            # reverse maps to know which residues of each target pocket are alignable
            for qi in gx[gx.is_interface].itertuples():
                best = None
                for oi, o in enumerate(orients):
                    ms, n = map_set(qi.rs, o)
                    frac = n / max(len(qi.rs), 1)
                    inv = {o[c][0]: (c, o[c][2], o[c][1]) for c in "AB"}   # target chain -> back to query
                    js, ocs = [], []
                    for t in gy.itertuples():
                        _, nt = map_set(t.rs, inv)
                        # alignable part of T: residues of T that map back
                        t_al = frozenset(x for x in t.rs if map_set(frozenset([x]), inv)[1] == 1)
                        js.append(jac(ms, t_al) if t_al else 0.0)
                        ocs.append(len(ms & t_al) / min(len(ms), len(t_al)) if (t_al and ms) else 0.0)
                    js = np.asarray(js)
                    cand = (frac, js, oi, np.asarray(ocs))
                    if best is None or (js.max() if len(js) else 0) > (best[1].max() if len(best[1]) else 0):
                        best = cand
                frac, js, oi, ocs = best
                pos = gy.pocket_id.values[js >= J_ORTHO].tolist()
                pos_oc = gy.pocket_id.values[ocs >= J_ORTHO].tolist()   # diagnostic: overlap coefficient >= 0.5
                rec = {"query": qi.pocket_id, "query_complex": X, "partner_complex": Y, "type": r.type,
                       "org_query": r.org1 if X == r.cx1 else r.org2, "org_partner": r.org2 if X == r.cx1 else r.org1,
                       "pair_ident": r.pair_ident, "frac_mapped": frac, "orientation": oi,
                       "n_candidates": len(gy), "best_j": float(js.max()) if len(js) else 0.0,
                       "positives": pos, "n_positives": len(pos), "positives_overlap": pos_oc,
                       "n_positives_overlap": len(pos_oc)}
                diag.append(rec)
                if frac >= MIN_MAPPED and pos:
                    queries.append(rec)
    D = pd.DataFrame(diag)
    Q = pd.DataFrame(queries)
    dm = D[D.frac_mapped >= MIN_MAPPED]
    print(f"[ppips] diag: frac_mapped>=0.5: {len(dm)}; best_j quantiles "
          f"{dm.best_j.quantile([.1, .25, .5, .75, .9]).round(2).tolist()}; best_j>=0.3: {(dm.best_j >= 0.3).sum()}",
          flush=True)
    print(f"[ppips] P-ortho: interface queries considered {len(D)}, with counterpart {len(Q)} "
          f"(complex pairs {Q[['query_complex', 'partner_complex']].drop_duplicates().shape[0]})", flush=True)

    # ---------------------------------------------------------------- splits
    pg = pd.read_parquet(OUT / "protein_groups.parquet")
    pgroup = dict(zip(pg.accession, pg.protein_group))
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)
    for c, (p1, p2) in acc.items():
        union("cx:" + c, "pg:" + pgroup[p1])
        union("cx:" + c, "pg:" + pgroup[p2])
    for r in il.itertuples():
        union("cx:" + r.cx1, "cx:" + r.cx2)
    C = pd.DataFrame({"complex": sorted(acc)})
    C["group"] = C.complex.map(lambda c: find("cx:" + c))
    C["organism"] = C.complex.map(dict(zip(cx.modelEntityId, cx.organism)))
    C["type"] = C.complex.map(ctype)
    bs = pd.read_csv(BURROW_SPLIT, sep="\t", usecols=["uniprot_all", "split"])
    btrain = set()
    for u in bs.loc[bs.split.isin(["train", "dev"]), "uniprot_all"].dropna():
        btrain.update(str(u).replace(";", ",").split(","))
    C["burrow_train_protein"] = C.complex.map(lambda c: any(p in btrain or p.split("-")[0] in btrain for p in acc[c]))
    gsize = C.group.value_counts()
    giant = gsize.index[0]
    forced = set(C.group[C.burrow_train_protein]) | {giant}
    C["split"] = None
    C.loc[C.group.isin(forced), "split"] = "train"
    rest = [g for g in gsize.index if g not in forced]
    rng = np.random.default_rng(SEEDS[0])
    rest = [rest[i] for i in rng.permutation(len(rest))]
    n_rest = int(gsize[rest].sum())
    tgt = {"train": 0.6 * n_rest, "val": 0.2 * n_rest, "test": 0.2 * n_rest}
    cnt = {"train": 0, "val": 0, "test": 0}
    gsplit = {}
    for g in rest:     # greedy: put each group where the remaining deficit (relative) is largest
        s = max(tgt, key=lambda k: (tgt[k] - cnt[k]) / tgt[k])
        gsplit[g] = s
        cnt[s] += gsize[g]
    C.loc[C.split.isna(), "split"] = C.group.map(gsplit)
    C["giant"] = C.group == giant
    C.to_parquet(SPL / "ppips_complex_splits.parquet", index=False)
    split_of = dict(zip(C.complex, C.split))

    P["split"] = P.complex.map(split_of)
    P.drop(columns=["rs"]).to_parquet(pf, index=False)
    S["split"] = S.complex.map(split_of)
    Q["split"] = Q.query_complex.map(split_of)
    assert (Q.query_complex.map(split_of) == Q.partner_complex.map(split_of)).all()
    D.to_parquet(OUT / "ortho_diag.parquet", index=False)
    S.to_parquet(OUT / "sym_pairs_all.parquet", index=False)      # git-ignored working copy (pre-seal)
    Q.to_parquet(OUT / "ortho_queries_all.parquet", index=False)
    for s in ("train", "val"):
        S[S.split == s].to_parquet(SPL / f"ppips_sym_pairs_{s}.parquet", index=False)
        Q[Q.split == s].to_parquet(SPL / f"ppips_ortho_queries_{s}.parquet", index=False)
    write_sealed({"ppips_test_queries.parquet": Q[Q.split == "test"],
                  "ppips_sym_test_pairs.parquet": S[S.split == "test"]})
    # the unsealed working copies would leak the test labels -> remove test rows from them
    S[S.split != "test"].to_parquet(OUT / "sym_pairs_all.parquet", index=False)
    Q[Q.split != "test"].to_parquet(OUT / "ortho_queries_all.parquet", index=False)
    D[D.query_complex.map(split_of) != "test"].to_parquet(OUT / "ortho_diag.parquet", index=False)

    cnts = {
        "complexes": C.split.value_counts().to_dict(),
        "complex_groups": C.groupby("split").group.nunique().to_dict(),
        "giant_group_complexes": int(gsize.iloc[0]), "n_groups": int(len(gsize)),
        "burrow_train_complexes": int(C.burrow_train_protein.sum()),
        "pockets": P.split.value_counts().to_dict(),
        "interface_pockets": P[P.is_interface].split.value_counts().to_dict(),
        "sym_pairs": S.split.value_counts().to_dict(),
        "sym_pairs_interface": S[S.interface].split.value_counts().to_dict(),
        "sym_on_axis_pockets": on_axis,
        "ortho_interface_queries_considered": int(len(D)),
        "ortho_queries": Q.split.value_counts().to_dict(),
        "ortho_complex_pairs": Q.groupby("split").apply(
            lambda g: g[["query_complex", "partner_complex"]].drop_duplicates().shape[0]).to_dict(),
        "ortho_queries_by_type": {f"{k[0]}/{k[1]}": int(v) for k, v in Q.groupby(["split", "type"]).size().items()},
        "ortho_queries_if_overlap_coef_rule": int(((D.frac_mapped >= MIN_MAPPED) & (D.n_positives_overlap > 0)).sum()),
        "ortho_candidates_p50": float(Q.n_candidates.median()),
        "ortho_positives_p50": float(Q.n_positives.median()),
        "ortho_frac_mapped_ge_0.5_and_no_counterpart": int(((D.frac_mapped >= MIN_MAPPED) & (D.n_positives == 0)).sum()),
        "ortho_low_mapping": int((D.frac_mapped < MIN_MAPPED).sum()),
    }
    (ROOT / "results/ppi").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/ppi/ppips_counts.json").write_text(json.dumps(cnts, indent=1, default=str))
    print(json.dumps(cnts, indent=1, default=str))


if __name__ == "__main__":
    main()
