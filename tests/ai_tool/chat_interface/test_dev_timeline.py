"""Development Timeline / Job。Cursor ライブは推測しない。"""
from __future__ import annotations

import json

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.classify import classify_request, intent_of
from ai_tool.chat_interface.dev_timeline import build_timeline, cursor_live_status, extract_cursor_test_items
from ai_tool.chat_interface.development_job import maybe_record_job
from tests.ai_tool.chat_interface.test_r35b_chat_interface import _plain_chat


def test_classify_keeps_chat_and_tool_creation_apart():
    assert classify_request("こんにちは") == "chat"
    assert classify_request("GPUの温度を教えて") == "chat"
    assert classify_request("GPU温度取得Toolを作って") == "tool_creation"
    assert classify_request("CPU温度を取得するToolを作って") == "tool_creation"
    assert classify_request("Phase Pを全部テストしてください") == "development"
    assert intent_of("tool_creation") == "TOOL_CREATION"


def test_hello_does_not_create_job(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-test-timeline-hello")
    result = run_chat_turn(session, "こんにちは", chat_fn=_plain_chat())
    assert result["route"] == "chat"
    assert result["intent"] == "CHAT"
    assert result["development_job"] is None
    assert session.get("development_jobs") == []


def test_hello_does_not_invent_proposal_ids(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    from ai_tool.chat_interface.activity import session_activity
    from ai_tool.chat_interface.dev_cases import session_jobs_as_notes
    from ai_tool.chat_interface.dev_timeline import build_timeline

    session = empty_session("cs-test-timeline-hello-ids")
    run_chat_turn(session, "こんにちは", chat_fn=_plain_chat())
    assert session_jobs_as_notes(session) == []
    calls = [e for e in session_activity(session)["events"] if e["type"] == "LOCAL_AGENT_CALL"]
    assert calls[0].get("proposal_id") in (None, "")
    assert calls[0].get("development_job_id") in (None, "")
    timeline = build_timeline(session)
    assert timeline["jobs"] == [] or all(not j.get("proposal_id") for j in timeline["jobs"])



def test_tool_request_creates_job(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-test-timeline-job")
    result = run_chat_turn(
        session,
        "GPU温度取得Toolを作って",
        chat_fn=_plain_chat("仕様案のみ。登録しません。"),
    )
    assert result["route"] == "tool_creation"
    job = result["development_job"]
    assert job is not None
    assert job["cursor_live"] == "NOT_OBSERVED"
    assert job["status"] == "recorded"
    assert session["development_jobs"][0]["id"] == job["id"]
    roles = [m["role"] for m in session["messages"]]
    assert roles[0] == "user"
    assert "notice" in roles
    assert any("開発依頼として記録" in m["content"] for m in session["messages"] if m["role"] == "notice")


def test_timeline_separates_cursor_report_and_machine():
    live = cursor_live_status()
    assert live["status"] == "NOT_OBSERVED"
    assert "NOT OBSERVED" in live["label"]

    items = extract_cursor_test_items(
        {"tests": {"P-1": "PASS", "P-2": {"status": "FAIL"}}},
        None,
    )
    assert [i["id"] for i in items] == ["P-1", "P-2"]
    assert items[0]["source"] == "cursor_report"
    assert items[0]["actor"] == "cursor"
    assert items[0]["status"] == "PASS"
    assert items[0]["detail"] == "未取得"
    assert items[1]["status"] == "FAIL"
    obs_items = extract_cursor_test_items(
        None,
        {"tests": {"A_DirectCall": {"status": "PASS", "executor": "cursor_python", "local_agent_executed": False}}},
    )
    assert obs_items[0]["observed"]["executor"] == "cursor_python"
    assert obs_items[0]["detail"] is None
    blob_items = json.dumps(obs_items, ensure_ascii=False)
    assert "VRAM" not in blob_items
    assert "温度" not in blob_items

    data = build_timeline(None)
    assert data["cursor_live"]["status"] == "NOT_OBSERVED"
    types = [e["type"] for e in data["events"]]
    assert "GIT" in types
    assert "TEST" in types
    assert "RUN" in types
    test_rows = [e for e in data["events"] if e["type"] == "TEST"]
    assert any(e.get("status") == "NOT_AVAILABLE" or e.get("body") == "NOT AVAILABLE" for e in test_rows)
    cursor_lists = [e for e in data["events"] if e["type"] == "TEST_LIST"]
    assert cursor_lists
    assert cursor_lists[0]["layer"] == "cursor_report"
    assert cursor_lists[0]["counts_as_pytest"] is False
    blob = json.dumps(data, ensure_ascii=False)
    assert "Cursor is running" not in blob
    assert "currently testing" not in blob.lower()


def test_maybe_record_job_skips_chat():
    session = empty_session("cs-no-job")
    assert maybe_record_job(session, "こんにちは", "chat") is None
    assert session["development_jobs"] == []
