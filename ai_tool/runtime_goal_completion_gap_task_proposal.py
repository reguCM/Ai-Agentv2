"""Identity-grounded, non-persistent Completion Gap Task Proposal v0.

The proposal is deliberately not a Runtime Task.  It contains no copied Human
Meaning, Requirement text, or Acceptance text, and grants no execution
authority.  A later Task-creation boundary must consume it only after its own
approval/creation contract is implemented.
"""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.runtime_goal_completion_gap_proposal_readiness import (
    assess_runtime_goal_completion_gap_proposal_readiness,
)


def _token(value: Any) -> str:
    return str(value or "").strip()


def _tokens(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return list(dict.fromkeys(token for item in value if (token := _token(item))))


def _blocked(readiness: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": _token(readiness.get("status")) or "FAIL_CLOSED",
        "handoff_id": readiness.get("handoff_id"),
        "run_execution_id": readiness.get("run_execution_id"),
        "proposal": None,
        "proposal_readiness": dict(readiness),
    }


def build_runtime_goal_completion_gap_task_proposal(
    session: Mapping[str, Any],
    *,
    mission: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return one bounded proposed-work envelope only when Proposal is ready.

    The operation is intentionally generic: existing identities establish the
    *scope* of a future corrective task, but do not authorize this layer to
    invent a new implementation method or restate canonical text.
    """
    readiness = assess_runtime_goal_completion_gap_proposal_readiness(
        session,
        mission=mission,
        candidate=candidate,
    )
    if _token(readiness.get("status")) != "PROPOSAL_READY":
        return _blocked(readiness)

    fresh = readiness.get("candidate")
    if not isinstance(fresh, Mapping):
        return {
            **_blocked(readiness),
            "status": "FAIL_CLOSED",
        }
    acceptance_id = _token(fresh.get("acceptance_id"))
    blocker = fresh.get("blocker")
    requirement_ids = _tokens(fresh.get("requirement_ids"))
    source_task_ids = _tokens(fresh.get("source_task_ids"))
    runtime_task_ids = _tokens(fresh.get("runtime_task_ids"))
    if (
        not acceptance_id
        or not isinstance(blocker, Mapping)
        or not requirement_ids
        or not source_task_ids
        or not runtime_task_ids
    ):
        return {
            **_blocked(readiness),
            "status": "FAIL_CLOSED",
        }
    if _token(blocker.get("acceptance_id")) != acceptance_id:
        return {
            **_blocked(readiness),
            "status": "FAIL_CLOSED",
        }

    proposal = {
        "proposal_type": "COMPLETION_GAP_TASK",
        "proposal_status": "CANDIDATE_ONLY",
        "acceptance_id": acceptance_id,
        "blocker": {
            "acceptance_id": acceptance_id,
            "reason": _token(blocker.get("reason")),
            "acceptance_judgment": _token(blocker.get("acceptance_judgment")),
            "meaning_coverage": _token(blocker.get("meaning_coverage")),
        },
        "requirement_ids": requirement_ids,
        "source_task_ids": source_task_ids,
        "runtime_task_ids": runtime_task_ids,
        "evidence_ids": _tokens(fresh.get("evidence_ids")),
        "proposal_boundary": {
            "creates_runtime_task": False,
            "executes_action": False,
            "adds_evidence": False,
            "registers_acceptance_support": False,
            "persists_to_session": False,
        },
    }
    return {
        "status": "TASK_PROPOSAL_CANDIDATE",
        "handoff_id": readiness.get("handoff_id"),
        "run_execution_id": readiness.get("run_execution_id"),
        "proposal": proposal,
        "proposal_readiness": readiness,
    }


__all__ = ["build_runtime_goal_completion_gap_task_proposal"]
