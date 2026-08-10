#!/usr/bin/env python3
"""plot_threshold.py -- analyse a count-threshold sweep and draw the curves.

Reads a results CSV produced by ``count_threshold_sweep.sh`` (one row per
``(count, trial)``) and turns it into the headline research artifact: a
success-rate-vs-sample-count *psychometric curve* with 95% Wilson confidence
intervals and a fitted logistic model whose 50% crossover is the estimated
"trace threshold". Also plots the supporting evidence (min_time, score, run
time vs count) and writes an aggregated per-count summary CSV.

Why a fitted curve: real timing is noisy, so each count has a *probability* of
recovering the key, not a yes/no. The threshold is where that probability
crosses 50%; fitting lets us read it off between the sampled counts instead of
guessing.

Usage:
    pip install matplotlib numpy      # one-time (not bundled with the lab)
    python3 experiments/plot_threshold.py experiments/count_threshold_10x_results.csv

Outputs (next to the CSV / under experiments/plots/):
    <prefix>_summary.csv                     aggregated per-count table
    plots/<tag>_success_rate.{png,svg}       the psychometric curve
    plots/<tag>_covariates.{png,svg}         min_time & score vs count (flat)
    plots/<tag>_runtime.{png,svg}            wall-time vs count (linear)
Stdlib only for parsing; matplotlib + numpy for the maths/plots.
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
    matplotlib.use("Agg")  # headless: write files, never open a window
    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
    sys.exit(
        f"error: missing dependency '{exc.name}'.\n"
        "This analysis needs matplotlib + numpy:\n"
        "    pip install matplotlib numpy"
    )

Z95 = 1.959963984540054  # standard normal 97.5th percentile


# --------------------------------------------------------------------------- #
# Loading & aggregation
# --------------------------------------------------------------------------- #
def _num(value):
    """Parse a CSV cell to float, tolerating the harness 'NA' sentinel."""
    if value is None:
        return math.nan
    value = value.strip()
    if value == "" or value.upper() == "NA":
        return math.nan
    try:
        return float(value)
    except ValueError:
        return math.nan


def load_rows(path):
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"count", "result"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"error: {path} is missing column(s): {', '.join(sorted(missing))}")
        return list(reader)


def wilson_interval(k, n, z=Z95):
    """95% Wilson score interval for k successes in n Bernoulli trials."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    # The Wilson interval always brackets p; clamp so floating-point error at
    # p=0 / p=1 (where the bound equals p analytically) can't invert them.
    return (min(p, max(0.0, center - half)), max(p, min(1.0, center + half)))


def aggregate(rows):
    """Collapse per-trial rows into one record per count."""
    by_count = defaultdict(list)
    for r in rows:
        try:
            c = int(float(r["count"]))
        except (ValueError, KeyError):
            continue
        by_count[c].append(r)

    out = []
    for count in sorted(by_count, reverse=True):
        trials = by_count[count]
        n = len(trials)
        passes = sum(1 for t in trials if t.get("result", "").strip().upper() == "PASS")
        rate = passes / n if n else 0.0
        lo, hi = wilson_interval(passes, n)
        secs = [_num(t.get("seconds")) for t in trials]
        mint = [_num(t.get("min_time")) for t in trials]
        score = [_num(t.get("score")) for t in trials]
        out.append({
            "count": count,
            "n": n,
            "passes": passes,
            "success_rate": rate,
            "ci_lo": lo,
            "ci_hi": hi,
            "mean_seconds": _nanmean(secs),
            "median_seconds": _nanmedian(secs),
            "mean_min_time": _nanmean(mint),
            "mean_score": _nanmean(score),
        })
    return out


def _nanmean(xs):
    xs = [x for x in xs if not math.isnan(x)]
    return sum(xs) / len(xs) if xs else math.nan


def _nanmedian(xs):
    xs = sorted(x for x in xs if not math.isnan(x))
    if not xs:
        return math.nan
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


