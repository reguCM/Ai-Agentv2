"""
過去失敗の再現用。全文に正規表現をかけ、フェンスを無視し、1件だけ選ぶ。
既存 Mapping のコピーではない。仕様でもない。
"""

from __future__ import annotations

import re


_READ = re.compile(r"(読む|読みたい|\bread\b)", re.I)
_TEST = re.compile(r"(テストを実行|run (the )?tests?|\bTEST\b)", re.I)
_PATCH = re.compile(r"(\bPATCH\b|\bREADY\b)", re.I)


def naive_select(text, known_files):
    text = text or ""
    files = []
    for name in known_files or []:
        posix = str(name).replace("\\", "/")
        base = posix.split("/")[-1]
        if base in text and posix not in files:
            files.append(posix)
    read = bool(_READ.search(text))
    test = bool(_TEST.search(text))
    patch = bool(_PATCH.search(text))
    chosen = None
    if test:
        chosen = {
            "tool_name": "run_test",
            "tool_arguments": {},
            "reason": "naive_fulltext_TEST",
        }
    elif read and files:
        chosen = {
            "tool_name": "read_file",
            "tool_arguments": {"path": files[0]},
            "reason": "naive_fulltext_read",
        }
    elif patch:
        chosen = {
            "tool_name": "apply_patch",
            "tool_arguments": {},
            "reason": "naive_fulltext_READY_or_PATCH",
        }
    return {
        "input_text": text,
        "selected_actions": [chosen] if chosen else [],
        "mapping_status": "selected" if chosen else "unrecognized",
        "naive": True,
        "file_mentions": files,
        "flags": {"read": read, "test": test, "patch": patch},
    }
