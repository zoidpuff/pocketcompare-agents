#!/usr/bin/env python
"""L4 — point-cloud pocket encoder (PREREG Addendum A1; configs/a4_grid.yaml; pocketcompare.l4).

    python scripts/train_l4.py --config egnn_base --device cuda:2          # 3 seeds (SEEDS[:3]) of one grid entry
    python scripts/train_l4.py --all --devices cuda:2,cuda:3                # whole grid, one process per device
    python scripts/train_l4.py --synthetic --config egnn_base --device cuda:2 --max-epochs 2   # smoke test
    python scripts/train_l4.py --embed egnn_base --device cuda:2            # (re)write eval embeddings only

Data rules = scripts/train_a4b.py (its ``Data`` class is reused unchanged, input N1): BLiPS-train v2 labelled pairs,
L<->D same-site positives (D-matched train sites), PPIPS-train P-sym + P-ortho positives; never TOUGH-M1,
BLiPS-val, PPIPS-val or any test set.  Same ES hold-out (10 % of BLiPS-train homology groups, rng(SEEDS[0])),
same in-batch-negative masking, same InfoNCE + lambda * BCE loss, same L/D endpoint sampling.  Items = BLiPS-train
L point sets, BLiPS-train U point sets, PPIPS-train D point sets (data/processed/l4, scripts/l4_extract.py), in
the order of ``Data``.  Point features z-scored with BLiPS-train (L + U) point statistics (label-free).
Augmentation: uniform random rotation and point dropout per pocket (training only).  Model selection inside a
seed: best ES epoch (mean of L / D ROC-AUC on the ES pairs).  ``--synthetic``: random point clouds + permuted
labels (code test; nothing real is learnt).

Outputs: results/models/l4/<config>/{seed<k>.pt, point_scaler.json, n1_stats.json, config.json (sha256 of every
file), train_log.json, emb_<dataset>_<loc>.npy (ensemble embeddings for blips / tough_m1 / ppips eval)}.
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
sys.path.insert(0, str(ROOT / "scripts"))

from pocketcompare import a4b as A4  # noqa: E402
from pocketcompare import evaluate as ev  # noqa: E402
from pocketcompare import l4 as L4  # noqa: E402
from pocketcompare.provenance import git_state, sha256_file  # noqa: E402
from pocketcompare.seeds import SEEDS  # noqa: E402

GRID = ROOT / "configs/a4_grid.yaml"
OUT = ROOT / "results/models/l4"
PTS = ROOT / "data/processed/l4"
EVAL_SETS = (("blips", "L"), ("blips", "U"), ("tough_m1", "L"), ("tough_m1", "U"), ("ppips", "D"))


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


# ============================================================================================ point tensors
_STORES: dict = {}


def store(dataset, loc):
    k = (dataset, loc)
    if k not in _STORES:
        _STORES[k] = (L4.PointStore(PTS / dataset / f"{loc}.npz"), pd.read_parquet(PTS / dataset / "ids.parquet"))
    return _STORES[k]


def point_scaler() -> L4.PointScaler:
    """z-statistics of the analytic point features: BLiPS-train v2 sites, L + U point sets pooled (label-free)."""
    names = json.loads((PTS / "blips" / "layout.json").read_text())["feature_names"]
    tr = set(A4.blips_train_ids())
    F = []
    for loc in ("L", "U"):
        st, ids = store("blips", loc)
        for i in np.flatnonzero(ids.pocket_id.isin(tr).to_numpy() & ids[f"has_{loc}"].to_numpy()):
            F.append(st.get(i)[1])
    return L4.PointScaler.fit(names, np.concatenate(F).astype(np.float32))


def gather(dataset, loc, pocket_ids, scaler, synthetic=False, rng=None):
    """Padded (n, CAP, 3) xyz, (n, CAP, F) features, (n, CAP) mask (numpy) + availability of ``pocket_ids``."""
    st, ids = store(dataset, loc)
    row = pd.Series(np.arange(len(ids)), index=ids.pocket_id).reindex(list(pocket_ids)).to_numpy()
    n = len(row)
    d_point = len(scaler.names) + L4.N_TYPES + 1
    X = np.zeros((n, L4.CAP, 3), np.float32)
    H = np.zeros((n, L4.CAP, d_point), np.float16)
    M = np.zeros((n, L4.CAP), np.float32)
    av = np.zeros(n, bool)
    for i, r in enumerate(row):
        if not np.isfinite(r) or st.size(int(r)) == 0:
            M[i, 0] = 1.0                                  # placeholder single point (never scored)
            continue
        p, f, t, v = st.get(int(r))
        if synthetic:                                       # random clouds: nothing real can be learnt
            m = int(rng.integers(20, L4.CAP + 1))
            p = rng.normal(scale=4.0, size=(m, 3)).astype(np.float32)
            f = rng.normal(size=(m, f.shape[1])).astype(np.float32)
            t = rng.random((m, t.shape[1])).astype(np.float32)
            v = rng.choice([1.0, 27.0], size=m).astype(np.float32)
            h = np.concatenate([f, t, np.log(v)[:, None]], 1)
        else:
            h = L4.point_input(scaler(np.asarray(f, np.float32)), np.asarray(t, np.float32), v)
        m = len(p)
        X[i, :m], H[i, :m], M[i, :m] = p, h, 1.0
        av[i] = True
    return X, H, M, av


# ============================================================================================ training
def augment(x, mask, cfg, gen):
    import torch
    if cfg["rotate"]:
        R = L4.random_rotations(x.shape[0], generator=gen, device=x.device)
        x = torch.bmm(x, R)
    if cfg["point_dropout"] > 0:
        keep = (torch.rand(mask.shape, generator=gen, device=x.device) >= cfg["point_dropout"]).float() * mask
        enough = keep.sum(1) >= torch.clamp(mask.sum(1), max=8)
        mask = torch.where(enough[:, None], keep, mask)
    return x, mask


def embed_items(model, T, items, device, cfg, bs=256, train=False, gen=None):
    import torch
    out = []
    for s in range(0, len(items), bs):
        ii = torch.as_tensor(items[s:s + bs], device=device)
        x, h, m = T["X"][ii], T["H"][ii].float(), T["M"][ii]
        if train:
            x, m = augment(x, m, cfg, gen)
        n1 = T["N1"][ii] if T.get("N1") is not None else None
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=x.is_cuda):
            z = model(x, h, m, n1=n1)
        out.append(z.float())
    return torch.cat(out)


def es_metric(model, data, T, device, cfg):
    import torch
    model.eval()
    with torch.no_grad():
        Z = torch.nn.functional.normalize(embed_items(model, T, np.arange(2 * data.Nb), device, cfg), dim=1)
        Z = Z.cpu().numpy()
    model.train()
    a, b, y = data.es_pairs
    out = {"auc_L": ev.roc_auc(y.astype(bool), (Z[a] * Z[b]).sum(1))}
    m = data.dmatch[a] & data.dmatch[b]
    out["auc_D"] = ev.roc_auc(y[m].astype(bool), (Z[data.Nb + a[m]] * Z[data.Nb + b[m]]).sum(1))
    out["es"] = 0.5 * (out["auc_L"] + out["auc_D"])
    return out


def train_seed(cfg, data, T, seed, device, log):
    import torch
    import torch.nn.functional as F
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    gen = torch.Generator(device=device)
    gen.manual_seed(seed)
    model = L4.build_model(cfg, T["H"].shape[-1], T["N1"].shape[1] if T.get("N1") is not None else 0).to(device)
    scale = torch.nn.Parameter(torch.tensor(10.0, device=device))
    bias = torch.nn.Parameter(torch.tensor(-5.0, device=device))
    opt = torch.optim.AdamW(list(model.parameters()) + [scale, bias], lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    w_src = [cfg["w_blips_pos"], cfg["w_ld"], cfg["w_ppips"]]
    best, best_state, best_ep, bad, hist = -np.inf, None, -1, 0, []
    t0 = time.time()
    for ep in range(cfg["max_epochs"]):
        tot = {"nce": 0.0, "bce": 0.0}
        for _ in range(cfg["steps_per_epoch"]):
            ia, ib, ea, eb = data.sample_pos(rng, cfg["batch_pos"], w_src, cfg["p_d"])
            items = [ia, ib]
            if cfg["lambda_bce"] > 0:
                la, lb, ly, ltc = data.sample_lab(rng, cfg["batch_lab"], cfg["p_d"])
                items += [la, lb]
            Z = embed_items(model, T, np.concatenate(items), device, cfg, bs=10 ** 9, train=True, gen=gen)
            B = len(ia)
            za, zb = Z[:B], Z[B:2 * B]
            logits = za @ zb.T / cfg["tau"]
            mask = torch.from_numpy(data.neg_mask(ea, eb)).to(device)
            logits = logits.masked_fill(mask, float("-inf"))
            tgt = torch.arange(B, device=device)
            loss_nce = 0.5 * (F.cross_entropy(logits, tgt) + F.cross_entropy(logits.T, tgt))
            loss = loss_nce
            if cfg["lambda_bce"] > 0:
                Bl = len(la)
                ca, cb = Z[2 * B:2 * B + Bl], Z[2 * B + Bl:]
                lg = scale * (ca * cb).sum(1) + bias
                t = torch.from_numpy(ltc if cfg["graded"] else ly.astype(np.float32)).to(device)
                loss_bce = F.binary_cross_entropy_with_logits(lg, t)
                loss = loss + cfg["lambda_bce"] * loss_bce
                tot["bce"] += float(loss_bce)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tot["nce"] += float(loss_nce)
        m = es_metric(model, data, T, device, cfg)
        hist.append({"epoch": ep, **{k: v / cfg["steps_per_epoch"] for k, v in tot.items()}, **m,
                     "t_s": time.time() - t0})
        log(f"  seed {seed} ep {ep}: nce {hist[-1]['nce']:.3f} bce {hist[-1]['bce']:.3f} ES {m['es']:.4f} "
            f"(L {m['auc_L']:.3f} D {m['auc_D']:.3f}) {time.time() - t0:.0f}s")
        if m["es"] > best + 1e-6:
            best, best_ep, bad = m["es"], ep, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg["patience"]:
                break
    model.load_state_dict(best_state)
    model.eval()
    mem = torch.cuda.max_memory_allocated(device) / 2 ** 30 if str(device).startswith("cuda") else 0.0
    log(f"  seed {seed}: best epoch {best_ep} ES {best:.4f}; {len(hist)} epochs, {time.time() - t0:.0f} s, "
        f"peak GPU mem {mem:.1f} GiB")
    return model, {"seed": seed, "best_epoch": best_ep, "best_es": best, "epochs_run": len(hist), "history": hist,
                   "wall_s": time.time() - t0, "peak_gpu_gib": mem}


def build_training(cfg, synthetic, device, log):
    import torch
    import train_a4b
    data = train_a4b.Data("N1", synthetic=synthetic)
    sc = point_scaler()
    rng = np.random.default_rng(SEEDS[0])
    pk = pd.read_parquet(ROOT / "data/processed/ppi/ppips/pockets.parquet")
    ppt = pk[pk.split == "train"].reset_index(drop=True).pocket_id.tolist()
    if len(ppt) != data.Np:
        raise RuntimeError("PPIPS-train pocket order differs from train_a4b.Data")
    parts = [gather("blips", "L", data.site_ids, sc, synthetic, rng),
             gather("blips", "U", data.site_ids, sc, synthetic, rng),
             gather("ppips", "D", ppt, sc, synthetic, rng)]
    X, H, M = (np.concatenate([p[k] for p in parts]) for k in range(3))
    av = np.concatenate([p[3] for p in parts])
    T = {"X": torch.from_numpy(X).to(device), "H": torch.from_numpy(H).to(device), "M": torch.from_numpy(M).to(device),
         "N1": torch.from_numpy(np.nan_to_num(data.X)).to(device) if cfg["concat_n1"] else None}
    n_pts = M.sum(1)
    data.n.update(items=len(X), items_without_points=int((~av).sum()), pts_median=float(np.median(n_pts[av])))
    log(f"items {len(X)} (no points: {(~av).sum()}), point dim {H.shape[-1]}; {data.n}")
    return data, T, sc


# ============================================================================================ inference
def load_models(model_dir, device="cpu"):
    import torch
    model_dir = Path(model_dir)
    cfg = json.loads((model_dir / "config.json").read_text())
    sc = L4.PointScaler.from_dict(json.loads((model_dir / "point_scaler.json").read_text()))
    n1s = A4.PartScaler.from_dict(json.loads((model_dir / "n1_stats.json").read_text())) if cfg["concat_n1"] else None
    models = []
    for s in cfg["seeds"]:
        m = L4.build_model(cfg, cfg["d_point"], cfg.get("d_n1", 0))
        m.load_state_dict(torch.load(model_dir / f"seed{s}.pt", map_location=device, weights_only=True))
        models.append(m.to(device).eval())
    return models, cfg, sc, n1s


def ensemble_embed(models, cfg, sc, n1s, dataset, loc, pocket_ids, device, bs=256):
    """(n, out_dim * n_seeds) / sqrt(n_seeds) float32 (inner product = mean seed cosine); unavailable rows = 0."""
    import torch
    X, H, M, av = gather(dataset, loc, pocket_ids, sc)
    N1 = None
    if n1s is not None:
        mode = "L" if loc == "L" else "D"
        N1 = np.nan_to_num(A4.head_input(A4.raw_parts(dataset, mode, pocket_ids, "N1"), n1s))
    T = {"X": torch.from_numpy(X).to(device), "H": torch.from_numpy(H).to(device), "M": torch.from_numpy(M).to(device),
         "N1": torch.from_numpy(N1).to(device) if N1 is not None else None}
    with torch.no_grad():
        E = torch.cat([embed_items(m, T, np.arange(len(X)), device, cfg, bs=bs) for m in models], 1)
    E = (E / np.sqrt(len(models))).cpu().numpy().astype(np.float32)
    E[~av] = 0.0
    return E, av


def write_embeddings(model_dir, device):
    models, cfg, sc, n1s = load_models(model_dir, device)
    files = {}
    for dataset, loc in EVAL_SETS:
        ids = A4.ids_table(dataset).pocket_id.tolist()
        E, av = ensemble_embed(models, cfg, sc, n1s, dataset, loc, ids, device)
        f = Path(model_dir) / f"emb_{dataset}_{loc}.npy"
        np.save(f, E)
        files[f.name] = sha256_file(f)
    return files


# ============================================================================================ driver
def run_config(name, device, synthetic=False, out_root=OUT, max_epochs=None, steps=None):
    import torch
    grid, _ = load_grid()
    cfg = grid[name]
    if max_epochs is not None:
        cfg["max_epochs"] = max_epochs
    if steps is not None:
        cfg["steps_per_epoch"] = steps
    t0 = time.time()

    def log(msg):
        print(f"[{name} {time.time() - t0:6.0f}s] {msg}", flush=True)

    data, T, sc = build_training(cfg, synthetic, device, log)
    out = Path(out_root) / name
    out.mkdir(parents=True, exist_ok=True)
    seeds = list(SEEDS[:3])
    logs, files = [], {}
    (out / "point_scaler.json").write_text(json.dumps(sc.to_dict()))
    (out / "n1_stats.json").write_text(json.dumps(data.scaler.to_dict()))
    for s in seeds:
        model, info = train_seed(cfg, data, T, s, device, log)
        f = out / f"seed{s}.pt"
        torch.save(model.state_dict(), f)
        files[f.name] = sha256_file(f)
        logs.append(info)
    for f in ("point_scaler.json", "n1_stats.json"):
        files[f] = sha256_file(out / f)
    (out / "train_log.json").write_text(json.dumps(logs))
    git = git_state()
    conf = {**cfg, "seeds": seeds, "d_point": int(T["H"].shape[-1]),
            "d_n1": int(T["N1"].shape[1]) if T.get("N1") is not None else 0, "synthetic": synthetic,
            "data_counts": data.n, "files_sha256": files, "grid_sha256": sha256_file(GRID),
            "script_sha256": sha256_file(__file__), "l4_module_sha256": sha256_file(ROOT / "src/pocketcompare/l4.py"),
            "points_sha256": {f"{d}/{l}": sha256_file(PTS / d / f"{l}.npz") for d, l in
                              (("blips", "L"), ("blips", "U"), ("ppips", "D"))},
            "git_commit": git["git_commit"], "git_dirty": git["git_dirty"], "device": device,
            "torch": torch.__version__, "best_epochs": [lg["best_epoch"] for lg in logs],
            "best_es": [lg["best_es"] for lg in logs], "wall_s_train": time.time() - t0}
    (out / "config.json").write_text(json.dumps(conf, indent=1, default=str))
    del T
    torch.cuda.empty_cache()
    t1 = time.time()
    conf["embeddings_sha256"] = write_embeddings(out, device)
    conf["wall_s_embed"] = time.time() - t1
    (out / "config.json").write_text(json.dumps(conf, indent=1, default=str))
    log(f"saved {out}")
    return conf


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--device", default="cuda:2")
    ap.add_argument("--devices", default="cuda:2,cuda:3")
    ap.add_argument("--synthetic", action="store_true", help="random point clouds + permuted labels (smoke test)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--max-epochs", type=int, default=None, help="override (smoke tests only)")
    ap.add_argument("--steps", type=int, default=None, help="override steps/epoch (smoke tests only)")
    ap.add_argument("--embed", default=None, help="only (re)write eval embeddings of these configs")
    a = ap.parse_args()
    if a.embed:
        for name in a.embed.split(","):
            write_embeddings(Path(a.out) / name, a.device)
        return
    if not a.synthetic and os.environ.get("L4_AUDIT_PASSED") != "1":
        raise SystemExit("refusing to fit on real data: set L4_AUDIT_PASSED=1 only after the PI's go (split audit)")
    if a.all:
        grid, _ = load_grid()
        devs = a.devices.split(",")
        names = list(grid)
        procs = []
        for k, dev in enumerate(devs):
            mine = names[k::len(devs)]
            cmd = [sys.executable, __file__, "--device", dev, "--out", a.out] + (["--synthetic"] if a.synthetic else [])
            if a.max_epochs:
                cmd += ["--max-epochs", str(a.max_epochs)]
            procs.append(subprocess.Popen([*cmd, "--config", ",".join(mine)]))
        rc = [p.wait() for p in procs]
        if any(rc):
            raise SystemExit(f"worker failure: {rc}")
        return
    for name in a.config.split(","):
        run_config(name, a.device, synthetic=a.synthetic, out_root=a.out, max_epochs=a.max_epochs, steps=a.steps)


if __name__ == "__main__":
    main()
