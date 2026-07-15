---
name: verify-both
description: Rebuild and verify both the C (aes_lab) and Go (aes_lab_go) implementations of this AES timing-attack lab agree with each other. Use after changing src/aes_lab.c or go/main.go, before committing, or whenever asked to confirm both implementations still work.
---

Run these steps and report results tersely (pass/fail per step, not raw command output):

1. Rebuild the C binary: `make clean && make` from the repo root. Confirm no compiler warnings.
2. Rebuild the Go binary: `cd go && go build -o aes_lab_go .`. Confirm `go vet ./...` is clean.
3. Run `./aes_lab selftest` and `cd go && ./aes_lab_go selftest`. Both must print `selftest=ok`.
4. Cross-language file compatibility, both directions, using a scratch temp
   directory (do not leave `.bin` files in the repo — they're gitignored but
   still clutter the working tree):
   - C writes, Go reads: `aes_lab keygen`, `aes_lab collect` (small count,
     e.g. 50000, synthetic mode is enough for this check), then
     `aes_lab_go attack-final` + `aes_lab_go verify` on the C-produced file.
   - Go writes, C reads: same in reverse.
   - Both must report `SUCCESS` and recover the same key that was generated.
5. Report one line per check (build/vet/selftest-C/selftest-go/cross-compat-1/cross-compat-2),
   pass or fail. If anything fails, stop and show the actual failing output for that step only.

Clean up any scratch `.bin`/binary files created during this check.
