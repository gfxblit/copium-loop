
- [2026-02-01 18:02:43] Ensure `MatrixPillar.COMPLETION_STATUSES` must include all terminal node states (including `journaled` and `no_lesson`) to guarantee correct duration and completion time rendering in the dashboard.
- [2026-02-01 18:52:27] Explicitly forbid evaluator nodes (like `architect`) from using filesystem modification tools in their system prompts to maintain strict role separation.
