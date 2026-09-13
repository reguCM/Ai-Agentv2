"""Tests for Experimental Tool Execution Trial (Phase 4)."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.agent_integration.experimental_exposure import (
    build_trial_ollama_tools,
    load_registry_tools,
)
from ai_tool.agent_integration.trial import (
    execute_trial_tool,
    run_experimental_trial,
    run_trial_scenario,
)
from ai_tool.agent_integration.trial_scenarios import (
    ROUTING_COMPARISON,
    URL_FETCH_SCENARIO,
    WEB_SEARCH_SCENARIO,
)
from ai_tool.catalog.store import catalog_entries_dir


@pytest.fixture
def catalog_sandbox(tmp_path: Path) -> Path:
    dest = tmp_path / "entries"
    shutil.copytree(catalog_entries_dir(), dest)
    return dest


def _registry_sha256() -> str:
    path = Path(__file__).resolve().parents[3] / "registry" / "tools.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _production_ollama_tools_snapshot() -> str:
    registry = {"tools": load_registry_tools()}
    tools = []
    for tool in registry["tools"]:
        if tool.get("visibility") != "agent":
            continue
        properties = {}
        required = []
        for name, parameter in tool.get("input", {}).items():
            param = dict(parameter)
            if param.pop("required", False):
                required.append(name)
            properties[name] = param
        parameters = {"type": "object", "properties": properties}
        if required:
            parameters["required"] = required
        tools.append({"type": "function", "function": {"name": tool["name"], "parameters": parameters}})
    return json.dumps(tools, sort_keys=True)


# --- Exposure ---


def test_trial_exposes_read_url_text_and_search_web(catalog_sandbox: Path) -> None:
    tools = build_trial_ollama_tools(
        experimental_tool_ids=["local:read_url_text"],
        production_tool_names=["search_web"],
        entries_dir=catalog_sandbox,
    )
    names = {t["function"]["name"] for t in tools}
    assert "read_url_text" in names
    assert "search_web" in names
    read_url = next(t for t in tools if t["function"]["name"] == "read_url_text")
    assert read_url["_trial_meta"]["experimental"] is True
    assert read_url["_trial_meta"]["tool_id"] == "local:read_url_text"


def test_production_discovery_registry_read_url_available(catalog_sandbox: Path) -> None:
    adapter = AgentToolDiscoveryAdapter(catalog_entries_dir=catalog_sandbox)
    tool = adapter.get_tool_descriptor("local:read_url_text")
    assert tool is not None
    assert tool.agent_available is True
    assert tool.discovery_category == "production"


# --- Routing scenarios ---


def test_url_scenario_selects_read_url_text(catalog_sandbox: Path) -> None:
    tools = build_trial_ollama_tools(
        experimental_tool_ids=["local:read_url_text"],
        production_tool_names=["search_web"],
        entries_dir=catalog_sandbox,
    )
    result = run_trial_scenario(URL_FETCH_SCENARIO, tools=tools, catalog_entries_dir=catalog_sandbox)
    assert result.routing_match is True
    assert result.selected_tools[0].tool_name == "read_url_text"
    assert result.executions[0].ok is True
    assert result.executions[0].result["ok"] is True
    assert "Trial fixture body" in result.executions[0].result["content"]


def test_search_scenario_selects_search_web(catalog_sandbox: Path) -> None:
    tools = build_trial_ollama_tools(
        experimental_tool_ids=["local:read_url_text"],
        production_tool_names=["search_web"],
        entries_dir=catalog_sandbox,
    )
    result = run_trial_scenario(WEB_SEARCH_SCENARIO, tools=tools, catalog_entries_dir=catalog_sandbox)
    assert result.routing_match is True
    assert result.selected_tools[0].tool_name == "search_web"
    assert result.executions[0].ok is True
    assert len(result.executions[0].result["hits"]) >= 1


def test_result_used_in_follow_up_message(catalog_sandbox: Path) -> None:
    tools = build_trial_ollama_tools(
        experimental_tool_ids=["local:read_url_text"],
        production_tool_names=["search_web"],
        entries_dir=catalog_sandbox,
    )
    result = run_trial_scenario(URL_FETCH_SCENARIO, tools=tools, catalog_entries_dir=catalog_sandbox)
    tool_msgs = [m for m in result.messages if m.get("role") == "tool"]
    assert len(tool_msgs) >= 1
    assert "Trial fixture body" in tool_msgs[0]["content"]
    assert result.final_answer is not None


# --- Safety ---


def test_registry_unchanged_after_trial(catalog_sandbox: Path) -> None:
    before = _registry_sha256()
    run_experimental_trial(catalog_entries_dir=catalog_sandbox, audit=False)
    after = _registry_sha256()
    assert before == after


def test_production_ollama_schema_unchanged(catalog_sandbox: Path) -> None:
    before = _production_ollama_tools_snapshot()
    run_experimental_trial(catalog_entries_dir=catalog_sandbox, audit=False)
    after = _production_ollama_tools_snapshot()
    assert before == after


def test_trial_execution_count_nonzero(catalog_sandbox: Path) -> None:
    result = run_experimental_trial(catalog_entries_dir=catalog_sandbox, audit=False)
    assert result.execution_count >= 2
    assert result.ok is True


def test_routing_comparison_documented() -> None:
    assert "search_web" in ROUTING_COMPARISON
    assert "read_url_text" in ROUTING_COMPARISON
    assert ROUTING_COMPARISON["search_web"]["not_for"] != ROUTING_COMPARISON["read_url_text"]["not_for"]


def test_execute_unknown_tool_fails(catalog_sandbox: Path) -> None:
    from ai_tool.agent_integration.trial import _catalog_index

    record = execute_trial_tool(
        "nonexistent_tool",
        {},
        catalog_by_name=_catalog_index(catalog_sandbox),
    )
    assert record.ok is False
    assert "unknown" in (record.error or "")
