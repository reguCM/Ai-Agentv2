"""
仮の機械的 Mapping。正式規則ではない。Schema でもない。
M1 だけ自動実行する。M2 以降は記録のみ。
LLM 失敗と Mapping 不足を混ぜない。
"""

from __future__ import annotations

import re


READ_HINT = re.compile(
    r"(read|check|inspect|examine|review|open|look at|確認|読む|読ん|調べ|見て)",
    re.I,
)
LIST_HINT = re.compile(r"\b(list files|list the files|what files|ファイル一覧|ファイルを列挙)", re.I)
TEST_HINT = re.compile(r"\b(run (the )?tests?|re-?run pytest|pytest を|テストを(再)?実行)", re.I)
PROGRAM_HINT = re.compile(r"\b(run (python )?main\.py|main\.py を実行)", re.I)
ORIGIN_HINT = re.compile(
    r"(where .{0,40}(come from|generated|defined)|生成元|どこから|定義を確認)",
    re.I,
)
VAGUE = re.compile(
    r"(related code|relevant code|further (investigation|analysis)|さらに調査|関連するコード)",
    re.I,
)
STOP_SEARCH = {
    "the",
    "a",
    "an",
    "to",
    "of",
    "and",
    "or",
    "may",
    "might",
    "should",
    "need",
    "check",
    "code",
    "file",
    "error",
    "problem",
    "issue",
}

_FENCE = re.compile(
    r"(?:(?P<label>[\w./\\-]+\.py)\s*\n)?```(?:python)?\n(?P<body>.*?)```",
    re.S,
)
_HASH_FILE = re.compile(r"^#\s*([\w./\\-]+\.py)\s*$", re.M)


def classify_mapping(text, known_files):
    """
    戻り値は観測用。正式 Mapping 仕様ではない。
    executed 対象は M1 の先頭 1 件のみ（呼び出し側）。
    """
    text = text or ""
    known = _normalize_known(known_files)
    fences = _fences(text, known)
    files_mentioned = _files_mentioned(text, known)
    candidates = []

    for item in fences:
        candidates.append(
            {
                "status": "M1",
                "reason": "named_code_fence",
                "target": item["path"],
                "action": "write",
                "tool_name": "apply_patch",
                "tool_arguments": {"path": item["path"], "content": item["content"]},
                "execute": True,
            }
        )

    if TEST_HINT.search(text):
        candidates.append(
            {
                "status": "M1",
                "reason": "explicit_run_test",
                "target": "tests",
                "action": "run_test",
                "tool_name": "run_test",
                "tool_arguments": {},
                "execute": True,
            }
        )
    if PROGRAM_HINT.search(text):
        candidates.append(
            {
                "status": "M1",
                "reason": "explicit_run_program",
                "target": "main.py",
                "action": "run_program",
                "tool_name": "run_program",
                "tool_arguments": {},
                "execute": True,
            }
        )
    if LIST_HINT.search(text):
        candidates.append(
            {
                "status": "M1",
                "reason": "explicit_list_files",
                "target": ".",
                "action": "list",
                "tool_name": "list_files",
                "tool_arguments": {"recursive": True},
                "execute": True,
            }
        )

    for path in files_mentioned:
        if any(item.get("target") == path and item.get("tool_name") == "apply_patch" for item in candidates):
            continue
        if _file_has_read_intent(text, path):
            candidates.append(
                {
                    "status": "M1",
                    "reason": "named_file_with_read_intent",
                    "target": path,
                    "action": "read",
                    "tool_name": "read_file",
                    "tool_arguments": {"path": path},
                    "execute": True,
                }
            )
        else:
            candidates.append(
                {
                    "status": "M2",
                    "reason": "named_file_without_clear_action",
                    "target": path,
                    "action": "read",
                    "tool_name": "read_file",
                    "tool_arguments": {"path": path},
                    "execute": False,
                }
            )

    if ORIGIN_HINT.search(text) and not any(item["status"] == "M1" and item["action"] == "read" for item in candidates):
        symbol = _origin_symbol(text)
        if symbol and symbol.lower() not in STOP_SEARCH:
            candidates.append(
                {
                    "status": "M2",
                    "reason": "origin_phrase_without_filename",
                    "target": symbol,
                    "action": "search",
                    "tool_name": "search_files",
                    "tool_arguments": {"query": symbol},
                    "execute": False,
                }
            )

    if VAGUE.search(text) and not candidates:
        candidates.append(
            {
                "status": "M3",
                "reason": "vague_related_code",
                "target": None,
                "action": None,
                "tool_name": None,
                "tool_arguments": {},
                "execute": False,
            }
        )

    if _looks_like_stopword_search(text) and not files_mentioned:
        word = _stopword_hit(text)
        candidates.append(
            {
                "status": "M5",
                "reason": "stopword_would_mislead_search",
                "target": word,
                "action": "search",
                "tool_name": "search_files",
                "tool_arguments": {"query": word},
                "execute": False,
            }
        )

    if not candidates:
        candidates.append(
            {
                "status": "M4",
                "reason": "no_mechanical_target",
                "target": None,
                "action": None,
                "tool_name": None,
                "tool_arguments": {},
                "execute": False,
            }
        )

    executable = [item for item in candidates if item.get("execute")]
    chosen = executable[0] if executable else None
    statuses = sorted({item["status"] for item in candidates})
    return {
        "provisional": True,
        "not_official_mapping_spec": True,
        "candidates": candidates,
        "mapping_status": chosen["status"] if chosen else statuses[0],
        "mapping_result": chosen,
        "execute": chosen,
        "unexecuted_reason": None if chosen else "no_M1_or_not_mechanical",
    }


