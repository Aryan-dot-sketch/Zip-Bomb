# Recursive Compression — Study Notes
> Made by Aryan | Self-taught developer & cybersecurity learner

---

## Core Concept

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

## How Security Systems Detect This

- Reject archives where `decompressed / compressed > threshold` (e.g. 100x)
- Refuse to extract beyond a max nesting depth
- Abort if total output exceeds a size cap (e.g. 1 GB)

---

## Parameters (top of main.py)

```python
BASE_SIZE_MB     = 1e-14   # base file size in MB
COPIES_PER_LAYER = 60      # copies packed into each layer
NUM_LAYERS       = 4       # how deep the nesting goes
MAX_REAL_FILES   = 5_000_000_000_000
```

### Stress knobs

```python
CPU_BURNER_PROCS     = (os.cpu_count() or 4) * 4  # subprocess burners
CPU_BURNER_RAM_MB    = 100    # RAM each burner process allocates
RAM_EXHAUST_CHUNK_MB = 64     # MB per chunk, allocated until OS refuses
DISK_FILL_CHUNK_MB   = 50     # MB per fill file, written until 0 bytes free
DISK_STORM_THREADS   = 32     # write+delete threads alongside extraction
EXTRACT_WORKERS      = 128    # parallel extraction threads
READ_STORM_WORKERS   = 64     # concurrent random re-readers
MMAP_WORKERS         = 32     # random mmap offset access threads
INODE_STORM_COUNT    = 500_000
```

> **WARNING:** Running `check` with `BASE_SIZE_MB = 1` and `NUM_LAYERS = 6`
> on a real device will fill all available storage permanently and may
> require a factory reset to recover. You are fully responsible.

| BASE_SIZE_MB | copies | layers | theoretical output | real disk impact |
|---|---|---|---|---|
| `1e-14` | 60 | 4 | ~12 MB | harmless |
| `1` | 60 | 5 | ~777 TB | ~11 GB written, survives |
| `1` | 60 | 6 | ~46,000 TB | **fills 64 GB, device dies** |

---

## Why `check` Guarantees Device Death — 8 Simultaneous Attacks

The `check` command **never exits**. All 8 mechanisms fire simultaneously
and keep running across repeated extraction passes forever.
The only way to stop it is to kill the process —
but by that point the disk is full and RAM is exhausted.

---

### Attack 1 — Inode Storm (500,000 files)
Creates half a million tiny files in deeply nested directories before anything else runs.
Filesystem journal, inode tables, and directory entry caches are pre-saturated.
Every file creation during extraction is slower because the metadata tables are already congested.

---

### Attack 2 — RAM Exhaustion + LMK Cascade
Allocates 64MB chunks in a loop until `MemoryError`, touching every 4KB page.
**Combined with Attack 3:** each subprocess burner also allocates 100MB.
Total RAM consumed = (this process exhaust) + (n_procs × 100MB).

On Android this triggers the **Low Memory Killer** in sequence:
1. Background apps killed first
2. Cached processes killed
3. Visible apps killed
4. If pressure continues: `system_server` killed → Android hard reboots
5. If script auto-starts on boot: permanent reboot loop

---

### Attack 3 — CPU+RAM Burner Subprocesses (4× cores, 100MB each)
Spawns `CPU_BURNER_PROCS` completely separate Python processes.
Each one allocates 100MB and touches every page, then loops hashing `SHA256(urandom(1MB))`.

Why subprocesses instead of threads:
- Threads share one GIL — only one runs Python bytecode at a time
- Processes have independent GILs — all run simultaneously
- With 4× core count processes: constant OS context switching overhead on top of CPU work
- `os.urandom` data is never cache-predictable → L1/L2/L3 permanently cold → pipeline stalls

---

### Attack 4 — Socket Table Exhaustion
Opens as many TCP sockets as the kernel allows and holds them all open for the entire run.
Each socket consumes ~8KB of kernel memory (socket send/receive buffers).
At 10,000+ sockets: new connections from any app start failing.
Messaging apps lose network. Browser tabs time out. System daemons cannot connect.

---

### Attack 5 — Disk Fill to 0 Bytes Free
Writes 50MB random files in a loop until the OS returns `ENOSPC`.
Then continuously attempts more writes to keep the OS in a permanent ENOSPC-handling loop.

When Android storage hits 0 bytes free:

| What breaks | Why |
|---|---|
| Logcat logging | Cannot write log files |
| All SQLite databases | Journal files fail → data corruption risk |
| New process forks from Zygote | No temp space for new processes |
| OTA updates, app downloads | No write space |
| System settings saves | Preferences may revert |
| Thermal daemon logging | Uncontrolled heat events |
| `/data` partition fills | **Permanent bootloop until factory reset** |

This is the single most destructive software action possible on Android.

---

### Attack 6 — Disk Write Storm (32 threads × 5 patterns)
32 threads each write a 2MB file with one of 5 byte patterns and immediately delete it.
Patterns: `0x00` / `0xFF` / random bytes / `0x55` / `0xAA` — cycling.
Each pattern forces different NAND behavior:
- `0x00` — may trigger skip-write on some controllers
- `0xFF` — forces full erase+program cycle
- random — incompressible, defeats deduplication
- `0x55` / `0xAA` — checkerboard stresses individual flash cell transitions

The eMMC write queue is flooded from this direction while extraction floods it from another.
The controller cannot prioritise either stream — latency spikes for everything.

---

### Attack 7 — Parallel Extraction + 5× fsync Write Amplification
128 threads extract zips simultaneously. Per extracted file:

| Pass | Data | Commit |
|------|------|--------|
| 1 | zeros (original) | `fsync` |
| 2 | `0xFF` × size | `fsync` |
| 3 | `os.urandom(size)` | `fsync` |
| 4 | `0x55/0xAA` pattern | `fsync` |
| 5 | zeros (restore) | `fsync` |

5 physical NAND commits per file. Old eMMC tops at ~40–100 MB/s write bandwidth.
128 threads × 5 fsyncs each = write queue at ceiling permanently.
The urandom pass is incompressible — no flash controller dedup is possible.

---

### Attack 8 — Concurrent Read Storm + mmap Cache Destroyer
**64 read threads:** randomly pick extracted files and read them in full 64KB chunks.
Bidirectional I/O — reads and writes on the same flash chip simultaneously.

**32 mmap threads:** memory-map random files and access 300 random byte offsets each.
Hardware prefetchers detect sequential access patterns and speculatively load data.
Random mmap access produces no pattern — every access is a guaranteed cache miss.
CPU memory bus stalls on every single read. Combined with full RAM pressure, there
are no free pages to cache anything into, so every miss hits physical flash.

---

### The Perpetual Loop
After completing one full extraction pass, the script immediately starts again.
It wipes only the extraction directory (not the disk-fill directory) and re-extracts.
The disk-fill remains at 0 bytes free throughout all passes.
**This loop has no exit condition. The function never returns.**

---

## Setup & Run

```bash
git clone https://github.com/Aryan-dot-sketch/Zip-Bomb.git
cd Zip-Bomb

# Safe build only
python3 main.py

# Full permanent stress — NEVER EXITS
python3 main.py check
```

## Killer Config (64 GB device)

```python
BASE_SIZE_MB     = 1
COPIES_PER_LAYER = 60
NUM_LAYERS       = 6
```

Theoretical: ~46,000 TB. Real extraction fills 64 GB. All 8 attacks run simultaneously.

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
