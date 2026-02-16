## 2025-02-17 - Asynchronous Telemetry Logging
**Learning:** Frequent small I/O writes (`open()`/`write()`/`close()`) in the main thread (even in an async context) block the event loop, causing measurable latency (~50ms for 1000 logs).
**Action:** Offload file logging to a `ThreadPoolExecutor` (single worker to preserve order) and ensure `read_log()` calls `flush()` to maintain "read-your-writes" consistency for tests and dashboard updates.

## 2025-02-18 - [Regex Pre-compilation in Shell]
**Learning:** Pre-compiling regexes in hot paths (like subprocess output streaming) yields measurable performance gains (~6-8%) even in Python where `re` module has some caching.
**Action:** Always pre-compile regexes used in loops or frequently called utility functions, especially for high-throughput I/O operations.
