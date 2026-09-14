"""Read-only Audit summary derived from Acceptance Meaning Trace observations."""
from __future__ import annotations

from typing import Any, Mapping


ALIGNMENTS = ("MATCH", "PARTIAL", "MISMATCH", "UNTRACEABLE")


def build_acceptance_meaning_audit(acceptance_result: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize existing criterion traces without affecting any judgment."""
    criteria = [
        row for row in (acceptance_result.get("criterion_trace") or []) if isinstance(row, Mapping)
    ]
    counts = {status: 0 for status in ALIGNMENTS}
    details: list[dict[str, Any]] = []
    for criterion in criteria:
        trace = criterion.get("evidence_requirement_trace")
        trace = trace if isinstance(trace, Mapping) else {}
        coverage = str(trace.get("coverage") or "UNTRACEABLE")
        if coverage not in counts:
            coverage = "UNTRACEABLE"
        counts[coverage] += 1
        evidence_rows = [row for row in (trace.get("evidence") or []) if isinstance(row, Mapping)]
        observed_requirement_ids: list[str] = []
        for evidence in evidence_rows:
            reverse = evidence.get("trace")
            if not isinstance(reverse, Mapping):
                continue
            for requirement_id in reverse.get("requirement_ids") or []:
                token = str(requirement_id or "").strip()
                if token and token not in observed_requirement_ids:
                    observed_requirement_ids.append(token)
        details.append(
            {
                "acceptance_id": str(criterion.get("acceptance_id") or ""),
                "acceptance_judgment": str(acceptance_result.get("status") or ""),
                "meaning_coverage": coverage,
                "expected_requirement_ids": [
                    str(item) for item in (trace.get("expected_requirement_ids") or []) if str(item)
                ],
                "evidence_ids": [
                    str(row.get("evidence_id") or "") for row in evidence_rows if str(row.get("evidence_id") or "")
                ],
                "observed_requirement_ids": observed_requirement_ids,
            }
        )
    return {
        "criteria_count": len(criteria),
        "coverage_counts": counts,
        "criteria": details,
    }


__all__ = ["ALIGNMENTS", "build_acceptance_meaning_audit"]
