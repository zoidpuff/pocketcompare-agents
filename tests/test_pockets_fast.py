"""Fast-backend adapter (src/pocketcompare/pockets_fast.py) == reference adapter (pockets.featurize_structure):
points, features, point scores, full pocket list, v2/region flags, and the proteome descriptors built on them.
AF example of BURROW (AF-P00918, AF mode) and 1a28_A (standard mode).  GPU check runs only if CUDA is available."""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
pk = pytest.importorskip("pocketcompare.pockets")
pf = pytest.importorskip("pocketcompare.pockets_fast")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/proteome"))

EXD = Path("/cluster/project/beltrao/gmagnus/pocket_detect/release/burrow/examples")
AF = EXD / "AF-P00918-F1-model_v6.cif.gz"
CRY = EXD / "1a28_A.pdb"
pytestmark = pytest.mark.skipif(not AF.exists(), reason="BURROW examples not mounted")
KEYS = ("points", "X", "vol", "is_metal", "feats", "point_score", "pk_score", "pk_center", "pk_indptr", "pk_indices",
        "pk_in_v2", "pk_in_region", "pk_residues", "res_ids", "res_names", "atom_xyz", "atom_name", "pk_desc")


def _same(a, b):
    for k in KEYS:
        x, y = getattr(a, k), getattr(b, k)
        assert x.shape == y.shape, k
        assert np.array_equal(x, y), k
    assert list(a.feature_names) == list(b.feature_names)


@pytest.mark.parametrize("path,af", [(AF, True), (CRY, False)])
def test_fast_cpu_equals_reference(path, af):
    ref = pk.featurize_structure(path, af_mode=af, key="x")
    fast = pf.featurize_fast_cpu(path, "x", af_mode=af)
    _same(ref, fast)


def test_fast_gpu_equals_reference_and_descriptors():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("no GPU")
    from pocketdetect.burrow.fast.gpu import featurize_batch
    from proteome_lib import describe_structure
    ref = pk.featurize_structure(AF, af_mode=True, key="x")
    fm = pf.fast_model()
    it, info = pf.load_and_prep(AF, "x", af_mode=True, fm=fm)
    (ps, sc), = featurize_batch([it], fm.cfg, f"cuda:{torch.cuda.device_count() - 1}", fm)
    gpu = pf.featurized_from_points(it.P, ps, sc, fm, "x")
    _same(ref, gpu)
    dr, dg = describe_structure(ref, info["plddt"]), describe_structure(gpu, info["plddt"])
    assert len(dr["records"]) == len(dg["records"]) > 0
    for x, y in zip(dr["a1"] + dr["env"], dg["a1"] + dg["env"]):
        assert np.array_equal(x, y)
    assert all(r["n_points"] >= 10 for r in dg["records"])
    assert all(np.isfinite(r["plddt_mean"]) for r in dg["records"])
