"""A1 and env descriptors: known answers on synthetic pockets, sampling/size behaviour, and invariances of the
sph8 shaper and the env block on a real structure (ported from the research test suite)."""
import dataclasses

import numpy as np
import pytest
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from conftest import LIG, PDB
from pocketcompare import pockets as pk
from pocketcompare.descriptors import a1 as A1
from pocketcompare.descriptors import env as ENV


def rel(a, b):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    return np.linalg.norm(a - b) / max(np.linalg.norm(a), 1e-12)


def cos(a, b):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def block(v, cfg, name):
    b = next(b for b in A1.a1_layout(cfg) if b.name == name)
    return v[b.start:b.stop]


# ------------------------------------------------------------------------------------------ synthetic pockets
FEATS = ("bur6", "bur10", "bur16", "burbb16", "depth", "escape", "nearest")
def _attrs(P, axes):
    rn = np.sqrt(((P / np.asarray(axes)) ** 2).sum(1))
    T = np.zeros((len(P), 8))
    T[P[:, 0] > 0, 0] = 1.0                                      # hydrophobic half
    T[(P[:, 0] <= 0) & (P[:, 1] > 0), 2] = 1.0                   # donor quarter
    T[(P[:, 0] <= 0) & (P[:, 1] <= 0), 3] = 0.7                  # acceptor quarter (soft)
    T[(P[:, 0] <= 0) & (P[:, 1] <= 0), 6] = 0.3                  # ... with some negative
    bur = np.clip(1.0 - rn, 0, 1)
    return T, {f: bur.copy() for f in FEATS}


