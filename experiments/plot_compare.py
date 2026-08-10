#!/usr/bin/env python3
"""plot_compare.py -- overlay recovery curves from several count-threshold runs.

Draws one success-rate-vs-count psychometric plot with multiple implementations
on the same axes (points + 95% Wilson CIs + logistic fit + 50% threshold marker
per series). This is the cross-language comparison figure: C vs Go(GC on) vs
Go(GC off), showing how far apart their trace thresholds sit.

Reuses the aggregation / Wilson / logistic-fit code in plot_threshold.py so the
numbers here are identical to the per-run analysis.

Usage:
    python3 experiments/plot_compare.py \
        C=experiments/count_threshold_go_10x_results.csv \
        "Go (GC on)=experiments/count_threshold_go_count_results.csv" \
        "Go (GC off)=experiments/count_threshold_go_gcoff_count_results.csv"

Output:
    experiments/plots/cross_language_recovery.{png,svg}
"""
from __future__ import annotations

import math
import os
import sys

import plot_threshold as pt  # same directory; reuse its maths

try:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:  # pragma: no cover
    sys.exit(f"error: missing dependency '{exc.name}': pip install matplotlib numpy")

# Distinct, colour-blind-friendly series colours.
PALETTE = ["#1f6feb", "#d1495b", "#2e8540", "#9b5de5", "#e08e00"]


def main(argv):
    if len(argv) < 2:
        sys.exit(f"usage: {argv[0]} LABEL=path.csv [LABEL=path.csv ...]")

    series = []
    for spec in argv[1:]:
        if "=" not in spec:
            sys.exit(f"error: expected LABEL=path.csv, got '{spec}'")
        label, path = spec.split("=", 1)
        if not os.path.isfile(path):
            sys.exit(f"error: no such file: {path}")
        rows = pt.aggregate(pt.load_rows(path))
        if not rows:
            sys.exit(f"error: no usable rows in {path}")
        series.append((label.strip(), rows, pt.fit_logistic(rows)))

    fig, ax = plt.subplots(figsize=(10, 6))
    all_counts = []
    for i, (label, rows, fit) in enumerate(series):
        colour = PALETTE[i % len(PALETTE)]
        counts = np.array([r["count"] for r in rows], dtype=float)
        rate = np.array([r["success_rate"] for r in rows])
        lo = np.array([r["ci_lo"] for r in rows])
        hi = np.array([r["ci_hi"] for r in rows])
        all_counts.extend(counts.tolist())

        n50 = fit[2] if fit else None
        lbl = f"{label}" + (f"  (N50 ≈ {n50:,.0f})" if n50 else "")
        ax.errorbar(counts, rate, yerr=[rate - lo, hi - rate], fmt="o", ms=6,
                    color=colour, ecolor=colour, alpha=0.9, capsize=3, zorder=3,
                    label=lbl)
        if fit is not None:
            a, b, thr = fit
            grid = np.linspace(math.log2(min(all_counts)), math.log2(max(all_counts)), 300)
            curve = 1.0 / (1.0 + np.exp(-(a + b * grid)))
            ax.plot(2.0 ** grid, curve, "-", color=colour, lw=2, alpha=0.85, zorder=2)
            ax.axvline(thr, color=colour, ls="--", lw=1.0, alpha=0.7, zorder=1)

    ax.axhline(0.5, color="#c0c0c0", lw=1, zorder=0)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("sample count (traces)  [log₂ axis]")
    ax.set_ylabel("key-recovery success rate")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("Cross-language recovery: trace threshold by implementation")
    ax.grid(True, which="both", ls=":", alpha=0.4)
    ax.legend(loc="lower right", fontsize=9)

    outdir = os.path.join(os.path.dirname(os.path.abspath(argv[1].split("=", 1)[1])), "plots")
    os.makedirs(outdir, exist_ok=True)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(outdir, f"cross_language_recovery.{ext}"),
                    dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {outdir}/cross_language_recovery.png (+ .svg)")
    for label, _rows, fit in series:
        if fit:
            print(f"  {label:<14} N50 = {fit[2]:,.0f}  (2^{math.log2(fit[2]):.2f})")


if __name__ == "__main__":
    main(sys.argv)
