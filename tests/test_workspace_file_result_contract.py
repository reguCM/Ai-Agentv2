from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tools.system.tool_result_contract import validate_tool_result_v1


paths_module = importlib.import_module("tools.file.workspace._paths")
read_module = importlib.import_module("tools.file.workspace.read_file")
list_module = importlib.import_module("tools.file.workspace.list_files")
search_module = importlib.import_module("tools.file.workspace.search_files")


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "registry").mkdir()
    (tmp_path / "registry" / "tools.json").write_text("{}", encoding="utf-8")
    for module in (paths_module, list_module, search_module):
        monkeypatch.setattr(module, "workspace_root", lambda root=tmp_path: root)
    return tmp_path


def assert_v1(result: dict) -> None:
    assert validate_tool_result_v1(result) == []


def test_read_file_success_pagination_and_eof(workspace: Path) -> None:
    (workspace / "sample.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")

    page = read_module.read_file("sample.txt", offset=1, limit=2)
    assert_v1(page)
    assert page["status"] == "success"
    assert page["truncated"] is False
    assert page["has_more"] is True
    assert page["next_offset"] == 3

    final = read_module.read_file("sample.txt", offset=3, limit=2)
    assert_v1(final)
    assert final["has_more"] is False
    assert final["next_offset"] is None


@pytest.mark.parametrize(
    "path",
    ["missing.txt", "registry", "../outside.txt"],
)
def test_read_file_failures_are_strict_v1(workspace: Path, path: str) -> None:
    assert_v1(read_module.read_file(path))
    assert read_module.read_file(path)["status"] == "failure"


