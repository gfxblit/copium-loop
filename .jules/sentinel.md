## 2024-05-22 - Stale Output File Leak in JulesEngine

**Vulnerability:** `JulesEngine` was reading `JULES_OUTPUT.txt` without ensuring it was created by the current session. If the current session failed to create the file, it would read a stale file from a previous session, potentially leading to information disclosure or incorrect workflow behavior.

**Learning:** Temporary files used for inter-process communication must be strictly managed. Assuming a file will be overwritten is not enough; it must be explicitly cleaned up before use.

**Prevention:** Always clean up temporary files before starting a process that is expected to create them. Use `try...finally` blocks to ensure cleanup after use. When possible, use `tempfile` module to generate unique file names instead of fixed paths.
