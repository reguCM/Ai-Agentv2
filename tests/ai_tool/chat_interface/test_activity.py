"""Local Agent 処理の観測。Cursor 経路は推測しない。"""
from __future__ import annotations

from types import SimpleNamespace

from ai_tool.chat_interface.activity import session_activity, stamp_events
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.dev_cases import get_case
from tests.ai_tool.chat_interface.test_r35b_chat_interface import _gpu_then_answer, _plain_chat


def _search_then_answer():
    step = {"i": 0}

    def chat(**_kwargs):
        if step["i"] == 0:
            step["i"] += 1
            fn = SimpleNamespace(name="search_web", arguments={"query": "RTX 3060 specifications"})
            call = SimpleNamespace(function=fn)
            return SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]))
        return SimpleNamespace(message=SimpleNamespace(content="調査しました。", tool_calls=[]))

    return chat


def _two_tools_then_answer():
    step = {"i": 0}

    def chat(**_kwargs):
        if step["i"] == 0:
            step["i"] += 1
            gpu = SimpleNamespace(function=SimpleNamespace(name="get_gpu_status", arguments={}))
            cpu = SimpleNamespace(function=SimpleNamespace(name="get_cpu_status", arguments={}))
            return SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[gpu, cpu]))
        return SimpleNamespace(message=SimpleNamespace(content="両方確認しました。", tool_calls=[]))

    return chat


def _two_searches_then_answer():
    step = {"i": 0}

    def chat(**_kwargs):
        if step["i"] == 0:
            step["i"] += 1
            first = SimpleNamespace(function=SimpleNamespace(name="search_web", arguments={"query": "q1 nvidia vram"}))
            second = SimpleNamespace(function=SimpleNamespace(name="search_web", arguments={"query": "q2 rtx 3060"}))
            return SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[first, second]))
        return SimpleNamespace(message=SimpleNamespace(content="2件調べました。", tool_calls=[]))

    return chat


def test_hello_has_no_tool_call(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-act-hello")
    session["model"] = "qwen3:8b"
    result = run_chat_turn(session, "こんにちは", chat_fn=_plain_chat(), model="qwen3:8b")
    cid = result["correlation_id"]
    assert cid.startswith("ac-")
    assert session["turns"][-1]["correlation_id"] == cid
    assert {e.get("correlation_id") for e in result["events"]} == {cid}
    assert result["development_job"] is None
    types = [e.get("type") for e in result["events"]]
    assert "local_agent_call" in types
    assert "tool_call" not in types or all(
        e.get("status") == "none" for e in result["events"] if e.get("type") == "tool"
    )
    act = session_activity(session)
    assert act["cursor_to_local_agent"] == "NOT_CONNECTED"
    tool_rows = [e for e in act["events"] if e["type"] == "TOOL_CALL"]
    assert tool_rows
    assert tool_rows[0]["title"] == "Local Agent Tool Call: NONE"
    assert tool_rows[0]["status"] == "none"
    llm = next(e for e in act["events"] if e["type"] == "LLM_CALL")
    assert llm["model"] == "qwen3:8b"
    assert llm["executed_by"] == "local_llm"


def test_gpu_tool_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-act-gpu")
    session["model"] = "qwen3:8b"
    result = run_chat_turn(session, "GPUの温度を教えて", chat_fn=_gpu_then_answer(), model="qwen3:8b")
    names = [t["name"] for t in result["tools"]]
    assert "get_gpu_status" in names
    cid = result["correlation_id"]
    assert cid.startswith("ac-")
    stamped = [e for e in result["events"] if e.get("type") == "tool_result"]
    assert stamped
    assert stamped[0]["correlation_id"] == cid
    assert stamped[0]["executed_by"] == "local_agent"
    assert stamped[0]["requested_by"] == "user"
    act = session_activity(session)
    tools = [e for e in act["events"] if e["type"] == "TOOL_CALL" and e.get("name") == "get_gpu_status"]
    assert tools
    assert tools[0]["correlation_id"] == cid


def test_search_summary_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda name, arguments, **_k: {
            "query": "RTX 3060 specifications",
            "hits": [{"title": "RTX 3060"}, {"title": "spec"}],
        },
    )
    session = empty_session("cs-act-search")
    result = run_chat_turn(session, "RTX 3060について調べて", chat_fn=_search_then_answer(), model="qwen3:8b")
    assert any(t["name"] == "search_web" for t in result["tools"])
    act = session_activity(session)
    search = [e for e in act["events"] if e["type"] == "SEARCH"]
    assert search
    assert search[0]["query"] == "RTX 3060 specifications"
    assert search[0]["hit_count"] == 2
    assert search[0]["executed_by"] == "local_agent"
    writes = [e for e in act["events"] if e["type"] == "RESEARCH_WRITE"]
    assert writes
    assert writes[0]["status"] == "NOT_OBSERVED"
    assert result["research_saved"] is False
    web = next(e for e in result["events"] if e.get("type") == "web_search")
    assert web["hit_count"] == 2
    assert web["query"] == "RTX 3060 specifications"
    assert web["actor"] == "local_agent"
    assert web["executed_by"] == "local_agent"
    assert search[0]["layer"] == "real"
    assert search[0]["search_index"] == 1
    search_steps = [s for s in result["pipeline"] if s.get("id") == "search"]
    assert search_steps
    assert search_steps[0]["query"] == "RTX 3060 specifications"
    write_step = next(s for s in result["pipeline"] if s["id"] == "research_write")
    assert write_step["status"] == "NOT_OBSERVED"
    assert write_step["executed"] is False
    path_step = next(s for s in result["pipeline"] if s["id"] == "research_path")
    assert path_step["status"] == "NOT_CONNECTED"
    assert path_step["executed"] is False
    types = [e["type"] for e in act["events"]]
    assert "RESEARCH_PROCESS" not in types
    assert "RESEARCH_RESULT" not in types
    assert act["research_path"] == "NOT_CONNECTED"
    assert act["matrix_write"] == "NOT_OBSERVED"


