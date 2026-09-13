from __future__ import annotations

from ai_tool.goal_handoff_runtime_bridge import (
    HANDOFF_TASK_SOURCE,
    build_handoff_task_records,
    runtime_task_id,
    seed_orchestrator_from_handoff,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.task_runtime import TaskStatus


def _sample_packet() -> dict:
    return {
        "handoff_id": "gh-test",
        "goal": {"summary": "Create tetris/main.py in Dedicated Sandbox"},
        "scope": {
            "in_scope": ["tetris/main.py exists"],
            "affected_paths": ["tetris/main.py"],
        },
        "acceptance_criteria": [
            {"id": "A1", "statement": "tetris/main.py exists", "verification": "sandbox"}
        ],
        "implementation_tasks": [
            {
                "id": "T1",
                "title": "Create tetris/main.py",
                "acceptance": ["tetris/main.py exists in Sandbox"],
                "verification": ["list_files observes tetris/main.py"],
                "dependencies": [],
            },
            {
                "id": "T2",
                "title": "Verify runnable game loop",
                "acceptance": ["python tetris/main.py starts"],
                "verification": [],
                "dependencies": ["T1"],
            },
        ],
    }


def test_runtime_task_id_preserves_handoff_identity():
    assert runtime_task_id("T1") == "gh-T1"


def test_build_handoff_task_records_maps_source_fields():
    root, records, first = build_handoff_task_records(_sample_packet())
    assert root.goal_id == "G1"
    assert first == "gh-T1"
    assert len(records) == 2
    t1 = records[0]
    assert t1.task_id == "gh-T1"
    assert t1.source == HANDOFF_TASK_SOURCE
    assert t1.source_task_id == "T1"
    assert t1.status == TaskStatus.IN_PROGRESS.value
    t2 = records[1]
    assert t2.task_id == "gh-T2"
    assert t2.source_task_id == "T2"
    assert t2.depends_on == ["gh-T1"]
    assert t2.status == TaskStatus.PENDING.value


def test_seed_orchestrator_from_handoff_is_deterministic():
    packet = _sample_packet()
    first = ChatTaskOrchestrator("seed-a", "implement tetris")
    seed_orchestrator_from_handoff(first, packet)
    second = ChatTaskOrchestrator("seed-b", "implement tetris")
    seed_orchestrator_from_handoff(second, packet)
    assert first.current_task_id == second.current_task_id == "gh-T1"
    assert [task.task_id for task in first.runtime.tasks.values()] == [
        task.task_id for task in second.runtime.tasks.values()
    ]
    assert first.runtime.tasks["gh-T1"].source_task_id == "T1"
