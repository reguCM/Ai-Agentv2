"""Chat Runtime gate: Requirement Semantic Revalidation before implementation seed."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from ai_tool.chat_interface.requirement_resolution import (
    PHASE_REQUIREMENTS_RESOLVED,
    RequirementResolutionBundle,
    project_to_runtime_adoption,
)
from ai_tool.requirement_semantic_explanation import format_human_facing_message
from ai_tool.revalidation_protocol import utc_now_iso
from ai_tool.requirement_semantic_clarification import blocks_implementation_entry
from ai_tool.requirement_semantic_revalidation import (
    DerivedSpecView,
    ResolvedContext,
    SemanticRevalidationResult,
    derived_spec_from_handoff,
    derived_spec_from_implementation_seed,
    evaluate_semantic_revalidation,
    human_meaning_from_bundle,
    semantic_revalidation_enabled,
)


def build_derived_spec_for_implementation_entry(
    *,
    handoff_packet: Mapping[str, Any] | None,
    completion_conditions: Sequence[str],
    explicit_constraints: Sequence[str] | None = None,
    extra_statements: Sequence[str] | None = None,
) -> DerivedSpecView:
    if handoff_packet is not None:
        return derived_spec_from_handoff(handoff_packet)
    return derived_spec_from_implementation_seed(
        completion_conditions=completion_conditions,
        explicit_constraints=explicit_constraints,
        extra_statements=extra_statements,
    )


def resolved_context_from_handoff(
    handoff_packet: Mapping[str, Any] | None,
) -> ResolvedContext:
    if not isinstance(handoff_packet, Mapping):
        return ResolvedContext()
    meta = handoff_packet.get("metadata")
    if not isinstance(meta, Mapping):
        return ResolvedContext()
    return ResolvedContext.from_mapping(meta.get("semantic_resolved_context"))


def run_implementation_semantic_revalidation(
    bundle: RequirementResolutionBundle,
    derived: DerivedSpecView,
    *,
    resolved_context: ResolvedContext | None = None,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "fake",
    use_llm_open_compare: bool = True,
) -> SemanticRevalidationResult:
    if bundle.requirement_resolution_phase != PHASE_REQUIREMENTS_RESOLVED:
        return SemanticRevalidationResult(
            decision="REVALIDATION_ERROR",
            reason_codes=["REVALIDATION_ERROR"],
            candidates=[],
            details="requirements_not_resolved",
            evaluated_at=utc_now_iso(),
        )
    human = human_meaning_from_bundle(bundle)
    return evaluate_semantic_revalidation(
        human,
        derived,
        resolved_context=resolved_context,
        chat_fn=chat_fn,
        model=model,
        use_llm_open_compare=use_llm_open_compare,
    )


def should_run_semantic_revalidation_gate(
    *,
    resolution_bundle: RequirementResolutionBundle | None,
) -> bool:
    if not semantic_revalidation_enabled():
        return False
    if resolution_bundle is None:
        return False
    return resolution_bundle.requirement_resolution_phase == PHASE_REQUIREMENTS_RESOLVED


def preview_implementation_adoption(
    bundle: RequirementResolutionBundle,
    requirement_conditions: Sequence[str] | None = None,
) -> tuple[list[str], list[str]]:
    adopted = list(requirement_conditions or [])
    constraints: list[str] = []
    if bundle.structured_requirements:
        projected, constraints = project_to_runtime_adoption(bundle.structured_requirements)
        if projected:
            adopted = projected
    return adopted, constraints


def semantic_revalidation_blocked_answer(result: SemanticRevalidationResult) -> str:
    return format_human_facing_message(result, include_debug=False)


__all__ = [
    "blocks_implementation_entry",
    "build_derived_spec_for_implementation_entry",
    "preview_implementation_adoption",
    "resolved_context_from_handoff",
    "run_implementation_semantic_revalidation",
    "semantic_revalidation_blocked_answer",
    "should_run_semantic_revalidation_gate",
]
