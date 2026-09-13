"""Catalog entry read/write — limited to ai_tool/catalog/entries (Phase 3)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ENTRIES_DIR = _REPO_ROOT / "ai_tool" / "catalog" / "entries"


def catalog_entries_dir() -> Path:
    return _DEFAULT_ENTRIES_DIR


def _resolve_entries_dir(entries_dir: Path | None) -> Path:
    return entries_dir if entries_dir is not None else catalog_entries_dir()


def list_entry_paths(*, entries_dir: Path | None = None) -> list[Path]:
    root = _resolve_entries_dir(entries_dir)
    if not root.is_dir():
        return []
    return sorted(root.glob("*.json"))


def find_entry_path(tool_id: str, *, entries_dir: Path | None = None) -> Path | None:
    for path in list_entry_paths(entries_dir=entries_dir):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and str(data.get("tool_id") or "") == tool_id:
            return path
    return None


def load_catalog_entry(
    tool_id: str,
    *,
    entries_dir: Path | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    path = find_entry_path(tool_id, entries_dir=entries_dir)
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return path, data


def save_catalog_entry(
    path: Path,
    entry: dict[str, Any],
) -> None:
    """Persist catalog metadata only — does not touch registry or execute tools."""
    path.write_text(
        json.dumps(entry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
