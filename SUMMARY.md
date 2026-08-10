# SUMMARY.md — Complete project handoff (AES cache-timing study)

> Purpose: a fresh chat/agent (or the user) can read this file and continue the
> work with full context. Everything decided, measured, built, and still open is
> recorded here. Last updated: 2026-08-05.

---

## 1. What this project is

Educational, **local-only** lab studying **AES-128 cache-timing key recovery**
against a deliberately vulnerable, table-driven AES target. Implements the
**Bonneau–Mironov final-round cache-collision attack**. Three independent,
standard-library-only ports kept manually in sync, sharing one CLI contract:

| Language | Entry point | Role |
|---|---|---|
| C | `src/aes_lab.c` → `./aes_lab` | primary/reference |
| Go | `go/main.go` → `go/aes_lab_go` | port |
| Python | `python/aes_lab.py` | port |

CLI contract (identical across ports): `selftest, keygen, collect, collect-real,
attack-final, verify`. Exit code **0 = key recovered & verified**, **2 = failed**.
`*.bin` files (keys/traces) are gitignored, unencrypted, contain key material —
**never commit them**.

The research goal: (a) find the **measured trace-count threshold** of the attack,
and (b) hold the algorithm fixed and vary only the **implementation language** to
see how the runtime affects that threshold. This is the user's **first formal
research study**; it is intended for **publication + a competition**.

---

## 2. THE DELIVERABLE — the paper (DONE)

Complete, compiled, verified **13-page paper**:
- **`paper/paper.tex` → `paper/paper.pdf`** (single-column `article`, ~13 pp).
- Compile: `cd paper && tectonic paper.tex` (Tectonic installed at
  `/opt/homebrew/bin/tectonic` via Homebrew — no sudo; first run downloads a
  package bundle, later runs are seconds).
- Structure: Abstract → Introduction (Contributions + 4 RQs) → Background →
  Related Work → Methodology → Results → Analysis & Discussion → Conclusion &
  Future Work → Appendix (provenance) → References.
- Status: builds clean; only a cosmetic 18 pt overfull-hbox on a bibliography URL
  (invisible in output). All 7 tables + 4 figures render; citations [1]–[6] resolve.

Supporting files in `paper/`:
- `references.bib` — 6 refs (FIPS-197, Kocher, Bernstein, Bonneau–Mironov,
  Osvik–Shamir–Tromer, Neve–Seifert–Wang).
- `results.tex`, `analysis.tex`, `methodology_additions.tex` — drop-in fragments
  (also assembled inside `paper.tex`); plus `.md` mirrors.
- `paper_supplement.tex/.pdf` — earlier reading-copy of just Results+Analysis
  (superseded by `paper.tex` but kept).
- `provenance.md` — dataset governance table.
- `draft_errata.md` — the 6 fixes vs the original `foundation/draft1.pdf`.

There is also a project memory at
`~/.claude/projects/-Users-huan-AES-Research-C/memory/aes-paper-datasets.md`.

---

## 3. EVERY DECISION MADE (with rationale)

### 3.1 Standing methodological principle
**"IMPL (language) is the ONLY independent variable."** Across every
cross-language comparison, hold identical: counts, fixed key, dials
(`-repeat`/`-evict-kb`), `TRIALS`, `PASS_MIN`, `INTERLEAVE`, seed policy. Any
outcome difference is then attributable to the language runtime alone. (The GC
ablation is a *deliberate* second variable, given its own tag.)

### 3.2 Canonical dataset decisions (IMPORTANT — easy to get wrong)
There are THREE C count sweeps at identical config. Decision:
- **CANONICAL C = `experiments/count_threshold_go_10x_results.csv` (seed 4175)**,
  **relabeled Go→C**. It was launched with `IMPL=go` *before the language selector
  existed in the harness*, so the environment variable was ignored and the **C
  binary actually ran**. Verified C by: no `impl` field in meta (pre-knob),
  `min_time` and 0.94 ms/sample matching C. Clean run, **N50 ≈ 51,346 (2^15.6)**,
  97/170. This is the paper's headline C result.
