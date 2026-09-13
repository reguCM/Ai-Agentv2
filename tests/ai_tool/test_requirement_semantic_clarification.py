"""Clarification impact / rework risk (v0)."""
from __future__ import annotations

from ai_tool.chat_interface.semantic_revalidation_gate import (
    blocks_implementation_entry,
    semantic_revalidation_blocked_answer,
)
from ai_tool.requirement_semantic_clarification import (
    assess_clarification_impact,
    needs_early_clarification,
)
from ai_tool.requirement_semantic_explanation import format_human_facing_message
from ai_tool.requirement_semantic_revalidation import (
    DerivedSpecView,
    HumanMeaningCanonical,
    ResolvedContext,
    SemanticRevalidationResult,
    evaluate_semantic_revalidation,
)


def _human(goal: str, **meta) -> HumanMeaningCanonical:
    return HumanMeaningCanonical(
        original_goal=goal,
        structured_requirements=[],
        metadata=dict(meta),
    )


def _pass_result() -> SemanticRevalidationResult:
    return SemanticRevalidationResult(decision="PASS", reason_codes=[], candidates=[])


def test_case_a_explicit_high_impact_no_clarification():
    """run_123 step4 — HIGH impact but LOW uncertainty → continue."""
    human = _human("run_123 の step4 から再開して")
    ctx = ResolvedContext(
        reference_target="run_123",
        resume_point="step4",
        reference_state="STOPPED",
        reference_explicit=True,
        downstream_impact_if_wrong="HIGH",
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Resume run_123 from step4"],
        metadata={"downstream_impact": "HIGH"},
    )
    result = evaluate_semantic_revalidation(
        human, derived, resolved_context=ctx, use_llm_open_compare=False
    )
    assert result.decision == "PASS"
    clar = result.clarification or {}
    assert clar.get("semantic_uncertainty") == "LOW"
    assert clar.get("downstream_impact") == "HIGH"
    assert clar.get("clarification_needed") is False
    assert clar.get("high_impact_alone_forces_human") is False
    assert not blocks_implementation_entry(result)


def test_case_b_vague_continuation_high_rework_early_confirm():
    human = _human("前回の続き", continuation_reference_vague=True)
    ctx = ResolvedContext(
        interpretation_alternatives=[
            {
                "id": "stopped",
                "label": "前回 STOPPED した task の途中から再開",
                "downstream_impact": "HIGH",
            },
            {
                "id": "completed",
                "label": "前回 COMPLETED した task の次工程から開始",
                "downstream_impact": "HIGH",
            },
        ],
        leading_interpretation_id="stopped",
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Continue prior work"],
    )
    result = evaluate_semantic_revalidation(
        human, derived, resolved_context=ctx, use_llm_open_compare=False
    )
    clar = result.clarification or {}
    assert clar.get("semantic_uncertainty") == "MEDIUM"
    assert clar.get("downstream_impact") == "HIGH"
    assert clar.get("clarification_needed") is True
    assert blocks_implementation_entry(result)
    message = semantic_revalidation_blocked_answer(result)
    assert "手戻り" in message or "確認" in message
    assert "STOPPED" in message or "stopped" in message.casefold()
    choices = clar.get("choices") or []
    assert any(c.get("kind") == "free_input" for c in choices)


def test_case_c_low_rework_no_over_ask():
    human = _human("UIはシンプルに")
    ctx = ResolvedContext(
        interpretation_alternatives=[
            {"id": "a", "label": "minimal chrome", "downstream_impact": "LOW"},
            {"id": "b", "label": "compact layout", "downstream_impact": "LOW"},
        ],
    )
    derived = DerivedSpecView(source_kind="implementation_seed", statements=["Simple UI"])
    result = evaluate_semantic_revalidation(
        human, derived, resolved_context=ctx, use_llm_open_compare=False
    )
    clar = result.clarification or {}
    assert clar.get("clarification_needed") is False
    assert not blocks_implementation_entry(result)


def test_high_impact_alone_does_not_force_human():
    assert needs_early_clarification(
        semantic_uncertainty="LOW",
        downstream_impact="HIGH",
        semantic_decision="PASS",
    ) is False


def test_explanation_does_not_change_clarification_decision():
    human = _human("前回の続き", continuation_reference_vague=True)
    ctx = ResolvedContext(
        interpretation_alternatives=[
            {"id": "a", "label": "alt A", "downstream_impact": "HIGH"},
            {"id": "b", "label": "alt B", "downstream_impact": "HIGH"},
        ],
    )
    derived = DerivedSpecView(source_kind="implementation_seed", statements=["x"])
    result = evaluate_semantic_revalidation(
        human, derived, resolved_context=ctx, use_llm_open_compare=False
    )
    needed_before = (result.clarification or {}).get("clarification_needed")
    msg = format_human_facing_message(result)
    needed_after = (result.clarification or {}).get("clarification_needed")
    assert needed_before == needed_after
    assert "semantic_uncertainty" not in msg


def test_clarification_reason_natural_language_present():
    assessment = assess_clarification_impact(
        _human("前回の続き"),
        ResolvedContext(
            interpretation_alternatives=[
                {"id": "a", "label": "A", "downstream_impact": "HIGH"},
                {"id": "b", "label": "B", "downstream_impact": "HIGH"},
            ],
        ),
        DerivedSpecView(source_kind="x", statements=[]),
        _pass_result(),
    )
    assert assessment.clarification_reason_explanation
    assert "HIGH" not in assessment.clarification_reason_explanation
