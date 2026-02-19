## 2025-02-17 - Asynchronous Telemetry Logging
**Learning:** Frequent small I/O writes (`open()`/`write()`/`close()`) in the main thread (even in an async context) block the event loop, causing measurable latency (~50ms for 1000 logs).
**Action:** Offload file logging to a `ThreadPoolExecutor` (single worker to preserve order) and ensure `read_log()` calls `flush()` to maintain "read-your-writes" consistency for tests and dashboard updates.

## 2025-02-18 - File Polling with Scandir and Metadata Caching
**Learning:** Repeatedly globbing (`Path.glob`) and opening files in a tight loop (e.g., UI polling) is extremely CPU-intensive and I/O-bound. `os.scandir` + `mtime/size` caching avoids unnecessary `open()` calls, yielding ~5x performance improvement.
**Action:** Use `os.scandir` for directory iteration and cache file metadata (`mtime`, `size`) to skip unchanged files in polling loops.

## 2025-02-24 - Batching Git Subprocess Calls
**Learning:** Sequential subprocess calls (e.g., `git remote`, then `git remote get-url`) incur significant overhead (~20-40ms per call). Parsing batched output from `git remote -v` reduces this to a single call, yielding ~6x speedup (4.69ms vs 28.89ms).
**Action:** Prefer single, verbose git commands (like `git remote -v` or `git status --porcelain`) and parse the output in Python over multiple specific subprocess calls.
