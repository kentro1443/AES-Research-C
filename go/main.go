package main

import (
	"bufio"
	"bytes"
	crand "crypto/rand"
	"encoding/binary"
	"fmt"
	"io"
	"math"
	mrand "math/rand"
	"os"
	"strconv"
	"time"
	"unsafe"
)

type u8 = byte
type u32 = uint32
type u64 = uint64

type sampleT struct {
	P [16]u8
	C [16]u8
	T u64
}

type sampleHeaderT struct {
	Magic     u64
	Count     u32
	Mode      u32
	VerifierP [16]u8
	VerifierC [16]u8
}

const (
	aesBlock         = 16
	aesExpanded      = 176
	maxSamples       = 1 << 22
	pairs            = 120
	magic            = u64(0x41455354494d4531)
	modeSynthetic    = u32(1)
	modeReal         = u32(2)
	defaultEvictSize = 256 * 1024
	evictStride      = 64
	finalStride      = 4096
)

var useColor bool
var clrReset, clrTitle, clrLabel, clrOk, clrWarn string
var timingSink u8
var tablesReady bool
var evictSize = defaultEvictSize
var evictBuf []u8
var evictBufSize int

// alignedBuf over-allocates and returns a page-aligned sub-slice, standing
// in for C's __attribute__((aligned(4096))) statics; safe because Go's
// current GC is non-moving.
func alignedBuf(size int) []u8 {
	raw := make([]u8, size+4095)
	base := uintptr(unsafe.Pointer(&raw[0]))
	aligned := (base + 4095) &^ 4095
	return unsafe.Slice((*u8)(unsafe.Pointer(&raw[aligned-base])), size)
}

var te0 = alignedBuf(256 * 4)
var te1 = alignedBuf(256 * 4)
var te2 = alignedBuf(256 * 4)
var te3 = alignedBuf(256 * 4)
var finalTable = alignedBuf(256 * finalStride)

var sbox = [256]u8{
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
}

var invsbox = [256]u8{
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
}

var rcon = [10]u8{0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36}

var shiftRowsPerm = [16]u8{0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2, 7, 12, 1, 6, 11}

func xtime(x u8) u8 { return (x << 1) ^ ((x >> 7) * 0x1b) }
func mul3(x u8) u8  { return xtime(x) ^ x }

func addRoundKey(s []u8, rk []u8) {
	for i := 0; i < 16; i++ {
		s[i] ^= rk[i]
	}
}

func subBytes(s []u8) {
	for i := 0; i < 16; i++ {
		s[i] = sbox[s[i]]
	}
}

func shiftRows(s []u8) {
	var t [16]u8
	for i := 0; i < 16; i++ {
		t[i] = s[shiftRowsPerm[i]]
	}
	copy(s, t[:])
}

func mixColumns(s []u8) {
	for c := 0; c < 4; c++ {
		a := s[4*c : 4*c+4]
		x := a[0] ^ a[1] ^ a[2] ^ a[3]
		y := a[0]
		a[0] ^= x ^ xtime(a[0]^a[1])
		a[1] ^= x ^ xtime(a[1]^a[2])
		a[2] ^= x ^ xtime(a[2]^a[3])
		a[3] ^= x ^ xtime(a[3]^y)
	}
}

func keyExpand(key []u8, w []u8) {
	copy(w[0:16], key[0:16])
	bytesN, r := 16, 0
	var temp [4]u8
	for bytesN < aesExpanded {
		copy(temp[:], w[bytesN-4:bytesN])
		if bytesN&15 == 0 {
			k := temp[0]
			temp[0] = sbox[temp[1]] ^ rcon[r]
			r++
			temp[1] = sbox[temp[2]]
			temp[2] = sbox[temp[3]]
			temp[3] = sbox[k]
		}
		for i := 0; i < 4; i++ {
			w[bytesN] = w[bytesN-16] ^ temp[i]
			bytesN++
		}
	}
}

