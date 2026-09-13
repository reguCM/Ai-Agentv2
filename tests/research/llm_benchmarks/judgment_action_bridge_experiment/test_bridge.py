"""判断→Action 橋渡し。T1–T15。既存 Mapping は使わない。"""

from research.llm_benchmarks.judgment_action_bridge_experiment.bridge import (
    parse_judgment,
    run_scripted,
)
from research.llm_benchmarks.judgment_action_bridge_experiment.workspace import (
    apply_patch,
    copy_fixture,
    run_program,
    run_test,
)


KNOWN = ["main.py", "helper.py", "config.py", "tests/test_main.py"]


def _selected_calls(parsed):
    return [
        (item["tool_name"], item.get("tool_arguments") or {})
        for item in parsed["selected_actions"]
    ]


def test_t1_single_file_read():
    parsed = parse_judgment("helper.pyを確認したい", KNOWN)
    assert parsed["judgment_received"] is True
    assert _selected_calls(parsed) == [("read_file", {"path": "helper.py"})]


def test_t2_single_test():
    parsed = parse_judgment("テストを実行したい", KNOWN)
    assert _selected_calls(parsed) == [("run_test", {})]


def test_t3_single_patch():
    text = (
        "config.py を修正する。\n"
        "config.py\n"
        "```python\n"
        "FIELD_COUNT = 3\n"
        "READY = False\n"
        "```\n"
    )
    parsed = parse_judgment(text, KNOWN)
    assert parsed["selected_actions"][0]["tool_name"] == "apply_patch"
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "config.py"
    assert "FIELD_COUNT = 3" in parsed["selected_actions"][0]["tool_arguments"]["content"]


def test_t4_multiple_actions():
    parsed = parse_judgment("helper.pyを確認したい。その後Testを実行したい。", KNOWN)
    assert [item["tool_name"] for item in parsed["selected_actions"]] == [
        "read_file",
        "run_test",
    ]


def test_t5_action_order():
    parsed = parse_judgment("main.pyを見てからhelper.pyを確認したい", KNOWN)
    paths = [item["tool_arguments"]["path"] for item in parsed["selected_actions"]]
    assert paths == ["main.py", "helper.py"]


def test_t6_filename_extraction():
    parsed = parse_judgment("config.pyを調べる必要がある", KNOWN)
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "config.py"


def test_t7_ambiguous_does_not_execute():
    for text in ("ちょっと確認したい", "原因を調べる必要がある", "この辺を見てください"):
        parsed = parse_judgment(text, KNOWN)
        assert parsed["selected_actions"] == []
        assert parsed["mapping_status"] in ("unresolved", "needs_clarification")


def test_t8_similar_words_do_not_trigger_tools():
    text = (
        "helper.pyを確認したい。\n"
        "Testについてはまだ実行しない。\n"
        "パッチ内にはREADYという文字列がある。\n"
    )
    parsed = parse_judgment(text, KNOWN)
    assert _selected_calls(parsed) == [("read_file", {"path": "helper.py"})]
    names = [item["tool_name"] for item in parsed["selected_actions"]]
    assert "run_test" not in names
    assert "apply_patch" not in names


def test_t9_fence_tokens_are_not_actions():
    text = (
        "helper.pyを確認したい。\n"
        "Testはまだ実行しない。\n"
        "```python\n"
        "def test_ready():\n"
        "    # READ\n"
        "    # TEST\n"
        "    # READY\n"
        "    assert READY\n"
        "```\n"
    )
    parsed = parse_judgment(text, KNOWN)
    assert _selected_calls(parsed) == [("read_file", {"path": "helper.py"})]


def test_t10_distant_judgment_still_extracts_inspect():
    text = (
        "helper.pyを確認したい。\n"
        + ("説明 " * 30)
        + "\n以上が次に必要なことである。\n"
    )
    parsed = parse_judgment(text, KNOWN)
    assert _selected_calls(parsed) == [("read_file", {"path": "helper.py"})]


