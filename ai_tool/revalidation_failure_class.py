"""Mechanical failure classification for semantic revalidation Lab harnesses."""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.llm_json_parse import LLMEmptyResponseError
from ai_tool.revalidation_protocol import SEMANTIC_REVALIDATION_OUTCOMES

FAILURE_CLASS_SYSTEM_MISSING_INPUTS = "system_missing_inputs"
FAILURE_CLASS_SYSTEM_NOT_CONFIGURED = "system_not_configured"
FAILURE_CLASS_LLM_SCHEMA_FAILURE = "llm_schema_failure"
FAILURE_CLASS_LLM_EMPTY_RESPONSE = "llm_empty_response"
FAILURE_CLASS_LLM_PARSE_FAILURE = "llm_parse_failure"
FAILURE_CLASS_UNKNOWN_OUTCOME = "unknown_outcome"
FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE = "semantic_cannot_determine"
FAILURE_CLASS_RESOLVED = "resolved"

MECHANICAL_RETRY_FAILURE_CLASSES = frozenset(
    {
        FAILURE_CLASS_LLM_SCHEMA_FAILURE,
        FAILURE_CLASS_LLM_EMPTY_RESPONSE,
        FAILURE_CLASS_LLM_PARSE_FAILURE,
        FAILURE_CLASS_UNKNOWN_OUTCOME,
    }
)

SYSTEM_FAILURE_CLASSES = frozenset(
    {
        FAILURE_CLASS_SYSTEM_MISSING_INPUTS,
        FAILURE_CLASS_SYSTEM_NOT_CONFIGURED,
    }
)

SEMANTIC_FAILURE_CLASSES = frozenset({FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE})


def classify_revalidation_failure(
    result: Mapping[str, Any] | None,
    *,
    error: BaseException | None = None,
) -> str:
    """Classify one revalidation evaluation into a Lab failure_class."""
    if error is not None:
        if isinstance(error, LLMEmptyResponseError):
            return FAILURE_CLASS_LLM_EMPTY_RESPONSE
        if error.__class__.__name__ == "JSONDecodeError":
            return FAILURE_CLASS_LLM_PARSE_FAILURE
        return FAILURE_CLASS_LLM_PARSE_FAILURE

    row = dict(result or {})
    outcome = str(row.get("outcome") or "").strip()
    reason = str(row.get("reason") or "").strip()

    if outcome in {"still_valid", "needs_revision", "invalid"}:
        return FAILURE_CLASS_RESOLVED

    if reason == "missing_required_inputs":
        return FAILURE_CLASS_SYSTEM_MISSING_INPUTS
    if reason == "chat_fn_not_configured":
        return FAILURE_CLASS_SYSTEM_NOT_CONFIGURED
    if reason == "invalid_llm_schema":
        return FAILURE_CLASS_LLM_SCHEMA_FAILURE

    if outcome == "cannot_determine":
        raw_payload = row.get("llm_payload")
        if isinstance(raw_payload, Mapping):
            raw_outcome = str(raw_payload.get("outcome") or "").strip()
            if raw_outcome and raw_outcome not in SEMANTIC_REVALIDATION_OUTCOMES:
                return FAILURE_CLASS_UNKNOWN_OUTCOME
        if reason:
            return FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE
        return FAILURE_CLASS_UNKNOWN_OUTCOME

    if outcome:
        return FAILURE_CLASS_UNKNOWN_OUTCOME
    return FAILURE_CLASS_LLM_PARSE_FAILURE


def is_cannot_determine_outcome(result: Mapping[str, Any] | None) -> bool:
    return str((result or {}).get("outcome") or "").strip() == "cannot_determine"


def is_resolved_outcome(result: Mapping[str, Any] | None) -> bool:
    return classify_revalidation_failure(result) == FAILURE_CLASS_RESOLVED


def is_mechanical_retry_candidate(failure_class: str) -> bool:
    return failure_class in MECHANICAL_RETRY_FAILURE_CLASSES


def is_semantic_only_failure(failure_class: str) -> bool:
    return failure_class in SEMANTIC_FAILURE_CLASSES


def is_unnecessary_escalation_candidate(
    *,
    failure_class: str,
    final_outcome: Mapping[str, Any] | None,
) -> bool:
    """True when stronger-local HELP would likely be wasted on mechanical failure."""
    if is_resolved_outcome(final_outcome):
        return False
    return failure_class in MECHANICAL_RETRY_FAILURE_CLASSES | SYSTEM_FAILURE_CLASSES


__all__ = [
    "FAILURE_CLASS_LLM_EMPTY_RESPONSE",
    "FAILURE_CLASS_LLM_PARSE_FAILURE",
    "FAILURE_CLASS_LLM_SCHEMA_FAILURE",
    "FAILURE_CLASS_RESOLVED",
    "FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE",
    "FAILURE_CLASS_SYSTEM_MISSING_INPUTS",
    "FAILURE_CLASS_SYSTEM_NOT_CONFIGURED",
    "FAILURE_CLASS_UNKNOWN_OUTCOME",
    "MECHANICAL_RETRY_FAILURE_CLASSES",
    "SEMANTIC_FAILURE_CLASSES",
    "SYSTEM_FAILURE_CLASSES",
    "classify_revalidation_failure",
    "is_cannot_determine_outcome",
    "is_mechanical_retry_candidate",
    "is_resolved_outcome",
    "is_semantic_only_failure",
    "is_unnecessary_escalation_candidate",
]