func encryptBlock(in []u8, out []u8, w []u8) {
	var s [16]u8
	copy(s[:], in[0:16])
	addRoundKey(s[:], w[0:16])
	for r := 1; r <= 9; r++ {
		subBytes(s[:])
		shiftRows(s[:])
		mixColumns(s[:])
		addRoundKey(s[:], w[16*r:16*r+16])
	}
	subBytes(s[:])
	shiftRows(s[:])
	addRoundKey(s[:], w[160:176])
	copy(out[0:16], s[:])
}

func initTables() {
	if tablesReady {
		return
	}
	for i := 0; i < 256; i++ {
		x := sbox[i]
		te0[i*4+0], te0[i*4+1], te0[i*4+2], te0[i*4+3] = xtime(x), x, x, mul3(x)
		te1[i*4+0], te1[i*4+1], te1[i*4+2], te1[i*4+3] = mul3(x), xtime(x), x, x
		te2[i*4+0], te2[i*4+1], te2[i*4+2], te2[i*4+3] = x, mul3(x), xtime(x), x
		te3[i*4+0], te3[i*4+1], te3[i*4+2], te3[i*4+3] = x, x, mul3(x), xtime(x)
		finalTable[i*finalStride] = x
	}
	tablesReady = true
}

// go:noinline forces a real call boundary around every table read, standing
// in for C's volatile pointers which block the compiler from eliding or
// reordering the lookups that make the timing side channel observable.
//
//go:noinline
func ttableColumn(out []u8, a, b, c, d u8, rk []u8) {
	x0 := te0[int(a)*4:]
	x1 := te1[int(b)*4:]
	x2 := te2[int(c)*4:]
	x3 := te3[int(d)*4:]
	for i := 0; i < 4; i++ {
		out[i] = x0[i] ^ x1[i] ^ x2[i] ^ x3[i] ^ rk[i]
	}
}

//go:noinline
func ttableEncryptBlock(in []u8, out []u8, w []u8) {
	initTables()
	var s, t [16]u8
	copy(s[:], in[0:16])
	addRoundKey(s[:], w[0:16])
	for r := 1; r <= 9; r++ {
		rk := w[16*r : 16*r+16]
		ttableColumn(t[0:4], s[0], s[5], s[10], s[15], rk[0:4])
		ttableColumn(t[4:8], s[4], s[9], s[14], s[3], rk[4:8])
		ttableColumn(t[8:12], s[8], s[13], s[2], s[7], rk[8:12])
		ttableColumn(t[12:16], s[12], s[1], s[6], s[11], rk[12:16])
		copy(s[:], t[:])
	}
	rk := w[160:176]
	for i := 0; i < 16; i++ {
		out[i] = finalTable[int(s[shiftRowsPerm[i]])*finalStride] ^ rk[i]
	}
}

//go:noinline
func disturbCache() {
	if evictBuf == nil || evictBufSize < evictSize {
		buf := make([]u8, evictSize)
		for i := range buf {
			buf[i] = u8(i)
		}
		evictBuf = buf
		evictBufSize = evictSize
	}
	acc := timingSink
	for i := 0; i < evictSize; i += evictStride {
		acc ^= evictBuf[i]
	}
	timingSink = acc
}

func invertLastRoundKey(last []u8, raw []u8) {
	w := make([]u8, aesExpanded)
	copy(w[160:176], last[0:16])
	for round := 10; round >= 1; round-- {
		prev := w[16*(round-1) : 16*(round-1)+16]
		cur := w[16*round : 16*round+16]
		for i := 12; i >= 4; i -= 4 {
			for b := 0; b < 4; b++ {
				prev[i+b] = cur[i+b] ^ cur[i-4+b]
			}
		}
		temp := [4]u8{prev[13], prev[14], prev[15], prev[12]}
		temp[0] = sbox[temp[0]] ^ rcon[round-1]
		temp[1] = sbox[temp[1]]
		temp[2] = sbox[temp[2]]
		temp[3] = sbox[temp[3]]
		for b := 0; b < 4; b++ {
			prev[b] = cur[b] ^ temp[b]
		}
	}
	copy(raw[0:16], w[0:16])
}

