"""Lab-oriented hard capability failure classification (non-production)."""
from __future__ import annotations

HARD_CAPABILITY_MISSING = "hard_capability_missing"
NOT_HARD_CAPABILITY_FAILURE = "not_hard_capability_failure"
UNKNOWN_FAILURE = "unknown_failure"


def classify_hard_capability_failure(
    error: BaseException | str | None,
    *,
    required_capability: str,
) -> str:
    """Classify an execution-time failure for post-failure fallback routing."""
    if error is None:
        return UNKNOWN_FAILURE
    message = str(error).casefold()
    if required_capability == "tool_calling":
        if "does not support tools" in message:
            return HARD_CAPABILITY_MISSING
        if "status code: 400" in message and "tool" in message:
            return HARD_CAPABILITY_MISSING
        if "ollama_rejected_tools_parameter" in message:
            return HARD_CAPABILITY_MISSING
    return NOT_HARD_CAPABILITY_FAILURE


def is_hard_capability_missing(failure_class: str) -> bool:
    return failure_class == HARD_CAPABILITY_MISSING


__all__ = [
    "HARD_CAPABILITY_MISSING",
    "NOT_HARD_CAPABILITY_FAILURE",
    "UNKNOWN_FAILURE",
    "classify_hard_capability_failure",
    "is_hard_capability_missing",
]
