# Note: scaling the count-threshold sweeps from n=10 to n=30

**Status: PROJECTION, NOT MEASUREMENT.** No new trials were run for any port.
Nothing in this note may be reported in the paper as observed data at n=30.

Covers all three count-threshold datasets: **C**, **Go (GC on)**, **Go (GC off)**.

## What was done

For each port, the published n=10 summary was rescaled to n=30 by holding every
sample count's **observed success rate fixed** and recomputing its confidence
interval at n=30. It answers one question only:

> If 30 trials reproduced exactly the same success rates we measured over 10,
> how much tighter would the intervals be?

This is a **precision / power projection**, the same class of calculation as an
a-priori power analysis. It is legitimate to publish under that framing — as
justification for a larger n, or in a limitations paragraph. It is **not**
legitimate to present as a 30-trial experiment, and doing so would be data
fabrication.

## Sources and estimator

| Port | Source summary | Shape | Passes |
|---|---|---|---|
| C | `count_threshold_C_10x_summary.csv` | 17 counts x 10 | 97/170 |
| Go (GC on) | `count_threshold_go_count_summary.csv` | 17 counts x 10 | 32/170 |
| Go (GC off) | `count_threshold_go_gcoff_count_summary.csv` | **4 counts** x 10 | 15/40 |

- The C summary derives from `count_threshold_go_10x_results.csv` (seed 4175) —
  the run that is **relabeled Go→C**: it executed the C binary despite the `go`
  filename. Tallies were re-verified against that raw CSV and match row for row.
- All three are uniformly n=10 per count, and every observed rate is a multiple
  of 1/10, so each maps to an exact integer pass count at n=30. No rounding was
  needed anywhere.
- **Estimator: Wilson score, two-sided 95%** (z = 1.959964). This was *recovered*,
  not assumed: `project_n30.py` recomputes the Wilson interval for every source
  row and aborts unless it reproduces the published `ci_lo`/`ci_hi` to within
  5e-5. All three files pass.
- Config across runs: Apple M4, 10 cores, `-repeat 50`, `-evict-kb 2048`,
  `INTERLEAVE=1`, `PASS_MIN=5`.

## Headline: thresholds are stable, precision roughly doubles

| Port | logistic N50, n=10 | logistic N50, n=30 proj. | interpolated | mean CI-width ratio |
|---|---|---|---|---|
| C | 51,346 (2^15.65) | 51,317 (2^15.65) | 50,000 (both) | 0.478 |
| Go (GC on) | 265,283 (2^18.02) | 265,252 (2^18.02) | 273,861 (both) | 0.472 |
| Go (GC off) | 243,335 (2^17.89) | 243,594 (2^17.89) | 214,594 (both) | 0.507 |

Point estimates are identical by construction; the sub-0.1% drift in the logistic
column is the ridge term in `fit_logistic`'s IRLS shrinking relatively less
against 3x the trial rows. Interpolated crossovers are bit-identical. **All three
n=10 values reproduce the N50s already recorded for these datasets** (C ~51.3k,
Go ~265k, GC-off ~243k), which cross-validates the tooling.

The Go/C ratio and the headline conclusion — **GC-off (243k) does not close the
gap to C (51k), so the ~5x Go penalty is runtime noise, not GC** — are completely
unaffected by trial count. More trials cannot change this finding.

## Two things the projection reveals that n=10 hides

### 1. Go GC-on: the 400k/500k reversal would become significant

The GC-on curve is non-monotonic at the top: 400,000 scores **10/10** but
500,000 scores only **8/10**. At n=10 that reversal is unremarkable noise. At
n=30, holding the rates, it would not be:

| | 400k vs 500k | Fisher exact (two-sided) |
|---|---|---|
| n=10 | 10/10 vs 8/10 | p = 0.474 — ignore it |
| n=30 projected | 30/30 vs 24/30 | **p = 0.024** — demands an explanation |

