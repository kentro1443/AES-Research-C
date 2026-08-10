#!/usr/bin/env python3
"""plot_projection.py -- draw the n=10 -> n=30 precision projection.

Companion to project_n30.py. Reads the two *summary* CSVs (not the per-trial
results CSVs that plot_threshold.py wants) and renders:

    plots/<tag>_success_rate.{png,svg}   psychometric curve at projected n=30
    plots/<tag>_ci_compare.{png,svg}     n=10 vs n=30 interval widths

Every figure is captioned PROJECTION. The n=30 error bars are NOT measurements:
they are what the Wilson interval would be if 30 trials reproduced the observed
n=10 rates. See experiments/note.md.

Deliberately does not regenerate the covariate/runtime panels: those plot
per-trial means, which the projection leaves untouched, so they would be
pixel-identical to the published go_10x_* figures and only invite confusion.

The logistic fit and empirical crossover are imported from plot_threshold.py
rather than reimplemented, so the threshold maths stays single-sourced.

Usage:
    python3 experiments/plot_projection.py \
        experiments/count_threshold_C_10x_summary.csv \
        experiments/count_threshold_C_30x_projected_summary.csv
"""
from __future__ import annotations

import csv
import math
import os
import sys

try:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
    sys.exit(f"error: missing dependency '{exc.name}'.\n    pip install matplotlib numpy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_threshold import fit_logistic, interp_crossover  # noqa: E402

C_N10, C_N30, C_GRID = "#9aa5b1", "#1f6feb", "#d1495b"
NOTE = ("PROJECTION - not measured data. n=30 intervals show what the Wilson CI "
        "would be if 30 trials\nreproduced the observed n=10 success rates. "
        "Point estimates are unchanged by construction.")


def load_summary(path):
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "count": int(float(r["count"])),
                "n": int(r["n"]),
                "passes": int(r["passes"]),
                "success_rate": float(r["success_rate"]),
                "ci_lo": float(r["ci_lo"]),
                "ci_hi": float(r["ci_hi"]),
            })
    return sorted(rows, key=lambda r: -r["count"])


def _caption(fig, y):
    """Stamp the PROJECTION disclaimer below the axes.

    Placed at negative figure-y and relied on bbox_inches='tight' to grow the
    saved canvas around it, rather than reserving a band via tight_layout(rect=),
    which double-counts against tight's own padding and leaves a visible gap.
    """
    fig.text(0.5, y, NOTE, ha="center", va="top", fontsize=8, color="#8a6d1f",
             bbox=dict(boxstyle="round,pad=0.45", fc="#fff8e1", ec="#e0c56e"))


def _save(fig, outdir, stem):
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(outdir, f"{stem}.{ext}"), dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {os.path.join(outdir, stem)}.png (+ .svg)")


def bracket_50(rows):
    """The consecutive sampled counts straddling the 50% crossing.

    Everything between them is unsampled, so the threshold there rests on the
    fit's shape rather than on data. Trial count cannot narrow this gap -- only
    adding counts can -- which is why it is drawn separately from the CIs.
    """
    ordered = sorted(rows, key=lambda r: r["count"])
    for lo, hi in zip(ordered, ordered[1:]):
        if lo["success_rate"] <= 0.5 <= hi["success_rate"]:
            return lo["count"], hi["count"]
    return None


def derive_tag(path):
    """count_threshold_<tag>_summary.csv -> <tag> (mirrors plot_threshold.py)."""
    stem = os.path.basename(path)
    stem = stem[:-4] if stem.endswith(".csv") else stem
    if stem.endswith("_summary"):
        stem = stem[:-len("_summary")]
    return stem.replace("count_threshold", "").strip("_") or "projection"


def plot_success(r30, fit, cross, tag, label, outdir):
    c = np.array([r["count"] for r in r30], dtype=float)
    p = np.array([r["success_rate"] for r in r30])
    lo = np.array([r["ci_lo"] for r in r30])
    hi = np.array([r["ci_hi"] for r in r30])

    fig, ax = plt.subplots(figsize=(9, 5.9))

    br = bracket_50(r30)
    if br is not None:
        span = math.log2(br[1]) - math.log2(br[0])
        ax.axvspan(br[0], br[1], color="#f0b429", alpha=0.16, zorder=0,
                   label=f"unsampled gap around 50% ({span:.2f} log2 wide)")

    ax.errorbar(c, p, yerr=[p - lo, hi - p], fmt="o", ms=6, color=C_N30,
                ecolor=C_N10, capsize=3, zorder=3,
                label="success rate (projected 95% Wilson CI, n=30)")

    if fit is not None:
        a, b, thr = fit
        grid = np.linspace(math.log2(c.min()), math.log2(c.max()), 300)
        ax.plot(2.0 ** grid, 1.0 / (1.0 + np.exp(-(a + b * grid))), "-",
                color=C_GRID, lw=2, zorder=2, label="logistic fit")
        ax.axvline(thr, color=C_GRID, ls="--", lw=1.2,
                   label=f"fit 50% threshold = {thr:,.0f}")
    if cross is not None:
        ax.axvline(cross, color="#2e8540", ls=":", lw=1.4,
                   label=f"interpolated 50% = {cross:,.0f}")

    ax.axhline(0.5, color="#c0c0c0", lw=1, zorder=1)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("sample count (traces)  [log2 axis]")
    ax.set_ylabel("key-recovery success rate")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("AES cache-timing attack: success rate vs sample count\n"
                 f"({label}, n=30 PROJECTED from n=10)")
    ax.grid(True, which="both", ls=":", alpha=0.4)
    # 'best' rather than a fixed corner: the C curve saturates on the right so
    # lower-right is clear, but the Go curves are still rising there and would
    # sit under a pinned legend.
    ax.legend(loc="best", fontsize=9, framealpha=0.92)
    fig.tight_layout()
    _caption(fig, -0.02)
    _save(fig, outdir, f"{tag}_success_rate")


