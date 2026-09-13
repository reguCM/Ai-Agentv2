"""Tests for Web Evidence → LLM Context Architecture Investigation."""
from __future__ import annotations

from ai_tool.experimental.evidence_context.packager import (
    EvidenceBundle,
    EvidenceSource,
    build_context,
    compress_context_levels,
    fact_coverage_in_context,
)
from ai_tool.web_evidence_llm_context_investigation import (
    CONTEXT_FORMATS,
    investigation_cases,
    proxy_llm_from_context,
    run_format_comparison,
    run_web_evidence_llm_context_investigation,
)
from ai_tool.web_tool_success_class_accuracy_evaluation import ExpectedFact


def test_investigation_cases_minimum():
    cases = investigation_cases()
    assert len(cases) >= 10
    ids = {c.case_id for c in cases}
    assert "IC-B01" in ids
    assert "IC-F01" in ids


def test_build_context_formats():
    case = investigation_cases()[0]
    for fmt in CONTEXT_FORMATS:
        ctx = build_context(fmt, case)
        assert len(ctx) > 0
        assert case.user_request in ctx or "EVIDENCE" in ctx or "PASSAGES" in ctx or "SOURCES" in ctx


def test_passage_smaller_than_raw():
    case = next(c for c in investigation_cases() if c.case_id == "IC-B10")
    raw = build_context("A1_RAW", case)
    passage = build_context("A2_PASSAGE", case)
    assert len(passage) <= len(raw)


def test_source_grouped_has_metadata():
    case = next(c for c in investigation_cases() if c.case_id == "IC-B09")
    ctx = build_context("A3_SOURCE_GROUPED", case)
    assert "url" in ctx
    assert "excerpt" in ctx


def test_claim_format_includes_claims():
    case = investigation_cases()[0]
    ctx = build_context("A4_CLAIM", case)
    assert "CLAIM_ORIENTED" in ctx
    assert "claims" in ctx


def test_verification_block_on_a5():
    case = investigation_cases()[0]
    ctx = build_context("A5_VERIFY", case)
    assert "VERIFICATION_METADATA" in ctx


def test_compression_ladder_levels():
    case = investigation_cases()[0]
    levels = compress_context_levels(case)
    assert set(levels) == {"full", "passage", "claim", "source_summary"}


def test_fact_coverage_in_context():
    case = investigation_cases()[0]
    ctx = build_context("A1_RAW", case)
    met, total = fact_coverage_in_context(ctx, case.expected_facts)
    assert total == len(case.expected_facts)
    assert met >= 1


def test_proxy_llm_optimistic_correct():
    case = investigation_cases()[0]
    ctx = build_context("A1_RAW", case)
    ans = proxy_llm_from_context(ctx, case, optimistic=True)
    assert len(ans) > 0


def test_conflict_case_dual_sources():
    case = next(c for c in investigation_cases() if c.case_id == "IC-F01")
    assert len(case.sources) == 2
    raw = case.raw_combined
    assert "275" in raw or "2,750" in raw
    assert "752" in raw or "2,752" in raw


def test_format_comparison_rows():
    cases = investigation_cases()
    rows = run_format_comparison(cases)
    assert len(rows) == len(cases) * len(CONTEXT_FORMATS)


def test_investigation_runs():
    result = run_web_evidence_llm_context_investigation(fetch_live_baseline=False)
    assert result["overall"] in ("PASS", "PARTIAL")
    assert result["decision"] in ("STOP", "CONTINUE", "INVESTIGATE", "EXPERIMENTAL", "RECORD")
    assert result["production_changes"] == []
    agg = result["investigation_a_format_comparison"]["aggregate"]
    assert "A1_RAW" in agg
    assert len(result["core_capability_discovery"]) >= 3


def test_evidence_bundle_raw_combined():
    bundle = EvidenceBundle(
        case_id="T01",
        user_request="test",
        query="test",
        sources=[
            EvidenceSource(url="u1", title="t1", main_text="alpha"),
            EvidenceSource(url="u2", title="t2", main_text="beta"),
        ],
        expected_facts=[
            ExpectedFact("f1", "text", [r"alpha"], [r"alpha"]),
        ],
    )
    assert "alpha" in bundle.raw_combined
    assert "beta" in bundle.raw_combined
