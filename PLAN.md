# PLAN.md — Experiment runbook (C → Go → Python)

A standing to-do list of every experiment left to run for this study, in
priority order. Each phase is **self-contained and independently runnable** —
you can stop after any phase, and nothing here overwrites a previous phase's
output (every phase uses a unique `RUN_TAG`). Written this way on purpose
because the machine is currently unstable: run one phase, verify it, move on.

**Status so far:** C count-threshold sweep is **done**. Clean 10-trial run
(`RUN_TAG=10x_clean`, seed 10053) puts the C threshold at **≈100,000 traces**
(50% at 100k; 10/10 at ≥200k; ~0/10 at ≤50k). That is the count dimension only —
this plan covers everything still outstanding.

---

## 0. Preconditions — do these before EVERY run

The single biggest risk to this study is background load (an earlier 6-hour run
was ruined by Microsoft Edge being left open). Real timing is only meaningful on
an idle machine. Before launching any phase below:

1. **Quit everything** — browsers (Edge/Chrome), Slack, Docker, Spotlight
   indexing, syncing apps. Then confirm the machine is idle:
   ```bash
   cd /Users/huan/AES-Research-C
   uptime                                # 1-min load average should be < 1.0
   top -l 1 -n 5 -o cpu | head -15     # nothing should be eating CPU
   ```

2. **Baseline speed check (~90 s)** — proves you're back at the ~0.94 ms/sample
   reference before committing hours. Want ≈ 95 s real time; if it's 120 s+, the
   machine is NOT idle — stop and fix that first.
   ```bash
   ./aes_lab keygen /tmp/probe_key.bin
   time ./aes_lab collect-real /tmp/probe_key.bin /tmp/probe.bin 100000 \
     -repeat 50 -evict-kb 2048 > /dev/null 2>&1
   rm -f /tmp/probe.bin /tmp/probe_key.bin
   ```

3. **Launch pattern** — always wrap long runs so they survive sleep and a closed
   terminal. `caffeinate -i` blocks idle-sleep; `nohup ... &` detaches it:
   ```bash
   nohup caffeinate -i env <ENV VARS> ./experiments/<script>.sh \
     > /tmp/<phase>.out 2>&1 &
   tail -f /tmp/<phase>.out       # watch progress; Ctrl-C only stops the tail
   ```

4. **Mid-run health check** — run any time during a sweep. If mean ms/sample
   climbs above ~1.2, something woke up; note it and consider restarting rather
   than finishing a tainted run.
   ```bash
   awk -F, 'NR>1{n++; s+=$9/$1*1000} END{printf "mean %.2f ms/sample over %d runs (want ~0.95)\n", s/n, n}' \
     experiments/<the CSV being written>.csv
   ```

> **Unstable-machine note.** If a phase dies partway, its CSV still holds every
> completed `(count,trial)` row — the plot scripts tolerate partial data. You can
> re-launch the same phase under a `_retry` tag and merge later, or just re-run
> it whole. Never reuse a tag from a completed phase; you'll overwrite good data.

---

# PART A — C (finish this before touching Go/Python)

## Phase C1 — The dials: `-repeat` and `-evict-kb`  ⭐ do this first

**Question:** the count threshold is 100k *at the default dials* (`-repeat 50`,
`-evict-kb 2048`). Can you buy the threshold back by turning the dials up? Does
turning them down break a count that otherwise passes? `-repeat` averages out
timing noise; `-evict-kb` sets how hard the cache is flushed (signal strength).

**Design:** hold the count at the **knee (100,000)** so success sits near 50% and
has room to move both up and down as each dial changes. Sweep one dial at a time
with the other at baseline. 10 trials/point, interleaved, majority vote (≥5/10).

Tooling already exists (`experiments/dial_sweep.sh`). No code changes needed.

```bash
cd /Users/huan/AES-Research-C
nohup caffeinate -i env \
  RUN_TAG=knee100k TRIALS=10 PASS_MIN=5 INTERLEAVE=1 FIXED_COUNT=100000 \
  REPEAT_VALUES="10 20 30 50 75 100" EVICT_VALUES="256 512 1024 2048 4096" \
  ./experiments/dial_sweep.sh > /tmp/dial_knee100k.out 2>&1 &
tail -f /tmp/dial_knee100k.out
```

- **Est. runtime:** ~3–4 h (11 points × 10 trials; cost scales with each dial).
- **Outputs:** `experiments/dial_sweep_knee100k_results.csv`, `_.log`, `_meta.txt`
- **Analyze:**
  ```bash
  python3 experiments/plot_dials.py experiments/dial_sweep_knee100k_results.csv
  ```

