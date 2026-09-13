from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SlotStatus = Literal["FOUND", "UNKNOWN", "EXCLUDED", "REFERENCE_ONLY"]
Priority = Literal["P0", "P1", "P2"]
BuilderStatus = Literal["OK", "PARTIAL", "ERROR"]
ContentStatus = Literal[
    "FETCHED",
    "NOT_FETCHED",
    "EXCLUDED_OUTSIDE_ALLOWLIST",
    "EXCLUDED_SENSITIVE",
    "FETCH_FAILED",
]
CompressionMode = Literal["full", "none"]

P0_SLOTS = (
    "identity",
    "specification",
    "contract",
    "implementation",
    "tests",
    "safety",
)
P1_SLOTS = ("change_policy", "catalog", "known_limitations")
P2_SLOTS = ("related_context",)
ALL_SLOTS = (*P0_SLOTS, *P1_SLOTS, *P2_SLOTS)


@dataclass
class SlotEntry:
    status: SlotStatus
    reason: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SelectedFile:
    path: str
    slot: str
    reason: str
    priority: Priority
    content_status: ContentStatus
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextManifest:
    tool_id: str
    slots: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"tool_id": self.tool_id, "slots": self.slots}


@dataclass
class ContextBuildResult:
    status: BuilderStatus
    tool_id: str
    manifest: ContextManifest
    selected_files: list[SelectedFile]
    missing_slots: list[str]
    excluded_files: list[dict[str, Any]]
    warnings: list[str]
    content: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "tool_id": self.tool_id,
            "manifest": self.manifest.to_dict(),
            "selected_files": [f.to_dict() for f in self.selected_files],
            "missing_slots": self.missing_slots,
            "excluded_files": self.excluded_files,
            "warnings": self.warnings,
            "content": self.content,
        }
