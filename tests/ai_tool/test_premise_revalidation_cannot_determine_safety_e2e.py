"""Safety-0: premise cannot_determine blocks execution and goal completion."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.agent_turn import _incomplete_goal_stop_reason
from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    supersede_decision,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.decision_premise_revalidation import run_premise_revalidations
from ai_tool.dev_skill_pipeline import normalize_implementation_tasks
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.mission_memory.chat_persist import bind_execution_identity, persist_chat_execution
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.premise_corrective_replan import premise_revalidation_blocks_task_execution
from ai_tool.production_handoff_bridge import (
    build_production_handoff_packet,
    prepare_production_handoff_orchestrator,
)
from ai_tool.task_execution_guard import TaskExecutionBlockedError
from tools.ai.task_runtime import TaskStatus
from tests.ai_tool.test_production_handoff_decision_supply import (
    D_JSON_V1,
    D_JSON_V2,
    KEY_JSON,
    _decisions,
    _plan_tasks,
)


@pytest.fixture
def mission_store(tmp_path, monkeypatch):
    root = tmp_path / "mission_memory"
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: root,
    )
    return MissionMemoryStore(root)


def _response_json(payload: dict):
    return SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)))


def _chat_fixed(payload: dict):
    def chat(**_kwargs):
        return _response_json(payload)

    return chat


def _seed_handoff_orchestrator(mission_store) -> ChatTaskOrchestrator:
    exec1 = ChatTaskOrchestrator("exec-1", "build service")
    bind_execution_identity(exec1)
    exec1.confirmed_clarifications = list(_decisions())
    recorded = persist_chat_execution(
        exec1,
        stop_reason="DETERMINED",
        determined=True,
        answer="decisions saved",
        store=mission_store,
    )
    exec2 = ChatTaskOrchestrator("exec-2", "build service")
    bind_execution_identity(exec2, resume_mission_id=recorded["mission_id"])
    prepare_production_handoff_orchestrator(exec2, store=mission_store)
    plan_tasks = normalize_implementation_tasks(
        _plan_tasks(),
        default_acceptance=["done"],
        default_verification=["check"],
    )
    packet = build_production_handoff_packet(
        exec2,
        initial_request="build service",
        plan={"tasks": plan_tasks},
        tech_spec={"summary": "service"},
        store=mission_store,
        handoff_slug="premise-cannot-determine-safety",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    return exec2


def test_premise_cannot_determine_blocks_in_progress_execution_and_goal_completion(
    mission_store,
):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    orchestrator.runtime.evaluate_task("gh-T1", ["project scaffold exists", "repo ready"])
    orchestrator.current_task_id = "gh-T2"
    orchestrator.runtime.tasks["gh-T2"].status = TaskStatus.IN_PROGRESS.value

    supersede_decision(
        orchestrator,
        D_JSON_V1,
        {
            "decision_id": D_JSON_V2,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "Markdown",
            "dimension": "acceptance",
        },
        execution_id=orchestrator.execution_id,
    )
    results = run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed(
            {
                "outcome": "cannot_determine",
                "reason": "Ambiguous whether Markdown applies to this task.",
            }
        ),
        model="fake",
    )
    assert len(results) == 1
    assert results[0]["outcome"] == "cannot_determine"

    stale = orchestrator.runtime.tasks["gh-T2"]
    block = premise_revalidation_blocks_task_execution(stale)
    assert block is not None
    assert block["outcome"] == "cannot_determine"
    assert block["task_status"] == TaskStatus.IN_PROGRESS.value

    wrapped = orchestrator.premise_execution_block_for_task("gh-T2")
    assert wrapped is not None
    assert wrapped["outcome"] == "cannot_determine"

    orchestrator.current_task_id = "gh-T2"
    with pytest.raises(TaskExecutionBlockedError):
        orchestrator.assert_current_task_executable_for_premise()

    completion_block = orchestrator.premise_revalidation_goal_completion_block()
    assert completion_block is not None
    assert completion_block["reason"] == "premise_revalidation_unresolved"
    assert _incomplete_goal_stop_reason(orchestrator) is not None


def test_premise_still_valid_does_not_block_execution(mission_store):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    orchestrator.runtime.evaluate_task("gh-T1", ["project scaffold exists", "repo ready"])
    orchestrator.current_task_id = "gh-T2"
    orchestrator.runtime.tasks["gh-T2"].status = TaskStatus.IN_PROGRESS.value

    supersede_decision(
        orchestrator,
        D_JSON_V1,
        {
            "decision_id": D_JSON_V2,
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "Markdown",
            "dimension": "acceptance",
        },
        execution_id=orchestrator.execution_id,
    )
    run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "still_valid", "reason": "Task remains valid."}),
        model="fake",
    )

    task = orchestrator.runtime.tasks["gh-T2"]
    assert premise_revalidation_blocks_task_execution(task) is None
    orchestrator.current_task_id = "gh-T2"
    orchestrator.assert_current_task_executable_for_premise()
    assert orchestrator.premise_revalidation_goal_completion_block() is None
