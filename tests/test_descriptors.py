"""A1 descriptor, baselines and similarity helpers (DESIGN §3 A1, §5 toy/geometry tests).

Real-structure tests use BURROW's example 1a28_A.pdb + the crystal progesterone (PDB mirror 1a28, STR chain A),
as tests/test_pockets.py does; cache-based tests use the TOUGH-M1 point cache when present."""
import dataclasses
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
from scipy.spatial.transform import Rotation  # noqa: E402

from pocketcompare.descriptors import a1 as A1  # noqa: E402
from pocketcompare.descriptors import baselines as BL  # noqa: E402
from pocketcompare import similarity as SIM  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
EX = PD / "release/burrow/examples/1a28_A.pdb"
MIRROR_1A28 = Path("/cluster/scratch/jjaenes/pdb/a2/1a28.cif.gz")
CACHE = ROOT / "data/processed/cache/points/tough_m1"
need_struct = pytest.mark.skipif(not (EX.exists() and MIRROR_1A28.exists()), reason="1a28 inputs not mounted")
need_cache = pytest.mark.skipif(not (CACHE / "index.parquet").exists(), reason="TOUGH-M1 point cache missing")


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


# ------------------------------------------------------------------------------------------ real structure
@pytest.fixture(scope="module")
def real():
    pk = pytest.importorskip("pocketcompare.pockets")
    from pocketdetect.structure import load_structure
    fs = pk.featurize_structure(EX)
    s = load_structure(str(MIRROR_1A28))
    m = (s.res_name == "STR") & (s.chain == "A") & ~s.is_hydrogen
    lig = s.coords[m].astype(np.float64)
    R, t = Rotation.random(random_state=3).as_matrix(), np.array([12.0, -30.0, 7.5])
    s0 = load_structure(str(EX))
    g = pk.featurize_structure(dataclasses.replace(s0, coords=(s0.coords.astype(np.float64) @ R.T + t)
                                                   .astype(s0.coords.dtype)))
    lp_a = pk.lmode_from_ligand(fs, lig)
    lp_b = pk.lmode_from_ligand(g, lig @ R.T + t)
    return fs, g, lp_a.idx, lp_b.idx


@need_struct
@pytest.mark.parametrize("name", ["default", "hard_typing", "no_resample", "resample_3A"])
def test_rotation_translation_invariance(real, name):
    import yaml
    fs, g, ia, ib = real
    assert len(ia) == len(ib) > 100
    cfg = A1.make_config(yaml.safe_load((ROOT / "configs/a1_grid.yaml").read_text())["configs"][name])
    va, _ = A1.a1_descriptor(A1.pocket_input(fs, ia), cfg)
    vb, _ = A1.a1_descriptor(A1.pocket_input(g, ib), cfg)
    assert rel(va, vb) < 1e-4, rel(va, vb)
    b1a, _ = BL.b1_descriptor(fs, ia)
    b1b, _ = BL.b1_descriptor(g, ib)
    assert rel(b1a, b1b) < 1e-4


@need_struct
def test_point_order_invariance_and_determinism(real):
    fs, _, ia, _ = real
    cfg = A1.make_config()
    v1, _ = A1.a1_descriptor(A1.pocket_input(fs, ia), cfg)
    v2, _ = A1.a1_descriptor(A1.pocket_input(fs, ia), cfg)
    assert v1.tobytes() == v2.tobytes()                                         # deterministic
    perm = np.random.default_rng(0).permutation(ia)
    for c in (cfg, A1.make_config({"resample": None}), A1.make_config({"typing": {"mode": "hard"}})):
        a, _ = A1.a1_descriptor(A1.pocket_input(fs, ia), c)
        b, _ = A1.a1_descriptor(A1.pocket_input(fs, perm), c)
        assert rel(a, b) < 1e-5


