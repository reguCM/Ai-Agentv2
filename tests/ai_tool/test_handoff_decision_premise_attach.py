"""CPU-deterministic tests for Handoff decision_premises auto-attach."""
from __future__ import annotations

import pytest

from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    DECISION_STATUS_SUPERSEDED,
    supersede_decision,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.dev_skill_pipeline import (
    build_handoff_packet,
    normalize_implementation_tasks,
    validate_handoff_packet,
)
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.human_decision_premise import (
    INITIAL_GRILL_SEMANTIC_DECISION_KEY,
    active_decision_catalog,
    build_initial_grill_decision_record,
    finalize_handoff_implementation_tasks,
    initial_grill_question_id_for_orchestrator,
    tasks_needing_revalidation,
)

KEY_JSON = "acceptance:output_format"
KEY_GUI = "scope:gui"
D_JSON_V1 = "d-json-v1"
D_GUI_V1 = "d-gui-v1"
D_JSON_V2 = "d-json-v2"


def _clarifications() -> list[dict]:
    return [
        {
            "decision_id": D_JSON_V1,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "JSON",
            "dimension": "acceptance",
        },
        {
            "decision_id": D_GUI_V1,
            "decision_key": KEY_GUI,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "GUIあり",
            "dimension": "scope",
        },
    ]


def _plan_tasks() -> list[dict]:
    return [
        {
            "id": "T1",
            "title": "Shared setup",
            "acceptance": ["project scaffold exists"],
            "verification": ["repo ready"],
            "dependencies": [],
            "size": "S",
        },
        {
            "id": "T2",
            "title": "Emit JSON API output",
            "acceptance": ["JSON response available"],
            "verification": ["json endpoint returns payload"],
            "dependencies": ["T1"],
            "size": "S",
            "premise_decision_keys": [KEY_JSON],
        },
        {
            "id": "T3",
            "title": "Build GUI screen",
            "acceptance": ["GUI visible"],
            "verification": ["manual UI check"],
            "dependencies": ["T1"],
            "size": "M",
            "premise_decision_keys": [KEY_GUI],
        },
    ]


def test_initial_grill_separates_semantic_key_from_question_instance():
    first = ChatTaskOrchestrator("grill-a", "find spec")
    first.initialize()
    first.mission_id = "m-grill-a"
    first.search_candidate_sets[("spec", ".")] = {
        "observation_role": "goal_request",
        "query": "PROJECT_SPEC",
        "path": ".",
    }
    first.goal_read_target = {"reason": "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES"}

    second = ChatTaskOrchestrator("grill-b", "find spec")
    second.initialize()
    second.mission_id = "m-grill-b"
    second.search_candidate_sets[("readme", "docs")] = {
        "observation_role": "goal_request",
        "query": "README",
        "path": "docs",
    }
    second.goal_read_target = {"reason": "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES"}

    question_a = initial_grill_question_id_for_orchestrator(first)
    question_b = initial_grill_question_id_for_orchestrator(second)
    assert question_a != question_b
    assert question_a.startswith("initial_grill:")
    assert question_b.startswith("initial_grill:")

    record_a = build_initial_grill_decision_record(
        "docs/PROJECT_SPEC.md",
        decision_key=INITIAL_GRILL_SEMANTIC_DECISION_KEY,
        question_id=question_a,
    )
    record_b = build_initial_grill_decision_record(
        "docs/README.md",
        decision_key=INITIAL_GRILL_SEMANTIC_DECISION_KEY,
        question_id=question_b,
    )
    assert record_a["decision_key"] == INITIAL_GRILL_SEMANTIC_DECISION_KEY
    assert record_b["decision_key"] == INITIAL_GRILL_SEMANTIC_DECISION_KEY
    assert record_a["question_id"] != record_b["question_id"]


def test_active_decision_catalog_has_one_active_row_per_key():
    catalog = active_decision_catalog(_clarifications())
    assert set(catalog) == {KEY_JSON, KEY_GUI}
    assert catalog[KEY_JSON]["decision_id"] == D_JSON_V1
    assert catalog[KEY_GUI]["decision_id"] == D_GUI_V1


