#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach/mach_time.h>
#endif

#define AES_BLOCK 16
#define AES_EXPANDED 176
#define MAX_SAMPLES (1u << 22)
#define PAIRS 120
#define MAGIC 0x41455354494d4531ULL
#define MODE_SYNTHETIC 1
#define MODE_REAL 2
#define EVICT_SIZE (8u * 1024u * 1024u)
#define EVICT_STRIDE 64u

typedef unsigned char u8;
typedef unsigned int u32;
typedef unsigned long long u64;

typedef struct {
  u8 p[16];
  u8 c[16];
  u64 t;
} sample_t;

typedef struct {
  u64 magic;
  u32 count;
  u32 mode;
  u8 verifier_p[16];
  u8 verifier_c[16];
} sample_header_t;

static int use_color = 0;
static const char *clr_reset = "";
static const char *clr_title = "";
static const char *clr_label = "";
static const char *clr_ok = "";
static const char *clr_warn = "";
static volatile u8 timing_sink = 0;

static const u8 sbox[256] = {
  0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
  0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
  0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
  0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
  0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
  0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
  0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
  0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
  0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
  0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
  0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
  0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
  0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
  0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
  0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
  0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
};

static const u8 invsbox[256] = {
  0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
  0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
  0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
  0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
  0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
  0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
  0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
  0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
  0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
  0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
  0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
  0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
  0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
  0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
  0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
  0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d
};

static const u8 rcon[10] = {0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36};

static u8 xtime(u8 x) { return (u8)((x << 1) ^ ((x >> 7) * 0x1b)); }

static void add_round_key(u8 s[16], const u8 *rk) {
  for (int i = 0; i < 16; i++) s[i] ^= rk[i];
}

static void sub_bytes(u8 s[16]) {
  for (int i = 0; i < 16; i++) s[i] = sbox[s[i]];
}

static void shift_rows(u8 s[16]) {
  u8 t[16];
  t[0]=s[0]; t[1]=s[5]; t[2]=s[10]; t[3]=s[15];
  t[4]=s[4]; t[5]=s[9]; t[6]=s[14]; t[7]=s[3];
  t[8]=s[8]; t[9]=s[13]; t[10]=s[2]; t[11]=s[7];
  t[12]=s[12]; t[13]=s[1]; t[14]=s[6]; t[15]=s[11];
  memcpy(s, t, 16);
}

static void mix_columns(u8 s[16]) {
  for (int c = 0; c < 4; c++) {
    u8 *a = s + 4 * c;
    u8 x = a[0] ^ a[1] ^ a[2] ^ a[3];
    u8 y = a[0];
    a[0] ^= x ^ xtime((u8)(a[0] ^ a[1]));
    a[1] ^= x ^ xtime((u8)(a[1] ^ a[2]));
    a[2] ^= x ^ xtime((u8)(a[2] ^ a[3]));
    a[3] ^= x ^ xtime((u8)(a[3] ^ y));
  }
}

static void key_expand(const u8 key[16], u8 w[176]) {
  memcpy(w, key, 16);
  int bytes = 16, r = 0;
  u8 temp[4];
  while (bytes < 176) {
    memcpy(temp, w + bytes - 4, 4);
    if ((bytes & 15) == 0) {
      u8 k = temp[0];
      temp[0] = (u8)(sbox[temp[1]] ^ rcon[r++]);
      temp[1] = sbox[temp[2]];
      temp[2] = sbox[temp[3]];
      temp[3] = sbox[k];
    }
    for (int i = 0; i < 4; i++) {
      w[bytes] = (u8)(w[bytes - 16] ^ temp[i]);
      bytes++;
    }
  }
}

static void encrypt_block(const u8 in[16], u8 out[16], const u8 w[176]) {
  u8 s[16];
  memcpy(s, in, 16);
  add_round_key(s, w);
  for (int r = 1; r <= 9; r++) {
    sub_bytes(s);
    shift_rows(s);
    mix_columns(s);
    add_round_key(s, w + 16 * r);
  }
  sub_bytes(s);
  shift_rows(s);
  add_round_key(s, w + 160);
  memcpy(out, s, 16);
}