def ellipsoid(axes, thin=False, frac=0.6):
    """Points of a filled ellipsoid on a 1 Å grid at half-integer coordinates (like BURROW's canonical frame).
    thin=True: 3x3x3 blocks lying fully inside with centre radius > frac are replaced by their centre voxel with
    vol = 27 (BURROW's exposed sub-lattice thinning); the dense copy holds exactly the same voxels."""
    ax = np.asarray(axes, float)
    rng = [np.arange(-np.ceil(a) - 3, np.ceil(a) + 4) for a in ax]
    G = np.stack(np.meshgrid(*rng, indexing="ij"), -1).reshape(-1, 3).astype(np.int64)
    P = G + 0.5
    inside = ((P / ax) ** 2).sum(1) <= 1.0
    G, P = G[inside], P[inside]
    vol = np.ones(len(P))
    if thin:
        blk = np.floor_divide(G, 3)
        keys, inv = np.unique(blk, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        full = np.bincount(inv, minlength=len(keys)) == 27
        ctr = keys * 3 + 1 + 0.5
        exposed = full & (np.sqrt(((ctr / ax) ** 2).sum(1)) > frac)
        is_ctr = np.all(np.mod(G, 3) == 1, axis=1)
        drop = exposed[inv] & ~is_ctr
        P, G = P[~drop], G[~drop]
        vol = np.where(exposed[inv][~drop], 27.0, 1.0)
    T, feats = _attrs(P, axes)
    return A1.PocketInput(xyz=P, X=P, vol=vol, is_metal=np.zeros(len(P), bool), feats=feats, point_types=T)


# ------------------------------------------------------------------------------------------ known answers
def test_pair_histogram_two_points_known_distance():
    r = np.linspace(2.0, 20.0, 14)
    for k in (0, 5, 13):
        C = np.array([[0.0, 0.0, 0.0], [r[k], 0.0, 0.0]])
        H = A1.pair_histogram(C, np.ones((2, 1)), 2.0, 20.0, 14, 1.0)[0, 0] / 2.0     # W^2 - sum w^2 = 2
        assert H.sum() == pytest.approx(1.0, abs=1e-12)
        assert int(np.argmax(H)) == k
        if 0 < k < 13:
            assert H[k - 1] == pytest.approx(H[k + 1], rel=1e-9)                       # symmetric smoothing
            g = np.exp(-((r - r[k]) ** 2) / 2.0)
            assert np.allclose(H, g / g.sum(), atol=1e-12)                              # exact Gaussian weights
    far = A1.pair_histogram(np.array([[0, 0, 0], [60.0, 0, 0]]), np.ones((2, 1)), 2, 20, 14, 1.0)[0, 0]
    near = A1.pair_histogram(np.array([[0, 0, 0], [0.5, 0, 0]]), np.ones((2, 1)), 2, 20, 14, 1.0)[0, 0]
    assert far[-1] == pytest.approx(2.0)                                               # open last bin
    assert int(np.argmax(near)) == 0 and near[0] > 0.9 * 2.0                           # first bin absorbs < r_min


def test_pair_block_through_descriptor_known_answer():
    """Two typed points (hydrophobic, donor) 7.0 Å apart, no resampling: only the shape-shape, shape-hyd,
    shape-don and hyd-don histograms are non-zero, each peaked at the bin nearest 7 Å."""
    P = np.array([[0.5, 0.5, 0.5], [7.5, 0.5, 0.5]])
    T = np.zeros((2, 8))
    T[0, 0] = 1.0
    T[1, 2] = 1.0
    pin = A1.PocketInput(xyz=P, X=P, vol=np.ones(2), is_metal=np.zeros(2, bool),
                         feats={f: np.ones(2) for f in FEATS}, point_types=T)
    cfg = A1.make_config({"resample": None, "blocks": ["pair"], "hellinger": False})
    v, lay = A1.a1_descriptor(pin, cfg)
    names = lay[0].names
    r = np.linspace(2, 20, 14)
    k = int(np.argmin(np.abs(r - 7.0)))
    g = np.exp(-((r - 7.0) ** 2) / 2.0)
    g /= g.sum()
    H = {n.rsplit(":", 1)[0]: [] for n in names}
    for n, x in zip(names, v):
        H[n.rsplit(":", 1)[0]].append(x)
    assert np.allclose(H["pair:shape-shape"], g, atol=1e-6)
    assert np.allclose(H["pair:shape-hyd"], 0.5 * g, atol=1e-6)      # ordered pairs (i,j): only i=hyd counts
    assert np.allclose(H["pair:hyd-don"], 0.5 * g, atol=1e-6)
    assert np.allclose(H["pair:hyd-hyd"], 0) and np.allclose(H["pair:acc-neg"], 0)
    assert int(np.argmax(H["pair:shape-shape"])) == k


def test_atom_typing_table():
    t = {n: i for i, n in enumerate(A1.ATOM_TYPES)}
    cases = [("SER", "OG", "O", "da"), ("PHE", "CZ", "C", "aro"), ("LYS", "NZ", "N", "pos"),
             ("PRO", "N", "N", "null"), ("GLY", "CA", "C", "null"), ("ALA", "N", "N", "don"),
             ("ASP", "OD2", "O", "neg"), ("ARG", "NH1", "N", "pos"), ("LEU", "CD1", "C", "hyd"),
             ("HIS", "NE2", "N", "da"), ("ASN", "OD1", "O", "acc"), ("MSE", "SE", "SE", "hyd"),
             ("XYZ", "C7", "C", "hyd"), ("XYZ", "O1", "O", "acc"), ("ALA", "OXT", "O", "neg")]
    for rn, an, el, want in cases:
        assert A1.atom_type(rn, an, el) == t[want], (rn, an)
    codes = A1.atom_type_codes(["SER", "PHE", "SER"], ["OG", "CZ", "OG"], ["O", "C", "O"])
    assert codes.tolist() == [t["da"], t["aro"], t["da"]]


def test_soft_typing_continuous_at_cutoff():
    """An atom crossing the typing radius changes the type vector continuously (cosine taper)."""
    cfg = A1.make_config()["typing"]
    at = np.array([[0.0, 0, 0]])
    vals = [A1.type_points(np.array([[d, 0, 0]]), at, np.array([1]), cfg)[0, 0] for d in (4.49, 4.4999, 4.5001)]
    assert vals[0] < 0.01 and vals[1] < 1e-6 and vals[2] == 0.0
    assert A1.type_points(np.array([[3.0, 0, 0]]), at, np.array([1]), cfg)[0, 0] == pytest.approx(1.0)


# ------------------------------------------------------------------------------------------ sampling / size
def test_thinned_and_dense_copies_agree_after_resampling():
    """Review round 1 (A1 sampling artefact): BURROW's thinned copy (vol=27 coarse points) and the dense copy of
    the same voxels give the same fingerprint after vol-weighted 2 Å resampling (and visibly less so without)."""
    axes = (12.0, 9.0, 7.0)
    dense, thin = ellipsoid(axes), ellipsoid(axes, thin=True, frac=0.3)
    assert dense.vol.sum() == thin.vol.sum()
    assert 27 * (thin.vol == 27).sum() > 0.4 * thin.vol.sum()          # > 40 % of the volume is thinned
    cfg = A1.make_config()
    vd, _ = A1.a1_descriptor(dense, cfg)
    vt, _ = A1.a1_descriptor(thin, cfg)
    for b in ("hist", "pair", "glob", "size"):
        assert cos(block(vd, cfg, b), block(vt, cfg, b)) > 0.995, b
    assert cos(block(vd, cfg, "usr"), block(vt, cfg, "usr")) > 0.99
    raw = A1.make_config({"resample": None})
    rd, _ = A1.a1_descriptor(dense, raw)
    rt, _ = A1.a1_descriptor(thin, raw)
    # without resampling the pair block of the thinned copy loses its short-distance mass
    assert rel(block(rd, raw, "pair"), block(rt, raw, "pair")) > 3 * rel(block(vd, cfg, "pair"),
                                                                          block(vt, cfg, "pair"))


def test_uniformly_scaled_pocket_size_free_blocks():
    """A 1.5x larger pocket with the same shape, composition and point density: the size-free blocks (type x
    buriedness histogram, global scalars) are unchanged; only size (and the Å-valued pair/USR blocks) move."""
    cfg = A1.make_config()
    a, _ = A1.a1_descriptor(ellipsoid((6.0, 4.0, 3.0)), cfg)
    b, _ = A1.a1_descriptor(ellipsoid((9.0, 6.0, 4.5)), cfg)
    assert cos(block(a, cfg, "hist"), block(b, cfg, "hist")) > 0.995
    assert rel(block(a, cfg, "glob"), block(b, cfg, "glob")) < 0.05
    assert block(b, cfg, "size")[0] - block(a, cfg, "size")[0] == pytest.approx(np.log(1.5 ** 3), abs=0.1)


def test_default_layout_dims():
    cfg = A1.make_config()
    lay = A1.a1_layout(cfg)
    assert lay[-1].stop == 514 and [b.name for b in lay] == ["hist", "pair", "usr", "glob", "size"]
    assert A1.config_hash(cfg) == "8f4f566dbad665ba"          # the frozen method's A1 configuration
    assert ENV.env_layout()[-1]["stop"] == 113


# ------------------------------------------------------------------------------------------ real structure
@pytest.fixture(scope="module")
def real():
    from pocketdetect.structure import load_structure
    fs = pk.featurize_structure(PDB)
    lig, _ = pk.read_ligand_heavy_atoms(LIG)
    R, t = Rotation.random(random_state=5).as_matrix(), np.array([-7.0, 25.0, 3.5])
    s0 = load_structure(str(PDB))
    g = pk.featurize_structure(dataclasses.replace(s0, coords=(s0.coords.astype(np.float64) @ R.T + t)
                                                   .astype(s0.coords.dtype)))
    la = pk.lmode_from_ligand(fs, lig).idx
    lb = pk.lmode_from_ligand(g, lig @ R.T + t).idx
    j = cKDTree(g.points).query(fs.points.astype(np.float64) @ R.T + t)[1]    # point map fs -> g
    return fs, g, la, lb, j, R, t


def _jacc(a, b):
    a, b = set(np.asarray(a).tolist()), set(np.asarray(b).tolist())
    return len(a & b) / max(len(a | b), 1)


@pytest.mark.parametrize("shaper", ["base", "sph8"])
def test_shaper_rigid_motion_invariance(real, shaper):
    fs, g, la, lb, j, R, t = real
    A = pk.shape_site(fs, la, shaper)
    B = pk.shape_site(g, lb, shaper)
    assert len(A) > 20
    assert _jacc(j[A], B) > 0.98, (shaper, _jacc(j[A], B))   # same points up to float32 boundary flips


def test_centroid_equivariance(real):
    fs, g, la, lb, j, R, t = real
    ca, cb = pk.buried_centroid(fs, la), pk.buried_centroid(g, lb)
    assert np.linalg.norm(ca @ R.T + t - cb) < 1e-3


def test_sphere_sites_are_buried_nested_and_ligand_free(real):
    fs, _, la, _, _, _, _ = real
    bur = fs.feature("bur10")
    s6, s8, s10 = (set(pk.shape_site(fs, la, f"sph{r}").tolist()) for r in (6, 8, 10))
    assert (bur[list(s8)] >= 0.5).all()
    assert s6 <= s8 <= s10
    # the located set only gives the centre: a sub-sampled locator gives (nearly) the same sphere
    assert _jacc(pk.shape_site(fs, la, "sph8"), pk.shape_site(fs, la[::2], "sph8")) > 0.8


def test_env_invariances(real):
    fs, g, la, lb, j, R, t = real
    for sh in ("base", "sph8"):
        A, B = pk.shape_site(fs, la, sh), pk.shape_site(g, lb, sh)
        va, vb = ENV.env_descriptor(fs, A), ENV.env_descriptor(g, B)
        assert va.shape == (113,)
        assert np.linalg.norm(va - vb) / np.linalg.norm(va) < 0.02, sh
    perm = np.random.default_rng(0).permutation(la)
    assert np.allclose(ENV.env_descriptor(fs, la), ENV.env_descriptor(fs, perm), atol=1e-6)
    h = ENV.env_descriptor(fs, la)
    lay = {b["name"]: b for b in ENV.env_layout()}
    mass = h[lay["env_hist"]["stop"] - 3:lay["env_hist"]["stop"]]
    assert abs(mass.sum() - 1.0) < 1e-5


def test_a1_point_order_invariance_and_determinism(real):
    fs, _, la, _, _, _, _ = real
    A = pk.shape_site(fs, la, "sph8")
    v1, _ = A1.a1_descriptor(A1.pocket_input(fs, A))
    v2, _ = A1.a1_descriptor(A1.pocket_input(fs, np.random.default_rng(1).permutation(A)))
    np.testing.assert_allclose(v1, v2, rtol=1e-5, atol=1e-6)
    assert np.array_equal(v1, A1.a1_descriptor(A1.pocket_input(fs, A))[0])


def test_a1_on_sphere_site_rigid_invariance(real):
    fs, g, la, lb, j, R, t = real
    A, B = pk.shape_site(fs, la, "sph8"), pk.shape_site(g, lb, "sph8")
    if set(j[A].tolist()) != set(B.tolist()):
        pytest.skip("boundary flip changed the point set; covered by the Jaccard test")
    va, _ = A1.a1_descriptor(A1.pocket_input(fs, A))
    vb, _ = A1.a1_descriptor(A1.pocket_input(g, B))
    assert np.linalg.norm(va - vb) / np.linalg.norm(va) < 1e-4
