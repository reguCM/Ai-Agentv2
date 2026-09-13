from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_tool.core.audit import append_audit
from ai_tool.core.models import ToolDescriptor
from ai_tool.core.safety import evaluate_tool_safety
from ai_tool.providers.local.provider import LocalToolProvider
from ai_tool.providers.mcp.provider import MCPToolProvider

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CATALOG_PATH = _REPO_ROOT / "registry" / "ai_tool_catalog.json"


class ToolCatalog:
    """Unified read-only view over local registry + experimental MCP catalog."""

    def __init__(self) -> None:
        self.local = LocalToolProvider()
        self.mcp = MCPToolProvider()

    def load_manual_entries(self) -> list[dict[str, Any]]:
        if not _CATALOG_PATH.is_file():
            return []
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        return list(data.get("tools") or [])

    def list_all_descriptors(self, *, include_mcp_live: bool = True) -> list[ToolDescriptor]:
        items = self.local.list_descriptors()
        for raw in self.load_manual_entries():
            items.append(ToolDescriptor(**raw))
        if include_mcp_live:
            try:
                items.extend(self.mcp.list_descriptors())
            except Exception:
                pass
        return items

    def summarize_for_agent_view(self) -> list[dict[str, Any]]:
        """Shape comparable to Ollama tool listing (metadata only, no execution)."""
        rows = []
        for d in self.list_all_descriptors(include_mcp_live=False):
            rows.append(
                {
                    "id": d.id,
                    "name": d.name,
                    "provider": d.provider,
                    "description": d.description,
                    "risk_level": d.risk_level,
                    "execution_mode": d.execution_mode,
                    "status": d.status,
                    "input_schema": d.input_schema,
                }
            )
        return rows

    def safety_report(self) -> list[dict[str, Any]]:
        report = []
        for d in self.list_all_descriptors(include_mcp_live=False):
            decision = evaluate_tool_safety(d)
            report.append({"tool_id": d.id, **decision.to_dict()})
        return report

    def audit_discovery(self) -> str:
        descriptors = self.list_all_descriptors()
        return append_audit(
            {
                "event": "tool_discovery",
                "count": len(descriptors),
                "providers": sorted({d.provider for d in descriptors}),
                "tool_ids": [d.id for d in descriptors],
            }
        )
