#!/usr/bin/env python3
import os
import random
import struct
import sys
import time

AES_BLOCK = 16
AES_EXPANDED = 176
MAX_SAMPLES = 1 << 22
PAIRS = 120
MAGIC = 0x41455354494D4531
MODE_SYNTHETIC = 1
MODE_REAL = 2
DEFAULT_EVICT_SIZE = 256 * 1024
EVICT_STRIDE = 64
FINAL_STRIDE = 4096

HEADER_STRUCT = struct.Struct("<QII16s16s")
SAMPLE_STRUCT = struct.Struct("<16s16sQ")

use_color = False
clr_reset = ""
clr_title = ""
clr_label = ""
clr_ok = ""
clr_warn = ""
timing_sink = 0
tables_ready = False
evict_size = DEFAULT_EVICT_SIZE
evict_buf = bytearray()

te0 = bytearray(256 * 4)
te1 = bytearray(256 * 4)
te2 = bytearray(256 * 4)
te3 = bytearray(256 * 4)
final_table = bytearray(256 * FINAL_STRIDE)

SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]

INVSBOX = [
    0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
    0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
    0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
    0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
    0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
    0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
    0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
    0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
    0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
    0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
    0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
    0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
    0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
    0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
    0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d,
]

RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]
SHIFT_ROWS_PERM = [0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2, 7, 12, 1, 6, 11]


def xtime(x):
    return (((x << 1) & 0xFF) ^ (((x >> 7) * 0x1B) & 0xFF)) & 0xFF


def mul3(x):
    return xtime(x) ^ x


def add_round_key(s, rk):
    for i in range(16):
        s[i] ^= rk[i]


def sub_bytes(s):
    for i in range(16):
        s[i] = SBOX[s[i]]


def shift_rows(s):
    t = [s[SHIFT_ROWS_PERM[i]] for i in range(16)]
    s[:] = t


def mix_columns(s):
    for c in range(4):
        i = 4 * c
        x = s[i] ^ s[i + 1] ^ s[i + 2] ^ s[i + 3]
        y = s[i]
        s[i] ^= x ^ xtime(s[i] ^ s[i + 1])
        s[i + 1] ^= x ^ xtime(s[i + 1] ^ s[i + 2])
        s[i + 2] ^= x ^ xtime(s[i + 2] ^ s[i + 3])
        s[i + 3] ^= x ^ xtime(s[i + 3] ^ y)
        for j in range(4):
            s[i + j] &= 0xFF


def key_expand(key):
    w = bytearray(AES_EXPANDED)
    w[0:16] = key[0:16]
    bytes_n = 16
    r = 0
    temp = [0, 0, 0, 0]
    while bytes_n < AES_EXPANDED:
        temp[:] = w[bytes_n - 4:bytes_n]
        if bytes_n & 15 == 0:
            k = temp[0]
            temp[0] = SBOX[temp[1]] ^ RCON[r]
            r += 1
            temp[1] = SBOX[temp[2]]
            temp[2] = SBOX[temp[3]]
            temp[3] = SBOX[k]
        for i in range(4):
            w[bytes_n] = w[bytes_n - 16] ^ temp[i]
            bytes_n += 1
    return w


def encrypt_block(block, w):
    s = bytearray(block[0:16])
    add_round_key(s, w[0:16])
    for r in range(1, 10):
        sub_bytes(s)
        shift_rows(s)
        mix_columns(s)
        add_round_key(s, w[16 * r:16 * r + 16])
    sub_bytes(s)
    shift_rows(s)
    add_round_key(s, w[160:176])
    return bytes(s)


def init_tables():
    global tables_ready
    if tables_ready:
        return
    for i in range(256):
        x = SBOX[i]
        te0[i * 4 + 0], te0[i * 4 + 1], te0[i * 4 + 2], te0[i * 4 + 3] = xtime(x), x, x, mul3(x)
        te1[i * 4 + 0], te1[i * 4 + 1], te1[i * 4 + 2], te1[i * 4 + 3] = mul3(x), xtime(x), x, x
        te2[i * 4 + 0], te2[i * 4 + 1], te2[i * 4 + 2], te2[i * 4 + 3] = x, mul3(x), xtime(x), x
        te3[i * 4 + 0], te3[i * 4 + 1], te3[i * 4 + 2], te3[i * 4 + 3] = x, x, mul3(x), xtime(x)
        final_table[i * FINAL_STRIDE] = x
    tables_ready = True


