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
        "rate limit reached",
        "service unavailable",
        "internal server error",
        "bad gateway",
        "gateway timeout",
        "quota exceeded",
        "resource has been exhausted",
    ]

    error_msg_lower = error_msg.lower()
    return any(pattern.lower() in error_msg_lower for pattern in infra_patterns)
