"""Audit of existing TDA structures for research reusability (Phase E)."""
from __future__ import annotations

from typing import Any

# What each structure stores and whether it supports future reuse
STRUCTURE_AUDIT: list[dict[str, Any]] = [
    {
        "structure": "TechnologyCandidate",
        "stores": [
            "name", "type", "version", "environment", "license",
            "unknowns", "conflicts", "url", "source_category", "source_title",
        ],
        "reusable": ["technology identity", "version/env/license facts", "source URLs"],
        "gaps": ["research_id", "checked_at at record level", "requirement linkage"],
    },
    {
        "structure": "VersionFact",
        "stores": ["technology", "version", "python", "cuda", "os", "license", "source", "provenance", "observed_at"],
        "reusable": ["environment/version comparison across requirements"],
        "gaps": ["requirement-specific facet keys"],
    },
    {
        "structure": "DecisionFactor",
        "stores": ["factor", "status", "detail", "candidate_id"],
        "reusable": ["decision explanation if requirement similar"],
        "gaps": ["not persisted across sessions by default"],
    },
    {
        "structure": "ResearchState",
        "stores": ["queries", "candidates", "unknowns", "conflicts", "sources_seen"],
        "reusable": ["same-session resume only"],
        "gaps": ["no cross-session persistence", "not a Research Record"],
    },
    {
        "structure": "ConversationState",
        "stores": ["candidates", "selected_candidate_id", "turn"],
        "reusable": ["selection within conversation"],
        "gaps": ["no research timestamp", "no requirement history"],
    },
    {
        "structure": "EvidenceSource",
        "stores": ["url", "title", "main_text", "evidence_id"],
        "reusable": ["source re-tracking", "text re-extraction if cached"],
        "gaps": ["no CheckedAt envelope at evidence pack level"],
    },
    {
        "structure": "ToolSpecificationDraft",
        "stores": ["tool_name", "dependencies", "version", "environment", "sources", "unknowns"],
        "reusable": ["spec starting point for same technology"],
        "gaps": ["stale spec if environment changed"],
    },
    {
        "structure": "APIObservation",
        "stores": ["api_name", "source", "observed_status", "unknown"],
        "reusable": ["API existence from prior official docs"],
        "gaps": ["version-specific API drift not tracked"],
    },
]


def audit_summary() -> dict[str, Any]:
    """High-level reuse readiness — no new Core assumed."""
    return {
        "can_identify_past_research": "partial — TechnologyCandidate + VersionFact sufficient with ResearchRecord envelope",
        "can_compare_requirements": "partial — metadata/token matching; no embedding",
        "can_track_timestamp": "yes — VersionFact.observed_at + ResearchRecord.checked_at",
        "can_re_track_sources": "yes — url + source_category in candidates",
        "needs_dedicated_database": False,
        "recommended_envelope": "ResearchRecord (list of dicts / in-memory store)",
        "structures": STRUCTURE_AUDIT,
    }
