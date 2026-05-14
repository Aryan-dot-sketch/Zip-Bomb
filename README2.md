# Recursive Compression Archiver v2 — Study Notes
> Made by Aryan | CEH | Self-taught developer & cybersecurity researcher

---

## What's Different from v1?

| Feature | v1 | v2 |
|---|---|---|
| Attack vectors | 8 | **218** |
| CPU burner types | 1 (SHA256 only) | **10 distinct algorithms** |
| Disk fill patterns | 1 | **5 simultaneously** |
| Write storm threads | 32 | **60+** |
| Memory attack types | Basic RAM exhaust | **13 techniques** |
| Socket attack types | TCP only | **TCP + UDP + Unix + socketpair** |
| File descriptor attacks | None | **4 types** |
| Thread flood | None | **500 threads** |
| Process flood | None | **200 subprocesses** |
| Python-level storms | None | **8 types** |
| Sync contention | None | **Mutex + RLock + Condition + Semaphore** |
| Filesystem pressure | Basic inode storm | **6 metadata attack types** |
| Disk truncate storm | None | **8 threads, 0→50MB→0 cycles** |
| Disk seek storm | None | **12 threads, random seek+write** |
| Entropy exhaustion | None | **48 threads draining os.urandom** |

---

## Core Concept (same as v1)

A zip bomb is a tiny archive that expands into a massive amount of data when extracted. It works because:

- Null bytes (`\x00`) compress at ~1000x using the DEFLATE algorithm
- Nesting copies multiplies the payload exponentially: `base_size × copies^layers`

## The Math

```
base_size  = 1 byte
copies     = 60 per layer
layers     = 4

theoretical output = 1 byte × 60^4 = 12,960,000 bytes (~12 MB)
```

Scale `base = 1 MB`, `layers = 6` → **46,000 TB**.

---

## Parameters (top of main.py)

```python
BASE_SIZE_MB     = 1e-14   # base file size in MB
COPIES_PER_LAYER = 60      # copies packed into each layer
NUM_LAYERS       = 4       # how deep the nesting goes
MAX_REAL_FILES   = 5_000_000_000_000
CORES            = os.cpu_count() or 4
```

| BASE_SIZE_MB | copies | layers | theoretical output | real disk impact |
|---|---|---|---|---|
| `1e-14` | 60 | 4 | ~12 MB | harmless |
| `1` | 60 | 5 | ~777 TB | ~11 GB written, survives |
| `1` | 60 | 6 | ~46,000 TB | **fills 64 GB, device dies** |

> **WARNING:** Running `check` with `BASE_SIZE_MB = 1` and `NUM_LAYERS = 6`
> on a real device will fill all available storage and may require a factory
> reset to recover. Only run on devices you own. You are fully responsible.

---

## Full Attack Vector Matrix — 218 Vectors

All 218 vectors fire **simultaneously** the moment `check` is called.
If any one fails, the remaining 217 keep running. The function never returns.

---

### [CPU] — 10 Subprocess Worker Types (vectors #1–10)

Each worker is a **fully independent OS process** — no GIL sharing.

| # | Algorithm | Processes | Why it's effective |
|---|---|---|---|
| 1 | SHA256 of urandom(1MB) + 100MB RAM alloc | CORES×3 | Cache-cold data, random I/O |
| 2 | sin/cos/sqrt/exp/pow floating-point chain | CORES×2 | FPU saturation |
| 3 | 256-bit big-integer LCG × XOR chain | CORES×2 | ALU saturation, no SIMD |
| 4 | 128MB↔128MB bytearray copy loop | CORES | Memory bandwidth saturation |
| 5 | zlib compress(10MB random, lvl=1) + decompress | CORES | CPU + memory combined |
| 6 | bz2 compress(4MB) + decompress | CORES//2 | Most CPU-hungry codec |
| 7 | Sort 5M random floats repeatedly | CORES//2 | Cache thrash + branch misprediction |
| 8 | 200×200 matrix multiply (pure Python loops) | CORES//2 | Interpreter overhead maximised |
| 9 | SHA512 chain: h=SHA512(h+urandom) | CORES×2 | Persistent hash state pressure |
| 10 | HMAC-SHA256, random 64-byte key, 1MB messages | CORES | Key schedule overhead |

Why subprocesses instead of threads: each subprocess has its own GIL, so all run Python bytecode simultaneously — threads cannot achieve this.

---

### [DISK] — Fill to 0 Bytes Free (vectors #11–15)

Five fill threads run **simultaneously**, each using a different byte pattern:

| # | Pattern | Why |
|---|---|---|
| 11 | `\x00` zeros | May trigger skip-write on some controllers |
| 12 | `\xff` ones | Forces full erase+program cycle on NAND |
| 13 | `os.urandom` | Incompressible — defeats flash deduplication |
| 14 | `\x55\xaa` alternating | Stresses individual cell bit transitions |
| 15 | `\x00`↔`\xff` alternating writes | Maximises write amplification factor |

When Android storage hits 0 bytes free:

