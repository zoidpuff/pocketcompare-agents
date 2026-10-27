#!/usr/bin/env python
"""Homology graph over every protein chain used by the project (DESIGN §2.1, as amended in design round 2).

Nodes (one per protein chain):
  tough_m1            7,524 shipped single-chain structures (chain = file chain)
  prospeccts          non-decoy structures, every protein chain listed in `protein_chains` (decoys are point-mutated
                      copies of P1 structures -> same proteins, skipped)
  vertex              PDB-mirror entry, the chains carrying the Vertex HET instances (all protein chains if none of
                      them is a protein chain); entries missing from the mirror are reported, not represented
  burrow_train/dev    BURROW representative chains (pocket_detect data/processed/{train,dev}/manifest.csv)
  burrow_partner      BURROW assembly-partner chains of those entries (train/work/asm_partners_{train,dev}.fasta);
                      symmetry copies "X-n" are mapped to deposited chain X
  af_set              BURROW Track C AF set (AFDB v6 model per UniProt; data/processed/af/af_manifest.csv, all rows
                      with a model incl. status=excluded)
  ppi_l               PPI-L pocket chains (data/splits/ppi_l_pockets.parquet; `ppi_split` = train/val/test of the PPI agent)
  dimers              AFDB predicted dimers, both chains (data/processed/dimers/manifest.tsv)
BURROW's test union is NOT added (no split rule here refers to it; its af_set/dimer parts are already nodes).

Sequences = observed residues of the structure as read by Foldseek (`createdb`, auth chain ids); partner chains that
are not in the deposited mmCIF fall back to the BURROW fasta sequence (sequence-only node).

Edges (between unique sequences, "sid"; nodes with identical sequences share a sid and are trivially linked):
  seq: MMseqs2 all-vs-all, -s 7.5 --max-seqs 5000 -e 1e-3, kept by `pocketdetect.datasets.leakage.apply_rule`
       verbatim (E < 1e-3, fident >= 0.30, qcov >= 0.5 or tcov >= 0.5 or alnlen >= 80)
  fs : Foldseek all-vs-all on one structure per sid (length >= MIN_FS_LEN), --exhaustive-search 0, -s 7.5, -a (backtrace, needed for TM columns),
       --max-seqs 2000; edge iff qtmscore >= 0.5 AND ttmscore >= 0.5 (TM >= 0.5 normalised by both chains) in any
       of the two search directions.

Groups (design round 2): connected components are computed WITHIN each split dataset only
  (tough_m1, prospeccts, vertex, blips = burrow_train + burrow_dev + af_set, dimers); exclusion across datasets uses
  DIRECT edges only (consumers: make_tough_m1_split.py, make_blips_split.py). The global component is reported for
  information. Gate: largest within-dataset component <= 10 % of that dataset's nodes.

Outputs
  data/splits/homology_nodes.parquet        node table (+ sid, group ids, global component)
  data/splits/homology_edges.parquet        sid-level edges passing either rule (best seq / best fs statistics)
  data/splits/homology_components.json      component size distributions + gate
  data/processed/homology/                  sequences, raw filtered hits (not committed; used by verify_splits.py)
Usage: python scripts/data/build_homology_graph.py --threads 24 [--work /tmp/gm_splits/homology]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pocketdetect.datasets.leakage import M8_COLUMNS, RULE, apply_rule  # noqa: E402  (BURROW's rule, verbatim)

PD = Path("/cluster/project/beltrao/gmagnus/pocket_detect")
MIRROR = Path("/cluster/scratch/jjaenes/pdb")
FOLDSEEK = ROOT / "tools/foldseek/bin/foldseek"
MMSEQS = ROOT / "tools/mmseqs/bin/mmseqs"
OUT = ROOT / "data/splits"
PROC = ROOT / "data/processed/homology"
MIN_FS_LEN = 20
TM_MIN = 0.5
FS_COLS = ["query", "target", "fident", "alnlen", "qlen", "tlen", "evalue", "bits", "prob", "alntmscore",
           "qtmscore", "ttmscore"]
GROUP_DATASETS = {"tough_m1": ["tough_m1"], "prospeccts": ["prospeccts"], "vertex": ["vertex"],
                  "blips": ["burrow_train", "burrow_dev", "af_set"], "dimers": ["dimers"]}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def mirror(pdb: str) -> Path:
    pdb = pdb.lower()
    return MIRROR / pdb[1:3] / f"{pdb}.cif.gz"


def read_fasta(path: Path) -> dict[str, str]:
    out, name, buf = {}, None, []
    for line in open(path):
        line = line.rstrip()
        if line.startswith(">"):
            if name is not None:
                out[name] = "".join(buf)
            name, buf = line[1:].split()[0], []
        else:
            buf.append(line)
    if name is not None:
        out[name] = "".join(buf)
    return out


# ----------------------------------------------------------------------------------------------- nodes
def collect_nodes() -> tuple[pd.DataFrame, dict]:
    """Rows: node_id, dataset, uniprot, pdb_id, chain, file, chain_rule, pocket_ids, extra."""
    rows, info = [], {}
    # TOUGH-M1 (pocket table rebuilt with the file chain)
    t = pd.read_parquet(ROOT / "data/processed/benchmarks/tough_m1_pockets.parquet")
    for r in t.itertuples():
        rows.append(dict(node_id=f"tough_m1:{r.name}", dataset="tough_m1", uniprot=None, pdb_id=r.pdb_id,
                         chain=r.structure_chain, file=str(ROOT / r.structure_path), chain_rule="exact",
                         pocket_ids=r.pocket_id))
    # ProSPECCTs (structures only; no pair/label file is opened)
    p = pd.read_parquet(ROOT / "data/processed/benchmarks/prospeccts_pockets.parquet")
    p = p[~p.is_decoy.astype(bool) & p.structure_path.notna()]
    for path, g in p.groupby("structure_path", sort=True):
        stem = Path(path).parent.name + "/" + Path(path).name.split(".")[0]
        chains = sorted(set("".join(g.protein_chains.dropna().astype(str))))
        for ch in chains or ["*"]:
            rows.append(dict(node_id=f"prospeccts:{stem}:{ch}", dataset="prospeccts", uniprot=None,
                             pdb_id=g.pdb_id.iloc[0], chain=ch, file=str(ROOT / path),
                             chain_rule="exact" if ch != "*" else "all", pocket_ids=";".join(sorted(g.pocket_id))))
    info["prospeccts_decoys_skipped"] = int(pd.read_parquet(
        ROOT / "data/processed/benchmarks/prospeccts_pockets.parquet").is_decoy.astype(bool).sum())
    # Vertex
    v = pd.read_parquet(ROOT / "data/processed/benchmarks/vertex_pockets.parquet")
    missing = []
    for pdb, g in v.groupby("pdb_id", sort=True):
        f = mirror(pdb)
        if not f.exists():
            missing.append(pdb)
            continue
        chains = sorted({x.split(":")[0] for s in g.het_instances.dropna() for x in str(s).split(";") if ":" in x})
        up = ";".join(sorted(set(g.uniprot_ac.dropna().astype(str))))
        for ch in chains or ["*"]:
            rows.append(dict(node_id=f"vertex:{pdb}_{ch}", dataset="vertex", uniprot=up, pdb_id=pdb, chain=ch,
                             file=str(f), chain_rule="het_chain_or_all", pocket_ids=";".join(sorted(g.pocket_id))))
    info["vertex_entries_missing_from_mirror"] = missing
    # BURROW train/dev representatives + assembly partners
    for split in ("train", "dev"):
        m = pd.read_csv(PD / f"data/processed/{split}/manifest.csv", dtype={"chain": str, "pdb": str},
                        keep_default_na=False, na_values={"resolution": ["", "NaN"]})  # chain 'NA' is a real id
        m = m[m.status == "ok"]
        for r in m.itertuples():
            rows.append(dict(node_id=f"burrow_{split}:{r.entry_id}", dataset=f"burrow_{split}", uniprot=r.uniprot,
                             pdb_id=r.pdb, chain=r.chain, file=str(mirror(r.pdb)), chain_rule="exact",
                             pocket_ids=None))
        entries = set(m.entry_id)
        fa = read_fasta(PD / f"data/processed/train/work/asm_partners_{split}.fasta")
        seen = set()
        for h, seq in fa.items():
            entry, _, ch = h.partition("|")
            if entry not in entries:
                continue
            pdb = entry.split("__")[1].rsplit("_", 1)[0]
            base = ch.split("-")[0]
            if (pdb, base) in seen:
                continue
            seen.add((pdb, base))
            rows.append(dict(node_id=f"burrow_partner_{split}:{pdb}_{base}", dataset="burrow_partner",
                             uniprot=None, pdb_id=pdb, chain=base, file=str(mirror(pdb)), chain_rule="exact",
                             pocket_ids=None, fallback_seq=seq, partner_of=split))
    # AF set (Track C)
    a = pd.read_csv(PD / "data/processed/af/af_manifest.csv")
    for r in a.itertuples():
        f = PD / "data/processed/af" / str(r.model_path)
        if not isinstance(r.model_path, str) or not f.exists():
            continue
        rows.append(dict(node_id=f"af_set:{r.acc}", dataset="af_set", uniprot=r.acc, pdb_id=None, chain="A",
                         file=str(f), chain_rule="exact", pocket_ids=None, af_status=r.status))
    info["af_set_without_model"] = int(len(a) - sum(1 for r in rows if r["dataset"] == "af_set"))
    # PPI-L (Pasteur PPI pocketome; split assigned by the PPI agent): one node per (pdb, chain) with its split
    pl_path = ROOT / "data/splits/ppi_l_pockets.parquet"
    if pl_path.exists():
        pl = pd.read_parquet(pl_path, columns=["pdb", "chain", "uniprot", "split", "pocket_id"])
        for (pdb, ch), gp in pl.groupby(["pdb", "chain"], sort=True):
            splits = sorted(set(gp.split.dropna()))
            rows.append(dict(node_id=f"ppi_l:{pdb}_{ch}", dataset="ppi_l", uniprot=";".join(sorted(set(gp.uniprot.dropna()))),
                             pdb_id=pdb, chain=ch, file=str(mirror(pdb)), chain_rule="exact",
                             pocket_ids=";".join(sorted(gp.pocket_id)), ppi_split=";".join(splits)))
        info["ppi_l_source"] = "data/splits/ppi_l_pockets.parquet (columns pdb, chain, split only)"
    # AFDB dimers, both chains
    d = pd.read_csv(ROOT / "data/processed/dimers/manifest.tsv", sep="\t")
    for r in d.itertuples():
        for ch, up in (("A", r.uniprotAccession_1), ("B", r.uniprotAccession_2)):
            rows.append(dict(node_id=f"dimers:{r.modelEntityId}_{ch}", dataset="dimers", uniprot=up, pdb_id=None,
                             chain=ch, file=str(r.path), chain_rule="exact", pocket_ids=None,
                             dimer_type=r.type, organism=r.organism))
    nodes = pd.DataFrame(rows)
    assert nodes.node_id.is_unique, nodes.node_id[nodes.node_id.duplicated()].head()
    return nodes, info


# ----------------------------------------------------------------------------------------------- foldseek db
def run(cmd, **kw):
    cmd = [str(c) for c in cmd]
    log("$", " ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True, **kw)


def read_db_seqs(prefix: Path) -> dict[int, str]:
    data = open(prefix, "rb").read()
    out = {}
    for line in open(str(prefix) + ".index"):
        k, off, ln = line.split()
        out[int(k)] = data[int(off):int(off) + int(ln)].rstrip(b"\x00\n").decode()
    return out


def write_headers(prefix: Path, key2name: dict[int, str], dbtype_src: Path) -> None:
    """(Re)write <prefix>_h so that convertalis reports our own unique names (sids)."""
    off = 0
    for suf in ("_h", "_h.index", "_h.dbtype"):  # createsubdb soft-links these to the parent DB: never write through
        p = Path(str(prefix) + suf)
        if p.is_symlink() or p.exists():
            p.unlink()
    with open(str(prefix) + "_h", "wb") as fh, open(str(prefix) + "_h.index", "w") as fi:
        for k in sorted(key2name):
            b = (key2name[k] + "\n").encode() + b"\x00"
            fh.write(b)
            fi.write(f"{k}\t{off}\t{len(b)}\n")
            off += len(b)
    with open(str(dbtype_src), "rb") as src, open(str(prefix) + "_h.dbtype", "wb") as dst:
        dst.write(src.read())


def build_structure_db(nodes: pd.DataFrame, work: Path, threads: int) -> pd.DataFrame:
    files = sorted(set(nodes.file.dropna()))
    exists = [f for f in files if Path(f).exists()]
    db = work / "fsdb" / "all"
    db.parent.mkdir(parents=True, exist_ok=True)
    # Foldseek names entries <basename>_<chain>[_MODEL_n] and orders files itself; basenames collide across datasets
    # (e.g. TOUGH-M1 vs ProSPECCTs '1a42A.pdb'), so every input is staged as a symlink f<index>.<ext>.
    links = work / "fsdb" / "links"
    if not Path(str(db) + ".lookup").exists():
        links.mkdir(parents=True, exist_ok=True)
        staged = []
        for i, f in enumerate(exists):
            ext = "".join(Path(f).suffixes[-2:]) if f.endswith(".gz") else Path(f).suffix
            ln = links / f"f{i:06d}{ext}"
            if ln.is_symlink() or ln.exists():
                ln.unlink()
            ln.symlink_to(f)
            staged.append(str(ln))
        (work / "fsdb" / "files.tsv").write_text("\n".join(staged) + "\n")
        (work / "fsdb" / "files_map.tsv").write_text("\n".join(f"f{i:06d}\t{f}" for i, f in enumerate(exists)) + "\n")
        run([FOLDSEEK, "createdb", work / "fsdb" / "files.tsv", db, "--chain-name-mode", "1", "--threads", threads,
             "-v", "1"])
    look = pd.read_csv(str(db) + ".lookup", sep="\t", header=None, names=["key", "name", "fileidx"])
    assert look.name.str.match(r"^f\d{6}_").all(), look.name.head()
    look["file"] = [exists[int(n[1:7])] for n in look.name]
    # name = f<index>_<chain> or f<index>_MODEL_<n>_<chain> (multi-model files); keep model 1 only
    def parse(n):
        rest = n[8:]
        if rest.startswith("MODEL_"):
            _, model, chain = rest.split("_", 2)
            return int(model), chain
        return 1, rest
    parsed = [parse(n) for n in look.name]
    look["model"] = [m for m, _ in parsed]
    look["chain"] = [c for _, c in parsed]
    look = look[look.model == look.groupby("file").model.transform("min")]
    look = look.drop_duplicates(["file", "chain"], keep="first")
    seqs = read_db_seqs(db)
    look["seq"] = look.key.map(seqs)
    return look


# ----------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=24)
    ap.add_argument("--work", default="/tmp/gm_splits/homology")
    args = ap.parse_args()
    t0 = time.time()
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    nodes, info = collect_nodes()
    log("nodes collected", nodes.dataset.value_counts().to_dict())
    look = build_structure_db(nodes, work, args.threads)
    log("foldseek entries", len(look))

    # map nodes -> foldseek entries
    by_file = {f: g for f, g in look.groupby("file")}
    keys, seqs, n_rows = [], [], []
    expanded = []
    for r in nodes.itertuples():
        g = by_file.get(r.file)
        sel = None
        if g is not None:
            if r.chain_rule == "all" or r.chain == "*":
                sel = g
            else:
                sel = g[g.chain == r.chain]
                if len(sel) == 0 and r.chain_rule == "het_chain_or_all":
                    sel = None  # resolved below (ligand-only chain)
        if sel is not None and len(sel):
            k = sel.iloc[0]
            expanded.append((r.node_id, int(k.key), k.seq, "structure"))
        else:
            expanded.append((r.node_id, None, None, None))
    em = pd.DataFrame(expanded, columns=["node_id", "fs_key", "seq", "seq_source"])
    nodes = nodes.merge(em, on="node_id", how="left")
    # Vertex: HET chain is not a protein chain -> all protein chains of that entry (one node per chain)
    vfix = nodes[(nodes.dataset == "vertex") & nodes.fs_key.isna()]
    extra = []
    for pdb, g in vfix.groupby("pdb_id"):
        present = set(nodes[(nodes.dataset == "vertex") & (nodes.pdb_id == pdb) & nodes.fs_key.notna()].chain)
        if present:
            continue  # other HET chains of this entry are protein chains already
        lk = by_file.get(g.file.iloc[0])
        if lk is None:
            continue
        for k in lk.itertuples():
            extra.append(dict(node_id=f"vertex:{pdb}_{k.chain}", dataset="vertex", uniprot=g.uniprot.iloc[0],
                              pdb_id=pdb, chain=k.chain, file=g.file.iloc[0], chain_rule="all_protein_chains",
                              pocket_ids=g.pocket_ids.iloc[0], fs_key=int(k.key), seq=k.seq, seq_source="structure"))
    nodes = nodes[~nodes.node_id.isin(vfix.node_id)]
    if extra:
        nodes = pd.concat([nodes, pd.DataFrame(extra)], ignore_index=True).drop_duplicates("node_id")
    info["vertex_het_chain_not_protein_entries"] = int(vfix.pdb_id.nunique())
    # BURROW representatives Foldseek could not read -> BURROW's stored observed sequence (sequence-only node)
    obs_all = read_fasta(PD / "data/processed/train/work/final_all_obs.fasta")
    m = nodes.dataset.isin(["burrow_train", "burrow_dev"]) & nodes.fs_key.isna()
    nodes.loc[m, "fallback_seq"] = [obs_all.get(n.split(":", 1)[1]) for n in nodes.loc[m, "node_id"]]
    # partners not present in the deposited file -> sequence-only from BURROW's fasta
    m = nodes.dataset.isin(["burrow_partner", "burrow_train", "burrow_dev"]) & nodes.fs_key.isna() & nodes.fallback_seq.notna()
    nodes.loc[m, "seq"] = nodes.loc[m, "fallback_seq"]
    nodes.loc[m, "seq_source"] = "fasta"
    unresolved = nodes[nodes.seq.isna()]
    info["nodes_unresolved"] = unresolved.groupby("dataset").size().to_dict()
    info["nodes_unresolved_examples"] = unresolved.node_id.head(20).tolist()
    nodes = nodes[nodes.seq.notna() & (nodes.seq.str.len() > 0)].copy()
    nodes = nodes.drop(columns=["fallback_seq"])
    nodes["seq_len"] = nodes.seq.str.len()

    # sanity: BURROW representatives' Foldseek sequence vs BURROW's stored representative sequence (observed)
    obs = read_fasta(PD / "data/processed/train/work/final_all_obs.fasta")
    br = nodes[nodes.dataset.isin(["burrow_train", "burrow_dev"])]
    eq = [obs.get(n.split(":", 1)[1]) == s for n, s in zip(br.node_id, br.seq)]
    info["burrow_rep_seq_equal_to_burrow_obs"] = f"{sum(eq)}/{len(eq)}"
    info["seq_source_counts"] = {f"{a}/{b}": int(v) for (a, b), v in nodes.groupby(["dataset", "seq_source"]).size().items()}

    # unique sequences -> sid
    useq = sorted(set(nodes.seq))
    sid_of = {s: f"s{i:06d}" for i, s in enumerate(useq)}
    nodes["sid"] = nodes.seq.map(sid_of)
    with open(PROC / "sequences.fasta", "w") as fh:
        for s in useq:
            fh.write(f">{sid_of[s]}\n{s}\n")
    log("unique sequences", len(useq))

    # ---------------- MMseqs2 all-vs-all
    import hashlib
    seq_hash = hashlib.sha256((PROC / "sequences.fasta").read_bytes()).hexdigest()
    stamp = PROC / "sequences.sha256"
    if not stamp.exists() or stamp.read_text().strip() != seq_hash:  # sequence set changed -> redo both searches
        for f in ("mmseqs_allvsall.m8", "foldseek_allvsall_tm04.parquet"):
            (PROC / f).unlink(missing_ok=True)
        stamp.write_text(seq_hash + "\n")
    m8 = PROC / "mmseqs_allvsall.m8"
    if not m8.exists():
        mw = work / "mmseqs"
        import shutil
        shutil.rmtree(mw, ignore_errors=True)
        mw.mkdir()
        env = {**os.environ, "OMP_NUM_THREADS": str(args.threads)}
        run([MMSEQS, "createdb", PROC / "sequences.fasta", mw / "db", "--dbtype", "1", "-v", "1"], env=env)
        run([MMSEQS, "search", mw / "db", mw / "db", mw / "res", mw / "tmp", "-s", "7.5", "--max-seqs", "5000",
             "-e", "1e-3", "--threads", args.threads, "-v", "1"], env=env)
        run([MMSEQS, "convertalis", mw / "db", mw / "db", mw / "res", str(m8) + ".part", "--format-output",
             ",".join(M8_COLUMNS), "--threads", args.threads, "-v", "1"], env=env)
        os.replace(str(m8) + ".part", m8)
    s8 = pd.read_csv(m8, sep="\t", header=None, names=M8_COLUMNS)
    s8 = s8[s8["query"] != s8["target"]]
    s8 = s8[apply_rule(s8)]
    log("mmseqs rule hits", len(s8))

    # ---------------- Foldseek all-vs-all on one structure per sid
    fs_out = PROC / "foldseek_allvsall_tm04.parquet"
    if not fs_out.exists():
        import shutil
        shutil.rmtree(work / "fsrep", ignore_errors=True)
        rep = (nodes[nodes.fs_key.notna() & (nodes.seq_len >= MIN_FS_LEN)]
               .sort_values(["sid", "node_id"]).drop_duplicates("sid"))
        fw = work / "fsrep"
        fw.mkdir(exist_ok=True)
        (fw / "ids.txt").write_text("\n".join(str(int(k)) for k in rep.fs_key) + "\n")
        src = work / "fsdb" / "all"
        for suf in ("", "_ss", "_ca"):
            run([FOLDSEEK, "createsubdb", fw / "ids.txt", str(src) + suf, str(fw / "rep") + suf, "-v", "1"])
        write_headers(fw / "rep", dict(zip(rep.fs_key.astype(int), rep.sid)), Path(str(src) + "_h.dbtype"))
        run([FOLDSEEK, "search", fw / "rep", fw / "rep", fw / "aln", fw / "tmp", "--threads", args.threads,
             "-s", "7.5", "--exhaustive-search", "0", "--max-seqs", "2000", "-e", "10", "-a", "-v", "1"])
        run([FOLDSEEK, "convertalis", fw / "rep", fw / "rep", fw / "aln", fw / "aln.m8", "--format-output",
             ",".join(FS_COLS), "--threads", args.threads, "-v", "1"])
        chunks = []
        for ch in pd.read_csv(fw / "aln.m8", sep="\t", header=None, names=FS_COLS, chunksize=5_000_000):
            ch = ch[(ch["query"] != ch["target"]) & (np.minimum(ch.qtmscore, ch.ttmscore) >= 0.4)]
            chunks.append(ch)
        fs = pd.concat(chunks, ignore_index=True)
        fs.to_parquet(fs_out, index=False)
        info["foldseek_reps"] = int(len(rep))
    fs = pd.read_parquet(fs_out)
    fs = fs[np.minimum(fs.qtmscore, fs.ttmscore) >= TM_MIN]
    log("foldseek TM>=0.5 (both) hits", len(fs))

    # ---------------- sid-level edges (unordered, best statistics per pair)
    def unordered(df):
        a = np.where(df["query"] < df["target"], df["query"], df["target"])
        b = np.where(df["query"] < df["target"], df["target"], df["query"])
        return df.assign(sid_a=a, sid_b=b)
    se = (unordered(s8).sort_values(["bits"], ascending=False).drop_duplicates(["sid_a", "sid_b"])
          [["sid_a", "sid_b", "fident", "alnlen", "qcov", "tcov", "evalue"]].assign(seq_edge=True))
    fe = unordered(fs).assign(tm_min=lambda d: np.minimum(d.qtmscore, d.ttmscore))
    fe = (fe.sort_values("tm_min", ascending=False).drop_duplicates(["sid_a", "sid_b"])
          [["sid_a", "sid_b", "tm_min", "alntmscore"]].rename(columns={"alntmscore": "fs_alntm"}).assign(fs_edge=True))
    edges = se.merge(fe, on=["sid_a", "sid_b"], how="outer")
    edges["seq_edge"] = edges.seq_edge.fillna(False).astype(bool)
    edges["fs_edge"] = edges.fs_edge.fillna(False).astype(bool)
    edges["alnlen"] = edges.alnlen.astype("Int32")
    edges["evalue"] = edges.evalue.astype("float32")
    for c in ("fident", "qcov", "tcov", "tm_min", "fs_alntm"):
        edges[c] = edges[c].astype("float32")
    edges = edges.sort_values(["sid_a", "sid_b"]).reset_index(drop=True)
    log("edges", len(edges), "seq", int(edges.seq_edge.sum()), "fs", int(edges.fs_edge.sum()),
        "fs-only", int((edges.fs_edge & ~edges.seq_edge).sum()))

    # ---------------- components
    sids = np.array([sid_of[s] for s in useq])
    idx = {s: i for i, s in enumerate(sids)}
    ea = edges.sid_a.map(idx).to_numpy()
    eb = edges.sid_b.map(idx).to_numpy()

    def components(sub_sids: set[str]) -> dict[str, int]:
        keep = np.array([s in sub_sids for s in sids])
        msk = keep[ea] & keep[eb]
        n = len(sids)
        g = coo_matrix((np.ones(msk.sum()), (ea[msk], eb[msk])), shape=(n, n))
        _, lab = connected_components(g, directed=False)
        return {s: int(lab[idx[s]]) for s in sub_sids}

    comp = {}
    glob = components(set(sids))
    nodes["global_component"] = nodes.sid.map(glob)
    nodes["group_dataset"] = None
    nodes["group_id"] = None
    for gname, dsets in GROUP_DATASETS.items():
        m = nodes.dataset.isin(dsets)
        if gname == "blips":
            m &= ~((nodes.dataset == "af_set") & (nodes.af_status != "included"))
        cm = components(set(nodes.loc[m, "sid"]))
        # renumber by size (largest = 0) for readability
        lab = nodes.loc[m, "sid"].map(cm)
        order = lab.value_counts().index.tolist()
        ren = {c: i for i, c in enumerate(order)}
        nodes.loc[m, "group_dataset"] = gname
        nodes.loc[m, "group_id"] = [f"{gname}:g{ren[c]:05d}" for c in lab]
        sizes = lab.value_counts()
        comp[gname] = dict(n_nodes=int(m.sum()), n_groups=int(len(sizes)), largest=int(sizes.iloc[0]),
                           largest_frac=round(float(sizes.iloc[0] / m.sum()), 4),
                           top10=[int(x) for x in sizes.head(10)],
                           size_hist={k: int(v) for k, v in pd.cut(sizes, [0, 1, 2, 5, 10, 50, 100, 500, 1e9],
                                      labels=["1", "2", "3-5", "6-10", "11-50", "51-100", "101-500", ">500"])
                                      .value_counts().sort_index().items()},
                           gate_largest_le_10pct=bool(sizes.iloc[0] / m.sum() <= 0.10))
    gs = nodes.global_component.value_counts()
    comp["global_info_only"] = dict(n_nodes=int(len(nodes)), n_components=int(len(gs)), largest=int(gs.iloc[0]),
                                    largest_frac=round(float(gs.iloc[0] / len(nodes)), 4),
                                    top10=[int(x) for x in gs.head(10)])
    # direct-edge cross-dataset summary (node counts with >=1 direct edge to another dataset)
    sid_ds = nodes.groupby("sid").dataset.agg(lambda x: set(x)).to_dict()
    nb = {}
    for a, b in zip(edges.sid_a, edges.sid_b):
        nb.setdefault(a, set()).update(sid_ds.get(b, ()))
        nb.setdefault(b, set()).update(sid_ds.get(a, ()))
    for s, ds in sid_ds.items():  # identical sequences are direct neighbours
        nb.setdefault(s, set()).update(ds)
    cross = {}
    for dsn, g in nodes.groupby("dataset"):
        cross[dsn] = {o: int(sum(o in nb.get(s, ()) for s in g.sid)) for o in sorted(nodes.dataset.unique())
                      if o != dsn}
    comp["direct_edge_node_counts"] = cross

    nodes_out = nodes.drop(columns=["seq", "file"]).copy()
    nodes_out["fs_key"] = nodes_out.fs_key.astype("Int64")
    nodes_out.to_parquet(OUT / "homology_nodes.parquet", index=False)
    edges.to_parquet(OUT / "homology_edges.parquet", index=False, compression="zstd", compression_level=19)
    nodes[["node_id", "sid", "file", "chain", "fs_key"]].to_parquet(PROC / "node_files.parquet", index=False)
    s8.to_parquet(PROC / "mmseqs_rule_hits.parquet", index=False)
    meta = dict(info=info, components=comp, rule_seq=RULE, rule_fs=f"qtmscore>={TM_MIN} and ttmscore>={TM_MIN}",
                n_nodes=int(len(nodes)), n_sids=int(len(sids)), n_edges=int(len(edges)),
                n_seq_edges=int(edges.seq_edge.sum()), n_fs_edges=int(edges.fs_edge.sum()),
                nodes_per_dataset=nodes.dataset.value_counts().to_dict(),
                foldseek_min_len=MIN_FS_LEN, tools=dict(foldseek=str(FOLDSEEK), mmseqs=str(MMSEQS)),
                wall_s=round(time.time() - t0, 1))
    (OUT / "homology_components.json").write_text(json.dumps(meta, indent=1, default=str))
    log(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("n_nodes", "n_groups", "largest", "largest_frac")}
                    for k, v in comp.items() if k != "direct_edge_node_counts"}))
    log("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
