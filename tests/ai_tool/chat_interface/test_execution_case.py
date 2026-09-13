"""Execution Case。既存 ID の別名ではない横断キー。"""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.dev_timeline import build_timeline
from ai_tool.chat_interface.execution_case import get_case_bundle, link_member, load_case
from ai_tool.spec_proposal.follow import append_human_revision
from ai_tool.spec_proposal.propose import propose_specification
from tests.ai_tool.chat_interface.test_activity import _search_then_answer, _two_tools_then_answer
from tests.ai_tool.chat_interface.test_r35b_chat_interface import _plain_chat


VALID = {
    "proposed_specification": "Case に属する仕様候補",
    "objectives": ["追跡"],
    "inputs": [],
    "outputs": [],
    "behavior": [],
    "constraints": [],
    "completion_conditions": [],
    "confirmed": [],
    "proposed": [{"text": "case_id", "status": "PROPOSED"}],
    "assumptions": [],
    "unknowns": [],
    "human_confirmation_required": [],
    "risks": [],
    "alternatives": [],
    "rationale": "横断キー",
    "confidence": "low",
}


def _json_chat():
    from types import SimpleNamespace

    def fn(**_kwargs):
        return SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(VALID, ensure_ascii=False), tool_calls=[])
        )

    return fn


def test_two_turns_share_case_keep_distinct_correlation(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-case-multi")
    first = run_chat_turn(session, "この機能を実装して", chat_fn=_json_chat(), model="mock")
    second = run_chat_turn(session, "いや、ここはこうして", chat_fn=_plain_chat(), model="mock")
    assert first["case_id"]
    assert first["case_id"].startswith("cx-")
    assert first["case_id"] != first["correlation_id"]
    assert first["case_id"] != session["session_id"]
    assert first["case_id"] == second["case_id"]
    assert first["correlation_id"] != second["correlation_id"]
    assert first["correlation_id"].startswith("ac-")
    bundle = get_case_bundle(first["case_id"])
    assert bundle["ok"] is True
    assert first["correlation_id"] in bundle["correlation_ids"]
    assert second["correlation_id"] in bundle["correlation_ids"]
    assert len(bundle["turns"]) == 2


def test_multiple_llm_and_tools_on_same_case(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-case-tools")
    result = run_chat_turn(
        session, "GPUとCPUの状態を教えて", chat_fn=_two_tools_then_answer(), model="mock"
    )
    cid = result["case_id"]
    assert {e.get("case_id") for e in result["events"] if e.get("type") in {"tool_result", "llm"}} == {cid}
    names = {t["name"] for t in result["tools"]}
    assert "get_gpu_status" in names
    bundle = get_case_bundle(cid)
    tool_names = [t["name"] for turn in bundle["turns"] for t in turn.get("tools") or []]
    assert "get_gpu_status" in tool_names
    assert "get_cpu_status" in tool_names


def test_search_and_error_belong_to_case(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda name, arguments, **_k: {"query": "q", "hits": [{"title": "a"}]},
    )
    session = empty_session("cs-case-search")
    searched = run_chat_turn(session, "調べて", chat_fn=_search_then_answer(), model="mock")
    assert searched["web_search"] is True
    assert any(e.get("type") == "web_search" and e.get("case_id") == searched["case_id"] for e in searched["events"])

    def boom(**_kwargs):
        raise ConnectionError("connection refused")

    failed = run_chat_turn(session, "もう一度", chat_fn=boom, model="mock")
    assert failed["is_error"] is True
    assert failed["case_id"] == searched["case_id"]
    bundle = get_case_bundle(searched["case_id"])
    assert any(t.get("is_error") for t in bundle["turns"])
    assert any(t.get("web_search") for t in bundle["turns"])


def test_classify_is_not_case_start(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-case-hello")
    hello = run_chat_turn(session, "こんにちは", chat_fn=_plain_chat(), model="mock")
    impl = run_chat_turn(session, "この機能を実装して", chat_fn=_json_chat(), model="mock")
    assert hello["route"] == "chat"
    assert impl["route"] == "development"
    assert hello["case_id"] == impl["case_id"]
    assert hello["development_job"] is None
    assert impl["development_job"] is not None
    assert impl["development_job"]["case_id"] == impl["case_id"]
    assert impl["development_job"]["id"] != impl["case_id"]


def test_proposal_and_human_revision_keep_case(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path / "spec"))
    llm = propose_specification("要求Z", chat_fn=_json_chat(), model="mock")
    assert str(llm.get("case_id") or "").startswith("cx-")
    rev = append_human_revision(
        parent_proposal_id=llm["proposal_id"],
        revision_reason="確認",
    )
    assert rev["case_id"] == llm["case_id"]
    assert rev["correlation_id"] != llm["correlation_id"]
    bundle = get_case_bundle(llm["case_id"])
    ids = {p["proposal_id"] for p in bundle["proposals"]}
    assert llm["proposal_id"] in ids
    assert rev["proposal_id"] in ids


def test_explicit_run_link_is_membership_git_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-case-run")
    result = run_chat_turn(session, "こんにちは", chat_fn=_plain_chat(), model="mock")
    cid = result["case_id"]
    bundle0 = get_case_bundle(cid)
    assert bundle0["runs"] == []
    linked = link_member(cid, "run_id", "20260831_000000_example")
    assert linked["ok"] is True
    bundle = get_case_bundle(cid)
    assert bundle["runs"] == ["20260831_000000_example"]
    timeline = build_timeline(session, case_id=cid)
    assert timeline["case_id"] == cid
    assert not any(e.get("type") == "TEST" for e in timeline["events"])
    assert not any(e.get("type") in {"GIT", "GIT_COMMIT"} for e in timeline["events"])
    activity = [e for e in timeline["events"] if e.get("stream") == "local_agent"]
    assert activity
    assert all(e.get("case_id") == cid for e in activity)


def test_case_id_is_not_session_job_or_run(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-case-ids")
    result = run_chat_turn(session, "GPU温度取得Toolを作って", chat_fn=_json_chat(), model="mock")
    case_id = result["case_id"]
    job_id = result["development_job"]["id"]
    assert case_id.startswith("cx-")
    assert job_id.startswith("dj-")
    assert result["correlation_id"].startswith("ac-")
    assert case_id != job_id
    assert case_id != session["session_id"]
    stored = load_case(case_id)
    assert stored["not_a_rename_of"] == [
        "session_id",
        "correlation_id",
        "job_id",
        "proposal_id",
        "run_id",
    ]


def test_http_get_execution_case(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-case-http")
    result = run_chat_turn(session, "こんにちは", chat_fn=_plain_chat(), model="mock")
    from ai_tool.chat_interface.server import ChatHandler

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ChatHandler)
    Thread(target=httpd.serve_forever, daemon=True).start()
    conn = HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=20)
    try:
        conn.request("GET", "/api/execution-cases/" + result["case_id"])
        payload = json.loads(conn.getresponse().read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["case_id"] == result["case_id"]
        assert result["correlation_id"] in payload["correlation_ids"]
        assert payload["extension_points"]["cursor_handoff"]
        conn.request("GET", "/api/execution-cases")
        listed = json.loads(conn.getresponse().read().decode("utf-8"))
        assert any(c["case_id"] == result["case_id"] for c in listed["cases"])
    finally:
        httpd.shutdown()
