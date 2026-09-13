"""Tool Specification Draft — research output, not auto-implementation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ai_tool.experimental.development_assistance.decision_factors import compute_decision_factors
from ai_tool.experimental.development_assistance.version_facts import version_facts_from_candidate


@dataclass
class ToolSpecificationDraft:
    tool_name: str
    purpose: str
    runtime: str
    dependencies: list[str]
    version: str
    environment: dict[str, str]
    api_notes: list[str]
    license: str
    sources: list[dict[str, str]]
    unknowns: list[str]
    constraints: list[str]
    selected_candidate_id: str = ""
    provenance_note: str = "Draft from Web Research — not verified by execution"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_spec_draft(
    requirement: str,
    candidate: dict[str, Any],
    *,
    selected_candidate_id: str = "",
) -> ToolSpecificationDraft:
    """Build spec draft from selected candidate — user implements manually."""
    env = dict(candidate.get("environment") or {})
    vf = version_facts_from_candidate(candidate)
    factors = compute_decision_factors(candidate)
    constraints = [f"{f.factor}: {f.detail} ({f.status})" for f in factors if f.status in ("unknown", "conflict")]

    deps: list[str] = []
    if candidate.get("type") in ("Library", "OSS"):
        deps.append(str(candidate.get("name")))
    if env.get("python") and env["python"] != "UNKNOWN":
        deps.append(env["python"])

    api_notes: list[str] = []
    desc = str(candidate.get("description") or "")
    for token in ("movej", "movel", "set_digital_out", "Thread", "REST API", "SDK"):
        if token.lower() in desc.lower():
            api_notes.append(f"Observed mention: {token} (existence not mechanically verified)")

    return ToolSpecificationDraft(
        tool_name=f"tool_{candidate.get('name', 'draft')[:40].replace(' ', '_').lower()}",
        purpose=requirement[:200],
        runtime=env.get("python") or "UNKNOWN",
        dependencies=deps,
        version=vf.version,
        environment=env,
        api_notes=api_notes,
        license=str(candidate.get("license") or "UNKNOWN"),
        sources=[
            {
                "title": str(candidate.get("source_title") or ""),
                "url": str(candidate.get("url") or ""),
                "category": str(candidate.get("source_category") or ""),
            }
        ],
        unknowns=list(candidate.get("unknowns") or []),
        constraints=constraints,
        selected_candidate_id=selected_candidate_id or str(candidate.get("candidate_id") or ""),
    )
