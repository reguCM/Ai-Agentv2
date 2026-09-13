"""Production Agent bridge for experimental catalog tools (Phase 5).

Exposes selected experimental tools to the live Agent LLM schema and execute_tool
path WITHOUT registering them in registry/tools.json.

read_url_text は registry/tools.json（visibility=agent）へ移行済み。
正規経路は Registry → create_ollama_tools() → execute_tool()。
overlay は _EXPERIMENTAL_AGENT_TOOL_IDS が空のとき no-op。
"""
from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ai_tool.agent_integration.sources import load_experimental_entries

AskConfirmFn = Callable[[str, dict[str, Any]], bool | None]
LogToolCallFn = Callable[..., None]
LogToolResultFn = Callable[..., None]
AuthorizeFn = Callable[..., dict[str, Any]]
BlockedResultFn = Callable[..., dict[str, Any]]

# Catalog tool_ids enabled for production Agent overlay (NOT registry registration).
# read_url_text graduated to registry/tools.json — keep empty to avoid double exposure.
_EXPERIMENTAL_AGENT_TOOL_IDS = frozenset()


def experimental_read_url_enabled() -> bool:
    raw = str(os.environ.get("AI_AGENT_DISABLE_EXPERIMENTAL_READ_URL") or "").strip().lower()
    return raw not in ("1", "true", "yes")


def enabled_experimental_tool_ids() -> list[str]:
    if not experimental_read_url_enabled():
        return []
    return sorted(_EXPERIMENTAL_AGENT_TOOL_IDS)


