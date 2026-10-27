"""BLiPS pocket tables for the point cache (DESIGN §2.2 / §2.6; scripts/data/prep_blips_pockets.py).

One row per BLiPS site in the format read by ``scripts/build_point_cache.py`` (pocket_def_type ``ligand_xyz``:
the L-mode pocket = BURROW points <= 4 Å of the given heavy-atom coordinates).

train/val (dataset ``blips``)
    structure = BURROW train/dev representative chain (pocket_detect data/processed/{train,dev}/manifest.csv);
    the manifest's /cluster/work/beltrao/shared/rsyncPDB/... path is remapped to the mounted mirror
    /cluster/scratch/jjaenes/pdb/<mid2>/<id>.cif.gz; featurised on that author chain only (BURROW's training
    input, ``trainset.load_input``).  Ligands = the entry's pooled ligand instances (``lig_coords``, already
    superposed on the representative chain) of the site (``lig_site == site_index``) whose CCD is in the site's
    qualifying set ``q_ccds`` (the set that defines the site's labels); the L-mode pocket uses the UNION of their
    heavy atoms.  ``alt_ligand_xyz`` = instances of the label ligand (``label_ccd``) only (sensitivity).
test holo (dataset ``blips_test_holo``)
    structure = the LIGYSIS representative chain of the af_set site (``rep_chain``), featurised on that chain;
    sites without one (non-benchmark LIGYSIS sites) use the source chain of their first qualifying transferred
    instance (Track C transfer order).  Ligands = the site's transferred instances (Track C gt, status ok) whose
    CCD is in ``q_ccds``, re-transferred from their source PDB entry onto that chain with Track C's own routine
    (build_af_set.transfer_instance: site-CA Kabsch, same contact rules), accepted if RMSD <= 2 Å.  If none is
    accepted, the first qualifying instance's own source chain is used instead (``holo_chain_source`` =
    ``first_ligand_entry_fallback``).
test AF (dataset ``blips_test_af``)
    structure = AFDB v6 model (af_mode=True).  Ligands = transferred instances on the model (af/gt/*.json.gz)
    whose CCD is in ``q_ccds`` with local RMSD <= 2 Å (Track C acceptance); if none, the lowest-RMSD qualifying
    instance is used and ``lig_fallback`` is set.
Test tables carry no ligand identities (CCD codes stay in the sealed site file).
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
OLD_MIRROR = "/cluster/work/beltrao/shared/rsyncPDB/data/structures/divided/mmCIF/"
MIRROR = Path("/cluster/scratch/jjaenes/pdb")
LIG_RMSD_ACCEPT = 2.0


def remap_mmcif(path: str) -> str:
    if not path.startswith(OLD_MIRROR):
        raise ValueError(f"unexpected structure path {path}")
    return str(MIRROR / path[len(OLD_MIRROR):])


def mirror_path(pdb: str) -> str:
    return str(MIRROR / pdb[1:3] / f"{pdb}.cif.gz")


def _manifests() -> pd.DataFrame:
    out = []
    for split in ("train", "dev"):
        m = pd.read_csv(PD / f"data/processed/{split}/manifest.csv", dtype={"chain": str, "pdb": str},
                        keep_default_na=False)
        out.append(m[m.status == "ok"].assign(burrow_split=split))
    return pd.concat(out, ignore_index=True).set_index("entry_id")


def trainval_table(sites: pd.DataFrame) -> pd.DataFrame:
    """``sites`` = BLiPS train/val rows of data/splits/blips_sites.parquet (with q_ccds / label_ccd)."""
    man = _manifests()
    rows = []
    for protein, g in sites.groupby("protein", sort=True):
        r = man.loc[protein]
        with np.load(PD / r.npz, allow_pickle=False) as d:
            a = {k: d[k] for k in ("lig_coords", "lig_ptr", "lig_site", "lig_ccd", "lig_source")}
            meta = json.loads(str(d["meta_json"]))
        assert meta["chain"] == r.chain
        for s in g.itertuples():
            q = set(s.q_ccds.split(";"))
            sel = np.flatnonzero((a["lig_site"] == int(s.site_index)) & np.isin(a["lig_ccd"], list(q)))
            lab = [i for i in sel if a["lig_ccd"][i] == s.label_ccd]
            xyz = np.concatenate([a["lig_coords"][a["lig_ptr"][i]:a["lig_ptr"][i + 1]] for i in sel]) if len(sel) \
                else np.zeros((0, 3), np.float32)
            alt = np.concatenate([a["lig_coords"][a["lig_ptr"][i]:a["lig_ptr"][i + 1]] for i in lab]) if lab \
                else np.zeros((0, 3), np.float32)
            rows.append(dict(pocket_id=s.site_id, structure_key=protein, structure_path=remap_mmcif(r.structure_path),
                             chains=[r.chain], pocket_def_type="ligand_xyz",
                             ligand_xyz=xyz.astype(np.float64).ravel(), alt_ligand_xyz=alt.astype(np.float64).ravel(),
                             n_lig_instances=int(len(sel)), n_lig_sources=int(len(set(a["lig_source"][sel]))),
                             n_label_instances=int(len(lab))))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- test (af_set)
def _af_gt(structure_id: str) -> dict:
    with gzip.open(PD / f"data/processed/af/gt/{structure_id}.json.gz", "rt") as fh:
        return json.load(fh)


def test_af_rows(sites: pd.DataFrame) -> pd.DataFrame:
    """``sites``: sealed BLiPS-test rows (site_id, structure_id, site_name, q_ccds) -> AF-model pocket table."""
    man = pd.read_csv(PD / "data/processed/af/af_manifest.csv").set_index("structure_id")
    rows = []
    for sid_, g in sites.groupby("structure_id", sort=True):
        gt = _af_gt(sid_)
        by = {s["site_name"]: s for s in gt["sites"]}
        for s in g.itertuples():
            q = set(s.q_ccds.split(";"))
            ligs = [l for l in by[s.site_name]["ligands"] if l["resname"] in q]
            acc = [l for l in ligs if l["rmsd"] <= LIG_RMSD_ACCEPT]
            fb = False
            if not acc and ligs:
                acc, fb = [min(ligs, key=lambda l: l["rmsd"])], True
            xyz = np.vstack([np.asarray(l["coords"], float).reshape(-1, 3) for l in acc]) if acc else np.zeros((0, 3))
            rows.append(dict(pocket_id=s.site_id, structure_key=sid_,
                             structure_path=str(PD / "data/processed/af" / man.loc[sid_, "model_path"]),
                             chains=[gt["chain"]], pocket_def_type="ligand_xyz", ligand_xyz=xyz.ravel(),
                             n_lig_instances=len(acc), lig_fallback=fb,
                             lig_rmsd_max=float(max(l["rmsd"] for l in acc)) if acc else np.nan,
                             site_plddt_mean=by[s.site_name].get("plddt_mean")))
    return pd.DataFrame(rows)


class _RepChainView:
    """Duck-typed stand-in for build_af_set's AF model object: ``ca`` {k: xyz}, ``seq``."""

    def __init__(self, chain, uni_of_k: dict):
        self.ca = chain.ca
        self.seq = chain.seq
        self.uni_of_k = uni_of_k


