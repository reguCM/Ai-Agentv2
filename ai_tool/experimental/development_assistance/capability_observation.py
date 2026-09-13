"""Capability observation records for TDA Phase C discovery."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Stage = Literal[
    "Requirement",
    "Research Gate",
    "Query",
    "Search",
    "Evidence",
    "Candidate",
    "Environment",
    "Proposal",
    "User Selection",
    "Specification",
]

ReusePotential = Literal["LOW", "MEDIUM", "HIGH"]
CostLevel = Literal["LOW", "MEDIUM", "HIGH"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
ObsDecision = Literal[
    "REUSE",
    "RECORD",
    "INVESTIGATE",
    "EXPERIMENTAL",
    "DEFER",
    "REJECT",
]

STAGES: list[Stage] = [
    "Requirement",
    "Research Gate",
    "Query",
    "Search",
    "Evidence",
    "Candidate",
    "Environment",
    "Proposal",
    "User Selection",
    "Specification",
]


@dataclass
class CapabilityObservation:
    id: str
    phase: str
    stage: Stage
    problem: str
    idea: str
    trigger: str
    existing_capability: str
    reuse_potential: ReusePotential
    implementation_cost: CostLevel
    risk: RiskLevel
    decision: ObsDecision
    reason: str
    case_id: str = ""
    generality: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Reference catalog A–J from Phase C spec (for explicit evaluation, not auto-implement)
CANDIDATE_CATALOG: list[dict[str, str]] = [
    {"id": "CAP-A", "name": "Environment Profiler", "topic": "local machine env vs web-stated env"},
    {"id": "CAP-B", "name": "Version Compatibility Matrix", "topic": "compatible/incompatible/unknown matrix"},
    {"id": "CAP-C", "name": "API / Function Existence Observation", "topic": "FOUND/NOT_FOUND/UNKNOWN"},
    {"id": "CAP-D", "name": "Documentation Extractor", "topic": "PDF/official doc structured extraction"},
    {"id": "CAP-E", "name": "License Observation", "topic": "license metadata for comparison"},
    {"id": "CAP-F", "name": "Dependency Graph", "topic": "Tool→Library→Runtime deps"},
    {"id": "CAP-G", "name": "Documentation Version Tracking", "topic": "LLM knowledge vs Web version"},
    {"id": "CAP-H", "name": "Tool Specification Validator", "topic": "Proposal→Spec structural check"},
    {"id": "CAP-I", "name": "Research Resume / Research Context", "topic": "prior research + open questions"},
    {"id": "CAP-J", "name": "Experiment/Sandbox Runner", "topic": "install/run candidate OSS"},
]