def ttable_column(a, b, c, d, rk):
    ia = a * 4
    ib = b * 4
    ic = c * 4
    id_ = d * 4
    return bytes([
        te0[ia + i] ^ te1[ib + i] ^ te2[ic + i] ^ te3[id_ + i] ^ rk[i]
        for i in range(4)
    ])


def ttable_encrypt_block(block, w):
    init_tables()
    s = bytearray(block[0:16])
    add_round_key(s, w[0:16])
    for r in range(1, 10):
        rk = w[16 * r:16 * r + 16]
        t = bytearray(16)
        t[0:4] = ttable_column(s[0], s[5], s[10], s[15], rk[0:4])
        t[4:8] = ttable_column(s[4], s[9], s[14], s[3], rk[4:8])
        t[8:12] = ttable_column(s[8], s[13], s[2], s[7], rk[8:12])
        t[12:16] = ttable_column(s[12], s[1], s[6], s[11], rk[12:16])
        s = t
    rk = w[160:176]
    out = bytearray(16)
    for i in range(16):
        out[i] = final_table[s[SHIFT_ROWS_PERM[i]] * FINAL_STRIDE] ^ rk[i]
    return bytes(out)


def disturb_cache():
    global evict_buf, timing_sink
    if len(evict_buf) < evict_size:
        evict_buf = bytearray((i & 0xFF) for i in range(evict_size))
    acc = timing_sink
    for i in range(0, evict_size, EVICT_STRIDE):
        acc ^= evict_buf[i]
    timing_sink = acc


def invert_last_round_key(last):
    w = bytearray(AES_EXPANDED)
    w[160:176] = last[0:16]
    for round_n in range(10, 0, -1):
        prev_start = 16 * (round_n - 1)
        cur_start = 16 * round_n
        for i in range(12, 3, -4):
            for b in range(4):
                w[prev_start + i + b] = w[cur_start + i + b] ^ w[cur_start + i - 4 + b]
        temp = [w[prev_start + 13], w[prev_start + 14], w[prev_start + 15], w[prev_start + 12]]
        temp[0] = SBOX[temp[0]] ^ RCON[round_n - 1]
        temp[1] = SBOX[temp[1]]
        temp[2] = SBOX[temp[2]]
        temp[3] = SBOX[temp[3]]
        for b in range(4):
            w[prev_start + b] = w[cur_start + b] ^ temp[b]
    return bytes(w[0:16])


def random_bytes(n):
    try:
        return os.urandom(n)
    except OSError as exc:
        print(f"random: {exc}", file=sys.stderr)
        raise SystemExit(1)


def read_file_exact(path, n):
    with open(path, "rb") as f:
        data = f.read(n)
    if len(data) != n:
        raise OSError("unexpected EOF")
    return data


def write_file_exact(path, data):
    with open(path, "wb") as f:
        f.write(data)


def init_console():
    global use_color, clr_reset, clr_title, clr_label, clr_ok, clr_warn
    use_color = sys.stdout.isatty() and os.environ.get("NO_COLOR", "") == ""
    if use_color:
        clr_reset = "\033[0m"
        clr_title = "\033[1;36m"
        clr_label = "\033[1m"
        clr_ok = "\033[1;32m"
        clr_warn = "\033[1;33m"


def clean_label(label):
    while label and label[-1] in "=:":
        label = label[:-1]
    return label[:63]


def print_field_prefix(label):
    print(f"  {clr_label}{clean_label(label):<24}{clr_reset} : ", end="")


def print_hex(label, x):
    print_field_prefix(label)
    print(bytes(x).hex())


def print_step(title):
    print(f"\n{clr_title}============================================================{clr_reset}")
    print(f"{clr_title}{title}{clr_reset}")
    print(f"{clr_title}============================================================{clr_reset}")


def print_note(text):
    print(f"  {text}")


def print_field_str(label, value):
    print_field_prefix(label)
    print(value)


def print_field_u32(label, value):
    print_field_prefix(label)
    print(int(value))


def print_field_u64(label, value):
    print_field_prefix(label)
    print(int(value))


def print_field_double(label, value):
    print_field_prefix(label)
    print(f"{value:.3f}")


