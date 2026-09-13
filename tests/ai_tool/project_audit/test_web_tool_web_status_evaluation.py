"""Evaluation harness tests for Web Status Phase."""
from __future__ import annotations

from ai_tool.web_tool_web_status_evaluation import (
    CASE_RUNNERS,
    run_web_status_evaluation,
)


def test_all_cases_run():
    result = run_web_status_evaluation()
    assert len(result["cases"]) == 7


def test_case_1_success():
    c = CASE_RUNNERS["C1"]()
    assert c.match is True
    assert c.observed_overall == "SUCCESS"


def test_case_2_search_failed():
    c = CASE_RUNNERS["C2"]()
    assert c.observed_overall == "SEARCH_FAILED"
    assert c.boundary_applied is True


def test_case_7_hallucination_resistance():
    c = CASE_RUNNERS["C7"]()
    assert c.match is True
    assert c.boundary_applied is True


def test_evaluation_summary():
    result = run_web_status_evaluation()
    assert result["summary"]["total"] == 7
    assert result["summary"]["passed"] >= 6
