from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_tool.core.audit import append_audit
from ai_tool.experimental.scoped_read.config import (
    ScopedReadConfig,
    default_allowlist_config_path,
    load_scoped_read_config,
)
from ai_tool.experimental.scoped_read.paths import (
    find_repo_root,
    has_parent_segment,
    is_probably_binary,
    match_allowlist_root,
    resolve_repo_path,
    to_repo_relative,
)


def _error(
    *,
    path: str,
    error: str,
    content: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "path": path,
        "error": error,
        "content": content,
    }


def _success(
    *,
    path: str,
    root_id: str,
    size_bytes: int,
    total_lines: int,
    offset: int,
    limit: int | None,
    returned_lines: int,
    content: str,
    truncated: bool,
) -> dict[str, Any]:
    return {
        "ok": True,
        "path": path,
        "root_id": root_id,
        "size_bytes": size_bytes,
        "total_lines": total_lines,
        "offset": offset,
        "limit": limit,
        "returned_lines": returned_lines,
        "content": content,
        "truncated": truncated,
        "error": None,
    }


def _audit_event(
    *,
    requested_path: str,
    resolved_path: str | None,
    allowlist_root_id: str | None,
    allowlist_decision: str,
    result: dict[str, Any],
    failure_reason: str | None,
    audit_log: Path | None = None,
) -> None:
    kwargs: dict[str, Any] = {}
    if audit_log is not None:
        kwargs["log_path"] = audit_log
    append_audit(
        {
            "event": "scoped_read_execution",
            "tool_id": "local:workspace_read_text_scoped",
            "requested_path": requested_path,
            "resolved_path": resolved_path,
            "allowlist_root_id": allowlist_root_id,
            "allowlist_decision": allowlist_decision,
            "ok": result.get("ok"),
            "final_status": "OK" if result.get("ok") else "REJECTED",
            "failure_reason": failure_reason,
            "error": result.get("error"),
        },
        **kwargs,
    )


