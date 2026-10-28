#!/usr/bin/env python
"""PDB-T step 3 (PREREG2): leakage removal against every training source + PDB-T homology components.

    python scripts/data/pdbt_homology.py --threads 24 [--work /tmp/gm_pdbt]

PDB-T chains = the primary chains of the sites in data/processed/pdbt/sites_raw.parquet.  Their sequences are the
observed residues as read by Foldseek ``createdb`` (auth chain ids), exactly as build_homology_graph.py reads every
other node; unique sequences get ids ``p<6 digits>``.
Training sources (direct-edge targets; node ids of data/splits/homology_nodes.parquet, sequences = the graph's own
data/processed/homology/sequences.fasta, structures = its Foldseek representative DB, one per sid):
  blips_v2_trainval  BLiPS train/val v2 sites' proteins (blips_sites_v2.parquet, partition train | val)
  burrow_rep         BURROW train + dev representative chains (BURROW's training / model-selection data)
  burrow_partner     BURROW assembly-partner chains of those entries (context BURROW saw in training)
  ppips_trainval     both chains of every PPIPS train / val complex (dimers:<complex>_{A,B}; A4b / L4 training data)
  tough_m1_dev       TOUGH-M1-dev pockets' chains
Edge rule = build_homology_graph.py: MMseqs2 search -s 7.5 --max-seqs 5000 -e 1e-3 -a, kept by BURROW's
  apply_rule verbatim; or exhaustive Foldseek (--exhaustive-search 1, -e 10, -a) with min(qTM, tTM) >= 0.5,
  exact TM (--exact-tmscore 1) for every hit with approximate min-TM in [0.45, 0.60), approximate >= 0.60 accepted.
  Both search directions (PDB-T -> train and train -> PDB-T) are run and either counts; identical sequences are
  edges.  A PDB-T sequence with any edge to a training sid is removed (all its chains / sites).
Freshness (not leakage): a PDB-T sequence IDENTICAL to a chain of TOUGH-M1-test, ProSPECCTs, Vertex or BLiPS-test
  (af_set) is removed.  Chains whose entity UniProt accession equals an af_set accession are flagged
  (``test_uniprot_af_set``, reported only: not an exact sequence).
PDB-T groups: MMseqs2 + exhaustive Foldseek all-vs-all among the PDB-T sequences (same rule); groups = connected
  components of the subgraph induced by the KEPT sequences (bootstrap units).
Output: data/processed/pdbt/chain_homology.parquet (pdb_id, chain, sid, protein, remove_*, touch_*, group_id),
        data/processed/pdbt/homology_counts.json, data/processed/pdbt/pdbt_edges.parquet, train_hits.parquet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
from pocketdetect.datasets.leakage import M8_COLUMNS, apply_rule  # noqa: E402  (BURROW's rule, verbatim)

FOLDSEEK = ROOT / "tools/foldseek/bin/foldseek"
MMSEQS = ROOT / "tools/mmseqs/bin/mmseqs"
PROC = ROOT / "data/processed/pdbt"
HOM = ROOT / "data/processed/homology"
SPLITS = ROOT / "data/splits"
REP_DB = Path("/tmp/gm_splits/homology/fsrep/rep")    # build_homology_graph.py representative DB (headers = sid)
TM_MIN, FS_CAND, FS_SURE, MIN_FS_LEN = 0.5, 0.45, 0.60, 20
FS_COLS = ["query", "target", "fident", "alnlen", "qlen", "tlen", "evalue", "bits", "prob", "alntmscore",
           "qtmscore", "ttmscore"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def run(cmd, **kw):
    cmd = [str(c) for c in cmd]
    log("$", " ".join(cmd[:7]), "...")
    subprocess.run(cmd, check=True, **kw)


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


def read_db_seqs(prefix: Path) -> dict[int, str]:
    data = open(prefix, "rb").read()
    out = {}
    for line in open(str(prefix) + ".index"):
        k, off, ln = line.split()
        out[int(k)] = data[int(off):int(off) + int(ln)].rstrip(b"\x00\n").decode()
    return out


def write_headers(prefix: Path, key2name: dict[int, str], dbtype_src: Path) -> None:
    off = 0
    for suf in ("_h", "_h.index", "_h.dbtype"):
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


def subdb(src: Path, keys, dst: Path, headers: dict | None = None):
    ids = dst.parent / (dst.name + ".ids")
    ids.write_text("\n".join(str(int(k)) for k in sorted(keys)) + "\n")
    for suf in ("", "_ss", "_ca"):
        run([FOLDSEEK, "createsubdb", ids, str(src) + suf, str(dst) + suf, "-v", "1"])
    if headers is not None:
        write_headers(dst, headers, Path(str(src) + "_h.dbtype"))
    else:
        run([FOLDSEEK, "createsubdb", ids, str(src) + "_h", str(dst) + "_h", "-v", "1"])


def foldseek_search(q: Path, t: Path, out: Path, threads: int) -> pd.DataFrame:
    """Exhaustive search q -> t; approximate TM for all hits, exact TM for the uncertain band; returns edges."""
    w = out.parent / (out.name + "_w")
    shutil.rmtree(w, ignore_errors=True)
    w.mkdir(parents=True)
    run([FOLDSEEK, "search", q, t, w / "aln", w / "tmp", "--threads", threads, "--exhaustive-search", "1",
         "-e", "10", "-a", "-v", "1"])
    run([FOLDSEEK, "convertalis", q, t, w / "aln", w / "aln.m8", "--format-output", ",".join(FS_COLS),
         "--threads", threads, "-v", "1"])
    fs = pd.read_csv(w / "aln.m8", sep="\t", header=None, names=FS_COLS)
    n_all = len(fs)
    fs = fs[np.minimum(fs.qtmscore, fs.ttmscore) >= FS_CAND].copy()
    amin = np.minimum(fs.qtmscore, fs.ttmscore)
    band = fs[amin < FS_SURE]
    fs["qtm_exact"] = np.nan
    fs["ttm_exact"] = np.nan
    if len(band):
        qk = {n: int(k) for k, n in (l.rstrip("\n").split("\t")[:2] for l in open(str(q) + "_h.keymap"))}
        tk = {n: int(k) for k, n in (l.rstrip("\n").split("\t")[:2] for l in open(str(t) + "_h.keymap"))}
        with open(w / "cand.tsv", "w") as fh:
            for a, b in sorted({(qk[x], tk[y]) for x, y in zip(band["query"], band["target"])}):
                fh.write(f"{a}\t{b}\t0\t0\n")
        run([FOLDSEEK, "tsv2db", w / "cand.tsv", w / "cand_pref", "--output-dbtype", "7", "-v", "1"])
        run([FOLDSEEK, "structurealign", q, t, w / "cand_pref", w / "cand_aln", "-a", "-e", "10",
             "--threads", threads, "-v", "1"])
        run([FOLDSEEK, "convertalis", q, t, w / "cand_aln", w / "cand_exact.m8", "--format-output",
             "query,target,qtmscore,ttmscore", "--exact-tmscore", "1", "--threads", threads, "-v", "1"])
        ex = pd.read_csv(w / "cand_exact.m8", sep="\t", header=None,
                         names=["query", "target", "qtm_exact", "ttm_exact"]).drop_duplicates(["query", "target"])
        fs = fs.drop(columns=["qtm_exact", "ttm_exact"]).merge(ex, on=["query", "target"], how="left")
    has = fs.qtm_exact.notna()
    approx_min = np.minimum(fs.qtmscore, fs.ttmscore)
    fs["tm_min"] = np.where(has, np.minimum(fs.qtm_exact, fs.ttm_exact), approx_min)
    fs["fs_edge"] = (fs.tm_min >= TM_MIN) & (has | (approx_min >= FS_SURE))
    fs.attrs["n_hits"] = n_all
    fs.attrs["n_band"] = int(len(band))
    shutil.rmtree(w / "tmp", ignore_errors=True)
    return fs


def keymap(prefix: Path):
    """<prefix>_h.keymap: key -> header name (for tsv2db candidate lists)."""
    data = open(str(prefix) + "_h", "rb").read()
    with open(str(prefix) + "_h.keymap", "w") as fo:
        for line in open(str(prefix) + "_h.index"):
            k, off, ln = line.split()
            name = data[int(off):int(off) + int(ln)].rstrip(b"\x00\n").decode().split()[0]
            fo.write(f"{k}\t{name}\n")


def mmseqs_search(qfa: Path, tfa: Path, w: Path, threads: int) -> pd.DataFrame:
    shutil.rmtree(w, ignore_errors=True)
    w.mkdir(parents=True)
    env = {**os.environ, "OMP_NUM_THREADS": str(threads)}
    run([MMSEQS, "createdb", qfa, w / "q", "--dbtype", "1", "-v", "1"], env=env)
    if tfa == qfa:
        t = w / "q"
    else:
        run([MMSEQS, "createdb", tfa, w / "t", "--dbtype", "1", "-v", "1"], env=env)
        t = w / "t"
    run([MMSEQS, "search", w / "q", t, w / "res", w / "tmp", "-s", "7.5", "--max-seqs", "5000", "-e", "1e-3", "-a",
         "--threads", threads, "-v", "1"], env=env)
    run([MMSEQS, "convertalis", w / "q", t, w / "res", w / "res.m8", "--format-output", ",".join(M8_COLUMNS),
         "--threads", threads, "-v", "1"], env=env)
    s8 = pd.read_csv(w / "res.m8", sep="\t", header=None, names=M8_COLUMNS)
    s8 = s8[s8["query"] != s8["target"]]
    return s8[apply_rule(s8)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=24)
    ap.add_argument("--work", default="/tmp/gm_pdbt")
    a = ap.parse_args()
    t0 = time.time()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    counts = {}
    S = pd.read_parquet(PROC / "sites_raw.parquet", columns=["pdb_id", "chain", "structure_path"])
    CH = pd.read_parquet(PROC / "chains.parquet")
    chains = S.drop_duplicates(["pdb_id", "chain"]).merge(CH, on=["pdb_id", "chain"], how="left")
    files = sorted(set(chains.structure_path))
    log("PDB-T site chains", len(chains), "entries", len(files))

    # ---------------- PDB-T Foldseek DB (staged symlinks f<idx>.cif.gz, auth chain names)
    db = work / "fsdb" / "all"
    if not Path(str(db) + ".lookup").exists():
        links = work / "fsdb" / "links"
        shutil.rmtree(work / "fsdb", ignore_errors=True)
        links.mkdir(parents=True)
        staged = []
        for i, f in enumerate(files):
            ln = links / f"f{i:06d}.cif.gz"
            ln.symlink_to(f)
            staged.append(str(ln))
        (work / "fsdb" / "files.tsv").write_text("\n".join(staged) + "\n")
        run([FOLDSEEK, "createdb", work / "fsdb" / "files.tsv", db, "--chain-name-mode", "1", "--threads",
             a.threads, "-v", "1"])
    look = pd.read_csv(str(db) + ".lookup", sep="\t", header=None, names=["key", "name", "fileidx"])
    look["file"] = [files[int(n[1:7])] for n in look.name]
    look["chain"] = [n[8:].split("_", 2)[-1] if n[8:].startswith("MODEL_") else n[8:] for n in look.name]
    look["model"] = [int(n[8:].split("_")[1]) if n[8:].startswith("MODEL_") else 1 for n in look.name]
    look = look[look.model == look.groupby("file").model.transform("min")].drop_duplicates(["file", "chain"])
    seqs = read_db_seqs(db)
    look["seq"] = look.key.map(seqs)
    chains = chains.merge(look[["file", "chain", "key", "seq"]].rename(columns={"file": "structure_path"}),
                          on=["structure_path", "chain"], how="left")
    counts["chains_without_foldseek_entry"] = int(chains.key.isna().sum())
    chains["seq"] = chains.seq.fillna(chains.seq_gemmi)          # fallback: gemmi observed sequence
    chains["seq_source"] = np.where(chains.key.notna(), "foldseek", "gemmi")
    useq = sorted(set(chains.seq))
    pid = {s: f"p{i:06d}" for i, s in enumerate(useq)}
    chains["sid"] = chains.seq.map(pid)
    with open(PROC / "pdbt_sequences.fasta", "w") as fh:
        for s in useq:
            fh.write(f">{pid[s]}\n{s}\n")
    counts["n_chains"] = int(len(chains))
    counts["n_unique_sequences"] = len(useq)

    # ---------------- training / test node sets
    nodes = pd.read_parquet(SPLITS / "homology_nodes.parquet")
    b2 = pd.read_parquet(SPLITS / "blips_sites_v2.parquet")
    tm = pd.read_parquet(SPLITS / "tough_m1_pockets_split.parquet")
    cs = pd.read_parquet(SPLITS / "ppips_complex_splits.parquet")
    ppc = set(cs[cs.split.isin(["train", "val"])].complex)
    dim = nodes[nodes.dataset == "dimers"]
    dim_cx = dim.node_id.str.slice(len("dimers:")).str.rsplit("_", n=1).str[0]
    train_sets = {
        "blips_v2_trainval": set(nodes[nodes.node_id.isin(set(b2[b2.partition.isin(["train", "val"])].node_id))].sid),
        "burrow_rep": set(nodes[nodes.dataset.isin(["burrow_train", "burrow_dev"])].sid),
        "burrow_partner": set(nodes[nodes.dataset == "burrow_partner"].sid),
        "ppips_trainval": set(dim[dim_cx.isin(ppc)].sid),
        "tough_m1_dev": set(nodes[nodes.node_id.isin(set(tm[tm.partition == "dev"].node_id))].sid)}
    counts["ppips_trainval_complexes"] = len(ppc)
    counts["ppips_trainval_complexes_matched"] = int(dim_cx[dim_cx.isin(ppc)].nunique())
    test_sets = {
        "tough_m1_test": set(nodes[nodes.node_id.isin(set(tm[tm.partition == "test"].node_id))].sid),
        "prospeccts": set(nodes[nodes.dataset == "prospeccts"].sid),
        "vertex": set(nodes[nodes.dataset == "vertex"].sid),
        "blips_test_af_set": set(nodes[nodes.dataset == "af_set"].sid)}
    counts["train_sids"] = {k: len(v) for k, v in train_sets.items()}
    train_all = set().union(*train_sets.values())
    counts["train_sids_union"] = len(train_all)
    gseq = read_fasta(HOM / "sequences.fasta")
    seq2gsid = {s: k for k, s in gseq.items()}
    # identical sequences
    chains["gsid_identical"] = chains.seq.map(seq2gsid)
    with open(work / "train.fasta", "w") as fh:
        for s in sorted(train_all):
            fh.write(f">{s}\n{gseq[s]}\n")

    # ---------------- MMseqs2 (both directions)
    s1 = mmseqs_search(PROC / "pdbt_sequences.fasta", work / "train.fasta", work / "mm_q2t", a.threads)
    s2 = mmseqs_search(work / "train.fasta", PROC / "pdbt_sequences.fasta", work / "mm_t2q", a.threads)
    s2 = s2.rename(columns={"query": "target", "target": "query"})
    seq_hits = pd.concat([s1[["query", "target"]], s2[["query", "target"]]]).drop_duplicates()
    log("mmseqs PDB-T x train rule hits", len(seq_hits))

    # ---------------- Foldseek: PDB-T rep DB (one structure per pid, len >= MIN_FS_LEN) vs training reps
    rep = chains[chains.key.notna() & (chains.seq.str.len() >= MIN_FS_LEN)].sort_values(["sid", "pdb_id", "chain"]) \
        .drop_duplicates("sid")
    qdb = work / "q" / "pdbt"
    qdb.parent.mkdir(exist_ok=True)
    subdb(db, rep.key.astype(int), qdb, dict(zip(rep.key.astype(int), rep.sid)))
    keymap(qdb)
    rep_names = {}
    data = open(str(REP_DB) + "_h", "rb").read()
    for line in open(str(REP_DB) + "_h.index"):
        k, off, ln = line.split()
        rep_names[int(k)] = data[int(off):int(off) + int(ln)].rstrip(b"\x00\n").decode()
    tkeys = [k for k, n in rep_names.items() if n in train_all]
    counts["train_sids_with_structure"] = len(tkeys)
    tdb = work / "t" / "train"
    tdb.parent.mkdir(exist_ok=True)
    subdb(REP_DB, tkeys, tdb, {k: rep_names[k] for k in tkeys})
    keymap(tdb)
    f1 = foldseek_search(qdb, tdb, work / "fs_q2t", a.threads)
    f2 = foldseek_search(tdb, qdb, work / "fs_t2q", a.threads)
    counts["foldseek_q2t"] = dict(n_hits=f1.attrs["n_hits"], n_band=f1.attrs["n_band"], n_edges=int(f1.fs_edge.sum()))
    counts["foldseek_t2q"] = dict(n_hits=f2.attrs["n_hits"], n_band=f2.attrs["n_band"], n_edges=int(f2.fs_edge.sum()))
    f2 = f2.rename(columns={"query": "target", "target": "query"})
    fs_hits = pd.concat([f1[f1.fs_edge][["query", "target", "tm_min"]], f2[f2.fs_edge][["query", "target", "tm_min"]]])
    log("foldseek PDB-T x train edges", len(fs_hits))
    hits = pd.concat([seq_hits.assign(kind="seq"), fs_hits[["query", "target"]].assign(kind="fs")])
    hits.to_parquet(PROC / "train_hits.parquet", index=False)

    # ---------------- per PDB-T sid: touches which training source
    per = {}
    for q, t, k in zip(hits["query"], hits["target"], hits["kind"]):
        per.setdefault(q, set()).add((t, k))
    for name, ss in train_sets.items():
        chains[f"touch_{name}"] = [bool(g in ss) or any(t in ss for t, _ in per.get(p, ()))
                                   for p, g in zip(chains.sid, chains.gsid_identical)]
    tr_any = lambda p, g, kind: bool(g in train_all) or any(t in train_all for t, k in per.get(p, ()) if k == kind)  # noqa: E731
    chains["remove_train_seq"] = [tr_any(p, g, "seq") for p, g in zip(chains.sid, chains.gsid_identical)]
    chains["remove_train_fs"] = [tr_any(p, None, "fs") for p in chains.sid]
    chains["remove_train"] = chains.remove_train_seq | chains.remove_train_fs
    # remove at the sequence level (all chains of a removed sid)
    rem_sid = set(chains[chains.remove_train].sid)
    chains["remove_train"] = chains.sid.isin(rem_sid)
    # freshness: exact sequence in a test set
    for name, ss in test_sets.items():
        chains[f"test_exact_{name}"] = chains.gsid_identical.isin(ss)
    af_acc = set(nodes[nodes.dataset == "af_set"].uniprot.dropna())
    chains["test_uniprot_af_set"] = [bool(set(str(u).split(";")) & af_acc) if u else False
                                     for u in chains.uniprot.fillna("")]
    tcols = [f"test_exact_{n}" for n in test_sets] + ["test_uniprot_af_set"]
    # removal = exact sequence only (as instructed); the af_set UniProt match is reported, not applied
    chains["remove_test_exact"] = chains[[f"test_exact_{n}" for n in test_sets]].any(axis=1)
    chains["protein"] = [u if u else f"seq:{p}" for u, p in zip(chains.uniprot.fillna(""), chains.sid)]

    # ---------------- PDB-T all-vs-all (groups)
    w = work / "self"
    w.mkdir(exist_ok=True)
    ss_ = mmseqs_search(PROC / "pdbt_sequences.fasta", PROC / "pdbt_sequences.fasta", work / "mm_self", a.threads)
    fself = foldseek_search(qdb, qdb, work / "fs_self", a.threads)
    fself = fself[fself.fs_edge & (fself["query"] != fself["target"])]
    E = pd.concat([ss_[["query", "target"]].assign(seq_edge=True),
                   fself[["query", "target"]].assign(fs_edge=True)])
    E["sid_a"] = np.minimum(E["query"], E["target"])
    E["sid_b"] = np.maximum(E["query"], E["target"])
    E = E.groupby(["sid_a", "sid_b"], as_index=False).agg(seq_edge=("seq_edge", "any"), fs_edge=("fs_edge", "any"))
    E["seq_edge"] = E.seq_edge.fillna(False).astype(bool)
    E["fs_edge"] = E.fs_edge.fillna(False).astype(bool)
    E.to_parquet(PROC / "pdbt_edges.parquet", index=False)
    keep = chains[~chains.remove_train & ~chains.remove_test_exact]
    ks = sorted(set(keep.sid))
    ix = {s: i for i, s in enumerate(ks)}
    m = E.sid_a.isin(ix) & E.sid_b.isin(ix)
    g = coo_matrix((np.ones(m.sum()), (E.sid_a[m].map(ix), E.sid_b[m].map(ix))), shape=(len(ks), len(ks)))
    _, lab = connected_components(g, directed=False)
    vc = pd.Series(lab).value_counts()
    order = sorted(vc.index, key=lambda c: (-vc[c], min(np.flatnonzero(lab == c))))
    ren = {c: f"pdbt:g{i:05d}" for i, c in enumerate(order)}
    gid = {s: ren[lab[ix[s]]] for s in ks}
    chains["group_id"] = chains.sid.map(gid)
    out_cols = ["pdb_id", "chain", "entity_id", "uniprot", "protein", "sid", "seq_source", "n_obs", "gsid_identical",
                "remove_train", "remove_train_seq", "remove_train_fs", *[f"touch_{n}" for n in train_sets],
                "remove_test_exact", *tcols, "group_id"]
    chains["seq_len"] = chains.seq.str.len()
    chains[out_cols + ["seq_len"]].to_parquet(PROC / "chain_homology.parquet", index=False)
    u = chains.drop_duplicates("sid")
    counts.update(
        chain_level=dict(n=int(len(chains)), remove_train=int(chains.remove_train.sum()),
                         remove_train_seq=int(chains.remove_train_seq.sum()), remove_train_fs_only=int(
                             (chains.remove_train_fs & ~chains.remove_train_seq).sum()),
                         **{f"touch_{n}": int(chains[f"touch_{n}"].sum()) for n in train_sets},
                         remove_test_exact_not_train=int((chains.remove_test_exact & ~chains.remove_train).sum()),
                         **{c: int((chains[c] & ~chains.remove_train).sum()) for c in tcols},
                         kept=int(len(keep))),
        sequence_level=dict(n=int(len(u)), remove_train=int(u.remove_train.sum()),
                            kept=int(len(ks))),
        pdbt_edges=dict(n=int(len(E)), seq=int(E.seq_edge.sum()), fs=int(E.fs_edge.sum())),
        groups=dict(n_groups=int(len(vc)), largest_sids=int(vc.iloc[0]) if len(vc) else 0,
                    singletons=int((vc == 1).sum())),
        wall_s=round(time.time() - t0))
    (PROC / "homology_counts.json").write_text(json.dumps(counts, indent=1, default=str))
    log(json.dumps(counts, default=str))


if __name__ == "__main__":
    main()
