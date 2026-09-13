"""Tests for Web Evidence → Live LLM Context Format Shootout."""
from __future__ import annotations

from ai_tool.experimental.evidence_context.packager import (
    build_hybrid_context,
    build_production_raw_context,
)
from ai_tool.web_evidence_live_llm_context_shootout import (
    SHOOTOUT_FORMATS,
    analyze_conflict_answer,
    build_shootout_context,
    make_mock_shootout_chat_fn,
    normalize_response,
    run_web_evidence_live_llm_context_shootout,
)
from ai_tool.web_evidence_llm_context_investigation import investigation_cases


def test_shootout_formats_build():
    case = investigation_cases()[0]
    for fmt in SHOOTOUT_FORMATS:
        ctx = build_shootout_context(fmt, case)
        assert len(ctx) > 0
        assert case.user_request in ctx or "USER_REQUEST" in ctx


def test_production_raw_has_enrichment():
    case = investigation_cases()[0]
    ctx = build_production_raw_context(case)
    assert "grounding" in ctx
    assert "main_text" in ctx
    assert "web_status" in ctx


def test_hybrid_no_verification_block():
    case = investigation_cases()[0]
    ctx = build_hybrid_context(case, include_verification=False)
    assert "VERIFICATION_METADATA" not in ctx
    assert "SOURCE:" in ctx


def test_normalize_strips_whitespace():
    assert normalize_response("  hello   world  ") == "hello world"


def test_conflict_analysis_dual_year():
    ans = "2024年推計275万人、2020年国勢調査2752412人"
    r = analyze_conflict_answer(ans)
    assert r["distinguishes_years"] is True
    assert r["mentions_2024"] is True
    assert r["mentions_2020"] is True


def test_conflict_merge_detection():
    r = analyze_conflict_answer("人口は999万人です")
    assert r["suspected_merge"] is True


def test_mock_shootout_runs_subset():
    cases = [c for c in investigation_cases() if c.case_id in ("IC-B01", "IC-B02")]
    result = run_web_evidence_live_llm_context_shootout(
        chat_fn=make_mock_shootout_chat_fn(),
        model="mock",
        llm_enabled=True,
        fetch_live_baseline=False,
        case_ids=[c.case_id for c in cases],
    )
    assert result["cases_run"] == 2
    assert result["arms_total"] == 8
    assert result["production_changes"] == []
    agg = result["aggregate_by_format"]
    assert agg["A_RAW"]["accuracy"] >= 0.5


def test_shootout_skipped_without_llm():
    result = run_web_evidence_live_llm_context_shootout(
        llm_enabled=False,
        fetch_live_baseline=False,
        case_ids=["IC-B01"],
    )
    assert result["decision_log"]["decision"] == "RECORD"
    rows = result["results"]
    assert all(r["answer_class"] == "SKIPPED" for r in rows)


def test_investigation_cases_cover_categories():
    cases = investigation_cases()
    cats = {c.category for c in cases}
    for needed in ("basic", "entity", "numeric", "temporal", "conflict", "english"):
        assert needed in cats
