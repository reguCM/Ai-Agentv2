from __future__ import annotations

import pytest

from ai_tool.dev_skill_pipeline import build_handoff_packet, validate_handoff_packet
from ai_tool.requirement_handoff_binding import validate_requirement_handoff_bindings


def _requirements() -> list[dict]:
    return [
        {
            "requirement_id": "req-tetris",
            "source_text": "Build Tetris",
            "disposition": "GOAL",
            "resolution_status": "resolved",
            "materiality": "blocks_design",
            "normalized_meaning": "Build Tetris",
        },
        {
            "requirement_id": "req-rules",
            "source_text": "Rules are correct",
            "disposition": "AMBIGUOUS_REQUIREMENT",
            "resolution_status": "resolved",
            "materiality": "blocks_design",
            "normalized_meaning": "Correct basic Tetris rules",
        },
    ]


def _packet(bindings: list[dict] | None, *, requirements: list[dict] | None = None) -> dict:
    plan: dict = {
        "tasks": [
            {"id": "T1", "title": "Implement game rules", "size": "S"},
            {"id": "T2", "title": "Implement controls", "size": "S"},
        ]
    }
    if bindings is not None:
        plan["requirement_bindings"] = bindings
    return build_handoff_packet(
        initial_request="Build Tetris",
        aligned_spec={
            "summary": "Build Tetris",
            "numbered_conditions": ["Build Tetris", "Correct basic Tetris rules"],
            "non_goals": ["Online play"],
            "acceptance_criteria": ["Rules work", "Controls respond"],
        },
        prd_rel="prd.md",
        tech_spec_rel="tech.md",
        plan_rel="plan.md",
        todo_rel="todo.md",
        tech_spec={"summary": "Build Tetris", "modules": [{"path": "tetris/main.py"}]},
        plan=plan,
        skill_steps=["goal-handoff"],
        source_binding={
            "mission_id": "m-tetris",
            "requirement_ids": sorted(
                str(row["requirement_id"])
                for row in requirements
                if str(row.get("requirement_id") or "")
            ) if requirements is not None else ["req-rules", "req-tetris"],
        },
        structured_requirements=requirements,
    )


def test_one_material_requirement_bound_to_one_task_passes() -> None:
    requirements = [_requirements()[0]]
    packet = _packet(
        [{"requirement_id": "req-tetris", "task_ids": ["T1"], "acceptance_ids": []}],
        requirements=requirements,
    )
    assert validate_handoff_packet(packet, structured_requirements=requirements) == []


def test_material_requirement_may_be_bound_to_acceptance_only() -> None:
    requirements = [_requirements()[0]]
    packet = _packet(
        [{"requirement_id": "req-tetris", "task_ids": [], "acceptance_ids": ["A1"]}],
        requirements=requirements,
    )
    assert validate_handoff_packet(packet, structured_requirements=requirements) == []


def test_material_requirement_can_bind_multiple_tasks_and_acceptance() -> None:
    requirements = [_requirements()[0]]
    packet = _packet(
        [{"requirement_id": "req-tetris", "task_ids": ["T1", "T2"], "acceptance_ids": ["A1", "A2"]}],
        requirements=requirements,
    )
    assert validate_handoff_packet(packet, structured_requirements=requirements) == []


def test_each_material_requirement_requires_its_own_binding() -> None:
    requirements = _requirements()
    packet = _packet(
        [
            {"requirement_id": "req-tetris", "task_ids": ["T1"], "acceptance_ids": ["A1"]},
            {"requirement_id": "req-rules", "task_ids": ["T1"], "acceptance_ids": ["A1"]},
        ],
        requirements=requirements,
    )
    assert validate_handoff_packet(packet, structured_requirements=requirements) == []


def test_unbound_material_requirement_is_rejected() -> None:
    with pytest.raises(ValueError, match="material_requirement_unbound:req-rules"):
        _packet(
            [{"requirement_id": "req-tetris", "task_ids": ["T1"], "acceptance_ids": []}],
            requirements=_requirements(),
        )


