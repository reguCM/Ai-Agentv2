"""Tests for Live E2E validation harness (deterministic mocks)."""
from __future__ import annotations

from pathlib import Path

from ai_tool.agent_integration.trial import TrialScenario, make_mock_chat_fn
from ai_tool.web_tool_status_boundary_live_e2e import run_agent_subprocess, run_live_e2e_validation


def _mock_chat_from_steps(tool_steps: list[dict], final: str):
    scenario = TrialScenario(
        scenario_id="live_e2e_mock",
        user_request="mock",
        expected_tool="search_web",
        routing_note="mock",
        mock_tool_calls=tool_steps,
        mock_final_answer=final,
    )
    return make_mock_chat_fn(scenario)


def test_live_e2e_case_c_fetch_failed_mock():
    chat = _mock_chat_from_steps(
        [
            {"name": "search_web", "arguments": {"query": "Osaka population", "limit": 3}},
            {"name": "read_url_text", "arguments": {"url": "https://example.com/a"}},
        ],
        "Population is 2,750,000 from the page.",
    )
    result = run_live_e2e_validation(
        chat_fn=chat,
        model="mock",
        live=False,
        case_filter="C",
    )
    case = result["cases"][0]
    assert case["observed_overall"] == "FETCH_FAILED"
    assert case["grade"] == "PASS"
    assert case["production_mirror"]["boundary_applied"] is True


def test_live_e2e_case_g_boundary_mock():
    chat = _mock_chat_from_steps(
        [{"name": "search_web", "arguments": {"query": "x", "limit": 5}}],
        "Web検索の結果、人口は約1,900万人です。",
    )
    result = run_live_e2e_validation(
        chat_fn=chat,
        model="mock",
        live=False,
        case_filter="G",
        trust_path=Path(__file__).resolve().parents[3] / "runs" / "ai_tool" / "_test_trust.json",
    )
    case = result["cases"][0]
    mirror = case["production_mirror"]
    assert mirror["boundary_applied"] is True
    assert "1900" not in (mirror.get("final_answer") or "")


def test_eval_harness_has_no_boundary():
    result = run_live_e2e_validation(chat_fn=None, model="", live=False, case_filter="B")
    case = result["cases"][0]
    assert case["eval_harness_only"]["boundary_applied"] is False


def test_subprocess_parser_callable():
    assert callable(run_agent_subprocess)
