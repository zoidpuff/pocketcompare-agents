#!/usr/bin/env python
"""EXPLORATORY (post-test) — AFDB dimer interface-pocket atlas: a DEMO, not an evaluation.

Input: fingerprints of all merged BURROW pockets (>= 10 points) of the 15,161 AFDB dimers
(scripts/exploratory/dimer_atlas_describe.sh: `pocketcompare describe --af-mode`, final method, fast GPU backend).
PPIPS caches were NOT reused: the full run took ~6 min, so one consistent run was simpler.

Declared before looking at any search result:
* Interface pocket: f_min >= 0.25 (share of the pocket's BURROW output residues on the minority chain;
  reports/ppi_dimers.md) and >= 10 points (all describe_all pockets have >= 10) and a non-zero fingerprint.
* Reference sets (FINAL fingerprints from the stored N1 parts; D mode = best sub-pocket covering the ligand where
  BURROW matched the site, else L mode, flagged): PPI-L modulator pockets (PLOC+PLONC, ALL splits — allowed because
  this is a demo, not an evaluation; only the pocket table is read, never a sealed pair file) and BLiPS
  train/val ligand pockets (non-PPI background).
* "Close neighbour": cosine above tau_pair = 99th percentile of the background distribution = cosine of random
  (interface pocket, BLiPS ligand pocket) pairs (2 M sampled pairs).  Because the max over many references exceeds
  a pairwise percentile easily, the same count is reported for an equal-size random BLiPS subset (n = #modulator
  pockets) as the null, and for non-interface dimer pockets as a second control.
* Homology flag: a dimer chain is homologous to a modulator target if it shares the sequence or has a direct edge
  in the global homology graph (data/splits/homology_edges.parquet; MMseqs2 leakage rule OR Foldseek min-TM >= 0.5;
  note: for non-PPIPS dimer chains only sequence edges exist) to the modulator pocket's chain.
* Clusters: Louvain (networkx, seed 0, resolution 1) on the graph of top-10 neighbours among interface pockets
  (other structures only) with cosine >= tau_pair.  "Family" of a pocket = the pair of homology groups of its two
  chains (global graph, dimers groups); cross-family cluster = many distinct families.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketcompare import a4b as A4  # noqa: E402
from pocketcompare import fpindex as FX  # noqa: E402

D = ROOT / "data/processed/dimer_atlas"
OUT = ROOT / "results/exploratory/dimer_atlas"
FMIN = 0.25
rng = np.random.default_rng(0)


def log(*a):
    print(*a, flush=True)


def load_atlas():
    meta, V, rec = FX.read_tables([D / "shard0.parquet", D / "shard1.parquet"])
    st = pd.concat([pd.read_parquet(D / f"shard{i}.structures.parquet") for i in (0, 1)], ignore_index=True)
    man = pd.read_csv(ROOT / "data/processed/dimers/manifest.tsv", sep="\t")
    man = man[["modelEntityId", "uniprotAccession_1", "uniprotAccession_2", "gene_1", "gene_2", "ipTM", "max_ipSAE",
               "max_pDockQ2", "organism", "type", "iface_plddt"]].rename(columns={"modelEntityId": "structure_stem"})
    meta = meta.merge(man, on="structure_stem", how="left", validate="many_to_one")
    ch = meta.residues.fillna("").str.split()
    nA = ch.map(lambda r: sum(x.startswith("A:") for x in r))
    nB = ch.map(lambda r: sum(x.startswith("B:") for x in r))
    tot = (nA + nB).replace(0, np.nan)
    meta["n_res_A"], meta["n_res_B"] = nA, nB
    meta["f_min"] = (np.minimum(nA, nB) / tot).fillna(0.0)
    meta["interface"] = (meta.f_min >= FMIN) & (meta.n_points >= 10) & meta.ok
    return meta, V, rec, st


def ref_vectors():
    """FINAL fingerprints of the reference pockets (D mode where matched, else L)."""
    from pocketcompare.method import Method
    m = Method()
    out = {}
    P = pd.read_parquet(ROOT / "data/splits/ppi_l_pockets.parquet")
    S = pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet")
    S = S[S.partition.isin(["train", "val"])]
    for name, ds, ids, extra in (("ppil", "ppi_l", P.pocket_id, P), ("blips", "blips", S.site_id, S)):
        it = A4.ids_table(ds).set_index("pocket_id")
        ids = [i for i in ids if i in it.index and bool(it.loc[i, "has_L"])]
        useD = np.array([bool(it.loc[i, "has_U"]) and bool(it.loc[i, "d_match"]) for i in ids])
        E = np.zeros((len(ids), m.dim), np.float32)
        for mode, mask in (("D", useD), ("L", ~useD)):
            if mask.any():
                sub = [i for i, k in zip(ids, mask) if k]
                E[mask] = m.embed(A4.raw_parts(ds, mode, sub, "N1"))
        ok = np.linalg.norm(E, axis=1) > 0
        out[name] = (pd.DataFrame({"ref_id": np.array(ids)[ok], "mode": np.where(useD, "D", "L")[ok]}), E[ok])
    return out, P, S


def homology_maps(meta_stems):
    nodes = pd.read_parquet(ROOT / "data/splits/homology_nodes.parquet",
                            columns=["node_id", "dataset", "sid", "group_id", "pocket_ids"])
    dn = nodes[nodes.dataset == "dimers"].copy()
    dn["stem"] = dn.node_id.str.slice(len("dimers:"), -2)
    dn["chain"] = dn.node_id.str[-1]
    pn = nodes[nodes.dataset == "ppi_l"]
    E = pd.read_parquet(ROOT / "data/splits/homology_edges.parquet", columns=["sid_a", "sid_b", "seq_edge", "fs_edge"])
    E = E[E.seq_edge | E.fs_edge]
    ds, ps = set(dn.sid), set(pn.sid)
    m1 = E.sid_a.isin(ds) & E.sid_b.isin(ps)
    m2 = E.sid_b.isin(ds) & E.sid_a.isin(ps)
    pairs = set(zip(E.sid_a[m1], E.sid_b[m1])) | set(zip(E.sid_b[m2], E.sid_a[m2]))
    pairs |= {(s, s) for s in ds & ps}
    dsid_any = {a for a, _ in pairs}
    chain_sid = dn.set_index(["stem", "chain"]).sid.to_dict()
    chain_grp = dn.set_index(["stem", "chain"]).group_id.to_dict()
    # PPI-L pocket -> chain sid
    psid = {}
    for sid, pids in zip(pn.sid, pn.pocket_ids):
        for p in str(pids).split():
            psid[p] = sid
    return pairs, dsid_any, chain_sid, chain_grp, psid


def louvain(n, I, Dm, tau, stems):
    import networkx as nx
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j, s in zip(I[i], Dm[i]):
            if j >= 0 and s >= tau and stems[i] != stems[j]:
                G.add_edge(i, int(j), weight=float(s))
    comms = nx.community.louvain_communities(G, weight="weight", resolution=1.0, seed=0)
    lab = np.full(n, -1)
    for k, c in enumerate(sorted(comms, key=len, reverse=True)):
        lab[list(c)] = k
    return lab, G.number_of_edges()


def main():
    import faiss
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    meta, V, rec, st = load_atlas()
    wall = int((D / "end_epoch").read_text()) - int((D / "start_epoch").read_text())
    thr = {"n_structures": int(len(st)), "n_errors": int((st.status != "ok").sum()), "n_pockets": int(len(meta)),
           "wall_s_both_shards": wall, "structures_per_s": len(st) / wall,
           "per_structure_cpu_s_median": float(st.total_s.median()), "workers": "2 x (11 CPU workers + 1 GPU)",
           "gpu_s_per_structure_median": float(st.gpu_s.median()) if "gpu_s" in st else None}
    iface = meta.interface.to_numpy()
    s_if = meta[iface].groupby("structure_stem").size()
    summ = {"EXPLORATORY": True, "demo_not_evaluation": True, "throughput": thr,
            "pockets_per_dimer_median": float(meta.groupby("structure_stem").size().median()),
            "n_interface_pockets": int(iface.sum()), "frac_pockets_interface": float(iface.mean()),
            "dimers_with_interface_pocket": int(len(s_if)), "frac_dimers_with_interface_pocket": len(s_if) / len(st),
            "by_type": meta[iface].groupby(["organism", "type"]).size().astype(int).to_dict().__repr__()}
    FX.write_table(D / "atlas_all_pockets.parquet", meta, V, rec)
    MI, VI = meta[iface].reset_index(drop=True), V[iface]
    FX.write_table(D / "atlas_interface_pockets.parquet", MI, VI, rec)
    # ---------------------------------------------------------------- FAISS indices
    ta = time.time()
    ii = FX.build_index(VI, MI, D / "index_interface_flat", kind="flat", record=rec)
    ib = FX.build_index(V[meta.ok.to_numpy()], meta[meta.ok], D / "index_all_ivfpq", kind="ivfpq", record=rec,
                        threads=16)
    summ["index"] = {"interface_flat": {k: ii[k] for k in ("n", "build_s")},
                     "all_ivfpq": {k: ib[k] for k in ("n", "build_s", "factory", "index_bytes_per_pocket")},
                     "total_build_s": time.time() - ta}
    log("indices", summ["index"])
    # ---------------------------------------------------------------- references
    refs, P, S = ref_vectors()
    (Rp_meta, Rp), (Rb_meta, Rb) = refs["ppil"], refs["blips"]
    summ["references"] = {"ppil_modulator_pockets": len(Rp), "ppil_D_mode": int((Rp_meta["mode"] == "D").sum()),
                          "blips_trainval_pockets": len(Rb), "blips_D_mode": int((Rb_meta["mode"] == "D").sum())}
    # background pairwise distribution (interface x BLiPS)
    a = rng.integers(0, len(VI), 2_000_000)
    b = rng.integers(0, len(Rb), 2_000_000)
    pair = np.einsum("ij,ij->i", VI[a], Rb[b])
    tau = float(np.quantile(pair, 0.99))
    summ["tau_pair_p99_iface_x_blips"] = tau
    summ["pair_quantiles_iface_x_blips"] = {q: float(np.quantile(pair, q)) for q in (0.5, 0.9, 0.99, 0.999)}
    sub = rng.choice(len(Rb), size=min(len(Rp), len(Rb)), replace=False)
    Rb_eq = Rb[sub]

    def nn(Q, R, k=1):
        ix = faiss.IndexFlatIP(R.shape[1])
        ix.add(np.ascontiguousarray(R))
        return ix.search(np.ascontiguousarray(Q), k)

    Dp, Ip = nn(VI, Rp, 5)
    Db, Ib = nn(VI, Rb_eq, 1)
    Dball, Iball = nn(VI, Rb, 1)
    nonif = (~iface) & meta.ok.to_numpy()
    Vn = V[nonif]
    Dpn, _ = nn(Vn, Rp, 1)
    Dbn, _ = nn(Vn, Rb_eq, 1)
    tau_nn = float(np.quantile(Db[:, 0], 0.99))
    summ["close_neighbour"] = {
        "interface": {"n": int(len(VI)), "nn_modulator_gt_tau_pair": int((Dp[:, 0] > tau).sum()),
                      "frac_nn_modulator_gt_tau_pair": float((Dp[:, 0] > tau).mean()),
                      "frac_nn_blips_equal_size_gt_tau_pair": float((Db[:, 0] > tau).mean()),
                      "tau_nn_p99_of_nn_to_blips_equal_size": tau_nn,
                      "nn_modulator_gt_tau_nn": int((Dp[:, 0] > tau_nn).sum()),
                      "frac_nn_modulator_gt_tau_nn": float((Dp[:, 0] > tau_nn).mean()),
                      "median_nn_cos_modulator": float(np.median(Dp[:, 0])),
                      "median_nn_cos_blips_equal_size": float(np.median(Db[:, 0])),
                      "frac_modulator_nn_beats_blips_nn": float((Dp[:, 0] > Db[:, 0]).mean())},
        "non_interface_control": {"n": int(len(Vn)), "frac_nn_modulator_gt_tau_pair": float((Dpn[:, 0] > tau).mean()),
                                  "frac_nn_blips_equal_size_gt_tau_pair": float((Dbn[:, 0] > tau).mean()),
                                  "frac_nn_modulator_gt_tau_nn": float((Dpn[:, 0] > tau_nn).mean()),
                                  "frac_modulator_nn_beats_blips_nn": float((Dpn[:, 0] > Dbn[:, 0]).mean())}}
    log(json.dumps(summ["close_neighbour"], indent=1))
    # ---------------------------------------------------------------- hits + homology flags
    pairs, dsid_any, chain_sid, chain_grp, psid = homology_maps(MI.structure_stem.unique())
    Pi = P.set_index("pocket_id")
    hits = MI[["pocket_id", "structure_stem", "organism", "type", "gene_1", "gene_2", "uniprotAccession_1",
               "uniprotAccession_2", "ipTM", "max_ipSAE", "f_min", "plddt_mean", "burrow_score", "volume_A3",
               "residues"]].copy()
    hits["nn_mod_cos"] = Dp[:, 0]
    hits["nn_blips_cos"] = Dball[:, 0]
    hits["nn_blips_id"] = Rb_meta.ref_id.to_numpy()[Iball[:, 0]]
    mid = Rp_meta.ref_id.to_numpy()[Ip[:, 0]]
    hits["mod_pocket"] = mid
    hits["mod_mode"] = Rp_meta["mode"].to_numpy()[Ip[:, 0]]
    for c in ("uniprot", "lig", "label", "pfam_name", "pdb", "smiles", "group"):
        hits[f"mod_{c}"] = Pi.loc[mid, c].to_numpy()
    sA = [chain_sid.get((s, "A")) for s in hits.structure_stem]
    sB = [chain_sid.get((s, "B")) for s in hits.structure_stem]
    ms = [psid.get(p) for p in mid]
    hits["hom_to_mod_target"] = [((a_, m_) in pairs) or ((b_, m_) in pairs) for a_, b_, m_ in zip(sA, sB, ms)]
    hits["hom_to_any_ppil"] = [(a_ in dsid_any) or (b_ in dsid_any) for a_, b_ in zip(sA, sB)]
    hits["same_uniprot_as_mod"] = [(m_ in (u1, u2)) for m_, u1, u2 in
                                   zip(hits.mod_uniprot, hits.uniprotAccession_1, hits.uniprotAccession_2)]
    hits["close"] = hits.nn_mod_cos > tau
    hits["close_strict"] = hits.nn_mod_cos > tau_nn
    hits.to_parquet(D / "interface_vs_modulators.parquet", index=False)
    cl = hits[hits.close]
    summ["close_hits_homology"] = {"n_close": int(len(cl)), "hom_to_matched_target": int(cl.hom_to_mod_target.sum()),
                                   "same_uniprot": int(cl.same_uniprot_as_mod.sum()),
                                   "non_homologous": int((~cl.hom_to_mod_target).sum()),
                                   "n_close_strict": int(hits.close_strict.sum()),
                                   "strict_non_homologous": int((hits.close_strict & ~hits.hom_to_mod_target).sum()),
                                   "dimers_with_close_hit": int(cl.structure_stem.nunique()),
                                   "frac_iface_hom_to_any_ppil": float(hits.hom_to_any_ppil.mean())}
    # examples: best per gene pair, distinct modulator targets; 10 overall + 10 non-homologous
    h = hits.sort_values("nn_mod_cos", ascending=False)
    h["pair"] = h.gene_1.astype(str) + "–" + h.gene_2.astype(str)

    def pick(df, n=10):
        out, seen_p, seen_t = [], set(), set()
        for r in df.itertuples():
            if r.pair in seen_p or r.mod_uniprot in seen_t:
                continue
            out.append(r.Index)
            seen_p.add(r.pair)
            seen_t.add(r.mod_uniprot)
            if len(out) == n:
                break
        return df.loc[out]
    cols = ["pair", "organism", "type", "ipTM", "max_ipSAE", "f_min", "plddt_mean", "nn_mod_cos", "nn_blips_cos",
            "mod_pocket", "mod_uniprot", "mod_pfam_name", "mod_lig", "mod_label", "hom_to_mod_target",
            "same_uniprot_as_mod"]
    ex_all = pick(h)[cols]
    ex_nonhom = pick(h[~h.hom_to_mod_target & ~h.hom_to_any_ppil])[cols]
    ex_all.to_csv(OUT / "examples_top.tsv", sep="\t", index=False, float_format="%.3f")
    ex_nonhom.to_csv(OUT / "examples_nonhomologous.tsv", sep="\t", index=False, float_format="%.3f")
    # ---------------------------------------------------------------- clusters
    tc = time.time()
    res = faiss.StandardGpuResources() if faiss.get_num_gpus() > 0 else None
    ix = faiss.IndexFlatIP(VI.shape[1])
    if res is not None:
        ix = faiss.index_cpu_to_gpu(res, 0, ix)
    ix.add(VI)
    Dk, Ik = ix.search(VI, 31)
    stems = MI.structure_stem.to_numpy()
    # keep the first 10 neighbours from other structures
    In = np.full((len(VI), 10), -1)
    Dn = np.full((len(VI), 10), -np.inf, np.float32)
    for i in range(len(VI)):
        k = 0
        for j, s in zip(Ik[i], Dk[i]):
            if j != i and stems[j] != stems[i]:
                In[i, k], Dn[i, k] = j, s
                k += 1
                if k == 10:
                    break
    knn_s = time.time() - tc
    lab, n_edges = louvain(len(VI), In, Dn, tau, stems)
    MI["cluster"] = lab
    gA = [chain_grp.get((s, "A")) for s in stems]
    gB = [chain_grp.get((s, "B")) for s in stems]
    MI["family"] = ["|".join(sorted([str(a_), str(b_)])) for a_, b_ in zip(gA, gB)]
    MI["pair"] = MI.gene_1.astype(str) + "–" + MI.gene_2.astype(str)
    MI["nn_mod_cos"] = hits.nn_mod_cos.to_numpy()
    MI["close_mod"] = hits.close.to_numpy()
    MI[["pocket_id", "cluster", "family", "pair", "organism", "type", "f_min", "ipTM", "nn_mod_cos"]].to_parquet(
        D / "interface_clusters.parquet", index=False)
    cs = MI.groupby("cluster").agg(n=("pocket_id", "size"), n_dimers=("structure_stem", "nunique"),
                                   n_families=("family", "nunique"), n_organisms=("organism", "nunique"),
                                   frac_close_mod=("close_mod", "mean"), mean_fmin=("f_min", "mean"),
                                   top_pairs=("pair", lambda x: ", ".join(x.value_counts().index[:6])))
    cs["max_family_share"] = MI.groupby("cluster").family.agg(lambda x: x.value_counts(normalize=True).iloc[0])
    cs = cs.sort_values("n", ascending=False)
    cs.to_csv(OUT / "clusters.tsv", sep="\t", float_format="%.3f")
    big = cs[cs.n >= 10]
    cross = big[(big.n_families >= 10) & (big.max_family_share < 0.3)].sort_values("n_families", ascending=False)
    cross.head(15).to_csv(OUT / "clusters_cross_family_top.tsv", sep="\t", float_format="%.3f")
    summ["clusters"] = {"method": "Louvain on top-10 other-structure neighbours with cos >= tau_pair",
                        "n_edges": int(n_edges), "n_clusters": int(cs.shape[0]),
                        "n_singletons": int((cs.n == 1).sum()), "n_clusters_ge10": int(len(big)),
                        "frac_pockets_in_ge10": float(big.n.sum() / len(MI)),
                        "n_cross_family_ge10fam_share_lt0.3": int(len(cross)),
                        "largest": int(cs.n.iloc[0]), "knn_s": knn_s, "cluster_s": time.time() - tc}
    summ["wall_s_analysis"] = time.time() - t0
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=str))
    log(json.dumps({k: summ[k] for k in ("close_hits_homology", "clusters")}, indent=1))
    log(ex_all.to_string())
    log(ex_nonhom.to_string())
    log(cross.head(8).to_string())


if __name__ == "__main__":
    main()
