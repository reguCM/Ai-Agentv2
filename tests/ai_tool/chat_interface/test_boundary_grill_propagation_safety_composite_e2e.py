"""run_chat_turn composite E2E: Boundary Grill Decision Change → propagation non-convergence → Safety Bridge."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.agent_turn import LoopStopReason, run_chat_turn
from ai_tool.chat_interface.boundary_grill import boundary_grill_runtime_connected
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    DECISION_STATUS_SUPERSEDED,
    OPTION_CONFIRM_CHANGE,
)
from ai_tool.chat_interface.gap_resolution_router import CapabilityId, GapKind
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.dev_skill_pipeline import normalize_implementation_tasks
from ai_tool.mission_memory.clarifications import load_confirmed_clarifications_for_mission
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.task_runtime import load_mission_completion_runtime
from ai_tool.skill_applicability import load_registry
from ai_tool.task_change_propagation_guard import GRAPH_STOP_REASON, GUARD_KEY
from ai_tool.task_execution_guard import TaskExecutionBlockedError
from ai_tool.task_upstream_supersession_revalidation import (
    STOP_REASON_MAX_WAVES_REACHED,
    run_task_change_propagation as real_run_task_change_propagation,
)
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_gap_resolution_phase1 import _gap_event
from tests.ai_tool.chat_interface.test_production_handoff_mainline_e2e import (
    MAINLINE_REQUEST,
    README_CONTENT,
)
from tests.ai_tool.test_production_handoff_decision_supply import KEY_JSON, KEY_GUI


def _propagation_plan_tasks() -> list[dict]:
    return [
        {
            "id": "TROOT",
            "title": "Root upstream",
            "acceptance": ["root ready"],
            "verification": ["root check"],
            "dependencies": [],
            "size": "S",
        },
        {
            "id": "TBRANCHA",
            "title": "Branch A downstream",
            "acceptance": ["branch A ready"],
            "verification": ["branch A check"],
            "dependencies": ["TROOT"],
            "size": "S",
            "premise_decision_keys": [KEY_JSON],
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


@pytest.fixture
def boundary_grill_runtime_connected_registry(monkeypatch):
    registry = copy.deepcopy(load_registry())
    for row in registry.get("skills") or []:
        if str(row.get("id") or "") == "grill-me":
            row["runtime_connected"] = True
    monkeypatch.setattr(
        "ai_tool.skill_applicability.load_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.boundary_grill.load_registry",
        lambda: registry,
    )
    return registry


@pytest.fixture
def mission_store(tmp_path, monkeypatch):
    root = tmp_path / "mission_memory"
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: root,
    )
    return MissionMemoryStore(root)


def _event_types(result: dict) -> list[str]:
    return [str(item.get("type") or "") for item in (result.get("events") or [])]


def _event_payloads(result: dict, event_type: str) -> list[dict]:
    return [
        dict(item)
        for item in (result.get("events") or [])
        if str(item.get("type") or "") == event_type
    ]


def _response_json(payload: dict):
    return SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)))


def _task_ids_from_runtime(runtime: dict) -> dict[str, str]:
    by_title = {
        str(row.get("title") or ""): str(row.get("task_id") or "")
        for row in (runtime.get("tasks") or [])
    }
    return {
        "root": by_title["Root upstream"],
        "branch_a": by_title["Branch A downstream"],
        "branch_b": by_title["Branch B downstream"],
        "deep": by_title["Deep downstream"],
    }


def _completion_runtime_from_task_runtime(runtime: dict) -> dict:
    return {
        "current_goal_id": runtime.get("current_goal_id"),
        "current_task_id": runtime.get("current_task_id"),
        "goals": list(runtime.get("goals") or []),
        "tasks": list(runtime.get("tasks") or []),
        "evidence": list(runtime.get("evidence") or []),
        "search_observations": list(runtime.get("search_observations") or []),
    }


def _propagation_nonconvergence_chat(task_ids: dict[str, str]):
    def chat(**kwargs):
        content = kwargs["messages"][0]["content"]
        if "Decision premise changes:" in content:
            return _response_json(
                {"outcome": "needs_revision", "reason": "root stale after decision change"}
            )
        for key in ("branch_a", "branch_b", "deep"):
            task_id = task_ids[key]
            if f"Downstream task ID: {task_id}" in content:
                return _response_json(
                    {"outcome": "needs_revision", "reason": f"downstream stale {key}"}
                )
        if kwargs.get("execution_profile") == "structured_output":
            return _response_json(
                {"outcome": "needs_revision", "reason": "structured propagation stale"}
            )
        return SimpleNamespace(message=SimpleNamespace(content="unused"))

    return chat


def _limited_propagation(*args, **kwargs):
    kwargs["max_waves"] = 1
    return real_run_task_change_propagation(*args, **kwargs)


def test_boundary_grill_decision_change_propagation_nonconvergence_composite_e2e(
    monkeypatch,
    tmp_path,
    boundary_grill_runtime_connected_registry,
    mission_store,
):
    assert boundary_grill_runtime_connected(boundary_grill_runtime_connected_registry) is True
    monkeypatch.setattr(
        "ai_tool.task_upstream_supersession_revalidation.run_task_change_propagation",
        _limited_propagation,
    )
    _prepare(
        monkeypatch,
        tmp_path,
        {"ok": True, "status": "success", "content": README_CONTENT},
    )
    session = empty_session("boundary-grill-propagation-safety")
    handoff_chat = _chat_sequence(_response("unused"))

    first = run_chat_turn(
        session,
        MAINLINE_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "README.md"})]),
            _response("README.md を読み取りました。"),
        ),
        model="fake",
    )
    assert _gap_event(first) is not None
    mission_id = str(first.get("mission_memory", {}).get("mission_id") or "")
    assert mission_id

    second = run_chat_turn(
        session,
        "acceptance_json_output",
        chat_fn=handoff_chat,
        model="fake",
    )
    assert "boundary_grill_answer_applied" in _event_types(second)

    session["production_handoff_plan_tasks"] = normalize_implementation_tasks(
        _propagation_plan_tasks(),
        default_acceptance=["done"],
        default_verification=["check"],
    )
    third = run_chat_turn(
        session,
        "behavior_gui_yes",
        chat_fn=handoff_chat,
        model="fake",
    )
    assert third.get("production_handoff_auto_triggered") is True
    assert "production_handoff_pipeline_completed" in _event_types(third)

    mission = mission_store.get_mission(mission_id)
    assert mission is not None
    json_decision_id = next(
        row["decision_id"]
        for row in (mission.get("confirmed_clarifications") or [])
        if row.get("decision_key") == KEY_JSON
    )
    handoff_runtime = third.get("task_runtime") or {}
    task_ids = _task_ids_from_runtime(handoff_runtime)
    resume_packet = {
        "original_request": session["last_original_request"],
        "completion_runtime": _completion_runtime_from_task_runtime(handoff_runtime),
        "mission_id": mission_id,
        "execution_id": str(third.get("mission_memory", {}).get("execution_id") or ""),
        "boundary_grill_resolved_dimensions": ["acceptance", "behavior"],
        "confirmed_clarifications": list(mission.get("confirmed_clarifications") or []),
        "user_explicit_conditions": list(mission.get("explicit_conditions") or []),
        "boundary_grill_round": 2,
        "active_contract": {},
        "open_dimensions": [],
    }
    session["awaiting_decision_change_confirmation"] = True
    session["decision_change_confirmation_state"] = {
        "phase": "decision_change_confirmation",
        "status": "AWAITING_HUMAN",
        "mission_id": mission_id,
        "execution_id": resume_packet["execution_id"],
        "consumer": "boundary_grill",
        "resume_packet": resume_packet,
        "pending_application": {
            "consumer": "boundary_grill",
            "contract": {},
            "proposed": {
                "decision_key": KEY_JSON,
                "text": "Markdown",
                "dimension": "acceptance",
                "option_id": "acceptance_markdown_output",
            },
            "prior": {
                "decision_id": json_decision_id,
                "decision_key": KEY_JSON,
                "text": "JSON",
            },
            "prior_decision_id": json_decision_id,
            "decision_key": KEY_JSON,
            "conflict_class": "replacement",
        },
        "active_contract": {},
    }

    change = run_chat_turn(
        session,
        OPTION_CONFIRM_CHANGE,
        chat_fn=_propagation_nonconvergence_chat(task_ids),
        model="fake",
    )
    events = _event_types(change)
    assert "decision_change_confirmed" in events
    assert "decision_superseded" in events
    assert "boundary_grill_answer_applied" in events
    assert "premise_revalidation_applied" in events
    assert "premise_pending_replacement_applied" in events
    assert "task_change_propagation_completed" in events
    assert "boundary_grill_reroute" in events
    assert "gap_resolution_routed" in events

    propagation_events = _event_payloads(change, "task_change_propagation_completed")
    assert propagation_events
    assert propagation_events[0].get("converged") is False
    assert propagation_events[0].get("stop_reason") == STOP_REASON_MAX_WAVES_REACHED
    guard = propagation_events[0].get("task_change_propagation_guard") or {}
    assert guard.get("unresolved") is True
    assert guard.get("graph_converged") is False

    gap = change.get("gap_resolution") or {}
    assert gap.get("gap_kind") == GapKind.STAGNATION_EXHAUSTED.value
    assert gap.get("winner") == CapabilityId.HELP.value
    assert gap.get("winner") != CapabilityId.TOOL_EVIDENCE.value
    assert change.get("awaiting_boundary_grill") is not True
    assert "未収束" in str(change.get("answer") or "")

    mission = mission_store.get_mission(mission_id)
    mission_runtime = load_mission_completion_runtime(mission_id, store=mission_store)
    assert mission_runtime is not None
    persisted_guard = mission_runtime.get(GUARD_KEY) or {}
    assert persisted_guard.get("unresolved") is True
    assert persisted_guard.get("graph_converged") is False

    executions = mission_store.list_executions(mission_id)
    assert executions
    latest = executions[-1]
    assert latest.get("result_determination") == "determined"
    assert latest.get("stop_reason") == GRAPH_STOP_REASON
    assert latest.get("stop_reason") != "DECISION_CHANGE_CONFIRMED"

    clarifications = load_confirmed_clarifications_for_mission(mission_id, store=mission_store)
    active_json = [
        row
        for row in clarifications
        if row.get("decision_key") == KEY_JSON
        and row.get("status", DECISION_STATUS_CONFIRMED) != DECISION_STATUS_SUPERSEDED
    ]
    assert len(active_json) == 1
    assert "Markdown" in str(active_json[0].get("text") or "")

    tool_executions: list[dict] = []

    def _track_tool(*_args, **_kwargs):
        tool_executions.append({"ok": True})
        return {"ok": True, "status": "success", "content": "should-not-run"}

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _track_tool,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.observe_gap_resolution_at_execution_end",
        lambda *args, **kwargs: (None, None, None),
    )

    session["awaiting_decision_change_confirmation"] = False
    session["decision_change_confirmation_state"] = None
    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = {
        "kind": "goal_continuation_v0",
        "mission_id": mission_id,
        "original_request": session["last_original_request"],
        "completion_runtime": mission_runtime,
        "winner": CapabilityId.HELP.value,
        "gap_kind": GapKind.STAGNATION_EXHAUSTED.value,
        "execution_id": str(change.get("mission_memory", {}).get("execution_id") or ""),
        "correlation_id": "boundary-grill-propagation-resume",
    }

    resumed = run_chat_turn(
        session,
        "continue",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "README.md"})]),
            _response("should not execute tools"),
        ),
        model="fake",
    )
    assert resumed.get("goal_continuation_restored") is True
    resume_events = _event_types(resumed)
    assert "task_change_propagation_execution_blocked" in resume_events
    assert tool_executions == []
    assert resumed.get("runtime_status_report", {}).get("reason_code") in {
        LoopStopReason.TASK_CHANGE_PROPAGATION_NON_CONVERGED.value,
        LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK.value,
        LoopStopReason.GOAL_INCOMPLETE_BLOCKED.value,
    }

    resume_runtime = resumed.get("task_runtime") or {}
    resumed_orchestrator = ChatTaskOrchestrator("verify-resume", session["last_original_request"])
    resumed_orchestrator.mission_id = mission_id
    resumed_orchestrator.apply_completion_runtime(mission_runtime, replace_graph=True)
    assert (mission_runtime.get(GUARD_KEY) or {}).get("unresolved") is True
    with pytest.raises(TaskExecutionBlockedError):
        resumed_orchestrator.assert_current_task_executable_for_premise()
    assert resumed_orchestrator.propagation_goal_completion_block() is not None
    assert resumed_orchestrator.incomplete_goal_terminal_outcome() is not None
