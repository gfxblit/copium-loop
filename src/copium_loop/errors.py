from typing import Any


def is_infrastructure_error(error_msg: str | None) -> bool:
    """
    Identifies common infrastructure/network errors that an LLM cannot resolve.
    """
    if not error_msg:
        return False

    infra_patterns = [
        "Could not resolve host",
        "fatal: unable to access",
        "Connection refused",
        "Operation timed out",
        "Network is unreachable",
        "all models exhausted",
    ]

    error_msg_lower = error_msg.lower()
    return any(pattern.lower() in error_msg_lower for pattern in infra_patterns)


def get_most_relevant_error(state: dict[str, Any]) -> str:
    """
    Extracts the most relevant error content for prompt generation.
    Prioritizes the latest message if it's a real failure to avoid stale last_error.
    """
    messages = state.get("messages", [])
    last_error = state.get("last_error", "")

    # Extract latest message content (ignoring initial request which is messages[0])
    latest_msg = ""
    if len(messages) > 1:
        latest_msg = getattr(messages[-1], "content", str(messages[-1]))

    # 1. Prefer the latest message if it's a real (non-infra) error.
    if latest_msg and not is_infrastructure_error(latest_msg):
        return latest_msg

    # 2. Otherwise, if we have a recorded last_error that is a real error, use it.
    if last_error and not is_infrastructure_error(last_error):
        return last_error

    # 3. Fallback: if we only have infra errors, prefer the most recent one.
    return latest_msg or last_error
