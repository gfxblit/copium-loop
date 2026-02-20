## 2025-02-17 - Asynchronous Telemetry Logging
**Learning:** Frequent small I/O writes (`open()`/`write()`/`close()`) in the main thread (even in an async context) block the event loop, causing measurable latency (~50ms for 1000 logs).
**Action:** Offload file logging to a `ThreadPoolExecutor` (single worker to preserve order) and ensure `read_log()` calls `flush()` to maintain "read-your-writes" consistency for tests and dashboard updates.

## 2025-02-18 - File Polling with Scandir and Metadata Caching
**Learning:** Repeatedly globbing (`Path.glob`) and opening files in a tight loop (e.g., UI polling) is extremely CPU-intensive and I/O-bound. `os.scandir` + `mtime/size` caching avoids unnecessary `open()` calls, yielding ~5x performance improvement.
**Action:** Use `os.scandir` for directory iteration and cache file metadata (`mtime`, `size`) to skip unchanged files in polling loops.

## 2025-02-18 - Optimized Sorting for File Polling
**Learning:** Sorting thousands of file entries by `mtime` (O(N log N)) every second for UI updates is a bottleneck, even with `os.scandir`. `heapq.nlargest` (O(N log K)) significantly reduces latency (from ~174ms to ~69ms for 10k files) when only the top K results are needed.
**Action:** Use `heapq.nlargest` instead of `sort()` when filtering for the most recent files in a large directory.
