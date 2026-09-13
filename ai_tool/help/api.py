"""Agent-facing Help API (H2+H3) wrapping in-repo H1 service.

Read-only: search / describe / handle_h. No tool execution.
Use before selecting a tool (discover -> understand -> select).
"""
from __future__ import annotations

from typing import Any

from ai_tool.help import h1_service

GENERIC_TOOL_SELECTION_RULE = """
Tool selection (generic Help/Discovery rule):
1. Discover: search Help for the needed capability (do not hardcode a tool name).
2. Understand: describe candidate tool_id(s) — schemas, risk, availability, side_effect.
3. Select: choose among Help results that are agent-available; then call that tool.
Do not invent tools. If Help finds no match, report a tool gap — do not guess.
This rule replaces per-tool "must use X" hardcoding wherever Help can resolve the need.
""".strip()

# H4 leftover (not H4-complete): search phrases are not Registry-backed.
_CAPABILITY_QUERIES = {
    "workspace_file_read": "read file",
    "workspace_file_search": "search file",
    "workspace_file_list": "list file",
    "workspace_file_write": "write file",
    "workspace_file_edit": "edit file",
    "workspace_file_create": "create file",
    "registry_read": "registry",
    "command_execution": "command",
    "python_execution": "python",
    "test_execution": "test",
}


def list_tools(*, audit: bool = False) -> dict[str, Any]:
    return h1_service.list_tools(audit=audit)


def search(query: str, *, audit: bool = False) -> dict[str, Any]:
    return h1_service.search(query, audit=audit)


def describe(tool_id: str, *, audit: bool = False) -> dict[str, Any]:
    return h1_service.describe(tool_id, audit=audit)


def handle_h(command: str, *, audit: bool = False) -> dict[str, Any]:
    return h1_service.handle_h(command, audit=audit)


def prefer_tool_for_capability(
    capability: str,
    *,
    fallback: str | None = None,
    audit: bool = False,
) -> str | None:
    """Resolve a tool name via Help search for a capability (generic rule)."""
    cap = (capability or "").strip()
    query = _CAPABILITY_QUERIES.get(cap, cap.replace("_", " "))
    if not query:
        return fallback
    try:
        result = search(query, audit=audit)
    except Exception:
        return fallback
    tools = result.get("tools") or []
    for card in tools:
        if not card.get("agent_available", True):
            continue
        tid = str(card.get("tool_id") or card.get("name") or "").strip()
        if not tid:
            continue
        if ":" in tid:
            tid = tid.split(":", 1)[-1]
        return tid
    return fallback


def format_help_for_chat(result: dict[str, Any]) -> str:
    """Render structured HelpResult as chat assistant text (no tool execution)."""
    lines: list[str] = []
    op = result.get("operation")
    ok = result.get("ok")
    if result.get("usage") and op in {"overview", "help", "invalid"}:
        lines.append(str(result["usage"]).rstrip())
    if result.get("message"):
        lines.append(str(result["message"]))
    if result.get("error"):
        lines.append(f"error: {result['error']}")
    tool = result.get("tool")
    if isinstance(tool, dict):
        lines.append(
            f"tool: {tool.get('tool_id')}  risk={tool.get('risk_level')}  "
            f"availability={tool.get('availability')}  side_effect={tool.get('side_effect')}"
        )
        if tool.get("name"):
            lines.append(f"  name: {tool.get('name')}")
        if tool.get("description"):
            lines.append(f"  desc: {tool.get('description')}")
        caps = tool.get("capabilities") or []
        if caps:
            lines.append(f"  capabilities: {', '.join(str(c) for c in caps)}")
        schema = tool.get("input_schema") or {}
        if schema:
            props = schema.get("properties") if isinstance(schema, dict) else None
            if isinstance(props, dict) and props:
                lines.append(f"  inputs: {', '.join(props.keys())}")
    tools = result.get("tools") or []
    if tools and op in {"list", "search", "overview"}:
        lines.append(f"tools ({result.get('count') or len(tools)}):")
        for card in tools[:40]:
            tid = card.get("tool_id") or card.get("name")
            desc = (card.get("description") or "")[:72]
            lines.append(f"- {tid}: {desc}")
        if len(tools) > 40:
            lines.append(f"... and {len(tools) - 40} more")
    if not lines:
        lines.append(f"HelpResult ok={ok} operation={op}")
    return "\n".join(lines).rstrip() + "\n"
