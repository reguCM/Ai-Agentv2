"""Shadow-only Progress Classification v0 wiring tests."""
from __future__ import annotations

from ai_tool.chat_interface.agent_turn import LoopStopReason, run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.progress_classification_shadow import (
    ProgressShadowTracker,
    snapshot_from_orchestrator,
)
from ai_tool.chat_interface.semantic_stagnation_warning import (
    is_semantic_fuse_stop,
    resolve_actual_stop_reason,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)


def test_snapshot_from_orchestrator_includes_runtime_fields():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    orchestrator.observe_tool(
        "read_file",
        {"path": "a"},
        {"status": "success"},
        {"path": "a"},
        relevant_tools=["read_file"],
    )
    snap = snapshot_from_orchestrator(orchestrator)
    assert snap.evidence_count >= 1
    assert snap.requirements_total >= 1


def test_shadow_tracker_emits_comparison_fields():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    from ai_tool.chat_interface.agent_turn import LoopCounters

    counters = LoopCounters(
        stagnation_limit=3,
        same_failure_limit=2,
        no_evidence_limit=6,
        configured_tool_limit=20,
    )
    tracker = ProgressShadowTracker()
    orchestrator.observe_tool(
        "read_file",
        {"path": "missing"},
        {"status": "failure"},
        {},
        relevant_tools=["read_file"],
    )
    counters.observe(signature="read:missing", status="failure", evidence_gain=False)
    row = tracker.observe_after_tool(
        orchestrator=orchestrator,
        counters=counters,
        tool_name="read_file",
        tool_arguments={"path": "missing"},
        tool_status="failure",
        would_have_stopped_by=None,
        current_stop_reason=None,
    )
    assert row["tool_sequence"] == 1
    assert row["attempt"] == 1
    assert "goal_progress" in row
    assert "stagnation" in row
    assert row["loop_counters"]["total_tool_calls"] == 1
    assert row["would_have_stopped_by"] is None
    assert row["current_stop_reason"] is None

    counters.observe(signature="read:missing", status="failure", evidence_gain=False)
    row2 = tracker.observe_after_tool(
        orchestrator=orchestrator,
        counters=counters,
        tool_name="read_file",
        tool_arguments={"path": "missing"},
        tool_status="failure",
        would_have_stopped_by=LoopStopReason.SAME_FAILURE_LIMIT,
        current_stop_reason=None,
        semantic_bypass_applied=True,
    )
    assert row2["would_have_stopped_by"] == "SAME_FAILURE_LIMIT"
    assert row2["current_stop_reason"] is None
    assert row2["semantic_bypass_applied"] is True
    payload = tracker.as_dict()
    assert payload["observation_only"] is True
    assert payload["progress_classification_stop_connected"] is False
    assert len(payload["observations"]) == 2


def test_run_chat_turn_adds_shadow_without_changing_stop_reason(tmp_path, monkeypatch):
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
        empty_session("shadow-stagnation-stop"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    assert result["runtime_status_report"]["reason_code"] == "STAGNATION_LIMIT"
    shadow = result["progress_classification_shadow"]
    assert shadow is not None
    assert shadow["observation_only"] is True
    assert len(shadow["observations"]) == 3
    last = shadow["observations"][-1]
    assert last["would_have_stopped_by"] == "STAGNATION_LIMIT"
    assert last["current_stop_reason"] == "STAGNATION_LIMIT"
    shadow_events = [
        item for item in result["events"] if item.get("type") == "progress_classification_shadow"
    ]
    assert len(shadow_events) == 3
    assert shadow_events[-1]["would_have_stopped_by"] == "STAGNATION_LIMIT"


def test_run_chat_turn_records_would_have_stopped_by_under_warning(tmp_path, monkeypatch):
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
        empty_session("shadow-warning"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    shadow = result["progress_classification_shadow"]
    assert shadow["semantic_bypass_enabled"] is True
    assert shadow["first_bypassed_stop_reason"] == "STAGNATION_LIMIT"
    assert shadow["bypass_count"] >= 1
    stagnation_rows = [
        row
        for row in shadow["observations"]
        if row["would_have_stopped_by"] == "STAGNATION_LIMIT"
    ]
    assert stagnation_rows
    assert stagnation_rows[0]["current_stop_reason"] is None
    report = result.get("runtime_status_report") or {}
    assert report.get("reason_code") != "TOOL_HARD_LIMIT"
    assert shadow["actual_stop_reason"] != "TOOL_HARD_LIMIT"
    assert result["loop_counters"]["total_tool_calls"] == 8