def plot_ci_compare(r10, r30, tag, label, outdir):
    """The money chart: how much the interval tightens, count by count."""
    by10 = {r["count"]: r for r in r10}
    counts = [r["count"] for r in r30]
    y = np.arange(len(counts))

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(13, 6.4), gridspec_kw={"width_ratios": [2.1, 1]})

    for i, r in enumerate(r30):
        a, b = by10[r["count"]], r
        ax1.plot([a["ci_lo"], a["ci_hi"]], [i + 0.16, i + 0.16], "-",
                 color=C_N10, lw=5, solid_capstyle="butt",
                 label="n=10 (measured)" if i == 0 else None)
        ax1.plot([b["ci_lo"], b["ci_hi"]], [i - 0.16, i - 0.16], "-",
                 color=C_N30, lw=5, solid_capstyle="butt",
                 label="n=30 (projected)" if i == 0 else None)
        ax1.plot(b["success_rate"], i, "|", color="#111", ms=13, mew=1.6,
                 zorder=4, label="success rate (identical)" if i == 0 else None)

    ax1.set_yticks(y, [f"{c:,}" for c in counts])
    ax1.invert_yaxis()
    ax1.set_xlim(-0.02, 1.02)
    ax1.set_xlabel("key-recovery success rate")
    ax1.set_ylabel("sample count (traces)")
    ax1.set_title("95% Wilson interval: n=10 vs projected n=30")
    ax1.grid(True, axis="x", ls=":", alpha=0.4)
    ax1.legend(loc="lower right", fontsize=9)

    w10 = np.array([by10[r["count"]]["ci_hi"] - by10[r["count"]]["ci_lo"] for r in r30])
    w30 = np.array([r["ci_hi"] - r["ci_lo"] for r in r30])
    ax2.barh(y + 0.19, w10, height=0.36, color=C_N10, label="n=10")
    ax2.barh(y - 0.19, w30, height=0.36, color=C_N30, label="n=30")
    ax2.set_yticks(y, [])
    ax2.invert_yaxis()
    ax2.set_xlabel("CI width")
    # Mean of the per-count ratios -- the same statistic note.md quotes. Not
    # w30.mean()/w10.mean(), which is a ratio of means and reads 0.50 here.
    ax2.set_title(f"width shrinks {np.mean(w30 / w10):.3f}x on average")
    ax2.grid(True, axis="x", ls=":", alpha=0.4)
    ax2.legend(loc="lower right", fontsize=9)

    fig.suptitle(f"{label}: tripling trials buys precision, "
                 "not a different threshold", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    _caption(fig, -0.03)
    _save(fig, outdir, f"{tag}_ci_compare")


def main(argv):
    if len(argv) not in (3, 4):
        sys.exit(f"usage: {argv[0]} <n10_summary.csv> <n30_projected_summary.csv> [label]")
    r10, r30 = load_summary(argv[1]), load_summary(argv[2])
    if [r["count"] for r in r10] != [r["count"] for r in r30]:
        sys.exit("error: the two summaries cover different sample counts")
    for a, b in zip(r10, r30):
        if abs(a["success_rate"] - b["success_rate"]) > 5e-5:
            sys.exit(f"error: count={a['count']} rates differ; not a pure projection")

    outdir = os.path.join(os.path.dirname(os.path.abspath(argv[2])), "plots")
    os.makedirs(outdir, exist_ok=True)
    tag = derive_tag(argv[2])
    label = argv[3] if len(argv) == 4 else tag

    if len(r30) < 6:
        print(f"  NOTE: only {len(r30)} sample counts in this sweep. More trials "
              "cannot compensate for a coarse\n        count grid -- the threshold "
              "estimate stays grid-limited. See note.md.")

    fit30, cross30 = fit_logistic(r30), interp_crossover(r30)
    plot_success(r30, fit30, cross30, tag, label, outdir)
    plot_ci_compare(r10, r30, tag, label, outdir)

    fit10, cross10 = fit_logistic(r10), interp_crossover(r10)
    print("\n  threshold estimates (should be ~unchanged -- that is the point):")
    for lbl, f, x in (("n=10 measured ", fit10, cross10),
                      ("n=30 projected", fit30, cross30)):
        fs = f"{f[2]:>9,.0f} (2^{math.log2(f[2]):.2f})" if f else "n/a"
        xs = f"{x:>9,.0f} (2^{math.log2(x):.2f})" if x else "n/a"
        print(f"    {lbl}  logistic {fs}   interpolated {xs}")


if __name__ == "__main__":
    main(sys.argv)
