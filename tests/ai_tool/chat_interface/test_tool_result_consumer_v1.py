from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.requirement_decomposition import (
    RequirementCondition,
    RequirementDecomposition,
)
from ai_tool.chat_interface.tool_observation import observe_tool_result


def _tool_then_answer(tool_name: str, captured: list[dict]):
    step = {"value": 0}

    def chat(**kwargs):
        if step["value"] == 0:
            step["value"] += 1
            call = SimpleNamespace(
                function=SimpleNamespace(name=tool_name, arguments={})
            )
            return SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=[call])
            )
        captured.extend(kwargs["messages"])
        return SimpleNamespace(
            message=SimpleNamespace(content="done", tool_calls=[])
        )

    return chat


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"ok": True, "status": "success", "error": None, "warnings": []}, "success"),
        ({"ok": True, "status": "partial", "error": None, "warnings": []}, "partial"),
        (
            {
                "ok": False,
                "status": "failure",
                "error": {"code": "failed", "message": "failed"},
                "warnings": [],
            },
            "failure",
        ),
        ({"ok": True, "error": None}, "success"),
        ({"ok": False, "error": "failed"}, "failure"),
        ({"ok": True, "truncated": True, "error": "limit"}, "partial"),
        ({}, "failure"),
    ],
)
def test_ui_observation_uses_normalized_status(raw: dict, expected: str) -> None:
    observation = observe_tool_result("sample_tool", raw)
    assert observation["status"] == expected


def test_ui_warning_is_visible_without_becoming_failure() -> None:
    observation = observe_tool_result(
        "search_files",
        {
            "ok": True,
            "status": "partial",
            "error": None,
            "warnings": [
                {"code": "scan_limit_reached", "message": "上限に到達しました"}
            ],
        },
    )
    assert observation["status"] == "partial"
    assert observation["error"] is None
    assert observation["warnings"] == [
        {"code": "scan_limit_reached", "message": "上限に到達しました"}
    ]


def test_ui_success_warning_stays_success() -> None:
    observation = observe_tool_result(
        "sample_tool",
        {
            "ok": True,
            "status": "success",
            "error": None,
            "warnings": [{"code": "notice", "message": "確認事項があります"}],
        },
    )
    assert observation["status"] == "success"
    assert observation["warnings"][0]["message"] == "確認事項があります"


def test_frontend_recursively_formats_structured_warning_arrays() -> None:
    app_js = (
        Path(__file__).resolve().parents[3]
        / "ai_tool"
        / "chat_interface"
        / "static"
        / "app.js"
    ).read_text(encoding="utf-8")
    assert 'child.some((item) => item && typeof item === "object")' in app_js
    assert ".map((item) => formatObservation(item" in app_js


@pytest.mark.parametrize(
    ("tool_name", "raw", "expected"),
    [
        (
            "read_file",
            {
                "ok": True,
                "status": "success",
                "error": None,
                "warnings": [],
                "has_more": True,
            },
            "success",
        ),
        (
            "list_files",
            {
                "ok": True,
                "status": "partial",
                "error": None,
                "warnings": [{"code": "entry_limit_reached", "message": "limit"}],
            },
            "partial",
        ),
        (
            "search_files",
            {
                "ok": True,
                "status": "partial",
                "error": None,
                "warnings": [{"code": "scan_limit_reached", "message": "limit"}],
            },
            "partial",
        ),
    ],
)
def test_workspace_file_tool_ui_classification(
    tool_name: str, raw: dict, expected: str
) -> None:
    assert observe_tool_result(tool_name, raw)["status"] == expected


def test_chat_turn_keeps_raw_result_for_llm(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions"
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _session_id: tmp_path / "trust.json",
    )
    raw = {
        "ok": True,
        "status": "partial",
        "error": None,
        "warnings": [{"code": "limit", "message": "partial"}],
        "tool_specific": {"kept": True},
    }
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda *_args, **_kwargs: raw,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: RequirementDecomposition(
            [RequirementCondition("C1", "tool resultを取得する")], "READY"
        ),
    )
    captured: list[dict] = []
    session = empty_session("consumer-v1")
    result = run_chat_turn(
        session,
        "toolを使って",
        chat_fn=_tool_then_answer("search_files", captured),
        model="fake",
    )
    tool_message = next(
        item
        for item in captured
        if isinstance(item, dict) and item.get("role") == "tool"
    )
    assert json.loads(tool_message["content"]) == raw
    assert result["tools"][0]["status"] == "partial"
