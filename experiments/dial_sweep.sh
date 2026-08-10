#!/usr/bin/env bash
#
# dial_sweep.sh
# ------------------------------------------------------------------------------
# Follow-up to count_threshold_sweep.sh. There we found the sample-count
# threshold (~50k) with -repeat/-evict-kb held fixed. Here we hold the SAMPLE
# COUNT fixed and sweep the two other dials, one at a time (coordinate style),
# to show how each affects the attack's success:
#
#   -repeat   : how many encryptions are summed per sample (noise averaging).
#               Higher -> cleaner per-sample timing -> should raise the pass rate.
#   -evict-kb : size of the cache-flush buffer walked before each encryption
#               (signal strength). Bigger -> tables evicted from deeper cache ->
#               stronger hit/miss signal -> should raise the pass rate. (Paper:
#               L2 eviction needs fewer samples than L1.)
#
# The count is fixed at FIXED_COUNT, chosen at the *marginal* knee of the count
# sweep (50,000 = 2/3 at the baseline dials), so both raising and lowering a dial
# can push the result across the PASS/fail boundary and be visible.
#
# Same success detection as before: attack-final exits 0 on key recovery, non-
# zero otherwise. Same fixed key is reused (experiments/work/key.bin) for
# comparability with the count sweep. TRIALS trials per point, majority vote.
# INTERLEAVE=1 (opt-in) randomises the run ORDER across all (sweep,value,trial)
# points with a reproducible seed, so background-load spikes don't bias a whole
# dial point's block.
#
# Output:
#   experiments/dial_sweep<sfx>_results.csv   one row per (sweep, value, trial)
#   experiments/dial_sweep<sfx>.log           full run log
#   experiments/dial_sweep<sfx>_meta.txt      environment + config sidecar
# ------------------------------------------------------------------------------
set -u

# ------------------------------- CONFIG ---------------------------------------
# All values are overridable via environment variables so the same script can
# run different experiments without clobbering outputs, e.g. the 10-trial run:
#   RUN_TAG=10x TRIALS=10 INTERLEAVE=1 FIXED_COUNT=50000 \
#     REPEAT_VALUES="10 20 30 50 75 100" EVICT_VALUES="256 512 1024 2048 4096" \
#     ./experiments/dial_sweep.sh
FIXED_COUNT=${FIXED_COUNT:-50000}   # count held constant while dials vary
BASE_REPEAT=${BASE_REPEAT:-50}      # baseline -repeat (used while sweeping evict)
BASE_EVICT=${BASE_EVICT:-2048}      # baseline -evict-kb (used while sweeping repeat)
TRIALS=${TRIALS:-3}
PASS_MIN=${PASS_MIN:-2}             # a point "passes" if >= this many of TRIALS succeed
RUN_TAG=${RUN_TAG:-}               # suffix for output files (empty = default names)
SWEEPS=${SWEEPS:-both}             # which sweeps to run: repeat | evict | both
INTERLEAVE=${INTERLEAVE:-0}        # 1 = randomise run order across all points
SEED=${SEED:-$RANDOM}              # RNG seed for the interleave shuffle (logged)
IMPL=${IMPL:-c}                    # which port to drive: c | go | python (identical CLI)
# shellcheck disable=SC2206
REPEAT_VALUES=(${REPEAT_VALUES:-10 20 30 50 75 100})      # evict fixed at BASE_EVICT
# shellcheck disable=SC2206
EVICT_VALUES=(${EVICT_VALUES:-256 512 1024 2048 4096})    # repeat fixed at BASE_REPEAT
# ------------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Select which language port to drive (same CLI contract across all three).
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
CSV="$SCRIPT_DIR/dial_sweep${SFX}_results.csv"
LOG="$SCRIPT_DIR/dial_sweep${SFX}.log"
META="$SCRIPT_DIR/dial_sweep${SFX}_meta.txt"
RUNLOG="$WORK/run.log"

mkdir -p "$WORK"
: > "$LOG"
log() { printf '%s\n' "$*" | tee -a "$LOG"; }

# ------------------------------- BUILD ----------------------------------------
log "== build ($IMPL) =="
if ! build_impl >>"$LOG" 2>&1; then log "ERROR: $IMPL build failed"; exit 1; fi
check_impl || { log "ERROR: $IMPL target missing after build"; exit 1; }

