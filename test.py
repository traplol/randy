import subprocess
import os
import pathlib
import sys
import difflib

import os

# Check if the terminal supports ANSI codes
supports_color = sys.stdout.isatty() and (os.name != "nt" or
                                          ("ANSICON" in os.environ and bool(os.environ["ANSICON"])))
if supports_color:
    PASSED = "\033[1;92m[PASSED]\033[0m"
    WARN = "\033[1;93m[WARN]\033[0m"
    FAILED = "\033[1;91m[FAILED]\033[0m"
else:
    PASSED = "[PASSED]"
    WARN = "[WARN]"
    FAILED = "[FAILED]"

def color_path(path):
    if not supports_color:
        return path
    return f"\033[1;96m{path}\033[0m"

def color_diff_line(line):
    if not supports_color:
        return line
    if len(line) == 0:
        return line
    if line[0] == "+":
        return f"\033[32m{line}\033[0m"
    if line[0] == "-":
        return f"\033[31m{line}\033[0m"
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
    subprocess.run(["./compile-libc", "-c", path_to_file, "-o", f"out/{no_ext}"])
    try:
        # run the executable and record output to file
        out_path = f"test/{no_ext}.output"
        with open(out_path, "wb") as output_file:
            subprocess.run([f"out/{no_ext}"], stdout=output_file)
        print(f"Recorded test: {color_path(out_path)}")
    except FileNotFoundError:
        print(f"{WARN}   {color_path(randy_file)}: did not compile.")

def run1(output_file, print_diff):
    # create out directory if it doesn"t exist
    if not os.path.exists("out/"):
        os.mkdir("out/")
    no_ext = pathlib.Path(output_file).stem
    randy_file = f"examples/{no_ext}.randy"
    # compile the randy file and create executable
    try_remove(f"out/{no_ext}.s")
    try_remove(f"out/{no_ext}.o")
    try_remove(f"out/{no_ext}")
    subprocess.run(["./compile-libc", "-c", randy_file, "-o", f"out/{no_ext}"])
    # run the executable and capture output into a string
    with open(f"test/{no_ext}.output", "rb") as expected_output_file:
        expected_output = expected_output_file.read().decode("utf-8")
    try:
        process = subprocess.Popen([f"out/{no_ext}"], stdout=subprocess.PIPE)
        generated_output, _ = process.communicate()
        generated_output = generated_output.decode("utf-8")
        # display any differences between expected and generated output
        diff = list(difflib.unified_diff(expected_output.splitlines(), generated_output.splitlines(), lineterm=""))
        if len(diff) == 0:
            print(f"{PASSED} {color_path(randy_file)}")
        else:
            print(f"{FAILED} {color_path(randy_file)}")
            if print_diff:
                for line in diff:
                    print(color_diff_line(line))
                #print("\n".join(diff))
    except FileNotFoundError:
        print(f"{WARN}   {color_path(randy_file)}: did not compile.")

def run_all():
    # create test directory if it doesn"t exist
    if not os.path.exists("test/"):
        os.mkdir("test/")
    for output_file in os.listdir("test/"):
        if output_file.endswith(".output"):
            run1(output_file, False)

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
            run1(sys.argv[2], True)
    else:
        print("Invalid command. Use 'record' or 'run'")