func randomBytes(buf []u8) {
	if _, err := crand.Read(buf); err != nil {
		fmt.Fprintln(os.Stderr, "random:", err)
		os.Exit(1)
	}
}

// readFileExact mirrors C's fread(buf, 1, len, f): reads exactly len(buf)
// bytes and only errors if the file is shorter; longer files are fine.
func readFileExact(path string, buf []u8) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = io.ReadFull(f, buf)
	return err
}

func writeFileExact(path string, buf []u8) error {
	return os.WriteFile(path, buf, 0o644)
}

func initConsole() {
	fi, err := os.Stdout.Stat()
	useColor = err == nil && fi.Mode()&os.ModeCharDevice != 0 && os.Getenv("NO_COLOR") == ""
	if useColor {
		clrReset = "\033[0m"
		clrTitle = "\033[1;36m"
		clrLabel = "\033[1m"
		clrOk = "\033[1;32m"
		clrWarn = "\033[1;33m"
	}
}

func cleanLabel(label string) string {
	n := len(label)
	for n > 0 && (label[n-1] == '=' || label[n-1] == ':') {
		n--
	}
	if n > 63 {
		n = 63
	}
	return label[:n]
}

func printFieldPrefix(label string) {
	fmt.Printf("  %s%-24s%s : ", clrLabel, cleanLabel(label), clrReset)
}

func printHex(label string, x []u8) {
	printFieldPrefix(label)
	for _, b := range x {
		fmt.Printf("%02x", b)
	}
	fmt.Println()
}

func printStep(title string) {
	fmt.Printf("\n%s============================================================%s\n", clrTitle, clrReset)
	fmt.Printf("%s%s%s\n", clrTitle, title, clrReset)
	fmt.Printf("%s============================================================%s\n", clrTitle, clrReset)
}

func printNote(text string) {
	fmt.Printf("  %s\n", text)
}

func printFieldStr(label, value string) {
	printFieldPrefix(label)
	fmt.Println(value)
}

func printFieldU32(label string, value u32) {
	printFieldPrefix(label)
	fmt.Printf("%d\n", value)
}

func printFieldU64(label string, value u64) {
	printFieldPrefix(label)
	fmt.Printf("%d\n", value)
}

func printFieldDouble(label string, value float64) {
	printFieldPrefix(label)
	fmt.Printf("%.3f\n", value)
}

func printProgress(label string, done, total u32) {
	const width = 28
	filled := 0
	if total != 0 {
		filled = int((u64(done) * width) / u64(total))
	}
	if filled > width {
		filled = width
	}
	printFieldPrefix(label)
	fmt.Print("[")
	for i := 0; i < width; i++ {
		if i < filled {
			fmt.Print("#")
		} else {
			fmt.Print(".")
		}
	}
	fmt.Printf("] %d/%d", done, total)
	if total != 0 {
		fmt.Printf(" (%d%%)", (u64(done)*100)/u64(total))
	}
	fmt.Println()
}

func printSamplePreview(s *sampleT) {
	printHex("first_plaintext=", s.P[:])
	printHex("first_ciphertext=", s.C[:])
	printFieldU64("first_timing", s.T)
}

func printOffsets(off []u8) {
	printFieldPrefix("round10 offsets")
	for i := 0; i < 16; i++ {
		if i > 0 {
			fmt.Print(" ")
		}
		fmt.Printf("%02x", off[i])
	}
	fmt.Println()
}

func modeName(mode u32) string {
	switch mode {
	case modeSynthetic:
		return "synthetic final-round cache-collision leakage"
	case modeReal:
		return "real measured encryption time"
	}
	return "unknown"
}

func finalRoundCollisions(c []u8, last []u8) int {
	collisions := 0
	for i := 0; i < 16; i++ {
		xi := invsbox[c[i]^last[i]]
		for j := i + 1; j < 16; j++ {
			xj := invsbox[c[j]^last[j]]
			if xi == xj {
				collisions++
			}
		}
	}
	return collisions
}