# Reuse the count-sweep key if present, else make one (kept fixed for the run).
if [ -f "$KEY" ]; then
  log "== reusing existing fixed key $KEY =="
else
  log "== keygen (new fixed key) =="
  "${AES[@]}" keygen "$KEY" >>"$LOG" 2>&1 || { log "ERROR: keygen failed"; exit 1; }
fi

# ------------------------------- META sidecar ---------------------------------
{
  echo "# dial_sweep run metadata"
  echo "timestamp_utc   : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "git_commit      : $(cd "$ROOT" && git rev-parse HEAD 2>/dev/null || echo NA)"
  echo "git_dirty       : $(cd "$ROOT" && [ -n "$(git status --porcelain 2>/dev/null)" ] && echo yes || echo no)"
  echo "uname           : $(uname -a)"
  echo "cpu             : $(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo NA)"
  echo "ncpu            : $(sysctl -n hw.ncpu 2>/dev/null || echo NA)"
  echo "memsize_bytes   : $(sysctl -n hw.memsize 2>/dev/null || echo NA)"
  echo "impl            : $IMPL"
  echo "fixed_count     : $FIXED_COUNT"
  echo "base_repeat     : $BASE_REPEAT"
  echo "base_evict_kb   : $BASE_EVICT"
  echo "trials          : $TRIALS"
  echo "pass_min        : $PASS_MIN"
  echo "sweeps          : $SWEEPS"
  echo "interleave      : $INTERLEAVE"
  echo "seed            : $SEED"
  echo "repeat_values   : ${REPEAT_VALUES[*]}"
  echo "evict_values    : ${EVICT_VALUES[*]}"
} > "$META"

# NOTE: result stays column 6; used/ignored appended at the end.
echo "sweep,count,repeat,evict_kb,trial,result,exit_code,min_time,score,seconds,used_samples,ignored_samples" > "$CSV"

