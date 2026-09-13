"""
文単位で intent / target / parameters を取る。全文1本正規表現で Tool は選ばない。
コードフェンス内の READ/TEST/READY は Action にしない。
仮仕様: 正式 Schema ではない。既存 parse パッケージは import しない。
"""

from __future__ import annotations

import re


_FENCE = re.compile(r"```(?:python)?\n(?P<body>.*?)```", re.S)
_HASH_FILE = re.compile(r"^#\s*([\w./\\-]+\.py)\s*$", re.M)
_IDENTIFIER = re.compile(r"\b([A-Z][A-Z0-9_]{1,})\b")
_ASSIGNMENT = re.compile(
    r"\b([A-Z][A-Z0-9_]{1,})\s*=\s*([A-Za-z0-9_]+)\b"
)
_JP_ASSIGN = re.compile(
    r"([A-Z][A-Z0-9_]{1,})\s*を\s*([A-Za-z0-9_]+)\s*に"
)
_MODIFY_TO = re.compile(
    r"([A-Z][A-Z0-9_]{1,})\s*=\s*([A-Za-z0-9_]+)\s+to\s+"
    r"(?:[A-Z][A-Z0-9_]{1,}\s*=\s*)?([A-Za-z0-9_]+)",
    re.I,
)
_NEGATE_TEST = re.compile(
    r"(まだ.{0,12}実行しない|実行しない|don't (run )?(the )?tests?|do not run)",
    re.I,
)
_RUN_TEST = re.compile(
    r"("
    r"テストを(再)?実行|"
    r"Testを.{0,12}実行|"
    r"Testしてください|"
    r"pytest|"
    r"re-?run (your |the )?tests?|"
    r"run (your |the )?tests?"
    r")",
    re.I,
)
_READ = re.compile(
    r"(確認したい|確認します|確認する|確認してください|読む|読みます|読んで|"
    r"見て|調べる必要がある|"
    r"\binspect\b|\blook at\b|\bread\b|\bexamine\b|\breview\b|\bopen\b)",
    re.I,
)
_OPEN = re.compile(r"\bopen\b", re.I)
_SEARCH = re.compile(r"(探す|検索|\bsearch\b)", re.I)
_PATCH = re.compile(
    r"(変更する|修正する|書き換|問題があれば修正|"
    r"\bmodify\b|\bchange\b|\bpatch\b)",
    re.I,
)
_SAVE = re.compile(r"\bsave\b", re.I)
_BARE_AMBIGUOUS = re.compile(
    r"^(修正してください|確認してください|そこを直してください|調べてください)[。．.]?$",
)
_SLASH_ACTIONS = re.compile(
    r"^\s*open\s*/\s*modify\s*/\s*run your tests\s*$",
    re.I,
)

SEARCH_STOPWORDS = {
    "THE",
    "A",
    "AN",
    "IS",
    "AND",
    "OR",
    "TO",
    "FOR",
    "YOUR",
    "TEST",
    "TESTS",
    "PLEASE",
    "THIS",
    "THAT",
    "IT",
    "READ",
    "PATCH",
    "RUN",
    "OPEN",
    "MODIFY",
    "SAVE",
    "TRUE",
    "FALSE",
}


def parse_actions(text, known_files):
    text = text or ""
    known = _normalize_known(known_files)
    fences = _extract_fences(text, known)
    masked = _FENCE.sub("\n", text)
    clauses = _split_clauses(masked)
    actions = []
    last_file = None
    order = 0
    for clause in clauses:
        if not clause.strip():
            continue
        if _SLASH_ACTIONS.match(clause.strip()):
            for piece, intent in (
                ("Open", "OPEN"),
                ("Modify", "PATCH"),
                ("Run your tests", "RUN_TEST"),
            ):
                order += 1
                actions.append(_from_intent(order, intent, piece, known, None, fences))
            last_file = None
            continue
        built = _clause_to_action(clause, known, last_file, fences)
        if built is None:
            continue
        order += 1
        built["order"] = order
        built["id"] = f"a{order}"
        if built.get("target"):
            last_file = built["target"]
        elif built.get("parameters", {}).get("inherited_target"):
            last_file = built["parameters"]["inherited_target"]
        actions.append(built)
    if not actions:
        actions.append(
            _action(
                0,
                "AMBIGUOUS",
                None,
                text,
                {},
                "low",
                [],
                execute=False,
                status="ambiguous",
                reason="no_action",
            )
        )
    return actions, fences, clauses


