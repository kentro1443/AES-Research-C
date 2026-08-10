#!/usr/bin/env python3
"""plot_dials.py -- analyse a dial sweep (-repeat and -evict-kb) and draw curves.

Companion to ``plot_threshold.py``. Reads a results CSV from ``dial_sweep.sh``
(one row per ``(sweep, dial value, trial)`` at a fixed sample count) and plots
key-recovery success rate against each of the two "dials" the attacker can turn
without changing the trace count:

  * -repeat   : encryptions summed per sample (noise averaging)
  * -evict-kb : cache-flush buffer size (signal strength)

Each point gets a 95% Wilson confidence interval, same as the count study.

Usage:
    pip install matplotlib numpy
    python3 experiments/plot_dials.py experiments/dial_sweep_10x_results.csv

Outputs:
    <prefix>_summary.csv                aggregated per-(sweep,value) table
    plots/<tag>_dials.{png,svg}         two-panel repeat / evict success curves
"""
from __future__ import annotations

import csv
import math
import os
import sys
from collections import defaultdict

try:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:  # pragma: no cover
    sys.exit(
        f"error: missing dependency '{exc.name}'.\n"
        "    pip install matplotlib numpy"
    )

Z95 = 1.959963984540054


def wilson_interval(k, n, z=Z95):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    # The Wilson interval always brackets p; clamp so floating-point error at
    # p=0 / p=1 (where the bound equals p analytically) can't invert them.
    return (min(p, max(0.0, center - half)), max(p, min(1.0, center + half)))


def load_rows(path):
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"sweep", "repeat", "evict_kb", "result"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"error: {path} missing column(s): {', '.join(sorted(missing))}")
        return list(reader)


def aggregate(rows):
    """Return {sweep: [records sorted by value]}; value is repeat or evict_kb."""
    buckets = defaultdict(list)  # (sweep, value) -> [rows]
    for r in rows:
        sweep = r.get("sweep", "").strip()
        if sweep not in ("repeat", "evict"):
            continue
        key = r["repeat"] if sweep == "repeat" else r["evict_kb"]
        try:
            value = int(float(key))
        except ValueError:
            continue
        buckets[(sweep, value)].append(r)

    by_sweep = defaultdict(list)
    for (sweep, value), trials in buckets.items():
        n = len(trials)
        passes = sum(1 for t in trials if t.get("result", "").strip().upper() == "PASS")
        lo, hi = wilson_interval(passes, n)
        by_sweep[sweep].append({
            "sweep": sweep, "value": value, "n": n, "passes": passes,
            "success_rate": passes / n if n else 0.0, "ci_lo": lo, "ci_hi": hi,
        })
    for sweep in by_sweep:
        by_sweep[sweep].sort(key=lambda r: r["value"])
    return by_sweep


def _panel(ax, recs, xlabel, title, color, logx):
    x = np.array([r["value"] for r in recs], dtype=float)
    rate = np.array([r["success_rate"] for r in recs])
    lo = np.array([r["ci_lo"] for r in recs])
    hi = np.array([r["ci_hi"] for r in recs])
    ax.errorbar(x, rate, yerr=[rate - lo, hi - rate], fmt="o-", ms=6,
                color=color, ecolor="#9aa5b1", capsize=3)
    ax.axhline(0.5, color="#c0c0c0", lw=1)
    if logx:
        ax.set_xscale("log", base=2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("key-recovery success rate")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title(title)
    ax.grid(True, which="both", ls=":", alpha=0.4)


def plot_dials(by_sweep, tag, outdir, fixed_count):
    have = [s for s in ("repeat", "evict") if by_sweep.get(s)]
    if not have:
        sys.exit("error: no repeat/evict rows to plot")
    fig, axes = plt.subplots(1, len(have), figsize=(6 * len(have), 5), squeeze=False)
    for ax, sweep in zip(axes[0], have):
        if sweep == "repeat":
            _panel(ax, by_sweep["repeat"], "-repeat (encryptions summed / sample)",
                   "Success vs -repeat (noise averaging)", "#1f6feb", logx=False)
        else:
            _panel(ax, by_sweep["evict"], "-evict-kb (cache-flush buffer, KiB)",
                   "Success vs -evict-kb (signal strength)", "#d1495b", logx=True)
    suffix = f" at count={fixed_count:,}" if fixed_count else ""
    fig.suptitle(f"AES cache-timing attack: dial sensitivity{suffix}")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(outdir, f"{tag}_dials.{ext}"), dpi=140, bbox_inches="tight")
    plt.close(fig)


def write_summary_csv(by_sweep, path):
    cols = ["sweep", "value", "n", "passes", "success_rate", "ci_lo", "ci_hi"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for sweep in ("repeat", "evict"):
            for r in by_sweep.get(sweep, []):
                w.writerow({k: (f"{r[k]:.4f}" if isinstance(r[k], float) else r[k])
                            for k in cols})


def print_table(by_sweep):
    for sweep in ("repeat", "evict"):
        recs = by_sweep.get(sweep)
        if not recs:
            continue
        label = "-repeat" if sweep == "repeat" else "-evict-kb"
        print(f"\n  {label} sweep:")
        print(f"  {'value':>8}  {'n':>3}  {'pass':>4}  {'rate':>6}  {'95% CI':>15}")
        print("  " + "-" * 44)
        for r in recs:
            print(f"  {r['value']:>8}  {r['n']:>3}  {r['passes']:>4}  "
                  f"{r['success_rate']*100:>5.0f}%  "
                  f"[{r['ci_lo']*100:>4.0f}%,{r['ci_hi']*100:>4.0f}%]")


def main(argv):
    if len(argv) != 2:
        sys.exit(f"usage: {argv[0]} <dial_sweep_*_results.csv>")
    csv_path = argv[1]
    if not os.path.isfile(csv_path):
        sys.exit(f"error: no such file: {csv_path}")

    rows = load_rows(csv_path)
    by_sweep = aggregate(rows)
    if not by_sweep:
        sys.exit("error: no usable repeat/evict rows in CSV")

    fixed_count = 0
    for r in rows:
        try:
            fixed_count = int(float(r.get("count", "0")))
            break
        except ValueError:
            continue

    base = os.path.basename(csv_path)
    stem = base[:-4] if base.endswith(".csv") else base
    if stem.endswith("_results"):
        stem = stem[:-len("_results")]
    tag = stem.replace("dial_sweep", "").strip("_") or "dial"

    exp_dir = os.path.dirname(os.path.abspath(csv_path))
    outdir = os.path.join(exp_dir, "plots")
    os.makedirs(outdir, exist_ok=True)

    plot_dials(by_sweep, tag, outdir, fixed_count)
    summary_path = os.path.join(exp_dir, f"{stem}_summary.csv")
    write_summary_csv(by_sweep, summary_path)

    print_table(by_sweep)
    print(f"\n  summary CSV : {summary_path}")
    print(f"  plots       : {outdir}/{tag}_dials.png (+ .svg)")


if __name__ == "__main__":
    main(sys.argv)
