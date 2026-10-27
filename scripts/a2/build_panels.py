#!/usr/bin/env python
"""A2 docking panels (DESIGN §3 A2): 128 fragments + 128 lead-like molecules, deterministic.

Stage `pool`  : parse the source files, apply the panel filters, protonate at pH 7.4 (dimorphite-dl,
                precision 0 = single dominant microstate), write the filtered pools as parquet.
Stage `pick`  : stratified MaxMin selection (SEEDS[0]) + ETKDGv3/MMFF 3D -> data/ref/panels/.

Sources (see DATA.md "Docking panels"):
  fragments : NCI Open Database, release 4 (NCI-Open_2012-05-01.sdf.gz, NCI/CADD group, public domain).
  lead-like : PocketVec lead-like set (1,000 molecules, sbnb-irb/PocketVec, MIT), i.e. the published pool
              from which PocketVec's 128-molecule panel was drawn.

Usage (project root, .venv active, PYTHONPATH=/tmp/adock/overlay for dimorphite_dl):
  python scripts/a2/build_panels.py --stage pool --workers 8
  python scripts/a2/build_panels.py --stage pick
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, Crippen, Descriptors, FilterCatalog, rdMolDescriptors
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit.SimDivFilters.rdSimDivPickers import MaxMinPicker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.seeds import SEEDS  # noqa: E402

RDLogger.DisableLog("rdApp.*")

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data/raw/panel_sources"
OUT = ROOT / "data/ref/panels"
POOL = ROOT / "data/raw/panel_sources/pools"

OK_EL = {1, 6, 7, 8, 9, 15, 16, 17, 35, 53}
# fragment filter (Ro3-like, widened to the heavy-atom window the brief asks for)
FRAG = dict(ha_min=8, ha_max=17, mw_max=300.0, rot_max=3, hbd_max=3, hba_max=6, logp_max=3.5, rings_min=1)
# lead-like filter
LEAD = dict(mw_min=200.0, mw_max=450.0, rot_max=6)
HA_BINS = [("ha8_9", 8, 9), ("ha10_14", 10, 14), ("ha15_17", 15, 17)]
HA_WEIGHT = {"ha8_9": 24, "ha10_14": 80, "ha15_17": 24}          # sums to 128
CLASSES = ["apolar_aromatic", "donor_rich", "acceptor_rich", "mixed", "cationic", "anionic"]


# --------------------------------------------------------------------------- chemistry helpers
def _catalog():
    p = FilterCatalog.FilterCatalogParams()
    p.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
    return FilterCatalog.FilterCatalog(p)


def pharmacophore_class(mol: Chem.Mol) -> str:
    """Six classes on the pH-7.4 microstate: cationic / anionic / donor-rich / acceptor-rich / mixed / apolar."""
    q = [a.GetFormalCharge() for a in mol.GetAtoms()]
    net, npos, nneg = sum(q), sum(c > 0 for c in q), sum(c < 0 for c in q)
    if net > 0:
        return "cationic"
    if net < 0:
        return "anionic"
    if npos and nneg:
        return "mixed"                       # zwitterion
    hbd, hba = rdMolDescriptors.CalcNumHBD(mol), rdMolDescriptors.CalcNumHBA(mol)
    if hbd <= 1 and hba <= 2:
        return "apolar_aromatic"
    if hbd >= 2 and hbd >= hba:
        return "donor_rich"
    if hba >= 3 and hba > hbd:
        return "acceptor_rich"
    return "mixed"


def ha_bin(ha: int) -> str | None:
    for name, lo, hi in HA_BINS:
        if lo <= ha <= hi:
            return name
    return None


def props(mol: Chem.Mol) -> dict:
    return dict(smiles=Chem.MolToSmiles(mol), mw=round(Descriptors.MolWt(mol), 2),
                n_heavy=mol.GetNumHeavyAtoms(), n_rot=rdMolDescriptors.CalcNumRotatableBonds(mol),
                hbd=rdMolDescriptors.CalcNumHBD(mol), hba=rdMolDescriptors.CalcNumHBA(mol),
                logp=round(Crippen.MolLogP(mol), 3), tpsa=round(rdMolDescriptors.CalcTPSA(mol), 2),
                n_rings=rdMolDescriptors.CalcNumRings(mol),
                net_charge=sum(a.GetFormalCharge() for a in mol.GetAtoms()),
                pharm_class=pharmacophore_class(mol))


# --------------------------------------------------------------------------- stage: pool
_W = {}


def _init_worker():
    from dimorphite_dl import protonate_smiles
    _W["pains"] = _catalog()
    _W["lfc"] = rdMolStandardize.LargestFragmentChooser()
    _W["prot"] = protonate_smiles


def _protonate(smi: str):
    out = _W["prot"](smi, ph_min=7.4, ph_max=7.4, precision=0.0, validate_output=True)
    return out[0] if out else None


def _frag_record(rec: str):
    """One SDF record text -> row dict or None."""
    mol = Chem.MolFromMolBlock(rec, removeHs=True)
    if mol is None:
        return None
    name = rec.split("\n", 1)[0].strip()
    try:
        mol = _W["lfc"].choose(mol)
        if any(a.GetAtomicNum() not in OK_EL for a in mol.GetAtoms()):
            return None
        ha = mol.GetNumHeavyAtoms()
        if not (FRAG["ha_min"] <= ha <= FRAG["ha_max"]):
            return None
        if Descriptors.MolWt(mol) > FRAG["mw_max"]:
            return None
        if rdMolDescriptors.CalcNumRings(mol) < FRAG["rings_min"]:
            return None
        if rdMolDescriptors.CalcNumRotatableBonds(mol) > FRAG["rot_max"]:
            return None
        if rdMolDescriptors.CalcNumHBD(mol) > FRAG["hbd_max"]:
            return None
        if rdMolDescriptors.CalcNumHBA(mol) > FRAG["hba_max"]:
            return None
        if Crippen.MolLogP(mol) > FRAG["logp_max"]:
            return None
        if _W["pains"].HasMatch(mol):
            return None
        ps = _protonate(Chem.MolToSmiles(mol))
        if ps is None:
            return None
        pm = Chem.MolFromSmiles(ps)
        if pm is None or not (FRAG["ha_min"] <= pm.GetNumHeavyAtoms() <= FRAG["ha_max"]):
            return None
        return dict(mol_id=f"NSC_{name}", source_smiles=Chem.MolToSmiles(mol), **props(pm))
    except Exception:  # noqa: BLE001
        return None


def _lead_record(smi: str):
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    try:
        mol = _W["lfc"].choose(mol)
        if any(a.GetAtomicNum() not in OK_EL for a in mol.GetAtoms()):
            return None
        ps = _protonate(Chem.MolToSmiles(mol))
        if ps is None:
            return None
        pm = Chem.MolFromSmiles(ps)
        if pm is None:
            return None
        mw = Descriptors.MolWt(pm)
        if not (LEAD["mw_min"] <= mw <= LEAD["mw_max"]):
            return None
        if rdMolDescriptors.CalcNumRotatableBonds(pm) > LEAD["rot_max"]:
            return None
        return dict(mol_id="", source_smiles=Chem.MolToSmiles(mol), **props(pm))
    except Exception:  # noqa: BLE001
        return None


def _frag_batch(recs):
    return [r for r in (_frag_record(t) for t in recs) if r]


def _lead_batch(smis):
    return [r for r in (_lead_record(s) for s in smis) if r]


def sdf_records(path, batch=500):
    buf, out = [], []
    with gzip.open(path, "rt", errors="replace") as fh:
        for line in fh:
            if line.startswith("$$$$"):
                out.append("".join(buf))
                buf = []
                if len(out) == batch:
                    yield out
                    out = []
            else:
                buf.append(line)
    if out:
        yield out


def stage_pool(workers: int):
    import multiprocessing as mp
    POOL.mkdir(parents=True, exist_ok=True)
    ctx = mp.get_context("fork")

    # ---- lead-like
    smis = [l.split()[0] for l in (SRC / "LLM.smi").read_text().splitlines() if l.strip()]
    print(f"lead-like source molecules: {len(smis)}", flush=True)
    with ctx.Pool(workers, initializer=_init_worker) as pool:
        rows = [r for part in pool.imap(_lead_batch, [smis[i:i + 50] for i in range(0, len(smis), 50)])
                for r in part]
    ld = pd.DataFrame(rows).drop_duplicates("smiles").reset_index(drop=True)
    ld["mol_id"] = [f"PV_LLM_{i:04d}" for i in range(len(ld))]
    ld.to_parquet(POOL / "leadlike_pool.parquet", index=False)
    print(f"lead-like pool after filters: {len(ld)}", flush=True)

    # ---- fragments
    n_rec = 0
    rows = []
    with ctx.Pool(workers, initializer=_init_worker) as pool:
        for part in pool.imap(_frag_batch, sdf_records(SRC / "NCI-Open_2012-05-01.sdf.gz"), chunksize=1):
            n_rec += 500
            rows += part
            if n_rec % 50000 == 0:
                print(f"  ~{n_rec} records, {len(rows)} kept", flush=True)
    fr = pd.DataFrame(rows).drop_duplicates("smiles").reset_index(drop=True)
    fr.to_parquet(POOL / "fragment_pool.parquet", index=False)
    print(f"fragment pool after filters + dedup: {len(fr)}", flush=True)


# --------------------------------------------------------------------------- stage: pick
def maxmin(df: pd.DataFrame, n: int, seed: int) -> list:
    """Deterministic MaxMin pick of n row positions on Morgan r2/2048 fingerprints, in pick order."""
    if n >= len(df):
        return list(range(len(df)))
    gen = AllChem.GetMorganGenerator(radius=2, fpSize=2048)
    fps = [gen.GetFingerprint(Chem.MolFromSmiles(s)) for s in df["smiles"]]
    return list(MaxMinPicker().LazyBitVectorPick(fps, len(fps), n, seed=seed))


def maxmin_embeddable(df: pd.DataFrame, n: int, seed: int, slack: int = 6) -> list:
    """MaxMin pick of n rows that also embed in 3D (over-pick by `slack`, keep the first n that embed)."""
    order = maxmin(df, min(n + slack, len(df)), seed)
    keep = []
    for i in order:
        if embed3d(df["smiles"].iloc[i], str(df["mol_id"].iloc[i]), seed) is not None:
            keep.append(i)
            if len(keep) == n:
                break
    return keep


def allocate(pool_counts: dict, total: int) -> dict:
    """Equal per class, HA_WEIGHT across bins; shortfalls redistributed to the largest strata (deterministic)."""
    per_class = total / len(CLASSES)
    tgt = {}
    for c in CLASSES:
        for b, _, _ in HA_BINS:
            tgt[(c, b)] = per_class * HA_WEIGHT[b] / total
    # largest-remainder rounding to `total`
    base = {k: int(np.floor(v)) for k, v in tgt.items()}
    rem = sorted(tgt, key=lambda k: (-(tgt[k] - base[k]), k))
    i = 0
    while sum(base.values()) < total:
        base[rem[i % len(rem)]] += 1
        i += 1
    # clip to pool availability, redistribute the deficit
    alloc = {k: min(v, pool_counts.get(k, 0)) for k, v in base.items()}
    deficit = total - sum(alloc.values())
    while deficit > 0:
        room = [k for k in sorted(alloc, key=lambda k: (-(pool_counts.get(k, 0) - alloc[k]), k))
                if pool_counts.get(k, 0) > alloc[k]]
        if not room:
            break
        for k in room:
            if deficit == 0:
                break
            alloc[k] += 1
            deficit -= 1
    return alloc


def embed3d(smiles: str, name: str, seed: int):
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    mh = Chem.AddHs(m)
    ps = AllChem.ETKDGv3()
    ps.randomSeed = seed
    if AllChem.EmbedMolecule(mh, ps) != 0:
        ps.useRandomCoords = True
        if AllChem.EmbedMolecule(mh, ps) != 0:
            return None
    try:
        if AllChem.MMFFHasAllMoleculeParams(mh):
            AllChem.MMFFOptimizeMolecule(mh, maxIters=500)
        else:
            AllChem.UFFOptimizeMolecule(mh, maxIters=500)
    except Exception:  # noqa: BLE001
        pass
    mh.SetProp("_Name", name)
    mh.SetProp("smiles", smiles)
    return mh


def write_panel(df: pd.DataFrame, tag: str, seed: int) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, w = [], Chem.SDWriter(str(OUT / f"{tag}.sdf"))
    for r in df.itertuples(index=False):
        mh = embed3d(r.smiles, r.mol_id, seed)
        if mh is None:
            print(f"  !! 3D embedding failed: {r.mol_id}", flush=True)
            continue
        w.write(mh)
        rows.append(r._asdict())
    w.close()
    out = pd.DataFrame(rows)
    out.to_csv(OUT / f"{tag}.csv", index=False)
    (OUT / f"{tag}.smi").write_text("".join(f"{r.smiles}\t{r.mol_id}\n" for r in out.itertuples(index=False)))
    return dict(n=len(out), sdf_sha256=sha256(OUT / f"{tag}.sdf"), csv_sha256=sha256(OUT / f"{tag}.csv"),
                smi_sha256=sha256(OUT / f"{tag}.smi"))


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def stage_pick(n: int):
    seed = SEEDS[0]
    fr = pd.read_parquet(POOL / "fragment_pool.parquet")
    ld = pd.read_parquet(POOL / "leadlike_pool.parquet")
    fr["ha_bin"] = [ha_bin(h) for h in fr["n_heavy"]]
    fr = fr[fr["ha_bin"].notna()].reset_index(drop=True)
    counts = fr.groupby(["pharm_class", "ha_bin"]).size().to_dict()
    alloc = allocate(counts, n)
    print("stratum pool / allocation:")
    picks = []
    for c in CLASSES:
        for b, _, _ in HA_BINS:
            k = (c, b)
            sub = fr[(fr.pharm_class == c) & (fr.ha_bin == b)].sort_values("smiles").reset_index(drop=True)
            take = alloc.get(k, 0)
            print(f"  {c:16s} {b:8s} pool {len(sub):6d}  take {take}")
            if take:
                picks.append(sub.iloc[maxmin_embeddable(sub, take, seed)])
    frp = pd.concat(picks).sort_values(["pharm_class", "ha_bin", "mol_id"]).reset_index(drop=True)
    frp.insert(0, "panel", "fragments")

    ldx = ld.sort_values("smiles").reset_index(drop=True)
    ldp = ldx.iloc[maxmin_embeddable(ldx, n, seed)].sort_values("mol_id").reset_index(drop=True)
    ldp.insert(0, "panel", "leadlike")
    ldp["ha_bin"] = [ha_bin(h) or "other" for h in ldp["n_heavy"]]
    ldp["pharm_class"] = ldp["pharm_class"]

    man = {"seed": seed, "n_per_panel": n,
           "fragments": {"source": "NCI Open Database release 4 (NCI-Open_2012-05-01.sdf.gz)",
                         "pool_size": int(len(fr)), "filters": FRAG,
                         "strata": {f"{c}|{b}": int(alloc.get((c, b), 0)) for c in CLASSES for b, _, _ in HA_BINS},
                         **write_panel(frp, "fragments_v1", seed)},
           "leadlike": {"source": "PocketVec lead-like set LLM.smi (sbnb-irb/PocketVec, MIT)",
                        "pool_size": int(len(ld)), "filters": LEAD, **write_panel(ldp, "leadlike_v1", seed)},
           "protonation": "dimorphite-dl 2.1.0, ph_min=ph_max=7.4, precision=0.0 (single dominant microstate)",
           "conformer": "RDKit ETKDGv3 (randomSeed=SEEDS[0]) + MMFF94 (UFF fallback), explicit H",
           "sources_sha256": {p.name: sha256(p) for p in sorted(SRC.glob("*")) if p.is_file()}}
    # overlap with PocketVec's published 128
    pub = {Chem.MolToSmiles(Chem.MolFromSmiles(l.split()[0]))
           for l in (SRC / "TOP_128_rDock_LLM.smi").read_text().splitlines() if l.strip()}
    ours = {Chem.MolToSmiles(Chem.MolFromSmiles(s)) for s in ldp["source_smiles"]}
    man["leadlike"]["overlap_with_published_TOP128"] = len(pub & ours)
    (OUT / "panels_manifest.json").write_text(json.dumps(man, indent=2, sort_keys=True) + "\n")
    print(json.dumps(man, indent=2, sort_keys=True))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["pool", "pick"])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--n", type=int, default=128)
    a = ap.parse_args()
    if a.stage == "pool":
        stage_pool(a.workers)
    else:
        stage_pick(a.n)
