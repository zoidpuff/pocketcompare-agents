#!/usr/bin/env python
"""Download the inputs of the Foldcomp tier-3 source to $FOLDCOMP_DIR (run as a job: afdb/fetch_foldcomp.sbatch).

    python afdb/fetch_foldcomp.py                          # afdb_uniprot_v4 (1.1 TB) + idmapping + NCBI taxdump
    python afdb/fetch_foldcomp.py --dbs afdb_rep_v4        # also the Foldseek cluster representatives (10 GB)
    python afdb/fetch_foldcomp.py --no-data                # only .index/.lookup/.dbtype + maps (testing)

* Foldcomp databases (MMseqs2-style: ``<db>`` data, ``<db>.index`` = key<TAB>offset<TAB>length, ``<db>.lookup`` =
  key<TAB>name<TAB>file, ``<db>.dbtype``) from https://foldcomp.steineggerlab.workers.dev/ (fetched from its S3 target). Files are
  fetched in --chunk-sized byte ranges by --streams parallel connections into ``<file>.part``; finished chunks
  are logged in ``<file>.part.done``, so an interrupted download resumes. The size is checked against the server
  and, for the data file, against the end of the last entry in the index, then ``.part`` is renamed.
  Measured from Euler: ~11 MB/s per connection, ~170 MB/s with 16 connections (1.1 TB in ~2 h).
* UniProt ``idmapping_selected.tab.gz`` (7.1 GB): downloaded the same way, then columns 1 (UniProtKB-AC) and 13
  (NCBI-taxon) are extracted with ``gzip -dc | cut -f1,13`` into ``uniprot_taxid.parquet`` (accession, taxid);
  the .gz is deleted unless --keep-idmapping.
* UniProt 2021_04 (the release AFDB v4 was built from; 151 GB knowledgebase tarball, deleted after use): accession ->
  taxid from the AC/OX lines into ``uniprot2021_04_taxid.parquet``; ~47 % of the v4 accessions are no longer in the
  current UniProt. Skip with --no-uniprot-2021-04.
* NCBI new_taxdump: rankedlineage.dmp + merged.dmp into $NCBI_DIR (as make_worklist.py would fetch it).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from afdb_common import env, out_root  # noqa: E402

# foldcomp.steineggerlab.workers.dev 302-redirects here; the workers.dev front end answers 403 to Python clients
FC_BASE = env("FOLDCOMP_BASE_URL", "https://steineggerlab.s3.amazonaws.com/foldcomp")
IDMAP_URL = ("https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/idmapping/"
             "idmapping_selected.tab.gz")
# AFDB v4 was built from UniProt 2021_04; ~47 % of its accessions are no longer in the current UniProt
# (redundant-proteome removal), so the 2021_04 flat file (AC + OX lines) supplies their taxids
UNIPROT_2021_04_URL = ("https://ftp.uniprot.org/pub/databases/uniprot/previous_releases/release-2021_04/knowledgebase/"
                       "knowledgebase2021_04.tar.gz")
TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz"


def log(*a):
    print(f"[fetch_foldcomp {time.strftime('%Y-%m-%d %H:%M:%S')}]", *a, file=sys.stderr, flush=True)


def resolve(url: str) -> tuple[str, int]:
    """(final URL after redirects, size) via a 1-byte ranged GET (HEAD is not always allowed)."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        final = r.geturl()
        cr = r.headers.get("Content-Range")
        if r.status != 206 or not cr:
            raise RuntimeError(f"{url}: server does not honour range requests (status {r.status})")
        return final, int(cr.split("/")[-1])


