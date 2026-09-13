"""仕様候補の追記ストア。同一要求でも上書きしない。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_tool.spec_proposal.paths import last_proposal_path, proposals_path


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_jsonl(path: Path | None = None) -> list[dict[str, Any]]:
    target = Path(path) if path is not None else proposals_path()
    if not target.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def next_version(request_id: str, path: Path | None = None) -> int:
    want = str(request_id or "").strip()
    if not want:
        return 1
    count = sum(1 for row in load_jsonl(path) if str(row.get("request_id") or "") == want)
    return count + 1


def append_proposal(record: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path is not None else proposals_path()
    _ensure_parent(target)
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return target


def save_last_proposal(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path is not None else last_proposal_path()
    _ensure_parent(target)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def load_last_proposal(path: Path | None = None) -> dict[str, Any] | None:
    target = Path(path) if path is not None else last_proposal_path()
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def list_by_request_id(request_id: str, path: Path | None = None) -> list[dict[str, Any]]:
    want = str(request_id or "").strip()
    if not want:
        return []
    return [row for row in load_jsonl(path) if str(row.get("request_id") or "") == want]


def get_by_proposal_id(proposal_id: str, path: Path | None = None) -> dict[str, Any] | None:
    want = str(proposal_id or "").strip()
    if not want:
        return None
    found = None
    for row in load_jsonl(path):
        if str(row.get("proposal_id") or "") == want:
            found = row
    return found


def list_by_parent_proposal_id(parent_proposal_id: str, path: Path | None = None) -> list[dict[str, Any]]:
    want = str(parent_proposal_id or "").strip()
    if not want:
        return []
    return [row for row in load_jsonl(path) if str(row.get("parent_proposal_id") or "") == want]
