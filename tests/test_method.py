"""Final-method API (pocketcompare.method): the describe() path reproduces the evaluated vectors, invariance to
rigid motions, determinism, identity = maximum similarity, config hash verification."""
import dataclasses
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
from scipy.spatial.transform import Rotation  # noqa: E402

method = pytest.importorskip("pocketcompare.method")
from pocketcompare import a4b as A4  # noqa: E402
from pocketcompare import pockets as pk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
EX = PD / "release/burrow/examples/1a28_A.pdb"
MIRROR_1A28 = Path("/cluster/scratch/jjaenes/pdb/a2/1a28.cif.gz")
need_1a28 = pytest.mark.skipif(not (EX.exists() and MIRROR_1A28.exists()), reason="1a28 inputs not mounted")
BLIPS_INDEX = ROOT / "data/processed/cache/points/blips/index.parquet"
need_blips = pytest.mark.skipif(not (BLIPS_INDEX.exists() and (A4.a1r_dir("blips") / "ids.parquet").exists()),
                                reason="BLiPS point cache / a1r descriptors not available")


@pytest.fixture(scope="module")
def M():
    return method.Method()


@pytest.fixture(scope="module")
def real():
    from pocketdetect.structure import load_structure
    s0 = load_structure(str(EX))
    s = load_structure(str(MIRROR_1A28))
    m = (s.res_name == "STR") & (s.chain == "A") & ~s.is_hydrogen
    lig = s.coords[m].astype(np.float64)
    R, t = Rotation.random(random_state=11).as_matrix(), np.array([12.0, -30.0, 4.5])
    moved = dataclasses.replace(s0, coords=(s0.coords.astype(np.float64) @ R.T + t).astype(s0.coords.dtype))
    fa, fb = pk.featurize_structure(s0), pk.featurize_structure(moved)
    return fa, fb, lig, lig @ R.T + t


@need_blips
@pytest.mark.parametrize("mode", ["L", "D"])
def test_describe_path_reproduces_evaluated_vectors(M, mode):
    """Method.raw_parts on a cached structure == the a1r descriptors that were evaluated (same embedding)."""
    ix = pd.read_parquet(BLIPS_INDEX)
    ids = A4.ids_table("blips")
    rows = ids[ids.d_match].pocket_id.iloc[:6].tolist() if mode == "D" else ids.pocket_id.iloc[:6].tolist()
    ix = ix.set_index("pocket_id").loc[rows]
    got = []
    for pid, r in ix.iterrows():
        fs = pk.Featurized.load(ROOT / r.cache_file)
        L = np.asarray(r.lmode_idx, np.int64)
        if mode == "L":
            base = L
        else:
            m, _ = pk.best_member(fs, L, list(r.d_members))
            base = fs.pocket_idx(m)
        got.append(M.raw_parts(fs, base))
    mats = [np.vstack([g[k] for g in got]) for k in range(len(M.parts))]
    ref = A4.raw_parts("blips", mode, rows, M.inp)
    for a, b in zip(mats, ref):
        np.testing.assert_allclose(a, b, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(M.embed(mats), M.embed(ref), atol=1e-5)


@need_1a28
def test_rigid_motion_invariance(M, real):
    fa, fb, lig_a, lig_b = real
    va, vb = M.describe(fa, site=lig_a), M.describe(fb, site=lig_b)
    assert va.shape == (1, M.dim)
    assert M.similarity(va[0], vb[0]) > 0.995
    # D mode, ligand-located BURROW pocket
    da, db = M.describe(fa, site=lig_a, locate="burrow"), M.describe(fb, site=lig_b, locate="burrow")
    assert M.similarity(da[0], db[0]) > 0.995


@need_1a28
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


def test_similarity_shapes(M):
    rng = np.random.default_rng(0)
    A = rng.normal(size=(3, M.dim)).astype(np.float32)
    A /= np.linalg.norm(A, axis=1, keepdims=True)
    assert isinstance(M.similarity(A[0], A[1]), float)
    assert M.similarity(A, A).shape == (3, 3)
    assert M.similarity(A[0], A).shape == (1, 3)


def test_config_hash_is_verified(tmp_path):
    import yaml
    cfg = yaml.safe_load(method.CONFIG.read_text())
    k = next(iter(cfg["files_sha256"]))
    cfg["files_sha256"][k] = "0" * 64
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(cfg))
    with pytest.raises(RuntimeError, match="sha256"):
        method.Method(p)
