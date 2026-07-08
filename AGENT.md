# Agent Context

This repository is an educational C research lab for AES timing attacks. It is
not a production crypto library and must not be presented as one.

## Project Purpose

The project demonstrates AES-128 key recovery from timing side-channel data.
It contains:

- A correct AES-128 implementation used for verification.
- A table-driven AES timing target used for real timing experiments.
- A synthetic timing mode used only to validate the statistical recovery
  pipeline.
- A measured demo-leak mode used only to show a deliberately vulnerable timed
  target.
- A final-round timing attack that recovers the final AES round key, reverses
  the AES-128 key schedule, and verifies the recovered raw key.

The main executable is `aes_lab`, built from `src/aes_lab.c`.

## Security And Honesty Rules

Always be explicit about which timing mode is being used.

- Synthetic mode is artificial. It models timing leakage and should not be
  described as real measurement.
- Demo-leak mode records real elapsed time, but the target intentionally adds a
  vulnerability. It should not be described as a natural cache-timing leak.
- Natural real mode records real elapsed time from the table-driven timing
  target. This is the closest mode to the paper-style methodology currently in
  the repo.

Do not claim the project breaks AES itself. It studies vulnerable
implementations and timing side channels.

Do not claim the implementation is byte-for-byte historical OpenSSL. The real
timing target is table-driven and intentionally shaped for research:

- Four aligned round tables.
- Separate final-round table.
- Page-strided final-table entries so the simple exact-collision attack can
  observe a clearer memory-timing signal on Apple Silicon.

Do not target third-party systems. Keep experiments local and permissioned.

## Important Files

- `src/aes_lab.c`: all implementation code.
- `Makefile`: builds `aes_lab` and runs `make test`.
- `README.md`: user-facing explanation and usage.
- `AGENT.md`: this file, for future agents.
- `.gitignore`: ignores generated binaries, sample traces, and key files.

Generated `.bin` files can contain keys or timing traces. Do not commit them.

## Build And Test

Use:

```bash
make test
```

Expected result:

- Standard AES implementation matches the NIST AES-128 test vector.
- T-table AES timing target also matches the same vector.
- Inverse key schedule recovers the original key from round 10.

## Timing Modes

Synthetic mode:

```bash
./aes_lab collect key.bin samples.bin 50000
```

This is artificial and should recover easily.

Natural real timing mode:

```bash
./aes_lab collect-real key.bin real_samples.bin 200000 -repeat 50 -evict-kb 2048
```

This measures real elapsed time from the table-driven timing target. It is the
mode to use when the user asks for pure timing measurement.

Measured demo-leak mode:

```bash
./aes_lab collect-real key.bin demo_samples.bin 50000 -demo-leak
```

This uses real measurement but intentionally adds timed work tied to final-round
collisions. Treat it as a controlled demonstration, not paper-faithful evidence.

## Known Successful Pure Real-Timing Recipe

A successful natural real-timing extraction was achieved with:

```bash
./aes_lab keygen ttable_real_key.bin
./aes_lab collect-real ttable_real_key.bin ttable_real_samples6.bin 200000 -repeat 50 -evict-kb 2048
./aes_lab attack-final ttable_real_samples6.bin ttable_real_recovered6.bin
./aes_lab verify ttable_real_recovered6.bin ttable_real_samples6.bin
```

The verified key in that run was:

```text
444699779e3f0dcf1a6ba221e1ca8c78
```

This recipe may still be noisy on future runs. If it fails, increase sample
count first, then adjust `-repeat` and `-evict-kb`.

## Attack Method Summary

The attack uses final-round ciphertext/timing correlations:

1. Collect many records containing plaintext, ciphertext, and timing.
2. For each ciphertext byte pair `(i, j)`, group timings by
   `delta = c[i] ^ c[j]`.
3. Low average timing suggests a final-round lookup collision.
4. The attack infers relationships of the form
   `round10_key[i] ^ round10_key[j]`.
5. It performs multi-start local search over round-key byte offsets.
6. For each candidate final round key, it reverses the AES-128 key schedule.
7. It verifies candidates against the stored plaintext/ciphertext pair.

## Current Limitations

- The natural real target is not a byte-for-byte reproduction of old OpenSSL.
- The final table is page-strided to amplify the exact-collision signal on M4.
- The current attack is the simpler exact-collision final-round attack, not the
  expanded final-round attack that handles normal cache-line groups directly.
- Real timing can fail because macOS scheduling, Apple Silicon cache behavior,
  and timer resolution add noise.

## Good Future Work

- Add signal-quality reporting before attempting key recovery.
- Implement the expanded final-round attack from the paper.
- Add a compact historical T-table mode and compare it with the page-strided
  research target.
- Add reproducible benchmark scripts for multiple sample counts.
- Add optional CSV exports for plotting timing distributions.