**Optional follow-up (C1b) — the "rescue" test.** Repeat the dial sweep at a
*failing* count (50k, which was 0/10) to see whether maxing the dials can lift a
sub-threshold count back to success. Only worth it if C1 shows the dials move the
needle meaningfully.
```bash
RUN_TAG=rescue50k TRIALS=10 PASS_MIN=5 INTERLEAVE=1 FIXED_COUNT=50000 \
  REPEAT_VALUES="50 100 150 200" EVICT_VALUES="2048 4096 8192" \
  ./experiments/dial_sweep.sh
```

## Phase C2 — Key sensitivity

**Question:** the entire count study used **one** fixed key. Is 100k a property
of the attack, or did that key happen to be easy/hard? Re-measure the knee across
several independent keys. This is the cheapest way to make the 100k number
credible rather than anecdotal.

**Prerequisite (tiny):** the harness reuses `experiments/work/key.bin` and has no
key-override knob. Swap the key file between runs by hand (procedure below). If
you'd rather I add a `KEY=<path>` env knob to the script so this is one loop
instead of manual swaps, that's a ~10-line change — ask and I'll do it.

**Manual procedure** — for each of, say, 5 keys, generate it, install it as the
reused key, and run a short knee sweep under a per-key tag:
```bash
cd /Users/huan/AES-Research-C
for i in 1 2 3 4 5; do
  ./aes_lab keygen experiments/work/key.bin        # fresh key, overwrites the reused one
  nohup caffeinate -i env \
    RUN_TAG=key$i TRIALS=10 PASS_MIN=5 INTERLEAVE=1 \
    COUNTS="150000 100000 75000" \
    ./experiments/count_threshold_sweep.sh > /tmp/key$i.out 2>&1
done
```
- Run keys **sequentially** (the `nohup ...` without a trailing `&` above waits
  for each), so only one collection is timing the machine at a time.
- **Est. runtime:** ~40 min per key × 5 ≈ 3.5 h total.
- **Note:** this overwrites `experiments/work/key.bin`. If you want the original
  100k-study key preserved, copy it aside first:
  `cp experiments/work/key.bin experiments/work/key_10x_clean.bin`.
- **Interpret by hand / with a small awk:** for each `key<i>` CSV, tally
  passes at 100k. If all five land near 5/10 at 100k, the threshold is
  key-independent — done. If they scatter widely, the threshold is
  key-dependent and you report a distribution, not a point.

## Phase C3 — (optional) `-repeat` × `-evict-kb` interaction grid

Only if C1 shows **both** dials matter. A full grid reveals whether they trade
off independently or interact. Skip if one dial dominates.
```bash
# Run as a set of dial sweeps, one per fixed evict value, or ask me to add a
# 2-D grid mode to dial_sweep.sh. Left unscripted on purpose — decide after C1.
```

### C deliverable
After C1 (+ C2), write `experiments/count_threshold_full_C_report.md`: the count
threshold (100k, with the clean-run CI table), the dial-response curves, the
key-sensitivity result, and how it all sits vs the paper's 2^15–2^16 band. Note
the count-vs-100k discrepancy with the older ~50k report is a known open item
(grouped-vs-interleaved design; see the July study) — state it, don't hide it.

---

# PART B — Go

## Phase B0 — Prerequisite: teach the harness to target Go (code change)

Both sweep scripts hardcode `BIN="$ROOT/aes_lab"` and `make`. Before any Go run,
add an `IMPL=c|go|python` knob that switches the build step and the binary path.
All three ports already share the identical CLI contract
(`keygen`/`collect-real`/`attack-final`), so this is a clean parameterization,
not a rewrite. **Ask me to implement B0 when you're ready** — it must land and be
smoke-tested (tiny counts) before G1.

Intended shape once B0 exists:
```bash
IMPL=go   # builds go/aes_lab_go and points BIN at it
```

## Phase G1 — Go count sweep (mirror of the C study)

Same counts, trials, and interleaving as the definitive C run, so the two are
directly comparable. **Expectation:** Go's GC + scheduler add timing jitter, so
predict a **higher** threshold than C's 100k — that gap is the headline result.

