# Project Memory

- [2026-02-02 21:33:29] Always propagate the `node` context through git and shell utility functions to ensure telemetry is correctly attributed to the active node in the dashboard.
- [2026-02-03 06:34:47] Log a node's 'success' status unconditionally at the beginning of its conditional routing function to ensure the UI dashboard correctly reflects its completion across all branching paths.
- [2026-02-04 18:23:19] Explicitly log a 'failed' status to telemetry when a node encounters a process failure to ensure the UI dashboard correctly renders visual failure indicators.
- [2026-02-12 11:30:00] Replaced the Rich-based Dashboard with a Textual-based TextualDashboard for the --monitor flag, improving UI flexibility and interaction. Removed the old Dashboard and InputReader implementations.
- [2026-02-12 11:45:00] Improved TextualDashboard with most-recent-first session sorting, arrow key navigation, and immediate stats loading on mount. Verified with full test suite.
