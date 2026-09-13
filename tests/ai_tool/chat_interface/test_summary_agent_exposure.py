"""get_system_summary を Chat 公開集合へ1件追加したことの契約。"""
from __future__ import annotations

from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools, ollama_tools_for_llm
from ai_tool.chat_interface.agent_turn import AGENT_VISIBLE_DEFAULT, SYSTEM_PROMPT

UNCHANGED = (
    "get_gpu_status",
    "get_gpu_processes",
    "cpu_status",
    "get_cpu_status",
    "search_web",
    "read_url_text",
)


def test_public_set_adds_only_summary():
    assert "get_system_summary" in AGENT_VISIBLE_DEFAULT
    for name in UNCHANGED:
        assert name in AGENT_VISIBLE_DEFAULT
    assert list(AGENT_VISIBLE_DEFAULT).count("get_system_summary") == 1


def test_llm_tool_schema_includes_summary():
    names = [t["function"]["name"] for t in ollama_tools_for_llm(build_production_agent_tools())]
    assert "get_system_summary" in names
    for name in UNCHANGED:
        assert name in names


def test_prompt_uses_supplied_registry_schema_as_public_tool_source():
    assert "Registry由来のTool schemaを正本" in SYSTEM_PROMPT
