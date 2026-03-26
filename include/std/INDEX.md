# include/std/
Standard library. Provides core types, generic data structures, memory management, and system interfaces.

## core.randy — fundamental types, libc externs, error handling, abort
```
extern puts, printf, fprintf, fflush, putchar, strerror
extern stdin, stdout, stderr
const true, false, NULL, sizeof_PTR
exit(code: int) / abort() / errno() -> int / _error(msg)
```

## memory.randy — libc memory allocation wrappers
```
extern malloc: (int -> ptr) / calloc: (int, int -> ptr) / free: (ptr -> void)
extern memcpy / memset / memmove: (ptr, ptr, int -> ptr)
```

## string.randy — `String` dynamic string type, cstr utilities
```
String::new(init) / new_from_cstr(cstr) / delete(self)
String::push(self, char) / pop(self) / back(self) -> char / get(self, idx) / set(self, idx, val)
String::append_string(self, string) / append_cstr(self, cstr) / append_int(self, n)
String::cstr(self) -> cstr / duplicate(self) -> String& / resize(self, new_cap) / reset(self)
string_eq(a, b) -> bool / cstr_eq(a, b) -> bool / cstr_len(cstr) -> int
```

## vector.randy — `Vector[T]` generic dynamic array (requires sizeof(T) == 8)
```
Vector[T]::new(init) / delete(self)
Vector[T]::push(self, val) / pop(self) / get(self, idx) -> T / set(self, idx, val)
Vector[T]::back(self) -> T / front(self) -> T / insert_front(self, val)
Vector[T]::resize(self, new_cap)
```

## queue.randy — `Queue[T]` generic FIFO queue
```
Queue[T]::new(init) / delete(self) / reset(self)
Queue[T]::enqueue(self, elem) / dequeue(self) -> T / peek(self) -> T / length(self) -> int
```

## list.randy — singly linked list (untyped ptr-based)
```
struct ListNode in next: ListNode&; data: ptr; end
struct List in head: ListNode&; tail: ListNode&; end
List::new() -> List& / List::delete(self) / List::append(self, data)
```

## hashmap.randy — `Hashmap[K, V, KHash, KCompare]` generic hash table
```
Hashmap::new(starting_capacity) / insert(self, key, val) / remove(self, key)
Hashmap::find(self, key) -> HashmapPair& / contains(self, key) -> bool
Hashmap::iter(self) -> HashmapIterator&
HashmapIterator::next(self) / key(self) / val(self)
```

## set.randy — `Set[K, KHash, KCompare]` generic hash set
```
Set::new(starting_capacity) / delete(self)
Set::insert(self, key) / remove(self, key) / contains(self, key) -> bool
Set::iter(self) -> SetIterator&
```

## map.randy — untyped hash map (ptr keys/values, function pointer hash/compare)
```
struct MapPair in key: ptr; val: ptr; end
struct Map in length: int; capacity: int; buffer: ptr; comparer: ptr; hasher: ptr; cache: MapPair&; end
Map::new(capacity, comparer, hasher) -> Map& / Map::delete(self)
Map::find(self, key) -> MapPair& / Map::set(self, key, value) / Map::remove(self, elem)
Map::iter_begin(self) -> MapPair& / Map::iter_end(self) -> MapPair& / Map::iter_next(self, iter) -> MapPair&
```

## arena.randy — fixed-size contiguous buffer with index-based access
```
struct Arena in length: int; elem_size: int; buffer: ptr; end
Arena::new(init, elem_size) -> Arena& / Arena::delete(self)
Arena::at(self, idx) -> ptr / Arena::set(self, idx, val)
```

## file.randy — file I/O via syscalls
```
open_for_read(path: cstr) -> fd / open_for_write(path: cstr) -> fd / close(fd) -> int
read_file(fd, buf, count) -> int / write_file(fd, buf, count) -> int
getcwd() -> String&
file_exists(path) / file_is_readable(path) / file_is_writable(path) / file_is_executable(path)
```

## process.randy — process management via syscalls
```
fork() -> int / execve(path, argv, envp) -> int / waitpid(pid, siginfo: ptr, options) -> int
subprocess_blocking(path, argv, envp) -> int
struct Siginfo in _buf: ptr; end
Siginfo::new() -> Siginfo& / Siginfo::delete(self)
Siginfo::si_signo(self) -> int / Siginfo::si_status(self) -> int / Siginfo::si_pid(self) -> int
```

## time.randy — `Timespec` struct, clock reading, sleep
```
make_timespec(sec, nsec) / make_empty_timespec() / free_timespec(self)
time(timespec) — monotonic clock / clock(timespec) — realtime clock
usleep(usec)
```

## syscall.randy — x86_64 Linux syscall constants (SYS_read=0 through SYS_process_mrelease=448) and raw `syscall(...)` asm function

## limits.randy — integer type bounds (CHAR_MIN/MAX, INT8-64_MIN/MAX, INT_MIN/MAX)
