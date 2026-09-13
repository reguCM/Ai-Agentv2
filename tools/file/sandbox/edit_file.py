"""Perform one exact text replacement in a sandbox file."""
from __future__ import annotations

import hashlib

from tools.ai.sandbox_workspace import SandboxError, SandboxSession, resolve_sandbox_path
from tools.file.sandbox._result import failure, timestamp


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def edit_file(path, old_text, new_text, *, sandbox_session: SandboxSession | None = None):
    if sandbox_session is None:
        return failure("sandbox_session_required", "Runtime-owned Sandbox Session is required.")
    if sandbox_session.session_kind != "DEDICATED":
        return failure("dedicated_sandbox_required", "A Dedicated Sandbox Session is required.")
    if not isinstance(path, str) or not path.strip():
        return failure("invalid_path", "path must be a non-empty relative string.")
    if not isinstance(old_text, str) or not old_text:
        return failure("invalid_old_text", "old_text must be a non-empty string.", path=path)
    if not isinstance(new_text, str):
        return failure("invalid_new_text", "new_text must be a string.", path=path)
    try:
        target = resolve_sandbox_path(sandbox_session, path, must_exist=True)
        if not target.is_file():
            return failure("not_a_file", "The target must be an existing file.", path=path)
        before = target.read_bytes()
        if b"\x00" in before:
            return failure("binary_file", "Binary files cannot be edited.", path=path)
        try:
            text = before.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return failure("decode_failed", "The file is not valid UTF-8 text.", path=path)
        matches = text.count(old_text)
        if matches == 0:
            return failure("old_text_not_found", "old_text was not found.", path=path)
        if matches > 1:
            return failure(
                "old_text_not_unique",
                "old_text must match exactly once.",
                path=path,
                match_count=matches,
            )
        after = text.replace(old_text, new_text, 1).encode("utf-8")
        # Revalidate identity and containment immediately before mutation.
        target = resolve_sandbox_path(sandbox_session, path, must_exist=True)
        target.write_bytes(after)
    except (SandboxError, OSError) as exc:
        return failure("sandbox_path_rejected", str(exc), path=path)
    mutation = {
        "tool": "edit_file",
        "sandbox_session_id": sandbox_session.session_id,
        "relative_path": path.replace("\\", "/"),
        "action": "exact_replace",
        "before_hash": _sha256(before),
        "after_hash": _sha256(after),
        "changed": before != after,
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