def _catalog_entries_by_name(entries_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for entry in load_experimental_entries(entries_dir=entries_dir):
        tool_id = str(entry.get("tool_id") or "")
        if tool_id not in _EXPERIMENTAL_AGENT_TOOL_IDS:
            continue
        if not experimental_read_url_enabled():
            continue
        name = str(entry.get("name") or "")
        if name:
            by_name[name] = entry
    return by_name


def is_experimental_agent_tool(tool_name: str, *, entries_dir: Path | None = None) -> bool:
    return tool_name in _catalog_entries_by_name(entries_dir)


def get_experimental_agent_tool(tool_name: str, *, entries_dir: Path | None = None) -> dict[str, Any] | None:
    return _catalog_entries_by_name(entries_dir).get(tool_name)


def catalog_entry_to_ollama_tool(entry: dict[str, Any]) -> dict[str, Any]:
    schema = dict(entry.get("input_schema") or {})
    description = str(entry.get("description") or "")
    routing = (
        " [EXPERIMENTAL — 既知URLの本文をHTTP GETで取得。"
        " URLが分からない探索は search_web を使う。Registry未登録。]"
    )
    if "search_web" not in description:
        description = description + routing
    return {
        "type": "function",
        "function": {
            "name": str(entry.get("name") or ""),
            "description": description,
            "parameters": schema,
        },
        "_agent_meta": {
            "tool_id": str(entry.get("tool_id") or ""),
            "source": "ai_tool/catalog/entries",
            "experimental_agent_tool": True,
            "registry_registered": False,
        },
    }


def append_experimental_agent_tools(
    base_tools: list[dict[str, Any]],
    *,
    entries_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Append experimental overlay tools; does not mutate existing registry-derived schemas."""
    overlay: list[dict[str, Any]] = []
    for entry in load_experimental_entries(entries_dir=entries_dir):
        tool_id = str(entry.get("tool_id") or "")
        if tool_id not in enabled_experimental_tool_ids():
            continue
        overlay.append(catalog_entry_to_ollama_tool(entry))
    if not overlay:
        return list(base_tools)
    existing = {t["function"]["name"] for t in base_tools}
    merged = list(base_tools)
    for tool in overlay:
        if tool["function"]["name"] not in existing:
            merged.append(tool)
    merged.sort(key=lambda t: t["function"]["name"])
    return merged


def ollama_tools_for_llm(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip internal metadata before sending to LLM."""
    return [{k: v for k, v in t.items() if not k.startswith("_")} for t in tools]


@dataclass
class ExperimentalAgentExposure:
    enabled: bool
    tool_names: list[str]
    tool_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "tool_names": self.tool_names,
            "tool_ids": self.tool_ids,
            "registry_registered": False,
        }


def get_experimental_agent_exposure(*, entries_dir: Path | None = None) -> ExperimentalAgentExposure:
    by_name = _catalog_entries_by_name(entries_dir)
    return ExperimentalAgentExposure(
        enabled=bool(by_name),
        tool_names=sorted(by_name.keys()),
        tool_ids=sorted(str(v.get("tool_id") or "") for v in by_name.values()),
    )


def normalize_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        if not arguments.strip():
            return {}
        return json.loads(arguments)
    return dict(arguments)


def execute_experimental_agent_tool(
    tool_name: str,
    arguments: Any,
    *,
    authorize: AuthorizeFn,
    blocked_result: BlockedResultFn,
    log_tool_call: LogToolCallFn,
    log_tool_result: LogToolResultFn,
    execution_actor: str,
    ask_tool_confirm: AskConfirmFn | None = None,
    bypass_tool_gate: bool = False,
    entries_dir: Path | None = None,
) -> dict[str, Any] | Any:
    """
    Execute experimental catalog tool through Agent gate.

    Safety: read_url_text SSRF checks run inside experimental reader — not bypassed.
    """
    entry = get_experimental_agent_tool(tool_name, entries_dir=entries_dir)
    if entry is None:
        raise ValueError(
            f"Experimental Agent tool not enabled: {tool_name}. "
            "Registry 登録済み Tool は agent.py execute_tool() 経由を使用してください。"
        )

    args = normalize_arguments(arguments)
    logged_arguments = dict(args)

    auth = authorize(
        tool_name,
        logged_arguments,
        ask_confirm=ask_tool_confirm,
        bypass=bypass_tool_gate,
    )
    if not auth.get("allowed"):
        denied = blocked_result(
            tool_name,
            reason=str(auth.get("decision") or "deny"),
            arguments=logged_arguments,
        )
        log_tool_call(
            execution_actor=execution_actor,
            tool_name=tool_name,
            arguments=logged_arguments,
            extra={"agent_tool_gate": auth, "blocked": True, "experimental_agent_tool": True},
        )
        log_tool_result(
            execution_actor=execution_actor,
            tool_name=tool_name,
            result=denied,
            extra={"agent_tool_gate": auth, "blocked": True, "experimental_agent_tool": True},
        )
        return denied

    ps = dict(entry.get("provider_specific") or {})
    module_name = str(ps.get("implementation_module") or "")
    function_name = str(ps.get("implementation_function") or "")

    log_tool_call(
        execution_actor=execution_actor,
        tool_name=tool_name,
        arguments=logged_arguments,
        extra={
            "agent_tool_gate": auth,
            "experimental_agent_tool": True,
            "catalog_tool_id": entry.get("tool_id"),
            "implementation_module": module_name,
        },
    )

    module = importlib.import_module(module_name)
    function = getattr(module, function_name)

    try:
        result = function(**args)
    except Exception as exc:
        log_tool_result(
            execution_actor=execution_actor,
            tool_name=tool_name,
            error=f"{type(exc).__name__}: {exc}",
            extra={"agent_tool_gate": auth, "experimental_agent_tool": True},
        )
        raise

    log_tool_result(
        execution_actor=execution_actor,
        tool_name=tool_name,
        result=result,
        extra={"agent_tool_gate": auth, "experimental_agent_tool": True},
    )
    return result


def discovery_experimental_agent_available(tool_id: str) -> bool:
    """Whether tool is exposed via production Agent overlay (distinct from registry agent_available)."""
    return tool_id in enabled_experimental_tool_ids()
