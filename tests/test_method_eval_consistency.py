"""Regression: the public API ``method.describe`` reproduces the vectors the evaluation scored.

For 20 TOUGH-M1-dev and 20 BLiPS-val pockets, BURROW is re-run from the structure file through
``method.describe(path, site=<ligand>)`` (L mode, the 4 Å ligand shell) and
``method.describe(path, site=<ligand>, locate="burrow")`` (D mode: matched merged region pocket -> best-covering
member), and compared with ``Method.embed(a4b.raw_parts(dataset, mode, ids))`` -- exactly what
``scripts/final_eval.py`` (MethodAdapter) and the A4b selection embedded.  The pockets are all dev/val pockets
whose evaluated D member differs from the legacy ``locate="burrow_flat"`` choice, topped up with the first
d_match pockets in id order, so the test fails if the D locator regresses to the legacy rule.

Also checks ``describe_all`` (merged region pockets >= 10 points) against the blind-test description rule.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

method = pytest.importorskip("pocketcompare.method")
from pocketcompare import a4b as A4  # noqa: E402
from pocketcompare import pockets as pk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
N_PER_SET = 20
TOL = 1e-5
BENCH = ROOT / "data/processed/benchmarks"
CACHE = ROOT / "data/processed/cache/points"
SETS = {
    "tough_m1": (ROOT / "data/splits/tough_m1_pockets_split.parquet", "pocket_id", "dev"),
    "blips": (ROOT / "data/splits/blips_sites_v2.parquet", "site_id", "val"),
}


def _have(ds):
    split, _, _ = SETS[ds]
    return all(p.exists() for p in (split, BENCH / f"{ds}_pockets.parquet", CACHE / ds / "index.parquet",
                                    A4.a1r_dir(ds) / "ids.parquet"))


@pytest.fixture(scope="module")
def M():
    return method.Method()


def _pick(ds):
    """(pocket rows of the benchmark table, cache-index rows), N_PER_SET pockets, deterministic."""
    split, col, part = SETS[ds]
    sp = pd.read_parquet(split)
    want = set(sp[col][sp.partition == part])
    ix = pd.read_parquet(CACHE / ds / "index.parquet")
    ids = A4.ids_table(ds).set_index("pocket_id")
    ix = ix[ix.pocket_id.isin(want) & (ix.status == "ok") & ix.pocket_id.isin(ids.index)].sort_values("pocket_id")
    ix = ix[ix.d_members.map(lambda m: m is not None and len(m) > 0)]
    ix = ix[((ix.d_coverage >= 0.3) | (ix.d_precision >= 0.5))]
    differ, rest = [], []
    for _, r in ix.iterrows():
        if len(differ) >= N_PER_SET // 2 and len(rest) >= N_PER_SET:
            break
        fs = pk.Featurized.load(ROOT / r.cache_file)
        L = np.asarray(r.lmode_idx, np.int64)
        m_flat, _ = pk.best_member(fs, L, np.flatnonzero(fs.pk_in_region))
        (differ if m_flat != int(ids.u_member[r.pocket_id]) else rest).append(r.pocket_id)
    chosen = (differ[:N_PER_SET // 2] + rest)[:N_PER_SET]
    bench = pd.read_parquet(BENCH / f"{ds}_pockets.parquet").set_index("pocket_id")
    return bench.loc[chosen], ix.set_index("pocket_id").loc[chosen], len(differ)


def _site(ds, row):
    if ds == "tough_m1":                  # resolve_pocket: the .sdf sibling of the shipped ligand file if present
        lf = ROOT / row.ligand_file
        return lf.with_suffix(".sdf") if lf.with_suffix(".sdf").exists() else lf
    return np.asarray(row.ligand_xyz, np.float64).reshape(-1, 3)


@pytest.mark.parametrize("ds", list(SETS))
def test_describe_reproduces_evaluation_embeddings(M, ds):
    if not _have(ds):
        pytest.skip(f"{ds} inputs not available")
    bench, ix, n_differ = _pick(ds)
    assert len(bench) == N_PER_SET
    got = {"L": [], "D": []}
    for pid, row in bench.iterrows():
        meta = pk.Featurized.load(ROOT / ix.cache_file[pid]).meta       # structure path / chains / AF mode
        path = meta["structure_path"]
        path = path if Path(path).is_absolute() else ROOT / path
        fs = pk.featurize_structure(path, chains=meta["chains"], af_mode=meta["af_mode"])
        site = _site(ds, row)
        got["L"].append(M.describe(fs, site=site)[0])
        v, info = M.describe(fs, site=site, locate="burrow", return_info=True)
        assert info.burrow_index[0] == int(A4.ids_table(ds).set_index("pocket_id").u_member[pid])
        got["D"].append(v[0])
    for mode in ("L", "D"):
        ref = M.embed(A4.raw_parts(ds, mode, list(bench.index), M.inp))
        err = np.abs(np.vstack(got[mode]) - ref).max()
        assert err <= TOL, (ds, mode, err)
    if ds == "tough_m1":
        assert n_differ >= 3          # the legacy locator picks another member for these: the test discriminates


@pytest.mark.parametrize("ds", list(SETS))
def test_legacy_locator_kept(M, ds):
    """``locate='burrow_flat'`` keeps the old rule (best member over all region pockets)."""
    if not _have(ds):
        pytest.skip(f"{ds} inputs not available")
    bench, ix, _ = _pick(ds)
    pid = bench.index[0]
    fs = pk.Featurized.load(ROOT / ix.cache_file[pid])
    site = _site(ds, bench.loc[pid])
    _, info = M.describe(fs, site=site, locate="burrow_flat", return_info=True)
    L = pk.lmode_from_ligand(fs, pk.read_ligand_heavy_atoms(site)[0] if isinstance(site, Path) else site)
    m, _ = pk.best_member(fs, L.idx, np.flatnonzero(fs.pk_in_region))
    assert info.burrow_index[0] == m


def test_describe_all_matches_blind_test_rule(M):
    """describe_all = merged region pockets >= 10 points, base = merged pocket (scripts/eval_blind.py)."""
    if not _have("blips"):
        pytest.skip("BLiPS cache not available")
    ix = pd.read_parquet(CACHE / "blips" / "index.parquet")
    fs = pk.Featurized.load(ROOT / ix.cache_file.iloc[0])
    V, info = M.describe_all(fs)
    merged = [mp for mp in pk.merge_pockets(fs, "region") if len(mp.idx) >= method.MIN_POINTS]
    assert len(V) == len(info) == len(merged) > 0
    ref = M.embed([np.vstack(c) for c in zip(*[M.raw_parts(fs, mp.idx) for mp in merged])])
    np.testing.assert_allclose(V, ref, atol=1e-6)
    assert list(info.burrow_index) == [mp.members[0] for mp in merged]
    Vm, im = M.describe_all(fs, unit="member")
    np.testing.assert_array_equal(Vm, M.describe(fs))
