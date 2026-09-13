"""Cross-execution Goal Gap progress for Goal Continuation (Phase 4).

Compares gap snapshots between continuation executions using existing Runtime
facts. Tool calls or LLM text changes alone do not count as PROGRESS.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from tools.ai.task_runtime import ProgressState, TaskStatus

# PROVISIONAL: cross-execution stagnation limit before HELP / Human escalation.
CONTINUATION_CROSS_EXECUTION_STAGNATION_LIMIT = 2


@dataclass
class GapSnapshot:
    gap_kind: str
    gap_resolved: bool
    answer_gate_verified: bool
    unsatisfied_conditions: list[str] = field(default_factory=list)
    satisfied_conditions: list[str] = field(default_factory=list)
    verified_evidence_ids: list[str] = field(default_factory=list)
    goal_statuses: dict[str, str] = field(default_factory=dict)
    task_statuses: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> GapSnapshot | None:
        if not isinstance(data, Mapping):
            return None
        return cls(
            gap_kind=str(data.get("gap_kind") or ""),
            gap_resolved=bool(data.get("gap_resolved")),
            answer_gate_verified=bool(data.get("answer_gate_verified")),
            unsatisfied_conditions=[
                str(item) for item in (data.get("unsatisfied_conditions") or []) if str(item)
            ],
            satisfied_conditions=[
                str(item) for item in (data.get("satisfied_conditions") or []) if str(item)
            ],
            verified_evidence_ids=[
                str(item) for item in (data.get("verified_evidence_ids") or []) if str(item)
            ],
            goal_statuses={
                str(key): str(value)
                for key, value in dict(data.get("goal_statuses") or {}).items()
            },
            task_statuses={
                str(key): str(value)
                for key, value in dict(data.get("task_statuses") or {}).items()
            },
        )


@dataclass
class ContinuationProgressObservation:
    verdict: str
    reasons: list[str]
    prior_snapshot: dict[str, Any] | None
    current_snapshot: dict[str, Any]
    continuation_stagnation_count: int
    continuation_blocked: bool
    help_escalation: bool
    regression_detected: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reasons": self.reasons,
            "prior_snapshot": self.prior_snapshot,
            "current_snapshot": self.current_snapshot,
            "continuation_stagnation_count": self.continuation_stagnation_count,
            "continuation_blocked": self.continuation_blocked,
            "help_escalation": self.help_escalation,
            "regression_detected": self.regression_detected,
            "stagnation_limit": CONTINUATION_CROSS_EXECUTION_STAGNATION_LIMIT,
        }


def capture_gap_snapshot(
    orchestrator: Any,
    *,
    gap_kind: str,
    gap_resolved: bool,
    answer_gate: Mapping[str, Any] | None,
) -> GapSnapshot:
    """Capture comparable Goal Gap facts from the current execution."""
    runtime = getattr(orchestrator, "runtime", None)
    tasks = getattr(runtime, "tasks", None) or {}
    evidence = getattr(runtime, "evidence", None) or {}
    goals = getattr(runtime, "goals", None) or {}

    unsatisfied: list[str] = []
    satisfied: list[str] = []
    verified_evidence_ids: list[str] = []

    for task in tasks.values():
        for condition in task.completion_conditions:
            status = str(task.condition_status.get(condition) or "UNKNOWN")
            if status == "SATISFIED":
                if condition not in satisfied:
                    satisfied.append(condition)
            else:
                if condition not in unsatisfied:
                    unsatisfied.append(condition)
        for evidence_id in task.evidence_ids:
            record = evidence.get(evidence_id)
            if record is not None and bool(getattr(record, "verified", False)):
                if evidence_id not in verified_evidence_ids:
                    verified_evidence_ids.append(str(evidence_id))

    return GapSnapshot(
        gap_kind=str(gap_kind or ""),
        gap_resolved=bool(gap_resolved),
        answer_gate_verified=bool((answer_gate or {}).get("verified")),
        unsatisfied_conditions=sorted(unsatisfied),
        satisfied_conditions=sorted(satisfied),
        verified_evidence_ids=sorted(verified_evidence_ids),
        goal_statuses={
            str(goal_id): str(getattr(goal, "status", "") or "")
            for goal_id, goal in goals.items()
        },
        task_statuses={
            str(task_id): str(getattr(task, "status", "") or "")
            for task_id, task in tasks.items()
        },
    )


def gap_signature(snapshot: GapSnapshot) -> tuple[Any, ...]:
    """Stable signature for stagnation detection."""
    return (
        snapshot.gap_kind,
        tuple(snapshot.unsatisfied_conditions),
        tuple(snapshot.satisfied_conditions),
        snapshot.answer_gate_verified,
        snapshot.gap_resolved,
    )


def _task_status_regressed(prior: Mapping[str, str], current: Mapping[str, str]) -> bool:
    rank = {
        TaskStatus.PENDING.value: 0,
        TaskStatus.IN_PROGRESS.value: 1,
        TaskStatus.COMPLETE.value: 2,
    }
    for task_id, prior_status in prior.items():
        current_status = current.get(task_id)
        if current_status is None:
            continue
        if rank.get(current_status, 0) < rank.get(prior_status, 0):
            return True
    return False


def compare_gap_snapshots(
    prior: GapSnapshot,
    current: GapSnapshot,
) -> tuple[str, list[str]]:
    """Return PROGRESS / STAGNATION / REGRESSION based on Goal Gap movement."""
    prior_unsat = set(prior.unsatisfied_conditions)
    cur_unsat = set(current.unsatisfied_conditions)
    prior_sat = set(prior.satisfied_conditions)
    cur_sat = set(current.satisfied_conditions)

    newly_satisfied = prior_unsat - cur_unsat
    lost_satisfied = prior_sat - cur_sat
    newly_unsatisfied = cur_unsat - prior_unsat

    if not prior.gap_resolved and current.gap_resolved:
        return ProgressState.PROGRESS.value, ["gap_resolved"]
    if not prior.answer_gate_verified and current.answer_gate_verified:
        return ProgressState.PROGRESS.value, ["answer_gate_verified"]
    if newly_satisfied:
        return ProgressState.PROGRESS.value, [
            f"conditions_satisfied:{','.join(sorted(newly_satisfied))}"
        ]

    if lost_satisfied:
        return ProgressState.REGRESSION.value, [
            f"conditions_lost:{','.join(sorted(lost_satisfied))}"
        ]
    if newly_unsatisfied and not newly_satisfied:
        return ProgressState.REGRESSION.value, [
            f"conditions_reopened:{','.join(sorted(newly_unsatisfied))}"
        ]
    if _task_status_regressed(prior.task_statuses, current.task_statuses):
        return ProgressState.REGRESSION.value, ["task_status_regressed"]
    if (
        prior.answer_gate_verified
        and not current.answer_gate_verified
        and not current.gap_resolved
    ):
        return ProgressState.REGRESSION.value, ["answer_gate_unverified"]

    if gap_signature(prior) == gap_signature(current):
        return ProgressState.STAGNATION.value, ["gap_signature_unchanged"]

    if (
        set(current.verified_evidence_ids) - set(prior.verified_evidence_ids)
        and not newly_satisfied
    ):
        return ProgressState.STAGNATION.value, ["evidence_without_condition_progress"]

    return ProgressState.STAGNATION.value, ["no_meaningful_gap_improvement"]


def observe_goal_continuation_progress(
    orchestrator: Any,
    *,
    prior_snapshot: Mapping[str, Any] | None,
    gap_kind: str,
    gap_resolved: bool,
    answer_gate: Mapping[str, Any] | None,
    continuation_stagnation_count: int = 0,
) -> ContinuationProgressObservation | None:
    """Compare current execution against the prior continuation snapshot."""
    prior = GapSnapshot.from_mapping(prior_snapshot)
    if prior is None:
        return None
    current = capture_gap_snapshot(
        orchestrator,
        gap_kind=gap_kind,
        gap_resolved=gap_resolved,
        answer_gate=answer_gate,
    )
    verdict, reasons = compare_gap_snapshots(prior, current)
    updated_count = int(continuation_stagnation_count)
    if verdict == ProgressState.PROGRESS.value:
        updated_count = 0
    elif verdict in {ProgressState.STAGNATION.value, ProgressState.REGRESSION.value}:
        updated_count += 1

    stagnation_limit_reached = updated_count >= CONTINUATION_CROSS_EXECUTION_STAGNATION_LIMIT
    return ContinuationProgressObservation(
        verdict=verdict,
        reasons=reasons,
        prior_snapshot=prior.as_dict(),
        current_snapshot=current.as_dict(),
        continuation_stagnation_count=updated_count,
        continuation_blocked=stagnation_limit_reached,
        help_escalation=stagnation_limit_reached,
        regression_detected=verdict == ProgressState.REGRESSION.value,
    )
