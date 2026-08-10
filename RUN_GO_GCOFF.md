# RUN_GO_GCOFF.md — smaller Go run, garbage collector OFF

**Hypothesis being tested:** the full Go run recovered the key only **1 / 280**
times (vs C's ~52% at 100k) because Go's runtime noise (GC pauses + goroutine
scheduling) buries the cache-timing leak. If that's right, quieting the runtime
should bring some recoveries back.

**The change vs the previous Go run:** exactly two environment variables —
everything else (key, counts, dials, trials, interleaving) is held identical, so
this is a clean **Go(GC-on) vs Go(GC-off)** comparison.

- `GOGC=off` — disables Go's garbage collector, so no GC pauses land in the
  middle of a timing measurement. (Heap just grows; fine at these sizes.)
- `GOMAXPROCS=1` — pins Go to one core, so the scheduler doesn't migrate the
  work mid-run.

These are standard Go runtime variables read straight from the environment — no
edit to `go/main.go` is required.

**Smaller than last time:** 4 counts (not 17) and a 3×3 dial grid (not 6×5), so
the whole thing is **~3.5 h** instead of ~7.5 h. All 4 counts and the dial point
are a subset of the previous Go run, so every number here has a direct
GC-on counterpart to compare against.

---

## 0. Before you start — machine idle (~1 min)

```bash
cd /Users/huan/AES-Research-C
uptime                              # 1-min load average should be < 1.0
top -l 1 -n 5 -o cpu | head -15     # nothing eating CPU
```

---

## 1. THE COMMAND — trimmed count + dial, GC off, one continuous run (~3.5 h)

```bash
cd /Users/huan/AES-Research-C
nohup caffeinate -i bash -c '
  GOGC=off GOMAXPROCS=1 IMPL=go RUN_TAG=go_gcoff_count TRIALS=10 PASS_MIN=5 INTERLEAVE=1 \
    COUNTS="500000 250000 100000 50000" \
    ./experiments/count_threshold_sweep.sh &&
  GOGC=off GOMAXPROCS=1 IMPL=go RUN_TAG=go_gcoff_dial TRIALS=10 PASS_MIN=5 INTERLEAVE=1 FIXED_COUNT=100000 \
    BASE_REPEAT=50 BASE_EVICT=2048 \
    REPEAT_VALUES="10 50 100" EVICT_VALUES="256 2048 4096" \
    ./experiments/dial_sweep.sh
' > /tmp/go_gcoff.out 2>&1 &
echo "launched PID $! — Go GC-off: trimmed count (~2h) then dial (~1.5h)"
```

- **Count sweep** (~2 h): 500k / 250k / 100k / 50k, 10 trials each. Previous Go
  scored **0/10 at every one of these.** Any nonzero here = GC noise was the cause.
- **Dial sweep** (~1.5 h): count fixed 100k; `-repeat` ∈ {10,50,100},
  `-evict-kb` ∈ {256,2048,4096}. `repeat=100` is where Go's lone pass appeared —
  GC-off + max averaging is the most likely place to recover.

**Outputs:**
| Sweep | Results CSV | Meta |
|---|---|---|
| count | `experiments/count_threshold_go_gcoff_count_results.csv` | `count_threshold_go_gcoff_count_meta.txt` |
| dial  | `experiments/dial_sweep_go_gcoff_dial_results.csv` | `dial_sweep_go_gcoff_dial_meta.txt` |

---

## 2. Watch it (optional)

```bash
tail -f /tmp/go_gcoff.out
```

**Memory watch** — GC-off means the heap only grows. At these sizes it should
stay well under a GB, but if you want to be sure nothing balloons:
```bash
top -l 1 -pid $(pgrep -f aes_lab_go) -stats mem 2>/dev/null | tail -3
```
If memory climbs toward multiple GB, stop and tell me — we'd switch `GOGC=off`
to a high-but-finite value like `GOGC=800` instead.

---

## 3. Analyze — the whole point is the before/after

```bash
# GC-off vs the previous GC-on Go run, count-by-count
echo "count   GCoff   GCon(prev)"
for c in 500000 250000 100000 50000; do
  off=$(awk -F, -v c=$c 'NR>1 && $1==c{n++; if($5=="PASS")p++} END{printf "%d/%d", p+0, n}' \
        experiments/count_threshold_go_gcoff_count_results.csv)
  on=$(awk -F, -v c=$c 'NR>1 && $1==c{n++; if($5=="PASS")p++} END{printf "%d/%d", p+0, n}' \
        experiments/count_threshold_go_count_results.csv)
  printf "%-7s %-7s %s\n" "$c" "$off" "$on"
done
```

Then the full plots if you want them:
```bash
python3 experiments/plot_threshold.py experiments/count_threshold_go_gcoff_count_results.csv
python3 experiments/plot_dials.py     experiments/dial_sweep_go_gcoff_dial_results.csv
```

**Reading the result:**
- **Passes appear** → confirmed: the Go gap was runtime noise, not the port. That's
  a real, publishable sub-finding. Next step would be scaling this back up.
- **Still ~0** → the noise is deeper than GC (timer resolution / interpreter of the
  timing loop). Also worth knowing — it says the leak is genuinely below Go's
  measurement floor on this machine.

---

## Notes

- **Confirm it's really Go + GC-off:** `grep '== build' experiments/count_threshold_sweep_go_gcoff_count.log`
  should say `(go)`. The env vars don't get logged by the runtime, but they're on
  the command line above, so the Go processes inherit them.
- **Fresh tags** (`go_gcoff_count`, `go_gcoff_dial`) — these do not overwrite the
  earlier `go_count` / `go_dial` files, so the comparison stays intact.
- **Second variable, on purpose:** unlike the strict "IMPL is the only variable"
  runs, this one deliberately changes the Go runtime (GC + core count) to isolate
  *why* Go failed. That's why it has its own tag and its own runbook.