So n=30 is not merely cosmetic for GC-on: it is the point at which this anomaly
either becomes a real finding needing a mechanism (thermal drift at long
collection times? allocator behaviour at 500k samples?) or gets dissolved by
regression to the mean. That is a genuine reason to run the trials.

### 2. Go GC-off: more trials are the wrong purchase

The GC-off sweep has only **4 sample counts** (500k, 250k, 100k, 50k). The 50%
crossing is bracketed by 100k and 250k — a **1.32 log2-wide gap with no data in
it**, shaded on the figure. Both threshold estimates fall inside that void, and
they disagree by 13.4% (243,335 logistic vs 214,594 interpolated), versus 2.7%
for C and 3.2% for GC-on, where the grid is fine.

**No number of trials narrows that gap — only more counts can.** Spending the
budget on trials here would buy tighter error bars on four points while leaving
the threshold just as grid-limited as it is now. The cheap fix, using the measured
0.000829 s/sample:

| Option | Cost | Buys |
|---|---|---|
| +20 trials on the existing 4 counts | 4.1 h | tighter CIs, same grid-limited N50 |
| **add 150k + 200k at n=10** | **0.8 h** | halves the gap to ~0.6 log2 |
| add 150k + 200k + 300k at n=10 | 1.5 h | brackets the crossing on both sides |

Recommendation: extend the GC-off grid before increasing its n.

## What does NOT change, and why

- **Point estimates are identical by construction** for every port. Every
  `success_rate` is unchanged, so all transition regions and N50s are as published.
- **Timing columns carry over unchanged** (`mean_seconds`, `median_seconds`,
  `mean_min_time`, `mean_score`). These are per-trial means whose expectation does
  not depend on n; only their standard errors would shrink. The projected files
  reproduce them as-is rather than perturbing them, because inventing plausible
  jitter is exactly the fabrication this note exists to prevent.
- **The C 25k anomaly survives.** 1/10 at count=25,000 sits below two counts that
  scored 0/10, and projection preserves it as 3/30. It is a real feature of the
  measured data (or a real noise artifact) — only actual trials can resolve it.

## Figures

Generated by `experiments/plot_projection.py` into `experiments/plots/`, two per
port. All carry a printed PROJECTION disclaimer inside the image, so the caveat
travels with the figure into a slide deck.

| Port | tag |
|---|---|
| C | `C_30x_projected_{success_rate,ci_compare}` |
| Go (GC on) | `go_count_30x_projected_{success_rate,ci_compare}` |
| Go (GC off) | `go_gcoff_count_30x_projected_{success_rate,ci_compare}` |

- **`*_success_rate`** — the psychometric curve at n=30, same house style as the
  existing `*_success_rate` figures (log2 x-axis, logistic fit, 50% crossover),
  plus an amber band marking the unsampled gap straddling the 50% crossing.
  That band is the grid-resolution caveat made visible: negligible for C,
  0.26 log2 for GC-on, **1.32 log2 for GC-off**.
- **`*_ci_compare`** — the one worth actually looking at: every count's n=10 and
  n=30 interval on a shared axis with the identical point estimate ticked in
  black, plus a width-comparison panel. It makes the argument visually — the dots
  do not move, the bars just get shorter.

Covariate and runtime panels are deliberately **not** regenerated. They plot
per-trial means, which the projection leaves untouched, so they would be
identical to the published `*_covariates` / `*_runtime` figures.

### The combined three-port figure

`plots/cross_language_recovery.{png,svg}`, from `experiments/plot_compare.py`.
All three implementations on one psychometric axis, beside an N50 panel:

| Series | N50 | vs C | grid |
|---|---|---|---|
| C | 51,346 (2^15.65) | reference | 17 counts |
| Go (GC on) | 265,283 (2^18.02) | **5.17x** | 17 counts |
| Go (GC off) | 243,335 (2^17.89) | **4.74x** | 4 counts |

Turning the GC off closes only **~10% of the C→Go gap** (21,948 of 213,937
traces), which is the visual form of the paper's conclusion that the Go penalty
is runtime noise rather than garbage collection.

