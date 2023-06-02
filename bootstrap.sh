#!/bin/bash

set -xe

rm -rf bootstrap
mkdir bootstrap

# Compile version 0
./compile-libc -c src/randy/main.randy -o out/randy -v

# Use version 0 to compile version 1
./out/randy -c src/randy/main.randy \
            -o bootstrap/randy1 \
            -I include \
            -ld -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc
#as -c bootstrap/randy1.s -o bootstrap/randy1.o
#ld -o bootstrap/randy1 bootstrap/randy1.o -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc

# Use version 1 to compile version 2
bootstrap/randy1 -c src/randy/main.randy \
                 -o bootstrap/randy2 \
                 -I include \
                 -ld -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc
#as -g3 -c bootstrap/randy2.s -o bootstrap/randy2.o
#ld -o bootstrap/randy2 bootstrap/randy2.o -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc

if [[ -f "bin/randy.bak" ]]; then
    cp bin/randy.bak bin/randy.bak2
fi

if [[ -f "bin/randy" ]]; then
    cp bin/randy bin/randy.bak
fi

cp bootstrap/randy2 bin/randy
