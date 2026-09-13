from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def failure(code: str, message: str, **fields: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "failure",
        "error": {"code": code, "message": message},
        "warnings": [],
        **fields,
    }