def holo_protein(task: dict) -> list:
    """One test protein: re-transfer the qualifying ligand instances of each site onto its representative chain.
    task = {acc, sites: [{site_id, site_name, rep_chain, residues, keys: [ligand keys]}]}."""
    import sys
    sys.path.insert(0, str(PD / "scripts/data"))
    import build_af_set as B
    B.MMCIF_DIR = MIRROR
    if "sifts" not in B.G:
        sifts = pd.read_csv(PD / "data/processed/af/external/pdb_chain_uniprot.tsv.gz", sep="\t", comment="#",
                            dtype=str)
        B.G["_sifts_df"] = sifts
        B.G["sifts"] = {}
        B.G["resolution"] = {}
    acc = task["acc"]
    if acc not in B.G.setdefault("_loaded_accs", set()):
        s2 = B.G["_sifts_df"]
        s2 = s2[s2.SP_PRIMARY == acc]
        for r in s2.itertuples(index=False):
            try:
                B.G["sifts"].setdefault((r.PDB, r.SP_PRIMARY), []).append(
                    (r.CHAIN, int(r.RES_BEG), int(r.RES_END), int(r.SP_BEG), int(r.SP_END)))
            except ValueError:
                continue
        B.G["_loaded_accs"].add(acc)
    entry_cache: dict = {}
    reps: dict = {}

    def target(rc):
        if rc not in reps:
            pdb, ch = rc.split("_", 1)
            st = B.read_first_model(Path(mirror_path(pdb)))
            chain = next((c for c in st[0] if c.name == ch), None)
            if chain is None:
                raise ValueError(f"chain {ch} not in {pdb}")
            C = B.Chain(chain, label_seq=True)
            l2u = {}
            for _, rb, re_, sb, _se in [x for x in B.G["sifts"].get((pdb, acc), []) if x[0] == ch]:
                for ls in range(rb, re_ + 1):
                    l2u[ls] = sb + (ls - rb)
            u2k = {l2u[ls]: k for k, ls in enumerate(C.lseq) if ls in l2u}
            if not u2k:
                raise ValueError("no SIFTS mapping for the holo chain")
            reps[rc] = (_RepChainView(C, {v: k for k, v in u2k.items()}), u2k)
        return reps[rc]

    out = []
    for s in task["sites"]:
        rec = dict(pocket_id=s["site_id"], structure_key=None, chains=None, structure_path=None,
                   pocket_def_type="ligand_xyz", ligand_xyz=np.zeros(0), n_lig_instances=0, holo_error=None,
                   holo_n_tried=len(s["keys"]), holo_rmsd_max=np.nan, holo_chain_source=None, holo_attempts="")
        cands = [(s["rep_chain"], s.get("holo_chain_source"))]
        if s.get("fallback_chain") and s["fallback_chain"] != s["rep_chain"]:
            cands.append((s["fallback_chain"], "first_ligand_entry_fallback"))
        errs, attempts = [], []
        for rc, src in cands:
            try:
                if not rc:
                    raise ValueError("no holo chain")
                view, u2k = target(rc)
                ok = []
                for key in s["keys"]:
                    lr = B.transfer_instance(key, s["residues"], view, u2k, entry_cache, acc)
                    attempts.append(f"{rc}:{lr['status']}:{lr['rmsd']:.2f}" if lr["status"] == "ok"
                                    else f"{rc}:{lr['status']}")
                    if lr["status"] == "ok" and lr["rmsd"] <= LIG_RMSD_ACCEPT:
                        ok.append(lr)
                if not ok:
                    raise ValueError("no qualifying ligand instance re-transferred (<= 2 A)")
                pdb, ch = rc.split("_", 1)
                rec.update(structure_key=rc, structure_path=mirror_path(pdb), chains=[ch], holo_chain_source=src,
                           ligand_xyz=np.vstack([l["coords"] for l in ok]).ravel(), n_lig_instances=len(ok),
                           holo_rmsd_max=float(max(l["rmsd"] for l in ok)),
                           holo_from_rep_entry=any(l["pdb"] == pdb for l in ok))
                break
            except Exception as e:  # noqa: BLE001
                errs.append(f"{src}: {type(e).__name__}: {e}")
        if rec["structure_key"] is None:
            rec["holo_error"] = " | ".join(errs)
        rec["holo_attempts"] = ";".join(attempts)
        out.append(rec)
    return out
