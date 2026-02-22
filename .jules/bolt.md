## 2025-02-17 - Asynchronous Telemetry Logging
**Learning:** Frequent small I/O writes (`open()`/`write()`/`close()`) in the main thread (even in an async context) block the event loop, causing measurable latency (~50ms for 1000 logs).
**Action:** Offload file logging to a `ThreadPoolExecutor` (single worker to preserve order) and ensure `read_log()` calls `flush()` to maintain "read-your-writes" consistency for tests and dashboard updates.

## 2025-02-18 - File Polling with Scandir and Metadata Caching
**Learning:** Repeatedly globbing (`Path.glob`) and opening files in a tight loop (e.g., UI polling) is extremely CPU-intensive and I/O-bound. `os.scandir` + `mtime/size` caching avoids unnecessary `open()` calls, yielding ~5x performance improvement.
**Action:** Use `os.scandir` for directory iteration and cache file metadata (`mtime`, `size`) to skip unchanged files in polling loops.

## 2025-02-18 - Optimize Git Remote Checks
**Learning:** Checking for git remotes using sequential subprocess calls (`git remote` list then `git remote get-url` per remote) is inefficient (N+1 problem).
**Action:** Use `git remote -v` to fetch all remote URLs in a single subprocess call and parse the output. This reduces overhead significantly, especially in environments where process spawning is expensive.

## 2025-02-19 - Efficient Recent File Selection
**Learning:** Sorting a large list of files by modification time (`path.stat().st_mtime`) just to get the top N most recent ones is inefficient (O(N log N) + N syscalls). `Path.rglob` creates Path objects for all files, adding overhead.
**Action:** Use recursive `os.scandir` to yield `DirEntry` objects (avoiding Path creation) and `heapq.nlargest` (O(N log K)) to select recent files. This reduced scan time by ~50% in benchmarks.
