"""Tests for Phase D — Practical Decision Support."""
from __future__ import annotations

import pytest

from ai_tool.experimental.development_assistance.api_observation import observe_api_in_text
from ai_tool.experimental.development_assistance.decision_factors import (
    compare_candidates_for_decision,
    compute_decision_factors,
)
from ai_tool.experimental.development_assistance.decision_support_harness import (
    phase_d_cases,
    run_decision_support_phase,
)
from ai_tool.experimental.development_assistance.research_state import ResearchState
from ai_tool.experimental.development_assistance.spec_draft import build_spec_draft
from ai_tool.experimental.development_assistance.version_facts import version_facts_from_candidate


def _sample_candidate(**overrides):
    base = {
        "candidate_id": "TCA",
        "name": "Polars",
        "type": "Library",
        "version": "1.0",
        "environment": {"python": "Python 3.10"},
        "license": "MIT",
        "source_category": "Official Documentation",
        "url": "https://example.com/polars",
        "source_title": "Polars docs",
        "unknowns": [],
        "conflicts": [],
        "description": "Polars data frame library",
    }
    base.update(overrides)
    return base


def test_version_fact_provenance():
    vf = version_facts_from_candidate(_sample_candidate())
    assert vf.version == "1.0"
    assert vf.provenance == "officially_documented"
    assert vf.license == "MIT"


def test_decision_factors_with_constraints():
    factors = compute_decision_factors(
        _sample_candidate(environment={"python": "Python 3.12"}),
        user_constraints={"python": "Python 3.12"},
    )
    py = next(f for f in factors if f.factor == "python_compatibility")
    assert py.status == "match"


def test_compare_candidates_not_ranking():
    a = _sample_candidate(candidate_id="TCA", license="MIT")
    b = _sample_candidate(candidate_id="TCB", name="Pandas", license="GPL", unknowns=["cuda"])
    cmp = compare_candidates_for_decision([a, b])
    assert "factors_by_candidate" in cmp
    assert cmp["recommendation_style"] == "material_explanation_not_mechanical_winner"


def test_api_observation_found_not_mechanical():
    obs = observe_api_in_text("movej", "The movej() command moves the robot", source="https://ur.com")
    assert obs.observed_status == "FOUND"
    obs2 = observe_api_in_text("pandas.read_csv", "The movej() command", source="https://ur.com")
    assert obs2.observed_status == "NOT_FOUND"


def test_spec_draft_from_candidate():
    draft = build_spec_draft("UR robot tool", _sample_candidate(description="movej movel URScript"))
    assert draft.tool_name
    assert draft.license == "MIT"
    assert draft.provenance_note


def test_research_state_resume():
    state = ResearchState(requirement="test")
    state.merge_run({
        "queries": ["polars docs"],
        "candidates": [_sample_candidate()],
        "proposal": {"unknown": ["cuda"], "conflicts": []},
    })
    ctx = state.resume_context_for_query("Bについてもう少し調べて")
    assert ctx["prior_queries"]
    assert ctx["known_unknowns"]


def test_phase_d_cases_cover_a_through_h():
    cases = phase_d_cases()
    ids = {c.tds_id for c in cases}
    for letter in "ABCDEFGH":
        assert f"TDS-{letter}" in ids


def test_run_decision_support_phase_offline():
    result = run_decision_support_phase(llm_enabled=False)
    assert result["total"] == 8
    assert result["pass_count"] >= 7
    assert result["version_matrix_evaluation"]["dedicated_matrix_needed"] is False
    assert result["core_discovery"]["c3_implemented"] == 0
