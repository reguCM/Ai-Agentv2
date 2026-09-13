"""P2-4 統合フロー検証の構造テスト（Live LLM 非依存）。"""
from __future__ import annotations

from ai_tool.agent_integration.file_tools_integration_verify import (
    file_tools_system_prompt,
    run_file_tools_scenario,
)
from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools
from tools.system.tool_contract import build_agent_ollama_tools


def test_file_tools_in_production_schema() -> None:
    names = {t["function"]["name"] for t in build_agent_ollama_tools()}
    assert {"list_files", "search_files", "read_file"} <= names


def test_system_prompt_mentions_file_tools() -> None:
    names = [t["function"]["name"] for t in build_production_agent_tools()]
    prompt = file_tools_system_prompt(names)
    assert "list_files" in prompt
    assert "search_files" in prompt
    assert "read_file" in prompt


def test_run_scenario_with_mock_chat() -> None:
    calls = [
        {
            "tool_calls": [
                type(
                    "TC",
                    (),
                    {
                        "function": type(
                            "F",
                            (),
                            {
                                "name": "list_files",
                                "arguments": '{"path": "tests/fixtures"}',
                            },
                        )()
                    },
                )()
            ],
            "content": "",
        },
        {"tool_calls": [], "content": "fixtures に3件"},
    ]
    state = {"i": 0}

    def mock_chat(**_kwargs):
        item = calls[state["i"]]
        state["i"] += 1
        return type(
            "R",
            (),
            {
                "message": type(
                    "M",
                    (),
                    {
                        "tool_calls": item["tool_calls"],
                        "content": item["content"],
                    },
                )()
            },
        )()

    result = run_file_tools_scenario(
        "mock",
        "tests/fixtures を一覧",
        chat_fn=mock_chat,
        model="mock",
        max_rounds=3,
    )
    assert result.tool_sequence() == ["list_files"]
    assert "fixtures" in result.final_answer