| What breaks | Why |
|---|---|
| Logcat logging | Cannot write log files |
| All SQLite databases | Journal files fail → data corruption risk |
| New process forks from Zygote | No temp space |
| OTA updates, app downloads | No write space |
| System settings saves | Preferences may revert |
| Thermal daemon logging | Uncontrolled heat events |
| `/data` partition fills | **Permanent bootloop until factory reset** |

---

### [DISK] — Write+Delete Storm (vectors #16–75)

60 threads total — 12 threads per pattern, 5 patterns:

| Vectors | Pattern | Threads |
|---|---|---|
| #16–27 | 2MB zeros | 12 |
| #28–39 | 2MB `\xff` | 12 |
| #40–51 | 2MB random bytes | 12 |
| #52–63 | 2MB `\x55\xaa` | 12 |
| #64–75 | 2MB checkerboard | 12 |

Each thread: write → fsync → delete → repeat. The eMMC write queue is flooded from this direction simultaneously with extraction.

---

### [DISK] — Size-Variant Storms (vectors #76–79)

| # | File size | Threads | Purpose |
|---|---|---|---|
| 76 | 512 bytes | 16 | Inode/journal pressure with tiny files |
| 77 | 4KB | 16 | Page-aligned write pressure |
| 78 | 100MB | 4 | Large sequential write pressure |
| 79 | 1B→50MB random | 8 | Unpredictable size → defeats controller optimisation |

---

### [DISK] — Metadata Pressure (vectors #80–95)

16 independent threads continuously: `create → stat → chmod → rename → delete`

Saturates the filesystem journal and inode tables independently of data writes.

---

### [DISK] — Truncate Storm (vectors #96–103)

8 threads each cycling: `grow file 0→50MB → fsync → truncate to 0 → fsync → repeat`

Forces the flash wear-levelling algorithm into constant remapping. Each fsync at 50MB commits a full physical erase block.

---

### [DISK] — Seek + Random-Write Storm (vectors #104–115)

12 threads each: open a 200MB file → random seek → write 4KB → fsync → repeat

Produces worst-case random-write I/O pattern — no sequential locality for the controller to optimise.

---

### [DISK] — Fragmentation + Append (vectors #116–118)

| # | Description |
|---|---|
| 116 | Write files cycling 1B/4KB/1MB/10MB, delete odd-indexed → maximum fragmentation |
| 117 | Copy files between two dirs, delete source → constant relocation pressure |
| 118 | Append 4KB to same file until 2GB, then delete and restart → append amplification |

---

### [FILESYSTEM METADATA] — 6 Attack Types (vectors #119–124)

| # | Attack |
|---|---|
| 119 | 500k-file inode storm: flat directory |
| 120 | Deep-nested inode storm: files at depth 1000 |
| 121 | 255-char filename storm (max POSIX filename length) |
| 122 | Dot-file storm (hidden files) |
| 123 | `readdir()` loop on 500k-entry directory |
| 124 | `os.stat()` loop on thousands of files |

---

### [MEMORY] — 13 Attack Types (vectors #125–137)

| # | Attack | Detail |
|---|---|---|
| 125 | RAM exhaust | 64MB chunks until `MemoryError`, every page touched |
| 126 | Anonymous mmap exhaust | `MAP_PRIVATE\|ANONYMOUS` until kernel refuses |
| 127 | Cache thrash A | Random access across 128MB (> L3 on all phones) |
| 128 | Cache thrash B | Stride every 128 bytes (2× cacheline) |
| 129 | Cache thrash C | Prime-step stride — defeats hardware prefetcher |
| 130 | False sharing | 32 threads writing adjacent bytes in shared bytearray |
| 131 | GC pressure A | Alloc+discard 10k dicts/sec → triggers GC constantly |
| 132 | GC pressure B | Circular references + explicit `gc.collect()` |
| 133 | Large string storm | Alloc+discard 128MB strings |
| 134 | bytearray copy storm | Copy 64MB→64MB repeatedly |
| 135 | Stack pressure | 32 threads at recursion depth 800 each |
| 136 | mmap random offset | Defeats page-cache — every access is a flash read |
| 137 | mmap sequential+random | Mixed access pattern — no prefetch wins |

---

### [NETWORK / SOCKET] — 6 Attack Types (vectors #138–143)

| # | Attack |
|---|---|
| 138 | TCP socket exhaust: open until `EMFILE`/`ENFILE`, hold all open |
| 139 | UDP socket exhaust |
| 140 | Unix-domain socket exhaust |
| 141 | `socketpair()` exhaust |
| 142 | Socket buffer fill: write to TCP socket with no reader |
| 143 | Rapid localhost connect/disconnect storm |

At 10,000+ open sockets: messaging apps lose network, browser tabs time out, system daemons cannot connect.

---

### [FILE DESCRIPTOR] — 4 Attack Types (vectors #144–147)

