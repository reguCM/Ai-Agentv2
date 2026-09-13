"""Problem Analysis 自由分析ベンチ。実 LLM は呼ばない。"""

from __future__ import annotations

from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import (
    problem_analysis_bench as guided,
    problem_analysis_free_bench as free,
)


FORBIDDEN_PROMPT_LABELS = (
    "Known",
    "Unknown",
    "Inconsistency",
    "Hypothesis",
    "Information needed",
    "Next steps",
    "Investigation Action",
    "Solution",
    "Root cause",
)


def test_free_prompt_has_no_category_list():
    prompt = free.build_prompt(guided.CASES[0]["failure"])
    assert "cpu_status" in prompt
    assert "Do not use tools." in prompt
    assert "Do not propose code changes yet." in prompt
    for label in FORBIDDEN_PROMPT_LABELS:
        assert label not in prompt
    assert "- what is known" not in prompt
    assert "what is unknown" not in prompt.lower()


def test_free_uses_same_failures_as_guided():
    assert [c["id"] for c in free.CASES] == [c["id"] for c in guided.CASES]
    assert [c["failure"] for c in free.CASES] == [c["failure"] for c in guided.CASES]


def test_free_run_case_saves_and_does_not_pass_tools(monkeypatch):
    seen = []

    def fake_chat(**kwargs):
        seen.append(kwargs)
        assert "tools" not in kwargs
        return SimpleNamespace(message=SimpleNamespace(content="free analysis text"))

    monkeypatch.setattr(free, "chat", fake_chat)
    record = free.run_case(free.CASES[-1])
    assert record["experiment"] == "problem_analysis_free"
    assert record["call_ok"] is True
    assert record["temperature"] == 0.0
    assert record["raw_output"] == "free analysis text"
    assert record["failure"]["tool_name"] == "unknown_tool"
    assert "Known" not in record["prompt"]
    assert record["observability"]["messages"][0]["content"] == record["prompt"]
    assert record["observability"]["chat_kwargs"]["tools"] == "not_used"
    assert seen and "tools" not in seen[0]
