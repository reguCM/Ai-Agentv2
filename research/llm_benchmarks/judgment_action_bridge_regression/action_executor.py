"""
検証済み Action を順実行する。結果を次入力へ返す。
PATCH の対象が未知で identifier があるときだけ SEARCH 補助を入れる。
config.py を根拠なく補完しない。既存 execute は import しない。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from research.llm_benchmarks.judgment_action_bridge_regression.tool_adapter import (
    dispatch,
    dump_result,
    search_files,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def format_next_input(tool_name, result, dumped):
    if tool_name == "read_file" and result.get("ok"):
        return f"You asked to inspect {result.get('path')}.\n\nHere is the file:\n\n{result.get('text') or ''}\n"
    if tool_name == "search_files" and result.get("ok"):
        lines = [
            f"{item.get('path')}:{item.get('line')}: {item.get('text')}"
            for item in result.get("matches") or []
        ]
        unique = result.get("unique_path") or "UNKNOWN"
        return (
            f"You asked to search {result.get('query')}.\n"
            f"unique_path: {unique}\n"
            f"unique_reason: {result.get('unique_reason')}\n"
            + "\n".join(lines)
            + "\n"
        )
    if tool_name in ("run_test", "run_program"):
        return (
            f"{tool_name}\n"
            f"command: {json.dumps(result.get('command'), ensure_ascii=False)}\n"
            f"exit_code: {result.get('exit_code')}\n"
            f"stdout:\n{result.get('stdout') or ''}"
            f"stderr:\n{result.get('stderr') or ''}"
            f"traceback:\n{result.get('traceback') or ''}\n"
        )
    if tool_name == "apply_patch" and result.get("ok"):
        return f"Patched {result.get('path')}.\n"
    return "Result:\n" + dumped["sent_tool_result"] + "\n"


def prepare_actions(actions, workspace=None):
    """未知 PATCH の直前へ SEARCH を挿入する。workspace が無いときは挿入しない。"""
    prepared = []
    for item in actions:
        current = dict(item)
        current["parameters"] = dict(item.get("parameters") or {})
        current["tool_arguments"] = dict(item.get("tool_arguments") or {})
        if (
            workspace is not None
            and current.get("intent") == "PATCH"
            and not current.get("target")
            and current.get("status") == "unknown_target"
        ):
            assignments = current["parameters"].get("assignments") or []
            query = assignments[0]["name"] if assignments else None
            if query:
                already = any(
                    prev.get("intent") == "SEARCH"
                    and (prev.get("parameters") or {}).get("query") == query
                    for prev in prepared
                )
                if not already:
                    prepared.append(
                        {
                            "id": f"{current.get('id')}_search",
                            "order": current.get("order") or 0,
                            "intent": "SEARCH",
                            "target": None,
                            "parameters": {"query": query},
                            "confidence": "medium",
                            "dependencies": [],
                            "source_text": current.get("source_text"),
                            "execute": True,
                            "status": "executable",
                            "reason": "assist_search_before_patch",
                            "tool_name": "search_files",
                            "tool_arguments": {"query": query},
                            "validated": True,
                            "validation_success": True,
                            "selected": False,
                            "assist": True,
                        }
                    )
                current["dependencies"] = list(current.get("dependencies") or []) + [
                    "search_unique_assignment"
                ]
        prepared.append(current)
    if workspace is not None:
        prepared = _bind_unique_search(prepared, workspace)
    return prepared


def _bind_unique_search(actions, workspace):
    bound = []
    last_unique = None
    last_query = None
    for item in actions:
        current = dict(item)
        if current.get("intent") == "SEARCH" and current.get("execute"):
            query = (current.get("parameters") or {}).get("query")
            preview = search_files(workspace, query)
            current["search_preview"] = {
                "unique_path": preview.get("unique_path"),
                "unique_reason": preview.get("unique_reason"),
                "unique_definition_files": preview.get("unique_definition_files"),
            }
            if preview.get("unique_reason") == "unique_assignment" and preview.get(
                "unique_path"
            ):
                last_unique = preview["unique_path"]
                last_query = query
            else:
                last_unique = None
                last_query = query
            bound.append(current)
            continue
        if (
            current.get("intent") == "PATCH"
            and not current.get("target")
            and last_unique
            and last_query
        ):
            names = [
                entry.get("name")
                for entry in (current.get("parameters") or {}).get("assignments") or []
            ]
            if last_query in names or not names:
                current = dict(current)
                current["target"] = last_unique
                current["execute"] = True
                current["status"] = "executable"
                current["reason"] = "resolved_from_unique_assignment"
                current["tool_name"] = "apply_patch"
                arguments = {"path": last_unique}
                assignments = (current.get("parameters") or {}).get("assignments")
                content = (current.get("parameters") or {}).get("content")
                if content:
                    arguments["content"] = content
                elif assignments:
                    arguments["assignments"] = assignments
                current["tool_arguments"] = arguments
                current["validated"] = True
                current["validation_success"] = True
        bound.append(current)
    return _maybe_read_after_search(bound)


def _maybe_read_after_search(actions):
    out = []
    for index, item in enumerate(actions):
        out.append(item)
        preview = item.get("search_preview") or {}
        if item.get("intent") != "SEARCH" or preview.get("unique_reason") != "unique_assignment":
            continue
        path = preview.get("unique_path")
        if not path:
            continue
        rest = actions[index + 1 :]
        if any(
            later.get("intent") in ("READ", "OPEN") and later.get("target") == path
            for later in rest
        ):
            continue
        if any(later.get("intent") == "PATCH" for later in rest):
            continue
        out.append(
            {
                "id": f"{item.get('id')}_read",
                "order": (item.get("order") or 0) + 0.5,
                "intent": "READ",
                "target": path,
                "parameters": {},
                "confidence": "medium",
                "dependencies": ["search_unique_assignment"],
                "source_text": item.get("source_text"),
                "execute": True,
                "status": "executable",
                "reason": "assist_read_after_unique_search",
                "tool_name": "read_file",
                "tool_arguments": {"path": path},
                "validated": True,
                "validation_success": True,
                "selected": False,
                "assist": True,
            }
        )
    return out


def execute_actions(workspace, actions):
    steps = []
    next_inputs = []
    for index, action in enumerate(actions, start=1):
        if not action.get("execute") or not action.get("tool_name"):
            steps.append(
                {
                    "timestamp": _now(),
                    "step_id": index,
                    "parsed_intent": action.get("intent"),
                    "selected_action": action,
                    "selection_reason": action.get("reason"),
                    "tool_name": None,
                    "tool_arguments": {},
                    "tool_result": None,
                    "execution_status": "skipped",
                    "mapping_status": action.get("status"),
                    "next_input": None,
                    "ok": False,
                    "execution_success": False,
                    "result_return_success": False,
                }
            )
            continue
        tool_name = action.get("tool_name")
        arguments = action.get("tool_arguments") or {}
        result = dispatch(workspace, tool_name, arguments)
        dumped = dump_result(result)
        next_input = format_next_input(tool_name, result, dumped)
        if tool_name in ("run_test", "run_program"):
            status = "ok" if result.get("exit_code") is not None else "error"
            ok = True
        else:
            ok = bool(result.get("ok"))
            status = "ok" if ok else "error"
        steps.append(
            {
                "timestamp": _now(),
                "step_id": index,
                "parsed_intent": action.get("intent"),
                "selected_action": action,
                "selection_reason": action.get("reason"),
                "tool_name": tool_name,
                "tool_arguments": arguments,
                "tool_result": dumped["raw_result"],
                "execution_status": status,
                "mapping_status": action.get("status"),
                "next_input": next_input,
                "ok": ok,
                "execution_success": status == "ok",
                "result_return_success": bool(next_input),
            }
        )
        next_inputs.append(next_input)
    return steps, next_inputs
