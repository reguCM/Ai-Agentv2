from __future__ import annotations

from copy import deepcopy

import pytest

from ai_tool.dev_skill_pipeline import build_handoff_packet
from ai_tool.production_meaning_context import (
    MeaningContextError,
    build_meaning_context_v0,
    validate_meaning_context,
)


def _mission() -> dict:
    return {
        "schema_version": "1",
        "mission_id": "m-meaning-context",
        "original_goal": "Create a high-quality Tetris game.",
        "explicit_conditions": ["Core game rules work correctly."],
        "explicit_constraints": ["Use Python."],
        "user_confirmed_supplements": [],
        "structured_requirements": [
            {
                "requirement_id": "req-quality",
                "source_text": "high-quality",
                "source_span": [9, 21],
                "disposition": "AMBIGUOUS_REQUIREMENT",
                "resolution_status": "resolved",
                "normalized_meaning": "Responsive controls, correct rules, and a polished basic presentation.",
                "provenance": "human_confirmed",
                "materiality": "blocks_design",
            }
        ],
        "confirmed_clarifications": [
            {
                "decision_id": "decision-quality-v1",
                "decision_key": "quality:definition",
                "status": "confirmed",
                "source": "requirement_resolution",
                "text": "Responsive controls, correct rules, and a polished basic presentation.",
                "human_confirmed": True,
            }
        ],
    }


def _handoff() -> dict:
    return build_handoff_packet(
        initial_request="Create a high-quality Tetris game.",
        aligned_spec={
            "summary": "Implement a high-quality Tetris game.",
            "numbered_conditions": ["Core game rules work correctly."],
            "non_goals": ["Online multiplayer is not included."],
            "acceptance_criteria": ["The game satisfies the core rule checks."],
        },
        prd_rel="design/prd.md",
        tech_spec_rel="design/tech-spec.md",
        plan_rel="design/plan.md",
        todo_rel="design/todo.md",
        tech_spec={"summary": "Tetris", "modules": [{"path": "tetris/main.py"}]},
        plan={
            "tasks": [
                {
                    "id": "T1",
                    "title": "Implement Tetris.",
                    "acceptance": ["Core game rules work correctly."],
                    "verification": ["Run the core-rule tests."],
                    "affected_paths": ["tetris/main.py"],
                    "decision_premises": [
                        {
                            "decision_key": "quality:definition",
                            "derived_from_decision_id": "decision-quality-v1",
                        }
                    ],
                    "size": "S",
                    "dependencies": [],
                    "maps_to_acceptance": ["A1"],
                }
            ]
        },
        skill_steps=["write-prd", "tech-spec", "planning-and-task-breakdown", "goal-handoff"],
        handoff_slug="meaning-context",
        source_binding={
            "mission_id": "m-meaning-context",
            "requirement_ids": ["req-quality"],
        },
    )


def test_meaning_context_is_deterministic_and_preserves_both_canonicals():
    mission = _mission()
    handoff = _handoff()

    first = build_meaning_context_v0(mission, handoff)
    second = build_meaning_context_v0(deepcopy(mission), deepcopy(handoff))

    assert first == second
    assert not validate_meaning_context(first)
    assert first["identity"]["binding_status"] == "BOUND"
    assert first["identity"]["requirement_ids"] == handoff["source_binding"]["requirement_ids"]
    assert first["identity"]["decision_ids"] == ["decision-quality-v1"]
    assert first["human_meaning"]["structured_requirements"] == mission[
        "structured_requirements"
    ]
    assert first["decision_context"]["confirmed_clarifications"] == mission[
        "confirmed_clarifications"
    ]
    assert first["implementation_meaning"]["implementation_tasks"] == handoff[
        "implementation_tasks"
    ]
    assert first["status"] == "partial"
    assert "decision_context.revision" in first["missing"]
    assert "decision_context.decision_authority" in first["missing"]
    assert "identity.requirement_to_handoff_binding" not in first["missing"]
    assert "execution_context.execution_actor" in first["missing"]


def test_meaning_context_fails_closed_on_mission_handoff_identity_mismatch():
    handoff = _handoff()
    handoff["source_binding"]["mission_id"] = "m-other"

    with pytest.raises(MeaningContextError, match="source_mission_mismatch"):
        build_meaning_context_v0(_mission(), handoff)


def test_meaning_context_fails_closed_on_requirement_identity_mismatch():
    handoff = _handoff()
    handoff["source_binding"]["requirement_ids"] = ["req-other"]

    with pytest.raises(MeaningContextError, match="source_requirement_mismatch"):
        build_meaning_context_v0(_mission(), handoff)


def test_meaning_context_rejects_schema_invalid_mission():
    mission = _mission()
    mission["invented_meaning"] = "must not be accepted"

    with pytest.raises(MeaningContextError, match="invalid_mission"):
        build_meaning_context_v0(mission, _handoff())


def test_meaning_context_fails_closed_on_unknown_decision_premise():
    handoff = _handoff()
    handoff["implementation_tasks"][0]["decision_premises"][0][
        "derived_from_decision_id"
    ] = "decision-unknown"

    with pytest.raises(MeaningContextError, match="inactive_or_missing_decision_premises"):
        build_meaning_context_v0(_mission(), handoff)