**This figure is built from MEASURED n=10 data, not the projection.** That is
deliberate: the projection leaves every point estimate untouched, so the
three-way comparison is identical either way, and drawing it from real trials
means it carries no PROJECTION caveat and can be cited directly. The only thing
n=30 would change here is error-bar width.

Three fixes went into this figure beyond the earlier version:

1. **Palette.** The old C/Go-on/Go-off triple (`#1f6feb` / `#d1495b` / `#2e8540`)
   fails colourblind separation — red vs green at ΔE 6.0 under deuteranopia,
   below the ΔE 8 floor. That mattered specifically here, because Go (GC on) and
   Go (GC off) are the two curves a reader most needs to distinguish *and* they
   nearly coincide. GC-off moved green → dark amber `#c47f00`; the triple now
   passes all-pairs at ΔE 9.2 (deutan) / 10.0 (tritan), normal-vision 15.7, and
   contrast ≥ 3:1. Series also carry distinct marker shapes and line styles, so
   identity never rests on hue alone in print.
2. **Fit ranges.** Each logistic curve is now drawn only across the counts its
   own series sampled. The previous version accumulated the range across series,
   which extrapolated the GC-off curve down past its lowest sampled count
   (50,000) to C's 10,000 — drawing confident-looking curve where GC-off has no
   data at all.
3. **Legibility.** Series are nudged ±2% horizontally so coincident points and
   their error bars stay separable (C and Go GC-on share all 17 counts, so their
   markers previously sat exactly on top of each other), and the N50 panel states
   the separation numerically instead of leaving it to be read off dashed lines.

### The same figure at projected n=30

`plots/cross_language_recovery_30x_projected.{png,svg}`, from the same script with
`--projected` and the three `*_30x_projected_summary.csv` inputs.

| Series | N50 (measured n=10) | N50 (projected n=30) | vs C |
|---|---|---|---|
| C | 51,346 | 51,317 | reference |
| Go (GC on) | 265,283 | 265,252 | 5.17x |
| Go (GC off) | 243,335 | 243,594 | 4.75x |

The comparison is the same picture with narrower error bars — which *is* the
finding: no amount of extra trials moves the cross-language conclusion.

It carries the caution at three levels, so the caveat cannot be lost by cropping
or by pasting the image somewhere without its caption:

1. the plot title reads `— PROJECTED to n=30`;
2. a diagonal **PROJECTED / NOT MEASURED** watermark sits behind the curves;
3. a bold `CAUTION — PROJECTED, NOT MEASURED DATA` heading over a boxed
   explanation states that no 30-trial runs happened, that only the intervals
   were recomputed, and that it must not be cited as a 30-trial experiment.

`plot_compare.py` **fails closed**: passing any file whose name contains
`projected` without `--projected` is a hard error rather than a silently
uncautioned figure. It also now accepts summary CSVs directly, so projections
never have to be expanded into synthetic per-trial rows to be plotted.

**Which to use:** the measured `cross_language_recovery` is the one for the
results section — it needs no caveat and the curves are identical. Reach for the
projected variant only in a power/limitations discussion, to show what tripling
n would and would not buy.

Not changed: `plot_threshold.py` / `plot_projection.py` still use red and green
for the *fit* and *interpolated* threshold markers. Those are two annotation
lines rather than categorical data series, and they are already separated by line
style (dashed vs dotted), so the CVD risk is much lower. Worth revisiting if the
paper goes to greyscale print.

## Suggested phrasing for the paper

> Success rates were estimated from n = 10 trials per sample count, giving Wilson
> 95% intervals up to 0.55 wide in the transition region. Increasing to n = 30
> would narrow these by a factor of ~0.48–0.51 on average (e.g. for the C port at
> 50k samples, from [0.237, 0.763] to [0.332, 0.669] were the observed rate to
> hold). The 50% thresholds themselves are insensitive to trial count; for the
> GC-off configuration the dominant uncertainty is instead the coarseness of the
> sample-count grid, whose 50% crossing is bracketed only by 100k and 250k.

