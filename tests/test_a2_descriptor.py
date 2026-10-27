"""A2 docking-profile descriptor (src/pocketcompare/descriptors/a2.py).

Synthetic raw docking tables with known structure: rank bins, LE residualisation, per-molecule z-scoring,
reference-set discipline (no fit-on-everything default) and the save/load round trip.
"""
import numpy as np
import pandas as pd
import pytest

from pocketcompare.descriptors.a2 import CONTACT_FEATURES, A2Config, A2Descriptor

RNG = np.random.default_rng(0)
M, P = 8, 60
MOLS = [f"m{i:02d}" for i in range(M)]
POCKETS = [f"p{i:03d}" for i in range(P)]


def make_raw(score=None, in_pocket=None, n_heavy=None, panel="fragments"):
    vol = 100.0 * np.exp(RNG.normal(0, 0.5, P))
    bur = RNG.uniform(0.4, 1.0, P)
    nh = np.arange(10, 10 + M) if n_heavy is None else n_heavy
    if score is None:
        # LE depends linearly on log volume and buriedness, plus a molecule effect and noise
        le = (-0.3 - 0.05 * np.log(vol)[:, None] - 0.1 * bur[:, None]
              + RNG.normal(0, 0.01, (P, M)) + np.linspace(-0.05, 0.05, M)[None, :])
        score = le * nh[None, :]
    rows = []
    for i, p in enumerate(POCKETS):
        for j, m in enumerate(MOLS):
            rows.append(dict(pocket_id=p, mol_id=m, panel=panel, seed=0, n_heavy=int(nh[j]),
                             score=float(score[i, j]), inter=float(score[i, j]),
                             le=float(score[i, j] / nh[j]), pose_dist_pocket=0.5,
                             in_pocket=True if in_pocket is None else bool(in_pocket[i, j]),
                             **{f: float(RNG.integers(0, 10)) if f != "buried_frac" else float(RNG.uniform(0, 1))
                                for f in CONTACT_FEATURES}))
    meta = pd.DataFrame(dict(pocket_id=POCKETS, volume_L=vol, bur16_L=bur))
    return pd.DataFrame(rows), meta


def test_fit_requires_explicit_reference_set():
    raw, meta = make_raw()
    d = A2Descriptor(A2Config(panel="fragments"))
    with pytest.raises(ValueError):
        d.fit(raw, meta)
    with pytest.raises(ValueError):
        d.fit(raw, meta, reference_pocket_ids=[])
    with pytest.raises(RuntimeError):
        A2Descriptor(A2Config(panel="fragments")).transform(raw, meta)


def test_rank_vector_and_nonbinder_bins():
    raw, meta = make_raw()
    # molecule 0 is a clear non-binder in the first five pockets (score far above the 90th percentile;
    # kept well under 10 % of the table so that it does not move the quantile onto its own tie)
    bad = raw.mol_id.eq("m00") & raw.pocket_id.isin(POCKETS[:5])
    raw.loc[bad, "score"] = 5.0
    # and molecule 1 is out of pocket in the first pocket only
    raw.loc[(raw.mol_id == "m01") & (raw.pocket_id == POCKETS[0]), "in_pocket"] = False
    d = A2Descriptor(A2Config(panel="fragments")).fit(raw, meta, POCKETS)
    X = d.transform(raw, meta)
    assert X.rank.shape == (P, M)
    assert np.all(X.rank[:5, 0] == M + 1)                    # score bin
    assert np.all(X.rank[:, M - 1] <= M)                     # the strongest-scoring molecule is never binned
    assert X.rank[0, 1] == M + 2                             # out-of-pocket bin
    binders = X.rank[0, 2:]
    assert set(np.round(binders).astype(int)) == set(range(1, M - 1))   # 1..N over the binders only
    # a dropped molecule lands in the "missing" bin
    sub = raw[raw.mol_id != "m05"]
    Y = d.transform(sub, meta)
    assert np.all(Y.rank[:, MOLS.index("m05")] == M + 3)


