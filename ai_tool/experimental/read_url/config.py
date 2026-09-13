from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FetchLimits:
    max_bytes: int = 262144
    max_main_text_chars: int = 32000
    timeout_seconds: float = 10.0
    max_redirects: int = 5


DEFAULT_LIMITS = FetchLimits()

USER_AGENT = "AI-Agent-experimental-read_url/0.1"

ALLOWED_SCHEMES = frozenset({"http", "https"})

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.google",
    }
)

ALLOWED_CONTENT_TYPE_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "application/javascript",  # sometimes served as text
)