```bash
cd /Users/huan/AES-Research-C
nohup caffeinate -i env IMPL=go \
  RUN_TAG=go_10x TRIALS=10 PASS_MIN=5 INTERLEAVE=1 \
  COUNTS="500000 400000 300000 250000 200000 150000 100000 75000 60000 50000 45000 40000 35000 30000 25000 20000 10000" \
  ./experiments/count_threshold_sweep.sh > /tmp/go_10x.out 2>&1 &
tail -f /tmp/go_10x.out
```
- **Est. runtime:** ~6 h (Go measured within ~15% of C's per-sample speed).
- **Analyze:** `python3 experiments/plot_threshold.py experiments/count_threshold_go_10x_results.csv`

## Phase G2 — (optional) Go dials
Only after G1. Same as C1 but `IMPL=go`, `FIXED_COUNT=` Go's measured knee.

### Go deliverable
`experiments/count_threshold_Go_report.md` + a **C-vs-Go comparison** (overlay
both success curves; report both 50% thresholds side by side).

---

# PART C — Python (reduced design — it is ~40× slower)

## Reality check first
Measured: Python `collect-real` runs at **≥36 ms/sample** (>180 s for just 5,000
samples), roughly **40× slower** than C. A full-fidelity count sweep would take
on the order of **9 days** — not feasible on this machine. Two honest options:

- **P-reduced (recommended):** a coarse sweep — fewer counts, fewer trials, and
  a smaller `-repeat` to cut per-sample cost — accepting a *rough* threshold.
- **P-null (also valid):** if even the reduced run barely recovers the key,
  report **"the pure-Python target is too noisy to characterize the same way"**
  as the finding. Python's per-encryption interpreter overhead swamps the
  cache-timing signal; that it may not leak exploitably is itself a result.

## Phase P0 — Prerequisite
The `IMPL` knob from **B0** also covers Python (`IMPL=python`). Nothing extra.

## Phase P1 — Python reduced count sweep
Fewer counts, 5 trials, `-repeat 10` (5× cheaper per sample than the C default).
Start high — if Python needs *more* traces than C, the knee may be well above
100k, so include large counts and be ready to extend upward.
```bash
cd /Users/huan/AES-Research-C
nohup caffeinate -i env IMPL=python \
  RUN_TAG=py_reduced TRIALS=5 PASS_MIN=3 INTERLEAVE=1 REPEAT=10 \
  COUNTS="500000 300000 200000 100000 50000" \
  ./experiments/count_threshold_sweep.sh > /tmp/py_reduced.out 2>&1 &
tail -f /tmp/py_reduced.out
```
- **Est. runtime:** rough — at ~7 ms/sample (repeat 10) and ~1.15M total
  sample-units, on the order of **~2–3 h**. Watch the health check; if a single
  point is dragging on for many minutes, kill and drop the largest counts.
- **Analyze:** `python3 experiments/plot_threshold.py experiments/count_threshold_py_reduced_results.csv`
- If nothing passes even at 500k: switch to the **P-null** writeup. Do **not**
  keep escalating counts for days.

### Python deliverable
`experiments/count_threshold_Python_report.md` — the reduced-design caveat, what
was found (a coarse threshold or a null result), and why Python is the noisy
outlier of the three ports.

---

## Master checklist

| Phase | What | Prereq | Runtime | Tag |
|------|------|--------|---------|-----|
| C1 ⭐ | C dials (repeat, evict) @100k | — | ~3–4 h | `knee100k` |
| C1b | C dial "rescue" @50k | after C1 | ~2 h | `rescue50k` |
| C2 | C key sensitivity (5 keys) | key-swap step | ~3.5 h | `key1..5` |
| C3 | C repeat×evict grid | if C1 warrants | TBD | — |
| B0 | Add `IMPL` knob to harness | **code change** | — | — |
| G1 | Go count sweep | B0 | ~6 h | `go_10x` |
| G2 | Go dials | G1 | ~3–4 h | `go_knee` |
| P1 | Python reduced count sweep | B0 | ~2–3 h | `py_reduced` |

**Order:** C1 → C2 → (C1b/C3 if warranted) → B0 → G1 → G2 → P1.

## Things to ask me to do (not runnable as-is)
- **B0** — add the `IMPL=c|go|python` knob to both sweep scripts (blocks all Go
  and Python work).
- **C2 convenience** — optional `KEY=<path>` env knob so key-sensitivity is one
  loop instead of manual file swaps.
- **Reports** — I write each `*_report.md` from the plot/summary output once the
  corresponding clean data exists.

## Invariants (keep every run comparable)
- One fixed key per study arm (except C2, which varies it deliberately).
- `INTERLEAVE=1` always — it's the fix for the grouped-trial bias that muddied
  the earlier study.
- `PASS_MIN=5` for 10-trial runs (a real majority), `PASS_MIN=3` for 5-trial.
- Never commit `*.bin` (keys/traces) — they're gitignored for a reason.
- Always record the seed (the harness logs it to `_meta.txt`); it makes the
  interleave order reproducible.
