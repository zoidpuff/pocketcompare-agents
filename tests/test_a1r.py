"""Ligand-free site shapers (pockets.shape_site & co.) and the A1r env block: invariances (D11 exploration).

Uses BURROW's example 1a28_A.pdb + crystal progesterone as tests/test_pockets.py; a rigidly moved in-memory copy
must give the same site (shapers) and the same descriptor (env, A1 on the shaped site)."""
import dataclasses
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
from scipy.spatial import cKDTree  # noqa: E402
from scipy.spatial.transform import Rotation  # noqa: E402

pk = pytest.importorskip("pocketcompare.pockets")
from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import a1r  # noqa: E402

PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
EX = PD / "release/burrow/examples/1a28_A.pdb"
MIRROR_1A28 = Path("/cluster/scratch/jjaenes/pdb/a2/1a28.cif.gz")
need = pytest.mark.skipif(not (EX.exists() and MIRROR_1A28.exists()), reason="1a28 inputs not mounted")


@pytest.fixture(scope="module")
def real():
    from pocketdetect.structure import load_structure
    fs = pk.featurize_structure(EX)
    s = load_structure(str(MIRROR_1A28))
    m = (s.res_name == "STR") & (s.chain == "A") & ~s.is_hydrogen
    lig = s.coords[m].astype(np.float64)
    R, t = Rotation.random(random_state=5).as_matrix(), np.array([-7.0, 25.0, 3.5])
    s0 = load_structure(str(EX))
    g = pk.featurize_structure(dataclasses.replace(s0, coords=(s0.coords.astype(np.float64) @ R.T + t)
                                                   .astype(s0.coords.dtype)))
    la = pk.lmode_from_ligand(fs, lig).idx
    lb = pk.lmode_from_ligand(g, lig @ R.T + t).idx
    j = cKDTree(g.points).query(fs.points.astype(np.float64) @ R.T + t)[1]    # point map fs -> g
    return fs, g, la, lb, j, R, t


def _jacc(a, b):
    a, b = set(np.asarray(a).tolist()), set(np.asarray(b).tolist())
    return len(a & b) / max(len(a | b), 1)


@need
@pytest.mark.parametrize("shaper", list(pk.SHAPERS))
def test_shaper_rigid_motion_invariance(real, shaper):
    fs, g, la, lb, j, R, t = real
    A = pk.shape_site(fs, la, shaper)
    B = pk.shape_site(g, lb, shaper)
    assert len(A) > 20
    # same points up to boundary flips of float32 features / distances
    assert _jacc(j[A], B) > 0.98, (shaper, _jacc(j[A], B))


@need
def test_centroid_equivariance(real):
    fs, g, la, lb, j, R, t = real
    ca, cb = pk.buried_centroid(fs, la), pk.buried_centroid(g, lb)
    assert np.linalg.norm(ca @ R.T + t - cb) < 1e-3


@need
def test_shapers_are_ligand_free_and_nested(real):
    fs, _, la, _, _, _, _ = real
    bur = fs.feature("bur10")
    for sh in ("res", "sph6", "sph8", "sph10"):
        assert (bur[pk.shape_site(fs, la, sh)] >= 0.5).all()
    s6, s8, s10 = (set(pk.shape_site(fs, la, f"sph{r}").tolist()) for r in (6, 8, 10))
    assert s6 <= s8 <= s10
    assert set(pk.shape_site(fs, la, "core8").tolist()) <= set(la.tolist())
    # sphere sites depend on the located set only through its centre: a sub-sampled locator with the same
    # buried centroid region gives (nearly) the same sphere
    half = la[::2]
    assert _jacc(pk.shape_site(fs, la, "sph8"), pk.shape_site(fs, half, "sph8")) > 0.8


@need
def test_env_invariances(real):
    fs, g, la, lb, j, R, t = real
    for sh in ("base", "sph8", "res"):
        A, B = pk.shape_site(fs, la, sh), pk.shape_site(g, lb, sh)
        va, vb = a1r.env_descriptor(fs, A), a1r.env_descriptor(g, B)
        assert va.shape == (a1r.env_layout()[-1]["stop"],)
        assert np.linalg.norm(va - vb) / np.linalg.norm(va) < 0.02, sh
    perm = np.random.default_rng(0).permutation(la)
    assert np.allclose(a1r.env_descriptor(fs, la), a1r.env_descriptor(fs, perm), atol=1e-6)
    h = a1r.env_descriptor(fs, la)
    lay = {b["name"]: b for b in a1r.env_layout()}
    mass = h[lay["env_hist"]["stop"] - 3:lay["env_hist"]["stop"]]
    assert abs(mass.sum() - 1.0) < 1e-5


@need
def test_a1_on_sphere_site_rigid_invariance(real):
    fs, g, la, lb, j, R, t = real
    A, B = pk.shape_site(fs, la, "sph8"), pk.shape_site(g, lb, "sph8")
    if set(j[A].tolist()) != set(B.tolist()):
        pytest.skip("boundary flip changed the point set; covered by the Jaccard test")
    va, _ = A1.a1_descriptor(A1.pocket_input(fs, A))
    vb, _ = A1.a1_descriptor(A1.pocket_input(g, B))
    assert np.linalg.norm(va - vb) / np.linalg.norm(va) < 1e-4
