"""Agent Tool Discovery Adapter — read-only, non-destructive (Phase 1)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_tool.agent_integration.models import (
    AgentDiscoveredTool,
    AgentAvailability,
    CatalogStatusLayers,
    DiscoveryCategory,
    DiscoveryResult,
)
from ai_tool.agent_integration.sources import (
    load_experimental_entries,
    load_manual_mcp_entries,
    repo_root,
)
from ai_tool.core.audit import append_audit
from ai_tool.providers.local.provider import LocalToolProvider

_REGISTRY_SOURCE = "registry/tools.json"
_CATALOG_ENTRIES_SOURCE = "ai_tool/catalog/entries"
_MANUAL_CATALOG_SOURCE = "registry/ai_tool_catalog.json"


def _catalog_layers_from_entry(entry: dict[str, Any]) -> CatalogStatusLayers:
    return CatalogStatusLayers(
        tool_status=str(entry.get("tool_status") or "unknown"),
        experiment_status=str(entry.get("experiment_status") or "unknown"),
        adoption_status=str(entry.get("adoption_status") or "unknown"),
    )


def _from_registry_entry(descriptor: Any) -> AgentDiscoveredTool:
    visibility = getattr(descriptor, "visibility", None) or "unknown"
    agent_available = visibility == "agent"

    if agent_available:
        category: DiscoveryCategory = "production"
        availability: AgentAvailability = "available"
        reason = None
        layers = CatalogStatusLayers(
            tool_status="available",
            experiment_status="tested",
            adoption_status="approved",
        )
        derivation = "derived_from_registry_visibility_agent"
    elif visibility == "pipeline":
        category = "not_ready"
        availability = "not_available"
        reason = "pipeline_not_agent_visible"
        layers = CatalogStatusLayers(
            tool_status="available",
            experiment_status="tested",
            adoption_status="approved",
        )
        derivation = "derived_from_registry_visibility_pipeline"
    else:
        category = "unavailable"
        availability = "not_available"
        reason = f"registry_visibility_{visibility}"
        layers = CatalogStatusLayers(
            tool_status="unavailable",
            experiment_status="unknown",
            adoption_status="not_reviewed",
        )
        derivation = "derived_from_registry_visibility_other"

    return AgentDiscoveredTool(
        tool_id=descriptor.id,
        name=descriptor.name,
        provider=descriptor.provider,
        description=descriptor.description,
        source=_REGISTRY_SOURCE,
        discovery_category=category,
        agent_available=agent_available,
        availability=availability,
        catalog_status=layers,
        input_schema=dict(descriptor.input_schema or {}),
        output_schema=descriptor.output_schema,
        side_effect="read_only" if descriptor.execution_mode == "read" else descriptor.execution_mode,
        risk_level=descriptor.risk_level,
        permissions=list(descriptor.permissions or []),
        unavailability_reason=reason,
        capabilities=list(descriptor.capabilities or []),
        registry_visibility=visibility,
        status_derivation=derivation,
    )


def _from_experimental_catalog_entry(entry: dict[str, Any]) -> AgentDiscoveredTool:
    layers = _catalog_layers_from_entry(entry)
    tool_id = str(entry.get("tool_id") or entry.get("id") or "")

    if layers.tool_status == "disabled":
        category: DiscoveryCategory = "unavailable"
        reason = "tool_status_disabled"
    elif layers.adoption_status in ("rejected", "deprecated"):
        category = "unavailable"
        reason = f"adoption_status_{layers.adoption_status}"
    elif layers.experiment_status == "experimental":
        category = "experimental"
        reason = "experimental_not_integrated"
    else:
        category = "not_ready"
        reason = "integration_conditions_not_met"

    return AgentDiscoveredTool(
        tool_id=tool_id,
        name=str(entry.get("name") or ""),
        provider=str(entry.get("provider") or "local"),
        description=str(entry.get("description") or ""),
        source=_CATALOG_ENTRIES_SOURCE,
        discovery_category=category,
        agent_available=False,
        availability="not_available",
        catalog_status=layers,
        input_schema=dict(entry.get("input_schema") or {}),
        output_schema=entry.get("output_schema"),
        side_effect=entry.get("side_effect"),
        risk_level=str(entry.get("risk_level") or "low"),
        permissions=list(entry.get("permissions") or []),
        unavailability_reason=reason,
        capabilities=list(entry.get("capabilities") or []),
        provider_specific=dict(entry.get("provider_specific") or {}) or None,
        status_derivation="from_catalog_entry",
    )


def _from_manual_mcp_entry(raw: dict[str, Any]) -> AgentDiscoveredTool:
    tool_id = str(raw.get("id") or raw.get("tool_id") or "")
    status_field = str(raw.get("status") or "experimental")
    layers = CatalogStatusLayers(
        tool_status="unavailable" if status_field == "experimental" else status_field,
        experiment_status="experimental",
        adoption_status="not_reviewed",
    )
    return AgentDiscoveredTool(
        tool_id=tool_id,
        name=str(raw.get("name") or ""),
        provider=str(raw.get("provider") or "mcp"),
        description=str(raw.get("description") or ""),
        source=_MANUAL_CATALOG_SOURCE,
        discovery_category="experimental",
        agent_available=False,
        availability="not_available",
        catalog_status=layers,
        input_schema=dict(raw.get("input_schema") or {}),
        output_schema=raw.get("output_schema"),
        side_effect="read_only",
        risk_level=str(raw.get("risk_level") or "low"),
        permissions=list(raw.get("permissions") or []),
        unavailability_reason="experimental_not_integrated",
        capabilities=list(raw.get("capabilities") or []),
        provider_specific={"source": raw.get("source")},
        status_derivation="derived_from_ai_tool_catalog_experimental",
    )


class AgentToolDiscoveryAdapter:
    """Read-only bridge: Agent ← AI-TOOL metadata. Does not execute tools."""

    def __init__(
        self,
        *,
        local_provider: LocalToolProvider | None = None,
        catalog_entries_dir: Path | None = None,
    ) -> None:
        self._local = local_provider or LocalToolProvider()
        self._catalog_entries_dir = catalog_entries_dir

    def discover_tools(self, *, audit: bool = True) -> DiscoveryResult:
        tools: list[AgentDiscoveredTool] = []

        registry_entries = self._local.list_descriptors()
        registry_names = {d.name for d in registry_entries}
        for descriptor in registry_entries:
            tools.append(_from_registry_entry(descriptor))

        for entry in load_experimental_entries(entries_dir=self._catalog_entries_dir):
            if str(entry.get("name") or "") in registry_names:
                continue
            tools.append(_from_experimental_catalog_entry(entry))

        for raw in load_manual_mcp_entries():
            tools.append(_from_manual_mcp_entry(raw))

        tools.sort(key=lambda t: t.tool_id)

        audit_id = None
        if audit:
            audit_id = append_audit(
                {
                    "event": "agent_tool_discovery",
                    "count": len(tools),
                    "agent_available_count": sum(1 for t in tools if t.agent_available),
                    "experimental_count": sum(1 for t in tools if t.discovery_category == "experimental"),
                    "tool_ids": [t.tool_id for t in tools],
                }
            )

        return DiscoveryResult(tools=tools, audit_id=audit_id)

    def get_tool_descriptor(self, tool_id: str) -> AgentDiscoveredTool | None:
        for tool in self.discover_tools(audit=False).tools:
            if tool.tool_id == tool_id:
                return tool
        return None

    def comparison_table(self) -> list[dict[str, Any]]:
        """Representative tools for Phase 1 observation."""
        wanted = {
            "local:get_gpu_status",
            "local:cpu_status",
            "local:read_file",
            "local:workspace_read_text_scoped",
            "local:read_url_text",
        }
        rows: list[dict[str, Any]] = []
        by_id = {t.tool_id: t for t in self.discover_tools(audit=False).tools}
        for tid in sorted(wanted):
            t = by_id.get(tid)
            if t is None:
                rows.append(
                    {
                        "tool_id": tid,
                        "provider": "UNKNOWN",
                        "source": "NOT_FOUND",
                        "agent_available": False,
                        "discovery_category": "UNKNOWN",
                    }
                )
                continue
            source_label = "Registry" if t.source == _REGISTRY_SOURCE else "AI-TOOL Catalog"
            if t.provider == "mcp":
                source_label = "AI-TOOL Catalog"
            rows.append(
                {
                    "tool_id": t.tool_id,
                    "name": t.name,
                    "provider": t.provider,
                    "source": source_label,
                    "agent_available": t.agent_available,
                    "discovery_category": t.discovery_category,
                    "catalog_status": t.catalog_status.to_dict(),
                }
            )
        return rows


def discover_tools(*, audit: bool = True) -> DiscoveryResult:
    return AgentToolDiscoveryAdapter().discover_tools(audit=audit)


def get_tool_descriptor(tool_id: str) -> AgentDiscoveredTool | None:
    return AgentToolDiscoveryAdapter().get_tool_descriptor(tool_id)
