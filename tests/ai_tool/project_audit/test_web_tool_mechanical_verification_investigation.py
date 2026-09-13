"""Tests for mechanical verification investigation."""
from __future__ import annotations

from ai_tool.experimental.mechanical_verification.verifier import (
    extract_heuristic_evidence_facts,
    numeric_values_match,
    verify_answer,
)
from ai_tool.web_tool_mechanical_verification_investigation import (
    built_in_scenarios,
    run_mechanical_verification_investigation,
    run_scenario,
)
from ai_tool.web_tool_success_class_accuracy_evaluation import ExpectedFact


def test_verify_numeric_match():
    fact = ExpectedFact(
        "pop", "numeric", [r"275"], [r"275"],
        numeric_min=2_700_000, numeric_max=2_800_000,
    )
    r = verify_answer(
        "Population is about 2,750,000 residents.",
        "人口は約275万人です。",
        [fact],
    )
    assert r.overall == "MATCH"


def test_verify_numeric_mismatch():
    fact = ExpectedFact(
        "pop", "numeric", [r"275"], [r"275"],
        numeric_min=2_700_000, numeric_max=2_800_000,
    )
    r = verify_answer(
        "Population is about 2,750,000.",
        "人口は約1,900万人です。",
        [fact],
    )
    assert r.overall == "MISMATCH"


def test_verify_unsupported_no_evidence():
    fact = ExpectedFact(
        "pop", "numeric", [r"275"], [r"275"],
        numeric_min=2_700_000, numeric_max=2_800_000,
    )
    r = verify_answer(
        "No demographic data here.",
        "人口は約282万人です。",
        [fact],
    )
    assert r.overall in ("MISMATCH", "UNSUPPORTED", "UNKNOWN")


def test_entity_mismatch():
    fact = ExpectedFact(
        "cap", "entity", [r"東京"], [r"東京"],
        forbidden_patterns=[r"大阪.*首都"],
    )
    r = verify_answer(
        "首都は東京と認識されている。",
        "日本の首都は大阪市です。",
        [fact],
    )
    assert r.overall == "MISMATCH"


def test_year_mismatch():
    fact = ExpectedFact("y", "temporal", [r"1889"], [r"1889"])
    r = verify_answer("1889年に施行", "1950年に施行", [fact])
    assert r.overall == "MISMATCH"


def test_numeric_tolerance():
    assert numeric_values_match(2_750_000, [2_817_627], relative_tolerance=0.05)
    assert not numeric_values_match(1_900_000, [2_817_627], relative_tolerance=0.05)


def test_million_english():
    fact = ExpectedFact(
        "osaka_population_en", "numeric", [r"million"], [r"million"],
        numeric_min=2_500_000, numeric_max=2_900_000,
    )
    r = verify_answer(
        "approximately 2.75 million people",
        "about 2.75 million",
        [fact],
    )
    assert r.overall == "MATCH"


def test_heuristic_extraction():
    facts = extract_heuristic_evidence_facts("Population 2,750,000 in 2024.")
    assert facts["years"]
    assert facts["all_numerics"]


def test_builtin_scenarios_minimum():
    specs = built_in_scenarios()
    assert len(specs) >= 10


def test_builtin_v02_mismatch():
    s = next(x for x in built_in_scenarios() if x.scenario_id == "V02")
    r = run_scenario(s)
    assert r.observed_verdict == "MISMATCH"
    assert r.match


def test_investigation_runs():
    result = run_mechanical_verification_investigation(fetch_live_baseline=False)
    assert result["overall"] in ("PASS", "PARTIAL")
    assert result["conclusion"] in ("A_NO_BUILD", "B_DESIGN_ONLY", "C_EXPERIMENTAL", "D_WARNING", "E_OTHER")
    assert result["metrics"]["total_scenarios"] >= 10
