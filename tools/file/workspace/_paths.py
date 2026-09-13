"""
Workspace 固定 root とパス安全解決。

root は本リポジトリ（registry/tools.json がある場所）に固定し、cwd に依存しない。
"""

from __future__ import annotations

from pathlib import Path

EXCLUDE_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".cursor",
    }
)

LIST_MAX_ENTRIES = 500
READ_MAX_BYTES = 64 * 1024
SEARCH_MAX_FILES_SCANNED = 200
SEARCH_MAX_MATCHES = 50
# Runtime may resume search_files this many times after scan_limit_reached.
SEARCH_MAX_CONTINUATION_PAGES = 64
SEARCH_MAX_FILE_BYTES = 256 * 1024
BINARY_SNIFF_BYTES = 8192


def workspace_root() -> Path:
    # tools/file/workspace/_paths.py → parents[3] == リポジトリ root
    root = Path(__file__).resolve().parents[3]
    marker = root / "registry" / "tools.json"
    if not marker.is_file():
        raise RuntimeError(
            f"workspace root を特定できません: {root} "
            "(registry/tools.json が見つかりません)"
        )
    return root


def path_error(message: str, *, code: str = "invalid_path", path=None) -> dict:
    payload = {
        "ok": False,
        "status": "failure",
        "error": {"code": code, "message": message},
        "warnings": [],
    }
    if path is not None:
        payload["path"] = str(path)
    return payload


def resolve_under_workspace(path: str | None, *, allow_directory: bool = True) -> Path | dict:
    """
    path を workspace root 配下に解決する。
    失敗時は error dict を返す（黙って別場所へフォールバックしない）。
    """
    try:
        root = workspace_root().resolve()
    except RuntimeError:
        return path_error(
            "workspace root を特定できません",
            code="workspace_root_unavailable",
        )

    raw = "." if path is None else str(path).strip()
    if not raw:
        raw = "."

    # 明示的な .. セグメントを拒否（解決前）
    parts = Path(raw).parts
    if ".." in parts:
        return path_error("path に '..' は使用できません", path=raw)

    candidate = Path(raw)
    if candidate.is_absolute():
        return path_error("絶対パスは使用できません", code="absolute_path")
    resolved = (root / candidate).resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        return path_error(
            "workspace root 外へのアクセスは禁止です",
            code="workspace_boundary",
            path=raw,
        )

    if not allow_directory and resolved.exists() and resolved.is_dir():
        return path_error(
            "ディレクトリは指定できません",
            code="directory_not_allowed",
            path=raw,
        )

    return resolved


def to_workspace_relative(path: Path) -> str:
    root = workspace_root().resolve()
    resolved = path.resolve()
    return resolved.relative_to(root).as_posix()


def is_probably_binary(path: Path) -> bool:
    with path.open("rb") as handle:
        chunk = handle.read(BINARY_SNIFF_BYTES)
    if b"\x00" in chunk:
        return True
    # 高比率の非テキスト制御文字
    if not chunk:
        return False
    textish = sum(1 for b in chunk if b in (9, 10, 13) or 32 <= b <= 126 or b >= 128)
    return (textish / len(chunk)) < 0.85


def should_skip_dir(name: str) -> bool:
    return name in EXCLUDE_DIR_NAMES
