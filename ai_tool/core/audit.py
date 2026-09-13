from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LOG = _REPO_ROOT / "runs" / "ai_tool" / "audit.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_audit_id() -> str:
    return str(uuid.uuid4())


def append_audit(
    event: dict[str, Any],
    *,
    log_path: Path | None = None,
) -> str:
    """Append tool discovery/execution event to JSONL audit log."""
    target = log_path or _DEFAULT_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    audit_id = event.get("audit_id") or new_audit_id()
    row = {"audit_id": audit_id, "timestamp": _now_iso(), **event}
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return audit_id
