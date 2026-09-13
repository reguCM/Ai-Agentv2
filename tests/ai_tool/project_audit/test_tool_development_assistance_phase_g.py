"""Tests for Phase G — Real-World Ambiguous Tool Development Evaluation."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.internal_tool_candidates import (
    generate_internal_candidates,
    select_primary_candidate,
)
from ai_tool.experimental.development_assistance.phase_g_harness import (
    AMBIGUOUS_REQUIREMENT,
    phase_g_cases,
    run_phase_g,
    run_phase_g_case,
)


def test_internal_candidates_no_human_tool_name():
    cands = generate_internal_candidates(AMBIGUOUS_REQUIREMENT)
    assert len(cands) >= 3
    assert all(c.tool for c in cands)
    assert all(c.why_llm_insufficient for c in cands)


def test_primary_selection_high_gap_for_ambiguous():
    cands = generate_internal_candidates(AMBIGUOUS_REQUIREMENT)
    selected, reason, factors = select_primary_candidate(cands, AMBIGUOUS_REQUIREMENT)
    assert selected.llm_knowledge_gap == "HIGH"
    assert "Robot" in selected.tool or "GPU" in selected.tool
    assert reason
    assert factors


def test_primary_selection_low_gap_for_simple():
    req = "単純なJSONファイルを読み込むToolを1つ考えてください"
    cands = generate_internal_candidates(req)
    selected, _, _ = select_primary_candidate(cands, req)
    assert selected.llm_knowledge_gap == "LOW"


def test_phase_g_cases_include_primary_and_comparisons():
    cases = phase_g_cases()
    assert any(c.case_id == "TG-1" for c in cases)
    assert len(cases) >= 4


def test_run_phase_g_primary_offline():
    spec = next(c for c in phase_g_cases() if c.case_id == "TG-1")
    result = run_phase_g_case(spec, llm_enabled=False)
    assert result["pass"]
    assert result["tool_specification"]
    assert result["implementation_feasibility"]["decision"] in (
        "BUILD_NOW", "BUILD_AFTER_RESEARCH", "EXPERIMENTAL_FIRST", "NOT_RECOMMENDED"
    )
    assert result["selected_tool"]["llm_knowledge_gap"] == "HIGH"


def test_run_phase_g_full_offline():
    result = run_phase_g(llm_enabled=False)
    assert result["total"] >= 4
    assert result["pass_count"] >= 4
    assert result["production_changes"] == 0
    assert result["core_discovery"]["c3_implemented"] == 0
    assert result["decision"] == "TDA_PRACTICAL_ENTRY_REACHED"
