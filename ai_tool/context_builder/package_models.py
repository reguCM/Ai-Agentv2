from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PackageReadiness = Literal["READY", "PARTIAL", "NOT_READY"]

SLOT_TO_FILENAME: dict[str, str] = {
    "specification": "SPECIFICATION.md",
    "contract": "CONTRACT.md",
    "implementation": "IMPLEMENTATION_CONTEXT.md",
    "tests": "TEST_CONTEXT.md",
    "safety": "SAFETY_CONTEXT.md",
    "change_policy": "CHANGE_POLICY.md",
    "catalog": "CATALOG_CONTEXT.md",
    "known_limitations": "KNOWN_LIMITATIONS.md",
    "related_context": "RELATED_CONTEXT.md",
}

PACKAGE_FILES = (
    "request.json",
    "SUMMARY.md",
    "CONTEXT_MANIFEST.json",
    *SLOT_TO_FILENAME.values(),
    "UNKNOWN_AND_MISSING.md",
)


@dataclass
class ExternalHelpPackageResult:
    tool_id: str
    package_dir: str
    readiness: PackageReadiness
    context_status: str
    missing_p0: list[str]
    files_written: list[str]
    unknown_count: int
    reference_only_count: int
    excluded_count: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
