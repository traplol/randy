# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Randy is a self-hosting compiled programming language targeting x86_64 Linux. The compiler is written in Randy itself and emits x86_64 assembly, linked against musl libc. The project status is archived/experimental.

## Build & Run

The compiler binary is at `bin/randy`. It requires musl libc as the dynamic linker. Since the binary's ELF interpreter is hardcoded to a path that may not exist, invoke it via musl directly:

```bash
# Run the compiler
/tmp/musl-install/lib/libc.so bin/randy -c <file>.randy -o <output> -I include \
  -ld -dynamic-linker /tmp/musl-install/lib/libc.so -lc
```

If musl is not installed at `/tmp/musl-install/`, build it from source:
```bash
cd /tmp && curl -sL https://musl.libc.org/releases/musl-1.2.4.tar.gz | tar xz
cd musl-1.2.4 && ./configure --prefix=/tmp/musl-install && make -j$(nproc) && make install
```

### Bootstrap (rebuild the compiler with itself)

```bash
./bootstrap.sh
```

This runs a 3-stage bootstrap: bin/randy compiles the compiler source to randy0, randy0 compiles to randy1, randy1 compiles to randy2, then verifies randy1.s and randy2.s are identical (fixed-point proof). On success, randy2 becomes the new bin/randy. **Note:** bootstrap.sh has a hardcoded musl path that may need updating.

### Compiler CLI Flags

`-c file` compile, `-o path` output, `-I path` include path, `-g` debug info, `-v/-vv/-vvv` verbosity, `-ir` print IR (no compile), `-ast` print AST (no compile), `-experimental` enable experimental features, `-ld flags...` pass remaining args to linker.

## Tests

There are two levels of testing:

### Unit/feature tests

```bash
python3 test.py run              # Run all 41 tests
python3 test.py run test_hello   # Run a single test (shows diff on failure)
python3 test.py record test_foo  # Record expected output for a new/updated test
```

Test files live in `test/` as `.randy` source with matching `.output` files for expected output. Compiled artifacts go to `out/`.

Test files can specify flags via header comments:
- `// -compile <flags>` — extra compiler flags
- `// -test <args>` — arguments passed to the test executable
- `// -nocompile` — test expects compilation to fail

The test runner uses the `MUSL_LIBC` env var (default: `/tmp/musl-install/lib/libc.so`).

### Bootstrap self-hosting verification

After changes to the compiler itself, run the bootstrap to verify correctness:

```bash
./bootstrap.sh
```

This is the definitive test for compiler changes. It compiles the compiler three times (randy→randy0→randy1→randy2) and verifies that randy1.s and randy2.s produce identical assembly. If the assembly diverges, the compiler is generating inconsistent output and the change is broken. A successful bootstrap proves the compiler can correctly compile itself — the fixed-point check catches codegen bugs that unit tests may miss.

## Compilation Pipeline

Defined in `src/randy/main.randy`:

1. **Lex** — tokenize source, resolve `#include` directives
2. **Parse** — recursive descent parser produces AST
3. **Instantiate generics** — monomorphize generic types into concrete types
4. **Calculate struct sizes** — layout and alignment
5. **Reachability analysis** — find all code reachable from `main`
6. **Type inference** — two-phase: shallow pass for declarations, deep pass for reachable expressions
7. **Type checking** — semantic validation of reachable code only
8. **AST rewriting** — inlining, defer generation
9. **IR lowering** — AST to stack-based intermediate representation
10. **Code generation** — IR to x86_64 assembly (System V AMD64 ABI)
11. Assembly and linking via GNU `as` and `ld`

## Architecture

The compiler source is in `src/randy/` (18 files, ~10.8k lines). Key modules by pipeline stage:

- **Frontend:** `lexer.randy` → `token.randy` / `token_stream.randy` → `parsing.randy` → `ast.randy`
- **Type system:** `type_table.randy` (type registry + generics), `type_infer.randy`, `type_checker.randy`, `symbol_table.randy`
- **Middle-end:** `compile_order.randy` (reachability), `comptime_eval.randy` (constant folding/static_assert), `ir_context.randy` (IR instructions), `ir_v2.randy` (experimental alternative)
- **Backend:** `x86_64_backend.randy` (assembly emission), `compiler_context.randy` (output accumulation)
- **Utilities:** `utils.randy`, `bits.randy`

The standard library is in `include/std/` (15 files, ~1.8k lines): generic data structures (`Vector[T]`, `Hashmap[K,V,KHash,KCompare]`, `Set`, `Map`, `Queue`, `List`), memory management (`memory.randy`, `arena.randy`), system interfaces (`syscall.randy`, `file.randy`, `process.randy`), and core types (`core.randy`, `string.randy`).

## Language Syntax Notes

- Functions: `def name param1 Type, param2 Type -> ReturnType in ... end`
- Structs: `struct Name field1 Type, field2 Type end`
- Methods: `def Type::method self& Type -> Ret in ... end` (called as `obj.method()`)
- Generics: `struct Vector[T] ... end` — monomorphized at compile time
- Pointer ops: `u8@`/`u64@` for typed reads, `u8!`/`u64!` for typed writes
- References: `&Type` suffix, auto-dereferencing on `.` access
- Inline asm: `asm name in "..." end`
