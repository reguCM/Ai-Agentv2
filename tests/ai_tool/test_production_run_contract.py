from __future__ import annotations

from copy import deepcopy

from ai_tool.production_meaning_context import build_meaning_context_v0, resume_meaning_projection
from ai_tool.production_run_contract import (
    build_production_run_contract,
    validate_production_run_contract,
)
from tests.ai_tool.test_production_meaning_context import _handoff, _mission


def _contract() -> tuple[dict, dict, dict, str]:
    mission = _mission()
    handoff = _handoff()
    meaning_context = build_meaning_context_v0(mission, handoff)
    handoff_hash = "handoff-canonical-hash"
    return (
        build_production_run_contract(
            started_execution_id="execution-initial",
            mission=mission,
            handoff=handoff,
            meaning_context=meaning_context,
            starting_task_id="gh-T1",
            handoff_canonical_hash=handoff_hash,
        ),
        mission,
        handoff,
        handoff_hash,
    )


def test_run_contract_is_deterministic_and_contains_only_start_references_and_snapshot():
    first, mission, handoff, handoff_hash = _contract()
    meaning_context = build_meaning_context_v0(mission, handoff)
    second = build_production_run_contract(
        started_execution_id="execution-initial",
        mission=deepcopy(mission),
        handoff=deepcopy(handoff),
        meaning_context=deepcopy(meaning_context),
        starting_task_id="gh-T1",
        handoff_canonical_hash=handoff_hash,
    )

    assert first == second
    assert set(first) == {
        "started_execution_id",
        "mission_id",
        "requirement_ids",
        "handoff_id",
        "handoff_canonical_hash",
        "starting_task_id",
        "meaning_context",
        "meaning_context_hash",
        "decision_premises",
    }
    assert first["decision_premises"] == [
        {
            "decision_key": "quality:definition",
            "active_decision_id": "decision-quality-v1",
            "validated_against_decision_id": "decision-quality-v1",
        }
    ]
    assert not validate_production_run_contract(
        first,
        mission=mission,
        handoff=handoff,
        meaning_context=meaning_context,
        handoff_canonical_hash=handoff_hash,
        runtime_snapshot={"tasks": [{"task_id": "gh-T1"}]},
    )


def test_run_contract_fails_closed_on_identity_meaning_decision_or_start_task_change():
    contract, mission, handoff, handoff_hash = _contract()
    meaning_context = build_meaning_context_v0(mission, handoff)

    cases = [
        ("mission_id", "m-other", "run_contract_mission_mismatch"),
        ("requirement_ids", ["req-other"], "run_contract_requirement_mismatch"),
        ("handoff_id", "gh-other", "run_contract_handoff_id_mismatch"),
        ("handoff_canonical_hash", "other-hash", "run_contract_handoff_hash_mismatch"),
        (
            "decision_premises",
            [{"decision_key": "quality:definition", "active_decision_id": "decision-other"}],
            "run_contract_decision_premise_mismatch",
        ),
    ]
    for field, value, expected in cases:
        changed = deepcopy(contract)
        changed[field] = value
        assert expected in validate_production_run_contract(
            changed,
            mission=mission,
            handoff=handoff,
            meaning_context=meaning_context,
            handoff_canonical_hash=handoff_hash,
        )

    tampered_meaning = deepcopy(contract)
    tampered_meaning["meaning_context"]["human_meaning"]["original_goal"] = "other"
    assert "run_contract_meaning_snapshot_tampered" in validate_production_run_contract(
        tampered_meaning,
        mission=mission,
        handoff=handoff,
        meaning_context=meaning_context,
        handoff_canonical_hash=handoff_hash,
    )
    assert "run_contract_starting_task_missing" in validate_production_run_contract(
        contract,
        mission=mission,
        handoff=handoff,
        meaning_context=meaning_context,
        handoff_canonical_hash=handoff_hash,
        runtime_snapshot={"tasks": [{"task_id": "gh-T2"}]},
    )


def test_resume_projection_ignores_non_meaning_mission_state_but_preserves_meaning_changes():
    contract, mission, handoff, handoff_hash = _contract()
    baseline = build_meaning_context_v0(mission, handoff)

    runtime_updated_mission = deepcopy(mission)
    runtime_updated_mission["completion_runtime"] = {"current_task_id": "gh-T1"}
    runtime_updated = build_meaning_context_v0(runtime_updated_mission, handoff)
    assert baseline["identity"]["mission_canonical_hash"] != runtime_updated["identity"][
        "mission_canonical_hash"
    ]
    assert resume_meaning_projection(baseline) == resume_meaning_projection(runtime_updated)
    assert not validate_production_run_contract(
        contract,
        mission=runtime_updated_mission,
        handoff=handoff,
        meaning_context=runtime_updated,
        handoff_canonical_hash=handoff_hash,
    )

    meaning_changed_mission = deepcopy(mission)
    meaning_changed_mission["structured_requirements"][0]["normalized_meaning"] = "changed"
    meaning_changed = build_meaning_context_v0(meaning_changed_mission, handoff)
    assert "run_contract_meaning_mismatch" in validate_production_run_contract(
        contract,
        mission=meaning_changed_mission,
        handoff=handoff,
        meaning_context=meaning_changed,
        handoff_canonical_hash=handoff_hash,
    )


def test_resume_projection_excludes_completion_only_supplements():
    contract, mission, handoff, handoff_hash = _contract()
    supplemented_mission = deepcopy(mission)
    supplemented_mission["user_confirmed_supplements"] = [
        {"text": "completion-only note", "source": "goal_completion"}
    ]
    supplemented = build_meaning_context_v0(supplemented_mission, handoff)

    assert not validate_production_run_contract(
        contract,
        mission=supplemented_mission,
        handoff=handoff,
        meaning_context=supplemented,
        handoff_canonical_hash=handoff_hash,
    )
