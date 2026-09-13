"""JSONL 追記ストア。上書き削除しない。LLM は使わない。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_tool.matrix.models import MatrixRecord
from ai_tool.matrix.paths import (
    last_ingest_path,
    last_trace_path,
    last_verify_path,
    last_ask_path,
    records_path,
    retractions_path,
    verify_log_path,
)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


class MatrixStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else records_path()

    def append(self, record: MatrixRecord) -> None:
        _ensure_parent(self.path)
        line = json.dumps(record.to_dict(), ensure_ascii=False) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def append_many(self, records: list[MatrixRecord]) -> None:
        for record in records:
            self.append(record)

    def get_by_id(self, record_id: str) -> dict[str, Any] | None:
        want = str(record_id or "").strip()
        if not want:
            return None
        for row in self.all_records():
            if str(row.get("record_id") or "") == want:
                return row
        return None

    def all_records(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
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


def load_retracted_ids(path: Path | None = None) -> set[str]:
    target = Path(path) if path is not None else retractions_path()
    if not target.is_file():
        return set()
    ids: set[str] = set()
    for line in target.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("record_id"):
            ids.add(str(item["record_id"]))
    return ids


def append_retraction(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path is not None else retractions_path()
    _ensure_parent(target)
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return target


def search_records(
    records: list[dict[str, Any]],
    *,
    q: str | None = None,
    entity: str | None = None,
    attribute: str | None = None,
    retracted_ids: set[str] | None = None,
    include_retracted: bool = False,
) -> list[dict[str, Any]]:
    """機械的検索。自然言語理解はしない。既定では retraction 済みを除外する。"""
    q_norm = (q or "").strip().casefold()
    ent = (entity or "").strip().casefold()
    attr = (attribute or "").strip().casefold()
    hidden = set() if include_retracted else (retracted_ids if retracted_ids is not None else load_retracted_ids())
    out: list[dict[str, Any]] = []
    for row in records:
        rid = str(row.get("record_id") or "")
        if rid and rid in hidden:
            continue
        entity_v = str(row.get("entity") or "").casefold()
        attr_v = str(row.get("attribute") or "").casefold()
        value_v = str(row.get("value") or "").casefold()
        title_v = str(row.get("source_title") or "").casefold()
        if ent and ent not in entity_v:
            continue
        if attr and attr not in attr_v:
            continue
        if q_norm:
            blob = " ".join([entity_v, attr_v, value_v, title_v])
            if q_norm not in blob:
                continue
        out.append(row)
    return out


def save_last_ingest(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path is not None else last_ingest_path()
    _ensure_parent(target)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def load_last_ingest(path: Path | None = None) -> dict[str, Any] | None:
    return _load_json_dict(path or last_ingest_path())


def save_last_verify(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path is not None else last_verify_path()
    _ensure_parent(target)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def load_last_verify(path: Path | None = None) -> dict[str, Any] | None:
    return _load_json_dict(path or last_verify_path())


def save_last_trace(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path is not None else last_trace_path()
    _ensure_parent(target)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def load_last_trace(path: Path | None = None) -> dict[str, Any] | None:
    return _load_json_dict(path or last_trace_path())


def save_last_ask(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path is not None else last_ask_path()
    _ensure_parent(target)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return target


def load_last_ask(path: Path | None = None) -> dict[str, Any] | None:
    return _load_json_dict(path or last_ask_path())


def append_verify_log(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path) if path is not None else verify_log_path()
    _ensure_parent(target)
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return target


def _load_json_dict(target: Path) -> dict[str, Any] | None:
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
