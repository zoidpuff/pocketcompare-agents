"""scripts/final_eval.py guards (synthetic files only; never touches data/sealed/)."""
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fe():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("final_eval", ROOT / "scripts/final_eval.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["final_eval"] = m
    spec.loader.exec_module(m)
    return m


def _sealed(tmp_path, fe, monkeypatch, corrupt=False):
    d = tmp_path / "sealed"
    d.mkdir()
    f = d / "x_pairs.parquet"
    pd.DataFrame({"a": [1, 2, 3]}).to_parquet(f)
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    sums = tmp_path / "sums.txt"
    sums.write_text(f"{'0' * 64 if corrupt else h}  data/sealed/x_pairs.parquet\n")
    os.chmod(f, 0)
    monkeypatch.setattr(fe, "SEALED_DIR", d)
    monkeypatch.setattr(fe, "SEALED_SUMS", sums)
    return f


def test_unseal_reads_restores_and_logs(tmp_path, fe, monkeypatch):
    f = _sealed(tmp_path, fe, monkeypatch)
    s = fe.Sealed(tmp_path / "log.tsv", enabled=True)
    df = s.read("x_pairs.parquet", "test")
    assert len(df) == 3
    assert (os.stat(f).st_mode & 0o777) == 0
    log = pd.read_csv(tmp_path / "log.tsv", sep="\t")
    assert len(log) == 1 and log.mode_after.astype(str).iloc[0] in ("0o0", "0")


def test_unseal_sha_mismatch_refuses_and_restores(tmp_path, fe, monkeypatch):
    f = _sealed(tmp_path, fe, monkeypatch, corrupt=True)
    s = fe.Sealed(tmp_path / "log.tsv", enabled=True)
    with pytest.raises(RuntimeError, match="sha256"):
        s.read("x_pairs.parquet", "test")
    assert (os.stat(f).st_mode & 0o777) == 0
    assert not (tmp_path / "log.tsv").exists()


def test_dryrun_never_unseals(tmp_path, fe, monkeypatch):
    _sealed(tmp_path, fe, monkeypatch)
    with pytest.raises(RuntimeError, match="outside a FINAL_EVAL run"):
        fe.Sealed(tmp_path / "log.tsv", enabled=False).read("x_pairs.parquet", "test")


def test_real_run_requires_final_eval(fe, monkeypatch):
    monkeypatch.delenv("FINAL_EVAL", raising=False)
    monkeypatch.setattr(sys, "argv", ["final_eval.py"])
    with pytest.raises(SystemExit, match="FINAL_EVAL=1"):
        fe.main()
