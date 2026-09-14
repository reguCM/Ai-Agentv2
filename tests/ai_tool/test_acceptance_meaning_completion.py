from __future__ import annotations

import pytest

from ai_tool.acceptance_meaning_completion import (
    assess_acceptance_meaning_completion_eligibility,
)


def _result(*, status: str = "PASS", coverages: list[str] | None = None) -> dict:
    coverages = coverages or ["MATCH"]
    criterion_trace = [
        {"acceptance_id": f"A{index}", "evidence_requirement_trace": {"coverage": coverage}}
        for index, coverage in enumerate(coverages, start=1)
    ]
    return {
        "status": status,
        "criterion_trace": criterion_trace,
        "meaning_trace_audit": {
            "criteria_count": len(coverages),
            "coverage_counts": {token: coverages.count(token) for token in ("MATCH", "PARTIAL", "MISMATCH", "UNTRACEABLE")},
            "criteria": [
                {"acceptance_id": f"A{index}", "acceptance_judgment": status, "meaning_coverage": coverage}
                for index, coverage in enumerate(coverages, start=1)
            ],
        },
    }


def test_all_pass_match_criteria_are_completion_eligible() -> None:
    assert assess_acceptance_meaning_completion_eligibility(_result(coverages=["MATCH", "MATCH"])) == {
        "completion_eligible": True,
        "blocking_criteria": [],
    }


@pytest.mark.parametrize("coverage", ["PARTIAL", "MISMATCH", "UNTRACEABLE"])
def test_pass_non_match_criterion_blocks_completion_without_changing_acceptance(coverage: str) -> None:
    result = _result(coverages=["MATCH", coverage])
    eligibility = assess_acceptance_meaning_completion_eligibility(result)
    assert result["status"] == "PASS"
    assert eligibility == {
        "completion_eligible": False,
        "blocking_criteria": [
            {"acceptance_id": "A2", "acceptance_judgment": "PASS", "meaning_coverage": coverage, "reason": "meaning_not_completion_eligible"}
        ],
    }


def test_acceptance_fail_is_not_completion_eligible_even_when_meaning_matches() -> None:
    eligibility = assess_acceptance_meaning_completion_eligibility(_result(status="FAIL"))
    assert eligibility["completion_eligible"] is False
    assert eligibility["blocking_criteria"][0]["reason"] == "acceptance_not_pass"


@pytest.mark.parametrize("mutate", [
    lambda result: result.pop("meaning_trace_audit"),
    lambda result: result["meaning_trace_audit"].update({"criteria_count": 2}),
    lambda result: result["meaning_trace_audit"]["criteria"].__setitem__(0, {"acceptance_id": "A9", "acceptance_judgment": "PASS", "meaning_coverage": "MATCH"}),
])
def test_missing_or_malformed_audit_fails_closed(mutate) -> None:
    result = _result()
    mutate(result)
    assert assess_acceptance_meaning_completion_eligibility(result)["completion_eligible"] is False
