"""Multi-wave task change propagation E2E."""
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
from ai_tool.premise_pending_replacement import run_premise_pending_replacements
from ai_tool.task_execution_guard import task_execution_blocked, task_superseded
from ai_tool.task_upstream_supersession_revalidation import (
    STOP_REASON_CONVERGED,
    STOP_REASON_MAX_WAVES_REACHED,
    STOP_REASON_REPEATED_CHANGE_SET,
    run_task_change_propagation,
    upstream_supersession_metadata,
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
        handoff_slug="task-change-propagation-e2e",
    )
    exec2.confirmed_clarifications = list(_decisions())
    seed_orchestrator_from_handoff(exec2, packet)
    for task_id in ("gh-T1", "gh-T2", "gh-T3", "gh-T4"):
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
    evaluated: list[str] = []

    def chat(**kwargs):
        content = kwargs["messages"][0]["content"]
        for task_id, outcome in outcomes.items():
            if f"Downstream task ID: {task_id}" in content:
                evaluated.append(task_id)
                return _response_json({"outcome": outcome, "reason": f"test {outcome}"})
        return _response_json({"outcome": "still_valid", "reason": "default still valid"})

    return chat, evaluated


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


def test_multi_wave_propagation_converges_through_three_waves(mission_store):
    orchestrator = _seed_propagation_orchestrator(mission_store)
    ids = _task_ids(orchestrator)
    root_change = _root_replacement(orchestrator)
    chat_fn, evaluated = _routing_chat(
        {
            ids["branch_a"]: "needs_revision",
            ids["branch_b"]: "still_valid",
            ids["deep"]: "needs_revision",
        }
    )

    result = run_task_change_propagation(
        orchestrator,
        [root_change],
        chat_fn=chat_fn,
        model="fake",
        propagation_id="pw-prop-e2e",
        max_waves=8,
    )

    assert result["propagation_id"] == "pw-prop-e2e"
    assert result["stop_reason"] == STOP_REASON_CONVERGED
    assert result["converged"] is True
    assert result["completed_wave_count"] == 3
    assert len(result["processed_change_sets"]) == 3
    assert len(result["successor_history"]) == 3

    wave0 = result["successor_history"][0]
    wave1 = result["successor_history"][1]
    wave2 = result["successor_history"][2]
    assert wave0["wave_index"] == 0
    assert wave1["wave_index"] == 1
    assert wave2["wave_index"] == 2
    assert wave0["input_changes"] == [root_change]
    assert wave0["successor_changes"][0]["old_task_id"] == ids["branch_a"]
    assert wave1["input_changes"][0]["old_task_id"] == ids["branch_a"]
    assert wave2["successor_changes"] == []

    branch_a = orchestrator.runtime.tasks[ids["branch_a"]]
    branch_a_successor = orchestrator.runtime.tasks[wave0["successor_changes"][0]["new_task_id"]]
    deep_successor = orchestrator.runtime.tasks[wave1["successor_changes"][0]["new_task_id"]]
    branch_b = orchestrator.runtime.tasks[ids["branch_b"]]

    assert task_superseded(branch_a)
    assert task_execution_blocked(branch_a) is not None
    assert task_execution_blocked(branch_a_successor) is None
    assert task_execution_blocked(deep_successor) is None
    assert task_execution_blocked(branch_b) is None
    assert upstream_supersession_metadata(branch_b)["outcome"] == "still_valid"

    assert evaluated.count(ids["branch_a"]) == 1
    assert evaluated.count(ids["branch_b"]) == 1
    assert evaluated.count(ids["deep"]) == 1

    for wave in result["waves"]:
        assert wave["propagation_id"] == "pw-prop-e2e"

    persist_chat_execution(
        orchestrator,
        stop_reason="TASK_CHANGE_PROPAGATION",
        determined=True,
        answer="propagation saved",
        store=mission_store,
    )
    mission_runtime = load_mission_completion_runtime(orchestrator.mission_id, store=mission_store)
    resumed = ChatTaskOrchestrator("resume", orchestrator.request)
    bind_execution_identity(resumed, resume_mission_id=orchestrator.mission_id, new_execution=True)
    resumed.apply_completion_runtime(mission_runtime, replace_graph=True)

    resumed_branch_a = resumed.runtime.tasks[ids["branch_a"]]
    resumed_branch_b = resumed.runtime.tasks[ids["branch_b"]]
    assert task_superseded(resumed_branch_a)
    assert upstream_supersession_metadata(resumed_branch_b)["outcome"] == "still_valid"
    assert resumed.runtime.tasks[wave0["successor_changes"][0]["new_task_id"]].task_id
    assert resumed.runtime.tasks[wave1["successor_changes"][0]["new_task_id"]].task_id


def test_propagation_stops_at_max_waves_without_success(mission_store):
    orchestrator = _seed_propagation_orchestrator(mission_store)
    ids = _task_ids(orchestrator)
    root_change = _root_replacement(orchestrator)
    chat_fn, _evaluated = _routing_chat(
        {
            ids["branch_a"]: "needs_revision",
            ids["branch_b"]: "needs_revision",
            ids["deep"]: "needs_revision",
        }
    )

    result = run_task_change_propagation(
        orchestrator,
        [root_change],
        chat_fn=chat_fn,
        model="fake",
        propagation_id="pw-prop-limit",
        max_waves=2,
    )

    assert result["stop_reason"] == STOP_REASON_MAX_WAVES_REACHED
    assert result["converged"] is False
    assert result["completed_wave_count"] == 2
    assert result["successor_history"][-1]["successor_changes"]


def test_propagation_detects_repeated_change_set(mission_store, monkeypatch):
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
        propagation_id="pw-prop-repeat",
        max_waves=4,
    )

    assert result["stop_reason"] == STOP_REASON_REPEATED_CHANGE_SET
    assert result["converged"] is False
    assert result["completed_wave_count"] == 1
