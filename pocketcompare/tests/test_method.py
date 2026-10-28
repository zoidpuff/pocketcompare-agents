"""Public API: invariance to rigid motions, determinism, identity = maximum similarity, file verification."""
import dataclasses

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from conftest import AF_CA2, AF_PR, LIG, PDB
from pocketcompare import method
from pocketcompare import pockets as pk


@pytest.fixture(scope="module")
def real():
    from pocketdetect.structure import load_structure
    s0 = load_structure(str(PDB))
    lig, _ = pk.read_ligand_heavy_atoms(LIG)
    R, t = Rotation.random(random_state=11).as_matrix(), np.array([12.0, -30.0, 4.5])
    moved = dataclasses.replace(s0, coords=(s0.coords.astype(np.float64) @ R.T + t).astype(s0.coords.dtype))
    fa, fb = pk.featurize_structure(s0), pk.featurize_structure(moved)
    return fa, fb, lig, lig @ R.T + t


def test_rigid_motion_invariance(M, real):
    fa, fb, lig_a, lig_b = real
    va, vb = M.describe(fa, site=lig_a), M.describe(fb, site=lig_b)
    assert va.shape == (1, M.dim)
    assert M.similarity(va[0], vb[0]) > 0.995
    da, db = M.describe(fa, site=lig_a, locate="burrow"), M.describe(fb, site=lig_b, locate="burrow")
    assert M.similarity(da[0], db[0]) > 0.995
    Va, ia = M.describe_all(fa)
    Vb, ib = M.describe_all(fb)
    assert list(ia.burrow_rank) == list(ib.burrow_rank)
    assert (np.einsum("nd,nd->n", Va, Vb) > 0.99).all()


def test_determinism_and_identity_is_max(M, real):
    fa, _, lig, _ = real
    V1, info = M.describe(fa, return_info=True)
    V2 = M.describe(fa)
    assert np.array_equal(V1, V2)
    assert len(V1) == int(fa.pk_in_region.sum()) == len(info)
    v = M.describe(fa, site=lig)
    assert np.array_equal(v, M.describe(fa, site=lig))
    ok = np.linalg.norm(V1, axis=1) > 0
    S = M.similarity(V1[ok], V1[ok])
    np.testing.assert_allclose(np.diag(S), 1.0, atol=1e-5)
    assert (np.diag(S)[:, None] >= S - 1e-6).all()
    assert abs(M.similarity(v[0], v[0]) - 1.0) < 1e-5
    assert M.similarity(v[0], v[0]) >= M.similarity(v, V1[ok]).max() - 1e-6


def test_file_path_equals_featurized_and_repeat_runs(M):
    V1, _ = M.describe_all(PDB)
    V2, _ = method.describe_all(str(PDB))
    assert np.array_equal(V1, V2)


def test_holo_site_finds_the_same_pocket_in_the_alphafold_model(M):
    """The progesterone site of the crystal structure retrieves the steroid pocket of the receptor's AlphaFold model
    first, and scores the unrelated carbonic anhydrase model's pockets much lower."""
    v = M.describe(PDB, site=str(LIG))
    W, info = M.describe_all(AF_PR, af_mode=True)
    C, _ = M.describe_all(AF_CA2, af_mode=True)
    s = M.similarity(v, W)[0]
    top = int(np.argmax(s))
    assert s[top] > 0.9 and "A:725" in info.residues[top].split()
    assert M.similarity(v, C).max() < s[top] - 0.5


def test_similarity_shapes(M):
    rng = np.random.default_rng(0)
    A = rng.normal(size=(3, M.dim)).astype(np.float32)
    A /= np.linalg.norm(A, axis=1, keepdims=True)
    assert isinstance(M.similarity(A[0], A[1]), float)
    assert M.similarity(A, A).shape == (3, 3)
    assert M.similarity(A[0], A).shape == (1, 3)


def test_config_hash_is_verified(tmp_path):
    import shutil

    import yaml
    from pocketcompare.resources import data_root
    root = tmp_path / "root"
    shutil.copytree(data_root() / "models", root / "models")
    (root / "configs").mkdir()
    cfg = yaml.safe_load((data_root() / "configs/final_method.yaml").read_text())
    p = root / "configs/ok.yaml"
    p.write_text(yaml.safe_dump(cfg))
    assert method.Method(p).dim == 384
    k = next(iter(cfg["files_sha256"]))
    cfg["files_sha256"][k] = "0" * 64
    p = root / "configs/bad.yaml"
    p.write_text(yaml.safe_dump(cfg))
    with pytest.raises(RuntimeError, match="sha256"):
        method.Method(p)


def test_empty_site_raises(M, real):
    fa, _, lig, _ = real
    with pytest.raises(ValueError):
        M.describe(fa, site=lig + 500.0)