func syntheticTime(c []u8, last []u8) u64 {
	collisions := finalRoundCollisions(c, last)
	return u64(int64(100000) - 500*int64(collisions) + int64(mrand.Intn(61)) - 30)
}

func realTimeEncrypt(p []u8, c []u8, w []u8, repeats u32) u64 {
	var total u64
	for r := u32(0); r < repeats; r++ {
		disturbCache()
		start := time.Now()
		ttableEncryptBlock(p, c, w)
		acc := timingSink
		for i := 0; i < 16; i++ {
			acc ^= c[i]
		}
		timingSink = acc
		total += u64(time.Since(start).Nanoseconds())
	}
	return total
}

func argStr(args []string, idx int, def string) string {
	if len(args) > idx {
		return args[idx]
	}
	return def
}

// parseU32Lenient mirrors strtoul's tolerant behavior (fall back to 0 on a
// malformed number) rather than strconv's strict all-or-nothing parsing.
func parseU32Lenient(s string) u32 {
	v, err := strconv.ParseUint(s, 0, 32)
	if err != nil {
		return 0
	}
	return u32(v)
}

func cmdKeygen(args []string) int {
	out := argStr(args, 2, "key.bin")
	var key [aesBlock]u8
	printStep("Key generation")
	printNote("Generating one random AES-128 key from /dev/urandom.")
	printNote("AES-128 keys are 16 bytes long.")
	randomBytes(key[:])
	if err := writeFileExact(out, key[:]); err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", out, err)
		return 1
	}
	printHex("key=", key[:])
	printFieldStr("wrote key file", out)
	return 0
}

func cmdCollect(args []string) int {
	keyfile := argStr(args, 2, "key.bin")
	out := argStr(args, 3, "samples.bin")
	count := u32(1 << 18)
	if len(args) > 4 {
		count = parseU32Lenient(args[4])
	}
	realMode := args[1] == "collect-real"
	mode := modeSynthetic
	if realMode {
		mode = modeReal
	}
	repeats := u32(1)

	for i := 5; i < len(args); i++ {
		switch args[i] {
		case "-real", "--real":
			fmt.Fprintln(os.Stderr, "error: -real was removed; use the collect-real command instead.")
			return 100
		case "-demo-leak", "--demo-leak":
			fmt.Fprintln(os.Stderr, "error: -demo-leak was removed; this lab now keeps measured timing pure.")
			return 100
		case "-synthetic", "--synthetic":
			fmt.Fprintln(os.Stderr, "error: -synthetic was removed; use the collect command instead.")
			return 100
		case "-repeat", "--repeat":
			if i+1 >= len(args) {
				fmt.Fprintf(os.Stderr, "error: unknown collection option: %s\n", args[i])
				return 100
			}
			if !realMode {
				fmt.Fprintln(os.Stderr, "error: -repeat only applies to collect-real.")
				return 100
			}
			i++
			repeats = parseU32Lenient(args[i])
			if repeats == 0 {
				repeats = 1
			}
		case "-evict-kb", "--evict-kb":
			if i+1 >= len(args) {
				fmt.Fprintf(os.Stderr, "error: unknown collection option: %s\n", args[i])
				return 100
			}
			if !realMode {
				fmt.Fprintln(os.Stderr, "error: -evict-kb only applies to collect-real.")
				return 100
			}
			i++
			kb := parseU32Lenient(args[i])
			if kb > 0 {
				evictSize = int(kb) * 1024
			}
		default:
			fmt.Fprintf(os.Stderr, "error: unknown collection option: %s\n", args[i])
			return 100
		}
	}
	if count == 0 || count > maxSamples {
		count = 1 << 18
	}

	printStep("Sample collection")
	printFieldStr("key file", keyfile)
	printFieldStr("output file", out)
	printFieldU32("requested samples", count)
	printFieldStr("timing mode", modeName(mode))
	if mode == modeReal {
		printFieldStr("target AES", "aligned T-table AES with separate final table")
		fmt.Printf("  %sNOTE%s real mode measures elapsed encryption time on this machine.\n", clrWarn, clrReset)
		printNote("Recovery may fail or need many more samples if the timing signal is weak.")
		printFieldU64("cache disturb bytes", u64(evictSize))
		printFieldU32("repeats per sample", repeats)
	}

	var key [aesBlock]u8
	w := make([]u8, aesExpanded)
	if err := readFileExact(keyfile, key[:]); err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", keyfile, err)
		return 1
	}
	printHex("loaded_key=", key[:])
	printNote("Expanding the raw key into 176 bytes of AES-128 round keys.")
	keyExpand(key[:], w)
	printHex("round10_key=", w[160:176])

	f, err := os.Create(out)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", out, err)
		return 1
	}
	defer f.Close()
	bw := bufio.NewWriter(f)

	var h sampleHeaderT
	h.Magic = magic
	h.Count = count
	h.Mode = mode
	randomBytes(h.VerifierP[:])
	encryptBlock(h.VerifierP[:], h.VerifierC[:], w)
	if err := binary.Write(bw, binary.LittleEndian, &h); err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", out, err)
		return 1
	}
	printNote("Writing a verifier pair into the sample file header.")
	printHex("verifier_plaintext=", h.VerifierP[:])
	printHex("verifier_ciphertext=", h.VerifierC[:])

	printNote("Generating plaintext/ciphertext/timing records.")
	var s sampleT
	var rec [40]u8
	for i := u32(0); i < count; i++ {
		randomBytes(s.P[:])
		if mode == modeReal {
			s.T = realTimeEncrypt(s.P[:], s.C[:], w, repeats)
		} else {
			encryptBlock(s.P[:], s.C[:], w)
			s.T = syntheticTime(s.C[:], w[160:176])
		}
		copy(rec[0:16], s.P[:])
		copy(rec[16:32], s.C[:])
		binary.LittleEndian.PutUint64(rec[32:40], s.T)
		bw.Write(rec[:])
		if i == 0 {
			printNote("First generated sample preview:")
			printSamplePreview(&s)
		}
		if count >= 8 && (i+1)%(count/4) == 0 {
			printProgress("collection", i+1, count)
		}
	}
	bw.Flush()
	printNote("Finished writing sample file.")
	printHex("key=", key[:])
	printFieldU32("samples", count)
	printFieldStr("out", out)
	return 0
}

