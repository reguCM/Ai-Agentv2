"""Problem Analysis 単体ベンチの保存確認。実 LLM は呼ばない。"""

from __future__ import annotations

from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import problem_analysis_bench as bench


def test_prompt_contains_failure_and_no_tool_catalog():
    failure = bench.CASES[0]["failure"]
    prompt = bench.build_prompt(failure)
    assert "cpu_status" in prompt
    assert "IndexError" in prompt
    assert "Do not use tools." in prompt
    assert "Do not propose code changes yet." in prompt
    assert "get_current_failure" not in prompt
    assert '{"action":"tool"' not in prompt


def test_run_case_saves_messages_raw_and_does_not_pass_tools(monkeypatch):
    seen = []

    def fake_chat(**kwargs):
        seen.append(kwargs)
        assert "tools" not in kwargs
        return SimpleNamespace(
            message=SimpleNamespace(content="Known: IndexError\nUnknown: which index")
        )

    monkeypatch.setattr(bench, "chat", fake_chat)
    record = bench.run_case(bench.CASES[0])
    assert record["experiment"] == "problem_analysis_standalone"
    assert record["raw_output"] == "Known: IndexError\nUnknown: which index"
    assert record["failure"]["error_type"] == "IndexError"
    assert record["prompt"] == record["observability"]["messages"][0]["content"]
    assert record["observability"]["messages"][0]["role"] == "user"
    assert record["observability"]["chat_kwargs"]["tools"] == "not_used"
    assert record["observability"]["chat_kwargs"]["tool_presentation"] == "none"
    assert record["observability"]["tools_used"] is False
    assert seen and "tools" not in seen[0]
    assert len(bench.CASES) == 5
