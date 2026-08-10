# Dial Sweep #1 — `-repeat` and `-evict-kb` at the 50k knee

**Date:** 2026-07-24
**Machine:** Apple M4 (Mac16,12), 10 logical cores, macOS 26.3.1
**Target:** `src/aes_lab.c` → `./aes_lab`, real-timing mode
**Depends on:** `count_threshold_report.md` (found the sample-count threshold ≈ 50k)
**Artifacts:** `dial_sweep.sh`, `dial_sweep_results.csv`, `dial_sweep.log`

---

## 1. Goal

The count sweep held `-repeat 50` and `-evict-kb 2048` fixed and varied only the
sample count. This follow-up does the opposite: **hold the sample count fixed and
sweep the two other dials, one at a time**, to see how each affects success.

- **`-repeat`** — encryptions summed per sample (noise averaging). More → cleaner
  per-sample timing.
- **`-evict-kb`** — cache-flush buffer walked before each encryption (signal
  strength). Bigger → tables evicted from deeper cache → stronger hit/miss signal.

Same fixed key as the count sweep, exit-code success detection, 3 trials per
point, majority (≥2/3) vote.

## 2. Setup — and the design choice that turned out wrong

The count was fixed at **50,000** — the *marginal knee* from the count sweep
(50k had scored 2/3 there). The idea was that a marginal count would let a dial
change push the result either way. **In hindsight this was the wrong operating
point** (see §5): at the knee the count's own run-to-run noise dominates, which
is fine for a dial with a huge effect (`repeat`) but drowns out a dial with a
subtle effect (`evict-kb`).

## 3. Results

### `-repeat` sweep (count = 50k, evict-kb = 2048)

| repeat | passes | avg min_time | verdict |
|-------:|:------:|:------------:|:-------:|
| 10 | 0/3 | ~19  | fail |
| 20 | 0/3 | ~42  | fail |
| 30 | 0/3 | ~67  | fail |
| **50** | **3/3** | ~113 | **PASS** |
| 75 | 1/3 | ~170 | fail |
| 100 | 2/3 | ~234 | PASS |

### `-evict-kb` sweep (count = 50k, repeat = 50)

| evict-kb | passes | avg min_time | verdict |
|---------:|:------:|:------------:|:-------:|
| 256  | 0/3 | ~103 | fail |
| 512  | 2/3 | ~111 | PASS |
| 1024 | 0/3 | ~112 | fail |
| 2048 | 0/3 | ~112 | fail |
| 4096 | 1/3 | ~106 | fail |

## 4. What we can (and cannot) conclude

**`-repeat` — clean, useful result: there is a hard floor around 50.** Below it
the attack *never* recovers the key (0/3 at 10/20/30). The mechanism is visible
in `min_time`, which scales linearly with repeat (~2.2 ticks per encryption): at
repeat=10 the entire measurement is only ~19 timer ticks, so the cache-collision
signal — a sub-tick effect — is lost to **timer quantization**. You need ≥~50
summed encryptions to lift the averaged signal above the clock granularity. Above
50 the tally wobbles (75→1/3, 100→2/3); that is just the noise of the marginal
50k count, not a real decline.

**`-evict-kb` — inconclusive.** The tally is non-monotonic nonsense (512 beats
1024 and 2048). The smoking gun: the **`evict=2048` point scored 0/3 here, but
the identical config scored 2/3 in the count sweep** — same key, same
parameters. So the pass/fail at 50k is governed by sample-count noise, not by
evict size. `min_time` is essentially flat (~103–112) across all evict sizes,
confirming evict barely moves the *minimum* timing; its effect lives in the
spread and is too small to resolve at this marginal count.

## 5. Lesson learned

Fixing the count at the **marginal knee** was the wrong way to isolate a dial:
the count's own noise dominates. To measure a dial cleanly, the count must **not**
be the limiting factor. The corrected design — carried out in Dial Sweep #2
(`dial_sweep_150k_*`) — fixes the count where the baseline passes **solidly**
(150,000 = 3/3) and sweeps each dial **downward** to find where it breaks, with
**5 trials** per point. There the dial is the deciding variable.

The `repeat` floor found here (≈50) is trustworthy because its effect is so large
it is unambiguous even through the knee noise; the `evict` question is deferred to
Dial Sweep #2.

## 6. Timing

Per-run cost scaled as expected: with count fixed at 50k, time ∝ `repeat` (10→~13s,
50→~47s, 100→~89s) and time ∝ `evict-kb` (256→~11s, 2048→~47s, 4096→~96s). Full
sweep (33 runs) ≈ 22 min.

## 7. Reproduce

```
./experiments/dial_sweep.sh          # defaults: count=50000, trials=3, this run
```

Config is overridable via environment variables (see the script header / Dial
Sweep #2). Raw per-trial data: `experiments/dial_sweep_results.csv`.