func pairIndex(i, j int) int {
	k := 0
	for a := 0; a < 16; a++ {
		for b := a + 1; b < 16; b++ {
			if a == i && b == j {
				return k
			}
			k++
		}
	}
	return -1
}

func candidateCost(off []u8, mean *[pairs][256]float64) float64 {
	c := 0.0
	p := 0
	for i := 0; i < 16; i++ {
		for j := i + 1; j < 16; j++ {
			c += mean[p][off[i]^off[j]]
			p++
		}
	}
	return c
}

func optimizeOffsets(off []u8, mean *[pairs][256]float64) (float64, int) {
	bestCost := candidateCost(off, mean)
	changed := true
	iterations := 0
	for iter := 0; iter < 200 && changed; iter++ {
		changed = false
		iterations = iter + 1
		for b := 1; b < 16; b++ {
			bestv := off[b]
			local := bestCost
			for v := 0; v < 256; v++ {
				old := off[b]
				off[b] = u8(v)
				c := candidateCost(off, mean)
				off[b] = old
				if c < local {
					local = c
					bestv = u8(v)
				}
			}
			if bestv != off[b] {
				off[b] = bestv
				bestCost = local
				changed = true
			}
		}
	}
	return bestCost, iterations
}

// writeVerifiedCandidate returns 0 (no k0 verified, keep searching), 1
// (found and written), or 2 (found but the file write failed). cmdAttack
// must collapse 2 into exit code 1 -- exit code 2 is reserved solely for
// "no verified candidate found after all starts", a different condition.
func writeVerifiedCandidate(off []u8, h *sampleHeaderT, out string, score float64, startIndex, iterations int) int {
	for k0 := 0; k0 < 256; k0++ {
		var last, raw, check [16]u8
		w := make([]u8, aesExpanded)
		for i := 0; i < 16; i++ {
			last[i] = u8(k0) ^ off[i]
		}
		invertLastRoundKey(last[:], raw[:])
		keyExpand(raw[:], w)
		encryptBlock(h.VerifierP[:], check[:], w)
		if bytes.Equal(check[:], h.VerifierC[:]) {
			if err := writeFileExact(out, raw[:]); err != nil {
				fmt.Fprintf(os.Stderr, "%s: %v\n", out, err)
				return 2
			}
			printFieldU32("successful start", u32(startIndex))
			printFieldU32("start iterations", u32(iterations))
			printFieldPrefix("verified candidate k0")
			fmt.Printf("%02x\n", k0)
			printHex("recovered_key=", raw[:])
			printHex("round10_key=", last[:])
			printFieldU32("samples", h.Count)
			printFieldDouble("score", score)
			printFieldStr("out", out)
			fmt.Printf("  %sSUCCESS%s recovered key verified against the stored plaintext/ciphertext pair.\n", clrOk, clrReset)
			return 1
		}
	}
	return 0
}

