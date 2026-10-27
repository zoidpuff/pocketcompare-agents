#!/usr/bin/env python
"""Index the AFDB human proteome tarball without extracting it (members are later read by byte offset).

    python scripts/proteome/index_tar.py [--tar PATH]

Writes data/processed/proteome_human/members.parquet (one row per *.pdb.gz model: name, uniprot, fragment,
offset_data, size) and members.json (tar size, mtime, sha256, member counts).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tarfile
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TAR = "/cluster/work/beltrao/shared/alphafold/v6/UP000005640_9606_HUMAN_v6.tar"
OUT = ROOT / "data/processed/proteome_human"
NAME = re.compile(r"AF-(?P<uniprot>[A-Z0-9]+(?:-\d+)?)-F(?P<frag>\d+)-model_v(?P<ver>\d+)\.pdb\.gz$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tar", default=TAR)
    a = ap.parse_args()
    t0 = time.time()
    st = os.stat(a.tar)
    h = hashlib.sha256()
    with open(a.tar, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 24), b""):
            h.update(b)
    rows, counts = [], {}
    with tarfile.open(a.tar) as tf:
        for m in tf:
            ext = m.name.split(".", 1)[1] if "." in m.name else ""
            counts[ext] = counts.get(ext, 0) + 1
            mm = NAME.search(m.name)
            if mm is None:
                continue
            rows.append(dict(name=m.name, stem=Path(m.name).name.replace(".pdb.gz", ""), uniprot=mm["uniprot"],
                             fragment=int(mm["frag"]), offset_data=m.offset_data, size=m.size))
    df = pd.DataFrame(rows)
    nfrag = df.groupby("uniprot").fragment.transform("max")
    df["n_fragments"] = nfrag
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT / "members.parquet", index=False)
    info = dict(tar=a.tar, size_bytes=st.st_size, mtime=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
                sha256=h.hexdigest(), member_counts=counts, n_members=sum(counts.values()),
                n_pdb_models=len(df), n_uniprot=int(df.uniprot.nunique()),
                n_fragmented_proteins=int((df.groupby("uniprot").fragment.max() > 1).sum()),
                n_fragment_models=int((df.n_fragments > 1).sum()), wall_s=round(time.time() - t0, 1))
    (OUT / "members.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
