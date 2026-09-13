"""判断ループ最小実験。実 LLM は呼ばない。既存 fixture は使わない。"""

from __future__ import annotations

from research.llm_benchmarks.judgment_loop_min_experiment import execute, mapping, workspace


KNOWN = ["main.py", "helper.py", "config.py", "store.py", "tests/test_main.py"]


def test_fixture_two_stage(tmp_path):
    dest = tmp_path / "proj"
    workspace.copy_fixture(dest)
    initial = execute.run_test(dest)
    assert initial["exit_code"] != 0
    assert "IndexError" in initial["stdout"] + initial["stderr"]

    dest.joinpath("config.py").write_text(
        'ITEM_LABELS = ["draft", "hold", "live"]\nITEM_SPAN = 3\n',
        encoding="utf-8",
    )
    after = execute.run_test(dest)
    text = after["stdout"] + after["stderr"]
    assert after["exit_code"] != 0
    assert "IndexError" not in text
    assert "AssertionError" in text or "store" in text

    dest.joinpath("store.py").write_text("STORE_OPEN = True\n", encoding="utf-8")
    both = execute.run_test(dest)
    assert both["exit_code"] == 0
    program = execute.run_program(dest)
    assert "live" in program["stdout"]
    assert "true" in program["stdout"].lower()


def test_prompt_has_no_investigation_hints():
    user = execute.build_initial_user(
        {"command": ["pytest"], "stdout": "F", "stderr": "", "exit_code": 1},
        {"command": ["python", "main.py"], "stdout": "", "stderr": "IndexError", "exit_code": 1},
    )
    assert "Analyze the current problem and determine what should be done next." in user
    assert "The program failed with the following output:" in user
    assert "helper.pyを" not in user
    assert "importを確認" not in user
    assert "read_file" not in user


def test_test_failure_feedback_does_not_direct_files():
    text = execute.format_test_failure(
        {"exit_code": 1, "stdout": "AssertionError", "stderr": "", "traceback": ""},
        {"command": ["python", "main.py"], "stdout": "{}", "stderr": "", "exit_code": 0, "traceback": ""},
    )
    assert text.startswith("The test still fails.")
    assert "別ファイル" not in text
    assert "helper.pyを" not in text


def test_inspect_helper_maps_to_read():
    result = mapping.classify_mapping("The next step is to inspect helper.py.", KNOWN)
    assert result["execute"]["tool_name"] == "read_file"
    assert result["execute"]["tool_arguments"]["path"] == "helper.py"


def test_origin_without_file_is_mapping_gap_not_llm_failure():
    result = mapping.classify_mapping("I need to inspect the code that creates rows.", KNOWN)
    assert result["execute"] is None
    gap = result["candidates"][0]
    assert gap["status"] == "mapping_gap"
    assert gap["not_llm_failure"] is True


def test_japanese_confirm_maps():
    result = mapping.classify_mapping("main.pyを確認する必要がある", KNOWN)
    assert result["execute"]["tool_name"] == "read_file"
    assert result["execute"]["tool_arguments"]["path"] == "main.py"
