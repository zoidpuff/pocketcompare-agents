#!/usr/bin/env python
"""A4b — learned projection head on the N1 / N2 inputs (PREREG §1; configs/a4b_grid.yaml).

    python scripts/train_a4b.py --config n1_base --device cuda:0            # 3 seeds (SEEDS[:3]) of one grid entry
    python scripts/train_a4b.py --all --devices cuda:0,cuda:1               # whole grid, one process per device
    python scripts/train_a4b.py --synthetic --config n1_base --device cpu   # code smoke test on random data only

Training data (never TOUGH-M1, BLiPS-val, PPIPS-val or any test set):
* BLiPS-train v2 labelled site pairs (data/splits/blips_train_pairs_v2.parquet; label, max_tc);
* L<->D same-site positives: the L-mode and D-mode (best sub-pocket U) descriptors of the same BLiPS-train site
  (only D-matched sites: coverage >= 0.3 or precision >= 0.5);
* PPIPS-train P-sym pairs and P-ortho (query, positive) pairs (D mode, merged region pockets).
Fixed choices (also in configs/a4b_grid.yaml ``common``):
* Early-stopping hold-out: 10 % of the BLiPS-train homology groups (``group_id``; rng(SEEDS[0]) permutation, groups
  added until >= 10 % of the train sites), identical for every config and seed.  Training pairs = both sites in the
  fit groups; ES pairs = at least one site in the hold-out groups (never trained on).  L<->D positives of hold-out
  sites are not trained on.
* Input = z-scored parts (BLiPS-train v2 L + U rows), clipped to +-5 (``pocketcompare.a4b.head_input``).
* Loss = symmetric InfoNCE over a batch of positive pairs with in-batch negatives (temperature tau; logits of
  pairs that may be positive are masked: same site/pocket, same homology group / PPIPS complex group, or a labelled
  BLiPS-train positive) + lambda * BCE on a balanced batch of labelled BLiPS-train pairs (logit = a * cos + b,
  learnable a, b; target = label, or max_tc if ``graded``).  Each BLiPS endpoint is drawn in L or D mode
  (D with p = 0.5 if D-matched).
* ES metric = mean of ROC-AUC (pocketcompare.evaluate.roc_auc) on the ES pairs in L mode and in D mode (both sites
  D-matched); evaluated every epoch; the best epoch's weights are kept; stop after ``patience`` epochs without
  improvement.
Outputs: results/models/a4b/<config>/{seed<k>.npz (float32 numpy params), input_stats.json, config.json (incl.
sha256 of every file), train_log.json}.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pocketcompare import a4b as A4  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare.provenance import git_state, sha256_file  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402

GRID = ROOT / "configs/a4b_grid.yaml"
OUT = ROOT / "results/models/a4b"


def load_grid():
    import yaml
    g = yaml.safe_load(GRID.read_text())
    out = {}
    for name, over in g["configs"].items():
        c = dict(g["common"])
        c.update(over or {})
        c["name"] = name
        out[name] = c
    return out, g


# ============================================================================================ data
class Data:
    """All training tensors for one input (N1 | N2).  Items: 0..Nb-1 BLiPS L rows, Nb..2Nb-1 BLiPS D rows,
    2Nb.. PPIPS-train pockets.  Entities (masking): BLiPS site s -> s; PPIPS pocket p -> Nb + p."""

    def __init__(self, inp: str, synthetic: bool = False):
        self.inp = inp
        rng = np.random.default_rng(SEEDS[0])
        sites = pd.read_parquet(A4.SITES_V2)
        tr = sites[sites.partition == "train"].sort_values("site_id").reset_index(drop=True)
        self.site_ids = tr.site_id.tolist()
        Nb = len(tr)
        self.Nb = Nb
        ids = A4.ids_table("blips").set_index("pocket_id").loc[self.site_ids]
        self.dmatch = ids.d_match.to_numpy(bool)
        # ---- inputs
        self.scaler = A4.blips_train_scaler(inp)
        XL = A4.head_input(A4.raw_parts("blips", "L", self.site_ids, inp), self.scaler)
        XD = A4.head_input(A4.raw_parts("blips", "D", self.site_ids, inp), self.scaler)
        pk = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
        cs = pd.read_parquet(ROOT / "data/splits/ppips_complex_splits.parquet")
        pt = pk[pk.split == "train"].reset_index(drop=True)
        Xp = A4.head_input(A4.raw_parts("ppips", "D", pt.pocket_id.tolist(), inp), self.scaler)
        Np = len(pt)
        self.Np = Np
        X = np.concatenate([XL, XD, Xp]).astype(np.float32)
        if synthetic:     # code smoke test: random inputs, never real descriptors
            X = rng.normal(size=X.shape).astype(np.float32)
        self.X = X
        # ---- groups (global ints) per entity
        grp_b = pd.factorize(tr.group_id)[0]
        gmap = dict(zip(cs.complex, cs.group))
        grp_p = pd.factorize(pt.complex.map(gmap))[0] + grp_b.max() + 1
        self.group = np.concatenate([grp_b, grp_p]).astype(np.int64)
        # ---- ES hold-out groups (10 % of the sites)
        ug = rng.permutation(np.unique(grp_b))
        cnt = np.bincount(grp_b)
        hold, n = [], 0
        for g in ug:
            if n >= 0.1 * Nb:
                break
            hold.append(g)
            n += cnt[g]
        self.hold = np.isin(grp_b, hold)
        # ---- BLiPS labelled pairs
        pairs = pd.read_parquet(ROOT / "data/splits/blips_train_pairs_v2.parquet")
        pos = {s: i for i, s in enumerate(self.site_ids)}
        a = pairs.site_a.map(pos).to_numpy()
        b = pairs.site_b.map(pos).to_numpy()
        if np.isnan(a.astype(float)).any() or np.isnan(b.astype(float)).any():
            raise RuntimeError("train pair with a non-train site")
        y = pairs.label.to_numpy().astype(int)
        tc = pairs.max_tc.to_numpy(np.float32)
        if synthetic:     # labels permuted as well: pure noise, nothing real is learnt
            perm = rng.permutation(len(y))
            y, tc = y[perm], tc[perm]
        es = self.hold[a] | self.hold[b]
        self.tr_pairs = (a[~es], b[~es], y[~es], tc[~es])
        self.es_pairs = (a[es], b[es], y[es])
        self.knownpos = np.zeros((Nb, Nb), bool)
        self.knownpos[a[y == 1], b[y == 1]] = True
        self.knownpos[b[y == 1], a[y == 1]] = True
        # ---- positive-pair pools: (entity_a, item_a_L, item_a_D or -1, entity_b, ...)
        ta, tb, ty, _ = self.tr_pairs
        self.pool_blips = np.stack([ta[ty == 1], tb[ty == 1]], 1)
        ld = np.where(self.dmatch & ~self.hold)[0]
        self.pool_ld = ld
        ppos = {p: i for i, p in enumerate(pt.pocket_id)}
        sym = pd.read_parquet(ROOT / "data/splits/ppips_sym_pairs_train.parquet")
        orth = pd.read_parquet(ROOT / "data/splits/ppips_ortho_queries_train.parquet")
        pp = [(ppos[r.pocket_a], ppos[r.pocket_b]) for r in sym.itertuples()]
        pp += [(ppos[r.query], ppos[q]) for r in orth.itertuples() for q in r.positives]
        self.pool_ppips = np.asarray(pp, np.int64)
        self.n = {"sites": Nb, "sites_holdout": int(self.hold.sum()), "groups_holdout": len(hold),
                  "dmatch_sites": int(self.dmatch.sum()), "train_pairs": int((~es).sum()),
                  "train_pos": int(ty.sum()), "es_pairs": int(es.sum()), "es_pos": int(y[es].sum()),
                  "ld_pos": int(len(ld)), "ppips_pockets": Np, "ppips_pos": int(len(pp)),
                  "ppips_sym": int(len(sym)), "ppips_ortho": int(len(pp) - len(sym))}

    # items of BLiPS site s in a mode drawn per endpoint
    def blips_item(self, s, rng, p_d):
        d = self.dmatch[s] & (rng.random(len(s)) < p_d)
        return np.where(d, self.Nb + s, s)

    def sample_pos(self, rng, B, w, p_d):
        """(items_a, items_b, entities_a, entities_b) of B positive pairs from the source mixture ``w``."""
        src = rng.choice(3, size=B, p=np.asarray(w) / np.sum(w))
        ia, ib, ea, eb = (np.zeros(B, np.int64) for _ in range(4))
        k = src == 0
        if k.any():
            pr = self.pool_blips[rng.integers(len(self.pool_blips), size=k.sum())]
            flip = rng.random(k.sum()) < 0.5
            s, t = np.where(flip, pr[:, 1], pr[:, 0]), np.where(flip, pr[:, 0], pr[:, 1])
            ia[k], ib[k], ea[k], eb[k] = self.blips_item(s, rng, p_d), self.blips_item(t, rng, p_d), s, t
        k = src == 1
        if k.any():
            s = self.pool_ld[rng.integers(len(self.pool_ld), size=k.sum())]
            flip = rng.random(k.sum()) < 0.5
            ia[k], ib[k] = np.where(flip, self.Nb + s, s), np.where(flip, s, self.Nb + s)
            ea[k], eb[k] = s, s
        k = src == 2
        if k.any():
            pr = self.pool_ppips[rng.integers(len(self.pool_ppips), size=k.sum())]
            flip = rng.random(k.sum()) < 0.5
            s, t = np.where(flip, pr[:, 1], pr[:, 0]), np.where(flip, pr[:, 0], pr[:, 1])
            ia[k], ib[k], ea[k], eb[k] = 2 * self.Nb + s, 2 * self.Nb + t, self.Nb + s, self.Nb + t
        return ia, ib, ea, eb

    def sample_lab(self, rng, B, p_d):
        ta, tb, ty, tc = self.tr_pairs
        P_, N_ = np.where(ty == 1)[0], np.where(ty == 0)[0]
        k = np.concatenate([rng.choice(P_, B // 2), rng.choice(N_, B - B // 2)])
        return self.blips_item(ta[k], rng, p_d), self.blips_item(tb[k], rng, p_d), ty[k], tc[k]

    def neg_mask(self, ea, eb):
        """True where (a_i, b_j), i != j, may be a positive (masked from the InfoNCE denominator)."""
        m = (ea[:, None] == eb[None, :]) | (self.group[ea][:, None] == self.group[eb][None, :])
        bb = (ea[:, None] < self.Nb) & (eb[None, :] < self.Nb)
        kp = np.zeros_like(m)
        ii, jj = np.nonzero(bb)
        kp[ii, jj] = self.knownpos[ea[ii], eb[jj]]
        m |= kp
        np.fill_diagonal(m, False)
        return m


# ============================================================================================ model
def make_model(cfg, d_in):
    import torch.nn as nn
    layers = []
    if cfg.get("hidden"):
        layers += [nn.Linear(d_in, cfg["hidden"]), nn.LayerNorm(cfg["hidden"]), nn.GELU(),
                   nn.Dropout(cfg["dropout"]), nn.Linear(cfg["hidden"], cfg["out_dim"])]
    else:
        layers += [nn.Dropout(cfg["dropout"]), nn.Linear(d_in, cfg["out_dim"])]
    return nn.Sequential(*layers)


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


def es_metric(model, data: Data, device):
    """Mean of L-mode and D-mode ROC-AUC on the ES pairs (cosine of the head outputs)."""
    import torch
    import torch.nn.functional as F
    model.eval()
    with torch.no_grad():
        Z = F.normalize(model(torch.from_numpy(data.X[:2 * data.Nb]).to(device)), dim=1).cpu().numpy()
    model.train()
    a, b, y = data.es_pairs
    out = {}
    sL = (Z[a] * Z[b]).sum(1)
    out["auc_L"] = ev.roc_auc(y.astype(bool), sL)
    m = data.dmatch[a] & data.dmatch[b]
    sD = (Z[data.Nb + a[m]] * Z[data.Nb + b[m]]).sum(1)
    out["auc_D"] = ev.roc_auc(y[m].astype(bool), sD)
    out["es"] = 0.5 * (out["auc_L"] + out["auc_D"])
    return out


def train_seed(cfg, data: Data, seed: int, device: str, log):
    import torch
    import torch.nn.functional as F
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = make_model(cfg, data.X.shape[1]).to(device)
    scale = torch.nn.Parameter(torch.tensor(10.0, device=device))
    bias = torch.nn.Parameter(torch.tensor(-5.0, device=device))
    opt = torch.optim.AdamW(list(model.parameters()) + [scale, bias], lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    X = torch.from_numpy(data.X).to(device)
    w_src = [cfg["w_blips_pos"], cfg["w_ld"], cfg["w_ppips"]]
    best, best_state, best_ep, bad, hist = -np.inf, None, -1, 0, []
    t0 = time.time()
    for ep in range(cfg["max_epochs"]):
        tot = {"nce": 0.0, "bce": 0.0}
        for _ in range(cfg["steps_per_epoch"]):
            ia, ib, ea, eb = data.sample_pos(rng, cfg["batch_pos"], w_src, cfg["p_d"])
            za = F.normalize(model(X[torch.from_numpy(ia).to(device)]), dim=1)
            zb = F.normalize(model(X[torch.from_numpy(ib).to(device)]), dim=1)
            logits = za @ zb.T / cfg["tau"]
            mask = torch.from_numpy(data.neg_mask(ea, eb)).to(device)
            logits = logits.masked_fill(mask, float("-inf"))
            tgt = torch.arange(len(ia), device=device)
            loss_nce = 0.5 * (F.cross_entropy(logits, tgt) + F.cross_entropy(logits.T, tgt))
            loss = loss_nce
            if cfg["lambda_bce"] > 0:
                la, lb, ly, ltc = data.sample_lab(rng, cfg["batch_lab"], cfg["p_d"])
                ca = F.normalize(model(X[torch.from_numpy(la).to(device)]), dim=1)
                cb = F.normalize(model(X[torch.from_numpy(lb).to(device)]), dim=1)
                lg = scale * (ca * cb).sum(1) + bias
                t = torch.from_numpy(ltc if cfg["graded"] else ly.astype(np.float32)).to(device)
                loss_bce = F.binary_cross_entropy_with_logits(lg, t)
                loss = loss + cfg["lambda_bce"] * loss_bce
                tot["bce"] += float(loss_bce)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot["nce"] += float(loss_nce)
        m = es_metric(model, data, device)
        hist.append({"epoch": ep, **{k: v / cfg["steps_per_epoch"] for k, v in tot.items()}, **m})
        if m["es"] > best + 1e-6:
            best, best_ep, bad = m["es"], ep, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg["patience"]:
                break
    model.load_state_dict(best_state)
    model.eval()
    log(f"  seed {seed}: best epoch {best_ep} ES {best:.4f} (L {hist[best_ep]['auc_L']:.4f} D "
        f"{hist[best_ep]['auc_D']:.4f}); {len(hist)} epochs, {time.time() - t0:.0f} s")
    return export_params(model), {"seed": seed, "best_epoch": best_ep, "best_es": best, "epochs_run": len(hist),
                                  "history": hist, "wall_s": time.time() - t0}


def run_config(name, device, synthetic=False, out_root=OUT, max_epochs=None):
    grid, _ = load_grid()
    cfg = grid[name]
    if max_epochs is not None:
        cfg["max_epochs"] = max_epochs
    t0 = time.time()

    def log(msg):
        print(f"[{name} {time.time() - t0:6.0f}s] {msg}", flush=True)

    data = Data(cfg["input"], synthetic=synthetic)
    log(f"input {cfg['input']} d={data.X.shape[1]}; {data.n}")
    out = Path(out_root) / name
    out.mkdir(parents=True, exist_ok=True)
    seeds = list(SEEDS[:3])
    logs, files = [], {}
    for s in seeds:
        params, info = train_seed(cfg, data, s, device, log)
        f = out / f"seed{s}.npz"
        np.savez(f, **params)
        files[f.name] = sha256_file(f)
        logs.append(info)
    (out / "input_stats.json").write_text(json.dumps(data.scaler.to_dict()))
    files["input_stats.json"] = sha256_file(out / "input_stats.json")
    (out / "train_log.json").write_text(json.dumps(logs))
    git = git_state()
    conf = {**cfg, "seeds": seeds, "d_in": int(data.X.shape[1]), "synthetic": synthetic, "data_counts": data.n,
            "files_sha256": files, "grid_sha256": sha256_file(GRID), "script_sha256": sha256_file(__file__),
            "a4b_module_sha256": sha256_file(ROOT / "src/pocketcompare/a4b.py"), "git_commit": git["git_commit"],
            "git_dirty": git["git_dirty"], "device": device, "torch": __import__("torch").__version__,
            "best_epochs": [lg["best_epoch"] for lg in logs], "best_es": [lg["best_es"] for lg in logs],
            "wall_s": time.time() - t0}
    (out / "config.json").write_text(json.dumps(conf, indent=1, default=str))
    log(f"saved {out}")
    return conf


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--devices", default="cuda:0,cuda:1")
    ap.add_argument("--synthetic", action="store_true", help="random inputs (code smoke test; no real fit)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--max-epochs", type=int, default=None, help="override (smoke tests only)")
    a = ap.parse_args()
    if not a.synthetic and os.environ.get("A4B_AUDIT_PASSED") != "1":
        raise SystemExit("refusing to fit on real data: set A4B_AUDIT_PASSED=1 only after the PI's go (split audit)")
    if a.all:
        grid, _ = load_grid()
        devs = a.devices.split(",")
        names = list(grid)
        procs = []
        for k, dev in enumerate(devs):
            mine = names[k::len(devs)]
            cmd = [sys.executable, __file__, "--device", dev, "--out", a.out] + (["--synthetic"] if a.synthetic else [])
            procs.append(subprocess.Popen([*cmd, "--config", ",".join(mine)]))
        rc = [p.wait() for p in procs]
        if any(rc):
            raise SystemExit(f"worker failure: {rc}")
        return
    for name in a.config.split(","):
        run_config(name, a.device, synthetic=a.synthetic, out_root=a.out, max_epochs=a.max_epochs)


if __name__ == "__main__":
    main()
