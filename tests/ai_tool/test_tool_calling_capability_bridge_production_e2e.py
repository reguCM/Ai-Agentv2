"""Production-path E2E for tool_calling Hard Capability Bridge v0."""
from __future__ import annotations

from ai_tool.chat_interface.agent_turn import LoopStopReason, run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)


def _bridge_event(result: dict) -> dict:
    for item in result.get("events") or []:
        if item.get("type") == "tool_calling_capability_bridge":
            return item
    raise AssertionError("tool_calling_capability_bridge event not found")


def _models_seen(chat_fn) -> list[str]:
    seen: list[str] = []

    def _recording_chat(**kwargs):
        seen.append(str(kwargs.get("model") or ""))
        return chat_fn(**kwargs)

    _recording_chat.models_seen = seen
    return _recording_chat


def test_case_a_eligible_current_worker_no_routing(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "data": {"x": 1}})
    chat = _chat_sequence(
        _response(calls=[_tool_call("read_file", {"path": "a.txt"})]),
        _response("done"),
    )
    recording = _models_seen(chat)
    result = run_chat_turn(
        empty_session("bridge-case-a"),
        "file audit",
        chat_fn=recording,
        model="qwen3_8b",
    )

    bridge = _bridge_event(result)
    assert bridge["required_capabilities"] == ["tool_calling"]
    assert bridge["routing_performed"] is False
    assert bridge["current_model_eligible"] is True
    assert bridge["capability_source"] == "registry_verified"
    assert bridge["selected_model"] == "qwen3:8b"
    assert recording.models_seen
    assert all(model == "qwen3:8b" for model in recording.models_seen)
    assert result.get("error") is None
    assert bridge["capability_gap"] is False
    assert result.get("tool_used") is True


def test_case_b_ineligible_current_worker_is_skipped_before_llm(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "data": {"x": 1}})
    chat = _chat_sequence(
        _response(calls=[_tool_call("read_file", {"path": "a.txt"})]),
        _response("done"),
    )
    recording = _models_seen(chat)
    result = run_chat_turn(
        empty_session("bridge-case-b"),
        "file audit",
        chat_fn=recording,
        model="deepseek_coder_v2_16b",
    )

    bridge = _bridge_event(result)
    assert bridge["routing_performed"] is True
    assert bridge["current_model"] == "deepseek-coder-v2:16b"
    assert bridge["current_model_eligible"] is False
    assert bridge["selected_worker_id"] == "qwen3_8b"
    assert recording.models_seen
    assert "deepseek-coder-v2:16b" not in recording.models_seen
    assert all(model == "qwen3:8b" for model in recording.models_seen)
    assert result.get("error") is None


def test_case_c_no_eligible_worker_stops_without_llm(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.tool_calling_capability_bridge.TOOL_CALLING_FALLBACK_CANDIDATES",
        (),
    )

    def _must_not_run(**_kwargs):
        raise AssertionError("LLM must not run when capability gap is explicit")

    result = run_chat_turn(
        empty_session("bridge-case-c"),
        "file audit",
        chat_fn=_must_not_run,
        model="deepseek_coder_v2_16b",
    )

    bridge = _bridge_event(result)
    assert bridge["capability_gap"] is True
    assert bridge["routing_performed"] is False
    assert result["runtime_status_report"]["reason_code"] == LoopStopReason.HARD_CAPABILITY_GAP.value
    assert result["runtime_status_report"]["status"] == "BLOCKED"
    assert result.get("error") is None
    assert result["tool_used"] is False
