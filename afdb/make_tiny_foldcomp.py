#!/usr/bin/env python
"""Testing helper: a tiny but real Foldcomp database from the first N entries of a published one (one ranged
download; offsets stay valid because the data file starts at 0), plus uniprot_taxid.parquet for its accessions
from the UniProt REST API.

    python afdb/make_tiny_foldcomp.py DIR [--db afdb_swissprot_v4] [--n 300] [--drop-one]

``--drop-one`` leaves one accession out of the taxid map (written to smoke_dropped_accession.txt), so tests can
check the "unclassified" path.
"""
import argparse
import urllib.request
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

BASE = "https://steineggerlab.s3.amazonaws.com/foldcomp"


def get(name, rng=None):
    req = urllib.request.Request(f"{BASE}/{name}", headers={"Range": f"bytes={rng}"} if rng else {})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--db", default="afdb_swissprot_v4")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--drop-one", action="store_true")
    a = ap.parse_args()
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    idx = [x for x in get(f"{a.db}.index", "0-400000").split(b"\n") if x.count(b"\t") == 2][:a.n]
    keys = {x.split(b"\t")[0] for x in idx}
    lk = [x for x in get(f"{a.db}.lookup", "0-2000000").split(b"\n") if x.count(b"\t") == 2 and x.split(b"\t")[0] in keys]
    assert len(lk) == len(idx), (len(lk), len(idx))
    end = max(int(x.split(b"\t")[1]) + int(x.split(b"\t")[2]) for x in idx)
    (d / a.db).write_bytes(get(a.db, f"0-{end - 1}"))
    (d / f"{a.db}.index").write_bytes(b"\n".join(idx) + b"\n")
    (d / f"{a.db}.lookup").write_bytes(b"\n".join(lk) + b"\n")
    (d / f"{a.db}.dbtype").write_bytes(get(f"{a.db}.dbtype"))
    accs = [x.split(b"\t")[1].decode().split("-")[1] for x in lk]
    m = {}
    for i in range(0, len(accs), 400):
        q = ("https://rest.uniprot.org/uniprotkb/accessions?fields=accession,organism_id&format=tsv&size=500&"
             "accessions=" + ",".join(accs[i:i + 400]))
        for r in urllib.request.urlopen(q, timeout=300).read().decode().splitlines()[1:]:
            if r:
                acc, tax = r.split("\t")
                m[acc] = int(tax)
    if a.drop_one:
        drop = accs[7]
        m.pop(drop, None)
        (d / "smoke_dropped_accession.txt").write_text(drop)
    pq.write_table(pa.table({"accession": list(m), "taxid": pa.array(list(m.values()), pa.int32())}),
                   d / "uniprot_taxid.parquet")
    print(f"tiny {a.db}: {len(idx)} entries, {end:,} B; taxids for {len(m)} of {len(accs)} accessions")


if __name__ == "__main__":
    main()
