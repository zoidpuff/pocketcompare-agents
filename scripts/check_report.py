#!/usr/bin/env python
"""Check that numbers in a markdown report match their sidecar'd result files (DESIGN §5).

Tag convention: a number is followed (on the same line) by ``<!-- src: <path>#<key> -->``; the checked number is
the last number between the previous tag (or line start) and this tag, e.g.

    ROC-AUC 0.734 <!-- src: results/c1/auc.json#delta_auc.estimate --> (95 % CI ...)

* ``path`` is relative to ``--root`` (default: the project root).  The file must have a ``<path>.prov.json``
  sidecar (``pocketcompare.provenance``) whose ``result_sha256`` matches the file, and whose ``evaluate_sha256``
  matches the current ``src/pocketcompare/evaluate.py`` (``--allow-stale-eval`` downgrades this to a warning).
* ``key`` for .json: dotted path into the object (``a.b.0.c``; a literal top-level key containing dots wins).
  For .parquet/.tsv/.csv: ``column`` (the table must have exactly one row) or ``column[col=value,col2=value]``
  (the filter must select exactly one row).
* Match rule: the reported number equals the stored value rounded to the shown number of decimals
  (|reported - value| <= 0.5 * 10^-decimals + 1e-12).  A number with a ``%`` suffix matches if it equals 100 x the
  value (fractions) or the value itself (already a percentage).
* Untagged numbers with >= 2 decimals are listed as warnings (``--fail-untagged`` makes them errors).

Exit status 0 if every tag checks out, 1 otherwise (mismatch, missing file, missing/stale sidecar, bad key).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATE_PY = ROOT / "src" / "pocketcompare" / "evaluate.py"
TAG = re.compile(r"<!--\s*src:\s*([^#\s]+)#(.+?)\s*-->")
NUM = re.compile(r"(?<![\w.])([-−+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(\s?%)?")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _decimals(tok: str) -> int:
    mant = re.split(r"[eE]", tok)[0]
    d = len(mant.split(".")[1]) if "." in mant else 0
    if re.search(r"[eE]", tok):
        d -= int(re.split(r"[eE]", tok)[1])
    return d


def lookup(path: Path, key: str):
    suf = path.suffix.lower()
    if suf == ".json":
        obj = json.loads(path.read_text())
        if isinstance(obj, dict) and key in obj:
            return obj[key]
        for part in key.split("."):
            if isinstance(obj, list):
                obj = obj[int(part)]
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                raise KeyError(f"key {key!r}: {part!r} not found")
        return obj
    import pandas as pd

    if suf == ".parquet":
        df = pd.read_parquet(path)
    elif suf in (".tsv", ".csv"):
        df = pd.read_csv(path, sep="\t" if suf == ".tsv" else ",")
    else:
        raise ValueError(f"unsupported file type {suf}")
    m = re.fullmatch(r"([^\[\]]+?)(?:\[(.*)\])?", key.strip())
    if not m:
        raise KeyError(f"bad table key {key!r}")
    col, filt = m.group(1), m.group(2)
    if col not in df.columns:
        raise KeyError(f"column {col!r} not in {list(df.columns)[:20]}")
    sel = df
    if filt:
        for cond in filt.split(","):
            c, v = (x.strip() for x in cond.split("=", 1))
            if c not in sel.columns:
                raise KeyError(f"filter column {c!r} not found")
            sel = sel[sel[c].astype(str) == v]
    if len(sel) != 1:
        raise KeyError(f"key {key!r} selects {len(sel)} rows (need exactly 1)")
    return sel[col].iloc[0]


def matches(tok: str, pct: bool, value) -> bool:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    rep = float(tok.replace("−", "-"))
    if not math.isfinite(v):
        return False
    tol = 0.5 * 10 ** (-_decimals(tok)) + 1e-12
    cands = [v * 100, v] if pct else [v]
    return any(abs(rep - c) <= tol for c in cands)


def check(md: Path, root: Path = ROOT, allow_stale_eval: bool = False, fail_untagged: bool = False):
    errors, warnings, n_ok = [], [], 0
    eval_sha = _sha(EVALUATE_PY) if EVALUATE_PY.exists() else None
    sidecar_cache = {}
    in_code = False
    for ln, line in enumerate(md.read_text().splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        pos = 0
        for m in TAG.finditer(line):
            seg = line[pos:m.start()]
            pos = m.end()
            where = f"{md.name}:{ln}"
            nums = list(NUM.finditer(seg))
            if not nums:
                errors.append(f"{where}: tag {m.group(0)} has no number before it")
                continue
            tok, pct = nums[-1].group(1), bool(nums[-1].group(2))
            rel, key = m.group(1), m.group(2)
            f = (root / rel).resolve()
            if not f.exists():
                errors.append(f"{where}: {rel} does not exist")
                continue
            if f not in sidecar_cache:
                sc = f.with_name(f.name + ".prov.json")
                if not sc.exists():
                    sidecar_cache[f] = f"missing sidecar {sc.name}"
                else:
                    prov = json.loads(sc.read_text())
                    if prov.get("result_sha256") != _sha(f):
                        sidecar_cache[f] = "result file changed after its sidecar was written (sha256 mismatch)"
                    elif eval_sha and prov.get("evaluate_sha256") != eval_sha:
                        sidecar_cache[f] = "stale-eval"
                    else:
                        sidecar_cache[f] = None
            st = sidecar_cache[f]
            if st == "stale-eval":
                msg = f"{where}: {rel} was computed with a different evaluate.py"
                (warnings if allow_stale_eval else errors).append(msg)
                if not allow_stale_eval:
                    continue
            elif st:
                errors.append(f"{where}: {rel}: {st}")
                continue
            try:
                val = lookup(f, key)
            except (KeyError, ValueError, IndexError) as e:
                errors.append(f"{where}: {rel}#{key}: {e}")
                continue
            if matches(tok, pct, val):
                n_ok += 1
            else:
                errors.append(f"{where}: reported {tok}{'%' if pct else ''} != {rel}#{key} = {val!r}")
        # untagged numbers with >= 2 decimals (outside tags and outside tagged numbers)
        stripped = TAG.sub(" ", line)
        tagged_tokens = {NUM.findall(line[:m.start()])[-1][0] for m in TAG.finditer(line)
                         if NUM.findall(line[:m.start()])}
        for nm in NUM.finditer(stripped):
            tok = nm.group(1)
            if _decimals(tok) >= 2 and "." in tok and tok not in tagged_tokens:
                msg = f"{md.name}:{ln}: untagged number {tok}"
                (errors if fail_untagged else warnings).append(msg)
    return n_ok, errors, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown", nargs="+", type=Path)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--allow-stale-eval", action="store_true")
    ap.add_argument("--fail-untagged", action="store_true")
    a = ap.parse_args(argv)
    total_ok, total_err = 0, 0
    for md in a.markdown:
        n_ok, errs, warns = check(md, a.root, a.allow_stale_eval, a.fail_untagged)
        total_ok += n_ok
        total_err += len(errs)
        for w in warns:
            print(f"WARN  {w}")
        for e in errs:
            print(f"ERROR {e}")
    print(f"check_report: {total_ok} tagged numbers OK, {total_err} errors")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
