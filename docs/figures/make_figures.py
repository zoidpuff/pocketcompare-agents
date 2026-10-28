#!/usr/bin/env python
"""Generate the research-briefing figures for pocketcompare.

Usage:
    python make_figures.py /path/to/pocket_compare [--out DIR] [--only fig1,fig4]

Every plotted number is read from a committed result file of the research repository
(passed as the first argument). The source file of each value is recorded in a
"# src:" comment next to where it is read. Nothing under data/sealed/ is opened.
Output: <name>.png (200 dpi) and <name>.svg in --out (default: this script's folder).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle, Wedge  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

# ----------------------------------------------------------------------------------------------
# Palette (dataviz reference palette, light mode; categorical slots validated with
# validate_palette.js: slots 1-4 pass all checks; aqua/yellow need visible labels -> all marks
# that use them are directly labelled).
# ----------------------------------------------------------------------------------------------
C = dict(
    surface="#fcfcfb",
    ink="#0b0b0b",
    ink2="#52514e",
    muted="#898781",
    grid="#e1e0d9",
    axis="#c3c2b7",
    blue="#2a78d6",  # slot 1: FINAL / detected-pocket (D) / ligand-free
    orange="#eb6834",  # slot 2: ligand-defined (L) / size-driven
    aqua="#1baf7a",  # slot 3
    yellow="#eda100",  # slot 4
    magenta="#e87ba4",  # slot 5
    green="#008300",  # slot 6
    violet="#6250d6",  # slot 7
    red="#e34948",  # slot 8
    neutral="#6f6e69",  # de-emphasised series
    blue_wash="#e6f0fb",
    orange_wash="#fdede6",
    aqua_wash="#e3f5ee",
    gray_wash="#f0efec",
    sealed="#b54a1f",
)

FONT = "DejaVu Sans"


def setup_style():
    plt.rcParams.update({
        "font.family": FONT,
        "font.size": 10.5,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 10,
        "axes.labelsize": 10.5,
        "axes.labelcolor": C["ink2"],
        "axes.edgecolor": C["axis"],
        "axes.linewidth": 0.8,
        "axes.facecolor": C["surface"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": C["ink2"],
        "ytick.color": C["ink2"],
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 10,
        "text.color": C["ink"],
        "figure.facecolor": C["surface"],
        "savefig.facecolor": C["surface"],
        "grid.color": C["grid"],
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "svg.fonttype": "none",
        "lines.solid_capstyle": "round",
    })


def save(fig, out: Path, name: str):
    out.mkdir(parents=True, exist_ok=True)
    for ext, kw in (("png", dict(dpi=200)), ("svg", {})):
        fig.savefig(out / f"{name}.{ext}", bbox_inches="tight", pad_inches=0.2, **kw)
    plt.close(fig)
    print(f"wrote {name}.png / .svg")


def suptitle(fig, title, subtitle=None, y=0.995):
    fig.text(0.01, y, title, ha="left", va="top", fontsize=15, fontweight="bold", color=C["ink"])
    if subtitle:
        fig.text(0.01, y - 0.045, subtitle, ha="left", va="top", fontsize=10.5, color=C["ink2"])


def xgrid(ax):
    ax.grid(axis="x", zorder=0)
    ax.set_axisbelow(True)


def fmt(x, nd=3, sign=False):
    s = f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"
    return s.replace("-", "\u2212")


def load_json(p: Path):
    with open(p) as fh:
        return json.load(fh)


def draw_lock(ax, x, y, h_in=0.2, color=C["sealed"], transform=None):
    """Padlock glyph centred at (x, y) (data coords, or `transform`), drawn in its own tiny equal-aspect axes
    so it is never distorted; h_in = height in inches."""
    fig = ax.figure
    tr = transform if transform is not None else ax.transData
    fx, fy = fig.transFigure.inverted().transform(tr.transform((x, y)))
    W, H = fig.get_size_inches()
    w_in = h_in * 0.8
    la = fig.add_axes([fx - w_in / W / 2, fy - h_in / H / 2, w_in / W, h_in / H])
    la.set_xlim(0, 0.8)
    la.set_ylim(0, 1)
    la.axis("off")
    la.patch.set_alpha(0)
    la.add_patch(FancyBboxPatch((0.04, 0.02), 0.72, 0.52, boxstyle="round,pad=0,rounding_size=0.08", fc=color,
                                ec="none"))
    la.add_patch(Wedge((0.4, 0.56), 0.27, 0, 180, width=0.09, fc=color, ec="none"))
    la.add_patch(Rectangle((0.13, 0.50), 0.09, 0.08, fc=color, ec="none"))
    la.add_patch(Rectangle((0.58, 0.50), 0.09, 0.08, fc=color, ec="none"))
    la.add_patch(Circle((0.4, 0.28), 0.07, fc=C["surface"], ec="none"))
    return la


# ----------------------------------------------------------------------------------------------
# Data access helpers
# ----------------------------------------------------------------------------------------------
class Repo:
    def __init__(self, root: Path):
        self.root = Path(root)
        assert (self.root / "REPORT.md").exists(), f"not the research repo: {root}"

    def p(self, rel: str) -> Path:
        assert not rel.startswith("data/sealed"), "never open data/sealed/"
        return self.root / rel

    def json(self, rel):
        return load_json(self.p(rel))

    def parquet(self, rel):
        return pd.read_parquet(self.p(rel))

    def text(self, rel):
        return self.p(rel).read_text()


def summary_row(df, **kw):
    m = np.ones(len(df), bool)
    for k, v in kw.items():
        m &= (df[k] == v).to_numpy()
    sub = df[m]
    assert len(sub) == 1, (kw, len(sub))
    return sub.iloc[0]


# ==============================================================================================
# Figure 1: pipeline schematic
# ==============================================================================================
def fig1_pipeline(R: Repo, out: Path):
    import yaml

    cfg = yaml.safe_load(R.text("configs/final_method.yaml"))  # src: configs/final_method.yaml
    rt = R.json("results/dev/final_method_runtime.json")  # src: results/dev/final_method_runtime.json
    drt = R.json("results/tooling/describe_runtime.json")  # src: results/tooling/describe_runtime.json
    sph = cfg["site"]["shaper_sph8"]
    radius, bur_min = sph["radius_A"], sph["bur_min"]
    l_cut = cfg["site"]["L_cutoff_A"]
    d_in, out_dim, n_seeds, dims = cfg["a4b"]["d_in"], cfg["a4b"]["out_dim"], len(cfg["a4b"]["seeds"]), cfg["dims"]
    env_dims = cfg["env"]["dims"]
    a1_dims = d_in - env_dims
    # A1 block sizes; src: reports/a1_descriptors.md "Blocks" (hist 27, pair 392, usr 84, glob 10, size 1)
    a1_blocks = dict(hist=27, pair=392, usr=84, glob=10, size=1)
    assert sum(a1_blocks.values()) == a1_dims, (a1_blocks, a1_dims)
    assert n_seeds * out_dim == dims
    burrow_gpu = drt["runs"]["latency_gpu_inprocess"]["per_structure_total_s"]["median"]
    burrow_ref = drt["runs"]["latency_ref_cpu1"]["per_structure_total_s"]["median"]
    desc_ms = rt["D_ms_per_pocket_median"]
    head_us = rt["embed_us_per_pocket"]
    pair_us = rt["pair_us_batched_1M"]

    fig = plt.figure(figsize=(16, 8.2))
    ax = fig.add_axes([0, 0, 1, 0.885])
    ax.set_xlim(0, 160)
    ax.set_ylim(0, 79)
    ax.axis("off")
    suptitle(fig, "How pocketcompare turns a protein pocket into a 384-number fingerprint",
             "No sequence, fold or ligand information enters the fingerprint; similarity is a single dot product.",
             y=0.985)

    def box(x, y, w, h, title, lines, fc=C["gray_wash"], ec=C["axis"], step=None, tcolor=C["ink"]):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6", fc=fc, ec=ec, lw=1.0))
        if step is not None:
            ax.add_patch(Circle((x + 2.6, y + h - 2.8), 1.75, fc=C["ink2"], ec="none"))
            ax.text(x + 2.6, y + h - 2.85, str(step), ha="center", va="center", fontsize=9.5, color="white",
                    fontweight="bold")
        ax.text(x + 5.2, y + h - 2.8, title, ha="left", va="center", fontsize=11.5, fontweight="bold", color=tcolor)
        for i, (ln, col) in enumerate(lines):
            ax.text(x + 1.8, y + h - 7.2 - i * 3.1, ln, ha="left", va="center", fontsize=9.6, color=col)

    def arrow(x0, y0, x1, y1, conn="arc3", color=C["ink2"]):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=16, lw=1.6, color=color,
                                     connectionstyle=conn, shrinkA=0, shrinkB=0))

    rng = np.random.default_rng(3)
    # ---------- row 1 -------------------------------------------------------------------
    y1, h1 = 47, 31
    # 1 structure
    box(2, y1, 31, h1, "Protein structure", [("PDB entry, AlphaFold model", C["ink2"]), ("or predicted dimer", C["ink2"])],
        step=1)
    t = np.linspace(0, 1, 300)
    xs = 6 + 23 * t
    ys = y1 + 9 + 3.2 * np.sin(t * 6 * np.pi) * np.exp(-((t - 0.5) ** 2) / 0.5)
    ax.plot(xs, ys, color=C["neutral"], lw=4.5, solid_capstyle="round")
    ax.plot(xs, ys, color="#bdbcb5", lw=2.0, solid_capstyle="round")
    arrow(33.5, y1 + h1 / 2, 37.5, y1 + h1 / 2)

    # 2 BURROW grid
    box(38, y1, 37, h1, "BURROW grid points",
        [("1 \u00c5 grid in and around the protein;", C["ink2"]),
         ("each point carries buriedness and", C["ink2"]),
         ("chemistry features. Ligands, waters", C["ink2"]),
         ("and ions are stripped first.", C["ink2"])], step=2)
    gx, gy = np.meshgrid(np.arange(0, 11), np.arange(0, 3))
    gxx = 42 + gx.ravel() * 2.6
    gyy = y1 + 5.6 + gy.ravel() * 2.0
    core = (np.abs(gx.ravel() - 5) <= 2) & (gy.ravel() >= 1)
    ax.scatter(gxx[~core], gyy[~core], s=10, color="#bdbcb5", zorder=3, lw=0)
    ax.scatter(gxx[core], gyy[core], s=16, color=C["ink2"], zorder=3, lw=0)
    ax.text(56.5, y1 + 2.0, f"{burrow_gpu:.2f}\u2013{burrow_ref:.2f} s per structure, end to end (GPU / 1 core)",
            ha="center", va="center", fontsize=8.6, color=C["muted"])
    arrow(75.5, y1 + h1 / 2, 79.5, y1 + h1 / 2)

    # 3 site
    box(80, y1, 37, h1, "Locate the site",
        [("Deployment: a pocket BURROW detects", C["ink2"]),
         ("(no ligand needed).", C["ink2"]),
         ("Benchmarks: the detected pocket that", C["ink2"]),
         ("covers a known ligand (\u201cD-mode\u201d).", C["ink2"])], step=3)
    # icon: cavity with detected pocket dots
    cav = np.array([[84, y1 + 3], [96, y1 + 3], [96, y1 + 9.5], [92.5, y1 + 9.5], [92.5, y1 + 6], [87.5, y1 + 6],
                    [87.5, y1 + 9.5], [84, y1 + 9.5]])
    ax.add_patch(Polygon(cav, closed=True, fc="#d6d5ce", ec="none"))
    for xx in np.arange(88.4, 92.0, 1.1):
        for yy in np.arange(y1 + 6.8, y1 + 9.6, 1.1):
            ax.add_patch(Circle((xx, yy), 0.33, fc=C["blue"], ec="none"))
    ax.text(97.5, y1 + 6.3, "detected pocket", fontsize=8.8, color=C["ink2"], va="center")
    arrow(117.5, y1 + h1 / 2, 121.5, y1 + h1 / 2)

    # 4 sph8
    box(122, y1, 36, h1, "Redraw a standard site (\u201csph8\u201d)",
        [(f"Keep buried points (buriedness \u2265 {bur_min})", C["ink2"]),
         (f"within {radius:.0f} \u00c5 of the buriedness-weighted", C["ink2"]),
         ("centre. The same object results however", C["ink2"]),
         ("the site was found.", C["ink2"])], step=4)
    cx, cy = 140, y1 + 6.5
    ax.add_patch(Circle((cx, cy), 4.6, fc="none", ec=C["blue"], lw=1.4))
    pts = rng.uniform(-4.2, 4.2, size=(40, 2))
    pts = pts[np.hypot(pts[:, 0], pts[:, 1]) < 4.1]
    ax.scatter(cx + pts[:, 0], cy + pts[:, 1] * 0.95, s=9, color=C["blue"], lw=0, zorder=4)
    ax.plot([cx], [cy], marker="*", ms=11, color=C["ink"], zorder=5)
    ax.annotate("", xy=(cx + 4.6, cy), xytext=(cx, cy), arrowprops=dict(arrowstyle="-", color=C["ink2"], lw=1))
    ax.text(cx + 2.3, cy - 0.5, f"{radius:.0f} \u00c5", fontsize=8.5, ha="center", va="top", color=C["ink"],
            bbox=dict(fc=C["gray_wash"], ec="none", pad=0.5), zorder=6)
    ax.text(cx + 6, cy, "buried\ncentre (\u2605)", fontsize=8.5, color=C["ink2"], va="center")

    # connector row1 -> row2 (elbow, right to left)
    ax.add_patch(FancyArrowPatch((140, y1 - 0.5), (19, 41.5), arrowstyle="-|>", mutation_scale=16, lw=1.6,
                                 color=C["ink2"], connectionstyle="angle,angleA=-90,angleB=0,rad=6",
                                 shrinkA=0, shrinkB=0))
    # ---------- row 2 -------------------------------------------------------------------
    y2, h2 = 3, 38
    # 5 cavity fingerprint
    box(2, y2, 48, h2, f"Cavity fingerprint ({a1_dims} numbers)",
        [("Grid points are typed by the nearby protein atoms:", C["ink2"])], step=5, fc=C["blue_wash"],
        ec="#b7d3f6")
    types = [("hydrophobic", C["blue"]), ("aromatic", C["orange"]), ("H-bond donor", C["aqua"]),
             ("H-bond acceptor", C["yellow"]), ("positive", C["magenta"]), ("negative", C["green"])]
    for i, (nm, col) in enumerate(types):
        xx = 4.5 + (i % 3) * 15.0
        yy = y2 + h2 - 11.2 - (i // 3) * 3.0
        ax.add_patch(Circle((xx, yy), 0.75, fc=col, ec="none"))
        ax.text(xx + 1.4, yy, nm, va="center", fontsize=9.2, color=C["ink"])
    blk_lines = [
        f"\u2022 type \u00d7 buriedness histograms ({a1_blocks['hist']})",
        f"\u2022 distance distributions for 28 type pairs ({a1_blocks['pair']})",
        f"\u2022 shape moments ({a1_blocks['usr']}), shape scalars ({a1_blocks['glob']}), volume ({a1_blocks['size']})",
    ]
    for i, ln in enumerate(blk_lines):
        ax.text(3.8, y2 + h2 - 19.2 - i * 3.1, ln, fontsize=9.3, color=C["ink"], va="center")
    # mini histogram + distance curve
    hb = np.array([3, 5, 2, 6, 4, 2, 5, 3])
    for i, v in enumerate(hb):
        ax.add_patch(Rectangle((5 + i * 1.6, y2 + 2.0), 1.1, v * 0.62, fc=C["blue"], ec="none"))
    dd = np.linspace(0, 1, 100)
    ax.plot(22 + dd * 14, y2 + 2.0 + 3.6 * np.exp(-((dd - 0.35) ** 2) / 0.02) + 1.4 * np.exp(-((dd - 0.75) ** 2) / 0.01),
            color=C["blue"], lw=2)
    ax.text(41, y2 + 3.3, "distance\ndistribution", fontsize=8.2, color=C["ink2"], va="center")
    arrow(50.5, y2 + h2 / 2, 53.5, y2 + h2 / 2)

    # plus env
    box(54, y2 + 15, 25, 23, f"+ Environment ({env_dims})",
        [("Chemistry of the lining", C["ink2"]), ("protein atoms and", C["ink2"]),
         ("residue-group composition", C["ink2"])], step=6, fc=C["blue_wash"], ec="#b7d3f6")
    box(54, y2, 25, 13, f"= {d_in} numbers", [("standardised and clipped", C["ink2"])], fc=C["gray_wash"])
    ax.text(66.5, y2 + 1.9, f"{desc_ms:.1f} ms per pocket (median, 1 core)", ha="center", fontsize=8.4,
            color=C["muted"])
    arrow(79.5, y2 + h2 / 2, 83.5, y2 + h2 / 2)

    # 7 projection
    box(84, y2, 34, h2, f"Learned linear projection \u00d7 {n_seeds}",
        [(f"{n_seeds} independently trained {d_in}\u2192{out_dim} maps", C["ink2"]),
         ("(seeds), each output scaled to unit", C["ink2"]),
         ("length, then concatenated.", C["ink2"]),
         ("Trained on ligand-sharing site pairs,", C["ink2"]),
         ("same-site pairs (ligand-located vs", C["ink2"]),
         ("detected) and dimer-interface pairs.", C["ink2"])], step=7)
    for k in range(n_seeds):
        x0 = 89 + k * 9
        ax.add_patch(Rectangle((x0, y2 + 3), 6.5, 6.5, fc="#d6d5ce", ec=C["ink2"], lw=0.8))
        for j in range(4):
            ax.plot([x0 + 0.6, x0 + 5.9], [y2 + 4.2 + j * 1.35] * 2, color=C["ink2"], lw=0.6)
        ax.text(x0 + 3.25, y2 + 10.6, f"seed {k}", ha="center", fontsize=8.2, color=C["ink2"])
    ax.text(101, y2 + 1.4, f"{head_us:.0f} \u00b5s per pocket", ha="center", fontsize=8.4, color=C["muted"])
    arrow(118.5, y2 + h2 / 2, 122.5, y2 + h2 / 2)

    # 8 fingerprint + search
    box(123, y2 + 15, 35, 23, f"{dims}-number fingerprint",
        [(f"unit vector; {rt['bytes_per_pocket_float32']:,} bytes as float32", C["ink2"])], step=8, fc=C["blue_wash"], ec="#b7d3f6")
    vals = rng.normal(size=32)
    for i, v in enumerate(vals):
        a = 0.25 + 0.75 * (abs(v) / np.abs(vals).max())
        ax.add_patch(Rectangle((126 + i * 0.95, y2 + 21), 0.8, 5, fc=C["blue"], alpha=a, ec="none"))
    box(123, y2, 35, 13, "Compare / search",
        [("cosine similarity; FAISS index", C["ink2"]), (f"{pair_us:.1f} \u00b5s per pair (batched)", C["muted"])],
        step=9)
    arrow(140.5, y2 + 15, 140.5, y2 + 13.2)
    save(fig, out, "fig1_pipeline")


# ==============================================================================================
# Figure 2: evaluation data and protection
# ==============================================================================================
def fig2_data(R: Repo, out: Path):
    tc = R.json("data/splits/tough_m1_split_counts.json")  # src: data/splits/tough_m1_split_counts.json
    b2 = R.json("data/splits/blips_split_counts_v2.json")  # src: data/splits/blips_split_counts_v2.json
    b1 = R.json("data/splits/blips_split_counts.json")  # src: data/splits/blips_split_counts.json (test = v1 test)
    pp = R.json("data/splits/ppips_burrow_homology.json")  # src: data/splits/ppips_burrow_homology.json
    fc = R.json("results/final/final_claims.json")  # src: results/final/final_claims.json (C2 pair counts)
    fd = R.json("results/final/final_details.json")  # src: results/final/final_details.json (PPI-L)
    vs = R.json("results/verify/v_spot.json")  # src: results/verify/v_spot.json (Vertex scored protein pairs)
    fps = R.json("results/final_post/final_post_summary.json")  # src: results/final_post/final_post_summary.json
    en = R.json("data/processed/pdbt/enumerate_counts.json")  # src: data/processed/pdbt/enumerate_counts.json
    sc = R.json("data/processed/pdbt/sites_counts.json")  # src: data/processed/pdbt/sites_counts.json
    bc = R.json("results/pdbt/build_counts.json")  # src: results/pdbt/build_counts.json
    pc = R.json("results/pdbt/claims.json")  # src: results/pdbt/claims.json (sites scored after D25 exclusions)

    fig = plt.figure(figsize=(16, 10.6))
    suptitle(fig, "Evaluation data: what each benchmark was used for, and how test data were protected",
             "Test labels were locked away (sealed: unreadable files with recorded checksums) before any method existed "
             "and read once, by the frozen method.", y=0.995)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.25], width_ratios=[1, 1], hspace=0.42, wspace=0.18,
                          left=0.03, right=0.98, top=0.88, bottom=0.03)

    # ---- A: TOUGH-M1 split -------------------------------------------------------------------
    axA = fig.add_subplot(gs[0, 0])
    axA.set_position([0.03, axA.get_position().y0, 0.42, axA.get_position().height])
    n_tot = tc["n_pockets_total"]
    parts = [("Development", tc["dev"]["n_pockets"], C["aqua"],
              "homologous to BURROW's training proteins; used to develop the method"),
             ("Sealed test", tc["test"]["n_pockets"], C["orange"],
              "no homologue in BURROW's training data; opened once"),
             ("Excluded", tc["excluded"]["n_pockets"], "#d6d5ce",
              "homologous to BURROW training AND to another sealed test set")]
    assert sum(p[1] for p in parts) == n_tot
    axA.set_xlim(0, n_tot)
    axA.set_ylim(-4.2, 1.6)
    axA.axis("off")
    axA.set_title("A   TOUGH-M1: leakage control leaves a small, clean test set", pad=4)
    axA.text(0, 1.05, f"All {n_tot:,} TOUGH-M1 pockets", fontsize=10.5, color=C["ink"], va="center")
    left = 0
    for lab, n, col, why in parts:
        axA.barh(0, n, left=left, height=0.9, color=col, edgecolor=C["surface"], linewidth=2)
        axA.text(left + n / 2, 0, f"{n:,}", ha="center", va="center", fontsize=10,
                 color=C["ink"], fontweight="bold")
        left += n
    d_n, t_n, e_n = (p[1] for p in parts)
    draw_lock(axA, d_n + t_n / 2, 0.85, h_in=0.2)
    for i, (lab, n, col, why) in enumerate(parts):
        yy = -1.3 - i * 1.0
        axA.add_patch(Rectangle((0, yy - 0.62), n_tot * 0.014, 0.8, fc=col, ec="none"))
        axA.text(n_tot * 0.025, yy, f"{lab}: {n:,} pockets ({n / n_tot:.0%})", fontsize=10, fontweight="bold",
                 va="center", color=C["ink"])
        axA.text(n_tot * 0.025, yy - 0.42, why, fontsize=9.4, va="center", color=C["ink2"])

    # ---- B: PDB-T funnel -----------------------------------------------------------------------
    axB = fig.add_subplot(gs[0, 1])
    n_scored = pc["meta"]["set"]["n_sites_pool"]
    steps = [
        ("PDB entries in the local mirror", en["n_files"], "entries"),
        ("released after 2025-11-12 (after all training data)", en["n_released_after_cutoff"], "entries"),
        ("X-ray / cryo-EM at \u2264 3 \u00c5 resolution", en["n_kept"], "entries"),
        ("ligand sites (\u2265 10 heavy atoms; no ions/additives)", sc["n_sites_one_per_chain_cluster"], "sites"),
        ("no homologue in any training set", bc["n_sites_after_leakage"], "sites"),
        ("\u2264 3 sites per protein; pairs sealed", bc["n_sites_after_protein_cap"], "sites"),
        ("scored (9 borderline sites removed first)", n_scored, "sites"),
    ]
    ys = np.arange(len(steps))[::-1]
    for (lab, n, unit), yy in zip(steps, ys):
        col = C["neutral"] if unit == "entries" else C["violet"]
        axB.barh(yy, n, height=0.62, color=col, edgecolor="none", zorder=3)
        axB.text(n * 1.15, yy, f"{n:,} {unit}", va="center", fontsize=9.5, color=C["ink"])
    axB.set_yticks(ys)
    axB.set_yticklabels([s_[0] for s_ in steps], fontsize=9.6)
    axB.tick_params(axis="y", length=0)
    axB.set_xscale("log")
    axB.set_xlim(500, 4e6)
    axB.spines["left"].set_visible(False)
    axB.set_xlabel("count (log scale)")
    xgrid(axB)
    axB.set_title("B   PDB-T: a fresh, time-split test set (built after the main test)", pad=4, x=-0.62)
    pB = axB.get_position()
    axB.set_position([0.75, pB.y0, 0.23, pB.height])
    draw_lock(axB, bc["n_sites_after_protein_cap"] * 9, ys[-2], h_in=0.2)

    # ---- C: role table ---------------------------------------------------------------------------
    axC = fig.add_subplot(gs[1, :])
    axC.axis("off")
    axC.set_xlim(0, 100)
    axC.set_ylim(0, 100)
    axC.set_title("C   Every dataset and its role (counts after leakage control)", pad=4)
    cols = [("Dataset", 1), ("What a positive pair means", 15.5), ("Training", 39), ("Development / selection", 56),
            ("Sealed test", 75)]
    for nm, x in cols:
        axC.text(x, 96, nm, fontsize=10.5, fontweight="bold", color=C["ink"], va="center")
    axC.plot([0.5, 99.5], [93, 93], color=C["axis"], lw=1)

    c2n = sum(v["missing"]["n_common"] for v in fc["C2"]["per_subset"].values())
    n_ortho_test = [r for r in fps["ppips"] if r["flag"] == "all" and r["arm"] == "FINAL"][0]["ortho_n_queries"]
    rows = [
        ("TOUGH-M1", "pockets binding similar ligands,\nin unrelated proteins",
         None, f"{tc['dev']['n_pockets']:,} pockets\n{tc['dev']['n_pos'] + tc['dev']['n_neg']:,} pairs",
         f"{tc['test']['n_pockets']:,} pockets, {tc['test']['n_pos'] + tc['test']['n_neg']:,} pairs\nclaims C1a, C1b, C1-D"),
        ("BLiPS (built here\nfrom BioLiP)", "two sites share a ligand,\nproteins in different families",
         f"{b2['train']['n_sites']:,} sites\n{b2['train']['n_pos']:,} positive pairs",
         f"{b2['val']['n_sites']:,} sites\n(method selection)",
         f"{b1['test']['n_sites']:,} sites with AlphaFold models\nAlphaFold-robustness item (C5)"),
        ("PPIPS (AFDB dimers)", "same interface pocket in an\northologous complex",
         f"{pp['train']['n_complexes']:,} complexes", f"{pp['val']['n_complexes']:,} complexes",
         f"{pp['test']['n_complexes']:,} complexes\n{n_ortho_test} ortholog queries (reported)"),
        ("ProSPECCTs", "published pocket-similarity\nbenchmark (10 subsets)", None, None,
         f"{c2n:,} pairs in subsets 5.2, 6.2, 7\nclaim C2"),
        ("Vertex", "published benchmark;\nmostly homologous pairs", None, None,
         f"{vs['vertex']['n_scored']:,} protein pairs (reported)"),
        ("PDB-T (PREREG2)", "as BLiPS, structures released\nafter all training data", None, None,
         f"{n_scored:,} sites, {pc['meta']['set']['n_pairs']:,} pairs\nclaims R1, R2, R3"),
        ("PPI-L (PPI modulators)", "pockets of protein\u2013protein\ninteraction inhibitors", None, None,
         f"only {fd['ppi_l']['n_pos']} positive pairs:\nfeasibility gate failed, not used"),
    ]
    rh = 12.6
    for i, (nm, meaning, tr, dv, te) in enumerate(rows):
        yc = 86 - i * rh
        if i % 2 == 0:
            axC.add_patch(Rectangle((0.5, yc - rh / 2), 99, rh, fc="#f4f3ef", ec="none", zorder=0))
        axC.text(1, yc, nm, fontsize=10.2, fontweight="bold", va="center", color=C["ink"])
        axC.text(15.5, yc, meaning, fontsize=9.3, va="center", color=C["ink2"])
        for x, val, colr in ((39, tr, C["blue"]), (56, dv, C["aqua"]), (75, te, C["orange"])):
            if val is None:
                axC.text(x + 1.2, yc, "\u2014", fontsize=10, va="center", color=C["muted"])
                continue
            axC.add_patch(Rectangle((x, yc - 3.4), 0.7, 6.8, fc=colr, ec="none"))
            axC.text(x + 1.6, yc, val, fontsize=9.4, va="center", color=C["ink"])
            if x == 75 and "not used" not in val:
                draw_lock(axC, 97.5, yc, h_in=0.22)
    draw_lock(axC, 1.6, -2.5, h_in=0.2)
    axC.text(3.2, -2.5, "locked: labels sealed until the single final evaluation; every read was logged with its "
             "checksum. Test proteins have no homologue (\u2265 30 % sequence identity or TM-score \u2265 0.5) "
             "in training/development data (disclosed exception DEV4: 66 TOUGH-M1 test pockets vs PPIPS training).", fontsize=9.2, color=C["ink2"], va="center")
    save(fig, out, "fig2_data")


# ==============================================================================================
# Figure 3: ligand imprint
# ==============================================================================================
def fig3_ligand_imprint(R: Repo, out: Path):
    fs = R.parquet("results/final/final_summary.parquet")  # src: results/final/final_summary.parquet
    vt = R.json("results/verify/v_tough.json")  # src: results/verify/v_tough.json (verifier's size predictors)
    T = fs[(fs.set == "tough_m1_test") & (fs.subset == "all")]

    fig = plt.figure(figsize=(16, 10.5))
    suptitle(fig, "Key finding: pockets cut out around the bound ligand carry the ligand's size",
             "On TOUGH-M1, similar ligands have similar sizes, so a ligand-shaped pocket lets almost any descriptor "
             "\u201ccheat\u201d. Detected pockets remove the shortcut.", y=0.995)

    # ---- A schematic ------------------------------------------------------------------------
    axA = fig.add_axes([0.02, 0.535, 0.96, 0.33])
    axA.set_xlim(0, 100)
    axA.set_ylim(0, 22.6)  # ~equal units for a 15.4 x 3.5 inch box
    axA.axis("off")
    axA.set_title("A   Two ways to define the same binding site", pad=2)
    cav_rel = np.array([[0, 0], [24, 0], [24, 19], [17.5, 19], [16.5, 7.5], [7.5, 7.5], [6.5, 19], [0, 19]])
    # cleft interior polygon (open towards the top)
    cleft_rel = np.array([[6.8, 19.5], [7.6, 7.6], [16.4, 7.6], [17.2, 19.5]])
    lig_rel = np.array([[10.0, 10.2], [11.6, 11.0], [13.2, 10.2], [14.2, 11.6]])

    def scene(x0, mode):
        body = cav_rel + [x0, 0.5]
        ax = axA
        ax.add_patch(Polygon(body, closed=True, fc="#d6d5ce", ec="none", zorder=1))
        ax.text(x0 + 2, 2.5, "protein", fontsize=9, color=C["ink2"])
        cl = MPath(cleft_rel + [x0, 0.5])
        gx, gy = np.meshgrid(np.arange(x0 + 7, x0 + 17.5, 0.85), np.arange(8.4, 20.0, 0.85))
        P = np.c_[gx.ravel(), gy.ravel()]
        inside = cl.contains_points(P)
        lig = lig_rel + [x0, 0.5]
        if mode == "L":
            d = np.min(np.hypot(P[:, None, 0] - lig[None, :, 0], P[:, None, 1] - lig[None, :, 1]), axis=1)
            keep = inside & (d < 2.6)
            ax.scatter(P[keep, 0], P[keep, 1], s=22, color=C["orange"], lw=0, zorder=3)
            ax.plot(lig[:, 0], lig[:, 1], color=C["ink"], lw=2.2, zorder=4)
            ax.scatter(lig[:, 0], lig[:, 1], s=48, color=C["ink"], zorder=5, lw=0)
        else:
            depth_ok = P[:, 1] < 16.0
            keep = inside & depth_ok
            ax.scatter(P[keep, 0], P[keep, 1], s=22, color=C["blue"], lw=0, zorder=3)
            ax.plot(lig[:, 0], lig[:, 1], color=C["ink"], lw=1.2, alpha=0.35, zorder=4, ls="-")
            ax.scatter(lig[:, 0], lig[:, 1], s=30, facecolor="none", edgecolor=C["ink"], alpha=0.45, zorder=5, lw=1)

    scene(2, "L")
    scene(54, "D")
    axA.text(29, 17.5, "Ligand-defined pocket (\u201cL-mode\u201d)", fontsize=11.5, fontweight="bold", va="center")
    axA.text(29, 14.6, "grid points within 4 \u00c5 of the bound\nligand (the common benchmark convention).\n"
             "The pocket's size and shape copy the\nligand's, so two pockets look alike when\ntheir ligands are alike.",
             fontsize=9.6, color=C["ink2"], va="top")
    axA.text(81, 17.5, "Detected pocket (\u201cD-mode\u201d)", fontsize=11.5, fontweight="bold", va="center")
    axA.text(81, 14.6, "the cavity found by BURROW without the\nligand (faded: shown only for reference).\n"
             "Its size reflects the protein, not the\nligand, as in real use on new proteins.",
             fontsize=9.6, color=C["ink2"], va="top")

    # ---- B: L vs D dumbbell ----------------------------------------------------------------------
    axB = fig.add_axes([0.235, 0.09, 0.27, 0.34])
    arms = [("Typed cavity fingerprint on the raw site (A1)", dict(arm="A1", config="pair_only", variant="raw")),
            ("BURROW's own pocket descriptors (B1)", dict(arm="B1", config="default", variant="raw")),
            ("ESM-2 protein language model (B4)", dict(arm="B4", config="esm2", variant="raw")),
            ("pocketcompare (FINAL)", dict(arm="FINAL", variant="raw"))]
    for i, (lab, kw) in enumerate(arms):
        L = summary_row(T, mode="L", **kw)["auc"]
        D = summary_row(T, mode="D", **kw)["auc"]
        y = len(arms) - 1 - i
        axB.plot([L, D], [y + 0.1, y - 0.1], color=C["axis"], lw=2, zorder=2)
        axB.scatter([L], [y + 0.1], s=80, color=C["orange"], zorder=4, edgecolor=C["surface"], linewidth=2)
        axB.scatter([D], [y - 0.1], s=80, color=C["blue"], zorder=4, edgecolor=C["surface"], linewidth=2)
        lo, hi = min(L, D), max(L, D)
        dl = D - L
        axB.text(hi + 0.012, y, f"\u0394 {fmt(dl, 3, True)}", va="center", fontsize=9.5, color=C["ink2"])
    axB.set_yticks(range(len(arms)))
    axB.set_yticklabels([a[0] for a in arms][::-1])
    for t in axB.get_yticklabels():
        if "FINAL" in t.get_text():
            t.set_fontweight("bold")
            t.set_color(C["ink"])
    axB.axvline(0.5, color=C["ink2"], lw=1, zorder=1)
    axB.text(0.502, 3.55, "chance", fontsize=8.8, color=C["ink2"], va="bottom")
    axB.set_xlim(0.47, 0.78)
    axB.set_ylim(-0.6, 3.9)
    axB.set_xlabel("ROC-AUC on TOUGH-M1 test (0.5 = random)")
    xgrid(axB)
    axB.legend(handles=[Line2D([], [], marker="o", ls="", color=C["orange"], ms=8, label="ligand-defined (L)"),
                        Line2D([], [], marker="o", ls="", color=C["blue"], ms=8, label="detected (D)")],
               loc="upper center", ncol=2, fontsize=9.5, bbox_to_anchor=(0.4, -0.16))
    axB.set_title("B   Same benchmark, two pocket definitions (test set)", pad=8)

    # ---- C: trivial predictors ---------------------------------------------------------------
    axC = fig.add_axes([0.725, 0.09, 0.255, 0.34])
    b0 = vt["b0"]
    preds = [
        ("Ligand heavy-atom count", b0["B0_ligand_heavy_atoms"]["auc"], C["orange"]),
        ("Pocket volume, ligand-defined (L)", b0["B0_L_volume(4A ligand shell)"]["auc"], C["orange"]),
        ("Pocket volume, detected (D)", b0["B0_D_volume(common D set)"]["auc"], C["blue"]),
        ("fpocket residue count (TOUGH-M1's pockets)", b0["B0_fpocket_shipped_n_residues"]["auc"], C["neutral"]),
        ("fpocket volume (TOUGH-M1's pockets)", b0["B0_fpocket_shipped_volume"]["auc"], C["neutral"]),
    ]
    for i, (lab, v, col) in enumerate(preds):
        y = len(preds) - 1 - i
        axC.plot([0.5, v], [y, y], color=col, lw=2, zorder=2)
        axC.scatter([v], [y], s=80, color=col, zorder=4, edgecolor=C["surface"], linewidth=2)
        axC.text(v + (0.012 if v >= 0.5 else -0.012), y, f"{v:.3f}", va="center",
                 ha="left" if v >= 0.5 else "right", fontsize=9.5, color=C["ink"])
    axC.set_yticks(range(len(preds)))
    axC.set_yticklabels([p[0] for p in preds][::-1])
    axC.axvline(0.5, color=C["ink2"], lw=1, zorder=1)
    axC.set_xlim(0.40, 1.0)
    axC.set_ylim(-0.6, 4.6)
    axC.set_xlabel("ROC-AUC on TOUGH-M1 test, size difference as the only score")
    xgrid(axC)
    axC.set_title("C   \u201cSize-only\u201d predictors: no pocket chemistry at all", pad=8)
    save(fig, out, "fig3_ligand_imprint")


# ==============================================================================================
# Figure 4: forest plot of pre-registered claims
# ==============================================================================================
def fig4_claims(R: Repo, out: Path):
    fc = R.json("results/final/final_claims.json")  # src: results/final/final_claims.json
    pc = R.json("results/pdbt/claims.json")["claims"]  # src: results/pdbt/claims.json
    sesoi = fc["C1a"]["sesoi"]
    # borderline flags: src: reports/verification_final.md ("The Holm result is fragile") and
    # results/verify/v_tough_mc_C1a.json / v_tough_mc_C1b.json (p by 2,000-replicate block)
    mc = {c: R.json(f"results/verify/v_tough_mc_{c}.json") for c in ("C1a", "C1b")}
    rows = [
        ("C1-D", fc["C1-D"], "pocketcompare vs BURROW descriptors", "TOUGH-M1 test, detected pockets", None),
        ("C1a", fc["C1a"], "pocketcompare vs BURROW descriptors", "TOUGH-M1 test, ligand-defined", "borderline"),
        ("C1b", fc["C1b"], "pocketcompare vs ESM-2", "TOUGH-M1 test, ligand-defined", "borderline"),
        ("C2", fc["C2"], "pocketcompare vs BURROW descriptors", "ProSPECCTs 5.2/6.2/7, ligand-defined", None),
        ("R1", pc["R1"], "pocketcompare vs BURROW descriptors", "PDB-T, detected pockets", None),
        ("R2", pc["R2"], "score fusion (+L4) vs pocketcompare", "PDB-T, detected pockets", None),
        ("R3", pc["R3"], "L4 network vs pocketcompare", "PDB-T, detected pockets", None),
    ]
    fig = plt.figure(figsize=(16, 7.6))
    suptitle(fig, "Pre-registered claims: effect sizes with 95 % confidence intervals",
             "Difference in ROC-AUC (first method minus comparator). Claims were fixed before the test data were "
             "opened; Holm-corrected one-sided p-values.", y=0.995)
    ax = fig.add_axes([0.30, 0.09, 0.34, 0.77])
    axT = fig.add_axes([0.655, 0.09, 0.34, 0.77], sharey=ax)
    axL = fig.add_axes([0.0, 0.09, 0.29, 0.77], sharey=ax)
    ypos = [9, 8, 7, 6, 3, 2, 1]
    for (cid, d, comp, setname, flag), y in zip(rows, ypos):
        rej = d["reject_h0_holm"]
        col = C["blue"] if rej else C["neutral"]
        ax.plot([d["ci_low"], d["ci_high"]], [y, y], color=col, lw=2.2, zorder=3)
        face = col if (rej and flag is None) else C["surface"]
        ax.scatter([d["delta"]], [y], s=95, facecolor=face, edgecolor=col, linewidth=2.2, zorder=4)
        axL.text(0.0, y + 0.17, f"{cid}  {comp}", fontsize=10.2, fontweight="bold", va="center", color=C["ink"])
        axL.text(0.0, y - 0.25, setname, fontsize=9.3, va="center", color=C["ink2"])
        if rej and flag is None:
            verdict, vcol = "supported", C["ink"]
        elif rej:
            pb = mc[cid]["p_by_2000_block"]
            verdict, vcol = (f"borderline: Monte-Carlo fragile\n(verifier re-runs: p {min(pb):.3f}\u2013{max(pb):.3f}"
                             f" vs 0.0167 needed)"), C["ink"]
        else:
            verdict, vcol = "not supported", C["ink2"]
        axT.text(0.0, y, f"{fmt(d['delta'], 3, True)}", fontsize=10, va="center", color=C["ink"])
        axT.text(0.16, y, f"[{fmt(d['ci_low'], 3, True)}, {fmt(d['ci_high'], 3, True)}]", fontsize=10, va="center",
                 color=C["ink2"])
        ph = d["p_holm"]
        axT.text(0.50, y, f"{ph:.3f}" if ph >= 0.1 else f"{ph:.4f}", fontsize=10, va="center", color=C["ink"])
        axT.text(0.65, y, verdict, fontsize=9.6, va="center", color=vcol,
                 fontweight="bold" if verdict == "supported" else "normal")
    for a in (axT, axL):
        a.axis("off")
        a.set_xlim(0, 1)
    hdr = 10.2
    axT.text(0.0, hdr, "\u0394 AUC", fontsize=10, fontweight="bold", va="center")
    axT.text(0.16, hdr, "95 % CI", fontsize=10, fontweight="bold", va="center")
    axT.text(0.50, hdr, "Holm p", fontsize=10, fontweight="bold", va="center")
    axT.text(0.65, hdr, "verdict", fontsize=10, fontweight="bold", va="center")
    ul = pd.read_csv(R.p("results/final/unseal_log.tsv"), sep="\t")  # src: results/final/unseal_log.tsv
    t_open = datetime.fromisoformat(ul.time.min()).strftime("%d Oct %H:%M")
    axL.text(0.0, 10.2, f"Main test (opened once, {t_open})", fontsize=10.5, fontweight="bold", color=C["ink2"],
             va="center")
    axL.text(0.0, 4.2, "Temporal replication on fresh data (PREREG2)", fontsize=10.5, fontweight="bold",
             color=C["ink2"], va="center")
    ax.axvline(0, color=C["ink"], lw=1.1, zorder=2)
    ax.axvline(sesoi, color=C["orange"], lw=1.2, ls=(0, (4, 3)), zorder=2)
    ax.text(sesoi + 0.004, 10.25, f"smallest effect\nof interest ({sesoi:.2f})", fontsize=8.8, color=C["ink2"],
            va="center")
    ax.text(-0.004, 10.25, "no\ndifference", fontsize=8.8, color=C["ink2"], va="center", ha="right")
    ax.axhline(4.9, color=C["axis"], lw=0.8)
    ax.set_ylim(0.3, 10.9)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-0.12, 0.32)
    ax.set_xlabel("difference in ROC-AUC (positive = first method better)")
    xgrid(ax)
    leg = [Line2D([], [], marker="o", ls="", ms=9, color=C["blue"], label="supported (Holm)"),
           Line2D([], [], marker="o", ls="", ms=9, markerfacecolor=C["surface"], markeredgecolor=C["blue"],
                  markeredgewidth=2, label="supported, fragile"),
           Line2D([], [], marker="o", ls="", ms=9, markerfacecolor=C["surface"], markeredgecolor=C["neutral"],
                  markeredgewidth=2, label="not supported")]
    ax.legend(handles=leg, loc="upper center", bbox_to_anchor=(0.5, -0.11), ncol=3, fontsize=9.3)
    save(fig, out, "fig4_claims")


# ==============================================================================================
# Figure 5: TOUGH-M1 comparison raw vs size-stratified
# ==============================================================================================
def fig5_tough_comparison(R: Repo, out: Path):
    fs = R.parquet("results/final/final_summary.parquet")  # src: results/final/final_summary.parquet
    T = fs[(fs.set == "tough_m1_test") & (fs.subset == "all")]
    arms = [
        ("pocketcompare (FINAL)", dict(arm="FINAL", variant="raw", mode="L"), "ours"),
        ("FINAL's unlearned input (N1)", dict(arm="N1", config="N1", variant="raw", mode="L"), "ours"),
        ("L4 point-cloud network (declared variant)", dict(arm="L4", config="L4:egnn_small", variant="csls", mode="L"),
         "ours"),
        ("Typed cavity fingerprint, raw site (A1)", dict(arm="A1", config="pair_only", variant="raw", mode="L"), "ours"),
        ("G-LoSA (published scores)", dict(arm="B5T", config="glosa_ga", mode="native"), "pub"),
        ("SiteEngine (published scores)", dict(arm="B5T", config="siteengine_c1", mode="native"), "pub"),
        ("APoc (published scores)", None, "pub"),
        ("EPoCS (ESM-2 3B pocket embedding)", dict(arm="B5", config="epocs", variant="raw", mode="L"), "base"),
        ("BURROW's own descriptors (B1)", dict(arm="B1", config="default", variant="raw", mode="L"), "base"),
        ("ESM-2 lining residues (B4)", dict(arm="B4", config="esm2", variant="raw", mode="L"), "base"),
        ("Pocket size only (B0)", dict(arm="B0", config="default", variant="raw", mode="L"), "size"),
        ("Global fold similarity (TM-score)", dict(arm="B0p", config="tm_score", mode="native"), "base"),
    ]
    rows = []
    for lab, kw, kind in arms:
        if kw is None:  # APoc: best of the two shipped columns by raw AUC
            cands = [summary_row(T, arm="B5T", config=c, mode="native") for c in ("apoc_ps", "apoc_negp")]
            r = max(cands, key=lambda r: r["auc"])
            lab = f"APoc (published, best column)"
        else:
            r = summary_row(T, **kw)
        rows.append((lab, r["auc"], r["auc_strat"], kind))
    rows.sort(key=lambda t: t[2])
    fig, ax = plt.subplots(figsize=(13, 8.2))
    fig.subplots_adjust(left=0.30, right=0.97, top=0.865, bottom=0.12)
    suptitle(fig, "TOUGH-M1 test: removing the size signal changes the ranking",
             "Raw ROC-AUC vs ROC-AUC computed within bins of similar pocket size (\u201csize-stratified\u201d). "
             "Ligand-defined pockets (published tools: their own pockets); BURROW-clean test, 24,337 pairs.",
             y=0.995)
    for i, (lab, raw, strat, kind) in enumerate(rows):
        hl = kind == "ours" and lab.startswith("pocketcompare")
        ax.plot([raw, strat], [i, i], color=C["axis"], lw=2, zorder=2)
        ax.scatter([raw], [i], s=80, facecolor=C["surface"], edgecolor=C["orange"], linewidth=2.2, zorder=4)
        ax.scatter([strat], [i], s=85, color=C["blue"], zorder=5, edgecolor=C["surface"], linewidth=1.5)
        ax.text(max(raw, strat) + 0.012, i, f"{raw:.2f} \u2192 {strat:.2f}", va="center", fontsize=9.3,
                color=C["ink"] if hl else C["ink2"], fontweight="bold" if hl else "normal",
                bbox=dict(fc=C["surface"], ec="none", pad=1.0), zorder=6)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows])
    for t, r in zip(ax.get_yticklabels(), rows):
        if r[0].startswith("pocketcompare"):
            t.set_fontweight("bold")
            t.set_color(C["ink"])
    ax.axvline(0.5, color=C["ink2"], lw=1)
    ax.text(0.503, len(rows) - 0.35, "chance", fontsize=8.8, color=C["ink2"])
    ax.set_xlim(0.40, 0.90)
    ax.set_ylim(-0.7, len(rows) - 0.1)
    ax.set_xlabel("ROC-AUC (0.5 = random)")
    xgrid(ax)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", ms=8.5, markerfacecolor=C["surface"],
                              markeredgecolor=C["orange"], markeredgewidth=2, label="raw ROC-AUC"),
                       Line2D([], [], marker="o", ls="", ms=8.5, color=C["blue"], label="size-stratified ROC-AUC")],
              loc="upper center", bbox_to_anchor=(0.4, -0.08), ncol=2)
    save(fig, out, "fig5_tough_comparison")


# ==============================================================================================
# Figure 6: robustness
# ==============================================================================================
def fig6_robustness(R: Repo, out: Path):
    c5 = R.parquet("results/final_post/c5_holo_minus_af.parquet")  # src: results/final_post/c5_holo_minus_af.parquet
    ssr = R.json("results/tooling/site_score_recall.json")  # src: results/tooling/site_score_recall.json
    bl = pd.read_csv(R.p("results/final_post/blind_test/metrics.csv"))  # src: results/final_post/blind_test/metrics.csv

    fig = plt.figure(figsize=(16, 6.6))
    suptitle(fig, "Robustness: AlphaFold models, detection cut-offs and a fully blind search",
             None, y=0.995)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1, 1], wspace=0.42, left=0.11, right=0.985, top=0.83,
                          bottom=0.15)
    # A
    ax = fig.add_subplot(gs[0, 0])
    arms = [("FINAL", "pocketcompare (FINAL)"), ("N1", "unlearned input (N1)"), ("L4", "L4 network (declared)"),
            ("B1", "BURROW descriptors (B1)"), ("B4", "ESM-2 (B4)")]
    var = dict(FINAL="raw", N1="raw", L4="csls", B1="raw", B4="raw")
    y = 0
    yt, yl = [], []
    for arm, lab in arms:
        for mode, col, off in (("L", C["orange"], 0.17), ("D", C["blue"], -0.17)):
            r = c5[(c5.arm == arm) & (c5["mode"] == mode) & (c5.stratum == "all") & (c5.variant == var[arm])]
            assert len(r) == 1, (arm, mode)
            r = r.iloc[0]
            yy = -y + off
            ax.plot([r.ci_low, r.ci_high], [yy, yy], color=col, lw=2, zorder=3)
            ax.scatter([r.delta], [yy], s=55, color=col, zorder=4, edgecolor=C["surface"], linewidth=1.5)
        yt.append(-y)
        yl.append(lab)
        y += 1
    ax.axvspan(-0.03, 0.03, color=C["gray_wash"], zorder=0)
    ax.axvline(0, color=C["ink"], lw=1)
    ax.text(0, 0.62, "\u00b10.03: smaller than any\neffect of interest", fontsize=8.5, color=C["ink2"], ha="center",
            va="bottom")
    ax.set_yticks(yt)
    ax.set_yticklabels(yl)
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.set_ylim(-len(arms) + 0.4, 1.35)
    ax.set_xlim(-0.06, 0.06)
    ax.set_xlabel("ROC-AUC on crystal structures minus AlphaFold models\n(positive = worse on AlphaFold)")
    xgrid(ax)
    ax.set_title("A   Same sites, crystal vs AlphaFold model\n(BLiPS test)", pad=6)
    ax.legend(handles=[Line2D([], [], marker="o", ls="-", color=C["orange"], ms=7, label="ligand-defined (L)"),
                       Line2D([], [], marker="o", ls="-", color=C["blue"], ms=7, label="detected (D)")],
              loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=2, fontsize=9)

    # B
    ax = fig.add_subplot(gs[0, 1])
    cut = np.array([c["cut"] for c in ssr["cutoffs"]])
    rec = np.array([c["site_recall_given_detected"] for c in ssr["cutoffs"]])
    kept = np.array([c["pool_fraction_kept"] for c in ssr["cutoffs"]])
    ax.plot(cut, rec, color=C["blue"], lw=2, marker="o", ms=5)
    ax.plot(cut, kept, color=C["neutral"], lw=2, marker="o", ms=5)
    ax.text(cut[-1] + 0.01, rec[-1], "detected true\nligand sites\nkept", fontsize=9, color=C["ink"], va="center")
    ax.text(cut[-1] + 0.01, kept[-1], "all pockets\nkept", fontsize=9, color=C["ink"], va="center")
    i3 = int(np.argmin(np.abs(cut - 0.03)))
    ax.annotate(f"cut-off {cut[i3]:.2f}: {rec[i3]:.0%} of sites,\n{kept[i3]:.0%} of pockets",
                xy=(cut[i3], kept[i3]), xytext=(0.12, 0.88), fontsize=8.8, color=C["ink2"],
                arrowprops=dict(arrowstyle="-", color=C["ink2"], lw=0.8))
    ax.set_xlim(0, 0.62)
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0 %", "25 %", "50 %", "75 %", "100 %"])
    ax.set_xlabel("minimum BURROW pocket score kept")
    ax.set_ylabel("fraction kept")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.set_title(f"B   Pruning low-score pockets\n({ssr['n_sites']:,} known sites, {ssr['n_models']} AF models; dev data)",
                 pad=6)
    # C
    ax = fig.add_subplot(gs[0, 2])
    lab = {"final": "pocketcompare", "B1": "BURROW descr. (B1)", "B0": "pocket size (B0)"}
    sub = bl[(bl.variant == "all") & (bl.metric == "auc")]
    for j, arm in enumerate(["final", "B1", "B0"]):
        for cond, col, off, mk in ((True, C["blue"], 0.15, "o"), (False, C["neutral"], -0.15, "s")):
            r = sub[(sub.arm == arm) & (sub.conditional == cond)].iloc[0]
            yy = -j + off
            ax.plot([r.ci_low, r.ci_high], [yy, yy], color=col, lw=2)
            ax.scatter([r.estimate], [yy], s=55, color=col, marker=mk, zorder=4, edgecolor=C["surface"], lw=1.5)
            ax.text(r.ci_high + 0.008, yy, f"{r.estimate:.3f}", fontsize=9, va="center", color=C["ink"])
    ax.set_yticks([0, -1, -2])
    ax.set_yticklabels([lab[a] for a in ["final", "B1", "B0"]])
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.axvline(0.5, color=C["ink2"], lw=1)
    ax.text(0.503, 0.5, "chance", fontsize=8.8, color=C["ink2"], va="center")
    ax.set_xlim(0.48, 0.82)
    ax.set_ylim(-2.6, 0.6)
    ax.set_xlabel("ROC-AUC, partner site vs all ~14k pockets")
    xgrid(ax)
    det = bl[(bl.variant == "detection") & (bl.arm == "all_sites")].iloc[0]
    ax.set_title(f"C   Blind search on AlphaFold models\n(BLiPS test; BURROW finds {det.estimate:.0%} of sites)", pad=6)
    ax.legend(handles=[Line2D([], [], marker="o", ls="-", color=C["blue"], ms=7, label="both sites detected"),
                       Line2D([], [], marker="s", ls="-", color=C["neutral"], ms=7, label="missed sites count as failures")],
              loc="upper center", bbox_to_anchor=(0.4, -0.22), ncol=1, fontsize=9)
    save(fig, out, "fig6_robustness")


# ==============================================================================================
# Figure 7: scale
# ==============================================================================================
def _parse_log(p: Path):
    txt = p.read_text().strip().splitlines()[-1]
    m = re.search(r"(\d+) structures \((\d+) errors\), (\d+) pockets .*\[([\d.]+) s wall", txt)
    return dict(n=int(m.group(1)), err=int(m.group(2)), pockets=int(m.group(3)), wall=float(m.group(4)))


def _md_table(text: str, header_start: str):
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith(header_start):
            rows = []
            for l2 in lines[i + 2:]:
                if not l2.startswith("|"):
                    break
                rows.append([c.strip() for c in l2.strip().strip("|").split("|")])
            return rows
    raise KeyError(header_start)


def fig7_scale(R: Repo, out: Path):
    ps = R.json("results/proteome/summary.json")  # src: results/proteome/summary.json (human AFDB run, per stage)
    rt = R.json("results/dev/final_method_runtime.json")  # src: results/dev/final_method_runtime.json (head)
    logs = {k: [_parse_log(R.p(f"results/tooling/afdb_cost/node_{k}4x15_shard{i}.log")) for i in range(4)]
            for k in ("gpu", "cpu")}  # src: results/tooling/afdb_cost/node_{gpu,cpu}4x15_shard*.log
    quiet = _parse_log(R.p("results/tooling/afdb_cost/single_gpu_shard_quiet.log"))  # src: same dir
    cost_md = R.text("docs/AFDB_COST.md")  # src: docs/AFDB_COST.md section 5 table
    opts = _md_table(cost_md, "| option | hardware | expected time |")

    fig = plt.figure(figsize=(16, 9.6))
    suptitle(fig, "Cost at AlphaFold-database scale",
             "Measured on one shared node (64 CPU cores, 4 \u00d7 RTX 4090); 200 M-structure figures are extrapolations.",
             y=0.995)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 0.95], width_ratios=[1.15, 1], hspace=0.55, wspace=0.3,
                          left=0.12, right=0.98, top=0.86, bottom=0.04)
    # A stacked CPU seconds
    ax = fig.add_subplot(gs[0, 0])
    runs = [("run_gpu", "GPU-assisted BURROW"), ("run_fastcpu", "CPU only, fast backend"),
            ("run_refcpu", "CPU only, reference backend")]
    stages = [("read_decompress", "read file", C["aqua"]), ("burrow", "BURROW pocket detection", C["orange"]),
              ("descriptors", "fingerprint (sph8 + descriptor)", C["blue"])]
    for i, (rk, lab) in enumerate(runs):
        r = ps["runs"][rk]
        left = 0.0
        yy = -i
        for sk, slab, col in stages:
            v = r["cpu_s_per_structure"][sk] * 1000
            ax.barh(yy, v, left=left, height=0.52, color=col, edgecolor=C["surface"], linewidth=2)
            if v > 28:
                ax.text(left + v / 2, yy, f"{v:.0f}", ha="center", va="center", fontsize=9,
                        color="white" if col != C["aqua"] else C["ink"])
            left += v
        head_ms = rt["embed_us_per_pocket"] / 1000 * r["pockets_per_structure"]
        extra = f"  {left:.0f} ms"
        if r["gpu_s_per_structure"] > 0:
            extra += f" + {r['gpu_s_per_structure'] * 1000:.1f} GPU-ms"
        ax.text(left + 6, yy, extra, va="center", fontsize=9.5, color=C["ink"])
    ax.set_yticks([0, -1, -2])
    ax.set_yticklabels([r[1] for r in runs])
    ax.set_xlabel("CPU milliseconds per structure (human AFDB, 23,586 models)")
    ax.set_xlim(0, 780)
    xgrid(ax)
    ax.legend(handles=[Rectangle((0, 0), 1, 1, color=c) for _, _, c in stages] + [Line2D([], [], ls="")],
              labels=[s[1] for s in stages] + [f"linear head: {head_ms:.2f} ms per structure (too small to show)"],
              loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2, fontsize=9)
    ax.set_title("A   Where the time goes, per structure", pad=6)

    # B throughput
    ax = fig.add_subplot(gs[0, 1])
    g_n = sum(l["n"] for l in logs["gpu"])
    g_w = max(l["wall"] for l in logs["gpu"])
    c_n = sum(l["n"] for l in logs["cpu"])
    c_w = max(l["wall"] for l in logs["cpu"])
    bars = [
        ("full node, 4 GPUs + 60 workers", g_n / g_w, C["blue"]),
        ("full node, CPU only (60 workers)", c_n / c_w, C["neutral"]),
        ("1 GPU + 15 workers (quiet node)", quiet["n"] / quiet["wall"], C["blue"]),
        ("human run: 2 GPUs + 22 workers", ps["runs"]["run_gpu"]["structures_per_s"], C["blue"]),
        ("human run: 22 CPU workers", ps["runs"]["run_fastcpu"]["structures_per_s"], C["neutral"]),
    ]
    for i, (lab, v, col) in enumerate(bars):
        ax.barh(-i, v, height=0.55, color=col)
        ax.text(v + 6, -i, f"{v:.0f}", va="center", fontsize=9.5, color=C["ink"])
    ax.set_yticks([-i for i in range(len(bars))])
    ax.set_yticklabels([b[0] for b in bars])
    ax.set_xlabel("structures per second (end to end, incl. reading files)")
    ax.set_xlim(0, 430)
    xgrid(ax)
    ax.set_title(f"B   Measured throughput\n(node runs: {g_n:,} AF models from 4 proteomes, 0 errors)", pad=6)

    # C table of options
    ax = fig.add_subplot(gs[1, :])
    pC = ax.get_position()
    ax.set_position([0.03, pC.y0, 0.95, pC.height])
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_title("C   Fingerprinting all ~200 million AFDB structures: time on different hardware", pad=4)
    days_gpu = 200e6 / (g_n / g_w) / 86400
    days_cpu = 200e6 / (c_n / c_w) / 86400
    trows = [(o[0], o[1], o[2]) for o in opts]
    trows.append(("our node, CPU only", "64 cores, GPUs unused (measured 234 structures/s)".replace(
        "234", f"{c_n / c_w:.0f}"), f"\u2248 {days_cpu:.1f} days"))
    hx = [1, 27, 70]
    for x, h in zip(hx, ["option", "hardware", "expected time"]):
        ax.text(x, 94, h, fontsize=10.5, fontweight="bold", va="center")
    ax.plot([0.5, 99.5], [89, 89], color=C["axis"], lw=1)
    rh = 14.5
    for i, (a, b, c) in enumerate(trows):
        yc = 81 - i * rh
        if i % 2 == 0:
            ax.add_patch(Rectangle((0.5, yc - rh / 2), 99, rh, fc="#f4f3ef", ec="none"))
        ax.text(hx[0], yc, a, fontsize=9.8, va="center", color=C["ink"])
        ax.text(hx[1], yc, b.replace(" = ", "\n= "), fontsize=9.4, va="center", color=C["ink2"])
        c_main, _, c_note = c.partition(" (")
        ax.text(hx[2], yc + (2.2 if c_note else 0), c_main, fontsize=9.8, va="center", color=C["ink"],
                fontweight="bold")
        if c_note:
            ax.text(hx[2], yc - 3.0, "(" + c_note, fontsize=8.8, va="center", color=C["ink2"])
    ax.text(1, -1, f"Measured node rate {g_n / g_w:.0f} structures/s \u2192 200 M structures in \u2248 {days_gpu:.1f} "
            "days on one node. Rows A\u2013D from docs/AFDB_COST.md \u00a75 (B assumes linear scaling; not measured).",
            fontsize=9, color=C["ink2"], va="center")
    save(fig, out, "fig7_scale")


# ==============================================================================================
# Figure 8: process timeline
# ==============================================================================================
LANES = ["design & review", "data & splits", "methods & dev evaluation", "test & verification", "post-test"]
# id -> (lane, label, kind); times are parsed from RESEARCH_TREE.md (src) unless noted.
EVENTS = {
    "D2": (1, "test labels sealed", "integrity"),
    "DEV1": (1, "DEV1: reviewer saw labels pre-seal", "deviation"),
    "D4": (0, "design v1 (review round 1)", "decision"),
    "D5": (0, "design v2 frozen (round 2)", "decision"),
    "D6": (0, "size strata amended", "decision"),
    "D7": (1, "PPI-L gate fails", "fail"),
    "D8": (1, "TOUGH-M1 dev/test split", "decision"),
    "D10": (2, "fragment-docking gate fails", "fail"),
    "D11": (2, "ligand-imprint finding \u2192 claim C1-D", "key"),
    "D14": (0, "PREREG consolidated", "decision"),
    "D15": (1, "split audit fails \u2192 rebuild", "fail"),
    "D16": (0, "addendum: L4 candidate", "decision"),
    "D18": (1, "rebuilt splits accepted", "decision"),
    "D19": (2, "tie-break rule", "decision"),
    "D20": (2, "final method selected", "key"),
    "D21": (3, "FREEZE", "key"),
    "DEV3": (3, "DEV3: run aborted, re-run", "deviation"),
    "DEV4": (3, "DEV4 (verifier)", "deviation"),
    "D22": (0, "M3 retrospective", "decision"),
    "D24": (4, "PREREG2: PDB-T registered", "key"),
    "DEV6": (4, "DEV6: missing items post hoc", "deviation"),
    "D25": (4, "9 borderline sites excluded", "decision"),
    "DEV7": (4, "DEV7: PDB-T run aborted", "deviation"),
    "D26": (4, "stop (D26)", "decision"),
}
KIND_STYLE = {
    "decision": dict(marker="o", color=C["neutral"]),
    "key": dict(marker="D", color=C["blue"]),
    "integrity": dict(marker="s", color=C["sealed"]),
    "fail": dict(marker="X", color=C["red"]),
    "deviation": dict(marker="^", color=C["orange"]),
}


def fig9_process(R: Repo, out: Path):
    tree = R.text("RESEARCH_TREE.md")  # src: RESEARCH_TREE.md (Decisions + status headings)
    t0 = datetime(2026, 10, 27, 18, 0)

    def hours(hhmm, date=None):
        h, m = map(int, hhmm.split(":"))
        if date is None:
            date = "2026-10-27" if h >= 12 else "2026-10-28"
        d = datetime.strptime(f"{date} {hhmm}", "%Y-%m-%d %H:%M")
        return (d - t0).total_seconds() / 3600

    times = {}
    for m in re.finditer(r"^- (D\d+|DEV\d+) \((\d\d:\d\d)", tree, flags=re.M):
        times.setdefault(m.group(1), hours(m.group(2)))
    miles = []
    for m in re.finditer(r"^### (2026-10-2\d) (\d\d:\d\d) \u2014 (M\d) ([^\n(]*)", tree, flags=re.M):
        miles.append((hours(m.group(2), m.group(1)), m.group(3), m.group(4).strip()))
    # extra timestamps from logs (src noted)
    extra = []

    def iso_h(s):
        d = datetime.fromisoformat(s).replace(tzinfo=None)
        return (d - t0).total_seconds() / 3600

    ul = pd.read_csv(R.p("results/final/unseal_log.tsv"), sep="\t")  # src: results/final/unseal_log.tsv
    extra.append((iso_h(ul.time.min()), 3, "final evaluation (sealed files read once)", "integrity"))
    vl = pd.read_csv(R.p("results/verify/unseal_log.tsv"), sep="\t")  # src: results/verify/unseal_log.tsv
    extra.append((iso_h(vl.time.min()), 3, "independent verification", "key"))
    gate = R.json("results/pdbt/gate.json")  # src: results/pdbt/gate.json (created)
    extra.append(((datetime.strptime(gate["created"], "%Y-%m-%d %H:%M:%S") - t0).total_seconds() / 3600, 4,
                  "PDB-T built + sealed", "integrity"))
    pl = pd.read_csv(R.p("results/pdbt/unseal_log.tsv"), sep="\t")  # src: results/pdbt/unseal_log.tsv
    extra.append((iso_h(pl.time.max()), 4, "PDB-T evaluated: R1 replicates", "key"))
    try:  # src: git commit time of the AFDB cost assessment (docs/AFDB_COST.md)
        ct = subprocess.run(["git", "-C", str(R.root), "log", "-1", "--format=%cI", "--", "docs/AFDB_COST.md"],
                            capture_output=True, text=True, check=True).stdout.strip()
        cts = subprocess.run(["git", "-C", str(R.root), "log", "--format=%cI", "--", "docs/AFDB_COST.md"],
                             capture_output=True, text=True, check=True).stdout.split()
        extra.append((iso_h(cts[-1]), 4, "AFDB cost assessment", "decision"))
    except Exception:
        pass

    ev = []
    for k, (lane, lab, kind) in EVENTS.items():
        if k in times:
            ev.append((times[k], lane, lab, kind))
    ev += extra
    ev.sort()

    fig, ax = plt.subplots(figsize=(17, 11.8))
    fig.subplots_adjust(left=0.125, right=0.985, top=0.865, bottom=0.1)
    suptitle(fig, "How the agents worked: 16 hours from kickoff to a replicated result",
             "Wall-clock time, 27 Oct 18:00 \u2192 28 Oct 10:30 (CET). Each marker is a recorded decision, deviation "
             "or event; the sealed test data were opened only after the method was frozen.", y=0.995)
    nl = len(LANES)
    LH = 2.25  # lane height (data units)
    base = {i: (nl - 1 - i) * LH for i in range(nl)}
    for i in range(nl):
        if i % 2 == 0:
            ax.axhspan(base[i] - 0.3, base[i] + LH - 0.3, color="#f4f3ef", zorder=0)
    ax.set_yticks([base[i] + 0.45 for i in range(nl)])
    ax.set_yticklabels(LANES, fontsize=10.5)
    x_hi = 16.75
    ax.set_xlim(-0.3, x_hi)
    ax.set_ylim(-0.35, nl * LH - 0.2)
    tf = times.get("D21")
    if tf is not None:
        ax.axvline(tf, color=C["blue"], lw=1.6, zorder=1)
        ax.text(tf + 0.07, nl * LH - 0.3, "method frozen \u2192 test opened", fontsize=9.2, color=C["blue"],
                va="top", fontweight="bold")
    for h, mid, txt in miles:
        ax.axvline(h, color=C["axis"], lw=1, zorder=1)
        ax.text(h, nl * LH - 0.15, mid, fontsize=9, color=C["ink2"], ha="center", va="bottom", fontweight="bold")
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    tiers = [0.34 + 0.29 * k for k in range(6)]
    # marker positions (nudge coincident times), forward in time
    placed_x = {i: [] for i in range(nl)}
    items = []
    for h, lane, lab, kind in ev:
        hx = h
        while any(abs(hx - q) < 0.12 for q in placed_x[lane]):
            hx += 0.15
        placed_x[lane].append(hx)
        items.append((hx, lane, lab, kind))
        st = KIND_STYLE[kind]
        ax.scatter([hx], [base[lane]], s=75, marker=st["marker"], color=st["color"], zorder=5,
                   edgecolor=C["surface"], linewidth=1.2)
    # labels: latest event first, each takes the lowest free tier to its right (staircase, so leader
    # lines never cross labels); flip to the left only when no tier is free.
    occupied = {i: [] for i in range(nl)}
    leaders = {i: [] for i in range(nl)}
    for hx, lane, lab, kind in sorted(items, key=lambda t: -t[0]):
        y0 = base[lane]
        t = ax.text(hx, y0, lab, fontsize=8.8, color=C["ink"], va="center", ha="left", zorder=6)
        bb = t.get_window_extent(renderer=rend)
        w = inv.transform((bb.x1, 0))[0] - inv.transform((bb.x0, 0))[0]

        def free(x0, x1, k, strict=True):
            if x0 < -0.3 or x1 > x_hi:
                return False
            if any(x0 - 0.05 < lx < x1 + 0.05 and lt > k for lx, lt in leaders[lane]):
                return False  # would cover a later event's leader line
            if strict and any(ok < k and o0 - 0.05 < hx < o1 + 0.05 for o0, o1, ok in occupied[lane]):
                return False  # own leader would cross a placed label
            return all(not (ok == k and x0 < o1 + 0.08 and x1 > o0 - 0.08) for o0, o1, ok in occupied[lane])

        choice = None
        for strict in (True, False):
            for side in ("right", "left"):
                for k in range(len(tiers)):
                    x0, x1 = (hx - 0.04, hx - 0.04 + w) if side == "right" else (hx + 0.04 - w, hx + 0.04)
                    if free(x0, x1, k, strict):
                        choice = (side, k, x0, x1)
                        break
                if choice:
                    break
            if choice:
                break
        assert choice is not None, lab
        side, k, x0, x1 = choice
        occupied[lane].append((x0, x1, k))
        leaders[lane].append((hx, k))
        t.set_ha("left" if side == "right" else "right")
        t.set_x(hx - 0.04 if side == "right" else hx + 0.04)
        t.set_y(y0 + tiers[k])
        ax.plot([hx, hx], [y0 + 0.1, y0 + tiers[k] - 0.1], color=C["axis"], lw=0.8, zorder=2)
    ticks = np.arange(0, 17, 1)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{(18 + int(t)) % 24:02d}:00" for t in ticks], fontsize=9)
    ax.set_xlabel("clock time (27 Oct \u2192 28 Oct)")
    ax.grid(axis="x", color=C["grid"])
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    leg = [Line2D([], [], ls="", marker=KIND_STYLE[k]["marker"], color=KIND_STYLE[k]["color"], ms=8, label=l)
           for k, l in (("key", "key result / event"), ("decision", "decision"),
                        ("integrity", "sealing / sealed-data access"), ("fail", "failed gate or audit"),
                        ("deviation", "disclosed protocol deviation"))]
    ax.legend(handles=leg, loc="upper center", bbox_to_anchor=(0.45, -0.075), ncol=5, fontsize=9.3)
    save(fig, out, "fig9_process")


# ==============================================================================================
# Figure 9: negative results
# ==============================================================================================
def fig8_negative(R: Repo, out: Path):
    td = R.json("results/dev/tough_m1_dev_v2splits_details.json")  # src: results/dev/tough_m1_dev_v2splits_details.json
    pv = R.json("results/dev/ppips_val_v2splits_details.json")  # src: results/dev/ppips_val_v2splits_details.json
    pc = R.json("results/pdbt/claims.json")["claims"]  # src: results/pdbt/claims.json
    pr = R.json("results/exploratory/ppi_r/summary.json")  # src: results/exploratory/ppi_r/summary.json

    g = td["gate"]["A1+A2frag|raw"]["delta_strat_vs_cf_A1"]
    rows = [("Fragment docking added to the cavity fingerprint", "TOUGH-M1 dev, \u0394 size-stratified AUC",
             g["estimate"], g["ci_low"], g["ci_high"], 0.01)]
    names = {"rank": "rank profile", "le_resid": "efficiency-residual profile", "ifp": "interaction profile"}
    for h in pv["hypothesis"]:
        if h["stratum"] == "all" and h["variant"] == "raw":
            rows.append((f"PPI pockets: fragments vs lead-like ({names[h['block']]})", "PPIPS val, \u0394 MRR",
                         h["d_mrr"], h["d_mrr_lo"], h["d_mrr_hi"], None))
    rows.append(("Score fusion (pocketcompare + L4) vs pocketcompare", "fresh PDB-T data, \u0394 ROC-AUC (R2)",
                 pc["R2"]["delta"], pc["R2"]["ci_low"], pc["R2"]["ci_high"], None))
    rows.append(("L4 network vs pocketcompare", "fresh PDB-T data, \u0394 ROC-AUC (R3)",
                 pc["R3"]["delta"], pc["R3"]["ci_low"], pc["R3"]["ci_high"], None))

    fig = plt.figure(figsize=(16, 6.6))
    suptitle(fig, "What did not work", "Pre-registered gates and hypotheses that failed, and two "
             "\u201cimprovements\u201d that did not hold up on fresh data. Dots: estimate; lines: 95 % CI.", y=0.995)
    ax = fig.add_axes([0.30, 0.16, 0.36, 0.66])
    for i, (lab, sub, est, lo, hi, gate) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=C["neutral"], lw=2, zorder=3)
        ax.scatter([est], [y], s=70, color=C["neutral"], zorder=4, edgecolor=C["surface"], lw=1.5)
        if gate is not None:
            ax.scatter([gate], [y], marker="|", s=260, color=C["orange"], zorder=5, lw=2.2)
            ax.text(gate + 0.005, y + 0.3, f"required \u2265 +{gate:.2f}", fontsize=8.6, color=C["ink2"])
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{r[0]}\n{r[1]}" for r in rows][::-1], fontsize=9.4)
    ax.axvline(0, color=C["ink"], lw=1.1)
    ax.set_xlabel("difference (positive = idea helps)")
    ax.set_xlim(min(r[3] for r in rows) - 0.02, max(r[4] for r in rows) + 0.02)
    ax.set_ylim(-0.6, len(rows) - 0.3)
    xgrid(ax)
    ax.set_title("A   Ideas that gave no improvement", pad=8)

    ax2 = fig.add_axes([0.80, 0.16, 0.18, 0.66])
    arms = [("FINAL", "pocketcompare"), ("N1", "unlearned input (N1)"), ("B1", "BURROW descr. (B1)"),
            ("B4", "ESM-2 (B4)")]
    for i, (k, lab) in enumerate(arms):
        a = pr["arms"][k]["query_mean"]["auc"]
        y = len(arms) - 1 - i
        ax2.plot([a["ci_low"], a["ci_high"]], [y, y], color=C["neutral"], lw=2)
        ax2.scatter([a["estimate"]], [y], s=70, color=C["neutral"], zorder=4, edgecolor=C["surface"], lw=1.5)
        ax2.text(a["ci_high"] + 0.006, y, f"{a['estimate']:.3f}", fontsize=9, va="center")
    ax2.set_yticks(range(len(arms)))
    ax2.set_yticklabels([a[1] for a in arms][::-1], fontsize=9.4)
    ax2.axvline(0.5, color=C["ink"], lw=1.1)
    ax2.text(0.501, len(arms) - 0.45, "chance", fontsize=8.8, color=C["ink2"])
    ax2.set_xlim(0.40, 0.68)
    ax2.set_ylim(-0.6, len(arms) - 0.2)
    ax2.set_xlabel("ROC-AUC")
    xgrid(ax2)
    ax2.set_title(f"B   PPI-inhibitor pockets vs\nmatched ligand pockets (exploratory)\n"
                  f"({pr['n_queries']:,} queries, {pr['n_query_groups']} homology groups)", pad=8)
    save(fig, out, "fig8_negative")


FIGS = dict(fig1=fig1_pipeline, fig2=fig2_data, fig3=fig3_ligand_imprint, fig4=fig4_claims,
            fig5=fig5_tough_comparison, fig6=fig6_robustness, fig7=fig7_scale, fig8=fig9_process,
            fig9=fig8_negative)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("research_repo", type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--only", default="", help="comma-separated subset, e.g. fig1,fig4")
    a = ap.parse_args()
    setup_style()
    R = Repo(a.research_repo)
    sel = [s for s in a.only.split(",") if s] or list(FIGS)
    for k in sel:
        FIGS[k](R, a.out)


if __name__ == "__main__":
    main()