def test_unknown_requirement_task_and_acceptance_references_are_rejected() -> None:
    requirements = _requirements()
    packet = _packet(None, requirements=None)
    packet["requirement_bindings"] = [
        {"requirement_id": "req-unknown", "task_ids": ["T99"], "acceptance_ids": ["A99"]}
    ]
    errors = validate_handoff_packet(packet, structured_requirements=requirements)
    assert "unknown_requirement_binding:req-unknown" in errors
    assert "unknown_requirement_binding_task:req-unknown:T99" in errors
    assert "unknown_requirement_binding_acceptance:req-unknown:A99" in errors
    assert "material_requirement_unbound:req-tetris" in errors
    assert "material_requirement_unbound:req-rules" in errors


def test_duplicate_and_empty_binding_rows_are_rejected() -> None:
    requirements = _requirements()
    packet = _packet(None, requirements=None)
    packet["requirement_bindings"] = [
        {"requirement_id": "req-tetris", "task_ids": ["T1"], "acceptance_ids": []},
        {"requirement_id": "req-tetris", "task_ids": [], "acceptance_ids": []},
        {"requirement_id": "req-rules", "task_ids": ["T1"], "acceptance_ids": ["A1"]},
    ]
    errors = validate_requirement_handoff_bindings(packet, requirements)
    assert "duplicate_requirement_binding:req-tetris" in errors
    assert "unbound_requirement_binding:req-tetris" in errors


def test_non_material_noise_does_not_require_coverage() -> None:
    noise = [
        {
            "requirement_id": "req-noise",
            "disposition": "NOISE",
            "resolution_status": "resolved",
            "materiality": "informational",
        }
    ]
    packet = _packet(None, requirements=noise)
    assert validate_handoff_packet(packet, structured_requirements=noise) == []


def test_tetris_trace_is_identity_only_and_complete() -> None:
    requirements = _requirements()
    packet = _packet(
        [
            {"requirement_id": "req-tetris", "task_ids": ["T1", "T2"], "acceptance_ids": ["A1", "A2"]},
            {"requirement_id": "req-rules", "task_ids": ["T1"], "acceptance_ids": ["A1"]},
        ],
        requirements=requirements,
    )
    trace = {
        row["requirement_id"]: (row["task_ids"], row["acceptance_ids"])
        for row in packet["requirement_bindings"]
    }
    assert trace == {
        "req-tetris": (["T1", "T2"], ["A1", "A2"]),
        "req-rules": (["T1"], ["A1"]),
    }
    assert validate_requirement_handoff_bindings(packet, requirements) == []


def test_tetris_five_material_meanings_all_trace_to_handoff_identities() -> None:
    requirements = [
        {"requirement_id": "req-r1", "disposition": "GOAL", "resolution_status": "resolved", "materiality": "blocks_design"},
        {"requirement_id": "req-r2", "disposition": "AMBIGUOUS_REQUIREMENT", "resolution_status": "resolved", "materiality": "blocks_design"},
        {"requirement_id": "req-r3", "disposition": "AMBIGUOUS_REQUIREMENT", "resolution_status": "resolved", "materiality": "blocks_design"},
        {"requirement_id": "req-r4", "disposition": "AMBIGUOUS_REQUIREMENT", "resolution_status": "resolved", "materiality": "blocks_design"},
        {"requirement_id": "req-r5", "disposition": "AMBIGUOUS_REQUIREMENT", "resolution_status": "resolved", "materiality": "blocks_design"},
    ]
    packet = _packet(
        [
            {"requirement_id": "req-r1", "task_ids": ["T1", "T2"], "acceptance_ids": ["A1", "A2"]},
            {"requirement_id": "req-r2", "task_ids": ["T1"], "acceptance_ids": ["A1"]},
            {"requirement_id": "req-r3", "task_ids": ["T2"], "acceptance_ids": ["A2"]},
            {"requirement_id": "req-r4", "task_ids": [], "acceptance_ids": ["A1"]},
            {"requirement_id": "req-r5", "task_ids": ["T2"], "acceptance_ids": ["A2"]},
        ],
        requirements=requirements,
    )
    trace = {row["requirement_id"]: (row["task_ids"], row["acceptance_ids"]) for row in packet["requirement_bindings"]}
    assert trace == {
        "req-r1": (["T1", "T2"], ["A1", "A2"]),
        "req-r2": (["T1"], ["A1"]),
        "req-r3": (["T2"], ["A2"]),
        "req-r4": ([], ["A1"]),
        "req-r5": (["T2"], ["A2"]),
    }
