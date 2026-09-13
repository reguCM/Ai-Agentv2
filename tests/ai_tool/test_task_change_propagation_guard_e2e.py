"""Persistent graph-level safety for task change propagation (Cases 1-5)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.agent_turn import (
    LoopStopReason,
    _boundary_grill_post_apply_reroute,
    _incomplete_goal_stop_reason,
)
from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    supersede_decision,
)
from ai_tool.chat_interface.gap_resolution_router import (
    CapabilityId,
    GapKind,
    route_gap_resolution_from_orchestrator,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.decision_premise_revalidation import run_premise_revalidations
from ai_tool.dev_skill_pipeline import normalize_implementation_tasks
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.mission_memory.chat_persist import bind_execution_identity, persist_chat_execution
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.task_runtime import load_mission_completion_runtime
from ai_tool.premise_pending_replacement import run_premise_pending_replacements
from ai_tool.task_change_propagation_guard import (
    GRAPH_STOP_REASON,
    GUARD_KEY,
    effective_stop_reason_for_boundary_grill,
    get_propagation_guard,
    graph_propagation_blocks_execution,
    propagation_blocks_goal_completion,
)
from ai_tool.task_execution_guard import TaskExecutionBlockedError, task_execution_blocked
from ai_tool.task_upstream_supersession_revalidation import (
    STOP_REASON_CONVERGED,
    STOP_REASON_MAX_WAVES_REACHED,
    STOP_REASON_REPEATED_CHANGE_SET,
    run_task_change_propagation,
)
from ai_tool.production_handoff_bridge import (
    build_production_handoff_packet,
    prepare_production_handoff_orchestrator,
)
from tests.ai_tool.test_production_handoff_decision_supply import (
    D_JSON_V1,
    D_JSON_V2,
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


def _propagation_plan_tasks() -> list[dict]:
    return [
        {
            "id": "TROOT",
            "title": "Root upstream",
            "acceptance": ["root ready"],
            "verification": ["root check"],
            "dependencies": [],
            "size": "S",
            "premise_decision_keys": [KEY_JSON],
        },
        {
            "id": "TBRANCHA",
            "title": "Branch A downstream",
            "acceptance": ["branch A ready"],
            "verification": ["branch A check"],
            "dependencies": ["TROOT"],
            "size": "S",
        },
        {
            "id": "TBRANCHB",
            "title": "Branch B downstream",
            "acceptance": ["branch B ready"],
            "verification": ["branch B check"],
            "dependencies": ["TROOT"],
            "size": "S",
        },
        {
            "id": "TDEEP",
            "title": "Deep downstream",
            "acceptance": ["deep ready"],
            "verification": ["deep check"],
            "dependencies": ["TBRANCHA"],
            "size": "S",
        },
    ]


def _seed_propagation_orchestrator(mission_store) -> ChatTaskOrchestrator:
    exec1 = ChatTaskOrchestrator("exec-1", "build service")
    bind_execution_identity(exec1)
    exec1.confirmed_clarifications = list(_decisions())
    persist_chat_execution(
        exec1,
        stop_reason="DETERMINED",
        determined=True,
        answer="decisions saved",
        store=mission_store,
    )
    exec2 = ChatTaskOrchestrator("exec-2", "build service")
    bind_execution_identity(exec2, resume_mission_id=exec1.mission_id)
    prepare_production_handoff_orchestrator(exec2, store=mission_store)
    plan_tasks = normalize_implementation_tasks(
        _propagation_plan_tasks(),
        default_acceptance=["done"],
        default_verification=["check"],
    )
    packet = build_production_handoff_packet(
        exec2,
        initial_request="build service",
        plan={"tasks": plan_tasks},
        tech_spec={"summary": "service"},
        store=mission_store,
        handoff_slug="task-change-propagation-guard-e2e",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    for task_id in list(exec2.runtime.tasks):
        exec2.runtime.tasks[task_id].status = TaskStatus.PENDING.value
    return exec2


def _task_ids(orchestrator: ChatTaskOrchestrator) -> dict[str, str]:
    by_title = {
        str(task.title): str(task_id)
        for task_id, task in orchestrator.runtime.tasks.items()
    }
    return {
        "root": by_title["Root upstream"],
        "branch_a": by_title["Branch A downstream"],
        "branch_b": by_title["Branch B downstream"],
        "deep": by_title["Deep downstream"],
    }


def _routing_chat(outcomes: dict[str, str]):
    def chat(**kwargs):
        content = kwargs["messages"][0]["content"]
        for task_id, outcome in outcomes.items():
            if f"Downstream task ID: {task_id}" in content:
                return _response_json({"outcome": outcome, "reason": f"test {outcome}"})
        return _response_json({"outcome": "still_valid", "reason": "default still valid"})

    return chat


def _root_replacement(orchestrator: ChatTaskOrchestrator) -> dict[str, str]:
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
        chat_fn=lambda **_kwargs: _response_json(
            {"outcome": "needs_revision", "reason": "root stale"}
        ),
        model="fake",
    )
    replacements = run_premise_pending_replacements(orchestrator)
    assert len(replacements) == 1
    return {
        "old_task_id": replacements[0]["source_task_id"],
        "new_task_id": replacements[0]["new_upstream_task_id"],
    }


def _assert_graph_unresolved_safety(orchestrator: ChatTaskOrchestrator) -> None:
    guard = get_propagation_guard(orchestrator)
    assert guard is not None
    assert guard["unresolved"] is True
    assert guard["graph_converged"] is False
    assert graph_propagation_blocks_execution(orchestrator) is not None
    assert propagation_blocks_goal_completion(orchestrator) is not None
    with pytest.raises(TaskExecutionBlockedError) as exc:
        orchestrator.assert_current_task_executable_for_premise()
    assert exc.value.payload.get("reason") == GRAPH_STOP_REASON
    assert _incomplete_goal_stop_reason(orchestrator) is not LoopStopReason.COMPLETED
    assert _incomplete_goal_stop_reason(orchestrator) is not None


def test_case1_max_waves_reached_blocks_execution_and_goal_completion(mission_store):
    orchestrator = _seed_propagation_orchestrator(mission_store)
    ids = _task_ids(orchestrator)
    root_change = _root_replacement(orchestrator)

    result = run_task_change_propagation(
        orchestrator,
        [root_change],
        chat_fn=_routing_chat(
            {
                ids["branch_a"]: "needs_revision",
                ids["branch_b"]: "needs_revision",
                ids["deep"]: "needs_revision",
            }
        ),
        model="fake",
        propagation_id="guard-case1",
        max_waves=2,
    )

    assert result["stop_reason"] == STOP_REASON_MAX_WAVES_REACHED
    assert result["converged"] is False
    _assert_graph_unresolved_safety(orchestrator)

    slice_row = orchestrator.completion_runtime_slice()
    assert GUARD_KEY in slice_row
    assert slice_row[GUARD_KEY]["unresolved"] is True


def test_case2_persisted_guard_survives_cross_execution_resume(mission_store):
    orchestrator = _seed_propagation_orchestrator(mission_store)
    ids = _task_ids(orchestrator)
    root_change = _root_replacement(orchestrator)
    run_task_change_propagation(
        orchestrator,
        [root_change],
        chat_fn=_routing_chat(
            {
                ids["branch_a"]: "needs_revision",
                ids["branch_b"]: "needs_revision",
                ids["deep"]: "needs_revision",
            }
        ),
        model="fake",
        propagation_id="guard-case2",
        max_waves=2,
    )

    persist_chat_execution(
        orchestrator,
        stop_reason=GRAPH_STOP_REASON,
        determined=True,
        answer="propagation guard saved",
        store=mission_store,
    )
    mission_runtime = load_mission_completion_runtime(orchestrator.mission_id, store=mission_store)
    assert mission_runtime.get(GUARD_KEY, {}).get("unresolved") is True

    resumed = ChatTaskOrchestrator("resume", orchestrator.request)
    bind_execution_identity(resumed, resume_mission_id=orchestrator.mission_id, new_execution=True)
    resumed.apply_completion_runtime(mission_runtime, replace_graph=True)

    _assert_graph_unresolved_safety(resumed)
    assert resumed.graph_propagation_execution_block() is not None


def test_case3_repeated_change_set_blocks_without_success(mission_store, monkeypatch):
    orchestrator = _seed_propagation_orchestrator(mission_store)
    root_change = _root_replacement(orchestrator)
    from ai_tool.task_upstream_supersession_revalidation import run_upstream_supersession_wave as real_wave

    def cycling_wave(orch, rows, **kwargs):
        wave_index = kwargs.get("wave_index")
        if wave_index == 0:
            return {
                "propagation_id": kwargs.get("propagation_id"),
                "wave_index": wave_index,
                "evaluations": [],
                "completed_wave_index": wave_index,
                "successor_changes": [root_change],
                "consumed": [],
            }
        return real_wave(orch, rows, **kwargs)

    monkeypatch.setattr(
        "ai_tool.task_upstream_supersession_revalidation.run_upstream_supersession_wave",
        cycling_wave,
    )
    result = run_task_change_propagation(
        orchestrator,
        [root_change],
        chat_fn=lambda **_kwargs: _response_json(
            {"outcome": "still_valid", "reason": "noop"}
        ),
        model="fake",
        propagation_id="guard-case3",
        max_waves=4,
    )

    assert result["stop_reason"] == STOP_REASON_REPEATED_CHANGE_SET
    assert result["converged"] is False
    _assert_graph_unresolved_safety(orchestrator)


def test_case4_converged_with_held_allows_unrelated_execution_blocks_goal(mission_store):
    orchestrator = _seed_propagation_orchestrator(mission_store)
    ids = _task_ids(orchestrator)
    root_change = _root_replacement(orchestrator)

    result = run_task_change_propagation(
        orchestrator,
        [root_change],
        chat_fn=_routing_chat(
            {
                ids["branch_a"]: "cannot_determine",
                ids["branch_b"]: "still_valid",
                ids["deep"]: "still_valid",
            }
        ),
        model="fake",
        propagation_id="guard-case4",
        max_waves=4,
    )

    assert result["stop_reason"] == STOP_REASON_CONVERGED
    assert result["converged"] is True
    assert result["held_tasks"]

    guard = get_propagation_guard(orchestrator)
    assert guard is not None
    assert guard["graph_converged"] is True
    assert guard["unresolved"] is True
    assert graph_propagation_blocks_execution(orchestrator) is None
    assert propagation_blocks_goal_completion(orchestrator) is not None

    held_task = orchestrator.runtime.tasks[ids["branch_a"]]
    runnable_task = orchestrator.runtime.tasks[ids["branch_b"]]
    assert task_execution_blocked(held_task) is not None
    assert task_execution_blocked(runnable_task) is None

    orchestrator.current_task_id = ids["branch_b"]
    orchestrator.assert_current_task_executable_for_premise()

    orchestrator.current_task_id = ids["branch_a"]
    with pytest.raises(TaskExecutionBlockedError):
        orchestrator.assert_current_task_executable_for_premise()

    assert _incomplete_goal_stop_reason(orchestrator) is not None


def test_case5_boundary_grill_propagation_non_converged_reroutes_with_help(mission_store):
    orchestrator = _seed_propagation_orchestrator(mission_store)
    ids = _task_ids(orchestrator)
    root_change = _root_replacement(orchestrator)
    run_task_change_propagation(
        orchestrator,
        [root_change],
        chat_fn=_routing_chat(
            {
                ids["branch_a"]: "needs_revision",
                ids["branch_b"]: "needs_revision",
                ids["deep"]: "needs_revision",
            }
        ),
        model="fake",
        propagation_id="guard-case5",
        max_waves=2,
    )

    effective, note = effective_stop_reason_for_boundary_grill(
        "DECISION_CHANGE_CONFIRMED",
        orchestrator,
    )
    assert effective == GRAPH_STOP_REASON
    assert note is not None
    assert "未収束" in note

    decision = route_gap_resolution_from_orchestrator(
        orchestrator,
        stop_reason=effective,
        answer_gate={"verified": False, "reason": "completion_evidence_incomplete"},
    )
    assert decision.gap_kind == GapKind.STAGNATION_EXHAUSTED.value
    assert decision.winner == CapabilityId.HELP.value

    events: list[dict] = [{"type": "decision_superseded"}]
    result = _boundary_grill_post_apply_reroute(
        orchestrator,
        events=events,
        correlation_id="guard-case5",
        memory={},
        model="fake",
        applied={"needs_more_boundary_grill": False},
        stop_reason="DECISION_CHANGE_CONFIRMED",
        lifecycle_suffix="test",
        chat_fn=None,
    )
    event_types = [str(item.get("type") or "") for item in result.get("events") or []]
    assert "boundary_grill_reroute" in event_types
    assert "gap_resolution_routed" in event_types
    assert result.get("gap_resolution", {}).get("gap_kind") == GapKind.STAGNATION_EXHAUSTED.value
    assert result.get("gap_resolution", {}).get("winner") == CapabilityId.HELP.value
    assert "未収束" in str(result.get("answer") or "")
