"""Policy HTTP。Chat 回答経路ではない。"""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread


def _start() -> tuple[ThreadingHTTPServer, int]:
    from ai_tool.chat_interface.server import ChatHandler

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ChatHandler)
    Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def test_policy_http_evaluate_blocks_false_complete():
    httpd, port = _start()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request("GET", "/api/policy")
        loaded = json.loads(conn.getresponse().read().decode("utf-8"))
        assert loaded["ok"] is True
        assert loaded["policy"]["policy_id"] == "ai-agent-development-policy"
        conn.request(
            "POST",
            "/api/policy/evaluate",
            body=json.dumps(
                {
                    "items": [{"id": "path", "status": "NOT_CONNECTED"}],
                    "tests_passed": True,
                    "claim_specification_complete": True,
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        data = json.loads(conn.getresponse().read().decode("utf-8"))
        assert data["test_status"] == "PASS"
        assert data["specification_status"] == "INCOMPLETE"
        assert data["may_claim_specification_complete"] is False
        assert data["blocked_complete_claim"] is True
        assert data["llm_used"] is False
    finally:
        httpd.shutdown()
