"""Post-Failure Hard Capability Fallback Lab unit tests (mocked chat_fn)."""
from __future__ import annotations

from unittest import mock

from ai_tool.hard_capability_failure_class import (
    HARD_CAPABILITY_MISSING,
    classify_hard_capability_failure,
)
from ai_tool.post_failure_capability_lab import (
    default_tool_task,
    run_case_a_pre_routing,
    run_case_b_post_failure_fallback,
    summarize_post_failure_lab,
)


def _success_chat(**_kwargs):
    fn = mock.Mock()
    fn.name = "echo_probe"
    fn.arguments = {"text": "ROUTING_LAB_OK"}
    msg = mock.Mock()
    msg.content = ""
    msg.tool_calls = [mock.Mock(function=fn)]
    return mock.Mock(message=msg)


def _deepseek_fail_chat(**kwargs):
    model = str(kwargs.get("model") or "")
    if "deepseek" in model:
        raise RuntimeError("model does not support tools (status code: 400)")
    return _success_chat(**kwargs)


def test_classify_hard_capability_missing_from_ollama_tools_rejection():
    failure_class = classify_hard_capability_failure(
        RuntimeError("model does not support tools (status code: 400)"),
        required_capability="tool_calling",
    )
    assert failure_class == HARD_CAPABILITY_MISSING


def test_case_a_pre_routing_skips_deepseek_and_succeeds_on_fallback():
    task = default_tool_task()
    observation = run_case_a_pre_routing(
        task,
        primary_worker_id="deepseek_coder_v2_16b",
        chat_fn=_deepseek_fail_chat,
    )
    assert observation.case == "A"
    assert observation.primary_execution_attempted is False
    assert observation.precheck_result == "primary_skipped_precheck"
    assert observation.selected_fallback == "qwen3_8b"
    assert observation.final_success is True
    assert observation.attempts == 1
    assert observation.native_tool_call is True


def test_case_b_post_failure_fallback_classifies_and_retries_same_task():
    task = default_tool_task()
    observation = run_case_b_post_failure_fallback(
        task,
        primary_worker_id="deepseek_coder_v2_16b",
        chat_fn=_deepseek_fail_chat,
    )
    assert observation.case == "B"
    assert observation.precheck_result == "bypassed"
    assert observation.primary_execution_attempted is True
    assert observation.failure_class == HARD_CAPABILITY_MISSING
    assert "does not support tools" in str(observation.primary_failure or "")
    assert observation.selected_fallback == "qwen3_8b"
    assert observation.final_success is True
    assert observation.attempts == 2
    assert observation.native_tool_call is True


def test_summary_shows_both_paths_succeed_with_lower_attempts_for_case_a():
    task = default_tool_task()
    case_a = run_case_a_pre_routing(
        task,
        primary_worker_id="deepseek_coder_v2_16b",
        chat_fn=_deepseek_fail_chat,
    )
    case_b = run_case_b_post_failure_fallback(
        task,
        primary_worker_id="deepseek_coder_v2_16b",
        chat_fn=_deepseek_fail_chat,
    )
    summary = summarize_post_failure_lab(case_a, case_b)
    assert summary["both_paths_succeed"] is True
    assert summary["pre_routing_avoids_primary_failure"] is True
    assert summary["post_failure_fallback_demonstrated"] is True
    assert summary["case_a_attempts"] == 1
    assert summary["case_b_attempts"] == 2
    assert summary["case_a_lower_attempt_count"] is True
