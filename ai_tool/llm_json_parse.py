"""Shared JSON LLM response parsing for Dev Skill pipeline harnesses."""
from __future__ import annotations

import json
import re
from typing import Any


class LLMEmptyResponseError(ValueError):
    """Raised when the model returns no usable message content for JSON parsing."""

    def __init__(self, message: str, *, diagnostics: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = dict(diagnostics or {})


def llm_response_diagnostics(response: Any) -> dict[str, Any]:
    """Capture observable response fields without parsing JSON."""
    msg = getattr(response, "message", None)
    content = str(getattr(msg, "content", None) or "")
    thinking = str(getattr(msg, "thinking", None) or "")
    dumped: dict[str, Any] = {}
    if hasattr(response, "model_dump"):
        try:
            dumped = response.model_dump()
        except Exception:  # noqa: BLE001
            dumped = {}
    return {
        "content_len": len(content),
        "thinking_len": len(thinking),
        "content_preview": content[:240],
        "thinking_preview": thinking[:240],
        "eval_count": dumped.get("eval_count"),
        "prompt_eval_count": dumped.get("prompt_eval_count"),
        "done": dumped.get("done"),
        "done_reason": dumped.get("done_reason"),
    }


def message_content(response: Any) -> str:
    return str(getattr(getattr(response, "message", None), "content", None) or "")


def strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I | re.S)
    return cleaned.strip()


def parse_json_content(
    text: str,
    *,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extracted = strip_json_fence(text)
    if not extracted:
        raise LLMEmptyResponseError(
            "LLM returned empty message content before JSON parsing",
            diagnostics=diagnostics,
        )
    try:
        payload = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def parse_llm_json_response(
    response: Any,
    *,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed = dict(diagnostics or llm_response_diagnostics(response))
    text = message_content(response)
    if not text.strip():
        raise LLMEmptyResponseError(
            "LLM returned empty message content",
            diagnostics=observed,
        )
    return parse_json_content(text, diagnostics=observed)


__all__ = [
    "LLMEmptyResponseError",
    "llm_response_diagnostics",
    "message_content",
    "parse_json_content",
    "parse_llm_json_response",
    "strip_json_fence",
]
