"""Upstream supersession revalidation for downstream tasks."""
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
from ai_tool.premise_corrective_replan import run_premise_corrective_replans
from ai_tool.premise_pending_replacement import run_premise_pending_replacements
from ai_tool.task_execution_guard import task_execution_blocked
from ai_tool.task_upstream_supersession_revalidation import (
    canonical_change_set,
    change_set_identity,
    consume_upstream_supersession_outcomes,
    run_upstream_supersession_revalidations,
    run_upstream_supersession_wave,
    successor_already_generated,
    upstream_supersession_metadata,
)
from ai_tool.production_handoff_bridge import (
    build_production_handoff_packet,
    prepare_production_handoff_orchestrator,
)
from tests.ai_tool.test_production_handoff_decision_supply import (
    D_GUI_V1,
    D_JSON_V1,
    D_JSON_V2,
    KEY_GUI,
    KEY_JSON,
    _decisions,
)
from tools.ai.task_runtime import TaskStatus


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


def _seed_orchestrator(mission_store) -> ChatTaskOrchestrator:
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
        handoff_slug="upstream-supersession-e2e",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    return exec2


def _supersede_json_decision(orchestrator: ChatTaskOrchestrator) -> None:
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


def test_pending_replacement_downstream_still_valid_then_ordering_hold(mission_store):
    orchestrator = _seed_orchestrator(mission_store)
    orchestrator.current_task_id = "gh-T1"
    orchestrator.runtime.tasks["gh-T1"].status = TaskStatus.PENDING.value
    follower_id = "gh-T2"

    _supersede_json_decision(orchestrator)
    revalidation_results = run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "stale JSON task"}),
        model="fake",
    )
    replacements = run_premise_pending_replacements(orchestrator, revalidation_results)
    assert len(replacements) == 1
    replacement_id = replacements[0]["new_upstream_task_id"]

    follower = orchestrator.runtime.tasks[follower_id]
    assert follower.depends_on == [replacement_id]

    upstream = run_upstream_supersession_revalidations(
        orchestrator,
        replacements,
        chat_fn=_chat_fixed({"outcome": "still_valid", "reason": "consumer still valid"}),
        model="fake",
    )
    assert upstream[0]["outcome"] == "still_valid"
    assert task_execution_blocked(follower) is None
    assert orchestrator.has_open_runnable_task() is True
    assert orchestrator.current_task_id == replacement_id

    runnable_before = [
        task_id
        for task_id, task in orchestrator.runtime.tasks.items()
        if task.status not in {TaskStatus.COMPLETE.value, TaskStatus.CANCELLED.value}
        and task_execution_blocked(task) is None
        and all(
            orchestrator.runtime.tasks[dep].status == TaskStatus.COMPLETE.value
            for dep in (task.depends_on or [])
            if dep in orchestrator.runtime.tasks
        )
    ]
    assert follower_id not in runnable_before

    orchestrator.runtime.evaluate_task(
        replacement_id,
        list(orchestrator.runtime.tasks[replacement_id].completion_conditions),
    )
    assert orchestrator.runtime.tasks[replacement_id].status == TaskStatus.COMPLETE.value
    assert orchestrator.has_open_runnable_task() is True
    assert follower_id in {
        task_id
        for task_id, task in orchestrator.runtime.tasks.items()
        if task.status not in {TaskStatus.COMPLETE.value, TaskStatus.CANCELLED.value}
        and task_execution_blocked(task) is None
        and all(
            orchestrator.runtime.tasks[dep].status == TaskStatus.COMPLETE.value
            for dep in (task.depends_on or [])
            if dep in orchestrator.runtime.tasks
        )
    }


