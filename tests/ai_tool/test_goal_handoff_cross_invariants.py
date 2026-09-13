from __future__ import annotations

from ai_tool.chat_interface.goal_continuation_resume import (
    advance_to_open_task,
    restore_orchestrator_from_goal_continuation,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.goal_handoff_runtime_bridge import build_handoff_task_records
from tools.ai.task_runtime import TaskStatus


def _three_task_packet() -> dict:
    return {
        "handoff_id": "gh-cross",
        "goal": {"summary": "Implement tetris in sandbox"},
        "scope": {"in_scope": ["tetris/main.py exists"], "affected_paths": ["tetris/main.py"]},
        "acceptance_criteria": [
            {"id": "A1", "statement": "tetris/main.py exists", "verification": "sandbox"}
        ],
        "implementation_tasks": [
            {
                "id": "T1",
                "title": "Create tetris/main.py",
                "acceptance": ["file exists"],
                "verification": [],
                "dependencies": [],
            },
            {
                "id": "T2",
                "title": "Add game loop",
                "acceptance": ["loop runs"],
                "verification": [],
                "dependencies": ["T1"],
            },
            {
                "id": "T3",
                "title": "Add scoring",
                "acceptance": ["score updates"],
                "verification": [],
                "dependencies": ["T2"],
            },
        ],
    }


def _seed_handoff_orchestrator() -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("handoff-exec-1", "implement tetris")
    orchestrator.initialize(handoff_packet=_three_task_packet())
    return orchestrator


def test_cross_execution_restore_keeps_handoff_task_graph():
    first = _seed_handoff_orchestrator()
    first.runtime.tasks["gh-T1"].status = TaskStatus.COMPLETE.value
    first.runtime.tasks["gh-T2"].status = TaskStatus.IN_PROGRESS.value
    first.current_task_id = "gh-T2"

    packet = {
        "kind": "goal_continuation_v0",
        "mission_id": "m-handoff",
        "original_request": first.request,
        "completion_runtime": first.completion_runtime_slice(),
    }
    restored = restore_orchestrator_from_goal_continuation("handoff-exec-2", packet)

    task_ids = set(restored.runtime.tasks.keys())
    assert task_ids == {"gh-T1", "gh-T2", "gh-T3"}
    assert "T1" not in task_ids
    assert restored.runtime.tasks["gh-T2"].source_task_id == "T2"
    assert restored.runtime.tasks["gh-T2"].source == "goal_handoff"
    assert restored.current_task_id == "gh-T2"
    assert restored.runtime.goals["G1"].title.startswith("Implement tetris")


def test_dependency_blocks_runnable_until_predecessor_complete():
    orchestrator = _seed_handoff_orchestrator()
    t1 = orchestrator.runtime.tasks["gh-T1"]
    t2 = orchestrator.runtime.tasks["gh-T2"]
    t3 = orchestrator.runtime.tasks["gh-T3"]

    assert orchestrator.current_task_id == "gh-T1"
    assert t1.status == TaskStatus.IN_PROGRESS.value
    assert t2.status == TaskStatus.PENDING.value
    assert t3.status == TaskStatus.PENDING.value

    assert orchestrator.has_open_runnable_task() is True
    t1.status = TaskStatus.COMPLETE.value
    assert orchestrator.has_open_runnable_task() is True
    assert advance_to_open_task(orchestrator) == "gh-T2"

    t2.status = TaskStatus.COMPLETE.value
    assert advance_to_open_task(orchestrator) == "gh-T3"


def test_build_handoff_records_preserve_dependency_identity():
    _, records, first = build_handoff_task_records(_three_task_packet())
    by_id = {record.task_id: record for record in records}
    assert first == "gh-T1"
    assert by_id["gh-T2"].depends_on == ["gh-T1"]
    assert by_id["gh-T3"].depends_on == ["gh-T2"]
    assert by_id["gh-T3"].source_task_id == "T3"
