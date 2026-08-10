# Sample-Count Threshold of the C AES Cache-Timing Attack

**Date:** 2026-07-23
**Machine:** Apple M4 (Mac16,12), 10 logical cores, macOS 26.3.1
**Target:** `src/aes_lab.c` → `./aes_lab`, real-timing mode (`collect-real`)
**Attack:** Bonneau & Mironov *Final Round Attack* (groups ciphertext-byte pairs
by `Δ = c[i] ^ c[j]`, picks lowest-average timing, refines with multi-start
local search — §6 + Appendix D of *Cache-Collision Timing Attacks Against AES*)
**Artifacts:** `count_threshold_sweep.sh`, `count_threshold_results.csv`,
`count_threshold_sweep.log`

---

## 1. What we set out to find

The known-good recipe in `success_attempt.txt` recovers the key using **500,000**
real-timing samples:

```
./aes_lab collect-real key.bin samples.bin 500000 -repeat 50 -evict-kb 2048
./aes_lab attack-final samples.bin final.bin
./aes_lab verify final.bin samples.bin
```

500,000 is ≈ 2^18.9 — roughly **8–15× more** than the paper's published median
for this exact attack (Table 1: 2^15 ≈ 32,768; Table 2 Pentium III: 2^16 L1 /
2^15 L2). So `500000` was a safe over-estimate; the *actual* minimum number of
traces needed on this machine was unknown. **Goal: find that threshold** — the
fewest samples from which the attack still recovers the key on this hardware.

## 2. Why this method

- **Vary only the sample count.** `-repeat 50` and `-evict-kb 2048` were held
  fixed so the sole variable is the number of traces — the classic "trace
  threshold", directly comparable to the paper's Table 1/2 conditions.
- **One fixed key, reused for every run** (`732979c8…`), so key-to-key variation
  can't contaminate the count signal.
- **Machine-readable success, no output parsing.** `attack-final` self-verifies
  each key candidate against a plaintext/ciphertext pair stored in the sample
  header and exits **0 on success, non-zero (2) on failure**. The harness just
  reads the exit code.
- **Noise handling — 3 trials per count.** Real timing is non-deterministic
  (background load, scheduler, thermal), so a given count can pass one run and
  miss the next. Each count was run **3×**; a count "passes" if it succeeds in
  **≥ 2 of 3** trials (majority vote).
- **Step down and log the whole curve.** We swept the count *downward* and kept
  going *past* the first failures to a floor, so the PASS→fail transition is
  visible rather than being cut off by a single noisy miss.

## 3. What was actually run

`experiments/count_threshold_sweep.sh` did, in order:

1. `make` the C target and `keygen` one key into `experiments/work/key.bin`.
2. For each count in
   `500000 400000 300000 250000 200000 150000 100000 75000 50000 40000 30000 20000`,
   run **3 trials** of: `collect-real` (fixed key, `-repeat 50 -evict-kb 2048`)
   → `attack-final`; record the exit code plus `min_time` and the attack `score`.
3. Append one CSV row per `(count, trial)` and print a per-count pass tally with
   a live ETA.

The same `samples.bin` was overwritten each run. All `*.bin` are gitignored.

## 4. Results

Per-count tally (3 trials each), with average wall-time per run:

| Count   | Passes | Verdict | Avg run time |
|--------:|:------:|:-------:|-------------:|
| 500,000 | 3/3 | **PASS** | 472 s (7m52s) |
| 400,000 | 3/3 | **PASS** | 378 s |
| 300,000 | 3/3 | **PASS** | 283 s |
| 250,000 | 3/3 | **PASS** | 236 s |
| 200,000 | 3/3 | **PASS** | 189 s |
| 150,000 | 3/3 | **PASS** | 144 s |
| 100,000 | 3/3 | **PASS** | 95 s |
| **75,000**  | **2/3** | **PASS** (1 noisy miss) | 71 s |
| **50,000**  | **2/3** | **PASS** (1 noisy miss) | 47 s |
| 40,000  | 0/3 | fail | 38 s |
| 30,000  | 0/3 | fail | 28 s |
| 20,000  | 0/3 | fail | 19 s |

**Threshold (lowest count still passing ≥ 2/3): ≈ 50,000 samples.**

Three regimes, with a sharp transition:

- **≥ 100,000** — rock-solid, 3/3 every time.
- **50,000–75,000** — noisy boundary, 2/3 (works most of the time, occasional miss).
- **≤ 40,000** — collapses completely, 0/3 (never recovers).

## 5. Timing