def test_complete_upstream_corrective_redirects_and_holds_downstream(mission_store):
    orchestrator = _seed_orchestrator(mission_store)
    orchestrator.runtime.evaluate_task(
        "gh-T1",
        ["JSON response available", "json endpoint returns payload"],
    )
    follower_id = "gh-T2"
    assert orchestrator.runtime.tasks["gh-T1"].status == TaskStatus.COMPLETE.value
    assert orchestrator.runtime.tasks[follower_id].depends_on == ["gh-T1"]

    _supersede_json_decision(orchestrator)
    revalidation_results = run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "completed JSON stale"}),
        model="fake",
    )
    correctives = run_premise_corrective_replans(orchestrator, revalidation_results)
    assert len(correctives) == 1
    corrective_id = correctives[0]["new_upstream_task_id"]
    follower = orchestrator.runtime.tasks[follower_id]

    assert orchestrator.runtime.tasks["gh-T1"].status == TaskStatus.COMPLETE.value
    assert follower.depends_on == [corrective_id]

    run_upstream_supersession_revalidations(
        orchestrator,
        correctives,
        chat_fn=_chat_fixed({"outcome": "still_valid", "reason": "consumer still valid"}),
        model="fake",
    )
    assert task_execution_blocked(follower) is None
    assert orchestrator.has_open_runnable_task() is True
    assert follower_id not in {
        task_id
        for task_id, task in orchestrator.runtime.tasks.items()
        if task.status not in {TaskStatus.COMPLETE.value, TaskStatus.CANCELLED.value}
        and task_execution_blocked(task) is None
        and all(
            orchestrator.runtime.tasks[dep].status == TaskStatus.COMPLETE.value
            for dep in (task.depends_on or [])
            if dep in orchestrator.runtime.tasks
        )
    }


def test_case_a_pending_downstream_needs_revision_generates_replacement_once(mission_store):
    orchestrator = _seed_orchestrator(mission_store)
    orchestrator.current_task_id = "gh-T1"
    orchestrator.runtime.tasks["gh-T1"].status = TaskStatus.PENDING.value
    follower_id = "gh-T2"

    _supersede_json_decision(orchestrator)
    run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "invalid", "reason": "stale JSON task"}),
        model="fake",
    )
    replacements = run_premise_pending_replacements(orchestrator)
    wave = run_upstream_supersession_wave(
        orchestrator,
        replacements,
        chat_fn=_chat_fixed(
            {
                "outcome": "needs_revision",
                "reason": "Consumer task assumes JSON interface.",
            }
        ),
        model="fake",
        propagation_id="pw-case-a",
        wave_index=0,
    )
    follower = orchestrator.runtime.tasks[follower_id]
    successor_id = wave["successor_changes"][0]["new_task_id"]
    successor = orchestrator.runtime.tasks[successor_id]

    assert wave["propagation_id"] == "pw-case-a"
    assert wave["wave_index"] == 0
    assert wave["completed_wave_index"] == 0
    assert wave["successor_changes"] == [
        {"old_task_id": follower_id, "new_task_id": successor_id}
    ]
    assert len(wave["evaluations"]) == 1
    assert len(wave["consumed"]) == 1
    assert wave["consumed"][0]["skipped"] is False
    assert follower.status == TaskStatus.CANCELLED.value
    assert follower.superseded_by_task_id == successor_id
    assert task_execution_blocked(follower) is not None
    assert successor.status == TaskStatus.PENDING.value
    assert task_execution_blocked(successor) is None
    meta = upstream_supersession_metadata(follower)
    assert meta is not None
    assert meta["outcome"] == "needs_revision"
    assert meta["successor_change"] == {
        "old_task_id": follower_id,
        "new_task_id": successor_id,
    }

    replacement_id = replacements[0]["new_upstream_task_id"]
    orchestrator.runtime.evaluate_task(
        replacement_id,
        list(orchestrator.runtime.tasks[replacement_id].completion_conditions),
    )
    assert task_execution_blocked(successor) is None
    assert successor_already_generated(
        orchestrator,
        follower_id,
        canonical_change_set(meta["evaluated_against_change_set"]),
    )
    second = consume_upstream_supersession_outcomes(
        orchestrator,
        wave["evaluations"],
        propagation_id="pw-case-a",
        wave_index=0,
    )
    assert second["successor_changes"] == [
        {"old_task_id": follower_id, "new_task_id": successor_id}
    ]
    assert second["consumed"][0]["skipped"] is True


