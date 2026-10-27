#!/usr/bin/env python
"""Sanity (b): known-family check (descriptive only; no benchmark labels).

    python scripts/proteome/sanity_family.py

Family annotation available locally: KLIFS human protein kinases (data/raw/klifs/downloads/kinase_information.json,
555 human kinases with UniProt + KLIFS group).  Site annotation: pocket_detect's known BioLiP2 small-molecule sites
mapped to UniProt numbering (pocket_detect/data/processed/proteome_human/known_pockets_uniprot.tsv; read-only).
A pocket is "at a known small-molecule site" if >= 50 % of its lining residues are residues of one such site.

Queries: Q-site = kinase pockets at a known small-molecule site; Q-all = all kinase pockets.
For each query, its top-10 hits after removing pockets of the same UniProt entry (from the exact top-50 list; raw
cosine and CSLS-db re-ranking) are scored as: kinase pocket (any pocket of a KLIFS kinase), kinase-site pocket, and
same KLIFS group (kinase hits only).  Expectation = size-matched random: each hit is replaced by a random pocket of the
same pocket-volume decile; expected fraction = mean over hits of P(category | decile) (same-UniProt excluded is
ignored, < 0.01 % of the pool).

Output: results/proteome/sanity_family.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data/processed/proteome_human/index"
KNOWN = Path("/cluster/project/beltrao/gmagnus/pocket_detect/data/processed/proteome_human/known_pockets_uniprot.tsv")
KLIFS = ROOT / "data/raw/klifs/downloads/kinase_information.json"


def main():
    pk = pd.read_parquet(P / "pockets.parquet")
    I50 = np.load(P / "knn_exact_I.npy")
    kl = pd.DataFrame(json.load(open(KLIFS)))
    kl = kl[(kl.species == "Human") & kl.uniprot.astype(bool)]
    group = dict(zip(kl.uniprot, kl.group))
    is_kin = pk.uniprot.isin(group).to_numpy()
    kn = pd.read_csv(KNOWN, sep="\t")
    sm = kn[kn.category == "small_molecule"]
    sites: dict = {}
    for u, r in zip(sm.uniprot, sm.residues):
        sites.setdefault(u, []).append(set(r.split()))
    at_site = np.zeros(len(pk), bool)
    for i, (u, r) in enumerate(zip(pk.uniprot, pk.residues)):
        if u in sites:
            R = set(r.split())
            at_site[i] = bool(R) and max(len(R & S) for S in sites[u]) / len(R) >= 0.5
    kin_site = is_kin & at_site
    dec = pd.qcut(pk.volume_A3.rank(method="first"), 10, labels=False).to_numpy()
    p_kin = np.array([is_kin[dec == b].mean() for b in range(10)])
    p_ks = np.array([kin_site[dec == b].mean() for b in range(10)])
    uni = pk.uniprot.to_numpy()
    grp = np.array([group.get(u, "") for u in uni])

    def hits_of(I, q, k=10):
        h = [j for j in I[q] if uni[j] != uni[q]]
        return np.asarray(h[:k], np.int64)

    out = dict(n_pockets=len(pk), n_kinase_proteins_in_index=int(len(set(uni[is_kin]))),
               n_kinase_pockets=int(is_kin.sum()), frac_kinase_pockets=float(is_kin.mean()),
               n_at_known_sm_site=int(at_site.sum()), n_kinase_site_pockets=int(kin_site.sum()),
               n_kinase_proteins_with_site_pocket=int(len(set(uni[kin_site]))), rankings={})
    rankings = {"raw": I50}
    cs = P / "knn_csls_db_I.npy"
    if cs.exists():
        rankings["csls_db"] = np.load(cs)
    for rname, I in rankings.items():
        res = {}
        for qname, qmask in (("Q-site", kin_site), ("Q-all", is_kin), ("control: non-kinase site pockets",
                                                                       at_site & ~is_kin)):
            qs = np.flatnonzero(qmask)
            obs_k, exp_k, obs_ks, exp_ks, same_g, exp_g, n_h = [], [], [], [], [], [], []
            gfreq = pd.Series(grp[is_kin]).value_counts(normalize=True).to_dict()
            for q in qs:
                h = hits_of(I, q)
                if len(h) == 0:
                    continue
                n_h.append(len(h))
                obs_k.append(is_kin[h].mean())
                exp_k.append(p_kin[dec[h]].mean())
                obs_ks.append(kin_site[h].mean())
                exp_ks.append(p_ks[dec[h]].mean())
                kh = h[is_kin[h]]
                if is_kin[q] and len(kh):
                    same_g.append((grp[kh] == grp[q]).mean())
                    exp_g.append(gfreq.get(grp[q], 0.0))
            res[qname] = dict(n_queries=len(qs), mean_hits_considered=float(np.mean(n_h)) if n_h else 0.0,
                              frac_hits_kinase=float(np.mean(obs_k)), expected_size_matched=float(np.mean(exp_k)),
                              enrichment=float(np.mean(obs_k) / np.mean(exp_k)),
                              frac_hits_kinase_site=float(np.mean(obs_ks)),
                              expected_kinase_site_size_matched=float(np.mean(exp_ks)),
                              enrichment_kinase_site=float(np.mean(obs_ks) / np.mean(exp_ks)) if np.mean(exp_ks) else None,
                              frac_queries_with_any_kinase_hit=float(np.mean(np.array(obs_k) > 0)),
                              same_klifs_group_among_kinase_hits=float(np.mean(same_g)) if same_g else None,
                              same_group_expected=float(np.mean(exp_g)) if exp_g else None)
        out["rankings"][rname] = res
    (ROOT / "results/proteome/sanity_family.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    sys.exit(main())
