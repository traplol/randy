#!/bin/bash

set -xe

MUSL="${MUSL_LIBC:-/tmp/musl-install/lib/libc.so}"

if [[ ! -f "$MUSL" ]]; then
    echo "ERROR: musl libc not found at $MUSL"
    echo "Set MUSL_LIBC to the path of musl's libc.so, or install musl at /tmp/musl-install/"
    exit 1
fi

run() { "$MUSL" "$@"; }

rm -rf bootstrap
mkdir bootstrap

# Compile version 0
run bin/randy -c src/randy/main.randy \
    -o bootstrap/randy0 \
    -I include \
    -v -g \
    -ld -dynamic-linker "$MUSL" -lc

# Use version 0 to compile version 1
run bootstrap/randy0 -c src/randy/main.randy \
    -o bootstrap/randy1 \
    -I include \
    -v \
    -ld -dynamic-linker "$MUSL" -lc

# Use version 1 to compile version 2
run bootstrap/randy1 -c src/randy/main.randy \
    -o bootstrap/randy2 \
    -I include \
    -v \
    -ld -dynamic-linker "$MUSL" -lc

cmp bootstrap/randy1.s bootstrap/randy2.s || exit 1

if [[ -f "bin/randy.bak" ]]; then
    cp bin/randy.bak bin/randy.bak2
fi

if [[ -f "bin/randy" ]]; then
    cp bin/randy bin/randy.bak
fi

# If cmp succeeds then we can, in theory, close the bootstrap loop
cp bootstrap/randy2 bin/randy
echo "BOOTSTRAP SUCCESS"
