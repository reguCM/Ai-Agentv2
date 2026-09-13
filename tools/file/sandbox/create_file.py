"""Create one new text file inside a Runtime-owned dedicated sandbox."""
from __future__ import annotations

import hashlib
from pathlib import Path

from tools.ai.sandbox_workspace import SandboxError, SandboxSession, resolve_sandbox_path
from tools.file.sandbox._result import failure, timestamp


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_file(path, content, *, sandbox_session: SandboxSession | None = None):
    if sandbox_session is None:
        return failure("sandbox_session_required", "Runtime-owned Sandbox Session is required.")
    if sandbox_session.session_kind != "DEDICATED":
        return failure("dedicated_sandbox_required", "A Dedicated Sandbox Session is required.")
    if not isinstance(path, str) or not path.strip():
        return failure("invalid_path", "path must be a non-empty relative string.")
    if not isinstance(content, str):
        return failure("invalid_content", "content must be a string.", path=path)
    try:
        target = resolve_sandbox_path(sandbox_session, path)
        if target.exists() or target.is_symlink():
            return failure("path_exists", "Existing files are not overwritten.", path=path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Re-resolve after parent creation so a junction/symlink cannot bypass the guard.
        target = resolve_sandbox_path(sandbox_session, path)
        data = content.encode("utf-8")
        with target.open("xb") as stream:
            stream.write(data)
    except FileExistsError:
        return failure("path_exists", "Existing files are not overwritten.", path=path)
    except (SandboxError, OSError) as exc:
        return failure("sandbox_path_rejected", str(exc), path=path)
    mutation = {
        "tool": "create_file",
        "sandbox_session_id": sandbox_session.session_id,
        "relative_path": path.replace("\\", "/"),
        "action": "create",
        "before_hash": None,
        "after_hash": _sha256(data),
        "changed": True,
        "timestamp": timestamp(),
    }
    return {
        "ok": True,
        "status": "success",
        "error": None,
        "warnings": [],
        "path": mutation["relative_path"],
        "mutation": mutation,
    }
