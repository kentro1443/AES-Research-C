# Results

## Trace-count threshold (C)

Canonical C run (seed 4175), 10 trials/count, 95% Wilson CIs. Recovery is 0% at
≤35k and a reliable 100% at ≥100k. Logistic fit in log₂(count): **N50 ≈ 51,346
(2¹⁵·⁶⁵)**; model-independent interpolation agrees at ≈50,000. High reliability
(≥90%) is first reached at ≈75k.

| Traces | Recovered | Rate | 95% CI |
|---:|:--:|:--:|:--:|
| ≥100,000 | 10/10 | 100% | [72, 100] |
| 75,000 | 9/10 | 90% | [60, 98] |
| 60,000 | 7/10 | 70% | [40, 89] |
| 50,000 | 5/10 | 50% | [24, 76] |
| 45,000 | 4/10 | 40% | [17, 69] |
| 40,000 | 1/10 | 10% | [2, 40] |
| ≤35,000 | 0–1/10 | ≤10% | [0, 40] |

Mean `min_time` stays within 112–121 ticks and mean score within ~17,200–17,460
across all counts — **flat**, with no trend. The per-trace leak is unchanged;
only the stability of the group means improves with count. The threshold is an
averaging effect, not a signal cliff. *(Fig: `go_10x_success_rate`, `go_10x_covariates`.)*

## Cross-language recovery

Identical counts, key, dials, and recovery logic; each language collects its own
traces. 50% thresholds:

| Implementation | N50 (traces) | log₂ | Ratio to C |
|:--|:--:|:--:|:--:|
| C | 51,346 | 15.65 | 1.0× |
| Go (GC on) | 265,283 | 18.02 | **5.2×** |
| Go (GC off) | 243,335 | 17.89 | 4.7× |

**Go needs ~5× more traces than C** for the same recovery probability. Python is
deferred (native collection at these counts is prohibitively slow and expected
to recover near 0). *(Fig: `cross_language_recovery`.)*

## Runtime-noise ablation (Go GC on vs off)

Disabling the collector and pinning one core lowers N50 only from ≈265k to ≈243k
(~8%, within noise). At matched counts GC-off is equal-or-better everywhere, but
the ~5× gap to C is untouched — **quieting the runtime does not explain Go's
disadvantage.**

| Traces | GC on | GC off |
|---:|:--:|:--:|
| 500,000 | 8/10 | 9/10 |
| 250,000 | 4/10 | 6/10 |
| 100,000 | 0/10 | 0/10 |
| 50,000 | 0/10 | 0/10 |

## Dial sweep (C, at 100k)

| `-repeat` (e=2048) | Rate | | `-evict-kb` (r=50) | Rate |
|---:|:--:|--|---:|:--:|
| 10 | 60% | | 256 | 80% |
| 20 | 50% | | 512 | 60% |
| 30 | 50% | | 1024 | 10% |
| 50 | 70% | | 2048 | 50% |
| 75 | 20% | | 4096 | 100% |
| 100 | 20% | | | |

More `-repeat` does **not** help (and appears to hurt at 75–100); the strongest
eviction (4096 KiB) gives the best recovery (100%). Robust reading: at this
count, signal strength matters more than extra averaging. The **Go dial sweep is
uninformative** — 100k lies far below Go's ≈265k threshold, so recovery is ≈0
(1/110 GC-on, 1/60 GC-off) regardless of dials — a design consequence, not a
null effect.
