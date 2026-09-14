"""Fail-closed Goal Completion eligibility from persisted Acceptance Meaning Audit."""
from __future__ import annotations

from typing import Any, Mapping


_COVERAGES = {"MATCH", "PARTIAL", "MISMATCH", "UNTRACEABLE"}


def _block(
    acceptance_id: str | None,
    acceptance_judgment: str,
    meaning_coverage: str,
    reason: str,
) -> dict[str, str | None]:
    return {
        "acceptance_id": acceptance_id,
        "acceptance_judgment": acceptance_judgment,
        "meaning_coverage": meaning_coverage,
        "reason": reason,
    }


def assess_acceptance_meaning_completion_eligibility(
    acceptance_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Read existing Acceptance audit only; never mutate or re-evaluate it."""
    result = acceptance_result if isinstance(acceptance_result, Mapping) else {}
    judgment = str(result.get("status") or "").strip()
    audit = result.get("meaning_trace_audit")
    trace = result.get("criterion_trace")
    blocks: list[dict[str, str | None]] = []
    if not judgment:
        blocks.append(_block(None, "UNKNOWN", "UNKNOWN", "missing_acceptance_judgment"))
    if not isinstance(audit, Mapping):
        blocks.append(_block(None, judgment or "UNKNOWN", "UNKNOWN", "missing_meaning_trace_audit"))
        return {"completion_eligible": False, "blocking_criteria": blocks}
    criteria = audit.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        blocks.append(_block(None, judgment or "UNKNOWN", "UNKNOWN", "missing_required_criterion"))
        return {"completion_eligible": False, "blocking_criteria": blocks}
    if int(audit.get("criteria_count") or -1) != len(criteria):
        blocks.append(_block(None, judgment or "UNKNOWN", "UNKNOWN", "malformed_meaning_trace_audit"))
    if not isinstance(trace, list):
        blocks.append(_block(None, judgment or "UNKNOWN", "UNKNOWN", "missing_criterion_trace"))
        return {"completion_eligible": False, "blocking_criteria": blocks}
    trace_by_id = {
        str(row.get("acceptance_id") or "").strip(): row
        for row in trace
        if isinstance(row, Mapping) and str(row.get("acceptance_id") or "").strip()
    }
    seen_ids: set[str] = set()
    for row in criteria:
        if not isinstance(row, Mapping):
            blocks.append(_block(None, judgment or "UNKNOWN", "UNKNOWN", "malformed_criterion_audit"))
            continue
        acceptance_id = str(row.get("acceptance_id") or "").strip()
        coverage = str(row.get("meaning_coverage") or "UNKNOWN").strip()
        criterion_judgment = str(row.get("acceptance_judgment") or judgment or "UNKNOWN").strip()
        if not acceptance_id or acceptance_id in seen_ids:
            blocks.append(_block(acceptance_id or None, criterion_judgment, coverage, "invalid_criterion_identity"))
            continue
        seen_ids.add(acceptance_id)
        trace_row = trace_by_id.get(acceptance_id)
        trace_coverage = (
            str(((trace_row or {}).get("evidence_requirement_trace") or {}).get("coverage") or "UNKNOWN")
        )
        if trace_row is None or trace_coverage != coverage:
            blocks.append(_block(acceptance_id, criterion_judgment, coverage, "criterion_identity_inconsistent"))
            continue
        if coverage not in _COVERAGES:
            blocks.append(_block(acceptance_id, criterion_judgment, coverage, "unknown_meaning_coverage"))
            continue
        if judgment != "PASS":
            blocks.append(_block(acceptance_id, criterion_judgment, coverage, "acceptance_not_pass"))
            continue
        if criterion_judgment != "PASS":
            blocks.append(_block(acceptance_id, criterion_judgment, coverage, "criterion_judgment_inconsistent"))
            continue
        if coverage != "MATCH":
            blocks.append(_block(acceptance_id, criterion_judgment, coverage, "meaning_not_completion_eligible"))
    return {"completion_eligible": not blocks, "blocking_criteria": blocks}


__all__ = ["assess_acceptance_meaning_completion_eligibility"]
