#!/usr/bin/env bash
#
# count_threshold_sweep.sh
# ------------------------------------------------------------------------------
# Pin down the *sample-count threshold* of the C AES cache-timing attack:
# the fewest real-timing samples ("traces") from which `attack-final` can still
# recover the AES-128 key on THIS machine.
#
# Method (see success_attempt.txt for the known-good recipe this generalises):
#   * One fixed key, generated once and reused for every run, so the only
#     variable is the sample count.
#   * `-repeat` and `-evict-kb` are held fixed (default 50 / 2048), matching the
#     conditions of the Bonneau & Mironov "Final Round Attack" (Table 1: 2^15
#     samples; Table 2 Pentium III: 2^16 L1 / 2^15 L2). Only the count varies.
#   * Real timing is noisy, so each count is run TRIALS times and we record how
#     many trials recovered the key. A count "passes" if it succeeds in at least
#     PASS_MIN of TRIALS (a majority vote).
#   * We step the count DOWN and log the whole curve (past the first failures),
#     so the pass -> fail transition is visible rather than cut off by one noisy
#     miss.
#   * INTERLEAVE=1 (opt-in) randomises the run ORDER across (count,trial) pairs
#     with a reproducible seed, so a transient background-load spike can't bias a
#     whole count's block (the rigour gap flagged in count_threshold_report.md
#     §9). Default INTERLEAVE=0 keeps the original grouped order.
#
# Success detection needs no output parsing: `attack-final` self-verifies each
# candidate against the plaintext/ciphertext pair stored in the sample-file
# header and exits 0 on success, non-zero (2) when no key is recovered.
#
# Output:
#   experiments/count_threshold<sfx>_results.csv  one row per (count, trial)
#   experiments/count_threshold_sweep<sfx>.log    full run log
#   experiments/count_threshold<sfx>_meta.txt     environment + config sidecar
# Reproduce / tweak: edit the CONFIG block below and re-run. Key/sample *.bin
# files stay under experiments/work/ and are gitignored (never committed).
# ------------------------------------------------------------------------------
set -u

# ------------------------------- CONFIG ---------------------------------------
# All values are overridable via environment variables, e.g. the definitive run:
#   RUN_TAG=10x TRIALS=10 INTERLEAVE=1 \
#     COUNTS="500000 400000 300000 250000 200000 150000 100000 75000 60000 \
#             50000 45000 40000 35000 30000 25000 20000 10000" \
#     ./experiments/count_threshold_sweep.sh
REPEAT=${REPEAT:-50}         # -repeat: encryptions summed per sample (noise averaging)
EVICT_KB=${EVICT_KB:-2048}   # -evict-kb: cache-flush buffer size in KiB (signal strength)
TRIALS=${TRIALS:-3}          # runs per count (noise handling)
PASS_MIN=${PASS_MIN:-2}      # a count "passes" if >= this many of TRIALS succeed
RUN_TAG=${RUN_TAG:-}         # suffix for output files (empty = default names)
INTERLEAVE=${INTERLEAVE:-0}  # 1 = randomise run order across (count,trial) pairs
SEED=${SEED:-$RANDOM}        # RNG seed for the interleave shuffle (logged, reproducible)
IMPL=${IMPL:-c}              # which port to drive: c | go | python (identical CLI contract)
# Sample counts to test, high -> low. Coarse up top, finer near the paper's
# expected region (~2^15..2^16 = 32768..65536). Edit freely / override via env.
# shellcheck disable=SC2206
COUNTS=(${COUNTS:-500000 400000 300000 250000 200000 150000 100000 75000 50000 40000 30000 20000})
# ------------------------------------------------------------------------------

# Resolve repo root from this script's location (experiments/<script>).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Select which language port to drive. All three expose the same CLI contract
# (keygen/collect-real/attack-final); only the build step and entry point differ.
# AES is an array so the Python port can be "python3 <script>" rather than a binary.
case "$IMPL" in
  c)
    AES=("$ROOT/aes_lab")
    build_impl() { ( cd "$ROOT" && make ); }
    check_impl() { [ -x "$ROOT/aes_lab" ]; }
    ;;
  go)
    AES=("$ROOT/go/aes_lab_go")
    build_impl() { ( cd "$ROOT/go" && go build -o aes_lab_go . ); }
    check_impl() { [ -x "$ROOT/go/aes_lab_go" ]; }
    ;;
  python)
    AES=("python3" "$ROOT/python/aes_lab.py")
    build_impl() { :; }
    check_impl() { [ -f "$ROOT/python/aes_lab.py" ]; }
    ;;
  *)
    echo "ERROR: unknown IMPL='$IMPL' (want c|go|python)" >&2; exit 1
    ;;
