## 2024-05-22 - [Sentinel Initialized]
**Vulnerability:** Missing security journal.
**Learning:** Security learnings must be tracked to prevent regression.
**Prevention:** Created journal.

## 2024-05-22 - [Prompt Injection in Workflow Nodes]
**Vulnerability:** `journaler_node`, `reviewer_node`, and `architect_node` constructed prompts using unsanitized inputs (`git_diff`, `telemetry_log`). An attacker could inject instructions (e.g., via a malicious PR diff) to bypass review or manipulate the journal.
**Learning:** Even internal tools operating on git repositories are vulnerable to prompt injection if they consume untrusted content (like PR diffs) into LLM prompts.
**Prevention:** Always sanitize inputs (escape XML-like tags) before embedding them in prompts. Use `engine.sanitize_for_prompt`. Updated `utils.py` to enforce sanitization centrally for prompts that include `git_diff`.
