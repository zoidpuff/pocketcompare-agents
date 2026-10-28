#!/usr/bin/env python
"""Retrain the pocketcompare projection head on your own pocket pairs (needs ``pip install pocketcompare[train]``).

    pocketcompare describe structures/ --n1 -o pockets.parquet            # N1 descriptors (+ fingerprints)
    python scripts/train_head.py --pockets pockets.parquet --pairs pairs.tsv --out my_head/ [--device cuda:0]
    python -c "from pocketcompare.method import Method; m = Method('my_head/method.yaml'); print(m.dim)"

This is a compact port of the recipe that produced the published head (research script ``train_a4b.py``,
configuration ``n1_linear``).  Published defaults: linear head 627 -> 128 with dropout 0.2 on the input, 3 seeds
(0, 1, 2), AdamW (lr 1e-3, weight decay 1e-4), 50 steps per epoch, at most 80 epochs, early stopping with patience
10 on a 10 % homology-group hold-out, loss = symmetric InfoNCE (temperature 0.1, 256 positive pairs per batch,
in-batch negatives) + 1.0 x BCE on a balanced batch of 512 labelled pairs (logit = a * cosine + b, learnable a, b).

Inputs
------
``--pockets``: one or more parquet tables written by ``pocketcompare describe --n1`` (columns ``pocket_id`` and
``n1``; other columns are ignored).  Pocket ids must be unique across the tables.

``--pairs``: a table (.tsv, .csv or .parquet) with one row per labelled pocket pair:

=============  ========  ===========================================================================================
column         required  meaning
=============  ========  ===========================================================================================
pocket_a       yes       ``pocket_id`` of the first pocket
pocket_b       yes       ``pocket_id`` of the second pocket
label          yes       1 = similar (e.g. the two pockets bind the same / a similar ligand), 0 = dissimilar
group_a        no        homology group of pocket_a (e.g. a sequence/structure cluster id); default: the structure
                         (the part of the pocket id before the first ':')
group_b        no        homology group of pocket_b
source         no        name of the pair source (default ``pairs``); positives are drawn from the sources with the
                         weights of ``--source-weights``
=============  ========  ===========================================================================================

Groups do two things: (1) InfoNCE never uses two pockets of the same group (or a known positive pair) as a negative
pair; (2) the early-stopping hold-out is 10 % of the pockets, chosen as whole groups, and hold-out pockets are never
trained on.  Negatives (label 0) are used only by the BCE term; positives by both terms.

The published head used three positive sources (``--source-weights blips=0.5,ld=0.25,ppips=0.25``; counts from
``models/n1_linear/config.json``):
* ``blips``: BioLiP ligand-sharing pairs among 2,318 training sites (33,334 labelled training pairs, 5,574 positive;
  positives and negatives, the only source of the BCE term);
* ``ld``: 1,560 same-site pairs (the ligand-shell description and the BURROW-pocket description of the same site,
  i.e. ``describe(..., site=ligand)`` and ``describe(..., site=ligand, locate="burrow")``) teaching invariance to
  the pocket definition;
* ``ppips``: 3,327 protein-protein-interface pocket pairs among 15,555 AlphaFold-dimer pockets (2,284 symmetric
  copies in homodimers, 1,043 interolog pairs).
The original script additionally drew each BLiPS endpoint at random in ligand-shell or BURROW-pocket form
(p = 0.5); here every pocket is a row of its own, so add both forms as separate pockets to imitate it.
``scripts/build_pair_table_example.py`` writes a tiny example of both inputs from the example structures.

Input statistics: ``--stats fit`` (default) z-scores each N1 part with the mean/std of all pockets in the pair
table (the published head used the training sites); ``--stats shipped`` reuses the published statistics.

Output directory: ``seed<k>.npz`` (float32 ``w2``/``b2`` [+ ``w1``/``b1``/``ln_w``/``ln_b`` with ``--hidden``]),
``input_stats.json``, ``config.json``, ``train_log.json`` and ``method.yaml`` (a config for
``pocketcompare.method.Method``; the BURROW model, site definition and N1 descriptor are those of the frozen method).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULTS = dict(hidden=None, out_dim=128, dropout=0.2, lr=1e-3, weight_decay=1e-4, tau=0.1, batch_pos=256,
                batch_lab=512, lambda_bce=1.0, steps_per_epoch=50, max_epochs=80, patience=10, holdout=0.1)


def sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def roc_auc(y, s) -> float:
    """ROC-AUC (Mann-Whitney, ties averaged); NaN if a class is missing."""
    from scipy.stats import rankdata
    y = np.asarray(y, bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(np.asarray(s, np.float64))
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


# ============================================================================================ data
def read_pairs(path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix == ".parquet":
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p, sep="\t" if p.suffix in (".tsv", ".txt") else ",")
    miss = {"pocket_a", "pocket_b", "label"} - set(df.columns)
    if miss:
        raise SystemExit(f"{path}: missing columns {sorted(miss)}")
    df["label"] = df["label"].astype(int)
    if not df.label.isin([0, 1]).all():
        raise SystemExit("label must be 0 or 1")
    if "source" not in df:
        df["source"] = "pairs"
    for s in ("a", "b"):
        if f"group_{s}" not in df:
            df[f"group_{s}"] = df[f"pocket_{s}"].astype(str).str.split(":").str[0]
    return df


class Data:
    """Pockets (rows of X), their groups, the labelled pairs and the positive pools per source."""

    def __init__(self, pocket_tables, pairs: pd.DataFrame, stats: str, holdout: float, seed: int, log):
        from pocketcompare import fpindex as FX
        from pocketcompare import head as H
        ids, Ns = [], []
        for t in pocket_tables:
            meta, _, _, N = FX.read_table(t, with_n1=True)
            ids += meta.pocket_id.astype(str).tolist()
            Ns.append(N)
        N = np.vstack(Ns).astype(np.float64)
        if len(set(ids)) != len(ids):
            raise SystemExit("pocket ids are not unique across the --pockets tables")
        pos = pd.Series(np.arange(len(ids)), index=ids)
        need = pd.unique(pd.concat([pairs.pocket_a, pairs.pocket_b]).astype(str))
        missing = [p for p in need if p not in pos.index]
        if missing:
            raise SystemExit(f"{len(missing)} pair pockets not in --pockets (e.g. {missing[:3]})")
        use = pos.loc[need].to_numpy()
        mats = H.split_parts(N[use])
        ok = H.available(mats)
        if not ok.all():
            log(f"dropping {int((~ok).sum())} pockets without a descriptor (and their pairs)")
        self.ids = [p for p, k in zip(need, ok) if k]
        idx = {p: i for i, p in enumerate(self.ids)}
        mats = [m[ok] for m in mats]
        if stats == "shipped":
            from pocketcompare import method
            self.scaler = method.default().scaler
        else:
            self.scaler = H.PartScaler.fit("N1", [mats])
        self.X = H.head_input(mats, self.scaler)
        pairs = pairs[pairs.pocket_a.astype(str).isin(idx) & pairs.pocket_b.astype(str).isin(idx)]
        a = pairs.pocket_a.astype(str).map(idx).to_numpy()
        b = pairs.pocket_b.astype(str).map(idx).to_numpy()
        y = pairs.label.to_numpy()
        src = pairs.source.astype(str).to_numpy()
        # groups: first assignment of each pocket wins
        g = {}
        for p, q in ((pairs.pocket_a, pairs.group_a), (pairs.pocket_b, pairs.group_b)):
            for k, v in zip(p.astype(str), q.astype(str)):
                g.setdefault(k, v)
        self.group = pd.factorize(pd.Series([g[p] for p in self.ids]))[0].astype(np.int64)
        # early-stopping hold-out: whole groups until >= holdout of the pockets
        rng = np.random.default_rng(seed)
        cnt = np.bincount(self.group)
        hold, n = [], 0
        for gg in rng.permutation(np.unique(self.group)):
            if n >= holdout * len(self.ids):
                break
            hold.append(gg)
            n += cnt[gg]
        self.hold = np.isin(self.group, hold)
        es = self.hold[a] | self.hold[b]
        self.tr = (a[~es], b[~es], y[~es], src[~es])
        self.es = (a[es], b[es], y[es])
        if len(np.unique(self.es[2])) < 2:
            log("note: the hold-out has no positive and negative pairs -> no early stopping (fixed max_epochs)")
            self.es = None
        self.knownpos = set(zip(a[y == 1].tolist(), b[y == 1].tolist())) | set(zip(b[y == 1].tolist(),
                                                                                  a[y == 1].tolist()))
        ta, tb, ty, ts = self.tr
        self.pools = {s: np.stack([ta[(ty == 1) & (ts == s)], tb[(ty == 1) & (ts == s)]], 1) for s in np.unique(ts)}
        self.pools = {s: v for s, v in self.pools.items() if len(v)}
        lab_src = {s for s in np.unique(ts) if ((ts == s) & (ty == 0)).any()}
        lab = np.isin(ts, list(lab_src))
        self.lab = (ta[lab], tb[lab], ty[lab])
        if not self.pools:
            raise SystemExit("no positive training pairs outside the hold-out")
        self.n = {"pockets": len(self.ids), "pockets_holdout": int(self.hold.sum()), "groups": int(cnt.size),
                  "train_pairs": int(len(ta)), "train_pos": int(ty.sum()),
                  "es_pairs": 0 if self.es is None else int(len(self.es[0])),
                  "positives_per_source": {s: int(len(v)) for s, v in self.pools.items()},
                  "bce_pairs": int(len(self.lab[0])), "bce_sources": sorted(lab_src)}

    def sample_pos(self, rng, B, weights: dict):
        srcs = list(self.pools)
        w = np.asarray([weights.get(s, 1.0) for s in srcs], float)
        if w.sum() <= 0:
            raise SystemExit("all positive sources have weight 0")
        k = rng.choice(len(srcs), size=B, p=w / w.sum())
        ia, ib = np.zeros(B, np.int64), np.zeros(B, np.int64)
        for j, s in enumerate(srcs):
            m = k == j
            if m.any():
                pr = self.pools[s][rng.integers(len(self.pools[s]), size=m.sum())]
                flip = rng.random(m.sum()) < 0.5
                ia[m], ib[m] = np.where(flip, pr[:, 1], pr[:, 0]), np.where(flip, pr[:, 0], pr[:, 1])
        return ia, ib

    def sample_lab(self, rng, B):
        a, b, y = self.lab
        P_, N_ = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
        k = np.concatenate([rng.choice(P_, B // 2), rng.choice(N_, B - B // 2)])
        return a[k], b[k], y[k]

    def neg_mask(self, ia, ib):
        """True where (a_i, b_j), i != j, may be a positive (masked from the InfoNCE denominator)."""
        m = (ia[:, None] == ib[None, :]) | (self.group[ia][:, None] == self.group[ib][None, :])
        if self.knownpos:
            kp = np.array([[(x, z) in self.knownpos for z in ib.tolist()] for x in ia.tolist()], bool)
            m |= kp
        np.fill_diagonal(m, False)
        return m


# ============================================================================================ model / training
def make_model(cfg, d_in):
    import torch.nn as nn
    if cfg["hidden"]:
        return nn.Sequential(nn.Linear(d_in, cfg["hidden"]), nn.LayerNorm(cfg["hidden"]), nn.GELU(),
                             nn.Dropout(cfg["dropout"]), nn.Linear(cfg["hidden"], cfg["out_dim"]))
    return nn.Sequential(nn.Dropout(cfg["dropout"]), nn.Linear(d_in, cfg["out_dim"]))


def export_params(model) -> dict:
    import torch.nn as nn
    lin = [m for m in model if isinstance(m, nn.Linear)]
    ln = [m for m in model if isinstance(m, nn.LayerNorm)]
    p = {}
    if len(lin) == 2:
        p.update(w1=lin[0].weight, b1=lin[0].bias, ln_w=ln[0].weight, ln_b=ln[0].bias, w2=lin[1].weight,
                 b2=lin[1].bias)
    else:
        p.update(w2=lin[0].weight, b2=lin[0].bias)
    return {k: v.detach().cpu().numpy().astype(np.float32) for k, v in p.items()}


def es_metric(model, data: Data, device) -> float:
    import torch
    import torch.nn.functional as F
    model.eval()
    with torch.no_grad():
        Z = F.normalize(model(torch.from_numpy(data.X).to(device)), dim=1).cpu().numpy()
    model.train()
    a, b, y = data.es
    return roc_auc(y.astype(bool), (Z[a] * Z[b]).sum(1))


def train_seed(cfg, data: Data, seed: int, device: str, weights: dict, log):
    import torch
    import torch.nn.functional as F
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = make_model(cfg, data.X.shape[1]).to(device)
    scale = torch.nn.Parameter(torch.tensor(10.0, device=device))
    bias = torch.nn.Parameter(torch.tensor(-5.0, device=device))
    opt = torch.optim.AdamW(list(model.parameters()) + [scale, bias], lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    X = torch.from_numpy(data.X).to(device)
    use_bce = cfg["lambda_bce"] > 0 and len(data.lab[0]) and (data.lab[2] == 1).any() and (data.lab[2] == 0).any()
    best, best_state, best_ep, bad, hist = -np.inf, None, -1, 0, []
    t0 = time.time()
    for ep in range(cfg["max_epochs"]):
        tot = {"nce": 0.0, "bce": 0.0}
        for _ in range(cfg["steps_per_epoch"]):
            ia, ib = data.sample_pos(rng, cfg["batch_pos"], weights)
            za = F.normalize(model(X[torch.from_numpy(ia).to(device)]), dim=1)
            zb = F.normalize(model(X[torch.from_numpy(ib).to(device)]), dim=1)
            logits = (za @ zb.T / cfg["tau"]).masked_fill(torch.from_numpy(data.neg_mask(ia, ib)).to(device),
                                                           float("-inf"))
            tgt = torch.arange(len(ia), device=device)
            loss_nce = 0.5 * (F.cross_entropy(logits, tgt) + F.cross_entropy(logits.T, tgt))
            loss = loss_nce
            if use_bce:
                la, lb, ly = data.sample_lab(rng, cfg["batch_lab"])
                ca = F.normalize(model(X[torch.from_numpy(la).to(device)]), dim=1)
                cb = F.normalize(model(X[torch.from_numpy(lb).to(device)]), dim=1)
                lg = scale * (ca * cb).sum(1) + bias
                loss_bce = F.binary_cross_entropy_with_logits(lg, torch.from_numpy(ly.astype(np.float32)).to(device))
                loss = loss + cfg["lambda_bce"] * loss_bce
                tot["bce"] += float(loss_bce)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot["nce"] += float(loss_nce)
        es = es_metric(model, data, device) if data.es is not None else float(ep)
        hist.append({"epoch": ep, **{k: v / cfg["steps_per_epoch"] for k, v in tot.items()}, "es": es})
        if es > best + 1e-6:
            best, best_ep, bad = es, ep, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg["patience"]:
                break
    model.load_state_dict(best_state)
    model.eval()
    log(f"  seed {seed}: best epoch {best_ep}" + (f", hold-out ROC-AUC {best:.4f}" if data.es is not None else "")
        + f"; {len(hist)} epochs, {time.time() - t0:.0f} s")
    return export_params(model), {"seed": seed, "best_epoch": best_ep, "best_es": best, "epochs_run": len(hist),
                                  "history": hist}


def write_method_yaml(out: Path, cfg: dict, files: dict, name: str):
    import yaml
    from pocketcompare.resources import default_config
    base = yaml.safe_load(default_config().read_text())
    m = {k: base[k] for k in ("parts", "site", "a1", "env", "burrow")}
    doc = {"name": name, "root": ".", "kind": "learned", "variant": "raw", "input": "N1",
           "dims": cfg["out_dim"] * len(cfg["seeds"]), "csls_k": 10, **m,
           "input_stats": "input_stats.json", "model_files": [f"seed{s}.npz" for s in cfg["seeds"]],
           "files_sha256": files}
    (out / "method.yaml").write_text("# written by scripts/train_head.py\n" + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pockets", nargs="+", required=True, help="parquet tables from `pocketcompare describe --n1`")
    ap.add_argument("--pairs", required=True, help="pair table (.tsv/.csv/.parquet; see the module docstring)")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--stats", choices=["fit", "shipped"], default="fit")
    ap.add_argument("--source-weights", default="", help="e.g. blips=0.5,ld=0.25,ppips=0.25 (default: equal)")
    for k, v in DEFAULTS.items():
        ap.add_argument("--" + k.replace("_", "-"), type=type(v) if v is not None else int, default=v)
    a = ap.parse_args(argv)
    try:
        import torch  # noqa: F401
    except ImportError:
        raise SystemExit("PyTorch is needed: pip install 'pocketcompare[train]'")
    cfg = {k: getattr(a, k) for k in DEFAULTS}
    cfg["seeds"] = [int(s) for s in a.seeds.split(",")]
    weights = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in a.source_weights.split(",") if kv}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def log(msg):
        print(f"[{time.time() - t0:6.0f}s] {msg}", file=sys.stderr, flush=True)

    data = Data(a.pockets, read_pairs(a.pairs), a.stats, cfg["holdout"], cfg["seeds"][0], log)
    log(f"data: {json.dumps(data.n)}")
    files, logs = {}, []
    for s in cfg["seeds"]:
        params, info = train_seed(cfg, data, s, a.device, weights, log)
        np.savez(out / f"seed{s}.npz", **params)
        files[f"seed{s}.npz"] = sha256_file(out / f"seed{s}.npz")
        logs.append(info)
    (out / "input_stats.json").write_text(json.dumps(data.scaler.to_dict()))
    files["input_stats.json"] = sha256_file(out / "input_stats.json")
    (out / "train_log.json").write_text(json.dumps(logs))
    import torch
    conf = {**cfg, "input": "N1", "d_in": int(data.X.shape[1]), "stats": a.stats, "source_weights": weights,
            "data_counts": data.n, "pairs": str(a.pairs), "pairs_sha256": sha256_file(a.pairs),
            "device": a.device, "torch": torch.__version__, "best_epochs": [lg["best_epoch"] for lg in logs]}
    (out / "config.json").write_text(json.dumps(conf, indent=1, default=str))
    files["config.json"] = sha256_file(out / "config.json")
    write_method_yaml(out, cfg, files, f"custom:{out.name}")
    log(f"saved {out}/ (use: pocketcompare.method.Method('{out}/method.yaml'))")


if __name__ == "__main__":
    main()