esac
WORK="$SCRIPT_DIR/work"
KEY="$WORK/key.bin"
SAMPLES="$WORK/samples.bin"
RECKEY="$WORK/final.bin"
SFX=""; [ -n "$RUN_TAG" ] && SFX="_$RUN_TAG"
CSV="$SCRIPT_DIR/count_threshold${SFX}_results.csv"
LOG="$SCRIPT_DIR/count_threshold_sweep${SFX}.log"
META="$SCRIPT_DIR/count_threshold${SFX}_meta.txt"
RUNLOG="$WORK/run.log"        # transient per-run capture

mkdir -p "$WORK"
: > "$LOG"

log() { printf '%s\n' "$*" | tee -a "$LOG"; }

# ------------------------------- BUILD ----------------------------------------
log "== build ($IMPL) =="
if ! build_impl >>"$LOG" 2>&1; then
  log "ERROR: $IMPL build failed (see $LOG)"; exit 1
fi
check_impl || { log "ERROR: $IMPL target not found after build"; exit 1; }

# ------------------------------- KEY ------------------------------------------
# Reuse an existing fixed key if present (keeps re-runs comparable); else make one.
if [ -f "$KEY" ]; then
  log "== reusing existing fixed key $KEY =="
else
  log "== keygen (one fixed key, reused for every run) =="
  "${AES[@]}" keygen "$KEY" >>"$LOG" 2>&1 || { log "ERROR: keygen failed"; exit 1; }
fi

# ------------------------------- META sidecar ---------------------------------
# Record enough to reproduce/interpret this run later.
{
  echo "# count_threshold_sweep run metadata"
  echo "timestamp_utc   : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "git_commit      : $(cd "$ROOT" && git rev-parse HEAD 2>/dev/null || echo NA)"
  echo "git_dirty       : $(cd "$ROOT" && [ -n "$(git status --porcelain 2>/dev/null)" ] && echo yes || echo no)"
  echo "uname           : $(uname -a)"
  echo "cpu             : $(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo NA)"
  echo "ncpu            : $(sysctl -n hw.ncpu 2>/dev/null || echo NA)"
  echo "memsize_bytes   : $(sysctl -n hw.memsize 2>/dev/null || echo NA)"
  echo "impl            : $IMPL"
  echo "repeat          : $REPEAT"
  echo "evict_kb        : $EVICT_KB"
  echo "trials          : $TRIALS"
  echo "pass_min        : $PASS_MIN"
  echo "interleave      : $INTERLEAVE"
  echo "seed            : $SEED"
  echo "counts          : ${COUNTS[*]}"
} > "$META"

# ------------------------------- CSV header -----------------------------------
# NOTE: result stays column 5 so the summary awk below is index-stable; the two
# new fields are appended at the end.
echo "count,trial,repeat,evict_kb,result,exit_code,min_time,score,seconds,used_samples,ignored_samples" > "$CSV"

# Planned total sample-units, for a live ETA.
total_planned=0
for c in "${COUNTS[@]}"; do total_planned=$(( total_planned + c * TRIALS )); done
done_units=0
done_secs=0

log ""
log "== sweep config =="
log "impl=$IMPL  repeat=$REPEAT  evict_kb=$EVICT_KB  trials=$TRIALS  pass_min=$PASS_MIN  interleave=$INTERLEAVE  seed=$SEED"
log "counts: ${COUNTS[*]}"
log "planned total sample-units: $total_planned (ETA refines after the first run)"
log ""
log "CSV  -> $CSV"
log "META -> $META"
log ""

