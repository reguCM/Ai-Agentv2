"""Extended Tool Specification for Phase G real-world evaluation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ai_tool.experimental.development_assistance.spec_draft import ToolSpecificationDraft, build_spec_draft


@dataclass
class ExtendedToolSpecification:
    tool_name: str
    purpose: str
    user_problem: str
    inputs: list[str]
    outputs: list[str]
    dependencies: list[str]
    environment: dict[str, str]
    versions: dict[str, str]
    license: str
    apis: list[str]
    external_resources: list[dict[str, str]]
    failure_modes: list[str]
    unknowns: list[str]
    safety_constraints: list[str]
    implementation_boundary: str
    base_draft: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_extended_spec(
    requirement: str,
    candidate: dict[str, Any],
    *,
    selected_tool_name: str = "",
    user_problem: str = "",
) -> ExtendedToolSpecification:
    base = build_spec_draft(requirement, candidate)
    env = dict(base.environment)
    desc = str(candidate.get("description") or "")

    apis: list[str] = list(base.api_notes)
    if "REST API" in desc or candidate.get("type") == "API":
        apis.append("REST API integration (observed in source)")

    failure_modes = [
        "Source information stale — verify CheckedAt before production use",
        "Unknown fields remain — do not assume compatibility",
    ]
    if candidate.get("conflicts"):
        failure_modes.append("Conflicting sources — user must resolve before implementation")

    safety = [
        "Do not treat Web Evidence as ground truth",
        "No automatic code execution in TDA path",
    ]
    if "robot" in selected_tool_name.lower() or "ur" in desc.lower():
        safety.append("Robot motion requires safety limits and e-stop awareness — not verified by TDA")

    return ExtendedToolSpecification(
        tool_name=selected_tool_name or base.tool_name,
        purpose=base.purpose,
        user_problem=user_problem or requirement[:200],
        inputs=["User-provided files/commands per tool design"],
        outputs=["Structured result / status report"],
        dependencies=base.dependencies,
        environment=env,
        versions={"component": base.version, "python": env.get("python", "UNKNOWN"), "cuda": env.get("cuda", "UNKNOWN")},
        license=base.license,
        apis=apis,
        external_resources=base.sources,
        failure_modes=failure_modes,
        unknowns=base.unknowns,
        safety_constraints=safety,
        implementation_boundary="Specification draft only — Phase G does not auto-implement",
        base_draft=base.to_dict(),
    )
