from __future__ import annotations

import copy

import pytest

from ai_tool.chat_interface.agent_turn import _attach_requirement_contract
from ai_tool.chat_interface.goal_continuation_resume import restore_orchestrator_from_goal_continuation
from ai_tool.chat_interface.requirement_resolution import (
    PHASE_REQUIREMENTS_RESOLVED,
    extract_requirement_resolution,
    project_to_runtime_adoption,
    sync_canonical_requirements_from_mission,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version


def test_g1_resolution_bundle_has_requirement_ids():
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    ids = {row.requirement_id for row in bundle.structured_requirements}
    assert ids
    assert all(str(item).strip() for item in ids)


def test_g2_g4_orchestrator_preserves_requirement_identity():
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    adopted, _ = project_to_runtime_adoption(bundle.structured_requirements)
    orchestrator = ChatTaskOrchestrator(
        "corr-1",
        bundle.original_goal,
        completion_conditions=adopted,
    )
    _attach_requirement_contract(orchestrator, bundle)
    by_id = {row["requirement_id"]: row for row in orchestrator.structured_requirements}
    for row in bundle.structured_requirements:
        stored = by_id[row.requirement_id]
        assert stored["source_text"] == row.source_text
        assert stored.get("normalized_meaning") == row.normalized_meaning
        assert stored["disposition"] == row.disposition
        assert stored["resolution_status"] == row.resolution_status


def test_g3_all_requirement_ids_preserved_for_multiple_spans():
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    expected_ids = {row.requirement_id for row in bundle.structured_requirements}
    adopted, _ = project_to_runtime_adoption(bundle.structured_requirements)
    orchestrator = ChatTaskOrchestrator(
        "corr-2",
        bundle.original_goal,
        completion_conditions=adopted or ["relevant evidence observed"],
    )
    _attach_requirement_contract(orchestrator, bundle)
    runtime_ids = {row["requirement_id"] for row in orchestrator.structured_requirements}
    assert runtime_ids == expected_ids


def test_g5_completion_condition_strings_unchanged_by_attach():
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    adopted, _ = project_to_runtime_adoption(bundle.structured_requirements)
    before = list(adopted)
    orchestrator = ChatTaskOrchestrator(
        "corr-3",
        bundle.original_goal,
        completion_conditions=before,
    )
    _attach_requirement_contract(orchestrator, bundle)
    assert list(orchestrator._completion_conditions) == before


def test_snapshot_roundtrip_preserves_structured_requirements():
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    adopted, _ = project_to_runtime_adoption(bundle.structured_requirements)
    orchestrator = ChatTaskOrchestrator(
        "corr-4",
        bundle.original_goal,
        completion_conditions=adopted,
    )
    bundle.requirement_resolution_phase = PHASE_REQUIREMENTS_RESOLVED
    _attach_requirement_contract(orchestrator, bundle)
    snap = orchestrator.snapshot()
    restored = ChatTaskOrchestrator("corr-5", bundle.original_goal)
    restored.apply_canonical_requirements_from_state(snap)
    assert {r["requirement_id"] for r in restored.structured_requirements} == {
        r.requirement_id for r in bundle.structured_requirements
    }
    assert restored.requirement_resolution_phase == PHASE_REQUIREMENTS_RESOLVED


def test_goal_continuation_restore_hydrates_from_mission(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission_memory",
    )
    bundle = extract_requirement_resolution(
        "Pythonでテトリスを作って",
        use_heuristic_only=True,
    )
    mission_id = "m-transport-1"
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
    orchestrator = restore_orchestrator_from_goal_continuation("corr-6", packet)
    assert {r["requirement_id"] for r in orchestrator.structured_requirements} == {
        r.requirement_id for r in bundle.structured_requirements
    }
