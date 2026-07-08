# AES Research C

This repository is a small C research lab for studying AES cache-timing key
recovery. It is based on the methodology from classic AES timing-attack papers,
especially final-round cache-collision attacks.

The goal is educational: show the whole pipeline from key generation, to
encryption samples, to timing analysis, to recovering the AES key.

Important: this project does not attack your Mac's built-in AES implementation.
Modern systems usually use hardware AES or constant-time software. This lab uses
a deliberately leaky timing model so the full statistical attack pipeline can be
learned and reproduced safely on a local machine.

## What This Project Demonstrates

AES itself is not being mathematically broken. AES is still considered secure
when implemented correctly.

The weakness studied here is an implementation side channel. A side channel is
extra information leaked by a program while it runs. In this case, the leaked
information is timing.

Old high-speed AES implementations often used lookup tables. The table entries
read during encryption depend on secret internal AES values, which depend on the
key. CPU memory/cache behavior can make some lookups slightly faster than
others. If an attacker collects enough encryptions and timings, statistics can
reveal patterns about the secret key.

This lab models that situation with synthetic timing:

```text
plaintext + key -> AES encryption -> ciphertext
                         |
                         v
                  timing-like leakage
```

The attack then receives many records like this:

```text
plaintext, ciphertext, timing
```

From those records, it recovers the original AES-128 key.

## Safety And Scope

Use this only for learning, research, and systems you own or have permission to
test.

The current implementation is intentionally local:

- It generates a key locally.
- It encrypts local random plaintext blocks.
- It writes local sample files.
- It recovers the locally generated key.

It does not include network probing, malware behavior, privilege escalation, or
tools for attacking third-party systems.

## Repository Files

### `Makefile`

The build file. It defines three useful commands:

```bash
make
```

Builds the program:

```text
src/aes_lab.c -> aes_lab
```

```bash
make test
```

Builds the program and runs the built-in AES self-test.

```bash
make clean
```

Removes generated local artifacts such as the compiled binary and `.bin` files.

### `src/aes_lab.c`

The entire research lab program. It includes:

- AES-128 encryption.
- AES key expansion.
- Reverse key expansion from the final round key.
- Sample generation.
- Synthetic timing leakage.
- Final-round timing analysis.
- Key recovery.
- Verification.

The program is built as one command-line tool called `aes_lab`.

### `.gitignore`

Keeps generated files out of git:

- `aes_lab`
- `*.bin`
- `*.o`
- `.DS_Store`

This matters because generated `.bin` files may contain secret keys and large
sample traces. They should not be committed.

## Build Requirements

On macOS, you need a C compiler. Apple's `clang` from Xcode Command Line Tools is
enough.

Build:

```bash
make
```

Run the self-test:

```bash
make test
```

Expected output:

```text
selftest=ok
```

## Quick Start

From the repository directory:

```bash
make test
./aes_lab keygen key.bin
./aes_lab collect key.bin samples.bin 262144
./aes_lab attack-final samples.bin recovered_key.bin
./aes_lab verify recovered_key.bin samples.bin
```

You should see the generated key, recovered key, and verified key match.

Example shape:

```text
key=0c77aad2c105ef0530011c4e07fae978
recovered_key=0c77aad2c105ef0530011c4e07fae978
verified_key=0c77aad2c105ef0530011c4e07fae978
```

The program is intentionally verbose and formatted for readability. It prints
bordered sections, aligned fields, progress bars, compact tables, sample
previews, verifier plaintext/ciphertext pairs, and the key-recovery
relationships it is using.

## Command Reference

### `selftest`

```bash
./aes_lab selftest
```

Checks two things:

1. AES encryption matches a known NIST AES-128 test vector.
2. Reversing the final round key produces the original key.

If this fails, the rest of the lab should not be trusted.

### `keygen`

```bash
./aes_lab keygen [key.bin]
```

Creates a random 16-byte AES-128 key and writes it to a file.

Default output:

```text
key.bin
```

Example:

```bash
./aes_lab keygen mykey.bin
```

AES-128 keys are 16 bytes, or 128 bits.

### `collect`

```bash
./aes_lab collect [key.bin] [samples.bin] [count]
```

Generates timing samples.

For each sample, the program:

1. Generates a random 16-byte plaintext.
2. Encrypts it with the AES key.
3. Computes a synthetic timing value based on final-round collisions.
4. Stores plaintext, ciphertext, and timing in the sample file.

Example:

```bash
./aes_lab collect mykey.bin mysamples.bin 262144
```

The sample count should be large because timing attacks are statistical. One
sample teaches almost nothing. Many samples reveal a pattern.

During collection, the program prints:

- The loaded AES key.
- The final AES round key.
- The verifier plaintext/ciphertext pair.
- A preview of the first generated sample.
- A progress bar at 25%, 50%, 75%, and 100%.

### `attack-final`

```bash
./aes_lab attack-final [samples.bin] [recovered_key.bin]
```

Runs the final-round timing attack.

It reads the sample file and tries to recover the original AES key without
reading the key file.

The attack uses:

```text
ciphertext + timing
```