def _clause_to_action(clause, known, last_file, fences):
    files = _files_in(clause, known)
    identifiers = [
        name for name in _IDENTIFIER.findall(clause) if name not in SEARCH_STOPWORDS
    ]
    assignments = _assignments_in(clause)
    negate_test = bool(_NEGATE_TEST.search(clause))
    run_test = bool(_RUN_TEST.search(clause)) and not negate_test
    save = bool(_SAVE.search(clause))
    patch = bool(_PATCH.search(clause)) or bool(_JP_ASSIGN.search(clause)) or bool(
        _MODIFY_TO.search(clause)
    )
    search = bool(_SEARCH.search(clause))
    read = bool(_READ.search(clause))
    open_word = bool(_OPEN.search(clause))
    if _BARE_AMBIGUOUS.match(clause.strip()):
        return _action(
            0,
            "AMBIGUOUS",
            None,
            clause,
            {},
            "low",
            [],
            execute=False,
            status="ambiguous",
            reason="bare_request",
        )
    if save and files and not patch and not run_test and not read:
        return _action(
            0,
            "SAVE",
            files[0],
            clause,
            {},
            "medium",
            [],
            execute=False,
            status="not_a_tool",
            reason="save_not_mapped",
        )
    if run_test:
        return _action(
            0,
            "RUN_TEST",
            None,
            clause,
            {},
            "high",
            [],
            execute=True,
            status="parsed",
            reason="explicit_run_test",
            tool_name="run_test",
            tool_arguments={},
        )
    if search or (identifiers and read and not files and not assignments):
        query = identifiers[0] if identifiers else None
        if query is None:
            return _action(
                0,
                "SEARCH",
                None,
                clause,
                {"query": None},
                "low",
                [],
                execute=False,
                status="ambiguous",
                reason="search_without_query",
            )
        return _action(
            0,
            "SEARCH",
            None,
            clause,
            {"query": query},
            "high",
            [],
            execute=True,
            status="parsed",
            reason="identifier_search",
            tool_name="search_files",
            tool_arguments={"query": query},
        )
    if patch or assignments:
        target = files[0] if files else None
        inherited = None
        if target is None and last_file:
            inherited = last_file
            target = last_file
            # 同一発話の直前ファイル。workspace からの推測ではない。
        fence = _fence_for(files, fences) if files else None
        parameters = {"assignments": assignments}
        if fence:
            parameters["content"] = fence["content"]
            target = target or fence["path"]
        if inherited:
            parameters["inherited_target"] = inherited
        if target is None and not assignments and not fence:
            return _action(
                0,
                "PATCH",
                None,
                clause,
                parameters,
                "low",
                [],
                execute=False,
                status="ambiguous",
                reason="patch_without_change",
            )
        if target is None:
            return _action(
                0,
                "PATCH",
                None,
                clause,
                parameters,
                "medium",
                [],
                execute=False,
                status="unknown_target",
                reason="patch_target_unknown",
            )
        tool_arguments = {"path": target}
        if fence:
            tool_arguments["content"] = fence["content"]
        elif assignments:
            tool_arguments["assignments"] = assignments
        else:
            return _action(
                0,
                "PATCH",
                target,
                clause,
                parameters,
                "low",
                [],
                execute=False,
                status="ambiguous",
                reason="patch_without_change",
            )
        return _action(
            0,
            "PATCH",
            target,
            clause,
            parameters,
            "high" if files or fence else "medium",
            ["inherit_previous_file"] if inherited and not files else [],
            execute=True,
            status="parsed",
            reason="named_patch" if files else "inherited_patch",
            tool_name="apply_patch",
            tool_arguments=tool_arguments,
        )
    if (read or open_word) and files:
        intent = "OPEN" if open_word and not re.search(r"(確認|読む|読み)", clause) else "READ"
        path = files[0]
        return _action(
            0,
            intent,
            path,
            clause,
            {},
            "high",
            [],
            execute=True,
            status="parsed",
            reason="named_file",
            tool_name="read_file",
            tool_arguments={"path": path},
        )
    if read or open_word:
        intent = "OPEN" if open_word else "READ"
        return _action(
            0,
            intent,
            None,
            clause,
            {},
            "low",
            [],
            execute=False,
            status="unknown_target",
            reason="inspect_without_file",
        )
    if files and not patch and not run_test:
        return None
    return None


