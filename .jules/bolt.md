## 2025-02-17 - Asynchronous Telemetry Logging
**Learning:** Frequent small I/O writes (`open()`/`write()`/`close()`) in the main thread (even in an async context) block the event loop, causing measurable latency (~50ms for 1000 logs).
**Action:** Offload file logging to a `ThreadPoolExecutor` (single worker to preserve order) and ensure `read_log()` calls `flush()` to maintain "read-your-writes" consistency for tests and dashboard updates.

## 2025-02-18 - File Polling with Scandir and Metadata Caching
**Learning:** Repeatedly globbing (`Path.glob`) and opening files in a tight loop (e.g., UI polling) is extremely CPU-intensive and I/O-bound. `os.scandir` + `mtime/size` caching avoids unnecessary `open()` calls, yielding ~5x performance improvement.
**Action:** Use `os.scandir` for directory iteration and cache file metadata (`mtime`, `size`) to skip unchanged files in polling loops.

## 2025-02-18 - Optimize Git Remote Checks
**Learning:** Checking for git remotes using sequential subprocess calls (`git remote` list then `git remote get-url` per remote) is inefficient (N+1 problem).
**Action:** Use `git remote -v` to fetch all remote URLs in a single subprocess call and parse the output. This reduces overhead significantly, especially in environments where process spawning is expensive.

## 2025-02-18 - Efficient Top-K File Selection
**Learning:** Sorting an entire directory listing (`O(N log N)`) just to get the top K most recent files is wasteful when N is large. `heapq.nlargest` (`O(N log K)`) combined with `os.scandir` (avoiding `Path` object creation overhead) yields a ~3x speedup for session log polling.
**Action:** Use `heapq.nlargest` with a generator yielding `DirEntry` objects (to leverage cached stats) when filtering large file sets.
