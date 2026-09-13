"""
Ollama Tool Calling capability probe — model-agnostic diagnostic.

特定モデル名をハードコードしない。active profile の model で 1 回 probe する。
"""

from __future__ import annotations

from typing import Any

_TOOL_PROBE = {
    "type": "function",
    "function": {
        "name": "_capability_probe",
        "description": "Internal capability probe — do not use.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def probe_tool_calling(model: str, *, chat_fn: Any | None = None) -> dict[str, Any]:
    """
    Return {supported: bool|None, error: str|None, detail: str|None}.
    supported=None when probe could not run (e.g. import error).
    """
    if chat_fn is None:
        try:
            from tools.system.llm import chat as default_chat

            chat_fn = default_chat
        except Exception as exc:  # noqa: BLE001
            return {"supported": None, "error": str(exc), "detail": "chat_import_failed"}

    try:
        chat_fn(model=model, messages=[{"role": "user", "content": "ping"}], tools=[_TOOL_PROBE])
    except Exception as exc:  # noqa: BLE001 — surface Ollama HTTP errors
        message = str(exc)
        if "does not support tools" in message.lower():
            return {
                "supported": False,
                "error": message,
                "detail": "ollama_rejected_tools_parameter",
            }
        return {"supported": None, "error": message, "detail": "probe_failed"}

    return {"supported": True, "error": None, "detail": "tools_parameter_accepted"}