| # | Attack |
|---|---|
| 144 | FD exhaust: open output files until `EMFILE`, hold all open |
| 145 | Pipe exhaust: `os.pipe()` until `EMFILE`, hold all open |
| 146 | Pipe fill: write to pipe until `EAGAIN`, never read |
| 147 | `dup()` exhaust: duplicate existing FD until table full |

---

### [PROCESS / THREAD] — 3 Attack Types (vectors #148–150)

| # | Attack |
|---|---|
| 148 | Process flood: 200 subprocesses each with 50MB RAM + CPU burn |
| 149 | Thread flood: 500 daemon threads each in busy loop |
| 150 | Context-switch storm: 500 threads sleeping 0.001s (maximises scheduler overhead) |

---

### [SYNCHRONISATION CONTENTION] — 4 Attack Types (vectors #151–200)

| Vectors | Primitive | Threads | Effect |
|---|---|---|---|
| #151–182 | `threading.Lock` | 32 | Constant mutex contention |
| #183–198 | `threading.RLock` | 16 | Reentrant lock overhead |
| #199 | `threading.Condition` | 4 | notify+wait tight loop |
| #200 | `threading.Semaphore` | — | acquire/release storm |

---

### [ENTROPY / KERNEL RANDOM] — 2 Attack Types (vectors #201–202)

| # | Attack |
|---|---|
| 201 | 32 threads each reading `os.urandom(4MB)` per iteration |
| 202 | 16 threads each reading `os.urandom(8MB)` per iteration |

Drains the kernel entropy pool. On some kernels this blocks other processes waiting for random data.

---

### [PYTHON OVERHEAD STORMS] — 8 Attack Types (vectors #203–210)

| # | Storm | Detail |
|---|---|---|
| 203 | Exception storm | raise+catch `ValueError` ~1M/sec → GIL + exception table pressure |
| 204 | JSON encode/decode | Large nested dict, ~10MB |
| 205 | pickle dumps/loads | Large object graph |
| 206 | struct pack/unpack | 1M fields per iteration |
| 207 | base64 encode/decode | 32MB buffers |
| 208 | zlib in-thread | compress/decompress loop (complements subprocess version) |
| 209 | bz2 in-thread | compress/decompress loop |
| 210 | hashlib in-thread | SHA256 of large buffers |

---

### [ZIP BOMB CORE] — Perpetual Extraction Loop (vectors #211–218)

| # | Pass | Action |
|---|---|---|
| 211 | 1 | Extract zeros → fsync |
| 212 | 2 | Overwrite `\xff` → fsync |
| 213 | 3 | Overwrite `os.urandom` → fsync (incompressible, no flash dedup) |
| 214 | 4 | Overwrite `\x55\xaa` → fsync |
| 215 | 5 | Restore zeros → fsync |
| 216 | — | SHA256 verify pass (CPU + read I/O simultaneously) |
| 217 | — | 128-worker parallel extraction (128 simultaneous fsync storms) |
| 218 | — | Perpetual re-extraction after each pass — **never exits** |

5 physical NAND commits per file × 128 threads = write queue at ceiling permanently.

---

## How Security Systems Detect This

- Reject archives where `decompressed / compressed > threshold` (e.g. 100×)
- Refuse to extract beyond a max nesting depth
- Abort if total output exceeds a size cap (e.g. 1 GB)
- Monitor for rapid inode creation storms
- Rate-limit socket/FD creation per process

---

## Setup & Run

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# Safe build only — creates nested zips, no stress
python3 main.py

# Full permanent stress — 218 vectors — NEVER EXITS
python3 main.py check
```

> **Legal disclaimer:** Only run on devices you own. Unauthorized use against
> systems you don't own is illegal under the IT Act and equivalent laws worldwide.

---

## Killer Config (64 GB device)

```python
BASE_SIZE_MB     = 1
COPIES_PER_LAYER = 60
NUM_LAYERS       = 6
```

Theoretical: ~46,000 TB. Real extraction fills 64 GB. All 218 attacks run simultaneously.

> **WARNING:** This config guarantees a factory reset is required to recover.

---

## Clean Up (if you can still access the device)

```bash
rm -rf output/
```

---

## Further Reading

- [DEFLATE spec (RFC 1951)](https://www.rfc-editor.org/rfc/rfc1951)
- [42.zip — 42 KB → 4.5 PB](https://www.unforgettable.dk/)
- [How antivirus handles zip bombs](https://blog.rapid7.com/2020/05/26/zip-bombs-how-to-detect-them/)
- [Flash write amplification](https://en.wikipedia.org/wiki/Write_amplification)
- [Android Low Memory Killer](https://source.android.com/docs/core/perf/lmkd)
- [Python GIL and multiprocessing](https://docs.python.org/3/glossary.html#term-global-interpreter-lock)
- [NAND flash P/E cycles and wear](https://en.wikipedia.org/wiki/Flash_memory#Limitations)
- [Linux FD limits and ulimit](https://man7.org/linux/man-pages/man2/setrlimit.2.html)
- [Linux socket buffer internals](https://www.kernel.org/doc/html/latest/networking/net_dim.html)
- [Python threading and the GIL](https://realpython.com/python-gil/)
