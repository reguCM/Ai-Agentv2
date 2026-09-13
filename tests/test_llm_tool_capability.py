"""LLM Tool Calling capability probe tests."""
from __future__ import annotations

from unittest import mock

from tools.system.llm_tool_capability import probe_tool_calling


def test_probe_supported_when_chat_accepts_tools():
    def _chat(**kwargs):
        return mock.Mock(message=mock.Mock(tool_calls=[], content="ok"))

    out = probe_tool_calling("any-model", chat_fn=_chat)
    assert out["supported"] is True


def test_probe_unsupported_on_ollama_error():
    def _chat(**kwargs):
        raise RuntimeError("model does not support tools (status code: 400)")

    out = probe_tool_calling("any-model", chat_fn=_chat)
    assert out["supported"] is False
    assert "does not support tools" in (out["error"] or "").lower()
