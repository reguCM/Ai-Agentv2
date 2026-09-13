"""R3.5-B Chat Interface。Production Workflow と agent.py CLI は変えない。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session, sessions_dir
from ai_tool.chat_interface.classify import classify_request
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f


class _Msg:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _Resp:
    def __init__(self, message):
        self.message = message


def _plain_chat(_content="こんにちは。Tool は使いません。"):
    def chat(**_kwargs):
        return _Resp(_Msg(content=_content, tool_calls=[]))

    return chat


def _gpu_then_answer():
    step = {"i": 0}

    def chat(**_kwargs):
        if step["i"] == 0:
            step["i"] += 1
            fn = SimpleNamespace(name="get_gpu_status", arguments={})
            call = SimpleNamespace(function=fn)
            return _Resp(_Msg(content="", tool_calls=[call]))
        return _Resp(_Msg(content="GPUの状態を確認しました。", tool_calls=[]))

    return chat


def test_default_workflow_still_off():
    result = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
    )
    assert result.facet_discovery == "off"


def test_phase_f_still_adopt():
    result = run_phase_f(llm_enabled=False)
    assert result["decision"] == "ADOPT"
    assert result["core_discovery"]["c3_implemented"] == 0


def test_classify_routes():
    assert classify_request("GPUの状態を教えて") == "chat"
    assert classify_request("こんにちは") == "chat"
    assert classify_request("CPU温度を取得するToolを作って") == "tool_creation"


def test_hello_no_tools_with_mock_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR",
        tmp_path / "sessions",
    )
    session = empty_session("cs-test-hello")
    result = run_chat_turn(session, "こんにちは", chat_fn=_plain_chat())
    assert result["route"] == "chat"
    assert result["tool_used"] is False
    assert result["web_search"] is False
    assert result["research_saved"] is False
    assert result["cursor_connected"] is False
    assert result["memory"]["dump_all_passed_to_llm"] is False
    types = [e["type"] for e in result["events"]]
    assert "tool" in types
    assert any(e.get("status") == "none" for e in result["events"] if e["type"] == "tool")
    assert any("Tool は使いませんでした" in line for line in result["status_lines"])
    assert any("ユーザー入力を受信しました" in line for line in result["status_lines"])


def test_gpu_tool_path_with_mock_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR",
        tmp_path / "sessions",
    )
    session = empty_session("cs-test-gpu")
    result = run_chat_turn(session, "GPUの状態を教えて", chat_fn=_gpu_then_answer())
    assert result["tool_used"] is True
    names = [t["name"] for t in result["tools"]]
    assert "get_gpu_status" in names
    assert result["web_search"] is False
    assert "tool_select" in [e["type"] for e in result["events"]]
    assert any("get_gpu_status を選択しました" in line for line in result["status_lines"])


def test_tool_create_does_not_write_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR",
        tmp_path / "sessions",
    )
    registry = Path("registry/tools.json")
    before = registry.read_text(encoding="utf-8")
    session = empty_session("cs-test-create")
    result = run_chat_turn(
        session,
        "CPU温度を取得するToolを作って",
        chat_fn=_plain_chat("仕様案: cpu_temp。登録しません。"),
    )
    after = registry.read_text(encoding="utf-8")
    assert result["route"] == "tool_creation"
    assert result["registry_write"] is False
    assert result["awaiting_human_review"] is True
    assert after == before


def test_followup_does_not_dump_all_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR",
        tmp_path / "sessions",
    )
    session = empty_session("cs-test-follow")
    result = run_chat_turn(
        session,
        "前に調べたAをPython 3.13で使えるか調べて",
        chat_fn=_plain_chat("ResearchRecord が無いので bind できません。"),
    )
    mem = result["memory"]
    assert mem["dump_all_passed_to_llm"] is False
    assert mem["research_saved"] is False
    assert mem["copied_312_evidence_to_313"] is False
    assert mem["pointer"]["status"] in {"UNRESOLVED", "BOUND", "NOT_A_POINTER"}
    assert mem["all_memory_facet_count"] == 0
    assert "dump_all" not in json.dumps(result.get("answer") or "")
