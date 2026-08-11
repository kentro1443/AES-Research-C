#!/usr/bin/env python3
"""plot_compare.py -- overlay recovery curves from several count-threshold runs.

Draws the cross-language comparison figure: C vs Go(GC on) vs Go(GC off) on one
psychometric axis (points + 95% Wilson CIs + logistic fit per series), beside an
N50 panel that states the threshold separation directly.

Uses MEASURED per-trial data (n=10), not the n=30 projection. The projection
leaves every point estimate untouched, so this comparison is identical either
way and is better drawn from real trials -- no PROJECTION caveat needed. See
experiments/note.md.

Reuses the aggregation / Wilson / logistic-fit code in plot_threshold.py so the
numbers here are identical to the per-run analysis.

Usage:
    python3 experiments/plot_compare.py \
        C=experiments/count_threshold_go_10x_results.csv \
        "Go (GC on)=experiments/count_threshold_go_count_results.csv" \
        "Go (GC off)=experiments/count_threshold_go_gcoff_count_results.csv"

Pass --projected with the *_30x_projected_summary.csv files to draw the same
comparison at the projected n=30. That variant is stamped with a caution banner
and a diagonal watermark, and writes to a separate filename. Passing a file whose
name contains "projected" without the flag is a hard error, so the projection can
never be rendered as if it were measured.

Output:
    experiments/plots/cross_language_recovery.{png,svg}
    experiments/plots/cross_language_recovery_30x_projected.{png,svg}   (--projected)
"""
from __future__ import annotations

import math
import os
import sys

import csv

import plot_threshold as pt  # same directory; reuse its maths
from plot_projection import load_summary  # owns reading projected summaries

try:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:  # pragma: no cover
    sys.exit(f"error: missing dependency '{exc.name}': pip install matplotlib numpy")

# Categorical series palette, assigned in fixed order (never cycled).
# Validated all-pairs: worst CVD separation dE 9.2 (deutan) / 10.0 (tritan),
# normal-vision 15.7, contrast >= 3:1 against a white surface. The previous
# green (#2e8540) failed CVD against the red at dE 6.0 -- which mattered
# precisely here, because Go(GC on) and Go(GC off) are the two curves a reader
# most needs to tell apart and they very nearly coincide.
PALETTE = ["#1f6feb", "#d1495b", "#c47f00", "#9b5de5", "#00857a"]
# Secondary encoding so identity never rests on hue alone (print / CVD).
# Marker shape only: every curve is drawn solid. Dashing some series would read
# as "extrapolated / less certain", but all three curves are the same kind of
# logistic fit over equally real measurements. Dashes are reserved for the
# vertical threshold rules, which genuinely are annotation rather than data.
MARKERS = ["o", "s", "^", "D", "v"]

INK, INK_MUTED = "#1a1a1a", "#5c6670"

CAUTION_TITLE = "CAUTION — PROJECTED, NOT MEASURED DATA"
CAUTION_BODY = (
    "No 30-trial runs were performed. Each success rate is the observed n=10 value held fixed; "
    "only the 95% Wilson intervals are\nrecomputed at n=30. Point estimates — and all three N50 "
    "thresholds — are therefore unchanged from the measured figure.\n"
    "Do not cite this as a 30-trial experiment. See experiments/note.md."
)


def load_any(path):
    """Load a per-trial results CSV or an already-aggregated summary CSV.

    Projections only exist as summaries. Expanding one into synthetic PASS/FAIL
    rows so the per-trial loader could eat it would produce a file
    indistinguishable from a real 30-trial run, so the summary is read directly.
    """
    with open(path, newline="") as fh:
        fields = set(csv.DictReader(fh).fieldnames or [])
    if "result" in fields:
        return pt.aggregate(pt.load_rows(path))
    if {"count", "n", "passes", "success_rate", "ci_lo", "ci_hi"} <= fields:
        return load_summary(path)
    sys.exit(f"error: {path} is neither a results CSV (needs 'result') nor a "
             f"summary CSV (needs count/n/passes/success_rate/ci_lo/ci_hi)")


