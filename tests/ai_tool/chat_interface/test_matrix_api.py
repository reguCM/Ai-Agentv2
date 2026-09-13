"""Matrix HTTP。Chat /api/chat とは別。実 Web は使わない。"""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from ai_tool.matrix.ingest import ingest_web_to_matrix
from ai_tool.matrix.store import MatrixStore
from tests.ai_tool.matrix.test_matrix_store import _search


def _start() -> tuple[ThreadingHTTPServer, int]:
    from ai_tool.chat_interface.server import ChatHandler

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ChatHandler)
    Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def test_matrix_http_search_without_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    ingest_web_to_matrix("RTX 3060 VRAM", search_fn=_search, store=store)
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request("GET", "/api/matrix/search?q=RTX+3060")
        data = json.loads(conn.getresponse().read().decode("utf-8"))
        assert data["ok"] is True
        assert data["llm_used"] is False
        assert data["count"] >= 2
        assert any(r.get("value") == "12 GB" for r in data["records"])

        conn.request("GET", "/api/matrix/search?entity=RTX+3060&attribute=VRAM+capacity")
        attr = json.loads(conn.getresponse().read().decode("utf-8"))
        assert any(r.get("value") == "12 GB" for r in attr["records"])
        sample = next(r for r in attr["records"] if r.get("value") == "12 GB")
        assert sample["source_url"]
        assert sample["observed_at"]
        assert sample["provenance"]

        conn.request("GET", "/api/matrix/last")
        last = json.loads(conn.getresponse().read().decode("utf-8"))
        assert last["executed"] is True
        types = [e.get("type") for e in (last["ingest"] or {}).get("events") or []]
        assert "matrix_write" in types
        assert "research" not in types
    finally:
        httpd.shutdown()


def test_matrix_http_verify_not_available(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from ai_tool.matrix.models import MatrixRecord

    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(
        MatrixRecord(
            record_id="mr-no-url",
            entity="RTX 3060",
            attribute="VRAM capacity",
            value="12 GB",
            source_url="",
            source_title="",
            observed_at=datetime.now(timezone.utc).isoformat(),
            provenance="web_search → extract → matrix_write",
            ingest_id="ing-no-url",
            query="RTX 3060",
            excerpt=None,
        )
    )
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request(
            "POST",
            "/api/matrix/verify",
            body=json.dumps({"record_id": "mr-no-url"}),
            headers={"Content-Type": "application/json"},
        )
        data = json.loads(conn.getresponse().read().decode("utf-8"))
        assert data["result"] == "NOT_AVAILABLE"
        assert data["llm_used"] is False
        assert data["cause"] == "NOT_OBSERVED"
        types = [e.get("type") for e in data.get("events") or []]
        assert "matrix_record" in types
        assert "verify_result" in types
        assert "fetch" not in types
        conn.request("GET", "/api/matrix/last_verify")
        last = json.loads(conn.getresponse().read().decode("utf-8"))
        assert last["executed"] is True
        assert (last.get("verify") or {}).get("result") == "NOT_AVAILABLE"
    finally:
        httpd.shutdown()


def test_matrix_http_trace_does_not_mutate(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from ai_tool.matrix.models import MatrixRecord
    from ai_tool.matrix.verify import records_bytes

    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(
        MatrixRecord(
            record_id="mr-16-http",
            entity="RTX 3060",
            attribute="VRAM capacity",
            value="16 GB",
            source_url="https://en.wikipedia.org/wiki/RTX_5000",
            source_title="RTX 5000",
            observed_at=datetime.now(timezone.utc).isoformat(),
            provenance="web_search → fetch → extract → matrix_write",
            ingest_id="ing-http-16",
            query="RTX 3060",
            excerpt="RTX 5000 The GeForce RTX 50 series",
        )
    )
    before = records_bytes(store)
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request(
            "POST",
            "/api/matrix/trace",
            body=json.dumps({"record_id": "mr-16-http"}),
            headers={"Content-Type": "application/json"},
        )
        data = json.loads(conn.getresponse().read().decode("utf-8"))
        assert data["cause"] == "ENTITY_SOURCE_MISMATCH"
        assert data["llm_used"] is False
        assert data["records_unchanged"] is True
        types = [e.get("type") for e in data.get("events") or []]
        assert types[:6] == ["matrix_record", "search", "fetch", "extract", "normalize", "matrix_write"]
        conn.request("GET", "/api/matrix/last_trace")
        last = json.loads(conn.getresponse().read().decode("utf-8"))
        assert last["executed"] is True
        assert (last.get("trace") or {}).get("cause") == "ENTITY_SOURCE_MISMATCH"
    finally:
        httpd.shutdown()
    assert records_bytes(store) == before


def test_matrix_http_ask_sufficient_no_web(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from ai_tool.matrix.models import MatrixRecord

    monkeypatch.setenv("AI_AGENT_MATRIX_DIR", str(tmp_path))
    store = MatrixStore(tmp_path / "records.jsonl")
    store.append(
        MatrixRecord(
            record_id="mr-ask-http",
            entity="RTX 3060",
            attribute="VRAM capacity",
            value="12 GB",
            source_url="https://en.wikipedia.org/wiki/RTX_3060",
            source_title="RTX 3060",
            observed_at=datetime.now(timezone.utc).isoformat(),
            provenance="web_search → fetch → extract → matrix_write",
            ingest_id="ing-ask-http",
            query="RTX 3060",
            excerpt="12 GB",
        )
    )
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request(
            "POST",
            "/api/matrix/ask",
            body=json.dumps({"question": "RTX 3060のVRAM容量を教えて", "fallback": False, "use_llm": False}),
            headers={"Content-Type": "application/json"},
        )
        data = json.loads(conn.getresponse().read().decode("utf-8"))
        assert data["decision"] == "SUFFICIENT"
        assert data["web_search_count"] == 0
        assert data["llm_used"] is False
        assert data["chat_path"] == "NOT_CONNECTED"
        conn.request("GET", "/api/matrix/last_ask")
        last = json.loads(conn.getresponse().read().decode("utf-8"))
        assert last["executed"] is True
        assert (last.get("ask") or {}).get("decision") == "SUFFICIENT"
    finally:
        httpd.shutdown()


def test_chat_path_still_not_matrix_write(tmp_path, monkeypatch):
    from ai_tool.chat_interface.activity import session_activity
    from ai_tool.chat_interface.agent_turn import run_chat_turn
    from ai_tool.chat_interface.chat_session import empty_session
    from tests.ai_tool.chat_interface.test_r35b_chat_interface import _plain_chat

    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-matrix-chat-isolated")
    run_chat_turn(session, "こんにちは", chat_fn=_plain_chat(), model="qwen3:8b")
    act = session_activity(session)
    assert act["matrix_write"] == "NOT_OBSERVED"
    assert act["research_path"] == "NOT_CONNECTED"
    types = [e["type"] for e in act["events"]]
    assert "MATRIX_WRITE" not in types
    assert "matrix_write" not in types
