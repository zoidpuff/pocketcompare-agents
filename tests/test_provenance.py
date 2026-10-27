"""Tests of pocketcompare.provenance and scripts/check_report.py (toy files in tmp_path only)."""
import importlib.util
import json
import os
import socket
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pocketcompare import provenance as pv

ROOT = Path(__file__).resolve().parents[1]


def _load_check_report():
    spec = importlib.util.spec_from_file_location("check_report", ROOT / "scripts" / "check_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def inputs(tmp_path):
    f = tmp_path / "in.txt"
    f.write_text("hello\n")
    return f


@pytest.mark.parametrize("ext", [".parquet", ".json", ".tsv", ".csv"])
def test_write_result_formats(tmp_path, inputs, ext):
    df = pd.DataFrame({"arm": ["A1", "B1"], "auc": [0.71, 0.65]})
    out = tmp_path / f"res{ext}"
    prov = pv.write_result(out, df, script=__file__, args=["--x", "1"], config={"b": 2, "a": 1},
                           inputs=[inputs], seed=0, device="cpu")
    sc = Path(str(out) + ".prov.json")
    assert out.exists() and sc.exists()
    on_disk = json.loads(sc.read_text())
    assert on_disk == json.loads(json.dumps(prov))
    if ext == ".parquet":
        back = pd.read_parquet(out)
    elif ext == ".json":
        back = pd.DataFrame(json.loads(out.read_text()))
    else:
        back = pd.read_csv(out, sep="\t" if ext == ".tsv" else ",")
    pd.testing.assert_frame_equal(back, df)
    assert prov["n_rows"] == 2
    assert prov["result_sha256"] == pv.sha256_file(out)


def test_sidecar_fields(tmp_path, inputs):
    out = tmp_path / "r.json"
    prov = pv.write_result(out, {"auc": 0.7, "ci": [0.6, 0.8]}, script=__file__, args={"k": 3},
                           config={"b": 2, "a": 1}, inputs=[inputs], seed=4, device="cpu")
    for k in ("git_commit", "git_dirty", "script", "script_sha256", "args", "config", "config_sha256", "inputs",
              "evaluate_sha256", "seed", "device", "hostname", "start_time", "end_time", "wall_seconds"):
        assert k in prov, k
    assert prov["script_sha256"] == pv.sha256_file(__file__)
    assert prov["evaluate_sha256"] == pv.sha256_file(ROOT / "src" / "pocketcompare" / "evaluate.py")
    assert prov["inputs"][0]["sha256"] == pv.sha256_file(inputs) and prov["inputs"][0]["method"] == "sha256"
    assert prov["seed"] == 4 and prov["device"] == "cpu" and prov["hostname"] == socket.gethostname()
    assert prov["wall_seconds"] >= 0 and prov["start_time"] <= prov["end_time"]
    assert prov["git_commit"] is None or len(prov["git_commit"]) == 40
    assert isinstance(prov["git_dirty"], (bool, type(None)))
    # config hash is order-independent for dicts, and file-content based for paths
    assert prov["config_sha256"] == pv.config_sha256({"a": 1, "b": 2})
    cfg = tmp_path / "c.yaml"
    cfg.write_text("a: 1\n")
    assert pv.config_sha256(cfg) == pv.sha256_file(cfg)
    assert json.loads(out.read_text()) == {"auc": 0.7, "ci": [0.6, 0.8]}


def test_numpy_payload_and_explicit_start(tmp_path):
    out = tmp_path / "r.json"
    prov = pv.write_result(out, {"auc": np.float64(0.5), "reps": np.arange(3)}, script=None, args=[],
                           config=None, seed=0, device="cpu", start_time=0.0)
    assert json.loads(out.read_text()) == {"auc": 0.5, "reps": [0, 1, 2]}
    assert prov["config_sha256"] is None and prov["wall_seconds"] > 1e9


def test_large_input_fingerprint(tmp_path, monkeypatch):
    f = tmp_path / "big.bin"
    f.write_bytes(b"x" * 100)
    monkeypatch.setattr(pv, "LARGE_FILE", 10)
    fp = pv.file_fingerprint(f)
    assert fp["method"] == "size_mtime" and fp["size"] == 100 and "sha256" not in fp
    assert fp["mtime_ns"] == os.stat(f).st_mtime_ns


def test_process_start_time_plausible():
    import time

    t = pv.process_start_time()
    assert time.time() - 86400 * 2 < t <= time.time()


def test_refuses_dirty_final(monkeypatch, tmp_path):
    monkeypatch.setattr(pv, "git_state", lambda: {"git_commit": "x" * 40, "git_dirty": True,
                                                  "git_dirty_files": ["a"], "git_untracked": 0})
    monkeypatch.setattr(pv, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="clean"):
        pv.write_result(tmp_path / "results" / "final" / "x.json", {"a": 1}, script=None, args=[], config=None,
                        seed=0, device="cpu")
    assert not (tmp_path / "results" / "final" / "x.json").exists()


def test_append_trial(tmp_path):
    tp = tmp_path / "results" / "trials.tsv"
    pv.append_trial("A1", {"bins": 12}, "tough_m1_dev", {"auc": 0.7}, "results/a.json", trials_path=tp)
    pv.append_trial("A1", {"bins": 16, "note": "tab\there"}, "tough_m1_dev", {"auc": 0.72}, "r/b.json",
                    trials_path=tp)
    lines = tp.read_text().splitlines()
    assert lines[0].split("\t") == pv.TRIAL_COLUMNS and len(lines) == 3
    df = pd.read_csv(tp, sep="\t")
    assert list(df["arm"]) == ["A1", "A1"] and json.loads(df["metrics"][1]) == {"auc": 0.72}
    assert df["config_sha256"][0] == pv.config_sha256({"bins": 12})
    assert all(len(ln.split("\t")) == len(pv.TRIAL_COLUMNS) for ln in lines)
    first = lines[:2]
    pv.append_trial("B1", {}, "blips_val", {"auc": 0.6}, "r/c.json", trials_path=tp)
    assert tp.read_text().splitlines()[:2] == first  # append-only


def test_append_trial_refuses_foreign_header(tmp_path):
    tp = tmp_path / "trials.tsv"
    tp.write_text("something\telse\n")
    with pytest.raises(RuntimeError, match="header"):
        pv.append_trial("A1", {}, "dev", {}, "x", trials_path=tp)


# ------------------------------------------------------------------------------------------- check_report
def _toy_results(tmp_path):
    pv.write_result(tmp_path / "res" / "c1.json", {"delta_auc": {"estimate": 0.04213, "ci_low": 0.0112},
                                                   "auc": 0.7349, "miss_rate": 0.0213},
                    script=None, args=[], config=None, seed=0, device="cpu")
    pv.write_result(tmp_path / "res" / "arms.parquet",
                    pd.DataFrame({"arm": ["A1", "B1"], "split": ["dev", "dev"], "auc": [0.7213, 0.6588]}),
                    script=None, args=[], config=None, seed=0, device="cpu")


def test_check_report_ok_and_mismatch(tmp_path):
    cr = _load_check_report()
    _toy_results(tmp_path)
    md = tmp_path / "r.md"
    md.write_text(
        "C1: dAUC 0.042 <!-- src: res/c1.json#delta_auc.estimate --> (lower 0.011 "
        "<!-- src: res/c1.json#delta_auc.ci_low -->), AUC 0.73 <!-- src: res/c1.json#auc -->.\n"
        "Misses 2.1 % <!-- src: res/c1.json#miss_rate -->; A1 0.721 <!-- src: res/arms.parquet#auc[arm=A1] -->,\n"
        "B1 0.66 <!-- src: res/arms.parquet#auc[arm=B1,split=dev] -->.\n"
        "```\nignored 0.123 <!-- src: res/c1.json#nope -->\n```\n")
    n_ok, errs, warns = cr.check(md, tmp_path)
    assert errs == [] and n_ok == 6 and warns == []
    assert cr.main([str(md), "--root", str(tmp_path)]) == 0
    md.write_text("AUC 0.74 <!-- src: res/c1.json#auc -->\n")  # 0.7349 rounds to 0.73
    assert cr.main([str(md), "--root", str(tmp_path)]) == 1
    md.write_text("AUC 0.73 <!-- src: res/arms.parquet#auc -->\n")  # 2 rows: ambiguous key
    n_ok, errs, _ = cr.check(md, tmp_path)
    assert len(errs) == 1 and "2 rows" in errs[0]
    md.write_text("AUC 0.73 <!-- src: res/c1.json#missing.key -->\n<!-- src: res/c1.json#auc --> no number\n")
    assert len(cr.check(md, tmp_path)[1]) == 2


def test_check_report_sidecar_problems(tmp_path):
    cr = _load_check_report()
    _toy_results(tmp_path)
    (tmp_path / "res" / "nosc.json").write_text('{"auc": 0.5}')
    md = tmp_path / "r.md"
    md.write_text("x 0.5 <!-- src: res/nosc.json#auc -->\ny 0.5 <!-- src: res/gone.json#auc -->\n")
    n_ok, errs, _ = cr.check(md, tmp_path)
    assert n_ok == 0 and any("missing sidecar" in e for e in errs) and any("does not exist" in e for e in errs)
    assert cr.main([str(md), "--root", str(tmp_path)]) == 1
    # result edited after its sidecar was written
    f = tmp_path / "res" / "c1.json"
    f.write_text(f.read_text().replace("0.7349", "0.7351"))
    md.write_text("AUC 0.735 <!-- src: res/c1.json#auc -->\n")
    assert any("sha256 mismatch" in e for e in cr.check(md, tmp_path)[1])


def test_check_report_stale_eval_and_untagged(tmp_path):
    cr = _load_check_report()
    _toy_results(tmp_path)
    sc = tmp_path / "res" / "c1.json.prov.json"
    prov = json.loads(sc.read_text())
    prov["evaluate_sha256"] = "0" * 64
    sc.write_text(json.dumps(prov))
    md = tmp_path / "r.md"
    md.write_text("AUC 0.73 <!-- src: res/c1.json#auc --> and an untagged 0.812 here\n")
    _, errs, warns = cr.check(md, tmp_path)
    assert any("different evaluate.py" in e for e in errs)
    n_ok, errs, warns = cr.check(md, tmp_path, allow_stale_eval=True)
    assert n_ok == 1 and errs == [] and any("untagged number 0.812" in w for w in warns)
    assert len(cr.check(md, tmp_path, allow_stale_eval=True, fail_untagged=True)[1]) == 1
