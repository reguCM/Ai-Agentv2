"""要求の分岐。独立した分類器 Core ではない。LLM に丸投げしない。"""
from __future__ import annotations

import re
from typing import Literal

Route = Literal["chat", "tool_creation", "development", "research"]

_TOOL_CREATE = re.compile(
    r"Toolを作|ツールを作|新しいTool|新規Tool|toolを作成|ツールを作成",
    re.I,
)
_DEVELOPMENT = re.compile(
    r"テストまで|全部テスト|テストして|テストしてください|実装して|開発して|"
    r"Phase\s*[A-Z0-9._-]+.*テスト",
    re.I,
)
_RESEARCH = re.compile(
    r"ResearchRecord|技術調査",
    re.I,
)
_FOLLOWUP = re.compile(
    r"前に調べた|その技術A|前の技術A|前のやつ|前回のやつ",
    re.I,
)

INTENT = {
    "chat": "CHAT",
    "tool_creation": "TOOL_CREATION",
    "development": "DEVELOPMENT",
    "research": "RESEARCH",
}


def classify_request(text: str) -> Route:
    raw = text or ""
    if _TOOL_CREATE.search(raw):
        return "tool_creation"
    if _RESEARCH.search(raw):
        return "research"
    if _DEVELOPMENT.search(raw):
        return "development"
    return "chat"


def looks_like_followup(text: str) -> bool:
    return bool(_FOLLOWUP.search(text or ""))


def intent_of(route: str) -> str:
    return INTENT.get(route, "CHAT")
