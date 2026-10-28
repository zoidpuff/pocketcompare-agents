"""pocketcompare quickstart, Python API.  Usage: python examples/quickstart.py

1. describe a pocket from a ligand, 2. describe all pockets of an AlphaFold model, 3. compare,
4. build an index over a folder (FAISS if installed, else numpy), 5. search.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from pocketcompare import method

EX = Path(__file__).resolve().parent

# 1. A ligand-defined site: progesterone (STR) in the crystal structure 1A28, chain A -> one 384-d unit vector
site = method.describe(EX / "pdb/1a28_A.pdb", site=str(EX / "pdb/1a28_STR.pdb"))
print("site fingerprint:", site.shape, "norm", round(float(np.linalg.norm(site)), 4))
#    other ways to give a site: site=xyz (n, 3) ligand heavy atoms, site=["A:718", "A:725", ...] (residues),
#    and locate="burrow" to describe the BURROW pocket at the site instead of the ligand shell.

# 2. Every pocket of an AlphaFold model (af_mode=True: BURROW's pLDDT-aware mode)
V, info = method.describe_all(EX / "afdb/AF-P06401-F1-model_v6.cif.gz", af_mode=True)
print(f"\nprogesterone receptor AlphaFold model: {len(V)} pockets")

# 3. Compare: cosine = inner product (higher = more similar)
s = method.similarity(site, V)[0]
show = info.assign(score=s)[["burrow_rank", "burrow_score", "score", "residues"]].sort_values("score",
                                                                                            ascending=False)
print(show.head(3).to_string(index=False, max_colwidth=60))

# 4. An index over a folder of structures
vecs, meta = [], []
for f in sorted((EX / "afdb").glob("*.cif.gz")):
    W, inf = method.describe_all(f, af_mode=True)
    keep = inf["ok"].to_numpy()                         # zero vectors = not describable (no buried points)
    vecs.append(W[keep])
    meta.append(inf[keep].assign(structure=f.name))
X = np.vstack(vecs).astype(np.float32)
meta = pd.concat(meta, ignore_index=True)
try:
    import faiss
    index = faiss.IndexFlatIP(X.shape[1])               # exact; fingerprints are unit vectors, score = inner product
    index.add(X)
    D, I = index.search(site.astype(np.float32), 5)
    D, I = D[0], I[0]
except ImportError:                                     # pip install pocketcompare[search] for FAISS
    S = (site @ X.T)[0]
    I = np.argsort(-S)[:5]
    D = S[I]

# 5. Search: top-5 pockets over the folder
print(f"\ntop hits among {len(X)} pockets of {meta.structure.nunique()} AlphaFold models:")
print(meta.iloc[I][["structure", "burrow_rank", "residues"]].assign(score=D).to_string(index=False,
                                                                                    max_colwidth=50))
