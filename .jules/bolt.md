## 2025-02-17 - Asynchronous Telemetry Logging
**Learning:** Frequent small I/O writes (`open()`/`write()`/`close()`) in the main thread (even in an async context) block the event loop, causing measurable latency (~50ms for 1000 logs).
**Action:** Offload file logging to a `ThreadPoolExecutor` (single worker to preserve order) and ensure `read_log()` calls `flush()` to maintain "read-your-writes" consistency for tests and dashboard updates.

## 2025-02-18 - File Polling with Scandir and Metadata Caching
**Learning:** Repeatedly globbing (`Path.glob`) and opening files in a tight loop (e.g., UI polling) is extremely CPU-intensive and I/O-bound. `os.scandir` + `mtime/size` caching avoids unnecessary `open()` calls, yielding ~5x performance improvement.
**Action:** Use `os.scandir` for directory iteration and cache file metadata (`mtime`, `size`) to skip unchanged files in polling loops.

## 2025-02-18 - Git Remote Batching
**Learning:** Iterating over git remotes to query their URLs individually (`git remote` then `git remote get-url <remote>`) scales linearly with the number of remotes, causing significant subprocess overhead (~15ms for 20 remotes).
**Action:** Use `git remote -v` to fetch all remote URLs in a single subprocess call, reducing overhead to a constant time (~3ms), regardless of the number of remotes.