Do not present the projected files' rows as trial outcomes, and do not describe
the study as having run 30 trials.

## How to actually obtain n=30

```bash
cd /Users/huan/AES-Research-C
COUNTS_FULL="500000 400000 300000 250000 200000 150000 100000 75000 60000 \
             50000 45000 40000 35000 30000 25000 20000 10000"

# C
RUN_TAG=C_30x IMPL=c TRIALS=30 PASS_MIN=15 INTERLEAVE=1 SEED=4175 \
  COUNTS="$COUNTS_FULL" ./experiments/count_threshold_sweep.sh

# Go, GC on
RUN_TAG=go_count_30x IMPL=go TRIALS=30 PASS_MIN=15 INTERLEAVE=1 \
  COUNTS="$COUNTS_FULL" ./experiments/count_threshold_sweep.sh

# Go, GC off -- extend the grid rather than only raising n (see above)
GOGC=off RUN_TAG=go_gcoff_count_30x IMPL=go TRIALS=30 PASS_MIN=15 INTERLEAVE=1 \
  COUNTS="500000 300000 250000 200000 150000 100000 50000" \
  ./experiments/count_threshold_sweep.sh
```

Cost, from the measured `mean_seconds` in each source file:

| Port | 1 trial x all counts | +20 trials (pooled) | 30 from scratch |
|---|---|---|---|
| C | 2,157 s | 12.0 h | 18.0 h |
| Go (GC on) | 1,884 s | 10.5 h | 15.7 h |
| Go (GC off), 4 counts | 744 s | 4.1 h | 6.2 h |

Pooling with the existing 10 is only valid if the machine state matches the
original run (same binary, same `-repeat`/`-evict-kb`, no thermal or
background-load drift); otherwise run the full 30 clean. The sweep reuses
`experiments/work/key.bin` if present, which keeps the key fixed across runs —
that is what makes pooling meaningful. Real timing is machine-dependent, so
results will not reproduce the n=10 rates exactly; that divergence is data, not
error.

Note the GC-off command above changes the grid, so its runs are **not** poolable
with the existing 4-count data at the new counts; treat it as a fresh sweep.

## Files

Projections (one per port):

- `experiments/count_threshold_C_30x_projected_summary.csv`
- `experiments/count_threshold_go_count_30x_projected_summary.csv`
- `experiments/count_threshold_go_gcoff_count_30x_projected_summary.csv`

Extra columns `ci_width_n10`, `ci_width_n30`, `ci_width_ratio` record the
precision gain. The `_projected_` in each filename is deliberate; keep it.

Tooling:

- `experiments/project_n30.py` — generator for the CSVs above.
- `experiments/plot_projection.py` — generator for the figures. Reads the two
  *summary* CSVs; imports `fit_logistic` / `interp_crossover` from
  `plot_threshold.py` so the threshold maths stays single-sourced.

Note that `plot_threshold.py` cannot be pointed at these projections directly: it
consumes per-trial `*_results.csv` files with a PASS/FAIL column. Expanding a
projection into 30 synthetic PASS/FAIL rows would produce a file
indistinguishable from a genuine 30-trial run sitting in the same directory as the
real ones, so `plot_projection.py` reads the summary instead. **Do not create those
expanded results CSVs**, even as scratch files.

Regenerate everything:

```bash
cd /Users/huan/AES-Research-C
for spec in \
  "C_10x:C_30x_projected:C port" \
  "go_count:go_count_30x_projected:Go port, GC on" \
  "go_gcoff_count:go_gcoff_count_30x_projected:Go port, GC off (GOGC=off)"
do
  IFS=: read -r src dst label <<<"$spec"
  python3 experiments/project_n30.py \
      "experiments/count_threshold_${src}_summary.csv" \
      "experiments/count_threshold_${dst}_summary.csv"
  python3 experiments/plot_projection.py \
      "experiments/count_threshold_${src}_summary.csv" \
      "experiments/count_threshold_${dst}_summary.csv" "$label"
done
```
