"""Event 観測は LLM へ渡す raw result とは別。再実行しない。無いキーは作らない。"""
from __future__ import annotations

from types import SimpleNamespace

from ai_tool.chat_interface.activity import session_activity
from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.events import pipeline_steps, summarize_tool_result
from ai_tool.chat_interface.tool_observation import observe_tool_result
from tests.ai_tool.chat_interface.test_r35b_chat_interface import _gpu_then_answer, _plain_chat


def _summary_then_answer():
    step = {"i": 0}

    def chat(**_kwargs):
        if step["i"] == 0:
            step["i"] += 1
            fn = SimpleNamespace(name="get_system_summary", arguments={})
            call = SimpleNamespace(function=fn)
            return SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]))
        return SimpleNamespace(message=SimpleNamespace(content="要約しました。", tool_calls=[]))

    return chat


COMPOSED = {
    "status": "ok",
    "ok": True,
    "error": None,
    "observation_source": "composed",
    "source": "existing_observation_tools",
    "sections": {
        "time": {
            "datetime": "2026-08-31T00:12:50+09:00",
            "timezone": "Tokyo Standard Time",
            "formatted": "2026-08-31 00:12:50 +0900",
            "ok": True,
            "status": "ok",
            "error": None,
            "observation_source": "real",
        },
        "cpu": {
            "model": "12th Gen Intel(R) Core(TM) i5-12400",
            "physical_cores": 6,
            "load_percentage": 40,
            "ok": True,
            "status": "ok",
        },
        "memory": {
            "total_mb": 65277,
            "used_mb": 30215,
            "free_mb": 35061,
            "used_percent": 46,
            "ok": True,
            "status": "ok",
        },
        "gpu": {
            "gpu": "NVIDIA GeForce RTX 3060",
            "temperature": 61.0,
            "utilization": 11.0,
            "vram_used": 7843,
            "vram_total": 12288,
            "ok": True,
            "status": "ok",
        },
    },
    "derived": {"ok_by_section": {"time": True, "cpu": True, "memory": True, "gpu": True}},
    "hits": [{"title": "should-not-store-on-summary"}],
}


def test_observe_summary_keeps_sections_not_hits():
    obs = observe_tool_result("get_system_summary", COMPOSED)
    assert obs["status"] == "success"
    assert obs["observation_source"] == "composed"
    assert obs["composed_section_keys"] == ["time", "cpu", "memory", "gpu"]
    assert obs["independent_tool_calls"] is False
    assert obs["sections"]["memory"]["used_mb"] == 30215
    assert obs["sections"]["gpu"]["gpu"] == "NVIDIA GeForce RTX 3060"
    assert "hits" not in obs["sections"]
    assert "hits" in (obs.get("omitted") or [])
    assert "invented" not in obs
    assert "get_system_time" not in obs


def test_observe_does_not_invent_missing_fields():
    obs = observe_tool_result("get_gpu_status", {"ok": True, "gpu": "NVIDIA GeForce RTX 3060", "status": "ok"})
    assert obs["gpu"] == "NVIDIA GeForce RTX 3060"
    assert "temperature" not in obs
    assert "sections" not in obs
    assert "composed_section_keys" not in obs


def test_observe_search_omits_hit_bodies():
    obs = observe_tool_result(
        "search_web",
        {
            "query": "q",
            "status": "ok",
            "source": "web",
            "hits": [{"title": "A", "url": "https://example.test", "snippet": "secret body"}],
        },
    )
    assert obs["query"] == "q"
    assert obs["hit_count"] == 1
    assert obs["status"] == "success"
    assert obs["source"] == "web"
    assert obs["omitted"] == ["hits"]
    assert "snippet" not in str(obs.get("titles"))
    assert "https://example.test" not in str(obs)


def test_observe_search_keeps_backends_not_hit_bodies():
    obs = observe_tool_result(
        "search_web",
        {
            "query": "q",
            "hits": [{"title": "A", "url": "https://example.test", "snippet": "secret body"}],
            "backends_tried": ["duckduckgo", "bing"],
            "fetch_limit": 8,
            "return_limit": 5,
            "candidates_collected": 3,
            "web_status": {"overall": "PARTIAL"},
            "error": None,
        },
    )
    assert obs["query"] == "q"
    assert obs["hit_count"] == 1
    assert obs["backends_tried"] == ["duckduckgo", "bing"]
    assert obs["fetch_limit"] == 8
    assert obs["web_status_overall"] == "PARTIAL"
    assert obs["omitted"] == ["hits"]
    assert "secret body" not in str(obs)
    assert "https://example.test" not in str(obs)


