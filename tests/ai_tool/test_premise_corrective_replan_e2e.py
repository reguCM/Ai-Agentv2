"""Premise corrective replan for complete tasks and execution hold for stale open tasks."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    supersede_decision,
)
from ai_tool.chat_interface.goal_continuation_resume import (
    restore_orchestrator_from_goal_continuation,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.decision_premise_revalidation import run_premise_revalidations
from ai_tool.dev_skill_pipeline import normalize_implementation_tasks
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.mission_memory.chat_persist import bind_execution_identity, persist_chat_execution
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.task_runtime import load_mission_completion_runtime
from ai_tool.premise_corrective_replan import (
    PREMISE_CORRECTIVE_SOURCE,
    premise_revalidation_blocks_task_execution,
    run_premise_corrective_replans,
)
from ai_tool.task_execution_guard import TaskExecutionBlockedError
from tools.ai.task_runtime import TaskStatus
from ai_tool.production_handoff_bridge import (
    build_production_handoff_packet,
    prepare_production_handoff_orchestrator,
)
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
        handoff_slug="corrective-replan-e2e",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    return exec2


def test_complete_task_gets_corrective_replan_with_d2_premise_and_resume(mission_store):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    orchestrator.runtime.evaluate_task("gh-T1", ["project scaffold exists", "repo ready"])
    orchestrator.runtime.evaluate_task(
        "gh-T2",
        ["JSON response available", "json endpoint returns payload"],
    )
    assert orchestrator.runtime.tasks["gh-T2"].status == "complete"
    assert orchestrator.runtime.tasks["gh-T2"].decision_premises[0]["derived_from_decision_id"] == D_JSON_V1

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
    revalidation_results = run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed(
            {
                "outcome": "needs_revision",
                "reason": "JSON output task is stale under Markdown decision.",
            }
        ),
        model="fake",
    )
    assert revalidation_results[0]["outcome"] == "needs_revision"

    corrective = run_premise_corrective_replans(orchestrator, revalidation_results)
    assert len(corrective) == 1
    source = orchestrator.runtime.tasks["gh-T2"]
    corrective_id = corrective[0]["corrective_task_id"]
    corrective_task = orchestrator.runtime.tasks[corrective_id]

    assert source.status == "complete"
    assert source.decision_premises[0]["derived_from_decision_id"] == D_JSON_V1
    assert corrective_task.source_task_id == "gh-T2"
    assert corrective_task.source == PREMISE_CORRECTIVE_SOURCE
    assert corrective_task.depends_on == ["gh-T1"]
    assert "gh-T2" not in corrective_task.depends_on
    assert corrective_task.decision_premises == [
        {
            "decision_key": KEY_JSON,
            "derived_from_decision_id": D_JSON_V2,
            "validated_against_decision_id": D_JSON_V2,
        }
    ]
    assert corrective_task.decision_premises[0]["derived_from_decision_id"] != D_JSON_V1

    persist_chat_execution(
        orchestrator,
        stop_reason="PREMISE_CORRECTIVE_REPLAN",
        determined=True,
        answer="corrective replan added",
        store=mission_store,
    )
    mission_runtime = load_mission_completion_runtime(orchestrator.mission_id, store=mission_store)
    assert mission_runtime is not None
    resumed = ChatTaskOrchestrator("resume", orchestrator.request)
    bind_execution_identity(resumed, resume_mission_id=orchestrator.mission_id, new_execution=True)
    from ai_tool.mission_memory.clarifications import restore_mission_clarifications

    restore_mission_clarifications(resumed, store=mission_store)
    resumed.apply_completion_runtime(mission_runtime, replace_graph=True)

    assert resumed.runtime.tasks["gh-T2"].status == "complete"
    restored_corrective = next(
        task
        for task in resumed.runtime.tasks.values()
        if task.source == PREMISE_CORRECTIVE_SOURCE and task.source_task_id == "gh-T2"
    )
    assert restored_corrective.decision_premises[0]["derived_from_decision_id"] == D_JSON_V2
    assert restored_corrective.depends_on == ["gh-T1"]


def test_in_progress_invalid_task_is_execution_blocked_without_replacement(mission_store):
    orchestrator = _seed_handoff_orchestrator(mission_store)
    orchestrator.runtime.evaluate_task("gh-T1", ["project scaffold exists", "repo ready"])
    orchestrator.current_task_id = "gh-T2"
    orchestrator.runtime.tasks["gh-T2"].status = TaskStatus.IN_PROGRESS.value
    assert orchestrator.runtime.tasks["gh-T2"].status != "complete"

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
        chat_fn=_chat_fixed(
            {
                "outcome": "invalid",
                "reason": "Pending JSON task cannot continue under Markdown.",
            }
        ),
        model="fake",
    )
    corrective = run_premise_corrective_replans(orchestrator)
    assert corrective == []

    stale = orchestrator.runtime.tasks["gh-T2"]
    block = premise_revalidation_blocks_task_execution(stale)
    assert block is not None
    assert block["outcome"] == "invalid"
    wrapped = orchestrator.premise_execution_block_for_task("gh-T2")
    assert wrapped is not None
    assert wrapped["outcome"] == block["outcome"]
    assert wrapped["reason"] == "premise_revalidation_execution_blocked"

    orchestrator.current_task_id = "gh-T2"
    with pytest.raises(TaskExecutionBlockedError):
        orchestrator.assert_current_task_executable_for_premise()

    assert sum(
        1
        for task in orchestrator.runtime.tasks.values()
        if task.source == PREMISE_CORRECTIVE_SOURCE and task.source_task_id == "gh-T2"
    ) == 0
