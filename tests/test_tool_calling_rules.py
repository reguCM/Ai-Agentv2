"""Tool Calling 規約（P1-2）の最小検証テスト。"""

from __future__ import annotations

import json

import pytest

from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from tools.system.tool_contract import (
    ToolNotFoundError,
    build_agent_ollama_tools,
    canonical_tool_name,
    get_registry_tool,
    is_agent_visible,
    list_agent_visible_tools,
    list_registry_tools,
    load_tool_registry,
    registry_entry_to_ollama_tool,
    tool_calling_capability_summary,
    validate_agent_visible_registry,
    validate_registry_entry,
)


def test_canonical_tool_name_accepts_registry_and_provider_schema() -> None:
    assert canonical_tool_name({"name": "sample"}) == "sample"
    assert canonical_tool_name({"function": {"name": "sample"}}) == "sample"


# --- Test 1: Registry 読込 ---


def test_registry_loads() -> None:
    registry = load_tool_registry()
    assert isinstance(registry.get("tools"), list)
    assert len(registry["tools"]) >= 20


def test_list_registry_tools_has_required_fields() -> None:
    for entry in list_registry_tools():
        assert entry.get("name")
        assert entry.get("module")
        assert entry.get("function")
        assert entry.get("description")


# --- Test 2: Schema → Ollama ---


def test_ollama_schema_for_read_url_text() -> None:
    entry = get_registry_tool("read_url_text")
    ollama = registry_entry_to_ollama_tool(entry)
    fn = ollama["function"]
    assert fn["name"] == "read_url_text"
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "url" in params["properties"]
    assert "url" in params["required"]


def test_build_agent_ollama_tools_matches_visibility_filter() -> None:
    visible_names = {t["name"] for t in list_agent_visible_tools()}
    ollama_names = {t["function"]["name"] for t in build_agent_ollama_tools()}
    assert ollama_names == visible_names
    assert "get_gpu_status" in ollama_names
    assert "create_tool_proposal" not in ollama_names


# --- Test 3: 代表 Tool 実行 ---


def test_representative_tools_execute() -> None:
    for tool_name in ("get_gpu_status", "get_cpu_status", "get_gpu_processes"):
        rec = execute_registry_tool(tool_name, {})
        assert rec.ok is True, f"{tool_name} failed: {rec.error}"
        assert isinstance(rec.result, dict)


# --- Test 4: Tool エラーが構造化され LLM 返却可能な形 ---


def test_read_url_text_ssrf_error_structured() -> None:
    rec = execute_registry_tool("read_url_text", {"url": "http://127.0.0.1/secret"})
    assert rec.ok is False
    assert rec.result.get("ok") is False
    assert rec.result.get("error")
    # Agent はこの dict を json.dumps して role=tool へ載せる
    payload = json.dumps(rec.result, ensure_ascii=False)
    assert "error" in payload


# --- Test 5: visibility ---


def test_visibility_agent_only_exposed_to_ollama() -> None:
    proposal = get_registry_tool("create_tool_proposal")
    assert not is_agent_visible(proposal)
    gpu = get_registry_tool("get_gpu_status")
    assert is_agent_visible(gpu)


def test_agent_visible_registry_validation_no_blocking_issues() -> None:
    report = validate_agent_visible_registry()
    assert report["agent_visible_count"] >= 12
    assert report["issue_count"] == 0


# --- Test 6: 代表 Tool 規約整合 ---


@pytest.mark.parametrize(
    "tool_name",
    [
        "get_gpu_status",
        "get_cpu_status",
        "get_gpu_processes",
        "read_url_text",
    ],
)
def test_representative_tools_pass_contract_validation(tool_name: str) -> None:
    entry = get_registry_tool(tool_name)
    issues = validate_registry_entry(entry, strict_new=False)
    assert issues == [], f"{tool_name}: {issues}"


def test_get_registry_tool_missing() -> None:
    with pytest.raises(ToolNotFoundError):
        get_registry_tool("nonexistent_tool_xyz")


def test_tool_calling_summary() -> None:
    summary = tool_calling_capability_summary()
    assert summary["agent_visible_tools"] >= 12
    assert "read_url_text" in summary["agent_tool_names"]
