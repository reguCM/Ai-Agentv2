from __future__ import annotations

from ai_tool.chat_interface.requirement_resolution import (
    build_canonical_requirement_runtime_coverage,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.task_runtime import ConditionStatus, EvidenceRecord, GoalNode, TaskRecord


def _orchestrator_with_tasks(
    *,
    projection: list[dict[str, str]],
    tasks: list[TaskRecord],
) -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("cov", "goal")
    orchestrator.runtime.add_goal(GoalNode("G1", "root"))
    for task in tasks:
        orchestrator.runtime.add_task(task)
    orchestrator.canonical_requirement_projection = list(projection)
    return orchestrator


def _runtime_snapshot(orchestrator: ChatTaskOrchestrator) -> dict:
    snap: dict = {"goals": {}, "tasks": {}, "evidence": {}}
    for goal_id, goal in orchestrator.runtime.goals.items():
        snap["goals"][goal_id] = goal.status
    for task_id, task in orchestrator.runtime.tasks.items():
        snap["tasks"][task_id] = {
            "status": task.status,
            "condition_status": dict(task.condition_status),
            "condition_evidence": {
                key: list(refs) for key, refs in task.condition_evidence.items()
            },
        }
    for evidence_id, record in orchestrator.runtime.evidence.items():
        snap["evidence"][evidence_id] = record.summary
    return snap


def test_c1_satisfied_condition_with_evidence():
    task = TaskRecord("T1", "G1", "t", "i", ["condition-A"])
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-A", "completion_condition": "condition-A"}],
        tasks=[task],
    )
    orchestrator.runtime.add_evidence(
        EvidenceRecord(
            evidence_id="E1",
            source_type="tool",
            source="s",
            summary="ok",
            created_by_action="A1",
        ),
        ["T1"],
    )
    orchestrator.runtime.support_completion_conditions("T1", "E1", ["condition-A"])
    row = build_canonical_requirement_runtime_coverage(orchestrator)[0]
    match = row["runtime_matches"][0]
    assert match == {
        "task_id": "T1",
        "condition_status": ConditionStatus.SATISFIED.value,
        "evidence_ids": ["E1"],
    }


def test_c2_unknown_status_without_evidence():
    task = TaskRecord("T2", "G1", "t", "i", ["condition-B"])
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-B", "completion_condition": "condition-B"}],
        tasks=[task],
    )
    match = build_canonical_requirement_runtime_coverage(orchestrator)[0]["runtime_matches"][0]
    assert match["task_id"] == "T2"
    assert match["condition_status"] == ConditionStatus.UNKNOWN.value
    assert match["evidence_ids"] == []


def test_c3_multiple_tasks_keep_distinct_status():
    task_one = TaskRecord("T1", "G1", "one", "i", ["shared"])
    task_two = TaskRecord("T2", "G1", "two", "i", ["shared"])
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-S", "completion_condition": "shared"}],
        tasks=[task_one, task_two],
    )
    orchestrator.runtime.add_evidence(
        EvidenceRecord(
            evidence_id="E1",
            source_type="tool",
            source="s",
            summary="s",
            created_by_action="A1",
        ),
        ["T1"],
    )
    orchestrator.runtime.support_completion_conditions("T1", "E1", ["shared"])
    by_task = {
        row["task_id"]: row
        for row in build_canonical_requirement_runtime_coverage(orchestrator)[0]["runtime_matches"]
    }
    assert by_task["T1"]["condition_status"] == ConditionStatus.SATISFIED.value
    assert by_task["T2"]["condition_status"] == ConditionStatus.UNKNOWN.value


def test_c4_no_matching_task_empty_runtime_matches():
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-X", "completion_condition": "orphan"}],
        tasks=[TaskRecord("T1", "G1", "t", "i", ["other"])],
    )
    row = build_canonical_requirement_runtime_coverage(orchestrator)[0]
    assert row["runtime_matches"] == []


def test_c5_does_not_cross_wire_other_conditions():
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-A", "completion_condition": "condition-A"}],
        tasks=[
            TaskRecord("T1", "G1", "a", "i", ["condition-A"]),
            TaskRecord("T2", "G1", "b", "i", ["other"]),
        ],
    )
    orchestrator.runtime.add_evidence(
        EvidenceRecord(
            evidence_id="E-other",
            source_type="tool",
            source="x",
            summary="x",
            created_by_action="A1",
        ),
        ["T2"],
    )
    orchestrator.runtime.support_completion_conditions("T2", "E-other", ["other"])
    match = build_canonical_requirement_runtime_coverage(orchestrator)[0]["runtime_matches"][0]
    assert match["evidence_ids"] == []
    assert match["condition_status"] == ConditionStatus.UNKNOWN.value


def test_c6_coverage_helper_does_not_mutate_runtime():
    task = TaskRecord("T1", "G1", "t", "i", ["condition-A"])
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-A", "completion_condition": "condition-A"}],
        tasks=[task],
    )
    before = _runtime_snapshot(orchestrator)
    build_canonical_requirement_runtime_coverage(orchestrator)
    orchestrator.canonical_requirement_runtime_coverage()
    after = _runtime_snapshot(orchestrator)
    assert before == after
