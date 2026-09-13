"""Past Research Record — envelope over existing TDA metadata, not a Database Core."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.api_observation import APIObservation
from ai_tool.experimental.development_assistance.version_facts import version_facts_from_candidate


def _topic_from_requirement(requirement: str) -> str:
    tokens = [t for t in requirement.replace("。", " ").split() if len(t) > 1]
    return " ".join(tokens[:6])[:80]


def _research_id(requirement: str, checked_at: str) -> str:
    h = hashlib.sha256(f"{requirement}|{checked_at}".encode()).hexdigest()[:12]
    return f"RR-{h}"


@dataclass
class ResearchRecord:
    research_id: str
    requirement: str
    topic: str
    technology_candidates: list[dict[str, Any]]
    version_facts: list[dict[str, Any]]
    environment_facts: dict[str, str]
    license_facts: list[str]
    api_observations: list[dict[str, Any]]
    sources: list[dict[str, str]]
    unknowns: list[str]
    conflicts: list[dict[str, Any]]
    queries: list[str]
    checked_at: str
    provenance: str = "web_research"
    facet_records: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def technology_names(self) -> list[str]:
        return [str(c.get("name") or "") for c in self.technology_candidates if c.get("name")]


def build_research_record(
    run_result: dict[str, Any],
    *,
    api_observations: list[APIObservation] | None = None,
    checked_at: str | None = None,
) -> ResearchRecord:
    """Build a Research Record from a completed TDA/web run — reuse-oriented envelope."""
    requirement = str(run_result.get("requirement") or run_result.get("case_id") or "")
    candidates = run_result.get("candidates") or []
    ts = checked_at or datetime.now(timezone.utc).isoformat()
    vfs = [version_facts_from_candidate(c).to_dict() for c in candidates if c.get("type") != "Custom Build"]

    env_merged: dict[str, str] = {}
    for c in candidates:
        for k, v in (c.get("environment") or {}).items():
            if v and v != "UNKNOWN":
                env_merged.setdefault(k, str(v))

    licenses = sorted({str(c.get("license")) for c in candidates if c.get("license") not in (None, "UNKNOWN")})
    sources = [
        {
            "title": str(c.get("source_title") or ""),
            "url": str(c.get("url") or ""),
            "category": str(c.get("source_category") or ""),
        }
        for c in candidates
        if c.get("url")
    ]

    prop = run_result.get("proposal") or {}
    unknowns = list(prop.get("unknown") or [])
    for c in candidates:
        unknowns.extend(c.get("unknowns") or [])
    unknowns = sorted(set(unknowns))

    api_obs = [a.to_dict() for a in (api_observations or [])]

    return ResearchRecord(
        research_id=_research_id(requirement, ts),
        requirement=requirement,
        topic=_topic_from_requirement(requirement),
        technology_candidates=[dict(c) for c in candidates],
        version_facts=vfs,
        environment_facts=env_merged,
        license_facts=licenses,
        api_observations=api_obs,
        sources=sources,
        unknowns=unknowns,
        conflicts=list(prop.get("conflicts") or run_result.get("conflicts") or []),
        queries=list(run_result.get("queries") or []),
        checked_at=ts,
        facet_records=list(run_result.get("facet_records") or []),
    )


@dataclass
class ResearchStore:
    """In-memory past research index — not a Knowledge Core."""

    records: list[ResearchRecord] = field(default_factory=list)

    def add(self, record: ResearchRecord) -> None:
        self.records.append(record)

    def add_from_run(self, run_result: dict[str, Any], **kwargs: Any) -> ResearchRecord:
        rec = build_research_record(run_result, **kwargs)
        self.add(rec)
        return rec

    def to_dict(self) -> dict[str, Any]:
        return {"count": len(self.records), "records": [r.to_dict() for r in self.records]}

    def find_by_technology(self, name: str) -> list[ResearchRecord]:
        name_l = name.lower()
        return [r for r in self.records if any(name_l in n.lower() for n in r.technology_names)]

    def find_by_topic_token(self, token: str) -> list[ResearchRecord]:
        t = token.lower()
        return [
            r
            for r in self.records
            if t in r.requirement.lower() or t in r.topic.lower()
            or any(t in n.lower() for n in r.technology_names)
        ]
