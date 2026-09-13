"""Goal continuation must honor mission requirement_resolution gate (read-only)."""
from __future__ import annotations

import copy

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.requirement_resolution import (
    PHASE_AWAITING_HUMAN,
    PHASE_REQUIREMENTS_RESOLVED,
    extract_requirement_resolution,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)


def _mission_record(mission_id: str, bundle, **extra):
    record = {
        "schema_version": schema_version(),
        "mission_id": mission_id,
        "explicit_conditions": [],
        "explicit_constraints": [],
        "user_confirmed_supplements": [],
        **bundle.as_mission_fields(),
        **extra,
    }
    return record


def _continuation_packet(orchestrator: ChatTaskOrchestrator, mission_id: str) -> dict:
    return {
        "kind": "goal_continuation_v0",
        "mission_id": mission_id,
        "original_request": orchestrator.request,
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "failure_tail": [],
        "prior_execution_id": orchestrator.execution_id,
        "prior_correlation_id": "prior-corr",
        "gap_kind": "fact_gap",
        "router_winner": "tool_evidence",
    }


def _setup_store(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC", "1")
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission_memory",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions"
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )


def test_a_resolved_continuation_allowed(tmp_path, monkeypatch):
    _setup_store(monkeypatch, tmp_path)
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    assert bundle.requirement_resolution_phase == PHASE_REQUIREMENTS_RESOLVED
    mission_id = "m-resolved-gate"
    store = MissionMemoryStore.from_default()
    store.put_mission(_mission_record(mission_id, bundle))

    orch = ChatTaskOrchestrator("c1", "Pythonでテトリスを作って")
    orch.mission_id = mission_id
    orch.initialize()
    session = empty_session("gc-resolved")
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


def test_b_unresolved_continuation_blocked(tmp_path, monkeypatch):
    _setup_store(monkeypatch, tmp_path)
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    assert bundle.requirement_resolution_phase == PHASE_AWAITING_HUMAN
    mission_id = "m-blocked-gate"
    store = MissionMemoryStore.from_default()
    mission_before = _mission_record(mission_id, bundle)
    store.put_mission(mission_before)

    orch = ChatTaskOrchestrator("c1", "簡単なテトリスを作って")
    orch.mission_id = mission_id
    orch.initialize()
    session = empty_session("gc-blocked")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = _continuation_packet(orch, mission_id)

    agent_calls = {"n": 0}
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._chat_turn",
        lambda *_a, **_k: agent_calls.__setitem__("n", agent_calls["n"] + 1),
    )
    result = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(_response("{}")),
        model="fake",
    )
    assert agent_calls["n"] == 0
    assert result.get("awaiting_requirement_resolution") is True
    mission_after = store.get_mission(mission_id)
    assert mission_after.get("original_goal") == mission_before["original_goal"]
    assert mission_after.get("structured_requirements") == mission_before["structured_requirements"]


def test_c_resolve_then_continuation_allowed(tmp_path, monkeypatch):
    _setup_store(monkeypatch, tmp_path)
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    mission_id = "m-resolve-then-go"
    store = MissionMemoryStore.from_default()
    store.put_mission(_mission_record(mission_id, bundle))

    orch = ChatTaskOrchestrator("c1", "簡単なテトリスを作って")
    orch.mission_id = mission_id
    orch.initialize()
    session = empty_session("gc-resolve")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = _continuation_packet(orch, mission_id)

    agent_calls = {"n": 0}
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._chat_turn",
        lambda *_a, **_k: (agent_calls.__setitem__("n", agent_calls["n"] + 1), {
            "route": "chat",
            "answer": "ok",
            "events": [],
            "tool_used": False,
            "tools": [],
        })[1],
    )
    blocked = run_chat_turn(session, "継続", chat_fn=_chat_sequence(_response("{}")), model="fake")
    assert blocked.get("awaiting_requirement_resolution") is True
    assert agent_calls["n"] == 0

    run_chat_turn(
        session,
        "最小実装でよい",
        chat_fn=_chat_sequence(_response("{}")),
        model="fake",
    )
    assert store.get_mission(mission_id).get("requirement_resolution_phase") == (
        PHASE_REQUIREMENTS_RESOLVED
    )

    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = _continuation_packet(orch, mission_id)
    agent_calls["n"] = 0
    third = run_chat_turn(
        session,
        "継続",
        chat_fn=_chat_sequence(_response("done")),
        model="fake",
    )
    assert agent_calls["n"] == 1
    assert not third.get("awaiting_requirement_resolution")


def test_d_preservation_no_regeneration(tmp_path, monkeypatch):
    _setup_store(monkeypatch, tmp_path)
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    mission_id = "m-preserve"
    store = MissionMemoryStore.from_default()
    mission = _mission_record(mission_id, bundle)
    store.put_mission(mission)
    snapshot = copy.deepcopy(mission)

    orch = ChatTaskOrchestrator("c1", snapshot["original_goal"])
    orch.mission_id = mission_id
    orch.initialize()
    session = empty_session("gc-preserve")
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = _continuation_packet(orch, mission_id)

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._chat_turn",
        lambda *_a, **_k: {"route": "chat", "answer": "", "events": [], "tool_used": False, "tools": []},
    )
    run_chat_turn(session, "継続", chat_fn=_chat_sequence(_response("{}")), model="fake")
    after = store.get_mission(mission_id)
    assert after["original_goal"] == snapshot["original_goal"]
    assert len(after["structured_requirements"]) == len(snapshot["structured_requirements"])
    for before_row, after_row in zip(
        snapshot["structured_requirements"],
        after["structured_requirements"],
    ):
        assert before_row["source_text"] == after_row["source_text"]
        assert before_row.get("provenance") == after_row.get("provenance")