def test_case_b_complete_downstream_needs_revision_generates_corrective_once(mission_store):
    orchestrator = _seed_orchestrator(mission_store)
    follower_id = "gh-T2"
    orchestrator.runtime.evaluate_task(
        "gh-T1",
        ["JSON response available", "json endpoint returns payload"],
    )
    orchestrator.runtime.tasks[follower_id].status = TaskStatus.COMPLETE.value

    _supersede_json_decision(orchestrator)
    run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "completed JSON stale"}),
        model="fake",
    )
    correctives = run_premise_corrective_replans(orchestrator)
    wave = run_upstream_supersession_wave(
        orchestrator,
        correctives,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "completed consumer stale"}),
        model="fake",
        propagation_id="pw-case-b",
        wave_index=0,
    )
    follower = orchestrator.runtime.tasks[follower_id]
    successor_id = wave["successor_changes"][0]["new_task_id"]

    assert follower.status == TaskStatus.COMPLETE.value
    assert wave["successor_changes"] == [
        {"old_task_id": follower_id, "new_task_id": successor_id}
    ]
    assert orchestrator.runtime.tasks[successor_id].source == "premise_corrective_replan"
    assert task_execution_blocked(follower) is not None
    assert task_execution_blocked(orchestrator.runtime.tasks[successor_id]) is None


def test_case_c_in_progress_downstream_needs_revision_keeps_hold_without_successor(mission_store):
    orchestrator = _seed_orchestrator(mission_store)
    orchestrator.runtime.tasks["gh-T1"].status = TaskStatus.PENDING.value
    follower_id = "gh-T2"
    orchestrator.runtime.tasks[follower_id].status = TaskStatus.IN_PROGRESS.value

    _supersede_json_decision(orchestrator)
    run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "stale JSON task"}),
        model="fake",
    )
    replacements = run_premise_pending_replacements(orchestrator)
    wave = run_upstream_supersession_wave(
        orchestrator,
        replacements,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "in progress consumer stale"}),
        model="fake",
        propagation_id="pw-case-c",
        wave_index=0,
    )
    follower = orchestrator.runtime.tasks[follower_id]

    assert wave["successor_changes"] == []
    assert wave["consumed"] == []
    assert follower.status == TaskStatus.IN_PROGRESS.value
    assert task_execution_blocked(follower) is not None
    meta = upstream_supersession_metadata(follower)
    assert meta["outcome"] == "needs_revision"
    assert meta.get("successor_change") is None


def test_case_d_still_valid_releases_hold_without_successor(mission_store):
    orchestrator = _seed_orchestrator(mission_store)
    orchestrator.runtime.tasks["gh-T1"].status = TaskStatus.PENDING.value
    follower_id = "gh-T2"

    _supersede_json_decision(orchestrator)
    run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "stale JSON task"}),
        model="fake",
    )
    replacements = run_premise_pending_replacements(orchestrator)
    wave = run_upstream_supersession_wave(
        orchestrator,
        replacements,
        chat_fn=_chat_fixed({"outcome": "still_valid", "reason": "consumer still valid"}),
        model="fake",
        propagation_id="pw-case-d",
        wave_index=0,
    )
    follower = orchestrator.runtime.tasks[follower_id]

    assert wave["successor_changes"] == []
    assert wave["consumed"] == []
    assert task_execution_blocked(follower) is None
    meta = upstream_supersession_metadata(follower)
    assert meta["outcome"] == "still_valid"


def test_upstream_supersession_persists_through_mission_resume(mission_store):
    orchestrator = _seed_orchestrator(mission_store)
    orchestrator.runtime.evaluate_task(
        "gh-T1",
        ["JSON response available", "json endpoint returns payload"],
    )
    _supersede_json_decision(orchestrator)
    run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "stale"}),
        model="fake",
    )
    correctives = run_premise_corrective_replans(orchestrator)
    run_upstream_supersession_revalidations(
        orchestrator,
        correctives,
        chat_fn=_chat_fixed({"outcome": "still_valid", "reason": "ok"}),
        model="fake",
    )
    persist_chat_execution(
        orchestrator,
        stop_reason="UPSTREAM_SUPERSESSION",
        determined=True,
        answer="upstream supersession saved",
        store=mission_store,
    )
    mission_runtime = load_mission_completion_runtime(orchestrator.mission_id, store=mission_store)
    resumed = ChatTaskOrchestrator("resume", orchestrator.request)
    bind_execution_identity(resumed, resume_mission_id=orchestrator.mission_id, new_execution=True)
    resumed.apply_completion_runtime(mission_runtime, replace_graph=True)
    follower = resumed.runtime.tasks["gh-T2"]
    meta = upstream_supersession_metadata(follower)
    assert meta is not None
    assert meta["outcome"] == "still_valid"
    assert meta["upstream_changes"] == [
        {
            "old_task_id": "gh-T1",
            "new_task_id": correctives[0]["new_upstream_task_id"],
        }
    ]


