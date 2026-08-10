# SCRIPT.md — Mentor presentation (AES cache-timing study)

> A ready-to-deliver talk (~12–15 min). Each section has **[SHOW]** (which
> figure/table to put up), **[SAY]** (spoken script), and **numbers to cite**.
> Figures are in `experiments/plots/` (PNG+SVG); tables are in `paper/paper.pdf`.
> Open `paper/paper.pdf` alongside for tables.

---

## 0. One-line thesis (memorize this)
**"On a modern Apple M4, our C attack recovers an AES-128 key from ~50,000 timing
traces; the *same* attack written in Go needs ~5× more — and we show that gap is
runtime measurement *noise*, not the garbage collector or raw speed."**

---

## 1. Motivation & problem (1–2 min)
**[SHOW]** nothing / title slide.
**[SAY]** "AES is mathematically strong, but its *implementation* can leak. Old
table-driven AES indexes lookup tables with key-dependent bytes, so cache
hits/misses — and therefore timing — depend on the key. Bonneau and Mironov
turned this into a key-recovery attack using *cache collisions*: when two
ciphertext bytes collide in the final round, their timing is slightly lower, and
that reveals a relation between two key bytes. We built a controlled lab that
implements this attack and asks two questions:
 1. **How many traces** do you actually need? and
 2. Does that number change with the **language** the attack is written in — C vs
    Go vs Python?"

**Cite:** the attack recovers *relative* key bytes from 120 ciphertext-byte pairs
(⁠16 choose 2⁠), then brute-forces one 256-value offset and *cryptographically
verifies* the key against a stored plaintext/ciphertext pair. Success is
objective: exit 0 = verified key, exit 2 = fail.

---

## 2. Method in one breath (1–2 min)
**[SAY]** "For each trace: random plaintext, flush the cache with a 2 MB buffer,
time 50 repeated encryptions, store it. We collect N traces, group by
ciphertext-byte differences, average each group's timing, score all 120 pairwise
tables, and recover + verify the key. Because timing is noisy, recovery is
**probabilistic**, not pass/fail — so we run **10 trials per trace count** and
report the **success rate with 95% Wilson confidence intervals**, and fit a
**logistic curve** whose 50% point (N50) we call the threshold. Everything is held
fixed — one key, same parameters, interleaved run order — so the only thing that
varies is what we intend to vary."

---

## 3. RESULT 1 — The C threshold (2 min)
**[SHOW]** `experiments/plots/go_10x_success_rate.png`  (paper Fig. 1 / Table 1)
**[SAY]** "This is the headline curve for C. X-axis is trace count on a log₂
scale, y-axis is recovery rate, error bars are 95% Wilson intervals, the red curve
is the logistic fit. The 50% threshold is **N50 ≈ 51,000 traces**. Below ~35k it
essentially never works; by 75k it's 90% reliable; by 100k it's 100%."

**[SHOW]** `experiments/plots/go_10x_covariates.png`  (paper Fig. 2)
**[SAY]** "Crucially, the threshold is a *statistical* effect, not a signal
cliff. These two plots show the minimum timing and the attack score are **flat**
across every trace count. The per-trace leak doesn't change — what changes is how
*stable* the averages are. More traces = cleaner averages = the correct key
relation wins. That's why we get a smooth psychometric curve, not a hard edge."

**Cite:** N50 ≈ 51,346 (2^15.6); 90% at ~75k; min_time 112–121 ticks and score
~17,300 flat throughout.

---

## 4. RESULT 2 — The cross-language gap (2–3 min, the core finding)
**[SHOW]** `experiments/plots/cross_language_recovery.png`  (paper Fig. 3 / Table 2)
**[SAY]** "Now the same attack, same key, same parameters — but each language
collects its own traces. C is the blue curve on the left. Go, with the garbage
collector on (red) and off (green), sits **~5× to the right**: Go's threshold is
**N50 ≈ 265,000 vs C's ~51,000**. So writing the identical attack in a managed
runtime costs you about five times as many traces."

**[SAY continued]** "The natural guess is 'Go is just slower,' but that's not it —
and I can show *why*."

---

## 5. RESULT 3 — Why? GC ablation + timer normalization (2–3 min, the clincher)
**[SHOW]** paper Table 3 (GC on vs off) and Table 5 (per-stage cost).
**[SAY]** "Two pieces of evidence.

**First, we turned the garbage collector off** (`GOGC=off`) and pinned one core
(`GOMAXPROCS=1`). If GC pauses were the cause, the threshold should drop a lot. It
barely moved — 265k to 243k, about 8%, and the gap to C stayed. So it's **not the
garbage collector**.

**Second, we normalized the timers.** The three languages use different clocks —
C counts Apple mach-ticks at 41.67 ns each, Go and Python already report
nanoseconds — which is why raw numbers looked 100× apart. Once converted, Go's
*mean* time per encryption is only **~2.4× C's**, nowhere near the 5× threshold
gap. So the gap isn't mean overhead either.

**Conclusion:** the 5× is driven by **variance** — Go's managed runtime (bounds
checks, scheduler, coarser timing) makes each measurement *noisier*, so you need
more traces to average the noise down. The attack is the same; the *measurement
quality* differs."

