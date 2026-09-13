"""Agent Help API (H2+H3) — thin wrapper over Help System H1.

Discover -> understand -> select. Never executes tools.
Distinct from HELP Packet (upper-AI escalation).
"""
from ai_tool.help.api import (
    GENERIC_TOOL_SELECTION_RULE,
    describe,
    format_help_for_chat,
    handle_h,
    list_tools,
    prefer_tool_for_capability,
    search,
)

__all__ = [
    "GENERIC_TOOL_SELECTION_RULE",
    "describe",
    "format_help_for_chat",
    "handle_h",
    "list_tools",
    "prefer_tool_for_capability",
    "search",
]