- **C replicate (clean, ~100k): `count_threshold_10x_clean` (seed 10053)**, 64/170.
  Reported only as run-to-run variability context.
- **EXCLUDED as contaminated: `count_threshold_10x` (seed 23394)** — the
  *earliest* run. Objectively bad environment: **2.997 ms/sample (~3× baseline)**,
  wide `min_time` [109–146], threshold ~150k. The user initially said "use the
  earliest one / isn't it ~50k?" but the earliest run is actually the contaminated
  ~150k one; after seeing the ms/sample evidence the user confirmed: **use seed
  4175 (the ~50k, latest, relabeled-from-Go run).**

### 3.3 The column-parse bug (do not repeat)
An earlier tally read the **wrong CSV column** (used `$3` = repeat) and produced a
false **"Go 0/170 — Go never recovers."** Corrected: count CSV `result = column 5`,
dial CSV `result = column 6`. **Always tally by column NAME** (the plot scripts do
this). Real Go count = 32/170; Go does recover, just needs ~5× more traces.

### 3.4 The "Go beats C" illusion (root cause)
Very early, a run tagged `go_10x` looked like "Go beats C." Investigation showed
the **IMPL knob did not exist yet**, so `IMPL=go` silently ran the C binary — it
was C data mislabeled as Go. This is the same file now used as **canonical C**
(seed 4175). After this discovery, the `IMPL=c|go|python` selector was built into
`experiments/count_threshold_sweep.sh` and `dial_sweep.sh`, so later Go runs are
genuinely Go.

### 3.5 GC ablation decision
Hypothesis: Go's higher threshold is runtime noise. Test with **`GOGC=off`**
(disable garbage collector) + **`GOMAXPROCS=1`** (pin one core) — env vars read by
the Go runtime, no source change. Result: threshold moves only ~8% (265k→243k),
gap to C intact → **GC is NOT the cause; it's broad measurement noise.**

### 3.6 Timer-unit finding (resolved a footnote → sharp claim)
The three ports use different clocks:
- C: `mach_absolute_time()` — Apple-Silicon timebase **24 MHz → 41.667 ns/tick**
  (confirmed via `sysctl -n hw.tbfrequency` = 24000000).
- Go: `time.Since().Nanoseconds()` — nanoseconds.
- Python: `time.perf_counter_ns()` — nanoseconds.
So raw `min_time` looked ~100× apart purely from units. **Normalized per
encryption: C 99 ns, Go 235 ns (~2.4×), Python 41,894 ns (~420×).** Conclusion:
mean overhead (2.4× Go) ≠ the 5× threshold gap → gap is **variance-driven**.

### 3.7 Python decision
Full Python recovery is infeasible (~weeks; likely ~0 recoveries). Approach
chosen: **run a small clean probe → measure ms/sample → extrapolate net time →
show it's virtually impossible.** Framed as a runtime-feasibility result, not a
recovery result. Python recovery **deferred to future work** in the paper.

### 3.8 Paper-writing decisions (confirmed with user)
- **Format:** single-column LaTeX `article` (matches draft), ~10–14 pp.
- **Scope:** fully **integrate & revise** — one cohesive paper; tighten draft's
  Intro/Methodology, fix all 6 errata inline, add Abstract, Related Work, Results,
  Analysis, Conclusion.
