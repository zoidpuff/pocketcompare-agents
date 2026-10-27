#!/usr/bin/env python
"""Sanity (a): does a pocket from a perturbed copy of a model retrieve its own original at rank 1?

    CUDA_VISIBLE_DEVICES=2 python scripts/proteome/sanity_jitter.py --n 20

20 random non-fragment models that have >= 1 indexed pocket (seed 0).  Copies (PDB text rewritten, 1e-3 Å):
  rot     random rotation about the centroid + random 10 Å translation;
  jit0.5  rot + per-atom isotropic Gaussian noise, RMS displacement 0.5 Å;
  jit1.0  rot + noise with RMS displacement 1.0 Å (sigma = 1/sqrt(3) Å per coordinate).
Detected arm: each copy runs through the same pipeline (fast CPU path, AF mode, region rule, merge, >= 10 points, sph8,
A1 + env, z-scored embedding).  A copy pocket's counterpart = the original pocket of the same model with the
highest lining-residue Jaccard (>= 0.5 required).  Query = the copy embedding against the full proteome index
(exact inner product, all N indexed pockets; the copy itself is not in the index).
Fixed-centre arm (``<cond>|fixed_centre``): every original pocket's sph8 centre, moved by the same rigid transform,
is described in the copy's BURROW points (no re-detection) -> isolates featurisation + descriptor noise.

Output: results/proteome/sanity_jitter.json (+ per-pocket parquet in data/processed/proteome_human/index/).
"""
from __future__ import annotations

import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "2")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import gzip  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts/proteome")]
from pocketcompare import pockets_fast as pf  # noqa: E402
from pocketcompare import pockets as pkm  # noqa: E402
from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import a1r  # noqa: E402
from proteome_lib import CFG, FEATS, describe_structure, embed_a1env  # noqa: E402
from scipy.spatial.transform import Rotation  # noqa: E402

import faiss  # noqa: E402

P = ROOT / "data/processed/proteome_human"
TAR = "/cluster/work/beltrao/shared/alphafold/v6/UP000005640_9606_HUMAN_v6.tar"


def transform_pdb(text: str, rng, rms: float) -> str:
    lines = text.splitlines()
    at = [i for i, l in enumerate(lines) if l.startswith(("ATOM  ", "HETATM"))]
    X = np.array([[float(lines[i][30:38]), float(lines[i][38:46]), float(lines[i][46:54])] for i in at])
    R = Rotation.random(random_state=int(rng.integers(1 << 31))).as_matrix()
    c = X.mean(0)
    t = rng.normal(size=3)
    t = 10.0 * t / np.linalg.norm(t)
    Y = (X - c) @ R.T + c + t
    if rms > 0:
        Y = Y + rng.normal(scale=rms / np.sqrt(3), size=Y.shape)
    for i, (x, y, z) in zip(at, Y):
        l = lines[i]
        lines[i] = f"{l[:30]}{x:8.3f}{y:8.3f}{z:8.3f}{l[54:]}"
    return "\n".join(lines) + "\n", (lambda p: (np.asarray(p, float) - c) @ R.T + c + t)


