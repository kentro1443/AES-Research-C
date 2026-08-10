# Methodology additions

Extends the draft's Methodology to cover the experiments actually run.

## Dial sweep at a fixed trace count

Complement to the threshold experiment: hold trace count fixed, vary the two
collection dials, to separate *averaging* from *signal strength*.

- **`-repeat` r** — encryptions accumulated per trace; larger r = more averaging
  relative to fixed timer overhead.
- **`-evict-kb` e** — memory region read before each timed op; larger e disturbs
  more cache, expected to strengthen the collision signal.

Count is fixed at **100,000 traces** — chosen deliberately as C's *marginal*
region, just above its 50% threshold, where recovery is most sensitive to signal
quality. A count deep in the reliable (100%) or failure (0%) regime would mask
dial effects; the knee maximises dynamic range. Sweep r ∈ {10,20,30,50,75,100}
and e ∈ {256,512,1024,2048,4096} KiB about the r=50/e=2048 baseline, 10
interleaved trials/point.

## Native cross-language recovery

Different from the draft's shared-dataset plan (Sec 2.11). Each implementation
performs its **own** measured collection with its native timer, then its own
recovery; we compare recovery **reliability** vs trace count. This measures how a
language's runtime affects the timing channel it can capture — the "separate
runtime-dependent experiment" the draft anticipates — not the correctness of a
shared computation.

Trace count, the fixed key, dials, outlier rule, recovery algorithm, and
verification are identical; only the implementation (and its collection runtime)
changes. Since each language collects independently, trace data and seeds differ
across implementations — so differences in recovery are attributable to runtime
behaviour in collection, not to the (common) attack logic. Kept distinct from the
shared-dataset consistency test (future work).

## Garbage-collector ablation (Go)

To test whether Go's managed-runtime noise causes its higher threshold, repeat Go
collection with **`GOGC=off`** (no GC pauses inside timed regions) and
**`GOMAXPROCS=1`** (one core, no cross-core migration). Both are read from the
environment by the Go runtime — no source change. For cost, the ablation uses a
reduced grid (counts {500k,250k,100k,50k}; 3×3 dial grid), so it is compared to
the GC-on run only at matched points and by fitted N50, never by a grid-dependent
high-reliability count.

## Dataset governance and exclusion criteria

Fixed rules to avoid selective reporting; excluded runs' metadata preserved (see
`provenance.md`).

- **Environment gate** — exclude if mean collection cost > ~1.2 ms/sample
  (baseline ≈ 0.94). One 10-trial C sweep is excluded (~3.0 ms/sample).
- **Design gate** — exclude pilots with fewer trials, missing sidecars, or
  single-point grids from the primary analysis (design context only).
- **Implementation identity** — one retained C run was launched with an
  `IMPL=go` tag before the harness supported language selection; the C binary
  actually ran. Verified C (no `impl` field; `min_time`/ms-sample match C) and
  relabelled. Documented because an earlier positional parse of the result column
  produced wrong tallies; all counts are recomputed by column name.
