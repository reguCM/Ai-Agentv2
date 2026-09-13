"""Unit tests for tool_calling Hard Capability Bridge v0."""
from __future__ import annotations

from unittest.mock import Mock

from ai_tool.tool_calling_capability_bridge import (
    TOOL_CALLING_FALLBACK_CANDIDATES,
    apply_tool_calling_hard_capability_bridge,
    derive_required_hard_capabilities,
    worker_tool_calling_eligibility,
)


def test_derive_required_hard_capabilities_from_llm_tools_only():
    assert derive_required_hard_capabilities([]) == []
    assert derive_required_hard_capabilities(None) == []
    assert derive_required_hard_capabilities([{"type": "function"}]) == ["tool_calling"]


def test_registry_verified_supported_skips_live_probe():
    probe = Mock()
    result = apply_tool_calling_hard_capability_bridge(
        "qwen3_8b",
        llm_tools=[{"type": "function"}],
        probe_fn=probe,
    )
    probe.assert_not_called()
    assert result.routing_performed is False
    assert result.current_model_eligible is True
    assert result.selected_model == "qwen3:8b"
    assert result.capability_source == "registry_verified"
    assert result.capability_gap is False


def test_registry_verified_unsupported_routes_without_running_current_model_probe():
    probe = Mock()
    result = apply_tool_calling_hard_capability_bridge(
        "deepseek_coder_v2_16b",
        llm_tools=[{"type": "function"}],
        probe_fn=probe,
    )
    probe.assert_not_called()
    assert result.routing_performed is True
    assert result.current_model == "deepseek-coder-v2:16b"
    assert result.selected_worker_id == "qwen3_8b"
    assert result.selected_model == "qwen3:8b"
    assert result.capability_gap is False


def test_unregistered_model_with_indeterminate_probe_does_not_fallback():
    probe = Mock(
        return_value={"supported": None, "error": "model not found", "detail": "probe_failed"}
    )
    result = apply_tool_calling_hard_capability_bridge(
        "unknown-local:7b",
        llm_tools=[{"type": "function"}],
        fallback_candidates=TOOL_CALLING_FALLBACK_CANDIDATES,
        probe_fn=probe,
    )
    assert result.capability_gap is True
    assert result.routing_performed is False
    assert result.routing_reason == "current_worker_indeterminate"
    assert probe.call_count == 1


def test_no_eligible_local_worker_reports_capability_gap():
    probe = Mock(
        return_value={
            "supported": False,
            "error": "does not support tools",
            "detail": "ollama_rejected_tools_parameter",
        }
    )
    result = apply_tool_calling_hard_capability_bridge(
        "deepseek_coder_v2_16b",
        llm_tools=[{"type": "function"}],
        fallback_candidates=("deepseek_coder_v2_16b",),
        probe_fn=probe,
    )
    assert result.capability_gap is True
    assert result.routing_reason == "no_eligible_local_worker"
    probe.assert_not_called()


def test_worker_tool_calling_eligibility_marks_deepseek_ineligible():
    state, source, reason = worker_tool_calling_eligibility("deepseek_coder_v2_16b")
    assert state == "ineligible"
    assert source == "registry_verified"
    assert reason == "registry_tool_calling_unsupported"
