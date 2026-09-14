"""Read-only Level 4 entry assessment for a saved Production Runtime Goal.

This module deliberately does not discover, create, persist, or schedule work.
It only separates remaining Completion blockers by the existing owner that must
run before a future Completion Gap Discovery capability could be considered.
"""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.acceptance_meaning_completion import (
    assess_acceptance_meaning_completion_eligibility,
)
from ai_tool.acceptance_meaning_verification_reentry import (
    build_acceptance_meaning_verification_reentry,
)
from ai_tool.runtime_goal_closure_report import build_runtime_goal_closure_report


_IDENTITY_BLOCKER_CODES = frozenset(
    {
        "invalid_handoff_identity",
        "missing_run_contract_or_meaning_context",
        "missing_mission",
        "run_contract_mismatch",
        "runtime_handoff_identity_mismatch",
        "missing_acceptance_evaluation",
        "acceptance_handoff_identity_mismatch",
        "missing_goal_judgment",
        "goal_judgment_handoff_identity_mismatch",
        "goal_judgment_eligibility_mismatch",
    }
)

_INVALID_CRITERION_REASONS = frozenset(
    {
        "missing_acceptance_judgment",
        "missing_meaning_trace_audit",
        "missing_required_criterion",
        "malformed_meaning_trace_audit",
        "missing_criterion_trace",
        "malformed_criterion_audit",
        "invalid_criterion_identity",
        "criterion_identity_inconsistent",
        "unknown_meaning_coverage",
    }
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _tokens(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item)]


def assess_runtime_goal_completion_gap_entry(
    session: Mapping[str, Any],
    *,
    mission: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Classify whether existing owners preclude Level 4 Gap Discovery.

    ``ELIGIBLE_FOR_COMPLETION_GAP_DISCOVERY`` is intentionally only an
    assessment result.  It authorizes neither Task creation nor execution.
    """
    closure = build_runtime_goal_closure_report(session, mission=mission)
    closure_status = str(closure.get("status") or "")
    closure_blockers = [
        _mapping(item) for item in closure.get("blockers") or [] if isinstance(item, Mapping)
    ]
    codes = {str(item.get("code") or "") for item in closure_blockers}
    base = {
        "handoff_id": closure.get("handoff_id"),
        "run_execution_id": closure.get("run_execution_id"),
        "closure_status": closure_status,
        "closure_blockers": closure_blockers,
    }

    if closure_status == "CLOSURE_READY":
        return {**base, "status": "NOT_APPLICABLE_COMPLETED", "blocking_criteria": []}
    if closure_status == "INCONCLUSIVE" or codes & _IDENTITY_BLOCKER_CODES:
        return {**base, "status": "FAIL_CLOSED_IDENTITY", "blocking_criteria": []}

    readiness = _mapping(session.get("production_acceptance_readiness"))
    if not bool(readiness.get("acceptance_ready")):
        return {
            **base,
            "status": "RETURN_TO_EXISTING_WORK",
            "blocking_criteria": [],
            "readiness": {
                "incomplete_task_ids": _tokens(readiness.get("incomplete_task_ids")),
                "unresolved_failure_ids": _tokens(readiness.get("unresolved_failure_ids")),
                "missing_evidence": [
                    _mapping(item)
                    for item in readiness.get("missing_evidence") or []
                    if isinstance(item, Mapping)
                ],
            },
        }

    handoff = _mapping(session.get("production_handoff_packet"))
    acceptance_row = _mapping(session.get("production_acceptance_evaluation"))
    acceptance = _mapping(acceptance_row.get("result"))
    runtime = _mapping(session.get("production_runtime_snapshot"))
    eligibility = assess_acceptance_meaning_completion_eligibility(acceptance)
    blocking_criteria = [
        _mapping(item)
        for item in eligibility.get("blocking_criteria") or []
        if isinstance(item, Mapping)
    ]

    if any(str(item.get("reason") or "") in _INVALID_CRITERION_REASONS for item in blocking_criteria):
        return {**base, "status": "FAIL_CLOSED_CRITERION_IDENTITY", "blocking_criteria": blocking_criteria}

    # The existing helper decides whether a non-MATCH PASS can be repaired by
    # an identity-bound verification Action on an existing Runtime Task.
    reentry = build_acceptance_meaning_verification_reentry(
        acceptance,
        handoff_packet=handoff,
        mission=mission,
        runtime=_SnapshotRuntime(runtime),
    )
    reentry_status = str(reentry.get("status") or "")
    if reentry_status == "VERIFICATION_REENTRY_CONTEXT_READY":
        return {
            **base,
            "status": "RETURN_TO_VERIFICATION_REENTRY",
            "blocking_criteria": blocking_criteria,
            "verification_reentry": reentry,
        }
    if reentry_status == "VERIFICATION_REENTRY_UNRESOLVED":
        return {
            **base,
            "status": "FAIL_CLOSED_VERIFICATION_IDENTITY",
            "blocking_criteria": blocking_criteria,
            "verification_reentry": reentry,
        }

    # A non-MATCH criterion without an executable identity-bound verification
    # route may require a Human canonical-meaning decision, not new work.
    if any(str(item.get("meaning_coverage") or "") != "MATCH" for item in blocking_criteria):
        return {
            **base,
            "status": "RETURN_TO_HUMAN_MEANING",
            "blocking_criteria": blocking_criteria,
            "verification_reentry": reentry,
        }

    # At this point all existing Runtime work is complete, readiness is true,
    # identity is valid, and the remaining criterion-level blocker is an
    # Acceptance failure rather than a known Evidence/Meaning route.
    if blocking_criteria and "acceptance_not_pass" in {
        str(item.get("reason") or "") for item in blocking_criteria
    }:
        return {
            **base,
            "status": "ELIGIBLE_FOR_COMPLETION_GAP_DISCOVERY",
            "blocking_criteria": blocking_criteria,
            "verification_reentry": reentry,
        }

    return {
        **base,
        "status": "INCONCLUSIVE_NO_CONCRETE_CRITERION_BLOCKER",
        "blocking_criteria": blocking_criteria,
        "verification_reentry": reentry,
    }


class _SnapshotTask:
    def __init__(self, row: Mapping[str, Any]) -> None:
        self.__dict__.update(dict(row))


class _SnapshotRuntime:
    """Minimal read-only adapter for the existing verification helper."""

    def __init__(self, snapshot: Mapping[str, Any]) -> None:
        self.tasks = {
            str(row.get("task_id") or ""): _SnapshotTask(row)
            for row in snapshot.get("tasks") or []
            if isinstance(row, Mapping) and str(row.get("task_id") or "")
        }


__all__ = ["assess_runtime_goal_completion_gap_entry"]
