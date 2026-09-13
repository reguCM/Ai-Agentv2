"""Production verification / Goal Acceptance reconnection (no Tetris-hardcoded runtime)."""
from __future__ import annotations

from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.mission_memory.chat_persist import persist_chat_execution
from ai_tool.production_verification_acceptance import (
    TEST_RUN_CLOSED,
    evaluate_handoff_goal_acceptance,
    pending_verification_action,
    pytest_failed_repair_hint,
    resolve_mission_achievement,
)
from tools.ai.task_runtime import ActionRecord, EvidenceRecord, FailureRecord, GoalStatus, TaskStatus


def _packet(*, slug: str, acceptance: list[dict], tasks: list[dict], pytest_targets: list[str]) -> dict:
    return {
        "handoff_id": f"gh-verify-{slug}",
        "goal": {"summary": slug},
        "scope": {"in_scope": [row["statement"] for row in acceptance], "affected_paths": ["app.py"]},
        "acceptance_criteria": acceptance,
        "implementation_tasks": tasks,
        "test_plan": {"pytest": pytest_targets},
    }


def _calc_packet() -> dict:
    return _packet(
        slug="calc",
        acceptance=[
            {
                "id": "A1",
                "statement": "CLI calculator exists",
                "verification": "create_file succeeds",
            },
            {
                "id": "A2",
                "statement": "arithmetic tests pass",
                "verification": "pytest tests/test_calc_cli.py",
            },
        ],
        tasks=[
            {
                "id": "T1",
                "title": "Write calculator",
                "acceptance": ["CLI calculator exists"],
                "verification": ["create_file succeeds"],
                "maps_to_acceptance": ["A1"],
            },
            {
                "id": "T2",
                "title": "Verify arithmetic",
                "acceptance": ["arithmetic tests pass"],
                "verification": ["pytest tests/test_calc_cli.py"],
                "dependencies": ["T1"],
                "maps_to_acceptance": ["A2"],
            },
        ],
        pytest_targets=["tests/test_calc_cli.py"],
    )


def _complete(task) -> None:
    task.satisfied_conditions = list(task.completion_conditions)
    for condition in task.completion_conditions:
        task.condition_status[condition] = "SATISFIED"
    task.status = TaskStatus.COMPLETE.value


def test_all_tasks_complete_is_not_goal_acceptance_pass():
    orch = ChatTaskOrchestrator("va-all-tasks", "PythonでCLIの四則演算電卓を作って")
    seed_orchestrator_from_handoff(orch, _calc_packet())
    for task in orch.runtime.tasks.values():
        orch.runtime.evaluate_task(task.task_id, list(task.completion_conditions))
    synthesis = orch.finish("files exist")
    g1 = orch.runtime.goals["G1"]
    assert g1.status != GoalStatus.COMPLETE.value
    acceptance = evaluate_handoff_goal_acceptance(orch, final_answer="files exist")
    assert acceptance["status"] == "FAIL"
    assert synthesis.get("ready") is False or g1.status != GoalStatus.COMPLETE.value


def test_case_b_file_exists_without_verification_fails_acceptance():
    orch = ChatTaskOrchestrator("va-b", "PythonでCLIの四則演算電卓を作って")
    seed_orchestrator_from_handoff(orch, _calc_packet())
    _complete(orch.runtime.tasks["gh-T1"])
    orch.runtime.add_evidence(
        EvidenceRecord(
            "E1",
            "file",
            "app.py",
            "created",
            "A1",
            tool_name="create_file",
            supported_completion_conditions=["CLI calculator exists"],
        ),
        ["gh-T1"],
    )
    result = evaluate_handoff_goal_acceptance(orch, final_answer="app.py exists")
    assert result["status"] == "FAIL"
    assert result["verification_closed"] is False
    resolved = resolve_mission_achievement(orch, final_answer="app.py exists")
    assert not resolved or not resolved.get("goal_achievement_performed")


