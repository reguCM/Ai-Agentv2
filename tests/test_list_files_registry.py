"""list_files Registry 公開（P2-2）のテスト。"""

from __future__ import annotations

import json
import platform

import pytest

from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from tools.file.workspace.list_files import list_files
from tools.system.tool_contract import (
    build_agent_ollama_tools,
    get_registry_tool,
    registry_entry_to_ollama_tool,
)

SAMPLE_FILE = "tests/fixtures/p2_read_file_sample.txt"


# --- Registry / Schema ---


def test_list_files_in_registry() -> None:
    entry = get_registry_tool("list_files")
    assert entry["module"] == "tools.file.workspace.list_files"
    assert entry["function"] == "list_files"
    assert entry["visibility"] == "agent"
    assert entry.get("side_effect") == "read-only"
    assert "recursive" not in (entry.get("input") or {})


def test_list_files_ollama_schema() -> None:
    entry = get_registry_tool("list_files")
    ollama = registry_entry_to_ollama_tool(entry)
    fn = ollama["function"]
    assert fn["name"] == "list_files"
    params = fn["parameters"]
    assert "path" in params["properties"]
    assert "path" not in params.get("required", [])
    assert "recursive" not in params["properties"]
    assert "glob" not in params["properties"]


def test_list_files_exposed_in_agent_tools() -> None:
    names = {t["function"]["name"] for t in build_agent_ollama_tools()}
    assert "list_files" in names
    assert "read_file" in names
    assert "search_files" in names


# --- 正常列挙 ---


def test_list_files_workspace_root() -> None:
    result = list_files(".")
    assert result["ok"] is True
    assert result["recursive"] is False
    names = {e["name"] for e in result["entries"]}
    assert "registry" in names
    assert "tests" in names
    assert result["error"] is None


def test_list_files_inner_directory() -> None:
    result = list_files("tests/fixtures")
    assert result["ok"] is True
    assert any(e["name"] == "p2_read_file_sample.txt" and e["type"] == "file" for e in result["entries"])


def test_list_files_default_path_via_registry() -> None:
    rec = execute_registry_tool("list_files", {})
    assert rec.ok is True
    assert rec.result["ok"] is True
    assert rec.result["count"] >= 1


def test_list_files_non_recursive() -> None:
    result = list_files("tests")
    assert result["ok"] is True
    entry_names = {e["name"] for e in result["entries"]}
    assert "fixtures" in entry_names
    # fixtures 配下のファイル名は直下一覧に含まれない
    assert "p2_read_file_sample.txt" not in entry_names


# --- エラー ---


def test_list_files_missing_directory() -> None:
    result = list_files("tests/does_not_exist_p2_2")
    assert result["ok"] is False
    assert "存在しません" in result["error"]["message"]


def test_list_files_file_instead_of_directory() -> None:
    result = list_files(SAMPLE_FILE)
    assert result["ok"] is False
    assert "ディレクトリ" in result["error"]["message"]


@pytest.mark.parametrize(
    "bad_path",
    [
        "../README.md",
        "..\\README.md",
        "tests/../../README.md",
        "tests\\..\\..\\README.md",
        "/etc",
        "C:\\Windows\\System32",
        "\\\\localhost\\c$\\Windows",
    ],
)
def test_list_files_rejects_escape_paths(bad_path: str) -> None:
    if bad_path.startswith("/etc") and platform.system().lower() == "windows":
        pytest.skip("POSIX absolute path on Windows")
    result = list_files(bad_path)
    assert result["ok"] is False
    err = result["error"]["message"].lower()
    payload = json.dumps(result, ensure_ascii=False).lower()
    assert "root=" not in payload
    assert any(
        token in err
        for token in (
            "workspace",
            "禁止",
            "使用できません",
            "..",
            "存在しません",
        )
    )


def test_list_files_error_serializable_for_llm() -> None:
    result = list_files("../outside")
    assert result["ok"] is False
    payload = json.dumps(result, ensure_ascii=False)
    parsed = json.loads(payload)
    assert parsed["ok"] is False
    assert "root=" not in payload.lower()


# --- Native Tool Calling ループ（Ollama 非依存） ---


def test_list_files_native_tool_calling_loop_mock() -> None:
    messages: list[dict] = [
        {"role": "user", "content": "tests/fixtures ディレクトリの中身を一覧して"},
    ]
    rec = execute_registry_tool("list_files", {"path": "tests/fixtures"})
    assert rec.ok is True
    messages.append(
        {
            "role": "tool",
            "tool_name": "list_files",
            "content": json.dumps(rec.result, ensure_ascii=False),
        }
    )
    content = messages[-1]["content"]
    assert "p2_read_file_sample.txt" in content
