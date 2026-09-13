"""search_files Registry 公開（P2-3）のテスト。"""

from __future__ import annotations

import json
import platform

import pytest

from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from tools.file.workspace.search_files import search_files
from tools.system.tool_contract import (
    build_agent_ollama_tools,
    get_registry_tool,
    registry_entry_to_ollama_tool,
)

SAMPLE_FILE = "tests/fixtures/p2_read_file_sample.txt"


# --- Registry / Schema ---


def test_search_files_in_registry() -> None:
    entry = get_registry_tool("search_files")
    assert entry["module"] == "tools.file.workspace.search_files"
    assert entry["function"] == "search_files"
    assert entry["visibility"] == "agent"
    assert entry.get("side_effect") == "read-only"
    props = (entry.get("input") or {})
    assert "query" in props
    assert "after" in props
    assert "glob" not in props


def test_search_files_ollama_schema() -> None:
    entry = get_registry_tool("search_files")
    ollama = registry_entry_to_ollama_tool(entry)
    fn = ollama["function"]
    assert fn["name"] == "search_files"
    params = fn["parameters"]
    assert "query" in params["properties"]
    assert "path" in params["properties"]
    assert "after" in params["properties"]
    assert "query" in params["required"]
    assert "after" not in params["required"]
    assert "glob" not in params["properties"]


def test_search_files_exposed_in_agent_tools() -> None:
    names = {t["function"]["name"] for t in build_agent_ollama_tools()}
    assert "search_files" in names
    assert "read_file" in names
    assert "list_files" in names


# --- 正常系 ---


def test_search_files_finds_string_in_workspace() -> None:
    result = search_files("get_gpu_status", path="tools/system/gpu")
    assert result["ok"] is True
    assert result["match_count"] >= 1
    assert any("gpu_status.py" in m["path"] for m in result["matches"])


def test_search_files_recursive_under_directory() -> None:
    result = search_files("def get_gpu_status", path="tools")
    assert result["ok"] is True
    paths = {m["path"] for m in result["matches"]}
    assert any("gpu_status.py" in p for p in paths)


def test_search_files_multiple_lines_same_file() -> None:
    result = search_files("P2-1", path="tests/fixtures")
    assert result["ok"] is True
    sample_matches = [m for m in result["matches"] if m["path"].endswith("p2_read_file_sample.txt")]
    assert len(sample_matches) >= 1
    assert all("line" in m and "text" in m for m in sample_matches)


def test_search_files_no_matches() -> None:
    result = search_files("zzz_no_match_token_p2_3_xyz", path="tests/fixtures")
    assert result["ok"] is True
    assert result["match_count"] == 0
    assert result["matches"] == []


def test_search_files_via_registry_execute() -> None:
    rec = execute_registry_tool(
        "search_files",
        {"query": "P2-1", "path": "tests/fixtures"},
    )
    assert rec.ok is True
    assert rec.result["match_count"] >= 1


def test_search_files_plain_string_not_regex() -> None:
    result = search_files("get_.*_status", path="tools/system/gpu")
    assert result["ok"] is True
    assert result["match_count"] == 0


def test_search_files_single_file_path() -> None:
    result = search_files("P2-1", path=SAMPLE_FILE)
    assert result["ok"] is True
    assert result["match_count"] >= 1
    assert all(m["path"].endswith("p2_read_file_sample.txt") for m in result["matches"])


# --- 異常系 ---


def test_search_files_empty_query() -> None:
    result = search_files("")
    assert result["ok"] is False
    assert "query" in result["error"]["message"]


def test_search_files_missing_path() -> None:
    result = search_files("test", path="tests/does_not_exist_p2_3")
    assert result["ok"] is False
    assert "存在しません" in result["error"]["message"]


@pytest.mark.parametrize(
    "bad_path",
    [
        "../README.md",
        "..\\README.md",
        "tests/../../README.md",
        "/etc",
        "C:\\Windows\\System32",
        "\\\\localhost\\c$\\Windows",
    ],
)
def test_search_files_rejects_escape_paths(bad_path: str) -> None:
    if bad_path.startswith("/etc") and platform.system().lower() == "windows":
        pytest.skip("POSIX absolute path on Windows")
    result = search_files("test", path=bad_path)
    assert result["ok"] is False
    payload = json.dumps(result, ensure_ascii=False).lower()
    assert "root=" not in payload


def test_search_files_error_serializable_for_llm() -> None:
    result = search_files("x", path="../outside")
    assert result["ok"] is False
    payload = json.dumps(result, ensure_ascii=False)
    assert json.loads(payload)["ok"] is False


# --- Native Tool Calling ループ（Ollama 非依存） ---


def test_search_files_native_tool_calling_loop_mock() -> None:
    messages = [
        {
            "role": "user",
            "content": "tools/system/gpu 以下で get_gpu_status を検索して",
        },
    ]
    rec = execute_registry_tool(
        "search_files",
        {"query": "get_gpu_status", "path": "tools/system/gpu"},
    )
    assert rec.ok is True
    messages.append(
        {
            "role": "tool",
            "tool_name": "search_files",
            "content": json.dumps(rec.result, ensure_ascii=False),
        }
    )
    assert "gpu_status" in messages[-1]["content"]
