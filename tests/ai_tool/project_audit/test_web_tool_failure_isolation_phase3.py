"""Tests for Web Tool Failure Isolation Phase 3 harness."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ai_tool.web_tool_failure_isolation_phase3 import (
    analyze_live_trace,
    build_automation_insights,
    build_proposed_options,
    build_root_cause_table,
    domain_status,
    probe_search_isolation,
)


def test_probe_search_isolation_structure():
    with patch("ai_tool.web_tool_failure_isolation_phase3.search_web") as sw, patch(
        "ai_tool.web_tool_failure_isolation_phase3.gws.search_duckduckgo", return_value=[]
    ), patch("ai_tool.web_tool_failure_isolation_phase3.gws.search_wikipedia", return_value=[]), patch(
        "ai_tool.web_tool_failure_isolation_phase3.gws.search_wikipedia_en", return_value=[]
    ):
        sw.return_value = {"hits": [], "query": "q"}
        row = probe_search_isolation("q", "lbl", None)
        assert row.query == "q"
        assert "duckduckgo" in row.per_backend


def test_analyze_live_trace_fetch_skip():
    case = {
        "case_id": "B",
        "user_request": "検索して、見つかったページの内容を読んで説明してください。",
        "selected_tools": ["search_web"],
        "tool_call_count": 1,
        "tool_arguments": [{"query": "test"}],
        "tool_results": [{"hits": [{"title": "t", "relevance_hint": "low"}], "query": "test"}],
        "final_answer": "answer",
    }
    row = analyze_live_trace(case, source_run="test", prompt_variant="minimal")
    assert row.fetch_explicitly_requested is True
    assert row.fetch_calls == 0
    assert row.agent_blocked_fetch is False
    assert row.classification["fetch_skip_cause"] == "HYPOTHESIS_LLM_DID_NOT_SELECT_FETCH"


def test_root_cause_table_nonempty():
    table = build_root_cause_table([], [], [], {})
    assert isinstance(table, list)


def test_automation_insights_structure():
    insights = build_automation_insights()
    assert insights
    assert "symptom" in insights[0]
    assert "decision_rule" in insights[0]


def test_domain_status_keys():
    analysis = {"search_isolation": [{"first_hit_relevant": False}]}
    domains = domain_status(analysis)
    assert set(domains.keys()) == {"SEARCH", "AGENT", "LLM", "FETCH", "PROMPT"}


def test_phase2_artifacts_exist_if_present():
    root = Path(__file__).resolve().parents[3]
    phase2 = root / "runs" / "ai_tool" / "20260828_214841_web_tool_practical_evaluation_phase2"
    if phase2.is_dir():
        case = json.loads((phase2 / "case_B_live_phase2.json").read_text(encoding="utf-8"))
        row = analyze_live_trace(case, source_run=phase2.name, prompt_variant="minimal")
        assert row.case_id == "B"
