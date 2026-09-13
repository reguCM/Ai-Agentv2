from __future__ import annotations

from ai_tool.chat_interface.requirement_resolution import (
    build_canonical_requirement_evidence_trace,
    extract_requirement_resolution,
    sync_canonical_requirement_projection,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.task_runtime import EvidenceRecord, GoalNode, TaskRecord


def _orchestrator_with_tasks(
    *,
    projection: list[dict[str, str]],
    tasks: list[TaskRecord],
) -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("trace", "goal text")
    orchestrator.runtime.add_goal(GoalNode("G1", "root"))
    for task in tasks:
        orchestrator.runtime.add_task(task)
    orchestrator.canonical_requirement_projection = list(projection)
    return orchestrator


def test_e1_traces_requirement_through_condition_to_evidence():
    task = TaskRecord(
        "T1",
        "G1",
        "observe",
        "inst",
        ["condition-A"],
    )
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-A", "completion_condition": "condition-A"}],
        tasks=[task],
    )
    orchestrator.runtime.add_evidence(
        EvidenceRecord(
            evidence_id="E1",
            source_type="tool",
            source="read",
            summary="seen",
            created_by_action="A1",
        ),
        ["T1"],
    )
    orchestrator.runtime.support_completion_conditions("T1", "E1", ["condition-A"])
    trace = build_canonical_requirement_evidence_trace(orchestrator)
    assert len(trace) == 1
    row = trace[0]
    assert row["requirement_id"] == "req-A"
    assert row["completion_condition"] == "condition-A"
    assert row["runtime_matches"] == [
        {"task_id": "T1", "condition_status": "SATISFIED", "evidence_ids": ["E1"]}
    ]


def test_e2_condition_without_evidence_lists_empty_refs():
    task = TaskRecord("T1", "G1", "t", "i", ["condition-B"])
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-B", "completion_condition": "condition-B"}],
        tasks=[task],
    )
    trace = build_canonical_requirement_evidence_trace(orchestrator)[0]
    assert trace["runtime_matches"] == [
        {"task_id": "T1", "condition_status": "UNKNOWN", "evidence_ids": []}
    ]


def test_e3_does_not_attach_unrelated_condition_evidence():
    task_a = TaskRecord("T1", "G1", "a", "i", ["condition-A"])
    task_other = TaskRecord("T2", "G1", "b", "i", ["other-condition"])
    orchestrator = _orchestrator_with_tasks(
        projection=[{"requirement_id": "req-A", "completion_condition": "condition-A"}],
        tasks=[task_a, task_other],
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
    orchestrator.runtime.support_completion_conditions("T2", "E-other", ["other-condition"])
    trace = build_canonical_requirement_evidence_trace(orchestrator)[0]
    assert trace["runtime_matches"] == [
        {"task_id": "T1", "condition_status": "UNKNOWN", "evidence_ids": []}
    ]


def test_e4_multiple_tasks_same_condition_all_listed():
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
    trace = build_canonical_requirement_evidence_trace(orchestrator)[0]
    assert len(trace["runtime_matches"]) == 2
    by_task = {row["task_id"]: row["evidence_ids"] for row in trace["runtime_matches"]}
    assert by_task["T1"] == ["E1"]
    assert by_task["T2"] == []


def test_e5_unprojected_canonical_rows_absent_from_trace():
    bundle = extract_requirement_resolution(
        "簡単なテトリスを作って",
        use_heuristic_only=True,
    )
    orchestrator = ChatTaskOrchestrator("e5", bundle.original_goal)
    orchestrator.structured_requirements = [row.as_dict() for row in bundle.structured_requirements]
    sync_canonical_requirement_projection(orchestrator)
    trace = orchestrator.canonical_requirement_evidence_trace()
    traced_ids = {row["requirement_id"] for row in trace}
    projection_ids = {
        entry["requirement_id"] for entry in orchestrator.canonical_requirement_projection
    }
    assert traced_ids <= projection_ids
    ambiguous = next(
        row for row in bundle.structured_requirements if row.source_text == "簡単な"
    )
    assert ambiguous.requirement_id not in traced_ids
    assert ambiguous.requirement_id not in projection_ids
