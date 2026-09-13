from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ProviderKind = Literal["local", "mcp", "api", "other"]
ExecutionMode = Literal["read", "write", "modify"]
RiskLevel = Literal["low", "medium", "high"]
Availability = Literal["local", "remote"]
AuthKind = Literal["none", "user", "token", "oauth", "unknown"]
CostKind = Literal["free", "paid", "unknown"]
StatusKind = Literal["experimental", "available", "disabled", "adopt_candidate", "not_ready"]


@dataclass
class ToolDescriptor:
    """Unified tool metadata for local and external tools (Phase 1 draft)."""

    id: str
    name: str
    provider: ProviderKind
    source: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    permissions: list[str] = field(default_factory=list)
    risk_level: RiskLevel = "low"
    execution_mode: ExecutionMode = "read"
    availability: Availability = "local"
    authentication: AuthKind = "none"
    cost: CostKind = "free"
    status: StatusKind = "experimental"
    evidence: list[str] = field(default_factory=list)
    # Bridge to existing registry (local only)
    registry_name: str | None = None
    module: str | None = None
    function: str | None = None
    visibility: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolExecutionResult:
    tool_id: str
    provider: ProviderKind
    ok: bool
    result: Any
    error: str | None = None
    duration_ms: float | None = None
    audit_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
