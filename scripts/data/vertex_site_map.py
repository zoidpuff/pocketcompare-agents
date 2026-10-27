#!/usr/bin/env python
"""Vertex site_index -> ligand instance, and pocket-table refresh after the PDB mirror sync (LABEL-FREE).

    python scripts/data/vertex_site_map.py --workers 24

Reads ONLY data/processed/benchmarks/vertex_pockets.parquet (pocket ids, PDB ids, HET codes, site indices) and the
mmCIF files of the local PDB mirror.  It never reads protein_pairs.tsv (chmod 000), any *_pairs file or
data/sealed/.  (scripts/data/build_benchmarks.py is NOT used for the refresh: it re-parses the raw label files.)

Why: the Vertex SI names a pocket ``<PDB>_<k>`` + a HET code but not which instance of that ligand.  The pocket
adapter mapped k to the k-th instance of HET, which is wrong: within one PDB entry the site indices run across
DIFFERENT HET codes (184/184 multi-site entries carry distinct HETs, e.g. 1kvl sites 1,2,3 = THN, KCP, CLS), and
480 single-site pockets have k > number of HET copies.  So k enumerates ligand sites of the entry.  The only public
re-implementation (DeeplyTough, Simonovsky & Meyers 2020, ``datasets/vertex.py`` + ``misc/ligand_extract.py``)
takes site k = the k-th HETATM residue of model 1 in file order with >= 3 atoms whose name is not in its
ignore list (``data/ref/deeplytough_ignore_list.json``, excipients + saccharides + stabilisers), regardless of
the HET code.  This script measures, label-free, which enumeration reproduces the given HET code at position k:

  het_k   : k-th copy of HET                         (old adapter rule)
  dt      : k-th HET residue, >= 3 atoms, not in DT ignore list   (DeeplyTough rule)
  all3    : k-th HET residue with >= 3 atoms (no ignore list)
  dt_type : k-th distinct residue NAME under the DT filter

Frozen resolution rule (written before looking at any label; labels are never read here):
  1. the ``dt`` residue if its name equals HET  -> site_rule = "dt_match"
  2. else the ``dt_type`` choice if its name equals HET: its first copy -> "dt_type_match"
  3. else the first copy of HET in file order -> "het_first_fallback"
  4. HET absent / no file -> unresolved (pocket fails in the cache; counted as a miss)

Outputs: data/processed/benchmarks/vertex_site_map.parquet (+ .prov.json), an updated vertex_pockets.parquet
(columns refreshed: in_pdb_mirror, structure_path, file_missing, n_het_instances_in_mirror, het_instances; added:
site_het_instance, site_rule, site_rule_variants) — the previous table is kept as vertex_pockets.pre_sitemap.parquet
— and results/benchmarks/vertex_site_map_summary.json.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
BENCH = ROOT / "data/processed/benchmarks"
TABLE = BENCH / "vertex_pockets.parquet"
MIRROR = Path("/cluster/scratch/jjaenes/pdb")
IGNORE = set(json.loads((ROOT / "data/ref/deeplytough_ignore_list.json").read_text())["ignore_list"])
IGNORE_STRIPPED = {x.strip() for x in IGNORE}
WATER = {"HOH", "WAT", "DOD", "H2O"}


def mirror_path(pdb_id: str) -> Path:
    return MIRROR / pdb_id[1:3] / f"{pdb_id}.cif.gz"


def het_residues(pdb_id: str):
    """[(chain:seqid, resname, n_atoms)] of hetero residues of model 1 in gemmi/file order (waters excluded)."""
    import gemmi
    p = mirror_path(pdb_id)
    if not p.exists():
        return None
    st = gemmi.read_structure(str(p))
    st.setup_entities()
    out = []
    for ch in st[0]:
        for res in ch:
            if res.het_flag != "H" or res.name in WATER:
                continue
            out.append((f"{ch.name}:{res.seqid}", res.name, len(res)))
    return out


def resolve(args):
    pdb_id, sites = args          # sites: [(pocket_id, het, k)]
    try:
        hets = het_residues(pdb_id)
    except Exception as e:  # noqa: BLE001
        return [{"pocket_id": p, "error": f"read: {e!r}"} for p, _, _ in sites]
    if hets is None:
        return [{"pocket_id": p, "error": "not in mirror"} for p, _, _ in sites]
    dt = [h for h in hets if h[2] >= 3 and h[1] not in IGNORE_STRIPPED]
    all3 = [h for h in hets if h[2] >= 3]
    types = list(dict.fromkeys(h[1] for h in dt))
    out = []
    for pid, het, k in sites:
        copies = [h for h in hets if h[1] == het]
        pick = lambda L: L[k - 1] if 1 <= k <= len(L) else None  # noqa: E731
        v = {"het_k": pick(copies), "dt": pick(dt), "all3": pick(all3)}
        t = types[k - 1] if 1 <= k <= len(types) else None
        v["dt_type"] = next((h for h in dt if h[1] == t), None) if t else None
        rec = {"pocket_id": pid, "error": None, "n_het_residues": len(hets), "n_dt_sites": len(dt),
               "n_copies": len(copies), "het_instances": ";".join(h[0] for h in copies)}
        for name, h in v.items():
            rec[f"{name}_res"] = h[0] if h else None
            rec[f"{name}_name"] = h[1] if h else None
            rec[f"{name}_match"] = bool(h and h[1] == het)
        if rec["dt_match"]:
            rec.update(site_het_instance=v["dt"][0], site_rule="dt_match")
        elif rec["dt_type_match"]:
            rec.update(site_het_instance=v["dt_type"][0], site_rule="dt_type_match")
        elif copies:
            rec.update(site_het_instance=copies[0][0], site_rule="het_first_fallback")
        else:
            rec.update(site_het_instance=None, site_rule="unresolved_het_absent")
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    t0 = time.time()
    tab = pd.read_parquet(TABLE)
    by = {p: [(r.pocket_id, r.het, int(r.site_index)) for r in g.itertuples()] for p, g in tab.groupby("pdb_id")}
    with ProcessPoolExecutor(a.workers) as ex:
        recs = [r for rs in ex.map(resolve, sorted(by.items()), chunksize=16) for r in rs]
    m = pd.DataFrame(recs).set_index("pocket_id").loc[tab.pocket_id].reset_index()
    m["site_index"] = tab.site_index.to_numpy()
    m["het"] = tab.het.to_numpy()
    ok = m.error.isna()
    summ = {"n_pockets": int(len(m)), "n_with_structure": int(ok.sum()),
            "n_structures_missing_after_sync": int(tab.loc[~ok.to_numpy(), "pdb_id"].nunique()),
            "missing_pdb_ids": sorted(tab.loc[~ok.to_numpy(), "pdb_id"].unique().tolist()),
            "previously_missing_now_present": int(sum(1 for p in tab.loc[~tab.in_pdb_mirror, "pdb_id"].unique()
                                                      if mirror_path(p).exists())),
            "rule_counts": m.site_rule.value_counts(dropna=False).to_dict(), "variant_match_rate": {}}
    for sub, mask in (("all", ok), ("k1", ok & (m.site_index == 1)), ("k_gt1", ok & (m.site_index > 1))):
        summ["variant_match_rate"][sub] = {"n": int(mask.sum()), **{v: float(m.loc[mask, f"{v}_match"].mean())
                                           for v in ("het_k", "dt", "all3", "dt_type")}}
    both = ok & m.het_k_match & m.dt_match
    summ["het_k_vs_dt_same_instance_when_both_match"] = float((m.het_k_res[both] == m.dt_res[both]).mean())
    summ["old_rule_changed_instance"] = int((ok & (m.site_het_instance != m.het_k_res)).sum())
    summ["wall_s"] = round(time.time() - t0, 1)
    # ---- write
    from pocketcompare.provenance import write_result
    write_result(BENCH / "vertex_site_map.parquet", m, script=__file__, args=sys.argv[1:],
                 config={"rule": "dt_match > dt_type_match > het_first_fallback", "ignore_list":
                         "data/ref/deeplytough_ignore_list.json"}, inputs=[TABLE, ROOT / "data/ref/deeplytough_ignore_list.json"],
                 seed=None, device="cpu", start_time=t0)
    bak = BENCH / "vertex_pockets.pre_sitemap.parquet"
    if not bak.exists():
        shutil.copy2(TABLE, bak)
    new = tab.copy()
    new["in_pdb_mirror"] = [mirror_path(p).exists() for p in new.pdb_id]
    new["structure_path"] = [str(mirror_path(p)) if ok_ else None for p, ok_ in zip(new.pdb_id, new.in_pdb_mirror)]
    new["file_missing"] = ~new.in_pdb_mirror
    mi = m.set_index("pocket_id")
    new["het_instances"] = new.pocket_id.map(mi.het_instances).fillna("")
    new["n_het_instances_in_mirror"] = new.pocket_id.map(mi.n_copies).astype(float)
    new.loc[~new.in_pdb_mirror, "n_het_instances_in_mirror"] = np.nan
    new["site_het_instance"] = new.pocket_id.map(mi.site_het_instance)
    new["site_rule"] = new.pocket_id.map(mi.site_rule).fillna("unresolved_no_structure")
    new.to_parquet(TABLE, index=False)
    (ROOT / "results/benchmarks").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/benchmarks/vertex_site_map_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
