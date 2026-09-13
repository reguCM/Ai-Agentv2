"""Tests for broader success-class evaluation."""
from __future__ import annotations

from ai_tool.web_tool_broader_success_class_evaluation import (
    architecture_options_broader,
    broader_dataset_v2,
    classify_layers,
    compute_failure_rates,
    decide_production_change,
    run_broader_success_class_evaluation,
)
from ai_tool.web_tool_success_class_accuracy_evaluation import SuccessClassCaseResult


def test_broader_dataset_covers_categories():
    ds = broader_dataset_v2(include_live=True)
    cats = {c.category for c in ds}
    for req in ("entity", "numeric", "temporal", "scope", "english", "non_wikipedia", "negative"):
        assert req in cats
    assert len(ds) >= 20


def test_layer_separation_web_vs_llm():
    cr = SuccessClassCaseResult(
        "x", "basic_facts", "l", False, "SEARCH_FAILED", None, 0,
        "cannot", "cannot", "SKIPPED", [], [], {}, "production_mirror", True,
    )
    layers = classify_layers(cr, loop_agg={"overall": "SEARCH_FAILED", "layers": {"search": "FAILED"}})
    assert layers.web_failure is True
    assert layers.llm_failure is False
    assert layers.failure_layer == "SEARCH"


def test_llm_failure_only_when_web_success():
    cr = SuccessClassCaseResult(
        "y", "numeric", "l", True, "SUCCESS", True, 100,
        "wrong", "wrong", "Numeric Error", [], [], {}, "production_mirror", False,
        expect_correct=True, taxonomy_control=False,
    )
    layers = classify_layers(cr, loop_agg={"overall": "SUCCESS", "layers": {
        "search": "SUCCESS", "fetch": "SUCCESS", "extraction": "READY", "evidence": "AVAILABLE",
    }})
    assert layers.llm_failure is True
    assert layers.web_failure is False


def test_decide_stop_no_change_high_accuracy():
    rates = {
        "accuracy_rate": 0.9,
        "numeric_error_rate": 0.05,
        "llm_failure_count": 1,
        "expected_correct_success_class_count": 10,
    }
    baseline = {"golden_pass": True}
    opts = architecture_options_broader(rates, {})
    decision, sel, _why, _rej, mech = decide_production_change(rates, baseline, opts)
    assert decision == "STOP_NO_CHANGE"
    assert sel == "OPT0_NO_CHANGE"
    assert mech == "NOT_RECOMMENDED"


def test_architecture_has_opt6_opt7():
    opts = architecture_options_broader({"accuracy_rate": 0.8}, {})
    ids = {o["id"] for o in opts}
    assert "OPT6_POST_LLM_VERIFY" in ids
    assert "OPT7_EVAL_CANONICAL_BRIDGE" in ids


def test_run_broader_mock_only():
    result = run_broader_success_class_evaluation(include_live=False, llm_enabled=False)
    assert result["overall"] == "PASS"
    assert result["decision"] in ("STOP_NO_CHANGE", "INVESTIGATE_MORE", "PROPOSE_CHANGE")
    assert result["cases_run"] >= 15
