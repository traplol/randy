# Open the unistd_64.h file
with open('/usr/include/x86_64-linux-gnu/asm/unistd_64.h') as f:
    # Read the file contents
    content = f.read()

# Find all lines that start with "#define __NR_", which indicate syscall definitions
lines = [line.strip() for line in content.split('\n') if line.startswith('#define __NR_')]

# Extract the syscall number and name from each line
syscalls = {}
for line in lines:
    _, name, num = line.split()
    num = int(num)
    name = name.replace('__NR_', '').lower()
    syscalls[num] = name

# Print the name and number of each syscall
for nr, name in sorted(syscalls.items()):
    print(f"const SYS_{name} = {nr};")
