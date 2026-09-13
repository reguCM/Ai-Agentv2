"""Preserved ideas — REJECT/DEFER/RECORD for re-evaluation on future requirements."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

IdeaDecision = Literal["REUSE", "RECORD", "DEFER", "INVESTIGATE", "EXPERIMENTAL", "REJECT"]


@dataclass
class PreservedIdea:
    idea: str
    why_it_appeared: str
    higher_level_goal: str
    why_not_implemented: str
    existing_alternative: str
    potential_future_trigger: str
    decision: IdeaDecision
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    case_id: str = ""
    re_evaluable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Catalog from Phase E false discoveries — seed for cross-requirement re-evaluation
DEFAULT_PRESERVED_IDEAS: list[PreservedIdea] = [
    PreservedIdea(
        idea="Knowledge Base",
        why_it_appeared="L3 goal: accumulate research assets",
        higher_level_goal="Future tool development research reuse",
        why_not_implemented="ResearchStore + ResearchRecord sufficient",
        existing_alternative="research_record.py / ResearchStore",
        potential_future_trigger="Cross-project persistence or multi-user store needed",
        decision="REJECT",
    ),
    PreservedIdea(
        idea="Vector DB / RAG",
        why_it_appeared="Semantic research identity matching",
        higher_level_goal="Match past research to new requirements",
        why_not_implemented="Token/metadata matching sufficient in PoC",
        existing_alternative="extract_requirement_facets + find_best_match",
        potential_future_trigger="Repeated false negative on research identity",
        decision="REJECT",
    ),
    PreservedIdea(
        idea="Research Transaction Core",
        why_it_appeared="Stateful multi-step research resume",
        higher_level_goal="Continue interrupted research",
        why_not_implemented="ResearchState + ResearchRecord cover PoC",
        existing_alternative="research_state.py + research_record.py",
        potential_future_trigger="Complex branching research with rollback",
        decision="DEFER",
    ),
    PreservedIdea(
        idea="Sandbox Runner",
        why_it_appeared="Environment verification beyond docs",
        higher_level_goal="Confirm tool runs in target environment",
        why_not_implemented="Security/isolation risk; not measured necessary",
        existing_alternative="Decision factors + UNKNOWN labels",
        potential_future_trigger="Multiple cases blocked without execution",
        decision="DEFER",
    ),
    PreservedIdea(
        idea="Version Matrix Core",
        why_it_appeared="Compatibility comparison across versions",
        higher_level_goal="Environment-appropriate tool selection",
        why_not_implemented="VersionFact + decision_factors sufficient",
        existing_alternative="version_facts.py",
        potential_future_trigger="Repeated partial reuse failures on version facets",
        decision="REJECT",
    ),
]


@dataclass
class IdeaCatalog:
    ideas: list[PreservedIdea] = field(default_factory=lambda: list(DEFAULT_PRESERVED_IDEAS))

    def add(self, idea: PreservedIdea) -> None:
        self.ideas.append(idea)

    def add_from_discovery(
        self,
        *,
        name: str,
        higher_goal: str,
        decision: IdeaDecision,
        alternative: str,
        reason: str,
        case_id: str = "",
    ) -> None:
        self.add(
            PreservedIdea(
                idea=name,
                why_it_appeared=f"Capability discovery from: {higher_goal}",
                higher_level_goal=higher_goal,
                why_not_implemented=reason,
                existing_alternative=alternative,
                potential_future_trigger=f"New requirement re-opens need for {name}",
                decision=decision,
                case_id=case_id,
            )
        )

    def re_evaluate_for_requirement(self, requirement: str) -> list[PreservedIdea]:
        """Ideas that may become relevant again — not auto-implement."""
        req = requirement.lower()
        hits: list[PreservedIdea] = []
        for idea in self.ideas:
            if idea.decision not in ("REJECT", "DEFER", "RECORD"):
                continue
            triggers = [
                idea.idea.lower(),
                idea.potential_future_trigger.lower(),
            ]
            if any(t in req for t in triggers if len(t) > 4):
                hits.append(idea)
            elif idea.decision == "RECORD" and any(
                tok in req for tok in idea.higher_level_goal.lower().split() if len(tok) > 5
            ):
                hits.append(idea)
        return hits

    def to_dict(self) -> dict[str, Any]:
        return {"count": len(self.ideas), "ideas": [i.to_dict() for i in self.ideas]}