def _from_intent(order, intent, clause, known, last_file, fences):
    if intent == "RUN_TEST":
        item = _action(
            order,
            "RUN_TEST",
            None,
            clause,
            {},
            "high",
            [],
            execute=True,
            status="parsed",
            reason="slash_run_test",
            tool_name="run_test",
            tool_arguments={},
        )
    elif intent == "OPEN":
        item = _action(
            order,
            "OPEN",
            None,
            clause,
            {},
            "low",
            [],
            execute=False,
            status="unknown_target",
            reason="open_without_file",
        )
    else:
        item = _action(
            order,
            "PATCH",
            None,
            clause,
            {},
            "low",
            [],
            execute=False,
            status="unknown_target",
            reason="modify_without_target",
        )
    item["id"] = f"a{order}"
    return item


def _action(
    order,
    intent,
    target,
    source,
    parameters,
    confidence,
    dependencies,
    execute,
    status,
    reason,
    tool_name=None,
    tool_arguments=None,
):
    return {
        "id": f"a{order}",
        "order": order,
        "intent": intent,
        "target": target,
        "parameters": parameters or {},
        "confidence": confidence,
        "dependencies": list(dependencies or []),
        "source_text": source,
        "execute": execute,
        "status": status,
        "reason": reason,
        "tool_name": tool_name,
        "tool_arguments": tool_arguments or {},
        "validated": False,
        "selected": False,
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
    found.sort(
        key=lambda name: blob.find(name.split("/")[-1])
        if name.split("/")[-1] in blob
        else blob.find(name)
    )
    return found


def _assignments_in(clause):
    found = []
    seen = set()
    for match in _JP_ASSIGN.finditer(clause):
        item = {"name": match.group(1), "value": match.group(2)}
        key = (item["name"], item["value"])
        if key not in seen:
            seen.add(key)
            found.append(item)
    for match in _MODIFY_TO.finditer(clause):
        item = {"name": match.group(1), "value": match.group(3)}
        key = (item["name"], item["value"])
        if key not in seen:
            seen.add(key)
            found.append(item)
    if found:
        return found
    for match in _ASSIGNMENT.finditer(clause):
        item = {"name": match.group(1), "value": match.group(2)}
        key = (item["name"], item["value"])
        if key not in seen:
            seen.add(key)
            found.append(item)
    return found


def _split_clauses(text):
    prepared = re.sub(r"\n?\s*\d+\.\s+", "\n", text)
    pieces = []
    for line in re.split(r"\n+", prepared):
        line = line.strip()
        if not line:
            continue
        if _SLASH_ACTIONS.match(line):
            pieces.append(line)
            continue
        parts = re.split(r"(?<=[。．])|(?<=[a-z0-9'\"\)])\.\s+", line)
        for part in parts:
            part = part.strip(" *")
            if part:
                pieces.append(part)
    return pieces


def _extract_fences(text, known):
    items = []
    known_set = set(known)
    bases = {name.split("/")[-1]: name for name in known}
    for match in _FENCE.finditer(text or ""):
        body = match.group("body") or ""
        before = text[: match.start()]
        label = ""
        tail = before[-80:].replace("\\", "/")
        for name in known:
            base = name.split("/")[-1]
            if base in tail:
                label = name
        hashed = _HASH_FILE.search(body)
        path = label
        if hashed:
            path = hashed.group(1).replace("\\", "/")
        if path in bases:
            path = bases[path]
        if path not in known_set and path.split("/")[-1] in bases:
            path = bases[path.split("/")[-1]]
        if path not in known_set:
            path = None
        items.append({"path": path, "content": body, "start": match.start()})
    return items


def _fence_for(files, fences):
    if not fences:
        return None
    if files:
        for item in fences:
            if item.get("path") in files:
                return item
    named = [item for item in fences if item.get("path")]
    if len(named) == 1:
        return named[0]
    return None
