---
name: trace-threshold
description: Compare the C (aes_lab) and Go (aes_lab_go) implementations' minimum reliable sample count for real-timing key recovery, by running collect-real -> attack-final across an increasing sample-count sequence for both binaries. Use when asked to run a real-timing extraction experiment or compare trace-thresholds between the two languages. Not auto-invoked -- user-triggered only.
disable-model-invocation: true
---

Run a trace-threshold sweep comparing `aes_lab` (C) and `aes_lab_go` (Go).
Accepts optional `$ARGUMENTS` to override the default sample-count sequence
or restrict to one language (e.g. `$ARGUMENTS = "go 500000 1000000"` or
`$ARGUMENTS = "250000 500000 1000000 1500000"` for both languages).

## Defaults

- Sample-count sequence: `250000 500000 1000000 1500000`
- Fixed params: `-repeat 50 -evict-kb 2048` (the recipe already proven to
  work in `success_attempt.txt` and README's Go Port section)
- Repeats per count: 3 (the local search in `attack-final` uses randomized
  restarts -- especially in Go, where `math/rand` is always freshly seeded
  per process, unlike C's accidentally-deterministic `rand()` -- so a single
  run at a given count isn't a reliable signal; do not report a single-run
  result as the threshold)
- Both binaries must already be built (`aes_lab`, `go/aes_lab_go`); rebuild
  first if missing or stale.

## Procedure

For each language and each sample count in the sequence, repeated 3 times:

1. `keygen` a fresh key.
2. `collect-real` at that sample count with the fixed `-repeat`/`-evict-kb`.
3. `attack-final` on the resulting samples.
4. `verify` the recovered key against the samples file.
5. Record: language, sample count, run number, success/failure (exit code),
   and (if attack-final printed it) `used samples`/`ignored samples`/final
   score.

Per this project's background-run preference, launch each collect-real run
in the background rather than blocking, and check back rather than
polling. A single count/language/repeat combination can take several
minutes at large counts -- budget accordingly, and let the user know
roughly how long the full sweep is expected to take before starting.

Use a scratch temp directory for all generated `.bin` files -- do not leave
them in the repo.

## Reporting

Report a compact table: rows = sample count, columns = language, cells =
success rate out of 3 repeats (e.g. "3/3", "1/3", "0/3"). Call out the
lowest sample count where each language first reaches 3/3 (or close to it)
as that language's practical trace-threshold on this run. Keep the report
terse -- a table plus 2-3 sentences of interpretation, not a full transcript
of every run's output.
