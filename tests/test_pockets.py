"""Pocket adapter (src/pocketcompare/pockets.py): BURROW equivalence, rotation/translation invariance, L-mode and
D-mode on a crystal ligand, determinism, cache round trip.  Uses BURROW's example 1a28_A.pdb (progesterone
receptor LBD) and, for the ligand, the PDB mirror entry 1a28 (STR, chain A; same coordinate frame)."""
import dataclasses
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
pk = pytest.importorskip("pocketcompare.pockets")
from scipy.spatial import cKDTree  # noqa: E402
from scipy.spatial.transform import Rotation  # noqa: E402

PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
EX = PD / "release/burrow/examples/1a28_A.pdb"
MIRROR_1A28 = Path("/cluster/scratch/jjaenes/pdb/a2/1a28.cif.gz")
need_ex = pytest.mark.skipif(not EX.exists(), reason="BURROW example not mounted")
need_lig = pytest.mark.skipif(not MIRROR_1A28.exists(), reason="PDB mirror entry 1a28 not available")


@pytest.fixture(scope="module")
def fs():
    return pk.featurize_structure(EX)


@pytest.fixture(scope="module")
def ligand():
    from pocketdetect.structure import load_structure
    s = load_structure(str(MIRROR_1A28))
    m = (s.res_name == "STR") & (s.chain == "A") & ~s.is_hydrogen
    return s.coords[m].astype(np.float64)


def _rot(seed):
    return Rotation.random(random_state=seed).as_matrix(), np.array([10.0, -20.0, 5.0])


def _match(fs_a, fs_b, R, t):
    d, j = cKDTree(fs_b.points).query(fs_a.points.astype(np.float64) @ R.T + t)
    return d, j


@need_ex
def test_all_points_and_features(fs):
    assert fs.feats.shape == (len(fs.points), 84) and len(fs.feature_names) == 84
    # all solvent-shell points, not only pocket points: dense (1), coarse sub-lattice (27), metal (0) weights
    assert set(np.unique(fs.vol).tolist()) <= {0.0, 1.0, 27.0} and (fs.vol == 27).any()
    in_pockets = np.unique(fs.pk_indices)
    assert len(in_pockets) < 0.5 * len(fs.points)
    assert np.array_equal(fs.is_metal, fs.vol == 0)
    assert fs.meta["pocketdetect_commit"] and len(fs.meta["model_sha256"]) == 64


@need_ex
def test_matches_burrow_export(fs):
    from pocketdetect.burrow.export import pocket_representations
    for sel, kw in ((fs.pk_in_region, {"output_rule": "region"}), (fs.pk_in_v2, {}),
                    (np.ones(fs.n_pockets, bool), {"min_score": None})):
        rep = pocket_representations(EX, **kw)
        assert np.allclose(rep["points"][["x", "y", "z"]].to_numpy(), fs.points)
        assert np.array_equal(rep["points"][fs.feature_names].to_numpy(np.float32), fs.feats)
        ids = np.flatnonzero(sel)
        assert len(ids) == len(rep["pockets"])
        for r, i in enumerate(ids, 1):
            assert np.array_equal(np.sort(rep["pocket_points"][r]), np.sort(fs.pocket_idx(i)))
            assert rep["pockets"].score[r - 1] == pytest.approx(fs.pk_score[i], abs=1e-12)


@need_ex
def test_rotation_translation_invariance_in_memory(fs):
    """Exact transform of the parsed coordinates: same points, features equal up to float32 round-off
    (an atom exactly at a 4/8/12 Å count boundary may flip for a handful of points)."""
    from pocketdetect.structure import load_structure
    s = load_structure(str(EX))
    R, t = _rot(0)
    g = pk.featurize_structure(dataclasses.replace(s, coords=(s.coords.astype(np.float64) @ R.T + t)
                                                   .astype(s.coords.dtype)))
    assert len(g.points) == len(fs.points)
    d, j = _match(fs, g, R, t)
    assert d.max() < 1e-3
    assert np.abs(fs.feats - g.feats[j]).max(1).__gt__(1e-4).mean() < 0.01      # < 1 % of points differ
    assert np.allclose(fs.X, g.X[j], atol=1e-3)                                # canonical frame identical
    assert g.n_pockets == fs.n_pockets and np.allclose(g.pk_score, fs.pk_score, atol=1e-6)


@need_ex
def test_rotation_translation_invariance_rotated_file(fs, tmp_path):
    """Rotated + translated copy written as a PDB file (coordinates rounded to 1e-3 Å)."""
    import gemmi
    R, t = _rot(1)
    st = gemmi.read_structure(str(EX))
    for m in st:
        m.transform_pos_and_adp(gemmi.Transform(gemmi.Mat33(R.tolist()), gemmi.Vec3(*t)))
    p = tmp_path / "rot.pdb"
    st.write_pdb(str(p))
    g = pk.featurize_structure(p)
    assert abs(len(g.points) - len(fs.points)) <= 0.002 * len(fs.points)
    d, j = _match(fs, g, R, t)
    ok = d < 0.01
    assert ok.mean() > 0.995
    diff = np.abs(fs.feats[ok] - g.feats[j[ok]])
    assert (diff > 1e-3).mean() < 0.01                    # < 1 % of feature values move (boundary round-off)
    assert np.median(diff) == 0.0


