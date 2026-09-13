"""
暫定 Mapping。正式規則ではない。
判断失敗と Mapping 不能を同一視しない。
inspect helper.py → read_file は実行する。
「rows の生成元」だけなら実行しない（Mapping 不能として記録）。
"""

from __future__ import annotations

import re


INSPECT = re.compile(
    r"(read|inspect|check|examine|review|open|look at|confirm|確認|読む|読ん|調べ|見て)",
    re.I,
)
LIST_HINT = re.compile(r"\b(list files|list the files|what files|ファイル一覧)", re.I)
TEST_HINT = re.compile(r"\b(run (the )?tests?|re-?run pytest|pytest を|テストを(再)?実行)", re.I)
PROGRAM_HINT = re.compile(r"\b(run (python )?main\.py|main\.py を実行)", re.I)
WRITE_HINT = re.compile(r"\b(fix|patch|change|update|write|replace|修正|書き換)", re.I)
ORIGIN_HINT = re.compile(
    r"(code that creates|where .{0,40}(come from|generated|defined)|生成元|どこから)",
    re.I,
)
_FENCE = re.compile(
    r"(?:(?P<label>[\w./\\-]+\.py)\s*\n)?```(?:python)?\n(?P<body>.*?)```",
    re.S,
)
_HASH_FILE = re.compile(r"^#\s*([\w./\\-]+\.py)\s*$", re.M)


def classify_mapping(text, known_files):
    text = text or ""
    known = _normalize_known(known_files)
    files_mentioned = _files_mentioned(text, known)
    fences = _fences(text, known)
    candidates = []

    for path in files_mentioned:
        if _near_inspect(text, path):
            candidates.append(_item("M1", "inspect_named_file", path, "read", "read_file", {"path": path}, True))
        else:
            candidates.append(
                _item("M2", "named_file_without_inspect", path, "read", "read_file", {"path": path}, False)
            )

    if LIST_HINT.search(text):
        candidates.append(
            _item("M1", "list_files", ".", "list", "list_files", {"recursive": True}, True)
        )
    if TEST_HINT.search(text):
        candidates.append(_item("M1", "run_test", "tests", "run_test", "run_test", {}, True))
    if PROGRAM_HINT.search(text):
        candidates.append(_item("M1", "run_program", "main.py", "run_program", "run_program", {}, True))

    allow_patch = bool(WRITE_HINT.search(text)) or not any(item["execute"] and item["action"] == "read" for item in candidates)
    for item in fences:
        candidates.append(
            _item(
                "M1" if allow_patch else "M2",
                "named_code_fence",
                item["path"],
                "write",
                "apply_patch",
                {"path": item["path"], "content": item["content"]},
                allow_patch,
            )
        )

    if ORIGIN_HINT.search(text) and not any(item["execute"] for item in candidates):
        candidates.append(
            {
                "status": "mapping_gap",
                "reason": "origin_without_filename",
                "target": None,
                "action": None,
                "tool_name": None,
                "tool_arguments": {},
                "execute": False,
                "not_llm_failure": True,
            }
        )

    if not candidates:
        candidates.append(
            {
                "status": "mapping_gap",
                "reason": "no_mechanical_target",
                "target": None,
                "action": None,
                "tool_name": None,
                "tool_arguments": {},
                "execute": False,
                "not_llm_failure": True,
            }
        )

    executable = [item for item in candidates if item.get("execute")]
    chosen = _prefer(executable)
    return {
        "provisional": True,
        "candidates": candidates,
        "mapping_status": chosen["status"] if chosen else "mapping_gap",
        "mapping_output": chosen,
        "execute": chosen,
        "unexecuted_reason": None if chosen else "no_executable_mapping",
    }


def _item(status, reason, target, action, tool_name, arguments, execute):
    return {
        "status": status,
        "reason": reason,
        "target": target,
        "action": action,
        "tool_name": tool_name,
        "tool_arguments": arguments,
        "execute": execute,
        "not_llm_failure": status in ("M2", "mapping_gap"),
    }


def _prefer(executable):
    order = ["read", "list", "search", "run_test", "run_program", "write"]
    ranked = sorted(executable, key=lambda item: order.index(item["action"]) if item["action"] in order else 99)
    return ranked[0] if ranked else None


def _normalize_known(known_files):
    out = []
    for name in known_files or []:
        posix = str(name).replace("\\", "/")
        out.append(posix)
    return sorted(set(out), key=len, reverse=True)


def _files_mentioned(text, known):
    found = []
    blob = text.replace("\\", "/")
    for name in known:
        base = name.split("/")[-1]
        if name in blob or re.search(rf"(?<![\w./]){re.escape(base)}(?![\w])", blob):
            if name not in found:
                found.append(name)
    return found


def _near_inspect(text, path):
    base = path.split("/")[-1]
    for match in re.finditer(re.escape(path) + r"|" + re.escape(base), text.replace("\\", "/")):
        start = max(0, match.start() - 64)
        end = min(len(text), match.end() + 64)
        if INSPECT.search(text[start:end]):
            return True
    return False


def _fences(text, known):
    items = []
    known_set = set(known)
    bases = {name.split("/")[-1]: name for name in known}
    for match in _FENCE.finditer(text):
        body = match.group("body") or ""
        label = (match.group("label") or "").replace("\\", "/")
        hashed = _HASH_FILE.search(body)
        path = label or (hashed.group(1).replace("\\", "/") if hashed else "")
        if path in bases:
            path = bases[path]
        if path not in known_set and path.split("/")[-1] in bases:
            path = bases[path.split("/")[-1]]
        if path not in known_set:
            continue
        if "def " not in body and "=" not in body:
            continue
        items.append({"path": path, "content": body})
    return items
