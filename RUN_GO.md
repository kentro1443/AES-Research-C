# RUN_GO.md — Go runs (count sweep + dial sweep, one continuous command)

Two Go experiments, back-to-back in a single unattended command:
1. **Count sweep** — vary only the sample count (mirror of the C study).
2. **Dial sweep** — hold count fixed, vary `-repeat` and `-evict-kb`.

## What changed since your last "Go" run (important)

Your previous `go_10x` run was **not Go** — the harness had no way to target Go,
so `IMPL=go` was ignored and it ran the C binary. That's now fixed: both sweep
scripts take `IMPL=c|go|python`. Verified before writing this:
- `IMPL=go` builds with `go build` (log shows `== build (go) ==`, not `make`).
- Go's `min_time` is ~100× C's at the same `-repeat` — genuinely different code.
- **Go reads the same `experiments/work/key.bin` as C** (cross-checked: both
  recover the identical key), so the Go run uses the *same fixed key* as the C
  reference and the comparison is valid.

**Reference for comparison:** C threshold ≈ **50k** (the earliest C run; the
100k `10x_clean` run is treated as contaminated and disregarded).

---

## 0. Before you start — confirm the machine is idle (~1 min)

Background load is what ruins these runs. Quit browsers/Slack/Docker, then:
```bash
cd /Users/huan/AES-Research-C
uptime                              # 1-min load average should be < 1.0
top -l 1 -n 5 -o cpu | head -15     # nothing should be eating CPU
```

---

## 1. THE COMMAND — runs both Go sweeps continuously (~8–9 h total)

Paste this one block. `caffeinate -i` blocks idle-sleep; `nohup ... &` detaches
it so it survives a closed terminal; `&&` means the dial sweep starts only if the
count sweep finished cleanly.

```bash
cd /Users/huan/AES-Research-C
nohup caffeinate -i bash -c '
  IMPL=go RUN_TAG=go_count TRIALS=10 PASS_MIN=5 INTERLEAVE=1 \
    COUNTS="500000 400000 300000 250000 200000 150000 100000 75000 60000 50000 45000 40000 35000 30000 25000 20000 10000" \
    ./experiments/count_threshold_sweep.sh &&
  IMPL=go RUN_TAG=go_dial TRIALS=10 PASS_MIN=5 INTERLEAVE=1 FIXED_COUNT=100000 \
    BASE_REPEAT=50 BASE_EVICT=2048 \
    REPEAT_VALUES="10 20 30 50 75 100" EVICT_VALUES="256 512 1024 2048 4096" \
    ./experiments/dial_sweep.sh
' > /tmp/go_both.out 2>&1 &
echo "launched PID $! — both Go sweeps will run back-to-back"
```

- **Count sweep** (~6 h): same 17 counts as the C study, so the Go threshold is
  directly comparable to C's ~50k.
- **Dial sweep** (~3–4 h): count fixed at **100,000** — byte-for-byte identical
  config to your C `knee100k` dial run (same count, `BASE_REPEAT=50`,
  `BASE_EVICT=2048`, same `-repeat`/`-evict-kb` value lists, 10 trials,
  interleaved). Language is the only variable.
- Both: 10 trials/point, interleaved (seed logged to the meta file), majority
  vote ≥5/10.

**Outputs:**
| Sweep | Results CSV | Log | Meta |
|---|---|---|---|
| count | `experiments/count_threshold_go_count_results.csv` | `count_threshold_sweep_go_count.log` | `count_threshold_go_count_meta.txt` |
| dial  | `experiments/dial_sweep_go_dial_results.csv` | `dial_sweep_go_dial.log` | `dial_sweep_go_dial_meta.txt` |

---

## 2. Watch it (optional)

```bash
tail -f /tmp/go_both.out                       # live progress + ETA
```

**Health check** — run any time; mean should stay near ~0.95 ms/sample. If it
climbs past ~1.2, something woke up — note it, consider restarting:
```bash
awk -F, 'NR>1{n++; s+=$9/$1*1000} END{printf "count sweep: mean %.2f ms/sample over %d runs\n", s/n, n}' \
  experiments/count_threshold_go_count_results.csv
```

---

## 3. Analyze (after it finishes)

```bash
python3 experiments/plot_threshold.py experiments/count_threshold_go_count_results.csv
python3 experiments/plot_dials.py     experiments/dial_sweep_go_dial_results.csv
```
Each prints a per-point table with 95% CIs and the fitted 50% threshold, and
writes PNG/SVG plots + a summary CSV into `experiments/plots/`.

---

## Notes

- **Confirm it's really Go while it runs:** `grep '== build' experiments/count_threshold_sweep_go_count.log`
  should say `(go)`, and `grep '^impl' experiments/count_threshold_go_count_meta.txt`
  should say `go`. (Belt-and-suspenders against the previous mislabel.)
- **Fresh tags** (`go_count`, `go_dial`) — these do **not** overwrite the old
  contaminated `go_10x` files.
- **Controlled comparison:** every knob here matches the corresponding C run —
  same counts, dials, trials, key, interleaving. `IMPL` (c vs go) is the only
  independent variable, so any difference in the result is attributable to the
  language port and nothing else. The dial run in particular is identical to the
  C `dial_sweep_knee100k` run (count=100k).
- **Reproducibility caveat:** C's threshold wandered ~50k↔100k across runs on
  this machine. A single Go sweep is one draw from that distribution too — if you
  want a defensible "Go vs C" claim, plan to repeat the paired command a couple
  of times and compare distributions, not single numbers.
