"""Read-only catalog sources for Agent Tool Discovery."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENTRIES_DIR = _REPO_ROOT / "ai_tool" / "catalog" / "entries"
_MANUAL_CATALOG = _REPO_ROOT / "registry" / "ai_tool_catalog.json"


def repo_root() -> Path:
    return _REPO_ROOT


def load_experimental_entries(*, entries_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load AI-TOOL catalog entries (experimental local tools). Read-only."""
    root = entries_dir if entries_dir is not None else _ENTRIES_DIR
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            out.append(data)
    return out


def load_manual_mcp_entries() -> list[dict[str, Any]]:
    """Load registry/ai_tool_catalog.json entries. Read-only."""
    if not _MANUAL_CATALOG.is_file():
        return []
    data = json.loads(_MANUAL_CATALOG.read_text(encoding="utf-8"))
    return list(data.get("tools") or [])
