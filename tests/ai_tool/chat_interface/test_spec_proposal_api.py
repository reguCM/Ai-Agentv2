"""仕様候補 HTTP。Chat 通常回答経路ではない。"""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace


VALID = {
    "proposed_specification": "APIから仕様候補を保存する",
    "objectives": ["蓄積"],
    "inputs": ["request"],
    "outputs": ["SpecificationProposal"],
    "behavior": ["追記"],
    "constraints": ["上書きしない"],
    "completion_conditions": ["構造化保存"],
    "confirmed": [{"text": "Phase 1 のみ", "status": "CONFIRMED"}],
    "proposed": [{"text": "JSONL 追記", "status": "PROPOSED"}],
    "assumptions": [],
    "unknowns": [],
    "human_confirmation_required": [],
    "risks": [],
    "alternatives": [],
    "rationale": "上書きしない",
    "confidence": "low",
}


def _start() -> tuple[ThreadingHTTPServer, int]:
    from ai_tool.chat_interface.server import ChatHandler

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ChatHandler)
    Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def test_spec_http_propose_and_last(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))

    def fake_chat(**_kwargs):
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(VALID, ensure_ascii=False)))

    monkeypatch.setattr("tools.system.llm.chat", fake_chat)
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request("GET", "/api/spec/last")
        last0 = json.loads(conn.getresponse().read().decode("utf-8"))
        assert last0["executed"] is False
        assert last0["proposal"] is None

        conn.request(
            "POST",
            "/api/spec/propose",
            body=json.dumps({"request": "仕様候補を保存できるようにする", "model": "mock"}),
            headers={"Content-Type": "application/json"},
        )
        data = json.loads(conn.getresponse().read().decode("utf-8"))
        assert data["saved"] is True
        assert data["parse_status"] == "ok"
        assert data["source"] == "api"
        assert data["chat_path"] == "NOT_CONNECTED"
        assert data["policy_eval"]["may_claim_specification_complete"] is False
        assert data["human_revision"] is None
        assert data["origin"] == "llm_proposal"
        assert data["llm_judgment"] == "NOT_IMPLEMENTED"
        assert data["learning_method"] == "NOT_DETERMINED"
        assert str(data.get("correlation_id") or "").startswith("ac-")

        conn.request("GET", "/api/spec/last")
        last = json.loads(conn.getresponse().read().decode("utf-8"))
        assert last["executed"] is True
        assert last["proposal"]["proposal_id"] == data["proposal_id"]

        conn.request("GET", f"/api/spec/proposals?request_id={data['request_id']}")
        listed = json.loads(conn.getresponse().read().decode("utf-8"))
        assert listed["llm_used"] is False
        assert listed["count"] == 1

        conn.request("GET", f"/api/spec/proposal?proposal_id={data['proposal_id']}")
        by_id = json.loads(conn.getresponse().read().decode("utf-8"))
        assert by_id["found"] is True
        assert by_id["proposal"]["proposal_id"] == data["proposal_id"]
        assert by_id["proposal"]["request_id"] == data["request_id"]
        assert by_id["llm_used"] is False
    finally:
        httpd.shutdown()


