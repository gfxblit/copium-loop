## 2025-02-17 - Asynchronous Telemetry Logging
**Learning:** Frequent small I/O writes (`open()`/`write()`/`close()`) in the main thread (even in an async context) block the event loop, causing measurable latency (~50ms for 1000 logs).
**Action:** Offload file logging to a `ThreadPoolExecutor` (single worker to preserve order) and ensure `read_log()` calls `flush()` to maintain "read-your-writes" consistency for tests and dashboard updates.

## 2025-02-18 - File Polling with Scandir and Metadata Caching
**Learning:** Repeatedly globbing (`Path.glob`) and opening files in a tight loop (e.g., UI polling) is extremely CPU-intensive and I/O-bound. `os.scandir` + `mtime/size` caching avoids unnecessary `open()` calls, yielding ~5x performance improvement.
**Action:** Use `os.scandir` for directory iteration and cache file metadata (`mtime`, `size`) to skip unchanged files in polling loops.

## 2025-02-18 - Optimize Git Remote Checks
**Learning:** Checking for git remotes using sequential subprocess calls (`git remote` list then `git remote get-url` per remote) is inefficient (N+1 problem).
**Action:** Use `git remote -v` to fetch all remote URLs in a single subprocess call and parse the output. This reduces overhead significantly, especially in environments where process spawning is expensive.

## 2024-05-19 - Fast File Discovery with Metadata
**Learning:** `Path.rglob` followed by `Path.stat()` iterates all files but requires a separate system call for `stat()` on each matched file. In Python, `os.scandir` caches `stat` metadata (on most POSIX/Windows systems), so an explicit recursive generator using `os.scandir` combined with `entry.stat()` avoids the extra system calls, making bulk metadata reads (like finding the most recent logs) noticeably faster.
**Action:** When searching directories where file metadata (like `st_mtime` or `st_size`) is immediately needed, write a recursive `os.scandir` generator instead of relying on `Path.rglob()`.
