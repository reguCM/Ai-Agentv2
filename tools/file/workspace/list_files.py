"""Workspace 内のファイル・ディレクトリ一覧。"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from tools.file.workspace._paths import (
    LIST_MAX_ENTRIES,
    path_error,
    resolve_under_workspace,
    should_skip_dir,
    to_workspace_relative,
    workspace_root,
)


def list_files(path=".", recursive=False, glob=None):
    """
    Workspace 内のエントリを一覧する。

    Args:
        path: 起点となるWorkspace内の相対パス
        recursive: True なら再帰
        glob: 任意。ファイル名に対する glob パターン（例: "*.py"）
    """
    base = resolve_under_workspace(path, allow_directory=True)
    if isinstance(base, dict):
        return base

    if not base.exists():
        return path_error("パスが存在しません", code="path_not_found", path=path)
    if not base.is_dir():
        return path_error(
            "list_files の path はディレクトリである必要があります",
            code="directory_required",
            path=path,
        )

    pattern = str(glob).strip() if glob not in (None, "") else None
    entries = []
    truncated = False
    walk_errors = 0

    def consider(item: Path):
        nonlocal truncated
        name = item.name
        if pattern and not fnmatch.fnmatch(name, pattern):
            return True
        if len(entries) >= LIST_MAX_ENTRIES:
            truncated = True
            return False
        kind = "dir" if item.is_dir() else "file"
        entries.append(
            {
                "path": to_workspace_relative(item),
                "name": name,
                "type": kind,
            }
        )
        return True

    def _record_walk_error() -> None:
        nonlocal walk_errors
        walk_errors += 1

    try:
        if recursive:
            stop = False
            for dirpath, dirnames, filenames in _walk(base, _record_walk_error):
                if stop:
                    break
                dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
                current = Path(dirpath)
                for dirname in sorted(dirnames):
                    if not consider(current / dirname):
                        stop = True
                        break
                if stop:
                    break
                for filename in sorted(filenames):
                    if not consider(current / filename):
                        stop = True
                        break
        else:
            for item in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if item.is_dir() and should_skip_dir(item.name):
                    continue
                if not consider(item):
                    break
    except OSError:
        return path_error("一覧取得に失敗しました", code="list_failed", path=path)

    if walk_errors and not entries:
        return path_error("一覧取得に失敗しました", code="list_failed", path=path)

    warnings = []
    if truncated:
        warnings.append(
            {
                "code": "entry_limit_reached",
                "message": f"件数が上限 {LIST_MAX_ENTRIES} に達したため打ち切りました",
                "details": {"count": len(entries), "limit": LIST_MAX_ENTRIES},
            }
        )
    if walk_errors:
        warnings.append(
            {
                "code": "directories_skipped",
                "message": "一部のディレクトリを列挙できませんでした",
                "details": {"count": walk_errors},
            }
        )

    partial = truncated or bool(walk_errors)

    return {
        "ok": True,
        "status": "partial" if partial else "success",
        "root": to_workspace_relative(workspace_root()),
        "base": to_workspace_relative(base),
        "recursive": bool(recursive),
        "glob": pattern,
        "count": len(entries),
        "truncated": truncated,
        "has_more": truncated,
        "next_cursor": None,
        "entries": entries,
        "error": None,
        "warnings": warnings,
    }


def _walk(base: Path, on_error):
    # os.walk 互換だが Path ベース
    import os

    return os.walk(base, onerror=lambda _exc: on_error())
