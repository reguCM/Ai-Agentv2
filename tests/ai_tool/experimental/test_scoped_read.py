from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_tool.experimental.scoped_read.config import load_scoped_read_config
from ai_tool.experimental.scoped_read.reader import workspace_read_text_scoped


def _read(path: str, *, mini_repo: Path, mini_config_path: Path, **kwargs):
    cfg = load_scoped_read_config(repo_root=mini_repo, config_path=mini_config_path)
    return workspace_read_text_scoped(
        path,
        audit=False,
        config=cfg,
        **kwargs,
    )


# --- Normal ---


def test_normal_text_file(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool/sample.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is True
    assert result["content"] == "hello\nworld"
    assert result["root_id"] == "ai_tool_docs"
    assert result["error"] is None


def test_normal_md_json_txt(mini_repo: Path, mini_config_path: Path) -> None:
    for name in ("sample.md", "sample.json", "sample.txt"):
        result = _read(f"docs/ai_tool/{name}", mini_repo=mini_repo, mini_config_path=mini_config_path)
        assert result["ok"] is True, name


def test_normal_unicode(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool/unicode.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is True
    assert "日本語" in result["content"]


def test_normal_empty_file(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool/empty.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is True
    assert result["content"] == ""
    assert result["total_lines"] == 0


def test_normal_specs_root(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read(
        "docs/ai_tool/tool_creation/specs/spec.json",
        mini_repo=mini_repo,
        mini_config_path=mini_config_path,
    )
    assert result["ok"] is True
    assert result["root_id"] == "tool_creation_specs"


def test_real_repo_allowlisted_file(repo_root: Path) -> None:
    cfg = load_scoped_read_config(repo_root=repo_root)
    result = workspace_read_text_scoped(
        "docs/ai_tool/README.md",
        audit=False,
        config=cfg,
    )
    assert result["ok"] is True
    assert result["root_id"] == "ai_tool_docs"


# --- Boundary ---


def test_boundary_allowlist_root_file(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool/sample.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is True


def test_boundary_nested_under_root(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read(
        "docs/ai_tool/subdir/nested.txt",
        mini_repo=mini_repo,
        mini_config_path=mini_config_path,
    )
    assert result["ok"] is True


def test_boundary_max_size_exact(mini_repo: Path, mini_config_path: Path) -> None:
    exact = mini_repo / "docs" / "ai_tool" / "exact.bin"
    exact.write_bytes(b"a" * 65536)
    result = _read("docs/ai_tool/exact.bin", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is True
    assert result["size_bytes"] == 65536


def test_boundary_max_size_exceeded(mini_repo: Path, mini_config_path: Path) -> None:
    over = mini_repo / "docs" / "ai_tool" / "over.bin"
    over.write_bytes(b"a" * 65537)
    result = _read("docs/ai_tool/over.bin", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert "size exceeds max_bytes" in result["error"]


def test_boundary_offset_limit(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read(
        "docs/ai_tool/sample.txt",
        mini_repo=mini_repo,
        mini_config_path=mini_config_path,
        offset=2,
        limit=1,
    )
    assert result["ok"] is True
    assert result["content"] == "world"
    assert result["offset"] == 2
    assert result["limit"] == 1


def test_boundary_default_line_limit_truncates(mini_repo: Path, mini_config_path: Path) -> None:
    many = mini_repo / "docs" / "ai_tool" / "many.txt"
    many.write_text("\n".join(f"line{i}" for i in range(600)), encoding="utf-8")
    result = _read("docs/ai_tool/many.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is True
    assert result["returned_lines"] == 500
    assert result["truncated"] is True
    assert result["limit"] is None


# --- Invalid ---


def test_invalid_empty_path(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert "invalid input" in result["error"]


def test_invalid_whitespace_path(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("   ", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False


def test_invalid_not_found(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool/missing.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert result["error"] == "file not found"


def test_invalid_directory(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool/dir_only", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert result["error"] == "not a file"


def test_invalid_bad_offset(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read(
        "docs/ai_tool/sample.txt",
        mini_repo=mini_repo,
        mini_config_path=mini_config_path,
        offset=0,
    )
    assert result["ok"] is False


def test_invalid_bad_limit(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read(
        "docs/ai_tool/sample.txt",
        mini_repo=mini_repo,
        mini_config_path=mini_config_path,
        limit=-1,
    )
    assert result["ok"] is False


# --- Safety ---


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside/secret.txt",
        "../../outside/secret.txt",
        "docs/../outside/secret.txt",
        "docs/../../outside/secret.txt",
    ],
)
def test_safety_traversal_rejected(
    mini_repo: Path,
    mini_config_path: Path,
    bad_path: str,
) -> None:
    result = _read(bad_path, mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert result["error"] == "path traversal"


def test_safety_outside_allowlist_prefix_trap(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool_evil/trap.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert result["error"] == "path outside allowlist"


def test_safety_outside_allowlist_repo_file(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("outside/secret.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert result["error"] == "path outside allowlist"


def test_safety_absolute_path_inside_allowlist(mini_repo: Path, mini_config_path: Path) -> None:
    target = mini_repo / "docs" / "ai_tool" / "sample.txt"
    result = _read(str(target), mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is True


def test_safety_absolute_path_outside_repo(mini_repo: Path, mini_config_path: Path) -> None:
    outside = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "win.ini"
    if not outside.is_file():
        pytest.skip("system file unavailable for absolute path test")
    result = _read(str(outside), mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert result["error"] == "path outside allowlist"


def test_safety_symlink_escape_rejected(
    mini_repo: Path,
    mini_config_path: Path,
    symlink_escape: Path | None,
) -> None:
    if symlink_escape is None:
        pytest.skip("symlink creation not supported on this platform")
    result = _read("docs/ai_tool/link.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert result["error"] == "path outside allowlist"


def test_safety_no_write_operations(mini_repo: Path, mini_config_path: Path) -> None:
    fn = workspace_read_text_scoped
    forbidden = ("write", "delete", "rename", "move", "append", "modify", "chmod")
    for name in forbidden:
        assert not hasattr(fn, name)


def test_safety_binary_rejected(mini_repo: Path, mini_config_path: Path) -> None:
    binary = mini_repo / "docs" / "ai_tool" / "binary.dat"
    binary.write_bytes(b"\x00\x01\x02\x03")
    result = _read("docs/ai_tool/binary.dat", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert result["error"] == "binary file"


# --- Failure / permission ---


def test_failure_io_unreadable_file(mini_repo: Path, mini_config_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("chmod-based permission test unreliable on Windows")
    unreadable = mini_repo / "docs" / "ai_tool" / "locked.txt"
    unreadable.write_text("secret\n", encoding="utf-8")
    unreadable.chmod(0o000)
    try:
        result = _read("docs/ai_tool/locked.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
        assert result["ok"] is False
        assert "permission denied" in result["error"]
    finally:
        unreadable.chmod(0o644)


# --- Output contract ---


def test_output_contract_success_keys(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool/sample.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    for key in (
        "ok",
        "path",
        "root_id",
        "size_bytes",
        "total_lines",
        "offset",
        "limit",
        "returned_lines",
        "content",
        "truncated",
        "error",
    ):
        assert key in result


def test_output_contract_error_keys(mini_repo: Path, mini_config_path: Path) -> None:
    result = _read("docs/ai_tool/missing.txt", mini_repo=mini_repo, mini_config_path=mini_config_path)
    assert result["ok"] is False
    assert "path" in result
    assert "error" in result
    assert result.get("content") is None or "content" not in result or result["content"] is None
