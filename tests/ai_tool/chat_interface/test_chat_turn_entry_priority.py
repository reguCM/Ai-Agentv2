"""run_chat_turn entry priority: RR/Grill replies vs continuation vs new Goal."""
from __future__ import annotations

import json

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.requirement_decomposition import decompose_requirements
from ai_tool.chat_interface.requirement_resolution import (
    PHASE_AWAITING_HUMAN,
    extract_requirement_resolution,
)
from ai_tool.chat_interface.requirement_resolution_grill import (
    launch_requirement_resolution_grill,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator, has_creation_intent
from ai_tool.mission_memory.store import MissionMemoryStore
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_goal_continuation_requirement_gate import (
    _continuation_packet,
    _mission_record,
    _setup_store,
)


def _grill_align_chat(**kwargs):
    system = "\n".join(
        str(row.get("content") or "")
        for row in (kwargs.get("messages") or [])
        if row.get("role") == "system"
    )
    if "scoring a grill-me interview" in system:
        content = json.dumps(
            {
                "dimensions": {
                    key: 0
                    for key in ("goals", "acceptance", "boundaries", "alternatives", "assumptions")
                },
                "aggregate": 0,
                "weakest": [],
                "ready_to_exit": True,
                "aligned_spec": {
                    "summary": "aligned",
                    "numbered_conditions": ["Pythonでテトリスを作る"],
                    "non_goals": [],
                    "acceptance_criteria": ["最小実装"],
                },
            },
            ensure_ascii=False,
        )
    else:
        content = "{}"
    return type("R", (), {"message": type("M", (), {"content": content})()})()


def test_t1_requirement_resolution_reply_does_not_seed_new_goal(tmp_path, monkeypatch):
    _setup_store(monkeypatch, tmp_path)
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    assert bundle.requirement_resolution_phase == PHASE_AWAITING_HUMAN
    mission_id = "m-entry-rr"
    store = MissionMemoryStore.from_default()
    store.put_mission(_mission_record(mission_id, bundle))
    launched = launch_requirement_resolution_grill(
        mission_id=mission_id,
        original_request="簡単なテトリスを作って",
        bundle=bundle,
    )
    assert launched is not None
    session = empty_session("entry-t1")
    session["awaiting_requirement_resolution"] = True
    session["requirement_resolution_state"] = launched["state"]

    seed = {"n": 0}

    def wrapped(*args, **kwargs):
        seed["n"] += 1
        return decompose_requirements(*args, **kwargs)

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        wrapped,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._chat_turn",
        lambda *_a, **_k: {"route": "chat", "answer": "seeded", "events": [], "tool_used": False, "tools": []},
    )
    result = run_chat_turn(
        session,
        "最小実装でよい",
        chat_fn=_grill_align_chat,
        model="fake",
    )
    assert seed["n"] == 0
    assert result.get("goal_continuation_restored") is not True
    event_missions = {
        str(item.get("mission_id") or "")
        for item in (result.get("events") or [])
        if item.get("mission_id")
    }
    assert mission_id in event_missions
    assert store.get_mission(mission_id).get("original_goal") == "簡単なテトリスを作って"


def test_t2_production_grill_reply_does_not_seed_new_goal(tmp_path, monkeypatch):
    _setup_store(monkeypatch, tmp_path)
    mission_id = "m-entry-grill"
    store = MissionMemoryStore.from_default()
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    store.put_mission(_mission_record(mission_id, bundle))
    session = empty_session("entry-t2")
    session["awaiting_production_grill_me"] = True
    session["production_grill_me_state"] = {
        "mission_id": mission_id,
        "original_request": "Pythonでテトリスを作って",
        "transcript": [],
        "active_contract": {
            "question_id": "production_grill_me:r1",
            "question": "完成条件は？",
            "dimension": "acceptance",
            "decision_key": "spec:acceptance",
            "decision_subject": "acceptance",
        },
    }
    seed = {"n": 0}
    original = ChatTaskOrchestrator.__init__

    def wrapped(self, *args, **kwargs):
        seed["n"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ChatTaskOrchestrator, "__init__", wrapped)
    result = run_chat_turn(
        session,
        "repository audit plan",
        chat_fn=_grill_align_chat,
        model="fake",
    )
    assert seed["n"] == 0
    assert result.get("goal_continuation_restored") is not True
    assert result.get("awaiting_production_grill_me") is False or result.get("aligned_spec")


def test_t3_explicit_continuation_resumes_existing_mission(tmp_path, monkeypatch):
    _setup_store(monkeypatch, tmp_path)
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    mission_id = "m-entry-cont"
    store = MissionMemoryStore.from_default()
    store.put_mission(_mission_record(mission_id, bundle))
    orch = ChatTaskOrchestrator("c1", "Pythonでテトリスを作って")
    orch.mission_id = mission_id
    orch.initialize()
    session = empty_session("entry-t3")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = _continuation_packet(orch, mission_id)
    agent_calls = {"n": 0}

    def fake_turn(*_a, **_k):
        agent_calls["n"] += 1
        return {
            "route": "chat",
            "answer": "ok",
            "events": [],
            "tool_used": False,
            "tools": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._chat_turn", fake_turn)
    result = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(_response("done")),
        model="fake",
    )
    assert agent_calls["n"] == 1
    assert not result.get("awaiting_requirement_resolution")
    assert not result.get("awaiting_production_grill_me")


def test_t4_unrelated_agent_request_starts_new_goal_without_resume(tmp_path, monkeypatch):
    _setup_store(monkeypatch, tmp_path)
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    mission_id = "m-entry-old"
    store = MissionMemoryStore.from_default()
    store.put_mission(_mission_record(mission_id, bundle))
    orch = ChatTaskOrchestrator("c1", "Pythonでテトリスを作って")
    orch.mission_id = mission_id
    orch.initialize()
    session = empty_session("entry-t4")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = _continuation_packet(orch, mission_id)
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "content": "x"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: {"ok": True, "status": "success", "content": "x"},
    )
    result = run_chat_turn(
        session,
        "repository audit plan",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "a.txt"})]),
            _response("unrelated summary"),
        ),
        model="fake",
    )
    assert result.get("goal_continuation_restored") is not True
    new_mission = str((result.get("mission_memory") or {}).get("mission_id") or "")
    assert new_mission
    assert new_mission != mission_id
    assert session.get("awaiting_goal_continuation") is True
    assert session.get("goal_continuation_resume", {}).get("mission_id") == mission_id


def test_t5_idle_creation_goal_can_start_production_grill_phase1(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("entry-t5")
    assert not session.get("awaiting_requirement_resolution")
    assert not session.get("awaiting_production_grill_me")
    assert not session.get("awaiting_goal_continuation")
    assert has_creation_intent("Pythonでテトリスを作って")
    result = run_chat_turn(
        session,
        "Pythonでテトリスを作って",
        chat_fn=_grill_align_chat,
        model="fake",
    )
    events = [str(item.get("type") or "") for item in (result.get("events") or [])]
    assert result.get("awaiting_production_grill_me") or result.get("aligned_spec")
    assert any(
        name in {"production_grill_me_awaiting_human", "production_grill_me_aligned"}
        for name in events
    )
