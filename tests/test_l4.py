"""L4 point-cloud encoder: E(3) invariance, determinism, padding/order invariance, FPS (synthetic data only)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from pocketcompare import l4 as L4  # noqa: E402

CFG = {"layers": 3, "hidden": 32, "k": 16, "n_rbf": 16, "r_max": 12.0, "update_x": True, "out_dim": 128,
       "dropout": 0.1, "concat_n1": False}


def _cloud(rng, m, F=93):
    p = rng.normal(scale=4.0, size=(m, 3)).astype(np.float32)
    h = rng.normal(size=(m, F)).astype(np.float32)
    h[:, -1] = np.log(rng.choice([1.0, 27.0], size=m))
    return p, h


def _orth(rng, reflect=False):
    Q, R = np.linalg.qr(rng.normal(size=(3, 3)))
    Q = Q * np.sign(np.diag(R))
    if (np.linalg.det(Q) < 0) != reflect:
        Q[:, 0] *= -1
    return Q.astype(np.float32)


def _embed(model, sets):
    X, H, M = L4.pad_batch(sets)
    with torch.no_grad():
        return model(torch.from_numpy(X).double(), torch.from_numpy(H).double(), torch.from_numpy(M).double()).numpy()


@pytest.mark.parametrize("update_x", [True, False])
def test_e3_invariance(update_x):
    rng = np.random.default_rng(0)
    torch.manual_seed(0)
    model = L4.build_model({**CFG, "update_x": update_x}, 93).double().eval()
    sets = [_cloud(rng, m) for m in (30, 120, 256)]
    z0 = _embed(model, sets)
    assert np.allclose(np.linalg.norm(z0, axis=1), 1.0, atol=1e-9)
    for k in range(5):
        moved = [((p @ _orth(rng, reflect=k == 4).T + rng.normal(scale=20, size=3)).astype(np.float32), h)
                 for p, h in sets]
        z1 = _embed(model, moved)
        assert np.abs(z1 - z0).max() < 1e-4, np.abs(z1 - z0).max()


def test_permutation_and_padding_invariance():
    rng = np.random.default_rng(1)
    torch.manual_seed(1)
    model = L4.build_model(CFG, 93).double().eval()
    p, h = _cloud(rng, 80)
    perm = rng.permutation(80)
    z0 = _embed(model, [(p, h)])
    z1 = _embed(model, [(p[perm], h[perm]), _cloud(rng, 200)])[:1]   # other batch member, other padding
    assert np.abs(z1 - z0).max() < 1e-6


def test_random_rotations_are_rotations():
    R = L4.random_rotations(64).double()
    eye = torch.eye(3, dtype=torch.float64).expand(64, 3, 3)
    assert torch.allclose(R @ R.transpose(1, 2), eye, atol=1e-5)
    assert torch.allclose(torch.det(R), torch.ones(64, dtype=torch.float64), atol=1e-5)


def test_fps_deterministic_and_invariant():
    rng = np.random.default_rng(2)
    p = rng.normal(scale=5, size=(700, 3))
    w = rng.choice([1.0, 27.0], size=700)
    s0 = L4.fps(p, w, 256)
    assert len(s0) == 256 and len(np.unique(s0)) == 256
    assert np.array_equal(s0, L4.fps(p, w, 256))
    s1 = L4.fps(p @ _orth(rng).T + 3.0, w, 256)
    assert len(np.intersect1d(s0, s1)) >= 250            # identical up to float ties
    assert np.array_equal(L4.fps(p[:100], w[:100], 256), np.arange(100))
