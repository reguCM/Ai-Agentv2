"""切り分け実験の入力確認。実 LLM は呼ばない。"""

from __future__ import annotations

from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import (
    problem_analysis_context_split_bench as bench,
    problem_analysis_context_split_cases as split,
)


def test_f1_is_failure_json_only():
    built = split.build_input("A", "F1")
    assert "IndexError" in built["prompt"]
    assert "traceback:" not in built["prompt"]
    assert "source:" not in built["prompt"]
    assert "conversation:" not in built["prompt"]
    assert "Known" not in built["prompt"]
    assert "Do not propose code changes yet." not in built["prompt"]


def test_a_has_real_traceback_and_source_b_does_not():
    a2 = split.build_input("A", "F2")
    a3 = split.build_input("A", "F3")
    a4 = split.build_input("A", "F4")
    assert "cpu_status.py" in a2["prompt"]
    assert "def cpu_status():" in a3["prompt"]
    assert "rows = ['LoadPercentage', '--------------']" in a4["prompt"]
    b2 = split.build_input("B", "F2")
    b3 = split.build_input("B", "F3")
    assert "traceback:\nNOT_RECORDED" in b2["prompt"]
    assert "source:\nNOT_RECORDED" in b3["prompt"]
    assert "def " not in b3["prompt"].split("source:", 1)[1]


def test_f5_reuses_previous_fixture_conversation_unmodified():
    a5 = split.build_input("A", "F5")
    assert "CPU状態を取得できるToolを作ってください。" in a5["prompt"]
    assert a5["extras"]["conversation_included"] is True
    assert "traceback:" not in a5["prompt"]


def test_run_one_does_not_pass_tools(monkeypatch):
    seen = []

    def fake_chat(**kwargs):
        seen.append(kwargs)
        assert "tools" not in kwargs
        return SimpleNamespace(message=SimpleNamespace(content="split out"))

    monkeypatch.setattr(bench, "chat", fake_chat)
    from tools.system.config import get_llm_profile

    record = bench.run_one("C", "F1", "deepseek-coder-v2:16b", get_llm_profile())
    assert record["condition"] == "F1"
    assert record["call_ok"] is True
    assert record["error"] is None
    assert seen[0]["model"] == "deepseek-coder-v2:16b"
    assert len(bench.LETTERS) * len(bench.COMPARE_MODELS) * len(split.CONDITIONS) == 50
