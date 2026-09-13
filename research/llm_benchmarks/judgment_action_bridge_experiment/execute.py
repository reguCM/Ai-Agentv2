"""選択された Action を順に実行し、結果を次入力へ返す。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from research.llm_benchmarks.judgment_action_bridge_experiment.workspace import (
    dispatch,
    dump_result,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def format_next_input(tool_name, result, dumped):
    if tool_name == "read_file" and result.get("ok"):
        return f"You asked to inspect {result.get('path')}.\n\nHere is the file:\n\n{result.get('text') or ''}\n"
    if tool_name == "list_files" and result.get("ok"):
        names = [item["path"] for item in result.get("entries") or []]
        return "You asked to list files.\n\n" + "\n".join(names) + "\n"
    if tool_name in ("run_test", "run_program"):
        return (
            f"{tool_name}\n"
            f"command: {json.dumps(result.get('command'), ensure_ascii=False)}\n"
            f"exit_code: {result.get('exit_code')}\n"
            f"stdout:\n{result.get('stdout') or ''}"
            f"stderr:\n{result.get('stderr') or ''}"
            f"traceback:\n{result.get('traceback') or ''}\n"
        )
    return "Result:\n" + dumped["sent_tool_result"] + "\n"


def run_scripted(workspace, actions):
    steps = []
    for index, action in enumerate(actions, start=1):
        tool_name = action.get("tool_name")
        arguments = action.get("tool_arguments") or {}
        result = dispatch(workspace, tool_name, arguments)
        dumped = dump_result(result)
        next_input = format_next_input(tool_name, result, dumped)
        ok = bool(result.get("ok")) if "ok" in result else result.get("exit_code") == 0
        if tool_name in ("run_test", "run_program"):
            ok = True
            status = "ok" if result.get("exit_code") is not None else "error"
        else:
            status = "ok" if result.get("ok") else "error"
        steps.append(
            {
                "timestamp": _now(),
                "step_id": index,
                "parsed_intent": action.get("intent"),
                "selected_action": action,
                "selection_reason": action.get("selection_reason"),
                "tool_name": tool_name,
                "tool_arguments": arguments,
                "tool_result": dumped["raw_result"],
                "execution_status": status,
                "mapping_status": action.get("status"),
                "next_input": next_input,
                "ok": ok,
            }
        )
    return steps