def ranged_download(url: str, dest: Path, streams: int, chunk: int, retries: int = 10) -> Path:
    """Reuse ``dest`` if it exists with the server's size (e.g. fetched earlier by curl); refuse to touch a file of
    another size (a download may still be writing it); else download into ``dest.part`` (resumable)."""
    final, size = resolve(url)
    if dest.exists():
        have = dest.stat().st_size
        if have == size:
            log(f"{dest.name}: present with the expected size ({size:,} B), reused")
            return dest
        raise SystemExit(f"{dest}: {have:,} B but the server has {size:,} B. If another download is still writing "
                         "it, wait for it to finish; otherwise delete the file and re-run (downloads resume from "
                         f"{dest.name}.part).")
    part, donef = Path(str(dest) + ".part"), Path(str(dest) + ".part.done")
    if not part.exists() or part.stat().st_size != size:
        with open(part, "ab") as fh:
            fh.truncate(size)
    done = {int(x) for x in donef.read_text().split()} if donef.exists() else set()
    n = (size + chunk - 1) // chunk
    todo = [k for k in range(n) if k not in done]
    log(f"{dest.name}: {size:,} B in {n} chunks of {chunk >> 20} MB, {len(todo)} to fetch, {streams} streams")
    lock = threading.Lock()
    fd = os.open(part, os.O_WRONLY)
    t0, got = time.time(), [0]

    def one(k: int):
        a, b = k * chunk, min(size, (k + 1) * chunk) - 1
        for i in range(retries):
            try:
                req = urllib.request.Request(final, headers={"Range": f"bytes={a}-{b}"})
                with urllib.request.urlopen(req, timeout=300) as r:
                    if r.status != 206:
                        raise RuntimeError(f"status {r.status}")
                    pos = a
                    while True:
                        buf = r.read(4 << 20)
                        if not buf:
                            break
                        os.pwrite(fd, buf, pos)
                        pos += len(buf)
                if pos != b + 1:
                    raise RuntimeError(f"short chunk {k}: {pos - a} of {b + 1 - a} B")
                with lock:
                    with open(donef, "a") as fh:
                        fh.write(f"{k}\n")
                    got[0] += b + 1 - a
                return
            except Exception as e:  # noqa: BLE001
                log(f"{dest.name} chunk {k}: {e} (attempt {i + 1}/{retries})")
                time.sleep(min(120, 5 * 2 ** i))
        raise RuntimeError(f"{dest.name}: chunk {k} failed")

    last = time.time()
    with ThreadPoolExecutor(streams) as ex:
        futs = [ex.submit(one, k) for k in todo]
        for f in as_completed(futs):
            f.result()
            if time.time() - last > 60:
                last = time.time()
                el = time.time() - t0
                log(f"{dest.name}: {got[0] / 1e9:.1f} GB this run, {got[0] / el / 1e6:.0f} MB/s")
    os.fsync(fd)
    os.close(fd)
    if part.stat().st_size != size:
        raise RuntimeError(f"{dest.name}: size {part.stat().st_size} != {size}")
    part.replace(dest)
    donef.unlink(missing_ok=True)
    el = time.time() - t0
    log(f"{dest.name}: done, {size:,} B ({got[0] / max(el, 1) / 1e6:.0f} MB/s over {el:.0f} s)")
    return dest


def check_db(d: Path, db: str):
    """The data file must end where the index's last entry ends (entries are stored contiguously in key order)."""
    idx, data = d / f"{db}.index", d / db
    if not (idx.exists() and data.exists()):
        return
    with open(idx, "rb") as fh:
        fh.seek(max(0, idx.stat().st_size - 4096))
        _, off, ln = fh.read().strip().split(b"\n")[-1].split(b"\t")
    end = int(off) + int(ln)
    size = data.stat().st_size
    if end != size:
        raise SystemExit(f"{db}: index ends at {end:,} but the data file has {size:,} B")
    log(f"{db}: index consistent with the data file ({size:,} B)")


def idmapping(d: Path, streams: int, chunk: int, keep: bool):
    out = d / "uniprot_taxid.parquet"
    if out.exists():
        log(f"{out.name}: present")
        return
    gz = d / "idmapping_selected.tab.gz"
    ours = not gz.exists()
    if not ours:                  # fetched separately (e.g. by curl): use it as it is (UniProt updates it monthly)
        log(f"{gz.name}: using the local file ({gz.stat().st_size:,} B)")
    else:
        gz = ranged_download(IDMAP_URL, gz, streams, chunk)
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.csv as pacsv
    import pyarrow.parquet as pq
    t0 = time.time()
    p = subprocess.Popen(f"gzip -dc '{gz}' | cut -f1,13", shell=True, stdout=subprocess.PIPE)
    rd = pacsv.open_csv(p.stdout, read_options=pacsv.ReadOptions(column_names=["accession", "taxid"],
                                                                 block_size=64 << 20),
                        parse_options=pacsv.ParseOptions(delimiter="\t", quote_char=False),
                        convert_options=pacsv.ConvertOptions(column_types={"accession": pa.string(),
                                                                           "taxid": pa.string()}))
    tmp = Path(str(out) + ".tmp")
    w, n = None, 0
    for b in rd:
        tax = b.column(1)
        tax = pc.cast(pc.if_else(pc.equal(tax, ""), None, tax), pa.int32())
        t = pa.table({"accession": b.column(0), "taxid": tax})
        if w is None:
            w = pq.ParquetWriter(str(tmp), t.schema, compression="zstd")
        w.write_table(t)
        n += len(t)
    w.close()
    if p.wait() != 0:
        raise RuntimeError(f"gzip -dc {gz} | cut failed (incomplete download?)")
    tmp.replace(out)
    log(f"{out.name}: {n:,} accessions in {time.time() - t0:.0f} s ({out.stat().st_size / 1e9:.1f} GB)")
    if ours and not keep:                # a file that was there before is left alone
        gz.unlink()