static u64 now_ticks(void) {
#ifdef __APPLE__
  return (u64)mach_absolute_time();
#elif defined(CLOCK_MONOTONIC_RAW)
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
  return (u64)ts.tv_sec * 1000000000ULL + (u64)ts.tv_nsec;
#else
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (u64)ts.tv_sec * 1000000000ULL + (u64)ts.tv_nsec;
#endif
}

static void disturb_cache(void) {
  static u8 *buf = NULL;
  if (!buf) {
    buf = (u8 *)malloc(EVICT_SIZE);
    if (!buf) { perror("malloc"); exit(1); }
    for (size_t i = 0; i < EVICT_SIZE; i++) buf[i] = (u8)i;
  }
  u8 acc = timing_sink;
  for (size_t i = 0; i < EVICT_SIZE; i += EVICT_STRIDE) {
    acc ^= buf[i];
  }
  timing_sink = acc;
}

static u64 real_time_encrypt(const u8 p[16], u8 c[16], const u8 w[176]) {
  disturb_cache();
  u64 start = now_ticks();
  encrypt_block(p, c, w);
  u8 acc = timing_sink;
  for (int i = 0; i < 16; i++) acc ^= c[i];
  timing_sink = acc;
  u64 end = now_ticks();
  return end - start;
}

static void invert_last_round_key(const u8 last[16], u8 raw[16]) {
  u8 w[176] = {0};
  memcpy(w + 160, last, 16);
  for (int round = 10; round >= 1; round--) {
    u8 *prev = w + 16 * (round - 1);
    u8 *cur = w + 16 * round;
    for (int i = 12; i >= 4; i -= 4)
      for (int b = 0; b < 4; b++) prev[i + b] = (u8)(cur[i + b] ^ cur[i - 4 + b]);
    u8 temp[4] = { prev[13], prev[14], prev[15], prev[12] };
    temp[0] = (u8)(sbox[temp[0]] ^ rcon[round - 1]);
    temp[1] = sbox[temp[1]];
    temp[2] = sbox[temp[2]];
    temp[3] = sbox[temp[3]];
    for (int b = 0; b < 4; b++) prev[b] = (u8)(cur[b] ^ temp[b]);
  }
  memcpy(raw, w, 16);
}

static void random_bytes(u8 *buf, size_t len) {
  FILE *f = fopen("/dev/urandom", "rb");
  if (!f) { perror("/dev/urandom"); exit(1); }
  if (fread(buf, 1, len, f) != len) { perror("fread"); exit(1); }
  fclose(f);
}

static int read_file_exact(const char *path, void *buf, size_t len) {
  FILE *f = fopen(path, "rb");
  if (!f) return -1;
  size_t n = fread(buf, 1, len, f);
  fclose(f);
  return n == len ? 0 : -1;
}

static int write_file_exact(const char *path, const void *buf, size_t len) {
  FILE *f = fopen(path, "wb");
  if (!f) return -1;
  size_t n = fwrite(buf, 1, len, f);
  fclose(f);
  return n == len ? 0 : -1;
}

static void init_console(void) {
  use_color = isatty(STDOUT_FILENO) && getenv("NO_COLOR") == NULL;
  if (use_color) {
    clr_reset = "\033[0m";
    clr_title = "\033[1;36m";
    clr_label = "\033[1m";
    clr_ok = "\033[1;32m";
    clr_warn = "\033[1;33m";
  }
}

static void clean_label(const char *label, char out[64]) {
  size_t n = strlen(label);
  while (n > 0 && (label[n - 1] == '=' || label[n - 1] == ':')) n--;
  if (n >= 64) n = 63;
  memcpy(out, label, n);
  out[n] = 0;
}

static void print_field_prefix(const char *label) {
  char clean[64];
  clean_label(label, clean);
  printf("  %s%-24s%s : ", clr_label, clean, clr_reset);
}

