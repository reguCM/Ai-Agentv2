from __future__ import annotations

import os
import pytest

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.requirement_resolution import (
    PHASE_AWAITING_HUMAN,
    PHASE_REQUIREMENTS_RESOLVED,
    extract_requirement_resolution,
    project_to_runtime_adoption,
    requirements_block_implementation_entry,
    segment_original_goal,
)
from ai_tool.chat_interface.task_orchestration import is_agent_task
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version, validate_mission


def _prepare(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions"
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission_memory",
    )
    monkeypatch.setenv("AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC", "1")


def test_creation_intent_is_agent_task():
    assert is_agent_task("簡単なテトリスを作って")


def test_segment_simple_tetris_covers_original():
    goal = "簡単なテトリスを作って"
    spans = segment_original_goal(goal)
    assert "".join(span.text for span in spans) == goal
    assert any(span.text == "簡単な" for span in spans)


def test_extract_simple_tetris_blocks_implementation():
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    assert bundle.original_goal == "簡単なテトリスを作って"
    assert any(row.source_text == "簡単な" for row in bundle.structured_requirements)
    assert bundle.requirement_resolution_phase == PHASE_AWAITING_HUMAN
    assert requirements_block_implementation_entry(
        bundle.requirement_resolution_phase,
        bundle.structured_requirements,
    )


def test_python_constraint_projection():
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    conditions, constraints = project_to_runtime_adoption(bundle.structured_requirements)
    assert bundle.requirement_resolution_phase == PHASE_REQUIREMENTS_RESOLVED
    assert any("Python" in item for item in constraints)
    assert any("テトリス" in item for item in conditions)


def test_prohibition_subtype():
    bundle = extract_requirement_resolution(
        "赤いボタンは絶対に消さないでテトリスを作って",
        use_heuristic_only=True,
    )
    prohibition = next(
        row
        for row in bundle.structured_requirements
        if row.constraint_subtype == "prohibition"
    )
    assert "消さない" in prohibition.source_text
    _, constraints = project_to_runtime_adoption(bundle.structured_requirements)
    assert any(item.startswith("PROHIBITION:") for item in constraints)


def test_mission_schema_accepts_structured_requirements():
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    mission = {
        "schema_version": schema_version(),
        "mission_id": "m-req-1",
        "explicit_conditions": [],
        "explicit_constraints": [],
        "user_confirmed_supplements": [],
        **bundle.as_mission_fields(),
    }
    assert validate_mission(mission).verdict == "ACCEPT"


def test_run_chat_turn_blocks_then_resumes_e2e(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    agent_turn_calls = {"n": 0}

    def fake_chat_turn(*_args, **_kwargs):
        agent_turn_calls["n"] += 1
        return {
            "route": "chat",
            "answer": "implemented",
            "events": [],
            "tool_used": False,
            "tools": [],
            "task_runtime": {"status": "ok"},
        }

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._chat_turn",
        fake_chat_turn,
    )
    session = empty_session()
    def noop_chat(**_kwargs):
        return type("R", (), {"message": type("M", (), {"content": "{}"})()})()

    first = run_chat_turn(
        session,
        "簡単なテトリスを作って",
        chat_fn=noop_chat,
        model="test-model",
    )
    assert first.get("awaiting_requirement_resolution") is True
    assert agent_turn_calls["n"] == 0
    mission_id = (first.get("mission_memory") or {}).get("mission_id")
    assert mission_id
    store = MissionMemoryStore.from_default()
    mission = store.get_mission(mission_id)
    assert mission is not None
    assert mission.get("original_goal") == "簡単なテトリスを作って"
    assert mission.get("requirement_resolution_phase") == PHASE_AWAITING_HUMAN

    second = run_chat_turn(
        session,
        "最小の落下テトリスで十分",
        chat_fn=noop_chat,
        model="test-model",
    )
    assert second.get("awaiting_requirement_resolution") is False
    assert agent_turn_calls["n"] == 1
    mission = store.get_mission(mission_id)
    assert mission.get("requirement_resolution_phase") == PHASE_REQUIREMENTS_RESOLVED
    assert any(
        row.get("provenance") == "human_confirmed"
        for row in (mission.get("structured_requirements") or [])
        if row.get("source_text") == "簡単な"
    )