def uniprot_2021_04(d: Path, streams: int, chunk: int, keep: bool):
    """accession (primary and secondary) -> taxid of UniProt 2021_04 from the AC/OX lines of uniprot_sprot.dat.gz +
    uniprot_trembl.dat.gz inside knowledgebase2021_04.tar.gz (151 GB; downloaded in ranges, then streamed through
    tar | gzip -dc | grep; ~1-2 h). Output: uniprot2021_04_taxid.parquet."""
    out = d / "uniprot2021_04_taxid.parquet"
    if out.exists():
        log(f"{out.name}: present")
        return
    tgz = ranged_download(UNIPROT_2021_04_URL, d / "knowledgebase2021_04.tar.gz", streams, chunk)
    import pyarrow as pa
    import pyarrow.parquet as pq
    t0 = time.time()
    cmd = (f"tar -xOzf '{tgz}' uniprot_sprot.dat.gz uniprot_trembl.dat.gz | gzip -dc | "
           "LC_ALL=C grep -E '^(AC|OX)   '")
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, bufsize=1 << 24)
    tmp = Path(str(out) + ".tmp")
    w, accs, taxs, pend, n, n_entries = None, [], [], [], 0, 0
    schema = pa.schema([("accession", pa.string()), ("taxid", pa.int32())])

    def flush():
        nonlocal w, accs, taxs
        if w is None:
            w = pq.ParquetWriter(str(tmp), schema, compression="zstd")
        w.write_table(pa.table({"accession": accs, "taxid": pa.array(taxs, pa.int32())}, schema=schema))
        accs, taxs = [], []
    for line in p.stdout:
        if line.startswith(b"AC"):
            pend += [x.strip().decode() for x in line[5:].split(b";") if x.strip()]
        else:                                           # OX   NCBI_TaxID=9606 {ECO:...};
            v = line[5:].split(b"=", 1)[1]
            tid = int(v.split(b";")[0].split()[0])
            accs += pend
            taxs += [tid] * len(pend)
            n += len(pend)
            n_entries += 1
            pend = []
            if len(accs) >= 5_000_000:
                flush()
                if n_entries % 20_000_000 < 3_000_000:
                    log(f"2021_04: {n_entries:,} entries, {n:,} accessions ({time.time() - t0:.0f} s)")
    flush()
    w.close()
    if p.wait() != 0:
        raise RuntimeError("tar | gzip | grep failed")
    tmp.replace(out)
    log(f"{out.name}: {n_entries:,} entries, {n:,} accessions (primary + secondary) in {time.time() - t0:.0f} s")
    if not keep:
        tgz.unlink()


def taxdump(ncbi: Path):
    if (ncbi / "rankedlineage.dmp").exists():
        log(f"NCBI taxonomy present in {ncbi}")
        return
    ncbi.mkdir(parents=True, exist_ok=True)
    tgz = ncbi / "new_taxdump.tar.gz"
    urllib.request.urlretrieve(TAXDUMP_URL, tgz)
    with tarfile.open(tgz) as tf:
        for n in ("rankedlineage.dmp", "merged.dmp"):
            tf.extract(n, ncbi, filter="data")
    tgz.unlink()
    log(f"NCBI taxonomy -> {ncbi}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--dir", default=None, help="default $FOLDCOMP_DIR (= $OUT_ROOT/foldcomp)")
    ap.add_argument("--dbs", nargs="+", default=["afdb_uniprot_v4"],
                    help="afdb_uniprot_v4 (all ~214 M v4 models), afdb_rep_v4 (2.3 M reps), afdb_swissprot_v4")
    ap.add_argument("--no-data", action="store_true", help="only .index/.lookup/.dbtype (no data files)")
    ap.add_argument("--no-idmapping", action="store_true")
    ap.add_argument("--keep-idmapping", action="store_true", help="keep idmapping_selected.tab.gz")
    ap.add_argument("--no-taxdump", action="store_true")
    ap.add_argument("--no-uniprot-2021-04", action="store_true",
                    help="skip the UniProt 2021_04 taxids (then ~47 %% of tier 3 has no taxid but its tar's)")
    ap.add_argument("--keep-uniprot-2021-04", action="store_true", help="keep knowledgebase2021_04.tar.gz")
    ap.add_argument("--streams", type=int, default=env("FETCH_STREAMS", 16))
    ap.add_argument("--chunk-mb", type=int, default=256)
    a = ap.parse_args()
    root = out_root(a.out_root)
    d = Path(a.dir or env("FOLDCOMP_DIR", str(root / "foldcomp")))
    d.mkdir(parents=True, exist_ok=True)
    chunk = a.chunk_mb << 20
    for db in a.dbs:
        for suf in (".dbtype", ".index", ".lookup") + (() if a.no_data else ("",)):
            ranged_download(f"{FC_BASE}/{db}{suf}", d / f"{db}{suf}", a.streams, chunk)
        check_db(d, db)
    if not a.no_idmapping:
        idmapping(d, a.streams, chunk, a.keep_idmapping)
    if not a.no_uniprot_2021_04:
        uniprot_2021_04(d, a.streams, chunk, a.keep_uniprot_2021_04)
    if not a.no_taxdump:
        taxdump(Path(env("NCBI_DIR", str(root / "ncbi"))))
    log(f"done: {d}")


if __name__ == "__main__":
    main()
