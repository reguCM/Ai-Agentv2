"""Tests for Web Tool Failure Analysis Phase 1 harness (offline-safe)."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ai_tool.web_tool_failure_analysis import (
    analyze_html_composition,
    analyze_practical_eval_agent_loop,
    grade_domains,
    load_practical_eval_artifacts,
    virtual_body_extract,
)


SAMPLE_HTML = """
<!DOCTYPE html><html><head><title>Test</title><script>x=1</script></head>
<body><nav>Nav</nav>
<div class="mw-parser-output"><h2 id="人口">人口</h2><p>272万人</p></div>
</body></html>
"""


def test_virtual_body_extract_finds_population():
    out = virtual_body_extract(SAMPLE_HTML)
    assert "272" in out["text"]
    assert "人口" in out["text"]


def test_analyze_html_composition():
    comp = analyze_html_composition(SAMPLE_HTML)
    assert comp["likely_html_not_plain"] is True
    assert comp["mw_parser_output"] is True
    assert comp["population_section_marker"] is True


def test_analyze_practical_eval_agent_loop_h5():
    cases = [
        {
            "case_id": "F",
            "selected_tools": ["search_web"],
            "tool_results": [{"hits": [], "error": "no hits"}],
            "final_answer": "約1,900万人です",
            "tool_call_count": 1,
        }
    ]
    out = analyze_practical_eval_agent_loop(cases)
    assert out["H5_count"] == 1
    assert out["H5_verdict"] == "CONFIRMED"


def test_grade_domains_with_mock_probes():
    from ai_tool.web_tool_failure_analysis import FetchProbeResult, SearchProbeResult

    search = [
        SearchProbeResult(
            query="q",
            label="fact_lookup",
            tool_result={"hits": [{"title": "t"}]},
            per_backend={},
            per_backend_errors={},
            ranked_preview=[],
            hit_count=1,
            empty_snippet_count=1,
            classification={},
        )
    ]
    fetch = [
        FetchProbeResult(
            url="u",
            label="html_heavy_wikipedia",
            fetch_result={"truncated": True},
            composition={},
            virtual_extract={},
            population_signals={},
            h1_comparison={"hypothesis_h1_supported": True},
        )
    ]
    practical = {"found": True}
    agent = {"H4_count": 2, "C4_C5_html_json_meta_responses": 2, "case_rows": []}
    grades = grade_domains(search, fetch, practical, agent)
    assert grades["FETCH_QUALITY"] == "FAIL"
    assert grades["RESULT_UTILIZATION"] == "FAIL"


def test_load_practical_eval_artifacts_structure():
    result = load_practical_eval_artifacts()
    assert "found" in result
    assert "cases" in result
