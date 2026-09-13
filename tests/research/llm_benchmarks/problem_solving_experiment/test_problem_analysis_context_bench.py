"""文脈増加実験の入力確認。実 LLM は呼ばない。"""

from __future__ import annotations

from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import (
    problem_analysis_context_bench as bench,
    problem_analysis_context_cases as cases,
)


def test_prompt_has_no_analysis_taxonomy():
    prompt = cases.build_prompt(cases.CASES[0], 1)
    lowered = prompt.lower()
    for phrase in (
        "known",
        "unknown",
        "inconsistency",
        "what can be understood",
        "information needed",
        "next steps",
        "investigate",
        "root cause",
    ):
        assert phrase not in lowered
    assert prompt.startswith("Analyze the problem below.")
    assert "Do not fix the problem." in prompt
    assert "Do not use tools." in prompt


def test_level5_6_do_not_invent_source_for_synthetic_cases():
    for case in cases.CASES[1:]:
        ctx5 = cases.build_context(case, 5)
        ctx6 = cases.build_context(case, 6)
        assert "traceback: NOT_RECORDED" in ctx5
        assert "Source:\nNOT_RECORDED" in ctx6
        assert "def " not in ctx6


def test_case_a_level5_6_use_fixture_source_and_traceback():
    a = cases.CASES[0]
    ctx5 = cases.build_context(a, 5)
    ctx6 = cases.build_context(a, 6)
    assert "IndexError" in ctx5
    assert "cpu_status.py" in ctx5
    assert "return_value: NOT_RECORDED" in ctx5
    assert "validation: NOT_RECORDED" in ctx5
    assert "def cpu_status():" in ctx6
    assert "rows = ['LoadPercentage', '--------------']" in ctx6


def test_run_case_does_not_pass_tools(monkeypatch):
    seen = []

    def fake_chat(**kwargs):
        seen.append(kwargs)
        assert "tools" not in kwargs
        return SimpleNamespace(message=SimpleNamespace(content="ctx analysis"))

    monkeypatch.setattr(bench, "chat", fake_chat)
    from tools.system.config import get_llm_profile

    profile = get_llm_profile()
    record = bench.run_case(cases.CASES[0], 1, profile, "deepseek-coder-v2:16b")
    assert record["case"] == "A"
    assert record["level"] == 1
    assert record["call_ok"] is True
    assert record["raw_output"] == "ctx analysis"
    assert record["context"] in record["prompt"]
    assert seen and "tools" not in seen[0]
    assert len(cases.CASES) * len(bench.LEVELS) == 30
