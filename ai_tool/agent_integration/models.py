"""Agent Tool Discovery — read-only models (Phase 1)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

DiscoveryCategory = Literal["production", "experimental", "unavailable", "not_ready"]
AgentAvailability = Literal["available", "not_available", "unknown"]


@dataclass
class CatalogStatusLayers:
    """Three-layer catalog status — never collapsed into a single label."""

    tool_status: str
    experiment_status: str
    adoption_status: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class AgentDiscoveredTool:
    """Read-only discovery record for Agent integration Phase 1."""

    tool_id: str
    name: str
    provider: str
    description: str
    source: str
    discovery_category: DiscoveryCategory
    agent_available: bool
    availability: AgentAvailability
    catalog_status: CatalogStatusLayers
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    side_effect: str | None = None
    risk_level: str = "low"
    permissions: list[str] = field(default_factory=list)
    unavailability_reason: str | None = None
    capabilities: list[str] = field(default_factory=list)
    provider_specific: dict[str, Any] | None = None
    registry_visibility: str | None = None
    status_derivation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["catalog_status"] = self.catalog_status.to_dict()
        return d


@dataclass
class DiscoveryResult:
    tools: list[AgentDiscoveredTool]
    audit_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "count": len(self.tools),
            "tools": [t.to_dict() for t in self.tools],
        }
