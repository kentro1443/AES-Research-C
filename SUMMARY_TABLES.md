# Run summary tables (AES cache-timing study)

Apple M4, one fixed key, 10 trials per point, interleaved, commit `405b3de`.
Success/Attempts = verified key recoveries / trials.

---

## Table 1 — C, count sweep  (`count_threshold_C_10x`, seed 4175)

| COUNTS | SUCCESS/ATTEMPTS |
|---:|:---:|
| 500,000 | 10/10 |
| 400,000 | 10/10 |
| 300,000 | 10/10 |
| 250,000 | 10/10 |
| 200,000 | 10/10 |
| 150,000 | 10/10 |
| 100,000 | 10/10 |
| 75,000 | 9/10 |
| 60,000 | 7/10 |
| 50,000 | 5/10 |
| 45,000 | 4/10 |
| 40,000 | 1/10 |
| 35,000 | 0/10 |
| 30,000 | 0/10 |
| 25,000 | 1/10 |
| 20,000 | 0/10 |
| 10,000 | 0/10 |

---

## Table 2 — C, dial sweep at 100k  (`dial_sweep_knee100k`, seed 11065)

| SWEEP | SUCCESS/ATTEMPTS |
|:--|:---:|
| repeat = 10 | 6/10 |
| repeat = 20 | 5/10 |
| repeat = 30 | 5/10 |
| repeat = 50 | 7/10 |
| repeat = 75 | 2/10 |
| repeat = 100 | 2/10 |
| evict = 256 | 8/10 |
| evict = 512 | 6/10 |
| evict = 1024 | 1/10 |
| evict = 2048 | 5/10 |
| evict = 4096 | 10/10 |

---

## Table 3 — Go (GC on), count sweep  (`count_threshold_go_count`, seed 14778)

| COUNTS | SUCCESS/ATTEMPTS |
|---:|:---:|
| 500,000 | 8/10 |
| 400,000 | 10/10 |
| 300,000 | 6/10 |
| 250,000 | 4/10 |
| 200,000 | 2/10 |
| 150,000 | 2/10 |
| 100,000 | 0/10 |
| 75,000 | 0/10 |
| 60,000 | 0/10 |
| 50,000 | 0/10 |
| 45,000 | 0/10 |
| 40,000 | 0/10 |
| 35,000 | 0/10 |
| 30,000 | 0/10 |
| 25,000 | 0/10 |
| 20,000 | 0/10 |
| 10,000 | 0/10 |

---

## Table 4 — Go (GC on), dial sweep at 100k  (`dial_sweep_go_dial`, seed 20346)

| SWEEP | SUCCESS/ATTEMPTS |
|:--|:---:|
| repeat = 10 | 0/10 |
| repeat = 20 | 0/10 |
| repeat = 30 | 0/10 |
| repeat = 50 | 0/10 |
| repeat = 75 | 0/10 |
| repeat = 100 | 1/10 |
| evict = 256 | 0/10 |
| evict = 512 | 0/10 |
| evict = 1024 | 0/10 |
| evict = 2048 | 0/10 |
| evict = 4096 | 0/10 |

---

## Table 5 — Go (GC off), count sweep  (`count_threshold_go_gcoff_count`, seed 9744)

| COUNTS | SUCCESS/ATTEMPTS |
|---:|:---:|
| 500,000 | 9/10 |
| 250,000 | 6/10 |
| 100,000 | 0/10 |
| 50,000 | 0/10 |

---

## Table 6 — Go (GC off), dial sweep at 100k  (`dial_sweep_go_gcoff_dial`, seed 31480)

| SWEEP | SUCCESS/ATTEMPTS |
|:--|:---:|
| repeat = 10 | 0/10 |
| repeat = 50 | 0/10 |
| repeat = 100 | 0/10 |
| evict = 256 | 0/10 |
| evict = 2048 | 1/10 |
| evict = 4096 | 0/10 |