# run_one <count> <repeat> <evict_kb> -> echoes: <result> <exit> <min_time> <score> <seconds> <used> <ignored>
run_one() {
  local count="$1" repeat="$2" evict="$3" t0 t1 ec result mint score secs used ignored
  t0=$(date +%s)
  "${AES[@]}" collect-real "$KEY" "$SAMPLES" "$count" -repeat "$repeat" -evict-kb "$evict" > "$RUNLOG" 2>&1
  "${AES[@]}" attack-final "$SAMPLES" "$RECKEY" >> "$RUNLOG" 2>&1
  ec=$?
  t1=$(date +%s); secs=$(( t1 - t0 ))
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

# record_run <sweep> <count> <repeat> <evict> <trial> : run, append CSV, log.
record_run() {
  local sweep="$1" count="$2" repeat="$3" evict="$4" trial="$5"
  local result ec mint score secs used ignored
  read -r result ec mint score secs used ignored <<<"$(run_one "$count" "$repeat" "$evict")"
  echo "$sweep,$count,$repeat,$evict,$trial,$result,$ec,$mint,$score,$secs,$used,$ignored" >> "$CSV"
  log "   [$sweep] count=$count repeat=$repeat evict_kb=$evict trial=$trial: $result (exit $ec, ${secs}s, min_time=$mint, score=$score)"
}

log ""
log "== dial sweep config =="
log "impl=$IMPL  fixed count=$FIXED_COUNT  trials=$TRIALS  pass_min=$PASS_MIN  interleave=$INTERLEAVE  seed=$SEED"
log "repeat sweep (evict=$BASE_EVICT): ${REPEAT_VALUES[*]}"
log "evict  sweep (repeat=$BASE_REPEAT): ${EVICT_VALUES[*]}"
log "CSV  -> $CSV"
log "META -> $META"
log ""

# Build the list of points to run as "sweep repeat evict" tuples (count is fixed).
points=()
if [ "$SWEEPS" = "both" ] || [ "$SWEEPS" = "repeat" ]; then
  for r in "${REPEAT_VALUES[@]}"; do points+=("repeat $r $BASE_EVICT"); done
fi
if [ "$SWEEPS" = "both" ] || [ "$SWEEPS" = "evict" ]; then
  for e in "${EVICT_VALUES[@]}"; do points+=("evict $BASE_REPEAT $e"); done
fi

# ------------------------------- SWEEP ----------------------------------------
if [ "$INTERLEAVE" = "1" ]; then
  log "== interleaved run order (seed=$SEED) =="
  sched=()
  while read -r line; do
    [ -n "$line" ] && sched+=("$line")
  done < <(
    for p in "${points[@]}"; do
      set -- $p; sweep="$1"; repeat="$2"; evict="$3"
      for trial in $(seq 1 "$TRIALS"); do printf '%s %s %s %s\n' "$sweep" "$repeat" "$evict" "$trial"; done
    done | awk -v seed="$SEED" '
      { a[NR]=$0 }
      END { srand(seed); n=NR;
            for(i=n;i>1;i--){ j=int(rand()*i)+1; t=a[i]; a[i]=a[j]; a[j]=t }
            for(i=1;i<=n;i++) print a[i] }'
  )
  n=${#sched[@]}; idx=0
  for entry in "${sched[@]}"; do
    idx=$(( idx + 1 ))
    set -- $entry; sweep="$1"; repeat="$2"; evict="$3"; trial="$4"
    log "-- run $idx/$n --"
    record_run "$sweep" "$FIXED_COUNT" "$repeat" "$evict" "$trial"
  done
else
  # --- Sweep 1: -repeat (evict fixed) ---
  if [ "$SWEEPS" = "both" ] || [ "$SWEEPS" = "repeat" ]; then
    log "########## SWEEP 1: -repeat  (count=$FIXED_COUNT, evict-kb=$BASE_EVICT fixed) ##########"
    for r in "${REPEAT_VALUES[@]}"; do
      log "-- repeat: count=$FIXED_COUNT repeat=$r evict_kb=$BASE_EVICT --"
      for trial in $(seq 1 "$TRIALS"); do record_run "repeat" "$FIXED_COUNT" "$r" "$BASE_EVICT" "$trial"; done
    done
  fi
  # --- Sweep 2: -evict-kb (repeat fixed) ---
  if [ "$SWEEPS" = "both" ] || [ "$SWEEPS" = "evict" ]; then
    log ""
    log "########## SWEEP 2: -evict-kb  (count=$FIXED_COUNT, repeat=$BASE_REPEAT fixed) ##########"
    for e in "${EVICT_VALUES[@]}"; do
      log "-- evict: count=$FIXED_COUNT repeat=$BASE_REPEAT evict_kb=$e --"
      for trial in $(seq 1 "$TRIALS"); do record_run "evict" "$FIXED_COUNT" "$BASE_REPEAT" "$e" "$trial"; done
    done
  fi
fi

# ------------------------------- SUMMARY --------------------------------------
# Re-derived from the CSV, so it is order-independent (works for both modes).
if [ "$SWEEPS" = "both" ] || [ "$SWEEPS" = "repeat" ]; then
  log ""
  log "== summary: -repeat sweep (count=$FIXED_COUNT, evict=$BASE_EVICT) =="
  log "   repeat : passes/trials : verdict"
  for r in "${REPEAT_VALUES[@]}"; do
    p=$(awk -F, -v r="$r" '$1=="repeat" && $3==r && $6=="PASS"{n++} END{print n+0}' "$CSV")
    if [ "$p" -ge "$PASS_MIN" ]; then v="PASS"; else v="fail"; fi
    log "   $r : $p/$TRIALS : $v"
  done
fi
if [ "$SWEEPS" = "both" ] || [ "$SWEEPS" = "evict" ]; then
  log ""
  log "== summary: -evict-kb sweep (count=$FIXED_COUNT, repeat=$BASE_REPEAT) =="
  log "   evict_kb : passes/trials : verdict"
  for e in "${EVICT_VALUES[@]}"; do
    p=$(awk -F, -v e="$e" '$1=="evict" && $4==e && $6=="PASS"{n++} END{print n+0}' "$CSV")
    if [ "$p" -ge "$PASS_MIN" ]; then v="PASS"; else v="fail"; fi
    log "   $e : $p/$TRIALS : $v"
  done
fi
log ""
log "Full per-trial data: $CSV"
log "Run metadata:        $META"
log "Done."
