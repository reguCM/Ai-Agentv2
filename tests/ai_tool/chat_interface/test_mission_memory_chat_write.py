from __future__ import annotations

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.mission_memory.chat_persist import (
    bind_execution_identity,
    persist_chat_execution,
)
from ai_tool.mission_memory.store import MissionMemoryStore
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)


def test_simple_chat_does_not_write_mission_memory(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    result = run_chat_turn(
        empty_session("simple"),
        "こんにちは",
        chat_fn=_chat_sequence(_response("hello")),
        model="fake",
    )
    assert result.get("task_runtime") is None
    assert result.get("mission_memory") is None
    assert MissionMemoryStore.from_default().get_mission("m1") is None


def test_agent_turn_writes_determined_execution(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    result = run_chat_turn(
        empty_session("agent-task"),
        "repository audit plan",
        chat_fn=_chat_sequence(_response("answer")),
        model="fake",
    )
    recorded = result["mission_memory"]
    assert recorded["ok"] is True
    assert recorded["result_determination"] == "determined"
    assert recorded["execution_end_state_judgment"] == "not_judged"
    store = MissionMemoryStore.from_default()
    mission = store.get_mission(recorded["mission_id"])
    execution = store.get_execution(recorded["mission_id"], recorded["execution_id"])
    assert mission is not None
    assert mission["original_goal"] == "repository audit plan"
    assert execution is not None
    assert execution["determined_result"] == result["answer"]
    assert execution["goal_achievement_performed"] is False
    assert "goal_achievement_result" not in execution
    assert execution["correlation_id"] == result["correlation_id"]


def test_tool_evidence_is_persisted_as_new_canonical(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "data": {"x": 1}})
    chat = _chat_sequence(_response(calls=[_tool_call("read_file")]), _response("answer"))
    result = run_chat_turn(
        empty_session("evidence"), "file audit", chat_fn=chat, model="fake"
    )
    recorded = result["mission_memory"]
    assert recorded["ok"] is True
    assert recorded["new_evidence_ids"]
    store = MissionMemoryStore.from_default()
    evidence = store.get_evidence(recorded["new_evidence_ids"][0])
    assert evidence is not None
    assert evidence["observed_at"]
    assert "persisted_at" not in evidence
    assert evidence["created_by_execution_id"] == recorded["execution_id"]


def test_runtime_error_writes_undetermined_execution(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)

    def boom(**_kwargs):
        raise RuntimeError("provider down")

    result = run_chat_turn(
        empty_session("err"),
        "repository audit plan",
        chat_fn=boom,
        model="fake",
    )
    assert result.get("is_error") is True
    recorded = result["mission_memory"]
    assert recorded["ok"] is True
    assert recorded["result_determination"] == "undetermined"
    execution = MissionMemoryStore.from_default().get_execution(
        recorded["mission_id"], recorded["execution_id"]
    )
    assert execution is not None
    assert "determined_result" not in execution
    assert execution["execution_end_state_judgment"] == "not_judged"
    assert execution["stop_reason"] == "RUNTIME_ERROR"


def test_resume_keeps_mission_and_adds_execution(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    first = ChatTaskOrchestrator("c1", "同じ任務")
    first.initialize()
    bind_execution_identity(first, new_execution=True)
    persist_chat_execution(
        first,
        stop_reason="HUMAN_GRILL",
        determined=True,
        answer="pause",
        correlation_id="c1",
    )
    second = ChatTaskOrchestrator("c2", "同じ任務")
    second.initialize()
    bind_execution_identity(
        second, resume_mission_id=first.mission_id, new_execution=True
    )
    persist_chat_execution(
        second,
        stop_reason="COMPLETED",
        determined=True,
        answer="continued",
        correlation_id="c2",
    )
    store = MissionMemoryStore.from_default()
    listed = store.list_executions(first.mission_id)
    assert [item["execution_id"] for item in listed] == [
        first.execution_id,
        second.execution_id,
    ]
    assert listed[0]["execution_sequence"] == 1
    assert listed[1]["execution_sequence"] == 2
    assert listed[0]["execution_end_state"] == "paused"
    assert "execution_end_state" not in listed[1]