def test_observe_read_url_omits_body():
    obs = observe_tool_result(
        "read_url_text",
        {"url": "https://example.test", "main_text": "x" * 5000, "quality": {"fact_ready": True}},
    )
    assert obs["url"] == "https://example.test"
    assert obs["main_text_chars"] == 5000
    assert obs["fact_ready"] is True
    assert obs["omitted"] == ["main_text"]
    assert "main_text" not in obs
    assert "x" * 50 not in str(obs)


def test_hello_has_no_tool_result_observation(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-obs-hello")
    result = run_chat_turn(session, "こんにちは", chat_fn=_plain_chat(), model="qwen3:8b")
    assert result["tools"] == []
    assert not any(e.get("type") == "tool_result" for e in result["events"])
    assert not any(e.get("type") == "compose" for e in result["events"])
    steps = result["pipeline"]
    assert not any(s.get("id") == "tool_result" for s in steps)
    act = session_activity(session)
    assert [e["type"] for e in act["events"] if e["type"] in {"TOOL_RESULT", "COMPOSE"}] == []


def test_gpu_observation_from_real_execute(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    session = empty_session("cs-obs-gpu")
    result = run_chat_turn(session, "GPUの状態を教えて", chat_fn=_gpu_then_answer(), model="qwen3:8b")
    tool = next(t for t in result["tools"] if t["name"] == "get_gpu_status")
    summary = tool["summary"]
    assert "gpu" in summary or "status" in summary
    assert summary.get("composed_section_keys") is None
    tr = next(e for e in result["events"] if e.get("type") == "tool_result")
    assert tr["summary"] == summary
    act = session_activity(session)
    results = [e for e in act["events"] if e["type"] == "TOOL_RESULT"]
    assert results
    assert results[0]["name"] == "get_gpu_status"


def test_composed_result_emits_compose_without_child_tool_calls(tmp_path, monkeypatch):
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        lambda name, arguments, **_k: dict(COMPOSED),
    )
    session = empty_session("cs-obs-sum")
    result = run_chat_turn(
        session,
        "今のPCのシステム状態を教えて",
        chat_fn=_summary_then_answer(),
        model="qwen3:8b",
    )
    names = [t["name"] for t in result["tools"]]
    assert names == ["get_system_summary"]
    types = [e.get("type") for e in result["events"]]
    assert types.count("tool_call") == 1
    assert types.count("compose") == 1
    compose = next(e for e in result["events"] if e["type"] == "compose")
    assert compose["sections"] == ["time", "cpu", "memory", "gpu"]
    assert compose["independent_tool_calls"] is False
    assert compose["executed_by"] == "local_agent"
    summary = result["tools"][0]["summary"]
    assert summary["sections"]["memory"]["total_mb"] == 65277
    pipeline_ids = [s["id"] for s in result["pipeline"]]
    assert pipeline_ids.count("compose") == 1
    act = session_activity(session)
    assert [e["name"] for e in act["events"] if e["type"] == "TOOL_CALL" and e.get("name")] == ["get_system_summary"]
    compose_rows = [e for e in act["events"] if e["type"] == "COMPOSE"]
    assert compose_rows
    assert compose_rows[0]["sections"] == ["time", "cpu", "memory", "gpu"]


def test_summarize_delegates_to_observation():
    out = summarize_tool_result("get_system_summary", COMPOSED)
    assert out["composed_section_keys"] == ["time", "cpu", "memory", "gpu"]


def test_pipeline_skips_compose_when_no_sections():
    steps = pipeline_steps(
        model="qwen3:8b",
        tools=[{"name": "get_gpu_status", "status": "success", "summary": {"ok": True, "gpu": "x"}}],
    )
    assert [s["id"] for s in steps if s["id"] == "compose"] == []
    assert any(s["id"] == "tool_result" for s in steps)


def test_pipeline_search_does_not_mark_write_executed():
    steps = pipeline_steps(
        model="qwen3:8b",
        tools=[
            {
                "name": "search_web",
                "status": "success",
                "summary": {"query": "q", "hit_count": 2, "omitted": ["hits"]},
            }
        ],
        web_search=True,
        research_saved=False,
    )
    ids = [s["id"] for s in steps]
    assert ids.count("search") == 1
    search = next(s for s in steps if s["id"] == "search")
    assert search["query"] == "q"
    assert search["hit_count"] == 2
    assert search["executed"] is True
    result = next(s for s in steps if s["id"] == "tool_result")
    assert result["label"] == "SEARCH_RESULT"
    write = next(s for s in steps if s["id"] == "research_write")
    assert write["status"] == "NOT_OBSERVED"
    assert write["executed"] is False
    path = next(s for s in steps if s["id"] == "research_path")
    assert path["status"] == "NOT_CONNECTED"
    assert path["executed"] is False
    assert "RESEARCH_PROCESS" not in ids
