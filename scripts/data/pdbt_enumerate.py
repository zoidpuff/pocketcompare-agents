#!/usr/bin/env python
"""PDB-T step 1 (PREREG2): enumerate PDB-mirror entries released after 2025-11-12, X-ray / EM, resolution <= 3.0 Å.

Phase A (every *.cif.gz of /cluster/scratch/jjaenes/pdb): read only the header block (decompress until the
  ``_pdbx_audit_revision_history`` and ``_pdbx_database_status`` categories have been passed, at most HEAD_LINES lines).
  Older-format files (45 k in the mirror) carry the revision history after the coordinates: for every file whose
  header block has no revision history the whole file is parsed (``rev_full_parse``).
  initial release date = revision_date of the revision with the lowest ordinal (= first revision, "Initial release");
  fallback ONLY if the file has no revision history: _pdbx_database_status.recvd_initial_deposition_date
  (flag ``date_source`` = deposition_fallback; such entries are kept only if that date > CUTOFF, which is a
  conservative proxy because release follows deposition).
Phase B (entries with release date > CUTOFF): gemmi.cif full parse of _exptl.method, X-ray resolution
  (_refine.ls_d_res_high, fallback _reflns.d_resolution_high), EM resolution (_em_3d_reconstruction.resolution).
  Kept: any method is X-RAY DIFFRACTION or ELECTRON MICROSCOPY and that method's resolution <= 3.0 Å
  (min over the X-ray/EM values present).
Output: data/processed/pdbt/entries.parquet (all scanned entries with date fields; phase-B fields for the new ones)
        data/processed/pdbt/enumerate_counts.json
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import time
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MIRROR = Path("/cluster/scratch/jjaenes/pdb")
OUT = ROOT / "data/processed/pdbt"
CUTOFF = "2025-11-12"
MAX_RES = 3.0
HEAD_LINES = 4000
OK_METHODS = {"X-RAY DIFFRACTION", "ELECTRON MICROSCOPY"}


def _val(tok: str) -> str:
    import gemmi
    return gemmi.cif.as_string(tok)


def head_dates(path: str) -> dict:
    """Release / deposition dates from the header block of one mmCIF.gz (no full parse): decompress line by line
    until both categories have been seen and closed (next '#' separator), then parse that prefix with gemmi."""
    import gemmi
    rec = {"pdb_id": Path(path).name.split(".")[0], "rev_date": None, "rev_date_min": None, "dep_date": None,
           "head_error": None, "head_lines": 0}
    try:
        buf, seen_rev, seen_st, cur = [], False, False, None
        with gzip.open(path, "rt", errors="replace") as fh:
            for n, line in enumerate(fh):
                buf.append(line)
                if line.startswith("_pdbx_audit_revision_history."):
                    seen_rev, cur = True, "rev"
                elif line.startswith("_pdbx_database_status."):
                    seen_st, cur = True, "st"
                elif line.startswith("#"):
                    if seen_rev and seen_st:
                        break
                    cur = None
                if n >= HEAD_LINES:
                    break
        rec["head_lines"] = n + 1
        b = gemmi.cif.read_string("".join(buf)).sole_block()
        t = b.find("_pdbx_audit_revision_history.", ["ordinal", "revision_date"])
        revs = []
        for r in t:
            try:
                o = int(r[0])
            except ValueError:
                o = 10 ** 9
            d = gemmi.cif.as_string(r[1])
            if re.match(r"\d{4}-\d{2}-\d{2}$", d):
                revs.append((o, d))
        if revs:
            rec["rev_date"] = min(revs)[1]
            rec["rev_date_min"] = min(d for _, d in revs)
        dd = [gemmi.cif.as_string(x) for x in b.find_values("_pdbx_database_status.recvd_initial_deposition_date")]
        rec["dep_date"] = dd[0] if dd and re.match(r"\d{4}-\d{2}-\d{2}$", dd[0]) else None
    except Exception as e:  # noqa: BLE001
        rec["head_error"] = f"{type(e).__name__}: {e}"
    if rec["rev_date"] is None:
        # older-format files carry the revision history near the END (after the coordinates): full parse
        try:
            b = gemmi.cif.read(path).sole_block()
            t = b.find("_pdbx_audit_revision_history.", ["ordinal", "revision_date"])
            revs = []
            for r in t:
                try:
                    o = int(r[0])
                except ValueError:
                    o = 10 ** 9
                d = gemmi.cif.as_string(r[1])
                if re.match(r"\d{4}-\d{2}-\d{2}$", d):
                    revs.append((o, d))
            if revs:
                rec["rev_date"] = min(revs)[1]
                rec["rev_date_min"] = min(d for _, d in revs)
                rec["rev_full_parse"] = True
            if rec["dep_date"] is None:
                dd = [gemmi.cif.as_string(x) for x in
                      b.find_values("_pdbx_database_status.recvd_initial_deposition_date")]
                rec["dep_date"] = dd[0] if dd else None
            rec["head_error"] = None
        except Exception as e:  # noqa: BLE001
            rec["head_error"] = f"full: {type(e).__name__}: {e}"
    return rec


def _f(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def full_meta(path: str) -> dict:
    import gemmi
    rec = {"pdb_id": Path(path).name.split(".")[0], "methods": None, "res_xray": None, "res_em": None,
           "meta_error": None, "dep_date_full": None}
    try:
        b = gemmi.cif.read(path).sole_block()
        meth = [_val(x) for x in b.find_values("_exptl.method")]
        rec["methods"] = ";".join(sorted(set(meth)))
        rx = [_f(x) for x in b.find_values("_refine.ls_d_res_high")]
        rx = [x for x in rx if x is not None]
        if not rx:
            rx = [x for x in (_f(y) for y in b.find_values("_reflns.d_resolution_high")) if x is not None]
        re_ = [x for x in (_f(y) for y in b.find_values("_em_3d_reconstruction.resolution")) if x is not None]
        rec["res_xray"] = min(rx) if rx else None
        rec["res_em"] = min(re_) if re_ else None
        dd = [_val(x) for x in b.find_values("_pdbx_database_status.recvd_initial_deposition_date")]
        rec["dep_date_full"] = dd[0] if dd else None
    except Exception as e:  # noqa: BLE001
        rec["meta_error"] = f"{type(e).__name__}: {e}"
    return rec


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(str(p) for p in MIRROR.glob("*/*.cif.gz"))
    print(f"[enum] {len(files)} mmCIF files", flush=True)
    with get_context("spawn").Pool(a.workers) as pool:
        heads = pool.map(head_dates, files, chunksize=256)
    H = pd.DataFrame(heads)
    H["path"] = files
    H["date_source"] = np.where(H.rev_date.notna(), "revision_history",
                                np.where(H.dep_date.notna(), "deposition_fallback", "none"))
    H["release_date"] = H.rev_date.where(H.rev_date.notna(), H.dep_date)
    print(f"[enum] phase A {time.time() - t0:.0f}s; date sources {H.date_source.value_counts().to_dict()}", flush=True)
    new = H[H.release_date.notna() & (H.release_date > CUTOFF)]
    with get_context("spawn").Pool(a.workers) as pool:
        meta = pool.map(full_meta, new.path.tolist(), chunksize=8)
    M = pd.DataFrame(meta)
    E = H.merge(M, on="pdb_id", how="left")
    mset = E.methods.fillna("").str.split(";")
    xr = mset.apply(lambda m: "X-RAY DIFFRACTION" in m)
    em = mset.apply(lambda m: "ELECTRON MICROSCOPY" in m)
    res = np.fmin(np.where(xr, E.res_xray.astype(float), np.nan), np.where(em, E.res_em.astype(float), np.nan))
    E["method_ok"] = xr | em
    E["resolution"] = res
    E["is_new"] = E.release_date.notna() & (E.release_date > CUTOFF)
    E["keep"] = E.is_new & E.method_ok & (E.resolution <= MAX_RES)
    E.drop(columns=[c for c in ("rev_ordinal",) if c in E]).to_parquet(OUT / "entries.parquet", index=False)
    n = E[E.is_new]
    counts = dict(
        cutoff=CUTOFF, max_resolution=MAX_RES, n_files=int(len(E)),
        date_source=E.date_source.value_counts().to_dict(), n_head_error=int(E.head_error.notna().sum()),
        n_released_after_cutoff=int(E.is_new.sum()),
        n_released_after_cutoff_by_source=n.date_source.value_counts().to_dict(),
        n_new_meta_error=int(n.meta_error.notna().sum()),
        new_methods=n.methods.fillna("?").value_counts().head(12).to_dict(),
        n_new_xray_or_em=int(n.method_ok.sum()),
        n_new_xray_or_em_res_missing=int((n.method_ok & n.resolution.isna()).sum()),
        n_kept=int(E.keep.sum()),
        n_kept_xray=int((E.keep & xr).sum()), n_kept_em=int((E.keep & em).sum()),
        new_release_date_range=[str(n.release_date.min()), str(n.release_date.max())],
        mirror_latest_release=str(E.release_date.max()), wall_s=round(time.time() - t0, 1))
    (OUT / "enumerate_counts.json").write_text(json.dumps(counts, indent=1, default=str))
    print(json.dumps(counts, indent=1, default=str), flush=True)


if __name__ == "__main__":
    sys.exit(main())