def test_t11_followup_after_result(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    first = parse_judgment("helper.pyを確認したい", KNOWN)
    executed = run_scripted(workspace, first["selected_actions"])
    assert executed[0]["execution_status"] == "ok"
    assert "FIELD_COUNT" in executed[0]["next_input"]
    second = parse_judgment("config.pyを確認したい", KNOWN)
    executed2 = run_scripted(workspace, second["selected_actions"])
    assert executed2[0]["tool_arguments"]["path"] == "config.py"
    assert "READY" in executed2[0]["next_input"]


def test_t12_patch_test_failure_rejudgment(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    initial = run_test(workspace)
    assert initial["exit_code"] != 0
    run_scripted(
        workspace,
        [
            {
                "tool_name": "apply_patch",
                "tool_arguments": {
                    "path": "config.py",
                    "content": "FIELD_COUNT = 3\nREADY = False\n",
                },
            }
        ],
    )
    after = run_test(workspace)
    assert after["exit_code"] != 0
    assert "ready" in (after["stdout"] or "").lower() or after["exit_code"] == 1


def test_t13_test_pass_stops(tmp_path):
    workspace = copy_fixture(tmp_path / "ws")
    run_scripted(
        workspace,
        [
            {
                "tool_name": "apply_patch",
                "tool_arguments": {
                    "path": "config.py",
                    "content": "FIELD_COUNT = 3\nREADY = True\n",
                },
            }
        ],
    )
    after = run_test(workspace)
    program = run_program(workspace)
    assert after["exit_code"] == 0
    assert program["exit_code"] == 0


def test_t14_unmapped_request():
    parsed = parse_judgment("世界平和が必要だ", KNOWN)
    assert parsed["selected_actions"] == []
    assert parsed["mapping_status"] in ("mapping_gap", "unresolved", "needs_clarification")


def test_t15_multiple_candidates_kept():
    parsed = parse_judgment("helper.pyを調査したい", KNOWN)
    tools = {item["tool_name"] for item in parsed["action_candidates"]}
    assert "read_file" in tools
    assert "search_files" in tools
    selected = [item["tool_name"] for item in parsed["selected_actions"]]
    assert selected == ["read_file"]
    assert "search_files" not in selected


def test_yomu_is_inspect_not_run_test():
    parsed = parse_judgment("helper.pyを読む", KNOWN)
    assert _selected_calls(parsed) == [("read_file", {"path": "helper.py"})]
    assert "run_test" not in [item["tool_name"] for item in parsed["selected_actions"]]


def test_does_not_rewrite_inspect_to_run_test():
    parsed = parse_judgment("config.pyを調べたい", KNOWN)
    assert parsed["selected_actions"][0]["tool_arguments"]["path"] == "config.py"


def test_full_solve_loop_scripted(tmp_path):
    from research.llm_benchmarks.judgment_action_bridge_experiment.workspace import git_init_workspace

    workspace = copy_fixture(tmp_path / "ws")
    git_init_workspace(workspace)
    assert run_test(workspace)["exit_code"] != 0
    read_helper = parse_judgment("helper.pyを確認したい", KNOWN)
    helper_steps = run_scripted(workspace, read_helper["selected_actions"])
    assert "load_items" in helper_steps[0]["next_input"]
    read_config = parse_judgment("config.pyを確認したい", KNOWN)
    config_steps = run_scripted(workspace, read_config["selected_actions"])
    assert "FIELD_COUNT" in config_steps[0]["next_input"]
    patch1 = parse_judgment(
        "config.py を修正する。\nconfig.py\n```python\nFIELD_COUNT = 3\nREADY = False\n```\n",
        KNOWN,
    )
    run_scripted(workspace, patch1["selected_actions"])
    mid = run_test(workspace)
    assert mid["exit_code"] != 0
    patch2 = parse_judgment(
        "config.py を修正する。\nconfig.py\n```python\nFIELD_COUNT = 3\nREADY = True\n```\n",
        KNOWN,
    )
    run_scripted(workspace, patch2["selected_actions"])
    final = run_test(workspace)
    assert final["exit_code"] == 0


def test_this_file_then_test_does_not_invent_path():
    parsed = parse_judgment("このファイルを調べてからTestしたい", KNOWN)
    inspect = [item for item in parsed["action_candidates"] if item.get("intent") == "inspect"]
    assert inspect
    assert inspect[0]["status"] in ("unresolved", "needs_clarification")
    assert not any(
        item["tool_name"] == "read_file" and item.get("execute")
        for item in parsed["selected_actions"]
    )
