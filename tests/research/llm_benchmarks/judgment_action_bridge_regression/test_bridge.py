"""
固定 LLM 文 → Bridge → Tool。既存実験は import しない。
"""

from research.llm_benchmarks.judgment_action_bridge_regression.bridge import process
from research.llm_benchmarks.judgment_action_bridge_regression.fixed_inputs import (
    AMBIGUOUS_CHECK,
    AMBIGUOUS_FIX,
    AMBIGUOUS_LOOK,
    AMBIGUOUS_THERE,
    CASE_A_READ_HELPER,
    CASE_B_PATCH_NO_FILE,
    CASE_C_OPEN_MODIFY_RUN,
    CASE_D_RUN_TEST_AGAIN,
    CASE_E_FENCE_TOKENS,
    CONFIRM_CONFIG,
    CYCLE_TEXTS,
    GEMMA_T4_RAW,
    GEMMA_T5_RAW,
    KNOWN,
    MISSING_FILE,
    MULTI_READ_THEN_TEST,
    ORDER_MAIN_THEN_HELPER,
    PATCH_THEN_TEST,
    READ_THEN_PATCH_NAMED,
    READY_NOT_READ,
    RUN_THE_TESTS_AGAIN,
    SEARCH_FIELD_COUNT,
    SENTENCE_SEQUENCE,
)
from research.llm_benchmarks.judgment_action_bridge_regression.old_mapping import (
    old_mapping_select,
)
from research.llm_benchmarks.judgment_action_bridge_regression.tool_adapter import (
    copy_fixture,
    git_init_workspace,
)


def _intents(parsed):
    return [item["intent"] for item in parsed["action_candidates"]]


def _tools(parsed):
    return [item["tool_name"] for item in parsed["selected_actions"]]


def _paths(parsed):
    return [
        (item.get("tool_arguments") or {}).get("path")
        for item in parsed["selected_actions"]
        if item.get("tool_name") == "read_file"
    ]


def test_01_read_helper():
    parsed = process(CASE_A_READ_HELPER, KNOWN)
    assert _tools(parsed) == ["read_file"]
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "helper.py"
    assert parsed["flags"]["parse_success"] is True


def test_02_confirm_config():
    parsed = process(CONFIRM_CONFIG, KNOWN)
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "config.py"


def test_03_search_field_count():
    parsed = process(SEARCH_FIELD_COUNT, KNOWN)
    assert _tools(parsed) == ["search_files"]
    assert parsed["selected_actions"][0]["tool_arguments"]["query"] == "FIELD_COUNT"


def test_04_patch_field_count_without_file():
    parsed = process(CASE_B_PATCH_NO_FILE, KNOWN)
    assert parsed["selected_actions"] == []
    patches = [item for item in parsed["action_candidates"] if item["intent"] == "PATCH"]
    assert patches
    assert patches[0]["target"] is None
    assert patches[0]["status"] == "unknown_target"
    assert patches[0]["parameters"]["assignments"][0] == {"name": "FIELD_COUNT", "value": "3"}


def test_05_run_test_again():
    parsed = process(CASE_D_RUN_TEST_AGAIN, KNOWN)
    assert _tools(parsed) == ["run_test"]
    old = old_mapping_select(CASE_D_RUN_TEST_AGAIN, KNOWN)
    assert old["selected_actions"] == []


def test_06_open_modify_run_splits_and_does_not_guess():
    parsed = process(CASE_C_OPEN_MODIFY_RUN, KNOWN)
    assert "OPEN" in _intents(parsed)
    assert "PATCH" in _intents(parsed)
    assert "RUN_TEST" in _intents(parsed)
    assert _tools(parsed) == ["run_test"]
    for item in parsed["action_candidates"]:
        if item["intent"] in ("OPEN", "PATCH"):
            assert item["execute"] is False
            assert item["target"] is None


def test_07_fence_tokens_are_not_actions():
    parsed = process(CASE_E_FENCE_TOKENS, KNOWN)
    assert _tools(parsed) == ["read_file"]
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "helper.py"
    old = old_mapping_select(CASE_E_FENCE_TOKENS, KNOWN)
    old_names = [item["tool_name"] for item in old["selected_actions"]]
    assert "apply_patch" in old_names or "run_test" in old_names


def test_08_ambiguous_fix_stops():
    for text in (AMBIGUOUS_FIX, AMBIGUOUS_CHECK, AMBIGUOUS_LOOK, AMBIGUOUS_THERE):
        parsed = process(text, KNOWN)
        assert parsed["selected_actions"] == []
        assert parsed["mapping_status"] == "ambiguous"
        assert parsed["flags"]["validation_success"] is True


def test_09_multiple_actions():
    parsed = process(MULTI_READ_THEN_TEST, KNOWN)
    assert _tools(parsed) == ["read_file", "read_file", "run_test"]
    assert [item["tool_arguments"].get("path") for item in parsed["selected_actions"][:2]] == [
        "helper.py",
        "config.py",
    ]


def test_10_action_order():
    parsed = process(ORDER_MAIN_THEN_HELPER, KNOWN)
    assert _paths(parsed) == ["main.py", "helper.py"]
    assert parsed["flags"]["sequence_success"] is True