# --------------------------------------------------------------------------- #
# Logistic (psychometric) fit:  P(success) = sigmoid(a + b * log2(count))
# --------------------------------------------------------------------------- #
def fit_logistic(rows):
    """IRLS logistic regression on trial-level 0/1 outcomes.

    Feature x = log2(count). Returns (a, b, threshold_count) or None if the fit
    is unusable. A tiny ridge term keeps perfectly separated data (all-pass at
    the top, all-fail at the bottom) from blowing up.
    """
    xs, ys = [], []
    for r in rows:
        x = math.log2(r["count"])
        for _ in range(r["passes"]):
            xs.append(x); ys.append(1.0)
        for _ in range(r["n"] - r["passes"]):
            xs.append(x); ys.append(0.0)
    if len(set(xs)) < 2 or not (0 < sum(ys) < len(ys)):
        return None

    X = np.column_stack([np.ones(len(xs)), np.array(xs)])
    y = np.array(ys)
    beta = np.zeros(2)
    ridge = 1e-4 * np.eye(2)
    for _ in range(100):
        eta = X @ beta
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1 - p), 1e-9, None)
        # Newton / IRLS step with a small ridge for numerical stability.
        H = X.T @ (X * w[:, None]) + ridge
        grad = X.T @ (y - p) - ridge @ beta
        try:
            step = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            return None
        beta = beta + step
        if np.max(np.abs(step)) < 1e-8:
            break
    a, b = float(beta[0]), float(beta[1])
    if abs(b) < 1e-9:
        return None
    threshold = 2.0 ** (-a / b)  # x where sigmoid = 0.5
    return a, b, threshold


def interp_crossover(rows):
    """Empirical 50% crossover by linear interpolation in log2(count) space,
    independent of the model -- a sanity check on the logistic threshold."""
    ordered = sorted(rows, key=lambda r: r["count"])
    for lo, hi in zip(ordered, ordered[1:]):
        if lo["success_rate"] <= 0.5 <= hi["success_rate"]:
            x0, y0 = math.log2(lo["count"]), lo["success_rate"]
            x1, y1 = math.log2(hi["count"]), hi["success_rate"]
            if y1 == y0:
                return lo["count"]
            x = x0 + (0.5 - y0) * (x1 - x0) / (y1 - y0)
            return 2.0 ** x
    return None


# --------------------------------------------------------------------------- #
# Plotting
# --------------------------------------------------------------------------- #
def plot_success(rows, fit, cross, tag, outdir):
    counts = np.array([r["count"] for r in rows], dtype=float)
    rate = np.array([r["success_rate"] for r in rows])
    lo = np.array([r["ci_lo"] for r in rows])
    hi = np.array([r["ci_hi"] for r in rows])

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.errorbar(counts, rate, yerr=[rate - lo, hi - rate], fmt="o", ms=6,
                color="#1f6feb", ecolor="#9aa5b1", capsize=3, zorder=3,
                label="observed success rate (95% Wilson CI)")

    if fit is not None:
        a, b, thr = fit
        grid = np.linspace(math.log2(counts.min()), math.log2(counts.max()), 300)
        curve = 1.0 / (1.0 + np.exp(-(a + b * grid)))
        ax.plot(2.0 ** grid, curve, "-", color="#d1495b", lw=2,
                label="logistic fit", zorder=2)
        ax.axvline(thr, color="#d1495b", ls="--", lw=1.2,
                   label=f"fit 50% threshold ≈ {thr:,.0f}")
    if cross is not None:
        ax.axvline(cross, color="#2e8540", ls=":", lw=1.2,
                   label=f"interpolated 50% ≈ {cross:,.0f}")

    ax.axhline(0.5, color="#c0c0c0", lw=1, zorder=1)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("sample count (traces)  [log₂ axis]")
    ax.set_ylabel("key-recovery success rate")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("AES cache-timing attack: success rate vs sample count")
    ax.grid(True, which="both", ls=":", alpha=0.4)
    ax.legend(loc="lower right", fontsize=9)
    _save(fig, outdir, f"{tag}_success_rate")


