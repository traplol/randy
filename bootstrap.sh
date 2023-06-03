#!/bin/bash

set -xe

rm -rf bootstrap
mkdir bootstrap

# Compile version 0
bin/randy -c src/randy/main.randy \
          -o bootstrap/randy0 \
          -I include \
          -v \
          -ld -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc

# Use version 0 to compile version 1
bootstrap/randy0 -c src/randy/main.randy \
                 -o bootstrap/randy1 \
                 -I include \
                 -v \
                 -ld -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc

# Use version 1 to compile version 2
bootstrap/randy1 -c src/randy/main.randy \
                 -o bootstrap/randy2 \
                 -I include \
                 -v \
                 -ld -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc

cmp bootstrap/randy1.s bootstrap/randy2.s || exit 1

if [[ -f "bin/randy.bak" ]]; then
    cp bin/randy.bak bin/randy.bak2
fi

if [[ -f "bin/randy" ]]; then
    cp bin/randy bin/randy.bak
fi

# If cmp succeeds then we can, in theory, close the bootstrap loop
cp bootstrap/randy2 bin/randy
