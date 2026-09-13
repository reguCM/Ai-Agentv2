"""System readiness checks for automatic Production Handoff."""
from __future__ import annotations

from ai_tool.chat_interface.decision_change_gate import DECISION_STATUS_CONFIRMED
from ai_tool.chat_interface.gap_resolution_router import GapKind, GapResolutionDecision
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.production_handoff_bridge import (
    assess_production_handoff_readiness,
    orchestrator_has_goal_handoff_seed,
    session_has_production_handoff,
)
from tests.ai_tool.chat_interface.test_production_handoff_mainline_e2e import MAINLINE_REQUEST


def _orchestrator_with_boundary_decisions() -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("readiness", MAINLINE_REQUEST)
    orchestrator.mission_id = "m-ready"
    orchestrator.boundary_grill_resolved_dimensions = ["acceptance", "behavior"]
    orchestrator.confirmed_clarifications = [
        {
            "decision_id": "d-json",
            "decision_key": "acceptance:output_format",
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "JSON",
            "dimension": "acceptance",
        },
        {
            "decision_id": "d-gui",
            "decision_key": "scope:gui",
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "GUIあり",
            "dimension": "behavior",
        },
    ]
    orchestrator.user_explicit_conditions = ["JSON APIで出力"]
    return orchestrator


def test_ready_when_boundary_dimensions_closed_and_gap_resolved():
    orchestrator = _orchestrator_with_boundary_decisions()
    orchestrator.boundary_grill_resolved_dimensions = ["acceptance", "behavior"]
    decision = GapResolutionDecision(
        gap_kind=GapKind.NONE.value,
        gap_resolved=True,
        winner=None,
    )
    readiness = assess_production_handoff_readiness(
        orchestrator,
        gap_decision=decision,
        trigger="auto",
    )
    assert readiness.ready is True
    assert readiness.blockers == []
    assert "boundary_grill_decisions_confirmed" in readiness.reasons


def test_blocks_while_boundary_dimension_open():
    orchestrator = _orchestrator_with_boundary_decisions()
    orchestrator.boundary_grill_resolved_dimensions = ["acceptance"]
    readiness = assess_production_handoff_readiness(orchestrator, trigger="auto")
    assert readiness.ready is False
    assert "awaiting_boundary_grill" in readiness.blockers


def test_blocks_when_handoff_already_seeded():
    from tools.ai.task_runtime import TaskRecord, TaskStatus

    orchestrator = _orchestrator_with_boundary_decisions()
    orchestrator.runtime.tasks["gh-T9"] = TaskRecord(
        task_id="gh-T9",
        goal_id="G1",
        title="seed",
        instruction="seed",
        completion_conditions=[],
        status=TaskStatus.PENDING.value,
        source="goal_handoff",
    )
    assert orchestrator_has_goal_handoff_seed(orchestrator) is True
    readiness = assess_production_handoff_readiness(orchestrator, trigger="auto")
    assert readiness.ready is False
    assert "handoff_already_issued" in readiness.blockers


def test_blocks_when_session_already_has_handoff():
    session = {"production_handoff_completed": True, "production_handoff_id": "gh-existing"}
    assert session_has_production_handoff(session) is True
    orchestrator = _orchestrator_with_boundary_decisions()
    readiness = assess_production_handoff_readiness(
        orchestrator,
        session=session,
        trigger="auto",
    )
    assert readiness.ready is False
    assert "handoff_already_issued" in readiness.blockers


def test_auto_ready_when_only_required_boundary_dimension_resolved():
    orchestrator = ChatTaskOrchestrator(
        "readiness-single-dim",
        "README.md を読んで成果物を作成してください。\n"
        "完了条件は次の2通りがともに妥当ですが、どちらを採用するか未決です。\n"
        "A: 先頭3行をそのまま引用する\n"
        "B: 1段落の要約文を生成する",
    )
    orchestrator.mission_id = "m-ready-single"
    orchestrator.boundary_grill_resolved_dimensions = ["acceptance"]
    orchestrator.confirmed_clarifications = [
        {
            "decision_id": "d-accept",
            "decision_key": "acceptance:output_format",
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "quote",
            "dimension": "acceptance",
        }
    ]
    orchestrator.user_explicit_conditions = ["quote"]
    readiness = assess_production_handoff_readiness(
        orchestrator,
        gap_decision=GapResolutionDecision(
            gap_kind=GapKind.NONE.value,
            gap_resolved=True,
            winner=None,
        ),
        trigger="auto",
    )
    assert readiness.ready is True


def test_auto_blocks_when_continuation_winner_pending():
    orchestrator = _orchestrator_with_boundary_decisions()
    readiness = assess_production_handoff_readiness(
        orchestrator,
        gap_decision=GapResolutionDecision(
            gap_kind=GapKind.NONE.value,
            gap_resolved=True,
            winner="replan",
        ),
        trigger="auto",
    )
    assert readiness.ready is False
    assert "continuation_winner_pending" in readiness.blockers


def test_blocks_when_blocking_gap_remains():
    orchestrator = _orchestrator_with_boundary_decisions()
    decision = GapResolutionDecision(
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        winner="tool_evidence",
    )
    readiness = assess_production_handoff_readiness(
        orchestrator,
        gap_decision=decision,
        trigger="auto",
    )
    assert readiness.ready is False
    assert "blocking_gap_unresolved" in readiness.blockers
