"""Phase 5: Production Boundary Grill vertical route (Bridge-1/2)."""
from __future__ import annotations

import copy

import pytest

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.boundary_grill import (
    apply_boundary_grill_answer,
    boundary_grill_runtime_connected,
    build_boundary_grill_contract,
    launch_boundary_grill,
    needs_boundary_spec_clarification,
    request_has_material_spec_fork,
)
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.gap_resolution_router import (
    CapabilityId,
    GapKind,
    classify_gap_kind,
    route_gap_resolution_from_orchestrator,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.skill_applicability import load_registry
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_gap_resolution_phase1 import _gap_event

SIMPLE_SUMMARY_REQUEST = "README.md を読んで要約してください。"
MATERIAL_FORK_REQUEST = (
    "README.md を読んで成果物を作成してください。\n"
    "完了条件は次の2通りがともに妥当ですが、どちらを採用するか未決です。\n"
    "A: 先頭3行をそのまま引用する\n"
    "B: 1段落の要約文を生成する"
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


def _boundary_grill_event(result: dict) -> dict | None:
    for item in result.get("events") or []:
        if item.get("type") == "boundary_grill":
            return item
    return None


def test_simple_summary_request_is_not_material_spec_fork():
    assert request_has_material_spec_fork(SIMPLE_SUMMARY_REQUEST) is False
    assert request_has_material_spec_fork(
        "Completion Condition:\n1. file read\n2. summary"
    ) is False


def test_material_spec_fork_detects_unresolved_ab_completion_paths():
    assert request_has_material_spec_fork(MATERIAL_FORK_REQUEST) is True


def test_boundary_grill_contract_uses_human_ui_policy():
    orchestrator = ChatTaskOrchestrator("bg-contract", MATERIAL_FORK_REQUEST)
    orchestrator.initialize()
    contract = build_boundary_grill_contract(orchestrator)
    assert contract.grill_reason == "boundary_grill"
    assert contract.recommended_option_id
    record = launch_boundary_grill(
        orchestrator,
        route_gap_resolution_from_orchestrator(
            orchestrator,
            stop_reason="COMPLETED",
            answer_gate={"verified": False, "reason": "spec_meaning_ambiguous"},
        ),
    )
    assert record["record"]["selection_policy"] == "human_ui"


def test_apply_boundary_grill_answer_does_not_auto_complete_goal():
    orchestrator = ChatTaskOrchestrator("bg-apply", MATERIAL_FORK_REQUEST)
    orchestrator.initialize()
    orchestrator.runtime.tasks["T1"].status = "complete"
    contract = build_boundary_grill_contract(orchestrator).as_dict()
    applied = apply_boundary_grill_answer(
        orchestrator,
        "指定ファイルの先頭3行をそのまま引用できれば完了",
        contract,
    )
    assert applied["applied"] is True
    assert orchestrator.user_explicit_conditions
    assert orchestrator.runtime.goals["G1"].status != "complete"


def test_readme_summary_does_not_launch_boundary_grill(
    monkeypatch, tmp_path, boundary_grill_runtime_connected_registry
):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "content": README_CONTENT})
    session = empty_session("boundary-grill-negative")
    result = run_chat_turn(
        session,
        SIMPLE_SUMMARY_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "README.md"})]),
            _response("README.md を読み取り、要約しました。"),
        ),
        model="fake",
    )
    routed = _gap_event(result)
    assert routed is not None
    assert routed.get("gap_kind") != GapKind.SPEC_MEANING_GAP.value
    assert routed.get("winner") != CapabilityId.SKILL_GRILL_ME.value
    assert result.get("awaiting_boundary_grill") is False
    assert _boundary_grill_event(result) is None
    assert session.get("awaiting_boundary_grill") is False


def test_material_spec_fork_launches_boundary_grill_vertical_route(
    monkeypatch, tmp_path, boundary_grill_runtime_connected_registry
):
    assert boundary_grill_runtime_connected(boundary_grill_runtime_connected_registry) is True
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "content": README_CONTENT})
    session = empty_session("boundary-grill-positive")

    first = run_chat_turn(
        session,
        MATERIAL_FORK_REQUEST,
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
    assert _boundary_grill_event(first) is not None
    mission_id = str(first.get("mission_memory", {}).get("mission_id") or "")
    assert mission_id

    session["production_handoff_plan_tasks"] = [
        {
            "id": "T1",
            "title": "Complete quoted summary",
            "acceptance": ["quoted lines reported"],
            "verification": ["manual check"],
            "dependencies": [],
            "size": "S",
        }
    ]
    second = run_chat_turn(
        session,
        "指定ファイルの先頭3行をそのまま引用できれば完了",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )

    assert second.get("awaiting_boundary_grill") is False
    event_types = [str(item.get("type") or "") for item in (second.get("events") or [])]
    reroute_events = [
        item for item in second.get("events") or [] if item.get("type") == "boundary_grill_reroute"
    ]
    if "production_handoff_pipeline_completed" in event_types:
        assert second.get("production_handoff_auto_triggered") is True
    else:
        assert reroute_events
        assert reroute_events[0].get("gap_resolved") is True
        assert reroute_events[0].get("winner") != CapabilityId.SKILL_GRILL_ME.value
    assert str(second.get("mission_memory", {}).get("mission_id") or "") == mission_id


def test_readme_v0_still_routes_goal_completion_human_not_boundary_grill(
    monkeypatch, tmp_path, boundary_grill_runtime_connected_registry
):
    from tests.ai_tool.chat_interface.test_goal_completion_gate import (
        README_E2E_REQUEST,
        _listing_execute,
    )

    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    session = empty_session("boundary-grill-readme-v0")
    result = run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    routed = _gap_event(result)
    assert routed is not None
    assert routed.get("winner") == CapabilityId.GOAL_COMPLETION_HUMAN.value
    assert result.get("awaiting_boundary_grill") is False
    assert result.get("awaiting_goal_completion_human") is True


def test_spec_meaning_ambiguous_requires_material_spec_fork():
    orchestrator = ChatTaskOrchestrator("bg-classify", MATERIAL_FORK_REQUEST)
    orchestrator.initialize()
    orchestrator.runtime.tasks["T1"].status = "complete"
    from tools.ai.task_runtime import EvidenceRecord

    orchestrator.runtime.evidence["E1"] = EvidenceRecord(
        evidence_id="E1",
        source_type="tool",
        source="read_file",
        summary="observed",
        verified=True,
        created_by_action="A1",
        tool_name="read_file",
        target="README.md",
    )
    orchestrator.runtime.tasks["T1"].evidence_ids = ["E1"]
    assert needs_boundary_spec_clarification(orchestrator) is True
    _, gate = orchestrator.gate_answer("観測しました")
    assert gate.get("reason") == "spec_meaning_ambiguous"
    from ai_tool.chat_interface.gap_resolution_router import build_router_input_from_orchestrator

    inp = build_router_input_from_orchestrator(
        orchestrator,
        stop_reason="COMPLETED",
        answer_gate=gate,
    )
    assert classify_gap_kind(inp) == GapKind.SPEC_MEANING_GAP
    assert inp.needs_goal_completion_human is False

    simple = ChatTaskOrchestrator("bg-simple", SIMPLE_SUMMARY_REQUEST)
    simple.initialize()
    simple.runtime.tasks["T1"].status = "complete"
    simple.runtime.evidence["E1"] = orchestrator.runtime.evidence["E1"]
    simple.runtime.tasks["T1"].evidence_ids = ["E1"]
    assert needs_boundary_spec_clarification(simple) is False
