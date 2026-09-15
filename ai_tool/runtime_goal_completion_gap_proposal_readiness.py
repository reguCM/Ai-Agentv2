"""Read-only gate between Completion Gap Discovery and a future Task Proposal.

The gate never trusts a previously returned Candidate by itself.  It derives
the current Entry Assessment and Discovery result again, then compares their
identity-only Candidate to the supplied one.
"""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.runtime_goal_completion_gap_discovery import (
    discover_runtime_goal_completion_gaps,
)
from ai_tool.runtime_goal_completion_gap_entry import (
    assess_runtime_goal_completion_gap_entry,
)


_IDENTITY_LIST_FIELDS = (
    "requirement_ids",
    "source_task_ids",
    "runtime_task_ids",
)


def _token(value: Any) -> str:
    return str(value or "").strip()


def _identity_list(row: Mapping[str, Any], field: str) -> list[str] | None:
    values = row.get(field)
    if not isinstance(values, (list, tuple)):
        return None
    result = [_token(item) for item in values]
    if not result or any(not item for item in result) or len(set(result)) != len(result):
        return None
    return result


def _result(
    status: str,
    *,
    entry: Mapping[str, Any],
    discovery: Mapping[str, Any],
    candidate: Mapping[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": status,
        "handoff_id": discovery.get("handoff_id") or entry.get("handoff_id"),
        "run_execution_id": discovery.get("run_execution_id") or entry.get("run_execution_id"),
        "entry_status": entry.get("status"),
        "discovery_status": discovery.get("status"),
    }
    if candidate is not None:
        result["candidate"] = dict(candidate)
    if reason:
        result["reason"] = reason
    return result


def assess_runtime_goal_completion_gap_proposal_readiness(
    session: Mapping[str, Any],
    *,
    mission: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Decide whether one prior Candidate is still current enough for Proposal.

    No Task, Action, Evidence, Acceptance support relation, Session field, or
    persistent validation state is created.  A future Proposal creator must
    call this function immediately before it acts and proceed only on
    ``PROPOSAL_READY``.
    """
    entry = assess_runtime_goal_completion_gap_entry(session, mission=mission)
    discovery = discover_runtime_goal_completion_gaps(session, mission=mission)
    if _token(entry.get("status")) != _token(discovery.get("entry_status")):
        return _result(
            "FAIL_CLOSED",
            entry=entry,
            discovery=discovery,
            reason="entry_discovery_state_inconsistent",
        )

    discovery_status = _token(discovery.get("status"))
    if discovery_status == "HUMAN_REQUIRED":
        return _result("HUMAN_REQUIRED", entry=entry, discovery=discovery)
    if discovery_status == "FAIL_CLOSED":
        return _result("FAIL_CLOSED", entry=entry, discovery=discovery)
    if discovery_status != "GAP_CANDIDATE":
        entry_status = _token(entry.get("status"))
        if entry_status == "RETURN_TO_EXISTING_WORK":
            return _result("RETURN_TO_EXISTING_WORK", entry=entry, discovery=discovery)
        if entry_status == "RETURN_TO_VERIFICATION_REENTRY":
            return _result("RETURN_TO_VERIFICATION_REENTRY", entry=entry, discovery=discovery)
        return _result("NO_PROPOSAL_CANDIDATE", entry=entry, discovery=discovery)

    supplied = dict(candidate) if isinstance(candidate, Mapping) else {}
    handoff_id = _token(supplied.get("handoff_id"))
    run_execution_id = _token(supplied.get("run_execution_id"))
    acceptance_id = _token(supplied.get("acceptance_id"))
    if not handoff_id or not run_execution_id or not acceptance_id:
        return _result(
            "FAIL_CLOSED",
            entry=entry,
            discovery=discovery,
            reason="missing_candidate_identity",
        )
    if handoff_id != _token(discovery.get("handoff_id")) or run_execution_id != _token(
        discovery.get("run_execution_id")
    ):
        return _result(
            "STALE_CANDIDATE",
            entry=entry,
            discovery=discovery,
            reason="candidate_run_identity_mismatch",
        )
    fresh_rows = [
        dict(row)
        for row in discovery.get("candidates") or []
        if isinstance(row, Mapping) and _token(row.get("acceptance_id")) == acceptance_id
    ]
    if len(fresh_rows) != 1:
        return _result(
            "STALE_CANDIDATE",
            entry=entry,
            discovery=discovery,
            reason="candidate_acceptance_not_current",
        )
    fresh = fresh_rows[0]
    for field in _IDENTITY_LIST_FIELDS:
        supplied_values = _identity_list(supplied, field)
        fresh_values = _identity_list(fresh, field)
        if supplied_values is None or fresh_values is None:
            return _result(
                "FAIL_CLOSED",
                entry=entry,
                discovery=discovery,
                reason=f"invalid_candidate_{field}",
            )
        if set(supplied_values) != set(fresh_values):
            return _result(
                "STALE_CANDIDATE",
                entry=entry,
                discovery=discovery,
                reason=f"candidate_{field}_mismatch",
            )
    blocker = supplied.get("blocker")
    fresh_blocker = fresh.get("blocker")
    if not isinstance(blocker, Mapping) or not isinstance(fresh_blocker, Mapping):
        return _result(
            "FAIL_CLOSED",
            entry=entry,
            discovery=discovery,
            reason="invalid_candidate_blocker",
        )
    for field in ("acceptance_id", "reason", "acceptance_judgment", "meaning_coverage"):
        if _token(blocker.get(field)) != _token(fresh_blocker.get(field)):
            return _result(
                "STALE_CANDIDATE",
                entry=entry,
                discovery=discovery,
                reason=f"candidate_blocker_{field}_mismatch",
            )
    return _result(
        "PROPOSAL_READY",
        entry=entry,
        discovery=discovery,
        candidate=fresh,
    )


__all__ = ["assess_runtime_goal_completion_gap_proposal_readiness"]
