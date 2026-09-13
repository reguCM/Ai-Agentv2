"""
Problem Analysis 文脈増加実験の入力。

Level 5/6 は既存 fixture・実験で確認できる情報だけ。原因の捏造はしない。
B〜E に traceback / source は無い（合成 Failure）。NOT_RECORDED と明示する。
"""

from __future__ import annotations

import traceback

from tests.fixtures.broken_tools import SOURCE_INDEX_ERROR


PROMPT_TEMPLATE = """Analyze the problem below.

Do not fix the problem.
Do not use tools.

{context}
"""

CASES = [
    {
        "letter": "A",
        "id": "A_index_error",
        "tool_name": "cpu_status",
        "error_type": "IndexError",
        "error": "list index out of range",
        "task_en": "Obtain the current CPU status.",
        "task_ja": "CPU状態を取得できるToolを作る。",
        "conversation": (
            "User:\n"
            "CPU状態を取得できるToolを作ってください。\n\n"
            "Assistant:\n"
            "cpu_status Toolを作成しました。\n\n"
            "User:\n"
            "実行してください。\n\n"
            "Assistant:\n"
            "cpu_statusを実行します。"
        ),
        "history": [
            "CPU情報取得処理を実装した。",
            "cpu_statusを実行した。",
            "実行時にIndexErrorが発生した。",
        ],
        "has_source": True,
        "module": "tools.system.cpu.cpu_status",
        "function": "cpu_status",
        "source": SOURCE_INDEX_ERROR.strip() + "\n",
    },
    {
        "letter": "B",
        "id": "B_none_attribute",
        "tool_name": "data_loader",
        "error_type": "AttributeError",
        "error": "'NoneType' object has no attribute 'items'",
        "task_en": "Load data.",
        "task_ja": "データを読み込めるToolを作る。",
        "conversation": (
            "User:\n"
            "データを読み込めるToolを作ってください。\n\n"
            "Assistant:\n"
            "data_loader Toolを作成しました。\n\n"
            "User:\n"
            "実行してください。\n\n"
            "Assistant:\n"
            "data_loaderを実行します。"
        ),
        "history": [
            "データ読み込み処理を実装した。",
            "data_loaderを実行した。",
            "実行時にAttributeErrorが発生した。",
        ],
        "has_source": False,
        "module": None,
        "function": None,
        "source": None,
    },
    {
        "letter": "C",
        "id": "C_validation_fields",
        "tool_name": "validator",
        "error_type": "ValidationError",
        "error": "expected 3 fields, got 2",
        "task_en": "Validate the input.",
        "task_ja": "入力を検証できるToolを作る。",
        "conversation": (
            "User:\n"
            "入力を検証できるToolを作ってください。\n\n"
            "Assistant:\n"
            "validator Toolを作成しました。\n\n"
            "User:\n"
            "実行してください。\n\n"
            "Assistant:\n"
            "validatorを実行します。"
        ),
        "history": [
            "入力検証処理を実装した。",
            "validatorを実行した。",
            "実行時にValidationErrorが発生した。",
        ],
        "has_source": False,
        "module": None,
        "function": None,
        "source": None,
    },
    {
        "letter": "D",
        "id": "D_cuda_init",
        "tool_name": "runtime_check",
        "error_type": "RuntimeError",
        "error": "CUDA initialization failed",
        "task_en": "Check the runtime environment.",
        "task_ja": "実行環境を確認できるToolを作る。",
        "conversation": (
            "User:\n"
            "実行環境を確認できるToolを作ってください。\n\n"
            "Assistant:\n"
            "runtime_check Toolを作成しました。\n\n"
            "User:\n"
            "実行してください。\n\n"
            "Assistant:\n"
            "runtime_checkを実行します。"
        ),
        "history": [
            "実行環境の確認処理を実装した。",
            "runtime_checkを実行した。",
            "実行時にRuntimeErrorが発生した。",
        ],
        "has_source": False,
        "module": None,
        "function": None,
        "source": None,
    },
    {
        "letter": "E",
        "id": "E_information_poor",
        "tool_name": "unknown_tool",
        "error_type": "RuntimeError",
        "error": "operation failed",
        "task_en": "Perform the requested operation.",
        "task_ja": "必要な処理を実行できるToolを作る。",
        "conversation": (
            "User:\n"
            "必要な処理を実行できるToolを作ってください。\n\n"
            "Assistant:\n"
            "unknown_tool を作成しました。\n\n"
            "User:\n"
            "実行してください。\n\n"
            "Assistant:\n"
            "unknown_toolを実行します。"
        ),
        "history": [
            "要求された処理を実装した。",
            "unknown_toolを実行した。",
            "実行時にRuntimeErrorが発生した。",
        ],
        "has_source": False,
        "module": None,
        "function": None,
        "source": None,
    },
]


def _failure_block(case):
    return (
        f"Tool: {case['tool_name']}\n"
        f"Status: fail\n"
        f"Error type: {case['error_type']}\n"
        f"Error: {case['error']}"
    )


def _capture_index_error_traceback():
    namespace = {}
    compiled = compile(SOURCE_INDEX_ERROR, "cpu_status.py", "exec")
    exec(compiled, namespace)
    try:
        namespace["cpu_status"]()
    except IndexError:
        return traceback.format_exc()
    return "NOT_OBSERVED"


def _execution_details(case):
    if case["has_source"]:
        tb = _capture_index_error_traceback()
        return (
            "Execution details:\n"
            f"module: {case['module']}\n"
            f"function: {case['function']}\n"
            "return_value: NOT_RECORDED\n"
            "validation: NOT_RECORDED\n"
            "traceback:\n"
            f"{tb.rstrip()}\n"
        )
    return (
        "Execution details:\n"
        "module: NOT_RECORDED\n"
        "function: NOT_RECORDED\n"
        "return_value: NOT_RECORDED\n"
        "validation: NOT_RECORDED\n"
        "traceback: NOT_RECORDED\n"
    )


def _source_block(case):
    if case["has_source"]:
        return "Source:\n" + case["source"].rstrip() + "\n"
    return "Source:\nNOT_RECORDED\n"


def build_context(case, level):
    if level == 1:
        return _failure_block(case)
    if level == 2:
        return (
            f"Task:\n{case['task_en']}\n\n"
            f"Tool:\n{case['tool_name']}\n\n"
            "Status:\nfail\n\n"
            f"Error type:\n{case['error_type']}\n\n"
            f"Error:\n{case['error']}\n"
        )
    if level == 3:
        return (
            "Conversation:\n\n"
            f"{case['conversation']}\n\n"
            f"Tool:\n{case['tool_name']}\n\n"
            "Status:\nfail\n\n"
            f"Error type:\n{case['error_type']}\n\n"
            f"Error:\n{case['error']}\n"
        )
    if level == 4:
        steps = "\n".join(
            f"{i}. {line}" for i, line in enumerate(case["history"], start=1)
        )
        return (
            f"Task:\n{case['task_ja']}\n\n"
            "Conversation:\n\n"
            f"{case['conversation']}\n\n"
            "Execution history:\n\n"
            f"{steps}\n\n"
            "Failure:\n"
            f"{_failure_block(case)}\n"
        )
    if level == 5:
        return build_context(case, 4).rstrip() + "\n\n" + _execution_details(case)
    if level == 6:
        return build_context(case, 5).rstrip() + "\n\n" + _source_block(case)
    raise ValueError(f"unknown level: {level}")


def build_prompt(case, level):
    return PROMPT_TEMPLATE.format(context=build_context(case, level))
