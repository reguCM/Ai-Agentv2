"""Read-only Agent Tool Discovery Hook (Phase 2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.agent_integration.models import AgentDiscoveredTool, DiscoveryResult


@dataclass
class AgentDiscoveryHookRecord:
    """Flattened discovery row for Agent / run logging."""

    tool_id: str
    source: str
    provider: str
    discovery_category: str
    agent_available: bool
    tool_status: str
    experiment_status: str
    adoption_status: str
    unavailability_reason: str | None = None
    experimental_agent_exposed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "source": self.source,
            "provider": self.provider,
            "discovery_category": self.discovery_category,
            "agent_available": self.agent_available,
            "experimental_agent_exposed": self.experimental_agent_exposed,
            "tool_status": self.tool_status,
            "experiment_status": self.experiment_status,
            "adoption_status": self.adoption_status,
            "unavailability_reason": self.unavailability_reason,
        }


@dataclass
class AgentDiscoveryHookResult:
    """Result of a read-only discovery hook invocation."""

    ok: bool
    tools: list[AgentDiscoveryHookRecord] = field(default_factory=list)
    production_count: int = 0
    experimental_count: int = 0
    agent_available_count: int = 0
    execution_count: int = 0
    audit_id: str | None = None
    error: str | None = None
    discovery_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "discovery_only": self.discovery_only,
            "execution_count": self.execution_count,
            "audit_id": self.audit_id,
            "error": self.error,
            "production_count": self.production_count,
            "experimental_count": self.experimental_count,
            "agent_available_count": self.agent_available_count,
            "tools": [t.to_dict() for t in self.tools],
        }

    def agent_summary(self) -> dict[str, Any]:
        """Compact summary safe for Agent startup logging."""
        return {
            "ok": self.ok,
            "discovery_only": True,
            "execution_count": self.execution_count,
            "total": len(self.tools),
            "production_count": self.production_count,
            "experimental_count": self.experimental_count,
            "agent_available_count": self.agent_available_count,
            "error": self.error,
        }


def _to_hook_record(tool: AgentDiscoveredTool) -> AgentDiscoveryHookRecord:
    experimental_exposed = False
    try:
        from ai_tool.agent_integration.production_bridge import discovery_experimental_agent_available

        experimental_exposed = discovery_experimental_agent_available(tool.tool_id)
    except Exception:
        experimental_exposed = False
    return AgentDiscoveryHookRecord(
        tool_id=tool.tool_id,
        source=tool.source,
        provider=tool.provider,
        discovery_category=tool.discovery_category,
        agent_available=tool.agent_available,
        tool_status=tool.catalog_status.tool_status,
        experiment_status=tool.catalog_status.experiment_status,
        adoption_status=tool.catalog_status.adoption_status,
        unavailability_reason=tool.unavailability_reason,
        experimental_agent_exposed=experimental_exposed,
    )


def run_agent_discovery_hook(
    *,
    adapter: AgentToolDiscoveryAdapter | None = None,
    audit: bool = True,
) -> AgentDiscoveryHookResult:
    """
    Read-only discovery hook for Agent Core.

    Never executes tools. Never modifies Registry. Raises no exceptions to callers
    when used via `safe_run_agent_discovery_hook`.
    """
    ad = adapter or AgentToolDiscoveryAdapter()
    discovery: DiscoveryResult = ad.discover_tools(audit=audit)
    records = [_to_hook_record(t) for t in discovery.tools]
    production = sum(1 for r in records if r.discovery_category == "production")
    experimental = sum(1 for r in records if r.discovery_category == "experimental")
    agent_available = sum(1 for r in records if r.agent_available)
    return AgentDiscoveryHookResult(
        ok=True,
        tools=records,
        production_count=production,
        experimental_count=experimental,
        agent_available_count=agent_available,
        execution_count=0,
        audit_id=discovery.audit_id,
        error=None,
    )


def safe_run_agent_discovery_hook(
    *,
    adapter: AgentToolDiscoveryAdapter | None = None,
    audit: bool = True,
) -> AgentDiscoveryHookResult:
    """Fail-safe wrapper: discovery errors must not break Agent startup."""
    try:
        return run_agent_discovery_hook(adapter=adapter, audit=audit)
    except Exception as exc:  # noqa: BLE001
        return AgentDiscoveryHookResult(
            ok=False,
            tools=[],
            execution_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )
