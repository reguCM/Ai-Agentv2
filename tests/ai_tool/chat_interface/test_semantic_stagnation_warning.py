"""Semantic stagnation warning — observation-period continue-on-warning tests."""
from __future__ import annotations

from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import LoopStopReason, run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.progress_classification_v0 import (
    ProgressStateSnapshot,
    classify_progress_transition,
)
from ai_tool.chat_interface.agent_turn import LoopCounters
from ai_tool.chat_interface.semantic_stagnation_warning import (
    SemanticStagnationWarningTracker,
    active_semantic_warnings,
    is_semantic_fuse_stop,
    resolve_actual_stop_reason,
    semantic_warning_enabled_from_pipeline,
)
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)


def test_semantic_warning_helpers():
    assert is_semantic_fuse_stop(LoopStopReason.STAGNATION_LIMIT) is True
    assert is_semantic_fuse_stop(LoopStopReason.TOOL_HARD_LIMIT) is False
    assert (
        resolve_actual_stop_reason(
            LoopStopReason.STAGNATION_LIMIT,
            semantic_warning_enabled=True,
        )
        is None
    )
    assert (
        resolve_actual_stop_reason(
            LoopStopReason.STAGNATION_LIMIT,
            semantic_warning_enabled=False,
        )
        is LoopStopReason.STAGNATION_LIMIT
    )
    assert semantic_warning_enabled_from_pipeline({}) is False
    assert (
        semantic_warning_enabled_from_pipeline(
            {"semantic_stagnation_warning_enabled": True}
        )
        is True
    )
    assert (
        semantic_warning_enabled_from_pipeline(
            {"semantic_stagnation_warning_enabled": False}
        )
        is False
    )


def test_active_semantic_warnings_lists_all_thresholds():
    counters = LoopCounters(
        stagnation_limit=3,
        same_failure_limit=9,
        no_evidence_limit=4,
        configured_tool_limit=20,
    )
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    assert active_semantic_warnings(counters) == [
        "STAGNATION_LIMIT",
        "NO_EVIDENCE_LIMIT",
    ]
    assert counters.stop_reason() is LoopStopReason.STAGNATION_LIMIT


def test_warning_tracker_collects_post_warning_progress():
    tracker = SemanticStagnationWarningTracker()
    stable = ProgressStateSnapshot(
        satisfied_conditions=["relevant evidence observed"],
        unsatisfied_conditions=["answer produced"],
        verified_evidence_ids=["E1"],
    )
    classification = classify_progress_transition(None, stable)
    payload = tracker.observe_fuse_trigger(
        would_have_stopped_by=LoopStopReason.STAGNATION_LIMIT,
        tool_sequence=3,
        counters=SimpleNamespace(
            stagnation_count=3,
            same_failure_count=0,
            no_evidence_count=2,
            total_tool_calls=3,
        ),
        classification=classification,
        action_signature='{"tool":"read_file"}',
        failure_signature=None,
        state_key=("stable",),
    )
    assert payload is not None
    assert payload["display"] is True
    assert payload["warning_reason"] == "STAGNATION_LIMIT"
    assert tracker.first_warning_tool_sequence == 3

    growing = ProgressStateSnapshot(
        satisfied_conditions=["relevant evidence observed"],
        unsatisfied_conditions=[],
        verified_evidence_ids=["E1", "E2"],
    )
    tracker.observe_post_warning_step(
        classification=classify_progress_transition(stable, growing),
        action_signature='{"tool":"search_files"}',
    )
    tracker.finalize(
        actual_stop_reason=LoopStopReason.STAGNATION_LIMIT,
        orchestrator=None,
    )
    summary = tracker.as_dict()["post_warning_summary"]
    assert summary["tools_after_warning"] == 1
    assert summary["observation_progress_after_warning"] is True
    assert summary["action_changed_after_warning"] is True
    assert summary["final_stop_reason"] == "STAGNATION_LIMIT"


def test_run_chat_turn_warns_and_continues_past_semantic_fuse(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 3,
            "agent_same_failure_limit": 3,
            "agent_no_evidence_limit": 6,
            "semantic_stagnation_warning_enabled": True,
        },
    )
    responses = []
    for _index in range(8):
        responses.append(
            _response(calls=[_tool_call("read_file", {"path": "PROJECT_SPEC.md"})])
        )
    responses.append(_response("done"))
    result = run_chat_turn(
        empty_session("semantic-warning"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    warning = result["semantic_stagnation_warning"]
    assert warning is not None
    assert warning["first_warning_reason"] == "STAGNATION_LIMIT"
    assert warning["first_warning_tool_sequence"] == 4
    assert warning["semantic_warning_mode"] is True
    assert warning["production_semantic_fuse_stop_connected"] is False
    assert warning["progress_classification_stop_connected"] is False
    assert "STAGNATION_LIMIT" in warning["last_active_semantic_warnings"]
    assert warning["user_message"] is not None
    report = result.get("runtime_status_report") or {}
    assert report.get("reason_code") != "TOOL_HARD_LIMIT"
    assert result["loop_counters"]["total_tool_calls"] == 8
    warning_events = [
        item
        for item in result["events"]
        if item.get("type") == "semantic_stagnation_warning"
    ]
    assert len(warning_events) == 1
    assert warning_events[0]["display"] is True
    shadow = result["progress_classification_shadow"]
    assert shadow["first_bypassed_stop_reason"] == "STAGNATION_LIMIT"
    assert shadow["actual_stop_reason"] != "TOOL_HARD_LIMIT"


def test_run_chat_turn_stops_on_semantic_fuse_when_warning_disabled(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 2,
            "agent_same_failure_limit": 3,
            "agent_no_evidence_limit": 6,
            "semantic_stagnation_warning_enabled": False,
        },
    )
    responses = [
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(""),
    ]
    result = run_chat_turn(
        empty_session("semantic-fuse-stop"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    assert result["runtime_status_report"]["reason_code"] == "STAGNATION_LIMIT"
    assert result["semantic_stagnation_warning"]["warning_count"] == 0
