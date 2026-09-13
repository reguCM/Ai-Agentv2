"""run_chat_turn composite E2E: premise revalidation persistence via Mission Memory."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.boundary_grill import boundary_grill_runtime_connected
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    DECISION_STATUS_SUPERSEDED,
    OPTION_CONFIRM_CHANGE,
)
from ai_tool.chat_interface.gap_resolution_router import CapabilityId, GapKind
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.decision_premise_revalidation import run_premise_revalidations
from ai_tool.human_decision_premise import tasks_needing_revalidation
from ai_tool.mission_memory.clarifications import load_confirmed_clarifications_for_mission
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.task_runtime import load_mission_completion_runtime
from ai_tool.skill_applicability import load_registry
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
from tests.ai_tool.test_production_handoff_decision_supply import (
    KEY_JSON,
    _plan_tasks,
)

D_JSON_MARKDOWN = "d-json-markdown-v2"
D_JSON_YAML = "d-json-yaml-v3"


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


def _completion_runtime_from_task_runtime(runtime: dict) -> dict:
    return {
        "current_goal_id": runtime.get("current_goal_id"),
        "current_task_id": runtime.get("current_task_id"),
        "goals": list(runtime.get("goals") or []),
        "tasks": list(runtime.get("tasks") or []),
        "evidence": list(runtime.get("evidence") or []),
        "search_observations": list(runtime.get("search_observations") or []),
    }


def _response_json(payload: dict):
    return SimpleNamespace(
        message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
    )


def _structured_revalidation_chat(counter: list[int]):
    def chat(**kwargs):
        if kwargs.get("execution_profile") == "structured_output":
            counter.append(1)
            return _response_json(
                {
                    "outcome": "still_valid",
                    "reason": "Active decision still supports the task.",
                }
            )
        return SimpleNamespace(message=SimpleNamespace(content="unused"))

    return chat


def _active_decision_id(clarifications: list[dict], decision_key: str) -> str:
    active = [
        row
        for row in clarifications
        if row.get("decision_key") == decision_key
        and row.get("status", DECISION_STATUS_CONFIRMED) != DECISION_STATUS_SUPERSEDED
    ]
    assert len(active) == 1
    return str(active[0]["decision_id"])


def test_run_chat_turn_premise_revalidation_mission_resume_composite_e2e(
    monkeypatch,
    tmp_path,
    boundary_grill_runtime_connected_registry,
    mission_store,
):
    assert boundary_grill_runtime_connected(boundary_grill_runtime_connected_registry) is True
    _prepare(
        monkeypatch,
        tmp_path,
        {"ok": True, "status": "success", "content": README_CONTENT},
    )
    session = empty_session("premise-revalidation-mainline")
    revalidation_calls: list[int] = []
    handoff_chat = _chat_sequence(_response("unused"))
    revalidation_chat = _structured_revalidation_chat(revalidation_calls)

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

    session["production_handoff_plan_tasks"] = _plan_tasks()
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
    assert load_mission_completion_runtime(mission_id, store=mission_store) is not None
    json_decision_id = _active_decision_id(mission.get("confirmed_clarifications") or [], KEY_JSON)
    handoff_runtime = third.get("task_runtime") or {}
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

    revalidation_calls.clear()
    change = run_chat_turn(
        session,
        OPTION_CONFIRM_CHANGE,
        chat_fn=revalidation_chat,
        model="fake",
    )
    assert "decision_change_confirmed" in _event_types(change)
    assert "decision_superseded" in _event_types(change)
    assert "premise_revalidation_applied" in _event_types(change)
    assert len(revalidation_calls) == 1

    mission = mission_store.get_mission(mission_id)
    mission_runtime = load_mission_completion_runtime(mission_id, store=mission_store)
    assert mission_runtime is not None
    gh_t2 = next(row for row in mission_runtime["tasks"] if row["task_id"] == "gh-T2")
    assert gh_t2["decision_premises"][0]["derived_from_decision_id"] == json_decision_id
    markdown_id = _active_decision_id(mission.get("confirmed_clarifications") or [], KEY_JSON)
    assert gh_t2["decision_premises"][0]["validated_against_decision_id"] == markdown_id
    assert gh_t2["revalidation"]["premise_revalidation"]["outcome"] == "still_valid"
    assert gh_t2["revalidation"]["premise_revalidation"]["evaluated_against_decision_ids"] == {
        KEY_JSON: markdown_id,
    }

    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.observe_gap_resolution_at_execution_end",
        lambda *args, **kwargs: (None, None, None),
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: {
            "ok": True,
            "status": "success",
            "content": "done",
        },
    )

    session["awaiting_goal_continuation"] = True
    session["goal_continuation_resume"] = {
        "kind": "goal_continuation_v0",
        "mission_id": mission_id,
        "original_request": session["last_original_request"],
        "completion_runtime": {"tasks": [], "goals": []},
        "winner": CapabilityId.TOOL_EVIDENCE.value,
        "gap_kind": GapKind.SPEC_MEANING_GAP.value,
        "execution_id": str(change.get("mission_memory", {}).get("execution_id") or ""),
        "correlation_id": "carrier-only",
    }

    revalidation_calls.clear()
    resumed = run_chat_turn(
        session,
        "continue",
        chat_fn=_chat_sequence(_response("continuation step complete.")),
        model="fake",
    )
    assert resumed.get("goal_continuation_restored") is True
    runtime = resumed.get("task_runtime") or {}
    tasks = {row["task_id"]: row for row in runtime.get("tasks") or []}
    assert tasks["gh-T2"]["decision_premises"][0]["derived_from_decision_id"] == json_decision_id
    assert tasks["gh-T2"]["decision_premises"][0]["validated_against_decision_id"] == markdown_id
    assert tasks["gh-T2"]["revalidation"]["premise_revalidation"]["outcome"] == "still_valid"
    assert tasks["gh-T2"]["revalidation"]["needs_revalidation"] is False
    assert revalidation_calls == []

    resume_orchestrator = ChatTaskOrchestrator("verify-skip", session["last_original_request"])
    resume_orchestrator.mission_id = mission_id
    resume_orchestrator.confirmed_clarifications = load_confirmed_clarifications_for_mission(
        mission_id,
        store=mission_store,
    )
    resume_orchestrator.apply_completion_runtime(
        load_mission_completion_runtime(mission_id, store=mission_store) or {},
        replace_graph=True,
    )
    assert run_premise_revalidations(
        resume_orchestrator,
        chat_fn=_structured_revalidation_chat(revalidation_calls),
        model="fake",
    ) == []
    assert revalidation_calls == []
    assert [row["task_id"] for row in tasks_needing_revalidation(resume_orchestrator)] == []

    resumed_runtime = _completion_runtime_from_task_runtime(runtime)
    session["awaiting_decision_change_confirmation"] = True
    session["decision_change_confirmation_state"] = {
        "phase": "decision_change_confirmation",
        "status": "AWAITING_HUMAN",
        "mission_id": mission_id,
        "execution_id": str(resumed.get("mission_memory", {}).get("execution_id") or ""),
        "consumer": "boundary_grill",
        "resume_packet": {
            **resume_packet,
            "execution_id": str(resumed.get("mission_memory", {}).get("execution_id") or ""),
            "completion_runtime": resumed_runtime,
            "confirmed_clarifications": load_confirmed_clarifications_for_mission(
                mission_id,
                store=mission_store,
            ),
        },
        "pending_application": {
            "consumer": "boundary_grill",
            "contract": {},
            "proposed": {
                "decision_key": KEY_JSON,
                "text": "YAML",
                "dimension": "acceptance",
                "option_id": "acceptance_yaml_output",
            },
            "prior": {
                "decision_id": markdown_id,
                "decision_key": KEY_JSON,
                "text": "Markdown",
            },
            "prior_decision_id": markdown_id,
            "decision_key": KEY_JSON,
            "conflict_class": "replacement",
        },
        "active_contract": {},
    }

    revalidation_calls.clear()
    third_change = run_chat_turn(
        session,
        OPTION_CONFIRM_CHANGE,
        chat_fn=revalidation_chat,
        model="fake",
    )
    assert "premise_revalidation_applied" in _event_types(third_change)
    assert len(revalidation_calls) == 1
    mission = mission_store.get_mission(mission_id)
    gh_t2 = next(
        row
        for row in (load_mission_completion_runtime(mission_id, store=mission_store) or {})["tasks"]
        if row["task_id"] == "gh-T2"
    )
    yaml_id = _active_decision_id(mission.get("confirmed_clarifications") or [], KEY_JSON)
    assert gh_t2["decision_premises"][0]["derived_from_decision_id"] == json_decision_id
    assert gh_t2["decision_premises"][0]["validated_against_decision_id"] == yaml_id
    assert gh_t2["revalidation"]["premise_revalidation"]["outcome"] == "still_valid"
