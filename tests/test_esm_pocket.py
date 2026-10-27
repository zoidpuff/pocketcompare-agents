import os
import numpy as np
import pytest
from pocketcompare.descriptors import esm_pocket as ep

PDB = "data/raw/tough_m1/extracted/TOUGH-M1_dataset/11asA/11asA.pdb"


def test_window_starts():
    assert ep.window_starts(500) == [0]
    s = ep.window_starts(2000)
    assert s[0] == 0 and s[-1] == 2000 - 1022 and all(b - a <= 511 for a, b in zip(s, s[1:]))


def test_numbering_map_not_one_based(tmp_path):
    p = tmp_path / "x.pdb"
    lines = []
    for i, (rn, num, ic) in enumerate([("ALA", 43, " "), ("GLY", 44, " "), ("SER", 44, "A"), ("LYS", 50, " ")]):
        lines.append(f"ATOM  {i+1:5d}  CA  {rn} B{num:4d}{ic}   {i*3.8:8.3f}   0.000   0.000  1.00  0.00           C")
    p.write_text("\n".join(lines) + "\nEND\n")
    ch = ep.chain_residues(p)
    assert ch["B"] == ("AGSK", ["43", "44", "44A", "50"])
    embs = {"B": np.arange(4, dtype=np.float16)[:, None] * np.ones((1, 3), np.float16)}
    v, nf, nm = ep.pool_pocket(ch, embs, ["B:44A", "B:50", "B:99"])
    assert nf == 2 and nm == 1 and np.allclose(v, 2.5)
    v, nf, _ = ep.pool_pocket(ch, embs, ["A:43"])  # single chain remap
    assert nf == 1 and np.allclose(v, 0)


@pytest.mark.skipif(not os.path.exists(PDB), reason="no data")
def test_real_structure_residue_alignment():
    ch = ep.chain_residues(PDB)
    seq, ids = ch["A"]
    assert len(seq) == len(ids)
    assert seq[ids.index("43")] in "ACDEFGHIKLMNPQRSTVWYX"


@pytest.mark.skipif(not os.path.exists(PDB), reason="no data")
def test_gpu_embed(tmp_path):
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("no GPU")
    e = ep.ESMEmbedder("cuda", tmp_path)
    seq = ep.chain_residues(PDB)["A"][0]
    a = e.embed_chain(seq)
    assert a.shape == (len(seq), ep.DIM) and a.dtype == np.float16 and np.isfinite(a).all()
    # window consistency: windowed path on a short seq is not used; check long-seq averaging runs
    long = (seq * 6)[:1500]
    b = e.embed_chain(long)
    assert b.shape == (1500, ep.DIM) and np.isfinite(b).all()