def plot_covariates(rows, tag, outdir):
    counts = np.array([r["count"] for r in rows], dtype=float)
    mint = np.array([r["mean_min_time"] for r in rows])
    score = np.array([r["mean_score"] for r in rows])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(counts, mint, "o-", color="#1f6feb")
    ax1.set_xscale("log", base=2)
    ax1.set_xlabel("sample count [log₂]")
    ax1.set_ylabel("mean min_time (ticks)")
    ax1.set_title("min_time is flat → knee is statistical")
    ax1.grid(True, which="both", ls=":", alpha=0.4)

    ax2.plot(counts, score, "o-", color="#d1495b")
    ax2.set_xscale("log", base=2)
    ax2.set_xlabel("sample count [log₂]")
    ax2.set_ylabel("mean attack score")
    ax2.set_title("score is flat → per-sample leak unchanged")
    ax2.grid(True, which="both", ls=":", alpha=0.4)
    fig.suptitle("Supporting evidence: the threshold is an averaging effect, "
                 "not a signal cliff")
    _save(fig, outdir, f"{tag}_covariates")


def plot_runtime(rows, tag, outdir):
    counts = np.array([r["count"] for r in rows], dtype=float)
    secs = np.array([r["mean_seconds"] for r in rows])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(counts, secs, "o-", color="#2e8540")
    ax.set_xlabel("sample count (traces)")
    ax.set_ylabel("mean wall time per run (s)")
    ax.set_title("Collection cost scales linearly with sample count")
    ax.grid(True, ls=":", alpha=0.4)
    _save(fig, outdir, f"{tag}_runtime")


def _save(fig, outdir, stem):
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(outdir, f"{stem}.{ext}"), dpi=140, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Output tables
# --------------------------------------------------------------------------- #
def write_summary_csv(rows, path):
    cols = ["count", "n", "passes", "success_rate", "ci_lo", "ci_hi",
            "mean_seconds", "median_seconds", "mean_min_time", "mean_score"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.4f}" if isinstance(r[k], float) else r[k])
                        for k in cols})


def print_table(rows, fit, cross):
    print(f"\n{'count':>8}  {'n':>3}  {'pass':>4}  {'rate':>6}  "
          f"{'95% CI':>15}  {'s/run':>7}")
    print("  " + "-" * 52)
    for r in rows:
        print(f"{r['count']:>8}  {r['n']:>3}  {r['passes']:>4}  "
              f"{r['success_rate']*100:>5.0f}%  "
              f"[{r['ci_lo']*100:>4.0f}%,{r['ci_hi']*100:>4.0f}%]  "
              f"{r['mean_seconds']:>7.0f}")
    print()
    if fit is not None:
        _, _, thr = fit
        print(f"  logistic-fit 50% threshold : {thr:,.0f} traces "
              f"(≈ 2^{math.log2(thr):.2f})")
    if cross is not None:
        print(f"  interpolated 50% crossover : {cross:,.0f} traces "
              f"(≈ 2^{math.log2(cross):.2f})")
    if fit is None and cross is None:
        print("  (no 50% crossover in the sampled range)")


# --------------------------------------------------------------------------- #
def main(argv):
    if len(argv) != 2:
        sys.exit(f"usage: {argv[0]} <count_threshold_*_results.csv>")
    csv_path = argv[1]
    if not os.path.isfile(csv_path):
        sys.exit(f"error: no such file: {csv_path}")

    rows = aggregate(load_rows(csv_path))
    if not rows:
        sys.exit("error: no usable rows in CSV")

    fit = fit_logistic(rows)
    cross = interp_crossover(rows)

    # Derive a tag from the filename: count_threshold_<tag>_results.csv -> <tag>
    base = os.path.basename(csv_path)
    stem = base[:-4] if base.endswith(".csv") else base
    if stem.endswith("_results"):
        stem = stem[:-len("_results")]
    tag = stem.replace("count_threshold", "").strip("_") or "count"

    exp_dir = os.path.dirname(os.path.abspath(csv_path))
    outdir = os.path.join(exp_dir, "plots")
    os.makedirs(outdir, exist_ok=True)

    plot_success(rows, fit, cross, tag, outdir)
    plot_covariates(rows, tag, outdir)
    plot_runtime(rows, tag, outdir)

    summary_path = os.path.join(exp_dir, f"{stem}_summary.csv")
    write_summary_csv(rows, summary_path)

    print_table(rows, fit, cross)
    print(f"  summary CSV : {summary_path}")
    print(f"  plots       : {outdir}/{tag}_*.png (+ .svg)")


if __name__ == "__main__":
    main(sys.argv)
