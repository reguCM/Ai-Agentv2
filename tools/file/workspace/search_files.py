"""Workspace 内テキスト検索。"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from tools.file.workspace._paths import (
    SEARCH_MAX_FILE_BYTES,
    SEARCH_MAX_FILES_SCANNED,
    SEARCH_MAX_MATCHES,
    is_probably_binary,
    path_error,
    resolve_under_workspace,
    should_skip_dir,
    to_workspace_relative,
    workspace_root,
)


def search_files(query, path=".", glob=None, after=None):
    """
    Workspace 内を検索し、path・行番号・抜粋を返す。

    Args:
        query: 検索文字列（必須）
        path: Workspace内の相対検索起点（任意）
        glob: ファイル名 glob（任意、例: "*.py"）
        after: 直前ページの next_cursor。この相対パスより後の走査順から再開する。
    """
    if query is None or not str(query).strip():
        return path_error("query が空です", code="invalid_query")

    needle = str(query)
    base = resolve_under_workspace(path, allow_directory=True)
    if isinstance(base, dict):
        return base

    if not base.exists():
        return path_error("パスが存在しません", code="path_not_found", path=path)

    after_rel = None
    after_raw = str(after).strip() if after not in (None, "") else ""
    if after_raw:
        after_resolved = resolve_under_workspace(after_raw, allow_directory=False)
        if isinstance(after_resolved, dict):
            return after_resolved
        try:
            after_resolved.resolve().relative_to(base.resolve())
        except ValueError:
            return path_error(
                "after は検索 path 以下である必要があります",
                code="after_outside_path",
                path=after_raw,
            )
        after_rel = to_workspace_relative(after_resolved)

    pattern = str(glob).strip() if glob not in (None, "") else None
    matches = []
    files_scanned = 0
    truncated_matches = False
    truncated_scan = False
    last_scanned_path = None
    seen_after = after_rel is None
    excluded_reasons: dict[str, int] = {}
    skipped_reasons: dict[str, int] = {}

    def count(bucket: dict[str, int], reason: str) -> None:
        bucket[reason] = bucket.get(reason, 0) + 1

    files = _iter_files(base, excluded_reasons, skipped_reasons)
    for file_path in files:
        rel = to_workspace_relative(file_path)
        if not seen_after:
            if rel == after_rel:
                seen_after = True
            continue
        name = file_path.name
        if pattern and not fnmatch.fnmatch(name, pattern):
            count(excluded_reasons, "file_pattern")
            continue

        try:
            size = file_path.stat().st_size
        except OSError:
            count(skipped_reasons, "stat_failed")
            continue
        if size > SEARCH_MAX_FILE_BYTES:
            count(excluded_reasons, "oversized")
            continue
        try:
            binary = is_probably_binary(file_path)
        except OSError:
            count(skipped_reasons, "unreadable")
            continue
        if binary:
            count(excluded_reasons, "binary")
            continue
        if files_scanned >= SEARCH_MAX_FILES_SCANNED:
            truncated_scan = True
            break

        files_scanned += 1
        last_scanned_path = rel
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            count(skipped_reasons, "unreadable")
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            if needle not in line:
                continue
            matches.append(
                {
                    "path": rel,
                    "line": line_no,
                    "text": line[:400],
                }
            )
            if len(matches) >= SEARCH_MAX_MATCHES:
                truncated_matches = True
                if files_scanned >= SEARCH_MAX_FILES_SCANNED:
                    truncated_scan = True
                break
        if truncated_matches:
            break

    if after_rel is not None and not seen_after:
        return path_error(
            "after に指定したパスが走査順に現れませんでした",
            code="after_not_found",
            path=after_raw,
        )

    warnings = []
    if truncated_matches:
        warnings.append(
            {
                "code": "match_limit_reached",
                "message": f"マッチ数が上限 {SEARCH_MAX_MATCHES} に達したため打ち切りました",
                "details": {"match_count": len(matches), "limit": SEARCH_MAX_MATCHES},
            }
        )
    if truncated_scan:
        warnings.append(
            {
                "code": "scan_limit_reached",
                "message": f"走査ファイル数が上限 {SEARCH_MAX_FILES_SCANNED} に達したため打ち切りました",
                "details": {
                    "files_scanned": files_scanned,
                    "limit": SEARCH_MAX_FILES_SCANNED,
                },
            }
        )
    if skipped_reasons:
        warnings.append(
            {
                "code": "files_skipped",
                "message": "一部の検索対象ファイルを処理できませんでした",
                "details": {"total": sum(skipped_reasons.values())},
            }
        )

    partial = truncated_matches or truncated_scan or bool(skipped_reasons)
    next_cursor = last_scanned_path if truncated_matches or truncated_scan else None

    return {
        "ok": True,
        "status": "partial" if partial else "success",
        "query": needle,
        "base": to_workspace_relative(base),
        "glob": pattern,
        "after": after_rel,
        "files_scanned": files_scanned,
        "match_count": len(matches),
        "truncated": truncated_matches or truncated_scan,
        "has_more": truncated_matches or truncated_scan,
        "last_scanned_path": last_scanned_path,
        "next_cursor": next_cursor,
        "matches": matches,
        "excluded": {
            "total": sum(excluded_reasons.values()),
            "reasons": excluded_reasons,
        },
        "skipped": {
            "total": sum(skipped_reasons.values()),
            "reasons": skipped_reasons,
        },
        "error": None,
        "warnings": warnings,
    }


def _iter_files(
    base: Path,
    excluded_reasons: dict[str, int],
    skipped_reasons: dict[str, int],
):
    root = workspace_root().resolve()
    if base.is_file():
        yield base
        return

    import os

    def record_walk_error(_exc) -> None:
        skipped_reasons["directory_unreadable"] = (
            skipped_reasons.get("directory_unreadable", 0) + 1
        )

    for dirpath, dirnames, filenames in os.walk(base, onerror=record_walk_error):
        skipped_dirs = [d for d in dirnames if should_skip_dir(d)]
        if skipped_dirs:
            excluded_reasons["excluded_directory"] = (
                excluded_reasons.get("excluded_directory", 0) + len(skipped_dirs)
            )
        dirnames[:] = sorted(
            (d for d in dirnames if not should_skip_dir(d)), key=str.lower
        )
        current = Path(dirpath)
        try:
            current.resolve().relative_to(root)
        except ValueError:
            dirnames[:] = []
            continue
        for filename in sorted(filenames):
            yield current / filename