def test_le_residualisation_removes_size_and_buriedness():
    raw, meta = make_raw()
    d = A2Descriptor(A2Config(panel="fragments")).fit(raw, meta, POCKETS)
    X = d.transform(raw, meta)
    lv = np.log(meta.set_index("pocket_id").loc[X.pocket_id, "volume_L"].to_numpy())
    bur = meta.set_index("pocket_id").loc[X.pocket_id, "bur16_L"].to_numpy()
    le_raw = raw.pivot(index="pocket_id", columns="mol_id", values="le").loc[X.pocket_id, MOLS].to_numpy()
    for j in range(M):
        assert abs(np.corrcoef(le_raw[:, j], lv)[0, 1]) > 0.5           # the confound is there to start with
        assert abs(np.corrcoef(X.le_resid[:, j], lv)[0, 1]) < 0.05      # ... and is regressed out
        assert abs(np.corrcoef(X.le_resid[:, j], bur)[0, 1]) < 0.05
    assert np.allclose(X.le_resid.mean(0), 0, atol=1e-5)
    assert np.allclose(X.le_resid.std(0), 1, atol=1e-2)


def test_ifp_block_is_z_scored_on_the_reference_set():
    raw, meta = make_raw()
    d = A2Descriptor(A2Config(panel="fragments")).fit(raw, meta, POCKETS)
    X = d.transform(raw, meta)
    assert X.ifp.shape == (P, M * len(CONTACT_FEATURES))
    assert np.allclose(X.ifp.mean(0), 0, atol=1e-5)
    assert np.allclose(X.ifp.std(0), 1, atol=1e-2)
    assert len(X.names()) == X.concat().shape[1]


def test_reference_subset_changes_the_fit_and_transform_is_out_of_sample():
    raw, meta = make_raw()
    ref = POCKETS[:30]
    a = A2Descriptor(A2Config(panel="fragments")).fit(raw, meta, ref)
    b = A2Descriptor(A2Config(panel="fragments")).fit(raw, meta, POCKETS)
    assert not np.allclose(a.le_coef_, b.le_coef_)
    assert not np.isclose(a.nonbinder_threshold_[0], b.nonbinder_threshold_[0])
    Xa = a.transform(raw, meta)
    # held-out pockets are transformed with the reference statistics, so they are not forced to mean 0
    held = np.array([p not in set(ref) for p in Xa.pocket_id])
    assert abs(Xa.le_resid[held].mean()) >= 0.0 and np.isfinite(Xa.le_resid[held]).all()
    assert Xa.le_resid.shape[0] == P


def test_save_load_round_trip(tmp_path):
    raw, meta = make_raw()
    d = A2Descriptor(A2Config(panel="fragments")).fit(raw, meta, POCKETS[:40])
    p = d.save(tmp_path / "ref.npz")
    e = A2Descriptor.load(p)
    xa, xb = d.transform(raw, meta), e.transform(raw, meta)
    assert np.allclose(xa.concat(), xb.concat())
    assert list(e.mol_id_) == MOLS and e.cfg == d.cfg


def test_seed_aggregation_is_the_mean():
    raw, meta = make_raw()
    r2 = raw.copy()
    r2["seed"] = 1
    r2["score"] = r2["score"] + 1.0
    r2["le"] = r2["score"] / r2["n_heavy"]
    both = pd.concat([raw, r2], ignore_index=True)
    d = A2Descriptor(A2Config(panel="fragments")).fit(both, meta, POCKETS)
    one = A2Descriptor(A2Config(panel="fragments")).fit(raw, meta, POCKETS)
    # mean over the two seeds shifts LE by +0.5/n_heavy, so the regression intercepts differ by that
    assert np.allclose(d.le_coef_[:, 0] - one.le_coef_[:, 0], 0.5 / np.arange(10, 10 + M), atol=1e-6)
