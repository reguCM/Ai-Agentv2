"""Workspace 内テキストファイルの読取。"""

from __future__ import annotations

from tools.file.workspace._paths import (
    READ_MAX_BYTES,
    is_probably_binary,
    path_error,
    resolve_under_workspace,
    to_workspace_relative,
)


def read_file(path, offset=None, limit=None):
    """
    Workspace 内のテキストファイルを読む。

    Args:
        path: Workspace内の相対ファイルパス
        offset: 開始行（1-based、任意）
        limit: 返す最大行数（任意）
    """
    target = resolve_under_workspace(path, allow_directory=False)
    if isinstance(target, dict):
        return target

    if not target.exists():
        return path_error("ファイルが存在しません", code="path_not_found", path=path)
    if not target.is_file():
        return path_error("通常ファイルではありません", code="not_a_file", path=path)

    try:
        size = target.stat().st_size
    except OSError:
        return path_error("stat に失敗しました", code="stat_failed", path=path)

    if size > READ_MAX_BYTES:
        return path_error(
            f"ファイルサイズが上限 {READ_MAX_BYTES} bytes を超えています (size={size})",
            code="file_too_large",
            path=path,
        )

    try:
        binary = is_probably_binary(target)
    except OSError:
        return path_error("読取に失敗しました", code="read_failed", path=path)
    if binary:
        return path_error("バイナリファイルは読めません", code="binary_file", path=path)

    start_line = 1
    if offset is not None:
        try:
            start_line = int(offset)
        except (TypeError, ValueError):
            return path_error(
                f"offset が不正です: {offset!r}",
                code="invalid_offset",
                path=path,
            )
        if start_line < 1:
            return path_error(
                "offset は 1 以上である必要があります",
                code="invalid_offset",
                path=path,
            )

    max_lines = None
    if limit is not None:
        try:
            max_lines = int(limit)
        except (TypeError, ValueError):
            return path_error(
                f"limit が不正です: {limit!r}",
                code="invalid_limit",
                path=path,
            )
        if max_lines < 1:
            return path_error(
                "limit は 1 以上である必要があります",
                code="invalid_limit",
                path=path,
            )

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path_error("読取に失敗しました", code="read_failed", path=path)

    all_lines = text.splitlines()
    total_lines = len(all_lines)
    # offset が末尾を超える場合は空（エラーではなく範囲外の空結果）
    if start_line > total_lines:
        selected = []
        end_line = start_line - 1
    else:
        slice_start = start_line - 1
        if max_lines is None:
            selected = all_lines[slice_start:]
        else:
            selected = all_lines[slice_start : slice_start + max_lines]
        end_line = start_line + len(selected) - 1 if selected else start_line - 1

    lines = [{"line": start_line + i, "text": line} for i, line in enumerate(selected)]
    has_more = end_line < total_lines

    return {
        "ok": True,
        "status": "success",
        "path": to_workspace_relative(target),
        "size_bytes": size,
        "total_lines": total_lines,
        "offset": start_line,
        "limit": max_lines,
        "returned_lines": len(lines),
        "lines": lines,
        "truncated": False,
        "has_more": has_more,
        "next_offset": end_line + 1 if has_more else None,
        "error": None,
        "warnings": [],
    }
