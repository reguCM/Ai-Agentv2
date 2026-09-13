from __future__ import annotations

import json

import pytest

from ai_tool.llm_json_parse import LLMEmptyResponseError, parse_json_content


def test_parse_json_content_strips_fence() -> None:
    payload = parse_json_content(
        """```json
        {"question": "Which runtime?", "recommended_answer": "Dedicated Sandbox"}
        ```"""
    )
    assert payload["recommended_answer"] == "Dedicated Sandbox"


def test_empty_text_raises_llm_empty_response_not_json_decode() -> None:
    with pytest.raises(LLMEmptyResponseError) as excinfo:
        parse_json_content("")
    assert "JSONDecodeError" not in str(excinfo.value)
    assert isinstance(excinfo.value.diagnostics, dict)


def test_invalid_json_still_raises_json_decode_error() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_json_content("{not-json")
