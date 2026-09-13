"""Phase 2: goal continuation resume into existing Agent Loop."""
from __future__ import annotations

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.goal_continuation_resume import (
    advance_to_open_task,
    apply_failure_tail,
    is_explicit_continuation_trigger,
    restore_orchestrator_from_goal_continuation,
    validate_goal_continuation_packet,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.task_runtime import FailureRecord
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_execution_end_invariants import (
    _run_agent_false_success_llm_final_without_runtime,
)
from tests.ai_tool.chat_interface.test_gap_resolution_phase1 import _gap_event


def _continuation_event(result: dict) -> dict | None:
    for item in result.get("events") or []:
        if item.get("type") == "goal_continuation_restored":
            return item
    return None


def _run_fact_gap_with_continuation(monkeypatch, tmp_path):
    first, session = _run_agent_false_success_llm_final_without_runtime(
        monkeypatch, tmp_path
    )
    assert first.get("goal_continuation_resume") is not None
    assert session.get("awaiting_goal_continuation") is True
    routed = _gap_event(first)
    assert routed is not None
    assert routed.get("gap_kind") == "fact_gap"
    return first, session


def test_explicit_continuation_trigger_requires_marker():
    assert is_explicit_continuation_trigger("継続") is True
    assert is_explicit_continuation_trigger("continue") is True
    assert is_explicit_continuation_trigger("README.md を確認して") is False


def test_restore_helpers_reopen_incomplete_task():
    orchestrator = ChatTaskOrchestrator("restore", "request")
    orchestrator.initialize()
    orchestrator.runtime.tasks["T1"].status = "in_progress"
    orchestrator.runtime.failures.append(
        FailureRecord(
            failure_id="f1",
            task_id="T1",
            action_id="a1",
            tool_name="read_file",
            arguments={},
            failure_code="MISSING",
            evidence_gain=False,
            created_at="now",
        )
    )
    packet = {
        "kind": "goal_continuation_v0",
        "mission_id": "m-test",
        "original_request": "request",
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "failure_tail": [
            {
                "failure_id": "f-tail",
                "task_id": "T1",
                "action_id": "a-tail",
                "tool_name": "read_file",
                "arguments": {"path": "README.md"},
                "failure_code": "MISSING",
                "evidence_gain": False,
                "created_at": "now",
            }
        ],
    }
    restored = restore_orchestrator_from_goal_continuation("corr-2", packet)
    assert restored.mission_id == "m-test"
    assert restored.execution_id
    assert restored.current_task_id == "T1"
    assert any(item.failure_id == "f-tail" for item in restored.runtime.failures)


def test_goal_continuation_resume_same_mission_new_execution(monkeypatch, tmp_path):
    first, session = _run_fact_gap_with_continuation(monkeypatch, tmp_path)
    mission_id = str(first.get("mission_memory", {}).get("mission_id") or "")
    prior_execution_id = str(first.get("mission_memory", {}).get("execution_id") or "")
    assert mission_id
    assert prior_execution_id

    call_count = {"n": 0}

    def execute(name, arguments, **_kwargs):
        call_count["n"] += 1
        if name == "read_file":
            return {
                "ok": True,
                "status": "success",
                "path": arguments.get("path"),
                "content": "audit evidence line",
                "error": None,
            }
        raise AssertionError(name)

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    second = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "a.txt"})]),
            _response("a.txt を読み取り、audit summary を更新しました。"),
        ),
        model="fake",
    )

    restored = _continuation_event(second)
    assert restored is not None
    assert restored.get("mission_id") == mission_id
    assert restored.get("prior_execution_id") == prior_execution_id
    assert second.get("goal_continuation_restored") is True
    assert second.get("correlation_id") != first.get("correlation_id")
    second_mission = str(second.get("mission_memory", {}).get("mission_id") or "")
    second_execution = str(second.get("mission_memory", {}).get("execution_id") or "")
    assert second_mission == mission_id
    assert second_execution
    assert second_execution != prior_execution_id
    assert call_count["n"] >= 1
    routed = _gap_event(second)
    assert routed is not None or second.get("answer_gate") is not None


def test_unrelated_message_does_not_resume_old_mission(monkeypatch, tmp_path):
    first, session = _run_fact_gap_with_continuation(monkeypatch, tmp_path)
    mission_id = str(first.get("mission_memory", {}).get("mission_id") or "")

    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: {
            "ok": True,
            "status": "success",
            "content": "x",
        },
    )
    unrelated = run_chat_turn(
        session,
        "repository audit plan",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "a.txt"})]),
            _response("unrelated summary"),
        ),
        model="fake",
    )
    assert unrelated.get("goal_continuation_restored") is not True
    unrelated_mission = str(unrelated.get("mission_memory", {}).get("mission_id") or "")
    assert unrelated_mission
    assert unrelated_mission != mission_id
    assert session.get("awaiting_goal_continuation") is True
    assert session.get("goal_continuation_resume", {}).get("mission_id") == mission_id


def test_restore_failure_does_not_start_new_mission(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("phase2-restore-fail")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = {
        "kind": "goal_continuation_v0",
        "mission_id": "m-broken",
        "original_request": "broken request",
        "completion_runtime": {},
    }
    result = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    assert result.get("goal_continuation_restore_failed") is True
    assert result.get("mission_memory") is None
    assert session.get("awaiting_goal_continuation") is True
    assert validate_goal_continuation_packet(session["goal_continuation_resume"])


def test_successful_resume_clears_stale_awaiting_when_no_new_packet(monkeypatch, tmp_path):
    first, session = _run_fact_gap_with_continuation(monkeypatch, tmp_path)
    prior_packet = dict(session["goal_continuation_resume"])

    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: {
            "ok": True,
            "status": "success",
            "content": "done",
        },
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.observe_gap_resolution_at_execution_end",
        lambda *args, **kwargs: (None, None, None),
    )
    second = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "a.txt"})]),
            _response("audit completed with verified evidence"),
        ),
        model="fake",
    )
    assert second.get("goal_continuation_restored") is True
    assert second.get("goal_continuation_resume") is None
    assert session.get("awaiting_goal_continuation") is False
    assert session.get("goal_continuation_resume") is None
    assert prior_packet.get("mission_id") == str(
        second.get("mission_memory", {}).get("mission_id") or ""
    )
