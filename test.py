import subprocess
import os
import pathlib
import sys
import difflib

def record(path_to_file):
    # create out directory if it doesn't exist
    if not os.path.exists('out/'):
        os.mkdir('out/')
    # create test directory if it doesn't exist
    if not os.path.exists('test/'):
        os.mkdir('test/')
    # compile the randy file and create executable
    no_ext = os.path.splitext(os.path.basename(path_to_file))[0]
    subprocess.run(['./compile-libc', '-c', path_to_file, '-o', f'out/{no_ext}'])
    # run the executable and record output to file
    with open(f'test/{no_ext}.output', 'wb') as output_file:
        subprocess.run([f'out/{no_ext}'], stdout=output_file)

def run1(output_file):
    # create out directory if it doesn't exist
    if not os.path.exists('out/'):
        os.mkdir('out/')
    no_ext = pathlib.Path(output_file).stem
    randy_file = f"examples/{no_ext}.randy"
    # compile the randy file and create executable
    subprocess.run(['./compile-libc', '-c', randy_file, '-o', f'out/{no_ext}'])
    # run the executable and capture output into a string
    with open(f'test/{no_ext}.output', 'rb') as expected_output_file:
        expected_output = expected_output_file.read().decode('utf-8')
    process = subprocess.Popen([f'out/{no_ext}'], stdout=subprocess.PIPE)
    generated_output, _ = process.communicate()
    generated_output = generated_output.decode('utf-8')
    # display any differences between expected and generated output
    diff = list(difflib.unified_diff(expected_output.splitlines(), generated_output.splitlines(), lineterm=''))
    if len(diff) == 0:
        print(f"{randy_file}: passed")
    else:
        print(f"{randy_file}: failed")
        print("\n".join(diff))

def run_all():
    # create test directory if it doesn't exist
    if not os.path.exists('test/'):
        os.mkdir('test/')
    for output_file in os.listdir('test/'):
        if output_file.endswith('.output'):
            run1(output_file)

def usage():
    print('Usage: python script.py [record/run] [.randy file / No argument needed]')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage()
        exit(1)
    elif sys.argv[1] == 'record':
        if len(sys.argv) < 3:
            usage()
            exit(1)
        record(sys.argv[2])
    elif sys.argv[1] == 'run':
        if len(sys.argv) < 3:
            run_all()
        else:
            run1(sys.argv[2])
    else:
        print('Invalid command. Use "record" or "run"')
