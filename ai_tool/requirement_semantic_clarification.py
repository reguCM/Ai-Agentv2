"""Clarification impact / rework risk (v0) — separate from semantic diff decision."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from ai_tool.requirement_semantic_revalidation import (
    DerivedSpecView,
    HumanMeaningCanonical,
    ResolvedContext,
    SemanticRevalidationResult,
)

ImpactLevel = Literal["LOW", "MEDIUM", "HIGH"]
UncertaintyLevel = Literal["LOW", "MEDIUM", "HIGH"]

CLARIFICATION_REASON_UNCERTAINTY = "semantic_uncertainty"
CLARIFICATION_REASON_HIGH_REWORK_RISK = "high_rework_risk_with_material_ambiguity"
CLARIFICATION_REASON_AMBIGUOUS_REFERENCE = "ambiguous_reference"


@dataclass
class InterpretationAlternative:
    alternative_id: str
    label: str
    downstream_impact: ImpactLevel = "MEDIUM"

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.alternative_id,
            "label": self.label,
            "downstream_impact": self.downstream_impact,
        }


@dataclass
class ClarificationChoice:
    choice_id: str
    label: str
    kind: str  # confirm_leading | alternative | free_input

    def as_dict(self) -> dict[str, str]:
        return {"id": self.choice_id, "label": self.label, "kind": self.kind}


@dataclass
class ClarificationImpactAssessment:
    semantic_uncertainty: UncertaintyLevel
    downstream_impact: ImpactLevel
    clarification_needed: bool
    clarification_reason: str
    leading_interpretation: str = ""
    interpretation_alternatives: list[InterpretationAlternative] = field(default_factory=list)
    choices: list[ClarificationChoice] = field(default_factory=list)
    clarification_reason_explanation: str = ""
    high_impact_alone_forces_human: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "semantic_uncertainty": self.semantic_uncertainty,
            "downstream_impact": self.downstream_impact,
            "clarification_needed": self.clarification_needed,
            "clarification_reason": self.clarification_reason,
            "leading_interpretation": self.leading_interpretation,
            "interpretation_alternatives": [a.as_dict() for a in self.interpretation_alternatives],
            "choices": [c.as_dict() for c in self.choices],
            "clarification_reason_explanation": self.clarification_reason_explanation,
            "high_impact_alone_forces_human": self.high_impact_alone_forces_human,
        }


def _level(raw: Any, default: ImpactLevel = "MEDIUM") -> ImpactLevel:
    token = str(raw or "").strip().upper()
    if token in ("LOW", "MEDIUM", "HIGH"):
        return token  # type: ignore[return-value]
    return default


def _alternatives_from_context(context: ResolvedContext) -> list[InterpretationAlternative]:
    raw = getattr(context, "interpretation_alternatives", None) or []
    out: list[InterpretationAlternative] = []
    for row in raw:
        if not isinstance(row, Mapping):
            continue
        alt_id = str(row.get("id") or row.get("alternative_id") or "").strip()
        label = str(row.get("label") or row.get("summary") or "").strip()
        if not alt_id or not label:
            continue
        out.append(
            InterpretationAlternative(
                alternative_id=alt_id,
                label=label,
                downstream_impact=_level(row.get("downstream_impact"), "MEDIUM"),
            )
        )
    return out


def assess_semantic_uncertainty(
    human: HumanMeaningCanonical,
    context: ResolvedContext,
) -> UncertaintyLevel:
    override = human.metadata.get("semantic_uncertainty") or getattr(
        context, "semantic_uncertainty", None
    )
    if override:
        return _level(override, "MEDIUM")  # type: ignore[return-value]

    if context.ambiguous_reference or len(context.candidates) > 1:
        return "HIGH"

    if bool(getattr(context, "reference_explicit", False)):
        return "LOW"
    if context.reference_target and (context.resume_point or context.reference_state):
        return "LOW"

    alternatives = _alternatives_from_context(context)
    if len(alternatives) >= 2:
        return "MEDIUM"

    if human.metadata.get("continuation_reference_vague"):
        return "MEDIUM"

    return "LOW"


def assess_downstream_impact(
    human: HumanMeaningCanonical,
    context: ResolvedContext,
    derived: DerivedSpecView,
    alternatives: list[InterpretationAlternative],
) -> ImpactLevel:
    override = (
        human.metadata.get("downstream_impact")
        or getattr(context, "downstream_impact_if_wrong", None)
        or derived.metadata.get("downstream_impact")
    )
    if override:
        return _level(override, "MEDIUM")  # type: ignore[return-value]

    if alternatives:
        impacts = {a.downstream_impact for a in alternatives}
        if "HIGH" in impacts and len(alternatives) >= 2:
            return "HIGH"

    if len(context.candidates) > 1:
        states = {str(c.get("state") or "").casefold() for c in context.candidates}
        if "stopped" in states and "completed" in states:
            return "HIGH"

    scope = str(derived.metadata.get("implementation_scope") or "").casefold()
    if scope in ("large", "high", "major"):
        return "HIGH"
    if derived.metadata.get("touches_external_state"):
        return "HIGH"

    return "MEDIUM"


def _leading_interpretation(
    context: ResolvedContext,
    alternatives: list[InterpretationAlternative],
) -> str:
    lead_id = getattr(context, "leading_interpretation_id", None) or context.reference_target
    if lead_id:
        for alt in alternatives:
            if alt.alternative_id == lead_id:
                return alt.label
    if alternatives:
        return alternatives[0].label
    if context.reference_target and context.reference_state:
        parts = [context.reference_target]
        if context.resume_point:
            parts.append(f"resume={context.resume_point}")
        if context.reference_state:
            parts.append(f"state={context.reference_state}")
        return " / ".join(parts)
    return ""


def _build_choices(
    leading: str,
    alternatives: list[InterpretationAlternative],
) -> list[ClarificationChoice]:
    if not alternatives:
        return [
            ClarificationChoice("C", "その他（自由入力）", "free_input"),
        ]
    choices: list[ClarificationChoice] = [
        ClarificationChoice("A", "その意味で合っている", "confirm_leading"),
    ]
    idx = 0
    for alt in alternatives:
        if leading and alt.label == leading:
            continue
        letter = chr(ord("B") + idx)
        idx += 1
        choices.append(ClarificationChoice(letter, alt.label, "alternative"))
    choices.append(ClarificationChoice("C", "その他（自由入力）", "free_input"))
    return choices


def _clarification_reason_explanation_nl(
    *,
    uncertainty: UncertaintyLevel,
    impact: ImpactLevel,
    reason: str,
    leading: str,
) -> str:
    if reason == CLARIFICATION_REASON_AMBIGUOUS_REFERENCE:
        return (
            "参照先を一意に特定できないため、"
            "実装前に確認します。"
        )
    if uncertainty == "HIGH":
        return (
            "意味の解釈に複数の有力な候補があり、"
            "実装前に確認します。"
        )
    if uncertainty == "MEDIUM" and impact == "HIGH":
        base = (
            "この解釈が違う場合、この後の設計・実装対象そのものが変わり、"
            "大きな手戻りになるため、実装前に確認します。"
        )
        if leading:
            return base
        return base
    return "実装前に確認が必要です。"


def needs_early_clarification(
    *,
    semantic_uncertainty: UncertaintyLevel,
    downstream_impact: ImpactLevel,
    semantic_decision: str,
) -> bool:
    if semantic_decision != "PASS":
        return False
    if semantic_uncertainty == "LOW":
        return False
    if semantic_uncertainty == "HIGH":
        return True
    if semantic_uncertainty == "MEDIUM" and downstream_impact == "HIGH":
        return True
    return False


def assess_clarification_impact(
    human: HumanMeaningCanonical,
    context: ResolvedContext,
    derived: DerivedSpecView,
    semantic_result: SemanticRevalidationResult,
) -> ClarificationImpactAssessment:
    alternatives = _alternatives_from_context(context)
    uncertainty = assess_semantic_uncertainty(human, context)
    impact = assess_downstream_impact(human, context, derived, alternatives)
    leading = _leading_interpretation(context, alternatives)

    needed = needs_early_clarification(
        semantic_uncertainty=uncertainty,
        downstream_impact=impact,
        semantic_decision=semantic_result.decision,
    )
    high_impact_alone_forces = (
        needed and uncertainty == "LOW" and impact == "HIGH"
    )

    reason = ""
    if semantic_result.decision == "NEED_HUMAN":
        needed = True
        reason = CLARIFICATION_REASON_AMBIGUOUS_REFERENCE
        if uncertainty == "LOW":
            uncertainty = "HIGH"
    elif needed:
        reason = (
            CLARIFICATION_REASON_HIGH_REWORK_RISK
            if uncertainty == "MEDIUM" and impact == "HIGH"
            else CLARIFICATION_REASON_UNCERTAINTY
        )

    choices = _build_choices(leading, alternatives) if needed else []
    explanation = (
        _clarification_reason_explanation_nl(
            uncertainty=uncertainty,
            impact=impact,
            reason=reason,
            leading=leading,
        )
        if needed
        else ""
    )

    return ClarificationImpactAssessment(
        semantic_uncertainty=uncertainty,
        downstream_impact=impact,
        clarification_needed=needed,
        clarification_reason=reason,
        leading_interpretation=leading,
        interpretation_alternatives=alternatives,
        choices=choices,
        clarification_reason_explanation=explanation,
        high_impact_alone_forces_human=high_impact_alone_forces,
    )


def attach_clarification_assessment(
    result: SemanticRevalidationResult,
    human: HumanMeaningCanonical,
    context: ResolvedContext,
    derived: DerivedSpecView,
) -> SemanticRevalidationResult:
    assessment = assess_clarification_impact(human, context, derived, result)
    result.clarification = assessment.as_dict()
    return result


def blocks_implementation_entry(result: SemanticRevalidationResult) -> bool:
    from ai_tool.requirement_semantic_revalidation import blocks_implementation

    if blocks_implementation(result.decision):
        return True
    clar = result.clarification or {}
    return bool(clar.get("clarification_needed"))
