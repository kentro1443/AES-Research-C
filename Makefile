CC ?= clang
CFLAGS ?= -O3 -std=c11 -Wall -Wextra -pedantic
LDFLAGS ?=

all: aes_lab

aes_lab: src/aes_lab.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

test: aes_lab
	./aes_lab selftest

clean:
	rm -f aes_lab *.bin

.PHONY: all test clean
