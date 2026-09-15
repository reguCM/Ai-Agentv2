"""Read-only Completion Gap candidate discovery for a saved Production Run.

This module does not create Runtime Tasks, Actions, Evidence, or Acceptance
support relations.  It only composes already-persisted identities into a
candidate that a later, separately-authorized task-creation capability may use.
"""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.goal_handoff_runtime_bridge import runtime_task_id
from ai_tool.runtime_goal_completion_gap_entry import (
    assess_runtime_goal_completion_gap_entry,
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _token(value: Any) -> str:
    return str(value or "").strip()


def _tokens(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return list(dict.fromkeys(token for item in value if (token := _token(item))))


def _fail(base: Mapping[str, Any], code: str) -> dict[str, Any]:
    return {
        "status": "FAIL_CLOSED",
        "handoff_id": base.get("handoff_id"),
        "run_execution_id": base.get("run_execution_id"),
        "entry_status": base.get("entry_status"),
        "entry_assessment": dict(base),
        "candidates": [],
        "errors": [code],
    }


def _non_candidate(base: Mapping[str, Any], status: str) -> dict[str, Any]:
    return {
        "status": status,
        "handoff_id": base.get("handoff_id"),
        "run_execution_id": base.get("run_execution_id"),
        "entry_status": base.get("entry_status"),
        "entry_assessment": dict(base),
        "candidates": [],
    }


def _requirements_by_acceptance(handoff: Mapping[str, Any]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for binding in handoff.get("requirement_bindings") or []:
        if not isinstance(binding, Mapping):
            raise ValueError("invalid_requirement_binding")
        requirement_id = _token(binding.get("requirement_id"))
        if not requirement_id:
            raise ValueError("missing_requirement_binding_id")
        for acceptance_id in _tokens(binding.get("acceptance_ids")):
            refs = rows.setdefault(acceptance_id, [])
            if requirement_id not in refs:
                refs.append(requirement_id)
    return rows


def _criterion_rows(acceptance: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in acceptance.get("criterion_trace") or []:
        if not isinstance(row, Mapping):
            raise ValueError("invalid_criterion_trace")
        acceptance_id = _token(row.get("acceptance_id"))
        if not acceptance_id or acceptance_id in result:
            raise ValueError("invalid_criterion_identity")
        result[acceptance_id] = dict(row)
    return result


def _source_tasks_by_acceptance(handoff: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in handoff.get("implementation_tasks") or []:
        if not isinstance(row, Mapping):
            raise ValueError("invalid_handoff_task")
        source_task_id = _token(row.get("id"))
        if not source_task_id:
            raise ValueError("missing_handoff_task_id")
        for acceptance_id in _tokens(row.get("maps_to_acceptance")):
            refs = result.setdefault(acceptance_id, [])
            if source_task_id not in refs:
                refs.append(source_task_id)
    return result


def _evidence_ids(criterion: Mapping[str, Any]) -> list[str]:
    trace = _mapping(criterion.get("evidence_requirement_trace"))
    return _tokens(
        [
            row.get("evidence_id")
            for row in trace.get("evidence") or []
            if isinstance(row, Mapping)
        ]
    )


def discover_runtime_goal_completion_gaps(
    session: Mapping[str, Any],
    *,
    mission: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Derive identity-only Completion Gap candidates from an eligible Run.

    ``GAP_CANDIDATE`` deliberately means only that the existing saved facts
    identify an Acceptance blocker and its Handoff/Runtime anchors.  It is not
    a permission to create or execute a Task.
    """
    entry = assess_runtime_goal_completion_gap_entry(session, mission=mission)
    entry_status = _token(entry.get("status"))
    base = {
        "handoff_id": entry.get("handoff_id"),
        "run_execution_id": entry.get("run_execution_id"),
        "entry_status": entry_status,
    }
    if entry_status == "RETURN_TO_HUMAN_MEANING":
        return _non_candidate(base, "HUMAN_REQUIRED")
    if entry_status.startswith("FAIL_CLOSED") or entry_status.startswith("INCONCLUSIVE"):
        return _fail(base, f"entry_assessment:{entry_status}")
    if entry_status != "ELIGIBLE_FOR_COMPLETION_GAP_DISCOVERY":
        return _non_candidate(base, "NO_DISCOVERABLE_GAP")

    handoff = _mapping(session.get("production_handoff_packet"))
    acceptance_row = _mapping(session.get("production_acceptance_evaluation"))
    acceptance = _mapping(acceptance_row.get("result"))
    runtime = _mapping(session.get("production_runtime_snapshot"))
    mission_rows = {
        _token(row.get("requirement_id"))
        for row in ((mission or {}).get("structured_requirements") or [])
        if isinstance(row, Mapping) and _token(row.get("requirement_id"))
    }
    source_requirement_ids = {
        _token(item)
        for item in ((_mapping(handoff.get("source_binding"))).get("requirement_ids") or [])
        if _token(item)
    }
    try:
        criteria = _criterion_rows(acceptance)
        requirements = _requirements_by_acceptance(handoff)
        sources = _source_tasks_by_acceptance(handoff)
    except ValueError as exc:
        return _fail(base, str(exc))
    runtime_ids = {
        _token(row.get("task_id"))
        for row in runtime.get("tasks") or []
        if isinstance(row, Mapping) and _token(row.get("task_id"))
    }

    candidates: list[dict[str, Any]] = []
    for blocker in entry.get("blocking_criteria") or []:
        if not isinstance(blocker, Mapping):
            return _fail(base, "invalid_blocking_criterion")
        acceptance_id = _token(blocker.get("acceptance_id"))
        if not acceptance_id:
            return _fail(base, "missing_blocking_acceptance_id")
        if _token(blocker.get("reason")) != "acceptance_not_pass":
            return _fail(base, f"unsupported_blocking_reason:{acceptance_id}")
        if _token(blocker.get("meaning_coverage")) != "MATCH":
            return _fail(base, f"non_match_meaning_blocker:{acceptance_id}")
        criterion = criteria.get(acceptance_id)
        if criterion is None:
            return _fail(base, f"criterion_trace_not_found:{acceptance_id}")
        coverage = _token(_mapping(criterion.get("evidence_requirement_trace")).get("coverage"))
        if coverage != "MATCH":
            return _fail(base, f"criterion_coverage_mismatch:{acceptance_id}")
        requirement_ids = requirements.get(acceptance_id) or []
        if not requirement_ids:
            return _fail(base, f"requirement_binding_not_found:{acceptance_id}")
        if any(item not in mission_rows or item not in source_requirement_ids for item in requirement_ids):
            return _fail(base, f"requirement_identity_mismatch:{acceptance_id}")
        source_task_ids = sources.get(acceptance_id) or []
        if not source_task_ids:
            return _fail(base, f"handoff_task_mapping_not_found:{acceptance_id}")
        mapped_runtime_task_ids = [runtime_task_id(item) for item in source_task_ids]
        if any(item not in runtime_ids for item in mapped_runtime_task_ids):
            return _fail(base, f"runtime_task_mapping_not_found:{acceptance_id}")
        candidates.append(
            {
                "handoff_id": base["handoff_id"],
                "run_execution_id": base["run_execution_id"],
                "acceptance_id": acceptance_id,
                "blocker": {
                    "acceptance_id": acceptance_id,
                    "reason": _token(blocker.get("reason")),
                    "acceptance_judgment": _token(blocker.get("acceptance_judgment")),
                    "meaning_coverage": _token(blocker.get("meaning_coverage")),
                },
                "requirement_ids": list(requirement_ids),
                "source_task_ids": list(source_task_ids),
                "runtime_task_ids": mapped_runtime_task_ids,
                "evidence_ids": _evidence_ids(criterion),
            }
        )

    if not candidates:
        return _non_candidate(base, "NO_DISCOVERABLE_GAP")
    return {
        "status": "GAP_CANDIDATE",
        **base,
        "entry_assessment": entry,
        "candidates": candidates,
    }


__all__ = ["discover_runtime_goal_completion_gaps"]
