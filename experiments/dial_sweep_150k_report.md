# Dial Sweep #2 — `-repeat` and `-evict-kb` at a solid 150k

**Date:** 2026-07-24
**Machine:** Apple M4 (Mac16,12), 10 logical cores, macOS 26.3.1
**Target:** `src/aes_lab.c` → `./aes_lab`, real-timing mode
**Supersedes:** the design of Dial Sweep #1 (`dial_sweep_report.md`), which fixed
the count at the noisy 50k knee and could not isolate `-evict-kb`.
**Artifacts:** `dial_sweep.sh`, `dial_sweep_150k_results.csv`, `dial_sweep_150k.log`
(pothole confirmation: `dial_sweep_pothole_*`)

---

## 1. Corrected design

To isolate a dial, the sample count must **not** be the limiting factor. So the
count was fixed at **150,000** — solidly above the ~50k threshold — and each dial
was swept **downward** to find where it breaks, with **5 trials** per point
(majority ≥3/5). Same fixed key as every other experiment.

- `-repeat` swept {50, 40, 30, 20, 10}, evict-kb fixed at 2048.
- `-evict-kb` swept {2048, 1024, 512, 256, 128}, repeat fixed at 50.

## 2. Results

### `-repeat` (count = 150k, evict-kb = 2048)

| repeat | passes | avg min_time | verdict |
|-------:|:------:|:------------:|:-------:|
| 50 | 3/5 | ~110 | PASS |
| 40 | 4/5 | ~88  | PASS |
| 30 | 4/5 | ~64  | PASS |
| 20 | 3/5 | ~43  | PASS |
| 10 | 4/5 | ~20  | PASS |

### `-evict-kb` (count = 150k, repeat = 50)

| evict-kb | passes | avg min_time | verdict |
|---------:|:------:|:------------:|:-------:|
| 2048 | 5/5 | ~110 | PASS |
| **1024** | **0/5** | ~111 | **fail** (fluke — refuted in §3.2/§6) |
| 512  | 4/5 | ~110 | PASS |
| 256  | 4/5 | ~103 | PASS |
| 128  | 5/5 | ~98  | PASS |

## 3. Findings

### 3.1 `-repeat` has **no floor** at 150k — this overturns Dial Sweep #1

Every repeat value passes, down to **repeat=10** (4/5). Dial Sweep #1 had found a
"hard floor ≈ 50" at 50k samples; that floor was **not fundamental** — it was an
artifact of 50k being marginal. With 3× the samples, averaging *across samples*
compensates for coarse per-sample timing: at repeat=10 each measurement is only
~20 timer ticks (the signal is sub-tick), yet the attack still succeeds because
there are enough samples to average the quantization noise away.

**This is the count↔repeat trade-off, quantified:** more traces buy you a lower
repeat. At the ~50k threshold you need repeat≥50; at 150k, repeat=10 suffices.

### 3.2 `-evict-kb` — bigger is unnecessary at 150k; there is **no** dead zone

With enough samples, even a **128 KB** flush works (5/5). The paper's "flush
deeper → fewer samples" advantage only bites when samples are scarce; here the
count covers for a weak flush. `min_time` is flat (~95–114) across all evict
sizes — evict size does not move the *minimum* encryption time; its effect lives
in the timing *spread*.

**The `evict-kb = 1024` point scored 0/5 in the sweep above, but this did NOT
reproduce.** A focused re-run (150k, repeat=50, evict-kb {2048, 1024, 512},
**8 trials** each — §6) gave 1024 → **7/8 PASS**, statistically identical to its
neighbours (2048 → 8/8, 512 → 8/8). **There is no 1 MB pothole.** Across
128 KB–2048 KB the attack passes uniformly at 150k.

This is the most important methodological lesson of the whole study. The tempting
binomial argument — "P(0/5) = 0.2⁵ ≈ 3×10⁻⁴, so it can't be noise" — is **wrong**,
because it assumes the five trials are *independent*. They are not: consecutive
runs at one setting are close together in time, so a burst of background load on
the machine depresses the timing signal for the **whole block at once**. The 0/5
was a single correlated event (one unlucky ~7-minute window), not five
independent failures. **Defenses:** confirm any surprising anomaly with a fresh
run (done — it vanished), and/or interleave/randomise the run order so a load
spike can't align with one parameter value. Reporting the retracted hypothesis
here, rather than deleting it, is deliberate — the failure mode is the finding.

## 4. Cross-experiment picture (count ↔ dials)

| Regime | `-repeat` needed | `-evict-kb` needed |
|---|---|---|
| Near the threshold (~50k samples) | ≥ ~50 (load-bearing) | matters; knee dominated by count noise |
| Comfortable (150k samples) | as low as 10 | as low as 128 KB (no dead zones) |

The dials are only load-bearing when samples are scarce. Given enough traces,
both become nearly free across the whole tested range — there is no special bad
value (the apparent 1 MB pothole was background-load noise, refuted in §3.2/§6).

## 5. Timing

Per-run cost with count fixed at 150k: time ∝ repeat (10→~43s … 50→~142s) and
time ∝ evict-kb (128→~24s … 2048→~142s). Full 150k sweep (10 points × 5 trials
= 50 runs) ≈ 58 min.

## 6. Pothole confirmation — refuted

Focused re-run (150k, repeat=50, **8 trials**), `dial_sweep_pothole_results.csv`:

| evict-kb | passes | verdict |
|---------:|:------:|:-------:|
| 2048 | 8/8 | PASS |
| **1024** | **7/8** | **PASS** |
| 512  | 8/8 | PASS |

The single 1024 failure (trial 6) is ordinary marginal noise — the 150k baseline
itself misses occasionally (the repeat=50 corner of the main sweep was 3/5). The
1 MB dead zone does **not** exist; the earlier 0/5 was a time-correlated
background-load artifact (see §3.2).

## 7. Reproduce

```
# full corrected sweep
RUN_TAG=150k FIXED_COUNT=150000 TRIALS=5 PASS_MIN=3 \
  REPEAT_VALUES="50 40 30 20 10" EVICT_VALUES="2048 1024 512 256 128" \
  ./experiments/dial_sweep.sh

# focused pothole confirmation (evict sweep only)
RUN_TAG=pothole SWEEPS=evict FIXED_COUNT=150000 TRIALS=8 PASS_MIN=5 \
  EVICT_VALUES="2048 1024 512" ./experiments/dial_sweep.sh
```
