"""Lightweight version facts for decision support (not a Version Matrix Core)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Provenance = Literal[
    "officially_documented",
    "observed_from_source",
    "inferred",
    "unknown",
    "actually_tested",
]


@dataclass
class VersionFact:
    technology: str
    version: str
    python: str = "UNKNOWN"
    cuda: str = "UNKNOWN"
    os: str = "UNKNOWN"
    license: str = "UNKNOWN"
    source: str = ""
    source_category: str = "Other"
    provenance: Provenance = "observed_from_source"
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def version_facts_from_candidate(candidate: dict[str, Any]) -> VersionFact:
    """Build a single VersionFact from TechnologyCandidate dict — no compatibility claims."""
    env = candidate.get("environment") or {}
    meta = candidate.get("metadata") or {}
    prov: Provenance = "observed_from_source"
    if candidate.get("source_category") == "Official Documentation":
        prov = "officially_documented"
    elif candidate.get("type") == "Custom Build":
        prov = "inferred"

    return VersionFact(
        technology=str(candidate.get("name") or "UNKNOWN"),
        version=str(candidate.get("version") or "UNKNOWN"),
        python=str(env.get("python") or "UNKNOWN"),
        cuda=str(env.get("cuda") or "UNKNOWN"),
        os=str(env.get("os") or "UNKNOWN"),
        license=str(candidate.get("license") or "UNKNOWN"),
        source=str(candidate.get("url") or candidate.get("source_title") or ""),
        source_category=str(candidate.get("source_category") or "Other"),
        provenance=prov,
        observed_at=str(meta.get("observed_at") or datetime.now(timezone.utc).date().isoformat()),
    )
