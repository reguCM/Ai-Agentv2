"""Requirement Semantic Revalidation v0 — Human canonical meaning vs Derived Spec."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from ai_tool.chat_interface.requirement_resolution import (
    DISPOSITION_GOAL,
    MATERIALITY_BLOCKS,
    RESOLVED,
    RequirementResolutionBundle,
    StructuredRequirement,
)
from ai_tool.llm_json_parse import parse_llm_json_response
from ai_tool.revalidation_protocol import utc_now_iso

SemanticDecision = str  # PASS | CONTRADICTION | POSSIBLE_DRIFT | NEED_HUMAN | REVALIDATION_ERROR

KNOWN_REASON_CODES = frozenset(
    {
        "REQUIREMENT_OMISSION",
        "INTENT_DIRECTION_MISMATCH",
        "AI_GOAL_SUBSTITUTION",
        "SCOPE_OR_QUANTIFIER_DRIFT",
        "CONSTRAINT_STRENGTH_DRIFT",
        "PREFERENCE_HARDENING",
        "CONTEXT_REFERENCE_DRIFT",
        "CONTINUATION_STATE_MISMATCH",
        "OTHER_SEMANTIC_DRIFT",
    }
)

DIFFERENCE_CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "human_evidence",
                    "derived_evidence",
                    "semantic_difference",
                    "materiality",
                    "confidence",
                    "suggested_reason_code",
                ],
                "properties": {
                    "human_evidence": {"type": "string"},
                    "derived_evidence": {"type": "string"},
                    "semantic_difference": {"type": "string"},
                    "materiality": {"type": "string", "enum": ["material", "informational"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "suggested_reason_code": {"type": "string"},
                    "requirement_id": {"type": "string"},
                },
            },
        }
    },
}

HUMAN_POLICY_BLOCK_DANGEROUS_ONLY_AUTO_SAFE = "block_dangerous_only_auto_safe"
DERIVED_POLICY_UNCONDITIONAL_HUMAN = "unconditional_human_approval"
DERIVED_POLICY_SAFE_AUTO_UNKNOWN = "safe_auto_unknown"
HUMAN_SCOPE_DANGEROUS_ONLY = "dangerous_operations_only"
DERIVED_SCOPE_POSSIBLY_ALL_DANGEROUS = "possibly_dangerous_all_stopped"
HUMAN_SOFT_PREFERENCE = "soft_preference_present"
DERIVED_MANDATORY_PREFERENCE = "preference_hardened_to_mandatory"
DERIVED_OTHER_MATERIAL_DRIFT = "other_material_semantic_drift"


@dataclass
class ResolvedContext:
    reference_target: str | None = None
    reference_state: str | None = None
    resume_point: str | None = None
    ambiguous_reference: bool = False
    candidates: list[dict[str, str]] = field(default_factory=list)
    reference_explicit: bool = False
    semantic_uncertainty: str | None = None
    downstream_impact_if_wrong: str | None = None
    leading_interpretation_id: str | None = None
    interpretation_alternatives: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> ResolvedContext:
        if not isinstance(data, Mapping):
            return cls()
        ambiguous = bool(data.get("ambiguous_reference"))
        raw_candidates = data.get("candidates") or []
        candidates = [dict(c) for c in raw_candidates if isinstance(c, Mapping)]
        raw_alts = data.get("interpretation_alternatives") or []
        alternatives = [dict(a) for a in raw_alts if isinstance(a, Mapping)]
        return cls(
            reference_target=str(data.get("reference_target") or "").strip() or None,
            reference_state=str(data.get("reference_state") or "").strip() or None,
            resume_point=str(data.get("resume_point") or "").strip() or None,
            ambiguous_reference=ambiguous or len(candidates) > 1,
            candidates=candidates,
            reference_explicit=bool(data.get("reference_explicit")),
            semantic_uncertainty=str(data.get("semantic_uncertainty") or "").strip() or None,
            downstream_impact_if_wrong=str(data.get("downstream_impact_if_wrong") or "").strip()
            or None,
            leading_interpretation_id=str(data.get("leading_interpretation_id") or "").strip()
            or None,
            interpretation_alternatives=alternatives,
        )


@dataclass
class DerivedSpecView:
    """Machine-facing view of AI-derived implementation specification."""

    source_kind: str
    statements: list[str]
    requirement_ids_addressed: list[str] = field(default_factory=list)
    continuation: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def joined_text(self) -> str:
        return "\n".join(s for s in self.statements if s).casefold()


@dataclass
class HumanMeaningCanonical:
    original_goal: str
    structured_requirements: list[StructuredRequirement]
    resolved_constraints: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    prohibitions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def material_requirements(self) -> list[StructuredRequirement]:
        return [
            r
            for r in self.structured_requirements
            if r.materiality == MATERIALITY_BLOCKS and r.resolution_status == RESOLVED
        ]

    def summary_lines(self) -> list[str]:
        lines = [self.original_goal]
        for row in self.structured_requirements:
            label = row.normalized_meaning or row.source_text
            lines.append(f"[{row.requirement_id}] {label}")
        lines.extend(self.resolved_constraints)
        lines.extend(self.preferences)
        lines.extend(self.prohibitions)
        return [ln for ln in lines if str(ln).strip()]


@dataclass
class SemanticDifferenceCandidate:
    human_evidence: str
    derived_evidence: str
    semantic_difference: str
    materiality: str
    confidence: str
    suggested_reason_code: str
    requirement_id: str | None = None
    source: str = "deterministic"

    def as_dict(self) -> dict[str, Any]:
        return {
            "human_evidence": self.human_evidence,
            "derived_evidence": self.derived_evidence,
            "semantic_difference": self.semantic_difference,
            "materiality": self.materiality,
            "confidence": self.confidence,
            "suggested_reason_code": self.suggested_reason_code,
            "requirement_id": self.requirement_id,
            "source": self.source,
        }


@dataclass
class SemanticRevalidationResult:
    decision: SemanticDecision
    reason_codes: list[str]
    candidates: list[SemanticDifferenceCandidate]
    human_explanation: dict[str, str] | None = None
    evaluated_at: str = ""
    details: str = ""
    clarification: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "candidates": [c.as_dict() for c in self.candidates],
            "human_explanation": self.human_explanation,
            "evaluated_at": self.evaluated_at,
            "details": self.details,
        }
        if self.clarification is not None:
            payload["clarification"] = self.clarification
        return payload


def semantic_revalidation_enabled() -> bool:
    raw = (os.environ.get("AI_AGENT_SEMANTIC_REVALIDATION") or "on").strip().lower()
    return raw not in ("0", "off", "false", "disable", "disabled")


def human_meaning_from_bundle(
    bundle: RequirementResolutionBundle,
    *,
    resolved_constraints: Sequence[str] | None = None,
    preferences: Sequence[str] | None = None,
    prohibitions: Sequence[str] | None = None,
) -> HumanMeaningCanonical:
    constraints: list[str] = []
    prefs: list[str] = []
    prohibs: list[str] = []
    for row in bundle.structured_requirements:
        if row.resolution_status != RESOLVED:
            continue
        label = (row.normalized_meaning or row.source_text).strip()
        if not label:
            continue
        if row.disposition == "CONSTRAINT":
            if row.constraint_subtype == "prohibition":
                prohibs.append(label)
            else:
                constraints.append(label)
        elif row.disposition == "PREFERENCE":
            prefs.append(label)
    constraints.extend(list(resolved_constraints or []))
    prefs.extend(list(preferences or []))
    prohibs.extend(list(prohibitions or []))
    return HumanMeaningCanonical(
        original_goal=bundle.original_goal,
        structured_requirements=list(bundle.structured_requirements),
        resolved_constraints=constraints,
        preferences=prefs,
        prohibitions=prohibs,
    )


def derived_spec_from_handoff(handoff_packet: Mapping[str, Any]) -> DerivedSpecView:
    statements: list[str] = []
    goal = handoff_packet.get("goal") or {}
    if isinstance(goal, Mapping):
        title = str(goal.get("title") or "").strip()
        summary = str(goal.get("summary") or "").strip()
        if title:
            statements.append(title)
        if summary:
            statements.append(summary)
    for row in handoff_packet.get("acceptance_criteria") or []:
        if isinstance(row, Mapping):
            st = str(row.get("statement") or "").strip()
            if st:
                statements.append(st)
    for row in handoff_packet.get("implementation_tasks") or []:
        if isinstance(row, Mapping):
            title = str(row.get("title") or "").strip()
            if title:
                statements.append(title)
    for row in handoff_packet.get("human_gates") or []:
        if isinstance(row, Mapping):
            desc = str(row.get("description") or row.get("gate") or "").strip()
            if desc:
                statements.append(desc)
    scope = handoff_packet.get("scope") or {}
    if isinstance(scope, Mapping):
        for item in scope.get("in_scope") or []:
            token = str(item).strip()
            if token:
                statements.append(token)
    cont = {}
    meta = handoff_packet.get("metadata") or {}
    if isinstance(meta, Mapping):
        cont = {
            k: str(meta.get(k) or "")
            for k in ("reference_target", "reference_state", "resume_point")
            if meta.get(k)
        }
    return DerivedSpecView(
        source_kind="goal_handoff",
        statements=statements,
        continuation=cont,
        metadata={"handoff_id": str(handoff_packet.get("handoff_id") or "")},
    )


def derived_spec_from_implementation_seed(
    *,
    completion_conditions: Sequence[str],
    explicit_constraints: Sequence[str] | None = None,
    extra_statements: Sequence[str] | None = None,
    continuation: Mapping[str, str] | None = None,
    source_kind: str = "implementation_seed",
) -> DerivedSpecView:
    statements = [str(s).strip() for s in completion_conditions if str(s).strip()]
    statements.extend(str(s).strip() for s in (explicit_constraints or []) if str(s).strip())
    statements.extend(str(s).strip() for s in (extra_statements or []) if str(s).strip())
    return DerivedSpecView(
        source_kind=source_kind,
        statements=statements,
        continuation=dict(continuation or {}),
    )


def _text_present(haystack: str, needle: str) -> bool:
    n = (needle or "").strip().casefold()
    if not n:
        return True
    return n in (haystack or "").casefold()


def run_deterministic_checks(
    human: HumanMeaningCanonical,
    derived: DerivedSpecView,
    context: ResolvedContext,
) -> list[SemanticDifferenceCandidate]:
    found: list[SemanticDifferenceCandidate] = []
    derived_text = derived.joined_text()

    if context.reference_target and context.reference_state:
        d_target = (derived.continuation.get("reference_target") or "").strip()
        d_state = (derived.continuation.get("reference_state") or "").strip().casefold()
        expected_state = context.reference_state.casefold()
        if d_target and d_target != context.reference_target:
            found.append(
                SemanticDifferenceCandidate(
                    human_evidence=f"reference_target={context.reference_target} state={context.reference_state}",
                    derived_evidence=f"reference_target={d_target} state={d_state or '(missing)'}",
                    semantic_difference="参照対象の run/task が一致しない",
                    materiality="material",
                    confidence="high",
                    suggested_reason_code="CONTEXT_REFERENCE_DRIFT",
                )
            )
        elif d_state and expected_state and d_state != expected_state:
            found.append(
                SemanticDifferenceCandidate(
                    human_evidence=f"state={context.reference_state}",
                    derived_evidence=f"state={d_state}",
                    semantic_difference="continuation 対象の状態が一致しない",
                    materiality="material",
                    confidence="high",
                    suggested_reason_code="CONTINUATION_STATE_MISMATCH",
                )
            )
        elif not d_target and not _state_token_present(derived_text, expected_state):
            if (
                _state_token_present(derived_text, "completed")
                and expected_state == "stopped"
            ):
                found.append(
                    SemanticDifferenceCandidate(
                        human_evidence=human.original_goal,
                        derived_evidence=derived.statements[0] if derived.statements else derived_text[:200],
                        semantic_difference="continuation state does not match resolved STOPPED reference",
                        materiality="material",
                        confidence="high",
                        suggested_reason_code="CONTINUATION_STATE_MISMATCH",
                    )
                )

    for row in human.material_requirements():
        label = (row.normalized_meaning or row.source_text).strip()
        if not label:
            continue
        if (
            row.disposition == DISPOSITION_GOAL
            and label.casefold() == human.original_goal.strip().casefold()
        ):
            continue
        if row.requirement_id in derived.requirement_ids_addressed:
            continue
        if _text_present(derived_text, label):
            continue
        significant = [p for p in _token_chunks(label) if len(p) >= 5]
        if significant:
            matched = sum(1 for part in significant if _text_present(derived_text, part))
            if matched / len(significant) >= 0.5:
                continue
        elif len(label) > 12 and not any(
            _text_present(derived_text, part) for part in _token_chunks(label)
        ):
            pass
        else:
            continue
        if len(label) > 8:
            found.append(
                SemanticDifferenceCandidate(
                    human_evidence=label,
                    derived_evidence="(not found in derived spec)",
                    semantic_difference="material requirement が Derived Spec に反映されていない",
                    materiality="material",
                    confidence="high",
                    suggested_reason_code="REQUIREMENT_OMISSION",
                    requirement_id=row.requirement_id,
                )
            )

    _append_policy_profile_deterministic(human, derived, found)
    return found


def _token_chunks(text: str) -> list[str]:
    parts = re.split(r"[\s、。,.;/]+", text)
    return [p for p in parts if len(p) >= 4]


def _state_token_present(text: str, state: str) -> bool:
    return state.casefold() in (text or "").casefold()


def _append_policy_profile_deterministic(
    human: HumanMeaningCanonical,
    derived: DerivedSpecView,
    found: list[SemanticDifferenceCandidate],
) -> None:
    human_policy = str(human.metadata.get("policy_intent") or "").strip()
    derived_policy = str(derived.metadata.get("policy_profile") or "").strip()
    human_scope = str(human.metadata.get("scope_intent") or "").strip()
    derived_scope = str(derived.metadata.get("scope_profile") or "").strip()

    if (
        human_policy == HUMAN_POLICY_BLOCK_DANGEROUS_ONLY_AUTO_SAFE
        and derived_policy == DERIVED_POLICY_UNCONDITIONAL_HUMAN
    ):
        found.append(
            SemanticDifferenceCandidate(
                human_evidence=human.original_goal,
                derived_evidence="; ".join(derived.statements[:3]),
                semantic_difference="safe operations should auto-continue but derived spec requires unconditional human approval",
                materiality="material",
                confidence="high",
                suggested_reason_code="INTENT_DIRECTION_MISMATCH",
            )
        )
        found.append(
            SemanticDifferenceCandidate(
                human_evidence=human.original_goal,
                derived_evidence="; ".join(derived.statements[:3]),
                semantic_difference="human goal replaced with AI safety-approval goal",
                materiality="material",
                confidence="high",
                suggested_reason_code="AI_GOAL_SUBSTITUTION",
            )
        )

    if (
        human_scope == HUMAN_SCOPE_DANGEROUS_ONLY
        and derived_scope == DERIVED_SCOPE_POSSIBLY_ALL_DANGEROUS
    ):
        found.append(
            SemanticDifferenceCandidate(
                human_evidence=human.original_goal,
                derived_evidence=derived.statements[0] if derived.statements else derived.joined_text()[:160],
                semantic_difference="scope expanded beyond dangerous-only constraint",
                materiality="material",
                confidence="high",
                suggested_reason_code="SCOPE_OR_QUANTIFIER_DRIFT",
            )
        )

    if (
        human.metadata.get("preference_strength") == HUMAN_SOFT_PREFERENCE
        and derived.metadata.get("preference_strength") == DERIVED_MANDATORY_PREFERENCE
    ):
        found.append(
            SemanticDifferenceCandidate(
                human_evidence="; ".join(human.preferences[:2]) or human.original_goal,
                derived_evidence="; ".join(derived.statements[:2]),
                semantic_difference="preference hardened into mandatory constraint",
                materiality="material",
                confidence="high",
                suggested_reason_code="PREFERENCE_HARDENING",
            )
        )

    if derived.metadata.get("material_drift") == DERIVED_OTHER_MATERIAL_DRIFT:
        drift = derived.metadata.get("material_drift_summary") or derived.statements[0]
        found.append(
            SemanticDifferenceCandidate(
                human_evidence=human.original_goal,
                derived_evidence=str(drift),
                semantic_difference=str(
                    derived.metadata.get("material_drift_detail")
                    or "material semantic difference outside known taxonomy"
                ),
                materiality="material",
                confidence="high",
                suggested_reason_code="OTHER_SEMANTIC_DRIFT",
            )
        )


def propose_open_semantic_differences_llm(
    human: HumanMeaningCanonical,
    derived: DerivedSpecView,
    *,
    chat_fn: Callable[..., Any],
    model: str,
) -> list[SemanticDifferenceCandidate]:
    prompt = _open_comparison_prompt(human, derived)
    response = chat_fn(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=[],
        format=DIFFERENCE_CANDIDATE_SCHEMA,
        execution_profile="structured_output",
        options={"temperature": 0, "num_predict": 1200},
    )
    payload = parse_llm_json_response(response)
    raw_candidates = payload.get("candidates") if isinstance(payload, Mapping) else []
    out: list[SemanticDifferenceCandidate] = []
    for row in raw_candidates or []:
        if not isinstance(row, Mapping):
            continue
        code = str(row.get("suggested_reason_code") or "OTHER_SEMANTIC_DRIFT").strip()
        if code not in KNOWN_REASON_CODES:
            code = "OTHER_SEMANTIC_DRIFT"
        out.append(
            SemanticDifferenceCandidate(
                human_evidence=str(row.get("human_evidence") or ""),
                derived_evidence=str(row.get("derived_evidence") or ""),
                semantic_difference=str(row.get("semantic_difference") or ""),
                materiality=str(row.get("materiality") or "informational"),
                confidence=str(row.get("confidence") or "low"),
                suggested_reason_code=code,
                requirement_id=str(row.get("requirement_id") or "") or None,
                source="llm",
            )
        )
    return out


def _open_comparison_prompt(human: HumanMeaningCanonical, derived: DerivedSpecView) -> str:
    human_block = json.dumps(human.summary_lines(), ensure_ascii=False, indent=2)
    derived_block = json.dumps(derived.statements, ensure_ascii=False, indent=2)
    return (
        "SEMANTIC_REVALIDATION_V0_OPEN_COMPARE\n"
        "Compare Human canonical meaning vs Derived Spec.\n"
        "Extract material semantic differences only. Do not judge design quality.\n"
        "Do not rationalize AI changes as safer or better.\n"
        "Japanese and English mixed text is normal.\n"
        "Use semantic concepts (scope, strength, intent, reference, state) not surface keyword rules.\n"
        "Return JSON matching the schema.\n\n"
        f"Human:\n{human_block}\n\nDerived:\n{derived_block}\n"
    )


def validate_difference_candidates(
    candidates: Sequence[SemanticDifferenceCandidate],
    human: HumanMeaningCanonical,
    derived: DerivedSpecView,
) -> list[SemanticDifferenceCandidate]:
    human_blob = "\n".join(human.summary_lines()).casefold()
    derived_blob = derived.joined_text()
    valid: list[SemanticDifferenceCandidate] = []
    for cand in candidates:
        he = (cand.human_evidence or "").strip()
        de = (cand.derived_evidence or "").strip()
        if not he or not de:
            continue
        if he.casefold() not in human_blob and not _evidence_anchored(he, human):
            continue
        if de != "(not found in derived spec)" and de.casefold() not in derived_blob:
            if not _evidence_anchored(de, human, derived=derived):
                continue
        if cand.requirement_id:
            ids = {r.requirement_id for r in human.structured_requirements}
            if cand.requirement_id not in ids:
                continue
        valid.append(cand)
    return valid


def _evidence_anchored(
    evidence: str,
    human: HumanMeaningCanonical,
    *,
    derived: DerivedSpecView | None = None,
) -> bool:
    ev = evidence.casefold()
    for ln in human.summary_lines():
        if len(ev) >= 8 and ev in ln.casefold():
            return True
    if derived:
        for ln in derived.statements:
            if len(ev) >= 8 and ev in ln.casefold():
                return True
    return False


def aggregate_decision(
    candidates: Sequence[SemanticDifferenceCandidate],
    *,
    context: ResolvedContext,
) -> SemanticRevalidationResult:
    if context.ambiguous_reference and not candidates:
        return SemanticRevalidationResult(
            decision="NEED_HUMAN",
            reason_codes=["CONTEXT_REFERENCE_DRIFT"],
            candidates=[],
            human_explanation=_build_human_explanation(
                human_evidence="参照先が複数候補",
                derived_evidence="(unresolved)",
                difference="resume 対象を一意に特定できない",
                question="どの run / task を参照しますか？",
            ),
            evaluated_at=utc_now_iso(),
            details="ambiguous_reference",
        )

    material = [c for c in candidates if c.materiality == "material"]
    if not material:
        return SemanticRevalidationResult(
            decision="PASS",
            reason_codes=[],
            candidates=list(candidates),
            evaluated_at=utc_now_iso(),
        )

    codes = sorted({c.suggested_reason_code for c in material})
    high = [c for c in material if c.confidence == "high"]
    contradiction_codes = {
        "INTENT_DIRECTION_MISMATCH",
        "AI_GOAL_SUBSTITUTION",
        "CONTINUATION_STATE_MISMATCH",
        "REQUIREMENT_OMISSION",
    }
    if high and any(c.suggested_reason_code in contradiction_codes for c in high):
        top = high[0]
        return SemanticRevalidationResult(
            decision="CONTRADICTION",
            reason_codes=codes,
            candidates=list(candidates),
            human_explanation=_build_human_explanation(
                human_evidence=top.human_evidence,
                derived_evidence=top.derived_evidence,
                difference=top.semantic_difference,
                question="このまま実装を開始せず、仕様を再確認します。",
            ),
            evaluated_at=utc_now_iso(),
        )

    if any(c.confidence == "high" for c in material):
        top = material[0]
        return SemanticRevalidationResult(
            decision="CONTRADICTION",
            reason_codes=codes,
            candidates=list(candidates),
            human_explanation=_build_human_explanation(
                human_evidence=top.human_evidence,
                derived_evidence=top.derived_evidence,
                difference=top.semantic_difference,
                question="Derived Spec を Human 要求に合わせて修正してください。",
            ),
            evaluated_at=utc_now_iso(),
        )

    top = material[0]
    return SemanticRevalidationResult(
        decision="POSSIBLE_DRIFT",
        reason_codes=codes,
        candidates=list(candidates),
        human_explanation=_build_human_explanation(
            human_evidence=top.human_evidence,
            derived_evidence=top.derived_evidence,
            difference=top.semantic_difference,
            question="この差分を許容するか、Derived Spec を修正するか判断してください。",
        ),
        evaluated_at=utc_now_iso(),
    )


def _build_human_explanation(
    *,
    human_evidence: str,
    derived_evidence: str,
    difference: str,
    question: str,
) -> dict[str, str]:
    return {
        "human_requirement": human_evidence,
        "ai_spec": derived_evidence,
        "difference": difference,
        "question": question,
    }


def evaluate_semantic_revalidation(
    human: HumanMeaningCanonical,
    derived: DerivedSpecView,
    *,
    resolved_context: ResolvedContext | None = None,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
    use_llm_open_compare: bool = True,
) -> SemanticRevalidationResult:
    from ai_tool.requirement_semantic_clarification import attach_clarification_assessment
    from ai_tool.requirement_semantic_explanation import with_human_facing_explanation

    ctx = resolved_context or ResolvedContext()

    def _finalize(result: SemanticRevalidationResult) -> SemanticRevalidationResult:
        result = attach_clarification_assessment(result, human, ctx, derived)
        return with_human_facing_explanation(result)

    if ctx.ambiguous_reference or len(ctx.candidates) > 1:
        return _finalize(
            SemanticRevalidationResult(
                decision="NEED_HUMAN",
                reason_codes=["CONTEXT_REFERENCE_DRIFT"],
                candidates=[],
                human_explanation=_build_human_explanation(
                    human_evidence=human.original_goal,
                    derived_evidence="(ambiguous reference)",
                    difference="どの run / task を参照するか、複数候補があり確定できません。",
                    question="再開または参照したい task / run はどれですか？",
                ),
                evaluated_at=utc_now_iso(),
                details="ambiguous_reference",
            )
        )
    try:
        deterministic = run_deterministic_checks(human, derived, ctx)
        llm_candidates: list[SemanticDifferenceCandidate] = []
        if use_llm_open_compare and chat_fn is not None:
            llm_candidates = propose_open_semantic_differences_llm(
                human, derived, chat_fn=chat_fn, model=model
            )
        merged = deterministic + llm_candidates
        validated = validate_difference_candidates(merged, human, derived)
        if ctx.ambiguous_reference:
            return _finalize(aggregate_decision(validated, context=ctx))
        return _finalize(aggregate_decision(validated, context=ctx))
    except Exception as exc:  # noqa: BLE001 — fail-closed
        return _finalize(
            SemanticRevalidationResult(
                decision="REVALIDATION_ERROR",
                reason_codes=["REVALIDATION_ERROR"],
                candidates=[],
                human_explanation=_build_human_explanation(
                    human_evidence=human.original_goal,
                    derived_evidence="(evaluator failure)",
                    difference=f"{type(exc).__name__}: {exc}",
                    question="意味の再確認を再実行するか、仕様を手動で確認してください。",
                ),
                evaluated_at=utc_now_iso(),
                details=str(exc),
            )
        )


def blocks_implementation(decision: str) -> bool:
    return decision in ("CONTRADICTION", "POSSIBLE_DRIFT", "NEED_HUMAN", "REVALIDATION_ERROR")