static void print_hex(const char *label, const u8 x[16]) {
  print_field_prefix(label);
  for (int i = 0; i < 16; i++) printf("%02x", x[i]);
  printf("\n");
}

static void print_step(const char *title) {
  printf("\n%s============================================================%s\n", clr_title, clr_reset);
  printf("%s%s%s\n", clr_title, title, clr_reset);
  printf("%s============================================================%s\n", clr_title, clr_reset);
}

static void print_note(const char *text) {
  printf("  %s\n", text);
}

static void print_field_str(const char *label, const char *value) {
  print_field_prefix(label);
  printf("%s\n", value);
}

static void print_field_u32(const char *label, u32 value) {
  print_field_prefix(label);
  printf("%u\n", value);
}

static void print_field_u64(const char *label, u64 value) {
  print_field_prefix(label);
  printf("%llu\n", value);
}

static void print_field_double(const char *label, double value) {
  print_field_prefix(label);
  printf("%.3f\n", value);
}

static void print_progress(const char *label, u32 done, u32 total) {
  const int width = 28;
  int filled = total ? (int)(((u64)done * width) / total) : 0;
  if (filled > width) filled = width;
  print_field_prefix(label);
  printf("[");
  for (int i = 0; i < width; i++) printf("%c", i < filled ? '#' : '.');
  printf("] %u/%u", done, total);
  if (total) printf(" (%u%%)", (unsigned)(((u64)done * 100) / total));
  printf("\n");
}

static void print_sample_preview(const sample_t *s) {
  print_hex("first_plaintext=", s->p);
  print_hex("first_ciphertext=", s->c);
  print_field_u64("first_timing", s->t);
}

static void print_offsets(const u8 off[16]) {
  print_field_prefix("round10 offsets");
  for (int i = 0; i < 16; i++) {
    printf("%s%02x", i ? " " : "", off[i]);
  }
  printf("\n");
}

static const char *mode_name(u32 mode) {
  if (mode == MODE_SYNTHETIC) return "synthetic final-round cache-collision leakage";
  if (mode == MODE_REAL) return "real measured encryption time";
  return "unknown";
}

static u64 synthetic_time(const u8 c[16], const u8 last[16]) {
  int collisions = 0;
  for (int i = 0; i < 16; i++) {
    u8 xi = invsbox[c[i] ^ last[i]];
    for (int j = i + 1; j < 16; j++) {
      u8 xj = invsbox[c[j] ^ last[j]];
      if (xi == xj) collisions++;
    }
  }
  return (u64)(100000 - 500 * collisions + (rand() % 61) - 30);
}

static int cmd_keygen(int argc, char **argv) {
  const char *out = argc > 2 ? argv[2] : "key.bin";
  u8 key[16];
  print_step("Key generation");
  print_note("Generating one random AES-128 key from /dev/urandom.");
  print_note("AES-128 keys are 16 bytes long.");
  random_bytes(key, 16);
  if (write_file_exact(out, key, 16)) { perror(out); return 1; }
  print_hex("key=", key);
  print_field_str("wrote key file", out);
  return 0;
}

