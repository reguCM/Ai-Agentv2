"""Deterministic Requirement-to-Handoff identity coverage checks."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


_NON_MATERIAL_DISPOSITIONS = {"NOISE", "CONTEXT"}


def material_requirement_ids(
    structured_requirements: Sequence[Mapping[str, Any]] | None,
) -> list[str]:
    """Return resolved, design-blocking Requirement identities only."""
    result: list[str] = []
    for row in structured_requirements or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("resolution_status") or "") != "resolved":
            continue
        if str(row.get("materiality") or "") != "blocks_design":
            continue
        if str(row.get("disposition") or "") in _NON_MATERIAL_DISPOSITIONS:
            continue
        requirement_id = str(row.get("requirement_id") or "").strip()
        if requirement_id:
            result.append(requirement_id)
    return sorted(set(result))


def validate_requirement_handoff_bindings(
    packet: Mapping[str, Any],
    structured_requirements: Sequence[Mapping[str, Any]] | None,
) -> list[str]:
    """Validate only explicit Handoff identity relations; never infer meaning."""
    requirements = [row for row in (structured_requirements or []) if isinstance(row, Mapping)]
    known_requirement_ids = {
        str(row.get("requirement_id") or "").strip() for row in requirements
    }
    known_requirement_ids.discard("")
    required_ids = set(material_requirement_ids(requirements))
    bindings = packet.get("requirement_bindings")
    if not isinstance(bindings, list):
        return ["missing_requirement_bindings"] if required_ids else []

    task_ids = {
        str(row.get("id") or "").strip()
        for row in (packet.get("implementation_tasks") or [])
        if isinstance(row, Mapping)
    }
    acceptance_ids = {
        str(row.get("id") or "").strip()
        for row in (packet.get("acceptance_criteria") or [])
        if isinstance(row, Mapping)
    }
    source_requirement_ids = {
        str(item or "").strip()
        for item in ((packet.get("source_binding") or {}).get("requirement_ids") or [])
    }
    errors: list[str] = []
    bound_ids: set[str] = set()
    seen: set[str] = set()
    for row in bindings:
        if not isinstance(row, Mapping):
            errors.append("invalid_requirement_binding")
            continue
        requirement_id = str(row.get("requirement_id") or "").strip()
        if not requirement_id:
            errors.append("invalid_requirement_binding_id")
            continue
        if requirement_id in seen:
            errors.append(f"duplicate_requirement_binding:{requirement_id}")
        seen.add(requirement_id)
        if requirement_id not in known_requirement_ids:
            errors.append(f"unknown_requirement_binding:{requirement_id}")
        if source_requirement_ids and requirement_id not in source_requirement_ids:
            errors.append(f"requirement_binding_not_in_source_binding:{requirement_id}")
        row_task_ids = [str(item or "").strip() for item in (row.get("task_ids") or [])]
        row_acceptance_ids = [str(item or "").strip() for item in (row.get("acceptance_ids") or [])]
        if not row_task_ids and not row_acceptance_ids:
            errors.append(f"unbound_requirement_binding:{requirement_id}")
        for task_id in row_task_ids:
            if task_id not in task_ids:
                errors.append(f"unknown_requirement_binding_task:{requirement_id}:{task_id}")
        for acceptance_id in row_acceptance_ids:
            if acceptance_id not in acceptance_ids:
                errors.append(
                    f"unknown_requirement_binding_acceptance:{requirement_id}:{acceptance_id}"
                )
        if row_task_ids or row_acceptance_ids:
            bound_ids.add(requirement_id)

    for requirement_id in sorted(required_ids - bound_ids):
        errors.append(f"material_requirement_unbound:{requirement_id}")
    return sorted(set(errors))


__all__ = ["material_requirement_ids", "validate_requirement_handoff_bindings"]
