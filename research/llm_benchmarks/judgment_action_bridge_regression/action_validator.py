"""Action の機械検証。対象が無ければ実行しない。既存 validate は import しない。"""

from __future__ import annotations

from research.llm_benchmarks.judgment_action_bridge_regression.action_parser import SEARCH_STOPWORDS


def validate_actions(actions, known_files, workspace_exists=None):
    known = {str(name).replace("\\", "/") for name in (known_files or [])}
    bases = {name.split("/")[-1] for name in known}
    exists = workspace_exists or {}
    out = []
    for item in actions:
        current = dict(item)
        current["parameters"] = dict(item.get("parameters") or {})
        current["tool_arguments"] = dict(item.get("tool_arguments") or {})
        intent = current.get("intent")
        status = current.get("status")
        if status in ("ambiguous", "not_a_tool", "no_action"):
            current["execute"] = False
            current["validated"] = status == "not_a_tool"
            current["validation_success"] = status != "no_action"
            out.append(current)
            continue
        if intent in ("READ", "OPEN"):
            current = _validate_read(current, known, bases, exists)
        elif intent == "SEARCH":
            current = _validate_search(current)
        elif intent == "PATCH":
            current = _validate_patch(current, known, bases, exists)
        elif intent == "RUN_TEST":
            current["validated"] = True
            current["validation_success"] = True
            current["execute"] = True
            current["status"] = "executable"
            current["tool_name"] = "run_test"
            current["tool_arguments"] = {}
        elif intent == "AMBIGUOUS":
            current["execute"] = False
            current["validated"] = True
            current["validation_success"] = True
            current["status"] = "ambiguous"
        else:
            current["execute"] = False
            current["validated"] = False
            current["validation_success"] = False
            current["status"] = "blocked"
            current["reason"] = "unknown_intent"
        out.append(current)
    return out


def _validate_read(current, known, bases, exists):
    path = current.get("target") or (current.get("tool_arguments") or {}).get("path")
    if not path:
        current["execute"] = False
        current["validated"] = True
        current["validation_success"] = True
        current["status"] = "unknown_target"
        current["reason"] = "inspect_without_file"
        return current
    posix = str(path).replace("\\", "/")
    in_known = posix in known or posix.split("/")[-1] in bases
    missing = exists.get(posix) is False or exists.get(posix.split("/")[-1]) is False
    if missing or not in_known:
        current["execute"] = False
        current["validated"] = True
        current["validation_success"] = True
        current["status"] = "missing_file"
        current["reason"] = "target_not_in_workspace"
        current["tool_name"] = None
        return current
    current["target"] = posix if posix in known else _resolve_base(posix, known)
    current["validated"] = True
    current["validation_success"] = True
    current["execute"] = True
    current["status"] = "executable"
    current["tool_name"] = "read_file"
    current["tool_arguments"] = {"path": current["target"]}
    return current


def _validate_search(current):
    query = (current.get("parameters") or {}).get("query") or (
        current.get("tool_arguments") or {}
    ).get("query")
    if not query:
        current["execute"] = False
        current["validated"] = True
        current["validation_success"] = True
        current["status"] = "ambiguous"
        current["reason"] = "search_without_query"
        return current
    if str(query).upper() in SEARCH_STOPWORDS or not str(query).isidentifier():
        current["execute"] = False
        current["validated"] = True
        current["validation_success"] = True
        current["status"] = "ambiguous"
        current["reason"] = "search_query_not_identifier"
        return current
    if not str(query).isupper() and "_" not in str(query):
        current["execute"] = False
        current["validated"] = True
        current["validation_success"] = True
        current["status"] = "ambiguous"
        current["reason"] = "search_query_not_identifier"
        return current
    current["validated"] = True
    current["validation_success"] = True
    current["execute"] = True
    current["status"] = "executable"
    current["tool_name"] = "search_files"
    current["tool_arguments"] = {"query": query}
    current["parameters"]["query"] = query
    return current


def _validate_patch(current, known, bases, exists):
    path = current.get("target")
    params = current.get("parameters") or {}
    assignments = params.get("assignments") or current.get("tool_arguments", {}).get(
        "assignments"
    )
    content = params.get("content") or current.get("tool_arguments", {}).get("content")
    if not assignments and not content:
        current["execute"] = False
        current["validated"] = True
        current["validation_success"] = True
        current["status"] = "ambiguous"
        current["reason"] = "patch_without_change"
        current["tool_name"] = None
        return current
    if not path:
        current["execute"] = False
        current["validated"] = True
        current["validation_success"] = True
        current["status"] = "unknown_target"
        current["reason"] = "patch_target_unknown"
        current["tool_name"] = None
        return current
    posix = str(path).replace("\\", "/")
    in_known = posix in known or posix.split("/")[-1] in bases
    missing = exists.get(posix) is False or exists.get(posix.split("/")[-1]) is False
    if missing or not in_known:
        current["execute"] = False
        current["validated"] = True
        current["validation_success"] = True
        current["status"] = "missing_file"
        current["reason"] = "target_not_in_workspace"
        current["tool_name"] = None
        return current
    resolved = posix if posix in known else _resolve_base(posix, known)
    current["target"] = resolved
    current["validated"] = True
    current["validation_success"] = True
    current["execute"] = True
    current["status"] = "executable"
    current["tool_name"] = "apply_patch"
    arguments = {"path": resolved}
    if content:
        arguments["content"] = content
    elif assignments:
        arguments["assignments"] = assignments
    current["tool_arguments"] = arguments
    return current


def _resolve_base(posix, known):
    base = posix.split("/")[-1]
    for name in known:
        if name.split("/")[-1] == base:
            return name
    return posix
