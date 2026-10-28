"""``pocketcompare`` CLI (describe / compare / index / search) on the example structures.

Checks: the output table matches ``method.describe_all`` / ``method.describe``; the ref, fast-CPU and (if a GPU is
present) GPU backends give identical fingerprints; ``compare`` = inner products; ``index`` + ``search`` return the
exact neighbours (flat) and, for OPQ+IVF-PQ with exact re-rank, the exact top hits; ``python -m pocketcompare``
works.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import AF_CA2 as AF
from conftest import EX, LIG, PDB
from pocketcompare import cli, method
from pocketcompare import fpindex as FX

try:
    import faiss  # noqa: F401
    HAVE_FAISS = True
except ImportError:
    HAVE_FAISS = False
need_faiss = pytest.mark.skipif(not HAVE_FAISS, reason="faiss not installed (pip install pocketcompare[search])")


def _cuda():
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="module")
def tables(tmp_path_factory):
    d = tmp_path_factory.mktemp("cli")
    assert cli.main(["describe", str(AF), "--af-mode", "-o", str(d / "af.parquet")]) == 0
    assert cli.main(["describe", str(PDB), "--n1", "-o", str(d / "pdb.parquet")]) == 0
    sub = d / "structs"
    sub.mkdir()
    for f in (AF, PDB):
        (sub / f.name).symlink_to(f)
    assert cli.main(["describe", str(sub), "--workers", "2", "-o", str(d / "dir.parquet")]) == 0
    return d


def test_describe_table(tables):
    meta, V, rec = FX.read_table(tables / "af.parquet")
    assert rec["dims"] == V.shape[1] == 384 and rec["method"].startswith("pocketcompare-final")
    for c in ("pocket_id", "burrow_score", "residues", "center_x", "center_y", "center_z", "volume_A3",
              "plddt_mean", "plddt_min", "ok"):
        assert c in meta
    assert meta.pocket_id.is_unique and meta.plddt_mean.notna().all()
    np.testing.assert_allclose(np.linalg.norm(V[meta.ok.to_numpy()], axis=1), 1.0, atol=1e-5)
    Vr, info = method.describe_all(AF, af_mode=True)
    np.testing.assert_array_equal(V, Vr)
    assert list(meta.burrow_rank) == list(info.burrow_rank)
    m2, V2, _, N2 = FX.read_table(tables / "pdb.parquet", with_n1=True)
    assert m2.plddt_mean.isna().all()                       # not an AF model: no pLDDT
    np.testing.assert_array_equal(V2, method.describe_all(PDB)[0])
    assert N2.shape == (len(V2), 627)
    np.testing.assert_allclose(method.default().embed_n1(N2), V2, atol=1e-6)
    md, Vd, _ = FX.read_table(tables / "dir.parquet")       # directory input, 2 workers
    assert set(md.structure_stem) == {"1a28_A", "AF-P00918-F1-model_v6"}
    st = pd.read_parquet(tables / "dir.structures.parquet")
    assert (st.status == "ok").all() and st.total_s.gt(0).all()


def test_describe_structure_without_pockets(tmp_path):
    """A structure with no pocket (a 4-residue fragment) gives 0 rows, not an error; a bad file is an error."""
    lines = [ln for ln in PDB.read_text().splitlines() if ln.startswith("ATOM") and int(ln[22:26]) < 686]
    (tmp_path / "frag.pdb").write_text("\n".join(lines) + "\nEND\n")
    (tmp_path / "bad.pdb").write_text("garbage\n")
    out = tmp_path / "o.parquet"
    assert cli.main(["describe", str(tmp_path / "frag.pdb"), str(tmp_path / "bad.pdb"), str(PDB), "-o", str(out)]) == 0
    st = pd.read_parquet(tmp_path / "o.structures.parquet").set_index("structure")
    assert st.loc[str(tmp_path / "frag.pdb"), "status"] == "ok" and st.loc[str(tmp_path / "frag.pdb"), "n_pockets"] == 0
    assert st.loc[str(tmp_path / "bad.pdb"), "status"] == "error"
    m, V, _ = FX.read_table(out)
    assert set(m.structure_stem) == {"1a28_A"} and len(V) == len(m)


def test_describe_fast_backend_identical(tables, tmp_path):
    for src, extra in ((AF, ["--af-mode"]), (PDB, [])):
        out = tmp_path / f"{src.name}.parquet"
        assert cli.main(["describe", str(src), "--backend", "fast", "-o", str(out)] + extra) == 0
        ref = tables / ("af.parquet" if src == AF else "pdb.parquet")
        (m0, V0, _), (m1, V1, _) = FX.read_table(ref), FX.read_table(out)
        np.testing.assert_array_equal(V0, V1)
        assert list(m0.residues) == list(m1.residues)


@pytest.mark.skipif(not _cuda(), reason="no CUDA device / torch")
def test_describe_gpu_backend_identical(tables, tmp_path):
    out = tmp_path / "gpu.parquet"
    assert cli.main(["describe", str(AF), str(PDB), "--device", "cuda:0", "--workers", "2", "-o", str(out)]) == 0
    m1, V1, rec = FX.read_table(out)
    assert rec["device"] == "cuda:0"
    m0, V0, _ = FX.read_table(tables / "pdb.parquet")
    sel = (m1.structure_stem == "1a28_A").to_numpy()
    np.testing.assert_allclose(V1[sel], V0, atol=1e-6)
    assert list(m1.residues[sel]) == list(m0.residues)


def test_describe_site_modes(tables, tmp_path):
    meta, _, _ = FX.read_table(tables / "pdb.parquet")
    res = meta.residues.iloc[0].replace(" ", ",")
    out = tmp_path / "res.parquet"
    assert cli.main(["describe", str(PDB), "--residues", res, "-o", str(out)]) == 0
    m, V, rec = FX.read_table(out)
    assert len(m) == 1 and m["mode"][0] == "L" and rec["site"] == res
    np.testing.assert_array_equal(V, method.describe(PDB, site=res.split(",")))
    out = tmp_path / "resD.parquet"
    assert cli.main(["describe", str(PDB), "--residues", res, "--locate", "burrow", "-o", str(out)]) == 0
    m, V, _ = FX.read_table(out)
    assert m["mode"][0] == "D" and m.burrow_rank[0] >= 1
    np.testing.assert_array_equal(V, method.describe(PDB, site=res.split(","), locate="burrow"))


def test_describe_ligand(tmp_path):
    out = tmp_path / "lig.parquet"
    assert cli.main(["describe", str(PDB), "--ligand", str(LIG), "-o", str(out)]) == 0
    m, V, _ = FX.read_table(out)
    np.testing.assert_array_equal(V, method.describe(PDB, site=str(LIG)))
    assert "A:725" in m.residues[0].split()          # progesterone site lining residue (Gln725)


def test_compare(tables, tmp_path):
    mat = tmp_path / "S.npy"
    pairs = tmp_path / "pairs.tsv"
    assert cli.main(["compare", str(tables / "af.parquet"), str(tables / "pdb.parquet"), "--matrix", str(mat),
                     "-o", str(pairs), "--top", "3"]) == 0
    _, A, _ = FX.read_table(tables / "af.parquet")
    _, B, _ = FX.read_table(tables / "pdb.parquet")
    np.testing.assert_allclose(np.load(mat), A @ B.T, atol=1e-6)
    p = pd.read_csv(pairs, sep="\t")
    assert len(p) == len(A) * min(3, len(B)) and (p.groupby("query_id").score.diff().dropna() <= 1e-7).all()
    # structures directly (described on the fly) == the tables
    assert cli.main(["compare", str(AF), str(tables / "af.parquet"), "--af-mode", "--matrix", str(mat)]) == 0
    np.testing.assert_allclose(np.diag(np.load(mat)), 1.0, atol=1e-5)


@pytest.fixture(scope="module")
def big_table(tables, tmp_path_factory):
    """1,200 unit vectors: the real example fingerprints + perturbed copies (enough to train IVF-PQ)."""
    d = tmp_path_factory.mktemp("big")
    m, V, rec = FX.read_tables([tables / "af.parquet", tables / "pdb.parquet"])
    rng = np.random.default_rng(0)
    rows, vecs = [m], [V]
    n = len(V)
    while sum(len(v) for v in vecs) < 1200:
        W = V + rng.normal(scale=0.08, size=V.shape).astype(np.float32)
        vecs.append(W / np.linalg.norm(W, axis=1, keepdims=True))
        k = len(rows)
        rows.append(m.assign(pocket_id=m.pocket_id + f":j{k}"))
    M = pd.concat(rows, ignore_index=True)
    X = np.vstack(vecs).astype(np.float32)
    FX.write_table(d / "big.parquet", M, X, rec)
    return d, M, X, n


@need_faiss
def test_index_and_search_flat(tables, big_table, tmp_path):
    d, M, X, n = big_table
    ix = tmp_path / "flat"
    assert cli.main(["index", str(d / "big.parquet"), "-o", str(ix)]) == 0
    hits = tmp_path / "hits.parquet"
    assert cli.main(["search", str(tables / "af.parquet"), str(ix), "-k", "5", "-o", str(hits)]) == 0
    h = pd.read_parquet(hits)
    mq, Q, _ = FX.read_table(tables / "af.parquet")
    S = Q @ X.T
    for qi, g in h.groupby("query_id", sort=False):
        i = int(np.flatnonzero(mq.pocket_id == qi)[0])
        exp = np.sort(S[i])[::-1][:5]
        np.testing.assert_allclose(g.score.to_numpy(), exp, atol=1e-5)
        assert g.hit_id.iloc[0] == qi                          # a pocket finds itself first
    assert cli.main(["search", str(tables / "af.parquet"), str(ix), "-k", "5", "--exclude-self", "-o",
                     str(hits)]) == 0
    h = pd.read_parquet(hits)
    assert (h.hit_id != h.query_id).all() and h.groupby("query_id").size().eq(5).all()


@need_faiss
def test_index_and_search_ivfpq(tables, big_table, tmp_path):
    d, M, X, n = big_table
    ix = tmp_path / "pq"
    assert cli.main(["index", str(d / "big.parquet"), "-o", str(ix), "--kind", "ivfpq", "--nlist", "8",
                     "--pq-m", "32"]) == 0
    info = FX.Index(ix).info
    assert info["factory"] == "OPQ32_384,IVF8,PQ32" and info["n"] == len(X)
    hits = tmp_path / "hits.parquet"
    assert cli.main(["search", str(d / "big.parquet"), str(ix), "-k", "10", "--nprobe", "8", "--rerank", "100",
                     "-o", str(hits)]) == 0
    h = pd.read_parquet(hits)
    S = X @ X.T
    top = np.argsort(-S, 1)[:, :10]
    got = h.pivot(index="query_id", columns="rank", values="hit_row").loc[M.pocket_id].to_numpy()
    assert FX.recall_at_k(got, top, 10) > 0.95
    sc = h.pivot(index="query_id", columns="rank", values="score").loc[M.pocket_id].to_numpy()
    np.testing.assert_allclose(sc, np.take_along_axis(S, got, 1), atol=2e-3)   # exact re-rank (fp16 vectors)


def test_python_m_entrypoint(tables):
    r = subprocess.run([sys.executable, "-m", "pocketcompare", "compare", str(tables / "af.parquet"),
                        str(tables / "af.parquet"), "--print", "3"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    assert "1.0000" in r.stdout
    exe = Path(sys.executable).with_name("pocketcompare")
    if exe.exists():
        r = subprocess.run([str(exe), "--help"], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0 and "describe" in r.stdout


def test_examples_present():
    for f in ("pdb/1a28_A.pdb", "pdb/1a28_STR.pdb", "afdb/AF-P00918-F1-model_v6.cif.gz",
              "afdb/AF-P06401-F1-model_v6.cif.gz"):
        assert (EX / f).is_file()