def format_duration(duration_seconds):
    seconds = int(duration_seconds)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def print_progress(label, done, total, remaining_seconds=None):
    width = 28
    filled = int((done * width) // total) if total else 0
    if filled > width:
        filled = width
    bar = "#" * filled + "." * (width - filled)
    print_field_prefix(label)
    print(f"[{bar}] {done}/{total}", end="")
    if total:
        print(f" ({(done * 100) // total}%)", end="")
    if remaining_seconds is not None:
        print(f" | estimated time remaining: {format_duration(remaining_seconds)}", end="")
    print()


def print_sample_preview(p, c, t):
    print_hex("first_plaintext=", p)
    print_hex("first_ciphertext=", c)
    print_field_u64("first_timing", t)


def print_offsets(off):
    print_field_prefix("round10 offsets")
    print(" ".join(f"{x:02x}" for x in off[:16]))


def mode_name(mode):
    if mode == MODE_SYNTHETIC:
        return "synthetic final-round cache-collision leakage"
    if mode == MODE_REAL:
        return "real measured encryption time"
    return "unknown"


def final_round_collisions(c, last):
    collisions = 0
    for i in range(16):
        xi = INVSBOX[c[i] ^ last[i]]
        for j in range(i + 1, 16):
            xj = INVSBOX[c[j] ^ last[j]]
            if xi == xj:
                collisions += 1
    return collisions


def synthetic_time(c, last):
    collisions = final_round_collisions(c, last)
    return 100000 - 500 * collisions + random.randrange(61) - 30


def real_time_encrypt(p, w, repeats):
    global timing_sink
    total = 0
    c = b""
    for _ in range(repeats):
        disturb_cache()
        start = time.perf_counter_ns()
        c = ttable_encrypt_block(p, w)
        acc = timing_sink
        for b in c:
            acc ^= b
        timing_sink = acc
        total += time.perf_counter_ns() - start
    return c, total


def arg_str(args, idx, default):
    return args[idx] if len(args) > idx else default


def parse_u32_lenient(s):
    try:
        return int(s, 0) & 0xFFFFFFFF
    except ValueError:
        return 0


def cmd_keygen(args):
    out = arg_str(args, 2, "key.bin")
    print_step("Key generation")
    print_note("Generating one random AES-128 key from /dev/urandom.")
    print_note("AES-128 keys are 16 bytes long.")
    key = random_bytes(16)
    try:
        write_file_exact(out, key)
    except OSError as exc:
        print(f"{out}: {exc}", file=sys.stderr)
        return 1
    print_hex("key=", key)
    print_field_str("wrote key file", out)
    return 0


def cmd_collect(args):
    global evict_size
    keyfile = arg_str(args, 2, "key.bin")
    out = arg_str(args, 3, "samples.bin")
    count = parse_u32_lenient(args[4]) if len(args) > 4 else (1 << 18)
    real_mode = args[1] == "collect-real"
    mode = MODE_REAL if real_mode else MODE_SYNTHETIC
    repeats = 1

    i = 5
    while i < len(args):
        opt = args[i]
        if opt in ("-real", "--real"):
            print("error: -real was removed; use the collect-real command instead.", file=sys.stderr)
            return 100
        if opt in ("-demo-leak", "--demo-leak"):
            print("error: -demo-leak was removed; this lab now keeps measured timing pure.", file=sys.stderr)
            return 100
        if opt in ("-synthetic", "--synthetic"):
            print("error: -synthetic was removed; use the collect command instead.", file=sys.stderr)
            return 100
        if opt in ("-repeat", "--repeat"):
            if i + 1 >= len(args):
                print(f"error: unknown collection option: {opt}", file=sys.stderr)
                return 100
            if not real_mode:
                print("error: -repeat only applies to collect-real.", file=sys.stderr)
                return 100
            i += 1
            repeats = parse_u32_lenient(args[i])
            if repeats == 0:
                repeats = 1
        elif opt in ("-evict-kb", "--evict-kb"):
            if i + 1 >= len(args):
                print(f"error: unknown collection option: {opt}", file=sys.stderr)
                return 100
            if not real_mode:
                print("error: -evict-kb only applies to collect-real.", file=sys.stderr)
                return 100
            i += 1
            kb = parse_u32_lenient(args[i])
            if kb > 0:
                evict_size = kb * 1024
        else:
            print(f"error: unknown collection option: {opt}", file=sys.stderr)
            return 100
        i += 1

    if count == 0 or count > MAX_SAMPLES:
        count = 1 << 18

    print_step("Sample collection")
    print_field_str("key file", keyfile)
    print_field_str("output file", out)
    print_field_u32("requested samples", count)
    print_field_str("timing mode", mode_name(mode))
    if mode == MODE_REAL:
        print_field_str("target AES", "aligned T-table AES with separate final table")
        print(f"  {clr_warn}NOTE{clr_reset} real mode measures elapsed encryption time on this machine.")
        print_note("Recovery may fail or need many more samples if the timing signal is weak.")
        print_field_u64("cache disturb bytes", evict_size)
        print_field_u32("repeats per sample", repeats)

    try:
        key = read_file_exact(keyfile, 16)
    except OSError as exc:
        print(f"{keyfile}: {exc}", file=sys.stderr)
        return 1
    print_hex("loaded_key=", key)
    print_note("Expanding the raw key into 176 bytes of AES-128 round keys.")
    w = key_expand(key)
    print_hex("round10_key=", w[160:176])

    verifier_p = random_bytes(16)
    verifier_c = encrypt_block(verifier_p, w)
    try:
        with open(out, "wb") as f:
            f.write(HEADER_STRUCT.pack(MAGIC, count, mode, verifier_p, verifier_c))
            print_note("Writing a verifier pair into the sample file header.")
            print_hex("verifier_plaintext=", verifier_p)
            print_hex("verifier_ciphertext=", verifier_c)
            print_note("Generating plaintext/ciphertext/timing records.")
            collection_started_at = time.monotonic()
            for n in range(count):
                p = random_bytes(16)
                if mode == MODE_REAL:
                    c, t = real_time_encrypt(p, w, repeats)
                else:
                    c = encrypt_block(p, w)
                    t = synthetic_time(c, w[160:176])
                f.write(SAMPLE_STRUCT.pack(p, c, t))
                if n == 0:
                    print_note("First generated sample preview:")
                    print_sample_preview(p, c, t)
                if count >= 8 and (n + 1) % (count // 4) == 0:
                    done = n + 1
                    remaining_seconds = None
                    if mode == MODE_REAL:
                        remaining_seconds = (time.monotonic() - collection_started_at) * (count - done) / done
                    print_progress("collection", done, count, remaining_seconds)
    except OSError as exc:
        print(f"{out}: {exc}", file=sys.stderr)
        return 1

    print_note("Finished writing sample file.")
    print_hex("key=", key)
    print_field_u32("samples", count)
    print_field_str("out", out)
    return 0


def pair_index(i, j):
    k = 0
    for a in range(16):
        for b in range(a + 1, 16):
            if a == i and b == j:
                return k
            k += 1
    return -1


PAIR_LIST = [(i, j) for i in range(16) for j in range(i + 1, 16)]


def candidate_cost(off, mean):
    c = 0.0
    for p, (i, j) in enumerate(PAIR_LIST):
        c += mean[p][off[i] ^ off[j]]
    return c


def optimize_offsets(off, mean):
    best_cost = candidate_cost(off, mean)
    changed = True
    iterations = 0
    for iter_n in range(200):
        if not changed:
            break
        changed = False
        iterations = iter_n + 1
        for b in range(1, 16):
            bestv = off[b]
            local = best_cost
            old = off[b]
            for v in range(256):
                off[b] = v
                cost = candidate_cost(off, mean)
                if cost < local:
                    local = cost
                    bestv = v
            off[b] = old
            if bestv != off[b]:
                off[b] = bestv
                best_cost = local
                changed = True
    return best_cost, iterations


def write_verified_candidate(off, h, out, score, start_index, iterations):
    _, count, _, verifier_p, verifier_c = h
    for k0 in range(256):
        last = bytes((k0 ^ off[i]) for i in range(16))
        raw = invert_last_round_key(last)
        w = key_expand(raw)
        check = encrypt_block(verifier_p, w)
        if check == verifier_c:
            try:
                write_file_exact(out, raw)
            except OSError as exc:
                print(f"{out}: {exc}", file=sys.stderr)
                return 2
            print_field_u32("successful start", start_index)
            print_field_u32("start iterations", iterations)
            print_field_prefix("verified candidate k0")
            print(f"{k0:02x}")
            print_hex("recovered_key=", raw)
            print_hex("round10_key=", last)
            print_field_u32("samples", count)
            print_field_double("score", score)
            print_field_str("out", out)
            print(f"  {clr_ok}SUCCESS{clr_reset} recovered key verified against the stored plaintext/ciphertext pair.")
            return 1
    return 0


def read_header(f):
    data = f.read(HEADER_STRUCT.size)
    if len(data) != HEADER_STRUCT.size:
        return None
    return HEADER_STRUCT.unpack(data)


def cmd_attack(args):
    samples_path = arg_str(args, 2, "samples.bin")
    out = arg_str(args, 3, "recovered_key.bin")
    print_step("Final-round timing attack")
    print_field_str("sample file", samples_path)
    print_field_str("recovered key out", out)
    try:
        f = open(samples_path, "rb")
    except OSError as exc:
        print(f"{samples_path}: {exc}", file=sys.stderr)
        return 1

    with f:
        h = read_header(f)
        if h is None or h[0] != MAGIC or h[1] == 0:
            print("bad sample file", file=sys.stderr)
            return 1
        _, count, mode, verifier_p, verifier_c = h
        print_field_u32("sample count", count)
        print_field_u32("sample mode", mode)
        print_field_str("timing mode", mode_name(mode))
        if mode == MODE_REAL:
            print(f"  {clr_warn}NOTE{clr_reset} real timing mode is experimental; recovery is not guaranteed.")
        print_hex("verifier_plaintext=", verifier_p)
        print_hex("verifier_ciphertext=", verifier_c)
        print_note("Building an average timing table for all 120 ciphertext-byte pairs.")
        print_note("For each pair (i,j), timings are grouped by delta = c[i] ^ c[j].")

        data_start = f.tell()
        min_time = (1 << 64) - 1
        for _ in range(count):
            rec = f.read(SAMPLE_STRUCT.size)
            if len(rec) != SAMPLE_STRUCT.size:
                print("truncated samples", file=sys.stderr)
                return 1
            t = struct.unpack_from("<Q", rec, 32)[0]
            if t < min_time:
                min_time = t
        cutoff = min_time * 2
        if cutoff >= (1 << 64):
            cutoff = (1 << 64) - 1
        print_field_u64("minimum timing", min_time)
        print_field_u64("outlier cutoff", cutoff)

        f.seek(data_start)
        sums = [[0.0] * 256 for _ in range(PAIRS)]
        nums = [[0] * 256 for _ in range(PAIRS)]
        used_samples = 0
        ignored_samples = 0
        first = True
        for n in range(count):
            rec = f.read(SAMPLE_STRUCT.size)
            if len(rec) != SAMPLE_STRUCT.size:
                print("truncated samples", file=sys.stderr)
                return 1
            p = rec[0:16]
            c = rec[16:32]
            t = struct.unpack_from("<Q", rec, 32)[0]
            if first:
                print_note("First sample read from file:")
                print_sample_preview(p, c, t)
                first = False
            if t > cutoff:
                ignored_samples += 1
                continue
            used_samples += 1
            for pair, (i, j) in enumerate(PAIR_LIST):
                d = c[i] ^ c[j]
                sums[pair][d] += float(t)
                nums[pair][d] += 1
            if count >= 8 and (n + 1) % (count // 4) == 0:
                print_progress("analysis read", n + 1, count)

    print_field_u32("used samples", used_samples)
    print_field_u32("ignored samples", ignored_samples)
    print_note("Converting timing sums into averages.")
    mean = [[0.0] * 256 for _ in range(PAIRS)]
    for p in range(PAIRS):
        for d in range(256):
            mean[p][d] = sums[p][d] / nums[p][d] if nums[p][d] else 1e30

    print_note("Finding the lowest-average delta for pairs involving byte 0.")
    print(f"\n  {'pair':<8} {'delta':<8} {'avg_time':<14} {'observations':<12}")
    print(f"  {'--------':<8} {'--------':<8} {'--------------':<14} {'------------':<12}")
    best_delta = [[0] * 16 for _ in range(16)]
    pp = 0
    for i in range(16):
        for j in range(i + 1, 16):
            best = 0
            for d in range(1, 256):
                if mean[pp][d] < mean[pp][best]:
                    best = d
            best_delta[i][j] = best
            best_delta[j][i] = best
            pp += 1

    initial = [0] * 16
    for j in range(1, 16):
        pidx = pair_index(0, j)
        best = best_delta[0][j]
        initial[j] = best
        print(f"  (0,{j:2d})   {best:02x}       {mean[pidx][best]:<14.3f} {nums[pidx][best]:<12d}")
    print_offsets(initial)

    print_note("Refining key-byte offsets with multi-start local search.")
    print(f"\n  {'start':<8} {'kind':<12} {'score':<16} {'iterations':<10}")
    print(f"  {'--------':<8} {'------------':<12} {'----------------':<16} {'----------':<10}")

    global_best = initial[:]
    global_cost = 1e300
    start_index = 0
    for start in range(81):
        kind = "random"
        off = [0] * 16
        if start == 0:
            off = initial[:]
            kind = "byte0"
        elif start <= 16:
            anchor = start - 1
            kind = "anchor"
            off[anchor] = best_delta[0][anchor]
            for j in range(1, 16):
                if j == anchor:
                    continue
                off[j] = off[anchor] ^ best_delta[anchor][j]
        else:
            for j in range(1, 16):
                off[j] = random.randrange(256)

        cost, iterations = optimize_offsets(off, mean)
        print(f"  {start_index:<8d} {kind:<12} {cost:<16.3f} {iterations:<10d}")
        if cost < global_cost:
            global_cost = cost
            global_best = off[:]
        ok = write_verified_candidate(off, h, out, cost, start_index, iterations)
        if ok:
            return 0 if ok == 1 else 1
        start_index += 1

    print_field_double("best unverified score", global_cost)
    print_offsets(global_best)
    print("no verified key candidate found", file=sys.stderr)
    return 2


def cmd_verify(args):
    keyfile = arg_str(args, 2, "recovered_key.bin")
    samples_path = arg_str(args, 3, "samples.bin")
    print_step("Recovered key verification")
    print_field_str("candidate key file", keyfile)
    try:
        key = read_file_exact(keyfile, 16)
    except OSError as exc:
        print(f"{keyfile}: {exc}", file=sys.stderr)
        return 1
    print_hex("candidate_key=", key)
    print_field_str("sample file", samples_path)
    try:
        with open(samples_path, "rb") as f:
            h = read_header(f)
    except OSError as exc:
        print(f"{samples_path}: {exc}", file=sys.stderr)
        return 1
    if h is None or h[0] != MAGIC:
        print("bad sample file", file=sys.stderr)
        return 1
    _, _, _, verifier_p, verifier_c = h
    print_hex("verifier_plaintext=", verifier_p)
    print_hex("expected_ciphertext=", verifier_c)
    w = key_expand(key)
    check = encrypt_block(verifier_p, w)
    print_hex("computed_ciphertext=", check)
    if check != verifier_c:
        print("verification failed", file=sys.stderr)
        return 2
    print_hex("verified_key=", key)
    print(f"  {clr_ok}SUCCESS{clr_reset} candidate key reproduces the verifier ciphertext.")
    return 0


def cmd_selftest():
    print_step("Self-test")
    print_note("Checking AES-128 encryption against a known NIST test vector.")
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    pt = bytes.fromhex("00112233445566778899aabbccddeeff")
    want = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")
    print_hex("test_key=", key)
    print_hex("test_plaintext=", pt)
    print_hex("expected_ciphertext=", want)
    w = key_expand(key)
    got = encrypt_block(pt, w)
    print_hex("computed_ciphertext=", got)
    if got != want:
        print_hex("got=", got)
        return 1
    print(f"  {clr_ok}OK{clr_reset} AES encryption test passed.")
    got = ttable_encrypt_block(pt, w)
    print_hex("ttable_ciphertext=", got)
    if got != want:
        return 3
    print(f"  {clr_ok}OK{clr_reset} T-table AES target matches the known vector.")
    print_note("Checking that round 10 key can be reversed back to the original key.")
    raw = invert_last_round_key(w[160:176])
    print_hex("recovered_from_round10=", raw)
    if raw != key:
        return 2
    print(f"  {clr_ok}OK{clr_reset} selftest=ok")
    return 0


def usage(argv0):
    sys.stderr.write(
        "usage:\n"
        f"  {argv0} selftest\n"
        f"  {argv0} keygen [key.bin]\n"
        f"  {argv0} collect [key.bin] [samples.bin] [count]\n"
        f"  {argv0} collect-real [key.bin] [samples.bin] [count] [-repeat N] [-evict-kb KB]\n"
        f"  {argv0} attack-final [samples.bin] [recovered_key.bin]\n"
        f"  {argv0} verify [recovered_key.bin] [samples.bin]\n"
    )


def run(args):
    init_console()
    if len(args) < 2:
        usage(args[0])
        return 100
    if args[1] == "selftest":
        return cmd_selftest()
    if args[1] == "keygen":
        return cmd_keygen(args)
    if args[1] in ("collect", "collect-real"):
        return cmd_collect(args)
    if args[1] == "attack-final":
        return cmd_attack(args)
    if args[1] == "verify":
        return cmd_verify(args)
    usage(args[0])
    return 100


if __name__ == "__main__":
    raise SystemExit(run(sys.argv))
