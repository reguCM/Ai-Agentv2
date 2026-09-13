"""調査連鎖条件実験。実 LLM は呼ばない。"""

from __future__ import annotations

from types import SimpleNamespace

from research.llm_benchmarks.problem_solving_experiment import (
    chain_conditions_bench as bench,
    chain_conditions_cases as cases,
    chain_conditions_mapping as mapping,
)


def test_f1_traceback_includes_helper_f2_does_not():
    f1 = cases.build_prompt(cases.RUN_CASES[0])
    f2 = cases.build_prompt(cases.RUN_CASES[1])
    assert f1["case_id"] == "F1_S1"
    assert f1["traceback_capture_ok"] is True
    assert "helper.py" in f1["traceback"]
    assert "pick_status" in f1["traceback"]
    assert f2["traceback_capture_ok"] is True
    assert "helper.py" not in f2["traceback"]
    assert "rows[2]" in f2["traceback"]
    assert "def load_rows" not in f2["prompt"]


def test_source_levels_do_not_leak_config():
    s2 = cases.build_prompt(next(item for item in cases.RUN_CASES if item["id"] == "F2_S2"))
    s3 = cases.build_prompt(next(item for item in cases.RUN_CASES if item["id"] == "F2_S3"))
    assert "from helper import load_rows" in s2["prompt"]
    assert "def load_rows" not in s2["prompt"]
    assert s2["bodies_leaked_that_should_not"]["helper.py"] is False
    assert s2["bodies_leaked_that_should_not"]["config.py"] is False
    assert "def load_rows" in s3["prompt"]
    assert "FIELD_COUNT = 2" not in s3["prompt"]
    assert s3["bodies_leaked_that_should_not"]["config.py"] is False


def test_f6_is_keyerror_not_indexerror():
    built = cases.build_prompt(next(item for item in cases.RUN_CASES if item["id"] == "F6_S1"))
    assert built["failure"]["error_type"] == "KeyError"
    assert "KeyError" in built["traceback"]
    assert "data[\"cpu\"]" in built["traceback"] or "data['cpu']" in built["traceback"]
    assert "METRIC_KEY" not in built["prompt"]


def test_prompt_has_no_investigation_instruction():
    built = cases.build_prompt(cases.RUN_CASES[0])
    assert "Do not use tools." in built["prompt"]
    assert "Do not fix the problem." in built["prompt"]
    assert "helper.pyを読め" not in built["prompt"]
    assert "不足情報を列挙" not in built["prompt"]
    assert "choose a tool" not in built["prompt"].lower()


def test_investigation_text_is_kept_raw():
    text = "Inspect helper.py because rows may come from load_rows()."
    record = mapping.llm_investigation_record(text)
    assert record["raw_output"] == text
    assert text in record["raw_request_excerpts"]
    assert "helper.py" in record["py_filenames_as_written"]


def test_mapping_does_not_search_english_words():
    text = "The file may fail and we should inspect helper.py next."
    chosen, info = mapping.next_read_mapping(
        text,
        fixture_files={"helper.py": "fixtures/helper.py"},
        already_read=[],
        source_already_given=[],
    )
    assert chosen["tool_selected"] == "read_file"
    assert chosen["tool_arguments"]["path"].endswith("helper.py")
    assert info["search_files_used"] is False
    assert "helper.py" in chosen["mapping_input_excerpt"]


def test_later_inspect_is_not_dropped_after_restatement():
    text = (
        "The error originates from helper.py.\n\n"
        "Inspect load_rows() in helper.py to see how rows is built."
    )
    chosen, info = mapping.next_read_mapping(
        text,
        fixture_files={"helper.py": "path/helper.py"},
        already_read=[],
        source_already_given=[],
    )
    assert chosen is not None
    assert chosen["tool_arguments"]["path"] == "path/helper.py"
    reasons = [item["reason"] for item in info["not_converted"]]
    assert "filename_in_chunk_without_request_words" in reasons


def test_run_one_separates_mapping_and_skips_tools_kwarg(monkeypatch):
    seen = []
    replies = [
        "Inspect helper.py to see how rows is built.",
        "FIELD_COUNT comes from config.py. Inspect config.py next.",
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

    case = next(item for item in cases.RUN_CASES if item["id"] == "F2_S1")
    record = bench.run_one(case, "deepseek-coder-v2:16b", get_llm_profile())
    assert record["turns"][0]["llm_investigation"]["raw_request_excerpts"]
    assert record["turns"][0]["mapping"]["search_files_used"] is False
    assert record["turns"][0]["tool_selected"] == "read_file"
    assert record["turns"][0]["tool_arguments"]["path"].endswith("helper.py")
    assert record["turns"][1]["tool_arguments"]["path"].endswith("config.py")
    assert "Tool result:" in seen[1]["messages"][-1]["content"]
    assert record["observation_flags"]["multi_step_investigation"] is True
    assert record["observation_flags"]["note"].startswith("experiment log helpers")