def test_spec_http_empty_request(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request(
            "POST",
            "/api/spec/propose",
            body=json.dumps({"request": "  "}),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 400
        assert data["saved"] is False
        assert data["llm_used"] is False
    finally:
        httpd.shutdown()


def test_spec_http_revise_and_problem(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))

    def fake_chat(**_kwargs):
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(VALID, ensure_ascii=False)))

    monkeypatch.setattr("tools.system.llm.chat", fake_chat)
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request(
            "POST",
            "/api/spec/propose",
            body=json.dumps({"request": "観測用の要求", "model": "mock"}),
            headers={"Content-Type": "application/json"},
        )
        proposed = json.loads(conn.getresponse().read().decode("utf-8"))
        pid = proposed["proposal_id"]

        conn.request(
            "POST",
            "/api/spec/revise",
            body=json.dumps({"parent_proposal_id": pid, "revision_reason": "影響が大きい"}),
            headers={"Content-Type": "application/json"},
        )
        rev = json.loads(conn.getresponse().read().decode("utf-8"))
        assert rev["origin"] == "human_revision"
        assert rev["llm_judgment"] == "NOT_IMPLEMENTED"
        assert rev["parent_proposal_id"] == pid
        assert str(rev.get("correlation_id") or "").startswith("ac-")
        assert rev["correlation_id"] != proposed["correlation_id"]

        conn.request(
            "POST",
            "/api/spec/problem",
            body=json.dumps({"parent_proposal_id": pid, "problem": "仮定が危険だった"}),
            headers={"Content-Type": "application/json"},
        )
        prob = json.loads(conn.getresponse().read().decode("utf-8"))
        assert prob["origin"] == "problem_record"
        assert prob["cause_status"] == "NOT_DETERMINED"
        assert str(prob.get("correlation_id") or "").startswith("ac-")
        assert prob["correlation_id"] != proposed["correlation_id"]
        assert prob["correlation_id"] != rev["correlation_id"]

        conn.request("GET", f"/api/spec/proposals?parent_proposal_id={pid}")
        kids = json.loads(conn.getresponse().read().decode("utf-8"))
        assert kids["count"] == 2
        origins = {row.get("origin") for row in kids["proposals"]}
        assert origins == {"human_revision", "problem_record"}

        conn.request("GET", f"/api/spec/proposal?proposal_id={rev['proposal_id']}")
        rev_row = json.loads(conn.getresponse().read().decode("utf-8"))
        assert rev_row["found"] is True
        assert rev_row["proposal"]["parent_proposal_id"] == pid
        assert rev_row["proposal"]["origin"] == "human_revision"
    finally:
        httpd.shutdown()


def test_spec_http_get_proposal_empty_and_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request("GET", "/api/spec/proposal")
        empty = conn.getresponse()
        empty_data = json.loads(empty.read().decode("utf-8"))
        assert empty.status == 400
        assert empty_data["executed"] is False
        assert empty_data["found"] is False
        assert empty_data["proposal"] is None

        conn.request("GET", "/api/spec/proposal?proposal_id=sp-does-not-exist")
        missing = json.loads(conn.getresponse().read().decode("utf-8"))
        assert missing["ok"] is True
        assert missing["executed"] is True
        assert missing["found"] is False
        assert missing["proposal"] is None
        assert missing["proposal_id"] == "sp-does-not-exist"
    finally:
        httpd.shutdown()


