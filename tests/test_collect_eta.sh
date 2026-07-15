#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/aes-collect-eta.XXXXXX")
trap 'rm -rf "$tmpdir"' EXIT HUP INT TERM

dd if=/dev/zero of="$tmpdir/key.bin" bs=16 count=1 2>/dev/null

(
  cd "$repo_root/go"
  GOCACHE="$tmpdir/go-cache" go build -o "$tmpdir/aes_lab_go" .
)

check_implementation() {
  name=$1
  shift

  "$@" collect-real "$tmpdir/key.bin" "$tmpdir/${name}-real.bin" 8 -evict-kb 1 \
    >"$tmpdir/${name}-real.out"
  if ! grep -Eq 'estimated time remaining: [0-9]+(h|m|s)' "$tmpdir/${name}-real.out"; then
    echo "$name collect-real did not print a human-readable estimated time remaining" >&2
    return 1
  fi
  if [ "$(grep -c 'estimated time remaining' "$tmpdir/${name}-real.out")" -ne 4 ]; then
    echo "$name collect-real did not print an estimate on every progress line" >&2
    return 1
  fi
  if ! grep -Eq '\(100%\).*estimated time remaining: 0s' "$tmpdir/${name}-real.out"; then
    echo "$name collect-real did not finish with zero estimated time remaining" >&2
    return 1
  fi

  "$@" collect "$tmpdir/key.bin" "$tmpdir/${name}-synthetic.bin" 8 \
    >"$tmpdir/${name}-synthetic.out"
  if grep -q 'estimated time remaining' "$tmpdir/${name}-synthetic.out"; then
    echo "$name collect printed an estimate reserved for collect-real" >&2
    return 1
  fi
}

check_implementation c "$repo_root/aes_lab"
check_implementation go "$tmpdir/aes_lab_go"
check_implementation python python3 "$repo_root/python/aes_lab.py"

echo "collect-real ETA output matches across C, Go, and Python"
