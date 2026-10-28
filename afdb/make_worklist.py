#!/usr/bin/env python
"""Build the AFDB work list: OUT_ROOT/worklist.parquet (+ .tsv, worklist.json summary) and
OUT_ROOT/skip_accessions.txt.

    python afdb/make_worklist.py                         # tiers 1, 2, 3 (full GCS listing ~11 min, cached)
    python afdb/make_worklist.py --tiers 1,2             # local data only
    python afdb/make_worklist.py --gcs-max-pages 20      # tier 3 from the first 20 listing pages (testing)

Tiers (README.md "Tier design"):
  1  the 46 local AFDB v6 proteomes in species_order.tsv order (+ any extra local proteome at the end);
     each tar is split into units of ~UNIT_STRUCTURES models (member ranges of the .cif.gz members).
  2  local Swiss-Prot v6 minus the accessions of tier 1 (the worker skips them; ranges count kept models).
  3  (TIER3_SOURCE=foldcomp, default) every other entry of the Foldcomp afdb_uniprot_v4 database (all AFDB v4
     models; fetch_foldcomp.py), taxid from UniProt idmapping, ordered by the same tree round-robin over taxon
     chunks of <= UNIT_STRUCTURES entries and packed into units (entry lists in OUT_ROOT/fc_entries_<db>.parquet);
     TIER_REPS=1 puts the afdb_rep_v4 representatives first. Or (TIER3_SOURCE=gcs):
     every other (taxid, shard) tar of the GCS v4 bucket (highest model version per (taxid, shard)), ordered by a
     tree round-robin over superkingdom -> phylum -> class -> order -> family -> genus -> taxon, leaves = tars by
     size descending; consecutive tars are packed into units of ~UNIT_STRUCTURES estimated models (most tars
     hold 1-10 models; one unit per tar would mean ~1 M units and ~3 M state/output files).
Accessions of tiers 1-2 (from the local tar member names) are written to skip_accessions.txt with the first
tier they occur in; the worker skips a member whose accession occurs in an earlier tier than its unit's tier.

Local tar member indices (name, offset, size of each .cif.gz) are cached in OUT_ROOT/tar_index/ (~1 h total the
first time on the shared file system, done in parallel threads); the GCS listing in OUT_ROOT/gcs_listing.tsv.gz;
NCBI taxonomy in OUT_ROOT/ncbi/.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from itertools import zip_longest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from afdb_common import (GCS_RE, HERE, atomic_write_bytes, atomic_write_json, env, out_root,  # noqa: E402
                         parse_model_name,
                         tar_index_dir)

AFDB_V4_TOTAL = 214_684_311          # structures in AFDB v4 (the GCS bucket), used to calibrate bytes/model
TAXDUMP_URL = "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz"
LEVELS = ["superkingdom", "phylum", "class", "order", "family", "genus"]
# v4 bytes per model: 25.95 TB of (taxid, shard) tars in the full listing (2026-10-28) / 214.68 M models
GCS_FULL_BYTES = 25_946_892_683_264
GCS_BYTES_PER_MODEL = GCS_FULL_BYTES / AFDB_V4_TOTAL
RATE = 380.0                          # structures/s per node (docs/AFDB_COST.md)


def log(*a):
    print(f"[make_worklist {time.strftime('%H:%M:%S')}]", *a, file=sys.stderr, flush=True)


# ============================================================================================ local tars
def index_tar(path: Path, cache_dir: Path) -> pd.DataFrame:
    """(name, offset_data, size) of every .cif.gz member, cached by (size, mtime)."""
    st = path.stat()
    cache = cache_dir / (path.name + ".parquet")
    if cache.exists():
        df = pd.read_parquet(cache)
        md = json.loads(Path(str(cache) + ".json").read_text()) if Path(str(cache) + ".json").exists() else {}
        if md.get("size") == st.st_size and md.get("mtime") == int(st.st_mtime):
            return df
    t0 = time.time()
    rows = []
    with tarfile.open(path) as tf:
        for m in tf:
            if m.isfile() and m.name.endswith(".cif.gz"):
                rows.append((m.name, m.offset_data, m.size))
    df = pd.DataFrame(rows, columns=["name", "offset_data", "size"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, cache)
    atomic_write_json(Path(str(cache) + ".json"), {"size": st.st_size, "mtime": int(st.st_mtime), "n": len(df),
                                                   "index_s": round(time.time() - t0, 1)})
    log(f"indexed {path.name}: {len(df)} models in {time.time() - t0:.0f} s")
    return df


def accessions_of(names) -> list[str]:
    return [(parse_model_name(n) or (Path(n).name,))[0] for n in names]


def range_units(idx: pd.DataFrame, keep: np.ndarray, size: int, limit: int | None):
    """Member ranges [start, end) of ``idx`` holding ~``size`` kept members each."""
    pos = np.flatnonzero(keep)
    if limit:
        pos = pos[:limit]
    out = []
    for s in range(0, len(pos), size):
        chunk = pos[s:s + size]
        a, b = int(chunk[0]), int(chunk[-1]) + 1
        out.append((a, b, int(len(chunk)), int(idx.offset_data.iloc[a]) - 512,
                    int(idx.offset_data.iloc[b - 1] + idx["size"].iloc[b - 1])))
    return out


def local_units(a, root: Path, tiers):
    so = pd.read_csv(HERE / "species_order.tsv", sep="\t", dtype={"taxid": int})
    if a.tier1_codes:
        want = a.tier1_codes.split(",")
        so = so[so.code.isin(want)].set_index("code").loc[want].reset_index()
    files = [Path(a.afdb_local) / f for f in so.file]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        log("WARNING missing local proteome tars:", missing)
    sp = Path(a.afdb_local) / "swissprot_cif_v6.tar"
    todo = [f for f in files if f.exists()] + ([sp] if (2 in tiers or 3 in tiers) and sp.exists() and not a.no_swissprot else [])
    cache = tar_index_dir(root)
    with ThreadPoolExecutor(a.index_threads) as ex:
        idx = dict(zip(todo, ex.map(lambda p: index_tar(p, cache), todo)))
    units, skip = [], {}
    for r, f in zip(so.itertuples(), files):
        if f not in idx:
            continue
        df = idx[f]
        acc = accessions_of(df.name)
        for x in acc:
            skip.setdefault(x, 1)
        if 1 in tiers:
            for (s, e, n, b0, b1) in range_units(df, np.ones(len(df), bool), a.unit_structures, a.limit_per_source):
                units.append(dict(tier=1, source_type="local_tar", source=str(f), sources=[str(f)], member_start=s,
                                  member_end=e, byte_start=b0, byte_end=b1, taxid=int(r.taxid), code=r.code,
                                  organism=r.species, model_version=6, est_structures=n))
    if sp in idx:
        df = idx[sp]
        acc = np.array(accessions_of(df.name), dtype=object)
        keep = np.array([x not in skip for x in acc])
        for x in acc[keep]:
            skip.setdefault(x, 2)
        if 2 in tiers:
            for (s, e, n, b0, b1) in range_units(df, keep, a.unit_structures, a.limit_per_source):
                units.append(dict(tier=2, source_type="local_tar", source=str(sp), sources=[str(sp)], member_start=s,
                                  member_end=e, byte_start=b0, byte_end=b1, taxid=-1, code="SWISSPROT",
                                  organism="Swiss-Prot (mixed)", model_version=6, est_structures=n))
        log(f"Swiss-Prot: {len(df)} models, {int(keep.sum())} not in tier 1")
    return units, skip, idx


# ============================================================================================ GCS listing
def gcs_listing(root: Path, max_pages: int | None, refresh: bool, listing_file: str | None) -> pd.DataFrame:
    if listing_file:
        df = pd.read_csv(listing_file, sep="\t", names=["name", "size"])
        log(f"GCS listing from {listing_file}: {len(df)} objects")
        return df
    cache = root / ("gcs_listing.tsv.gz" if not max_pages else f"gcs_listing.first{max_pages}.tsv.gz")
    if cache.exists() and not refresh:
        df = pd.read_csv(cache, sep="\t", names=["name", "size"])
        log(f"GCS listing from cache {cache}: {len(df)} objects")
        return df
    bucket = env("GCS_BUCKET", "public-datasets-deepmind-alphafold-v4")
    api = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o"
    rows, tok, pages, t0 = [], None, 0, time.time()
    while True:
        q = {"prefix": "proteomes/", "maxResults": "1000", "fields": "nextPageToken,items(name,size)"}
        if tok:
            q["pageToken"] = tok
        for k in range(8):
            try:
                with urllib.request.urlopen(api + "?" + urllib.parse.urlencode(q), timeout=120) as r:
                    d = json.load(r)
                break
            except Exception as e:  # noqa: BLE001
                log(f"listing page {pages}: {e}; retry {k + 1}")
                time.sleep(min(60, 2 ** k))
        else:
            raise SystemExit("GCS listing failed")
        rows += [(it["name"], int(it["size"])) for it in d.get("items", [])]
        pages += 1
        if pages % 200 == 0:
            log(f"listing: {pages} pages, {len(rows)} objects, {time.time() - t0:.0f} s")
        tok = d.get("nextPageToken")
        if not tok or (max_pages and pages >= max_pages):
            break
    log(f"GCS listing: {len(rows)} objects in {pages} pages, {time.time() - t0:.0f} s"
        + ("" if tok is None else " (truncated by --gcs-max-pages)"))
    df = pd.DataFrame(rows, columns=["name", "size"])
    atomic_write_bytes(cache, gzip.compress(df.to_csv(sep="\t", header=False, index=False).encode()))
    atomic_write_json(root / "gcs_listing.json", {"objects": len(df), "pages": pages, "complete": tok is None,
                                                  "seconds": round(time.time() - t0), "bucket": bucket,
                                                  "time": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return df


# ============================================================================================ NCBI taxonomy
def load_lineage(root: Path, taxids) -> pd.DataFrame:
    """taxid -> name + LEVELS, from NCBI new_taxdump rankedlineage.dmp (merged taxids followed)."""
    d = Path(env("NCBI_DIR", str(root / "ncbi")))
    rl, mg = d / "rankedlineage.dmp", d / "merged.dmp"
    if not rl.exists():
        d.mkdir(parents=True, exist_ok=True)
        tgz = d / "new_taxdump.tar.gz"
        log("downloading NCBI taxonomy", TAXDUMP_URL)
        urllib.request.urlretrieve(TAXDUMP_URL, tgz)
        with tarfile.open(tgz) as tf:
            for n in ("rankedlineage.dmp", "merged.dmp"):
                tf.extract(n, d, filter="data")
        tgz.unlink()
    merged = {}
    for line in open(mg):
        p = line.split("\t|")
        merged[int(p[0])] = int(p[1])
    want = {int(t) for t in taxids}
    want |= {merged[t] for t in want if t in merged}
    rows = {}
    with open(rl) as fh:
        for line in fh:
            t = int(line[:line.index("\t")])
            if t in want:
                p = [x.strip() for x in line.split("\t|")]
                # tax_id | tax_name | species | genus | family | order | class | phylum | kingdom | domain/realm
                top = p[9]
                if top not in ("Bacteria", "Archaea", "Eukaryota"):
                    top = "Viruses" if top else "unclassified"
                rows[t] = dict(tax_name=p[1], genus=p[3], family=p[4], order=p[5], **{"class": p[6]}, phylum=p[7],
                               superkingdom=top)
    out = []
    for t in sorted({int(x) for x in taxids}):
        r = rows.get(t) or rows.get(merged.get(t, -1))
        out.append(dict(taxid=t, **(r or dict(tax_name=f"taxid {t}", genus="", family="", order="", **{"class": ""},
                                                 phylum="", superkingdom="unclassified"))))
    if not out:
        return pd.DataFrame(columns=["taxid", "tax_name"] + LEVELS[::-1]).set_index("taxid")
    return pd.DataFrame(out).set_index("taxid")


# ============================================================================================ tree round-robin
def round_robin(keys: list[tuple], sizes: list[int]) -> list[int]:
    """Leaf positions in tree round-robin order. ``keys[i]`` = (superkingdom, ..., genus, taxid) of leaf i (a tar),
    ``sizes[i]`` its size. At every level the child groups are ordered by total size (descending; ties by name)
    and interleaved one item at a time; leaves of a taxon are ordered by size descending."""
    depth_max = len(keys[0]) if keys else 0

    def rec(idx: list[int], depth: int) -> list[int]:
        if depth == depth_max:
            return sorted(idx, key=lambda i: (-sizes[i], i))
        groups = defaultdict(list)
        for i in idx:
            groups[keys[i][depth]].append(i)
        if len(groups) == 1:
            return rec(idx, depth + 1)
        tot = {g: sum(sizes[i] for i in v) for g, v in groups.items()}
        order = sorted(groups, key=lambda g: (-tot[g], str(g)))
        return interleave([rec(groups[g], depth + 1) for g in order])
    return rec(list(range(len(keys))), 0)


def interleave(lists: list[list[int]]) -> list[int]:
    if len(lists) == 1:
        return lists[0]
    return [x for tup in zip_longest(*lists) for x in tup if x is not None]


def gcs_units(a, root: Path, skip: dict):
    lst = gcs_listing(root, a.gcs_max_pages, a.gcs_refresh, a.gcs_listing)
    m = lst.name.str.extract(GCS_RE.pattern)
    ok = m.notna().all(axis=1)
    lst, m = lst[ok].copy(), m[ok].astype(int)
    lst[["taxid", "shard", "ver"]] = m.to_numpy()
    n_obj = len(lst)
    lst = lst.sort_values(["taxid", "shard", "ver"]).drop_duplicates(["taxid", "shard"], keep="last")
    bpm = a.gcs_bytes_per_model or GCS_BYTES_PER_MODEL
    lst["est"] = np.maximum(1, np.round(lst["size"] / bpm)).astype(int)
    log(f"GCS: {n_obj} tar objects -> {len(lst)} (taxid, shard) tars (highest version), {lst.taxid.nunique()} taxa,"
        f" {lst['size'].sum() / 1e12:.2f} TB, ~{lst.est.sum() / 1e6:.1f} M models at {bpm / 1e3:.1f} kB/model")
    lin = load_lineage(root, lst.taxid.unique())
    lst = lst.join(lin, on="taxid").reset_index(drop=True)
    t0 = time.time()
    keys = list(zip(*[lst[c].tolist() for c in LEVELS], lst.taxid.tolist()))
    lst = lst.iloc[round_robin(keys, lst["size"].tolist())].reset_index(drop=True)
    log(f"tree round-robin over {len(lst)} tars: {time.time() - t0:.0f} s")
    units, cur = [], []

    def close():
        if not cur:
            return
        f, n = cur[0], sum(r["est"] for r in cur)
        more = f" (+{len(cur) - 1})" if len(cur) > 1 else ""
        units.append(dict(tier=3, source_type="gcs_tar", source=f["name"] + more, sources=[r["name"] for r in cur],
                          source_sizes=[int(r["size"]) for r in cur], member_start=0, member_end=-1, byte_start=0,
                          byte_end=int(sum(r["size"] for r in cur)), taxid=int(f["taxid"]),
                          code=f"tax{f['taxid']}{more}",
                          organism=f["tax_name"] + (f" and {len(cur) - 1} more tars" if len(cur) > 1 else ""),
                          model_version=int(max(r["ver"] for r in cur)), est_structures=int(n),
                          source_taxids=[int(r["taxid"]) for r in cur],
                          lineage=";".join(str(f[c]) for c in LEVELS)))
        cur.clear()
    run = 0
    for r in lst.to_dict("records"):
        if cur and (run + r["est"] > a.unit_structures or len(cur) >= a.gcs_unit_max_tars):
            close()
            run = 0
        cur.append(r)
        run += r["est"]
    close()
    # tier 1-2 accessions are expected in the bucket too: subtract them, scaled to the share of the bucket listed
    n_skip = len(skip) * min(1.0, lst["size"].sum() / GCS_FULL_BYTES)
    return units, dict(gcs_objects=n_obj, gcs_tars=len(lst), gcs_taxa=int(lst.taxid.nunique()),
                       gcs_bytes=int(lst["size"].sum()), bytes_per_model=round(bpm, 1),
                       est_structures_before_skip=int(lst.est.sum()),
                       est_structures_after_skip=int(max(0, lst.est.sum() - n_skip)))


# ============================================================================================ Foldcomp tier 3
def fc_dir(root: Path) -> Path:
    return Path(env("FOLDCOMP_DIR", str(root / "foldcomp")))


def fc_units(a, root: Path, skip: dict, db: str, exclude_db: str | None = None):
    """Tier-3 units from a Foldcomp database (``db`` = afdb_uniprot_v4 or afdb_rep_v4) with DuckDB.

    Reads ``<db>.index`` (key, offset, length) and ``<db>.lookup`` (key, name), parses accession / fragment /
    version from the names, drops accessions of tiers 1-2 (``skip``) and, with ``exclude_db``, the accessions of
    that database (the representatives already run first), joins NCBI taxids from ``uniprot_taxid.parquet``
    (accessions missing from the current UniProt -> taxid 0, "unclassified"), orders taxon chunks of at most
    UNIT_STRUCTURES entries by the tree round-robin and packs them into units. The entries go to
    ``OUT_ROOT/fc_entries_<db>.parquet`` (fc_unit, offset, length, key, accession, fragment, version, taxid),
    sorted by (fc_unit, offset): one file, ~100 k-row row groups, so a worker reads 1-2 row groups per unit.
    Memory: DuckDB with FC_DUCKDB_MEM (default 48 GB; spills to $TMPDIR); ~214 M entries take ~15-30 min on
    16 threads (measured in README)."""
    import duckdb
    d = fc_dir(root)
    idx, lkp = d / f"{db}.index", d / f"{db}.lookup"
    tax = Path(env("UNIPROT_TAXID", str(d / "uniprot_taxid.parquet")))
    for f in (idx, lkp, tax):
        if not f.exists():
            raise SystemExit(f"missing {f}: run afdb/fetch_foldcomp.py (or fetch_foldcomp.sbatch) first")
    t0 = time.time()
    con = duckdb.connect()
    threads = int(os.environ.get("SLURM_CPUS_PER_TASK") or min(16, os.cpu_count() or 4))
    tmpd = Path(os.environ.get("TMPDIR", "/tmp")) / f"duckdb_{os.getpid()}"
    con.execute(f"SET threads={threads}; SET memory_limit='{env('FC_DUCKDB_MEM', '48GB')}'; "
                f"SET temp_directory='{tmpd}'; SET preserve_insertion_order=false")
    con.execute(f"""CREATE TABLE e AS
        SELECT i.key, i.off, i.len, l.f AS tarno, struct_extract(l.r, 'acc') AS accession,
               TRY_CAST(struct_extract(l.r, 'frag') AS SMALLINT) AS fragment,
               TRY_CAST(struct_extract(l.r, 'ver') AS TINYINT) AS version
        FROM read_csv('{idx}', delim='\t', header=false, columns={{'key': 'UBIGINT', 'off': 'UBIGINT',
                                                                   'len': 'UINTEGER'}}) i
        JOIN (SELECT key, f, regexp_extract(name, '^AF-(.+)-F([0-9]+)-model_v([0-9]+)', ['acc', 'frag', 'ver']) AS r
              FROM read_csv('{lkp}', delim='\t', header=false, columns={{'key': 'UBIGINT', 'name': 'VARCHAR',
                                                                         'f': 'INTEGER'}})) l USING (key)""")
    n_all = con.execute("SELECT count(*) FROM e").fetchall()[0][0]
    n_bad = con.execute("SELECT count(*) FROM e WHERE accession = '' OR fragment IS NULL").fetchall()[0][0]
    log(f"{db}: {n_all:,} entries ({n_bad} unparsable names) read in {time.time() - t0:.0f} s")
    sk = pd.DataFrame({"accession": list(skip.keys())})
    con.register("skip_df", sk)
    excl = ""
    if exclude_db:
        ex = fc_dir(root) / f"{exclude_db}.lookup"
        con.execute(f"""CREATE TABLE ex AS SELECT DISTINCT regexp_extract(name, '^AF-(.+)-F[0-9]+-model', 1) AS accession
                        FROM read_csv('{ex}', delim='\t', header=false, columns={{'key': 'UBIGINT', 'name': 'VARCHAR',
                                                                                  'f': 'INTEGER'}})""")
        excl = "AND accession NOT IN (SELECT accession FROM ex)"
    # taxid: current UniProt idmapping; for accessions no longer in UniProt, the taxid shared by the other entries
    # of the same source tar (the lookup's 3rd column numbers the 1,015,797 GCS v4 proteome tars the database was
    # built from, one taxon per tar; checked by the agreement rate logged below)
    tax21 = Path(env("UNIPROT_TAXID_2021", str(d / "uniprot2021_04_taxid.parquet")))
    if tax21.exists():                 # UniProt 2021_04 (the AFDB v4 source release) for accessions removed since
        t21 = f"(SELECT accession, min(taxid) AS taxid FROM read_parquet('{tax21}') GROUP BY accession)"
    else:
        log(f"note: {tax21} missing: accessions no longer in UniProt get their tar's taxid or none")
        t21 = "(SELECT NULL::VARCHAR AS accession, NULL::INTEGER AS taxid WHERE false)"
    con.execute(f"""CREATE TABLE k0 AS
        SELECT e.*, coalesce(t.taxid, t21.taxid) AS utax, t.taxid IS NULL AND t21.taxid IS NOT NULL AS from21 FROM e
        LEFT JOIN read_parquet('{tax}') t USING (accession)
        LEFT JOIN {t21} t21 USING (accession)
        WHERE accession <> '' AND fragment IS NOT NULL
          AND accession NOT IN (SELECT accession FROM skip_df) {excl}""")
    con.execute("DROP TABLE e")
    con.execute("""CREATE TABLE ft AS SELECT tarno, mode(utax) AS ftax FROM k0 WHERE utax IS NOT NULL GROUP BY tarno""")
    n_dis, n_map = con.execute("""SELECT count(*) FILTER (WHERE utax <> ftax), count(*) FROM k0 JOIN ft USING (tarno)
                                  WHERE utax IS NOT NULL""").fetchall()[0]
    n_21 = con.execute("SELECT count(*) FROM k0 WHERE from21").fetchall()[0][0]
    n_files = con.execute("SELECT count(*) FROM ft").fetchall()[0][0]
    use_tar = n_files > 1 and n_dis <= 0.01 * max(n_map, 1)    # only where the 3rd column really numbers source tars
    if not use_tar:
        log(f"{db}: lookup column 3 does not identify source tars ({n_files} values): no taxid fill from tars")
        con.execute("DELETE FROM ft")
    con.execute("""CREATE TABLE k AS SELECT k0.* EXCLUDE (utax, tarno, from21), coalesce(utax, ftax, 0) AS taxid,
                   (utax IS NULL AND ftax IS NOT NULL) AS tax_from_tar FROM k0 LEFT JOIN ft USING (tarno)""")
    con.execute("DROP TABLE k0")
    n_keep = con.execute("SELECT count(*) FROM k").fetchall()[0][0]
    n_unmapped = con.execute("SELECT count(*) FROM k WHERE taxid = 0").fetchall()[0][0]
    n_fromtar = con.execute("SELECT count(*) FROM k WHERE tax_from_tar").fetchall()[0][0]
    log(f"{db}: taxid from UniProt (current idmapping, else 2021_04: {n_21:,}) for {n_map:,} entries ({n_dis:,} = {100 * n_dis / max(n_map, 1):.2f} % "
        f"differ from their tar's majority taxid); {n_fromtar:,} filled from the tar; {n_unmapped:,} unmapped")
    per_tax = con.execute("SELECT taxid, count(*) AS n FROM k GROUP BY taxid").df()
    log(f"{db}: {n_keep:,} entries kept ({n_all - n_keep:,} skipped as tier 1-2"
        f"{' / ' + exclude_db if exclude_db else ''} or unparsable), {n_unmapped:,} without a UniProt taxid, "
        f"{len(per_tax):,} taxa ({time.time() - t0:.0f} s)")
    lin = load_lineage(root, per_tax.taxid[per_tax.taxid > 0].unique())
    lin.loc[0] = dict(tax_name="unmapped accession (not in current UniProt)", genus="", family="", order="",
                      **{"class": ""}, phylum="", superkingdom="unclassified")
    leaf = a.unit_structures
    rows = []
    for t, n in zip(per_tax.taxid.to_numpy(), per_tax.n.to_numpy()):
        for c in range((int(n) + leaf - 1) // leaf):
            rows.append((int(t), c, int(min(leaf, n - c * leaf))))
    lv = pd.DataFrame(rows, columns=["taxid", "chunk", "n"]).join(lin, on="taxid")
    keys = list(zip(*[lv[c].tolist() for c in LEVELS], lv.taxid.tolist()))
    lv = lv.iloc[round_robin(keys, lv["n"].tolist())].reset_index(drop=True)
    units, cur, run = [], [], 0

    def close():
        if not cur:
            return
        f = cur[0]
        ntax = len({r["taxid"] for r in cur})
        units.append(dict(tier=3, source_type="foldcomp", source=db, sources=[f"fc_entries_{db}.parquet"],
                          source_sizes=[int(sum(r["n"] for r in cur))], member_start=len(units),
                          member_end=len(units) + 1, byte_start=0, byte_end=0, taxid=int(f["taxid"]),
                          code=f"tax{f['taxid']}" + (f" (+{ntax - 1})" if ntax > 1 else ""),
                          organism=f["tax_name"] + (f" and {ntax - 1} more taxa" if ntax > 1 else ""),
                          model_version=4, est_structures=int(sum(r["n"] for r in cur)),
                          source_taxids=sorted({int(r["taxid"]) for r in cur})[:50],
                          lineage=";".join(str(f[c]) for c in LEVELS)))
        for r in cur:
            r["fc_unit"] = len(units) - 1
        cur.clear()
    recs = lv.to_dict("records")
    for r in recs:
        if cur and (run + r["n"] > a.unit_structures or len(cur) >= a.gcs_unit_max_tars):
            close()
            run = 0
        cur.append(r)
        run += r["n"]
    close()
    lm = pd.DataFrame({"taxid": [r["taxid"] for r in recs], "chunk": [r["chunk"] for r in recs],
                       "fc_unit": np.array([r["fc_unit"] for r in recs], np.int32)})
    con.register("leafmap", lm)
    out = root / f"fc_entries_{db}.parquet"
    tmp = Path(str(out) + ".tmp")
    con.execute(f"""COPY (
        SELECT m.fc_unit, k.off, k.len, k.key, k.accession, k.fragment, k.version, CAST(k.taxid AS INTEGER) AS taxid
        FROM (SELECT *, CAST((row_number() OVER (PARTITION BY taxid ORDER BY key) - 1) // {leaf} AS INTEGER) AS chunk
              FROM k) k
        JOIN leafmap m USING (taxid, chunk)
        ORDER BY m.fc_unit, k.off)
        TO '{tmp}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 100000)""")
    os.replace(tmp, out)
    taxa = lin.reset_index().rename(columns={"index": "taxid"})
    taxa = taxa[taxa.taxid.isin(per_tax.taxid)]
    taxa.to_parquet(root / f"fc_taxa_{db}.parquet", index=False)
    con.close()
    log(f"{db}: {len(units):,} units -> {out.name} ({out.stat().st_size / 1e9:.2f} GB; {time.time() - t0:.0f} s)")
    return units, {f"{db}_entries": int(n_all), f"{db}_kept": int(n_keep), f"{db}_unmapped_taxid": int(n_unmapped),
                   f"{db}_taxid_idmapping": int(n_map), f"{db}_taxid_from_2021_04": int(n_21), f"{db}_taxid_from_tar": int(n_fromtar),
                   f"{db}_taxid_idmapping_vs_tar_disagree": int(n_dis),
                   f"{db}_taxa": int(len(per_tax)), f"{db}_units": len(units)}


# ============================================================================================ previous work list
KEY_COLS = ["unit_id", "tier", "source_type", "source", "member_start", "member_end", "est_structures"]


def _key(df: pd.DataFrame) -> pd.DataFrame:
    k = df[KEY_COLS].copy()
    k["sources"] = [tuple(x) for x in df["sources"]]
    return k.reset_index(drop=True)


def check_previous(root: Path, wl: pd.DataFrame, force: bool):
    """Before replacing an existing work list: every unit with a done marker must keep its definition (same
    unit_id, tier, source(s), member range), so finished outputs stay valid. Typical case: tiers 1-2 were run,
    tier 3 is added (or switched to another source) later. Failed markers of units that no longer exist or
    changed are moved to state/superseded/ (so a new unit with the same id is not mistaken for failed); the old
    work list is kept as worklist.<time>.parquet."""
    old_p = root / "worklist.parquet"
    if not old_p.exists():
        return
    old = pd.read_parquet(old_p)
    new_k = _key(wl).set_index("unit_id")
    old_k = _key(old).set_index("unit_id")
    ddir, fdir = root / "state" / "done", root / "state" / "failed"
    done = sorted(int(f.stem) for f in ddir.glob("*.json") if f.stem.isdigit()) if ddir.exists() else []
    bad = [u for u in done if u not in new_k.index or u not in old_k.index or
           not new_k.loc[u].equals(old_k.loc[u])]
    if bad and not force:
        raise SystemExit(f"refusing to replace {old_p}: {len(bad)} finished units would change definition "
                         f"(e.g. unit_id {bad[:5]}); outputs of finished units would no longer match the work list. "
                         "Use the same tier-1/2 options as before (or --force).")
    for t in sorted(set(old.tier)):
        o, n = old_k[old_k.tier == t], new_k[new_k.tier == t]
        same = len(o) == len(n) and o.equals(n)
        log(f"previous work list, tier {t}: {len(o)} units -> {len(n)} ({'identical' if same else 'CHANGED'})")
    moved = 0
    sup = root / "state" / "superseded" / time.strftime("%Y%m%dT%H%M%S")
    for f in (sorted(fdir.glob("*.json")) if fdir.exists() else []):
        u = int(f.stem) if f.stem.isdigit() else -1
        try:
            src = json.loads(f.read_text()).get("source")
        except (OSError, ValueError):
            src = None
        if u not in new_k.index or u not in old_k.index or not new_k.loc[u].equals(old_k.loc[u]) or \
                (src is not None and src != new_k.loc[u, "source"]):
            sup.mkdir(parents=True, exist_ok=True)
            f.replace(sup / f.name)
            moved += 1
    if moved:
        log(f"moved {moved} failed markers of replaced units to {sup}")
    backup = root / f"worklist.{time.strftime('%Y%m%dT%H%M%S')}.parquet"
    old_p.replace(backup)
    log(f"previous work list kept as {backup.name}")


# ============================================================================================ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-root", default=None, help="default $OUT_ROOT")
    ap.add_argument("--tiers", default="1,2,3")
    ap.add_argument("--afdb-local", default=env("AFDB_LOCAL", "/cluster/work/beltrao/shared/alphafold/v6"))
    ap.add_argument("--unit-structures", type=int, default=env("UNIT_STRUCTURES", 4000))
    ap.add_argument("--gcs-unit-max-tars", type=int, default=env("GCS_UNIT_MAX_TARS", 2000))
    ap.add_argument("--gcs-bytes-per-model", type=float, default=env("GCS_BYTES_PER_MODEL", 0.0))
    ap.add_argument("--gcs-max-pages", type=int, default=None, help="stop the GCS listing after N pages (testing)")
    ap.add_argument("--gcs-refresh", action="store_true", help="re-list the bucket even if a cached listing exists")
    ap.add_argument("--gcs-listing", default=None, help="use this listing (TSV: object name, size) instead")
    ap.add_argument("--tier3-source", choices=["foldcomp", "gcs"], default=env("TIER3_SOURCE", "foldcomp"))
    ap.add_argument("--foldcomp-db", default=env("FOLDCOMP_DB", "afdb_uniprot_v4"),
                    help="Foldcomp database in $FOLDCOMP_DIR for tier 3 (afdb_uniprot_v4 = all AFDB v4)")
    ap.add_argument("--tier-reps", type=int, default=env("TIER_REPS", 0),
                    help="1: run the afdb_rep_v4 representatives first within tier 3 (Foldcomp only)")
    ap.add_argument("--tier1-codes", default=None, help="restrict tier 1 to these codes (testing), e.g. ECOLI,HUMAN")
    ap.add_argument("--no-swissprot", action="store_true", help="leave Swiss-Prot out (testing)")
    ap.add_argument("--limit-per-source", type=int, default=None, help="first N models of each local tar (testing)")
    ap.add_argument("--max-units-per-tier", type=int, default=None, help="keep the first N units per tier (testing)")
    ap.add_argument("--index-threads", type=int, default=8)
    ap.add_argument("--force", action="store_true", help="replace a work list even if finished units change")
    ap.add_argument("--nodes", type=int, default=env("SLURM_NODES", 4))
    ap.add_argument("--rate", type=float, default=RATE, help="structures/s per node for the ETA")
    a = ap.parse_args()
    root = out_root(a.out_root)
    root.mkdir(parents=True, exist_ok=True)
    tiers = sorted({int(t) for t in a.tiers.split(",")})
    t0 = time.time()
    units, skip, _ = local_units(a, root, tiers)
    extra = {}
    if 3 in tiers and a.tier3_source == "gcs":
        u3, extra = gcs_units(a, root, skip)
        units += u3
    elif 3 in tiers:
        if a.tier_reps:                  # Foldseek cluster representatives first (still tier 3)
            ur, er = fc_units(a, root, skip, "afdb_rep_v4")
            units += ur
            extra.update(er)
        u3, e3 = fc_units(a, root, skip, a.foldcomp_db, exclude_db="afdb_rep_v4" if a.tier_reps else None)
        units += u3
        extra.update(e3)
    wl = pd.DataFrame(units)
    if a.max_units_per_tier:
        wl = wl.groupby("tier", group_keys=False).head(a.max_units_per_tier)
    wl = wl.sort_values("tier", kind="stable").reset_index(drop=True)
    for c, dflt in (("source_taxids", None), ("source_sizes", None), ("lineage", "")):
        if c not in wl:
            wl[c] = dflt
    wl["source_taxids"] = [x if isinstance(x, list) else [int(t)] for x, t in zip(wl.source_taxids, wl.taxid)]
    wl["source_sizes"] = [x if isinstance(x, list) else [int(e - b)] for x, b, e in
                          zip(wl.source_sizes, wl.byte_start, wl.byte_end)]
    so = pd.read_csv(HERE / "species_order.tsv", sep="\t")
    if (wl.tier == 1).any():
        lin1 = load_lineage(root, so.taxid.unique())
        m1 = wl.tier == 1
        wl.loc[m1, "lineage"] = [";".join(str(lin1.loc[t, c]) for c in LEVELS) for t in wl.loc[m1, "taxid"]]
    wl.loc[wl.tier == 2, "lineage"] = "mixed"
    wl.insert(0, "unit_id", np.arange(len(wl), dtype=np.int64))
    cols = ["unit_id", "tier", "source_type", "source", "sources", "member_start", "member_end", "byte_start",
            "byte_end", "taxid", "code", "organism", "lineage", "model_version", "est_structures", "source_taxids",
            "source_sizes"]
    wl = wl[cols]
    check_previous(root, wl, a.force)
    wl.to_parquet(root / "worklist.parquet.tmp", index=False)
    os.replace(root / "worklist.parquet.tmp", root / "worklist.parquet")
    tsv = wl.drop(columns=["sources", "source_taxids", "source_sizes"]).assign(n_sources=wl.sources.map(len))
    tsv.to_csv(root / "worklist.tsv.tmp", sep="\t", index=False)
    os.replace(root / "worklist.tsv.tmp", root / "worklist.tsv")
    skip_txt = "".join(f"{k}\t{v}\n" for k, v in sorted(skip.items()))
    atomic_write_bytes(root / "skip_accessions.txt", skip_txt.encode())
    rate = a.rate * a.nodes
    summ = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "tiers": {}, "nodes": a.nodes, "rate_per_node": a.rate,
            "skip_accessions": {"tier1": sum(v == 1 for v in skip.values()), "tier2": sum(v == 2 for v in skip.values())},
            **extra}
    for t, g in wl.groupby("tier"):
        n = int(g.est_structures.sum())
        if t == 3 and "est_structures_after_skip" in extra:
            n = int(extra["est_structures_after_skip"] * g.est_structures.sum() / max(1, extra["est_structures_before_skip"]))
        summ["tiers"][int(t)] = {"units": int(len(g)), "est_structures": n, "eta_hours": round(n / rate / 3600, 2)}
    summ["total_est_structures"] = sum(v["est_structures"] for v in summ["tiers"].values())
    summ["total_eta_hours"] = round(summ["total_est_structures"] / rate / 3600, 1)
    atomic_write_json(root / "worklist.json", summ)
    log(f"worklist: {len(wl)} units -> {root / 'worklist.parquet'} ({time.time() - t0:.0f} s)")
    for t, v in summ["tiers"].items():
        log(f"  tier {t}: {v['units']} units, {v['est_structures']:,} structures, ETA {v['eta_hours']} h "
            f"at {a.nodes} x {a.rate:.0f} structures/s")
    log(f"  total {summ['total_est_structures']:,} structures, ETA {summ['total_eta_hours']} h; "
        f"skip list {len(skip):,} accessions")


if __name__ == "__main__":
    main()
