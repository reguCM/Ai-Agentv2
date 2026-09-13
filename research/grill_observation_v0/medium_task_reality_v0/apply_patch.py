"""Apply Local-Implementer patches. Harness only; does not invent replacements."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

UPDATE_RE = re.compile(
    r"\*\*\*\s*UPDATE:\s*(?P<path>\S+)\s*"
    r"\*\*\*\s*SEARCH\s*\n(?P<search>.*?)\n"
    r"\*\*\*\s*REPLACE\s*\n(?P<replace>.*?)\n"
    r"\*\*\*\s*END",
    re.S,
)
FILE_RE = re.compile(
    r"\*\*\*\s*FILE:\s*(?P<path>\S+)\s*\n```(?:python)?\n(?P<body>.*?)\n```",
    re.S,
)
FENCE_PATH_RE = re.compile(
    r"```(?:python:)?(?P<path>[\w./\\-]+\.py)\n(?P<body>.*?)\n```",
    re.S,
)


def strip_think(raw: str) -> str:
    return re.sub(r"<think>.*?</think>", "", str(raw or ""), flags=re.S).strip()


def _normalize_rel(path: str) -> str:
    p = str(path or "").strip().replace("\\", "/")
    p = p.lstrip("./")
    if p.startswith("research/") and "/workspace/" in p:
        p = "workspace/" + p.split("/workspace/", 1)[1]
    if p.startswith("research/") and "/tests/" in p:
        p = "tests/" + p.split("/tests/", 1)[1]
    if p.startswith("medium_task_reality_v0/"):
        p = p.split("medium_task_reality_v0/", 1)[1]
    return p


def resolve_allowed(rel: str, *, here: Path, allowed_write: set[str]) -> Path | None:
    rel_n = _normalize_rel(rel)
    allowed_n = {_normalize_rel(a) for a in allowed_write}
    if rel_n not in allowed_n:
        base = Path(rel_n).name
        matches = [a for a in allowed_n if Path(a).name == base]
        if len(matches) != 1:
            return None
        rel_n = matches[0]
    target = (here / rel_n).resolve()
    here_r = here.resolve()
    try:
        target.relative_to(here_r)
    except ValueError:
        return None
    if not (str(target).startswith(str((here / "workspace").resolve())) or str(target).startswith(str((here / "tests").resolve()))):
        return None
    return target


def apply_implementer_output(
    raw: str,
    *,
    here: Path,
    allowed_write: set[str],
) -> dict[str, Any]:
    text = strip_think(raw)
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    errors: list[str] = []

    updates = list(UPDATE_RE.finditer(text))
    files = list(FILE_RE.finditer(text))
    if not files:
        files = list(FENCE_PATH_RE.finditer(text))

    if not updates and not files:
        return {
            "applied": applied,
            "rejected": rejected,
            "errors": ["no_patch_blocks_parsed"],
            "would_write": [],
        }

    for m in updates:
        rel = _normalize_rel(m.group("path"))
        target = resolve_allowed(rel, here=here, allowed_write=allowed_write)
        if target is None:
            rejected.append({"path": rel, "reason": "not_in_allowed_write_or_unsafe"})
            continue
        if not target.is_file():
            rejected.append({"path": rel, "reason": "target_missing_for_update"})
            continue
        original = target.read_text(encoding="utf-8")
        search = m.group("search")
        replace = m.group("replace")
        if search not in original:
            errors.append(f"search_not_found:{rel}")
            continue
        count = original.count(search)
        if count != 1:
            errors.append(f"search_not_unique:{rel}:{count}")
            continue
        target.write_text(original.replace(search, replace, 1), encoding="utf-8")
        applied.append({"path": rel, "kind": "update"})

    for m in files:
        rel = _normalize_rel(m.group("path"))
        target = resolve_allowed(rel, here=here, allowed_write=allowed_write)
        if target is None:
            rejected.append({"path": rel, "reason": "not_in_allowed_write_or_unsafe"})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(m.group("body") + "\n", encoding="utf-8")
        applied.append({"path": rel, "kind": "file"})

    return {
        "applied": applied,
        "rejected": rejected,
        "errors": errors,
        "would_write": [a["path"] for a in applied],
    }
