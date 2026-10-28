"""Golden test: the fingerprints of the example structures, generated with the research code of the frozen method
(``tests/data/golden.{npz,json}``), must be reproduced to <= 1e-6 by this package."""
import json

import numpy as np
import pytest

from conftest import DATA, EX

GOLD = json.loads((DATA / "golden.json").read_text())
TOL = GOLD["tolerance"]


@pytest.fixture(scope="module")
def gold():
    with np.load(DATA / "golden.npz") as z:
        return {k: z[k] for k in z.files}


@pytest.fixture(scope="module")
def fs_pdb():
    from pocketcompare import pockets as pk
    return pk.featurize_structure(EX / "pdb/1a28_A.pdb")


def _compute(M, fs_pdb, spec):
    site = spec.get("site")
    if isinstance(site, str):
        site = str(EX / site)
    if spec["call"] == "describe_all":
        src = fs_pdb if spec["structure"] == "pdb/1a28_A.pdb" else EX / spec["structure"]
        return M.describe_all(src, af_mode=spec.get("af_mode", False))
    return M.describe(fs_pdb, site=site, locate=spec.get("locate", "shell"), return_info=True)


@pytest.mark.parametrize("case", list(GOLD["cases"]))
def test_golden_fingerprints(M, gold, fs_pdb, case):
    c = GOLD["cases"][case]
    V, info = _compute(M, fs_pdb, c["spec"])
    ref = gold[case]
    assert V.shape == ref.shape == (c["n"], 384)
    assert np.abs(V - ref).max() <= TOL
    if c["burrow_rank"] is not None:
        assert [int(x) for x in info.burrow_rank] == c["burrow_rank"]
    if c["residues"] is not None:
        assert list(info.residues) == c["residues"]
    ok = np.linalg.norm(V, axis=1) > 0
    np.testing.assert_allclose(np.linalg.norm(V[ok], axis=1), 1.0, atol=1e-5)


def test_golden_n1_descriptors(M, gold, fs_pdb):
    """The raw N1 head input (627 d) of describe_all reproduces the research descriptors."""
    _, _, N = M.describe_all(fs_pdb, return_n1=True)
    ref = gold["pdb_all__n1"]
    assert N.shape == ref.shape
    np.testing.assert_allclose(N, ref, rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(M.embed_n1(N), gold["pdb_all"], atol=TOL)
