"""Stage observations for Phase G — TDA-discovered vs human-prescribed ideas."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ObsDecision = Literal["REUSE", "RECORD", "DEFER", "INVESTIGATE", "EXPERIMENTAL", "REJECT"]
IdeaOrigin = Literal["tda_natural", "phase_prior_catalog", "human_prescribed"]


@dataclass
class StageObservation:
    stage: str
    observation: str
    idea: str
    higher_level_concept: str
    existing_alternative: str
    decision: ObsDecision
    origin: IdeaOrigin = "tda_natural"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StageObservationLog:
    entries: list[StageObservation] = field(default_factory=list)
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add(
        self,
        stage: str,
        observation: str,
        idea: str,
        higher_level_concept: str,
        existing_alternative: str,
        decision: ObsDecision,
        *,
        origin: IdeaOrigin = "tda_natural",
    ) -> None:
        self.entries.append(
            StageObservation(
                stage=stage,
                observation=observation,
                idea=idea,
                higher_level_concept=higher_level_concept,
                existing_alternative=existing_alternative,
                decision=decision,
                origin=origin,
            )
        )

    def tda_natural_ideas(self) -> list[StageObservation]:
        return [e for e in self.entries if e.origin == "tda_natural"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "recorded_at": self.recorded_at,
            "count": len(self.entries),
            "tda_natural_count": len(self.tda_natural_ideas()),
            "entries": [e.to_dict() for e in self.entries],
        }
