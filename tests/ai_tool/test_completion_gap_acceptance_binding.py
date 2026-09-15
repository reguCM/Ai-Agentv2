from __future__ import annotations

import pytest

from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.goal_handoff_runtime_bridge import (
    COMPLETION_GAP_TASK_SOURCE,
    build_handoff_acceptance_runtime_trace,
    register_completion_gap_acceptance_binding,
    restore_orchestrator_from_runtime_snapshot,
    seed_orchestrator_from_handoff,
)
from ai_tool.production_verification_acceptance import handoff_acceptance_extra_failures
from tools.ai.sandbox_workspace import SandboxSession
from tools.ai.task_runtime import TaskRecord, TaskStatus


def _packet() -> dict:
    return {
        "handoff_id": "gh-completion-gap-binding",
        "goal": {"summary": "Verify the completion gap binding"},
        "acceptance_criteria": [
            {"id": "A1", "statement": "criterion one", "verification": "verify one"},
            {"id": "A2", "statement": "criterion two", "verification": "verify two"},
        ],
        "implementation_tasks": [
            {
                "id": "T1",
                "title": "Original task",
                "acceptance": ["criterion one"],
                "verification": ["verify one"],
                "maps_to_acceptance": ["A1", "A2"],
            }
        ],
    }


def _gap_task() -> TaskRecord:
    return TaskRecord(
        task_id="cg-1",
        goal_id="G1",
        title="Verify criterion A1 completion gap",
        instruction="Run the additional verification for A1.",
        completion_conditions=["verification result recorded"],
        status=TaskStatus.PENDING.value,
        source=COMPLETION_GAP_TASK_SOURCE,
        source_task_id="T1",
    )


def _sandbox(tmp_path) -> SandboxSession:
    root = tmp_path / "sandbox"
    root.mkdir()
    return SandboxSession(
        session_id="sandbox-completion-gap-binding",
        sandbox_root=str(root),
        branch="agent-sandbox/completion-gap-binding",
        base_head="base",
        current_head="head",
        status="ACTIVE",
        created_at="2026-09-15T00:00:00Z",
    )


def test_completion_gap_task_binds_to_one_explicit_acceptance_only() -> None:
    orchestrator = ChatTaskOrchestrator("cg-bind", "goal")
    seed_orchestrator_from_handoff(orchestrator, _packet())
    orchestrator.runtime.add_task(_gap_task())

    register_completion_gap_acceptance_binding(
        orchestrator,
        runtime_task_id="cg-1",
        source_task_id="T1",
        acceptance_id="A1",
    )

    trace = build_handoff_acceptance_runtime_trace(orchestrator)
    by_acceptance = {
        row["acceptance_id"]: {
            item["runtime_task_id"] for item in row["mapped_runtime_tasks"]
        }
        for row in trace
    }
    assert "cg-1" in by_acceptance["A1"]
    assert "cg-1" not in by_acceptance["A2"]


def test_completion_gap_binding_persists_and_restores_with_runtime_snapshot(tmp_path, monkeypatch) -> None:
    packet = _packet()
    orchestrator = ChatTaskOrchestrator("cg-restore", "goal")
    seed_orchestrator_from_handoff(orchestrator, packet)
    orchestrator.runtime.add_task(_gap_task())
    register_completion_gap_acceptance_binding(
        orchestrator,
        runtime_task_id="cg-1",
        source_task_id="T1",
        acceptance_id="A1",
    )
    monkeypatch.setattr("tools.ai.task_runtime.verify_sandbox_identity", lambda session: None)
    orchestrator.runtime.attach_sandbox_session(_sandbox(tmp_path))
    snapshot = orchestrator.snapshot()

    restored = ChatTaskOrchestrator("cg-restored", "goal")
    restore_orchestrator_from_runtime_snapshot(restored, packet, snapshot)

    assert restored.completion_gap_acceptance_bindings == [
        {"runtime_task_id": "cg-1", "source_task_id": "T1", "acceptance_id": "A1"}
    ]
    trace = build_handoff_acceptance_runtime_trace(restored)
    a1 = next(row for row in trace if row["acceptance_id"] == "A1")
    assert "cg-1" in {item["runtime_task_id"] for item in a1["mapped_runtime_tasks"]}


def test_invalid_completion_gap_binding_fails_closed() -> None:
    orchestrator = ChatTaskOrchestrator("cg-invalid", "goal")
    seed_orchestrator_from_handoff(orchestrator, _packet())
    orchestrator.runtime.add_task(_gap_task())

    with pytest.raises(ValueError, match="completion_gap_acceptance_not_found:A9"):
        register_completion_gap_acceptance_binding(
            orchestrator,
            runtime_task_id="cg-1",
            source_task_id="T1",
            acceptance_id="A9",
        )
    assert orchestrator.completion_gap_acceptance_bindings == []


def test_bound_completion_gap_task_is_required_for_acceptance_completion() -> None:
    orchestrator = ChatTaskOrchestrator("cg-readiness", "goal")
    seed_orchestrator_from_handoff(orchestrator, _packet())
    orchestrator.runtime.add_task(_gap_task())
    register_completion_gap_acceptance_binding(
        orchestrator,
        runtime_task_id="cg-1",
        source_task_id="T1",
        acceptance_id="A1",
    )
    orchestrator.runtime.tasks["gh-T1"].status = TaskStatus.COMPLETE.value

    failures = handoff_acceptance_extra_failures(orchestrator)
    assert ("TASK_COMPLETION", "Task State", "acceptance A1 mapped tasks are incomplete") in failures
    assert not any("acceptance A2 mapped tasks are incomplete" in row[2] for row in failures)