static int cmd_collect(int argc, char **argv) {
  const char *keyfile = argc > 2 ? argv[2] : "key.bin";
  const char *out = argc > 3 ? argv[3] : "samples.bin";
  u32 count = argc > 4 ? (u32)strtoul(argv[4], 0, 0) : (1u << 18);
  u32 mode = !strcmp(argv[1], "collect-real") ? MODE_REAL : MODE_SYNTHETIC;
  for (int i = 5; i < argc; i++) {
    if (!strcmp(argv[i], "-real") || !strcmp(argv[i], "--real")) mode = MODE_REAL;
    else if (!strcmp(argv[i], "-synthetic") || !strcmp(argv[i], "--synthetic")) mode = MODE_SYNTHETIC;
  }
  if (count == 0 || count > MAX_SAMPLES) count = (1u << 18);

  print_step("Sample collection");
  print_field_str("key file", keyfile);
  print_field_str("output file", out);
  print_field_u32("requested samples", count);
  print_field_str("timing mode", mode_name(mode));
  if (mode == MODE_REAL) {
    printf("  %sNOTE%s real mode measures elapsed encryption time on this machine.\n", clr_warn, clr_reset);
    print_note("Recovery may fail or need many more samples if the timing signal is weak.");
    print_field_u32("cache disturb bytes", EVICT_SIZE);
  }

  u8 key[16], w[176];
  if (read_file_exact(keyfile, key, 16)) { perror(keyfile); return 1; }
  print_hex("loaded_key=", key);
  print_note("Expanding the raw key into 176 bytes of AES-128 round keys.");
  key_expand(key, w);
  print_hex("round10_key=", w + 160);

  FILE *f = fopen(out, "wb");
  if (!f) { perror(out); return 1; }
  sample_header_t h;
  memset(&h, 0, sizeof h);
  h.magic = MAGIC;
  h.count = count;
  h.mode = mode;
  random_bytes(h.verifier_p, 16);
  encrypt_block(h.verifier_p, h.verifier_c, w);
  fwrite(&h, sizeof h, 1, f);
  print_note("Writing a verifier pair into the sample file header.");
  print_hex("verifier_plaintext=", h.verifier_p);
  print_hex("verifier_ciphertext=", h.verifier_c);

  print_note("Generating plaintext/ciphertext/timing records.");
  srand((unsigned)time(NULL));
  sample_t s;
  for (u32 i = 0; i < count; i++) {
    random_bytes(s.p, 16);
    if (mode == MODE_REAL) {
      s.t = real_time_encrypt(s.p, s.c, w);
    } else {
      encrypt_block(s.p, s.c, w);
      s.t = synthetic_time(s.c, w + 160);
    }
    fwrite(&s, sizeof s, 1, f);
    if (i == 0) {
      print_note("First generated sample preview:");
      print_sample_preview(&s);
    }
    if (count >= 8 && (i + 1) % (count / 4) == 0) {
      print_progress("collection", i + 1, count);
      fflush(stdout);
    }
  }
  fclose(f);
  print_note("Finished writing sample file.");
  print_hex("key=", key);
  print_field_u32("samples", count);
  print_field_str("out", out);
  return 0;
}

static int pair_index(int i, int j) {
  int k = 0;
  for (int a = 0; a < 16; a++)
    for (int b = a + 1; b < 16; b++, k++)
      if (a == i && b == j) return k;
  return -1;
}

static double candidate_cost(const u8 off[16], double mean[PAIRS][256]) {
  double c = 0.0;
  int p = 0;
  for (int i = 0; i < 16; i++)
    for (int j = i + 1; j < 16; j++, p++)
      c += mean[p][off[i] ^ off[j]];
  return c;
}

