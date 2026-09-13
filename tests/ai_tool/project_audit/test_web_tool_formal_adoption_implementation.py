"""Web Tool Formal Adoption — Implementation Phase verification."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _registry() -> dict:
    return json.loads((REPO / "registry" / "tools.json").read_text(encoding="utf-8"))


def _agent_visible() -> dict[str, dict]:
    return {t["name"]: t for t in _registry()["tools"] if t.get("visibility") == "agent"}


def _production_tool_names() -> list[str]:
    from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools

    return sorted(t["function"]["name"] for t in build_production_agent_tools())


# --- Registry ---


def test_search_web_registry_agent_visible() -> None:
    entry = _agent_visible()["search_web"]
    assert entry["module"] == "tools.system.network.search_web"
    assert entry["function"] == "search_web"
    assert entry["input"]["query"]["required"] is True


def test_read_url_text_registry_agent_visible() -> None:
    entry = _agent_visible()["read_url_text"]
    assert entry["module"] == "ai_tool.experimental.read_url.reader"
    assert entry["function"] == "read_url_text"
    assert entry["input"]["url"]["required"] is True


def test_observation_tools_unchanged() -> None:
    visible = _agent_visible()
    for name in ("get_gpu_status", "get_gpu_processes", "cpu_status", "get_cpu_status"):
        assert name in visible
        assert visible[name].get("observation_source") == "real" or name == "cpu_status"


def test_registry_json_valid() -> None:
    data = _registry()
    assert isinstance(data["tools"], list)
    names = [t["name"] for t in data["tools"]]
    assert len(names) == len(set(names))


# --- Agent schema ---


def test_production_schema_includes_web_tools() -> None:
    names = _production_tool_names()
    assert "search_web" in names
    assert "read_url_text" in names


def test_no_experimental_overlay_duplicate() -> None:
    from ai_tool.agent_integration.production_bridge import is_experimental_agent_tool

    tools = _production_tool_names()
    assert tools.count("read_url_text") == 1
    assert is_experimental_agent_tool("read_url_text") is False
    assert is_experimental_agent_tool("search_web") is False


def test_prompt_registry_schema_alignment() -> None:
    prompt = (REPO / "agent.py").read_text(encoding="utf-8")
    names = set(_production_tool_names())
    assert "search_web" in prompt
    assert "read_url_text" in prompt
    assert "[EXPERIMENTAL]" not in prompt.split("SYSTEM_PROMPT")[1][:2500]
    assert names >= {"search_web", "read_url_text", "get_gpu_status", "get_cpu_status"}


# --- Discovery lifecycle ---


def test_read_url_discovery_production_not_experimental_overlay() -> None:
    from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter

    adapter = AgentToolDiscoveryAdapter()
    matches = [t for t in adapter.discover_tools(audit=False).tools if t.tool_id == "local:read_url_text"]
    assert len(matches) == 1
    t = matches[0]
    assert t.agent_available is True
    assert t.discovery_category == "production"
    assert t.source == "registry/tools.json"


# --- Security ---


def test_read_url_localhost_blocked_via_registry_path() -> None:
    from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool

    rec = execute_registry_tool("read_url_text", {"url": "http://127.0.0.1/secret"})
    assert rec.ok is False
    err = str(rec.result.get("error") or "").lower()
    assert "ssrf" in err or "loopback" in err or "127.0.0.1" in err


def test_search_web_empty_query_no_fake_hits() -> None:
    from tools.system.network.search_web import search_web

    out = search_web("")
    assert out["hits"] == []
    assert out.get("error")


# --- Search → Fetch deterministic ---


def test_search_only_deterministic() -> None:
    from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools
    from ai_tool.agent_integration.trial import run_trial_scenario
    from ai_tool.agent_integration.trial_scenarios import WEB_SEARCH_SCENARIO

    result = run_trial_scenario(WEB_SEARCH_SCENARIO, tools=build_production_agent_tools())
    assert result.routing_match is True
    assert result.executions[0].selection.tool_name == "search_web"


def test_known_url_fetch_deterministic() -> None:
    from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools
    from ai_tool.agent_integration.trial import run_trial_scenario
    from ai_tool.agent_integration.trial_scenarios import URL_FETCH_SCENARIO

    result = run_trial_scenario(URL_FETCH_SCENARIO, tools=build_production_agent_tools())
    assert result.routing_match is True
    assert result.executions[0].selection.tool_name == "read_url_text"


def test_search_then_fetch_two_rounds() -> None:
    from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools
    from ai_tool.agent_integration.trial import TrialScenario, make_mock_chat_fn, run_trial_scenario

    scenario = TrialScenario(
        scenario_id="search_then_fetch_prod",
        user_request="調べてから公式ページを読んで",
        expected_tool="either",
        routing_note="Discovery then Fetch",
        mock_tool_calls=[
            {"name": "search_web", "arguments": {"query": "example topic", "limit": 3}},
            {"name": "read_url_text", "arguments": {"url": "https://example.com/page"}},
        ],
        mock_final_answer="done",
    )
    result = run_trial_scenario(
        scenario,
        tools=build_production_agent_tools(include_experimental_overlay=True),
        max_rounds=5,
    )
    assert len(result.executions) == 2
    assert result.executions[0].selection.tool_name == "search_web"
    assert result.executions[1].selection.tool_name == "read_url_text"


def test_read_url_success_mock_via_registry() -> None:
    from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool

    def mock_fetch(url, *, timeout_seconds, max_bytes, max_redirects):
        return 200, {"content-type": "text/plain"}, b"Hello from page", url

    import ai_tool.experimental.read_url.reader as reader_mod

    original = reader_mod.read_url_text

    def patched(**kwargs):
        kwargs["fetch_fn"] = mock_fetch
        return original(**kwargs)

    reader_mod.read_url_text = patched
    try:
        rec = execute_registry_tool("read_url_text", {"url": "https://example.com/page"})
        assert rec.ok is True
        assert "Hello" in rec.result["content"]
    finally:
        reader_mod.read_url_text = original


def test_formal_adoption_lifecycle_state() -> None:
    prompt = (REPO / "agent.py").read_text(encoding="utf-8")
    visible = _agent_visible()
    names = _production_tool_names()
    for tool in ("search_web", "read_url_text"):
        assert visible[tool]["visibility"] == "agent"
        assert tool in names
        assert tool in prompt
