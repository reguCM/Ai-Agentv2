"""Mechanical Verification engine — Evidence ↔ Claim deterministic check.

Reuses numeric/entity/temporal logic from success_class evaluation harness.
Maps claim support to MATCH / MISMATCH / UNSUPPORTED / UNKNOWN.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ai_tool.web_tool_success_class_accuracy_evaluation import (
    ExpectedFact,
    YEAR_PATTERN,
    _check_answer_fact,
    _detect_unsupported_additions,
    extract_numeric_values,
    extract_population_numeric_values,
)

VerificationVerdict = Literal["MATCH", "MISMATCH", "UNSUPPORTED", "UNKNOWN"]

_SUPPORT_TO_VERDICT: dict[str, VerificationVerdict] = {
    "supported": "MATCH",
    "contradicted": "MISMATCH",
    "unsupported": "UNSUPPORTED",
    "ambiguous": "UNKNOWN",
}

DEFAULT_NUMERIC_RELATIVE_TOLERANCE = 0.05


@dataclass
class VerificationResult:
    claim_id: str
    claim_text: str
    claim_type: str
    verdict: VerificationVerdict
    method: str
    tolerance: float | None = None
    evidence_present: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MechanicalVerificationReport:
    overall: VerificationVerdict
    results: list[VerificationResult] = field(default_factory=list)
    match_count: int = 0
    mismatch_count: int = 0
    unsupported_count: int = 0
    unknown_count: int = 0
    numeric_tolerance: float = DEFAULT_NUMERIC_RELATIVE_TOLERANCE

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["results"] = [r.to_dict() for r in self.results]
        return d


def _support_to_verdict(support: str) -> VerificationVerdict:
    return _SUPPORT_TO_VERDICT.get(support, "UNKNOWN")


def _aggregate_verdict(results: list[VerificationResult]) -> VerificationVerdict:
    if not results:
        return "UNKNOWN"
    if any(r.verdict == "MISMATCH" for r in results):
        return "MISMATCH"
    if any(r.verdict == "UNSUPPORTED" for r in results):
        return "UNSUPPORTED"
    if all(r.verdict == "MATCH" for r in results):
        return "MATCH"
    if any(r.verdict == "UNKNOWN" for r in results):
        return "UNKNOWN"
    return "MATCH"


def extract_heuristic_evidence_facts(evidence: str) -> dict[str, Any]:
    """Best-effort fact extraction without ExpectedFact ground truth."""
    blob = str(evidence or "")
    return {
        "population_numerics": extract_population_numeric_values(blob),
        "all_numerics": extract_numeric_values(blob),
        "years": list({m.group(0) for m in YEAR_PATTERN.finditer(blob)}),
        "char_length": len(blob),
    }


def verify_answer(
    evidence: str,
    answer: str | None,
    expected_facts: list[ExpectedFact],
    *,
    numeric_tolerance: float = DEFAULT_NUMERIC_RELATIVE_TOLERANCE,
    check_unsupported_numerics: bool = True,
) -> MechanicalVerificationReport:
    """
    Verify LLM answer claims against evidence using ExpectedFact specs.

    Requires ExpectedFact for question-specific verification.
    Heuristic-only verification is limited (see extract_heuristic_evidence_facts).
    """
    results: list[VerificationResult] = []
    ans = str(answer or "")

    if not ans.strip():
        return MechanicalVerificationReport(
            overall="UNKNOWN",
            results=[
                VerificationResult("empty_answer", "", "meta", "UNKNOWN", "empty_answer"),
            ],
            unknown_count=1,
            numeric_tolerance=numeric_tolerance,
        )

    for fact in expected_facts:
        ok, support, claims = _check_answer_fact(ans, evidence, fact)
        for c in claims:
            verdict = _support_to_verdict(c.support)
            results.append(
                VerificationResult(
                    claim_id=c.claim_id,
                    claim_text=c.claim_text,
                    claim_type=c.claim_type,
                    verdict=verdict,
                    method=c.verification_method or "expected_fact",
                    tolerance=numeric_tolerance if c.claim_type == "numeric" else None,
                    evidence_present=ok or support == "supported",
                )
            )

    if check_unsupported_numerics:
        for c in _detect_unsupported_additions(ans, evidence):
            results.append(
                VerificationResult(
                    claim_id=c.claim_id,
                    claim_text=c.claim_text,
                    claim_type=c.claim_type,
                    verdict=_support_to_verdict(c.support),
                    method=c.verification_method or "numeric_not_in_evidence",
                    tolerance=numeric_tolerance,
                    evidence_present=False,
                )
            )

    report = MechanicalVerificationReport(
        overall=_aggregate_verdict(results),
        results=results,
        numeric_tolerance=numeric_tolerance,
    )
    for r in results:
        if r.verdict == "MATCH":
            report.match_count += 1
        elif r.verdict == "MISMATCH":
            report.mismatch_count += 1
        elif r.verdict == "UNSUPPORTED":
            report.unsupported_count += 1
        else:
            report.unknown_count += 1
    return report


def numeric_values_match(
    answer_value: float,
    evidence_values: list[float],
    *,
    relative_tolerance: float = DEFAULT_NUMERIC_RELATIVE_TOLERANCE,
) -> bool:
    """Check if answer numeric is within tolerance of any evidence numeric."""
    if not evidence_values:
        return False
    for ev in evidence_values:
        if ev <= 0:
            continue
        if abs(answer_value - ev) / ev <= relative_tolerance:
            return True
    return False
