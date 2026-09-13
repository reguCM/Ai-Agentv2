"""Chat UI 開発状況パネル。読み取り専用。pytest は自動実行しない。"""
from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from ai_tool.chat_interface import dev_readonly
from ai_tool.chat_interface.dev_readonly import (
    _git,
    get_report,
    get_run,
    git_snapshot,
    list_reports,
    list_runs,
    mechanical_tests,
)


def test_unauthorized_git_args_are_rejected():
    code, out, err = _git(("commit", "-m", "x"))
    assert code == 1
    assert out == ""
    assert "許可されていない" in err


def test_mechanical_tests_do_not_use_cursor_passed_text(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    folder = runs / "run-with-claim"
    folder.mkdir(parents=True)
    (folder / "summary.json").write_text("{}", encoding="utf-8")
    (folder / "observations.json").write_text(
        json.dumps(
            {
                "unit_tests": {
                    "result": "27 passed",
                    "executor": "cursor",
                    "counts_as_local_agent": False,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dev_readonly, "RUNS_DIR", runs)
    monkeypatch.setattr(dev_readonly, "_REPO", tmp_path)

    mech = mechanical_tests()
    assert mech["source"] == "missing"
    assert mech["available"] is False
    assert mech["user_message"] == "機械的テスト結果：未取得"
    assert "27 passed" not in json.dumps(mech)

    detail = get_run("run-with-claim")
    assert detail["ok"] is True
    claim = detail["cursor_test_report"]
    assert claim["text"] == "27 passed"
    assert claim["source"] == "cursor_report"
    assert claim["counts_as_pytest"] is False
    assert detail["mechanical_tests"]["source"] == "missing"
    assert detail["mechanical_tests"]["user_message"] == "機械的テスト結果：未取得"

    snap = dev_readonly.tests_snapshot()
    assert snap["cursor_test_report"] is None
    assert snap["mechanical_tests"]["source"] == "missing"


def test_missing_run_and_path_traversal(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(dev_readonly, "RUNS_DIR", runs)

    missing = get_run("does-not-exist")
    assert missing["ok"] is False
    assert missing["error_kind"] == "not_found"

    traversal = get_run("../secret")
    assert traversal["ok"] is False
    assert traversal["error_kind"] == "invalid_id"

    slash = get_run("a/b")
    assert slash["ok"] is False
    assert slash["error_kind"] == "invalid_id"


def test_missing_report_and_path_traversal(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "ok.md").write_text("# hi\n<script>alert(1)</script>", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(dev_readonly, "REPORTS_DIR", reports)

    listed = list_reports()
    assert listed["ok"] is True
    assert listed["reports"][0]["name"] == "ok.md"

    body = get_report("ok.md")
    assert body["ok"] is True
    assert "<script>alert(1)</script>" in body["text"]

    missing = get_report("nope.md")
    assert missing["ok"] is False
    assert missing["error_kind"] == "not_found"

    traversal = get_report("../outside.md")
    assert traversal["ok"] is False
    assert traversal["error_kind"] == "invalid_id"
    assert "secret" not in json.dumps(traversal)


def test_list_runs_reads_summary_only(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    folder = runs / "20260830_test_run"
    folder.mkdir(parents=True)
    (folder / "summary.json").write_text(
        json.dumps(
            {
                "run_id": "20260830_test_run",
                "judgment": "PASS",
                "judgment_ja": "概要のみ",
                "session_id": "cs-test",
            }
        ),
        encoding="utf-8",
    )
    (runs / "empty_dir").mkdir()
    monkeypatch.setattr(dev_readonly, "RUNS_DIR", runs)

    data = list_runs()
    assert [r["run_id"] for r in data["runs"]] == ["20260830_test_run"]
    assert data["runs"][0]["judgment"] == "PASS"
    assert data["runs"][0]["source"] == "summary.json"


def test_git_snapshot_is_read_only():
    snap = git_snapshot()
    assert snap["read_only"] is True
    joined = " ".join(snap.get("commands") or [])
    for banned in ("commit", "reset", "checkout", "push", "pull"):
        assert banned not in joined
    assert "status" in joined
    assert "diff" in joined
    assert "log" in joined
    assert "counts" in snap
    assert "files" in snap
    assert "commits" in snap
    assert snap.get("head")
    assert snap.get("branch")


def test_real_run_separates_cursor_claim_from_pytest():
    detail = get_run("20260830_211406_r3_5c_local_agent_ui")
    assert detail["ok"] is True
    claim = detail["cursor_test_report"]
    assert claim is not None
    assert "passed" in claim["text"]
    assert claim["counts_as_pytest"] is False
    assert detail["mechanical_tests"]["source"] == "missing"
    assert detail["mechanical_tests"]["user_message"] == "機械的テスト結果：未取得"


def test_real_report_list_and_body():
    listed = list_reports()
    names = [r["name"] for r in listed["reports"]]
    assert "TDA_R3_5C_LOCAL_AGENT_UI.md" in names
    body = get_report("TDA_R3_5C_LOCAL_AGENT_UI.md")
    assert body["ok"] is True
    assert body["text"].startswith("# Local Agent UI")
    assert body["kind"] == "development"


def _start_chat_server() -> tuple[ThreadingHTTPServer, int]:
    from ai_tool.chat_interface.server import ChatHandler

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ChatHandler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


def test_http_dev_and_existing_chat_routes():
    httpd, port = _start_chat_server()
    conn = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        conn.request("GET", "/api/dev/runs")
        runs = json.loads(conn.getresponse().read().decode("utf-8"))
        assert runs["ok"] is True
        assert runs["kind"] == "development"
        assert any(r["run_id"] == "20260830_211406_r3_5c_local_agent_ui" for r in runs["runs"])

        conn.request("GET", "/api/dev/runs/does-not-exist")
        missing_run = json.loads(conn.getresponse().read().decode("utf-8"))
        assert missing_run["ok"] is False
        assert missing_run["error_kind"] == "not_found"

        conn.request("GET", "/api/dev/runs/..%2F..%2Fsecret")
        bad_run = json.loads(conn.getresponse().read().decode("utf-8"))
        assert bad_run["ok"] is False
        assert bad_run["error_kind"] == "invalid_id"

        conn.request("GET", "/api/dev/reports")
        reports = json.loads(conn.getresponse().read().decode("utf-8"))
        assert reports["ok"] is True

        conn.request("GET", "/api/dev/reports/nope.md")
        missing_report = json.loads(conn.getresponse().read().decode("utf-8"))
        assert missing_report["ok"] is False
        assert missing_report["error_kind"] == "not_found"

        conn.request("GET", "/api/dev/reports/..%2F..%2Foutside.md")
        bad_report = json.loads(conn.getresponse().read().decode("utf-8"))
        assert bad_report["ok"] is False
        assert bad_report["error_kind"] == "invalid_id"

        conn.request("GET", "/api/dev/git")
        git = json.loads(conn.getresponse().read().decode("utf-8"))
        assert git["read_only"] is True
        assert git["kind"] == "development"
        assert git.get("branch")
        assert git.get("head")
        assert isinstance(git.get("commits"), list)

        conn.request("GET", "/api/dev/cases")
        cases = json.loads(conn.getresponse().read().decode("utf-8"))
        assert cases["ok"] is True
        assert cases["cursor_live"]["status"] == "NOT_OBSERVED"
        assert any(c["id"] == "run-20260830_224107_get_system_time" for c in cases["cases"])

        conn.request("GET", "/api/dev/cases/run-20260830_224107_get_system_time")
        one = json.loads(conn.getresponse().read().decode("utf-8"))
        assert one["ok"] is True
        assert one["case"]["actor"] == "cursor"
        assert one["case"]["mechanical_tests"]["status"] == "NOT_AVAILABLE"
        assert "28 passed" in str((one["case"].get("cursor_report") or {}).get("text") or "")

        conn.request("GET", "/api/dev/events")
        timeline = json.loads(conn.getresponse().read().decode("utf-8"))
        assert timeline["ok"] is True
        assert timeline["cursor_live"]["status"] == "NOT_OBSERVED"
        assert "Cursor is running" not in json.dumps(timeline)

        conn.request("GET", "/api/dev/jobs")
        jobs = json.loads(conn.getresponse().read().decode("utf-8"))
        assert jobs["ok"] is True
        assert jobs["cursor_live"]["status"] == "NOT_OBSERVED"

        conn.request("GET", "/api/dev/jobs/does-not-exist")
        missing_job = json.loads(conn.getresponse().read().decode("utf-8"))
        assert missing_job["ok"] is False

        conn.request("GET", "/api/dev/tests")
        tests = json.loads(conn.getresponse().read().decode("utf-8"))
        assert tests["mechanical_tests"]["source"] == "missing"
        assert tests["cursor_test_report"] is None

        conn.request("POST", "/api/chat", body="{}", headers={"Content-Type": "application/json"})
        chat = json.loads(conn.getresponse().read().decode("utf-8"))
        assert chat["ok"] is False
        assert chat["error"] == "message が空です"
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()
