"""Tool Calling 失敗分類（execution_result レベル）。"""
from __future__ import annotations

import re
from typing import Any

from tools.system.context_monitor.schema import FAILURE_TYPES

_TOOL_MENTION_RE = re.compile(
    r"\b(read_file|search_files|list_files|write_file|tool_call)\b", re.I
)


def _thinking_mentions_tool(text: str, expected_tool: str | None = None) -> bool:
    if not text:
        return False
    if expected_tool and expected_tool.lower() in text.lower():
        return True
    return bool(_TOOL_MENTION_RE.search(text))


def _extract_tool_names_from_response(response: Any) -> list[str]:
    try:
        msg = getattr(response, "message", None)
        tcs = getattr(msg, "tool_calls", None) or []
        return [
            tc.function.name
            for tc in tcs
            if getattr(getattr(tc, "function", None), "name", None)
        ]
    except Exception:
        return []


def _thinking_text(response: Any) -> str:
    try:
        msg = getattr(response, "message", None)
        dump = msg.model_dump() if hasattr(msg, "model_dump") else {}
        return str(dump.get("thinking") or "")
    except Exception:
        return ""


def classify_llm_response(
    response: Any | None,
    *,
    expected_tool: str | None = None,
    tools_requested: bool = True,
    tool_execution_ok: bool | None = None,
    timeout: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    """LLM 応答から execution レベルの失敗分類。"""
    if timeout or (error and "timeout" in error.lower()):
        return _result("TIMEOUT", detail={"error": error, "timeout": True})

    if error:
        lowered = error.lower()
        if "context" in lowered and ("limit" in lowered or "length" in lowered):
            return _result("CONTEXT_LIMIT", detail={"error": error})
        if "gpu" in lowered or "vram" in lowered or "cuda" in lowered:
            return _result("GPU_RESOURCE_INSUFFICIENT", detail={"error": error})
        if "parse" in lowered or "json" in lowered:
            return _result("TOOL_CALL_PARSE_FAILED", detail={"error": error})

    if response is None:
        return _result("UNKNOWN", detail={"error": error or "no_response"})

    tool_names = _extract_tool_names_from_response(response)
    thinking = _thinking_text(response)

    if tool_execution_ok is False:
        return _result(
            "TOOL_EXECUTION_FAILED",
            detail={
                "native_tool_call": bool(tool_names),
                "native_tool_names": tool_names,
            },
        )

    if tools_requested and not tool_names:
        if _thinking_mentions_tool(thinking, expected_tool):
            return _result(
                "TOOL_CALL_NOT_GENERATED",
                detail={
                    "thinking_mentions_tool": True,
                    "expected_tool": expected_tool,
                    "native_tool_call": False,
                },
            )
        if expected_tool:
            return _result(
                "TOOL_CALL_NOT_GENERATED",
                detail={
                    "expected_tool": expected_tool,
                    "native_tool_call": False,
                },
            )

    return _result("NONE", detail={"native_tool_call": bool(tool_names), "native_tool_names": tool_names})


def classify_execution_record(record: dict[str, Any]) -> dict[str, Any]:
    """execution_result 辞書から失敗分類。"""
    if record.get("timeout"):
        return _result("TIMEOUT", detail=record)
    err = record.get("error")
    if err:
        return classify_llm_response(
            None,
            expected_tool=record.get("expected_tool"),
            tools_requested=record.get("tools_requested", True),
            tool_execution_ok=record.get("tool_execution_ok"),
            error=str(err),
        )

    if record.get("tool_execution_ok") is False:
        return _result("TOOL_EXECUTION_FAILED", detail=record)

    if record.get("failure_type") in FAILURE_TYPES:
        return _result(str(record["failure_type"]), detail=record)

    if record.get("native_tool_call") is False and record.get("tools_requested", True):
        thinking = str(record.get("thinking") or "")
        expected = record.get("expected_tool")
        if _thinking_mentions_tool(thinking, expected):
            return _result(
                "TOOL_CALL_NOT_GENERATED",
                detail={"thinking_mentions_tool": True, **record},
            )
        if expected:
            return _result("TOOL_CALL_NOT_GENERATED", detail=record)

    if record.get("execution_result") == "failure":
        return _result("UNKNOWN", detail=record)

    return _result("NONE", detail=record)


def execution_needs_recovery(classification: dict[str, Any]) -> bool:
    ft = classification.get("failure_type")
    return ft not in (None, "NONE")


def _result(failure_type: str, *, detail: dict | None = None) -> dict[str, Any]:
    ft = failure_type if failure_type in FAILURE_TYPES else "UNKNOWN"
    return {
        "failure_type": ft,
        "execution_result": "failure" if ft not in ("NONE",) else "success",
        "detail": detail or {},
    }
