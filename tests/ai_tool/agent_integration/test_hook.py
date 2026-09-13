"""Tests for Agent Tool Discovery Hook (Phase 2)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.agent_integration.hook import (
    run_agent_discovery_hook,
    safe_run_agent_discovery_hook,
)
from ai_tool.agent_integration.models import CatalogStatusLayers, DiscoveryResult


# --- Production via hook ---


def test_hook_production_tools_agent_available() -> None:
    result = run_agent_discovery_hook(audit=False)
    assert result.ok is True
    assert result.execution_count == 0
    prod = [t for t in result.tools if t.tool_id == "local:get_gpu_status"]
    assert len(prod) == 1
    assert prod[0].agent_available is True
    assert prod[0].discovery_category == "production"


def test_hook_production_count() -> None:
    result = run_agent_discovery_hook(audit=False)
    assert result.agent_available_count >= 6
    assert result.production_count >= 6


# --- Experimental via hook ---


def test_hook_experimental_scoped_read() -> None:
    result = run_agent_discovery_hook(audit=False)
    scoped = next(t for t in result.tools if t.tool_id == "local:workspace_read_text_scoped")
    assert scoped.agent_available is False
    assert scoped.discovery_category == "experimental"
    assert scoped.unavailability_reason == "experimental_not_integrated"


def test_hook_read_url_production() -> None:
    result = run_agent_discovery_hook(audit=False)
    url = next(t for t in result.tools if t.tool_id == "local:read_url_text")
    assert url.agent_available is True
    assert url.discovery_category == "production"


def test_hook_search_web_production() -> None:
    result = run_agent_discovery_hook(audit=False)
    sw = next(t for t in result.tools if t.tool_id == "local:search_web")
    assert sw.agent_available is True
    assert sw.discovery_category == "production"


# --- Unknown ---


def test_hook_unknown_via_adapter() -> None:
    adapter = AgentToolDiscoveryAdapter()
    assert adapter.get_tool_descriptor("local:nonexistent_xyz") is None


# --- Determinism ---


def test_hook_deterministic() -> None:
    a = run_agent_discovery_hook(audit=False).to_dict()
    b = run_agent_discovery_hook(audit=False).to_dict()
    a.pop("audit_id", None)
    b.pop("audit_id", None)
    assert a == b


# --- Safety ---


def test_hook_execution_count_zero() -> None:
    result = run_agent_discovery_hook(audit=False)
    assert result.execution_count == 0
    assert result.discovery_only is True


def test_hook_does_not_execute_experimental(monkeypatch: pytest.MonkeyPatch) -> None:
    import ai_tool.experimental.read_url.reader as r
    import ai_tool.experimental.scoped_read.reader as s

    monkeypatch.setattr(r, "read_url_text", MagicMock(side_effect=AssertionError("no execute")))
    monkeypatch.setattr(s, "workspace_read_text_scoped", MagicMock(side_effect=AssertionError("no execute")))
    result = run_agent_discovery_hook(audit=False)
    assert result.ok is True
    assert len(result.tools) > 0


def test_safe_hook_survives_adapter_failure() -> None:
    broken = MagicMock()
    broken.discover_tools.side_effect = RuntimeError("discovery broke")
    result = safe_run_agent_discovery_hook(adapter=broken)
    assert result.ok is False
    assert result.execution_count == 0
    assert "RuntimeError" in (result.error or "")


# --- Hook record fields ---


def test_hook_record_has_required_fields() -> None:
    result = run_agent_discovery_hook(audit=False)
    row = result.tools[0]
    d = row.to_dict()
    for key in (
        "tool_id",
        "source",
        "provider",
        "discovery_category",
        "agent_available",
        "tool_status",
        "experiment_status",
        "adoption_status",
    ):
        assert key in d
