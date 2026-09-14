"""Identity-only Verification re-entry context for Meaning-blocked Acceptance."""
from __future__ import annotations

from typing import Any, Mapping

from ai_tool.goal_handoff_source_binding import validate_handoff_source_binding
from ai_tool.goal_handoff_runtime_bridge import runtime_task_id


_BLOCKING_COVERAGES = {"PARTIAL", "MISMATCH", "UNTRACEABLE"}


def _token(value: Any) -> str:
    return str(value or "").strip()


def _tokens(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return list(dict.fromkeys(token for item in values if (token := _token(item))))


def _criterion_rows(acceptance_result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _token(row.get("acceptance_id")): row
        for row in (acceptance_result.get("criterion_trace") or [])
        if isinstance(row, Mapping) and _token(row.get("acceptance_id"))
    }


def _audit_rows(acceptance_result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    audit = acceptance_result.get("meaning_trace_audit")
    criteria = audit.get("criteria") if isinstance(audit, Mapping) else None
    return [row for row in (criteria or []) if isinstance(row, Mapping)]


def _expected_task_ids(
    requirement_ids: list[str],
    acceptance_id: str,
    handoff_packet: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    """Return Requirement-bound Handoff tasks and unresolved Requirement IDs."""
    bindings = [
        row for row in (handoff_packet.get("requirement_bindings") or []) if isinstance(row, Mapping)
    ]
    tasks_by_id = {
        _token(row.get("id")): row
        for row in (handoff_packet.get("implementation_tasks") or [])
        if isinstance(row, Mapping) and _token(row.get("id"))
    }
    source_tasks: list[str] = []
    unresolved: list[str] = []
    for requirement_id in requirement_ids:
        matching = [row for row in bindings if _token(row.get("requirement_id")) == requirement_id]
        candidate_ids = _tokens(
            [item for row in matching for item in _tokens(row.get("task_ids"))]
        )
        # A requirement may bind directly to an Acceptance. In that case its
        # mapped Handoff tasks are still the only identity-based task path.
        if not candidate_ids and any(acceptance_id in _tokens(row.get("acceptance_ids")) for row in matching):
            candidate_ids = [
                task_id
                for task_id, task in tasks_by_id.items()
                if acceptance_id in _tokens(task.get("maps_to_acceptance"))
            ]
        valid = [
            task_id
            for task_id in candidate_ids
            if task_id in tasks_by_id
            and acceptance_id in _tokens(tasks_by_id[task_id].get("maps_to_acceptance"))
        ]
        if not valid:
            unresolved.append(requirement_id)
            continue
        for task_id in valid:
            if task_id not in source_tasks:
                source_tasks.append(task_id)
    return source_tasks, unresolved


def build_acceptance_meaning_verification_reentry(
    acceptance_result: Mapping[str, Any] | None,
    *,
    handoff_packet: Mapping[str, Any],
    mission: Mapping[str, Any] | None,
    runtime: Any,
) -> dict[str, Any]:
    """Derive, but never execute or persist independently, Verification targets.

    The result intentionally contains identities only. A caller may retain this
    derived output in its existing judgment record for reload/audit, but this
    helper neither changes runtime state nor treats any observed Evidence as
    reusable for the expected Requirement.
    """
    result = acceptance_result if isinstance(acceptance_result, Mapping) else {}
    if _token(result.get("status")) != "PASS":
        return {"status": "NOT_APPLICABLE", "verification_reentry": []}
    source_errors = validate_handoff_source_binding(handoff_packet, mission)
    if source_errors:
        return {
            "status": "VERIFICATION_REENTRY_UNRESOLVED",
            "verification_reentry": [],
            "errors": [f"source_binding_mismatch:{error}" for error in source_errors],
        }

    traces = _criterion_rows(result)
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    for audit in _audit_rows(result):
        acceptance_id = _token(audit.get("acceptance_id"))
        coverage = _token(audit.get("meaning_coverage"))
        if coverage not in _BLOCKING_COVERAGES:
            continue
        if _token(audit.get("acceptance_judgment") or result.get("status")) != "PASS":
            continue
        trace = traces.get(acceptance_id)
        evidence_trace = trace.get("evidence_requirement_trace") if isinstance(trace, Mapping) else None
        if not acceptance_id or not isinstance(evidence_trace, Mapping):
            errors.append(f"missing_criterion_identity_trace:{acceptance_id or '<empty>'}")
            continue
        if _token(evidence_trace.get("coverage")) != coverage:
            errors.append(f"criterion_coverage_mismatch:{acceptance_id}")
            continue
        expected = _tokens(evidence_trace.get("expected_requirement_ids"))
        observed = _tokens(audit.get("observed_requirement_ids"))
        evidence_ids = _tokens(audit.get("evidence_ids"))
        if not expected:
            errors.append(f"missing_expected_requirement_ids:{acceptance_id}")
            continue
        target_requirements = (
            [item for item in expected if item not in observed]
            if coverage == "PARTIAL"
            else expected
        )
        if not target_requirements:
            errors.append(f"no_missing_requirement_ids:{acceptance_id}")
            continue
        source_task_ids, unresolved = _expected_task_ids(target_requirements, acceptance_id, handoff_packet)
        if unresolved:
            errors.extend(
                f"requirement_task_identity_missing:{acceptance_id}:{requirement_id}"
                for requirement_id in unresolved
            )
            continue
        runtime_task_ids = [runtime_task_id(task_id) for task_id in source_task_ids]
        runtime_tasks = getattr(runtime, "tasks", None) or {}
        missing_runtime = [task_id for task_id in runtime_task_ids if task_id not in runtime_tasks]
        if missing_runtime:
            errors.extend(f"runtime_task_not_found:{task_id}" for task_id in missing_runtime)
            continue
        entries.append(
            {
                "acceptance_id": acceptance_id,
                "meaning_coverage": coverage,
                "expected_requirement_ids": expected,
                "observed_requirement_ids": observed,
                "evidence_ids": evidence_ids,
                "requirement_ids": target_requirements,
                "source_task_ids": source_task_ids,
                "runtime_task_ids": runtime_task_ids,
                "reason": f"meaning_{coverage.lower()}_requires_verification",
            }
        )
    if errors:
        return {
            "status": "VERIFICATION_REENTRY_UNRESOLVED",
            "verification_reentry": entries,
            "errors": errors,
        }
    return {
        "status": "VERIFICATION_REENTRY_CONTEXT_READY" if entries else "NOT_APPLICABLE",
        "verification_reentry": entries,
    }


__all__ = ["build_acceptance_meaning_verification_reentry"]
