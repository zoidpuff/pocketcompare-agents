#!/usr/bin/env python
"""B0' — global Foldseek TM-score lookup tables, all-vs-all within each evaluation set (LABEL-FREE).

    python scripts/data/b0prime_foldseek.py --sets all --threads 22

Reads only pocket tables / partition tables (protein lists) and structure files.  No pair file, no label, nothing in
data/sealed/.  The tables are joined to (sealed) pairs only by scripts/final_eval.py.

Sets (one all-vs-all run each; a pocket's "protein" = one protein chain):
  tough_m1_test    pockets with partition == test in data/splits/tough_m1_pockets_split.parquet (shipped 1-chain files)
  tough_m1_dev     partition == dev (used by final_eval --dryrun-dev; the dev eval itself used the shipped TM list)
  prospeccts       every pocket of prospeccts_pockets.parquet (all 10 subsets incl. decoys; per-subset slices are
                   joined at evaluation time, so "within each subset" is covered)
  vertex           every pocket of vertex_pockets.parquet with a resolved site (scripts/data/vertex_site_map.py)
  blips_test_holo  holo chain of every BLiPS-test site (blips_test_holo_pockets.parquet: structure_key / chains)
  blips_val        holo chain of every BLiPS-val v2 site (dry run)
Chain rule (fixed before running): the protein chain with the most heavy atoms within 4.5 Å of the site ligand
(ProSPECCTs LIG residue, Vertex resolved HET instance, BLiPS ligand_xyz); TOUGH-M1 files are single-chain; if a
BLiPS structure_key names a chain it is used directly.  Chains are written as protein-only PDB files (model 1).

Foldseek (tools/foldseek, 3Di+AA, --exhaustive-search 1, -e inf): per ordered hit qtmscore / ttmscore / alntmscore.
Per unordered chain pair: tm_mean = mean of all available qTM and tTM values over both search directions
(**B0' primary score, pre-declared**), tm_max, tm_min, alntm (mean), fident (max), n_dir.  Pairs without any hit
get tm_* = 0 at join time (counted by final_eval).  Identical chain keys (same file + chain) score 1.

Outputs: data/processed/b0prime/<set>_keys.parquet (pocket_id, chain_key, file, chain, rule) and
<set>_tm.parquet (key_a < key_b, tm_mean, tm_max, tm_min, alntm, fident, n_dir) + .prov.json; marker
logs/b0prime_<set>.done.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "data/processed/b0prime"
FOLDSEEK = ROOT / "tools/foldseek/bin/foldseek"
BENCH = ROOT / "data/processed/benchmarks"
SETS = ("tough_m1_test", "tough_m1_dev", "prospeccts", "vertex", "blips_test_holo", "blips_val")
NEAR = 4.5


def _abs(p):
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def set_table(name: str) -> pd.DataFrame:
    """pocket_id, file, chain (or None), lig_sel: ('resname', chain:seqid) | ('xyz', array) | None."""
    if name.startswith("tough_m1"):
        part = name.split("_")[-1]
        sp = pd.read_parquet(ROOT / "data/splits/tough_m1_pockets_split.parquet")
        ids = set(sp.pocket_id[sp.partition == part])
        t = pd.read_parquet(BENCH / "tough_m1_pockets.parquet")
        t = t[t.pocket_id.isin(ids)]
        return pd.DataFrame({"pocket_id": t.pocket_id, "file": t.structure_path.map(lambda p: str(_abs(p))),
                             "chain": t.structure_chain, "lig": None})
    if name == "prospeccts":
        t = pd.read_parquet(BENCH / "prospeccts_pockets.parquet")
        lig = [("LIG", d.split(";")[0].split(":", 1)[1]) if d else None for d in t.pocket_def]
        return pd.DataFrame({"pocket_id": t.pocket_id, "file": t.structure_path.map(lambda p: str(_abs(p))),
                             "chain": None, "lig": lig})
    if name == "vertex":
        t = pd.read_parquet(BENCH / "vertex_pockets.parquet")
        t = t[t.site_het_instance.notna() & t.structure_path.notna()]
        return pd.DataFrame({"pocket_id": t.pocket_id, "file": t.structure_path, "chain": None,
                             "lig": [(h, s) for h, s in zip(t.het, t.site_het_instance)]})
    if name == "blips_test_holo":
        t = pd.read_parquet(BENCH / "blips_test_holo_pockets.parquet")
    elif name == "blips_val":
        sites = pd.read_parquet(ROOT / "data/splits/blips_sites_v2.parquet")
        ids = set(sites.site_id[sites.partition == "val"])
        t = pd.read_parquet(BENCH / "blips_pockets.parquet")
        t = t[t.pocket_id.isin(ids)]
    else:
        raise ValueError(name)
    ch = [c[0] if c is not None and len(c) == 1 else None for c in t.chains]
    return pd.DataFrame({"pocket_id": t.pocket_id, "file": t.structure_path.map(lambda p: str(_abs(p))),
                         "chain": ch, "lig": [("xyz", np.asarray(x, float).reshape(-1, 3)) for x in t.ligand_xyz]})


def _key(file, chain):
    return hashlib.sha1(f"{file}|{chain}".encode()).hexdigest()[:16] + f"_{chain}"


def extract(task):
    """One structure file: pick the chain per pocket, write protein-only chain PDBs.  -> rows."""
    import gemmi
    file, rows, cdir = task
    try:
        st = gemmi.read_structure(file)
        st.setup_entities()
        st.remove_ligands_and_waters()   # on a copy below we still need ligands -> read twice
        prot = gemmi.read_structure(file)
        prot.setup_entities()
    except Exception as e:  # noqa: BLE001
        return [{"pocket_id": r["pocket_id"], "chain_key": None, "rule": f"read_error:{e!r}"} for r in rows]
    model = prot[0]
    pchains = {ch.name for ch in st[0] if len(ch) and ch.get_polymer().check_polymer_type()
               in (gemmi.PolymerType.PeptideL, gemmi.PolymerType.PeptideD)}
    ns = None
    out = []
    for r in rows:
        chain, rule = r["chain"], "given"
        if chain is None:
            lig = r["lig"]
            xyz = None
            if lig is not None and lig[0] == "xyz":
                xyz = lig[1]
            elif lig is not None:
                rn, cs = lig
                c, _, sq = cs.partition(":")
                xyz = np.array([a.pos.tolist() for ch in model if ch.name == c for res in ch
                                if res.name == rn and str(res.seqid) == sq for a in res if a.element.name != "H"])
            if xyz is None or len(xyz) == 0:
                chain, rule = (sorted(pchains)[0] if pchains else None), "first_protein_chain(no ligand)"
            else:
                if ns is None:
                    ns = gemmi.NeighborSearch(st[0], gemmi.UnitCell(), 6).populate()
                cnt = {}
                for p in xyz:
                    for m in ns.find_atoms(gemmi.Position(*p), "\0", radius=NEAR):
                        cra = m.to_cra(st[0])
                        if cra.chain.name in pchains and cra.atom.element.name != "H":
                            cnt[cra.chain.name] = cnt.get(cra.chain.name, 0) + 1
                chain, rule = ((max(cnt, key=lambda k: (cnt[k], -ord(k[0]))), "most_contacts") if cnt
                               else ((sorted(pchains)[0] if pchains else None), "first_protein_chain(no contact)"))
        if chain is None:
            out.append({"pocket_id": r["pocket_id"], "chain_key": None, "rule": "no_protein_chain"})
            continue
        key = _key(file, chain)
        f = Path(cdir) / f"{key}.pdb"
        if not f.exists():
            s2 = gemmi.Structure()
            s2.cell = st.cell
            m2 = gemmi.Model("1")
            src = next((ch for ch in st[0] if ch.name == chain), None)
            if src is None:
                out.append({"pocket_id": r["pocket_id"], "chain_key": None, "rule": f"chain {chain} absent"})
                continue
            m2.add_chain(src)
            m2[0].name = "A"            # one chain per file; PDB format allows 1-char names only
            s2.add_model(m2)
            s2.setup_entities()
            s2.write_pdb(str(f))
        out.append({"pocket_id": r["pocket_id"], "chain_key": key, "file": file, "chain": chain, "rule": rule})
    return out


def run_set(name: str, threads: int, keep_tmp: bool):
    from pocketcompare.provenance import write_result
    t0 = time.time()
    tab = set_table(name)
    work = OUT / "work" / name
    cdir = work / "chains"
    if cdir.exists():
        shutil.rmtree(cdir)
    cdir.mkdir(parents=True)
    tasks = [(f, g.to_dict("records"), str(cdir)) for f, g in tab.groupby("file", sort=True)]
    with ProcessPoolExecutor(threads) as ex:
        keys = pd.DataFrame([r for rs in ex.map(extract, tasks, chunksize=8) for r in rs])
    keys = keys.set_index("pocket_id").loc[tab.pocket_id].reset_index()
    n_chain = len(list(cdir.glob("*.pdb")))
    print(f"[b0p] {name}: {len(tab)} pockets -> {keys.chain_key.notna().sum()} with chain, {n_chain} unique chains "
          f"({time.time() - t0:.0f} s)", flush=True)
    m8 = work / "allvsall.m8"
    cmd = [str(FOLDSEEK), "easy-search", str(cdir), str(cdir), str(m8), str(work / "tmp"), "--exhaustive-search", "1",
           "-e", "inf", "--threads", str(threads), "--format-output",
           "query,target,alntmscore,qtmscore,ttmscore,fident,prob", "-v", "1"]
    subprocess.run(cmd, check=True)
    hits = pd.read_csv(m8, sep="\t", header=None,
                       names=["q", "t", "alntm", "qtm", "ttm", "fident", "prob"], na_values=["-NAN", "NAN", "nan"])
    for c in ("alntm", "qtm", "ttm", "fident", "prob"):
        hits[c] = pd.to_numeric(hits[c], errors="coerce")
    hits = hits[hits.q != hits.t]
    a = np.where(hits.q < hits.t, hits.q, hits.t)
    b = np.where(hits.q < hits.t, hits.t, hits.q)
    h = pd.DataFrame({"key_a": a, "key_b": b, "qtm": hits.qtm, "ttm": hits.ttm, "alntm": hits.alntm,
                      "fident": hits.fident})
    g = h.groupby(["key_a", "key_b"], sort=True)
    tm = pd.DataFrame({"tm_mean": (g.qtm.sum() + g.ttm.sum()) / (2 * g.size()),
                       "tm_max": np.maximum(g.qtm.max(), g.ttm.max()),
                       "tm_min": np.minimum(g.qtm.min(), g.ttm.min()), "alntm": g.alntm.mean(),
                       "fident": g.fident.max(), "n_dir": g.size()}).reset_index()
    n_keys = keys.chain_key.nunique()
    info = {"set": name, "n_pockets": int(len(tab)), "n_pockets_with_chain": int(keys.chain_key.notna().sum()),
            "n_chains": int(n_keys), "n_pairs_possible": int(n_keys * (n_keys - 1) // 2),
            "n_pairs_with_hit": int(len(tm)), "rules": keys.rule.value_counts().to_dict(),
            "foldseek": " ".join(cmd[1:]), "wall_s": round(time.time() - t0, 1)}
    common = dict(script=__file__, args=sys.argv[1:], config={"set": name, "near_A": NEAR, "score": "tm_mean"},
                  seed=None, device="cpu", start_time=t0, extra=info)
    write_result(OUT / f"{name}_keys.parquet", keys.drop(columns=[c for c in ("lig",) if c in keys]), **common)
    write_result(OUT / f"{name}_tm.parquet", tm, **common)
    if not keep_tmp:
        shutil.rmtree(work / "tmp", ignore_errors=True)
        m8.unlink()
    (ROOT / "logs" / f"b0prime_{name}.done").write_text(time.strftime("%F %T") + "\n")
    print(f"[b0p] {name}: {info}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sets", default="all")
    ap.add_argument("--threads", type=int, default=22)
    ap.add_argument("--keep-tmp", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for s in (SETS if a.sets == "all" else a.sets.split(",")):
        run_set(s, a.threads, a.keep_tmp)


if __name__ == "__main__":
    main()
