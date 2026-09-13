"""Tool Calling圧縮仮説実験。実 LLM は呼ばない。既存 fixture は使わない。"""

from __future__ import annotations

from research.llm_benchmarks.tool_calling_compression_experiment import (
    bench,
    execute,
    observe,
    workspace,
)


FORBIDDEN_PROMPT = [
    "Analyze the error first",
    "Find the relevant file",
    "Check the imports",
    "Look for dependencies",
    "Use tools to investigate",
    "helper.py",
    "config.py",
    "list_files",
    "apply_patch",
]


def test_fixture_needs_two_changes(tmp_path):
    dest = tmp_path / "proj"
    workspace.copy_fixture(dest)
    initial = execute.run_test(dest)
    assert initial["exit_code"] != 0
    combined = initial["stdout"] + initial["stderr"]
    assert "IndexError" in combined

    dest.joinpath("config.py").write_text(
        'STAGE_NAMES = ["queued", "open", "closed"]\nSTAGE_LIMIT = 3\n',
        encoding="utf-8",
    )
    after_limit = execute.run_test(dest)
    after_text = after_limit["stdout"] + after_limit["stderr"]
    assert after_limit["exit_code"] != 0
    assert "IndexError" not in after_text
    assert "AssertionError" in after_text or "window" in after_text

    dest.joinpath("flags.py").write_text("WINDOW_OPEN = True\n", encoding="utf-8")
    both = execute.run_test(dest)
    assert both["exit_code"] == 0
    program = execute.run_program(dest)
    assert program["exit_code"] == 0
    assert "closed" in program["stdout"]
    assert "true" in program["stdout"].lower()


def test_prompt_is_minimal_and_has_no_search_hints():
    user = bench.build_initial_user(
        {"command": ["pytest"], "stdout": "F", "stderr": "", "exit_code": 1},
        {"command": ["python", "main.py"], "stdout": "", "stderr": "IndexError", "exit_code": 1},
    )
    assert user.startswith("Resolve the problem.")
    for phrase in FORBIDDEN_PROMPT:
        assert phrase not in user
    assert "thinking" not in user.lower()


def test_test_feedback_does_not_direct_other_files():
    text = bench.test_feedback_user(
        {"command": ["pytest"], "stdout": "AssertionError", "stderr": "", "exit_code": 1},
        {"command": ["python", "main.py"], "stdout": "{}", "stderr": "", "exit_code": 0},
    )
    assert text.startswith("Test result:")
    assert "別ファイル" not in text
    assert "helper.pyを" not in text
    assert "list_files" not in text


def test_tool_descriptions_do_not_prescribe_order():
    joined = " ".join(
        item["function"]["description"].lower() for item in workspace.OLLAMA_TOOLS
    )
    assert "first" not in joined
    assert "investigate" not in joined
    assert "start with" not in joined
    assert "helper" not in joined
    assert "dependency" not in joined


def test_mechanical_flags_do_not_infer_internal_reason():
    record = {
        "model": "qwen3:14b",
        "tool_calling_path": "native",
        "tool_calling_mode": "ollama_native_tools",
        "turns": [
            {
                "turn_id": 1,
                "raw_output": "",
                "parsed": {"native_tool_calls": [{"name": "read_file"}]},
                "tool_calls": ["read_file"],
                "files_read": ["helper.py"],
                "files_changed": [],
                "thinking_observed": False,
            }
        ],
    }
    summary = observe.summarize_run(record)
    assert summary["analysis_observable"] is False
    assert summary["tool_selection_observable"] is True
    assert summary["tool_call_without_visible_content_any"] is True
    assert summary["hypothesis_updated"] == "NOT_DETERMINED"
    assert summary["tool_result_used"] == "NOT_DETERMINED"
