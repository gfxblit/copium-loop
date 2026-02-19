## 2026-02-19 - Prompt Injection via Git Diff
**Vulnerability:** User input (code changes in git diff) was included directly in LLM prompts without sanitization. An attacker could inject XML-like closing tags (e.g., `</git_diff>`) to escape the context and manipulate the LLM's instructions.
**Learning:** Even "read-only" data like git diffs can be a vector for prompt injection if the prompt format relies on delimiters that can be mimicked by the data.
**Prevention:** Always sanitize untrusted data before including it in prompts. Use `engine.sanitize_for_prompt()` which escapes or replaces potential delimiters.