def test_case_c_fail_then_repair_then_pass():
    orch = ChatTaskOrchestrator("va-c", "PythonでCLIの四則演算電卓を作って")
    seed_orchestrator_from_handoff(orch, _calc_packet())
    _complete(orch.runtime.tasks["gh-T1"])
    orch.current_task_id = "gh-T2"
    orch.runtime.tasks["gh-T2"].status = TaskStatus.IN_PROGRESS.value
    orch.runtime.record_failure(
        FailureRecord("F1", "gh-T2", "A-test", "run_test_plan", {}, "pytest_failed")
    )
    assert pytest_failed_repair_hint(orch)
    assert pending_verification_action(orch) is None
    orch.runtime.record_action(
        ActionRecord(
            "A-repair",
            "gh-T2",
            "tool_call",
            "edit_file",
            {"path": "app.py"},
            "success",
            "ACCEPT",
            True,
        )
    )
    retry = pending_verification_action(orch)
    assert retry is not None
    assert retry["tool"] == "run_test_plan"
    orch.runtime.add_evidence(
        EvidenceRecord(
            "E-test",
            "test_safety_run",
            "test_safety://A-ok",
            "closed",
            "A-ok",
            tool_name="run_test_plan",
            supported_completion_conditions=[TEST_RUN_CLOSED],
        ),
        ["gh-T2"],
    )
    _complete(orch.runtime.tasks["gh-T2"])
    acceptance = evaluate_handoff_goal_acceptance(orch, final_answer="calculator works")
    assert acceptance["status"] == "PASS"
    resolved = resolve_mission_achievement(orch, final_answer="calculator works")
    assert resolved and resolved.get("goal_achievement_performed") is True
    assert orch.runtime.goals["G1"].status == GoalStatus.COMPLETE.value


def test_case_d_does_not_use_tetris_targets():
    orch = ChatTaskOrchestrator("va-d", "PythonでCLIの四則演算電卓を作って")
    seed_orchestrator_from_handoff(orch, _calc_packet())
    action = pending_verification_action(orch)
    # T1 is observation-only; T2 is current after seed? first runnable is T1
    assert orch.current_task_id == "gh-T1"
    assert action is None
    _complete(orch.runtime.tasks["gh-T1"])
    orch.finish("created")
    action = pending_verification_action(orch)
    commands = ((action or {}).get("arguments") or {}).get("test_plan", {}).get("commands") or []
    joined = " ".join(commands)
    assert "test_calc_cli.py" in joined
    assert "tetris" not in joined.casefold()


def test_mission_persist_does_not_set_achievement_on_fail(tmp_path):
    from ai_tool.mission_memory.store import MissionMemoryStore

    orch = ChatTaskOrchestrator("va-persist", "PythonでCLIの四則演算電卓を作って")
    seed_orchestrator_from_handoff(orch, _calc_packet())
    recorded = persist_chat_execution(
        orch,
        stop_reason="COMPLETED",
        determined=True,
        answer="app.py exists",
        correlation_id="c1",
        store=MissionMemoryStore(tmp_path / "mm"),
    )
    assert recorded["goal_achievement_performed"] is False
    store = MissionMemoryStore(tmp_path / "mm")
    row = store.get_execution(orch.mission_id, orch.execution_id)
    assert row is not None
    assert row.get("goal_achievement_performed") is False
    assert row.get("execution_end_state") != "achieved"


def test_observation_chat_finish_still_uses_all_tasks_complete():
    orch = ChatTaskOrchestrator("va-obs", "現在時刻を答えて")
    orch.initialize()
    orch.runtime.evaluate_task("T1", list(orch.runtime.tasks["T1"].completion_conditions))
    orch.current_task_id = "T2"
    synthesis = orch.finish("now")
    assert orch.runtime.goals["G1"].status == GoalStatus.COMPLETE.value
    assert synthesis["ready"] is True
