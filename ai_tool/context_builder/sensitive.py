from __future__ import annotations

import re
from pathlib import PurePosixPath

SENSITIVE_PATTERNS = (
    r"(^|/)\.env($|/|\.)",
    r"credentials",
    r"api[_-]?key",
    r"password",
    r"private[_-]?key",
    r"\.pem$",
    r"\.key$",
    r"token",
    r"secret",
)

_COMPILED = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_PATTERNS]


def is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(p.search(normalized) for p in _COMPILED)


def exclusion_reason(path: str) -> str | None:
    if is_sensitive_path(path):
        return "EXCLUDED_SENSITIVE"
    return None
