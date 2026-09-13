"""Phase 1: Decision Change Confirmation Gate (Boundary Grill)."""
from __future__ import annotations

import copy

import pytest

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.boundary_grill import (
    apply_boundary_grill_answer,
    build_boundary_grill_contract,
    launch_boundary_grill,
)
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    DECISION_STATUS_SUPERSEDED,
    OPTION_CONFIRM_CHANGE,
    OPTION_KEEP_PRIOR,
    active_decision_for_key,
    classify_answer_vs_prior,
    prepare_boundary_grill_answer,
    resolve_boundary_answer,
)
from ai_tool.chat_interface.gap_resolution_router import (
    CapabilityId,
    GapKind,
    route_gap_resolution_from_orchestrator,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.skill_applicability import load_registry
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _response,
)

MATERIAL_FORK_REQUEST = (
    "probe.txt の先頭1行を確認して報告する。\n"
    "報告形式は次の2通りがともに妥当ですが、どちらを採用するか未決です。\n"
    "A: 原文をそのまま報告する\n"
    "B: VALUE形式で報告する"
)


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


def _event_types(result: dict) -> list[str]:
    return [str(item.get("type") or "") for item in (result.get("events") or [])]


def _orchestrator_with_acceptance_a() -> tuple[ChatTaskOrchestrator, dict]:
    orchestrator = ChatTaskOrchestrator("dcg-a", MATERIAL_FORK_REQUEST)
    orchestrator.initialize()
    orchestrator.runtime.tasks["T1"].status = "complete"
    orchestrator.runtime.tasks["T1"].evidence_ids = ["e1"]
    orchestrator.mission_id = "m-test-decision-change"
    contract = build_boundary_grill_contract(orchestrator).as_dict()
    apply_boundary_grill_answer(
        orchestrator,
        "acceptance_quote_first_lines",
        contract,
    )
    return orchestrator, contract


def test_same_decision_key_replacement_triggers_confirmation():
    orchestrator, contract = _orchestrator_with_acceptance_a()
    prepared = prepare_boundary_grill_answer(
        orchestrator,
        "acceptance_one_paragraph_summary",
        contract,
    )
    assert prepared["conflict_class"] == "replacement"
    assert prepared["needs_confirmation"] is True
    assert prepared["decision_key"] == "acceptance:output_format"
    assert prepared["prior"]["option_id"] == "acceptance_quote_first_lines"
    assert prepared["proposed"]["option_id"] == "acceptance_one_paragraph_summary"


def test_different_decision_key_is_additional_info_not_replacement():
    prior = {
        "decision_key": "acceptance:output_format",
        "option_id": "acceptance_quote_first_lines",
        "text": "原文",
        "status": DECISION_STATUS_CONFIRMED,
    }
    proposed = {
        "decision_key": "acceptance:line_count",
        "text": "先頭1行のみ",
        "option_id": "",
    }
    assert classify_answer_vs_prior(prior, proposed) == "additional_info"


def test_concretization_does_not_need_confirmation():
    orchestrator, contract = _orchestrator_with_acceptance_a()
    proposed = resolve_boundary_answer(
        "指定ファイルの先頭3行をそのまま引用できれば完了",
        contract,
    )
    prior = active_decision_for_key(
        orchestrator.confirmed_clarifications,
        "acceptance:output_format",
    )
    assert classify_answer_vs_prior(prior, proposed) in {"duplicate", "concretization"}
    prepared = prepare_boundary_grill_answer(
        orchestrator,
        "指定ファイルの先頭3行をそのまま引用できれば完了",
        contract,
    )
    assert prepared["needs_confirmation"] is False


def test_confirm_change_supersedes_prior_record():
    orchestrator, contract = _orchestrator_with_acceptance_a()
    prior = active_decision_for_key(
        orchestrator.confirmed_clarifications,
        "acceptance:output_format",
    )
    prior_id = str(prior["decision_id"])
    proposed = resolve_boundary_answer("acceptance_one_paragraph_summary", contract)
    applied = apply_boundary_grill_answer(
        orchestrator,
        "",
        contract,
        proposed=proposed,
        supersede_prior_id=prior_id,
    )
    assert applied["applied"] is True
    rows = orchestrator.confirmed_clarifications
    old = next(row for row in rows if row.get("decision_id") == prior_id)
    new = next(row for row in rows if row.get("decision_id") == applied["decision_id"])
    assert old["status"] == DECISION_STATUS_SUPERSEDED
    assert old["superseded_by"] == new["decision_id"]
    assert new["status"] == DECISION_STATUS_CONFIRMED
    assert new["supersedes"] == prior_id