func cmdAttack(args []string) int {
	samplesPath := argStr(args, 2, "samples.bin")
	out := argStr(args, 3, "recovered_key.bin")
	printStep("Final-round timing attack")
	printFieldStr("sample file", samplesPath)
	printFieldStr("recovered key out", out)

	f, err := os.Open(samplesPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", samplesPath, err)
		return 1
	}
	defer f.Close()

	var h sampleHeaderT
	if err := binary.Read(f, binary.LittleEndian, &h); err != nil || h.Magic != magic || h.Count == 0 {
		fmt.Fprintln(os.Stderr, "bad sample file")
		return 1
	}
	printFieldU32("sample count", h.Count)
	printFieldU32("sample mode", h.Mode)
	printFieldStr("timing mode", modeName(h.Mode))
	if h.Mode == modeReal {
		fmt.Printf("  %sNOTE%s real timing mode is experimental; recovery is not guaranteed.\n", clrWarn, clrReset)
	}
	printHex("verifier_plaintext=", h.VerifierP[:])
	printHex("verifier_ciphertext=", h.VerifierC[:])
	printNote("Building an average timing table for all 120 ciphertext-byte pairs.")
	printNote("For each pair (i,j), timings are grouped by delta = c[i] ^ c[j].")

	dataStart, err := f.Seek(0, io.SeekCurrent)
	if err != nil {
		fmt.Fprintf(os.Stderr, "fseek: %v\n", err)
		return 1
	}

	minTime := u64(math.MaxUint64)
	var rec [40]u8
	br := bufio.NewReader(f)
	for n := u32(0); n < h.Count; n++ {
		if _, err := io.ReadFull(br, rec[:]); err != nil {
			fmt.Fprintln(os.Stderr, "truncated samples")
			return 1
		}
		t := binary.LittleEndian.Uint64(rec[32:40])
		if t < minTime {
			minTime = t
		}
	}
	cutoff := minTime * 2
	if cutoff < minTime {
		cutoff = math.MaxUint64
	}
	printFieldU64("minimum timing", minTime)
	printFieldU64("outlier cutoff", cutoff)

	// bufio.Reader has no seek-invalidation: always seek the raw file and
	// build a fresh reader, never reuse one across a Seek.
	if _, err := f.Seek(dataStart, io.SeekStart); err != nil {
		fmt.Fprintf(os.Stderr, "fseek: %v\n", err)
		return 1
	}
	br = bufio.NewReader(f)

	var sum [pairs][256]float64
	var num [pairs][256]u32
	usedSamples := u32(0)
	ignoredSamples := u32(0)
	var s sampleT
	for n := u32(0); n < h.Count; n++ {
		if _, err := io.ReadFull(br, rec[:]); err != nil {
			fmt.Fprintln(os.Stderr, "truncated samples")
			return 1
		}
		copy(s.P[:], rec[0:16])
		copy(s.C[:], rec[16:32])
		s.T = binary.LittleEndian.Uint64(rec[32:40])
		if n == 0 {
			printNote("First sample read from file:")
			printSamplePreview(&s)
		}
		if s.T > cutoff {
			ignoredSamples++
			continue
		}
		usedSamples++
		p := 0
		for i := 0; i < 16; i++ {
			for j := i + 1; j < 16; j++ {
				d := s.C[i] ^ s.C[j]
				sum[p][d] += float64(s.T)
				num[p][d]++
				p++
			}
		}
		if h.Count >= 8 && (n+1)%(h.Count/4) == 0 {
			printProgress("analysis read", n+1, h.Count)
		}
	}
	printFieldU32("used samples", usedSamples)
	printFieldU32("ignored samples", ignoredSamples)

	printNote("Converting timing sums into averages.")
	var mean [pairs][256]float64
	for p := 0; p < pairs; p++ {
		for d := 0; d < 256; d++ {
			if num[p][d] != 0 {
				mean[p][d] = sum[p][d] / float64(num[p][d])
			} else {
				mean[p][d] = 1e30
			}
		}
	}

	printNote("Finding the lowest-average delta for pairs involving byte 0.")
	fmt.Printf("\n  %-8s %-8s %-14s %-12s\n", "pair", "delta", "avg_time", "observations")
	fmt.Printf("  %-8s %-8s %-14s %-12s\n", "--------", "--------", "--------------", "------------")
	var bestDelta [16][16]u8
	pp := 0
	for i := 0; i < 16; i++ {
		for j := i + 1; j < 16; j++ {
			best := 0
			for d := 1; d < 256; d++ {
				if mean[pp][d] < mean[pp][best] {
					best = d
				}
			}
			bestDelta[i][j] = u8(best)
			bestDelta[j][i] = u8(best)
			pp++
		}
	}

	var initial [16]u8
	for j := 1; j < 16; j++ {
		p := pairIndex(0, j)
		best := bestDelta[0][j]
		initial[j] = best
		fmt.Printf("  (0,%2d)   %02x       %-14.3f %-12d\n", j, best, mean[p][best], num[p][best])
	}
	printOffsets(initial[:])

	printNote("Refining key-byte offsets with multi-start local search.")
	fmt.Printf("\n  %-8s %-12s %-16s %-10s\n", "start", "kind", "score", "iterations")
	fmt.Printf("  %-8s %-12s %-16s %-10s\n", "--------", "------------", "----------------", "----------")

	var globalBest, off [16]u8
	copy(globalBest[:], initial[:])
	globalCost := 1e300
	startIndex := 0

	for start := 0; start < 81; start++ {
		kind := "random"
		for i := range off {
			off[i] = 0
		}
		if start == 0 {
			copy(off[:], initial[:])
			kind = "byte0"
		} else if start <= 16 {
			anchor := start - 1
			kind = "anchor"
			off[anchor] = bestDelta[0][anchor]
			for j := 1; j < 16; j++ {
				if j == anchor {
					continue
				}
				off[j] = off[anchor] ^ bestDelta[anchor][j]
			}
		} else {
			for j := 1; j < 16; j++ {
				off[j] = u8(mrand.Intn(256))
			}
		}

		cost, iterations := optimizeOffsets(off[:], &mean)
		fmt.Printf("  %-8d %-12s %-16.3f %-10d\n", startIndex, kind, cost, iterations)
		if cost < globalCost {
			globalCost = cost
			copy(globalBest[:], off[:])
		}
		ok := writeVerifiedCandidate(off[:], &h, out, cost, startIndex, iterations)
		if ok != 0 {
			if ok == 1 {
				return 0
			}
			return 1
		}
		startIndex++
	}

	printFieldDouble("best unverified score", globalCost)
	printOffsets(globalBest[:])

	fmt.Fprintln(os.Stderr, "no verified key candidate found")
	return 2
}

