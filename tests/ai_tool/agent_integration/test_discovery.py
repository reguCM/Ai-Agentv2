"""Tests for Agent Tool Discovery Adapter (Phase 1 — read-only)."""
from __future__ import annotations

import json

import pytest

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter, discover_tools, get_tool_descriptor
from ai_tool.agent_integration.models import CatalogStatusLayers
from ai_tool.providers.local.provider import LocalToolProvider


@pytest.fixture
def adapter() -> AgentToolDiscoveryAdapter:
    return AgentToolDiscoveryAdapter()


# --- Production ---


def test_production_tools_discovered(adapter: AgentToolDiscoveryAdapter) -> None:
    result = adapter.discover_tools(audit=False)
    ids = {t.tool_id for t in result.tools}
    assert "local:get_gpu_status" in ids
    assert "local:cpu_status" in ids
    assert "local:search_web" in ids


def test_production_agent_available(adapter: AgentToolDiscoveryAdapter) -> None:
    gpu = adapter.get_tool_descriptor("local:get_gpu_status")
    assert gpu is not None
    assert gpu.agent_available is True
    assert gpu.discovery_category == "production"
    assert gpu.availability == "available"
    assert gpu.source == "registry/tools.json"
    assert gpu.registry_visibility == "agent"


def test_production_registry_consistency(adapter: AgentToolDiscoveryAdapter) -> None:
    local = LocalToolProvider()
    reg = local.get_descriptor("local:cpu_status")
    assert reg is not None
    disc = adapter.get_tool_descriptor("local:cpu_status")
    assert disc is not None
    assert disc.name == reg.name
    assert disc.description == reg.description
    assert disc.risk_level == reg.risk_level


# --- Experimental ---


def test_experimental_scoped_read_discovered(adapter: AgentToolDiscoveryAdapter) -> None:
    t = adapter.get_tool_descriptor("local:workspace_read_text_scoped")
    assert t is not None
    assert t.agent_available is False
    assert t.discovery_category == "experimental"
    assert t.unavailability_reason == "experimental_not_integrated"


def test_experimental_read_url_graduated_to_registry(adapter: AgentToolDiscoveryAdapter) -> None:
    t = adapter.get_tool_descriptor("local:read_url_text")
    assert t is not None
    assert t.agent_available is True
    assert t.discovery_category == "production"
    assert t.source == "registry/tools.json"
    assert t.risk_level == "medium"


def test_experimental_scoped_read_still_not_agent(adapter: AgentToolDiscoveryAdapter) -> None:
    t = adapter.get_tool_descriptor("local:workspace_read_text_scoped")
    assert t is not None
    assert t.agent_available is False
    assert t.discovery_category == "experimental"


# --- Unknown ---


def test_unknown_tool_not_fabricated() -> None:
    t = get_tool_descriptor("local:does_not_exist")
    assert t is None


def test_unknown_tool_id_no_crash(adapter: AgentToolDiscoveryAdapter) -> None:
    result = adapter.discover_tools(audit=False)
    assert all(t.tool_id for t in result.tools)


# --- Status preservation ---


def test_status_layers_not_collapsed(adapter: AgentToolDiscoveryAdapter) -> None:
    scoped = adapter.get_tool_descriptor("local:workspace_read_text_scoped")
    assert scoped is not None
    assert isinstance(scoped.catalog_status, CatalogStatusLayers)
    assert scoped.discovery_category == "experimental"
    assert scoped.catalog_status.tool_status != scoped.discovery_category


# --- Determinism ---


def test_deterministic_discovery(adapter: AgentToolDiscoveryAdapter) -> None:
    a = adapter.discover_tools(audit=False)
    b = adapter.discover_tools(audit=False)
    assert [t.to_dict() for t in a.tools] == [t.to_dict() for t in b.tools]


# --- Safety (no execution / no registry write) ---


def test_discovery_does_not_import_experimental_executors(monkeypatch: pytest.MonkeyPatch) -> None:
    import ai_tool.experimental.read_url.reader as reader_mod
    import ai_tool.experimental.scoped_read.reader as scoped_mod

    def boom(*a, **k):
        raise AssertionError("experimental tool must not be executed during discovery")

    monkeypatch.setattr(reader_mod, "read_url_text", boom)
    monkeypatch.setattr(scoped_mod, "workspace_read_text_scoped", boom)
    result = discover_tools(audit=False)
    assert len(result.tools) > 0


def test_pipeline_tools_not_agent_available(adapter: AgentToolDiscoveryAdapter) -> None:
    reg = adapter.get_tool_descriptor("local:create_tool_proposal")
    assert reg is not None
    assert reg.agent_available is False
    assert reg.discovery_category in ("not_ready", "unavailable")


# --- Comparison table ---


def test_comparison_table_representatives(adapter: AgentToolDiscoveryAdapter) -> None:
    rows = adapter.comparison_table()
    assert len(rows) == 5
    by_id = {r["tool_id"]: r for r in rows}
    assert by_id["local:get_gpu_status"]["agent_available"] is True
    assert by_id["local:get_gpu_status"]["discovery_category"] == "production"
    assert by_id["local:workspace_read_text_scoped"]["agent_available"] is False
    assert by_id["local:workspace_read_text_scoped"]["discovery_category"] == "experimental"
    assert by_id["local:read_url_text"]["agent_available"] is True
    assert by_id["local:read_url_text"]["discovery_category"] == "production"


def test_mcp_manual_catalog_experimental(adapter: AgentToolDiscoveryAdapter) -> None:
    mcp = adapter.get_tool_descriptor("mcp:get_current_time")
    assert mcp is not None
    assert mcp.agent_available is False
    assert mcp.discovery_category == "experimental"
    assert mcp.provider == "mcp"
