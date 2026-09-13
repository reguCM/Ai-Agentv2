"""
判断文を Action 候補へ分解する。既存 Mapping は使わない。
コードフェンス内の READ/TEST/READY は Action にしない。
仮仕様: 文単位で intent と target を取る。正式 Schema ではない。
"""

from __future__ import annotations

import re


_FENCE = re.compile(
    r"(?:(?P<label>[\w./\\-]+\.py)\s*\n)?```(?:python)?\n(?P<body>.*?)```",
    re.S,
)
_INSPECT = re.compile(
    r"(確認|読む|読み|読ん|調べ|調査|見て|inspect|look at|\bread\b|\bcheck\b|\bexamine\b|\breview\b)",
    re.I,
)
_RUN_TEST = re.compile(
    r"(テストを(再)?実行|pytest を|run (the )?tests?|テストしたい|Testしたい|Testを実行)",
    re.I,
)
_PATCH = re.compile(r"(修正する|書き換|\bapply_patch\b|patch (the )?file|\bpatch\s+[\w./-]+\.py)", re.I)
_LIST = re.compile(r"(ファイル一覧|list files|list the files)", re.I)
_NEGATE_TEST = re.compile(
    r"(まだ.{0,12}実行しない|実行しない|don't (run )?(the )?tests?|do not run)",
    re.I,
)
_HASH_FILE = re.compile(r"^#\s*([\w./\\-]+\.py)\s*$", re.M)


def parse_actions(text, known_files):
    text = text or ""
    known = _normalize_known(known_files)
    fences = _extract_fences(text, known)
    masked = _FENCE.sub("\n", text)
    clauses = _split_clauses(masked)
    actions = []
    order = 0
    for clause in clauses:
        if not clause.strip():
            continue
        files = _files_in(clause, known)
        inspect = bool(_INSPECT.search(clause))
        run_test = bool(_RUN_TEST.search(clause))
        patch = bool(_PATCH.search(clause))
        listed = bool(_LIST.search(clause))
        negate_test = bool(_NEGATE_TEST.search(clause))
        if negate_test:
            run_test = False
        if listed:
            order += 1
            actions.append(_action(order, "list_files", None, clause, "list_files", {"recursive": True}, True, "explicit_list"))
        if inspect and files:
            for path in files:
                order += 1
                actions.append(
                    _action(order, "inspect", path, clause, "read_file", {"path": path}, True, "inspect_named_file")
                )
                actions.append(
                    _action(
                        order,
                        "inspect",
                        path,
                        clause,
                        "search_files",
                        {"query": path.split("/")[-1]},
                        False,
                        "alternate_search",
                    )
                )
        elif inspect and not files:
            order += 1
            actions.append(
                _action(order, "inspect", None, clause, None, {}, False, "needs_clarification", status="needs_clarification")
            )
        if patch:
            matched = [item for item in fences if item["path"] in files or (not files and item["path"])]
            if files:
                matched = [item for item in fences if item["path"] in files]
            if matched:
                for item in matched:
                    order += 1
                    actions.append(
                        _action(
                            order,
                            "apply_patch",
                            item["path"],
                            clause,
                            "apply_patch",
                            {"path": item["path"], "content": item["content"]},
                            True,
                            "named_code_fence",
                        )
                    )
            else:
                order += 1
                actions.append(
                    _action(order, "apply_patch", None, clause, None, {}, False, "mapping_gap", status="mapping_gap")
                )
        if run_test:
            order += 1
            actions.append(_action(order, "run_test", None, clause, "run_test", {}, True, "explicit_run_test"))
    if not actions:
        actions.append(
            _action(0, "unresolved", None, text, None, {}, False, "mapping_gap", status="mapping_gap")
        )
    return actions, fences, clauses


def _action(order, intent, target, source, tool_name, arguments, execute, reason, status=None):
    if status is None:
        status = "executable" if execute else "candidate"
    return {
        "order": order,
        "intent": intent,
        "target": target,
        "source_text": source,
        "tool_name": tool_name,
        "tool_arguments": arguments,
        "execute": execute,
        "reason": reason,
        "status": status,
        "selection_reason": reason,
    }


def _normalize_known(known_files):
    out = []
    for name in known_files or []:
        posix = str(name).replace("\\", "/")
        out.append(posix)
    return sorted(set(out), key=len, reverse=True)


def _files_in(text, known):
    found = []
    blob = text.replace("\\", "/")
    for name in known:
        base = name.split("/")[-1]
        if name in blob or re.search(rf"(?<![\w./]){re.escape(base)}(?![\w])", blob):
            if name not in found:
                found.append(name)
    found.sort(key=lambda name: blob.find(name.split("/")[-1]) if name.split("/")[-1] in blob else blob.find(name))
    return found


def _split_clauses(text):
    pieces = []
    for line in re.split(r"\n+", text):
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[。．])", line)
        for part in parts:
            part = part.strip()
            if part:
                pieces.append(part)
    return pieces


def _extract_fences(text, known):
    items = []
    known_set = set(known)
    bases = {name.split("/")[-1]: name for name in known}
    for match in _FENCE.finditer(text or ""):
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
        items.append({"path": path, "content": body})
    return items
