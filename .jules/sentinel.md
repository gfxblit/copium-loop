## 2024-05-23 - Prompt Injection via Git Diff
**Vulnerability:** Git diffs were embedded directly into the LLM system prompt for the Architect and Reviewer nodes without sanitization.
**Learning:** External content (like git history) must be treated as untrusted user input when constructing LLM prompts, just like user messages.
**Prevention:** Always use `engine.sanitize_for_prompt()` (or equivalent escaping) when embedding any external content into a prompt.
