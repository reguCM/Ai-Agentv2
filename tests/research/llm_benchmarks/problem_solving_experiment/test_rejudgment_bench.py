"""Test後再判断実験。実 LLM は呼ばない。既存 fixture は使わない。"""

from __future__ import annotations

from research.llm_benchmarks.problem_solving_experiment import (
    rejudgment_bench as bench,
    rejudgment_execute as execute,
    rejudgment_workspace as workspace,
)


def test_fixture_needs_two_changes(tmp_path):
    dest = tmp_path / "proj"
    workspace.copy_fixture(dest)
    initial = execute.run_test(dest)
    assert initial["exit_code"] != 0
    combined = initial["stdout"] + initial["stderr"]
    assert "IndexError" in combined

    dest.joinpath("config.py").write_text(
        'STATUS_LABELS = ["LoadPercentage", "Idle", "Busy"]\nFIELD_COUNT = 3\n',
        encoding="utf-8",
    )
    after_count = execute.run_test(dest)
    after_text = after_count["stdout"] + after_count["stderr"]
    assert after_count["exit_code"] != 0
    assert "IndexError" not in after_text
    assert "AssertionError" in after_text or "ready" in after_text

    dest.joinpath("runtime.py").write_text("READY = True\n", encoding="utf-8")
    both = execute.run_test(dest)
    assert both["exit_code"] == 0
    program = execute.run_program(dest)
    assert program["exit_code"] == 0
    assert "Busy" in program["stdout"]
    assert "true" in program["stdout"].lower()


def test_prompt_has_no_investigation_or_tool_hints():
    user = bench.build_initial_user(
        {"command": ["pytest"], "stdout": "F", "stderr": "", "exit_code": 1},
        {"command": ["python", "main.py"], "stdout": "", "stderr": "IndexError", "exit_code": 1},
    )
    assert user.startswith("Analyze the problem and resolve it.")
    assert "helper.py" not in user
    assert "importを調査" not in user
    assert "原因を分解" not in user
    assert "list_files" not in user
    assert "apply_patch" not in user
    assert "別ファイル" not in user


def test_test_feedback_does_not_direct_other_files():
    text = bench.test_feedback_user(
        {"command": ["pytest"], "stdout": "AssertionError", "stderr": "", "exit_code": 1},
        {"command": ["python", "main.py"], "stdout": "{}", "stderr": "", "exit_code": 0},
    )
    assert text.startswith("Test result:")
    assert "別ファイル" not in text
    assert "import" not in text.lower() or "import" in "Test result"
    assert "helper.pyを" not in text