def test_finalize_attaches_premises_per_task_not_globally():
    tasks = finalize_handoff_implementation_tasks(
        normalize_implementation_tasks(
            _plan_tasks(),
            default_acceptance=["done"],
            default_verification=["check"],
        ),
        _clarifications(),
    )
    by_id = {task["id"]: task for task in tasks}
    assert "decision_premises" not in by_id["T1"]
    assert "premise_decision_keys" not in by_id["T1"]
    assert by_id["T2"]["decision_premises"] == [
        {"decision_key": KEY_JSON, "derived_from_decision_id": D_JSON_V1}
    ]
    assert by_id["T3"]["decision_premises"] == [
        {"decision_key": KEY_GUI, "derived_from_decision_id": D_GUI_V1}
    ]


def test_finalize_rejects_unknown_decision_key():
    tasks = normalize_implementation_tasks(
        [
            {
                "id": "T1",
                "title": "Bad task",
                "acceptance": ["x"],
                "verification": ["y"],
                "premise_decision_keys": ["acceptance:missing"],
            }
        ],
        default_acceptance=["done"],
        default_verification=["check"],
    )
    with pytest.raises(ValueError, match="unknown_decision_key"):
        finalize_handoff_implementation_tasks(tasks, _clarifications())


def test_finalize_rejects_inactive_derived_decision_id():
    tasks = normalize_implementation_tasks(
        [
            {
                "id": "T1",
                "title": "Stale explicit premise",
                "acceptance": ["x"],
                "verification": ["y"],
                "decision_premises": [
                    {
                        "decision_key": KEY_JSON,
                        "derived_from_decision_id": "d-stale",
                    }
                ],
            }
        ],
        default_acceptance=["done"],
        default_verification=["check"],
    )
    with pytest.raises(ValueError, match="inactive_decision_id"):
        finalize_handoff_implementation_tasks(tasks, _clarifications())


def test_build_handoff_packet_auto_attaches_and_validates_schema():
    packet = build_handoff_packet(
        initial_request="build service",
        prd_rel="docs/prd.md",
        tech_spec_rel="docs/tech.md",
        plan_rel="tasks/plan.md",
        todo_rel="tasks/todo.md",
        tech_spec={"summary": "service"},
        plan={"tasks": _plan_tasks()},
        skill_steps=["planning-and-task-breakdown", "goal-handoff"],
        confirmed_clarifications=_clarifications(),
        handoff_slug="decision-premise-e2e",
    )
    assert not validate_handoff_packet(packet)
    tasks = {row["id"]: row for row in packet["implementation_tasks"]}
    assert "decision_premises" not in tasks["T1"]
    assert tasks["T2"]["decision_premises"][0]["derived_from_decision_id"] == D_JSON_V1
    assert tasks["T3"]["decision_premises"][0]["derived_from_decision_id"] == D_GUI_V1


def test_handoff_generated_premises_revalidate_only_matching_runtime_task():
    packet = build_handoff_packet(
        initial_request="build service",
        prd_rel="docs/prd.md",
        tech_spec_rel="docs/tech.md",
        plan_rel="tasks/plan.md",
        todo_rel="tasks/todo.md",
        tech_spec={"summary": "service"},
        plan={"tasks": _plan_tasks()},
        skill_steps=["planning-and-task-breakdown", "goal-handoff"],
        confirmed_clarifications=_clarifications(),
        handoff_slug="decision-premise-runtime",
    )

    orchestrator = ChatTaskOrchestrator("runtime", "build service")
    orchestrator.confirmed_clarifications = list(_clarifications())
    seed_orchestrator_from_handoff(orchestrator, packet)

    resumed = ChatTaskOrchestrator("runtime-resume", orchestrator.request)
    resumed.confirmed_clarifications = list(orchestrator.confirmed_clarifications)
    resumed.apply_completion_runtime(
        orchestrator.completion_runtime_slice(),
        replace_graph=True,
    )

    supersede_decision(
        resumed,
        D_JSON_V1,
        {
            "decision_id": D_JSON_V2,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "YAML",
            "dimension": "acceptance",
        },
        execution_id="exec-2",
    )

    assert resumed.runtime.tasks["gh-T1"].revalidation is None
    json_task = resumed.runtime.tasks["gh-T2"]
    gui_task = resumed.runtime.tasks["gh-T3"]
    assert json_task.revalidation["needs_revalidation"] is True
    assert gui_task.revalidation["needs_revalidation"] is False
    assert [row["task_id"] for row in tasks_needing_revalidation(resumed)] == ["gh-T2"]
