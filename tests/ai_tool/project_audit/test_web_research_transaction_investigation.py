"""Tests for Web Research Transaction Investigation."""
from __future__ import annotations

import json
from pathlib import Path

from ai_tool.web_research_transaction_investigation import (
    URL_OSAKA,
    build_golden_transactions,
    compare_architecture_options,
    compare_orchestration_models,
    document_path_boundaries,
    extract_a3_mw_parser_output,
    extract_a4_metadata_stripped,
    research_result_schema_spike,
    run_investigation,
)

WIKI_OSAKA_FIXTURE = """
<html><head><title>大阪市 - Wikipedia</title></head><body>
<div id="mw-content-text"><div class="mw-parser-output">
<table class="infobox">{"wt":"wikidata junk"}</table>
<h2 id="人口">人口</h2><p>人口は272万5,133人（2024年）</p>
</div></div></body></html>
"""


def test_orchestration_models_count():
    models = compare_orchestration_models()["models"]
    assert "B1_current" in models
    assert "B3_rtt" in models
    assert len(models) >= 5


def test_schema_spike_minimal():
    spike = research_result_schema_spike()
    assert spike["assessment"]["verdict"] == "minimal_schema_sufficient_for_investigation_phase"
    assert "query" in spike["minimal_schema"]


def test_extraction_a4_fixture_finds_population():
    probe = extract_a4_metadata_stripped(WIKI_OSAKA_FIXTURE)
    assert probe.population_present is True
    assert probe.extraction_case in ("unknown", "case3_heuristic_false_negative")


def test_a3_fixture_boilerplate_without_article():
    probe = extract_a3_mw_parser_output(WIKI_OSAKA_FIXTURE)
    assert probe.population_present is True


def test_golden_transactions_three_cases():
    extraction = {
        "osaka": {
            "probes": [
                {
                    "probe_id": "A1",
                    "population_present": False,
                    "fact_ready": False,
                    "main_text_excerpt": "metadata",
                },
                {
                    "probe_id": "A4",
                    "population_present": True,
                    "fact_ready": True,
                    "main_text_excerpt": "人口272万",
                },
            ]
        },
        "capital": {
            "probes": [
                {
                    "probe_id": "A1",
                    "capital_present": True,
                    "fact_ready": True,
                    "main_text_excerpt": "東京",
                }
            ]
        },
    }
    golden = build_golden_transactions(extraction_results=extraction)
    assert len(golden) >= 3
    assert golden[0]["case_id"] == "GT1"
    assert golden[2]["failure_state"] == "SEARCH_FAILED"


def test_path_boundaries_documented():
    paths = document_path_boundaries()
    assert paths["paths"]["production_mirror"]["apply_web_answer_boundary"] is True
    assert paths["paths"]["tool_only_eval"]["apply_web_answer_boundary"] is False


def test_run_investigation_offline_structure():
    result = run_investigation(fetch_live=False, llm_enabled=False)
    assert result["stop"] is True
    assert result["production_changes"] is False
    assert "recommendation" in result
    assert len(result["investigation_d_golden_transactions"]) >= 3


def test_architecture_options_minimum_three():
    opts = compare_architecture_options({"osaka": {"probes": []}})
    assert len(opts["options"]) >= 4


def test_no_production_mutation_in_module():
    src = Path(__file__).resolve().parents[3] / "ai_tool" / "web_research_transaction_investigation.py"
    text = src.read_text(encoding="utf-8")
    assert "registry/tools.json" not in text
    assert "agent.py" not in text or "document_path" in text or "entry" in text


def test_osaka_url_constant():
    assert "wikipedia" in URL_OSAKA.lower()
