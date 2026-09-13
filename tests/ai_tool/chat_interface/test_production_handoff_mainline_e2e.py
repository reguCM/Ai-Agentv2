"""Production mainline E2E: Human Decision → Mission → Handoff → Runtime."""
from __future__ import annotations

import copy

import pytest

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.boundary_grill import boundary_grill_runtime_connected
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    DECISION_STATUS_SUPERSEDED,
    supersede_decision,
)
from ai_tool.chat_interface.gap_resolution_router import CapabilityId, GapKind
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.human_decision_premise import (
    INITIAL_GRILL_SEMANTIC_DECISION_KEY,
    INITIAL_GRILL_SEMANTIC_KEYS,
    initial_grill_question_id_for_orchestrator,
    initial_grill_semantic_decision_key,
    tasks_needing_revalidation,
)
from ai_tool.mission_memory.clarifications import load_confirmed_clarifications_for_mission
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.skill_applicability import load_registry
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_gap_resolution_phase1 import _gap_event
from tests.ai_tool.test_production_handoff_decision_supply import (
    KEY_GUI,
    KEY_JSON,
    _plan_tasks,
)

MAINLINE_REQUEST = (
    "README.md を読んでサービス仕様を確認してください。\n"
    "完了条件は次の2通りがともに妥当ですが、どちらを採用するか未決です。\n"
    "A: JSON APIで出力する\n"
    "B: 1段落の要約文を生成する\n"
    "また GUI 画面を含めるかも未決です。"
)
README_CONTENT = "README-LINE-1\nREADME-LINE-2\nREADME-LINE-3\n"


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


def _orchestrator_from_runtime(runtime: dict, request: str) -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("mainline-reval", request)
    orchestrator.apply_completion_runtime(runtime, replace_graph=True)
    orchestrator.confirmed_clarifications = [
        dict(item) for item in (runtime.get("confirmed_clarifications") or [])
    ]
    return orchestrator


def test_initial_grill_semantic_key_is_stable_not_question_slug():
    orchestrator = ChatTaskOrchestrator("initial-grill-key", "read docs/PROJECT_SPEC.md")
    orchestrator.mission_id = "m-initial-grill"
    orchestrator.goal_read_target = {
        "uniqueness_class": "IDENTITY_UNRESOLVED",
        "reason": "MULTIPLE_CONFIRMED_PATHS_IN_CANDIDATES",
        "status": "UNRESOLVED",
    }
    orchestrator.search_candidate_sets = {
        "s1": {
            "observation_role": "goal_request",
            "query": "project spec",
            "path": "docs/PROJECT_SPEC.md",
            "scan_complete": True,
        }
    }
    semantic = initial_grill_semantic_decision_key(orchestrator)
    question_id = initial_grill_question_id_for_orchestrator(orchestrator)
    assert semantic == INITIAL_GRILL_SEMANTIC_DECISION_KEY
    assert semantic == INITIAL_GRILL_SEMANTIC_KEYS["IDENTITY_UNRESOLVED"]
    assert question_id != semantic
    assert "q-project-spec" in question_id
    assert "p-docs-project-spec-md" in question_id or "p-dot" in question_id


def test_production_mainline_boundary_grill_handoff_and_revalidation(
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
    session = empty_session("production-handoff-mainline")

    first = run_chat_turn(
        session,
        MAINLINE_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "README.md"})]),
            _response("README.md を読み取りました。"),
        ),
        model="fake",
    )
    routed = _gap_event(first)
    assert routed is not None
    assert routed.get("gap_kind") == GapKind.SPEC_MEANING_GAP.value
    assert routed.get("winner") == CapabilityId.SKILL_GRILL_ME.value
    assert first.get("awaiting_boundary_grill") is True
    mission_id = str(first.get("mission_memory", {}).get("mission_id") or "")
    assert mission_id

    second = run_chat_turn(
        session,
        "acceptance_json_output",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    assert "boundary_grill_answer_applied" in _event_types(second)
    assert second.get("awaiting_boundary_grill") is True
    assert str(second.get("mission_memory", {}).get("mission_id") or "") == mission_id

    session["production_handoff_plan_tasks"] = _plan_tasks()
    third = run_chat_turn(
        session,
        "behavior_gui_yes",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    assert third.get("awaiting_boundary_grill") is False
    assert str(third.get("mission_memory", {}).get("mission_id") or "") == mission_id
    assert session.get("last_mission_id") == mission_id
    assert session.get("last_original_request")
    assert third.get("production_handoff_auto_triggered") is True
    assert "production_handoff_auto_triggered" in _event_types(third)
    assert "production_handoff_pipeline_completed" in _event_types(third)

    mission = mission_store.get_mission(mission_id)
    assert mission is not None
    stored = mission.get("confirmed_clarifications") or []
    assert len(stored) == 2
    assert {row["decision_key"] for row in stored} == {KEY_JSON, KEY_GUI}

    handoff = third
    packet = handoff.get("handoff_packet") or {}
    assert packet.get("handoff_id")
    tasks = {row["id"]: row for row in packet.get("implementation_tasks") or []}
    json_decision_id = next(
        row["decision_id"]
        for row in stored
        if row.get("decision_key") == KEY_JSON
    )
    gui_decision_id = next(
        row["decision_id"]
        for row in stored
        if row.get("decision_key") == KEY_GUI
    )
    assert tasks["T2"]["decision_premises"] == [
        {"decision_key": KEY_JSON, "derived_from_decision_id": json_decision_id}
    ]
    assert tasks["T3"]["decision_premises"] == [
        {"decision_key": KEY_GUI, "derived_from_decision_id": gui_decision_id}
    ]

    runtime = handoff.get("task_runtime") or {}
    assert runtime.get("tasks")
    assert "gh-T2" in {row["task_id"] for row in runtime.get("tasks") or []}

    restored = load_confirmed_clarifications_for_mission(mission_id, store=mission_store)
    assert len(restored) == 2

    reval_orch = _orchestrator_from_runtime(runtime, session["last_original_request"])
    reval_orch.mission_id = mission_id
    reval_orch.execution_id = str(handoff.get("mission_memory", {}).get("execution_id") or "exec-handoff")
    supersede_decision(
        reval_orch,
        json_decision_id,
        {
            "decision_id": "d-json-markdown-v2",
            "decision_key": KEY_JSON,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "Markdown",
            "dimension": "acceptance",
        },
        execution_id=reval_orch.execution_id,
    )
    assert reval_orch.runtime.tasks["gh-T1"].revalidation is None
    assert reval_orch.runtime.tasks["gh-T2"].revalidation["needs_revalidation"] is True
    assert reval_orch.runtime.tasks["gh-T3"].revalidation["needs_revalidation"] is False
    assert [row["task_id"] for row in tasks_needing_revalidation(reval_orch)] == ["gh-T2"]

    active_json = [
        row
        for row in reval_orch.confirmed_clarifications
        if row.get("status") != DECISION_STATUS_SUPERSEDED
        and row.get("decision_key") == KEY_JSON
    ]
    assert len(active_json) == 1
    assert active_json[0]["text"] == "Markdown"

    blocked = run_chat_turn(
        session,
        "goal handoff",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    assert "production_handoff_blocked" in _event_types(blocked)
    assert blocked.get("production_handoff_error") == "handoff_already_issued"
