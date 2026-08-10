# PROJECT_STATE.md

_Last verified: 2026-07-21_

## Current milestone

All three ports (C, Go, Python) implement the full pipeline — `keygen` →
`collect`/`collect-real` → `attack-final` → `verify` — with a matching CLI
contract and a cross-language ETA-output regression test. No milestone is
actively in progress; the project is in a stable, documented state.

## Implemented features

- AES-128 core + T-table timing target, in all three languages.
- Synthetic timing collection (`collect`) — modeled leak signal, reliable teaching path.
- Measured timing collection (`collect-real`) — real elapsed-time measurement around the T-table target, with `-repeat N` and `-evict-kb KB` tuning options.
- Final-round key recovery (`attack-final`) via delta-grouped timing averages + multi-start local search + brute-force of the last byte, verified against a header verifier pair.
- `verify` command to recheck a recovered key independently.
- Human-readable ETA progress output for `collect-real`, consistent across C/Go/Python (added in the `codex/time-left` branch, merged via PR #1).
- `NO_COLOR=1` support to disable ANSI output.

## Known defects / risks

- `go/aeslab` is a committed 2.8 MB binary in git history (commit 16b1aa3, "Refactor the affected module"). `.gitignore` only excludes `go/aes_lab_go` and `go/aes`, not `go/aeslab`, so this stray build artifact is tracked. Not yet cleaned up.
- Real-timing (`collect-real`) recovery is inherently stochastic and machine-dependent; `success_attempt.txt` records one working recipe on one machine, not a guarantee.
- No full cross-language key-recovery regression matrix exists; `make test` only checks C correctness and ETA output shape.

## Test status (verified 2026-07-21)

`make test` — **passing**:
- C build succeeds (`cc -O3 -std=c11 -Wall -Wextra -pedantic`).
- `./aes_lab selftest` — AES-128 NIST vector, T-table target, and key-schedule reversal all pass.
- `tests/test_collect_eta.sh` — ETA output matches across C, Go, and Python.

## Repository / branch status

- Single branch: `main`, tracking `origin/main`, clean working tree, no other worktrees.
- Previously had a `.claude/skills/` directory (trace-threshold, verify-both); deleted in commit 405b3de.

## File formats (stable, for reference)

- Key file: 16 raw bytes.
- Sample header: 48 bytes (magic, count, timing mode, verifier plaintext+ciphertext).
- Sample record: 40 bytes (16B plaintext, 16B ciphertext, 8B timing).
- Sample file size: `48 + count × 40` bytes (~10 MiB at default count of 262,144; ~160 MiB at max count of 4,194,304).
