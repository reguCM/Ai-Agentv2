"""判断層実験。実 LLM は呼ばない。既存 fixture は使わない。"""

from __future__ import annotations

from research.llm_benchmarks.judgment_layer_experiment import bench, execute, mapping, workspace


KNOWN = ["main.py", "helper.py", "config.py", "gate.py", "tests/test_main.py"]


def test_fixture_needs_two_changes(tmp_path):
    dest = tmp_path / "proj"
    workspace.copy_fixture(dest)
    initial = execute.run_test(dest)
    assert initial["exit_code"] != 0
    combined = initial["stdout"] + initial["stderr"]
    assert "IndexError" in combined

    dest.joinpath("config.py").write_text(
        'BIN_LABELS = ["empty", "hold", "ready"]\nBIN_SPAN = 3\n',
        encoding="utf-8",
    )
    after_span = execute.run_test(dest)
    after_text = after_span["stdout"] + after_span["stderr"]
    assert after_span["exit_code"] != 0
    assert "IndexError" not in after_text
    assert "AssertionError" in after_text or "dock" in after_text

    dest.joinpath("gate.py").write_text("DOCK_OPEN = True\n", encoding="utf-8")
    both = execute.run_test(dest)
    assert both["exit_code"] == 0
    program = execute.run_program(dest)
    assert program["exit_code"] == 0
    assert "ready" in program["stdout"]
    assert "true" in program["stdout"].lower()


def test_prompt_does_not_name_files_or_tools():
    user = bench.build_initial_user(
        {"command": ["pytest"], "stdout": "F", "stderr": "", "exit_code": 1},
        {"command": ["python", "main.py"], "stdout": "", "stderr": "IndexError", "exit_code": 1},
    )
    assert user.startswith("Analyze the problem and indicate the next investigation or action needed.")
    assert "helper.py" not in user
    assert "config.py" not in user
    assert "read_file" not in user
    assert "apply_patch" not in user
    assert "tools=" not in user
    assert "JSON" not in user


def test_m1_read_named_file():
    result = mapping.classify_mapping("I need to read helper.py to see how bins are built.", KNOWN)
    assert result["mapping_status"] == "M1"
    assert result["execute"]["tool_name"] == "read_file"
    assert result["execute"]["tool_arguments"]["path"] == "helper.py"


def test_m2_named_file_without_action_is_not_executed():
    result = mapping.classify_mapping("The traceback points at helper.py.", KNOWN)
    assert result["mapping_result"] is None or result["mapping_result"]["status"] != "M1"
    statuses = {item["status"] for item in result["candidates"]}
    assert "M2" in statuses
    assert result["execute"] is None


def test_m2_origin_phrase_is_not_executed():
    result = mapping.classify_mapping("bins の生成元を確認する必要がある", KNOWN)
    assert result["execute"] is None
    assert any(item["status"] == "M2" for item in result["candidates"])


def test_m3_vague_is_not_executed():
    result = mapping.classify_mapping("関連するコードを確認する", KNOWN)
    assert result["execute"] is None
    assert result["candidates"][0]["status"] == "M3"


def test_m4_no_target():
    result = mapping.classify_mapping("さらに調査が必要", KNOWN)
    assert result["execute"] is None
    assert any(item["status"] in ("M3", "M4") for item in result["candidates"])


def test_m5_may_is_not_executed():
    result = mapping.classify_mapping("Look up may in the documentation", KNOWN)
    assert result["execute"] is None
    assert any(item["status"] == "M5" for item in result["candidates"])


def test_m1_fence_apply_patch():
    text = "helper.py\n```python\ndef pick_bin(bins, index):\n    return bins[0]\n```\n"
    result = mapping.classify_mapping(text, KNOWN)
    assert result["execute"]["tool_name"] == "apply_patch"
    assert result["execute"]["tool_arguments"]["path"] == "helper.py"


def test_investigation_result_sends_file_text_not_tool_name():
    dumped = {"sent_tool_result": '{"ok": true}'}
    result = {"ok": True, "path": "helper.py", "text": "from config import BIN_SPAN\n"}
    text = workspace.format_investigation_result("read_file", dumped, result)
    assert "path: helper.py" in text
    assert "from config import BIN_SPAN" in text
    assert "read_file" not in text