def workspace_read_text_scoped(
    path: str | None = None,
    offset: int | None = None,
    limit: int | None = None,
    *,
    config: ScopedReadConfig | None = None,
    audit: bool = True,
    audit_log: Path | None = None,
) -> dict[str, Any]:
    """
    Read a text file within experimental allowlist roots (read-only).

    Configuration is loaded from allowed_roots.experimental.json unless `config`
    is supplied (used by isolated tests).
    """
    requested = "" if path is None else str(path)

    def finish(
        result: dict[str, Any],
        *,
        resolved_path: str | None = None,
        allowlist_root_id: str | None = None,
        allowlist_decision: str,
        failure_reason: str | None = None,
    ) -> dict[str, Any]:
        if audit:
            _audit_event(
                requested_path=requested,
                resolved_path=resolved_path,
                allowlist_root_id=allowlist_root_id,
                allowlist_decision=allowlist_decision,
                result=result,
                failure_reason=failure_reason,
                audit_log=audit_log,
            )
        return result

    if not requested.strip():
        result = _error(path=requested, error="invalid input: path is required")
        return finish(
            result,
            allowlist_decision="reject",
            failure_reason="INVALID_INPUT",
        )

    try:
        cfg = config or load_scoped_read_config(repo_root=find_repo_root())
    except (RuntimeError, ValueError, OSError) as exc:
        result = _error(path=requested, error=f"configuration error: {exc}")
        return finish(
            result,
            allowlist_decision="reject",
            failure_reason="CONFIG_ERROR",
        )

    rules = cfg.path_rules
    limits = cfg.limits

    if rules.reject_parent_segments and has_parent_segment(requested):
        result = _error(path=requested, error="path traversal")
        return finish(
            result,
            allowlist_decision="reject",
            failure_reason="PATH_TRAVERSAL",
        )

    try:
        logical = resolve_repo_path(requested, cfg.repo_root)
    except OSError as exc:
        result = _error(path=requested, error=f"invalid input: {exc}")
        return finish(
            result,
            allowlist_decision="reject",
            failure_reason="INVALID_INPUT",
        )

    repo_root = cfg.repo_root.resolve()
    try:
        logical.relative_to(repo_root)
    except ValueError:
        result = _error(path=requested, error="path outside allowlist")
        return finish(
            result,
            resolved_path=str(logical),
            allowlist_decision="reject",
            failure_reason="PATH_OUTSIDE_REPO",
        )

    if rules.reject_symlink_escape:
        try:
            resolved = logical.resolve(strict=False)
        except OSError as exc:
            result = _error(path=requested, error=f"read failed: {exc}")
            return finish(
                result,
                resolved_path=str(logical),
                allowlist_decision="reject",
                failure_reason="READ_FAILED",
            )
    else:
        resolved = logical

    rel_display = to_repo_relative(resolved, repo_root)
    root_id = match_allowlist_root(resolved, cfg.resolved_roots)
    if root_id is None:
        result = _error(path=requested, error="path outside allowlist")
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_decision="reject",
            failure_reason="PATH_OUTSIDE_ALLOWLIST",
        )

    if not resolved.exists():
        result = _error(path=requested, error="file not found")
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_root_id=root_id,
            allowlist_decision="reject",
            failure_reason="NOT_FOUND",
        )

    if resolved.is_dir():
        result = _error(path=requested, error="not a file")
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_root_id=root_id,
            allowlist_decision="reject",
            failure_reason="NOT_A_FILE",
        )

    if not resolved.is_file():
        result = _error(path=requested, error="not a file")
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_root_id=root_id,
            allowlist_decision="reject",
            failure_reason="NOT_A_FILE",
        )

    try:
        size_bytes = resolved.stat().st_size
    except OSError as exc:
        result = _error(path=requested, error=f"permission denied: {exc}")
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_root_id=root_id,
            allowlist_decision="reject",
            failure_reason="PERMISSION_DENIED",
        )

    if size_bytes > limits.max_bytes:
        result = _error(
            path=requested,
            error=f"size exceeds max_bytes (size={size_bytes}, limit={limits.max_bytes})",
        )
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_root_id=root_id,
            allowlist_decision="reject",
            failure_reason="LIMIT_EXCEEDED",
        )

    if is_probably_binary(resolved):
        result = _error(path=requested, error="binary file")
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_root_id=root_id,
            allowlist_decision="reject",
            failure_reason="BINARY_FILE",
        )

    start_line = 1
    if offset is not None:
        try:
            start_line = int(offset)
        except (TypeError, ValueError):
            result = _error(path=requested, error=f"invalid input: offset={offset!r}")
            return finish(
                result,
                resolved_path=rel_display,
                allowlist_root_id=root_id,
                allowlist_decision="reject",
                failure_reason="INVALID_INPUT",
            )
        if start_line < 1:
            result = _error(path=requested, error="invalid input: offset must be >= 1")
            return finish(
                result,
                resolved_path=rel_display,
                allowlist_root_id=root_id,
                allowlist_decision="reject",
                failure_reason="INVALID_INPUT",
            )

    user_limit: int | None
    if limit is not None:
        try:
            user_limit = int(limit)
        except (TypeError, ValueError):
            result = _error(path=requested, error=f"invalid input: limit={limit!r}")
            return finish(
                result,
                resolved_path=rel_display,
                allowlist_root_id=root_id,
                allowlist_decision="reject",
                failure_reason="INVALID_INPUT",
            )
        if user_limit < 1:
            result = _error(path=requested, error="invalid input: limit must be >= 1")
            return finish(
                result,
                resolved_path=rel_display,
                allowlist_root_id=root_id,
                allowlist_decision="reject",
                failure_reason="INVALID_INPUT",
            )
        effective_max_lines = user_limit
    else:
        user_limit = None
        effective_max_lines = limits.max_lines_default

    try:
        text = resolved.read_text(encoding=limits.encoding, errors=limits.encoding_errors)
    except OSError as exc:
        result = _error(path=requested, error=f"permission denied: {exc}")
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_root_id=root_id,
            allowlist_decision="reject",
            failure_reason="PERMISSION_DENIED",
        )
    except UnicodeDecodeError as exc:
        result = _error(path=requested, error=f"encoding error: {exc}")
        return finish(
            result,
            resolved_path=rel_display,
            allowlist_root_id=root_id,
            allowlist_decision="reject",
            failure_reason="ENCODING_ERROR",
        )

    all_lines = text.splitlines()
    total_lines = len(all_lines)
    truncated = False

    if start_line > total_lines:
        selected: list[str] = []
    else:
        slice_start = start_line - 1
        selected = all_lines[slice_start : slice_start + effective_max_lines]
        if len(selected) < len(all_lines[slice_start:]):
            truncated = True

    content = "\n".join(selected)
    result = _success(
        path=rel_display,
        root_id=root_id,
        size_bytes=size_bytes,
        total_lines=total_lines,
        offset=start_line,
        limit=user_limit,
        returned_lines=len(selected),
        content=content,
        truncated=truncated,
    )
    return finish(
        result,
        resolved_path=rel_display,
        allowlist_root_id=root_id,
        allowlist_decision="allow",
        failure_reason=None,
    )


def default_config() -> ScopedReadConfig:
    root = find_repo_root()
    return load_scoped_read_config(
        repo_root=root,
        config_path=default_allowlist_config_path(root),
    )
