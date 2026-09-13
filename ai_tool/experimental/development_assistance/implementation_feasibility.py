"""Implementation feasibility — no auto-build."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

FeasibilityDecision = Literal[
    "BUILD_NOW",
    "BUILD_AFTER_RESEARCH",
    "EXPERIMENTAL_FIRST",
    "NOT_RECOMMENDED",
]


@dataclass
class ImplementationFeasibility:
    decision: FeasibilityDecision
    rationale: str
    blockers: list[str]
    open_research: list[str]
    human_review_recommended: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_implementation_feasibility(
    *,
    spec_draft: dict[str, Any] | None,
    technology_candidates: list[dict[str, Any]],
    unknowns: list[str],
    conflicts: list[dict[str, Any]],
    internal_difficulty: str,
    llm_gap: str,
) -> ImplementationFeasibility:
    """Assess whether implementation is advisable — not mechanical."""
    blockers: list[str] = []
    open_research: list[str] = list(unknowns or [])

    if conflicts:
        blockers.append(f"{len(conflicts)} conflict(s) preserved — user must choose interpretation")
    if not spec_draft:
        return ImplementationFeasibility(
            decision="NOT_RECOMMENDED",
            rationale="Tool Specification Draft 未到達 — 実装判断材料不足",
            blockers=["no_spec_draft"],
            open_research=open_research,
            human_review_recommended=True,
        )

    env = spec_draft.get("environment") or {}
    if env.get("cuda") and env.get("cuda") != "UNKNOWN":
        open_research.append("CUDA/driver compatibility on target machine")

    if internal_difficulty == "HIGH" or llm_gap == "HIGH":
        if len(unknowns) > 2 or conflicts:
            return ImplementationFeasibility(
                decision="EXPERIMENTAL_FIRST",
                rationale="専門領域かつ Unknown/Conflict あり — 小さなExperimental PoCから開始を推奨",
                blockers=blockers,
                open_research=open_research,
                human_review_recommended=True,
            )
        return ImplementationFeasibility(
            decision="BUILD_AFTER_RESEARCH",
            rationale="仕様ドラフトはあるが専門領域 — 追加確認後に実装",
            blockers=blockers,
            open_research=open_research,
            human_review_recommended=False,
        )

    if len(unknowns) <= 1 and not conflicts:
        return ImplementationFeasibility(
            decision="BUILD_NOW",
            rationale="主要 Unknown が少なく Spec Draft 到達 — 実装着手可能（本 Phase では実装しない）",
            blockers=blockers,
            open_research=open_research,
            human_review_recommended=False,
        )

    return ImplementationFeasibility(
        decision="BUILD_AFTER_RESEARCH",
        rationale="残 Unknown あり — 不足調査後に実装",
        blockers=blockers,
        open_research=open_research,
        human_review_recommended=len(unknowns) > 3,
    )
