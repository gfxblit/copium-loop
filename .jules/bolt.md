## 2025-02-17 - Asynchronous Telemetry Logging
**Learning:** Frequent small I/O writes (`open()`/`write()`/`close()`) in the main thread (even in an async context) block the event loop, causing measurable latency (~50ms for 1000 logs).
**Action:** Offload file logging to a `ThreadPoolExecutor` (single worker to preserve order) and ensure `read_log()` calls `flush()` to maintain "read-your-writes" consistency for tests and dashboard updates.
## 2026-02-17 - Dashboard Log Polling Optimization
**Learning:** Opening thousands of log files every second in a polling loop (even if they haven't changed) causes significant CPU and I/O overhead. Using `os.scandir` + stat caching reduces loop time from ~9ms to ~1ms (9x speedup) in benchmarks.
**Action:** Use `os.scandir` and check `(st_mtime, st_size)` against a cache before opening files in file-watching loops.
