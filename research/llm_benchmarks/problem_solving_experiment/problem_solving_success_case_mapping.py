"""
実験側の保守的 NL→Tool 接続。正式 Mapping Schema ではない。

実行するのは、出力から具体的なファイル名・識別子・一覧要求が取れたときだけ。
「コードが必要」「ログが必要」だけでは変換しない。
LLM に Tool 名は出させていない。catalog も渡していない。
"""

from __future__ import annotations

import re
from pathlib import Path

from research.llm_benchmarks.problem_solving_experiment.problem_solving_success_case_fixture import (
    FIXTURE_DIR,
    fixture_rel_dir,
    fixture_rel_files,
)


# 事実の言い直しと要求を分けるための要求側キーワード。Schema ではない。
_REQUEST_EN = (
    r"(?:need(?:ed)?(?:\s+to)?|require(?:d)?|should(?:\s+\w+)?|"
    r"want(?:\s+to)?|please|"
    r"read|inspect|check|examine|open|review|investigate|fetch|"
    r"look(?:ing)?\s+at|see|show|get|obtain|retrieve|"
    r"implementation|definition|source|contents?|body)"
)
_REQUEST_JA = (
    r"(?:必要|確認|読[むんで]|見[てる]|中身|実装|内容|取得|開[きく]|"
    r"調べ|参照|ソース)"
)
_REQUEST = re.compile(_REQUEST_EN + r"|" + _REQUEST_JA, re.IGNORECASE)

_PY_FILE = re.compile(
    r"(?:`(?P<tick>[^`\n]+\.py)`|"
    r"(?P<path>(?:[A-Za-z]:)?(?:[/\\][\w.\-]+)+\.py)|"
    r"(?P<base>\b[\w.\-]+\.py\b))",
    re.IGNORECASE,
)

_IDENT = re.compile(
    r"(?:`(?P<tick>[A-Za-z_][A-Za-z0-9_]*)`|"
    r"(?:function|def|implementation|definition|symbol|identifier|関数)\s+"
    r"(?P<label>[A-Za-z_][A-Za-z0-9_]*)|"
    r"(?P<call>\b[A-Za-z_][A-Za-z0-9_]*)\s*\(\))",
)

_LIST_DIR = re.compile(
    r"(?:list(?:\s+the)?\s+files|directory\s+listing|project\s+structure|"
    r"what\s+files|which\s+files|ファイル(?:一?覧|構成)|どのファイル)",
    re.IGNORECASE,
)

_VAGUE = re.compile(
    r"(?:more\s+(?:code|logs?|information|context)|"
    r"(?:source|code|logs?)\s+(?:is\s+)?needed|"
    r"追加(?:情報|コード|ログ)|コードが必要|ログが必要)",
    re.IGNORECASE,
)

_SKIP_BASENAMES = frozenset(
    {
        "traceback.py",
        "<stdin>.py",
    }
)


def _window(text, start, end, radius=140):
    return text[max(0, start - radius) : min(len(text), end + radius)]


def _basename(raw):
    return Path(str(raw).replace("\\", "/")).name.lower()


def extract_py_mentions(text):
    found = []
    seen = set()
    for match in _PY_FILE.finditer(text or ""):
        raw = match.group("tick") or match.group("path") or match.group("base")
        if not raw:
            continue
        key = raw.replace("\\", "/").lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(
            {
                "raw": raw,
                "basename": _basename(raw),
                "span": [match.start(), match.end()],
                "near_request": bool(_REQUEST.search(_window(text, match.start(), match.end()))),
            }
        )
    return found


def extract_identifier_mentions(text):
    found = []
    seen = set()
    for match in _IDENT.finditer(text or ""):
        raw = match.group("tick") or match.group("label") or match.group("call")
        if not raw or raw.lower() in seen:
            continue
        if raw in {"IndexError", "RuntimeError", "AttributeError", "ValidationError"}:
            continue
        seen.add(raw.lower())
        found.append(
            {
                "raw": raw,
                "span": [match.start(), match.end()],
                "near_request": bool(_REQUEST.search(_window(text, match.start(), match.end()))),
            }
        )
    return found


def _resolve_fixture_file(basename):
    files = fixture_rel_files()
    for name, rel in files.items():
        if name.lower() == basename.lower():
            return rel
    return None


def map_information_requests(text, *, already_done=None):
    """
    変換できた要求を出現順で返す。変換不能は unmapped に残す。
    already_done: 実行済みの (tool, canonical_path_or_query) タプル。
    """
    already = set(already_done or [])
    text = text or ""
    mapped = []
    unmapped = []
    mentions = extract_py_mentions(text)

    for item in mentions:
        if item["basename"] in _SKIP_BASENAMES:
            continue
        if not item["near_request"]:
            unmapped.append(
                {
                    "reason": "filename_mentioned_without_request",
                    "raw": item["raw"],
                }
            )
            continue
        rel = _resolve_fixture_file(item["basename"])
        if rel is None:
            unmapped.append(
                {
                    "reason": "filename_not_in_fixture",
                    "raw": item["raw"],
                    "note": "fixture 外のパスへは実験では接続しない",
                }
            )
            continue
        key = ("read_file", rel)
        if key in already:
            unmapped.append({"reason": "already_read", "raw": item["raw"], "path": rel})
            continue
        mapped.append(
            {
                "tool_selected": "read_file",
                "tool_arguments": {"path": rel},
                "requested_information": item["raw"],
                "mapping_note": "basename matched fixture file near a request keyword",
                "done_key": key,
            }
        )

    if _LIST_DIR.search(text):
        rel_dir = fixture_rel_dir()
        key = ("list_files", rel_dir)
        if key not in already:
            mapped.append(
                {
                    "tool_selected": "list_files",
                    "tool_arguments": {
                        "path": rel_dir,
                        "recursive": False,
                    },
                    "requested_information": "directory listing",
                    "mapping_note": (
                        "list request scoped to this case fixture directory "
                        "(not the whole repository)"
                    ),
                    "done_key": key,
                }
            )
        else:
            unmapped.append({"reason": "already_listed", "path": rel_dir})

    for item in extract_identifier_mentions(text):
        if not item["near_request"]:
            continue
        if any(
            candidate["tool_selected"] == "read_file"
            for candidate in mapped
        ):
            break
        query = item["raw"]
        rel_dir = fixture_rel_dir()
        key = ("search_files", query)
        if key in already:
            continue
        mapped.append(
            {
                "tool_selected": "search_files",
                "tool_arguments": {
                    "query": query,
                    "path": rel_dir,
                    "glob": "*.py",
                },
                "requested_information": item["raw"],
                "mapping_note": (
                    "identifier near a request keyword; search scoped to fixture"
                ),
                "done_key": key,
            }
        )

    vague = bool(_VAGUE.search(text))
    if vague and not mapped:
        unmapped.append({"reason": "vague_code_or_logs_only"})

    return {
        "mapped": mapped,
        "unmapped": unmapped,
        "mentions": mentions,
        "vague_without_file": vague and not mapped,
    }


def next_mapping(text, *, already_done=None):
    result = map_information_requests(text, already_done=already_done)
    if result["mapped"]:
        return result["mapped"][0], result
    return None, result
