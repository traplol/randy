#!/bin/bash

set -xe

rm -rf bootstrap
mkdir bootstrap

# Compile version 0
./compile-libc -c src/randy/main.randy -o out/randy -v --ir-comments

# Use version 0 to compile version 1
./out/randy -c src/randy/main.randy -o bootstrap/randy1.s
as -c bootstrap/randy1.s -o bootstrap/randy1.o
ld -o bootstrap/randy1 bootstrap/randy1.o -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc

# Use version 1 to compile version 2
bootstrap/randy1 -c src/randy/main.randy -o bootstrap/randy2.s
as -g3 -c bootstrap/randy2.s -o bootstrap/randy2.o
ld -o bootstrap/randy2 bootstrap/randy2.o -dynamic-linker /home/max/workspace/musl-1.2.4/lib/libc.so -lc

