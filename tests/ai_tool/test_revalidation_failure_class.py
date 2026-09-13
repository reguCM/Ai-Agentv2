"""Unit tests for revalidation failure_class mapping."""
from __future__ import annotations

import json

import pytest

from ai_tool.llm_json_parse import LLMEmptyResponseError
from ai_tool.revalidation_failure_class import (
    FAILURE_CLASS_LLM_EMPTY_RESPONSE,
    FAILURE_CLASS_LLM_PARSE_FAILURE,
    FAILURE_CLASS_LLM_SCHEMA_FAILURE,
    FAILURE_CLASS_RESOLVED,
    FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE,
    FAILURE_CLASS_SYSTEM_MISSING_INPUTS,
    FAILURE_CLASS_SYSTEM_NOT_CONFIGURED,
    classify_revalidation_failure,
    is_mechanical_retry_candidate,
    is_unnecessary_escalation_candidate,
)
from ai_tool.revalidation_protocol import (
    semantic_revalidation_result_invalid_schema,
    semantic_revalidation_result_missing_chat_fn,
    semantic_revalidation_result_missing_inputs,
)


def test_classify_system_missing_inputs():
    result = semantic_revalidation_result_missing_inputs(["decision_premises"])
    assert classify_revalidation_failure(result) == FAILURE_CLASS_SYSTEM_MISSING_INPUTS
    assert not is_mechanical_retry_candidate(classify_revalidation_failure(result))


def test_classify_system_not_configured():
    result = semantic_revalidation_result_missing_chat_fn()
    assert classify_revalidation_failure(result) == FAILURE_CLASS_SYSTEM_NOT_CONFIGURED


def test_classify_llm_schema_failure():
    result = semantic_revalidation_result_invalid_schema({"foo": "bar"})
    assert classify_revalidation_failure(result) == FAILURE_CLASS_LLM_SCHEMA_FAILURE
    assert is_mechanical_retry_candidate(classify_revalidation_failure(result))


def test_classify_semantic_cannot_determine():
    result = {
        "outcome": "cannot_determine",
        "reason": "Ambiguous under active decisions.",
    }
    assert classify_revalidation_failure(result) == FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE
    assert not is_mechanical_retry_candidate(classify_revalidation_failure(result))


def test_classify_empty_and_parse_errors():
    assert (
        classify_revalidation_failure(None, error=LLMEmptyResponseError("empty"))
        == FAILURE_CLASS_LLM_EMPTY_RESPONSE
    )
    assert (
        classify_revalidation_failure(None, error=json.JSONDecodeError("bad", "", 0))
        == FAILURE_CLASS_LLM_PARSE_FAILURE
    )


def test_classify_resolved_outcomes():
    for outcome in ("still_valid", "needs_revision", "invalid"):
        assert classify_revalidation_failure({"outcome": outcome}) == FAILURE_CLASS_RESOLVED


def test_unnecessary_escalation_candidate_for_mechanical_unresolved():
    assert is_unnecessary_escalation_candidate(
        failure_class=FAILURE_CLASS_LLM_SCHEMA_FAILURE,
        final_outcome={"outcome": "cannot_determine"},
    )
    assert not is_unnecessary_escalation_candidate(
        failure_class=FAILURE_CLASS_SEMANTIC_CANNOT_DETERMINE,
        final_outcome={"outcome": "cannot_determine"},
    )
