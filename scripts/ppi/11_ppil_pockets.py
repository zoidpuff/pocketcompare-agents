#!/usr/bin/env python
"""PPI-L step 2: pocket table in our format + BURROW point cache via the pocket adapter (L-mode on the ligand).

Input : data/processed/ppi/ppil/ligand_instances.parquet (10_).
Structure = local PDB mirror mmCIF, chain = the ligand-bound chain only (the pocketome's PL systems are single
chains; the partner is absent).  Featurised once per (pdb, chain) with pockets.featurize_structure (holo
mode, default preset, `all` ranker).
L-mode (DESIGN §2.2): BURROW points <= 4 Å of the modulator's heavy atoms.  Ligand atoms = the HET residue
(chain:resnum, CCD id) found in the stripped hetero atoms of that chain (`definition = ligand_residue`);
fallback: heavy atoms of the shipped SDF (PDBe ModelServer export, PDB frame; `ligand_file:sdf`), accepted
only if it lies <= 6 Å from the protein.  Every pocket also gets its D-mode match (merged region pockets).
Writes data/processed/cache/points/ppi_l/<pdb>_<chain>.npz, data/processed/ppi/ppil/pockets.parquet
(pocket_id, structure_path, chain, pocket_def_type, pocket_def, ligand_file, ligand_resname, cache_file,
lmode_idx, ...), data/splits/inputs/ppi_l_chains.fasta (header = "pdb:<pdb>_<chain>"), chains/<pdb>_<chain>.pdb
(protein heavy atoms, for Foldseek), and logs/ppil_pockets.done.
Usage: python scripts/ppi/11_ppil_pockets.py --workers 14
"""
from __future__ import annotations

import os

for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PPIL = ROOT / "data/processed/ppi/ppil"
CACHE = ROOT / "data/processed/cache/points/ppi_l"
AA3 = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
       "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
       "TYR": "Y", "VAL": "V", "MSE": "M", "SEC": "U"}


