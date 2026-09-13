"""Tests for Web Research Benchmark harness."""
from __future__ import annotations

from ai_tool.web_research_benchmark import (
    load_benchmark_cases,
    probe_external_targets,
    run_self_tool_layer,
    run_web_research_benchmark,
)


def test_dataset_size():
    cases = load_benchmark_cases()
    assert 12 <= len(cases) <= 20


def test_categories_present():
    cases = load_benchmark_cases()
    cats = {c.category for c in cases}
    for prefix in ("B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08"):
        assert prefix in cats


def test_fixture_tool_layer_pass():
    case = next(c for c in load_benchmark_cases() if c.case_id == "WRB-F01")
    row = run_self_tool_layer(case)
    assert row["tool_layer_pass"] is True
    assert row["layer_failure"] == "NONE"


def test_external_probe_structure():
    probe = probe_external_targets()
    assert "tavily" in probe["targets"]
    assert probe["comparison_mode"]


def test_run_benchmark_smoke():
    result = run_web_research_benchmark(fetch_live=False, include_live_cases=False)
    assert result["production_changes"] == []
    assert result["golden_baseline"]["pass_count"] >= 2
    agg = result["self_benchmark"]["aggregate"]
    assert agg["cases"] >= 8
    assert result["benchmark_result"] in ("RESULT_A", "RESULT_B", "RESULT_C", "RESULT_D", "RESULT_E")
