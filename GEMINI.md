
- [2026-01-31 18:02:11] The `journaler` node should wrap `MemoryManager.log_learning` in try-except blocks to ensure that memory logging failures do not crash the agent workflow.
- [2026-01-31 18:09:36] The `journaler` node categorizes learnings into global/experiential (via `save_memory` with timestamps) and project-specific (via string output) to balance cross-project personalization with local codebase context.
- [2026-01-31 20:33:01] The `journaler` node now deduplicates project-specific learnings by including existing memories in the LLM prompt and handling the `NO_LESSON` sentinel value.
- [2026-02-01 16:54:37] The `architect` node requires a diff that includes uncommitted changes since the initial commit to accurately evaluate the progress of the implementation.
- [2026-02-01 17:31:38] The `journaler` node prompt includes "ANTI-PATTERNS" and "PRINCIPLES" sections with examples to ensure learnings are recorded as abstract architectural or process improvements rather than implementation changelogs.
