"""Tests for Web Tool End-to-End Evaluation Phase 3 harness."""
from __future__ import annotations

import json
from unittest.mock import patch

from ai_tool.web_tool_end_to_end_evaluation_phase3 import (
    detect_user_intent,
    evaluate_e2e_stages,
    run_tool_only_lane,
)
from ai_tool.web_tool_practical_evaluation import EVAL_CASES


def test_detect_user_intent_fetch():
    intent = detect_user_intent("ページの内容を読んで説明してください")
    assert intent.explicit_fetch_intent is True


def test_evaluate_e2e_stages_fetch_skip():
    case = next(c for c in EVAL_CASES if c.case_id == "B")
    intent = detect_user_intent(case.user_request)
    search_obs = {"search_calls": 1, "hit_count": 3, "top_relevance_hint": "medium", "low_relevance_hits": 0}
    fetch_obs = {"fetch_calls": 0, "any_fact_ready": False}
    answer_obs = {"answer_present": True, "hallucination_candidate": False, "html_meta_response": False,
                  "evidence_supported_claims": False, "uncertainty_expressed": False}
    stages = evaluate_e2e_stages(case, intent, search_obs, fetch_obs, answer_obs, lane="live_llm")
    assert stages.fetch == "FAIL"
    assert stages.end_to_end in ("FAIL", "PARTIAL")


def test_tool_only_lane_mocked():
    fake_search = {
        "query": "大阪市の人口",
        "hits": [{"title": "大阪市", "url": "https://ja.wikipedia.org/wiki/Osaka", "relevance_hint": "high", "backend": "wikipedia"}],
        "grounding": {"empty_search": False},
    }
    fake_fetch = {
        "ok": True,
        "url": "https://ja.wikipedia.org/wiki/Osaka",
        "main_text": "population text",
        "quality": {"fact_ready": False, "warnings": []},
        "grounding": {"fact_ready": False},
    }

    def exec_side_effect(name, args, **kw):
        from ai_tool.agent_integration.trial import TrialExecutionRecord, TrialToolSelection

        if name == "search_web":
            return TrialExecutionRecord(TrialToolSelection(name, args, "registry", False), fake_search, True, None)
        return TrialExecutionRecord(TrialToolSelection(name, args, "registry", False), fake_fetch, True, None)

    case = next(c for c in EVAL_CASES if c.case_id == "A")
    with patch("ai_tool.web_tool_end_to_end_evaluation_phase3.execute_registry_tool", side_effect=exec_side_effect):
        result = run_tool_only_lane(case)
    assert result["search"]["hit_count"] >= 1
    assert result["search"]["top_title"] == "大阪市"
    assert result["e2e_stages"]["search"] == "PASS"


def test_harness_structure_import():
    from ai_tool import web_tool_end_to_end_evaluation_phase3 as mod

    assert mod.SEARCH_HARDENING_HEAD
    assert len(mod.EVAL_CASES) == 7


def test_no_production_mutation_in_harness():
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "ai_tool" / "web_tool_end_to_end_evaluation_phase3.py"
    text = src.read_text(encoding="utf-8")
    assert "registry/tools.json" not in text
    assert "SYSTEM_PROMPT" not in text
