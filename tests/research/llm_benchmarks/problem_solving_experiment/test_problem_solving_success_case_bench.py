"""成功事例探索の入力・マッピング確認。実 LLM は呼ばない。"""

from __future__ import annotations

from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import (
    problem_solving_success_case_bench as bench,
    problem_solving_success_case_fixture as fixture,
    problem_solving_success_case_mapping as mapping,
)


def test_fixture_traceback_is_main_only():
    captured = fixture.capture_traceback()
    assert captured["ok"] is True
    assert "IndexError" in captured["traceback"]
    assert "main.py" in captured["traceback"]
    assert "rows[2]" in captured["traceback"]
    helper_src = fixture.HELPER_PY.read_text(encoding="utf-8")
    config_src = fixture.CONFIG_PY.read_text(encoding="utf-8")
    assert "FIELD_COUNT" not in captured["traceback"]
    assert helper_src.strip() not in captured["traceback"]
    assert config_src.strip() not in captured["traceback"]


def test_initial_prompt_excludes_helper_and_config_source():
    built = fixture.build_initial_prompt()
    assert built["traceback_capture_ok"] is True
    assert "Do not fix the problem yet." in built["prompt"]
    assert "Analyze the problem below." in built["prompt"]
    assert "helper.py" not in built["prompt"]
    assert "config.py" not in built["prompt"]
    assert built["helper_leaked_in_prompt"] is False
    assert built["config_leaked_in_prompt"] is False
    assert "def load_rows" not in built["prompt"]
    assert "FIELD_COUNT" not in built["prompt"]
    assert "Do not use tools" not in built["prompt"]
    assert "choose a tool" not in built["prompt"].lower()
    assert "read_file" not in built["prompt"]


def test_mapping_reads_named_file_near_request():
    chosen, info = mapping.next_mapping(
        "The list length is unknown. I need to read helper.py to see how rows is built."
    )
    assert chosen is not None
    assert chosen["tool_selected"] == "read_file"
    assert chosen["tool_arguments"]["path"].endswith("helper.py")
    assert info["vague_without_file"] is False


def test_mapping_does_not_fetch_on_fact_restatement():
    chosen, info = mapping.next_mapping(
        "The IndexError occurred in main.py when accessing a list index that is out of range."
    )
    assert chosen is None
    reasons = [item["reason"] for item in info["unmapped"]]
    assert "filename_mentioned_without_request" in reasons


def test_mapping_rejects_vague_code_request():
    chosen, info = mapping.next_mapping("More code and logs are needed to debug this.")
    assert chosen is None
    assert info["vague_without_file"] is True


def test_run_one_maps_helper_then_stops_without_tools_kwarg(monkeypatch):
    seen = []
    replies = [
        "I need to inspect helper.py because rows may come from another module.",
        "FIELD_COUNT appears to truncate the list. No further files are required.",
    ]

    def fake_chat(**kwargs):
        seen.append(
            {
                **kwargs,
                "messages": [dict(message) for message in kwargs["messages"]],
            }
        )
        assert "tools" not in kwargs
        content = replies[min(len(seen) - 1, len(replies) - 1)]
        return SimpleNamespace(message=SimpleNamespace(content=content))

    monkeypatch.setattr(bench, "chat", fake_chat)
    from tools.system.config import get_llm_profile

    record = bench.run_one("deepseek-coder-v2:16b", get_llm_profile())
    assert record["call_ok"] is True
    assert record["final"]["repair_executed"] is False
    assert record["final"]["test_result"] == "NOT_RUN"
    assert record["turns"][0]["tool_selected"] == "read_file"
    assert record["turns"][0]["tool_arguments"]["path"].endswith("helper.py")
    assert record["turns"][0]["tool_result"]["ok"] is True
    assert "load_rows" in json_text(record["turns"][0]["tool_result"])
    assert record["turns"][1]["tool_selected"] is None
    assert seen[0]["model"] == "deepseek-coder-v2:16b"
    assert "Tool result:" in seen[1]["messages"][-1]["content"]


def json_text(payload):
    import json

    return json.dumps(payload, ensure_ascii=False)
