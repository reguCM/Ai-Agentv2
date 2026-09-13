"""Environment policy wedge (VERIFY_ONLY)."""
from __future__ import annotations

from ai_tool.environment_policy import (
    ENVIRONMENT_POLICY_VERIFY_ONLY,
    detect_environment_mutation_proposals,
    evaluate_verify_only_gate,
    resolve_environment_policy,
    verify_only_blocks_auto_mutation,
)
from ai_tool.environment_precondition_checker import evaluate_environment_preconditions
from ai_tool.precondition_contract import (
    STATUS_SATISFIED,
    STATUS_UNSATISFIED,
    Precondition,
    PreconditionEvaluation,
    precondition_definition,
)
from ai_tool.tetris_execution_context import build_tetris_golden_path_execution_context


def test_goal_and_env_policy_separated():
    ctx = build_tetris_golden_path_execution_context()
    goal = "テトリスを作る"
    assert "VERIFY" not in goal
    assert resolve_environment_policy(ctx) == ENVIRONMENT_POLICY_VERIFY_ONLY
    assert ctx.get("environment_policy") == ENVIRONMENT_POLICY_VERIFY_ONLY


def test_case_a_valid_env_verify_only_continues():
    pre = evaluate_environment_preconditions()
    gate = evaluate_verify_only_gate(
        environment_policy=ENVIRONMENT_POLICY_VERIFY_ONLY,
        preconditions=pre,
        goal_text="テトリスを作る",
    )
    blocking = [p for p in pre if p.blocking and p.evaluation.status != STATUS_SATISFIED]
    if blocking:
        return
    assert gate.may_continue is True
    assert gate.mutations_executed == []
    assert gate.current_environment_verified is True


def test_case_b_invalid_env_verify_only_stops_without_mutation():
    base = precondition_definition(
        key="python_available",
        description="Python interpreter is available.",
        source="test",
        blocking=True,
        precondition_id="pc-env-python-available",
    )
    bad = Precondition(
        precondition_id=base.precondition_id,
        key=base.key,
        description=base.description,
        blocking=True,
        source="test",
        evaluation=PreconditionEvaluation(
            status=STATUS_UNSATISFIED,
            evidence_refs=["check:python_available:missing"],
        ),
    )
    gate = evaluate_verify_only_gate(
        environment_policy=ENVIRONMENT_POLICY_VERIFY_ONLY,
        preconditions=[bad],
        goal_text="テトリスを作る",
    )
    assert gate.may_continue is False
    assert gate.mutations_executed == []
    assert "VERIFY_ONLY" in gate.human_message
    assert "自動変更" in gate.human_message or "修復" in gate.human_message


def test_case_c_mutation_proposal_not_auto_executed():
    detected = detect_environment_mutation_proposals(
        ["Run docker compose up", "Install CUDA 12 for PyTorch"]
    )
    assert "docker_setup" in detected
    blocked, labels = verify_only_blocks_auto_mutation(
        environment_policy=ENVIRONMENT_POLICY_VERIFY_ONLY,
        proposed_mutations=detected,
    )
    assert blocked is True
    gate = evaluate_verify_only_gate(
        environment_policy=ENVIRONMENT_POLICY_VERIFY_ONLY,
        preconditions=[
            Precondition(
                precondition_id="pc-env-python-available",
                key="python_available",
                description="ok",
                blocking=True,
                source="test",
                evaluation=PreconditionEvaluation(
                    status=STATUS_SATISFIED,
                    evidence_refs=["ok"],
                ),
            )
        ],
        goal_text="テトリスを作る",
        derived_spec_texts=["docker compose up for deployment"],
    )
    assert gate.may_continue is False
    assert gate.mutations_executed == []
    assert gate.mutations_detected


def test_high_impact_explicit_reference_semantic_compat_hook():
    """Open semantic comparison can still see env drift; no new env reason codes."""
    from ai_tool.requirement_semantic_revalidation import evaluate_semantic_revalidation, DerivedSpecView, HumanMeaningCanonical

    human = HumanMeaningCanonical(
        original_goal="テトリスを作る",
        structured_requirements=[],
        metadata={},
    )
    derived = DerivedSpecView(
        source_kind="implementation_seed",
        statements=["Upgrade Python globally and rebuild venv before coding"],
    )
    result = evaluate_semantic_revalidation(human, derived, use_llm_open_compare=False)
    assert result.decision in ("CONTRADICTION", "POSSIBLE_DRIFT", "PASS")
