from pathlib import Path
from ai_tool.input_interpretation.benchmark import evaluate_case, render_markdown, run_benchmark

FIXTURE = Path(__file__).parents[2] / "fixtures" / "input_interpretation_cases.json"
LAYERED_FIXTURE = FIXTURE.parent / "input_interpretation"

def test_dirty_input_benchmark_covers_required_families():
    text = FIXTURE.read_text(encoding="utf-8")
    for marker in ("実際にこの文章をｙｐんで", "duplicate", "voice", "dialect", "constraint", "mixed"):
        assert marker in text

def test_benchmark_separates_checks_and_preserves_meaning():
    report = run_benchmark(FIXTURE)
    assert report["case_count"] >= 20
    # Typo recovery is deliberately not hard-coded into the baseline. These
    # cases remain visible failures until a dedicated adapter is supplied.
    assert report["failed"] == 5
    typo = next(item for item in report["cases"] if item["case_id"] == "representative-typo")
    assert typo["passed"] is False
    assert typo["checks"]["acceptable_interpretation"] is False
    row = next(item for item in report["cases"] if item["case_id"] == "mixed-negation-long")
    assert row["meaning_preserved"] is True
    assert set(row["checks"]) >= {"acceptable_interpretation", "constraint_preservation", "negation_preservation", "execution_order_preservation", "false_removal", "redundancy_removal"}

def test_markdown_is_human_comparable():
    markdown = render_markdown(run_benchmark(FIXTURE))
    assert "Reduction" in markdown
    assert "Availability" in markdown
    assert "representative-typo" in markdown

def test_layered_benchmark_has_three_levels_pairs_and_all_evaluation_types():
    report = run_benchmark(LAYERED_FIXTURE)
    assert report["case_count"] == 22
    assert all(report["level_scores"][level]["total"] > 0 for level in ("MICRO", "CONTEXTUAL", "REALISTIC"))
    assert set(report["evaluation_type_counts"]) == {"HARD_GOLD", "ACCEPTABLE_SET", "RUBRIC", "HUMAN_ADJUDICATED"}
    pairs = {row["pair_id"] for row in report["cases"] if row["pair_id"]}
    assert {"typo", "voice", "dialect", "ambiguity", "negation", "order"} <= pairs

def test_ambiguous_case_requires_clarification_and_does_not_overcommit():
    report = run_benchmark(LAYERED_FIXTURE)
    row = next(item for item in report["cases"] if item["case_id"] == "context_pronoun_ambiguous_001")
    assert row["result"]["request_ir"]["certainty"] == "AMBIGUOUS"
    assert row["result"]["request_ir"]["needs_clarification"] is True
    assert row["unsafe_overcommit"] is False
    assert row["passed"] is True

def test_provisional_is_not_promoted_to_known():
    report = run_benchmark(LAYERED_FIXTURE)
    row = next(item for item in report["cases"] if item["case_id"] == "context_provisional_001")
    assert row["result"]["request_ir"]["certainty"] == "PROVISIONAL"
    assert row["result"]["request_ir"]["assumptions"]
    assert row["passed"] is True

def test_critical_loss_forces_failure_even_with_high_partial_score():
    case = {
        "case_id": "critical-loss", "level": "MICRO", "evaluation_type": "RUBRIC", "input": "A.mdを読んで",
        "rubric": [
            {"field": "request_ir.operations", "expected": ["READ"], "importance": "MINOR", "weight": 99},
            {"field": "request_ir.negations", "expected": ["変更しない"], "importance": "CRITICAL", "weight": 1},
        ],
    }
    row = evaluate_case(case)
    assert row["score"] == 0.99
    assert row["critical_losses"] == ["request_ir.negations"]
    assert row["passed"] is False

def test_report_separates_capability_scores():
    report = run_benchmark(LAYERED_FIXTURE)
    assert set(report["capability_metrics"]) >= {"micro_diagnostic", "contextual_japanese", "realistic_agent", "hard_gold_accuracy", "critical_preservation", "ambiguity_handling", "unsafe_overcommit_count", "provisional_handling", "constraint_loss_count"}
    markdown = render_markdown(report)
    assert "Capability scores" in markdown and "HUMAN_ADJUDICATED" in markdown
