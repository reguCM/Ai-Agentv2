from __future__ import annotations

from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.goal_handoff_runtime_bridge import (
    build_handoff_acceptance_runtime_trace,
    build_handoff_task_records,
    seed_orchestrator_from_handoff,
)


def _packet_with_maps() -> dict:
    return {
        "handoff_id": "gh-step5",
        "goal": {"summary": "Tetris handoff"},
        "acceptance_criteria": [
            {"id": "A1", "statement": "statement-A", "verification": "verify-A"},
            {"id": "A2", "statement": "statement-B", "verification": "verify-B"},
        ],
        "implementation_tasks": [
            {
                "id": "T1",
                "title": "Task one",
                "acceptance": ["statement-A"],
                "verification": ["v1"],
                "maps_to_acceptance": ["A1", "A2"],
            },
            {
                "id": "T2",
                "title": "Task two",
                "acceptance": ["statement-B"],
                "verification": [],
                "maps_to_acceptance": ["A1"],
            },
            {
                "id": "T3",
                "title": "Task three",
                "acceptance": ["orphan task"],
                "verification": [],
            },
        ],
    }


def _goal_and_task_conditions(packet: dict) -> tuple[list[str], dict[str, list[str]]]:
    root, records, _ = build_handoff_task_records(packet)
    task_conditions = {record.task_id: list(record.completion_conditions) for record in records}
    return list(root.completion_conditions), task_conditions


def test_h1_acceptance_id_statement_preserved():
    orchestrator = ChatTaskOrchestrator("h1", "goal")
    seed_orchestrator_from_handoff(orchestrator, _packet_with_maps())
    by_id = {row["acceptance_id"]: row for row in orchestrator.handoff_acceptance_projection}
    assert by_id["A1"]["statement"] == "statement-A"
    assert by_id["A1"]["verification"] == "verify-A"


def test_h2_h3_task_maps_to_acceptance():
    orchestrator = ChatTaskOrchestrator("h2", "goal")
    seed_orchestrator_from_handoff(orchestrator, _packet_with_maps())
    by_source = {row["source_task_id"]: row for row in orchestrator.handoff_task_acceptance_mapping}
    assert by_source["T1"]["runtime_task_id"] == "gh-T1"
    assert by_source["T1"]["maps_to_acceptance"] == ["A1", "A2"]


def test_h4_acceptance_maps_to_multiple_runtime_tasks():
    orchestrator = ChatTaskOrchestrator("h4", "goal")
    seed_orchestrator_from_handoff(orchestrator, _packet_with_maps())
    trace = build_handoff_acceptance_runtime_trace(orchestrator)
    a1 = next(row for row in trace if row["acceptance_id"] == "A1")
    runtime_ids = [item["runtime_task_id"] for item in a1["mapped_runtime_tasks"]]
    assert runtime_ids == ["gh-T1", "gh-T2"]


def test_h5_no_maps_to_acceptance_not_invented():
    orchestrator = ChatTaskOrchestrator("h5", "goal")
    seed_orchestrator_from_handoff(orchestrator, _packet_with_maps())
    by_source = {row["source_task_id"]: row for row in orchestrator.handoff_task_acceptance_mapping}
    assert by_source["T3"]["maps_to_acceptance"] == []
    trace = orchestrator.handoff_acceptance_runtime_trace()
    a1 = next(row for row in trace if row["acceptance_id"] == "A1")
    assert "gh-T3" not in {item["runtime_task_id"] for item in a1["mapped_runtime_tasks"]}


def test_h6_h7_completion_condition_strings_unchanged():
    packet = _packet_with_maps()
    before_goal, before_tasks = _goal_and_task_conditions(packet)
    orchestrator = ChatTaskOrchestrator("h67", "goal")
    seed_orchestrator_from_handoff(orchestrator, packet)
    after_goal = list(orchestrator.runtime.goals["G1"].completion_conditions)
    after_tasks = {
        task_id: list(task.completion_conditions)
        for task_id, task in orchestrator.runtime.tasks.items()
    }
    assert after_goal == before_goal
    assert after_tasks == before_tasks