# run_one <count> <trial>  -> echoes: <result> <exit> <min_time> <score> <seconds> <used> <ignored>
run_one() {
  local count="$1" trial="$2"
  local t0 t1 ec result mint score secs used ignored

  t0=$(date +%s)
  "${AES[@]}" collect-real "$KEY" "$SAMPLES" "$count" -repeat "$REPEAT" -evict-kb "$EVICT_KB" \
      > "$RUNLOG" 2>&1
  "${AES[@]}" attack-final "$SAMPLES" "$RECKEY" >> "$RUNLOG" 2>&1
  ec=$?
  t1=$(date +%s)
  secs=$(( t1 - t0 ))

  if [ "$ec" -eq 0 ]; then result="PASS"; else result="FAIL"; fi
  mint=$(awk -F' : ' '/minimum timing/{v=$2} END{gsub(/[^0-9]/,"",v); print (v==""?"NA":v)}' "$RUNLOG")
  score=$(awk -F' : ' '{k=$1; gsub(/^ +| +$/,"",k);
                        if(k=="score"||k=="best unverified score"){v=$2}}
                   END{gsub(/[^0-9.]/,"",v); print (v==""?"NA":v)}' "$RUNLOG")
  used=$(awk -F' : ' '{k=$1; gsub(/^ +| +$/,"",k); if(k=="used samples"){v=$2}}
                  END{gsub(/[^0-9]/,"",v); print (v==""?"NA":v)}' "$RUNLOG")
  ignored=$(awk -F' : ' '{k=$1; gsub(/^ +| +$/,"",k); if(k=="ignored samples"){v=$2}}
                     END{gsub(/[^0-9]/,"",v); print (v==""?"NA":v)}' "$RUNLOG")

  printf '%s %s %s %s %s %s %s\n' "$result" "$ec" "$mint" "$score" "$secs" "$used" "$ignored"
}

# record_run <count> <trial> : run, append CSV, update ETA, log. Sets RUN_RESULT.
RUN_RESULT=""
record_run() {
  local count="$1" trial="$2"
  local result ec mint score secs used ignored eta
  read -r result ec mint score secs used ignored <<<"$(run_one "$count" "$trial")"
  RUN_RESULT="$result"
  echo "$count,$trial,$REPEAT,$EVICT_KB,$result,$ec,$mint,$score,$secs,$used,$ignored" >> "$CSV"

  done_units=$(( done_units + count ))
  done_secs=$(( done_secs + secs ))
  eta="?"
  if [ "$done_units" -gt 0 ]; then
    eta=$(awk -v du="$done_units" -v ds="$done_secs" -v tp="$total_planned" \
          'BEGIN{ if(du>0){ r=ds/du; rem=(tp-du)*r; printf "%d", (rem<0?0:rem) } else print 0 }')
    eta="$(( eta / 60 ))m$(( eta % 60 ))s"
  fi
  log "   count=$count trial=$trial: $result (exit $ec, ${secs}s, min_time=$mint, score=$score, used=$used, ignored=$ignored)  ETA~$eta"
}

# ------------------------------- SWEEP ----------------------------------------
if [ "$INTERLEAVE" = "1" ]; then
  log "== interleaved run order (seed=$SEED) =="
  # Build every (count,trial) pair, then shuffle with a seeded Fisher-Yates so
  # the order is reproducible from SEED but decorrelated from the count.
  sched_count=(); sched_trial=()
  while read -r c t; do
    [ -n "$c" ] || continue
    sched_count+=("$c"); sched_trial+=("$t")
  done < <(
    for count in "${COUNTS[@]}"; do
      for trial in $(seq 1 "$TRIALS"); do printf '%s %s\n' "$count" "$trial"; done
    done | awk -v seed="$SEED" '
      { a[NR]=$0 }
      END { srand(seed); n=NR;
            for(i=n;i>1;i--){ j=int(rand()*i)+1; t=a[i]; a[i]=a[j]; a[j]=t }
            for(i=1;i<=n;i++) print a[i] }'
  )
  n=${#sched_count[@]}
  for ((idx=0; idx<n; idx++)); do
    log "-- run $((idx+1))/$n : count=${sched_count[$idx]} trial=${sched_trial[$idx]} --"
    record_run "${sched_count[$idx]}" "${sched_trial[$idx]}"
  done
else
  for count in "${COUNTS[@]}"; do
    passes=0
    log "-- count=$count --"
    for trial in $(seq 1 "$TRIALS"); do
      record_run "$count" "$trial"
      [ "$RUN_RESULT" = "PASS" ] && passes=$(( passes + 1 ))
    done
    if [ "$passes" -ge "$PASS_MIN" ]; then verdict="PASS"; else verdict="fail"; fi
    log "   => count=$count  passes=$passes/$TRIALS  [$verdict]"
  done
fi

# ------------------------------- SUMMARY --------------------------------------
# Re-derived from the CSV, so it is order-independent (works for both modes).
log ""
log "== summary (count : passes/trials : verdict) =="
threshold=""
for count in "${COUNTS[@]}"; do
  passes=$(awk -F, -v c="$count" '$1==c && $5=="PASS"{n++} END{print n+0}' "$CSV")
  if [ "$passes" -ge "$PASS_MIN" ]; then v="PASS"; threshold="$count"; else v="fail"; fi
  log "   $count : $passes/$TRIALS : $v"
done

log ""
if [ -n "$threshold" ]; then
  log "THRESHOLD (lowest count still passing >= $PASS_MIN/$TRIALS): $threshold"
else
  log "THRESHOLD: none of the tested counts passed >= $PASS_MIN/$TRIALS (raise counts or repeat/evict)."
fi
log "Full per-trial data: $CSV"
log "Run metadata:        $META"
log "Done."
