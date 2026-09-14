"""Read-only Evidence -> Handoff Acceptance -> Mission Requirement identity trace."""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.goal_handoff_source_binding import validate_handoff_source_binding


class EvidenceRequirementTraceError(ValueError):
    """Raised when an Evidence identity cannot be traced without inference."""


def _fail(code: str) -> None:
    raise EvidenceRequirementTraceError(code)


def _token(value: Any) -> str:
    return str(value or "").strip()


def _unique_tokens(values: object) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return list(dict.fromkeys(token for item in values if (token := _token(item))))


def _evidence_record(evidence: object, runtime: Any) -> Any:
    if isinstance(evidence, str):
        evidence_id = _token(evidence)
        record = (getattr(runtime, "evidence", None) or {}).get(evidence_id)
        if record is None:
            _fail(f"evidence_not_found:{evidence_id or '<empty>'}")
        return record
    evidence_id = _token(getattr(evidence, "evidence_id", None))
    if not evidence_id:
        _fail("invalid_evidence_record")
    return evidence


def trace_evidence_requirement_identity(
    evidence: object,
    *,
    runtime: Any,
    handoff_packet: Mapping[str, Any],
    mission: Mapping[str, Any],
) -> dict[str, Any]:
    """Return identity-only reverse trace for an existing Evidence record.

    This function reads only existing runtime, handoff, and Mission structures.
    It never derives relations from text and never copies Human Meaning into the
    result: callers resolve ``mission_id`` + ``requirement_ids`` at the Mission
    canonical source when they need the Human Meaning itself.
    """
    source_errors = validate_handoff_source_binding(handoff_packet, mission)
    if source_errors:
        _fail(f"source_binding_mismatch:{source_errors[0]}")

    record = _evidence_record(evidence, runtime)
    evidence_id = _token(getattr(record, "evidence_id", None))
    runtime_task_ids = _unique_tokens(getattr(record, "task_ids", None))
    if not runtime_task_ids:
        _fail(f"evidence_has_no_task_ids:{evidence_id}")

    runtime_tasks = getattr(runtime, "tasks", None) or {}
    handoff_tasks = {
        _token(row.get("id")): row
        for row in (handoff_packet.get("implementation_tasks") or [])
        if isinstance(row, Mapping) and _token(row.get("id"))
    }
    acceptance_ids = {
        _token(row.get("id"))
        for row in (handoff_packet.get("acceptance_criteria") or [])
        if isinstance(row, Mapping) and _token(row.get("id"))
    }
    requirement_rows = {
        _token(row.get("requirement_id")): row
        for row in (mission.get("structured_requirements") or [])
        if isinstance(row, Mapping) and _token(row.get("requirement_id"))
    }
    source_requirement_ids = {
        _token(item)
        for item in ((handoff_packet.get("source_binding") or {}).get("requirement_ids") or [])
        if _token(item)
    }

    acceptance_to_requirements: dict[str, list[str]] = {}
    bindings = handoff_packet.get("requirement_bindings")
    if not isinstance(bindings, list):
        _fail("missing_requirement_bindings")
    for binding in bindings:
        if not isinstance(binding, Mapping):
            _fail("invalid_requirement_binding")
        requirement_id = _token(binding.get("requirement_id"))
        if not requirement_id:
            _fail("missing_requirement_binding_id")
        if requirement_id not in source_requirement_ids:
            _fail(f"requirement_binding_not_in_source_binding:{requirement_id}")
        if requirement_id not in requirement_rows:
            _fail(f"mission_requirement_not_found:{requirement_id}")
        for acceptance_id in _unique_tokens(binding.get("acceptance_ids")):
            if acceptance_id not in acceptance_ids:
                _fail(f"unknown_requirement_binding_acceptance:{requirement_id}:{acceptance_id}")
            acceptance_to_requirements.setdefault(acceptance_id, []).append(requirement_id)

    task_traces: list[dict[str, Any]] = []
    all_acceptance_ids: list[str] = []
    all_requirement_ids: list[str] = []
    for runtime_task_id in runtime_task_ids:
        task = runtime_tasks.get(runtime_task_id)
        if task is None:
            _fail(f"runtime_task_not_found:{runtime_task_id}")
        source_task_id = _token(getattr(task, "source_task_id", None))
        if not source_task_id:
            _fail(f"missing_source_task_id:{runtime_task_id}")
        handoff_task = handoff_tasks.get(source_task_id)
        if handoff_task is None:
            _fail(f"handoff_task_not_found:{source_task_id}")
        task_acceptance_ids = _unique_tokens(handoff_task.get("maps_to_acceptance"))
        if not task_acceptance_ids:
            _fail(f"task_has_no_acceptance_mapping:{source_task_id}")
        task_requirement_ids: list[str] = []
        for acceptance_id in task_acceptance_ids:
            if acceptance_id not in acceptance_ids:
                _fail(f"unknown_task_acceptance:{source_task_id}:{acceptance_id}")
            requirement_ids = list(dict.fromkeys(acceptance_to_requirements.get(acceptance_id) or []))
            if not requirement_ids:
                _fail(f"acceptance_has_no_requirement_binding:{acceptance_id}")
            task_requirement_ids.extend(requirement_ids)
        task_requirement_ids = list(dict.fromkeys(task_requirement_ids))
        task_traces.append(
            {
                "runtime_task_id": runtime_task_id,
                "source_task_id": source_task_id,
                "acceptance_ids": task_acceptance_ids,
                "requirement_ids": task_requirement_ids,
            }
        )
        all_acceptance_ids.extend(task_acceptance_ids)
        all_requirement_ids.extend(task_requirement_ids)

    return {
        "evidence_id": evidence_id,
        "runtime_task_ids": runtime_task_ids,
        "source_task_ids": [item["source_task_id"] for item in task_traces],
        "acceptance_ids": list(dict.fromkeys(all_acceptance_ids)),
        "requirement_ids": list(dict.fromkeys(all_requirement_ids)),
        "mission_id": _token(mission.get("mission_id")),
        "task_traces": task_traces,
    }


__all__ = ["EvidenceRequirementTraceError", "trace_evidence_requirement_identity"]
