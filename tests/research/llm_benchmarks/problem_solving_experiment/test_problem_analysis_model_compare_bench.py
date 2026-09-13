"""モデル比較ベンチ。実 LLM は呼ばない。既存 minimal ハーネスは変更しない。"""

from __future__ import annotations

from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import (
    problem_analysis_minimal_bench as minimal,
    problem_analysis_model_compare_bench as compare,
)


def test_compare_reuses_minimal_prompt_and_cases():
    assert compare.PROMPT_TEMPLATE == minimal.PROMPT_TEMPLATE
    assert [c["failure"] for c in compare.CASES] == [c["failure"] for c in minimal.CASES]
    assert [item["ollama_name"] for item in compare.COMPARE_MODELS] == [
        "deepseek-coder-v2:16b",
        "qwen3:14b",
    ]
    prompt = compare.build_prompt(compare.CASES[0]["failure"])
    assert prompt == minimal.build_prompt(minimal.CASES[0]["failure"])
    assert "what can be understood" not in prompt.lower()


def test_compare_run_case_passes_requested_model_without_tools(monkeypatch):
    seen = []

    def fake_chat(**kwargs):
        seen.append(kwargs)
        assert "tools" not in kwargs
        assert kwargs["model"] == "qwen3:14b"
        return SimpleNamespace(message=SimpleNamespace(content="qwen text"))

    monkeypatch.setattr(compare, "chat", fake_chat)
    record = compare.run_case(compare.CASES[0], "qwen3:14b")
    assert record["model"] == "qwen3:14b"
    assert record["temperature"] == 0.0
    assert record["call_ok"] is True
    assert record["raw_output"] == "qwen text"
    assert record["prompt"] == record["observability"]["messages"][0]["content"]
    assert record["observability"]["thinking_observed"] is False
    assert seen and "tools" not in seen[0]
    assert compare._case_file(compare.CASES[0]) == "case_A.json"
