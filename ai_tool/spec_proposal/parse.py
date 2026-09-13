"""LLM 出力から SpecificationProposal JSON を取る。自由文成功とは扱わない。"""
from __future__ import annotations

import json
from typing import Any


def extract_json_object(text: Any) -> dict[str, Any] | None:
    if isinstance(text, dict):
        return text
    blob = str(text or "").strip()
    if not blob:
        return None
    if blob.startswith("```"):
        lines = blob.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        blob = "\n".join(lines).strip()
    try:
        payload = json.loads(blob)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass
    start = blob.find("{")
    end = blob.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(blob[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
