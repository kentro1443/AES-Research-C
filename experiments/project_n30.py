#!/usr/bin/env python3
"""
project_n30.py -- rescale the n=10 count-threshold summary to n=30.

This does NOT invent new trial outcomes. It holds each threshold's observed
success rate fixed and recomputes the Wilson score 95% CI at n=30, i.e. it
answers "how much tighter would the interval be if 30 trials reproduced the
same rate?". Point estimates are unchanged by construction; only precision
moves. Timing columns are per-trial means, whose expectation does not depend
on n, so they carry over unchanged.

Estimator verified against the source file: Wilson score, z = 1.959964.
"""
import csv
import math
import sys

Z = 1.959963984540054  # two-sided 95% normal quantile


def wilson(k, n, z=Z):
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return max(0.0, center - half), min(1.0, center + half)


def main(src, dst, n_new=30):
    with open(src, newline="") as fh:
        rows = list(csv.DictReader(fh))

    # --- validate that the source CIs really are Wilson, before trusting the port
    for r in rows:
        n, k = int(r["n"]), int(r["passes"])
        lo, hi = wilson(k, n)
        if abs(lo - float(r["ci_lo"])) > 5e-5 or abs(hi - float(r["ci_hi"])) > 5e-5:
            sys.exit(
                f"ABORT: count={r['count']} source CI [{r['ci_lo']},{r['ci_hi']}] "
                f"!= Wilson [{lo:.4f},{hi:.4f}]; estimator assumption is wrong."
            )

    out = []
    for r in rows:
        n_old, k_old = int(r["n"]), int(r["passes"])
        rate = k_old / n_old
        k_new = rate * n_new
        if abs(k_new - round(k_new)) > 1e-9:
            sys.exit(f"ABORT: count={r['count']} rate {rate} not exact at n={n_new}")
        k_new = int(round(k_new))
        lo, hi = wilson(k_new, n_new)
        lo_old, hi_old = float(r["ci_lo"]), float(r["ci_hi"])
        out.append({
            "count": r["count"],
            "n": n_new,
            "passes": k_new,
            "success_rate": f"{rate:.4f}",
            "ci_lo": f"{lo:.4f}",
            "ci_hi": f"{hi:.4f}",
            "mean_seconds": r["mean_seconds"],
            "median_seconds": r["median_seconds"],
            "mean_min_time": r["mean_min_time"],
            "mean_score": r["mean_score"],
            "ci_width_n10": f"{hi_old - lo_old:.4f}",
            "ci_width_n30": f"{hi - lo:.4f}",
            "ci_width_ratio": f"{(hi - lo) / (hi_old - lo_old):.4f}",
        })

    with open(dst, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    # console view
    hdr = f"{'count':>7} {'k/n':>6} {'rate':>6}  {'n=10 CI':>16}  {'n=30 CI':>16}  {'width x':>7}"
    print(hdr)
    print("-" * len(hdr))
    for o, r in zip(out, rows):
        print(f"{o['count']:>7} {o['passes']:>3}/{o['n']:<2} {o['success_rate']:>6}  "
              f"[{float(r['ci_lo']):.4f},{float(r['ci_hi']):.4f}]  "
              f"[{float(o['ci_lo']):.4f},{float(o['ci_hi']):.4f}]  "
              f"{o['ci_width_ratio']:>7}")

    widths = [float(o["ci_width_ratio"]) for o in out]
    print(f"\nmean CI-width ratio (n=30 / n=10): {sum(widths)/len(widths):.4f}")

    # projected sweep cost: 20 additional trials over every count
    per_pass = sum(float(r["mean_seconds"]) for r in rows)
    print(f"one full pass (1 trial x all counts): {per_pass:.0f} s = {per_pass/3600:.2f} h")
    print(f"+20 trials  : {per_pass*20/3600:.1f} h")
    print(f"30 from zero: {per_pass*30/3600:.1f} h")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
