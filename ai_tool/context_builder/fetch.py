from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_tool.experimental.scoped_read.config import load_scoped_read_config
from ai_tool.experimental.scoped_read.reader import workspace_read_text_scoped


def fetch_allowlisted_content(
    path: str,
    *,
    repo_root: Path,
    audit: bool = False,
    audit_log: Path | None = None,
) -> dict[str, Any]:
    """Fetch file content via scoped read only. Never bypasses allowlist."""
    cfg = load_scoped_read_config(repo_root=repo_root)
    return workspace_read_text_scoped(
        path,
        config=cfg,
        audit=audit,
        audit_log=audit_log,
    )


def fetch_selected_contents(
    paths: list[str],
    *,
    repo_root: Path,
    compression: str = "full",
    audit: bool = False,
    audit_log: Path | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Return (content_map, errors_map).
    compression=none skips body fetch (manifest-only).
    """
    if compression == "none":
        return {}, {}

    content: dict[str, str] = {}
    errors: dict[str, str] = {}
    for path in sorted(set(paths)):
        result = fetch_allowlisted_content(
            path,
            repo_root=repo_root,
            audit=audit,
            audit_log=audit_log,
        )
        if result.get("ok"):
            content[path] = str(result.get("content") or "")
        else:
            errors[path] = str(result.get("error") or "fetch failed")
    return content, errors
