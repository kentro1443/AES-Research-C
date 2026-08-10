# Analysis

## The threshold is an averaging effect

Flat `min_time` and score across count localise the mechanism: the per-trace
cache-collision signal is a fixed quantity independent of trace count. What
changes with count is the variance of each ciphertext-difference group mean
`T[i,j][d]` — with more traces per group, the correct final-round relation
separates from the noise floor more reliably. Recovery is thus a smooth,
probabilistic function of count (the psychometric curve), not a hard boundary.

## Why Go needs ~5× more traces

Same attack, same key, ~5× more traces in Go. Since the recovery logic is
common, the difference is in collection: Go's measured timings are a noisier
estimate of the same signal, so more traces are needed to average that noise
down. The GC ablation is the decisive evidence — if GC pauses were the dominant
noise, disabling the collector would move the threshold substantially; instead
N50 moves only ~8% and the gap to C is intact. The residual noise is therefore
the broader managed-runtime measurement path (bounds checks, scheduler quanta,
higher-overhead/coarser timing), **not the garbage collector specifically**.
Go's disadvantage is real, reproducible, and a property of *measurement*.

*(Caveat: absolute `min_time` is much larger in Go than C; whether that is timer
units or true overhead needs inspecting each collector's timing primitive, so the
cross-language claim rests on recovery reliability, not raw timing magnitude.)*

## Dials: signal strength over averaging, and a design lesson

Within C at the knee, more `-repeat` doesn't help and the largest `-evict-kb`
helps most — consistent with the averaging/signal split: near threshold the
binding constraint is per-trace signal strength (stronger eviction), not extra
averaging, and very large `-repeat` may lengthen each measurement enough to admit
more perturbation. The Go dial sweep carries a **methodological lesson**: fixing
the dial count at C's knee (100k) placed it below Go's threshold (~265k), so it
could not probe Go's dial sensitivity. A per-implementation dial count (relative
to each language's own threshold) would be needed for a fair cross-language dial
comparison.

## Positioning against prior work

The attack follows Bonneau–Mironov's final-round cache-collision model, whose
expanded final-round attack recovers from a median of 2¹³–2¹⁴·³ samples (with
cache eviction) on 2006 processors. Our C threshold (N50 ≈ 2¹⁵·⁶; ≥90% ≈ 2¹⁶·²)
is ~one order of magnitude higher — expected, not contradictory: the comparison
mixes algorithm with platform and instrument (their hardware cycle counters on a
Pentium III/UltraSPARC vs our aggregate wall-clock timing on an Apple M4).
Agreement to within an order of magnitude on entirely different hardware
indicates the leakage mechanism reproduces as predicted; the absolute count is
platform-specific.

## Threats to validity

- **Single key** — thresholds may vary across keys.
- **Sampling uncertainty** — n=10 gives wide CIs near 0/10 and 10/10; N50 is an
  estimate; individual dial points shouldn't be over-read.
- **Environment sensitivity** — clean C runs give ~50k and ~100k, a contaminated
  one ~150k; controlled by the environment gate but not eliminable on a
  general-purpose machine.
- **Native-collection confound** — cross-language uses each language's own traces
  (different seeds): measures runtime-in-collection, not shared-dataset
  consistency (RQ2) or processing time (RQ3), both future work.
- **Reduced Go(GC-off) grid** and **platform confound** in the prior-work
  comparison — stated where used.
