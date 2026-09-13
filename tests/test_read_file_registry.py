"""read_file Registry 公開（P2-1）のテスト。"""

from __future__ import annotations

import json
import platform

import pytest

from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from tools.file.workspace.read_file import read_file
from tools.system.tool_contract import (
    build_agent_ollama_tools,
    get_registry_tool,
    registry_entry_to_ollama_tool,
)

SAMPLE_PATH = "tests/fixtures/p2_read_file_sample.txt"


# --- Test 1: Registry ---


def test_read_file_in_registry() -> None:
    entry = get_registry_tool("read_file")
    assert entry["module"] == "tools.file.workspace.read_file"
    assert entry["function"] == "read_file"
    assert entry["visibility"] == "agent"
    assert entry.get("side_effect") == "read-only"


# --- Test 2: Schema ---


def test_read_file_ollama_schema() -> None:
    entry = get_registry_tool("read_file")
    ollama = registry_entry_to_ollama_tool(entry)
    fn = ollama["function"]
    assert fn["name"] == "read_file"
    params = fn["parameters"]
    assert "path" in params["properties"]
    assert "path" in params["required"]
    assert "offset" in params["properties"]
    assert "offset" not in params.get("required", [])


def test_read_file_exposed_in_agent_tools() -> None:
    names = {t["function"]["name"] for t in build_agent_ollama_tools()}
    assert "read_file" in names
    assert "list_files" in names
    assert "search_files" in names


# --- Test 3: 正常読込 ---


def test_read_file_success() -> None:
    result = read_file(SAMPLE_PATH)
    assert result["ok"] is True
    assert result["path"] == SAMPLE_PATH.replace("\\", "/")
    assert result["total_lines"] >= 2
    assert result["lines"][0]["text"].startswith("P2-1")
    assert result["error"] is None


def test_read_file_via_registry_execute() -> None:
    rec = execute_registry_tool("read_file", {"path": SAMPLE_PATH})
    assert rec.ok is True
    assert rec.result["ok"] is True
    assert rec.result["lines"]


def test_read_file_offset_limit() -> None:
    result = read_file(SAMPLE_PATH, offset=2, limit=1)
    assert result["ok"] is True
    assert result["returned_lines"] == 1
    assert "offset" in result["lines"][0]["text"].lower()


# --- Test 4: 不存在 ---


def test_read_file_missing_file() -> None:
    result = read_file("tests/fixtures/does_not_exist_p2_1.txt")
    assert result["ok"] is False
    assert "存在しません" in result["error"]["message"]


# --- Test 5 & 6: Workspace 外 / Path Traversal ---


@pytest.mark.parametrize(
    "bad_path",
    [
        "../README.md",
        "..\\README.md",
        "tests/../../README.md",
        "tests\\..\\..\\README.md",
        "/etc/passwd",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "\\\\localhost\\c$\\Windows\\System32\\drivers\\etc\\hosts",
    ],
)
def test_read_file_rejects_escape_paths(bad_path: str) -> None:
    if bad_path.startswith("/etc") and platform.system().lower() == "windows":
        pytest.skip("POSIX absolute path on Windows")
    result = read_file(bad_path)
    assert result["ok"] is False
    err = result["error"]["message"].lower()
    assert any(
        token in err
        for token in (
            "workspace",
            "禁止",
            "使用できません",
            "..",
        )
    )


def test_read_file_rejects_directory() -> None:
    result = read_file("registry")
    assert result["ok"] is False
    assert "ディレクトリ" in result["error"]["message"]


# --- Test 7: Tool error → LLM 返却可能形 ---


def test_read_file_error_serializable_for_llm() -> None:
    result = read_file("../outside_workspace.txt")
    assert result["ok"] is False
    payload = json.dumps(result, ensure_ascii=False)
    parsed = json.loads(payload)
    assert parsed["ok"] is False
    assert parsed["error"]
    assert "root=" not in payload.lower()


# --- Test 8: Native Tool Calling ループ（mock LLM） ---


def test_read_file_native_tool_calling_loop_mock() -> None:
    """LLM tool_call → execute_registry_tool → role=tool 返却の最小ループ（Ollama 非依存）。"""
    messages: list[dict] = [
        {"role": "user", "content": f"{SAMPLE_PATH} を読んで1行目を教えて"},
    ]

    tool_name = "read_file"
    arguments = {"path": SAMPLE_PATH}
    rec = execute_registry_tool(tool_name, arguments)
    assert rec.ok is True

    messages.append(
        {
            "role": "tool",
            "tool_name": tool_name,
            "content": json.dumps(rec.result, ensure_ascii=False),
        }
    )

    assert any(m.get("role") == "tool" for m in messages)
    tool_content = messages[-1]["content"]
    assert "P2-1" in tool_content
    parsed = json.loads(tool_content)
    assert parsed["ok"] is True
