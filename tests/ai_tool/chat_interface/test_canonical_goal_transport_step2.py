from __future__ import annotations

import copy

from ai_tool.chat_interface.agent_turn import _attach_requirement_contract
from ai_tool.chat_interface.goal_continuation_resume import restore_orchestrator_from_goal_continuation
from ai_tool.chat_interface.requirement_resolution import (
    PHASE_AWAITING_HUMAN,
    PHASE_REQUIREMENTS_RESOLVED,
    extract_requirement_resolution,
    project_to_runtime_adoption,
    project_to_runtime_adoption_entries,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version


def _resolved_python_tetris_bundle():
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    assert bundle.requirement_resolution_phase == PHASE_REQUIREMENTS_RESOLVED
    return bundle


def test_t1_single_requirement_maps_to_condition():
    bundle = _resolved_python_tetris_bundle()
    goal_row = next(row for row in bundle.structured_requirements if row.disposition == "GOAL")
    adopted, _ = project_to_runtime_adoption(bundle.structured_requirements)
    orchestrator = ChatTaskOrchestrator("t1", bundle.original_goal, completion_conditions=adopted)
    _attach_requirement_contract(orchestrator, bundle)
    mapping = {row["requirement_id"]: row["completion_condition"] for row in orchestrator.canonical_requirement_projection}
    assert goal_row.requirement_id in mapping
    assert mapping[goal_row.requirement_id] in adopted


def test_t2_multiple_requirements_preserve_id_condition_pairs():
    bundle = _resolved_python_tetris_bundle()
    adopted, _ = project_to_runtime_adoption(bundle.structured_requirements)
    orchestrator = ChatTaskOrchestrator("t2", bundle.original_goal, completion_conditions=adopted)
    _attach_requirement_contract(orchestrator, bundle)
    entries = project_to_runtime_adoption_entries(bundle.structured_requirements)
    assert orchestrator.canonical_requirement_projection == entries
    assert {row["completion_condition"] for row in entries}.issubset(set(adopted))


def test_t3_unprojected_requirement_not_in_mapping():
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    assert bundle.requirement_resolution_phase == PHASE_AWAITING_HUMAN
    ambiguous = next(row for row in bundle.structured_requirements if row.source_text == "簡単な")
    orchestrator = ChatTaskOrchestrator(
        "t3",
        bundle.original_goal,
        completion_conditions=["placeholder"],
    )
    _attach_requirement_contract(orchestrator, bundle)
    mapped_ids = {row["requirement_id"] for row in orchestrator.canonical_requirement_projection}
    assert ambiguous.requirement_id not in mapped_ids
    assert len(orchestrator.structured_requirements) >= 2


def test_t4_project_to_runtime_adoption_strings_unchanged():
    bundle = _resolved_python_tetris_bundle()
    conditions, constraints = project_to_runtime_adoption(bundle.structured_requirements)
    expected_conditions = [
        row["completion_condition"] for row in project_to_runtime_adoption_entries(bundle.structured_requirements)
    ]
    assert conditions == expected_conditions
    assert any("Python" in item for item in constraints)


def test_t5_projection_matches_completion_conditions_on_orchestrator():
    bundle = _resolved_python_tetris_bundle()
    adopted, _ = project_to_runtime_adoption(bundle.structured_requirements)
    orchestrator = ChatTaskOrchestrator("t5", bundle.original_goal, completion_conditions=adopted)
    _attach_requirement_contract(orchestrator, bundle)
    projected_strings = [row["completion_condition"] for row in orchestrator.canonical_requirement_projection]
    assert projected_strings == adopted


def test_t8_resume_rebuilds_projection_from_mission_structured_requirements(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission_memory",
    )
    bundle = _resolved_python_tetris_bundle()
    mission_id = "m-step2-resume"
    mission = {
        "schema_version": schema_version(),
        "mission_id": mission_id,
        "original_goal": bundle.original_goal,
        "explicit_conditions": [],
        "explicit_constraints": [],
        "user_confirmed_supplements": [],
        "structured_requirements": [row.as_dict() for row in bundle.structured_requirements],
        "requirement_resolution_phase": PHASE_REQUIREMENTS_RESOLVED,
        "completion_runtime": {
            "current_goal_id": "G1.1",
            "current_task_id": "T1",
            "goals": [],
            "tasks": [
                {
                    "task_id": "T1",
                    "goal_id": "G1.1",
                    "title": "Observe",
                    "status": "in_progress",
                    "satisfied_conditions": [],
                    "condition_status": {},
                    "condition_evidence": {},
                    "evidence_ids": [],
                }
            ],
            "evidence": [],
        },
    }
    store = MissionMemoryStore.from_default()
    store.put_mission(mission)
    packet = {
        "kind": "goal_continuation_v0",
        "mission_id": mission_id,
        "original_request": bundle.original_goal,
        "completion_runtime": copy.deepcopy(mission["completion_runtime"]),
    }
    orchestrator = restore_orchestrator_from_goal_continuation("t8", packet)
    expected = project_to_runtime_adoption_entries(bundle.structured_requirements)
    assert orchestrator.canonical_requirement_projection == expected
