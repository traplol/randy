import subprocess
import os
import pathlib
import sys
import difflib
import shlex
import time
import fnmatch
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Check if the terminal supports ANSI codes
supports_color = sys.stdout.isatty() and (os.name != "nt" or
                                          ("ANSICON" in os.environ and bool(os.environ["ANSICON"])))
if supports_color:
    FAILED = "\033[1;91m[FAILED]\033[0m"
    PASSED = "\033[1;92m[PASSED]\033[0m"
    WARN = "\033[1;93m[WARN]\033[0m"
    SKIPPED = "\033[1;90m[SKIPPED]\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
else:
    FAILED = "[FAILED]"
    PASSED = "[PASSED]"
    WARN = "[WARN]"
    SKIPPED = "[SKIPPED]"
    BOLD = ""
    DIM = ""
    RESET = ""

def color_path(path):
    if not supports_color:
        return path
    return f"\033[1;96m{path}\033[0m"

def color_diff_line(line):
    if not supports_color:
        return line
    if len(line) == 0:
        return line
    if line[0] == "-":
        return f"\033[31m{line}\033[0m"
    if line[0] == "+":
        return f"\033[32m{line}\033[0m"
    if line.startswith("@@"):
        return f"\033[33m{line}\033[0m"
    return line

def format_duration(seconds):
    if seconds >= 1.0:
        return f"{seconds:.1f}s"
    return f"{seconds * 1000:.0f}ms"

ROOT = str(pathlib.Path(__file__).resolve().parent)
def try_remove(file_path):
    resolved = str(pathlib.Path(file_path).resolve())
    if os.path.commonpath([ROOT, resolved]) != ROOT:
        print(f"not removing file outside local directory:")
        print(f"given:    {file_path}")
        print(f"resolved: {resolved}")
        return False
    try:
        os.remove(resolved)
        return True
    except FileNotFoundError:
        return False
    except IsADirectoryError:
        return False

def get_extra_flags(path):
    comment_lines = []
    with open(path, "r") as f:
        while True:
            line = f.readline()
            if line.startswith("//"):
                comment_lines.append(line[2:].strip())
            else:
                break
    opts = defaultdict(list)
    for line in comment_lines:
        flags = shlex.split(line)
        if len(flags) > 0 and flags[0][0] == "-":
            opts[flags[0]] = flags[1:]
    return opts

MUSL_LIBC = os.environ.get("MUSL_LIBC", "/tmp/musl-install/lib/libc.so")

def make_compile_command(randy_file, out_file, extra_flags):
    return [MUSL_LIBC, "bin/randy", "-c", randy_file, "-o", out_file, "-I", "include"] + \
        extra_flags + \
        ["-ld", "-dynamic-linker", MUSL_LIBC, "-lc"]

def record(path_to_file):
    if not os.path.exists("out/"):
        os.mkdir("out/")
    if not os.path.exists("test/"):
        os.mkdir("test/")
    no_ext = os.path.splitext(os.path.basename(path_to_file))[0]
    try_remove(f"out/{no_ext}.s")
    try_remove(f"out/{no_ext}.o")
    try_remove(f"out/{no_ext}")
    randy_file = f"test/{no_ext}.randy"
    opts = get_extra_flags(randy_file)

    if "-nocompile" in opts:
        # For nocompile tests, compile and show the compiler output so the user
        # can write -expect lines based on it
        proc = subprocess.run(make_compile_command(randy_file, f"out/{no_ext}", opts["-compile"]),
                              capture_output=True)
        compiler_output = (proc.stdout or b"").decode("utf-8")
        if proc.returncode > 0:
            print(f"Compilation failed as expected. Compiler output:")
            print(compiler_output)
            print(f"Add {BOLD}// -expect \"substring\"{RESET} lines to {color_path(randy_file)} to match.")
        else:
            print(f"{WARN}   {color_path(randy_file)}: compiled successfully (expected failure).")
        return

    subprocess.run(make_compile_command(randy_file, f"out/{no_ext}", opts["-compile"]))
    try:
        out_path = f"test/{no_ext}.output"
        with open(out_path, "wb") as output_file:
            subprocess.run([f"out/{no_ext}"] + opts["-test"], stdout=output_file)
        print(f"Recorded test: {color_path(out_path)}")
    except FileNotFoundError:
        print(f"{WARN}   {color_path(randy_file)}: did not compile.")

class TestResult:
    def __init__(self, name, passed, duration, output_lines=None):
        self.name = name
        self.passed = passed
        self.duration = duration
        self.output_lines = output_lines or []