- **Python probe:** the agent runs a small clean probe when the machine is idle.
- **Foundational papers:** refer to them, but only occasionally / where needed
  (user said don't over-compare).

### 3.9 Reference correction
`foundation/ref.md` reference [4] (Bonneau–Mironov) cited an **ACM DOI that
actually resolves to a different paper** — Neve–Seifert–Wang, "A Refined Look at
Bernstein's AES Side-Channel Analysis" (ASIACCS 2006). The user then supplied the
**correct** Bonneau–Mironov CHES 2006 PDF (`foundation/bonneau.pdf`). Paper's
`references.bib` now has the correct [4] and adds Neve–Seifert–Wang as [6].

---

## 4. KEY NUMBERS (all verified, all in the paper)

### Trace-count thresholds (logistic N50, Wilson CIs)
| Impl | N50 | log2 | vs C |
|---|---|---|---|
| **C** (seed 4175) | **51,346** | 15.65 | 1.0× |
| Go GC on (14778) | 265,283 | 18.02 | **5.2×** |
| Go GC off (9744) | 243,335 | 17.89 | 4.7× |

- C 90%-reliable threshold ≈ **75k** (9/10 at 75k, 10/10 at ≥100k).
- C `min_time` 112–121 ticks, score ~17,200–17,460 — **flat** across counts →
  statistical knee (averaging), not a signal cliff.

### GC ablation (matched counts, Go)
| count | GC on | GC off |
|---|---|---|
| 500k | 8/10 | 9/10 |
| 250k | 4/10 | 6/10 |
| 100k | 0/10 | 0/10 |
| 50k | 0/10 | 0/10 |
GC-off equal-or-better at every matched count, but N50 barely moves (~8%).

### C dial sweep @ 100k
- `-repeat`: 10→60%, 20→50%, 30→50%, 50→70%, 75→20%, 100→20% (more repeat ≠ help).
- `-evict-kb`: 256→80%, 512→60%, 1024→10%, 2048→50%, 4096→**100%** (stronger
  eviction helps). Go dial ≈0 (1/110, 1/60) — 100k is below Go's threshold
  (design lesson, not a null result).

### Cross-language cost (clean probe, r=50, e=2048)
| Impl | collect ms/sample | attack ms/sample | per-enc (ns) | ×C |
|---|---|---|---|---|
| C | 0.93 | 0.008 | 99 | 1.0 |
| Go | 0.84 | 0.013 | 235 | 2.4 |
| Python | 51.3 | 14.6 | 41,894 | ~420 |
Python ≈ 55× C (collect), ≈ 1800× C (attack).

### Python feasibility (≈65.9 ms/sample collect+attack)
| Workload | Time |
|---|---|
| 1 trial @ 50k (C's N50) | ~55 min (would still fail) |
| 1 trial @ 265k (Go's N50) | ~4.9 h |
| Full 17-count × 10-trial sweep | ~17 days |

### Prior-work comparison
Bonneau–Mironov expanded final-round, **L2 eviction, median 2^13–2^14.3**
(8,192–20,251) on 2006 Pentium III/UltraSPARC. Our C N50 (~50k, 2^15.6) is
**~2.5–6×** their median; 90% (~75k) ≈ **9×** the 2^13 headline. ~1 order of
magnitude higher — expected given platform + instrument confound (Apple M4 +
wall-clock vs their cycle counters).

---

## 5. ALL DATA FILES (in `experiments/`)

### Included (canonical) — used in the paper
| Role | file stem | impl | seed | recovery |
|---|---|---|---|---|
| C count canonical | `count_threshold_go_10x` | C | 4175 | 97/170 |
| C count replicate | `count_threshold_10x_clean` | C | 10053 | 64/170 |
| C dial | `dial_sweep_knee100k` | C | 11065 | 57/110 |
| Go count (GC on) | `count_threshold_go_count` | Go | 14778 | 32/170 |
| Go dial (GC on) | `dial_sweep_go_dial` | Go | 20346 | 1/110 |
| Go count (GC off) | `count_threshold_go_gcoff_count` | Go | 9744 | 15/40 (4 counts) |
| Go dial (GC off) | `dial_sweep_go_gcoff_dial` | Go | 31480 | 1/60 (3×3) |

All at commit `405b3de` (working tree dirty = harness edited in place; attack
sources unchanged). Each `*_results.csv` has a `*_meta.txt` sidecar and a
`*_summary.csv` (aggregated rate + Wilson CI) from the plot scripts.

### Excluded (kept for audit)
- `count_threshold_10x` (seed 23394) — **contaminated** (~3.0 ms/sample) → ~150k.
- `count_threshold` (seed 17941) — 3-trial pilot.
- `count_threshold_knee` — 8-trial pilot, no meta.
- `count_threshold_v150k`, `dial_sweep_150k`, `dial_sweep_pothole`, `dial_sweep`
  — single-point / pilot sweeps used for design only.

---

## 6. TOOLING

- `experiments/count_threshold_sweep.sh` — count sweep. Env knobs: `IMPL`
  (c|go|python), `REPEAT`, `EVICT_KB`, `TRIALS`, `PASS_MIN`, `RUN_TAG`,
  `INTERLEAVE`, `SEED`, `COUNTS`. Writes CSV + log + meta.
- `experiments/dial_sweep.sh` — dial sweep. Env knobs add `FIXED_COUNT`,
  `BASE_REPEAT`, `BASE_EVICT`, `SWEEPS`, `REPEAT_VALUES`, `EVICT_VALUES`.
- `experiments/plot_threshold.py` — per-count Wilson CIs + logistic N50 +
  interpolated crossover + figures (`plots/<tag>_success_rate`, `_covariates`,
  `_runtime`) + `<stem>_summary.csv`. Needs matplotlib+numpy (installed: 3.9/2.0).
- `experiments/plot_dials.py` — dial analysis + `plots/<tag>_dials`.
- `experiments/plot_compare.py` — NEW: cross-language overlay
  (`plots/cross_language_recovery`). Usage:
  `python3 plot_compare.py "C=<csv>" "Go (GC on)=<csv>" "Go (GC off)=<csv>"`.
- Figures in `experiments/plots/` (PNG+SVG). The paper uses: `go_10x_success_rate`,
  `go_10x_covariates`, `cross_language_recovery`, `knee100k_dials`.

### Runbooks (agent-authored, user-run) at repo root
`RUN_GO.md` (Go count+dial), `RUN_GO_GCOFF.md` (GC-off run), `PLAN.md` (master
run plan). These are already-executed; kept for reference.

### How to reproduce the analysis from raw CSVs
```bash
python3 experiments/plot_threshold.py experiments/count_threshold_go_10x_results.csv    # C
python3 experiments/plot_threshold.py experiments/count_threshold_go_count_results.csv  # Go on
python3 experiments/plot_threshold.py experiments/count_threshold_go_gcoff_count_results.csv # Go off
python3 experiments/plot_dials.py     experiments/dial_sweep_knee100k_results.csv
python3 experiments/plot_compare.py "C=experiments/count_threshold_go_10x_results.csv" \
  "Go (GC on)=experiments/count_threshold_go_count_results.csv" \
  "Go (GC off)=experiments/count_threshold_go_gcoff_count_results.csv"
cd paper && tectonic paper.tex
```

---

## 7. THE 6 DRAFT ERRATA (all fixed in paper.tex; see paper/draft_errata.md)
1. Table 1 retained-run seed was 10053 → now anchored on seed 4175.
2. "Only one validated threshold run" no longer true (now 4 experiments).
3. RQ2/RQ3 described a shared-dataset experiment that was NOT run → replaced with
   native-collection RQs + shared-dataset moved to future work.
4. Native-collection confound (different seeds per language) now disclosed.
5. Broken `Section ??` cross-reference — gone in the integrated doc.
6. Reference [4] pointed to the wrong paper (Neve–Seifert–Wang) → corrected +
   Neve added as its own reference.

---

## 8. OPEN / FUTURE WORK (stated in the paper's Conclusion)
- **Shared-dataset consistency + performance** study: feed ONE trace file to all
  three ports, confirm identical verified key, compare stage-level runtimes
  (the draft's original RQ2/RQ3). NOT yet run.
- Multiple keys (currently one fixed key), alternative outlier rules (percentile
  trimming, MAD), per-implementation dial calibration.
- Repeat paired runs to characterize run-to-run variance as distributions.
- Optional: author/affiliation block in `paper.tex` (currently empty `\author{}`).
- Optional: fix the last 18 pt overfull-hbox (cosmetic, on a bibliography URL).

---

## 9. ENVIRONMENT NOTES
- Machine: Apple M4, 10 cores, 16 GiB, Darwin arm64. Timebase 24 MHz.
- Baseline clean collection ≈ 0.94 ms/sample; **environment gate** = exclude runs
  > ~1.2 ms/sample (background-load proxy).
- The user's machine is sometimes unstable/loaded — long runs are done by the
  user; the agent builds tooling and runbooks and runs only short probes.
- Tectonic installed; matplotlib 3.9 + numpy 2.0 installed.
