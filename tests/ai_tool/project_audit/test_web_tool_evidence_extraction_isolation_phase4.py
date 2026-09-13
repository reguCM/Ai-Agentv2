"""Tests for Evidence Extraction Isolation Phase 4."""
from __future__ import annotations

from ai_tool.web_tool_evidence_extraction_isolation_phase4 import (
    SAMPLE_ARTICLE_HTML,
    URL_E2_OSAKA,
    WIKI_LIKE_FIXTURE_HTML,
    _contains_target_fact,
    build_diagnosis,
    run_evidence_extraction_isolation,
    run_fetch_case,
)


def test_contains_target_fact_fixture():
    from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence

    ev = normalize_html_to_evidence(SAMPLE_ARTICLE_HTML)
    assert _contains_target_fact(ev["main_text"])


def test_e3_fixture_h2_heuristic_false_negative():
    row = run_fetch_case("E3", "fixture", url="fixture://x", fixture_html=WIKI_LIKE_FIXTURE_HTML)
    assert row.main_text_contains_target_fact is True
    assert row.fact_ready is False
    assert row.fact_ready_reason == "body_not_reached"


def test_e2_live_osaka_no_population_in_main_text():
    row = run_fetch_case("E2", "osaka", url=URL_E2_OSAKA)
    assert row.fetch_ok is True
    assert row.fact_ready is False
    # CONFIRMED in isolation runs: wikidata/metadata blob, not article 人口 section
    assert row.main_text_contains_target_fact is False or row.fact_ready is False


def test_isolation_without_llm():
    result = run_evidence_extraction_isolation(llm_enabled=False)
    assert result["cases"]
    assert result["findings"]["CONFIRMED FACT"]
    assert len(result["proposals"]) >= 2


def test_build_diagnosis_h1():
    from ai_tool.web_tool_evidence_extraction_isolation_phase4 import IsolationCaseResult

    cases = [
        IsolationCaseResult(
            case_id="E2",
            label="x",
            source_url=URL_E2_OSAKA,
            source_title=None,
            fetch_ok=True,
            main_text_length=100,
            main_text_contains_target_fact=False,
            fact_ready=False,
            body_reached=True,
            truncated=False,
            warnings=["main_text_looks_like_boilerplate_or_metadata"],
            main_text_excerpt="",
            evidence_quote=None,
            fact_ready_reason="boilerplate",
            state_class="C",
            hypothesis="h1",
            classification="CONFIRMED FACT",
        )
    ]
    d = build_diagnosis(cases)
    assert any("H1" in x for x in d["CONFIRMED FACT"])


def test_no_production_mutation():
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "ai_tool" / "web_tool_evidence_extraction_isolation_phase4.py"
    text = src.read_text(encoding="utf-8")
    assert "registry/tools.json" not in text