def run1(test_file, verbose=False):
    """Run a single test. Returns a TestResult. Thread-safe (no shared state)."""
    t0 = time.monotonic()
    no_ext = pathlib.Path(test_file).stem
    randy_file = f"test/{no_ext}.randy"
    opts = get_extra_flags(randy_file)
    output_lines = []

    if not os.path.exists("out/"):
        os.makedirs("out/", exist_ok=True)

    try_remove(f"out/{no_ext}.s")
    try_remove(f"out/{no_ext}.o")
    try_remove(f"out/{no_ext}")

    proc = subprocess.run(make_compile_command(randy_file, f"out/{no_ext}", opts["-compile"]),
                          capture_output=True)

    compiler_stdout = (proc.stdout or b"").decode("utf-8")
    compiler_stderr = (proc.stderr or b"").decode("utf-8")

    if proc.returncode < 0:
        duration = time.monotonic() - t0
        output_lines.append(f"Compiler terminated with signal {proc.returncode}")
        if compiler_stderr:
            output_lines.append(f"stderr: {compiler_stderr.rstrip()}")
        return TestResult(randy_file, False, duration, output_lines)

    if "-nocompile" in opts:
        duration = time.monotonic() - t0
        if proc.returncode <= 0:
            output_lines.append("Expected compilation to fail, but it succeeded.")
            return TestResult(randy_file, False, duration, output_lines)
        # Check -expect strings
        for expected in opts["-expect"]:
            if expected not in compiler_stdout:
                output_lines.append(f"Expected output to contain: {expected}")
                output_lines.append(f"Actual output: {compiler_stdout.rstrip()}")
                return TestResult(randy_file, False, duration, output_lines)
        return TestResult(randy_file, True, duration)

    if proc.returncode != 0:
        duration = time.monotonic() - t0
        output_lines.append("Compilation failed.")
        if verbose and compiler_stdout:
            output_lines.append(f"stdout: {compiler_stdout.rstrip()}")
        if verbose and compiler_stderr:
            output_lines.append(f"stderr: {compiler_stderr.rstrip()}")
        return TestResult(randy_file, False, duration, output_lines)

    # Run the compiled executable
    out_path = f"test/{no_ext}.output"
    if not os.path.exists(out_path):
        duration = time.monotonic() - t0
        output_lines.append(f"Missing expected output file: {out_path}")
        return TestResult(randy_file, False, duration, output_lines)

    with open(out_path, "rb") as f:
        expected_output = f.read().decode("utf-8")

    try:
        process = subprocess.Popen([f"out/{no_ext}"] + opts["-test"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        timeout = int(opts["-timeout"][0]) if opts["-timeout"] else 30
        generated_output, test_stderr = process.communicate(timeout=timeout)
        generated_output = generated_output.decode("utf-8")
        test_stderr = test_stderr.decode("utf-8")
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        duration = time.monotonic() - t0
        output_lines.append(f"Test timed out after {timeout} seconds.")
        return TestResult(randy_file, False, duration, output_lines)
    except FileNotFoundError:
        duration = time.monotonic() - t0
        output_lines.append("Compiled binary not found.")
        return TestResult(randy_file, False, duration, output_lines)

    duration = time.monotonic() - t0

    if process.returncode < 0:
        output_lines.append(f"Test terminated with signal {process.returncode}")
        if test_stderr:
            output_lines.append(f"stderr: {test_stderr.rstrip()}")
        return TestResult(randy_file, False, duration, output_lines)

    diff = list(difflib.unified_diff(expected_output.splitlines(), generated_output.splitlines(), lineterm=""))
    if len(diff) == 0:
        return TestResult(randy_file, True, duration)
    else:
        for line in diff:
            output_lines.append(line)
        return TestResult(randy_file, False, duration, output_lines)

def collect_tests(patterns=None):
    """Collect test files matching the given patterns. If no patterns, return all."""
    if not os.path.exists("test/"):
        return []
    all_tests = sorted(f for f in os.listdir("test/") if f.endswith(".randy"))
    if not patterns:
        return all_tests
    matched = []
    for test in all_tests:
        name = pathlib.Path(test).stem
        for pat in patterns:
            # Match against stem (no extension) — support glob patterns
            if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(name, f"test_{pat}") or \
               fnmatch.fnmatch(name, f"*{pat}*"):
                matched.append(test)
                break
    return matched

def run_tests(patterns=None, jobs=None, verbose=False, filter_kind=None):
    tests = collect_tests(patterns)
    if not tests:
        print("No tests found.")
        return

    # Filter by kind
    if filter_kind:
        filtered = []
        for t in tests:
            randy_file = f"test/{t}"
            opts = get_extra_flags(randy_file)
            is_nocompile = "-nocompile" in opts
            if filter_kind == "nocompile" and is_nocompile:
                filtered.append(t)
            elif filter_kind == "compile" and not is_nocompile:
                filtered.append(t)
        tests = filtered
        if not tests:
            print(f"No {filter_kind} tests found.")
            return

    total = len(tests)
    if jobs is None:
        jobs = min(os.cpu_count() or 1, total)

    t_start = time.monotonic()
    results = []
    passed_count = 0
    failed_count = 0
    failed_tests = []

    if jobs == 1 or total == 1:
        # Sequential mode — show progress inline
        for i, test in enumerate(tests):
            if sys.stdout.isatty() and not verbose:
                print(f"\033[2K[{i+1}/{total}] running {test}...", end="\r")
            result = run1(test, verbose)
            results.append(result)
            tag = PASSED if result.passed else FAILED
            timing = f" {DIM}({format_duration(result.duration)}){RESET}"
            if result.passed:
                passed_count += 1
                print(f"\033[2K[{i+1}/{total}] {tag} {color_path(result.name)}{timing}")
            else:
                failed_count += 1
                failed_tests.append(result)
                print(f"\033[2K[{i+1}/{total}] {tag} {color_path(result.name)}{timing}")
                if verbose:
                    for line in result.output_lines:
                        print(f"  {line}")
    else:
        # Parallel mode
        print(f"Running {total} tests with {jobs} workers...")
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(run1, test, verbose): test for test in tests}
            done = 0
            for future in as_completed(futures):
                done += 1
                result = future.result()
                results.append(result)
                tag = PASSED if result.passed else FAILED
                timing = f" {DIM}({format_duration(result.duration)}){RESET}"
                if result.passed:
                    passed_count += 1
                    print(f"\033[2K[{done}/{total}] {tag} {color_path(result.name)}{timing}")
                else:
                    failed_count += 1
                    failed_tests.append(result)
                    print(f"\033[2K[{done}/{total}] {tag} {color_path(result.name)}{timing}")
                    if verbose:
                        for line in result.output_lines:
                            print(f"  {line}")

    total_time = time.monotonic() - t_start

    # Summary
    print()
    if failed_tests:
        print(f"{BOLD}Failures:{RESET}")
        for result in sorted(failed_tests, key=lambda r: r.name):
            print(f"  {FAILED} {color_path(result.name)}")
            for line in result.output_lines:
                print(f"    {color_diff_line(line)}")
        print()

    summary = f"{passed_count} passed"
    if failed_count > 0:
        summary += f", {failed_count} failed"
    summary += f" ({total} total) in {format_duration(total_time)}"
    if failed_count == 0:
        print(f"{PASSED} {summary}")
    else:
        print(f"{FAILED} {summary}")

    return failed_count == 0

def usage():
    print(f"""Usage: python3 test.py <command> [options] [patterns...]

Commands:
  run [patterns...]     Run tests (all, or matching patterns)
  record <name>         Record expected output for a test

Options:
  -j N                  Run N tests in parallel (default: auto)
  -j1                   Run tests sequentially
  -v, --verbose         Show failure details inline and compiler output
  --nocompile           Only run nocompile tests
  --compile             Only run compile+run tests

Patterns:
  test.py run                     Run all tests
  test.py run test_hello          Run test_hello
  test.py run hello               Run tests matching *hello*
  test.py run 'error_*'           Run tests matching error_*
  test.py run --nocompile         Run only nocompile tests
  test.py run -v error            Run error tests with verbose output""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        exit(1)
    elif sys.argv[1] == "record":
        if len(sys.argv) < 3:
            usage()
            exit(1)
        record(sys.argv[2])
    elif sys.argv[1] == "run":
        args = sys.argv[2:]
        jobs = None
        verbose = False
        filter_kind = None
        patterns = []
        i = 0
        while i < len(args):
            if args[i] == "-v" or args[i] == "--verbose":
                verbose = True
            elif args[i] == "-j" and i + 1 < len(args):
                i += 1
                jobs = int(args[i])
            elif args[i].startswith("-j") and len(args[i]) > 2:
                jobs = int(args[i][2:])
            elif args[i] == "--nocompile":
                filter_kind = "nocompile"
            elif args[i] == "--compile":
                filter_kind = "compile"
            else:
                patterns.append(args[i])
            i += 1
        success = run_tests(patterns or None, jobs, verbose, filter_kind)
        exit(0 if success else 1)
    else:
        print(f"Unknown command: {sys.argv[1]}")
        usage()
        exit(1)