@need_struct
def test_identity_and_type_permuted_copy(real):
    fs, _, ia, _ = real
    cfg = A1.make_config()
    at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
    t = {n: i for i, n in enumerate(A1.ATOM_TYPES)}
    swap = np.arange(len(A1.ATOM_TYPES))
    for x, y in (("hyd", "neg"), ("aro", "don"), ("acc", "pos")):
        swap[t[x]], swap[t[y]] = t[y], t[x]
    v, _ = A1.a1_descriptor(A1.pocket_input(fs, ia, atom_types=at), cfg)
    vp, _ = A1.a1_descriptor(A1.pocket_input(fs, ia, atom_types=swap[at]), cfg)
    # z-score reference: the pockets BURROW found on the same structure (label-free background)
    bg = [A1.a1_descriptor(A1.pocket_input(fs, fs.pocket_idx(i), atom_types=at), cfg)[0]
          for i in range(fs.n_pockets) if len(fs.pocket_idx(i)) >= 10]
    D = np.vstack([v, vp] + bg)
    E = SIM.embed(D, SIM.ZScorer.fit(D[2:]))
    assert float(E[0] @ E[0]) == pytest.approx(1.0, abs=1e-6)
    s_perm = float(E[0] @ E[1])
    assert s_perm < 0.9
    E2 = SIM.embed(D, SIM.ZScorer.fit(D[2:]), A1.a1_layout(cfg), cfg["score_weights"])
    assert float(E2[0] @ E2[0]) == pytest.approx(1.0, abs=1e-6) and float(E2[0] @ E2[1]) < 0.95


@need_struct
def test_timing_default_under_50ms(real):
    fs, _, ia, _ = real
    cfg = A1.make_config()
    at = A1.atom_type_codes(fs.res_names[fs.atom_res], fs.atom_name, fs.atom_element)
    A1.a1_descriptor(A1.pocket_input(fs, ia, atom_types=at), cfg)
    ts = []
    for _ in range(5):
        t0 = time.perf_counter()
        A1.a1_descriptor(A1.pocket_input(fs, ia, atom_types=at), cfg)
        ts.append(time.perf_counter() - t0)
    assert np.median(ts) < 0.05


@need_cache
def test_cached_pocket_metal_channel_and_dmode():
    idx = pd.read_parquet(CACHE / "index.parquet")
    from pocketcompare.pockets import Featurized
    hit = None
    for _, r in idx.iloc[:400].iterrows():
        z = np.load(ROOT / r.cache_file)
        if z["is_metal"][np.asarray(r.lmode_idx)].any():
            hit = r
            break
    if hit is None:
        pytest.skip("no metal-candidate pocket in the first 400")
    fs = Featurized.load(ROOT / hit.cache_file)
    cfg = A1.make_config({"blocks": ["hist"], "hellinger": False})
    v, lay = A1.a1_descriptor(A1.pocket_input(fs, hit.lmode_idx), cfg)
    met = [x for n, x in zip(lay[0].names, v) if n.startswith("hist:met:")]
    assert sum(met) > 0


