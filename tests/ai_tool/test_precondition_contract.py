"""Precondition Contract v0 tests."""
from __future__ import annotations

import json
from pathlib import Path

from ai_tool.dev_skill_pipeline import build_handoff_packet, validate_handoff_packet
from ai_tool.precondition_contract import (
    STATUS_SATISFIED,
    STATUS_UNKNOWN,
    is_precondition_satisfied,
    precondition_definition,
    precondition_evaluated,
    preconditions_all_satisfied,
    preconditions_to_dicts,
    restore_preconditions,
    serialize_preconditions,
    tetris_handoff_precondition_fixtures,
    validate_precondition_dict,
    validate_preconditions,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _minimal_handoff_packet() -> dict:
    return build_handoff_packet(
        initial_request="テトリスを作って",
        prd={"title": "Tetris", "acceptance_criteria": ["tetris/main.py exists"]},
        prd_rel="logs/x/design/prd.md",
        tech_spec_rel="logs/x/design/tech-spec.md",
        plan_rel="logs/x/design/plan.md",
        todo_rel="logs/x/design/todo.md",
        tech_spec={"summary": "sandbox tetris"},
        plan={"tasks": [{"id": "T1", "title": "Bootstrap", "size": "S"}]},
        skill_steps=["write-prd", "planning-and-task-breakdown"],
    )


def test_existing_handoff_without_preconditions_stays_valid() -> None:
    packet = _minimal_handoff_packet()
    assert "preconditions" not in packet
    assert not validate_handoff_packet(packet)

    trial_packet = json.loads(
        (REPO_ROOT / "docs/handoffs/gh-20260910T094912Z-session-start-skill.json").read_text(
            encoding="utf-8"
        )
    )
    assert "preconditions" not in trial_packet
    assert not validate_handoff_packet(trial_packet)


def test_unknown_precondition_can_be_stored() -> None:
    fixtures = tetris_handoff_precondition_fixtures()
    assert len(fixtures) == 3
    for item in fixtures:
        assert item.evaluation.status == STATUS_UNKNOWN
        assert item.evaluation.evidence_refs == []
        assert not validate_precondition_dict(item.as_dict())

    packet = _minimal_handoff_packet()
    packet["preconditions"] = preconditions_to_dicts(fixtures)
    assert not validate_handoff_packet(packet)


def test_satisfied_precondition_requires_evidence_refs() -> None:
    satisfied = precondition_evaluated(
        key="tech_spec_exists",
        description="Tech spec artifact exists.",
        source="test",
        status=STATUS_SATISFIED,
        evidence_refs=["pe-tech-spec-path"],
        precondition_id="pc-test-satisfied",
    )
    assert is_precondition_satisfied(satisfied)
    assert not validate_precondition_dict(satisfied.as_dict())

    missing_evidence = satisfied.as_dict()
    missing_evidence["evaluation"]["evidence_refs"] = []
    assert any("evidence_refs" in message for message in validate_precondition_dict(missing_evidence))


def test_definition_only_is_not_satisfied() -> None:
    defined = precondition_definition(
        key="task_ids_unique",
        description="Task ids are unique.",
        source="test",
        precondition_id="pc-test-defined",
    )
    assert defined.evaluation.status == STATUS_UNKNOWN
    assert not is_precondition_satisfied(defined)
    assert not preconditions_all_satisfied([defined])


def test_multiple_preconditions_supported() -> None:
    items = tetris_handoff_precondition_fixtures()
    keys = {item.key for item in items}
    assert keys == {
        "tech_spec_exists",
        "task_ids_unique",
        "dependency_refs_resolved",
    }
    assert not validate_preconditions(preconditions_to_dicts(items))


def test_blocking_true_and_false_preserved() -> None:
    blocking = precondition_definition(
        key="tech_spec_exists",
        description="blocking example",
        source="test",
        blocking=True,
        precondition_id="pc-blocking-true",
    )
    non_blocking = precondition_definition(
        key="dependency_refs_resolved",
        description="non-blocking example",
        source="test",
        blocking=False,
        precondition_id="pc-blocking-false",
    )
    packet = _minimal_handoff_packet()
    packet["preconditions"] = preconditions_to_dicts([blocking, non_blocking])
    assert packet["preconditions"][0]["blocking"] is True
    assert packet["preconditions"][1]["blocking"] is False
    assert not validate_handoff_packet(packet)


def test_serialize_restore_roundtrip() -> None:
    original = tetris_handoff_precondition_fixtures()
    original.append(
        precondition_evaluated(
            key="tech_spec_exists",
            description="Tech spec on disk.",
            source="e2e_preflight",
            status=STATUS_SATISFIED,
            evidence_refs=["pe238ff52dab71480cac9e919317d64f32"],
            blocking=True,
            precondition_id="pc-tetris-tech-spec-eval",
        )
    )
    serialized = serialize_preconditions(original)
    restored = restore_preconditions(serialized)
    assert preconditions_to_dicts(restored) == preconditions_to_dicts(original)
