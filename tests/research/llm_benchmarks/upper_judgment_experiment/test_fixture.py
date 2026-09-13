"""上位判断層実験。実 LLM / GPT API は呼ばない。既存 fixture は使わない。"""

from __future__ import annotations

from research.llm_benchmarks.upper_judgment_experiment import execute, workspace


def test_fixture_needs_two_changes(tmp_path):
    dest = tmp_path / "proj"
    workspace.copy_fixture(dest)
    initial = execute.run_test(dest)
    assert initial["exit_code"] != 0
    assert "IndexError" in initial["stdout"] + initial["stderr"]

    dest.joinpath("config.py").write_text(
        'LANE_NAMES = ["north", "east", "west"]\nLANE_TAKE = 3\n',
        encoding="utf-8",
    )
    after_take = execute.run_test(dest)
    after_text = after_take["stdout"] + after_take["stderr"]
    assert after_take["exit_code"] != 0
    assert "IndexError" not in after_text
    assert "AssertionError" in after_text or "bay" in after_text

    dest.joinpath("bay.py").write_text("BAY_OPEN = True\n", encoding="utf-8")
    both = execute.run_test(dest)
    assert both["exit_code"] == 0
    program = execute.run_program(dest)
    assert program["exit_code"] == 0
    assert "west" in program["stdout"]
    assert "true" in program["stdout"].lower()


def test_solver_prompt_has_no_file_hints():
    text = execute.build_solver_prompt(
        {"command": ["pytest"], "stdout": "F", "stderr": "", "exit_code": 1},
        {"command": ["python", "main.py"], "stdout": "", "stderr": "IndexError", "exit_code": 1},
    )
    assert text.startswith("この問題を解決してください。")
    assert "helper.pyを" not in text
    assert "config.py" not in text
    assert "importを調べ" not in text
    assert "別ファイル" not in text
    assert "read_file" not in text