It also uses one plaintext/ciphertext verifier stored in the sample file to
confirm that the recovered key is correct.

During the attack, the program prints:

- Sample file metadata.
- The first sample read from disk.
- A progress bar while building the timing table.
- A compact table of the best low-time ciphertext delta for each `(0, j)` byte
  pair.
- The inferred final-round key offsets from byte 0.
- A compact local-search table showing score changes.
- The verified final-round key byte candidate.
- The recovered original AES key.

### `verify`

```bash
./aes_lab verify [recovered_key.bin] [samples.bin]
```

Checks the recovered key against the verifier plaintext/ciphertext pair stored
inside the sample file.

If verification succeeds, the recovered key is functionally correct for AES.

During verification, the program prints the candidate key, verifier plaintext,
expected ciphertext, and computed ciphertext so you can see exactly why the key
is accepted or rejected.

## A Beginner-Friendly Explanation Of The Attack

### 1. AES Uses A Key

AES is a block cipher. For AES-128:

- The plaintext block is 16 bytes.
- The key is 16 bytes.
- The ciphertext block is 16 bytes.

Conceptually:

```text
AES_encrypt(plaintext, key) = ciphertext
```

If AES is implemented correctly, knowing plaintext and ciphertext should not let
you recover the key.

### 2. AES Has Rounds

AES does not encrypt in one step. It performs several rounds of transformation.
For AES-128, there are 10 rounds.

Each round mixes the data with round key material derived from the original key.
The original key is expanded into many round keys:

```text
original key -> round key 0 -> round key 1 -> ... -> round key 10
```

This repository stores all expanded key bytes in a 176-byte array:

```c
u8 w[176]
```

### 3. The Final Round Is Special

The final AES round has a simpler structure than the earlier rounds. For each
ciphertext byte, the relationship is roughly:

```text
ciphertext_byte = SBOX(secret_internal_byte) XOR final_round_key_byte
```

That means if we can learn the final round key, we can reverse the AES key
schedule and recover the original key.

That is exactly what this lab does.

### 4. Timing Leaks A Pattern

In vulnerable table-based AES, internal values are used as indexes into lookup
tables. Some pairs of lookup indexes collide or line up in cache. Those
collisions can make encryption slightly faster.

The real-world idea is:

```text
more cache collisions -> slightly faster encryption
fewer cache collisions -> slightly slower encryption
```

This lab uses a synthetic version:

```c
return 100000 - 500 * collisions + noise;
```

So more final-round collisions produce lower timing values.

### 5. One Timing Is Not Enough

The timing difference is tiny and noisy. A single encryption does not reveal the
key.

But if you collect thousands or hundreds of thousands of samples, averages begin
to expose the pattern.

This is why the quick start uses:

```bash
262144
```

samples.

### 6. The Attack Looks At Byte Pairs

AES has 16 ciphertext bytes:

```text
c[0], c[1], c[2], ..., c[15]
```

The attack compares every pair:

```text
(0,1), (0,2), ..., (14,15)
```

There are 120 pairs total.

For each pair, the attack groups timings by:

```text
delta = c[i] XOR c[j]
```

If a certain `delta` tends to have a lower average time, that suggests something
about:

```text
final_round_key[i] XOR final_round_key[j]
```

### 7. The Attack Recovers Relative Key Bytes

The timing data first reveals relationships between final-round key bytes, not
the absolute key immediately.

The code represents those relationships as offsets:

```c
off[i] = final_round_key[0] XOR final_round_key[i]
```

Then the program guesses the missing first final-round byte. There are only 256
possibilities for one byte, so this is easy.

### 8. The Attack Verifies The Key

For each possible final-round key candidate:

1. Reverse the key schedule to get a possible original AES key.
2. Encrypt the verifier plaintext with that key.
3. Compare the result to the verifier ciphertext.

If it matches, the key is recovered.

## Walkthrough Of The Main Code

### Type Aliases

```c
typedef unsigned char u8;
typedef unsigned int u32;
typedef unsigned long long u64;
```

These make byte-level crypto code easier to read:

- `u8` means one byte.
- `u32` means 32-bit unsigned integer.
- `u64` means 64-bit unsigned integer.

### Sample Record

```c
typedef struct {
  u8 p[16];
  u8 c[16];
  u64 t;
} sample_t;
```

Each sample stores:

- `p`: plaintext block.
- `c`: ciphertext block.
- `t`: timing value.

This is the core attack data.

### Sample Header

```c
typedef struct {
  u64 magic;
  u32 count;
  u32 mode;
  u8 verifier_p[16];
  u8 verifier_c[16];
} sample_header_t;
```

The sample file starts with metadata:

- `magic`: identifies the file format.
- `count`: number of samples.
- `mode`: currently `1` for synthetic timing mode.
- `verifier_p`: a known plaintext.
- `verifier_c`: its ciphertext.

The verifier lets the attack prove that the recovered key is correct.

### AES Tables

```c
static const u8 sbox[256] = { ... };
static const u8 invsbox[256] = { ... };
static const u8 rcon[10] = { ... };
```

These are standard AES constants:

