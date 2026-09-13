"""Research resume context — conversation state extension, not Research Transaction Core."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ResearchState:
    """Minimal state for 'Bについてもう少し調べて' follow-ups."""
    requirement: str
    queries: list[str] = field(default_factory=list)
    candidate_ids: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    known_unknowns: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    selected_candidate_id: str = ""
    sources_seen: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def merge_run(self, run_result: dict[str, Any]) -> None:
        for q in run_result.get("queries") or []:
            if q not in self.queries:
                self.queries.append(q)
        for c in run_result.get("candidates") or []:
            cid = str(c.get("candidate_id") or "")
            if cid and cid not in self.candidate_ids:
                self.candidate_ids.append(cid)
                self.candidates.append(c)
            url = str(c.get("url") or "")
            if url and url not in self.sources_seen:
                self.sources_seen.append(url)
        prop = run_result.get("proposal") or {}
        for u in prop.get("unknown") or []:
            if u not in self.known_unknowns:
                self.known_unknowns.append(u)
        for cf in prop.get("conflicts") or []:
            self.conflicts.append(cf)

    def resume_context_for_query(self, follow_up: str) -> dict[str, Any]:
        """Context passed to additional research — no transaction log."""
        target = ""
        for cid in self.candidate_ids:
            if cid.lower() in follow_up.lower():
                target = cid
                break
        return {
            "prior_queries": list(self.queries),
            "prior_candidates": list(self.candidate_ids),
            "target_candidate": target,
            "known_unknowns": list(self.known_unknowns),
            "existing_conflicts": len(self.conflicts),
            "selected": self.selected_candidate_id,
        }
