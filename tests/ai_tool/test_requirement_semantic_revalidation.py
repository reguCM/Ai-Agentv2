"""Requirement Semantic Revalidation v0 regression tests (T1–T15)."""
from __future__ import annotations

import pytest

from ai_tool.chat_interface.requirement_resolution import (
    CONSTRAINT_SUBTYPE_PROHIBITION,
    DISPOSITION_CONSTRAINT,
    DISPOSITION_GOAL,
    DISPOSITION_PREFERENCE,
    MATERIALITY_BLOCKS,
    PHASE_REQUIREMENTS_RESOLVED,
    RESOLVED,
    RequirementResolutionBundle,
    StructuredRequirement,
)
from ai_tool.chat_interface.semantic_revalidation_gate import (
    blocks_implementation_entry,
    build_derived_spec_for_implementation_entry,
    run_implementation_semantic_revalidation,
)
from ai_tool.requirement_semantic_revalidation import blocks_implementation
from ai_tool.requirement_semantic_revalidation import (
    DERIVED_MANDATORY_PREFERENCE,
    DERIVED_OTHER_MATERIAL_DRIFT,
    DERIVED_POLICY_SAFE_AUTO_UNKNOWN,
    DERIVED_POLICY_UNCONDITIONAL_HUMAN,
    DERIVED_SCOPE_POSSIBLY_ALL_DANGEROUS,
    HUMAN_POLICY_BLOCK_DANGEROUS_ONLY_AUTO_SAFE,
    HUMAN_SCOPE_DANGEROUS_ONLY,
    HUMAN_SOFT_PREFERENCE,
    DerivedSpecView,
    HumanMeaningCanonical,
    ResolvedContext,
    evaluate_semantic_revalidation,
    human_meaning_from_bundle,
)


def _req(
    rid: str,
    text: str,
    *,
    disposition: str = DISPOSITION_GOAL,
    materiality: str = MATERIALITY_BLOCKS,
) -> StructuredRequirement:
    return StructuredRequirement(
        requirement_id=rid,
        source_text=text,
        source_span=[0, len(text)],
        disposition=disposition,
        resolution_status=RESOLVED,
        provenance="user_explicit",
        materiality=materiality,
    )


def _bundle(goal: str, *rows: StructuredRequirement) -> RequirementResolutionBundle:
    return RequirementResolutionBundle(
        original_goal=goal,
        structured_requirements=list(rows),
        requirement_resolution_phase=PHASE_REQUIREMENTS_RESOLVED,
    )


def _human_meta(**kwargs) -> HumanMeaningCanonical:
    return HumanMeaningCanonical(
        original_goal=kwargs.pop("goal", ""),
        structured_requirements=kwargs.pop("rows", []),
        metadata=dict(kwargs),
    )