**Cite:** GC off 265k→243k (~8%); per-encryption C 99 ns, Go 235 ns (2.4×),
Python 41,894 ns (~420×).

---

## 6. RESULT 4 — Python is infeasible (1–2 min)
**[SHOW]** paper Table 6 (Python feasibility).
**[SAY]** "Python we treat as a feasibility question, because it's an interpreter.
We measured it: ~51 ms per sample to collect and ~15 ms per sample to attack —
about 55× and 1800× slower than C. Extrapolating: a single trial at C's threshold
takes ~55 minutes and would still fail; a full characterization like we did for C
and Go would take **~17 days** of continuous compute. And because the interpreter
also inflates *variance*, Python's threshold is likely even higher than Go's. So
pure-Python measured recovery is **infeasible on this platform — not just slow.**
Python stays as a readable reference implementation."

---

## 7. RESULT 5 — Dials (optional, 1 min)
**[SHOW]** `experiments/plots/knee100k_dials.png`  (paper Fig. 4 / Table 4)
**[SAY]** "We also swept the two collection knobs at a fixed 100k count for C.
Takeaway: *stronger cache eviction* helps (biggest buffer → 100% recovery), but
*more repetition* doesn't — near the threshold, signal strength matters more than
extra averaging. One honest note: we couldn't probe Go's dials because we fixed
100k, which is below Go's threshold — a lesson for the next round."

---

## 8. Positioning & rigor (1 min)
**[SAY]** "Versus the original Bonneau–Mironov paper, which reports a median of
about 2^13–2^14 samples on 2006 hardware, our C threshold is roughly an order of
magnitude higher. That's expected: they used hardware cycle counters on a Pentium
III; we use aggregate wall-clock timing on an Apple M4 — different cache
hierarchy, coarser timer. Reproducing the mechanism to within an order of
magnitude on completely different hardware is actually a good sign. On rigor:
Wilson intervals, logistic fits, interleaved trials, an environment gate that
excludes background-load-contaminated runs, and cryptographic verification of
every recovered key."

---

## 9. Contributions & close (1 min)
**[SAY]** "To summarize our contributions:
 1. A statistically grounded trace threshold for this attack on modern hardware.
 2. The first controlled cross-language measurement of that threshold — Go needs ~5×.
 3. A garbage-collector ablation showing the gap is measurement noise, not GC.
 4. A timer-normalized cost comparison separating mean overhead from variance.
 5. A feasibility bound showing pure-Python recovery is impractical.
The big-picture message: **the practical cost of a cache-timing attack depends on
the implementation runtime, not only on the algorithm.** Next steps are a
shared-dataset consistency test across the three ports and multi-key
generalization."

---

## 10. Likely mentor questions — and answers

- **"Why is your C number ~10× Bonneau–Mironov?"** Different platform + timer
  (Apple M4 wall-clock vs 2006 cycle counters); the leakage mechanism still
  reproduces within an order of magnitude. It's a platform constant, not a
  contradiction.
- **"Is the 5× Go gap just one noisy run?"** N50 is a fitted value over 170
  trials with CIs; GC-on and GC-off (independent seeds) both land ~5×, and the
  matched-count table shows the same ordering. We flag n=10 uncertainty honestly
  and propose repeating paired runs.
- **"Could Go's gap be the timer resolution, not variance per se?"** Possibly —
  we localize it to the managed-runtime measurement path (GC ruled out; mean
  overhead ruled out). Pinning the exact sub-cause (timer granularity vs scheduler
  jitter) is stated as future work.
- **"Did you confirm the three ports implement the same attack?"** They recover
  the same key from the same *synthetic* data; a formal *shared-dataset* recovery
  match is the first item of future work.
- **"Why exclude one C run?"** Objective environment gate: it ran at ~3.0
  ms/sample (~3× baseline) with wide min_time — background load — so it's excluded
  with its metadata preserved (no cherry-picking).
- **"One key only?"** Yes, to isolate trace count; multi-key generalization is
  future work — stated as a limitation.

---

## 11. Cheat-sheet (numbers to have on the tip of your tongue)
- C threshold **N50 ≈ 51k** (2^15.6); 90% at ~75k; 100% by 100k.
- Go **N50 ≈ 265k**, GC-off **243k** → **~5× C**; GC-off only ~8% change.
- Per-encryption: C **99 ns**, Go **235 ns (2.4×)**, Python **41,894 ns (~420×)**.
- Python: ~51 ms/sample collect, ~15 ms attack → full sweep **~17 days**.
- Bonneau–Mironov median **2^13–2^14.3**; ours ~1 order of magnitude higher.
- Rigor: 10 trials/count, 95% Wilson CIs, logistic N50, interleaved, verified keys.

## 12. Files to have open during the talk
- `paper/paper.pdf` — for all tables (1–7) and the figures in context.
- `experiments/plots/go_10x_success_rate.png` — Fig 1 (C threshold).
- `experiments/plots/cross_language_recovery.png` — Fig 3 (the money slide).
- `experiments/plots/go_10x_covariates.png` — Fig 2 (flat → statistical).
- `experiments/plots/knee100k_dials.png` — Fig 4 (dials, optional).
