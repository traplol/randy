import subprocess
import os
import pathlib
import sys
import difflib
import shlex
import threading
from collections import defaultdict

# Check if the terminal supports ANSI codes
supports_color = sys.stdout.isatty() and (os.name != "nt" or
                                          ("ANSICON" in os.environ and bool(os.environ["ANSICON"])))
if supports_color:
    FAILED = "\033[2K\033[1;91m[FAILED]\033[0m"
    PASSED = "\033[2K\033[1;92m[PASSED]\033[0m"
    WARN = "\033[2K\033[1;93m[WARN]\033[0m"
    RUN = "\033[1;93m[RUN]\033[0m"
else:
    FAILED = "[FAILED]"
    PASSED = "[PASSED]"
    WARN = "[WARN]"

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
        #print(f"removed file: {resolved}")
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

def make_compile_command(randy_file, out_file, extra_flags):
    return ["bin/randy", "-c", randy_file, "-o", out_file, "-I", "include"] + \
        extra_flags + \
        ["-ld", "-dynamic-linker", "/home/max/workspace/musl-1.2.4/lib/libc.so", "-lc"]
    
def record(path_to_file):
    # create out directory if it doesn"t exist
    if not os.path.exists("out/"):
        os.mkdir("out/")
    # create test directory if it doesn"t exist
    if not os.path.exists("test/"):
        os.mkdir("test/")
    # compile the randy file and create executable
    no_ext = os.path.splitext(os.path.basename(path_to_file))[0]
    try_remove(f"out/{no_ext}.s")
    try_remove(f"out/{no_ext}.o")
    try_remove(f"out/{no_ext}")
    randy_file = f"test/{no_ext}.randy"
    opts = get_extra_flags(randy_file)
    subprocess.run(make_compile_command(randy_file, f"out/{no_ext}", opts["-compile"]))
    try:
        # run the executable and record output to file
        out_path = f"test/{no_ext}.output"
        with open(out_path, "wb") as output_file:
            subprocess.run([f"out/{no_ext}"] + opts["-test"], stdout=output_file)
        print(f"Recorded test: {color_path(out_path)}")
    except FileNotFoundError:
        print(f"{WARN}   {color_path(randy_file)}: did not compile.")

def run1(output_file, print_diff, just_one):
    passed = False
    # create out directory if it doesn"t exist
    if not os.path.exists("out/"):
        os.mkdir("out/")
    no_ext = pathlib.Path(output_file).stem
    randy_file = f"test/{no_ext}.randy"
    opts = get_extra_flags(randy_file)
    # compile the randy file and create executable
    try_remove(f"out/{no_ext}.s")
    try_remove(f"out/{no_ext}.o")
    try_remove(f"out/{no_ext}")
    proc = subprocess.run(make_compile_command(randy_file, f"out/{no_ext}", opts["-compile"]),
                          capture_output=not just_one)
    if proc.returncode < 0:
        print(f"\r{FAILED} {color_path(randy_file)} : compiler terminated with signal {proc.returncode}")
        return False
    if "-nocompile" in opts:
        if proc.returncode > 0:
            print(f"\r{PASSED} {color_path(randy_file)}")
            return True
        else:
            print(f"\r{FAILED} {color_path(randy_file)}")
            return False
    # run the executable and capture output into a string
    with open(f"test/{no_ext}.output", "rb") as expected_output_file:
        expected_output = expected_output_file.read().decode("utf-8")
    try:
        if sys.stdout.isatty():
            print(f"{RUN} {color_path(randy_file)}", end="\r")
        process = subprocess.Popen([f"out/{no_ext}"] + opts["-test"], stdout=subprocess.PIPE)
        generated_output, _ = process.communicate()
        generated_output = generated_output.decode("utf-8")
        if process.returncode < 0:
            print(f"{FAILED} {color_path(randy_file)} : test terminated with signal {process.returncode}")
            return False
            
        # display any differences between expected and generated output
        diff = list(difflib.unified_diff(expected_output.splitlines(), generated_output.splitlines(), lineterm=""))
        if len(diff) == 0:
            print(f"{PASSED} {color_path(randy_file)}")
            passed = True
        else:
            print(f"{FAILED} {color_path(randy_file)}")
            if print_diff:
                for line in diff:
                    print(color_diff_line(line))
    except FileNotFoundError:
        print(f"{WARN}   {color_path(randy_file)}: did not compile.")
    return passed

def run_all():
    # create test directory if it doesn"t exist
    if not os.path.exists("test/"):
        os.mkdir("test/")
    files = sorted(os.listdir("test/"))
    passed = 0
    tests = []
    for f in files:
        if f.endswith(".randy"):
            tests.append(f)
    for i, test in enumerate(tests):
        print(f"[{i+1}/{len(tests)}] ", end="")
        if run1(test, False, False):
            passed += 1
    print(f"[{passed}/{len(tests)}] tests passed.")

def usage():
    print("Usage: python script.py [record/run] [.randy file / No argument needed]")

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
        if len(sys.argv) < 3:
            run_all()
        else:
            run1(sys.argv[2], True, True)
    else:
        print("Invalid command. Use 'record' or 'run'")
