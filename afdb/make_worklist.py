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
  3  every other (taxid, shard) tar of the GCS v4 bucket (highest model version per (taxid, shard)), ordered by a
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
    ap.add_argument("--tier1-codes", default=None, help="restrict tier 1 to these codes (testing), e.g. ECOLI,HUMAN")
    ap.add_argument("--no-swissprot", action="store_true", help="leave Swiss-Prot out (testing)")
    ap.add_argument("--limit-per-source", type=int, default=None, help="first N models of each local tar (testing)")
    ap.add_argument("--max-units-per-tier", type=int, default=None, help="keep the first N units per tier (testing)")
    ap.add_argument("--index-threads", type=int, default=8)
    ap.add_argument("--nodes", type=int, default=env("SLURM_NODES", 4))
    ap.add_argument("--rate", type=float, default=RATE, help="structures/s per node for the ETA")
    a = ap.parse_args()
    root = out_root(a.out_root)
    root.mkdir(parents=True, exist_ok=True)
    tiers = sorted({int(t) for t in a.tiers.split(",")})
    t0 = time.time()
    units, skip, _ = local_units(a, root, tiers)
    extra = {}
    if 3 in tiers:
        u3, extra = gcs_units(a, root, skip)
        units += u3
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
        if t == 3 and extra:
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
