"""実験ログ用のスナップショット。chat / parser / dispatch の動作は変えない。"""

from __future__ import annotations

import copy
import json


TOOL_RESULT_CHAR_LIMIT = 3500


def copy_messages(messages):
    return copy.deepcopy(messages)


def chat_kwargs_snapshot(profile, model):
    """harness が chat() に渡す引数と、llm.chat が setdefault する profile 値の記録。tools は付けない。"""
    options = {
        "num_predict": int(profile.get("num_predict") or 2048),
        "temperature": float(profile.get("temperature") or 0),
    }
    if profile.get("context_limit"):
        options["num_ctx"] = int(profile.get("context_limit"))
    return {
        "model": model,
        "tools": "not_used",
        "keep_alive": profile.get("keep_alive") or "5m",
        "options": options,
        "timeout_seconds": int(profile.get("timeout_seconds") or 90),
        "tool_presentation": "system_text",
        "kwargs_source": {
            "harness_chat_call": ["model", "messages"],
            "llm_chat_setdefault": ["options", "keep_alive"],
            "not_passed": ["tools"],
        },
    }


def dump_tool_result_for_llm(result):
    """harness 既存の dumps + 3500 切断と同一。切断閾値・接尾辞は変えない。"""
    raw_json = json.dumps(result, ensure_ascii=False, default=str)
    truncated = len(raw_json) > TOOL_RESULT_CHAR_LIMIT
    if truncated:
        sent = raw_json[:TOOL_RESULT_CHAR_LIMIT] + "...(truncated)"
    else:
        sent = raw_json
    try:
        raw_stored = json.loads(raw_json)
    except json.JSONDecodeError:
        raw_stored = copy.deepcopy(result)
    return {
        "raw_result": raw_stored,
        "sent_tool_result": sent,
        "truncated": truncated,
        "sent_equals_raw_json": sent == raw_json,
        "llm_user_payload": "Tool result:\n" + sent,
        "execution_error": _execution_error(result),
    }


def _execution_error(result):
    if isinstance(result, dict) and result.get("ok") is False:
        return result.get("error")
    return None


def parse_log(raw, parsed):
    success = parsed is not None
    return {
        "parse_success": success,
        "parsed": parsed,
        "parse_error": None if success else "unparsed",
    }


def split_test_of_patch(payload):
    """既存 test_of_patch を分解。execution_success は例外なし。solution_correct は作らない。"""
    if not payload:
        return None
    error_type = payload.get("error_type")
    error = payload.get("error")
    exception = None
    if error_type not in (None, "") or error not in (None, ""):
        exception = {"error_type": error_type, "error": error}
        if payload.get("traceback"):
            exception["traceback"] = payload.get("traceback")
    return {
        "execution_success": payload.get("ok") is True and payload.get("status") == "pass",
        "execution_success_means": "no_exception",
        "exception": exception,
        "return_value": payload.get("return_value"),
    }
