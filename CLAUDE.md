# CLAUDE.md

## Purpose

Educational, local-only lab for studying AES-128 cache-timing key recovery
against a deliberately vulnerable, table-driven AES target. It does not
attack real cryptographic libraries or hardware AES, and has no network or
remote-probing features. Only use it against systems you own or have explicit
permission to test.

## Technology stack

Three independent, standard-library-only implementations of the same
pipeline, kept manually in sync (there is no shared library between them):

| Language | Entry point | Requirements |
| --- | --- | --- |
| C | `src/aes_lab.c` → `./aes_lab` | C11 compiler, Make |
| Go | `go/main.go` → `go/aes_lab_go` | Go 1.21+ |
| Python | `python/aes_lab.py` | Python 3.7+ |

The C implementation is the primary/reference port.

## Repository structure

- `src/aes_lab.c` — C AES core, timing target, collection, attack, verification, CLI
- `go/main.go` — Go port; `go/go.mod` module def; `go/.golangci.yml` lint config
- `python/aes_lab.py` — Python port
- `tests/test_collect_eta.sh` — cross-implementation ETA-output regression test
- `Makefile` — C build plus repo-wide test/cleanup targets
- `success_attempt.txt` — a recorded real-timing experiment recipe (reference data, not code)

## Build and test commands

```bash
make            # build C executable only
make test       # build C, run its selftest, run cross-language ETA regression test
make clean      # remove build artifacts, .bin files, Python caches, .DS_Store
(cd go && go build -o aes_lab_go .)
(cd go && go run . selftest)
python3 python/aes_lab.py selftest
```

`make test` requires a C compiler, Go, Python 3.7+, and POSIX shell utilities.
It does not run a full cross-language key-recovery matrix — it only checks
AES correctness (C) and ETA output shape (C/Go/Python).

## Coding conventions and constraints

- Every port exposes the same CLI command contract: `selftest`, `keygen`,
  `collect`, `collect-real`, `attack-final`, `verify`. Keep the contract
  identical across ports; behavioral changes must be applied to all three
  manually since there is no shared code.
- Go and Python explicitly serialize sample/key files as little-endian; C
  writes its native struct layout. Formats are only interchangeable on
  little-endian systems with the expected C struct layout — not a portable
  format guarantee. When changing serialization, verify each implementation
  can still read files written by the others.
- `*.bin` files (keys, sample traces) are gitignored — they can contain key
  material and are unencrypted. Never commit them.
- Test attack-logic changes against the synthetic (`collect`) workflow in
  every affected port before trusting `collect-real` results, since real
  timing is machine-dependent and noisy by nature.

## Workflow

- This is a from-scratch documentation setup — no prior CLAUDE.md existed.
- Definition of done for a change: builds clean, `make test` passes, and if
  the change touches shared behavior (attack logic, file format, CLI
  contract), all three ports were updated and manually cross-checked.
