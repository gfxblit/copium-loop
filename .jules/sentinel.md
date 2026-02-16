# Sentinel's Journal

## 2026-02-16 - Case-Insensitive Prompt Injection
**Vulnerability:** `sanitize_for_prompt` performed case-sensitive string replacement, allowing attackers to bypass sanitization using mixed-case tags (e.g., `</USER_REQUEST>` instead of `</user_request>`) to close XML blocks in the system prompt.
**Learning:** Security sanitization logic must be robust against variations in input format (case, whitespace, encoding) that might be interpreted meaningfully by the consumer (LLM).
**Prevention:** Use case-insensitive matching/replacement or normalize input before sanitization. Always assume the consumer (LLM) is "smart" enough to understand malformed or varied syntax.
