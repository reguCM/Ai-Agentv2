"""固定判断。LLM は使わない。期待 Tool は基盤検証用であり、正式 Mapping 仕様ではない。"""

from __future__ import annotations


KNOWN_FILES = ["main.py", "helper.py", "config.py", "tests/test_main.py"]

PARTIAL_CONFIG = "FIELD_COUNT = 3\nREADY = False\n"
FULL_CONFIG = "FIELD_COUNT = 3\nREADY = True\n"
SNIPPET_CONFIG = "FIELD_COUNT = 3\n"


def _call(tool, **arguments):
    return {"tool_name": tool, "tool_arguments": arguments}


MAPPING_CASES = [
    {
        "id": "case1_confirm_helper",
        "judgment": "helper.py を確認する",
        "expected_calls": [_call("read_file", path="helper.py")],
        "note": "指示書 Case 1",
    },
    {
        "id": "case2_want_to_read_helper",
        "judgment": "helper.py の内容を読みたい",
        "expected_calls": [_call("read_file", path="helper.py")],
        "note": "指示書 Case 2。INSPECT が「読む|読ん」で「読みたい」に一致するかは実測。",
    },
    {
        "id": "case3_helper_then_config",
        "judgment": "helper.py を調査した後、config.py も確認する",
        "expected_calls": [
            _call("read_file", path="helper.py"),
            _call("read_file", path="config.py"),
        ],
        "note": "指示書 Case 3。複数 Tool と順序。",
    },
    {
        "id": "case4_run_test_again",
        "judgment": "Testをもう一度実行する",
        "expected_calls": [_call("run_test")],
        "note": "指示書 Case 4。TEST_HINT がこの文言に一致するかは実測。",
    },
    {
        "id": "case5_read_then_test",
        "judgment": "helper.py を読んでからTestを実行する",
        "expected_calls": [_call("read_file", path="helper.py"), _call("run_test")],
        "note": "指示書 Case 5。順序保持。",
    },
]

MISMAPPING_CASES = [
    {
        "id": "failure_a_inspect_plus_run_tests_again",
        "judgment": "helper.pyを確認する必要があります。\nRun Tests Again.",
        "expected_calls": [_call("read_file", path="helper.py")],
        "note": "判断は読取。Run Tests Again が誤って選ばれれば Mapping 失敗。",
    },
    {
        "id": "failure_a_english_inspect",
        "judgment": "I need to inspect helper.py before making a change.",
        "expected_calls": [_call("read_file", path="helper.py")],
        "note": "監査で挙げた固定英文。inspect が近傍にある場合。",
    },
    {
        "id": "failure_a_distant_file_then_run_tests_again",
        "judgment": (
            "The complete source of main.py, helper.py, and tests/test_main.py is required.\n"
            + ("padding " * 20)
            + "\nRun Tests Again."
        ),
        "expected_calls": [_call("read_file", path="helper.py")],
        "note": "ファイル要求と inspect 語が離れ、Run Tests Again だけが M1 になる条件。",
    },
]

RETURN_CASE = {
    "id": "return_helper_read",
    "judgment": "helper.py を確認する",
    "expected_calls": [_call("read_file", path="helper.py")],
}

MULTI_TURN = [
    {
        "turn_id": 1,
        "judgment": "helper.py を確認する",
        "expected_calls": [_call("read_file", path="helper.py")],
    },
    {
        "turn_id": 2,
        "judgment": (
            "helper.py が config.py の FIELD_COUNT を使用しているため、config.py を確認する"
        ),
        "expected_calls": [_call("read_file", path="config.py")],
    },
    {
        "turn_id": 3,
        "judgment": (
            "config.py の値と helper.py の処理を比較して修正する。\n"
            "patch config.py\n"
            "config.py\n"
            f"```python\n{PARTIAL_CONFIG}```\n"
        ),
        "expected_calls": [_call("apply_patch", path="config.py", content=PARTIAL_CONFIG)],
    },
]

SOLVE_LOOP = [
    {
        "turn_id": 1,
        "judgment": "helper.py を確認する",
        "expected_calls": [_call("read_file", path="helper.py")],
    },
    {
        "turn_id": 2,
        "judgment": "config.py を確認する",
        "expected_calls": [_call("read_file", path="config.py")],
    },
    {
        "turn_id": 3,
        "judgment": (
            "I need to patch config.py.\n"
            "config.py\n"
            f"```python\n{PARTIAL_CONFIG}```\n"
        ),
        "expected_calls": [_call("apply_patch", path="config.py", content=PARTIAL_CONFIG)],
        "expect_test_after_patch": True,
        "expect_test_pass": False,
    },
    {
        "turn_id": 4,
        "judgment": "config.py を確認する",
        "expected_calls": [_call("read_file", path="config.py")],
    },
    {
        "turn_id": 5,
        "judgment": (
            "I need to patch config.py.\n"
            "config.py\n"
            f"```python\n{FULL_CONFIG}```\n"
        ),
        "expected_calls": [_call("apply_patch", path="config.py", content=FULL_CONFIG)],
        "expect_test_after_patch": True,
        "expect_test_pass": True,
    },
]

UNKNOWN_TOOL_JUDGMENT = {
    "id": "no_such_tool_name",
    "judgment": "call_unknown_widget now",
    "expected_calls": [],
    "note": "機械的対象が無ければ mapping_gap。Tool 不存在とは別。",
}