func cmdVerify(args []string) int {
	keyfile := argStr(args, 2, "recovered_key.bin")
	samplesPath := argStr(args, 3, "samples.bin")
	var key, check [16]u8
	w := make([]u8, aesExpanded)
	printStep("Recovered key verification")
	printFieldStr("candidate key file", keyfile)
	if err := readFileExact(keyfile, key[:]); err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", keyfile, err)
		return 1
	}
	printHex("candidate_key=", key[:])
	printFieldStr("sample file", samplesPath)
	f, err := os.Open(samplesPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", samplesPath, err)
		return 1
	}
	var h sampleHeaderT
	if err := binary.Read(f, binary.LittleEndian, &h); err != nil || h.Magic != magic {
		f.Close()
		fmt.Fprintln(os.Stderr, "bad sample file")
		return 1
	}
	f.Close()
	printHex("verifier_plaintext=", h.VerifierP[:])
	printHex("expected_ciphertext=", h.VerifierC[:])
	keyExpand(key[:], w)
	encryptBlock(h.VerifierP[:], check[:], w)
	printHex("computed_ciphertext=", check[:])
	if !bytes.Equal(check[:], h.VerifierC[:]) {
		fmt.Fprintln(os.Stderr, "verification failed")
		return 2
	}
	printHex("verified_key=", key[:])
	fmt.Printf("  %sSUCCESS%s candidate key reproduces the verifier ciphertext.\n", clrOk, clrReset)
	return 0
}