def _dual_upstream_plan_tasks() -> list[dict]:
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
            "id": "TGUI",
            "title": "Build GUI screen",
            "acceptance": ["GUI visible"],
            "verification": ["manual UI check"],
            "dependencies": [],
            "size": "S",
            "premise_decision_keys": [KEY_GUI],
        },
        {
            "id": "TINTEG",
            "title": "Integrate JSON and GUI",
            "acceptance": ["integrated surface ready"],
            "verification": ["integration check"],
            "dependencies": ["TJSON", "TGUI"],
            "size": "M",
        },
    ]


def _seed_dual_upstream_orchestrator(mission_store) -> ChatTaskOrchestrator:
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
        _dual_upstream_plan_tasks(),
        default_acceptance=["done"],
        default_verification=["check"],
    )
    packet = build_production_handoff_packet(
        exec2,
        initial_request="build service",
        plan={"tasks": plan_tasks},
        tech_spec={"summary": "service"},
        store=mission_store,
        handoff_slug="upstream-wave-e2e",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    for task_id in ("gh-T1", "gh-T2"):
        exec2.runtime.tasks[task_id].status = TaskStatus.PENDING.value
    return exec2


def test_multi_upstream_wave_aggregates_pairs_and_evaluates_once(mission_store):
    orchestrator = _seed_dual_upstream_orchestrator(mission_store)
    integrator_id = "gh-T3"
    assert set(orchestrator.runtime.tasks[integrator_id].depends_on) == {"gh-T1", "gh-T2"}

    _supersede_json_decision(orchestrator)
    supersede_decision(
        orchestrator,
        D_GUI_V1,
        {
            "decision_id": "d-gui-v2",
            "decision_key": KEY_GUI,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "GUIなし",
            "dimension": "scope",
        },
        execution_id=orchestrator.execution_id,
    )
    run_premise_revalidations(
        orchestrator,
        chat_fn=_chat_fixed({"outcome": "needs_revision", "reason": "stale upstream"}),
        model="fake",
    )
    replacements = run_premise_pending_replacements(orchestrator)
    assert len(replacements) == 2
    replacement_by_source = {row["source_task_id"]: row for row in replacements}
    successor_rows = [replacement_by_source["gh-T2"], replacement_by_source["gh-T1"]]

    call_count = {"n": 0}

    def counting_chat(**_kwargs):
        call_count["n"] += 1
        return _response_json({"outcome": "still_valid", "reason": "integrated task still valid"})

    upstream = run_upstream_supersession_revalidations(
        orchestrator,
        successor_rows,
        chat_fn=counting_chat,
        model="fake",
        propagation_id="pw-test-wave-1",
    )
    assert call_count["n"] == 1
    assert len(upstream) == 1
    integrator = orchestrator.runtime.tasks[integrator_id]
    meta = upstream_supersession_metadata(integrator)
    assert meta is not None
    assert meta["propagation_id"] == "pw-test-wave-1"
    assert canonical_change_set(meta["upstream_changes"]) == canonical_change_set(
        [
            {"old_task_id": "gh-T1", "new_task_id": replacement_by_source["gh-T1"]["new_upstream_task_id"]},
            {"old_task_id": "gh-T2", "new_task_id": replacement_by_source["gh-T2"]["new_upstream_task_id"]},
        ]
    )
    assert meta["outcome"] == "still_valid"
    assert task_execution_blocked(integrator) is None

    reversed_rows = [replacement_by_source["gh-T1"], replacement_by_source["gh-T2"]]
    skipped = run_upstream_supersession_revalidations(
        orchestrator,
        reversed_rows,
        chat_fn=counting_chat,
        model="fake",
        propagation_id="pw-test-wave-2",
    )
    assert call_count["n"] == 1
    assert skipped[0]["skipped"] is True
    assert skipped[0]["change_set_identity"] == meta.get("change_set_identity")
    assert skipped[0]["change_set_identity"] == change_set_identity(meta["upstream_changes"])