static int cmd_attack(int argc, char **argv) {
  const char *samples_path = argc > 2 ? argv[2] : "samples.bin";
  const char *out = argc > 3 ? argv[3] : "recovered_key.bin";
  print_step("Final-round timing attack");
  print_field_str("sample file", samples_path);
  print_field_str("recovered key out", out);
  FILE *f = fopen(samples_path, "rb");
  if (!f) { perror(samples_path); return 1; }
  sample_header_t h;
  if (fread(&h, sizeof h, 1, f) != 1 || h.magic != MAGIC || h.count == 0) {
    fprintf(stderr, "bad sample file\n");
    fclose(f);
    return 1;
  }
  print_field_u32("sample count", h.count);
  print_field_u32("sample mode", h.mode);
  print_field_str("timing mode", mode_name(h.mode));
  if (h.mode == MODE_REAL) {
    printf("  %sNOTE%s real timing mode is experimental; recovery is not guaranteed.\n",
           clr_warn, clr_reset);
  }
  print_hex("verifier_plaintext=", h.verifier_p);
  print_hex("verifier_ciphertext=", h.verifier_c);
  print_note("Building an average timing table for all 120 ciphertext-byte pairs.");
  print_note("For each pair (i,j), timings are grouped by delta = c[i] ^ c[j].");

  double sum[PAIRS][256] = {{0}};
  u32 num[PAIRS][256] = {{0}};
  sample_t s;
  for (u32 n = 0; n < h.count; n++) {
    if (fread(&s, sizeof s, 1, f) != 1) { fprintf(stderr, "truncated samples\n"); return 1; }
    if (n == 0) {
      print_note("First sample read from file:");
      print_sample_preview(&s);
    }
    int p = 0;
    for (int i = 0; i < 16; i++)
      for (int j = i + 1; j < 16; j++, p++) {
        u8 d = (u8)(s.c[i] ^ s.c[j]);
        sum[p][d] += (double)s.t;
        num[p][d]++;
      }
    if (h.count >= 8 && (n + 1) % (h.count / 4) == 0) {
      print_progress("analysis read", n + 1, h.count);
      fflush(stdout);
    }
  }
  fclose(f);

  print_note("Converting timing sums into averages.");
  double mean[PAIRS][256];
  for (int p = 0; p < PAIRS; p++)
    for (int d = 0; d < 256; d++)
      mean[p][d] = num[p][d] ? sum[p][d] / num[p][d] : 1e30;

  print_note("Finding the lowest-average delta for pairs involving byte 0.");
  printf("\n  %-8s %-8s %-14s %-12s\n", "pair", "delta", "avg_time", "observations");
  printf("  %-8s %-8s %-14s %-12s\n", "--------", "--------", "--------------", "------------");
  u8 off[16] = {0};
  for (int j = 1; j < 16; j++) {
    int p = pair_index(0, j);
    int best = 0;
    for (int d = 1; d < 256; d++) if (mean[p][d] < mean[p][best]) best = d;
    off[j] = (u8)best;
    printf("  (0,%2d)   %02x       %-14.3f %-12u\n",
           j, best, mean[p][best], num[p][best]);
  }
  print_offsets(off);

  print_note("Refining key-byte offsets with local search across all 120 pairs.");
  printf("\n  %-10s %-16s %-8s\n", "iteration", "score", "changed");
  printf("  %-10s %-16s %-8s\n", "----------", "----------------", "--------");
  double best_cost = candidate_cost(off, mean);
  int changed = 1;
  int iterations = 0;
  for (int iter = 0; iter < 200 && changed; iter++) {
    changed = 0;
    iterations = iter + 1;
    for (int b = 1; b < 16; b++) {
      u8 bestv = off[b];
      double local = best_cost;
      for (int v = 0; v < 256; v++) {
        u8 old = off[b];
        off[b] = (u8)v;
        double c = candidate_cost(off, mean);
        off[b] = old;
        if (c < local) { local = c; bestv = (u8)v; }
      }
      if (bestv != off[b]) {
        off[b] = bestv;
        best_cost = local;
        changed = 1;
      }
    }
    printf("  %-10d %-16.3f %-8s\n",
           iter + 1, best_cost, changed ? "yes" : "no");
  }
  print_field_u32("local search iterations", (u32)iterations);
  print_offsets(off);

  print_note("Trying 256 possibilities for final_round_key[0].");
  print_note("Each final-round key candidate is reversed to a raw AES key and checked.");
  for (int k0 = 0; k0 < 256; k0++) {
    u8 last[16], raw[16], w[176], check[16];
    for (int i = 0; i < 16; i++) last[i] = (u8)(k0 ^ off[i]);
    invert_last_round_key(last, raw);
    key_expand(raw, w);
    encrypt_block(h.verifier_p, check, w);
    if (!memcmp(check, h.verifier_c, 16)) {
      if (write_file_exact(out, raw, 16)) { perror(out); return 1; }
      print_field_prefix("verified candidate k0");
      printf("%02x\n", k0);
      print_hex("recovered_key=", raw);
      print_hex("round10_key=", last);
      print_field_u32("samples", h.count);
      print_field_double("score", best_cost);
      print_field_str("out", out);
      printf("  %sSUCCESS%s recovered key verified against the stored plaintext/ciphertext pair.\n",
             clr_ok, clr_reset);
      return 0;
    }
  }

  fprintf(stderr, "no verified key candidate found\n");
  return 2;
}

