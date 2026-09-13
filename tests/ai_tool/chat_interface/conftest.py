"""Chat テストが本番 spec_proposals を汚さない。"""
from __future__ import annotations

import pytest

import ai_tool.tool_calling_capability_bridge as tool_calling_bridge


def _is_test_double_model(identifier: str | None) -> bool:
    token = str(identifier or "").strip().casefold()
    return token.startswith("fake") or token.startswith("mock")


@pytest.fixture(autouse=True)
def _spec_proposal_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path / "spec_proposals"))
    monkeypatch.setenv("AI_AGENT_EXECUTION_CASES_DIR", str(tmp_path / "execution_cases"))
    monkeypatch.setenv("AI_AGENT_MISSION_MEMORY_DIR", str(tmp_path / "mission_memory"))
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")


@pytest.fixture(autouse=True)
def _tool_calling_bridge_test_double_passthrough(monkeypatch):
    real_apply = tool_calling_bridge.apply_tool_calling_hard_capability_bridge

    def _apply(current_model, *, llm_tools=None, **kwargs):
        provider = tool_calling_bridge.resolve_provider_model_name(current_model)
        if _is_test_double_model(current_model) or _is_test_double_model(provider):
            required = tool_calling_bridge.derive_required_hard_capabilities(llm_tools)
            if not required:
                return real_apply(current_model, llm_tools=llm_tools, **kwargs)
            worker_id = tool_calling_bridge.resolve_registry_worker_id(provider)
            return tool_calling_bridge.ToolCallingBridgeResult(
                required_capabilities=required,
                current_model=provider,
                current_worker_id=worker_id,
                current_model_eligible=True,
                selected_model=provider,
                selected_worker_id=worker_id,
                routing_performed=False,
                routing_reason="test_double_passthrough",
                capability_source="not_applicable",
                capability_gap=False,
                gap_reason=None,
                execution_profile=kwargs.get("execution_profile"),
                bridge_applied=False,
            )
        return real_apply(current_model, llm_tools=llm_tools, **kwargs)

    monkeypatch.setattr(
        tool_calling_bridge,
        "apply_tool_calling_hard_capability_bridge",
        _apply,
    )