def test_multiple_searches_share_correlation_and_keep_index(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")

    def _exec(name, arguments, **_k):
        query = (arguments or {}).get("query")
        return {
            "query": query,
            "hits": [{"title": str(query)}],
            "backends_tried": ["duckduckgo"],
            "error": None,
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", _exec)
    session = empty_session("cs-act-two-search")
    result = run_chat_turn(
        session,
        "NVIDIAとRTX 3060を調べて",
        chat_fn=_two_searches_then_answer(),
        model="qwen3:8b",
    )
    cid = result["correlation_id"]
    searches = [e for e in session_activity(session)["events"] if e["type"] == "SEARCH"]
    assert len(searches) == 2
    assert {e["correlation_id"] for e in searches} == {cid}
    assert [e["query"] for e in searches] == ["q1 nvidia vram", "q2 rtx 3060"]
    assert [e["search_index"] for e in searches] == [1, 2]
    assert [e["hit_count"] for e in searches] == [1, 1]
    assert searches[0]["actor"] == "local_agent"
    assert searches[0]["model"] == "qwen3:8b"
    writes = [e for e in session_activity(session)["events"] if e["type"] == "RESEARCH_WRITE"]
    assert writes[0]["status"] == "NOT_OBSERVED"


def test_hello_has_no_search_or_write(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-act-hello-search")
    result = run_chat_turn(session, "こんにちは", chat_fn=_plain_chat(), model="qwen3:8b")
    act = session_activity(session)
    assert [e for e in act["events"] if e["type"] == "SEARCH"] == []
    writes = [e for e in act["events"] if e["type"] == "RESEARCH_WRITE"]
    assert writes
    assert writes[0]["status"] == "NOT_OBSERVED"
    paths = [e for e in act["events"] if e["type"] == "RESEARCH_PATH"]
    assert paths
    assert paths[0]["status"] == "NOT_CONNECTED"
    assert "RESEARCH_PROCESS" not in [e["type"] for e in act["events"]]
    assert result["research_saved"] is False
    assert result["web_search"] is False
    write_step = next(s for s in result["pipeline"] if s["id"] == "research_write")
    assert write_step["executed"] is False


def test_multiple_tools_keep_order(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-act-multi")
    result = run_chat_turn(session, "GPUとCPUの状態を教えて", chat_fn=_two_tools_then_answer(), model="qwen3:8b")
    names = [t["name"] for t in result["tools"]]
    assert names == ["get_gpu_status", "get_cpu_status"]
    act = session_activity(session)
    tools = [e for e in act["events"] if e["type"] == "TOOL_CALL" and e.get("name")]
    assert [e["name"] for e in tools] == ["get_gpu_status", "get_cpu_status"]
    ids = {e["correlation_id"] for e in tools}
    assert len(ids) == 1


def test_cursor_case_does_not_claim_local_agent():
    detail = get_case("run-20260830_233232_get_memory_status")
    assert detail["ok"] is True
    bridge = detail["local_agent_bridge"]
    assert bridge["cursor_to_local_agent"] == "NOT_CONNECTED"
    assert bridge["local_agent_tool_call"] == "NONE"
    assert bridge["research_write"] == "NOT_OBSERVED"
    assert bridge["research_path"] == "NOT_CONNECTED"
    assert bridge["matrix_write"] == "NOT_OBSERVED"
    assert "NOT OBSERVED" in (detail["cursor_live"]["label"] or "")


def test_stamp_does_not_invent_cursor_request():
    rows = [{"type": "tool_result", "name": "get_gpu_status"}]
    stamp_events(rows, correlation_id="ac-x", model="qwen3:8b", requested_by="user")
    assert rows[0]["requested_by"] == "user"
    assert rows[0]["executed_by"] == "local_agent"
    assert rows[0].get("requested_by") != "cursor"