static int cmd_verify(int argc, char **argv) {
  const char *keyfile = argc > 2 ? argv[2] : "recovered_key.bin";
  const char *samples_path = argc > 3 ? argv[3] : "samples.bin";
  u8 key[16], w[176], check[16];
  print_step("Recovered key verification");
  print_field_str("candidate key file", keyfile);
  if (read_file_exact(keyfile, key, 16)) { perror(keyfile); return 1; }
  print_hex("candidate_key=", key);
  print_field_str("sample file", samples_path);
  FILE *f = fopen(samples_path, "rb");
  if (!f) { perror(samples_path); return 1; }
  sample_header_t h;
  if (fread(&h, sizeof h, 1, f) != 1 || h.magic != MAGIC) { fprintf(stderr, "bad sample file\n"); return 1; }
  fclose(f);
  print_hex("verifier_plaintext=", h.verifier_p);
  print_hex("expected_ciphertext=", h.verifier_c);
  key_expand(key, w);
  encrypt_block(h.verifier_p, check, w);
  print_hex("computed_ciphertext=", check);
  if (memcmp(check, h.verifier_c, 16)) {
    fprintf(stderr, "verification failed\n");
    return 2;
  }
  print_hex("verified_key=", key);
  printf("  %sSUCCESS%s candidate key reproduces the verifier ciphertext.\n",
         clr_ok, clr_reset);
  return 0;
}

static int cmd_selftest(void) {
  print_step("Self-test");
  print_note("Checking AES-128 encryption against a known NIST test vector.");
  const u8 key[16] = {0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0a,0x0b,0x0c,0x0d,0x0e,0x0f};
  const u8 pt[16] = {0x00,0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,0x99,0xaa,0xbb,0xcc,0xdd,0xee,0xff};
  const u8 want[16] = {0x69,0xc4,0xe0,0xd8,0x6a,0x7b,0x04,0x30,0xd8,0xcd,0xb7,0x80,0x70,0xb4,0xc5,0x5a};
  u8 w[176], got[16], raw[16];
  print_hex("test_key=", key);
  print_hex("test_plaintext=", pt);
  print_hex("expected_ciphertext=", want);
  key_expand(key, w);
  encrypt_block(pt, got, w);
  print_hex("computed_ciphertext=", got);
  if (memcmp(got, want, 16)) {
    print_hex("got=", got);
    return 1;
  }
  printf("  %sOK%s AES encryption test passed.\n", clr_ok, clr_reset);
  print_note("Checking that round 10 key can be reversed back to the original key.");
  invert_last_round_key(w + 160, raw);
  print_hex("recovered_from_round10=", raw);
  if (memcmp(raw, key, 16)) return 2;
  printf("  %sOK%s selftest=ok\n", clr_ok, clr_reset);
  return 0;
}

static void usage(const char *argv0) {
  fprintf(stderr,
    "usage:\n"
    "  %s selftest\n"
    "  %s keygen [key.bin]\n"
    "  %s collect [key.bin] [samples.bin] [count] [-real]\n"
    "  %s collect-real [key.bin] [samples.bin] [count]\n"
    "  %s attack-final [samples.bin] [recovered_key.bin]\n"
    "  %s verify [recovered_key.bin] [samples.bin]\n",
    argv0, argv0, argv0, argv0, argv0, argv0);
}

int main(int argc, char **argv) {
  init_console();
  if (argc < 2) { usage(argv[0]); return 100; }
  if (!strcmp(argv[1], "selftest")) return cmd_selftest();
  if (!strcmp(argv[1], "keygen")) return cmd_keygen(argc, argv);
  if (!strcmp(argv[1], "collect")) return cmd_collect(argc, argv);
  if (!strcmp(argv[1], "collect-real")) return cmd_collect(argc, argv);
  if (!strcmp(argv[1], "attack-final")) return cmd_attack(argc, argv);
  if (!strcmp(argv[1], "verify")) return cmd_verify(argc, argv);
  usage(argv[0]);
  return 100;
}