def test_read_file_binary_and_size_limit_are_failures(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (workspace / "binary.bin").write_bytes(b"\x00")
    (workspace / "large.txt").write_text("abcd", encoding="utf-8")
    monkeypatch.setattr(read_module, "READ_MAX_BYTES", 3)

    binary = read_module.read_file("binary.bin")
    large = read_module.read_file("large.txt")
    assert binary["error"]["code"] == "binary_file"
    assert large["error"]["code"] == "file_too_large"
    assert_v1(binary)
    assert_v1(large)


def test_absolute_path_is_rejected_even_inside_workspace(workspace: Path) -> None:
    target = workspace / "sample.txt"
    target.write_text("text", encoding="utf-8")
    result = read_module.read_file(str(target))
    assert result["error"]["code"] == "absolute_path"
    assert_v1(result)


def test_list_files_success_empty_and_deterministic_order(workspace: Path) -> None:
    (workspace / "empty").mkdir()
    assert list_module.list_files("empty")["entries"] == []

    (workspace / "listing").mkdir()
    (workspace / "listing" / "z.txt").write_text("z", encoding="utf-8")
    (workspace / "listing" / "a.txt").write_text("a", encoding="utf-8")
    (workspace / "listing" / "dir").mkdir()
    result = list_module.list_files("listing")
    assert_v1(result)
    assert result["status"] == "success"
    assert [item["name"] for item in result["entries"]] == ["dir", "a.txt", "z.txt"]


def test_list_files_limit_is_partial(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (workspace / "listing").mkdir()
    for name in ("a.txt", "b.txt", "c.txt"):
        (workspace / "listing" / name).write_text(name, encoding="utf-8")
    monkeypatch.setattr(list_module, "LIST_MAX_ENTRIES", 2)

    result = list_module.list_files("listing")
    assert_v1(result)
    assert result["status"] == "partial"
    assert result["error"] is None
    assert result["truncated"] is True
    assert result["has_more"] is True
    assert result["warnings"][0]["code"] == "entry_limit_reached"


def test_list_files_failures_are_strict_v1(workspace: Path) -> None:
    (workspace / "file.txt").write_text("text", encoding="utf-8")
    for path in ("missing", "file.txt", "../outside"):
        assert_v1(list_module.list_files(path))


def test_search_success_empty_match_and_path_handoff(workspace: Path) -> None:
    (workspace / "a.txt").write_text("needle\n", encoding="utf-8")
    found = search_module.search_files("needle")
    missing = search_module.search_files("absent")

    assert_v1(found)
    assert_v1(missing)
    assert found["status"] == "success"
    assert missing["match_count"] == 0
    handoff = read_module.read_file(found["matches"][0]["path"])
    assert_v1(handoff)
    assert handoff["lines"][0]["text"] == "needle"


def test_list_to_read_path_handoff(workspace: Path) -> None:
    (workspace / "a.txt").write_text("content", encoding="utf-8")
    listed = list_module.list_files(".")
    item = next(entry for entry in listed["entries"] if entry["name"] == "a.txt")
    assert read_module.read_file(item["path"])["ok"] is True


def test_search_scan_limit_is_partial(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for index in range(3):
        (workspace / f"{index}.txt").write_text("text", encoding="utf-8")
    monkeypatch.setattr(search_module, "SEARCH_MAX_FILES_SCANNED", 2)
    result = search_module.search_files("absent")
    assert_v1(result)
    assert result["status"] == "partial"
    assert result["has_more"] is True
    assert result["next_cursor"] == "1.txt"
    assert result["last_scanned_path"] == "1.txt"
    assert {warning["code"] for warning in result["warnings"]} == {
        "scan_limit_reached"
    }


def test_search_scan_resumes_after_cursor(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for index in range(3):
        (workspace / f"{index}.txt").write_text("text", encoding="utf-8")
    (workspace / "2.txt").write_text("needle", encoding="utf-8")
    monkeypatch.setattr(search_module, "SEARCH_MAX_FILES_SCANNED", 2)
    first = search_module.search_files("needle")
    assert first["match_count"] == 0
    assert first["next_cursor"] == "1.txt"
    second = search_module.search_files("needle", after=first["next_cursor"])
    assert_v1(second)
    assert second["has_more"] is False
    assert second["next_cursor"] is None
    assert second["match_count"] == 1
    assert second["matches"][0]["path"] == "2.txt"


def test_search_match_limit_resumes_after_cursor(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(3):
        (workspace / f"{index}.txt").write_text("needle\n", encoding="utf-8")
    monkeypatch.setattr(search_module, "SEARCH_MAX_MATCHES", 2)
    first = search_module.search_files("needle")
    assert first["has_more"] is True
    assert first["next_cursor"]
    assert {warning["code"] for warning in first["warnings"]} == {"match_limit_reached"}
    second = search_module.search_files("needle", after=first["next_cursor"])
    assert_v1(second)
    assert second["match_count"] >= 1
    assert "2.txt" in {item["path"] for item in second["matches"]}


def test_search_match_and_scan_limits_can_both_be_reported(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(2):
        (workspace / f"{index}.txt").write_text("needle", encoding="utf-8")
    monkeypatch.setattr(search_module, "SEARCH_MAX_FILES_SCANNED", 2)
    monkeypatch.setattr(search_module, "SEARCH_MAX_MATCHES", 2)
    result = search_module.search_files("needle")
    assert_v1(result)
    assert {warning["code"] for warning in result["warnings"]} == {
        "scan_limit_reached",
        "match_limit_reached",
    }


def test_search_reports_excluded_binary_oversized_and_directory(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (workspace / "binary.bin").write_bytes(b"\x00")
    (workspace / "large.txt").write_text("large", encoding="utf-8")
    (workspace / ".git").mkdir()
    (workspace / ".git" / "secret.txt").write_text("needle", encoding="utf-8")
    monkeypatch.setattr(search_module, "SEARCH_MAX_FILE_BYTES", 4)

    result = search_module.search_files("needle")
    assert_v1(result)
    assert result["status"] == "success"
    assert result["excluded"]["reasons"] == {
        "excluded_directory": 1,
        "oversized": 1,
        "binary": 1,
    }


def test_search_read_failure_is_skipped_partial(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = workspace / "unreadable.txt"
    target.write_text("needle", encoding="utf-8")
    original = Path.read_text

    def fail_selected(path: Path, *args, **kwargs):
        if path == target:
            raise PermissionError("denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_selected)
    result = search_module.search_files("needle")
    assert_v1(result)
    assert result["status"] == "partial"
    assert result["truncated"] is False
    assert result["skipped"] == {"total": 1, "reasons": {"unreadable": 1}}
    assert result["warnings"][0]["code"] == "files_skipped"


def test_search_traversal_is_deterministic(workspace: Path) -> None:
    for directory in ("z", "a"):
        (workspace / directory).mkdir()
        (workspace / directory / "match.txt").write_text("needle", encoding="utf-8")
    result = search_module.search_files("needle")
    assert [match["path"] for match in result["matches"]] == [
        "a/match.txt",
        "z/match.txt",
    ]


def test_search_failure_results_are_strict_v1(workspace: Path) -> None:
    for result in (
        search_module.search_files(""),
        search_module.search_files("x", path="missing"),
        search_module.search_files("x", path="../outside"),
    ):
        assert result["status"] == "failure"
        assert_v1(result)