func cmdSelftest() int {
	printStep("Self-test")
	printNote("Checking AES-128 encryption against a known NIST test vector.")
	key := []u8{0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f}
	pt := []u8{0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff}
	want := []u8{0x69, 0xc4, 0xe0, 0xd8, 0x6a, 0x7b, 0x04, 0x30, 0xd8, 0xcd, 0xb7, 0x80, 0x70, 0xb4, 0xc5, 0x5a}
	w := make([]u8, aesExpanded)
	var got, raw [16]u8
	printHex("test_key=", key)
	printHex("test_plaintext=", pt)
	printHex("expected_ciphertext=", want)
	keyExpand(key, w)
	encryptBlock(pt, got[:], w)
	printHex("computed_ciphertext=", got[:])
	if !bytes.Equal(got[:], want) {
		printHex("got=", got[:])
		return 1
	}
	fmt.Printf("  %sOK%s AES encryption test passed.\n", clrOk, clrReset)
	ttableEncryptBlock(pt, got[:], w)
	printHex("ttable_ciphertext=", got[:])
	if !bytes.Equal(got[:], want) {
		return 3
	}
	fmt.Printf("  %sOK%s T-table AES target matches the known vector.\n", clrOk, clrReset)
	printNote("Checking that round 10 key can be reversed back to the original key.")
	invertLastRoundKey(w[160:176], raw[:])
	printHex("recovered_from_round10=", raw[:])
	if !bytes.Equal(raw[:], key) {
		return 2
	}
	fmt.Printf("  %sOK%s selftest=ok\n", clrOk, clrReset)
	return 0
}

func usage(argv0 string) {
	fmt.Fprintf(os.Stderr,
		"usage:\n"+
			"  %s selftest\n"+
			"  %s keygen [key.bin]\n"+
			"  %s collect [key.bin] [samples.bin] [count]\n"+
			"  %s collect-real [key.bin] [samples.bin] [count] [-repeat N] [-evict-kb KB]\n"+
			"  %s attack-final [samples.bin] [recovered_key.bin]\n"+
			"  %s verify [recovered_key.bin] [samples.bin]\n",
		argv0, argv0, argv0, argv0, argv0, argv0)
}

func run(args []string) int {
	initConsole()
	if len(args) < 2 {
		usage(args[0])
		return 100
	}
	switch args[1] {
	case "selftest":
		return cmdSelftest()
	case "keygen":
		return cmdKeygen(args)
	case "collect", "collect-real":
		return cmdCollect(args)
	case "attack-final":
		return cmdAttack(args)
	case "verify":
		return cmdVerify(args)
	}
	usage(args[0])
	return 100
}

func main() {
	os.Exit(run(os.Args))
}