def test_spec_http_propose_keeps_passed_ids_and_does_not_invent(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path))

    def fake_chat(**_kwargs):
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(VALID, ensure_ascii=False)))

    monkeypatch.setattr("tools.system.llm.chat", fake_chat)
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request(
            "POST",
            "/api/spec/propose",
            body=json.dumps({"request": "IDを捨てない", "model": "mock"}),
            headers={"Content-Type": "application/json"},
        )
        bare = json.loads(conn.getresponse().read().decode("utf-8"))
        assert bare["saved"] is True
        assert bare["session_id"] is None
        assert bare["development_job_id"] is None
        assert bare["implementation_id"] is None
        assert bare["test_run_id"] is None

        conn.request(
            "POST",
            "/api/spec/propose",
            body=json.dumps(
                {
                    "request": "IDを渡す",
                    "model": "mock",
                    "session_id": "cs-from-api",
                    "development_job_id": "dj-from-api",
                    "implementation_id": "impl-from-api",
                    "test_run_id": "tr-from-api",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        linked = json.loads(conn.getresponse().read().decode("utf-8"))
        assert linked["session_id"] == "cs-from-api"
        assert linked["development_job_id"] == "dj-from-api"
        assert linked["implementation_id"] == "impl-from-api"
        assert linked["test_run_id"] == "tr-from-api"
        assert linked["parent_proposal_id"] is None
        assert linked["origin"] == "llm_proposal"
        assert linked["llm_judgment"] == "NOT_IMPLEMENTED"

        conn.request("GET", f"/api/spec/proposal?proposal_id={linked['proposal_id']}")
        fetched = json.loads(conn.getresponse().read().decode("utf-8"))
        assert fetched["found"] is True
        assert fetched["proposal"]["session_id"] == "cs-from-api"
        assert fetched["proposal"]["development_job_id"] == "dj-from-api"
        assert fetched["proposal"]["implementation_id"] == "impl-from-api"
        assert fetched["proposal"]["test_run_id"] == "tr-from-api"
    finally:
        httpd.shutdown()


def test_spec_http_get_existing_jsonl_record_without_rewrite(monkeypatch):
    """Phase1 ライブ原本を読むだけ。POST しない。origin 欠落を埋めない。"""
    from hashlib import sha256
    from pathlib import Path

    original_dir = (
        Path(__file__).resolve().parents[3]
        / "runs"
        / "ai_tool"
        / "20260831_123000_llm_spec_proposal_phase1"
        / "spec_proposals"
    )
    jsonl = original_dir / "proposals.jsonl"
    last = original_dir / "last_proposal.json"
    assert jsonl.is_file()
    before_jsonl = sha256(jsonl.read_bytes()).hexdigest()
    before_last = sha256(last.read_bytes()).hexdigest() if last.is_file() else None
    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(original_dir))

    known_id = "sp-20260831_032953-d68e7d66"
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request("GET", f"/api/spec/proposal?proposal_id={known_id}")
        data = json.loads(conn.getresponse().read().decode("utf-8"))
        assert data["found"] is True
        assert data["proposal"]["proposal_id"] == known_id
        assert data["proposal"]["request_id"] == "rq-acd543cde4c9a0a3"
        assert data["proposal"]["version"] == 1
        assert "origin" not in data["proposal"]
        assert data["proposal"].get("implementation_id") is None
    finally:
        httpd.shutdown()

    assert sha256(jsonl.read_bytes()).hexdigest() == before_jsonl
    if before_last is not None:
        assert sha256(last.read_bytes()).hexdigest() == before_last


def test_spec_ui_propose_passes_existing_session_id_only():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[3] / "ai_tool" / "chat_interface" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    propose = js.split("async function proposeSpec()")[1].split("async function reviseSpec()")[0]
    assert "session_id: sessionId || \"\"" in propose
    assert "development_job_id" not in propose


def test_dev_cases_http_keeps_chat_job_proposal_id(tmp_path, monkeypatch):
    from ai_tool.chat_interface.agent_turn import run_chat_turn
    from ai_tool.chat_interface.chat_session import empty_session

    monkeypatch.setenv("AI_AGENT_SPEC_PROPOSAL_DIR", str(tmp_path / "spec_proposals"))
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")

    def fake_chat(**_kwargs):
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(VALID, ensure_ascii=False)))

    session = empty_session("cs-http-job-ids")
    result = run_chat_turn(
        session,
        "CPU温度を取得するToolを作って",
        chat_fn=fake_chat,
    )
    pid = result["proposal"]["proposal_id"]
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request("GET", f"/api/dev/cases?session_id={session['session_id']}")
        data = json.loads(conn.getresponse().read().decode("utf-8"))
        jobs = data["chat_jobs"]
        assert jobs[0]["proposal_id"] == pid
        assert jobs[0]["request_id"] == result["proposal"]["request_id"]
        calls = [e for e in (data.get("local_agent_activity") or {}).get("events") or [] if e.get("type") == "LOCAL_AGENT_CALL"]
        assert calls[0]["proposal_id"] == pid

        conn.request("GET", f"/api/dev/events?session_id={session['session_id']}")
        timeline = json.loads(conn.getresponse().read().decode("utf-8"))
        assert timeline["jobs"][0]["proposal_id"] == pid
    finally:
        httpd.shutdown()

