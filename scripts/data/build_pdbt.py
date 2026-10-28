#!/usr/bin/env python
"""PDB-T: temporally held-out pocket-pair test set (PREREG2.md; RESEARCH_TREE D24).  Builds the set only: no
similarity score or method output is ever computed here.

    python scripts/data/pdbt_enumerate.py --workers 24          # step 1  -> data/processed/pdbt/entries.parquet
    python scripts/data/build_pdbt.py --stage ccd               # CCD table (SMILES, heavy atoms)
    python scripts/data/build_pdbt.py --stage sites  --workers 24
    python scripts/data/build_pdbt.py --stage leakage --threads 24   (scripts/data/pdbt_homology.py)
    python scripts/data/build_pdbt.py --stage pockets           # label-free pocket table -> point cache
    python scripts/build_point_cache.py --dataset pdbt --workers 22
    python scripts/data/build_pdbt.py --stage pairs             # pairs + gate + seal (one step)
(scripts/data/run_pdbt.sh runs everything, then the label-free descriptors.)

RULES (PREREG2; choices not fixed by PREREG2 are marked [def] and were fixed before any pair existed)
Entries   mirror entries with initial release (first _pdbx_audit_revision_history revision) > 2025-11-12, any method
          X-RAY DIFFRACTION or ELECTRON MICROSCOPY with that method's resolution <= 3.0 Å (pdbt_enumerate.py).
Ligands   instances (model 1, first altloc, H removed) of NON-POLYMER entities (branched/polymer entities = glycans,
          peptides, nucleic acids are never ligands); water excluded.  CCD SMILES from the wwPDB CCD
          (data/raw/ccd/components.cif.gz; first RDKit-parseable of SMILES_CANONICAL OpenEye, SMILES_CANONICAL
          CACTVS, SMILES OpenEye, SMILES CACTVS, SMILES ACDLabs); heavy atoms from that SMILES (as BLiPS).
          Qualifying: SMILES exists; >= 10 heavy atoms (ions/metals have 1); CCD not in data/ref/additives.txt;
          [def] no struct_conn 'covale' link to any other residue (covalent / polymer-like ligands); [def] observed
          instance has >= 10 heavy atoms.
Contacts  protein chain = polymer entity polypeptide(L) with >= 50 observed residues (CA present); a qualifying
          instance contacts a chain if any heavy-atom pair <= 4 Å.  [def] The instance is assigned to its primary
          chain (most contacting residues, then most contacting atoms, then chain name); the pocket is featurised on
          that chain alone (as BLiPS train/val and BLiPS-test holo).  [def] A site needs >= 2 contacting residues on
          its chain (BioLiP's receptor convention; removes e.g. rRNA-bound antibiotics touching one r-protein residue).
Sites     [def] on each chain, qualifying instances whose heavy atoms come <= 4 Å of each other form one physical
          site (connected components); q_ccds = their CCDs, ligand_xyz = union of their heavy atoms (BLiPS L-mode
          convention), label ligand = largest (heavy atoms, then CCD code).  Ligand clusters = Butina (Tc >= 0.6,
          ECFP4) over all qualifying PDB-T CCDs.  One site per (chain, label cluster): most ligand heavy atoms, then
          site index.
Leakage   pdbt_homology.py: direct edge (MMseqs2 -a + BURROW apply_rule, or exhaustive Foldseek min-TM >= 0.5) to
          any training source -> protein removed.  Exact observed-sequence identity with a test-set chain
          (TOUGH-M1-test, ProSPECCTs, Vertex, BLiPS-test af_set) -> removed (freshness).
Proteins  [def] protein = UniProt accession(s) of the chain's entity (_struct_ref UNP), else the observed sequence;
          [def] one site per (entry, protein, label cluster) (homo-oligomer copies; stable key
          sha256("<SEED>|<site_id>")), then <= 3 sites per protein as make_blips_split (distinct label clusters
          first, then the stable key).  Groups = connected components of the PDB-T homology graph (same rule).
Points    sites with < 10 L-mode BURROW points (point cache, label-free) are excluded before pairing (DESIGN §2.6,
          as BLiPS v2 / BLiPS-test).
Pairs     make_blips_split.make_pairs UNCHANGED: positives = different groups, max Tc over the two qualifying sets
          >= 0.7; per-cluster cap <= 300 (largest c with max share <= 10 %, as BLiPS); negatives = max Tc < 0.3,
          5 x positives, rng = default_rng(SEEDS[0]); promiscuous flag = the v1 BLiPS top-20 list.
Gate      >= 300 positives spanning >= 30 homology groups (distinct groups among positive-pair sites) and >= 10
          ligand clusters (distinct positive pair clusters) -> results/pdbt/gate.json, written before sealing.
Seal      data/sealed/pdbt_pairs.parquet written, sha256 appended to data/sealed_SHA256SUMS.txt, chmod 000, in one
          step; data/sealed restored to r-x.  Ligand identities are then stripped from every unsealed file.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import stat  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/data"))
from pocketcompare.seeds import SEEDS  # noqa: E402

PROC = ROOT / "data/processed/pdbt"
CCD_FILE = ROOT / "data/raw/ccd/components.cif.gz"
SEALED = ROOT / "data/sealed"
SPLITS = ROOT / "data/splits"
RES = ROOT / "results/pdbt"
BENCH = ROOT / "data/processed/benchmarks"
MIN_HA, MIN_CHAIN, CONTACT = 10, 50, 4.0
MIN_CONTACT_RES = 2                # [def] BioLiP convention (>= 2 receptor residues within contact distance)
BUTINA_SIM = 0.6
MAX_SITES_PER_PROTEIN = 3
MIN_POINTS = 10
SEED = SEEDS[0]
GATE = dict(min_pos=300, min_groups=30, min_clusters=10)
SMILES_PREF = [("SMILES_CANONICAL", "OpenEye"), ("SMILES_CANONICAL", "CACTVS"), ("SMILES", "OpenEye"),
               ("SMILES", "CACTVS"), ("SMILES", "ACDLabs")]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def additives() -> set[str]:
    out = set()
    for line in open(ROOT / "data/ref/additives.txt"):
        line = line.split("#")[0].strip()
        if line:
            out |= set(line.split())
    return out


# ----------------------------------------------------------------------------------------------- CCD
def stage_ccd():
    import gemmi
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    doc = gemmi.cif.read(str(CCD_FILE))
    rows = []
    for b in doc:
        desc = [(gemmi.cif.as_string(r[0]), gemmi.cif.as_string(r[1]), gemmi.cif.as_string(r[2]))
                for r in b.find("_pdbx_chem_comp_descriptor.", ["type", "program", "descriptor"])]
        smi, src = None, None
        for typ, prog in SMILES_PREF:
            for t, p, d in desc:
                if t == typ and p.startswith(prog) and Chem.MolFromSmiles(d) is not None:
                    smi, src = d, f"{typ}/{p}"
                    break
            if smi:
                break
        m = Chem.MolFromSmiles(smi) if smi else None
        n_heavy_atoms_ccd = sum(1 for _ in b.find_values("_chem_comp_atom.type_symbol")
                                if gemmi.cif.as_string(_) not in ("H", "D"))
        rows.append(dict(ccd=b.name, type=gemmi.cif.as_string(b.find_value("_chem_comp.type") or "?"),
                         smiles=smi, smiles_source=src, ha_smiles=m.GetNumHeavyAtoms() if m is not None else None,
                         ha_ccd_atoms=n_heavy_atoms_ccd))
    C = pd.DataFrame(rows)
    PROC.mkdir(parents=True, exist_ok=True)
    C.to_parquet(PROC / "ccd_table.parquet", index=False)
    log("ccd", len(C), "with smiles", int(C.smiles.notna().sum()))


# ----------------------------------------------------------------------------------------------- sites
_G: dict = {}


def _init_worker():
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = "1"
    C = pd.read_parquet(PROC / "ccd_table.parquet")
    _G["ha"] = dict(zip(C.ccd, C.ha_smiles))
    _G["add"] = additives()


def _reason(ccd: str) -> str:
    ha = _G["ha"].get(ccd)
    if ha is None or (isinstance(ha, float) and np.isnan(ha)):
        return "no_smiles"
    if ha <= 1:
        return "ion"
    if ccd in _G["add"]:
        return "additive"
    if ha < MIN_HA:
        return "small"
    return "ok"


def parse_entry(task: dict) -> dict:
    """One entry -> chains (protein, >= 50 aa) and physical ligand sites on their primary chains."""
    import gemmi
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    pdb = task["pdb_id"]
    out = {"pdb_id": pdb, "chains": [], "sites": [], "inst_reasons": {}, "error": None}
    try:
        doc = gemmi.cif.read(task["path"])
        b = doc.sole_block()
        unp = {}
        for r in b.find("_struct_ref.", ["db_name", "pdbx_db_accession", "entity_id"]):
            if gemmi.cif.as_string(r[0]) == "UNP":
                unp.setdefault(gemmi.cif.as_string(r[2]), set()).add(gemmi.cif.as_string(r[1]))
        st = gemmi.make_structure_from_block(b)
        st.remove_hydrogens()
        st.remove_alternative_conformations()
        ent_of_sub = {}
        for e in st.entities:
            for sc in e.subchains:
                ent_of_sub[sc] = e
        model = st[0]
        # covalent links (struct_conn covale): residue keys involved
        cov = set()
        for c in st.connections:
            if c.type == gemmi.ConnectionType.Covale:
                for p in (c.partner1, c.partner2):
                    cov.add((p.chain_name, str(p.res_id.seqid), p.res_id.name))
        prot_xyz, prot_meta = [], []
        lig = []
        for ch in model:
            n_obs, seq = 0, []
            for r in ch:
                e = ent_of_sub.get(r.subchain)
                if r.entity_type == gemmi.EntityType.Polymer and e is not None \
                        and e.polymer_type == gemmi.PolymerType.PeptideL:
                    if r.find_atom("CA", "*") is not None:
                        n_obs += 1
                        seq.append(gemmi.find_tabulated_residue(r.name).one_letter_code.upper()
                                   if gemmi.find_tabulated_residue(r.name) else "X")
                elif r.entity_type == gemmi.EntityType.NonPolymer and not r.is_water():
                    lig.append((ch.name, r))
            if n_obs >= MIN_CHAIN:
                ents = {ent_of_sub[r.subchain].name for r in ch if r.entity_type == gemmi.EntityType.Polymer
                        and r.subchain in ent_of_sub}
                eid = sorted(ents)[0] if ents else None
                out["chains"].append(dict(pdb_id=pdb, chain=ch.name, entity_id=eid, n_obs=n_obs,
                                          seq_gemmi="".join(c if c.isalpha() else "X" for c in seq),
                                          uniprot=";".join(sorted(unp.get(eid, set()))) if eid else ""))
                for r in ch:
                    if r.entity_type == gemmi.EntityType.Polymer:
                        for a in r:
                            prot_xyz.append(a.pos.tolist())
                            prot_meta.append((ch.name, f"{r.seqid.num}{r.seqid.icode}".strip()))
        prot_xyz = np.asarray(prot_xyz, float).reshape(-1, 3)
        tree = cKDTree(prot_xyz) if len(prot_xyz) else None
        reasons = out["inst_reasons"]
        inst = []
        for chname, r in lig:
            ccd = r.name
            why = _reason(ccd)
            if why == "ok" and (chname, str(r.seqid), ccd) in cov:
                why = "covalent"
            xyz = np.array([a.pos.tolist() for a in r], float).reshape(-1, 3)
            if why == "ok" and len(xyz) < MIN_HA:
                why = "observed_lt10"
            if why == "ok":
                if tree is None:
                    why = "no_protein_chain"
                else:
                    hits = tree.query_ball_point(xyz, CONTACT)
                    per_chain_res, per_chain_atoms = {}, {}
                    for h in hits:
                        for j in h:
                            c, rr = prot_meta[j]
                            per_chain_res.setdefault(c, set()).add(rr)
                            per_chain_atoms[c] = per_chain_atoms.get(c, 0) + 1
                    if not per_chain_res:
                        why = "no_contact"
                    else:
                        prim = sorted(per_chain_res, key=lambda c: (-len(per_chain_res[c]), -per_chain_atoms[c], c))[0]
                        inst.append(dict(ccd=ccd, xyz=xyz, chain=prim, n_res=len(per_chain_res[prim]),
                                         n_chains_contact=len(per_chain_res),
                                         res=per_chain_res[prim], inst=f"{chname}:{r.seqid.num}{r.seqid.icode}".strip()))
            reasons[why] = reasons.get(why, 0) + 1
        # physical sites per primary chain
        by_chain = {}
        for i in inst:
            by_chain.setdefault(i["chain"], []).append(i)
        for c, L in sorted(by_chain.items()):
            n = len(L)
            A = np.zeros((n, n), bool)
            trees = [cKDTree(x["xyz"]) for x in L]
            for i in range(n):
                for j in range(i + 1, n):
                    if trees[i].sparse_distance_matrix(trees[j], CONTACT).nnz > 0:
                        A[i, j] = A[j, i] = True
            _, lab = connected_components(A, directed=False)
            for k in sorted(set(lab)):
                mem = [L[i] for i in range(n) if lab[i] == k]
                ccds = sorted({m["ccd"] for m in mem})
                res = set().union(*[m["res"] for m in mem])
                out["sites"].append(dict(pdb_id=pdb, chain=c, phys_index=int(k), q_ccds=";".join(ccds),
                                         ligand_xyz=np.concatenate([m["xyz"] for m in mem]).ravel(),
                                         n_lig_atoms=int(sum(len(m["xyz"]) for m in mem)),
                                         n_lig_instances=len(mem), n_contact_res=len(res),
                                         max_chains_contact=int(max(m["n_chains_contact"] for m in mem)),
                                         instances=";".join(sorted(m["inst"] for m in mem))))
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def stage_sites(workers: int):
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
    from pocketcompare.splitutil import butina, ecfp4_from_mol, mol_from_smiles_list, tanimoto_matrix
    E = pd.read_parquet(PROC / "entries.parquet")
    E = E[E.keep].sort_values("pdb_id")
    tasks = E[["pdb_id", "path"]].to_dict("records")
    log("entries", len(tasks))
    t0 = time.time()
    res = []
    with get_context("spawn").Pool(workers, initializer=_init_worker) as pool:
        for k, r in enumerate(pool.imap_unordered(parse_entry, tasks, chunksize=4)):
            res.append(r)
            if (k + 1) % 1000 == 0:
                log(f"  {k + 1}/{len(tasks)} {time.time() - t0:.0f}s")
    errs = [r for r in res if r["error"]]
    chains = pd.DataFrame([c for r in res for c in r["chains"]])
    sites = pd.DataFrame([s for r in res for s in r["sites"]])
    reasons = pd.DataFrame([r["inst_reasons"] for r in res]).fillna(0).sum().astype(int).to_dict()
    meta = E.set_index("pdb_id")
    sites["release_date"] = sites.pdb_id.map(meta.release_date)
    sites["resolution"] = sites.pdb_id.map(meta.resolution)
    sites["methods"] = sites.pdb_id.map(meta.methods)
    sites["structure_path"] = sites.pdb_id.map(meta.path)
    # ligand universe, Butina clusters, label ligand
    C = pd.read_parquet(PROC / "ccd_table.parquet").set_index("ccd")
    qual = sorted({c for s in sites.q_ccds for c in s.split(";")})
    mols = {c: mol_from_smiles_list(C.at[c, "smiles"]) for c in qual}
    bad = [c for c, m in mols.items() if m is None]
    assert not bad, bad[:10]
    fps = np.array([ecfp4_from_mol(mols[c]) for c in qual])
    T = tanimoto_matrix(fps)
    cl = butina(T, BUTINA_SIM)
    cl_of = dict(zip(qual, cl.tolist()))
    ha = {c: int(C.at[c, "ha_smiles"]) for c in qual}
    sites["label_ccd"] = [max(s.split(";"), key=lambda c: (ha[c], c)) for s in sites.q_ccds]
    sites["label_ha"] = sites.label_ccd.map(ha)
    sites["label_cluster"] = sites.label_ccd.map(cl_of)
    n_phys = len(sites)
    sites = sites.sort_values(["pdb_id", "chain", "label_cluster", "n_lig_atoms", "phys_index"],
                              ascending=[True, True, True, False, True])
    sites = sites.drop_duplicates(["pdb_id", "chain", "label_cluster"], keep="first").copy()
    sites["site_id"] = [f"pdbt:{p}_{c}:{k}" for p, c, k in zip(sites.pdb_id, sites.chain, sites.phys_index)]
    sites = sites.sort_values("site_id").reset_index(drop=True)
    chains.to_parquet(PROC / "chains.parquet", index=False)
    sites.to_parquet(PROC / "sites_raw.parquet", index=False)
    np.save(PROC / "ccd_tanimoto.npy", T)
    pd.DataFrame(dict(ccd=qual, cluster=cl)).to_parquet(PROC / "ccd_clusters.parquet", index=False)
    counts = dict(n_entries=len(tasks), n_entry_errors=len(errs), entry_error_examples=[(r["pdb_id"], r["error"]) for r in errs[:10]],
                  n_entries_with_protein_chain=int(chains.pdb_id.nunique()), n_protein_chains=int(len(chains)),
                  ligand_instances_by_reason=reasons, n_physical_sites=int(n_phys),
                  n_sites_one_per_chain_cluster=int(len(sites)), n_entries_with_site=int(sites.pdb_id.nunique()),
                  n_site_chains=int(sites[["pdb_id", "chain"]].drop_duplicates().shape[0]),
                  n_qualifying_ccds=len(qual), n_ccd_clusters=int(len(set(cl))), wall_s=round(time.time() - t0))
    (PROC / "sites_counts.json").write_text(json.dumps(counts, indent=1, default=str))
    log(json.dumps({k: v for k, v in counts.items() if k != "entry_error_examples"}, default=str))


# ----------------------------------------------------------------------------------------------- selection
def stable_key(x: str) -> str:
    return hashlib.sha256(f"{SEED}|{x}".encode()).hexdigest()


def select_sites() -> tuple[pd.DataFrame, dict]:
    """Leakage removal -> one site per (protein, label cluster) -> <= 3 sites / protein; groups attached."""
    S = pd.read_parquet(PROC / "sites_raw.parquet")
    H = pd.read_parquet(PROC / "chain_homology.parquet")    # pdb_id, chain, sid, remove_*, group_id, protein
    S = S.merge(H, on=["pdb_id", "chain"], how="left", validate="m:1")
    c = {"n_sites_in": int(len(S))}
    c["n_sites_lt2_contact_res"] = int((S.n_contact_res < MIN_CONTACT_RES).sum())
    S = S[S.n_contact_res >= MIN_CONTACT_RES].copy()
    c["n_sites_no_homology_record"] = int(S.sid.isna().sum())
    S = S[S.sid.notna()].copy()
    for k in ("remove_train", "remove_test_exact"):
        c[f"n_sites_{k}"] = int(S[k].sum())
    S = S[~S.remove_train & ~S.remove_test_exact].copy()
    c["n_sites_after_leakage"] = int(len(S))
    S["_r"] = [stable_key(x) for x in S.site_id]
    # copies of the same site in one entry (homo-oligomer chains) -> one (stable key)
    S = S.sort_values(["pdb_id", "protein", "label_cluster", "_r"])
    S = S.drop_duplicates(["pdb_id", "protein", "label_cluster"], keep="first")
    c["n_sites_one_per_entry_protein_cluster"] = int(len(S))
    # <= 3 sites / protein exactly as make_blips_split: distinct label clusters first, then the stable key
    keep = []
    for _, gp in S.sort_values(["protein", "_r"]).groupby("protein", sort=True):
        chosen, seen = [], set()
        for i, cl_ in zip(gp.index, gp.label_cluster):
            if cl_ not in seen and len(chosen) < MAX_SITES_PER_PROTEIN:
                chosen.append(i)
                seen.add(cl_)
        for i in gp.index:
            if len(chosen) >= MAX_SITES_PER_PROTEIN:
                break
            if i not in chosen:
                chosen.append(i)
        keep += chosen
    S = S.loc[keep]
    c["n_sites_after_protein_cap"] = int(len(S))
    c["n_proteins"] = int(S.protein.nunique())
    return S.drop(columns=["_r"]).sort_values("site_id").reset_index(drop=True), c


def stage_pockets():
    """Label-free pocket table for scripts/build_point_cache.py (dataset 'pdbt'): no CCD codes."""
    S, c = select_sites()
    T = pd.DataFrame(dict(pocket_id=S.site_id, structure_key=[f"{p}_{ch}" for p, ch in zip(S.pdb_id, S.chain)],
                          structure_path=S.structure_path, chains=[[ch] for ch in S.chain],
                          pocket_def_type="ligand_xyz", ligand_xyz=S.ligand_xyz.tolist(),
                          n_lig_instances=S.n_lig_instances))
    BENCH.mkdir(parents=True, exist_ok=True)
    T.to_parquet(BENCH / "pdbt_pockets.parquet", index=False)
    (PROC / "selection_counts.json").write_text(json.dumps(c, indent=1))
    log(json.dumps(c))


# ----------------------------------------------------------------------------------------------- pairs + seal
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def stage_pairs():
    import make_blips_split as MB
    dest = SEALED / "pdbt_pairs.parquet"
    if dest.exists():
        raise SystemExit("data/sealed/pdbt_pairs.parquet exists: PDB-T pairs are created once (sealed).")
    S, c = select_sites()
    # DESIGN §2.6 point exclusion (label-free point cache)
    idx = pd.read_parquet(ROOT / "data/processed/cache/points/pdbt/index.parquet",
                          columns=["pocket_id", "status", "n_points", "d_coverage", "d_precision"])
    npt = dict(zip(idx.pocket_id, np.where(idx.status == "ok", idx.n_points.fillna(0), 0)))
    S["n_lmode_points"] = S.site_id.map(npt).fillna(0).astype(int)
    c["n_sites_cache_failed_or_missing"] = int((~S.site_id.isin(idx[idx.status == "ok"].pocket_id)).sum())
    c["n_sites_lt10_points"] = int((S.n_lmode_points < MIN_POINTS).sum())
    S["excluded_lt10"] = S.n_lmode_points < MIN_POINTS
    P0 = S[~S.excluded_lt10].reset_index(drop=True)
    c["n_sites_paired_pool"] = int(len(P0))
    # ligand universe of the pool
    from pocketcompare.splitutil import butina  # noqa: F401  (clusters were fixed in the sites stage)
    CL = pd.read_parquet(PROC / "ccd_clusters.parquet")
    Tfull = np.load(PROC / "ccd_tanimoto.npy")
    ccd_idx = {c_: i for i, c_ in enumerate(CL.ccd)}
    ccd_cluster = CL.cluster.to_numpy()
    top = set(json.loads((SPLITS / "blips_split_counts.json").read_text())["top20_promiscuous_ccds"])
    pairs, st = MB.make_pairs(P0, ccd_idx, Tfull, ccd_cluster, top, np.random.default_rng(SEED))
    # descriptive flags vs BLiPS-train v2 (qualifying CCDs of training sites)
    tr = pd.read_parquet(SPLITS / "blips_sites_v2.parquet")
    tr_ccd = {x for s in tr[tr.partition == "train"].q_ccds for x in s.split(";")}
    pairs["ccd_in_blips_train"] = np.where(pairs.label == 1, pairs.best_ccd_a.isin(tr_ccd) | pairs.best_ccd_b.isin(tr_ccd), None)
    pairs.insert(0, "pair_id", [f"pdbt:{i}" for i in range(len(pairs))])
    pos = pairs[pairs.label == 1]
    pos_groups = set(pos.group_a) | set(pos.group_b)
    vc = pos.pair_cluster.value_counts()
    gate = dict(created=time.strftime("%F %T"), prereg="PREREG2.md", rule=GATE,
                n_pos=int(len(pos)), n_neg=int((pairs.label == 0).sum()),
                n_pos_homology_groups=int(len(pos_groups)), n_pos_ligand_clusters=int(len(vc)),
                n_sites_in_pairs=int(len(set(pairs.site_a) | set(pairs.site_b))),
                n_groups_pool=int(P0.group_id.nunique()), n_sites_pool=int(len(P0)), n_proteins_pool=int(P0.protein.nunique()),
                max_pos_cluster_share=round(float(vc.iloc[0] / len(pos)), 4) if len(pos) else None,
                n_pos_shared_ge2=int((pos.n_shared_stratum == ">=2").sum()),
                n_pos_promiscuous=int(pos.promiscuous.sum()),
                n_pos_ccd_in_blips_train=int(pos.ccd_in_blips_train.astype(bool).sum()), **st)
    gate["pass"] = bool(gate["n_pos"] >= GATE["min_pos"] and gate["n_pos_homology_groups"] >= GATE["min_groups"]
                        and gate["n_pos_ligand_clusters"] >= GATE["min_clusters"])
    gate["verdict"] = "PASS: PDB-T supports the PREREG2 claims" if gate["pass"] else \
        "FAIL: PDB-T is reported descriptively only, no claims"
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "gate.json").write_text(json.dumps(gate, indent=1))
    log("GATE", json.dumps(gate))
    # ---- seal (write -> sha256 -> SUMS -> chmod 000; directory mode restored)
    mode = stat.S_IMODE(os.stat(SEALED).st_mode)
    try:
        os.chmod(SEALED, mode | stat.S_IWUSR)
        pairs.to_parquet(dest, index=False)
        h = sha256(dest)
        with open(ROOT / "data/sealed_SHA256SUMS.txt", "a") as fh:
            fh.write(f"{h}  data/sealed/pdbt_pairs.parquet\n")
        os.chmod(dest, 0)
    finally:
        os.chmod(SEALED, mode)
    c["sealed_sha256"] = h
    gate["sealed_sha256"] = h
    (RES / "gate.json").write_text(json.dumps(gate, indent=1))
    # ---- public site table (no ligand identities)
    cols = ["site_id", "pdb_id", "chain", "entity_id", "protein", "uniprot", "sid", "group_id", "release_date",
            "resolution", "methods", "structure_path", "n_lig_atoms", "n_lig_instances", "n_contact_res",
            "max_chains_contact", "n_lmode_points", "excluded_lt10"]
    S["hom_component"] = S.group_id          # column names read by scripts/eval_pdbt.py
    S["excluded"] = S.excluded_lt10.astype(bool)
    S[cols + ["hom_component", "excluded"]].to_parquet(SPLITS / "pdbt_sites.parquet", index=False)
    c.update(n_pairs=int(len(pairs)), n_pos=gate["n_pos"], n_neg=gate["n_neg"], gate_pass=gate["pass"])
    (RES / "build_counts.json").write_text(json.dumps(c, indent=1, default=str))
    # ---- strip ligand identities from unsealed intermediates
    R = pd.read_parquet(PROC / "sites_raw.parquet")
    R.drop(columns=["q_ccds", "label_ccd", "label_ha", "label_cluster"]).to_parquet(PROC / "sites_raw.parquet", index=False)
    for f in ("ccd_tanimoto.npy", "ccd_clusters.parquet"):
        (PROC / f).unlink(missing_ok=True)
    log("sealed", h, json.dumps(c, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=("ccd", "sites", "pockets", "pairs"))
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    {"ccd": stage_ccd, "sites": lambda: stage_sites(a.workers), "pockets": stage_pockets, "pairs": stage_pairs}[a.stage]()


if __name__ == "__main__":
    main()