def jaccard(a: str, b: str) -> float:
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if A | B else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    idx_dir = P / "index"
    pk = pd.read_parquet(idx_dir / "pockets.parquet")
    E = np.load(idx_dir / "emb.npy")
    zs = dict(np.load(P / "zstats.npz"))
    mem = pd.read_parquet(P / "members.parquet").set_index("stem")
    cand = sorted(set(pk.stem[pk.fragment == 1]) & set(mem.index[mem.n_fragments == 1]))
    stems = list(rng.choice(cand, a.n, replace=False))
    res = faiss.StandardGpuResources()
    index = faiss.GpuIndexFlatIP(res, E.shape[1])
    index.add(E)
    fm = pf.fast_model()
    rows = []
    tmpd = Path(tempfile.mkdtemp(prefix="pc_jitter_"))
    with open(TAR, "rb") as fh:
        for stem in stems:
            r = mem.loc[stem]
            fh.seek(int(r.offset_data))
            text = gzip.decompress(fh.read(int(r["size"]))).decode()
            orig = pk[pk.stem == stem]
            for cond, rms in (("rot", 0.0), ("jit0.5", 0.5), ("jit1.0", 1.0)):
                f = tmpd / f"{stem}_{cond}.pdb"
                txt, move = transform_pdb(text, rng, rms)
                f.write_text(txt)
                fs = pf.featurize_fast_cpu(f, stem, af_mode=True, fm=fm)
                f.unlink()
                from pocketdetect.burrow.af import residue_plddt  # noqa: F401  (pLDDT not needed here)
                d = describe_structure(fs, None, 0)
                # fixed-centre arm: the ORIGINAL pocket's sph8 centre, moved with the rigid transform, described
                # in the copy (isolates featurisation + descriptor noise from changes in detection)
                at_c = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
                fa, fe, gis = [], [], []
                for gi, o in orig.iterrows():
                    site = pkm.site_sphere(fs, move([o.cx, o.cy, o.cz]), 8.0)
                    if len(site) == 0:
                        continue
                    v, _ = A1.a1_descriptor(A1.pocket_input(fs, site, atom_types=at_c, features=FEATS), CFG)
                    fa.append(v)
                    fe.append(a1r.env_descriptor(fs, site))
                    gis.append(int(gi))
                if gis:
                    Ef = embed_a1env(np.stack(fa), np.stack(fe), zs)
                    Df, If = index.search(Ef, 100)
                    for j, gi in enumerate(gis):
                        hit = np.flatnonzero(If[j] == gi)
                        rows.append(dict(stem=stem, cond=cond + "|fixed_centre", copy_pocket=j, n_orig=len(orig),
                                         n_copy=len(gis), best_jaccard=1.0, orig_index=gi,
                                         cos_to_orig=float(Ef[j] @ E[gi]),
                                         rank_of_orig=int(hit[0]) + 1 if len(hit) else 101, top1_sim=float(Df[j, 0]),
                                         top1_same_protein=bool(pk.uniprot.iloc[int(If[j, 0])] == pk.uniprot.iloc[gi])))
                if not d["records"]:
                    rows.append(dict(stem=stem, cond=cond, copy_pocket=-1, n_orig=len(orig), n_copy=0))
                    continue
                Ec = embed_a1env(np.stack(d["a1"]), np.stack(d["env"]), zs)
                Dq, Iq = index.search(Ec, 100)
                for j, rec in enumerate(d["records"]):
                    jac = np.array([jaccard(rec["residues"], x) for x in orig.residues])
                    b = int(np.argmax(jac)) if len(jac) else -1
                    gi = int(orig.index[b]) if b >= 0 else -1
                    hit = np.flatnonzero(Iq[j] == gi)
                    rank = int(hit[0]) + 1 if len(hit) else 101
                    rows.append(dict(stem=stem, cond=cond, copy_pocket=j, n_orig=len(orig), n_copy=len(d["records"]),
                                     best_jaccard=float(jac[b]) if b >= 0 else 0.0, orig_index=gi,
                                     cos_to_orig=float(Ec[j] @ E[gi]) if gi >= 0 else np.nan,
                                     rank_of_orig=rank, top1_sim=float(Dq[j, 0]),
                                     top1_same_protein=bool(pk.uniprot.iloc[int(Iq[j, 0])] == pk.uniprot.iloc[gi])
                                     if gi >= 0 else False))
            print(stem, flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(idx_dir / "sanity_jitter.parquet", index=False)
    summ = {}
    for cond, g in df[df.copy_pocket >= 0].groupby("cond"):
        m = g[g.best_jaccard >= 0.5]
        summ[cond] = dict(n_copy_pockets=len(g), n_matched_j05=len(m),
                          frac_matched=float(len(m) / len(g)) if len(g) else np.nan,
                          rank1=float((m.rank_of_orig == 1).mean()), top5=float((m.rank_of_orig <= 5).mean()),
                          top10=float((m.rank_of_orig <= 10).mean()), median_rank=float(m.rank_of_orig.median()),
                          median_cos=float(m.cos_to_orig.median()),
                          rank1_j08=float((g[g.best_jaccard >= 0.8].rank_of_orig == 1).mean()),
                          n_j08=int((g.best_jaccard >= 0.8).sum()),
                          top1_same_protein=float(m.top1_same_protein.mean()))
    out = dict(n_models=len(stems), stems=stems, N_index=int(len(E)), per_condition=summ,
               n_orig_pockets=int(pk.stem.isin(stems).sum()))
    (ROOT / "results/proteome/sanity_jitter.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
