CC ?= clang
CFLAGS ?= -O3 -std=c11 -Wall -Wextra -pedantic
LDFLAGS ?=

all: aes_lab

aes_lab: src/aes_lab.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

test: aes_lab
	./aes_lab selftest
	./tests/test_collect_eta.sh

clean: clean-c clean-go clean-python clean-misc

clean-c:
	rm -f aes_lab *.bin

clean-go:
	rm -f go/aes_lab_go go/aes go/*.bin

clean-python:
	find python -type d -name '__pycache__' -prune -exec rm -rf {} +
	find python -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
	rm -rf .pytest_cache

clean-misc:
	rm -f .DS_Store go/.DS_Store python/.DS_Store

.PHONY: all test clean clean-c clean-go clean-python clean-misc
