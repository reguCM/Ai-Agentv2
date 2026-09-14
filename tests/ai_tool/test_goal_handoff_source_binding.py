from __future__ import annotations

import copy

from ai_tool.chat_interface.chat_session import empty_session, load_session, save_session
from ai_tool.dev_skill_pipeline import build_handoff_packet, validate_handoff_packet
from ai_tool.goal_handoff_source_binding import (
    build_handoff_source_binding,
    validate_handoff_source_binding,
)


def _mission(mission_id: str = "m-source") -> dict:
    return {
        "mission_id": mission_id,
        "structured_requirements": [
            {"requirement_id": "req-goal"},
            {"requirement_id": "req-quality"},
        ],
    }


def _packet(binding: dict) -> dict:
    return build_handoff_packet(
        initial_request="build the requested program",
        aligned_spec={
            "summary": "build the requested program",
            "numbered_conditions": ["implement the goal"],
            "non_goals": [],
            "acceptance_criteria": ["the goal is implemented"],
        },
        prd_rel="design/prd.md",
        tech_spec_rel="design/tech-spec.md",
        plan_rel="design/plan.md",
        todo_rel="design/todo.md",
        tech_spec={"summary": "build", "modules": [{"path": "app/main.py"}]},
        plan={"tasks": [{"id": "T1", "title": "build", "size": "S"}]},
        skill_steps=["goal-handoff"],
        source_binding=binding,
    )


def test_mission_requirements_produce_stable_schema_valid_binding() -> None:
    mission = _mission()
    first = build_handoff_source_binding(mission)
    second = build_handoff_source_binding(copy.deepcopy(mission))
    packet = _packet(first)

    assert first == second
    assert first == {
        "mission_id": "m-source",
        "requirement_ids": ["req-goal", "req-quality"],
    }
    assert validate_handoff_packet(packet) == []
    assert validate_handoff_source_binding(packet, mission) == []


def test_source_binding_fails_closed_for_mission_mismatch() -> None:
    packet = _packet(build_handoff_source_binding(_mission()))

    assert validate_handoff_source_binding(packet, _mission("m-other")) == [
        "source_mission_mismatch"
    ]


def test_source_binding_fails_closed_for_requirement_mismatch() -> None:
    mission = _mission()
    packet = _packet(build_handoff_source_binding(mission))
    packet["source_binding"]["requirement_ids"][1] = "req-unknown"

    assert validate_handoff_source_binding(packet, mission) == [
        "source_requirement_mismatch"
    ]


def test_schema_rejects_duplicate_requirement_references() -> None:
    binding = build_handoff_source_binding(_mission())
    binding["requirement_ids"] = ["req-goal", "req-goal"]

    errors = validate_handoff_packet(_packet(binding))

    assert any("non-unique" in error for error in errors)


def test_binding_survives_session_save_and_reload(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path)
    packet = _packet(build_handoff_source_binding(_mission()))
    session = empty_session("source-binding")
    session["production_handoff_packet"] = packet
    save_session(session)
    restored = load_session("source-binding")

    assert restored["production_handoff_packet"]["source_binding"] == packet[
        "source_binding"
    ]
