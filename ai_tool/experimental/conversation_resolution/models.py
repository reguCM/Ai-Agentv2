"""Data models for conversation resolution PoC (experimental only)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CandidateRelation = Literal["AGREEMENT", "NUMERIC_NEAR", "DEFINITION_DIFF", "TRUE_CONFLICT", "SINGLE"]
PresentationMode = Literal["SINGLE", "MERGED", "MULTI", "UNRESOLVED"]
FollowUpIntent = Literal[
    "ADOPT_A",
    "ADOPT_B",
    "COMPARE",
    "SHOW_SOURCE",
    "SHOW_BOTH",
    "CONTINUE",
    "UNKNOWN",
]


@dataclass
class SourceRecord:
    source_id: str
    url: str
    title: str
    backend: str = "fixture"
    source_type: str = "web"
    fetched_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceRecord:
    evidence_id: str
    source_id: str
    excerpt: str
    main_text: str
    fact_ready: bool | None = None
    web_status_overall: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationObservation:
    claim_id: str
    verdict: str
    method: str = "mechanical_verification"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    candidate_id: str
    label: str
    claim: str
    evidence_id: str
    source_id: str
    url: str
    source_title: str
    definition_label: str = ""
    numeric_values: list[float] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    verification: list[VerificationObservation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["verification"] = [v.to_dict() for v in self.verification]
        return d


@dataclass
class ConversationState:
    session_id: str
    user_request: str
    candidates: list[Candidate]
    selected_candidate_id: str | None = None
    presentation_mode: PresentationMode = "SINGLE"
    relation: CandidateRelation = "SINGLE"
    turn: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_request": self.user_request,
            "candidates": [c.to_dict() for c in self.candidates],
            "selected_candidate_id": self.selected_candidate_id,
            "presentation_mode": self.presentation_mode,
            "relation": self.relation,
            "turn": self.turn,
        }


@dataclass
class UserFacingPresentation:
    headline: str
    body: str
    mode: PresentationMode
    candidates_shown: list[str]
    citations: list[dict[str, str]]
    difference_note: str = ""
    source_links: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
