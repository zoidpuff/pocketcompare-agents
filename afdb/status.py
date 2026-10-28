#!/usr/bin/env python
"""Progress of the AFDB run: units done / claimed / failed / pending per tier, structures and pockets so far,
recent throughput, ETA and failures.

    python afdb/status.py [--out-root DIR] [--json] [--failures 20]

Done markers are parsed once and cached in OUT_ROOT/state/done_cache.parquet (only new markers are read).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from afdb_common import out_root  # noqa: E402

FIELDS = ["unit_id", "tier", "structures", "structures_ok", "structures_error", "pockets_all", "pockets_kept",
          "wall_s", "describe_s", "t", "host", "slurm_job_id"]


def load_done(root: Path) -> pd.DataFrame:
    ddir = root / "state" / "done"
    cache = root / "state" / "done_cache.parquet"
    old = pd.read_parquet(cache) if cache.exists() else pd.DataFrame(columns=FIELDS)
    have = set(old.unit_id.astype(int)) if len(old) else set()
    rows = []
    for e in os.scandir(ddir) if ddir.exists() else []:
        if not e.name.endswith(".json") or not e.name[:-5].isdigit() or int(e.name[:-5]) in have:
            continue
        try:
            d = json.loads(Path(e.path).read_text())
        except (OSError, ValueError):
            continue
        rows.append({k: d.get(k) for k in FIELDS})
    df = pd.concat([old, pd.DataFrame(rows, columns=FIELDS)], ignore_index=True) if rows else old
    if rows:
        try:
            tmp = cache.with_suffix(f".{os.getpid()}.tmp")
            df.astype({"slurm_job_id": str, "host": str}).to_parquet(tmp, index=False)
            os.replace(tmp, cache)
        except OSError:
            pass
    present = {int(e.name[:-5]) for e in os.scandir(ddir) if e.name[:-5].isdigit()} if ddir.exists() else set()
    return df[df.unit_id.astype(int).isin(present)].copy()          # markers deleted for a redo drop out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--failures", type=int, default=10, help="failed units listed")
    ap.add_argument("--window", type=float, default=3600.0, help="seconds for the recent-throughput window")
    a = ap.parse_args()
    root = out_root(a.out_root)
    wl = pd.read_parquet(root / "worklist.parquet", columns=["unit_id", "tier", "est_structures", "code"])
    done = load_done(root)
    now = time.time()
    cdir, fdir = root / "state" / "claims", root / "state" / "failed"
    claims = []
    for e in os.scandir(cdir) if cdir.exists() else []:
        if e.name.isdigit():
            try:
                c = json.loads(Path(e.path, "claim.json").read_text())
            except (OSError, ValueError):
                c = {}
            claims.append({"unit_id": int(e.name), "host": c.get("host"), "job": c.get("slurm_job_id"),
                           "task": c.get("slurm_array_task_id"), "age_h": (now - c.get("t", now)) / 3600})
    claims = pd.DataFrame(claims, columns=["unit_id", "host", "job", "task", "age_h"])
    failed = []
    for e in os.scandir(fdir) if fdir.exists() else []:
        if e.name.endswith(".json"):
            try:
                failed.append(json.loads(Path(e.path).read_text()))
            except (OSError, ValueError):
                pass
    failed = pd.DataFrame(failed, columns=["unit_id", "tier", "error", "host", "time"])
    ds, cs, fs = set(done.unit_id.astype(int)), set(claims.unit_id), set(failed.unit_id.astype(int)) if len(failed) else set()
    wl["state"] = ["done" if u in ds else "claimed" if u in cs else "failed" if u in fs else "pending"
                   for u in wl.unit_id]
    done["t"] = done["t"].astype(float)
    rec = done[done.t >= now - a.window]
    # window = the last --window seconds, or less if the run is younger (from the start of the first such unit)
    span = min(a.window, now - float((rec.t - rec.wall_s.astype(float)).min())) if len(rec) else a.window
    rate = float(rec.structures.sum()) / max(span, 1.0) if len(rec) else 0.0
    out = {"out_root": str(root), "time": time.strftime("%Y-%m-%d %H:%M:%S"), "tiers": {}}
    for t, g in wl.groupby("tier"):
        d = done[done.tier.astype(int) == t]
        rem = int(g.loc[g.state != "done", "est_structures"].sum())
        out["tiers"][int(t)] = {
            "units": int(len(g)), **{s: int((g.state == s).sum()) for s in ("done", "claimed", "failed", "pending")},
            "structures_done": int(d.structures.sum()), "structure_errors": int(d.structures_error.sum()),
            "pockets_all": int(d.pockets_all.sum()), "pockets_kept": int(d.pockets_kept.sum()),
            "est_structures_remaining": rem}
    rem_all = sum(v["est_structures_remaining"] for v in out["tiers"].values())
    out["recent_rate_structures_per_s"] = round(rate, 1)
    out["recent_window_s"] = a.window
    out["active_claims"] = int(len(claims))
    out["active_hosts"] = sorted({str(h) for h in claims.host.dropna()})
    out["eta_hours"] = round(rem_all / rate / 3600, 1) if rate > 0 else None
    if a.json:
        print(json.dumps(out, indent=1))
        return
    print(f"{out['time']}  {root}")
    print(f"{'tier':>4} {'units':>7} {'done':>7} {'claimed':>7} {'failed':>6} {'pending':>7} {'structures':>12} "
          f"{'errors':>7} {'pockets kept':>13} {'remaining':>12}")
    for t, v in out["tiers"].items():
        print(f"{t:>4} {v['units']:>7} {v['done']:>7} {v['claimed']:>7} {v['failed']:>6} {v['pending']:>7} "
              f"{v['structures_done']:>12,} {v['structure_errors']:>7,} {v['pockets_kept']:>13,} "
              f"{v['est_structures_remaining']:>12,}")
    eta = f"{out['eta_hours']} h" if out["eta_hours"] is not None else "n/a (nothing finished in the window)"
    print(f"recent throughput {rate:.0f} structures/s (last {min(a.window, span if len(rec) else a.window) / 60:.0f} min, all nodes); ETA {eta}")
    if len(claims):
        g = claims.groupby(["host", "job", "task"], dropna=False).agg(units=("unit_id", "size"),
                                                                      oldest_h=("age_h", "max")).reset_index()
        print("active claims:")
        print(g.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    if len(failed):
        print(f"failed units ({len(failed)}; re-run: python afdb/worker.py --retry-failed [--unit-ids ...]):")
        print(failed.head(a.failures)[["unit_id", "tier", "host", "error"]].to_string(index=False, max_colwidth=100))
    n_err = int(done.structures_error.sum()) if len(done) else 0
    if n_err:
        print(f"{n_err:,} structures with status != ok inside done units (see structures/tier*/<unit>.parquet)")


if __name__ == "__main__":
    main()
