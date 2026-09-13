"""Tests for User-Facing Resolution E2E Integration."""
from __future__ import annotations

from ai_tool.experimental.conversation_resolution.e2e_adapter import (
    evidence_sources_from_loop,
    make_canonical_tool_chat,
    make_multi_fixture_read_url_fn,
    run_canonical_evidence_collection,
)
from ai_tool.agent_integration.production_agent_web_loop import AgentWebLoopResult, ToolExecutionRecord
from ai_tool.experimental.evidence_context.packager import EvidenceSource
from ai_tool.web_research_user_facing_resolution_e2e import (
    e2e_cases,
    run_e2e_case,
    run_web_research_user_facing_resolution_e2e,
)
from ai_tool.web_research_user_facing_resolution_proof import make_mock_resolution_chat_fn
from ai_tool.web_tool_web_status_evaluation import GOOD_HTML


def test_evidence_sources_from_loop_multi_fetch():
    loop = AgentWebLoopResult(
        user_request="test",
        path="test",
        tool_executions=[
            ToolExecutionRecord(
                tool_name="read_url_text",
                arguments={"url": "https://fixture/a"},
                result={"ok": True, "url": "https://fixture/a", "main_text": "A text", "quality": {"fact_ready": True}},
            ),
            ToolExecutionRecord(
                tool_name="read_url_text",
                arguments={"url": "https://fixture/b"},
                result={"ok": True, "url": "https://fixture/b", "main_text": "B text", "quality": {"fact_ready": True}},
            ),
        ],
    )
    sources = evidence_sources_from_loop(loop)
    assert len(sources) == 2
    assert sources[0].url == "https://fixture/a"


def test_canonical_evidence_collection_fixture():
    url = "https://fixture.local/osaka"
    loop, meta, sources, fail = run_canonical_evidence_collection(
        "大阪市の人口",
        mock_tool_calls=[{"name": "read_url_text", "arguments": {"url": url}}],
        read_url_text_fn=make_multi_fixture_read_url_fn({url: GOOD_HTML}),
    )
    assert fail is None
    assert meta.production_equivalent is True
    assert len(sources) == 1
    assert loop.tool_executions[0].tool_name == "read_url_text"


def test_e2e_case_single_offline():
    case = next(c for c in e2e_cases(include_live=False) if c.case_id == "E2E-C01")
    r = run_e2e_case(case, llm_enabled=False)
    assert r["pass"] is True
    assert r["production_equivalent"] is True
    assert r["expected_mode"] == "SINGLE"


def test_e2e_case_definition_diff():
    case = next(c for c in e2e_cases(include_live=False) if c.case_id == "E2E-C02")
    r = run_e2e_case(case, llm_enabled=False)
    assert r["pass"] is True
    assert r["resolution"]["state"]["relation"] == "DEFINITION_DIFF"


def test_e2e_case_user_selection():
    case = next(c for c in e2e_cases(include_live=False) if c.case_id == "E2E-C04")
    r = run_e2e_case(case, llm_enabled=False)
    assert r["pass"] is True
    assert r["resolution"]["state"]["selected_candidate_id"] == "CB"


def test_e2e_cases_minimum():
    assert len(e2e_cases(include_live=False)) >= 8


def test_e2e_run_all_offline():
    result = run_web_research_user_facing_resolution_e2e(
        chat_fn=make_mock_resolution_chat_fn(),
        model="mock",
        llm_enabled=False,
        fetch_live_baseline=False,
        include_live=False,
    )
    assert result["production_changes"] == []
    assert result["golden_pass"] is True
    assert int(result["pass_count"].split("/")[0]) >= 7
    assert result["decision"] in ("CONTINUE_INVESTIGATION", "EXPERIMENTAL_RETAIN", "STOP_NO_CHANGE")