- **Per-sample rate: 0.944 ms/sample**, essentially constant across every count
  (0.942–0.962 ms) — collection time scales linearly with the sample count, as
  expected. The cost is dominated by the per-sample 2 MB cache-eviction walk
  (`-evict-kb 2048`) repeated 50× (`-repeat 50`).
- **Per-run examples:** 500k ≈ 472 s, 100k ≈ 95 s, 50k ≈ 47 s, 20k ≈ 19 s.
- **Total sweep wall time: 6001 s ≈ 1 h 40 m** for all 36 runs (12 counts × 3).

## 6. Interpretation

- **500,000 was ~10× overkill.** The attack is reliable at **~100,000** samples
  and still works most of the time down to **~50,000** on this machine.
- **The ~50k floor matches the paper.** Bonneau & Mironov report 2^15 ≈ 32,768
  (Table 1) and 2^15–2^16 ≈ 32k–65k (Table 2) for the Final Round Attack. The
  empirical boundary here — 40k fails, 50k marginal, 100k solid — lands squarely
  in that band: a clean real-hardware confirmation of their simulated numbers.
- **The failure is statistical, not a signal cliff.** `min_time` (~107–120
  ticks) and `score` (~17,000) are *flat* across every count, so per-sample leak
  strength does not change with count. What changes is **averaging**: fewer
  samples → noisier per-`Δ` timing averages → the local search occasionally
  locks onto the wrong byte offsets. That is exactly why the boundary is
  probabilistic (2/3) rather than a hard on/off cliff.

## 7. Caveats

- Machine-specific: numbers reflect this Apple M4 under its load at run time; a
  busier or different machine will shift the threshold.
- 50,000 and 75,000 are **marginal (2/3)** — single-run reproducibility there is
  not guaranteed. This was addressed by an 8-trial confirmation of the knee — see
  §9, which turns the 2/3 estimates into a proper success-rate curve.
- Only `-repeat 50 / -evict-kb 2048` were tested; those dials trade off against
  the count (see the follow-up dial-sweep experiment).

## 8. Reproduce

```
./experiments/count_threshold_sweep.sh          # ~1h40m, writes CSV + log
```

Edit the CONFIG block at the top of the script (`COUNTS`, `TRIALS`, `REPEAT`,
`EVICT_KB`, `PASS_MIN`) — all overridable via environment variables — to change
the schedule. Raw per-trial data is in `experiments/count_threshold_results.csv`.

## 9. Threshold confirmation — 8-trial success-rate curve

The initial sweep used 3 trials, leaving 50k/75k as noisy 2/3 estimates. A
focused re-run at **8 trials** per count (same fixed key, `-repeat 50
-evict-kb 2048`) over the knee makes the transition precise:

```
RUN_TAG=knee TRIALS=8 PASS_MIN=5 COUNTS="75000 60000 50000 45000 40000 30000" \
  ./experiments/count_threshold_sweep.sh
```

| Count  | Passes | Success rate | Verdict (≥5/8) |
|-------:|:------:|:------------:|:--------------:|
| 75,000 | 6/8 | 75%  | **PASS** |
| 60,000 | 6/8 | 75%  | **PASS** |
| 50,000 | 5/8 | 62%  | **PASS** |
| 45,000 | 2/8 | 25%  | fail |
| 40,000 | 2/8 | 25%  | fail |
| 30,000 | 0/8 | 0%   | fail |

Raw data: `experiments/count_threshold_knee_results.csv`.

**Conclusion — the ~50k threshold holds, with a sharp knee:**

- **≥ 60,000 → reliable** (~75% per single run; near-certain across a few tries).
- **~50,000 → the majority threshold** (62%): still the *lowest count that passes
  ≥ 5/8*, matching the original ≈50k figure.
- **The 50% crossover sits at ≈ 45–50k**, and success **collapses below 45k**
  (25% at 40–45k, 0% at 30k).

This lands squarely in the paper's Final-Round band (2^15–2^16 ≈ 32k–65k). Note
`min_time` (~106–121) is flat across the whole curve, confirming once more that
the knee is **statistical** (too few samples to average the per-Δ timings), not a
change in per-sample leak strength.

> **Methodology caveat.** Like all runs here, trials for a given count are
> consecutive in time, so a transient background-load spike can depress a whole
> block together (this is exactly what produced a spurious result in the dial
> sweep — see `dial_sweep_150k_report.md` §3.2). The curve above is smooth and
> monotone, so no block looks corrupted, but for publication-grade rigour the
> trials should be interleaved/randomised across counts rather than grouped.