def draw_curves(ax, series):
    """Main panel: success rate vs sample count, one series per implementation."""
    n = len(series)
    for i, (label, rows, fit) in enumerate(series):
        colour, marker = PALETTE[i % len(PALETTE)], MARKERS[i % len(MARKERS)]
        counts = np.array([r["count"] for r in rows], dtype=float)
        rate = np.array([r["success_rate"] for r in rows])
        lo = np.array([r["ci_lo"] for r in rows])
        hi = np.array([r["ci_hi"] for r in rows])

        # Nudge each series along the log axis so coincident points and their
        # error bars stay separable -- C and Go(GC on) share all 17 counts.
        dodge = 2.0 ** ((i - (n - 1) / 2.0) * 0.020)

        ax.errorbar(counts * dodge, rate, yerr=[rate - lo, hi - rate],
                    fmt=marker, ms=5.5, color=colour, ecolor=colour, alpha=0.75,
                    elinewidth=1.1, capsize=2.5, ls="none", zorder=3,
                    markeredgecolor="white", markeredgewidth=0.6)

        if fit is not None:
            a, b, thr = fit
            # Draw each fit only across the counts that series actually sampled.
            # (The previous version accumulated the range across series, which
            # extrapolated the GC-off curve down past its lowest sampled count.)
            grid = np.linspace(math.log2(counts.min()), math.log2(counts.max()), 300)
            ax.plot(2.0 ** grid, 1.0 / (1.0 + np.exp(-(a + b * grid))),
                    ls="-", color=colour, lw=2.0, alpha=0.95, zorder=2)
            # 50% threshold marker. Deliberately dashed for every series rather
            # than following the series line style: a solid vertical rule reads
            # as data, and these are annotation.
            ax.axvline(thr, color=colour, ls=(0, (5, 3)), lw=1.3, alpha=0.6, zorder=1)

    ax.axhline(0.5, color="#c8ccd0", lw=1, zorder=0)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("sample count (traces)  [log2 axis]")
    ax.set_ylabel("key-recovery success rate")
    ax.set_ylim(-0.04, 1.04)
    ax.grid(True, which="both", ls=":", alpha=0.35)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    # The threshold is stated in the legend, beside the dashed marker that shows
    # where it falls -- no separate panel needed.
    handles = []
    for i, (lbl, _rows, fit) in enumerate(series):
        text = f"{lbl}  (N50 ≈ {fit[2]:,.0f})" if fit is not None else lbl
        handles.append(plt.Line2D([], [], color=PALETTE[i % len(PALETTE)],
                                  marker=MARKERS[i % len(MARKERS)],
                                  ls="-", lw=2.0, ms=6,
                                  markeredgecolor="white", markeredgewidth=0.6,
                                  label=text))
    ax.legend(handles=handles, loc="upper left", fontsize=9.5, framealpha=0.93)


def main(argv):
    specs = [a for a in argv[1:] if a != "--projected"]
    projected = "--projected" in argv[1:]
    if not specs:
        sys.exit(f"usage: {argv[0]} [--projected] LABEL=path.csv [LABEL=path.csv ...]")

    series = []
    for spec in specs:
        if "=" not in spec:
            sys.exit(f"error: expected LABEL=path.csv, got '{spec}'")
        label, path = spec.split("=", 1)
        if not os.path.isfile(path):
            sys.exit(f"error: no such file: {path}")
        # Fail closed: a projected input must never render without the caution.
        if "projected" in os.path.basename(path) and not projected:
            sys.exit(f"error: {path} looks like a projection but --projected was "
                     "not passed; refusing to draw it without the caution banner")
        rows = load_any(path)
        if not rows:
            sys.exit(f"error: no usable rows in {path}")
        series.append((label.strip(), rows, pt.fit_logistic(rows)))

    fig, ax = plt.subplots(figsize=(11, 6.3))
    draw_curves(ax, series)

    ns = sorted({r["n"] for _l, rows, _f in series for r in rows})
    title = "AES cache-timing key recovery: trace threshold by implementation"
    if projected:
        title += f"  —  PROJECTED to n={'/'.join(str(x) for x in ns)}"
    fig.suptitle(title, fontsize=13.5, color=INK)

    if projected:
        # Diagonal watermark behind the curves: survives cropping and screenshots
        # in a way a footnote does not.
        ax.text(0.5, 0.5, "PROJECTED\nNOT MEASURED", transform=ax.transAxes,
                ha="center", va="center", fontsize=40, color="#b3541e",
                alpha=0.13, rotation=22, weight="bold", zorder=0)

    fig.tight_layout(rect=(0, 0 if projected else 0.045, 1, 0.955))
    grids = ", ".join(f"{lbl} {len(rows)}" for lbl, rows, _f in series)
    provenance = (
        "Vertical lines mark each series' 50% threshold (N50). Error bars are 95% Wilson "
        "intervals; curves are logistic fits over each\nseries' own sampled range. Series are "
        "nudged +-2% horizontally so coincident points stay separable.  "
        f"Sample counts per series: {grids}."
    )
    if projected:
        # Hung below the axes at negative figure-y so bbox_inches='tight' grows the
        # canvas around them. Reserving a band with tight_layout(rect=) instead
        # lets the box's opaque facecolor paint over the heading.
        fig.text(0.5, -0.025, CAUTION_TITLE, ha="center", va="top", fontsize=12,
                 color="#8a3a12", weight="bold")
        fig.text(0.5, -0.075, CAUTION_BODY + "\n\n" + provenance, ha="center",
                 va="top", fontsize=8, color="#7a4a20",
                 bbox=dict(boxstyle="round,pad=0.6", fc="#fdf3e3", ec="#d4a24c", lw=1.4))
    else:
        fig.text(0.5, 0.012,
                 f"Measured data, n={'/'.join(str(x) for x in ns)} trials per sample count. "
                 + provenance, ha="center", va="bottom", fontsize=8, color=INK_MUTED)

    stem = "cross_language_recovery" + ("_30x_projected" if projected else "")
    outdir = os.path.join(os.path.dirname(os.path.abspath(specs[0].split("=", 1)[1])), "plots")
    os.makedirs(outdir, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(outdir, f"{stem}.{ext}"), dpi=140, bbox_inches="tight")
    plt.close(fig)

    print(f"wrote {outdir}/{stem}.png (+ .svg)")
    base = next((f[2] for _l, _r, f in series if f is not None), None)
    for label, rows, fit in series:
        if fit:
            print(f"  {label:<14} N50 = {fit[2]:>9,.0f}  (2^{math.log2(fit[2]):.2f})"
                  f"  = {fit[2]/base:.2f}x  [{len(rows)} counts, n={rows[0]['n']}]")


if __name__ == "__main__":
    main(sys.argv)