def test_boundary_grill_replacement_launches_decision_change_confirmation(
    boundary_grill_runtime_connected_registry,
):
    orchestrator, contract = _orchestrator_with_acceptance_a()
    packet = {
        "original_request": orchestrator.request,
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "mission_id": orchestrator.mission_id,
        "execution_id": "x-prior",
        "boundary_grill_resolved_dimensions": list(
            orchestrator.boundary_grill_resolved_dimensions
        ),
        "confirmed_clarifications": [dict(item) for item in orchestrator.confirmed_clarifications],
        "boundary_grill_round": orchestrator.boundary_grill_round,
        "active_contract": contract,
        "open_dimensions": [],
    }
    orchestrator.boundary_grill_resolved_dimensions = []
    packet["boundary_grill_resolved_dimensions"] = []
    session = empty_session("decision-change-replacement")
    session["awaiting_boundary_grill"] = True
    session["boundary_grill_state"] = packet
    result = run_chat_turn(
        session,
        "acceptance_one_paragraph_summary",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    events = _event_types(result)
    assert "boundary_grill_answer_proposed" in events
    assert "decision_change_conflict_detected" in events
    assert "decision_change_confirmation_launched" in events
    assert "boundary_grill_answer_applied" not in events
    assert result.get("awaiting_decision_change_confirmation") is True
    assert session.get("awaiting_decision_change_confirmation") is True
    assert session.get("awaiting_boundary_grill") is not True


def test_keep_prior_discards_proposed_and_reroutes_without_boundary_represent(
    boundary_grill_runtime_connected_registry,
):
    orchestrator, contract = _orchestrator_with_acceptance_a()
    prior = active_decision_for_key(
        orchestrator.confirmed_clarifications,
        "acceptance:output_format",
    )
    proposed = resolve_boundary_answer("acceptance_one_paragraph_summary", contract)
    resume_packet = {
        "original_request": orchestrator.request,
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "mission_id": orchestrator.mission_id,
        "execution_id": "x-prior",
        "boundary_grill_resolved_dimensions": ["acceptance"],
        "confirmed_clarifications": [dict(item) for item in orchestrator.confirmed_clarifications],
        "user_explicit_conditions": list(orchestrator.user_explicit_conditions),
        "boundary_grill_round": orchestrator.boundary_grill_round,
        "active_contract": contract,
        "open_dimensions": [],
    }
    session = empty_session("decision-change-keep-prior")
    session["awaiting_decision_change_confirmation"] = True
    session["decision_change_confirmation_state"] = {
        "phase": "decision_change_confirmation",
        "status": "AWAITING_HUMAN",
        "mission_id": orchestrator.mission_id,
        "execution_id": "x-prior",
        "consumer": "boundary_grill",
        "resume_packet": resume_packet,
        "pending_application": {
            "consumer": "boundary_grill",
            "contract": contract,
            "proposed": proposed,
            "prior": dict(prior),
            "prior_decision_id": prior["decision_id"],
            "decision_key": "acceptance:output_format",
            "conflict_class": "replacement",
        },
        "active_contract": {},
    }
    result = run_chat_turn(
        session,
        OPTION_KEEP_PRIOR,
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    events = _event_types(result)
    assert "decision_change_rejected" in events
    assert "boundary_grill_reroute" in events
    assert "boundary_grill_answer_applied" not in events
    assert "boundary_grill_launched" not in events
    assert result.get("awaiting_boundary_grill") is not True
    assert result.get("gap_resolution", {}).get("winner") != CapabilityId.SKILL_GRILL_ME.value
    runtime = result.get("task_runtime") or {}
    active = [
        row
        for row in runtime.get("confirmed_clarifications") or []
        if row.get("status", DECISION_STATUS_CONFIRMED) != DECISION_STATUS_SUPERSEDED
        and row.get("source") == "boundary_grill"
    ]
    assert len(active) == 1
    assert "引用" in str(active[0].get("text") or "")


def test_confirm_change_via_resume_applies_b_and_supersedes_a(
    boundary_grill_runtime_connected_registry,
):
    orchestrator, contract = _orchestrator_with_acceptance_a()
    prior = active_decision_for_key(
        orchestrator.confirmed_clarifications,
        "acceptance:output_format",
    )
    proposed = resolve_boundary_answer("acceptance_one_paragraph_summary", contract)
    resume_packet = {
        "original_request": orchestrator.request,
        "completion_runtime": orchestrator.completion_runtime_slice(),
        "mission_id": orchestrator.mission_id,
        "execution_id": "x-prior",
        "boundary_grill_resolved_dimensions": ["acceptance"],
        "confirmed_clarifications": [dict(item) for item in orchestrator.confirmed_clarifications],
        "user_explicit_conditions": list(orchestrator.user_explicit_conditions),
        "boundary_grill_round": orchestrator.boundary_grill_round,
        "active_contract": contract,
        "open_dimensions": [],
    }
    session = empty_session("decision-change-confirm")
    session["awaiting_decision_change_confirmation"] = True
    session["decision_change_confirmation_state"] = {
        "phase": "decision_change_confirmation",
        "status": "AWAITING_HUMAN",
        "mission_id": orchestrator.mission_id,
        "execution_id": "x-prior",
        "consumer": "boundary_grill",
        "resume_packet": resume_packet,
        "pending_application": {
            "consumer": "boundary_grill",
            "contract": contract,
            "proposed": proposed,
            "prior": dict(prior),
            "prior_decision_id": prior["decision_id"],
            "decision_key": "acceptance:output_format",
            "conflict_class": "replacement",
        },
        "active_contract": {},
    }
    result = run_chat_turn(
        session,
        OPTION_CONFIRM_CHANGE,
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    events = _event_types(result)
    assert "decision_change_confirmed" in events
    assert "decision_superseded" in events
    assert "boundary_grill_answer_applied" in events
    runtime = result.get("task_runtime") or {}
    rows = runtime.get("confirmed_clarifications") or []
    superseded = [row for row in rows if row.get("status") == DECISION_STATUS_SUPERSEDED]
    active = [
        row
        for row in rows
        if row.get("status", DECISION_STATUS_CONFIRMED) != DECISION_STATUS_SUPERSEDED
        and row.get("source") == "boundary_grill"
    ]
    assert superseded
    assert len(active) == 1
    assert "要約" in str(active[0].get("text") or "")
    assert result.get("gap_resolution", {}).get("winner") != CapabilityId.SKILL_GRILL_ME.value
    assert result.get("awaiting_boundary_grill") is not True
