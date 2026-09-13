"""Tests for success-class accuracy evaluation harness."""
from __future__ import annotations

from pathlib import Path

from ai_tool.agent_integration.production_agent_web_loop import make_e2e_trust_file
from ai_tool.web_tool_success_class_accuracy_evaluation import (
    aggregate_accuracy,
    architecture_options,
    classify_answer,
    extract_numeric_values,
    run_success_class_accuracy_evaluation,
    run_success_class_case,
    select_option,
    success_class_dataset,
    ExpectedFact,
    SuccessClassCaseResult,
)


def test_extract_numeric_values_man_yen():
    nums = extract_numeric_values("人口は約275万人です")
    assert any(2_700_000 <= n <= 2_800_000 for n in nums)


def test_classify_correct_numeric():
    fact = ExpectedFact(
        "pop",
        "numeric",
        [r"275"],
        [r"275"],
        numeric_min=2_700_000,
        numeric_max=2_800_000,
    )
    ans_class, claims, met, _ = classify_answer(
        "人口は約275万人（2,750,000人）です。",
        "Population is about 2,750,000 residents.",
        [fact],
    )
    assert ans_class == "Correct"
    assert met["pop"] is True
    assert claims


def test_classify_numeric_error():
    fact = ExpectedFact(
        "pop",
        "numeric",
        [r"275"],
        [r"275"],
        numeric_min=2_700_000,
        numeric_max=2_800_000,
    )
    ans_class, _, met, _ = classify_answer(
        "人口は約1,900万人です。",
        "Population is about 2,750,000.",
        [fact],
    )
    assert ans_class == "Numeric Error"
    assert met["pop"] is False


def test_classify_entity_error():
    fact = ExpectedFact(
        "capital",
        "entity",
        [r"東京"],
        [r"東京"],
        forbidden_patterns=[r"大阪.*首都"],
    )
    ans_class, _, _, _ = classify_answer(
        "日本の首都は大阪市です。",
        "首都は東京と認識されている。",
        [fact],
    )
    assert ans_class in ("Entity Error", "Contradiction")


def test_mock_case_m03_numeric_error(tmp_path: Path):
    trust = tmp_path / "trust.json"
    make_e2e_trust_file(trust)
    spec = next(c for c in success_class_dataset(include_live=False) if c.case_id == "SC-M03")
    from ai_tool.agent_integration.trial import make_mock_chat_fn

    result = run_success_class_case(
        spec,
        chat_fn=make_mock_chat_fn(spec.mock_scenario),
        model="mock",
        trust_path=trust,
    )
    assert result.web_success is True
    assert result.answer_class == "Numeric Error"


def test_dataset_has_minimum_categories():
    ds = success_class_dataset(include_live=True)
    cats = {c.category for c in ds}
    for required in (
        "basic_facts",
        "numeric_facts",
        "entity_facts",
        "temporal_facts",
        "comparative",
        "multi_fact",
        "negative",
    ):
        assert required in cats
    assert len(ds) >= 10


def test_aggregate_accuracy():
    results = [
        SuccessClassCaseResult(
            "a", "basic_facts", "x", True, "SUCCESS", True, 100,
            "ok", "ok", "Correct", [], [], {}, "production_mirror", False,
            expect_correct=True,
        ),
        SuccessClassCaseResult(
            "b", "numeric_facts", "y", True, "SUCCESS", True, 100,
            "bad", "bad", "Numeric Error", [], [], {}, "production_mirror", False,
            expect_correct=False, taxonomy_control=True,
        ),
    ]
    agg = aggregate_accuracy(results)
    assert agg["web_success_count"] == 2
    assert agg["correct_count"] == 1
    assert agg["accuracy_rate"] == 1.0
    assert agg["taxonomy_detection_rate"] == 1.0


def test_select_stop_a_high_accuracy():
    agg = {
        "accuracy_rate": 0.9,
        "llm_answer_expected_correct_count": 10,
        "correct_count": 9,
        "live_accuracy_rate": 0.8,
        "live_success_class_count": 5,
        "taxonomy_detection_rate": 1.0,
        "failure_taxonomy": {"Numeric Error": 0, "Unsupported Addition": 0},
    }
    opts = architecture_options(agg)
    sel, _why, stop, mechanical, _ = select_option(agg, opts)
    assert sel == "OPT0_NO_ACTION"
    assert stop == "STOP_A"
    assert mechanical == "Not Recommended"


def test_run_evaluation_mock_only():
    result = run_success_class_accuracy_evaluation(include_live=False, llm_enabled=False)
    assert result["llm_answer_expected_correct_count"] >= 5
    assert result["web_success_count"] >= 7
    assert result["taxonomy_detection_rate"] == 1.0
    assert result["overall"] == "PASS"
