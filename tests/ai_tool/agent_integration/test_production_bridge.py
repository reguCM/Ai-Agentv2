"""Tests for Production Agent experimental bridge (Phase 5+)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.agent_integration.experimental_exposure import load_registry_tools, registry_entry_to_ollama_tool
from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from ai_tool.agent_integration.production_bridge import (
    append_experimental_agent_tools,
    discovery_experimental_agent_available,
    execute_experimental_agent_tool,
    experimental_read_url_enabled,
    get_experimental_agent_exposure,
    is_experimental_agent_tool,
    ollama_tools_for_llm,
)


def _registry_sha256() -> str:
    path = Path(__file__).resolve().parents[3] / "registry" / "tools.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_experimental_read_url_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_AGENT_DISABLE_EXPERIMENTAL_READ_URL", raising=False)
    assert experimental_read_url_enabled() is True


def test_overlay_empty_after_read_url_graduation() -> None:
    exposure = get_experimental_agent_exposure()
    assert exposure.enabled is False
    assert exposure.tool_names == []


def test_overlay_does_not_duplicate_registry_read_url() -> None:
    base = sorted(
        [
            registry_entry_to_ollama_tool(t)
            for t in load_registry_tools()
            if t.get("visibility") == "agent"
        ],
        key=lambda t: t["function"]["name"],
    )
    merged = append_experimental_agent_tools(base)
    names = [t["function"]["name"] for t in merged]
    assert names.count("read_url_text") == 1
    assert "search_web" in names
    read_url = next(t for t in merged if t["function"]["name"] == "read_url_text")
    assert "_agent_meta" not in read_url or not read_url.get("_agent_meta", {}).get("experimental_agent_tool")


def test_production_registry_tools_schema_unchanged_by_overlay() -> None:
    base_tools = sorted(
        [
            registry_entry_to_ollama_tool(t)
            for t in load_registry_tools()
            if t.get("visibility") == "agent"
        ],
        key=lambda t: t["function"]["name"],
    )
    before = json.dumps(
        [{k: v for k, v in t.items() if not k.startswith("_")} for t in base_tools],
        sort_keys=True,
    )
    merged = append_experimental_agent_tools(base_tools)
    prod_only = sorted(
        [t for t in merged if not t.get("_agent_meta", {}).get("experimental_agent_tool")],
        key=lambda t: t["function"]["name"],
    )
    after = json.dumps(
        [{k: v for k, v in t.items() if not k.startswith("_")} for t in prod_only],
        sort_keys=True,
    )
    assert before == after
    assert not any(t.get("_agent_meta", {}).get("experimental_agent_tool") for t in merged)


def test_registry_file_unchanged_by_bridge_helpers() -> None:
    before = _registry_sha256()
    append_experimental_agent_tools([])
    get_experimental_agent_exposure()
    assert _registry_sha256() == before


def test_discovery_agent_available_true_for_registry_read_url() -> None:
    adapter = AgentToolDiscoveryAdapter()
    tool = adapter.get_tool_descriptor("local:read_url_text")
    assert tool is not None
    assert tool.agent_available is True
    assert tool.discovery_category == "production"


def test_experimental_agent_available_overlay_disabled() -> None:
    assert discovery_experimental_agent_available("local:read_url_text") is False
    assert discovery_experimental_agent_available("local:search_web") is False


def test_localhost_blocked_via_registry_execute_path() -> None:
    rec = execute_registry_tool("read_url_text", {"url": "http://127.0.0.1/secret"})
    assert rec.ok is False
    err = str(rec.result.get("error") or "").lower()
    assert "ssrf" in err or "loopback" in err or "127.0.0.1" in err


def test_execute_success_with_mock_fetch_via_registry() -> None:
    def mock_fetch(url, *, timeout_seconds, max_bytes, max_redirects):
        body = b"Hello from trial page"
        return 200, {"content-type": "text/plain"}, body, url

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


def test_experimental_execute_raises_when_overlay_empty() -> None:
    with pytest.raises(ValueError, match="not enabled"):
        execute_experimental_agent_tool(
            "read_url_text",
            {"url": "https://example.com/"},
            authorize=MagicMock(return_value={"allowed": True}),
            blocked_result=MagicMock(),
            log_tool_call=MagicMock(),
            log_tool_result=MagicMock(),
            execution_actor="TEST_AGENT",
        )


def test_ollama_tools_for_llm_strips_meta() -> None:
    tools = append_experimental_agent_tools([])
    llm_tools = ollama_tools_for_llm(tools)
    for t in llm_tools:
        assert "_agent_meta" not in t
        assert "function" in t


def test_is_experimental_agent_tool_false_for_web_tools() -> None:
    assert is_experimental_agent_tool("read_url_text") is False
    assert is_experimental_agent_tool("search_web") is False
