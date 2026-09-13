"""Phase 5 Agent integration cases — tool selection / execution / safety."""
from __future__ import annotations

import pytest
from ai_tool.agent_integration.production_bridge import append_experimental_agent_tools
from ai_tool.agent_integration.trial import make_mock_chat_fn, run_trial_scenario
from ai_tool.agent_integration.trial_scenarios import URL_FETCH_SCENARIO, WEB_SEARCH_SCENARIO


@pytest.fixture
def agent_tools_with_experimental():
    base = [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Web search",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
    ]
    return append_experimental_agent_tools(base)


def test_case1_url_fetch(agent_tools_with_experimental) -> None:
    result = run_trial_scenario(
        URL_FETCH_SCENARIO,
        tools=agent_tools_with_experimental,
        chat_fn=make_mock_chat_fn(URL_FETCH_SCENARIO),
    )
    assert result.routing_match is True
    assert result.executions[0].selection.tool_name == "read_url_text"
    assert result.executions[0].ok is True
    assert any(m.get("role") == "tool" for m in result.messages)


def test_case2_web_search(agent_tools_with_experimental) -> None:
    result = run_trial_scenario(
        WEB_SEARCH_SCENARIO,
        tools=agent_tools_with_experimental,
        chat_fn=make_mock_chat_fn(WEB_SEARCH_SCENARIO),
    )
    assert result.routing_match is True
    assert result.executions[0].selection.tool_name == "search_web"


def test_case3_url_then_answer(agent_tools_with_experimental) -> None:
    scenario = URL_FETCH_SCENARIO
    result = run_trial_scenario(
        scenario,
        tools=agent_tools_with_experimental,
        chat_fn=make_mock_chat_fn(scenario),
    )
    assert result.final_answer is not None
    tool_content = next(m["content"] for m in result.messages if m.get("role") == "tool")
    assert "Trial fixture" in tool_content or "Hello" in tool_content or "ok" in tool_content


def test_case4_dangerous_url_blocked() -> None:
    from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool

    rec = execute_registry_tool("read_url_text", {"url": "http://localhost/admin"})
    assert rec.ok is False
    assert rec.result.get("ok") is False
    assert rec.result.get("error")


def test_regression_production_tool_names_unchanged() -> None:
    from ai_tool.agent_integration.experimental_exposure import load_registry_tools

    names = sorted(t["name"] for t in load_registry_tools() if t.get("visibility") == "agent")
    assert "search_web" in names
    assert "read_url_text" in names
    assert "read_file" in names
    assert "list_files" in names
    assert "search_files" in names
