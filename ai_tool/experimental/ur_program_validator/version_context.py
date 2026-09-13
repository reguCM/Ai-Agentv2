"""Version context — no Version Matrix Core."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_tool.experimental.ur_program_validator.spec_catalog import FunctionSpec, SpecCatalog


@dataclass
class VersionContext:
    robot: str
    polyscope_version: str
    urscript_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "robot": self.robot,
            "polyscope_version": self.polyscope_version,
            "urscript_version": self.urscript_version,
        }


def function_available(spec: FunctionSpec, ctx: VersionContext) -> tuple[str, str]:
    """
    Returns (availability, detail) — not mechanical compatibility engine.
    availability: available | deprecated | unknown | unavailable
    """
    if spec.polyscope_versions == ["5.0"] and _version_gte(ctx.polyscope_version, "5.10"):
        return "unavailable", "Function limited to PolyScope 5.0 in PoC catalog"
    if ctx.polyscope_version in spec.polyscope_versions:
        return "available", "Listed for this PolyScope version in catalog"
    if any(v.endswith(".x") for v in spec.polyscope_versions):
        major = ctx.polyscope_version.split(".")[0]
        if any(v.startswith(major) for v in spec.polyscope_versions):
            return "available", "Major version match (partial — not fully verified)"
    if spec.deprecated_in and _version_gte(ctx.polyscope_version, spec.deprecated_in):
        return "deprecated", f"Deprecated since PolyScope {spec.deprecated_in}"
    return "unknown", "Version availability not confirmed in catalog"


def _version_gte(a: str, b: str) -> bool:
    try:
        pa = [int(x) for x in a.split(".")[:2]]
        pb = [int(x) for x in b.split(".")[:2]]
        return pa >= pb
    except ValueError:
        return False