def chain_pdb(fs) -> str:
    out = []
    for i, (xyz, ai) in enumerate(zip(fs.atom_xyz, fs.atom_res)):
        rid = fs.res_ids[ai]
        ch, _, num = rid.rpartition(":")
        digits = "".join(c for c in num if c.isdigit() or c == "-")
        icode = num[len(digits):][:1] or " "
        nm = fs.atom_name[i]
        el = fs.atom_element[i]
        out.append(f"ATOM  {(i + 1) % 100000:5d} {nm:<4s} {fs.res_names[ai][:3]:>3s} A{int(digits) % 10000:4d}{icode}   "
                   f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00  0.00          {el:>2s}\n")
    return "".join(out) + "END\n"


def work(task: dict) -> tuple[list, dict]:
    from pocketcompare import pockets as pk
    t0 = time.perf_counter()
    out = Path(task["out"])
    tim = {"key": task["key"], "status": "ok", "cached": False}
    fs = None
    if out.exists():
        try:
            fs = pk.Featurized.load(out)
            tim["cached"] = fs.meta.get("adapter_version") == pk.ADAPTER_VERSION
            fs = fs if tim["cached"] else None
        except Exception:  # noqa: BLE001
            fs = None
    if fs is None:
        try:
            fs = pk.featurize_structure(task["path"], chains=[task["chain"]], key=task["key"])
            tim["bytes"] = fs.save(out)
            tim.update(fs.meta["timings"])
        except Exception as e:  # noqa: BLE001
            tim.update(status="failed", error=f"{type(e).__name__}: {e}")
            return [{"pocket_id": r["pocket_id"], "status": "failed", "failure_reason": tim["error"]}
                    for r in task["rows"]], tim
    seq = "".join(AA3.get(n, "X") for n in fs.res_names)
    (PPIL / "chains").mkdir(parents=True, exist_ok=True)
    (PPIL / "chains" / f"{task['key']}.pdb").write_text(chain_pdb(fs))
    tim.update(seq=seq, n_res=len(fs.res_ids), n_points=len(fs.points))
    merged = pk.merge_pockets(fs, "region")
    rows = []
    for r in task["rows"]:
        row = {"pocket_id": r["pocket_id"], "structure_key": task["key"], "status": "ok", "failure_reason": None}
        try:
            m = (fs.het_res == f"{r['chain']}:{r['resnum']}") & (fs.het_resname == r["lig"])
            if m.sum() > 0:
                xyz = fs.het_xyz[m]
                row["definition"] = "ligand_residue"
            else:
                if not r["ligand_file"]:
                    raise ValueError("ligand residue not in structure and no ligand file")
                xyz, _ = pk.read_ligand_heavy_atoms(ROOT / r["ligand_file"])
                row["definition"] = "ligand_file:sdf"
            lp = pk.lmode_from_ligand(fs, xyz)
            if lp.info["ligand_protein_min_dist"] > 6.0:
                raise ValueError(f"ligand {lp.info['ligand_protein_min_dist']:.1f} Å from the chain")
            if lp.n_points == 0:
                raise ValueError("empty L-mode pocket")
            dm = pk.dmode_match(fs, lp.idx, merged=merged)
            row.update(lmode_idx=lp.idx.astype(np.int32), n_points=lp.n_points,
                       n_points_dense=int((fs.vol[lp.idx] == 1).sum()), volume_A3=lp.volume_A3,
                       n_lining_res=len(lp.residues), lining_residues=" ".join(lp.residues),
                       n_ligand_atoms_struct=int(len(xyz)), ligand_protein_min_dist=lp.info["ligand_protein_min_dist"],
                       d_coverage=dm.coverage, d_missed=dm.missed,
                       d_members=np.asarray(dm.pocket.members if dm.pocket else [], np.int32),
                       d_precision=pk.coverage(fs, dm.pocket.idx, lp.idx) if dm.pocket else 0.0)
        except Exception as e:  # noqa: BLE001
            row.update(status="failed", failure_reason=f"{type(e).__name__}: {e}")
        rows.append(row)
    tim["total_s"] = time.perf_counter() - t0
    return rows, tim


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    L = pd.read_parquet(PPIL / "ligand_instances.parquet")
    L = L[L.in_pdb_mirror].copy()
    L["key"] = L.pdb + "_" + L.chain
    CACHE.mkdir(parents=True, exist_ok=True)
    tasks = []
    for k, g in L.groupby("key", sort=True):
        tasks.append({"key": k, "path": g.structure_path.iloc[0], "chain": g.chain.iloc[0],
                      "out": str(CACHE / f"{k}.npz"),
                      "rows": g[["pocket_id", "chain", "resnum", "lig", "ligand_file"]].fillna("").to_dict("records")})
    if a.limit:
        tasks = tasks[:a.limit]
    print(f"[ppil] {len(L)} ligand instances on {len(tasks)} chains", flush=True)
    rows, tims = [], []
    t0 = time.perf_counter()
    with ProcessPoolExecutor(a.workers, mp_context=get_context("spawn")) as ex:
        for i, f in enumerate(as_completed([ex.submit(work, t) for t in tasks]), 1):
            r, tm = f.result()
            rows += r
            tims.append(tm)
            if i % 500 == 0 or i == len(tasks):
                print(f"[ppil] {i}/{len(tasks)} {time.perf_counter() - t0:.0f} s", flush=True)
    T = pd.DataFrame(tims).sort_values("key")
    I = pd.DataFrame(rows)
    P = L.merge(I, on="pocket_id", how="left")
    P["pocket_def_type"] = "ligand_residue"
    P["pocket_def"] = P.lig + ":" + P.chain + ":" + P.resnum
    P["ligand_resname"] = P.lig
    P["cache_file"] = [str((CACHE / f"{k}.npz").relative_to(ROOT)) for k in P.key]
    P = P.drop(columns=["ecfp4_onbits"]).sort_values("pocket_id").reset_index(drop=True)
    sfx = f".limit{a.limit}" if a.limit else ""
    P.to_parquet(PPIL / f"pockets{sfx}.parquet", index=False)
    T.drop(columns=["seq"], errors="ignore").to_parquet(PPIL / f"featurize_timing{sfx}.parquet", index=False)
    ok = T[T.status == "ok"]
    if not a.limit:
        fa = ROOT / "data/splits/inputs/ppi_l_chains.fasta"
        fa.parent.mkdir(parents=True, exist_ok=True)
        fa.write_text("".join(f">pdb:{r.key}\n{r.seq}\n" for r in ok.itertuples()))
        (PPIL / "chains.fasta").write_text("".join(f">{r.key}\n{r.seq}\n" for r in ok.itertuples()))
    s = {"chains": len(T), "chains_ok": len(ok), "pockets": len(P), "pockets_ok": int((P.status == "ok").sum()),
         "definition": P.definition.value_counts().to_dict(),
         "failures": P.loc[P.status != "ok", "failure_reason"].astype(str).str.slice(0, 60).value_counts().head(10).to_dict(),
         "lmode_points_p50": float(P.n_points.median()), "lmode_volume_p50": float(P.volume_A3.median()),
         "d_missed_rate": float(P.loc[P.status == "ok", "d_missed"].astype(float).mean()),
         "disk_bytes": int(sum(p.stat().st_size for p in CACHE.glob("*.npz"))), "wall_s": time.perf_counter() - t0}
    (PPIL / f"pockets_summary{sfx}.json").write_text(json.dumps(s, indent=1, default=str))
    print(json.dumps(s, indent=1, default=str))
    if not a.limit:
        (ROOT / "logs/ppil_pockets.done").write_text(time.strftime("%F %T") + "\n")


if __name__ == "__main__":
    main()
