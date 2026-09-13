"""Phase 4: cross-execution Goal Gap progress (PROGRESS / STAGNATION / REGRESSION)."""
from __future__ import annotations

from ai_tool.chat_interface.gap_resolution_router import (
    CapabilityCandidate,
    CapabilityId,
    GapKind,
    GapResolutionDecision,
    GapRouterInput,
    apply_regression_continuation_bridge,
    build_goal_continuation_resume,
    is_current_gap_resolved,
    observe_gap_resolution_at_execution_end,
    route_gap_resolution_from_orchestrator,
)
from tools.ai.task_runtime import FailureRecord
from ai_tool.chat_interface.goal_continuation_progress import (
    CONTINUATION_CROSS_EXECUTION_STAGNATION_LIMIT,
    GapSnapshot,
    capture_gap_snapshot,
    compare_gap_snapshots,
    observe_goal_continuation_progress,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.task_runtime import ProgressState


def _partial_ab_snapshot() -> GapSnapshot:
    return GapSnapshot(
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate_verified=False,
        unsatisfied_conditions=["B"],
        satisfied_conditions=["A"],
    )


def _progress_ab_snapshot() -> GapSnapshot:
    return GapSnapshot(
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate_verified=False,
        unsatisfied_conditions=[],
        satisfied_conditions=["A", "B"],
    )


def test_compare_progress_when_unsatisfied_condition_closes():
    prior = _partial_ab_snapshot()
    current = _progress_ab_snapshot()
    verdict, reasons = compare_gap_snapshots(prior, current)
    assert verdict == ProgressState.PROGRESS.value
    assert any("conditions_satisfied" in item for item in reasons)


def test_compare_stagnation_when_gap_signature_unchanged():
    prior = _partial_ab_snapshot()
    current = _partial_ab_snapshot()
    verdict, reasons = compare_gap_snapshots(prior, current)
    assert verdict == ProgressState.STAGNATION.value
    assert "gap_signature_unchanged" in reasons


def test_evidence_only_increase_is_stagnation_not_progress():
    prior = _partial_ab_snapshot()
    current = GapSnapshot(
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate_verified=False,
        unsatisfied_conditions=["B"],
        satisfied_conditions=["A"],
        verified_evidence_ids=["E1"],
    )
    prior_evidence = GapSnapshot(
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate_verified=False,
        unsatisfied_conditions=["B"],
        satisfied_conditions=["A"],
        verified_evidence_ids=[],
    )
    verdict, reasons = compare_gap_snapshots(prior_evidence, current)
    assert verdict == ProgressState.STAGNATION.value
    assert reasons[0] in {
        "evidence_without_condition_progress",
        "gap_signature_unchanged",
    }


def test_observe_progress_resets_stagnation_count():
    prior = _partial_ab_snapshot().as_dict()
    orchestrator = ChatTaskOrchestrator("phase4", "audit")
    orchestrator.initialize()
    task = orchestrator.runtime.tasks["T1"]
    task.completion_conditions = ["A", "B"]
    task.condition_status = {"A": "SATISFIED", "B": "SATISFIED"}
    observation = observe_goal_continuation_progress(
        orchestrator,
        prior_snapshot=prior,
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate={"verified": False},
        continuation_stagnation_count=1,
    )
    assert observation is not None
    assert observation.verdict == ProgressState.PROGRESS.value
    assert observation.continuation_stagnation_count == 0
    assert observation.continuation_blocked is False


def test_observe_stagnation_increments_count():
    orchestrator = ChatTaskOrchestrator("phase4", "audit")
    orchestrator.initialize()
    task = orchestrator.runtime.tasks["T1"]
    task.completion_conditions = ["A", "B"]
    task.condition_status = {"A": "SATISFIED", "B": "UNKNOWN"}
    prior = capture_gap_snapshot(
        orchestrator,
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate={"verified": False},
    ).as_dict()
    observation = observe_goal_continuation_progress(
        orchestrator,
        prior_snapshot=prior,
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate={"verified": False},
        continuation_stagnation_count=0,
    )
    assert observation is not None
    assert observation.verdict == ProgressState.STAGNATION.value
    assert observation.continuation_stagnation_count == 1
    assert observation.continuation_blocked is False


def test_stagnation_limit_blocks_continuation_and_routes_help():
    orchestrator = ChatTaskOrchestrator("phase4", "audit")
    orchestrator.initialize()
    task = orchestrator.runtime.tasks["T1"]
    task.completion_conditions = ["A", "B"]
    task.condition_status = {"A": "SATISFIED", "B": "UNKNOWN"}
    snapshot = capture_gap_snapshot(
        orchestrator,
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate={"verified": False},
    ).as_dict()
    observation = observe_goal_continuation_progress(
        orchestrator,
        prior_snapshot=snapshot,
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate={"verified": False},
        continuation_stagnation_count=CONTINUATION_CROSS_EXECUTION_STAGNATION_LIMIT - 1,
    )
    assert observation is not None
    assert observation.continuation_blocked is True
    assert observation.help_escalation is True

    decision, resume, event = observe_gap_resolution_at_execution_end(
        orchestrator,
        stop_reason="AGENT_COMPLETED",
        answer_gate={"verified": False},
        loop_counters={},
        correlation_id="corr-phase4",
        recorded={"mission_id": "m1", "execution_id": "x1"},
        human_priority_blocked=False,
        gap_snapshot=snapshot,
        continuation_stagnation_count=observation.continuation_stagnation_count,
        block_continuation_resume=observation.continuation_blocked,
        help_escalation=observation.help_escalation,
    )
    assert resume is None
    assert event is not None
    assert event.get("continuation_resume_persisted") is False
    assert event.get("continuation_help_escalation") is True
    assert decision is not None
    assert decision.winner == CapabilityId.HELP.value


def test_continuation_packet_carries_gap_snapshot_and_stagnation_count():
    orchestrator = ChatTaskOrchestrator("phase4", "audit")
    orchestrator.initialize()
    from ai_tool.chat_interface.gap_resolution_router import route_gap_resolution_from_orchestrator

    decision = route_gap_resolution_from_orchestrator(
        orchestrator,
        stop_reason="AGENT_COMPLETED",
        answer_gate={"verified": False},
    )
    snapshot = capture_gap_snapshot(
        orchestrator,
        gap_kind=decision.gap_kind,
        gap_resolved=decision.gap_resolved,
        answer_gate={"verified": False},
    ).as_dict()
    packet = build_goal_continuation_resume(
        orchestrator,
        decision,
        recorded={"mission_id": "m1", "execution_id": "x1"},
        correlation_id="corr-packet",
        gap_snapshot=snapshot,
        continuation_stagnation_count=1,
    )
    assert packet.get("gap_snapshot") == snapshot
    assert packet.get("continuation_stagnation_count") == 1


def test_regression_reroutes_prior_recovery_winner_to_replan():
    orchestrator = ChatTaskOrchestrator("phase4", "audit")
    orchestrator.initialize()
    orchestrator.runtime.tasks["T1"].status = "in_progress"
    orchestrator.runtime.failures.append(
        FailureRecord(
            failure_id="f1",
            task_id="T1",
            action_id="a1",
            tool_name="read_file",
            arguments={"path": "missing.txt"},
            failure_code="MISSING",
            evidence_gain=False,
            created_at="now",
        )
    )
    decision = route_gap_resolution_from_orchestrator(
        orchestrator,
        stop_reason="AGENT_COMPLETED",
        answer_gate={"verified": False, "reason": "completion_evidence_incomplete"},
    )
    updated, bridge = apply_regression_continuation_bridge(
        decision,
        prior_winner=CapabilityId.RECOVERY.value,
        human_priority_blocked=False,
    )
    assert bridge is not None
    assert bridge.reroute_winner == CapabilityId.REPLAN.value
    assert bridge.superseded_winner == CapabilityId.RECOVERY.value
    assert bridge.block_continuation_resume is False
    assert updated.winner == CapabilityId.REPLAN.value

    snapshot = capture_gap_snapshot(
        orchestrator,
        gap_kind=updated.gap_kind,
        gap_resolved=updated.gap_resolved,
        answer_gate={"verified": False},
    ).as_dict()
    packet = build_goal_continuation_resume(
        orchestrator,
        updated,
        recorded={"mission_id": "m1", "execution_id": "x1"},
        correlation_id="corr-regression-replan",
        gap_snapshot=snapshot,
        continuation_stagnation_count=1,
        superseded_winner=CapabilityId.RECOVERY.value,
        regression_reroute=True,
    )
    assert packet.get("winner") == CapabilityId.REPLAN.value
    assert packet.get("superseded_winner") == CapabilityId.RECOVERY.value
    assert packet.get("regression_reroute") is True


def test_regression_without_replan_blocks_continuation_and_routes_help():
    decision = GapResolutionDecision(
        gap_kind=GapKind.SPEC_MEANING_GAP.value,
        gap_resolved=False,
        facts_sufficient=True,
        candidates=[
            CapabilityCandidate(
                id=CapabilityId.GOAL_COMPLETION_HUMAN.value,
                available=True,
                valuable=True,
                execute=True,
            )
        ],
        winner=CapabilityId.GOAL_COMPLETION_HUMAN.value,
    )
    updated, bridge = apply_regression_continuation_bridge(
        decision,
        prior_winner=CapabilityId.RECOVERY.value,
        human_priority_blocked=False,
    )
    assert bridge is not None
    assert bridge.reroute_winner is None
    assert bridge.help_escalation is True
    assert bridge.block_continuation_resume is True
    assert updated.winner == CapabilityId.HELP.value

    orchestrator = ChatTaskOrchestrator("phase4", "meaning gap")
    orchestrator.initialize()
    _, resume, event = observe_gap_resolution_at_execution_end(
        orchestrator,
        stop_reason="GOAL_COMPLETION_HUMAN",
        answer_gate={"verified": False, "reason": "awaiting_goal_completion_human"},
        loop_counters={},
        correlation_id="corr-regression-help",
        recorded={"mission_id": "m1", "execution_id": "x1"},
        human_priority_blocked=False,
        block_continuation_resume=True,
        help_escalation=True,
        decision=updated,
        regression_reroute=bridge.as_dict(),
    )
    assert resume is None
    assert event is not None
    assert event.get("winner") == CapabilityId.HELP.value
    assert event.get("continuation_resume_persisted") is False


def test_regression_does_not_reset_stagnation_count():
    prior = GapSnapshot(
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate_verified=False,
        unsatisfied_conditions=[],
        satisfied_conditions=["A", "B"],
    )
    current = GapSnapshot(
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate_verified=False,
        unsatisfied_conditions=["B"],
        satisfied_conditions=["A"],
    )
    verdict, _ = compare_gap_snapshots(prior, current)
    assert verdict == ProgressState.REGRESSION.value

    orchestrator = ChatTaskOrchestrator("phase4", "audit")
    orchestrator.initialize()
    task = orchestrator.runtime.tasks["T1"]
    task.completion_conditions = ["A", "B"]
    task.condition_status = {"A": "SATISFIED", "B": "UNKNOWN"}
    observation = observe_goal_continuation_progress(
        orchestrator,
        prior_snapshot=prior.as_dict(),
        gap_kind=GapKind.FACT_GAP.value,
        gap_resolved=False,
        answer_gate={"verified": False},
        continuation_stagnation_count=2,
    )
    assert observation is not None
    assert observation.verdict == ProgressState.REGRESSION.value
    assert observation.continuation_stagnation_count == 3
    assert observation.regression_detected is True


def test_regression_bridge_respects_human_priority():
    orchestrator = ChatTaskOrchestrator("phase4", "audit")
    orchestrator.initialize()
    decision = route_gap_resolution_from_orchestrator(
        orchestrator,
        stop_reason="GOAL_COMPLETION_HUMAN",
        answer_gate={"verified": False, "reason": "awaiting_goal_completion_human"},
    )
    prior_winner = CapabilityId.RECOVERY.value
    updated, bridge = apply_regression_continuation_bridge(
        decision,
        prior_winner=prior_winner,
        human_priority_blocked=True,
    )
    assert bridge is None
    assert updated.winner == decision.winner


def test_goal_completion_consumed_does_not_resolve_unrelated_fact_gap():
    inp = GapRouterInput(
        request="read part_b.txt",
        answer_gate={"verified": False, "reason": "completion_evidence_incomplete"},
        goal_incomplete=True,
        goal_completion_consumed=True,
        user_explicit_conditions=["part_a satisfied", "part_b satisfied"],
    )
    resolved, reasons = is_current_gap_resolved(inp, gap_kind=GapKind.FACT_GAP)
    assert resolved is False
    assert "user_explicit_completion_conditions" not in reasons
