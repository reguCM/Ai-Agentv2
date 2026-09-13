"""実コード実験。実 LLM は呼ばない。"""

from __future__ import annotations

from pathlib import Path

from research.llm_benchmarks.problem_solving_experiment import (
    real_code_bench as bench,
    real_code_execute as execute,
    real_code_workspace as workspace,
)


def test_fixture_produces_real_indexerror(tmp_path):
    dest = tmp_path / "proj"
    workspace.copy_fixture(dest)
    main_run = execute.run_main(dest)
    test_run = execute.run_pytest(dest)
    assert main_run["exit_code"] != 0
    assert test_run["exit_code"] != 0
    assert "IndexError" in main_run["stderr"]
    assert "Traceback (most recent call last):" in main_run["stderr"]
    assert "IndexError" in test_run["stderr"] or "IndexError" in test_run["stdout"]
    assert "list index out of range" in (main_run["stderr"] + test_run["stderr"] + test_run["stdout"])
    assert main_run["traceback"]
    assert " artificially" not in main_run["stderr"]


def test_prompt_does_not_instruct_import_or_traceback_strategy():
    captured = {
        "pytest": {
            "command": ["pytest"],
            "stdout": "",
            "stderr": "Traceback\nIndexError",
            "exit_code": 1,
        },
        "main_py": {
            "command": ["python", "main.py"],
            "stdout": "",
            "stderr": "Traceback\nIndexError",
            "exit_code": 1,
        },
    }
    prompt = bench.build_initial_user(captured)
    assert "この問題を解決してください。" in prompt
    assert "import先を確認" not in prompt
    assert "tracebackを確認" not in prompt
    assert "まずmain.py" not in prompt
    assert "原因を分解" not in prompt
    assert "必要情報を列挙" not in prompt
    assert "helper.pyを読むべき" not in prompt
    assert "Problem Analysis" not in prompt


def test_workspace_rejects_parent_path(tmp_path):
    dest = tmp_path / "proj"
    workspace.copy_fixture(dest)
    result = workspace.read_file(dest, "../secrets.txt")
    assert result["ok"] is False


def test_parse_text_tool_nested_braces():
    text = (
        'please write\n{"tool":"write_file","arguments":{"path":"main.py",'
        '"content":"x = {\\"status\\": 1}\\n"}}'
    )
    parsed, status = bench.parse_text_tool(text)
    assert status == "parsed_from_text"
    assert parsed["name"] == "write_file"
    assert parsed["arguments"]["path"] == "main.py"
    assert "status" in parsed["arguments"]["content"]