def _normalize_known(known_files):
    out = []
    for name in known_files or []:
        posix = str(name).replace("\\", "/")
        out.append(posix)
        if posix.startswith("tests/"):
            out.append(posix.split("/", 1)[1])
    return sorted(set(out), key=len, reverse=True)


def _files_mentioned(text, known):
    found = []
    lower = text.replace("\\", "/")
    for name in known:
        if name in lower or name.split("/")[-1] in _basename_hits(lower, name):
            if name not in found:
                found.append(name)
    return found


def _basename_hits(text, name):
    base = name.split("/")[-1]
    if re.search(rf"(?<![\w./]){re.escape(base)}(?![\w])", text):
        return [base]
    return []


def _file_has_read_intent(text, path):
    base = path.split("/")[-1]
    for match in re.finditer(re.escape(path) + r"|" + re.escape(base), text):
        start = max(0, match.start() - 48)
        end = min(len(text), match.end() + 48)
        if READ_HINT.search(text[start:end]):
            return True
    return False


def _fences(text, known):
    items = []
    known_set = set(known)
    known_bases = {name.split("/")[-1]: name for name in known}
    for match in _FENCE.finditer(text):
        body = match.group("body") or ""
        label = (match.group("label") or "").replace("\\", "/")
        hashed = _HASH_FILE.search(body)
        path = label or (hashed.group(1).replace("\\", "/") if hashed else "")
        if path in known_bases:
            path = known_bases[path]
        if path not in known_set and path.split("/")[-1] in known_bases:
            path = known_bases[path.split("/")[-1]]
        if path not in known_set:
            continue
        if "def " not in body and "=" not in body:
            continue
        items.append({"path": path, "content": body})
    return items


def _origin_symbol(text):
    match = re.search(
        r"`([A-Za-z_][A-Za-z0-9_]*)`|([A-Za-z_][A-Za-z0-9_]*)\s*(がどこ|の生成|is generated|come from)",
        text,
    )
    if not match:
        return None
    return match.group(1) or match.group(2)


def _looks_like_stopword_search(text):
    return bool(re.search(r"\b(look up|search(?:\s+for)?|調べ[るて])\s+['\"]?may['\"]?", text, re.I))


def _stopword_hit(text):
    match = re.search(r"\b(may|might)\b", text, re.I)
    return match.group(1) if match else "may"