def test_11_missing_file_not_executed(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    parsed = process(
        MISSING_FILE,
        KNOWN + ["missing_no_such.py"],
        workspace=workspace,
        execute=True,
    )
    assert parsed["selected_actions"] == []
    assert parsed["mapping_status"] == "missing_file"
    assert all(step["execution_status"] == "skipped" for step in parsed["steps"])


def test_12_patch_unknown_target():
    parsed = process(CASE_B_PATCH_NO_FILE, KNOWN)
    assert parsed["mapping_status"] == "unknown_target"


def test_13_search_then_read(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    parsed = process(SEARCH_FIELD_COUNT, KNOWN, workspace=workspace, execute=True)
    assert _tools(parsed)[:2] == ["search_files", "read_file"]
    assert parsed["selected_actions"][1]["tool_arguments"]["path"] == "config.py"
    assert "FIELD_COUNT = 1" in parsed["next_inputs"][1]
    assert parsed["flags"]["result_return_success"] is True


def test_14_read_then_patch(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    git_init_workspace(workspace)
    parsed = process(READ_THEN_PATCH_NAMED, KNOWN, workspace=workspace, execute=True)
    assert _tools(parsed) == ["read_file", "apply_patch"]
    text = (workspace / "config.py").read_text(encoding="utf-8")
    assert "FIELD_COUNT = 3" in text
    assert "READY = False" in text


def test_15_patch_then_run_test(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    git_init_workspace(workspace)
    parsed = process(PATCH_THEN_TEST, KNOWN, workspace=workspace, execute=True)
    assert _tools(parsed) == ["apply_patch", "run_test"]
    test_step = parsed["steps"][-1]
    assert test_step["tool_result"]["exit_code"] != 0


def test_16_run_test_fail_then_reaction(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    git_init_workspace(workspace)
    history = []
    for text in CYCLE_TEXTS:
        history.append(process(text, KNOWN, workspace=workspace, execute=True))
    first_test = history[3]
    assert first_test["steps"][-1]["tool_name"] == "run_test"
    assert first_test["steps"][-1]["tool_result"]["exit_code"] != 0
    assert "NameError" not in (first_test["steps"][-1]["next_input"] or "")
    last = history[-1]
    assert last["steps"][-1]["tool_name"] == "run_test"
    assert last["steps"][-1]["tool_result"]["exit_code"] == 0
    assert (workspace / "config.py").read_text(encoding="utf-8").strip() == (
        "FIELD_COUNT = 3\nREADY = True"
    )


def test_sentence_sequence_keeps_unknown_patch():
    parsed = process(SENTENCE_SEQUENCE, KNOWN)
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "helper.py"
    assert "SEARCH" in _intents(parsed)
    assert "RUN_TEST" in _intents(parsed)
    patches = [item for item in parsed["action_candidates"] if item["intent"] == "PATCH"]
    assert patches
    assert patches[0]["execute"] is False


def test_ready_prose_is_not_read():
    parsed = process(READY_NOT_READ, KNOWN)
    assert "read_file" not in _tools(parsed)
    assert all(item.get("intent") != "READ" for item in parsed["action_candidates"])


def test_run_the_tests_again():
    parsed = process(RUN_THE_TESTS_AGAIN, KNOWN)
    assert _tools(parsed) == ["run_test"]


def test_case_b_with_workspace_uses_search_not_guess(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    git_init_workspace(workspace)
    parsed = process(CASE_B_PATCH_NO_FILE, KNOWN, workspace=workspace, execute=True)
    assert parsed["selected_actions"][0]["tool_name"] == "search_files"
    assert parsed["selected_actions"][0]["tool_arguments"]["query"] == "FIELD_COUNT"
    patch = [item for item in parsed["selected_actions"] if item["tool_name"] == "apply_patch"]
    assert len(patch) == 1
    assert patch[0]["tool_arguments"]["path"] == "config.py"
    assert patch[0]["reason"] == "resolved_from_unique_assignment"


def test_gemma_t5_open_modify_run(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    git_init_workspace(workspace)
    parsed = process(GEMMA_T5_RAW, KNOWN, workspace=workspace, execute=True)
    tools = _tools(parsed)
    assert tools[0] == "read_file"
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "config.py"
    assert "apply_patch" in tools
    assert "run_test" in tools
    text = (workspace / "config.py").read_text(encoding="utf-8")
    assert "FIELD_COUNT = 3" in text


def test_gemma_t4_does_not_need_guess(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    git_init_workspace(workspace)
    old = old_mapping_select(GEMMA_T4_RAW, KNOWN)
    parsed = process(GEMMA_T4_RAW, KNOWN, workspace=workspace, execute=True)
    assert old["selected_actions"]
    assert "apply_patch" in [item["tool_name"] for item in parsed["selected_actions"]]
    assert any(
        item.get("tool_arguments", {}).get("path") == "config.py"
        and item.get("tool_name") == "apply_patch"
        for item in parsed["selected_actions"]
    )
    assert "run_test" in _tools(parsed)


def test_old_mapping_misses_read_helper():
    old = old_mapping_select("helper.pyを確認したい。", KNOWN)
    parsed = process("helper.pyを確認したい。", KNOWN)
    assert old["selected_actions"] == []
    assert _tools(parsed) == ["read_file"]
