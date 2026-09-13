"""Build Ollama tool schemas for experimental trial exposure (Phase 4)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_tool.agent_integration.sources import load_experimental_entries
from tools.system.tool_contract import (
    list_registry_tools,
    registry_entry_to_ollama_tool as contract_registry_entry_to_ollama_tool,
)


def load_registry_tools() -> list[dict[str, Any]]:
    return list_registry_tools()


def registry_entry_to_ollama_tool(entry: dict[str, Any]) -> dict[str, Any]:
    result = contract_registry_entry_to_ollama_tool(entry)
    result["_trial_meta"] = {
        "tool_id": f"local:{entry['name']}",
        "source": "registry/tools.json",
        "experimental": False,
        "visibility": entry.get("visibility"),
    }
    return result


def catalog_entry_to_ollama_tool(entry: dict[str, Any]) -> dict[str, Any]:
    schema = dict(entry.get("input_schema") or {})
    tool_name = str(entry.get("name") or "")
    description = str(entry.get("description") or "")
    if "[EXPERIMENTAL TRIAL]" not in description:
        description = f"{description} [EXPERIMENTAL TRIAL — isolated run only]"
    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description,
            "parameters": schema,
        },
        "_trial_meta": {
            "tool_id": str(entry.get("tool_id") or ""),
            "source": "ai_tool/catalog/entries",
            "experimental": True,
            "visibility": "experimental_trial",
        },
    }


def build_trial_ollama_tools(
    *,
    experimental_tool_ids: list[str] | None = None,
    production_tool_names: list[str] | None = None,
    entries_dir: Path | None = None,
    include_all_production: bool = False,
) -> list[dict[str, Any]]:
    """Merge production registry tools + experimental catalog tools for trial LLM exposure."""
    wanted_ids = set(experimental_tool_ids or ["local:read_url_text"])
    catalog_by_id = {
        str(e.get("tool_id") or ""): e for e in load_experimental_entries(entries_dir=entries_dir)
    }

    tools: list[dict[str, Any]] = []
    registry = load_registry_tools()

    if include_all_production:
        production_names = {str(t["name"]) for t in registry if t.get("visibility") == "agent"}
    else:
        production_names = set(production_tool_names or ["search_web"])

    for entry in registry:
        name = str(entry.get("name") or "")
        if name not in production_names:
            continue
        if entry.get("visibility") != "agent":
            continue
        tools.append(registry_entry_to_ollama_tool(entry))

    for tool_id in sorted(wanted_ids):
        catalog_entry = catalog_by_id.get(tool_id)
        if catalog_entry is None:
            continue
        tools.append(catalog_entry_to_ollama_tool(catalog_entry))

    tools.sort(key=lambda t: t["function"]["name"])
    return tools


def trial_tool_names(tools: list[dict[str, Any]]) -> list[str]:
    return [t["function"]["name"] for t in tools]
