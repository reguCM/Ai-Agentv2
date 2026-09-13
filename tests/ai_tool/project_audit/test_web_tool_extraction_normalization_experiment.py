"""Tests for extraction normalization experiment harness."""
from __future__ import annotations

from ai_tool.web_tool_extraction_normalization_experiment import (
    GT3_NAV_FIXTURE,
    GT6_SIMPLE_HTML,
    URL_GT1_OSAKA,
    evaluate_golden_case,
    golden_case_specs,
    run_extraction_normalization_experiment,
    score_strategies,
)
from ai_tool.web_tool_extraction_normalization_experiment import GoldenCaseSpec


def test_golden_specs_include_gt1_gt3():
    specs = golden_case_specs()
    ids = {s.case_id for s in specs}
    assert {"GT1", "GT2", "GT3"}.issubset(ids)


def test_gt3_fixture_no_false_evidence():
    spec = next(s for s in golden_case_specs() if s.case_id == "GT3")
    rows = evaluate_golden_case(spec, html=GT3_NAV_FIXTURE, fetch_meta={"fixture": True})
    for row in rows:
        assert row.evidence_presence.get("population") is False


def test_gt6_simple_html_passes_s0():
    spec = GoldenCaseSpec(
        case_id="GT6T",
        label="test",
        url="fixture://x",
        fixture_html=GT6_SIMPLE_HTML,
        expect="population",
        pass_criteria={"require_population": True},
    )
    rows = evaluate_golden_case(spec, html=GT6_SIMPLE_HTML, fetch_meta={"fixture": True})
    prod = next(r for r in rows if r.strategy_id == "S0_PRODUCTION")
    assert prod.mechanical_grade == "PASS"


def test_run_offline_structure():
    result = run_extraction_normalization_experiment(fetch_live=False, llm_enabled=False)
    assert result["stop"] is True
    assert result["production_changes"] is False
    assert result["fact_ready_semantics"]["changed"] is False


def test_score_strategies_structure():
    from ai_tool.web_tool_extraction_normalization_experiment import StrategyGoldenResult

    rows = [
        StrategyGoldenResult(
            case_id="GT1",
            strategy_id="S3_METADATA_STRIP",
            mechanical_grade="PASS",
            extraction_status="SUCCESS",
            evidence_presence={"population": True},
            fact_ready=True,
            fact_ready_reason="x",
            warnings=[],
            removed_regions=[],
            main_text_length=100,
            main_text_excerpt="",
            diagnosis={},
            trace=[],
        )
    ]
    s = score_strategies(rows)
    assert "per_strategy" in s


def test_osaka_url_constant():
    assert "大阪" in URL_GT1_OSAKA or "Osaka" in URL_GT1_OSAKA or "%E5%A4%A7" in URL_GT1_OSAKA


def test_no_production_mutation_in_prototype():
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "ai_tool" / "experimental" / "read_url" / "extraction_prototype.py"
    text = src.read_text(encoding="utf-8")
    assert "NOT Production" in text
    assert "normalize_html_to_evidence" in text