@need_ex
@need_lig
def test_lmode_ligand_plausible(fs, ligand):
    lp = pk.lmode_from_ligand(fs, ligand)
    assert len(ligand) == 23                              # progesterone heavy atoms
    assert 150 < lp.n_points < 1500 and 150 < lp.volume_A3 < 1500
    assert lp.volume_A3 == pytest.approx(fs.vol[lp.idx].sum())
    assert lp.info["ligand_protein_min_dist"] < 4.0
    # known progesterone contacts in 1A28 (Williams & Sigler 1998): Gln725, Arg766, Asn719
    assert {"A:725", "A:766", "A:719"} <= set(lp.residues)
    d = cKDTree(ligand).query(fs.points[lp.idx])[0]
    assert d.max() <= 4.0
    out = np.setdiff1d(np.arange(len(fs.points)), lp.idx)
    assert cKDTree(ligand).query(fs.points[out])[0].min() > 4.0


@need_ex
@need_lig
def test_lmode_residues(fs, ligand):
    lp = pk.lmode_from_ligand(fs, ligand)
    lr = pk.lmode_from_residues(fs, lp.residues)
    assert lr.n_points > 0 and (fs.feature("bur10")[lr.idx] >= 0.5).all()
    assert len(np.intersect1d(lr.idx, lp.idx)) > 0.5 * lp.n_points
    # TOUGH-M1-style "A:" prefix on a single-chain file with another chain letter is remapped
    ids = [r.replace("A:", "Z:") for r in lp.residues]
    lz = pk.lmode_from_residues(fs, ids)
    assert lz.info["chain_remapped"] and np.array_equal(lz.idx, lr.idx)
    with pytest.raises(ValueError):
        pk.lmode_from_residues(fs, ["A:99999"], single_chain_fallback=False)


@need_ex
@need_lig
def test_dmode_covers_ligand_site(fs, ligand):
    lp = pk.lmode_from_ligand(fs, ligand)
    merged = pk.merge_pockets(fs, "region")
    members = sorted(i for m in merged for i in m.members)
    assert members == np.flatnonzero(fs.pk_in_region).tolist()          # a partition of the region pockets
    dm = pk.dmode_match(fs, lp.idx, merged=merged)
    assert dm.coverage >= 0.3 and not dm.missed
    assert 0 in dm.pocket.members                                        # BURROW's top pocket
    # negative control: points > 25 Å from the ligand are not covered by the ligand-matched pocket
    far = np.flatnonzero(cKDTree(ligand).query(fs.points)[0] > 25)
    assert len(far) > 100 and pk.coverage(fs, far, dm.pocket.idx) == 0.0
    # positive control: the L-mode pocket fully covers itself
    assert pk.coverage(fs, lp.idx, lp.idx) == 1.0


@need_ex
@need_lig
def test_determinism_and_cache_roundtrip(fs, ligand, tmp_path):
    g = pk.featurize_structure(EX)
    for k in pk.Featurized._ARRAYS:
        assert np.array_equal(getattr(fs, k), getattr(g, k)), k
    a, b = tmp_path / "a.npz", tmp_path / "b.npz"
    fs.save(a)
    g.meta["timings"] = fs.meta["timings"]               # wall-clock timings are the only run-dependent field
    g.save(b)
    assert a.read_bytes() == b.read_bytes()
    h = pk.Featurized.load(a)
    for k in pk.Featurized._ARRAYS:
        assert np.array_equal(getattr(fs, k), getattr(h, k)), k
    assert h.feature_names == fs.feature_names and h.meta["model_path"] == fs.meta["model_path"]
    l1, l2 = pk.lmode_from_ligand(fs, ligand), pk.lmode_from_ligand(h, ligand)
    assert np.array_equal(l1.idx, l2.idx) and l1.residues == l2.residues
    d1, d2 = pk.dmode_match(fs, l1.idx), pk.dmode_match(h, l2.idx)
    assert d1.coverage == d2.coverage and d1.pocket.members == d2.pocket.members


def test_read_ligand_files(tmp_path):
    sdf = tmp_path / "x.sdf"
    sdf.write_text("\n x\n\n  3  2  0  0  0  0  0  0  0  0999 V2000\n"
                   "    1.0000    2.0000    3.0000 C   0  0\n"
                   "    1.5000    2.0000    3.0000 Cl  0  0\n"
                   "    0.5000    2.0000    3.0000 H   0  0\nM  END\n$$$$\n")
    xyz, el = pk.read_ligand_heavy_atoms(sdf)
    assert el == ["C", "CL"] and xyz.shape == (2, 3)
    pdb = tmp_path / "x.pdb"
    pdb.write_text("HETATM    1  C1  LIG A   1       1.000   2.000   3.000\n"
                   "HETATM    2 CL1  LIG A   1       1.500   2.000   3.000\n"
                   "HETATM    3  H1  LIG A   1       0.500   2.000   3.000\n")
    xyz2, el2 = pk.read_ligand_heavy_atoms(pdb)
    assert el2 == ["C", "CL"] and np.allclose(xyz, xyz2)
    assert pk.parse_residue_list("A:1,2, 3;B:7") == ["A:1", "A:2", "A:3", "B:7"]
