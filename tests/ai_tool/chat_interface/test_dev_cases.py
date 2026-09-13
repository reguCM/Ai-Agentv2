"""開発案件単位のまとめ。推測で依頼文を作らない。"""
from __future__ import annotations

from ai_tool.chat_interface.dev_cases import get_case, list_cases, run_slug, _match_reports


def test_get_system_time_is_one_case():
    listed = list_cases()
    assert listed["cursor_live"]["status"] == "NOT_OBSERVED"
    ids = [c["id"] for c in listed["cases"]]
    assert "run-20260830_224107_get_system_time" in ids
    case_id = "run-20260830_224107_get_system_time"
    detail = get_case(case_id)
    assert detail["ok"] is True
    c = detail["case"]
    assert c["actor"] == "cursor"
    assert c["request_status"] == "observed"
    assert "get_system_time" in (c["request"] or "")
    assert c["run_id"] == "20260830_224107_get_system_time"
    reports = [r["name"] for r in c["reports"]]
    assert "TDA_GET_SYSTEM_TIME.md" in reports
    paths = [f["path"] for f in (c["related_git"] or {}).get("files") or []]
    assert "tools/system/time/get_system_time.py" in paths
    assert "tests/test_get_system_time.py" in paths
    assert "registry/tools.json" in paths
    claim = c.get("cursor_report") or {}
    assert "28 passed" in str(claim.get("text") or "")
    test_ids = [t["id"] for t in c.get("cursor_tests") or []]
    assert "A_DirectCall" in test_ids
    assert "B_ReturnShape" in test_ids
    assert "C_ExistingToolRegression" in test_ids
    direct = next(t for t in c["cursor_tests"] if t["id"] == "A_DirectCall")
    assert direct["source"] == "cursor_report"
    assert direct["actor"] == "cursor"
    assert direct["status"] == "PASS"
    assert direct.get("observed", {}).get("executor") == "cursor_python"
    blob = str(c)
    assert "CPU/GPU Toolの温度" not in blob
    types = [e.get("type") for e in c["events"]]
    assert types.index("ARTIFACT") < types.index("RUN")
    assert types.index("RUN") < types.index("CURSOR_REPORT")
    assert types.index("CURSOR_REPORT") < types.index("TEST")
    assert c["mechanical_tests"]["status"] == "NOT_AVAILABLE"
    actors = {e.get("actor") for e in c["events"]}
    assert "cursor" in actors
    assert "mechanical" in actors
    blob = str(c)
    assert "Cursor is running" not in blob
    assert "実装開始" not in blob
    repo = detail["repository_status"]
    assert "untracked" in repo
    assert "この案件の変更とは限りません" in (repo.get("note") or "")


def test_missing_request_is_labeled():
    assert run_slug("20260830_211406_r3_5c_local_agent_ui") == "r3_5c_local_agent_ui"
    listed = list_cases()
    row = next(c for c in listed["cases"] if c["id"] == "run-20260830_211406_r3_5c_local_agent_ui")
    if row["request_status"] == "missing":
        assert row["title_source"] == "run_id_slug"
    reports = _match_reports("r3_5c_local_agent_ui")
    names = [r["name"] for r in reports]
    assert any("R3_5C" in n or "LOCAL_AGENT_UI" in n for n in names)


def test_case_invalid_and_missing():
    bad = get_case("../secret")
    assert bad["ok"] is False
    assert bad["error_kind"] == "invalid_id"
    missing = get_case("run-does-not-exist")
    assert missing["ok"] is False


def test_filter_tool_includes_system_time():
    data = list_cases(category="tool")
    ids = [c["id"] for c in data["cases"]]
    assert "run-20260830_224107_get_system_time" in ids
    assert "run-20260830_233232_get_memory_status" in ids
    latest = list_cases(category="latest")
    assert len(latest["cases"]) == 1


def test_get_memory_status_is_one_case():
    listed = list_cases()
    assert "run-20260830_233232_get_memory_status" in [c["id"] for c in listed["cases"]]
    detail = get_case("run-20260830_233232_get_memory_status")
    assert detail["ok"] is True
    c = detail["case"]
    assert c["actor"] == "cursor"
    assert c["request_status"] == "observed"
    assert "get_memory_status" in (c["slug"] or "")
    reports = [r["name"] for r in c["reports"]]
    assert "TDA_GET_MEMORY_STATUS.md" in reports
    paths = [f["path"] for f in (c["related_git"] or {}).get("files") or []]
    assert "tools/system/memory/get_memory_status.py" in paths
    assert "tests/test_get_memory_status.py" in paths
    assert "registry/tools.json" in paths
    assert "69 passed" in str((c.get("cursor_report") or {}).get("text") or "")
    assert c["mechanical_tests"]["status"] == "NOT_AVAILABLE"
    test_ids = [t["id"] for t in c.get("cursor_tests") or []]
    assert "A_DirectCall" in test_ids
    assert c["kind"] == "tool"
