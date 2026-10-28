"""scripts/build_pair_table_example.py + scripts/train_head.py end to end (tiny settings; needs PyTorch)."""
import subprocess
import sys

import numpy as np
import pytest

from conftest import PDB, ROOT

pytest.importorskip("torch")


def test_train_head_smoke(tmp_path):
    d = tmp_path / "demo"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/build_pair_table_example.py"), "--out", str(d)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr
    assert (d / "pockets.parquet").exists() and (d / "pairs.tsv").exists()
    r = subprocess.run([sys.executable, str(ROOT / "scripts/train_head.py"), "--pockets", str(d / "pockets.parquet"),
                        "--pairs", str(d / "pairs.tsv"), "--out", str(d / "head"), "--holdout", "0",
                        "--max-epochs", "2", "--steps-per-epoch", "3", "--batch-pos", "16", "--batch-lab", "16",
                        "--seeds", "0,1"], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr
    from pocketcompare.method import Method
    m = Method(d / "head/method.yaml")
    assert m.dim == 256 and len(m.heads) == 2
    V, info = m.describe_all(PDB)
    assert V.shape == (len(info), 256)
    np.testing.assert_allclose(np.linalg.norm(V, axis=1), 1.0, atol=1e-5)
