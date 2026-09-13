from __future__ import annotations

from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools
from ai_tool.chat_interface.agent_turn import (
    AGENT_VISIBLE_DEFAULT,
    agent_visible_capabilities,
)
from ai_tool.chat_interface.server import _capabilities


def test_capabilities_match_registry_and_actual_agent_exposure() -> None:
    registry_names = sorted(
        str(item["name"])
        for item in load_registry_tools()
        if item.get("visibility") == "agent"
    )
    ui = _capabilities()
    actual_names = sorted(
        item["function"]["name"]
        for item in build_production_agent_tools(include_experimental_overlay=False)
    )
    assert ui["tools"] == registry_names
    assert actual_names == registry_names
    assert len(ui["tool_details"]) == len(registry_names)
    assert {"read_file", "list_files", "search_files"} <= set(ui["tools"])


def test_non_agent_visibility_is_not_exposed() -> None:
    details = agent_visible_capabilities(
        [
            {"name": "visible", "visibility": "agent", "description": "shown"},
            {"name": "pipeline_only", "visibility": "pipeline"},
        ]
    )
    assert [item["name"] for item in details] == ["visible"]


def test_registry_addition_needs_no_ui_fixed_list_change(monkeypatch) -> None:
    fixture = [
        {"name": "future_tool", "visibility": "agent", "description": "future"}
    ]
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.load_registry_tools", lambda: fixture
    )
    assert _capabilities()["tools"] == ["future_tool"]


def test_display_sync_does_not_expand_security_bootstrap_allowlist() -> None:
    assert "read_file" not in AGENT_VISIBLE_DEFAULT
    assert "future_tool" not in AGENT_VISIBLE_DEFAULT
