"""Pending task supersession after premise revalidation."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

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
from ai_tool.mission_memory.task_runtime import load_mission_completion_runtime
from ai_tool.premise_pending_replacement import (
    PREMISE_PENDING_REPLACEMENT_SOURCE,
    run_premise_pending_replacements,
)
from ai_tool.production_handoff_bridge import (
    build_production_handoff_packet,
    prepare_production_handoff_orchestrator,
)
from ai_tool.task_execution_guard import TaskExecutionBlockedError
from tests.ai_tool.test_production_handoff_decision_supply import (
    D_JSON_V1,
    D_JSON_V2,
    KEY_JSON,
    _decisions,
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


def _json_follower_plan_tasks() -> list[dict]:
    return [
        {
            "id": "TJSON",
            "title": "Emit JSON API output",
            "acceptance": ["JSON response available"],
            "verification": ["json endpoint returns payload"],
            "dependencies": [],
            "size": "S",
            "premise_decision_keys": [KEY_JSON],
        },
        {
            "id": "TFOLLOW",
            "title": "Consume JSON output",
            "acceptance": ["consumer ready"],
            "verification": ["consumer check"],
            "dependencies": ["TJSON"],
            "size": "S",
        },
    ]


def _seed_json_pending_orchestrator(mission_store) -> ChatTaskOrchestrator:
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
        _json_follower_plan_tasks(),
        default_acceptance=["done"],
        default_verification=["check"],
    )
    packet = build_production_handoff_packet(
        exec2,
        initial_request="build service",
        plan={"tasks": plan_tasks},
        tech_spec={"summary": "service"},
        store=mission_store,
        handoff_slug="pending-replacement-e2e",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    exec2.current_task_id = "gh-T1"
    exec2.runtime.tasks["gh-T1"].status = "pending"
    return exec2


def test_pending_task_superseded_with_replacement_premise_and_resume(mission_store):
    orchestrator = _seed_json_pending_orchestrator(mission_store)
    assert orchestrator.runtime.tasks["gh-T1"].status == "pending"
    orchestrator.current_task_id = "gh-T1"

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
                "reason": "Pending JSON task is stale under Markdown decision.",
            }
        ),
        model="fake",
    )
    assert revalidation_results[0]["outcome"] == "needs_revision"

    replacements = run_premise_pending_replacements(orchestrator, revalidation_results)
    assert len(replacements) == 1
    source = orchestrator.runtime.tasks["gh-T1"]
    replacement_id = replacements[0]["replacement_task_id"]
    replacement = orchestrator.runtime.tasks[replacement_id]

    assert source.status == "cancelled"
    assert source.superseded_by_task_id == replacement_id
    assert source.instruction  # preserved, not overwritten for replacement content
    assert replacement.status == "pending"
    assert replacement.source == PREMISE_PENDING_REPLACEMENT_SOURCE
    assert replacement.source_task_id == "gh-T1"
    assert replacement.supersedes_task_id == "gh-T1"
    assert replacement.source_task_id != replacement.task_id
    assert replacement.decision_premises[0]["derived_from_decision_id"] == D_JSON_V2
    assert orchestrator.current_task_id == replacement_id

    orchestrator.current_task_id = "gh-T1"
    with pytest.raises(TaskExecutionBlockedError):
        orchestrator.assert_current_task_executable_for_premise()

    persist_chat_execution(
        orchestrator,
        stop_reason="PREMISE_PENDING_REPLACEMENT",
        determined=True,
        answer="pending replacement added",
        store=mission_store,
    )
    mission_runtime = load_mission_completion_runtime(orchestrator.mission_id, store=mission_store)
    assert mission_runtime is not None
    resumed = ChatTaskOrchestrator("resume", orchestrator.request)
    bind_execution_identity(resumed, resume_mission_id=orchestrator.mission_id, new_execution=True)
    from ai_tool.mission_memory.clarifications import restore_mission_clarifications

    restore_mission_clarifications(resumed, store=mission_store)
    resumed.apply_completion_runtime(mission_runtime, replace_graph=True)

    restored_source = resumed.runtime.tasks["gh-T1"]
    restored_replacement = next(
        task
        for task in resumed.runtime.tasks.values()
        if task.source == PREMISE_PENDING_REPLACEMENT_SOURCE and task.source_task_id == "gh-T1"
    )
    assert restored_source.status == "cancelled"
    assert restored_source.superseded_by_task_id == restored_replacement.task_id
    assert restored_replacement.decision_premises[0]["derived_from_decision_id"] == D_JSON_V2


def test_downstream_depends_on_redirected_after_pending_replacement(mission_store):
    orchestrator = _seed_json_pending_orchestrator(mission_store)
    follower = orchestrator.runtime.tasks["gh-T2"]
    assert follower.depends_on == ["gh-T1"]

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
        chat_fn=_chat_fixed({"outcome": "invalid", "reason": "stale JSON task"}),
        model="fake",
    )
    replacements = run_premise_pending_replacements(orchestrator)
    assert len(replacements) == 1
    replacement_id = replacements[0]["replacement_task_id"]
    assert replacements[0]["redirected_dependents"] == ["gh-T2"]
    assert orchestrator.runtime.tasks["gh-T2"].depends_on == [replacement_id]
    assert orchestrator.has_open_runnable_task() is True