# ------------------------------------------------------------------------------------------ baselines
def test_b1_columns():
    from pocketdetect.burrow.model import pocket_features  # noqa: F401
    names = ['n_pts', 'vol', 'sqrt_vol', 'sat_vol', 'score_sum', 'score_sqrt', 'score_mean', 'score_max',
             'score_top10', 'score_top30', 'score_q50', 'score_rank', 'score_rel', 'geo_strength', 'bur10_mean',
             'bur16_mean', 'bur24_mean', 'burbb10_mean', 'burbb16_mean', 'depth_mean', 'psp_mean', 'nearest_mean',
             'bur16_q90', 'bur16_q10', 'bur24_q90', 'bur24_q10', 'hit_apolar', 'hit_polar', 'hit_charged',
             'hit_aromatic', 'escape', 'n_all8', 'n_all12', 'n4_rg_aliphatic', 'n4_rg_aromatic', 'n4_rg_polar',
             'n4_rg_positive', 'n4_rg_negative', 'n4_rg_his_cys', 'n4_rg_gly_pro_other', 'f8_C', 'f8_N', 'f8_O',
             'f8_S', 'f8_aromatic', 'f8_hydrophobic_sc_C', 'f8_donor', 'f8_acceptor', 'f8_backbone',
             'f8_sidechain', 'f8_positive', 'f8_negative', 'f8_rg_aliphatic', 'f8_rg_aromatic', 'f8_rg_polar',
             'f8_rg_positive', 'f8_rg_negative', 'f8_rg_his_cys', 'f8_rg_gly_pro_other', 'f8_wcn', 'f8_coord',
             'prot_frac', 'metal_n', 'n_coord_max', 'pca1', 'pca2', 'pca3', 'aniso', 'extent', 'n_res',
             'n_chains', 'level', 'is_sub', 'is_score_src', 'n_atoms_prot', 'log_atoms']
    d = BL.b1_columns(names)
    lrn = BL.b1_columns(names, learned=True)
    assert len(names) == 76 and len(d) == 45 and len(lrn) == 50
    assert not any(c.startswith("score_") for c in d)
    assert set(lrn) - set(d) == set(BL.B1_LEARNED_SIZE_FREE)
    assert not {"vol", "n_pts", "pca1", "extent", "log_atoms", "prot_frac", "geo_strength"} & set(lrn)
    assert np.allclose(BL.b0_pair_scores(np.log([100.0, 200.0, 100.0]), [0, 0], [1, 2]), [-np.log(2), 0])


# ------------------------------------------------------------------------------------------ similarity
def test_zscore_reference_and_block_weighted_cosine():
    rng = np.random.default_rng(0)
    D = rng.normal(size=(50, 7)) * [1, 2, 3, 4, 5, 6, 0] + 3
    ids = np.array([f"p{i}" for i in range(50)])
    zs = SIM.ZScorer.fit(D, ids, ids[:20])
    assert np.allclose(zs.mean[:6], D[:20, :6].mean(0)) and zs.std[6] == 0
    Z = zs.transform(D)
    assert np.all(Z[:, 6] == 0)
    lay = [{"name": "a", "start": 0, "stop": 3}, {"name": "b", "start": 3, "stop": 7}]
    E = SIM.embed(D, zs, lay, {"a": 1.0, "b": 3.0})
    i, j = 4, 9
    ca = cos(Z[i, :3], Z[j, :3])
    cb = cos(Z[i, 3:6], Z[j, 3:6])
    assert float(E[i] @ E[j]) == pytest.approx((ca + 3 * cb) / 4, abs=1e-6)
    assert np.allclose(np.linalg.norm(E, axis=1), 1, atol=1e-6)
    E0 = SIM.embed(D, zs)
    assert float(E0[i] @ E0[j]) == pytest.approx(cos(Z[i], Z[j]), abs=1e-6)


def test_pair_scores_and_csls():
    rng = np.random.default_rng(1)
    E = SIM.l2_normalise(rng.normal(size=(200, 16))).astype(np.float32)
    ids = np.arange(200)
    i = rng.integers(0, 200, 5000)
    j = rng.integers(0, 200, 5000)
    S = E @ E.T
    assert np.allclose(SIM.pair_scores(E, i, j, batch=777), S[i, j], atol=1e-6)
    bg = np.arange(0, 200, 2)
    r = SIM.csls_r(E, E[bg], k=10, query_ids=ids, bg_ids=ids[bg], batch=33)
    for q in (0, 1, 50):
        row = S[q, bg].copy()
        row[bg == q] = -np.inf
        assert r[q] == pytest.approx(np.sort(row)[-10:].mean(), abs=1e-6)
    c = SIM.csls_pair_scores(E, i, j, r)
    assert np.allclose(c, S[i, j] - 0.5 * (r[i] + r[j]), atol=1e-6)
