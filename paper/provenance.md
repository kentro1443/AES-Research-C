# Dataset provenance and inclusion decisions

All runs: Apple M4, 10 logical cores, 16 GiB, Darwin arm64, source commit
`405b3de` (working tree dirty — the experiment harness under `experiments/` was
modified in place; the C/Go attack sources were not). One fixed AES key
(`experiments/work/key.bin`) is reused across every run so that trace count,
dials, and implementation are the only things that vary.

Shared count-sweep config (unless noted): 17 counts
`{500k,400k,300k,250k,200k,150k,100k,75k,60k,50k,45k,40k,35k,30k,25k,20k,10k}`,
10 trials/count, interleaved, `-repeat 50`, `-evict-kb 2048`, majority vote ≥5/10.
Shared dial config: count fixed 100k, `-repeat ∈ {10,20,30,50,75,100}`,
`-evict-kb ∈ {256,512,1024,2048,4096}`, 10 trials, interleaved.

## Included runs

| Role | File (stem) | Impl | Seed | Date (UTC) | Recovery | Note |
|---|---|---|---|---|---|---|
| **C count — canonical** | `count_threshold_go_10x` | **C** | 4175 | 2026-08-04 | 97/170 | N50 ≈ 51,346 (2¹⁵·⁶). Clean env (0.942 ms/sample). See relabel note. |
| C count — replicate | `count_threshold_10x_clean` | C | 10053 | 2026-07-31 | 64/170 | Clean env; N50 ≈ 100k. Reported for run-to-run variability only. |
| **C dial — canonical** | `dial_sweep_knee100k` | C | 11065 | 2026-08-04 | 57/110 | The informative dial sweep (100k ≈ C's knee). |
| **Go(GC on) count** | `count_threshold_go_count` | Go | 14778 | 2026-08-04 | 32/170 | N50 ≈ 265,283 (2¹⁸·⁰). |
| **Go(GC on) dial** | `dial_sweep_go_dial` | Go | 20346 | 2026-08-04 | 1/110 | Uninformative: 100k ≪ Go threshold. |
| **Go(GC off) count** | `count_threshold_go_gcoff_count` | Go | 9744 | 2026-08-05 | 15/40 | Reduced grid: counts {500k,250k,100k,50k} only. `GOGC=off GOMAXPROCS=1`. |
| **Go(GC off) dial** | `dial_sweep_go_gcoff_dial` | Go | 31480 | 2026-08-05 | 1/60 | Reduced 3×3 grid. Uninformative (same reason). |

## Excluded runs

| File (stem) | Reason for exclusion |
|---|---|
| `count_threshold_10x` (seed 23394) | **Contaminated environment** — 2.997 ms/sample (≈3× baseline), wide `min_time` spread [109–146]. Its inflated N50 (~150k) reflects background load, not the attack. |
| `count_threshold` (seed 17941) | Exploratory 3-trial pilot (16/51); superseded by the 10-trial runs. |
| `count_threshold_knee` (no meta) | Exploratory 8-trial knee probe; no reproducibility sidecar. |
| `count_threshold_v150k`, `dial_sweep_150k`, `dial_sweep_pothole`, `dial_sweep` | Exploratory single-point / pilot sweeps used to design the final grids. |

## Relabel note (critical for reproducibility)

The canonical C count run is stored under the misleading stem
`count_threshold_go_10x`. It was launched with `IMPL=go` **before the
language-selector knob existed in the harness**, so the environment variable was
silently ignored and the **C binary actually executed**. It is therefore C data,
verified three ways: (i) meta has no `impl` field (pre-knob); (ii) `min_time`
(~112–121 ticks) matches C and is ~300–500× smaller than genuine Go runs;
(iii) 0.942 ms/sample matches the C baseline. The file is retained under its
original name for auditability; analyses and the paper treat it as **C**.

An earlier analysis mistakenly tallied the `result` column by position and
reported this and the Go runs incorrectly (e.g. a spurious "Go 0/170"). All
tallies in the paper are recomputed by column *name* via
`experiments/plot_threshold.py` and cross-checked.