def test_t1_git_v1_v2_intent_inversion_contradiction():
    goal = "Block dangerous git ops only; auto safe; do not delegate safety judgment to human"
    human = _human_meta(
        goal=goal,
        rows=[_req("r1", goal)],
        policy_intent=HUMAN_POLICY_BLOCK_DANGEROUS_ONLY_AUTO_SAFE,
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=[
            "Require human approval for every push regardless of safety verification",
        ],
        metadata={"policy_profile": DERIVED_POLICY_UNCONDITIONAL_HUMAN},
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    assert result.decision == "CONTRADICTION"
    assert "INTENT_DIRECTION_MISMATCH" in result.reason_codes
    assert "AI_GOAL_SUBSTITUTION" in result.reason_codes


def test_t2_correct_safe_block_unknown_pass():
    goal = "Block dangerous only; auto safe; human only when unknown"
    human = _human_meta(
        goal=goal,
        rows=[_req("r1", goal)],
        policy_intent=HUMAN_POLICY_BLOCK_DANGEROUS_ONLY_AUTO_SAFE,
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=[
            "SAFE → AUTO; KNOWN_UNSAFE → BLOCK; UNKNOWN → NEED_HUMAN",
        ],
        metadata={"policy_profile": DERIVED_POLICY_SAFE_AUTO_UNKNOWN},
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    assert result.decision == "PASS"


def test_t3_scope_only_expansion_contradiction():
    human = _human_meta(
        goal="Stop dangerous operations only",
        rows=[_req("r1", "Stop dangerous operations only")],
        scope_intent=HUMAN_SCOPE_DANGEROUS_ONLY,
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Stop all possibly dangerous operations"],
        metadata={"scope_profile": DERIVED_SCOPE_POSSIBLY_ALL_DANGEROUS},
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    assert result.decision == "CONTRADICTION"
    assert "SCOPE_OR_QUANTIFIER_DRIFT" in result.reason_codes


def test_t4_preference_hardening_detected():
    human = HumanMeaningCanonical(
        original_goal="Prefer faster execution when possible",
        structured_requirements=[
            StructuredRequirement(
                requirement_id="p1",
                source_text="Prefer faster execution when possible",
                source_span=[0, 10],
                disposition=DISPOSITION_PREFERENCE,
                resolution_status=RESOLVED,
                provenance="user_explicit",
                materiality=MATERIALITY_BLOCKS,
            )
        ],
        preferences=["Prefer faster execution when possible"],
        metadata={"preference_strength": HUMAN_SOFT_PREFERENCE},
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Performance optimization is mandatory; slow configs are prohibited"],
        metadata={"preference_strength": DERIVED_MANDATORY_PREFERENCE},
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    assert result.decision == "CONTRADICTION"
    assert "PREFERENCE_HARDENING" in result.reason_codes


def test_t5_material_requirement_omission():
    bundle = _bundle(
        "Deliver A, B, and C",
        _req("a", "Deliver A"),
        _req("b", "Deliver B"),
        _req("c", "Deliver material deliverable C with audit trail"),
    )
    human = human_meaning_from_bundle(bundle)
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Deliver A", "Deliver B"],
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    assert result.decision == "CONTRADICTION"
    assert "REQUIREMENT_OMISSION" in result.reason_codes


def test_t6_stopped_vs_completed_continuation():
    human = HumanMeaningCanonical(
        original_goal="Resume from prior STOPPED task",
        structured_requirements=[_req("r1", "Resume STOPPED task run_a")],
    )
    ctx = ResolvedContext(reference_target="run_a", reference_state="STOPPED")
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Start new run from last COMPLETED task run_b"],
    )
    result = evaluate_semantic_revalidation(
        human, derived, resolved_context=ctx, use_llm_open_compare=False
    )
    assert result.decision == "CONTRADICTION"
    assert "CONTINUATION_STATE_MISMATCH" in result.reason_codes


def test_t7_ambiguous_continuation_need_human():
    human = HumanMeaningCanonical(
        original_goal="Continue previous work",
        structured_requirements=[_req("r1", "Continue previous work")],
    )
    ctx = ResolvedContext(
        ambiguous_reference=True,
        candidates=[{"id": "run_a", "state": "STOPPED"}, {"id": "run_b", "state": "STOPPED"}],
    )
    derived = DerivedSpecView(source_kind="implementation_seed", statements=["resume"])
    result = evaluate_semantic_revalidation(
        human, derived, resolved_context=ctx, use_llm_open_compare=False
    )
    assert result.decision == "NEED_HUMAN"


def test_t8_japanese_english_mixed_continuation():
    human = HumanMeaningCanonical(
        original_goal="前回 STOPPED した task の続きから resume して",
        structured_requirements=[
            _req("r1", "前回 STOPPED した task の続きから resume して")
        ],
    )
    ctx = ResolvedContext(reference_target="run_a", reference_state="STOPPED")
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Start new run from last COMPLETED task"],
    )
    result = evaluate_semantic_revalidation(
        human, derived, resolved_context=ctx, use_llm_open_compare=False
    )
    assert result.decision == "CONTRADICTION"
    assert "CONTINUATION_STATE_MISMATCH" in result.reason_codes


def test_t9_equivalent_paraphrase_pass():
    human = HumanMeaningCanonical(
        original_goal="Auto-continue operations confirmed safe",
        structured_requirements=[_req("r1", "Auto-continue operations confirmed safe")],
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=[
            "Operations classified SAFE continue without human confirmation",
        ],
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    assert result.decision == "PASS"


def test_t10_other_semantic_drift():
    human = HumanMeaningCanonical(
        original_goal="Ship weekly status reports",
        structured_requirements=[_req("r1", "Ship weekly status reports")],
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Ship monthly status reports"],
        metadata={
            "material_drift": DERIVED_OTHER_MATERIAL_DRIFT,
            "material_drift_summary": "Ship monthly status reports",
            "material_drift_detail": "cadence changed from weekly to monthly",
        },
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    assert result.decision == "CONTRADICTION"
    assert "OTHER_SEMANTIC_DRIFT" in result.reason_codes


def test_t11_contradiction_blocks_implementation():
    assert blocks_implementation("CONTRADICTION")


def test_t12_need_human_blocks_implementation():
    assert blocks_implementation("NEED_HUMAN")


def test_t13_pass_allows_implementation():
    bundle = _bundle("simple task", _req("r1", "simple task"))
    derived = build_derived_spec_for_implementation_entry(
        handoff_packet=None,
        completion_conditions=["simple task"],
    )
    result = run_implementation_semantic_revalidation(
        bundle, derived, use_llm_open_compare=False
    )
    assert result.decision == "PASS"
    assert not blocks_implementation(result.decision)


def test_t14_original_goal_immutable():
    bundle = _bundle("keep goal", _req("r1", "keep goal"))
    before = bundle.original_goal
    derived = DerivedSpecView(source_kind="implementation_seed", statements=["keep goal"])
    evaluate_semantic_revalidation(
        human_meaning_from_bundle(bundle), derived, use_llm_open_compare=False
    )
    assert bundle.original_goal == before


def test_t15_premise_revalidation_module_separate():
    from ai_tool import decision_premise_revalidation as prem
    from ai_tool import requirement_semantic_revalidation as req_sem
    from ai_tool import revalidation_protocol as proto

    assert hasattr(prem, "evaluate_premise_revalidation")
    assert hasattr(req_sem, "evaluate_semantic_revalidation")
    assert hasattr(proto, "evaluate_semantic_revalidation_llm")
    assert req_sem.evaluate_semantic_revalidation is not proto.evaluate_semantic_revalidation_llm


def test_human_natural_language_contradiction_not_reason_codes_only():
    from ai_tool.chat_interface.semantic_revalidation_gate import semantic_revalidation_blocked_answer

    goal = "Block dangerous git ops only; auto safe"
    human = _human_meta(
        goal=goal,
        rows=[_req("r1", goal)],
        policy_intent=HUMAN_POLICY_BLOCK_DANGEROUS_ONLY_AUTO_SAFE,
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Require human approval for every push regardless of safety"],
        metadata={"policy_profile": DERIVED_POLICY_UNCONDITIONAL_HUMAN},
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    message = semantic_revalidation_blocked_answer(result)
    assert result.decision == "CONTRADICTION"
    assert result.reason_codes
    assert "INTENT_DIRECTION_MISMATCH" not in message
    assert "CONTEXT_REFERENCE_DRIFT" not in message
    expl = result.human_explanation or {}
    assert expl.get("human_summary")
    assert goal in (expl.get("human_requirement_text") or expl.get("human_requirement") or "")
    assert "Require human approval" in message or "human approval" in message.casefold()
    assert "違い" in message or "一致" in message


def test_human_natural_language_need_human():
    human = HumanMeaningCanonical(
        original_goal="前回の続き",
        structured_requirements=[_req("r1", "前回の続き")],
    )
    ctx = ResolvedContext(
        ambiguous_reference=True,
        candidates=[{"id": "a", "state": "STOPPED"}, {"id": "b", "state": "STOPPED"}],
    )
    result = evaluate_semantic_revalidation(
        human, DerivedSpecView(source_kind="x", statements=["resume"]), resolved_context=ctx, use_llm_open_compare=False
    )
    from ai_tool.requirement_semantic_explanation import format_human_facing_message

    message = format_human_facing_message(result)
    assert result.decision == "NEED_HUMAN"
    assert "NEED_HUMAN" not in message
    assert "前回の続き" in message
    expl = result.human_explanation or {}
    assert expl.get("next_action_explanation")


def test_explanation_does_not_change_decision():
    from ai_tool.requirement_semantic_explanation import with_human_facing_explanation

    human = _human_meta(
        goal="Stop dangerous operations only",
        rows=[_req("r1", "Stop dangerous operations only")],
        scope_intent=HUMAN_SCOPE_DANGEROUS_ONLY,
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Stop all possibly dangerous operations"],
        metadata={"scope_profile": DERIVED_SCOPE_POSSIBLY_ALL_DANGEROUS},
    )
    before = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    after = with_human_facing_explanation(before)
    assert before.decision == after.decision
    assert before.reason_codes == after.reason_codes


def test_evaluator_error_fail_closed():
    human = HumanMeaningCanonical(original_goal="x", structured_requirements=[])

    def boom(**_kw):
        raise RuntimeError("llm down")

    derived = DerivedSpecView(source_kind="implementation_seed", statements=["x"])
    result = evaluate_semantic_revalidation(
        human, derived, chat_fn=boom, use_llm_open_compare=True
    )
    assert result.decision == "REVALIDATION_ERROR"
    assert blocks_implementation(result.decision)
