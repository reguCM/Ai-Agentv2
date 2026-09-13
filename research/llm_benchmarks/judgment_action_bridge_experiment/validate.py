"""機械検証。LLM の希望を別 Action に差し替えない。"""

from __future__ import annotations


def validate_actions(actions, known_files):
    known = {str(name).replace("\\", "/") for name in (known_files or [])}
    bases = {name.split("/")[-1] for name in known}
    out = []
    for item in actions:
        current = dict(item)
        tool = current.get("tool_name")
        args = current.get("tool_arguments") or {}
        path = args.get("path") or current.get("target")
        if current.get("status") in ("needs_clarification", "mapping_gap", "unresolved"):
            current["execute"] = False
            current["validated"] = False
            out.append(current)
            continue
        if tool == "read_file":
            if path not in known and (path or "").split("/")[-1] not in bases:
                current["execute"] = False
                current["status"] = "mapping_gap"
                current["selection_reason"] = "unknown_path"
                current["validated"] = False
            else:
                current["validated"] = True
        elif tool == "search_files":
            current["validated"] = True
            current["execute"] = False
        elif tool == "apply_patch":
            content = args.get("content")
            if not path or content is None or content == "":
                current["execute"] = False
                current["status"] = "mapping_gap"
                current["validated"] = False
            else:
                current["validated"] = True
        elif tool in ("run_test", "run_program", "list_files"):
            current["validated"] = True
        elif tool is None:
            current["execute"] = False
            current["validated"] = False
        else:
            current["execute"] = False
            current["status"] = "mapping_gap"
            current["selection_reason"] = "unknown_tool"
            current["validated"] = False
        out.append(current)
    return out
