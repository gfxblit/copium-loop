## 2025-02-12 - Shell Output Buffering Optimization
**Learning:** Found O(N^2) string concatenation and repeated regex compilation in `stream_subprocess` in `src/copium_loop/shell.py`. This can degrade performance significantly with large outputs.
**Action:** Use list accumulation + `"".join()` and pre-compile regexes at module level for string processing tasks in high-throughput streams.
