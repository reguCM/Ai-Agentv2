"""Problem Analysis 完全最小 Prompt ベンチ。実 LLM は呼ばない。"""

from __future__ import annotations

from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import (
    problem_analysis_bench as guided,
    problem_analysis_minimal_bench as minimal,
)


FORBIDDEN_SUBSTRINGS = (
    "known",
    "unknown",
    "inconsistency",
    "hypothesis",
    "cause",
    "root cause",
    "information needed",
    "investigate",
    "next steps",
    "solution",
    "repair",
    "evidence",
    "facts",
    "recommendations",
    "safe resolution",
    "what can be understood",
    "what cannot be determined",
    "carefully",
)


def test_minimal_prompt_is_only_analyze_do_not_fix_do_not_use_tools():
    template = minimal.PROMPT_TEMPLATE.lower()
    for phrase in FORBIDDEN_SUBSTRINGS:
        assert phrase not in template
    prompt = minimal.build_prompt(guided.CASES[0]["failure"])
    assert prompt.startswith("Analyze the failure.")
    assert "Do not fix the problem." in prompt
    assert "Do not use tools." in prompt
    assert "cpu_status" in prompt
    assert "IndexError" in prompt


def test_minimal_uses_same_failures_as_guided():
    assert [c["id"] for c in minimal.CASES] == [c["id"] for c in guided.CASES]
    assert [c["failure"] for c in minimal.CASES] == [c["failure"] for c in guided.CASES]


def test_minimal_run_case_saves_and_does_not_pass_tools(monkeypatch):
    seen = []

    def fake_chat(**kwargs):
        seen.append(kwargs)
        assert "tools" not in kwargs
        return SimpleNamespace(message=SimpleNamespace(content="minimal analysis text"))

    monkeypatch.setattr(minimal, "chat", fake_chat)
    record = minimal.run_case(minimal.CASES[0])
    assert record["experiment"] == "problem_analysis_minimal"
    assert record["call_ok"] is True
    assert record["temperature"] == 0.0
    assert record["raw_output"] == "minimal analysis text"
    assert "what can be understood" not in record["prompt"].lower()
    assert record["observability"]["messages"][0]["content"] == record["prompt"]
    assert record["observability"]["chat_kwargs"]["tools"] == "not_used"
    assert seen and "tools" not in seen[0]