- `sbox`: AES substitution table.
- `invsbox`: inverse substitution table.
- `rcon`: round constants used during key expansion.

### AES Round Functions

```c
add_round_key()
sub_bytes()
shift_rows()
mix_columns()
```

These implement the standard AES round transformations:

- `AddRoundKey`: XORs the state with round key bytes.
- `SubBytes`: applies the AES S-box.
- `ShiftRows`: rotates rows inside the AES state.
- `MixColumns`: mixes each column mathematically.

### Key Expansion

```c
static void key_expand(const u8 key[16], u8 w[176])
```

AES does not use the raw key directly in every round. It expands the 16-byte
key into 176 bytes of round key material.

For AES-128:

```text
11 round keys * 16 bytes = 176 bytes
```

### AES Encryption

```c
static void encrypt_block(const u8 in[16], u8 out[16], const u8 w[176])
```

Encrypts one 16-byte block:

1. Copy plaintext into the AES state.
2. XOR round key 0.
3. Run rounds 1 through 9.
4. Run the final round.
5. Copy the state into ciphertext output.

### Reverse Final Round Key

```c
static void invert_last_round_key(const u8 last[16], u8 raw[16])
```

This is crucial for the attack.

The timing attack recovers the final round key first. This function walks the
AES key schedule backward:

```text
round key 10 -> round key 9 -> ... -> original key
```

So a final-round key candidate becomes a raw AES key candidate.

### Synthetic Timing Leakage

```c
static u64 synthetic_time(const u8 c[16], const u8 last[16])
```

This function models the cache-collision signal.

It:

1. Uses ciphertext and the real final-round key to reconstruct final-round S-box
   input values.
2. Counts how many pairs are equal.
3. Returns a lower time when there are more collisions.
4. Adds small random noise.

This is the educational stand-in for real CPU cache timing.

### Collection Command

```c
static int cmd_collect(int argc, char **argv)
```

This command creates the attack dataset.

For each sample:

```text
random plaintext -> AES encrypt -> ciphertext -> synthetic timing -> write sample
```

### Attack Command

```c
static int cmd_attack(int argc, char **argv)
```

This is the recovery engine.

It:

1. Reads all samples.
2. Computes average timing for every ciphertext-byte pair and delta.
3. Picks low-time deltas as key-byte relationship candidates.
4. Optimizes the set of final-round key-byte offsets.
5. Tries all 256 possibilities for the first final-round key byte.
6. Reverses the key schedule for each candidate.
7. Verifies against the known verifier pair.
8. Writes the recovered key.

### Verification Command

```c
static int cmd_verify(int argc, char **argv)
```

Reads a recovered key and sample file, then checks:

```text
AES_encrypt(verifier_plaintext, recovered_key) == verifier_ciphertext
```

If yes, the recovered key is correct.

## Important Limitations

This project currently uses synthetic timing. That means the timing signal is
modeled by the program instead of measured from real M4 cache behavior.

This was chosen because:

- Modern Apple Silicon uses hardware features and cache behavior unlike the old
  Pentium-era systems in the papers.
- Modern crypto libraries avoid the vulnerable lookup-table style.
- Real cache timing requires careful calibration, CPU pinning, eviction logic,
  and a deliberately vulnerable table implementation.

The current code proves the attack methodology end to end. It does not prove
that your MacBook Air M4 leaks enough real timing information for this exact
attack.

## Common Questions

### Do I need my own plaintext and ciphertext?

For this lab, no. The `collect` command generates random plaintexts and
ciphertexts automatically.

If you provide your own plaintexts, the program could encrypt them and collect
timing samples, but you still need many samples.

### Is one plaintext/ciphertext pair enough?

No.

One pair can verify a guessed key, but it cannot reveal the key through this
timing attack. The attack needs many ciphertext/timing records.

### Why does the attack recover the final round key first?

Because the final AES round has a simpler relationship between ciphertext bytes
and final-round key bytes. Once the final round key is known, AES-128 key
expansion can be reversed to recover the original key.

### Why are generated `.bin` files ignored?

Because they may contain:

- Secret keys.
- Recovered keys.
- Large sample traces.

They are experiment outputs, not source code.

## Typical Experiment

```bash
make test
./aes_lab keygen key.bin
./aes_lab collect key.bin samples.bin 262144
./aes_lab attack-final samples.bin recovered_key.bin
./aes_lab verify recovered_key.bin samples.bin
```

To try a larger sample count:

```bash
./aes_lab collect key.bin samples.bin 524288
./aes_lab attack-final samples.bin recovered_key.bin
./aes_lab verify recovered_key.bin samples.bin
```

Larger sample counts usually make the statistics clearer, at the cost of more
time and disk space.

## Next Research Steps

Possible future improvements:

- Add a real timing backend using `mach_absolute_time()`.
- Add cache eviction buffers and calibration.
- Add a true T-table AES implementation closer to historical OpenSSL.
- Add a Bernstein-style profile/correlation workflow.
- Add input-file plaintext collection.
- Add CSV export for plotting timing distributions.
- Add tests around the attack scorer and sample file parser.
