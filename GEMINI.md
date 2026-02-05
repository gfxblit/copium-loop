# Project Memory

- [2026-02-01 19:41:06] Use the `temp_git_repo` fixture in `test/conftest.py` for all git-based integration tests to ensure reliable environment isolation and consistent execution via `subprocess.run`.
- [2026-02-02 21:33:29] Always propagate the `node` context through git and shell utility functions to ensure telemetry is correctly attributed to the active node in the dashboard.
- [2026-02-03 06:34:47] Log a node's 'success' status unconditionally at the beginning of its conditional routing function to ensure the UI dashboard correctly reflects its completion across all branching paths.
- [2026-02-03 07:35:16] Derive UI pillar names directly from the `node` field in telemetry events to ensure the dashboard accurately reflects all active nodes and supports dynamic discovery.
- [2026-02-04 18:23:19] Explicitly log a 'failed' status to telemetry when a node encounters a process failure to ensure the UI dashboard correctly renders visual failure indicators.
